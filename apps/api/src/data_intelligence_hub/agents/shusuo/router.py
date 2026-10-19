"""数说飞书机器人的 FastAPI 路由。

端点：
  POST /api/agents/shusuo/webhook   飞书事件推送（含 URL 校验）
  GET  /api/agents/shusuo/health    配置自检（不返回密钥）
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from fastapi.responses import JSONResponse

from . import commands, lark_client
from .config import get_shushuo_config
from .crypto import FeishuCryptoError, decrypt_event, verify_signature

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["shusuo"])

_DEDUPE_LIMIT = 1024
_DEDUPE_TTL_SECONDS = 600
_seen_events: OrderedDict[str, float] = OrderedDict()

_MAX_REPLY_CHARS = 6000


def _is_duplicate(event_id: str) -> bool:
    if not event_id:
        return False
    now = time.time()
    while _seen_events:
        oldest_id, seen_at = next(iter(_seen_events.items()))
        if now - seen_at <= _DEDUPE_TTL_SECONDS and len(_seen_events) < _DEDUPE_LIMIT:
            break
        _seen_events.popitem(last=False)
    if event_id in _seen_events:
        return True
    _seen_events[event_id] = now
    return False


def _json(data: dict[str, Any], status_code: int = 200) -> Response:
    return JSONResponse(content=data, status_code=status_code)


@router.get("/health")
async def shusuo_health() -> dict[str, Any]:
    config = get_shushuo_config()
    return {
        "app_id": config.app_id,
        "ready": config.ready,
        "encrypt_enabled": config.encrypt_enabled,
        "verification_token_configured": bool(config.verification_token),
        "default_project_id": config.default_project_id,
        "allowlist_size": len(config.allowed_open_ids),
    }


@router.post("/webhook")
async def shusuo_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lark_signature: str | None = Header(default=None),
    x_lark_request_timestamp: str | None = Header(default=None),
    x_lark_request_nonce: str | None = Header(default=None),
) -> Response:
    body_bytes = await request.body()
    try:
        body_text = body_bytes.decode("utf-8")
        envelope = json.loads(body_text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("shusuo_webhook_invalid_json")
        return _json({"code": 400, "msg": "invalid json"}, 400)
    if not isinstance(envelope, dict):
        return _json({"code": 400, "msg": "invalid payload"}, 400)

    config = get_shushuo_config()

    # 加密事件：先验签，再解密。URL 校验请求可能不带签名头。
    if "encrypt" in envelope:
        if not config.encrypt_enabled:
            logger.error(
                "shusuo_webhook_encrypted_but_no_key",
                encrypted_length=len(str(envelope.get("encrypt", ""))),
            )
            return _json({"code": 400, "msg": "encrypt key is not configured"}, 400)
        if x_lark_signature and not verify_signature(
            encrypt_key=config.encrypt_key,
            timestamp=x_lark_request_timestamp or "",
            nonce=x_lark_request_nonce or "",
            body=body_text,
            signature=x_lark_signature,
        ):
            logger.warning("shusuo_webhook_bad_signature")
            return _json({"code": 403, "msg": "invalid signature"}, 403)
        try:
            envelope = decrypt_event(str(envelope["encrypt"]), config.encrypt_key)
        except FeishuCryptoError as exc:
            logger.warning("shusuo_webhook_decrypt_failed", error=str(exc))
            return _json({"code": 400, "msg": "decrypt failed"}, 400)

    if envelope.get("type") == "url_verification":
        # URL 校验只回显 challenge，没有副作用。飞书在“应用新 token 之前”就会用旧
        # token 来校验地址；若这里强制比对 token，会形成死锁（210042）。真正的
        # 事件在下面对 token 做强制校验。
        token = str(envelope.get("token", ""))
        if config.verification_token and token != config.verification_token:
            logger.warning("shusuo_url_verification_token_mismatch")
        return _json({"challenge": envelope.get("challenge", "")})

    header = envelope.get("header") or {}
    if not isinstance(header, dict):
        return _json({"code": 400, "msg": "invalid header"}, 400)

    if config.verification_token:
        token = str(header.get("token", ""))
        if token != config.verification_token:
            return _json({"code": 403, "msg": "invalid verification token"}, 403)

    if config.app_id and header.get("app_id") and header.get("app_id") != config.app_id:
        logger.warning("shusuo_webhook_other_app", app_id=header.get("app_id"))
        return _json({"code": 403, "msg": "unexpected app"}, 403)

    event_id = str(header.get("event_id", ""))
    if _is_duplicate(event_id):
        return _json({"code": 0})

    background_tasks.add_task(_handle_envelope, envelope)
    return _json({"code": 0})


async def _handle_envelope(envelope: dict[str, Any]) -> None:
    try:
        header = envelope.get("header") or {}
        if header.get("event_type") != "im.message.receive_v1":
            return
        event = envelope.get("event") or {}
        sender = event.get("sender") or {}
        if sender.get("sender_type") == "app":
            return
        message = event.get("message") or {}
        message_id = str(message.get("message_id", ""))
        if not message_id:
            return
        chat_id = str(message.get("chat_id", ""))
        open_id = str((sender.get("sender_id") or {}).get("open_id", ""))

        config = get_shushuo_config()
        if config.allowed_open_ids and open_id not in config.allowed_open_ids:
            await lark_client.reply_text(
                message_id,
                "你没有使用数说的权限。请联系管理员加入白名单。",
            )
            return

        text = _extract_text(message)
        if not text:
            await lark_client.reply_text(
                message_id,
                "目前只支持文字指令。发「帮助」查看用法。",
            )
            return

        command = commands.parse_command(text)
        reply = await commands.execute(command)
        if reply.ack:
            await lark_client.reply_text(message_id, reply.ack)
        await lark_client.reply_text(message_id, _truncate(reply.text))
        logger.info(
            "shusuo_command_handled",
            command=command.name,
            argument=command.argument,
            chat_id=chat_id,
            open_id=open_id,
        )
    except Exception as exc:  # noqa: BLE001 - webhook 必须吞掉异常，避免飞书无限重试
        logger.exception("shusuo_event_failed", error=str(exc))


def _extract_text(message: dict[str, Any]) -> str:
    if message.get("message_type") != "text":
        return ""
    content = message.get("content")
    if isinstance(content, str):
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            return ""
    elif isinstance(content, dict):
        decoded = content
    else:
        return ""
    text = decoded.get("text", "")
    return commands.clean_text(str(text)) if isinstance(text, str) else ""


def _truncate(text: str) -> str:
    if len(text) <= _MAX_REPLY_CHARS:
        return text
    return text[: _MAX_REPLY_CHARS - 20] + "\n…（内容过长，已截断）"

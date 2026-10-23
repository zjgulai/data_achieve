"""数说飞书机器人的 FastAPI 路由。

端点：
  POST /api/agents/shusuo/webhook      飞书事件推送（含 URL 校验）
  POST /api/agents/shusuo/card-action  确认卡按钮回调（安全校验 + 后台执行）
  GET  /api/agents/shusuo/health       配置自检（不返回密钥）
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from fastapi.responses import JSONResponse

from . import capabilities, commands, lark_client, proposal_store, replies
from .cards import (
    cancelled_card,
    expired_card,
    failure_card,
    processing_card,
    success_card,
)
from .config import get_shushuo_config
from .crypto import FeishuCryptoError, decrypt_event, verify_signature
from .gate import MessageGateDecision, decide_message_gate
from .proposal_store import ProposalLookup

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["shusuo"])

# 卡片回调允许的动作白名单：新增动作必须先进白名单再实现。
CALLBACK_ACTION_ALLOWLIST = frozenset({"confirm", "cancel"})

_DEDUPE_LIMIT = 1024
_DEDUPE_TTL_SECONDS = 600
_seen_events: OrderedDict[str, float] = OrderedDict()

_EVENT_ID_LOG_MAX_CHARS = 128
_CHAT_TYPE_LOG_MAX_CHARS = 32


def _safe_log_value(value: object, max_chars: int) -> str:
    return str(value or "")[:max_chars]


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
            logger.warning(
                "shusuo_webhook_decrypt_failed",
                error_type=type(exc).__name__,
            )
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
        logger.warning("shusuo_webhook_other_app")
        return _json({"code": 403, "msg": "unexpected app"}, 403)

    event_id = str(header.get("event_id", ""))
    if _is_duplicate(event_id):
        return _json({"code": 0})

    background_tasks.add_task(_handle_envelope, envelope)
    return _json({"code": 0})


async def _handle_envelope(envelope: dict[str, Any]) -> None:
    try:
        header = envelope.get("header") or {}
        event_type = str(header.get("event_type", ""))
        logger.info(
            "shusuo_event_received",
            event_type=event_type,
            event_id=_safe_log_value(
                header.get("event_id"),
                _EVENT_ID_LOG_MAX_CHARS,
            ),
        )
        if event_type != "im.message.receive_v1":
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

        # 群聊只在被 @ 时回复；未 @ 的消息直接忽略，不插话。会话类型未知时 fail-closed。
        chat_type = message.get("chat_type")
        bot_open_id: str | None = None
        if chat_type == "group":
            try:
                bot_open_id = await lark_client.get_bot_open_id()
            except Exception as exc:  # noqa: BLE001 - 群聊必须 fail-closed
                logger.warning(
                    "shusuo_bot_identity_unavailable",
                    message_id=message_id,
                    error_type=type(exc).__name__,
                )
                return

        decision = decide_message_gate(
            chat_type=chat_type,
            mentions=message.get("mentions"),
            bot_open_id=bot_open_id,
        )
        if decision not in {
            MessageGateDecision.ALLOW_P2P,
            MessageGateDecision.ALLOW_GROUP_MENTION,
        }:
            log_method = (
                logger.warning
                if decision
                in {
                    MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE,
                    MessageGateDecision.IGNORE_BOT_ID_UNAVAILABLE,
                }
                else logger.debug
            )
            log_method(
                "shusuo_message_ignored",
                message_id=message_id,
                chat_type=_safe_log_value(chat_type, _CHAT_TYPE_LOG_MAX_CHARS),
                decision=decision.value,
            )
            return

        config = get_shushuo_config()
        if config.allowed_open_ids and open_id not in config.allowed_open_ids:
            await lark_client.reply_text(
                message_id,
                "你没有使用数说的权限。请联系管理员加入白名单。",
            )
            return

        logger.info(
            "shusuo_message_received",
            message_type=str(message.get("message_type", "")),
            chat_id=chat_id,
        )
        text = _extract_text(message)
        if not text:
            await lark_client.reply_text(
                message_id,
                "目前只支持文字指令。发「帮助」查看用法。",
            )
            return

        command = commands.parse_command(text)
        reply = await commands.execute(
            command,
            chat_id=chat_id,
            open_id=open_id,
            message_id=message_id,
        )
        if reply.ack:
            await lark_client.reply_text(message_id, reply.ack)
        if reply.card is not None and reply.pending_token:
            try:
                card_message_id = await lark_client.reply_card(message_id, reply.card)
            except Exception as exc:  # noqa: BLE001 - 卡片失败必须降级文本
                logger.warning(
                    "shusuo_card_send_failed",
                    message_id=message_id,
                    error_type=type(exc).__name__,
                )
                await lark_client.reply_text(message_id, replies.fit_text(reply.text))
            else:
                proposal_store.attach_message_ids(
                    reply.pending_token,
                    message_id=message_id,
                    card_message_id=card_message_id,
                )
        else:
            await lark_client.reply_text(message_id, replies.fit_text(reply.text))
        logger.info(
            "shusuo_command_handled",
            command=command.name,
            chat_id=chat_id,
        )
    except Exception as exc:  # noqa: BLE001 - webhook 必须吞掉异常，避免飞书无限重试
        logger.error(
            "shusuo_event_failed",
            error_type=type(exc).__name__,
        )


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


# ── 卡片按钮回调 ───────────────────────────────────────────────────────────────
#
# 与 /webhook 的区别：回调必须更严格——
# - 未配置 Verification Token 直接拒绝（webhook 的事件通道允许未配置时放行，
#   因为还有白名单兜底；回调能直接触发采集，必须 fail-closed）。
# - 非加密请求也必须带有效签名（encrypt-key 公式，见 crypto.verify_signature；
#   不要照搬 TikTok CDO 的 token 公式）。
# - allowed_open_ids 为空时拒绝：能点确认 = 能花上游额度，必须有显式白名单。
# - 三秒内返回 toast，采集放进 BackgroundTasks。

_TOAST_OK_CONFIRM = {"toast": {"type": "info", "content": "正在处理确认…"}}
_TOAST_OK_CANCEL = {"toast": {"type": "info", "content": "正在取消…"}}


def _card_toast(status: ProposalLookup, action: str) -> dict[str, Any]:
    if action == "confirm":
        if status is ProposalLookup.ACTIVE:
            return _TOAST_OK_CONFIRM
        return {"toast": {"type": "info", "content": replies.pending_status_text(status)}}
    if status is ProposalLookup.ACTIVE:
        return _TOAST_OK_CANCEL
    return {"toast": {"type": "info", "content": replies.pending_status_text(status)}}


@router.post("/card-action")
async def shusuo_card_action(
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
        logger.warning("shusuo_card_action_invalid_json")
        return _json({"code": 400, "msg": "invalid json"}, 400)
    if not isinstance(envelope, dict):
        return _json({"code": 400, "msg": "invalid payload"}, 400)

    config = get_shushuo_config()
    if not config.encrypt_enabled:
        logger.error("shusuo_card_action_no_encrypt_key")
        return _json({"code": 403, "msg": "encrypt key is not configured"}, 403)

    # 回调一律验签（encrypt-key 公式）：加密与非加密形态都不能绕过。
    if not verify_signature(
        encrypt_key=config.encrypt_key,
        timestamp=x_lark_request_timestamp or "",
        nonce=x_lark_request_nonce or "",
        body=body_text,
        signature=x_lark_signature or "",
    ):
        logger.warning("shusuo_card_action_bad_signature")
        return _json({"code": 403, "msg": "invalid signature"}, 403)

    if "encrypt" in envelope:
        try:
            envelope = decrypt_event(str(envelope["encrypt"]), config.encrypt_key)
        except FeishuCryptoError as exc:
            logger.warning(
                "shusuo_card_action_decrypt_failed",
                error_type=type(exc).__name__,
            )
            return _json({"code": 400, "msg": "decrypt failed"}, 400)
        if not isinstance(envelope, dict):
            return _json({"code": 400, "msg": "invalid payload"}, 400)

    # URL 校验只回显 challenge，没有副作用；也不强制比对 token（与 /webhook 同因）。
    if envelope.get("type") == "url_verification":
        return _json({"challenge": envelope.get("challenge", "")})

    # 回调必须配置 Verification Token 且匹配（fail-closed）。
    if not config.verification_token:
        logger.error("shusuo_card_action_token_not_configured")
        return _json({"code": 403, "msg": "verification token is not configured"}, 403)
    if str(envelope.get("token", "")) != config.verification_token:
        logger.warning("shusuo_card_action_token_mismatch")
        return _json({"code": 403, "msg": "invalid verification token"}, 403)

    callback_app_id = str(envelope.get("app_id", ""))
    if config.app_id and callback_app_id and callback_app_id != config.app_id:
        logger.warning("shusuo_card_action_other_app")
        return _json({"code": 403, "msg": "unexpected app"}, 403)

    action_value = envelope.get("action")
    action_value = action_value.get("value") if isinstance(action_value, dict) else None
    action_value = action_value if isinstance(action_value, dict) else {}
    action = str(action_value.get("action", ""))
    if action not in CALLBACK_ACTION_ALLOWLIST:
        logger.warning("shusuo_card_action_unknown_action")
        return _json({"code": 400, "msg": "unknown action"}, 400)

    # 回调白名单：空 = 拒绝（与 webhook 的"未配置即放行"不同，这里 fail-closed）。
    operator = envelope.get("operator")
    operator = operator if isinstance(operator, dict) else {}
    operator_open_id = str(operator.get("open_id", ""))
    if not config.allowed_open_ids:
        logger.warning("shusuo_card_action_allowlist_empty")
        return _json({"code": 403, "msg": "operator allowlist is empty"}, 403)
    if operator_open_id not in config.allowed_open_ids:
        logger.warning("shusuo_card_action_operator_not_allowed")
        return _json({"code": 403, "msg": "operator not allowed"}, 403)

    token = str(action_value.get("token", ""))
    context = envelope.get("context")
    context = context if isinstance(context, dict) else {}
    chat_id = str(context.get("open_chat_id", ""))
    card_message_id = str(context.get("open_message_id", ""))
    if not token or not operator_open_id:
        return _json({"code": 400, "msg": "missing token or operator"}, 400)

    # pending 归属校验：token 属于该 operator 才放行（chat_id 允许为空——
    # 卡片转发后 context 里的 open_chat_id 不可信，归属以 store 记录为准）。
    status, pending = proposal_store.peek_pending(token, chat_id, operator_open_id)
    if pending is None and chat_id:
        # 兼容卡片转发：按空 chat 上下文再查一次，仍以 operator 归属为准。
        status, pending = proposal_store.peek_pending(token, "", operator_open_id)
    if pending is None:
        logger.info(
            "shusuo_card_action_not_pending",
            action=action,
            lookup=status.value if isinstance(status, ProposalLookup) else "unknown",
        )
        return _json(_card_toast(status, action))

    if action == "confirm":
        background_tasks.add_task(
            _execute_card_confirm,
            token=token,
            chat_id=pending.chat_id,
            open_id=pending.open_id,
            card_message_id=card_message_id or pending.card_message_id or "",
        )
        return _json(_card_toast(ProposalLookup.ACTIVE, action))
    background_tasks.add_task(
        _execute_card_cancel,
        token=token,
        chat_id=pending.chat_id,
        open_id=pending.open_id,
        card_message_id=card_message_id or pending.card_message_id or "",
    )
    return _json(_card_toast(ProposalLookup.ACTIVE, action))


async def _safe_update_card(
    card_message_id: str, card: dict[str, Any], event: str
) -> None:
    """更新卡片；失败只记日志（不恢复 token、不重试、不重复采集）。"""
    if not card_message_id:
        return
    try:
        await lark_client.update_card(card_message_id, card)
    except Exception as exc:  # noqa: BLE001 - 卡片更新失败不能影响采集结果
        logger.warning(
            event,
            message_id=card_message_id,
            error_type=type(exc).__name__,
        )


async def _execute_card_confirm(
    *, token: str, chat_id: str, open_id: str, card_message_id: str
) -> None:
    """后台确认：处理中卡 → 强制预检 → 消费 token → 采集 → 结果卡。

    预检失败不消费 token；消费之后采集只做一次；update_card 失败只记日志。
    """
    try:
        status, pending = proposal_store.peek_pending(token, chat_id, open_id)
        if pending is None:
            await _safe_update_card(card_message_id, expired_card(), "shusuo_card_update_failed")
            return
        proposal = pending.proposal
        await _safe_update_card(
            card_message_id, processing_card(pending), "shusuo_card_update_failed"
        )
        preflight = await capabilities.preflight_proposal(proposal, force_status=True)
        if not preflight.allowed:
            await _safe_update_card(
                card_message_id,
                failure_card(pending, replies.preflight_error_text(preflight)),
                "shusuo_card_update_failed",
            )
            logger.info(
                "shusuo_card_confirm_preflight_blocked",
                endpoint_type=replies.fit_text(proposal.endpoint_type, limit=120),
            )
            return
        status, pending = proposal_store.consume_pending(token, chat_id, open_id)
        if pending is None:
            await _safe_update_card(
                card_message_id, expired_card(), "shusuo_card_update_failed"
            )
            return
        outcome = await capabilities.collect(
            pending.proposal.endpoint_type, preflight.normalized_params
        )
        if outcome.ok:
            card = success_card(pending, outcome)
        else:
            message = outcome.error_message or outcome.text or "上游没有返回记录"
            card = failure_card(pending, message)
        await _safe_update_card(card_message_id, card, "shusuo_card_update_failed")
        logger.info(
            "shusuo_card_confirmed",
            endpoint_type=replies.fit_text(proposal.endpoint_type, limit=120),
            ok=outcome.ok,
        )
    except Exception as exc:  # noqa: BLE001 - 后台任务必须吞掉异常
        logger.error("shusuo_card_confirm_failed", error_type=type(exc).__name__)


async def _execute_card_cancel(
    *, token: str, chat_id: str, open_id: str, card_message_id: str
) -> None:
    """后台取消：取消 token → 更新取消卡；绝不采集。"""
    try:
        _, pending = proposal_store.peek_pending(token, chat_id, open_id)
        status = proposal_store.cancel_pending(token, chat_id, open_id)
        if status is ProposalLookup.ACTIVE and pending is not None:
            card = cancelled_card(pending)
        else:
            card = expired_card()
        await _safe_update_card(
            card_message_id, card, "shusuo_card_update_failed"
        )
        logger.info("shusuo_card_cancelled", lookup=status.value)
    except Exception as exc:  # noqa: BLE001 - 后台任务必须吞掉异常
        logger.error("shusuo_card_cancel_failed", error_type=type(exc).__name__)

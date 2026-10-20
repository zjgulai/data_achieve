"""
FastAPI 路由：TikTok CDO 飞书机器人 webhook。

端点：
  POST /api/agents/tiktok-cdo/webhook       ← 飞书事件推送
  POST /api/agents/tiktok-cdo/webhook/callback ← 卡片按钮回调
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, Request, Response

from .card_builder import error_card, placeholder_card, result_card
from .cleaner import clean_and_analyze
from .config import get_cdo_config
from .data_sources import gather_data
from .intent import TikTokIntent, extract_intent
from .lark_client import send_card, update_card

logger = logging.getLogger(__name__)

router = APIRouter()


# ── webhook 主入口 ─────────────────────────────────────────────────────────────

@router.post("/webhook")
async def lark_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lark_signature: str | None = Header(None),
    x_lark_request_timestamp: str | None = Header(None),
    x_lark_request_nonce: str | None = Header(None),
) -> Response:
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8")

    try:
        event = json.loads(body_text)
    except Exception:
        return Response(content='{"code":400}', status_code=400)

    # 处理 url_verification challenge（飞书订阅事件首次验证，不需要验签）
    if event.get("type") == "url_verification":
        challenge = event.get("challenge", "")
        return Response(content=json.dumps({"challenge": challenge}), media_type="application/json")

    # 正常事件：验签
    config = get_cdo_config()
    if config.lark_verification_token and not _verify_signature(
        config.lark_verification_token,
        x_lark_request_timestamp or "",
        x_lark_request_nonce or "",
        body_text,
        x_lark_signature or "",
    ):
        return Response(content='{"code":403,"msg":"invalid signature"}', status_code=403)

    # 立即返回 200，异步处理
    background_tasks.add_task(_handle_message, event)
    return Response(content='{"code":0}', media_type="application/json")


# ── 卡片按钮回调 ───────────────────────────────────────────────────────────────

# 卡片回调允许的动作白名单。
# 新增动作必须先进白名单，避免外部构造 action 触发未审核的副作用。
CALLBACK_ACTION_ALLOWLIST = frozenset({"re_collect", "export_bitable"})


@router.post("/webhook/callback")
async def lark_card_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lark_signature: str | None = Header(None),
    x_lark_request_timestamp: str | None = Header(None),
    x_lark_request_nonce: str | None = Header(None),
) -> dict[str, Any]:
    """处理飞书卡片按钮回调。

    与 /webhook 同一套验签：回调也由飞书发出，必须校验签名。
    未配置 verification token 时直接拒绝，不放行。
    """
    # 先读原始 body 用于验签；验签必须基于原始字节。
    raw_body = await request.body()
    body_text = raw_body.decode("utf-8")

    config = get_cdo_config()
    if not config.lark_verification_token:
        logger.warning("cdo_callback_rejected: verification token 未配置")
        return {"code": 403, "msg": "callback_verification_not_configured"}

    if not _verify_signature(
        config.lark_verification_token,
        x_lark_request_timestamp or "",
        x_lark_request_nonce or "",
        body_text,
        x_lark_signature or "",
    ):
        logger.warning("cdo_callback_rejected: 签名不匹配")
        return {"code": 403, "msg": "invalid signature"}

    try:
        body: dict[str, Any] = json.loads(body_text)
    except json.JSONDecodeError:
        return {"code": 400, "msg": "invalid body"}

    action_val: dict[str, Any] = (body.get("action") or {}).get("value") or {}
    action_type = action_val.get("action", "")

    if action_type not in CALLBACK_ACTION_ALLOWLIST:
        logger.warning("cdo_callback_rejected: 未知动作 %s", action_type)
        return {"code": 400, "msg": "unknown action"}

    if action_type == "export_bitable":
        # 暂存数据已丢失，此处仅返回提示；完整实现需 Redis 缓存结果
        return {"toast": {"type": "info", "content": "导出功能需配置多维表格后生效"}}

    if action_type == "re_collect":
        raw_text = action_val.get("raw_text", "")
        # 从回调中获取 chat_id
        open_id = (body.get("sender") or {}).get("sender_id", {}).get("open_id", "")
        background_tasks.add_task(_re_collect, raw_text, open_id)
        return {"toast": {"type": "info", "content": "正在重新采集…"}}

    return {"code": 0}


# ── 异步消息处理 ───────────────────────────────────────────────────────────────

async def _handle_message(event: dict[str, Any]) -> None:
    try:
        header = event.get("header") or {}
        event_body = event.get("event") or {}

        # 过滤非 im.message.receive 事件
        if header.get("event_type") != "im.message.receive_v1":
            return

        message = event_body.get("message") or {}
        msg_type = message.get("message_type", "")

        # 只处理文本消息
        if msg_type != "text":
            return

        # 解析消息内容
        content_raw = message.get("content", "{}")
        content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
        text: str = content.get("text", "").strip()

        # 去掉 @ 机器人的提及标记（飞书会在文本中插入 <at>...
        import re
        text = re.sub(r"<at[^>]*>.*?</at>", "", text).strip()

        if not text:
            return

        # 获取 chat_id（群消息）或 open_id（单聊）
        chat_id = message.get("chat_id", "")
        sender_open_id = (event_body.get("sender") or {}).get("sender_id", {}).get("open_id", "")
        target_id = chat_id or sender_open_id

        if not target_id:
            logger.warning("无法获取目标 ID，跳过消息处理")
            return

        # 1. 发送占位卡
        intent_tmp = TikTokIntent(action="search", raw_text=text)
        message_id = await send_card(target_id, placeholder_card(intent_tmp))

        # 2. 意图提取
        intent = await extract_intent(text)
        logger.info("意图识别: %s kw=%s user=%s", intent.action, intent.keyword, intent.username)

        if intent.action == "unknown":
            await update_card(message_id, error_card(intent, "未能识别采集意图，请重新描述。"))
            return

        # 3. 更新占位卡（已知 action）
        await update_card(message_id, placeholder_card(intent))

        # 4. 采集数据 + 清洗 + L3 摘要
        config = get_cdo_config()
        try:
            cleaned = await asyncio.wait_for(
                _collect_and_clean(intent),
                timeout=config.tool_timeout_seconds,
            )
        except TimeoutError:
            await update_card(
                message_id, error_card(intent, "采集超时，请稍后重试。")
            )
            return

        # 5. 更新结果卡
        card = result_card(intent, cleaned)
        await update_card(message_id, card)

    except Exception as e:
        logger.exception("消息处理异常: %s", e)


async def _collect_and_clean(intent: TikTokIntent) -> dict[str, Any]:
    raw_data = await gather_data(intent)
    return await clean_and_analyze(raw_data, intent)


async def _re_collect(raw_text: str, open_id: str) -> None:
    if not raw_text or not open_id:
        return
    # 简单重触发：当作新消息处理
    fake_event = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": open_id}},
            "message": {
                "message_type": "text",
                "chat_id": open_id,
                "content": json.dumps({"text": raw_text}),
            },
        },
    }
    await _handle_message(fake_event)


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def _verify_signature(
    token: str, timestamp: str, nonce: str, body: str, signature: str
) -> bool:
    """飞书 webhook 验签。"""
    s = timestamp + nonce + token + body
    expected = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, signature)

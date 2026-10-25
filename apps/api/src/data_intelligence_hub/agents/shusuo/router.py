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
    internal_error_card,
    processing_card,
    replaced_card,
    retryable_preflight_card,
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

# 回调时间戳窗口。签名覆盖 timestamp+nonce+body，重放一份旧请求的签名仍然有效；
# 只有时间窗口能把「合法签名的旧请求」挡在动作执行之前。
CALLBACK_TIMESTAMP_WINDOW_SECONDS = 300


def _timestamp_is_fresh(timestamp: str, *, now: float | None = None) -> bool:
    """时间戳是否为「整数字符串」且在 ±窗口内。

    只接受纯十进制整数秒：`1e9`、`17000000.5`、前后带空格、负数都按畸形拒绝。
    未来时间同样超出窗口——时钟回拨不能变成永久有效的通行证。
    """
    if not timestamp or not timestamp.isascii() or not timestamp.isdigit():
        return False
    try:
        value = int(timestamp)
    except ValueError:  # pragma: no cover - isdigit 已挡住
        return False
    current = time.time() if now is None else now
    return abs(current - value) <= CALLBACK_TIMESTAMP_WINDOW_SECONDS


def _card_toast(status: ProposalLookup, action: str) -> dict[str, Any]:
    if action == "confirm":
        if status is ProposalLookup.ACTIVE:
            return _TOAST_OK_CONFIRM
        return {"toast": {"type": "info", "content": replies.pending_status_text(status)}}
    if status is ProposalLookup.ACTIVE:
        return _TOAST_OK_CANCEL
    return {"toast": {"type": "info", "content": replies.pending_status_text(status)}}


def _parse_card_callback(
    envelope: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """拆出 (header, event)。

    权威形态（schema 2.0 HTTP 推送，加密解开后相同）：
      {"header": {"token", "app_id", ...}, "event": {"operator", "action", "context"}}
    旧扁平形态（token/app_id/operator/action/context 在顶层）仅作向后兼容
    回退：header 用顶层凭证合成，event 就是整个 envelope。正常推送不受影响。
    """
    header = envelope.get("header")
    event = envelope.get("event")
    if isinstance(header, dict) or isinstance(event, dict):
        return (
            header if isinstance(header, dict) else {},
            event if isinstance(event, dict) else {},
        )
    flat_keys = ("token", "app_id", "operator", "action", "context")
    if any(key in envelope for key in flat_keys):
        synthetic_header = {
            key: envelope[key] for key in ("token", "app_id") if key in envelope
        }
        return synthetic_header, envelope
    return {}, {}


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

    # 签名通过 ≠ 请求新鲜：旧请求体带着旧签名重放仍然验签成功。
    # 这一层必须在任何读取 token / 消费 token 的动作之前。
    if not _timestamp_is_fresh(x_lark_request_timestamp or ""):
        logger.warning("shusuo_card_action_stale_timestamp")
        return _json({"code": 403, "msg": "stale timestamp"}, 403)

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

    header, event = _parse_card_callback(envelope)

    # 回调必须配置 Verification Token 且匹配（fail-closed）。凭证在 header 层。
    if not config.verification_token:
        logger.error("shusuo_card_action_token_not_configured")
        return _json({"code": 403, "msg": "verification token is not configured"}, 403)
    if str(header.get("token", "")) != config.verification_token:
        logger.warning("shusuo_card_action_token_mismatch")
        return _json({"code": 403, "msg": "invalid verification token"}, 403)

    callback_app_id = str(header.get("app_id", ""))
    if config.app_id and callback_app_id and callback_app_id != config.app_id:
        logger.warning("shusuo_card_action_other_app")
        return _json({"code": 403, "msg": "unexpected app"}, 403)

    action_value = event.get("action")
    action_value = action_value.get("value") if isinstance(action_value, dict) else None
    action_value = action_value if isinstance(action_value, dict) else {}
    action = str(action_value.get("action", ""))
    if action not in CALLBACK_ACTION_ALLOWLIST:
        logger.warning("shusuo_card_action_unknown_action")
        return _json({"code": 400, "msg": "unknown action"}, 400)

    # 回调白名单：空 = 拒绝（与 webhook 的"未配置即放行"不同，这里 fail-closed）。
    operator = event.get("operator")
    operator = operator if isinstance(operator, dict) else {}
    operator_open_id = str(operator.get("open_id", ""))
    if not config.allowed_open_ids:
        logger.warning("shusuo_card_action_allowlist_empty")
        return _json({"code": 403, "msg": "operator allowlist is empty"}, 403)
    if operator_open_id not in config.allowed_open_ids:
        logger.warning("shusuo_card_action_operator_not_allowed")
        return _json({"code": 403, "msg": "operator not allowed"}, 403)

    token = str(action_value.get("token", ""))
    context = event.get("context")
    context = context if isinstance(context, dict) else {}
    chat_id = str(context.get("open_chat_id", ""))
    card_message_id = str(context.get("open_message_id", ""))
    if not token or not operator_open_id:
        return _json({"code": 400, "msg": "missing token or operator"}, 400)

    # pending 归属校验：token 属于该 operator 才放行。
    #
    # 卡片转发后 context 里的 open_chat_id 可能缺失：此时没有会话可比，
    # 归属只能由 open_id 保证，直接按 token + 归属人查。
    #
    # 有 chat_id 时先按会话归属查；**只有**结果是 MISSING 才退回按 token 查。
    # EXPIRED / FORBIDDEN / REPLACED 都是确定结论，再查一次会把它们覆盖成
    # 第二次查询的结果（历史上就能把「已被替换」变成「没有待确认」）。
    if chat_id:
        status, pending = proposal_store.peek_pending(token, chat_id, operator_open_id)
        if pending is None and status is ProposalLookup.MISSING:
            status, pending = proposal_store.peek_by_token(token, operator_open_id)
    else:
        status, pending = proposal_store.peek_by_token(token, operator_open_id)
    if pending is None:
        if status is ProposalLookup.FORBIDDEN:
            # 他人提案：硬拒绝。双白名单时这一步才是真正的归属防线。
            logger.warning(
                "shusuo_card_action_forbidden",
                action=action,
            )
            return _json({"code": 403, "msg": "not proposal owner"}, 403)
        logger.info(
            "shusuo_card_action_not_pending",
            action=action,
            lookup=status.value if isinstance(status, ProposalLookup) else "unknown",
        )
        return _json(_card_toast(status, action))

    if action == "confirm":
        # 原子预留：调度前先消费 token，双击/重放的第二次请求在 peek 处
        # 就拿到 MISSING，不会排队第二个后台任务（关闭 M1 竞态）。
        # 消费后采集仍只在后台预检通过、再次原子消费成功后发生——
        # 预检失败会把 token 放回去（restore 不等于重新采集），用户可重试。
        consumed_status, reserved = proposal_store.consume_pending(
            token, pending.chat_id, pending.open_id
        )
        if reserved is None:
            logger.info(
                "shusuo_card_action_reserve_lost",
                action=action,
                lookup=consumed_status.value
                if isinstance(consumed_status, ProposalLookup)
                else "unknown",
            )
            return _json(_card_toast(consumed_status, action))
        background_tasks.add_task(
            _execute_card_confirm,
            token=token,
            chat_id=reserved.chat_id,
            open_id=reserved.open_id,
            card_message_id=card_message_id or reserved.card_message_id or "",
            reserved=reserved,
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
    *,
    token: str,
    chat_id: str,
    open_id: str,
    card_message_id: str,
    reserved: proposal_store.PendingProposal | None = None,
) -> None:
    """后台确认：处理中卡 → 强制预检 → 采集 → 结果卡。

    `reserved` 是路由层原子预留（consume）出来的 pending，生产路径总是传它：
    token 在调度前就已消费，双击/重放的第二个请求在 peek 处拿到 MISSING，
    不会排队第二个后台任务。`reserved=None` 只留给直接调用（测试/脚本）。

    预检失败不消耗机会：token 原样放回（同 token、同 TTL 端点），卡片换成
    「当前无法执行」的重试卡——不是上游失败卡，绝不能让人以为额度已经花掉。

    异常收尾分两段：预检之前抛错可以安全恢复 token（采集肯定没开始）；
    采集一旦可能开始就绝不恢复，只把卡片刷成安全失败态，防止重复计费。
    """
    collecting_started = False
    try:
        if reserved is None:
            status, pending = proposal_store.peek_pending(token, chat_id, open_id)
            if pending is None:
                await _safe_update_card(
                    card_message_id,
                    _status_card(status),
                    "shusuo_card_update_failed",
                )
                return
        else:
            pending = reserved
        proposal = pending.proposal
        await _safe_update_card(
            card_message_id, processing_card(pending), "shusuo_card_update_failed"
        )
        preflight = await capabilities.preflight_proposal(proposal, force_status=True)
        if not preflight.allowed:
            await _safe_update_card(
                card_message_id,
                retryable_preflight_card(pending, preflight),
                "shusuo_card_update_failed",
            )
            if reserved is not None:
                # 预检失败放回 token（原子预留的回滚）；不采集、不重试。
                proposal_store.restore_pending(reserved)
            logger.info(
                "shusuo_card_confirm_preflight_blocked",
                endpoint_type=replies.fit_text(proposal.endpoint_type, limit=120),
            )
            return
        collecting_started = True
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
        # 采集可能已经开始：绝不恢复 token（宁可让用户重发，也不重复计费）。
        if not collecting_started and reserved is not None:
            proposal_store.restore_pending(reserved)
        await _safe_update_card(
            card_message_id,
            internal_error_card(),
            "shusuo_card_update_failed",
        )


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
            card = _status_card(status)
        await _safe_update_card(
            card_message_id, card, "shusuo_card_update_failed"
        )
        logger.info("shusuo_card_cancelled", lookup=status.value)
    except Exception as exc:  # noqa: BLE001 - 后台任务必须吞掉异常
        logger.error("shusuo_card_cancel_failed", error_type=type(exc).__name__)


def _status_card(status: ProposalLookup) -> dict[str, Any]:
    """非 ACTIVE 状态的落卡：过期/替换/丢失分别给准确文案。

    REPLACED 用 expired 卡形（同为 grey「请重新发起」语义），但正文
    区分「已被新提案替换」；store 的 REPLACED 查询窗口（300s）过后
    退化为 MISSING，文案同为重新发起。
    """
    if status is ProposalLookup.REPLACED:
        return replaced_card()
    return expired_card()

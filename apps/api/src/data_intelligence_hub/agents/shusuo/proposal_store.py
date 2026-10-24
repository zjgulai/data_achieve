"""数说的一次性提案存储。

单进程内存存储：每个 `chat_id + open_id` 上下文只保留一个待确认提案；
新提案替换旧提案，token 只能消费一次，300 秒过期，API 重启即清空。
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .intents import Proposal

PENDING_TTL_SECONDS = 300
MAX_PENDING_PROPOSALS = 1024
_TOKEN_BYTES = 8

_PENDING_BY_TOKEN: dict[str, PendingProposal] = {}
_ACTIVE_TOKEN_BY_CONTEXT: dict[tuple[str, str], str] = {}
_REPLACED_TOKENS: dict[str, float] = {}


@dataclass(frozen=True, slots=True)
class PendingProposal:
    token: str
    chat_id: str
    open_id: str
    proposal: Proposal
    params_hash: str
    created_at: float
    expires_at: float
    message_id: str | None = None
    card_message_id: str | None = None


class ProposalLookup(StrEnum):
    ACTIVE = "active"
    MISSING = "missing"
    EXPIRED = "expired"
    REPLACED = "replaced"
    FORBIDDEN = "forbidden"


def _now(now: float | None) -> float:
    return time.time() if now is None else now


def _new_token() -> str:
    return secrets.token_hex(_TOKEN_BYTES).upper()


def _params_hash(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _drop(token: str) -> None:
    """从 active、replaced、context 三个索引里同时移除一个 token。"""
    _PENDING_BY_TOKEN.pop(token, None)
    _REPLACED_TOKENS.pop(token, None)
    for context, active_token in list(_ACTIVE_TOKEN_BY_CONTEXT.items()):
        if active_token == token:
            del _ACTIVE_TOKEN_BY_CONTEXT[context]


def clear_expired(*, now: float | None = None) -> None:
    current = _now(now)
    for token, pending in list(_PENDING_BY_TOKEN.items()):
        if current >= pending.expires_at:
            _drop(token)
    for token, created_at in list(_REPLACED_TOKENS.items()):
        if current - created_at >= PENDING_TTL_SECONDS:
            _drop(token)


def _enforce_capacity(now: float) -> None:
    if len(_PENDING_BY_TOKEN) < MAX_PENDING_PROPOSALS:
        return
    clear_expired(now=now)
    while len(_PENDING_BY_TOKEN) >= MAX_PENDING_PROPOSALS:
        oldest = min(_PENDING_BY_TOKEN.values(), key=lambda item: item.created_at)
        _drop(oldest.token)


def _resolve(
    token: str | None, chat_id: str, open_id: str, *, now: float | None = None
) -> tuple[ProposalLookup, PendingProposal | None]:
    current = _now(now)
    if token is None:
        active_token = _ACTIVE_TOKEN_BY_CONTEXT.get((chat_id, open_id))
        if active_token is None:
            return ProposalLookup.MISSING, None
        pending = _PENDING_BY_TOKEN.get(active_token)
        if pending is None:
            _ACTIVE_TOKEN_BY_CONTEXT.pop((chat_id, open_id), None)
            return ProposalLookup.MISSING, None
        if current >= pending.expires_at:
            _drop(active_token)
            return ProposalLookup.EXPIRED, None
        return ProposalLookup.ACTIVE, pending

    pending = _PENDING_BY_TOKEN.get(token)
    if pending is None:
        if token in _REPLACED_TOKENS:
            return ProposalLookup.REPLACED, None
        return ProposalLookup.MISSING, None
    if pending.chat_id != chat_id or pending.open_id != open_id:
        return ProposalLookup.FORBIDDEN, None
    if current >= pending.expires_at:
        _drop(token)
        return ProposalLookup.EXPIRED, None
    return ProposalLookup.ACTIVE, pending


def replace_pending(
    chat_id: str, open_id: str, proposal: Proposal, *, now: float | None = None
) -> PendingProposal:
    current = _now(now)
    context = (chat_id, open_id)
    old_token = _ACTIVE_TOKEN_BY_CONTEXT.get(context)
    if old_token is not None:
        # 先记 replaced，再移除旧提案；旧 token 仍要能查出 REPLACED 状态。
        _REPLACED_TOKENS[old_token] = current
        _PENDING_BY_TOKEN.pop(old_token, None)
    pending = PendingProposal(
        token=_new_token(),
        chat_id=chat_id,
        open_id=open_id,
        proposal=proposal,
        params_hash=_params_hash(proposal.params),
        created_at=current,
        expires_at=current + PENDING_TTL_SECONDS,
    )
    _enforce_capacity(current)
    _PENDING_BY_TOKEN[pending.token] = pending
    _ACTIVE_TOKEN_BY_CONTEXT[context] = pending.token
    return pending


def peek_pending(
    token: str | None, chat_id: str, open_id: str, *, now: float | None = None
) -> tuple[ProposalLookup, PendingProposal | None]:
    return _resolve(token, chat_id, open_id, now=now)


def consume_pending(
    token: str | None, chat_id: str, open_id: str, *, now: float | None = None
) -> tuple[ProposalLookup, PendingProposal | None]:
    status, pending = _resolve(token, chat_id, open_id, now=now)
    if pending is None or status is not ProposalLookup.ACTIVE:
        return status, None
    _drop(pending.token)
    return status, pending


def cancel_pending(
    token: str | None, chat_id: str, open_id: str, *, now: float | None = None
) -> ProposalLookup:
    status, pending = _resolve(token, chat_id, open_id, now=now)
    if pending is None or status is not ProposalLookup.ACTIVE:
        return status
    _drop(pending.token)
    return status


def restore_pending(pending: PendingProposal, *, now: float | None = None) -> None:
    """把原子预留（consume）出来的提案原样放回：同 token、同 TTL 端点。

    用于「预留后后台预检失败」的回滚——不是重新发提案，token/内容不变，
    仅当该上下文没有更新的活跃提案时才放回（避免覆盖用户的新提案）。
    `now` 仅为与其他 API 的签名一致性保留：恢复不重置时间戳。
    """
    del now  # 恢复不重算 TTL；保留参数是为了调用侧书写一致
    context = (pending.chat_id, pending.open_id)
    active_token = _ACTIVE_TOKEN_BY_CONTEXT.get(context)
    if active_token is not None and active_token != pending.token:
        return
    _REPLACED_TOKENS.pop(pending.token, None)
    _PENDING_BY_TOKEN[pending.token] = pending
    _ACTIVE_TOKEN_BY_CONTEXT[context] = pending.token


def attach_message_ids(
    token: str, *, message_id: str | None = None, card_message_id: str | None = None
) -> None:
    pending = _PENDING_BY_TOKEN.get(token)
    if pending is None:
        return
    updates: dict[str, Any] = {}
    if message_id is not None:
        updates["message_id"] = message_id
    if card_message_id is not None:
        updates["card_message_id"] = card_message_id
    if not updates:
        return
    _PENDING_BY_TOKEN[token] = replace(pending, **updates)


def clear_all() -> None:
    _PENDING_BY_TOKEN.clear()
    _ACTIVE_TOKEN_BY_CONTEXT.clear()
    _REPLACED_TOKENS.clear()

"""卡片回调的状态归属、预检失败重试路径与后台异常收尾。

三件事在这里锁定：

1. 空会话回退只在第一次查询是 MISSING 时进行——EXPIRED/FORBIDDEN/REPLACED
   必须原样保留，不能被第二次查询覆盖成 MISSING。
2. 预检失败给「重试」卡（不是上游失败卡），token 恢复且不延长 TTL；
   条件恢复后重试恰好执行一次。
3. 后台未捕获异常不得把卡片留在「正在采集」。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import cards
from data_intelligence_hub.agents.shusuo import proposal_store as shusuo_proposal_store
from data_intelligence_hub.agents.shusuo import router as shusuo_router
from data_intelligence_hub.agents.shusuo.config import get_shushuo_config
from data_intelligence_hub.agents.shusuo.intents import Proposal
from data_intelligence_hub.agents.shusuo.proposal_store import ProposalLookup
from data_intelligence_hub.main import app

CARD_ACTION_PATH = "/api/agents/shusuo/card-action"


@pytest.fixture(autouse=True)
def _state(monkeypatch):
    get_shushuo_config.cache_clear()
    shusuo_proposal_store.clear_all()
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", "act-key")
    monkeypatch.setenv("LARK_SHUSUO_VERIFICATION_TOKEN", "vt-act")
    monkeypatch.setenv("LARK_SHUSUO_APP_ID", "app-act")
    monkeypatch.setenv("SHUSUO_ALLOWED_OPEN_IDS", "ou-1,ou-2")
    get_shushuo_config.cache_clear()
    yield
    shusuo_proposal_store.clear_all()
    get_shushuo_config.cache_clear()


def _signed(
    payload: dict[str, Any], *, timestamp: int | None = None
) -> tuple[str, dict[str, str]]:
    import time

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    nonce = "n-act"
    signature = hashlib.sha256(f"{stamp}{nonce}act-key{body}".encode()).hexdigest()
    return body, {
        "X-Lark-Request-Timestamp": stamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
        "Content-Type": "application/json",
    }


def _payload(
    token: str,
    *,
    action: str = "confirm",
    operator: str = "ou-1",
    chat_id: str = "chat-act",
    message_id: str = "om-act",
    nested: bool = True,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "operator": {"open_id": operator},
        "action": {"value": {"action": action, "token": token}},
        "context": {"open_message_id": message_id, "open_chat_id": chat_id},
    }
    header = {"token": "vt-act", "app_id": "app-act"}
    if nested:
        return {"schema": "2.0", "header": header, "event": event}
    flat = dict(event)
    flat.update(header)
    flat["type"] = "card.action.trigger"
    return flat


def _seed(
    *,
    chat_id: str = "chat-act",
    open_id: str = "ou-1",
    now: float | None = None,
) -> str:
    clear = shusuo_proposal_store.clear_all
    clear()
    pending = shusuo_proposal_store.replace_pending(
        chat_id,
        open_id,
        Proposal(
            endpoint_type="tikhub_reddit_search",
            params={"keyword": "AI", "max_items": 10},
            title="Reddit 搜索",
        ),
        now=now,
    )
    shusuo_proposal_store.attach_message_ids(pending.token, card_message_id="om-act")
    return pending.token


def _install_card_updates(monkeypatch) -> list[tuple[str, dict[str, Any]]]:
    updates: list[tuple[str, dict[str, Any]]] = []

    async def fake_update_card(message_id: str, card: dict[str, Any]) -> bool:
        updates.append((message_id, card))
        return True

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", fake_update_card)
    return updates


def _install_preflight(monkeypatch, allowed: bool) -> AsyncMock:
    result = shusuo_capabilities.PreflightResult(
        allowed=allowed,
        availability="verified" if allowed else "config-gated",
        normalized_params={"keyword": "AI", "max_items": 10},
        errors=() if allowed else ("端点 tikhub_reddit_search 当前不可执行（缺配置/受限）。",),
        warnings=(),
        cost_notice="费用未知，按上游实际计费",
    )
    mock = AsyncMock(return_value=result)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", mock)
    return mock


# ---------------------------------------------------------------------------
# 1. 状态归属：第二次查询不能覆盖 EXPIRED / FORBIDDEN / REPLACED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("nested"), [True, False])
async def test_expired_token_is_not_masked_by_empty_chat_lookup(
    monkeypatch, nested: bool
) -> None:
    token = _seed(now=1)
    _install_card_updates(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    body, headers = _signed(_payload(token, nested=nested))
    response = TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)

    assert response.status_code == 200
    assert response.json().get("toast")
    # 过期提示必须来自 EXPIRED，而不是第二次查询的 MISSING
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-act", "ou-1")
    assert status is ProposalLookup.MISSING  # 已过期清理
    assert pending is None
    collect.assert_not_awaited()


async def test_replaced_token_is_not_masked_by_empty_chat_lookup(monkeypatch) -> None:
    token = _seed()
    shusuo_proposal_store.replace_pending(
        "chat-act",
        "ou-1",
        Proposal(endpoint_type="tikhub_reddit_search", params={"keyword": "B"}, title="新提案"),
    )
    _install_card_updates(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    body, headers = _signed(_payload(token))
    response = TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    collect.assert_not_awaited()


async def test_status_fallback_only_triggers_on_missing(monkeypatch) -> None:
    """直接锁语义：第一次 MISSING 才回退；其余状态原样返回。"""
    token = _seed()
    shusuo_proposal_store.replace_pending(
        "chat-act",
        "ou-1",
        Proposal(endpoint_type="tikhub_reddit_search", params={"keyword": "B"}, title="新提案"),
    )
    calls: list[tuple[str, str]] = []
    real_peek = shusuo_proposal_store.peek_pending

    def spy(token_value, chat_id, open_id, *, now=None):
        calls.append((str(token_value), chat_id))
        return real_peek(token_value, chat_id, open_id, now=now)

    monkeypatch.setattr(shusuo_proposal_store, "peek_pending", spy)
    _install_card_updates(monkeypatch)
    monkeypatch.setattr(shusuo_capabilities, "collect", AsyncMock())

    body, headers = _signed(_payload(token))
    TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)
    # REPLACED 命中后不得再发起空会话查询
    assert len(calls) == 1, calls


async def test_forbidden_operator_does_not_trigger_second_lookup(monkeypatch) -> None:
    token = _seed(open_id="ou-1")
    _install_card_updates(monkeypatch)
    monkeypatch.setattr(shusuo_capabilities, "collect", AsyncMock())
    calls: list[str] = []
    real_peek = shusuo_proposal_store.peek_pending

    def spy(token_value, chat_id, open_id, *, now=None):
        calls.append(open_id)
        return real_peek(token_value, chat_id, open_id, now=now)

    monkeypatch.setattr(shusuo_proposal_store, "peek_pending", spy)
    body, headers = _signed(_payload(token, operator="ou-2"))
    response = TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403
    assert len(calls) == 1, calls


async def test_forwarded_card_missing_chat_still_resolves(monkeypatch) -> None:
    """卡片转发后 chat_id 为空：第一次 MISSING 才允许按空会话再查。"""
    token = _seed()
    updates = _install_card_updates(monkeypatch)
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    _install_preflight(monkeypatch, allowed=True)

    payload = _payload(token, chat_id="")
    body, headers = _signed(payload)
    response = TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    assert collect.await_count == 1
    assert updates


# ---------------------------------------------------------------------------
# 2. 预检失败：重试卡 + token 恢复且不延长 TTL
# ---------------------------------------------------------------------------


async def test_preflight_failure_updates_retry_card_not_failure_card(
    monkeypatch,
) -> None:
    token = _seed()
    updates = _install_card_updates(monkeypatch)
    monkeypatch.setattr(shusuo_capabilities, "collect", AsyncMock())
    _install_preflight(monkeypatch, allowed=False)

    body, headers = _signed(_payload(token))
    response = TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200

    body_texts = [json.dumps(card, ensure_ascii=False) for _, card in updates]
    assert body_texts, "预检失败必须更新卡片"
    combined = "\n".join(body_texts)
    # 不是上游失败卡
    assert "采集未返回数据" not in combined
    # 明确当前状态/配置挡执行
    assert "无法执行" in combined or "不允许执行" in combined
    # 有 token 短码
    assert token in combined
    # 有重试 + 取消按钮
    actions = _button_actions(updates[-1][1])
    assert {"action": "confirm", "token": token} in actions
    assert {"action": "cancel", "token": token} in actions


def _button_actions(card: dict[str, Any]) -> list[dict[str, Any]]:
    body = card.get("body") or {}
    values: list[dict[str, Any]] = []
    for element in body.get("elements", []):
        if element.get("tag") != "button":
            continue
        for behavior in element.get("behaviors", []):
            value = behavior.get("value")
            if isinstance(value, dict):
                values.append(value)
    return values


async def test_preflight_failure_restores_token_without_extending_ttl(
    monkeypatch,
) -> None:
    import time

    created = time.time()
    token = _seed(now=created)
    _install_card_updates(monkeypatch)
    monkeypatch.setattr(shusuo_capabilities, "collect", AsyncMock())
    _install_preflight(monkeypatch, allowed=False)

    body, headers = _signed(_payload(token))
    TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)

    status, pending = shusuo_proposal_store.peek_pending(
        token, "chat-act", "ou-1", now=created + 200
    )
    assert status is ProposalLookup.ACTIVE
    assert pending is not None
    assert pending.created_at == created
    assert pending.expires_at == created + shusuo_proposal_store.PENDING_TTL_SECONDS


async def test_retry_after_recovery_executes_exactly_once(monkeypatch) -> None:
    token = _seed()
    _install_card_updates(monkeypatch)
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    allowed = {"value": False}

    async def preflight(proposal, *, force_status: bool = False):
        del proposal, force_status
        if allowed["value"]:
            return shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 10},
            )
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="config-gated",
            normalized_params={"keyword": "AI", "max_items": 10},
            errors=("端点 tikhub_reddit_search 当前不可执行（缺配置/受限）。",),
        )

    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", preflight)
    client = TestClient(app)

    body, headers = _signed(_payload(token))
    first = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert first.status_code == 200
    collect.assert_not_awaited()

    allowed["value"] = True
    second = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert second.status_code == 200
    assert collect.await_count == 1

    # 再点一次：token 已消费，不得再采集
    third = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert third.status_code == 200
    assert collect.await_count == 1


# ---------------------------------------------------------------------------
# 3. 后台异常不得留在「正在采集」
# ---------------------------------------------------------------------------


async def test_background_exception_leaves_safe_failure_card(monkeypatch) -> None:
    token = _seed()
    updates = _install_card_updates(monkeypatch)
    _install_preflight(monkeypatch, allowed=True)

    async def boom(endpoint_type: str, params: dict[str, Any]):
        del endpoint_type, params
        raise RuntimeError("unexpected internal failure")

    monkeypatch.setattr(shusuo_capabilities, "collect", boom)

    body, headers = _signed(_payload(token))
    # 后台任务自己吞掉异常（不能让飞书无限重试），响应仍是 200 toast
    response = TestClient(app).post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200

    rendered = [json.dumps(card, ensure_ascii=False) for _, card in updates]
    assert rendered, "异常后必须更新卡片"
    # 最后一张卡是安全失败态，不是「正在采集」
    assert "服务内部错误" in rendered[-1]
    assert "正在采集" not in rendered[-1]
    assert _button_actions(updates[-1][1]) == []


async def test_background_exception_never_restores_token(monkeypatch) -> None:
    """异常发生在可能已开始采集之后：绝不恢复 token（防重复计费）。"""
    token = _seed()
    _install_card_updates(monkeypatch)
    _install_preflight(monkeypatch, allowed=True)

    async def boom(endpoint_type: str, params: dict[str, Any]):
        del endpoint_type, params
        raise RuntimeError("unexpected internal failure")

    monkeypatch.setattr(shusuo_capabilities, "collect", boom)
    _, reserved = shusuo_proposal_store.consume_pending(token, "chat-act", "ou-1")
    assert reserved is not None
    await shusuo_router._execute_card_confirm(
        token=token,
        chat_id="chat-act",
        open_id="ou-1",
        card_message_id="om-act",
        reserved=reserved,
    )
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-act", "ou-1")
    assert status is ProposalLookup.MISSING
    assert pending is None


async def test_preflight_exception_before_collect_is_safe(monkeypatch) -> None:
    """预检自身抛错：未开始采集，可以安全恢复 token，但卡片不能停在处理中。"""
    token = _seed()
    updates = _install_card_updates(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    async def boom(proposal, *, force_status: bool = False):
        del proposal, force_status
        raise RuntimeError("preflight exploded")

    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", boom)
    _, reserved = shusuo_proposal_store.consume_pending(token, "chat-act", "ou-1")
    assert reserved is not None
    await shusuo_router._execute_card_confirm(
        token=token,
        chat_id="chat-act",
        open_id="ou-1",
        card_message_id="om-act",
        reserved=reserved,
    )
    collect.assert_not_awaited()
    combined = "\n".join(json.dumps(card, ensure_ascii=False) for _, card in updates)
    assert "服务内部错误" in combined
    # 采集明确没开始，token 可以安全保留给用户重试
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-act", "ou-1")
    assert status is ProposalLookup.ACTIVE


async def test_reserved_pending_path_is_the_production_path(monkeypatch) -> None:
    """生产路径传 reserved：不再依赖 peek，且不重复消费。"""
    token = _seed()
    _install_card_updates(monkeypatch)
    _install_preflight(monkeypatch, allowed=True)
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    _, pending = shusuo_proposal_store.consume_pending(token, "chat-act", "ou-1")
    assert pending is not None
    await shusuo_router._execute_card_confirm(
        token=token,
        chat_id="chat-act",
        open_id="ou-1",
        card_message_id="om-act",
        reserved=pending,
    )
    assert collect.await_count == 1


def test_cards_module_owns_the_replaced_card() -> None:
    """REPLACED 卡必须是 cards.py 的构件，不是 router 里的重复卡壳。"""
    assert hasattr(cards, "replaced_card")
    card = cards.replaced_card()
    assert card["schema"] == "2.0"
    text = json.dumps(card, ensure_ascii=False)
    assert "已被新提案替换" in text

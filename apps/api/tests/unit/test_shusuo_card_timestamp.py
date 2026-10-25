"""卡片回调的时间戳新鲜度。

签名覆盖 timestamp+nonce+body，所以重放一份旧请求的签名仍然有效；
必须额外拒绝超出 300 秒窗口的时间戳，否则回放可以反复触发执行路径。
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import proposal_store as shusuo_proposal_store
from data_intelligence_hub.agents.shusuo.config import get_shushuo_config
from data_intelligence_hub.main import app

CARD_ACTION_PATH = "/api/agents/shusuo/card-action"


@pytest.fixture(autouse=True)
def _state():
    get_shushuo_config.cache_clear()
    shusuo_proposal_store.clear_all()
    yield
    shusuo_proposal_store.clear_all()
    get_shushuo_config.cache_clear()


def _config(monkeypatch, *, encrypt_key: str = "ts-key", allowed: str = "ou-1") -> str:
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.setenv("LARK_SHUSUO_VERIFICATION_TOKEN", "vt-ts")
    monkeypatch.setenv("LARK_SHUSUO_APP_ID", "app-ts")
    monkeypatch.setenv("SHUSUO_ALLOWED_OPEN_IDS", allowed)
    get_shushuo_config.cache_clear()
    return encrypt_key


def _payload(token: str = "TOKEN1234", action: str = "confirm") -> dict[str, Any]:
    return {
        "schema": "2.0",
        "header": {"token": "vt-ts", "app_id": "app-ts"},
        "event": {
            "operator": {"open_id": "ou-1"},
            "action": {"value": {"action": action, "token": token}},
            "context": {"open_message_id": "om-ts", "open_chat_id": "chat-ts"},
        },
    }


def _signed(
    payload: dict[str, Any], encrypt_key: str, *, timestamp: str, nonce: str = "n"
) -> tuple[str, dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    signature = hashlib.sha256(
        f"{timestamp}{nonce}{encrypt_key}{body}".encode()
    ).hexdigest()
    return body, {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
        "Content-Type": "application/json",
    }


def _now() -> int:
    return int(time.time())


def test_fresh_timestamp_is_accepted(monkeypatch) -> None:
    encrypt_key = _config(monkeypatch)
    client = TestClient(app)
    body, headers = _signed(_payload(), encrypt_key, timestamp=str(_now()))
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200


@pytest.mark.parametrize("skew", [0, 1, 299])
def test_timestamp_within_window_is_accepted(monkeypatch, skew: int) -> None:
    encrypt_key = _config(monkeypatch)
    client = TestClient(app)
    body, headers = _signed(_payload(), encrypt_key, timestamp=str(_now() - skew))
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200


def test_window_boundary_is_inclusive_at_300_seconds(monkeypatch) -> None:
    """边界用冻结时钟：真实时钟的小数秒会让 300 秒抖动成 300.x。"""
    from data_intelligence_hub.agents.shusuo import router as shusuo_router

    frozen = 1_800_000_000.0
    monkeypatch.setattr(shusuo_router.time, "time", lambda: frozen)
    assert shusuo_router._timestamp_is_fresh(str(int(frozen) - 300)) is True
    assert shusuo_router._timestamp_is_fresh(str(int(frozen) - 301)) is False
    assert shusuo_router._timestamp_is_fresh(str(int(frozen) + 300)) is True
    assert shusuo_router._timestamp_is_fresh(str(int(frozen) + 301)) is False


@pytest.mark.parametrize("skew", [301, 3600, 86400])
def test_stale_timestamp_is_rejected(monkeypatch, skew: int) -> None:
    encrypt_key = _config(monkeypatch)
    client = TestClient(app)
    body, headers = _signed(_payload(), encrypt_key, timestamp=str(_now() - skew))
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


@pytest.mark.parametrize("skew", [301, 3600])
def test_future_timestamp_beyond_window_is_rejected(monkeypatch, skew: int) -> None:
    encrypt_key = _config(monkeypatch)
    client = TestClient(app)
    body, headers = _signed(_payload(), encrypt_key, timestamp=str(_now() + skew))
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "timestamp",
    ["", "abc", "1e9", "17000000.5", " 17000000 ", "-1", "99999999999999999999999"],
)
def test_malformed_timestamp_is_rejected(monkeypatch, timestamp: str) -> None:
    encrypt_key = _config(monkeypatch)
    client = TestClient(app)
    body, headers = _signed(_payload(), encrypt_key, timestamp=timestamp)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


async def test_stale_callback_does_not_execute_action(monkeypatch) -> None:
    """拒绝必须发生在动作执行之前：不消费 token、不采集。"""
    from unittest.mock import AsyncMock

    from data_intelligence_hub.agents.shusuo import commands

    encrypt_key = _config(monkeypatch)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 10},
            )
        ),
    )
    reply = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-ts",
        open_id="ou-1",
        message_id="om-src",
    )
    assert reply.pending_token
    token = reply.pending_token
    shusuo_proposal_store.attach_message_ids(token, card_message_id="om-ts")

    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    client = TestClient(app)
    body, headers = _signed(
        _payload(token=token), encrypt_key, timestamp=str(_now() - 600)
    )
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403
    collect.assert_not_awaited()
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-ts", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE
    assert pending is not None


async def test_replay_of_old_signed_body_is_rejected(monkeypatch) -> None:
    """签名有效的旧请求体重放：时间戳超窗，403。"""
    from unittest.mock import AsyncMock

    from data_intelligence_hub.agents.shusuo import commands

    encrypt_key = _config(monkeypatch)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 10},
            )
        ),
    )
    reply = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-ts",
        open_id="ou-1",
        message_id="om-src",
    )
    assert reply.pending_token
    token = reply.pending_token
    shusuo_proposal_store.attach_message_ids(token, card_message_id="om-ts")

    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    client = TestClient(app)

    # 首次：新鲜时间戳，正常执行
    body, headers = _signed(_payload(token=token), encrypt_key, timestamp=str(_now()))
    first = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert first.status_code == 200

    # 重放同一个 body + 同一个签名，只是把本地时钟推到窗口外
    stale = str(_now() - 4000)
    body2, headers2 = _signed(_payload(token=token), encrypt_key, timestamp=stale)
    replay = client.post(CARD_ACTION_PATH, content=body2, headers=headers2)
    assert replay.status_code == 403
    assert collect.await_count == 1

"""数说飞书机器人的契约测试。"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import Response
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import commands
from data_intelligence_hub.agents.shusuo import intents as shusuo_intents
from data_intelligence_hub.agents.shusuo import proposal_store as shusuo_proposal_store
from data_intelligence_hub.agents.shusuo import replies as shusuo_replies
from data_intelligence_hub.agents.shusuo import router as shusuo_router
from data_intelligence_hub.agents.shusuo.config import get_shushuo_config
from data_intelligence_hub.main import app
from data_intelligence_hub.platform_packages.models import PackageEndpoint
from data_intelligence_hub.platform_packages.service import CapabilityNotFoundError

WEBHOOK_PATH = "/api/agents/shusuo/webhook"
HEALTH_PATH = "/api/agents/shusuo/health"
CARD_ACTION_PATH = "/api/agents/shusuo/card-action"


@pytest.fixture(autouse=True)
def _clear_state():
    get_shushuo_config.cache_clear()
    shusuo_router._seen_events.clear()
    shusuo_proposal_store.clear_all()
    yield
    shusuo_router._seen_events.clear()
    shusuo_proposal_store.clear_all()
    get_shushuo_config.cache_clear()


def _encrypt(payload: dict[str, object], encrypt_key: str) -> str:
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(json.dumps(payload).encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode("ascii")


def _sign(timestamp: str, nonce: str, encrypt_key: str, body: str) -> str:
    return hashlib.sha256(f"{timestamp}{nonce}{encrypt_key}{body}".encode()).hexdigest()


def test_router_is_mounted_at_expected_prefix() -> None:
    paths = {route.path for route in app.routes}
    assert WEBHOOK_PATH in paths
    assert HEALTH_PATH in paths
    assert CARD_ACTION_PATH in paths


def test_health_reports_not_ready_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("LARK_SHUSUO_APP_ID", raising=False)
    monkeypatch.delenv("LARK_SHUSUO_APP_SECRET", raising=False)
    get_shushuo_config.cache_clear()
    client = TestClient(app)
    response = client.get(HEALTH_PATH)
    assert response.status_code == 200
    assert response.json()["ready"] is False


def test_webhook_challenge_is_echoed(monkeypatch) -> None:
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    get_shushuo_config.cache_clear()
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        json={"type": "url_verification", "challenge": "challenge-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-token"}


def test_url_verification_echoes_even_if_token_mismatches(monkeypatch) -> None:
    """飞书在应用新 token 之前会用旧 token 校验地址，必须仍回显 challenge。"""
    monkeypatch.setenv("LARK_SHUSUO_VERIFICATION_TOKEN", "expected")
    get_shushuo_config.cache_clear()
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        json={"type": "url_verification", "challenge": "x", "token": "old"},
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "x"}


def test_event_rejects_wrong_verification_token(monkeypatch) -> None:
    monkeypatch.setenv("LARK_SHUSUO_VERIFICATION_TOKEN", "expected")
    get_shushuo_config.cache_clear()
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        json={
            "header": {
                "event_type": "im.message.receive_v1",
                "event_id": "evt-wrong-token",
                "token": "wrong",
            },
            "event": {},
        },
    )
    assert response.status_code == 403


def test_encrypted_challenge_is_decrypted(monkeypatch) -> None:
    encrypt_key = "test-encrypt-key"
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    get_shushuo_config.cache_clear()

    encrypted = _encrypt(
        {"type": "url_verification", "challenge": "encrypted-challenge", "token": "t"},
        encrypt_key,
    )
    body = json.dumps({"encrypt": encrypted})
    timestamp, nonce = "1700000000", "nonce"
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": _sign(timestamp, nonce, encrypt_key, body),
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "encrypted-challenge"}


def test_encrypted_challenge_rejects_bad_signature(monkeypatch) -> None:
    encrypt_key = "test-encrypt-key"
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    get_shushuo_config.cache_clear()
    body = json.dumps({"encrypt": _encrypt({"type": "url_verification"}, encrypt_key)})
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": "bad",
            "X-Lark-Request-Timestamp": "1",
            "X-Lark-Request-Nonce": "n",
        },
    )
    assert response.status_code == 403


async def test_help_event_replies_with_help_text(monkeypatch) -> None:
    replies: list[str] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()

    envelope = {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-1"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_1",
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "帮助"}),
            },
        },
    }
    await shusuo_router._handle_envelope(envelope)
    assert len(replies) == 1
    assert "数说" in replies[0]
    assert "采集" in replies[0]


async def test_event_from_bot_is_ignored(monkeypatch) -> None:
    replies: list[str] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    envelope = {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-2"},
        "event": {
            "sender": {"sender_type": "app", "sender_id": {"open_id": "ou_bot"}},
            "message": {
                "message_id": "om_2",
                "chat_id": "oc_1",
                "message_type": "text",
                "content": json.dumps({"text": "帮助"}),
            },
        },
    }
    await shusuo_router._handle_envelope(envelope)
    assert replies == []


async def test_non_text_message_gets_hint(monkeypatch) -> None:
    replies: list[str] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    envelope = {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-3"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_3",
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "message_type": "image",
                "content": "{}",
            },
        },
    }
    await shusuo_router._handle_envelope(envelope)
    assert replies and "只支持文字指令" in replies[0]


async def test_allowlist_blocks_unknown_user(monkeypatch) -> None:
    monkeypatch.setenv("SHUSUO_ALLOWED_OPEN_IDS", "ou_allowed")
    get_shushuo_config.cache_clear()
    replies: list[str] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    envelope = {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-4"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_other"}},
            "message": {
                "message_id": "om_4",
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "帮助"}),
            },
        },
    }
    await shusuo_router._handle_envelope(envelope)
    assert replies and "没有使用数说的权限" in replies[0]


def test_parse_params_coerces_scalars_and_json() -> None:
    params = commands.parse_params(['keyword=AI', "max_items=5", "enabled=true", 'urls=["a","b"]'])
    assert params == {"keyword": "AI", "max_items": 5, "enabled": True, "urls": ["a", "b"]}


def test_parse_command_extracts_collect() -> None:
    command = commands.parse_command("采集 tikhub_reddit_search keyword=AI max_items=5")
    assert command.name == "collect"
    assert command.argument == "tikhub_reddit_search"
    assert command.params == {"keyword": "AI", "max_items": 5}


def test_parse_command_rejects_malformed_params() -> None:
    command = commands.parse_command("采集 tikhub_reddit_search keyword")
    assert command.name == "collect_error"
    assert "key=value" in command.argument


def test_parse_confirm_and_cancel_keep_token() -> None:
    assert commands.parse_command("确认 ABC123").argument == "ABC123"
    assert commands.parse_command("取消 ABC123").argument == "ABC123"


def test_parse_confirm_and_cancel_bare_have_no_token() -> None:
    assert commands.parse_command("确认").argument == ""
    assert commands.parse_command("取消").argument == ""


async def test_explicit_collect_blocked_by_preflight(monkeypatch) -> None:
    """显式采集预检失败时返回统一错误文本，不进入 capabilities.collect。"""
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(
            True, "采集完成", endpoint_type=endpoint_type
        )

    async def fake_preflight(proposal, *, force_status: bool = False):
        assert force_status is True
        assert proposal.endpoint_type == "tikhub_reddit_search"
        assert proposal.params == {"keyword": "AI", "max_items": 5}
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="degraded",
            normalized_params=dict(proposal.params),
            errors=("端点当前不可用，已取消采集。",),
        )

    monkeypatch.setattr(shusuo_capabilities, "collect", fake_collect)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    reply = await commands.execute(
        commands.Command("collect", "tikhub_reddit_search", {"keyword": "AI", "max_items": 5})
    )
    assert calls == []
    assert "端点当前不可用，已取消采集。" in reply.text
    assert reply.text.startswith("无法执行采集：")
    assert reply.ack is None


async def test_explicit_collect_runs_preflight_with_force_status(monkeypatch) -> None:
    """显式采集必须以 force_status=True 预检，通过后才执行采集。"""
    calls: list[tuple[str, dict[str, object]]] = []
    preflight_calls: list[tuple[str, bool]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(
            True, "采集完成", endpoint_type=endpoint_type
        )

    async def fake_preflight(proposal, *, force_status: bool = False):
        preflight_calls.append((proposal.endpoint_type, force_status))
        return shusuo_capabilities.PreflightResult(
            allowed=True,
            availability="verified",
            normalized_params=dict(proposal.params),
        )

    monkeypatch.setattr(shusuo_capabilities, "collect", fake_collect)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    reply = await commands.execute(
        commands.Command("collect", "tikhub_reddit_search", {"keyword": "AI", "max_items": 5})
    )
    assert preflight_calls == [("tikhub_reddit_search", True)]
    assert calls == [("tikhub_reddit_search", {"keyword": "AI", "max_items": 5})]
    assert reply.text.startswith("采集完成")
    assert "端点：tikhub_reddit_search" in reply.text


async def test_explicit_collect_preflight_unknown_endpoint(monkeypatch) -> None:
    """显式采集未知端点：预检拒绝，统一文案，不暴露内部异常。"""
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(
            True, "采集完成", endpoint_type=endpoint_type
        )

    async def fake_preflight(proposal, *, force_status: bool = False):
        assert force_status is True
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="unknown",
            normalized_params=dict(proposal.params),
            errors=("没有找到端点：no_such_endpoint",),
        )

    monkeypatch.setattr(shusuo_capabilities, "collect", fake_collect)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    reply = await commands.execute(
        commands.Command("collect", "no_such_endpoint", {"keyword": "AI"})
    )
    assert calls == []
    assert "没有找到端点：no_such_endpoint" in reply.text
    assert reply.text.startswith("无法执行采集：")


async def test_explicit_collect_preflight_join_multiple_errors(monkeypatch) -> None:
    """多个预检错误全部返回，便于用户一次修正。"""
    async def fake_preflight(proposal, *, force_status: bool = False):
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="verified",
            normalized_params={},
            errors=("缺少必填参数：query", "未知参数：unknown"),
        )

    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    reply = await commands.execute(
        commands.Command("collect", "demo_endpoint", {"unknown": 1})
    )
    assert "缺少必填参数：query" in reply.text
    assert "未知参数：unknown" in reply.text


def test_clean_text_removes_mentions() -> None:
    assert commands.clean_text("@_user_1 帮助") == "帮助"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@_user_1 帮助", "帮助"),
        ("@_user_1 @_user_2 帮助", "帮助"),
        ("@_all 帮助", "帮助"),
        ("  @_user_1   帮助  ", "帮助"),
    ],
)
def test_clean_text_removes_all_mentions(
    raw: str, expected: str
) -> None:
    assert commands.clean_text(raw) == expected


def _availability(**overrides):
    from data_intelligence_hub.platform_packages.status import EndpointAvailability

    values = {
        "endpoint_type": "demo",
        "availability": "verified",
        "missing_configuration": (),
        "last_test_status": None,
        "last_test_at": None,
        "last_records_count": None,
        "last_error_message": None,
        "policy_block_reason": None,
    }
    values.update(overrides)
    return EndpointAvailability(**values)


def test_block_reason_blocks_policy_denied() -> None:
    live = _availability(
        availability="config-gated",
        policy_block_reason="collection_policy_denied: no controlled egress",
    )
    reason = shusuo_capabilities._block_reason("demo", live)
    assert reason is not None
    assert "外访策略" in reason


def _endpoint(
    *,
    endpoint_type: str = "demo",
    status: str = "verified",
    required_params: tuple[str, ...] = (),
    optional_params: tuple[str, ...] = (),
    cost_hint: str | None = None,
    policy_block_reason: str | None = None,
) -> PackageEndpoint:
    return PackageEndpoint(
        capability_id=endpoint_type,
        canonical_capability_id=endpoint_type,
        is_alias_view=False,
        endpoint_type=endpoint_type,
        label=endpoint_type,
        platform="test",
        description="test endpoint",
        status=status,
        required_params=required_params,
        optional_params=optional_params,
        cost_hint=cost_hint,
        provider="test",
        provider_group="test",
        provider_label="test",
        content_type="post",
        method="GET",
        param_fields={},
        policy_block_reason=policy_block_reason,
    )


async def test_preflight_allows_verified_unknown_cost(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI", "max_items": 10},
        title="Reddit 搜索",
        estimated_items=10,
    )
    endpoint = _endpoint(
        endpoint_type="tikhub_reddit_search",
        required_params=("query",),
        optional_params=("max_items",),
        cost_hint=None,
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert result.availability == "verified"
    assert result.errors == ()
    assert result.warnings == ("费用未知，按上游实际计费。",)
    assert result.cost_notice == "费用未知，按上游实际计费"
    assert result.normalized_params == {"query": "AI", "max_items": 10}


@pytest.mark.parametrize(
    "availability",
    ["config-gated", "disabled", "degraded", "empty", "untested"],
)
async def test_preflight_rejects_non_verified(monkeypatch, availability: str) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI"},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(endpoint_type="tikhub_reddit_search", required_params=("query",))
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(
                    endpoint_type=endpoint.endpoint_type, availability=availability
                )
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert result.availability == availability
    assert result.errors


async def test_preflight_rejects_when_live_missing_and_static_not_verified(
    monkeypatch,
) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI"},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(
        endpoint_type="tikhub_reddit_search", required_params=("query",), status="pending"
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert result.availability == "pending"


async def test_preflight_uses_live_status_over_static_when_missing_live_entry(
    monkeypatch,
) -> None:
    """实时状态缺失时按规则回退静态 status：verified 放行。"""
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI"},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(
        endpoint_type="tikhub_reddit_search", required_params=("query",), status="verified"
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert result.availability == "verified"


async def test_preflight_live_status_beats_static_status(monkeypatch) -> None:
    """实时状态存在且不是 verified 时，静态 verified 也不放行。"""
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI"},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(
        endpoint_type="tikhub_reddit_search", required_params=("query",), status="verified"
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(
                    endpoint_type=endpoint.endpoint_type, availability="degraded"
                )
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert result.availability == "degraded"


async def test_preflight_rejects_unknown_endpoint(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="no_such_endpoint", params={}, title="未知端点"
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "get_capability",
        AsyncMock(side_effect=CapabilityNotFoundError("no_such_endpoint")),
    )
    monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert result.availability == "unknown"
    assert result.errors == ("没有找到端点：no_such_endpoint",)


async def test_preflight_rejects_missing_and_unknown_params(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"unknown": 1},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(
        endpoint_type="tikhub_reddit_search",
        required_params=("query",),
        optional_params=("max_items",),
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert "缺少必填参数：query" in result.errors
    assert "未知参数：unknown" in result.errors


async def test_preflight_missing_required_param_fails_closed(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "  "},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(endpoint_type="tikhub_reddit_search", required_params=("query",))
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert "缺少必填参数：query" in result.errors


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_items", 0),
        ("max_items", 51),
        ("maxItems", 51),
        ("num_results", 0),
        ("commentsPerPost", 51),
    ],
)
async def test_preflight_rejects_out_of_range_quantity(monkeypatch, key: str, value: int) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI", key: value},
        title="数量越界",
    )
    endpoint = _endpoint(
        endpoint_type="demo_endpoint",
        required_params=("query",),
        optional_params=(key,),
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert "数量必须在 1 到 50 之间" in result.errors[0]


@pytest.mark.parametrize(
    ("key", "value", "optional"),
    [
        ("max_items", 50, ()),
        ("maxItems", 1, ()),
        ("num_results", 50, ("num_results",)),
        ("commentsPerPost", 25, ("commentsPerPost",)),
        ("max_total_charge_usd", 5.0, ()),
        ("run_timeout_seconds", 600, ()),
    ],
)
async def test_preflight_accepts_in_range_quantity_and_meta_keys(
    monkeypatch, key: str, value: object, optional: tuple[str, ...]
) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI", key: value},
        title="数量合法",
    )
    endpoint = _endpoint(
        endpoint_type="demo_endpoint",
        required_params=("query",),
        optional_params=optional,
        cost_hint="~$0.001/条",
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert result.warnings == ()
    assert result.normalized_params[key] == value


async def test_preflight_rejects_universal_quantity_without_declaration_and_unknown_keys(
    monkeypatch,
) -> None:
    """非通用数量键未被端点声明时拒绝；完全未知的键也拒绝。"""
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI", "num_results": 10, "totally_unknown": 1},
        title="未声明参数",
    )
    endpoint = _endpoint(endpoint_type="demo_endpoint", required_params=("query",))
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert "未知参数：num_results" in result.errors
    assert "未知参数：totally_unknown" in result.errors


async def test_preflight_policy_block_reason_not_leaked(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI"},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(endpoint_type="tikhub_reddit_search", required_params=("query",))
    secret_reason = "collection_policy_denied: no controlled egress SECRET-REASON"
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(
                    endpoint_type=endpoint.endpoint_type,
                    availability="config-gated",
                    policy_block_reason=secret_reason,
                )
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert result.errors == ("当前受安全策略限制，无法执行该端点。",)
    assert all("SECRET-REASON" not in error for error in result.errors)
    assert all("collection_policy_denied" not in error for error in result.errors)


async def test_preflight_static_policy_block_reason_not_leaked(monkeypatch) -> None:
    """实时状态缺失时，静态目录的 policy_block_reason 也不得泄漏。"""
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"query": "AI"},
        title="Reddit 搜索",
    )
    endpoint = _endpoint(
        endpoint_type="tikhub_reddit_search",
        required_params=("query",),
        policy_block_reason="collection_policy_denied: STATIC-SECRET",
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(shusuo_capabilities, "live_status", AsyncMock(return_value={}))
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is False
    assert result.errors == ("当前受安全策略限制，无法执行该端点。",)
    assert all("STATIC-SECRET" not in error for error in result.errors)


@pytest.mark.parametrize(
    "cost_hint",
    [None, "", "按量计费", "按上游实际计费", "按结果计费，费用未知"],
)
async def test_preflight_warns_on_unknown_cost(monkeypatch, cost_hint: str | None) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI"},
        title="费用未知",
    )
    endpoint = _endpoint(
        endpoint_type="demo_endpoint",
        required_params=("query",),
        cost_hint=cost_hint,
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert result.warnings == ("费用未知，按上游实际计费。",)
    assert result.cost_notice == "费用未知，按上游实际计费"


async def test_preflight_known_cost_has_no_warning(monkeypatch) -> None:
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI"},
        title="费用已知",
    )
    endpoint = _endpoint(
        endpoint_type="demo_endpoint",
        required_params=("query",),
        cost_hint="~$0.001/条",
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert result.warnings == ()
    assert result.cost_notice == "费用约 ~$0.001/条"


async def test_preflight_propagates_force_status(monkeypatch) -> None:
    """显式采集要求 force_status=True 透传给 live_status。"""
    proposal = shusuo_intents.Proposal(
        endpoint_type="demo_endpoint",
        params={"query": "AI"},
        title="强制刷新",
    )
    endpoint = _endpoint(endpoint_type="demo_endpoint", required_params=("query",))
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    live_status_mock = AsyncMock(
        return_value={
            endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
        }
    )
    monkeypatch.setattr(shusuo_capabilities, "live_status", live_status_mock)
    await shusuo_capabilities.preflight_proposal(proposal, force_status=True)
    live_status_mock.assert_awaited_once_with(force=True)


async def test_preflight_keeps_collector_param_keys(monkeypatch) -> None:
    """不改名：commentsPerPost 等采集器键原样保留在 normalized_params。"""
    proposal = shusuo_intents.Proposal(
        endpoint_type="apify_tiktok_comments_scraper",
        params={"postURLs": ["https://www.tiktok.com/@user/video/123"], "commentsPerPost": 10},
        title="TikTok 评论",
    )
    endpoint = _endpoint(
        endpoint_type="apify_tiktok_comments_scraper",
        required_params=("postURLs",),
        optional_params=("commentsPerPost",),
        cost_hint="按事件计费",
    )
    monkeypatch.setattr(
        shusuo_capabilities, "get_capability", AsyncMock(return_value=endpoint)
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "live_status",
        AsyncMock(
            return_value={
                endpoint.endpoint_type: _availability(endpoint_type=endpoint.endpoint_type)
            }
        ),
    )
    result = await shusuo_capabilities.preflight_proposal(proposal)
    assert result.allowed is True
    assert result.normalized_params == {
        "postURLs": ["https://www.tiktok.com/@user/video/123"],
        "commentsPerPost": 10,
    }


def test_block_reason_blocks_missing_configuration() -> None:
    live = _availability(
        availability="config-gated",
        missing_configuration=("MEDIACRAWLER_BASE_URL",),
    )
    reason = shusuo_capabilities._block_reason("demo", live)
    assert reason is not None
    assert "MEDIACRAWLER_BASE_URL" in reason


def test_block_reason_allows_verified() -> None:
    assert shusuo_capabilities._block_reason("demo", _availability()) is None


def test_intent_social_search_with_platform() -> None:
    proposal = shusuo_intents.build_proposal("搜 reddit AI max_items=5")
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "tikhub_reddit_search"
    assert proposal.params == {"keyword": "AI", "max_items": 5}


def test_intent_social_search_without_platform_uses_exa() -> None:
    proposal = shusuo_intents.build_proposal("搜 AI 应用")
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "exa_search_auto"
    assert proposal.params["query"] == "AI 应用"


def test_intent_comment_parses_tiktok_url() -> None:
    proposal = shusuo_intents.build_proposal(
        "评论 https://www.tiktok.com/@user/video/123 max_items=8"
    )
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "apify_tiktok_comments_scraper"
    assert proposal.params["postURLs"] == ["https://www.tiktok.com/@user/video/123"]
    assert proposal.params["commentsPerPost"] == 8


def test_intent_comment_parses_reddit_url() -> None:
    proposal = shusuo_intents.build_proposal(
        "评论 https://www.reddit.com/r/test/comments/abc123/title/"
    )
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "tikhub_reddit_post_comments"
    assert proposal.params["post_id"] == "abc123"


def test_intent_comment_parses_youtube_url() -> None:
    proposal = shusuo_intents.build_proposal(
        "评论 https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "tikhub_youtube_video_comments"
    assert proposal.params["video_id"] == "dQw4w9WgXcQ"


def test_intent_price_accepts_asin() -> None:
    proposal = shusuo_intents.build_proposal("价格 B000000001")
    assert not isinstance(proposal, str)
    assert proposal.endpoint_type == "apify_amazon_price_tracker"
    assert proposal.params["products"] == [
        {"url": "https://www.amazon.com/dp/B000000001"}
    ]


def test_intent_unknown_platform_returns_hint() -> None:
    result = shusuo_intents.build_proposal("账号 facebook nike")
    assert isinstance(result, str)
    assert "tiktok" in result


def test_intent_rejects_limit_above_50() -> None:
    result = shusuo_intents.build_proposal("搜 reddit AI max_items=51")
    assert result == "数量必须在 1 到 50 之间。"


def test_intent_rejects_fake_tiktok_domain() -> None:
    result = shusuo_intents.build_proposal(
        "评论 https://evil-tiktok.com/@user/video/123"
    )
    assert isinstance(result, str)
    assert "只支持 TikTok、Reddit、YouTube" in result


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_intent_parses_youtube_variants(url: str, video_id: str) -> None:
    proposal = shusuo_intents.build_proposal(f"评论 {url}")
    assert not isinstance(proposal, str)
    assert proposal.params["video_id"] == video_id


def test_intent_price_uses_object_array() -> None:
    proposal = shusuo_intents.build_proposal("价格 B000000001")
    assert not isinstance(proposal, str)
    assert proposal.params["products"] == [
        {"url": "https://www.amazon.com/dp/B000000001"}
    ]


def _preflight(allowed: bool, **overrides) -> shusuo_capabilities.PreflightResult:
    values = {
        "allowed": allowed,
        "availability": "verified" if allowed else "degraded",
        "normalized_params": {"keyword": "AI", "max_items": 5},
        "errors": () if allowed else ("端点当前不可用，已取消采集。",),
        "warnings": (),
        "cost_notice": "费用未知，按上游实际计费",
    }
    values.update(overrides)
    return shusuo_capabilities.PreflightResult(**values)


async def test_intent_returns_card_without_collecting(monkeypatch) -> None:
    shusuo_proposal_store.clear_all()
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    reply = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
        message_id="om-1",
    )
    assert reply.card is not None
    assert reply.pending_token
    collect.assert_not_awaited()


async def test_intent_preflight_failure_keeps_no_pending(monkeypatch) -> None:
    """意图预检失败：返回统一错误文本，不留待确认提案，也绝不采集。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=False)),
    )
    reply = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    assert reply.card is None
    assert reply.pending_token is None
    assert reply.text.startswith("无法执行采集：")
    assert "端点当前不可用" in reply.text
    status, pending = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    assert pending is None
    collect.assert_not_awaited()


async def test_intent_replaces_previous_pending(monkeypatch) -> None:
    """新提案替换旧提案：旧 token 失效，只保留最新一张卡。"""
    shusuo_proposal_store.clear_all()
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    monkeypatch.setattr(
        shusuo_capabilities,
        "collect",
        AsyncMock(return_value=shusuo_capabilities.CollectOutcome(True, "采集完成")),
    )
    first = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    second = await commands.execute(
        commands.parse_command("搜 reddit ML"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    assert first.pending_token != second.pending_token
    status, pending = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE
    assert pending is not None
    assert pending.token == second.pending_token
    status, _ = shusuo_proposal_store.peek_pending(first.pending_token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.REPLACED


async def test_intent_text_carries_token_and_confirmation_hint(monkeypatch) -> None:
    """卡片失败时的文本兜底必须自带 token（短码）与确认指引。"""
    shusuo_proposal_store.clear_all()
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    reply = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    assert reply.pending_token in reply.text
    assert "确认" in reply.text
    assert "取消" in reply.text


async def test_confirm_consumes_before_collect_and_rejects_repeat(monkeypatch) -> None:
    """确认先消费 token 再采集；同一 token 第二次确认必须被拒。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    intent = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    token = intent.pending_token
    first = await commands.execute(
        commands.Command("confirm", token), chat_id="chat-1", open_id="ou-1"
    )
    second = await commands.execute(
        commands.Command("confirm", token), chat_id="chat-1", open_id="ou-1"
    )
    assert first.text != second.text
    collect.assert_awaited_once()


async def test_confirm_without_token_uses_single_active_proposal(monkeypatch) -> None:
    """裸「确认」只在当前上下文恰有一个活跃提案时生效。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    reply = await commands.execute(
        commands.Command("confirm"), chat_id="chat-1", open_id="ou-1"
    )
    assert reply.text.startswith("采集完成")
    collect.assert_awaited_once()
    status, _ = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING


async def test_confirm_without_pending_returns_hint() -> None:
    shusuo_proposal_store.clear_all()
    reply = await commands.execute(
        commands.Command("confirm"), chat_id="chat-empty", open_id="ou-1"
    )
    assert "没有待确认" in reply.text


async def test_confirm_runs_preflight_with_force_status_before_collect(
    monkeypatch,
) -> None:
    """确认路径：先 force_status=True 预检，失败不消费 token、不采集、不泄漏内部原因。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock()
    preflight_calls: list[tuple[shusuo_intents.Proposal, bool]] = []

    async def fake_preflight(proposal, *, force_status: bool = False):
        preflight_calls.append((proposal, force_status))
        if len(preflight_calls) == 1:
            # 意图提案预检通过（缓存状态即可）
            return shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params=dict(proposal.params),
            )
        # 确认时强刷新后变为策略拒绝
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="config-gated",
            normalized_params=dict(proposal.params),
            errors=("当前受安全策略限制，无法执行该端点。",),
        )

    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)

    intent = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    assert len(preflight_calls) == 1
    # 意图提案预检用缓存状态（force=False）；强刷新留给确认路径。
    assert preflight_calls[0][1] is False

    # 确认路径：peek → force preflight → 失败 → token 仍在（未被失败路径吃掉）
    token = intent.pending_token
    reply = await commands.execute(
        commands.Command("confirm", token), chat_id="chat-1", open_id="ou-1"
    )
    assert len(preflight_calls) == 2
    assert preflight_calls[1][1] is True
    assert collect.await_count == 0
    assert "当前受安全策略限制" in reply.text
    assert "CONFIRM-SECRET" not in reply.text
    assert "collection_policy_denied" not in reply.text
    # token 未被预检失败吃掉：显式取消能查到 ACTIVE 并清理
    assert (
        shusuo_proposal_store.cancel_pending(token, "chat-1", "ou-1")
        is shusuo_proposal_store.ProposalLookup.ACTIVE
    )


async def test_confirm_with_other_context_token_is_forbidden(monkeypatch) -> None:
    """token 属于其他上下文：拒绝执行，原提案保留。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    intent = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    reply = await commands.execute(
        commands.Command("confirm", intent.pending_token), chat_id="chat-2", open_id="ou-2"
    )
    assert "无法确认其他会话的提案" in reply.text
    collect.assert_not_awaited()
    status, _ = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE


async def test_confirm_replaced_token_is_rejected(monkeypatch) -> None:
    """旧 token 已被新提案替换：拒绝执行，提示回复新提案。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    first = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    await commands.execute(
        commands.parse_command("搜 reddit ML"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    reply = await commands.execute(
        commands.Command("confirm", first.pending_token), chat_id="chat-1", open_id="ou-1"
    )
    assert "替换" in reply.text
    collect.assert_not_awaited()


async def test_cancel_consumes_active_proposal(monkeypatch) -> None:
    """裸「取消」清理当前上下文提案；再确认提示没有待确认。"""
    shusuo_proposal_store.clear_all()
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    reply = await commands.execute(
        commands.Command("cancel"), chat_id="chat-1", open_id="ou-1"
    )
    assert "已取消" in reply.text
    status, _ = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    follow = await commands.execute(
        commands.Command("confirm"), chat_id="chat-1", open_id="ou-1"
    )
    assert "没有待确认" in follow.text
    collect.assert_not_awaited()


async def test_cancel_with_token_cancels_matching_proposal(monkeypatch) -> None:
    """带 token 的取消：只取消匹配提案。"""
    shusuo_proposal_store.clear_all()
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    intent = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    reply = await commands.execute(
        commands.Command("cancel", intent.pending_token), chat_id="chat-1", open_id="ou-1"
    )
    assert "已取消" in reply.text
    status, _ = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING


async def test_reply_texts_pass_fit_text(monkeypatch) -> None:
    """所有回复正文与 ack 显式经 fit_text（脱敏 + 6000 截断）。"""
    shusuo_proposal_store.clear_all()
    long_text = "x" * 8000

    async def fake_collect(endpoint_type, params):
        return shusuo_capabilities.CollectOutcome(False, long_text, endpoint_type=endpoint_type)

    async def fake_preflight(proposal, *, force_status: bool = False):
        return _preflight(allowed=True)

    monkeypatch.setattr(shusuo_capabilities, "collect", fake_collect)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    intent = await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    assert len(intent.text) <= shusuo_replies.MAX_REPLY_CHARS
    assert intent.ack is None or len(intent.ack) <= shusuo_replies.MAX_REPLY_CHARS
    confirm = await commands.execute(
        commands.Command("confirm"), chat_id="chat-1", open_id="ou-1"
    )
    assert len(confirm.text) <= shusuo_replies.MAX_REPLY_CHARS
    assert confirm.ack is not None and len(confirm.ack) <= shusuo_replies.MAX_REPLY_CHARS
    # 显式采集路径的预检强制 force_status=True
    forced = await commands.execute(
        commands.Command("collect", "tikhub_reddit_search", {"keyword": "AI", "max_items": 5}),
        chat_id="chat-1",
        open_id="ou-1",
    )
    assert len(forced.text) <= shusuo_replies.MAX_REPLY_CHARS


async def test_pending_is_isolated_by_chat_and_user(monkeypatch) -> None:
    """不同 chat 或不同用户各自持有独立提案。"""
    shusuo_proposal_store.clear_all()
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    await commands.execute(
        commands.parse_command("搜 reddit AI"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    status, _ = shusuo_proposal_store.peek_pending(None, "chat-1", "ou-2")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    status, _ = shusuo_proposal_store.peek_pending(None, "chat-2", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING


def test_intent_proposal_reply_requires_confirmation() -> None:
    proposal = shusuo_intents.build_proposal("热点 x")
    assert not isinstance(proposal, str)
    text = shusuo_intents.proposal_reply(proposal)
    assert "确认" in text
    assert "tikhub_x_trending" in text


def test_intent_proposal_reply_says_five_minutes() -> None:
    proposal = shusuo_intents.build_proposal("热点 x")
    assert not isinstance(proposal, str)
    text = shusuo_intents.proposal_reply(proposal)
    assert "5 分钟内有效" in text
    assert "10 分钟" not in text


async def test_unknown_without_llm_key_returns_help(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    reply = await commands.execute(commands.Command("unknown", "飞书会被墙挡吗"))
    assert "帮助" in reply.text


async def test_unknown_uses_llm_answer(monkeypatch) -> None:
    async def fake_answer(question: str) -> str:
        return f"回答：{question}"

    monkeypatch.setattr(commands.llm, "answer_question", fake_answer)
    reply = await commands.execute(commands.Command("unknown", "飞书会被墙挡吗"))
    assert reply.text == "回答：飞书会被墙挡吗"


def _p2p_envelope(text: str) -> dict[str, object]:
    return {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-p2p-gate"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_p2p_gate",
                "chat_id": "oc_p2p",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": text}),
            },
        },
    }


def _intent_card_flow_stubs(monkeypatch) -> tuple[list[str], list[dict[str, object]]]:
    """返回 (texts, cards)：reply_text/reply_card 的记录器；preflight 一律放行。"""
    texts: list[str] = []
    cards: list[dict[str, object]] = []

    async def fake_reply_text(message_id: str, text: str) -> str:
        texts.append(text)
        return "om_reply"

    async def fake_reply_card(message_id: str, card: dict[str, object]) -> str:
        cards.append(card)
        return "om_card_1"

    async def fake_bot_open_id() -> str:
        return "ou_bot"

    async def ok_preflight(proposal, *, force_status: bool = False):
        return shusuo_capabilities.PreflightResult(
            allowed=True,
            availability="verified",
            normalized_params=dict(proposal.params),
        )

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply_text)
    monkeypatch.setattr(shusuo_router.lark_client, "reply_card", fake_reply_card)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", ok_preflight)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    return texts, cards


async def test_card_send_success_attaches_message_ids(monkeypatch) -> None:
    """卡片发送成功：只发卡不发文本，pending 记录原消息与卡片消息 ID。"""
    shusuo_proposal_store.clear_all()
    texts, cards_sent = _intent_card_flow_stubs(monkeypatch)
    await shusuo_router._handle_envelope(_p2p_envelope("搜 reddit AI"))
    assert len(cards_sent) == 1
    assert texts == []
    pending_all = list(shusuo_proposal_store._PENDING_BY_TOKEN.values())
    assert len(pending_all) == 1
    pending = pending_all[0]
    assert pending.message_id == "om_p2p_gate"
    assert pending.card_message_id == "om_card_1"


async def test_card_send_failure_falls_back_to_text_with_token(monkeypatch) -> None:
    """卡片发送失败：结构化告警 + 文本兜底，文本必须携带 token 短码。"""
    shusuo_proposal_store.clear_all()
    texts, _cards = _intent_card_flow_stubs(monkeypatch)

    async def failing_card(message_id: str, card: dict[str, object]) -> str:
        raise RuntimeError("lark unavailable")

    monkeypatch.setattr(shusuo_router.lark_client, "reply_card", failing_card)
    with capture_logs() as logs:
        await shusuo_router._handle_envelope(_p2p_envelope("搜 reddit AI"))
    assert len(texts) == 1
    pending_all = list(shusuo_proposal_store._PENDING_BY_TOKEN.values())
    assert len(pending_all) == 1
    assert pending_all[0].token in texts[0]
    assert pending_all[0].card_message_id is None
    warning = next(
        entry for entry in logs if entry.get("event") == "shusuo_card_send_failed"
    )
    assert warning["error_type"] == "RuntimeError"
    assert "lark unavailable" not in str(warning)


def _group_envelope(*, mentions: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-group"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_group",
                "chat_id": "oc_group",
                "chat_type": "group",
                "message_type": "text",
                "content": json.dumps({"text": "@_user_1 帮助"}),
                "mentions": mentions or [],
            },
        },
    }


async def _run_group_case(monkeypatch, envelope) -> list[str]:
    replies: list[str] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    async def fake_bot_open_id() -> str:
        return "ou_bot"

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    await shusuo_router._handle_envelope(envelope)
    return replies


@dataclass
class GroupCaseResult:
    replies: list[str]
    executed: list[commands.Command]
    bot_open_id_calls: int


async def _run_message_case(
    monkeypatch,
    envelope: dict[str, object],
    *,
    bot_open_id: str = "ou_bot",
    bot_open_id_error: Exception | None = None,
) -> GroupCaseResult:
    replies: list[str] = []
    executed: list[commands.Command] = []
    calls = 0

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    async def fake_bot_open_id() -> str:
        nonlocal calls
        calls += 1
        if bot_open_id_error is not None:
            raise bot_open_id_error
        return bot_open_id

    async def fake_execute(
        command: commands.Command,
        *,
        chat_id: str = "",
        open_id: str = "",
        message_id: str = "",
    ) -> commands.Reply:
        executed.append(command)
        return commands.Reply(text="ok")

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.setattr(shusuo_router.commands, "execute", fake_execute)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    await shusuo_router._handle_envelope(envelope)
    return GroupCaseResult(replies, executed, calls)


async def test_group_message_without_mention_is_ignored(monkeypatch) -> None:
    replies = await _run_group_case(monkeypatch, _group_envelope())
    assert replies == []


async def test_group_message_with_mention_is_answered(monkeypatch) -> None:
    envelope = _group_envelope(mentions=[{"id": {"open_id": "ou_bot"}, "name": "数说"}])
    replies = await _run_group_case(monkeypatch, envelope)
    assert replies and "数说" in replies[0]


async def test_p2p_message_is_answered_without_mention(monkeypatch) -> None:
    replies: list[str] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    envelope = {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-p2p"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_p2p",
                "chat_id": "oc_p2p",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "帮助"}),
            },
        },
    }
    await shusuo_router._handle_envelope(envelope)
    assert replies and "数说" in replies[0]


async def test_group_without_mention_does_not_execute(monkeypatch) -> None:
    result = await _run_message_case(monkeypatch, _group_envelope())
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 1


async def test_group_mentioning_other_user_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[{"id": {"open_id": "ou_other"}, "name": "其他人"}]
    )
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []


async def test_group_with_multiple_mentions_including_bot_is_answered(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[
            {"id": {"open_id": "ou_other"}},
            {"id": {"open_id": "ou_bot"}},
        ]
    )
    result = await _run_message_case(monkeypatch, envelope)
    assert len(result.executed) == 1
    assert result.replies == ["ok"]


async def test_missing_chat_type_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope()
    message = envelope["event"]["message"]
    message.pop("chat_type")
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0


async def test_unknown_chat_type_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope()
    envelope["event"]["message"]["chat_type"] = "topic"
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0


async def test_unknown_chat_type_log_caps_external_fields_and_preserves_dedupe(
    monkeypatch,
) -> None:
    event_id = "event-prefix-" + "e" * 300
    chat_type = "unknown-prefix-" + "c" * 100
    envelope = _group_envelope()
    envelope["header"]["event_id"] = event_id
    envelope["event"]["message"]["chat_type"] = chat_type

    with capture_logs() as logs:
        result = await _run_message_case(monkeypatch, envelope)

    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0
    event_entry = next(
        entry for entry in logs if entry.get("event") == "shusuo_event_received"
    )
    ignored_entry = next(
        entry for entry in logs if entry.get("event") == "shusuo_message_ignored"
    )
    assert event_entry["event_id"] == event_id[:128]
    assert ignored_entry["chat_type"] == chat_type[:32]
    assert event_id not in str(logs)
    assert chat_type not in str(logs)
    assert shusuo_router._is_duplicate(event_id) is False
    assert shusuo_router._is_duplicate(event_id) is True
    assert event_id in shusuo_router._seen_events
    assert event_id[:128] not in shusuo_router._seen_events


def test_webhook_dedupes_full_long_event_id(monkeypatch) -> None:
    monkeypatch.delenv("LARK_SHUSUO_ENCRYPT_KEY", raising=False)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)
    event_id = "event-prefix-" + "e" * 300
    body = json.dumps(
        _encrypted_group_payload(
            event_id=event_id,
            chat_type="p2p",
            text="帮助",
        )
    )

    client = TestClient(app)
    for _ in range(2):
        response = client.post(
            WEBHOOK_PATH,
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json() == {"code": 0}

    assert len(executed) == 1
    assert len(replies) == 1
    assert event_id in shusuo_router._seen_events
    assert event_id[:128] not in shusuo_router._seen_events


async def test_p2p_does_not_query_bot_identity(monkeypatch) -> None:
    envelope = _p2p_envelope("帮助")
    result = await _run_message_case(monkeypatch, envelope)
    assert len(result.executed) == 1
    assert result.bot_open_id_calls == 0


async def test_bot_message_does_not_query_bot_identity(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[{"id": {"open_id": "ou_bot"}}]
    )
    envelope["event"]["sender"]["sender_type"] = "app"
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []
    assert result.bot_open_id_calls == 0


async def test_group_bot_identity_failure_is_silent(monkeypatch) -> None:
    envelope = _group_envelope(
        mentions=[{"id": {"open_id": "ou_bot"}}]
    )
    result = await _run_message_case(
        monkeypatch,
        envelope,
        bot_open_id_error=RuntimeError("bot info unavailable"),
    )
    assert result.replies == []
    assert result.executed == []


async def test_group_empty_bot_identity_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope(mentions=[{"id": {"open_id": "ou_bot"}}])
    result = await _run_message_case(monkeypatch, envelope, bot_open_id="")
    assert result.replies == []
    assert result.executed == []


async def test_group_malformed_mention_open_id_is_ignored(monkeypatch) -> None:
    envelope = _group_envelope(mentions=[{"id": {"open_id": 12345}}])
    result = await _run_message_case(monkeypatch, envelope)
    assert result.replies == []
    assert result.executed == []


async def test_command_handled_log_omits_message_text(monkeypatch) -> None:
    """命令参数就是用户输入，shusuo_command_handled 不得携带它。"""
    sentinel = "SECRET-SENTINEL-TEXT"

    async def fake_reply(message_id: str, text: str) -> str:
        return "om_reply"

    async def fake_bot_open_id() -> str:
        return "ou_bot"

    async def fake_execute(
        command: commands.Command,
        *,
        chat_id: str = "",
        open_id: str = "",
        message_id: str = "",
    ) -> commands.Reply:
        return commands.Reply(text="ok")

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.setattr(shusuo_router.commands, "execute", fake_execute)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()

    with capture_logs() as logs:
        await shusuo_router._handle_envelope(_p2p_envelope(f"采集 {sentinel}"))

    entries = [entry for entry in logs if entry.get("event") == "shusuo_command_handled"]
    assert entries, "缺少 shusuo_command_handled 日志"
    assert entries[-1]["command"] == "collect"
    assert "argument" not in entries[-1]
    for entry in logs:
        assert sentinel not in str(entry)
        assert "exc_info" not in entry


async def test_event_failed_log_omits_exception_text(monkeypatch) -> None:
    """shusuo_event_failed 只带 error_type，不携带异常文本或回溯。"""
    sentinel = "SECRET-SENTINEL-EXC"

    async def fake_reply(message_id: str, text: str) -> str:
        return "om_reply"

    async def fake_bot_open_id() -> str:
        return "ou_bot"

    async def fake_execute(
        command: commands.Command,
        *,
        chat_id: str = "",
        open_id: str = "",
        message_id: str = "",
    ) -> commands.Reply:
        raise RuntimeError(f"token={sentinel}")

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.setattr(shusuo_router.commands, "execute", fake_execute)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()

    with capture_logs() as logs:
        await shusuo_router._handle_envelope(_p2p_envelope("帮助"))

    entries = [entry for entry in logs if entry.get("event") == "shusuo_event_failed"]
    assert entries, "缺少 shusuo_event_failed 日志"
    assert entries[-1]["log_level"] == "error"
    assert entries[-1]["error_type"] == "RuntimeError"
    for entry in logs:
        assert sentinel not in str(entry)
        assert "exc_info" not in entry


def _post_encrypted_event(
    client: TestClient,
    envelope: dict[str, object],
    encrypt_key: str,
) -> Response:
    encrypted = _encrypt(envelope, encrypt_key)
    body = json.dumps({"encrypt": encrypted})
    timestamp, nonce = "1700000001", "nonce-group"
    return client.post(
        WEBHOOK_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": _sign(timestamp, nonce, encrypt_key, body),
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
        },
    )


def _encrypted_group_payload(
    *,
    event_id: str,
    chat_type: str = "group",
    mentions: list[dict[str, object]] | None = None,
    text: str = "@_user_1 帮助",
) -> dict[str, object]:
    message: dict[str, object] = {
        "message_id": "om_encrypted_group",
        "chat_id": "oc_encrypted",
        "message_type": "text",
        "content": json.dumps({"text": text}),
        "chat_type": chat_type,
        "mentions": mentions,
    }
    return {
        "header": {
            "event_type": "im.message.receive_v1",
            "event_id": event_id,
            "token": "t",
        },
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_user"}},
            "message": message,
        },
    }


def _install_webhook_stubs(monkeypatch) -> tuple[list[str], list[commands.Command]]:
    replies: list[str] = []
    executed: list[commands.Command] = []

    async def fake_reply(message_id: str, text: str) -> str:
        replies.append(text)
        return "om_reply"

    async def fake_bot_open_id() -> str:
        return "ou_bot"

    async def fake_execute(
        command: commands.Command,
        *,
        chat_id: str = "",
        open_id: str = "",
        message_id: str = "",
    ) -> commands.Reply:
        executed.append(command)
        return commands.Reply(text="ok")

    monkeypatch.setattr(shusuo_router.lark_client, "reply_text", fake_reply)
    monkeypatch.setattr(shusuo_router.lark_client, "get_bot_open_id", fake_bot_open_id)
    monkeypatch.setattr(shusuo_router.commands, "execute", fake_execute)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    return replies, executed


def test_encrypted_group_mention_executes_and_replies(monkeypatch) -> None:
    encrypt_key = "test-encrypt-key"
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)

    client = TestClient(app)
    response = _post_encrypted_event(
        client,
        _encrypted_group_payload(
            event_id="evt-enc-mention",
            mentions=[{"id": {"open_id": "ou_bot"}}],
        ),
        encrypt_key,
    )
    assert response.status_code == 200
    assert response.json() == {"code": 0}
    assert len(executed) == 1
    assert executed[0].name == "help"
    assert replies == ["ok"]


def test_encrypted_group_without_mention_is_silent(monkeypatch) -> None:
    encrypt_key = "test-encrypt-key"
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)

    client = TestClient(app)
    response = _post_encrypted_event(
        client,
        _encrypted_group_payload(event_id="evt-enc-no-mention", mentions=[]),
        encrypt_key,
    )
    assert response.status_code == 200
    assert response.json() == {"code": 0}
    assert executed == []
    assert replies == []


def test_encrypted_group_unknown_chat_type_is_silent(monkeypatch) -> None:
    encrypt_key = "test-encrypt-key"
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)

    client = TestClient(app)
    response = _post_encrypted_event(
        client,
        _encrypted_group_payload(
            event_id="evt-enc-unknown-chat",
            chat_type="topic",
            mentions=[{"id": {"open_id": "ou_bot"}}],
        ),
        encrypt_key,
    )
    assert response.status_code == 200
    assert response.json() == {"code": 0}
    assert executed == []
    assert replies == []


def test_encrypted_event_bad_signature_still_rejected(monkeypatch) -> None:
    encrypt_key = "test-encrypt-key"
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)

    encrypted = _encrypt(
        _encrypted_group_payload(
            event_id="evt-enc-bad-signature",
            mentions=[{"id": {"open_id": "ou_bot"}}],
        ),
        encrypt_key,
    )
    body = json.dumps({"encrypt": encrypted})
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": "bad",
            "X-Lark-Request-Timestamp": "1",
            "X-Lark-Request-Nonce": "n",
        },
    )
    assert response.status_code == 403
    assert executed == []
    assert replies == []


def test_duplicate_event_id_executes_once(monkeypatch) -> None:
    monkeypatch.delenv("LARK_SHUSUO_ENCRYPT_KEY", raising=False)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)

    client = TestClient(app)
    body = json.dumps(
        _encrypted_group_payload(
            event_id="evt-dup",
            chat_type="p2p",
            text="帮助",
        )
    )
    for _ in range(2):
        response = client.post(
            WEBHOOK_PATH,
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json() == {"code": 0}

    assert len(executed) == 1
    assert len(replies) == 1


def test_empty_event_id_is_processed_twice(monkeypatch) -> None:
    monkeypatch.delenv("LARK_SHUSUO_ENCRYPT_KEY", raising=False)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    replies, executed = _install_webhook_stubs(monkeypatch)

    client = TestClient(app)
    body = json.dumps(
        _encrypted_group_payload(event_id="", chat_type="p2p", text="帮助")
    )
    for _ in range(2):
        response = client.post(
            WEBHOOK_PATH,
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json() == {"code": 0}

    assert len(executed) == 2
    assert len(replies) == 2


# ---------- 卡片回调 /card-action ----------


def _signed_card_action(payload: dict[str, Any], encrypt_key: str) -> tuple[str, dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    timestamp = "1700000000"
    nonce = "nonce"
    signature = hashlib.sha256(
        f"{timestamp}{nonce}{encrypt_key}{body}".encode()
    ).hexdigest()
    return body, {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
        "Content-Type": "application/json",
    }


def _card_action_payload(
    *,
    action: str = "confirm",
    token: str = "TOKEN1234",
    operator: str = "ou-1",
    chat_id: str = "chat-1",
    message_id: str = "om-card-1",
    app_id: str | None = "app-x",
    token_value: str | None = "vt-card",
    nested: bool = True,
) -> dict[str, Any]:
    """真实飞书 schema 2.0 HTTP 回调形态：header/event 双层嵌套。

    header.token / header.app_id 是推送层凭证；event.operator / event.action /
    event.context 是业务载荷。encrypted 回调解密后同样是这个结构。
    nested=False 生成旧扁平形态，仅用于向后兼容回退分支的测试。
    """
    event: dict[str, Any] = {
        "operator": {"open_id": operator},
        "action": {"value": {"action": action, "token": token}},
        "context": {"open_message_id": message_id, "open_chat_id": chat_id},
    }
    header: dict[str, Any] = {}
    if app_id is not None:
        header["app_id"] = app_id
    if token_value is not None:
        header["token"] = token_value
    if nested:
        payload: dict[str, Any] = {
            "schema": "2.0",
            "header": header,
            "event": event,
        }
        return payload
    payload = dict(event)
    payload.update(header)
    payload["type"] = "card.action.trigger"
    return payload


def _card_action_config(
    monkeypatch,
    *,
    encrypt_key: str = "card-key",
    verification_token: str = "vt-card",
    app_id: str = "app-x",
    allowed: str = "ou-1",
) -> str:
    monkeypatch.setenv("LARK_SHUSUO_ENCRYPT_KEY", encrypt_key)
    monkeypatch.setenv("LARK_SHUSUO_VERIFICATION_TOKEN", verification_token)
    monkeypatch.setenv("LARK_SHUSUO_APP_ID", app_id)
    monkeypatch.setenv("SHUSUO_ALLOWED_OPEN_IDS", allowed)
    get_shushuo_config.cache_clear()
    return encrypt_key


async def _seed_pending_card(
    monkeypatch,
    *,
    chat_id: str = "chat-1",
    open_id: str = "ou-1",
    text: str = "搜 reddit AI",
) -> str:
    """预置一个活跃提案并绑定卡片消息 ID；返回 token。"""
    shusuo_proposal_store.clear_all()
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    reply = await commands.execute(
        commands.parse_command(text),
        chat_id=chat_id,
        open_id=open_id,
        message_id="om-source",
    )
    assert reply.pending_token
    shusuo_proposal_store.attach_message_ids(
        reply.pending_token, card_message_id="om-card-1"
    )
    return reply.pending_token


def test_card_action_rejects_bad_signature(monkeypatch) -> None:
    _card_action_config(monkeypatch)
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    client = TestClient(app)
    response = client.post(
        CARD_ACTION_PATH,
        json={"action": {"value": {"action": "confirm"}}},
    )
    assert response.status_code == 403


def test_card_action_rejects_valid_signature_but_bad_token(monkeypatch) -> None:
    """签名通过但 Verification Token 不匹配：403。"""
    encrypt_key = _card_action_config(monkeypatch, verification_token="right")
    client = TestClient(app)
    payload = _card_action_payload(token_value="wrong-token")
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


def test_card_action_rejects_wrong_app_id(monkeypatch) -> None:
    encrypt_key = _card_action_config(monkeypatch)
    client = TestClient(app)
    payload = _card_action_payload(app_id="app-other")
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


def test_card_action_rejects_missing_verification_token_config(monkeypatch) -> None:
    """Verification Token 未配置时 fail-closed：拒绝回调而不是放行。"""
    encrypt_key = _card_action_config(monkeypatch)
    monkeypatch.delenv("LARK_SHUSUO_VERIFICATION_TOKEN", raising=False)
    get_shushuo_config.cache_clear()
    client = TestClient(app)
    payload = _card_action_payload()
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


def test_card_action_rejects_unknown_action(monkeypatch) -> None:
    encrypt_key = _card_action_config(monkeypatch)
    client = TestClient(app)
    payload = _card_action_payload(action="delete_all")
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 400


async def test_card_action_rejects_non_owner(monkeypatch) -> None:
    """pending owner ou-1，操作人 ou-2（也在白名单）：403，且 token 不被消费。

    两人都在白名单时，归属校验（FORBIDDEN）才是唯一防线——
    这条测试锁定 H1：归属违规必须 403，不是 200 状态 toast。
    """
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-2")
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-2", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403
    collect.assert_not_awaited()
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE
    assert pending is not None


async def test_card_action_non_owner_cancel_also_forbidden(monkeypatch) -> None:
    """归属违规对 cancel 同样 403：不能替别人取消提案。"""
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-2")
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="cancel", token=token, operator="ou-2", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403
    collect.assert_not_awaited()
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE


async def test_card_action_rejects_empty_allowlist(monkeypatch) -> None:
    """allowed_open_ids 为空时拒绝：回调必须显式配置白名单。"""
    encrypt_key = _card_action_config(monkeypatch, allowed="")
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403
    collect.assert_not_awaited()


async def test_card_action_rejects_operator_not_in_allowlist(monkeypatch) -> None:
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-9")
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-outsider", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403
    collect.assert_not_awaited()


async def test_card_confirm_executes_once(monkeypatch) -> None:
    """确认回调：200 toast，后台执行恰好一次采集；重复点击不重复采集。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(
            True, "采集完成", endpoint_type="e"
        )
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    preflight_calls: list[bool] = []

    async def fake_preflight(proposal, *, force_status: bool = False):
        preflight_calls.append(force_status)
        return shusuo_capabilities.PreflightResult(
            allowed=True,
            availability="verified",
            normalized_params=dict(proposal.params),
        )

    # 在 seed 之后安装：意图预检走 seed 的 AsyncMock，后台确认走本 fake
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    first = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    second = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    toast = first.json().get("toast") or {}
    assert toast
    assert collect.await_count == 1
    # 确认回调的强制预检在后台执行，force_status=True
    assert preflight_calls == [True]


async def test_card_cancel_does_not_collect(monkeypatch) -> None:
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="cancel", token=token, operator="ou-1", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    assert response.json().get("toast")
    collect.assert_not_awaited()
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING


async def test_card_confirm_preflight_failure_does_not_consume(monkeypatch) -> None:
    """回调确认的强制预检失败：不消费 token、不采集。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    token = await _seed_pending_card(monkeypatch, open_id="ou-1")

    async def fake_preflight(proposal, *, force_status: bool = False):
        assert force_status is True
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="config-gated",
            normalized_params=dict(proposal.params),
            errors=("当前受安全策略限制，无法执行该端点。",),
        )

    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    collect.assert_not_awaited()
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE
    assert pending is not None


def test_card_unknown_token_returns_status_toast(monkeypatch) -> None:
    """token 已消费/过期/替换：200 toast 提示，不采集。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token="GHOST0000", operator="ou-1", chat_id="chat-1"
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    assert response.json().get("toast")
    collect.assert_not_awaited()


def test_card_action_challenge_echo_only(monkeypatch) -> None:
    """URL 校验只回显 challenge，不做 token 比对，也没有副作用。"""
    encrypt_key = _card_action_config(monkeypatch)
    client = TestClient(app)
    payload = {"type": "url_verification", "challenge": "card-challenge", "token": "old"}
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"challenge": "card-challenge"}


async def test_card_action_nested_shape_extracts_fields(monkeypatch) -> None:
    """真实推送形态（header/event 嵌套）：字段从 event 里取，路径全链路可通。"""
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-2")
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 5},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1", nested=True
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    assert response.json().get("toast")
    assert collect.await_count == 1


def test_card_action_nested_header_token_mismatch_rejected(monkeypatch) -> None:
    """嵌套 header.token 错误：403（不是从顶层读凭证的旧路径）。"""
    encrypt_key = _card_action_config(monkeypatch, verification_token="right")
    client = TestClient(app)
    payload = _card_action_payload(token_value="wrong", nested=True)
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


def test_card_action_nested_header_app_id_mismatch_rejected(monkeypatch) -> None:
    """嵌套 header.app_id 错误：403。"""
    encrypt_key = _card_action_config(monkeypatch)
    client = TestClient(app)
    payload = _card_action_payload(app_id="app-other", nested=True)
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 403


async def test_card_action_flat_shape_still_accepted(monkeypatch) -> None:
    """旧扁平形态向后兼容回退：顶层凭证/载荷可解析（不作为主要契约）。"""
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-2")
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 5},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1", nested=False
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    response = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert response.status_code == 200
    assert collect.await_count == 1


async def test_card_action_encrypted_nested_payload_executes(monkeypatch) -> None:
    """加密回调解密后也是 header/event 嵌套：凭证在 header，载荷在 event。"""
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-2")
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 5},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    inner = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1", nested=True
    )
    encrypted = _encrypt(inner, encrypt_key)
    body = json.dumps({"encrypt": encrypted})
    timestamp, nonce = "1700000001", "nonce-enc"
    response = client.post(
        CARD_ACTION_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": _sign(timestamp, nonce, encrypt_key, body),
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
        },
    )
    assert response.status_code == 200
    assert response.json().get("toast")
    assert collect.await_count == 1


async def test_card_action_encrypted_nested_header_token_mismatch(monkeypatch) -> None:
    encrypt_key = _card_action_config(monkeypatch, verification_token="right")
    client = TestClient(app)
    inner = _card_action_payload(token_value="wrong", nested=True)
    encrypted = _encrypt(inner, encrypt_key)
    body = json.dumps({"encrypt": encrypted})
    timestamp, nonce = "1700000002", "nonce-enc2"
    response = client.post(
        CARD_ACTION_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": _sign(timestamp, nonce, encrypt_key, body),
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
        },
    )
    assert response.status_code == 403


async def test_card_action_encrypted_payload_is_verified_and_decrypted(monkeypatch) -> None:
    """加密回调：验签（encrypt-key 公式）→ 解密 → 后台执行一次。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 5},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    client = TestClient(app)
    inner = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1"
    )
    encrypted = _encrypt(inner, encrypt_key)
    body = json.dumps({"encrypt": encrypted})
    timestamp, nonce = "1700000001", "nonce-enc"
    response = client.post(
        CARD_ACTION_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": _sign(timestamp, nonce, encrypt_key, body),
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
        },
    )
    assert response.status_code == 200
    assert response.json().get("toast")
    assert collect.await_count == 1


def test_card_action_encrypted_rejects_bad_signature(monkeypatch) -> None:
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    client = TestClient(app)
    inner = _card_action_payload()
    encrypted = _encrypt(inner, encrypt_key)
    body = json.dumps({"encrypt": encrypted})
    response = client.post(
        CARD_ACTION_PATH,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Signature": "bad",
            "X-Lark-Request-Timestamp": "1",
            "X-Lark-Request-Nonce": "n",
        },
    )
    assert response.status_code == 403
    collect.assert_not_awaited()


async def _run_card_confirm_background(
    monkeypatch,
    token: str,
) -> tuple[AsyncMock, list[tuple[str, dict[str, Any]]]]:
    """直接驱动后台确认协程；返回 (collect, update_card 调用参数)。"""
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(
            True,
            "采集完成",
            endpoint_type="e",
            task_run_id="run-1",
            records_count=3,
        )
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    updates: list[tuple[str, dict[str, Any]]] = []

    async def fake_update_card(message_id: str, card: dict[str, Any]) -> bool:
        updates.append((message_id, card))
        return True

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", fake_update_card)
    await shusuo_router._execute_card_confirm(
        token=token,
        chat_id="chat-1",
        open_id="ou-1",
        card_message_id="om-card-1",
    )
    return collect, updates


async def test_card_confirm_background_updates_cards_in_order(monkeypatch) -> None:
    """后台确认：处理中卡 → 成功卡；token 先消费；只采集一次。"""
    encrypt_key = _card_action_config(monkeypatch)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI", "max_items": 5},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    collect, updates = await _run_card_confirm_background(monkeypatch, token)
    assert collect.await_count == 1
    assert len(updates) == 2
    assert updates[0][0] == "om-card-1"
    assert "正在采集" in json.dumps(updates[0][1], ensure_ascii=False)
    assert "采集完成" in json.dumps(updates[1][1], ensure_ascii=False)
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    assert encrypt_key  # 配置 fixture 已生效


async def test_card_confirm_background_preflight_failure_updates_failure_card(
    monkeypatch,
) -> None:
    """后台确认预检失败：更新失败卡，token 保留，不采集。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)

    token = await _seed_pending_card(monkeypatch, open_id="ou-1")

    async def fake_preflight(proposal, *, force_status: bool = False):
        assert force_status is True
        return shusuo_capabilities.PreflightResult(
            allowed=False,
            availability="config-gated",
            normalized_params=dict(proposal.params),
            errors=("当前受安全策略限制，无法执行该端点。",),
        )

    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    updates: list[tuple[str, dict[str, Any]]] = []

    async def fake_update_card(message_id: str, card: dict[str, Any]) -> bool:
        updates.append((message_id, card))
        return True

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", fake_update_card)
    await shusuo_router._execute_card_confirm(
        token=token, chat_id="chat-1", open_id="ou-1", card_message_id="om-card-1"
    )
    collect.assert_not_awaited()
    # brief 顺序：先处理中卡，再失败卡（预检失败）
    assert len(updates) == 2
    assert "正在采集" in json.dumps(updates[0][1], ensure_ascii=False)
    assert "无法执行采集" in json.dumps(updates[1][1], ensure_ascii=False)
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE
    assert pending is not None
    assert encrypt_key


async def test_card_confirm_background_collect_failure_updates_failure_card(
    monkeypatch,
) -> None:
    """采集失败：失败卡更新；token 已消费，不会恢复。"""
    encrypt_key = _card_action_config(monkeypatch)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI"},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(
            False, "采集未返回数据", endpoint_type="e", error_message="上游没有返回记录"
        )
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    updates: list[tuple[str, dict[str, Any]]] = []

    async def fake_update_card(message_id: str, card: dict[str, Any]) -> bool:
        updates.append((message_id, card))
        return True

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", fake_update_card)
    await shusuo_router._execute_card_confirm(
        token=token, chat_id="chat-1", open_id="ou-1", card_message_id="om-card-1"
    )
    assert collect.await_count == 1
    assert len(updates) == 2
    assert "采集未返回数据" in json.dumps(updates[1][1], ensure_ascii=False)
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    assert encrypt_key


async def test_card_update_failure_only_logs(monkeypatch, caplog) -> None:
    """update_card 抛错：只记日志；不恢复 token、不重复采集、不重试。"""
    encrypt_key = _card_action_config(monkeypatch)
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(
            return_value=shusuo_capabilities.PreflightResult(
                allowed=True,
                availability="verified",
                normalized_params={"keyword": "AI"},
            )
        ),
    )
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(
            True, "采集完成", endpoint_type="e", task_run_id="run-2", records_count=1
        )
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    update_calls: list[int] = []

    async def failing_update_card(message_id: str, card: dict[str, Any]) -> bool:
        update_calls.append(1)
        raise RuntimeError("feishu update failed")

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", failing_update_card)
    await shusuo_router._execute_card_confirm(
        token=token, chat_id="chat-1", open_id="ou-1", card_message_id="om-card-1"
    )
    assert collect.await_count == 1
    assert len(update_calls) == 2  # 处理中卡 + 成功卡各试一次，失败只吞掉
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    assert encrypt_key


async def test_card_confirm_background_replaced_updates_replaced_card(
    monkeypatch,
) -> None:
    """后台确认遇到 REPLACED token：替换文案卡，绝不采集。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    # 新提案替换旧提案 → 旧 token 进 REPLACED 窗口
    monkeypatch.setattr(
        shusuo_capabilities,
        "preflight_proposal",
        AsyncMock(return_value=_preflight(allowed=True)),
    )
    await commands.execute(
        commands.parse_command("搜 reddit ML"),
        chat_id="chat-1",
        open_id="ou-1",
    )
    updates: list[tuple[str, dict[str, Any]]] = []

    async def fake_update_card(message_id: str, card: dict[str, Any]) -> bool:
        updates.append((message_id, card))
        return True

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", fake_update_card)
    await shusuo_router._execute_card_confirm(
        token=token, chat_id="chat-1", open_id="ou-1", card_message_id="om-card-1"
    )
    collect.assert_not_awaited()
    assert len(updates) == 1
    body = json.dumps(updates[0][1], ensure_ascii=False)
    assert "已被新提案替换" in body
    assert "正在采集" not in body
    assert encrypt_key


async def test_card_confirm_reserve_restored_on_preflight_failure(monkeypatch) -> None:
    """M1 原子预留回滚：路由层预留 → 后台预检失败 → token 放回可重试。

    全链路：HTTP 回调 → 原子 consume → 后台 force preflight 失败 →
    restore → 再来一次回调仍能走到采集（token 恢复）。
    """
    encrypt_key = _card_action_config(monkeypatch, allowed="ou-1,ou-2")
    collect = AsyncMock(
        return_value=shusuo_capabilities.CollectOutcome(True, "采集完成", endpoint_type="e")
    )
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    preflight_calls: list[bool] = []

    async def fake_preflight(proposal, *, force_status: bool = False):
        preflight_calls.append(force_status)
        if len(preflight_calls) == 1:
            # 第一次后台确认：seed 的意图预检走另一个 mock，不进本列表；
            # 强制刷新后策略拒绝 → 触发原子预留回滚
            assert force_status is True
            return shusuo_capabilities.PreflightResult(
                allowed=False,
                availability="config-gated",
                normalized_params=dict(proposal.params),
                errors=("当前受安全策略限制，无法执行该端点。",),
            )
        return shusuo_capabilities.PreflightResult(
            allowed=True,
            availability="verified",
            normalized_params=dict(proposal.params),
        )

    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    monkeypatch.setattr(shusuo_capabilities, "preflight_proposal", fake_preflight)
    client = TestClient(app)
    payload = _card_action_payload(
        action="confirm", token=token, operator="ou-1", chat_id="chat-1", nested=True
    )
    body, headers = _signed_card_action(payload, encrypt_key)
    first = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert first.status_code == 200
    collect.assert_not_awaited()
    # 预检失败回滚：token 回到 ACTIVE（原子预留被恢复）
    status, pending = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.ACTIVE
    assert pending is not None
    # 第二次点击：预检放行，采集恰好一次
    second = client.post(CARD_ACTION_PATH, content=body, headers=headers)
    assert second.status_code == 200
    assert collect.await_count == 1
    assert encrypt_key


async def test_card_cancel_background_updates_cancelled_card(monkeypatch) -> None:
    """后台取消：token 被取消，卡片更新为取消卡；不采集。"""
    encrypt_key = _card_action_config(monkeypatch)
    collect = AsyncMock()
    monkeypatch.setattr(shusuo_capabilities, "collect", collect)
    token = await _seed_pending_card(monkeypatch, open_id="ou-1")
    updates: list[tuple[str, dict[str, Any]]] = []

    async def fake_update_card(message_id: str, card: dict[str, Any]) -> bool:
        updates.append((message_id, card))
        return True

    monkeypatch.setattr(shusuo_router.lark_client, "update_card", fake_update_card)
    await shusuo_router._execute_card_cancel(
        token=token, chat_id="chat-1", open_id="ou-1", card_message_id="om-card-1"
    )
    collect.assert_not_awaited()
    assert len(updates) == 1
    assert "已取消" in json.dumps(updates[0][1], ensure_ascii=False)
    status, _ = shusuo_proposal_store.peek_pending(token, "chat-1", "ou-1")
    assert status is shusuo_proposal_store.ProposalLookup.MISSING
    assert encrypt_key

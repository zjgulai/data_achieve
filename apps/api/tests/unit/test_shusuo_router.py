"""数说飞书机器人的契约测试。"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
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
from data_intelligence_hub.agents.shusuo import router as shusuo_router
from data_intelligence_hub.agents.shusuo.config import get_shushuo_config
from data_intelligence_hub.main import app
from data_intelligence_hub.platform_packages.models import PackageEndpoint
from data_intelligence_hub.platform_packages.service import CapabilityNotFoundError

WEBHOOK_PATH = "/api/agents/shusuo/webhook"
HEALTH_PATH = "/api/agents/shusuo/health"


@pytest.fixture(autouse=True)
def _clear_state():
    get_shushuo_config.cache_clear()
    shusuo_router._seen_events.clear()
    yield
    shusuo_router._seen_events.clear()
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


async def test_explicit_collect_blocked_by_preflight(monkeypatch) -> None:
    """显式采集预检失败时返回统一错误文本，不进入 capabilities.collect。"""
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(True, "采集完成")

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
    assert reply.text == "端点当前不可用，已取消采集。"
    assert reply.ack is None


async def test_explicit_collect_runs_preflight_with_force_status(monkeypatch) -> None:
    """显式采集必须以 force_status=True 预检，通过后才执行采集。"""
    calls: list[tuple[str, dict[str, object]]] = []
    preflight_calls: list[tuple[str, bool]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(True, "采集完成")

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
    assert reply.text == "采集完成"


async def test_explicit_collect_preflight_unknown_endpoint(monkeypatch) -> None:
    """显式采集未知端点：预检拒绝，统一文案，不暴露内部异常。"""
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(True, "采集完成")

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
    assert reply.text == "没有找到端点：no_such_endpoint"


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


async def test_confirm_executes_pending_proposal(monkeypatch) -> None:
    shusuo_proposal_store.clear_all()
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"keyword": "AI", "max_items": 3},
        title="Reddit 搜索",
    )
    shusuo_proposal_store.replace_pending("chat-1", "", proposal)

    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(True, "采集完成")

    monkeypatch.setattr(shusuo_capabilities, "collect", fake_collect)
    reply = await commands.execute(commands.Command("confirm"), context_key="chat-1")
    assert calls == [("tikhub_reddit_search", {"keyword": "AI", "max_items": 3})]
    assert reply.text == "采集完成"


async def test_confirm_without_pending_returns_hint() -> None:
    shusuo_proposal_store.clear_all()
    reply = await commands.execute(commands.Command("confirm"), context_key="chat-empty")
    assert "没有待确认" in reply.text


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
        context_key: str = "",
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
        context_key: str = "",
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
        context_key: str = "",
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
        context_key: str = "",
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

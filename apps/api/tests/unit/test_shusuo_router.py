"""数说飞书机器人的契约测试。"""

from __future__ import annotations

import base64
import hashlib
import json
import os

import pytest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi.testclient import TestClient

from data_intelligence_hub.agents.shusuo import capabilities as shusuo_capabilities
from data_intelligence_hub.agents.shusuo import commands
from data_intelligence_hub.agents.shusuo import intents as shusuo_intents
from data_intelligence_hub.agents.shusuo import router as shusuo_router
from data_intelligence_hub.agents.shusuo.config import get_shushuo_config
from data_intelligence_hub.main import app

WEBHOOK_PATH = "/api/agents/shusuo/webhook"
HEALTH_PATH = "/api/agents/shusuo/health"


@pytest.fixture(autouse=True)
def _clear_config_cache():
    get_shushuo_config.cache_clear()
    yield
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


def test_clean_text_removes_mentions() -> None:
    assert commands.clean_text("@_user_1 帮助") == "帮助"


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
    assert proposal.params["products"] == ["https://www.amazon.com/dp/B000000001"]


def test_intent_unknown_platform_returns_hint() -> None:
    result = shusuo_intents.build_proposal("账号 facebook nike")
    assert isinstance(result, str)
    assert "tiktok" in result


async def test_confirm_executes_pending_proposal(monkeypatch) -> None:
    monkeypatch.setattr(shusuo_intents, "_PENDING", {})
    proposal = shusuo_intents.Proposal(
        endpoint_type="tikhub_reddit_search",
        params={"keyword": "AI", "max_items": 3},
        title="Reddit 搜索",
    )
    shusuo_intents.set_pending("chat-1", proposal)

    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_collect(endpoint_type, params):
        calls.append((endpoint_type, params))
        return shusuo_capabilities.CollectOutcome(True, "采集完成")

    monkeypatch.setattr(shusuo_capabilities, "collect", fake_collect)
    reply = await commands.execute(commands.Command("confirm"), context_key="chat-1")
    assert calls == [("tikhub_reddit_search", {"keyword": "AI", "max_items": 3})]
    assert reply.text == "采集完成"


async def test_confirm_without_pending_returns_hint() -> None:
    shusuo_intents.clear_pending("chat-empty")
    reply = await commands.execute(commands.Command("confirm"), context_key="chat-empty")
    assert "没有待确认" in reply.text


def test_intent_proposal_reply_requires_confirmation() -> None:
    proposal = shusuo_intents.build_proposal("热点 x")
    assert not isinstance(proposal, str)
    text = shusuo_intents.proposal_reply(proposal)
    assert "确认" in text
    assert "tikhub_x_trending" in text


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

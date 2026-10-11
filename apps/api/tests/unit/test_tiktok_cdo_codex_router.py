"""codex 版 TikTok CDO Agent 的契约测试。

该 agent 只在生产 B 运行，见 docs/【运维手册】生产环境基线.md。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from data_intelligence_hub.agents.tiktok_cdo.config import get_cdo_config
from data_intelligence_hub.main import app

WEBHOOK_PATH = "/api/agents/tiktok-cdo/webhook"
CALLBACK_PATH = "/api/agents/tiktok-cdo/webhook/callback"


def test_router_is_mounted_at_expected_prefix() -> None:
    paths = {route.path for route in app.routes}
    assert WEBHOOK_PATH in paths
    assert CALLBACK_PATH in paths


def test_webhook_challenge_is_publicly_mounted() -> None:
    client = TestClient(app)
    response = client.post(
        WEBHOOK_PATH,
        content=json.dumps({"type": "url_verification", "challenge": "challenge-token"}),
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-token"}


def test_webhook_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CDO_VERIFICATION_TOKEN", "token")
    get_cdo_config.cache_clear()
    try:
        client = TestClient(app)
        response = client.post(
            WEBHOOK_PATH,
            content=json.dumps({"event": {"message": {"content": "{}"}}}),
            headers={
                "x-lark-signature": "invalid",
                "x-lark-request-timestamp": "123",
                "x-lark-request-nonce": "nonce",
            },
        )
    finally:
        get_cdo_config.cache_clear()
    assert response.status_code == 403


def test_card_callback_handles_export_action() -> None:
    client = TestClient(app)
    response = client.post(
        CALLBACK_PATH,
        content=json.dumps({"action": {"value": {"action": "export_bitable"}}}),
    )
    assert response.status_code == 200
    assert response.json()["toast"]["type"] == "info"

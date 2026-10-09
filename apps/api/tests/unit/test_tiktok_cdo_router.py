from __future__ import annotations

import json

from fastapi.testclient import TestClient

from data_intelligence_hub.agents.tiktok_cdo.config import get_cdo_settings
from data_intelligence_hub.agents.tiktok_cdo.router import verify_signature
from data_intelligence_hub.main import app


def test_webhook_challenge_is_publicly_mounted() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/agents/tiktok-cdo/webhook",
        content=json.dumps({"type": "url_verification", "challenge": "challenge-token"}),
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-token"}


def test_signature_rejects_modified_body() -> None:
    signature = "f210e63cc962d5f912e14f754d56cfd5f44bcb98e74b893dcdc279311930c025"
    assert verify_signature("token", "123", "nonce", "body", signature)
    assert not verify_signature("token", "123", "nonce", "modified", signature)


def test_webhook_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("LARK_CDO_VERIFICATION_TOKEN", "token")
    get_cdo_settings.cache_clear()
    client = TestClient(app)
    response = client.post(
        "/api/agents/tiktok-cdo/webhook",
        content=json.dumps({"event": {"message": {"content": "{}"}}}),
        headers={
            "x-lark-signature": "invalid",
            "x-lark-request-timestamp": "123",
            "x-lark-request-nonce": "nonce",
        },
    )
    get_cdo_settings.cache_clear()
    assert response.status_code == 403

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from data_intelligence_hub.main import app


@pytest.mark.asyncio
async def test_health_reports_service_state() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["service"] == "Data Intelligence Hub API"
    assert payload["status"] in {"ok", "degraded"}
    assert payload["database"] in {"connected", "timeout", "unavailable"}

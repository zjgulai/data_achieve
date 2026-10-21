"""Live status semantics for GET /api/collectors/catalog (SP-02).

The static catalog ``status`` is a declaration. ``live_status`` is the runtime
availability from providers/status. The two must not overwrite each other.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from data_intelligence_hub.api.routes.collectors import (
    _apply_live_status,
    get_collector_catalog,
    router,
)
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.platform_packages import service as platform_service
from data_intelligence_hub.platform_packages.status import (
    EndpointAvailability,
    ProviderStatusResponse,
)
from data_intelligence_hub.schemas.collector_catalog import CollectorEndpointMetadata


def _endpoint(endpoint_type: str, status: str = "verified") -> CollectorEndpointMetadata:
    return CollectorEndpointMetadata(
        endpoint_type=endpoint_type,
        label=endpoint_type,
        platform="example",
        description="fixture",
        status=status,
        provider="fixture",
    )


def test_apply_live_status_sets_live_and_keeps_static_status() -> None:
    endpoints = [
        _endpoint("live_verified"),
        _endpoint("live_empty"),
        _endpoint("missing", status="pending"),
    ]
    statuses = {"live_verified": "verified", "live_empty": "empty"}

    result = _apply_live_status(endpoints, statuses)
    by_type = {endpoint.endpoint_type: endpoint for endpoint in result}

    assert by_type["live_verified"].live_status == "verified"
    assert by_type["live_empty"].live_status == "empty"
    assert by_type["missing"].live_status is None

    # Static declarations are untouched, including the endpoint without status.
    assert [endpoint.status for endpoint in result] == ["verified", "verified", "pending"]


def test_apply_live_status_does_not_mutate_input() -> None:
    endpoints = [_endpoint("live_verified")]

    _apply_live_status(endpoints, {"live_verified": "degraded"})

    assert endpoints[0].live_status is None
    assert endpoints[0].status == "verified"


def test_apply_live_status_with_empty_statuses_leaves_all_none() -> None:
    endpoints = [_endpoint("a"), _endpoint("b")]

    result = _apply_live_status(endpoints, {})

    assert all(endpoint.live_status is None for endpoint in result)
    assert [endpoint.status for endpoint in result] == ["verified", "verified"]


def test_catalog_applies_provider_status_when_session_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_provider_status(_session: object) -> ProviderStatusResponse:
        return ProviderStatusResponse(
            catalog_digest="test",
            endpoints=(
                EndpointAvailability(
                    endpoint_type="tikhub_tiktok_video_search",
                    availability="empty",
                    missing_configuration=(),
                    last_test_status="success",
                    last_test_at=None,
                    last_records_count=0,
                    last_error_message=None,
                ),
            ),
        )

    monkeypatch.setattr(platform_service, "get_provider_status", fake_get_provider_status)

    catalog = asyncio.run(
        get_collector_catalog(session=object())  # type: ignore[arg-type]
    )
    by_type = {
        endpoint.endpoint_type: endpoint
        for entry in catalog.collectors
        for endpoint in entry.endpoints
    }

    assert by_type["tikhub_tiktok_video_search"].live_status == "empty"
    assert by_type["tikhub_tiktok_video_search"].status == "verified"
    # Endpoints absent from the status response keep live_status None.
    assert by_type["apify_tiktok_scraper"].live_status is None


class _FailingSession:
    async def execute(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("db unavailable")


def test_status_lookup_failure_keeps_catalog_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        catalog = asyncio.run(
            get_collector_catalog(session=_FailingSession())  # type: ignore[arg-type]
        )

    assert catalog.collectors
    assert all(
        endpoint.live_status is None for entry in catalog.collectors for endpoint in entry.endpoints
    )
    assert "collector_catalog_live_status_failed" in caplog.text


def test_catalog_http_returns_200_when_status_lookup_fails() -> None:
    async def failing_session() -> AsyncIterator[_FailingSession]:
        yield _FailingSession()

    app = FastAPI()
    app.include_router(router, prefix="/api/collectors")
    app.dependency_overrides[get_session] = failing_session

    response = TestClient(app).get("/api/collectors/catalog")

    assert response.status_code == 200
    endpoints = [
        endpoint
        for collector in response.json()["collectors"]
        for endpoint in collector["endpoints"]
    ]
    assert endpoints
    assert all(endpoint["live_status"] is None for endpoint in endpoints)
    # Static declaration is still served unchanged.
    assert any(endpoint["status"] == "verified" for endpoint in endpoints)

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from data_intelligence_hub.api.routes import health as health_route
from data_intelligence_hub.core import database
from data_intelligence_hub.core.database import DatabaseSchemaStatus
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
    assert payload["schema"] in {"current", "pending", "missing", "timeout", "unavailable"}
    assert "schema_revision" in payload
    assert "schema_head" in payload


@pytest.mark.asyncio
async def test_health_is_ready_only_when_database_and_schema_are_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def connected_database() -> str:
        return "connected"

    async def current_schema() -> DatabaseSchemaStatus:
        return DatabaseSchemaStatus(
            status="current",
            current_revision="202606110013",
            head_revision="202606110013",
        )

    monkeypatch.setattr(health_route, "check_database", connected_database)
    monkeypatch.setattr(health_route, "check_database_schema", current_schema)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert payload["schema"] == "current"


@pytest.mark.asyncio
async def test_health_degrades_when_schema_is_not_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def connected_database() -> str:
        return "connected"

    async def pending_schema() -> DatabaseSchemaStatus:
        return DatabaseSchemaStatus(
            status="pending",
            current_revision="202606110012",
            head_revision="202606110013",
        )

    monkeypatch.setattr(health_route, "check_database", connected_database)
    monkeypatch.setattr(health_route, "check_database_schema", pending_schema)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "connected"
    assert payload["schema"] == "pending"


@pytest.mark.asyncio
async def test_database_schema_check_reports_current_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
            await connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('202606110013')")
            )
        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(database, "get_alembic_head_revision", lambda: "202606110013")

        schema_status = await database.check_database_schema()

        assert schema_status == DatabaseSchemaStatus(
            status="current",
            current_revision="202606110013",
            head_revision="202606110013",
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_schema_check_reports_missing_revision_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine: AsyncEngine = create_async_engine("sqlite+aiosqlite://")
    try:
        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(database, "get_alembic_head_revision", lambda: "202606110013")

        schema_status = await database.check_database_schema()

        assert schema_status == DatabaseSchemaStatus(
            status="missing",
            current_revision=None,
            head_revision="202606110013",
        )
    finally:
        await engine.dispose()

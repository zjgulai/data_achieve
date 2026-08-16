from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import capability_discovery as discovery_routes
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryPreviewResponse,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
    CapabilityDiscoveryFixtureInvalidError,
)

FIXTURE_IDS = [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1",
]
VALID_PAYLOAD = {
    "schema_version": "capability_discovery_preview_request.v1",
    "preview_mode": "fixture_replay",
    "fixture_ids": FIXTURE_IDS,
}


@dataclass(frozen=True, slots=True)
class DiscoveryRouteTestContext:
    client: AsyncClient
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


@dataclass
class RecordingLogger:
    exception_events: list[tuple[str, dict[str, object]]]

    def exception(self, event_name: str, **fields: object) -> None:
        self.exception_events.append((event_name, fields))


@pytest_asyncio.fixture()
async def route_context() -> AsyncIterator[DiscoveryRouteTestContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield DiscoveryRouteTestContext(
                client=client,
                engine=engine,
                session_factory=session_factory,
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        await engine.dispose()


async def register_and_login(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "discovery-owner@example.com",
            "password": "StrongPassword123!",
            "name": "Discovery Owner",
        },
    )
    assert response.status_code == 201


async def count_all_tables(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    async with session_factory() as session:
        for table in Base.metadata.sorted_tables:
            result = await session.execute(select(func.count()).select_from(table))
            counts[table.name] = result.scalar_one()
    return counts


@pytest.mark.asyncio
async def test_discovery_preview_requires_authentication(
    route_context: DiscoveryRouteTestContext,
) -> None:
    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json=VALID_PAYLOAD,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_discovery_preview_returns_four_source_fixture_response(
    route_context: DiscoveryRouteTestContext,
) -> None:
    await register_and_login(route_context.client)

    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json=VALID_PAYLOAD,
    )

    assert response.status_code == 200
    parsed = CapabilityDiscoveryPreviewResponse.model_validate(response.json())
    assert parsed.summary.source_count == 4
    assert parsed.summary.candidate_assertion_count == 7
    assert parsed.summary.evidence_count == 4
    assert parsed.summary.warning_count == 2
    assert parsed.summary.error_count == 0
    assert parsed.provider_call is False
    assert parsed.provider_call_attempted is False
    assert parsed.actor_run is False
    assert parsed.browser_run is False
    assert parsed.llm_call is False
    assert parsed.credential_read_attempted is False
    assert parsed.database_write is False
    assert parsed.database_migration is False
    assert parsed.workflow_run_created is False
    assert parsed.candidate_publish_allowed is False
    assert parsed.production_write_allowed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_payload",
    [
        {**VALID_PAYLOAD, "fixture_ids": []},
        {**VALID_PAYLOAD, "fixture_ids": [FIXTURE_IDS[0], FIXTURE_IDS[0]]},
        {**VALID_PAYLOAD, "fixture_ids": [*FIXTURE_IDS, "fifth-fixture"]},
        {**VALID_PAYLOAD, "raw_url": "https://example.com/source"},
        {**VALID_PAYLOAD, "preview_mode": "live_capture"},
    ],
)
async def test_discovery_preview_rejects_invalid_request_contract(
    route_context: DiscoveryRouteTestContext,
    invalid_payload: dict[str, object],
) -> None:
    await register_and_login(route_context.client)

    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json=invalid_payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_discovery_preview_maps_unknown_fixture_to_422(
    route_context: DiscoveryRouteTestContext,
) -> None:
    await register_and_login(route_context.client)
    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json={**VALID_PAYLOAD, "fixture_ids": ["not-registered"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "capability_discovery_fixture_unknown"


@pytest.mark.asyncio
async def test_discovery_preview_maps_invalid_fixture_to_503(
    route_context: DiscoveryRouteTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(route_context.client)

    def raise_invalid_fixture(*args: object, **kwargs: object) -> object:
        raise CapabilityDiscoveryFixtureInvalidError

    monkeypatch.setattr(
        discovery_routes,
        "build_capability_discovery_preview",
        raise_invalid_fixture,
    )
    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json=VALID_PAYLOAD,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "capability_discovery_fixture_invalid"


@pytest.mark.asyncio
async def test_discovery_preview_maps_contract_error_to_500(
    route_context: DiscoveryRouteTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(route_context.client)

    def raise_contract_error(*args: object, **kwargs: object) -> object:
        raise CapabilityDiscoveryContractInvalidError

    monkeypatch.setattr(
        discovery_routes,
        "build_capability_discovery_preview",
        raise_contract_error,
    )
    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json=VALID_PAYLOAD,
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "capability_discovery_contract_invalid"


@pytest.mark.asyncio
async def test_discovery_preview_sanitizes_and_logs_unknown_error(
    route_context: DiscoveryRouteTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(route_context.client)
    logger = RecordingLogger(exception_events=[])

    def raise_unknown(*args: object, **kwargs: object) -> object:
        raise RuntimeError("secret-payload-must-not-leak")

    monkeypatch.setattr(discovery_routes, "logger", logger)
    monkeypatch.setattr(
        discovery_routes,
        "build_capability_discovery_preview",
        raise_unknown,
    )
    response = await route_context.client.post(
        "/api/capabilities/discovery/preview",
        json=VALID_PAYLOAD,
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "internal_server_error"
    assert len(logger.exception_events) == 1
    event_name, fields = logger.exception_events[0]
    assert event_name == "capability_discovery_preview_failed"
    assert fields["error_type"] == "RuntimeError"
    assert "secret-payload-must-not-leak" not in str(fields)
    assert "fixture_ids" not in fields


@pytest.mark.asyncio
async def test_discovery_preview_executes_no_sql_write_and_changes_no_table_count(
    route_context: DiscoveryRouteTestContext,
) -> None:
    await register_and_login(route_context.client)
    before = await count_all_tables(route_context.session_factory)
    statements: list[str] = []
    forbidden_commands = {"INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"}

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _execution_context: object,
        _executemany: bool,
    ) -> None:
        normalized = " ".join(statement.split()).upper()
        statements.append(normalized)
        command = normalized.split(maxsplit=1)[0] if normalized else ""
        if command in forbidden_commands:
            raise AssertionError(f"discovery_preview_sql_write_forbidden:{command}")

    event.listen(
        route_context.engine.sync_engine,
        "before_cursor_execute",
        capture_statement,
    )
    try:
        response = await route_context.client.post(
            "/api/capabilities/discovery/preview",
            json=VALID_PAYLOAD,
        )
    finally:
        event.remove(
            route_context.engine.sync_engine,
            "before_cursor_execute",
            capture_statement,
        )
    after = await count_all_tables(route_context.session_factory)

    assert response.status_code == 200
    assert before == after
    assert statements
    assert all(statement.startswith("SELECT") for statement in statements)


@pytest.mark.asyncio
async def test_only_preview_post_route_is_registered_and_no_action_routes_exist(
    route_context: DiscoveryRouteTestContext,
) -> None:
    discovery_api_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and "/capabilities/discovery" in route.path
    ]
    assert len(discovery_api_routes) == 1
    assert discovery_api_routes[0].path == "/api/capabilities/discovery/preview"
    assert discovery_api_routes[0].methods == {"POST"}

    await register_and_login(route_context.client)
    for suffix in ("verify", "publish", "run", "refresh", "browser-capture"):
        response = await route_context.client.post(
            f"/api/capabilities/discovery/{suffix}",
            json={},
        )
        assert response.status_code == 404

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import capabilities as capability_routes
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.capability_matrix import CapabilityMatrixResponse
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_matrix import build_capability_matrix
from data_intelligence_hub.services.exceptions import CapabilityCatalogLoadError


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            CapabilityCatalogHead(
                singleton_key="global",
                current_revision_id=None,
                head_version=0,
            )
        )
        await session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def register_and_login(client: AsyncClient) -> None:
    register = await client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "StrongPassword123!",
            "name": "Owner",
        },
    )
    assert register.status_code == 201


@pytest.mark.asyncio
async def test_capability_routes_require_authentication(client: AsyncClient) -> None:
    for path in (
        "/api/capabilities/matrix",
        "/api/capabilities/assertions",
        "/api/capabilities/implementations",
        "/api/capabilities/implementations/youtube.v3",
    ):
        response = await client.get(path)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_capability_matrix_route_returns_complete_matrix(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get("/api/capabilities/matrix")
    assert response.status_code == 200

    payload = response.json()
    CapabilityMatrixResponse.model_validate(payload)
    assert payload == build_capability_matrix().model_dump(mode="json")
    assert payload["schema_version"] == "capability_matrix.v1"
    assert len(payload["platforms"]) == 7
    assert len(payload["access_channels"]) == 6
    assert "channels" not in payload
    assert len(payload["cells"]) == 42
    assert payload["summary"]["populated_cell_count"] == 7
    assert payload["summary"]["unknown_cell_count"] == 35
    assert payload["provider_call"] is False
    assert payload["production_write_allowed"] is False


@pytest.mark.asyncio
async def test_capability_route_resolves_one_catalog_per_request(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(client)
    youtube = get_capability_catalog(platform="youtube")
    calls = 0

    async def resolve_once(_session: AsyncSession) -> CapabilityCatalog:
        nonlocal calls
        calls += 1
        return youtube

    monkeypatch.setattr(
        capability_routes,
        "resolve_current_capability_catalog",
        resolve_once,
    )
    matrix_response = await client.get("/api/capabilities/matrix")
    assertions_response = await client.get("/api/capabilities/assertions")
    implementations_response = await client.get("/api/capabilities/implementations")
    detail_response = await client.get("/api/capabilities/implementations/youtube.v3")

    assert matrix_response.status_code == 200
    assert matrix_response.json() == build_capability_matrix(catalog=youtube).model_dump(
        mode="json"
    )
    assert assertions_response.status_code == 200
    assert {item["implementation_id"] for item in assertions_response.json()} == {"youtube.v3"}
    assert implementations_response.status_code == 200
    assert [item["implementation_id"] for item in implementations_response.json()] == ["youtube.v3"]
    assert detail_response.status_code == 200
    assert detail_response.json()["implementation"]["implementation_id"] == "youtube.v3"
    assert calls == 4


@pytest.mark.asyncio
async def test_capability_list_routes_apply_typed_filters(client: AsyncClient) -> None:
    await register_and_login(client)

    assertions_response = await client.get(
        "/api/capabilities/assertions",
        params={
            "platform": "youtube",
            "access_channel": "official_authorized_api",
            "resource_type": "conversation",
            "operation": "list_enumerate",
            "support_status": "candidate",
        },
    )
    assert assertions_response.status_code == 200
    assertions = assertions_response.json()
    assert len(assertions) == 1
    assert assertions[0]["implementation_id"] == "youtube.v3"

    implementations_response = await client.get(
        "/api/capabilities/implementations",
        params={
            "platform": "youtube",
            "access_channel": "official_authorized_api",
        },
    )
    assert implementations_response.status_code == 200
    implementations = implementations_response.json()
    assert len(implementations) == 1
    assert implementations[0]["implementation_id"] == "youtube.v3"


@pytest.mark.asyncio
async def test_capability_list_route_rejects_unknown_enum(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get(
        "/api/capabilities/assertions",
        params={"platform": "missing"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_capability_list_routes_return_empty_for_valid_zero_result(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    filters = {
        "platform": "youtube",
        "access_channel": "authorized_browser",
    }

    assertions_response = await client.get(
        "/api/capabilities/assertions",
        params=filters,
    )
    assert assertions_response.status_code == 200
    assert assertions_response.json() == []

    implementations_response = await client.get(
        "/api/capabilities/implementations",
        params=filters,
    )
    assert implementations_response.status_code == 200
    assert implementations_response.json() == []


@pytest.mark.asyncio
async def test_capability_implementation_detail_route(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get("/api/capabilities/implementations/youtube.v3")
    assert response.status_code == 200
    assert response.json()["implementation"]["implementation_id"] == "youtube.v3"

    missing_response = await client.get("/api/capabilities/implementations/missing-provider")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "capability_implementation_not_found"


@pytest.mark.asyncio
async def test_capability_matrix_route_maps_catalog_load_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(client)

    async def raise_catalog_load_error(_session: AsyncSession) -> CapabilityCatalog:
        raise CapabilityCatalogLoadError

    monkeypatch.setattr(
        capability_routes,
        "resolve_current_capability_catalog",
        raise_catalog_load_error,
    )
    response = await client.get("/api/capabilities/matrix")

    assert response.status_code == 500
    assert response.json()["detail"] == "capability_catalog_load_failed"

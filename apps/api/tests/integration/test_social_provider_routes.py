from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base


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
async def test_social_provider_routes_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/automation/social-provider-catalog")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_social_provider_catalog_route_returns_platforms(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get("/api/automation/social-provider-catalog")
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "external_provider_catalog.v1"
    assert payload["provider_call"] is False
    assert {item["provider_id"] for item in payload["providers"]} >= {
        "youtube.v3",
        "reddit.praw",
        "x.v2",
        "instagram_graph.v19",
        "threads.graph.v1",
        "tiktok_research",
    }


@pytest.mark.asyncio
async def test_social_provider_catalog_route_filters_by_platform(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.get(
        "/api/automation/social-provider-catalog",
        params={"platform": "reddit"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["providers"]) == 1
    assert payload["providers"][0]["platform"] == "reddit"


@pytest.mark.asyncio
async def test_social_provider_catalog_route_filters_by_resource_group(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.get(
        "/api/automation/social-provider-catalog",
        params={"resource-group": "ugc_posts"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert any(provider["platform"] == "linkedin" for provider in payload["providers"])


@pytest.mark.asyncio
async def test_social_provider_readiness_route_blocks_missing_credentials(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-provider-readiness",
        json={
            "platform": "youtube",
            "endpoints": ["search.list", "videos.list"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness"] is False
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["missing_credentials"] == ["api_key"]


@pytest.mark.asyncio
async def test_social_provider_gate_route_requires_authorization_and_returns_fixture_scope(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    not_authorized = await client.post(
        "/api/automation/social-provider-gate",
        json={
            "authorized": False,
            "platform": "youtube",
            "endpoints": ["search.list", "videos.list"],
            "credentials_ready": {"api_key": True},
            "approval_id": "test-approval-id-001",
        },
    )
    assert not_authorized.status_code == 400
    assert not_authorized.json()["detail"] == "social_provider_gate_authorization_required"

    authorized = await client.post(
        "/api/automation/social-provider-gate",
        json={
            "authorized": True,
            "platform": "youtube",
            "endpoints": ["search.list", "videos.list"],
            "credentials_ready": {"api_key": True},
            "max_requests": 20,
            "approval_id": "test-approval-id-002",
        },
    )
    assert authorized.status_code == 200
    payload = authorized.json()
    assert payload["provider_call_allowed"] is True
    assert payload["provider_call_attempted"] is False
    assert payload["run_scope"] == "fixture_gate_only"
    assert payload["production_write_allowed"] is False


@pytest.mark.asyncio
async def test_social_provider_live_approval_template_route(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-provider-live-approval-template",
        json={
            "platform": "youtube",
            "endpoints": ["videos.list"],
            "intended_use": "small scoped read-only YouTube validation",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["dependency_install_allowed"] is False
    assert payload["production_write_allowed"] is False
    assert payload["approval_packet"]["optional_dependency_extra"] == "social-youtube"


@pytest.mark.asyncio
async def test_social_provider_dependency_gate_route_returns_dry_run_install_plan(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-provider-dependency-gate",
        json={
            "platform": "reddit",
            "authorized": True,
            "approval_id": "approval-local-deps",
            "confirm_dependency_review": True,
            "install_scope": "local_dev_optional_dependency",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["dependency_install_allowed"] is True
    assert payload["dependency_install_executed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["installation_plan"]["package"] == "asyncpraw"
    assert payload["installation_plan"]["pyproject_extra"] == "social-reddit"


@pytest.mark.asyncio
async def test_social_provider_adapter_plan_route_returns_fixture_plan(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-provider-adapter-plan",
        json={
            "platform": "youtube",
            "endpoints": ["videos.list"],
            "fixture_limit": 2,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "social_provider_adapter_plan.v1"
    assert payload["provider_id"] == "youtube.v3"
    assert payload["adapter_module"] == "data_intelligence_hub.social_api.youtube.google_api_client"
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["live_client_created"] is False
    assert payload["production_write_allowed"] is False
    assert payload["planned_operations"][0]["provider_call"] is False


@pytest.mark.asyncio
async def test_social_provider_source_template_route_returns_no_write_payload(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-provider-source-template",
        json={
            "platform": "reddit",
            "endpoints": ["search"],
            "source_name": "Reddit search fixture source",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "social_provider_source_template.v1"
    assert payload["source_type"] == "manual_json"
    assert payload["source_create_allowed"] is False
    assert payload["source_created"] is False
    assert payload["task_created"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["production_write_allowed"] is False
    assert payload["source_create_payload"]["type"] == "manual_json"
    assert payload["source_create_payload"]["config"]["json_data"]["provider_call"] is False


@pytest.mark.asyncio
async def test_social_raw_preview_route_returns_fixture_records(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-raw-preview",
        json={
            "platform": "youtube",
            "endpoint": "videos.list",
            "fixture_limit": 2,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["fixture_only"] is True
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["production_write_allowed"] is False
    assert len(payload["records"]) == 2
    assert payload["records"][0]["schema_version"] == "social_raw.v1"


@pytest.mark.asyncio
async def test_social_raw_preview_route_blocks_live_comparison(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-raw-preview",
        json={
            "platform": "reddit",
            "endpoint": "search",
            "include_live_comparison": True,
            "authorized": True,
            "approval_id": "approval-ignored",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert "live_comparison_requires_separate_l4_authorization" in payload["blocked_reasons"]


@pytest.mark.asyncio
async def test_social_normalization_preview_route_returns_fixture_items(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-normalization-preview",
        json={
            "platform": "reddit",
            "endpoint": "comments.new",
            "fixture_limit": 1,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "social_normalization_preview.v1"
    assert payload["fixture_only"] is True
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["production_write_allowed"] is False
    assert payload["normalization_write_allowed"] is False
    assert payload["dataset_write_allowed"] is False
    assert len(payload["raw_records"]) == 1
    assert {item["schema_version"] for item in payload["normalized_items"]} == {
        "social_comment.v1",
        "social_voc_item.v1",
    }
    assert (
        payload["normalized_items"][0]["raw_record_id"]
        == payload["raw_records"][0]["raw_record_id"]
    )


@pytest.mark.asyncio
async def test_social_provider_readiness_unknown_platform_returns_404(client: AsyncClient) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-provider-readiness",
        json={
            "platform": "unknown",
            "endpoints": ["search.list"],
        },
    )
    assert response.status_code == 404

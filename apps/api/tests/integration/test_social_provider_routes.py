from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import social_provider as social_provider_routes
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.youtube_read_adapter import (
    YouTubeReadAdapterFoundationResponse,
    YouTubeReadPlanRequest,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.social_provider import (
    get_social_provider_catalog,
)
from data_intelligence_hub.services.social_provider import (
    prepare_youtube_read_plan as prepare_youtube_read_plan_service,
)
from data_intelligence_hub.social_api.youtube.fixtures import (
    YouTubeFixtureContractInvalidError,
)
from data_intelligence_hub.social_api.youtube.normalizer import (
    YouTubeNormalizedPayloadInvalidError,
)


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


def test_youtube_read_plan_openapi_preserves_typed_request_body() -> None:
    operation = app.openapi()["paths"]["/api/automation/social-provider-youtube-read-plan"]["post"]
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert schema["$ref"] == "#/components/schemas/YouTubeReadPlanRequest"


@pytest.mark.asyncio
async def test_youtube_read_plan_validation_sanitizer_is_path_scoped(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    response = await client.post(
        "/api/automation/social-provider-readiness",
        json={"platform": "youtube", "endpoints": []},
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert response.json()["detail"][0]["loc"] == ["body", "endpoints"]


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
    assert payload == get_social_provider_catalog().model_dump(mode="json")
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
async def test_social_catalog_and_readiness_resolve_one_current_catalog_each(
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
        social_provider_routes,
        "resolve_current_capability_catalog",
        resolve_once,
    )
    catalog_response = await client.get("/api/automation/social-provider-catalog")
    readiness_response = await client.post(
        "/api/automation/social-provider-readiness",
        json={
            "platform": "youtube",
            "endpoints": ["search.list", "videos.list"],
        },
    )

    assert catalog_response.status_code == 200
    assert [item["provider_id"] for item in catalog_response.json()["providers"]] == ["youtube.v3"]
    assert readiness_response.status_code == 200
    assert readiness_response.json()["provider_id"] == "youtube.v3"
    assert calls == 2


@pytest.mark.asyncio
async def test_social_provider_gate_uses_current_catalog(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(client)
    youtube = get_capability_catalog(platform="youtube")
    implementation = youtube.implementations[0].model_copy(
        update={"supported_endpoints": ["search.list"]}
    )
    current_catalog = youtube.model_copy(update={"implementations": [implementation]})
    calls = 0

    async def resolve_once(_session: AsyncSession) -> CapabilityCatalog:
        nonlocal calls
        calls += 1
        return current_catalog

    monkeypatch.setattr(
        social_provider_routes,
        "resolve_current_capability_catalog",
        resolve_once,
    )
    response = await client.post(
        "/api/automation/social-provider-gate",
        json={
            "authorized": True,
            "platform": "youtube",
            "endpoints": ["search.list", "videos.list"],
            "credentials_ready": {"api_key": True},
            "approval_id": "current-catalog-gate-001",
        },
    )

    assert response.status_code == 200
    assert response.json()["declared_readiness"] is False
    assert "scope_missing:videos.list" in response.json()["blocked_reasons"]
    assert calls == 1


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
    assert payload["schema_version"] == "social_provider_readiness.v2"
    assert payload["declared_readiness"] is False
    assert payload["readiness_basis"] == "caller_declared"
    assert payload["execution_enabled"] is False
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
    assert payload["schema_version"] == "social_provider_gate.v2"
    assert payload["declared_readiness"] is True
    assert payload["readiness_basis"] == "caller_declared"
    assert payload["execution_enabled"] is False
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["run_scope"] == "fixture_gate_only"
    assert payload["production_write_allowed"] is False


@pytest.mark.asyncio
async def test_youtube_read_plan_route_is_authenticated_strict_and_fixture_only(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unauthorized = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={"query": {"query": "agentic workflows"}},
    )
    assert unauthorized.status_code == 401

    await register_and_login(client)

    def prepare_at_fixture_time(
        payload: YouTubeReadPlanRequest,
        *,
        catalog: CapabilityCatalog,
    ) -> YouTubeReadAdapterFoundationResponse:
        return prepare_youtube_read_plan_service(
            payload,
            catalog=catalog,
            now=datetime(2026, 7, 19, tzinfo=UTC),
        )

    monkeypatch.setattr(
        social_provider_routes,
        "prepare_youtube_read_plan",
        prepare_at_fixture_time,
    )
    response = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={
            "query": {
                "query": "agentic workflows",
                "published_after": "2026-07-01T00:00:00Z",
                "published_before": "2026-07-17T00:00:00Z",
                "region_code": "US",
                "relevance_language": "en",
                "order": "relevance",
                "max_items": 50,
            },
            "credential_reference": "env:YOUTUBE_API_KEY",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    rendered = response.text
    assert payload["foundation_ready"] is True
    assert payload["execution_enabled"] is False
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["database_write"] is False
    assert payload["credential_reference"] is None
    assert payload["query"] is None
    assert "agentic workflows" not in rendered
    assert "env:YOUTUBE_API_KEY" not in rendered

    rejected = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={
            "query": {"query": "agentic workflows"},
            "api_key": "must-not-be-accepted",
        },
    )
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "youtube_read_plan_request_invalid"}
    assert "must-not-be-accepted" not in rejected.text

    invalid_reference = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={
            "query": {"query": "agentic workflows"},
            "credential_reference": "RAW_SECRET_VALUE",
        },
    )
    assert invalid_reference.status_code == 422
    assert invalid_reference.json() == {"detail": "youtube_read_plan_request_invalid"}
    assert "RAW_SECRET_VALUE" not in invalid_reference.text

    invalid_query = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={"query": {"query": "TOP_SECRET\n"}},
    )
    assert invalid_query.status_code == 422
    assert invalid_query.json() == {"detail": "youtube_read_plan_request_invalid"}
    assert "TOP_SECRET" not in invalid_query.text


@pytest.mark.asyncio
async def test_youtube_read_plan_route_reports_stale_and_sanitized_failures(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(client)

    def prepare_stale(
        payload: YouTubeReadPlanRequest,
        *,
        catalog: CapabilityCatalog,
    ) -> YouTubeReadAdapterFoundationResponse:
        return prepare_youtube_read_plan_service(
            payload,
            catalog=catalog,
            now=datetime(2026, 7, 19, tzinfo=UTC) + timedelta(days=31),
        )

    monkeypatch.setattr(social_provider_routes, "prepare_youtube_read_plan", prepare_stale)
    stale = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={"query": {"query": "agentic workflows"}},
    )
    assert stale.status_code == 200
    assert stale.json()["foundation_ready"] is False
    assert "youtube_quota_evidence_stale" in stale.json()["blocked_reasons"]
    assert stale.json()["provider_call_allowed"] is False

    for exception_type, detail in (
        (YouTubeFixtureContractInvalidError, "youtube_fixture_contract_invalid"),
        (YouTubeNormalizedPayloadInvalidError, "youtube_normalized_payload_invalid"),
    ):

        def raise_failure(
            payload: YouTubeReadPlanRequest,
            *,
            catalog: CapabilityCatalog,
            _exception_type: type[ValueError] = exception_type,
        ) -> YouTubeReadAdapterFoundationResponse:
            _ = (payload, catalog)
            raise _exception_type("UNTRUSTED_SECRET_DETAIL")

        monkeypatch.setattr(social_provider_routes, "prepare_youtube_read_plan", raise_failure)
        failed = await client.post(
            "/api/automation/social-provider-youtube-read-plan",
            json={"query": {"query": "agentic workflows"}},
        )
        assert failed.status_code == 500
        assert failed.json() == {"detail": detail}
        assert "UNTRUSTED_SECRET_DETAIL" not in failed.text


@pytest.mark.asyncio
async def test_youtube_read_plan_route_uses_current_catalog_and_returns_404(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(client)

    youtube = get_capability_catalog(platform="youtube")
    implementation = youtube.implementations[0].model_copy(
        update={"supported_endpoints": ["search.list"]}
    )
    blocked_catalog = youtube.model_copy(update={"implementations": [implementation]})

    async def resolve_blocked(_session: AsyncSession) -> CapabilityCatalog:
        return blocked_catalog

    monkeypatch.setattr(
        social_provider_routes,
        "resolve_current_capability_catalog",
        resolve_blocked,
    )
    blocked = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={"query": {"query": "agentic workflows"}},
    )
    assert blocked.status_code == 200
    assert blocked.json()["foundation_ready"] is False
    assert "scope_missing:videos.list" in blocked.json()["blocked_reasons"]

    async def resolve_reddit_only(_session: AsyncSession) -> CapabilityCatalog:
        return get_capability_catalog(platform="reddit")

    monkeypatch.setattr(
        social_provider_routes,
        "resolve_current_capability_catalog",
        resolve_reddit_only,
    )
    response = await client.post(
        "/api/automation/social-provider-youtube-read-plan",
        json={"query": {"query": "agentic workflows"}},
    )
    assert response.status_code == 404


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
async def test_social_dataset_preview_route_returns_no_write_rows(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-dataset-preview",
        json={
            "platform": "reddit",
            "endpoint": "comments.new",
            "fixture_limit": 1,
            "dataset_name": "Reddit comments VOC fixture",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "social_dataset_preview.v1"
    assert payload["dataset_type"] == "social_voc_fixture_preview"
    assert payload["dataset_schema_version"] == "social_voc_dataset.v1"
    assert payload["fixture_only"] is True
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["production_write_allowed"] is False
    assert payload["dataset_write_allowed"] is False
    assert payload["dataset_created"] is False
    assert payload["dataset_version_created"] is False
    assert payload["export_created"] is False
    assert payload["row_count"] == 1
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["source_schema_version"] == "social_voc_item.v1"
    assert payload["rows"][0]["raw_record_id"] == payload["rows"][0]["payload"]["raw_record_id"]


@pytest.mark.asyncio
async def test_social_task_run_approval_template_route_returns_packet(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-task-run-approval-template",
        json={
            "platform": "reddit",
            "endpoints": ["comments.new"],
            "intended_use": "small scoped Reddit comments VOC fixture run",
            "credential_reference": "secret:reddit-oauth-readonly",
            "source_name": "Reddit comments fixture source",
            "task_name": "Reddit comments fixture task",
            "dataset_name": "Reddit comments VOC fixture",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "social_task_run_approval_template.v1"
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["source_create_allowed"] is False
    assert payload["task_create_allowed"] is False
    assert payload["task_run_allowed"] is False
    assert payload["dataset_write_allowed"] is False
    assert payload["export_allowed"] is False
    assert payload["production_write_allowed"] is False
    assert payload["approval_packet"]["schema_version"] == "social_task_run_l4_approval_packet.v1"
    assert payload["approval_packet"]["provider_call"] is False
    assert payload["approval_packet"]["scope"]["endpoints"] == ["comments.new"]
    assert "confirm_no_provider_call_without_live_gate" in payload["required_confirmations"]


@pytest.mark.asyncio
async def test_social_execution_dry_run_route_returns_fixture_bundle(
    client: AsyncClient,
) -> None:
    await register_and_login(client)

    response = await client.post(
        "/api/automation/social-execution-dry-run",
        json={
            "platform": "reddit",
            "endpoint": "comments.new",
            "fixture_limit": 1,
            "dataset_name": "Reddit comments VOC fixture",
            "source_name": "Reddit comments fixture source",
            "task_name": "Reddit comments fixture task",
            "intended_use": "small scoped Reddit comments fixture dry-run",
            "credential_reference": "secret:reddit-oauth-readonly",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "social_execution_dry_run.v1"
    assert payload["fixture_only"] is True
    assert payload["provider_call_allowed"] is False
    assert payload["provider_call_attempted"] is False
    assert payload["credential_read_attempted"] is False
    assert payload["source_create_allowed"] is False
    assert payload["task_create_allowed"] is False
    assert payload["task_run_allowed"] is False
    assert payload["dataset_write_allowed"] is False
    assert payload["export_allowed"] is False
    assert payload["production_write_allowed"] is False
    assert [stage["stage"] for stage in payload["execution_plan"]] == [
        "readiness",
        "raw_preview",
        "normalization_preview",
        "dataset_preview",
        "source_template",
        "task_run_approval_template",
    ]
    assert payload["raw_preview"]["records"][0]["schema_version"] == "social_raw.v1"
    assert payload["dataset_preview"]["row_count"] == 1
    assert payload["source_template"]["source_create_allowed"] is False
    assert payload["task_run_approval_template"]["task_run_allowed"] is False


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

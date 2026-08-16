from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import (
    capability_governance as governance_routes,
)
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCatalogHead,
    CapabilityGovernanceMembership,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.schemas.capability_catalog import CapabilityStatus
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
)
from data_intelligence_hub.services.capability_governance.intake import (
    CapabilityGovernanceIdempotencyConflictError,
    CapabilityGovernancePreviewStaleError,
    CapabilityGovernanceTransactionStateError,
)
from data_intelligence_hub.services.capability_governance.publication import (
    CapabilityGovernanceCatalogSnapshotInvalidError,
)

FIXTURE_IDS = [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1",
]
GOVERNANCE_PATH = "/api/capabilities/governance"


@dataclass(frozen=True)
class GovernanceRouteContext:
    client: AsyncClient
    sessions: async_sessionmaker[AsyncSession]
    user_id: uuid.UUID


@dataclass
class RecordingLogger:
    exception_events: list[tuple[str, dict[str, object]]]

    def exception(self, event: str, **fields: object) -> None:
        self.exception_events.append((event, fields))


@pytest_asyncio.fixture()
async def route_context() -> AsyncIterator[GovernanceRouteContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email="governance-route@example.com",
                    password_hash="not-used",
                    name="Governance Route",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Governance Route Workspace",
                    slug="governance-route-workspace",
                    owner_id=user_id,
                ),
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role="owner",
                ),
                CapabilityGovernanceMembership(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    can_read=True,
                    can_review=True,
                    can_publish=True,
                    is_active=True,
                ),
                CapabilityCatalogHead(
                    singleton_key="global",
                    current_revision_id=None,
                    head_version=0,
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with sessions() as session:
            yield session

    previous_override = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            client.cookies.set("access_token", create_access_token(user_id))
            yield GovernanceRouteContext(
                client=client,
                sessions=sessions,
                user_id=user_id,
            )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_override
        await engine.dispose()


def _preview() -> CapabilityDiscoveryPreviewResponse:
    return build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=FIXTURE_IDS,
        )
    )


def _import_payload(preview: CapabilityDiscoveryPreviewResponse) -> dict[str, object]:
    return {
        "schema_version": "capability_governance_import_request.v1",
        "fixture_ids": FIXTURE_IDS,
        "expected_preview_fingerprint": preview.preview_fingerprint,
    }


def _verify_payload(
    preview: CapabilityDiscoveryPreviewResponse,
    candidate: CapabilityCandidateAssertionPreview,
) -> dict[str, object]:
    catalog = get_capability_catalog()
    matched = next(
        (
            (implementation, assertion)
            for implementation in catalog.implementations
            for assertion in catalog.assertions
            if implementation.implementation_id == assertion.implementation_id
            and implementation.platform == candidate.platform
            and implementation.access_channel == candidate.access_channel
            and assertion.resource_type == candidate.resource_type
            and assertion.operation == candidate.operation
        ),
        None,
    )
    assert matched is not None
    implementation, assertion = matched
    return {
        "schema_version": "capability_governance_review_request.v1",
        "expected_task_version": 1,
        "action": "verify",
        "reason": "Route-level verified publication evidence.",
        "canonical_implementation": implementation.model_dump(mode="json"),
        "canonical_assertion": {
            "assertion_id": assertion.assertion_id,
            "implementation_id": implementation.implementation_id,
            "resource_type": assertion.resource_type.value,
            "operation": assertion.operation.value,
            "support_status": CapabilityStatus.VERIFIED.value,
            "source_resource_group": assertion.source_resource_group,
            "region_scope": assertion.region_scope,
            "purpose_scope": assertion.purpose_scope,
            "auth_scope": assertion.auth_scope,
            "field_contract": assertion.field_contract,
            "constraints": [item.model_dump(mode="json") for item in assertion.constraints],
            "score_profile": assertion.score_profile.model_dump(mode="json"),
            "evidence_refs": candidate.evidence_refs,
        },
    }


@pytest.mark.asyncio
async def test_governance_routes_require_authentication(
    route_context: GovernanceRouteContext,
) -> None:
    route_context.client.cookies.clear()

    response = await route_context.client.get(f"{GOVERNANCE_PATH}/candidates")

    assert response.status_code == 401
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_governance_read_checks_permission_before_resource_lookup(
    route_context: GovernanceRouteContext,
) -> None:
    missing_key = "sha256:" + "0" * 64
    async with route_context.sessions() as session:
        membership = (
            await session.execute(
                select(CapabilityGovernanceMembership).where(
                    CapabilityGovernanceMembership.user_id == route_context.user_id
                )
            )
        ).scalar_one()
        membership.can_read = False
        membership.can_review = False
        membership.can_publish = False
        await session.commit()

    forbidden = await route_context.client.get(f"{GOVERNANCE_PATH}/candidates/{missing_key}")
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "capability_governance_forbidden"
    assert forbidden.headers["X-Request-ID"]

    preview = _preview()
    write_forbidden = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json={
            **_import_payload(preview),
            "expected_preview_fingerprint": "sha256:" + "f" * 64,
        },
        headers={"Idempotency-Key": "route-forbidden-before-preview-0001"},
    )
    assert write_forbidden.status_code == 403
    assert write_forbidden.json()["detail"] == "capability_governance_forbidden"

    async with route_context.sessions() as session:
        membership = (
            await session.execute(
                select(CapabilityGovernanceMembership).where(
                    CapabilityGovernanceMembership.user_id == route_context.user_id
                )
            )
        ).scalar_one()
        membership.can_read = True
        await session.commit()

    not_found = await route_context.client.get(f"{GOVERNANCE_PATH}/candidates/{missing_key}")
    assert not_found.status_code == 404
    assert not_found.json()["detail"] == "governance_resource_not_found"


@pytest.mark.asyncio
async def test_import_candidate_and_task_routes_are_strict_and_auditable(
    route_context: GovernanceRouteContext,
) -> None:
    preview = _preview()
    payload = _import_payload(preview)

    missing_key = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=payload,
    )
    assert missing_key.status_code == 422
    assert missing_key.headers["X-Request-ID"]

    invalid_key = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=payload,
        headers={"Idempotency-Key": "short"},
    )
    assert invalid_key.status_code == 422
    assert invalid_key.json()["detail"][0]["msg"] == "idempotency_key_invalid"
    assert invalid_key.headers["X-Request-ID"]

    extra_field = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json={**payload, "raw_fixture_body": "forbidden"},
        headers={"Idempotency-Key": "route-import-extra-0001"},
    )
    assert extra_field.status_code == 422
    assert extra_field.headers["X-Request-ID"]

    key = "route-import-success-0001"
    created = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert created.status_code == 201
    created_payload = created.json()
    assert created.headers["X-Request-ID"] == created_payload["request_id"]
    assert created_payload["database_write"] is True
    assert created_payload["idempotent_replay"] is False
    assert key not in created.text

    replay = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert replay.status_code == 200
    assert replay.headers["X-Request-ID"] == replay.json()["request_id"]
    assert replay.json()["database_write"] is False
    assert replay.json()["idempotent_replay"] is True

    candidates = await route_context.client.get(
        f"{GOVERNANCE_PATH}/candidates",
        params={"limit": 2, "offset": 0},
    )
    assert candidates.status_code == 200
    assert candidates.headers["X-Request-ID"]
    assert candidates.json()["permissions"] == {
        "can_read": True,
        "can_review": True,
        "can_publish": True,
    }
    assert candidates.json()["limit"] == 2
    assert len(candidates.json()["items"]) == 2
    candidate_key = created_payload["candidates"][0]["candidate_key"]
    candidate = await route_context.client.get(f"{GOVERNANCE_PATH}/candidates/{candidate_key}")
    assert candidate.status_code == 200
    candidate_payload = candidate.json()
    assert candidate_payload["candidate"]["candidate_key"] == candidate_key
    assert candidate_payload["candidate"]["candidate_assertion"]["verification_status"] == (
        "unverified"
    )
    assert candidate_payload["evidence"]
    assert candidate_payload["open_verification_task"]["status"] == "open"
    assert candidate_payload["latest_decision"] is None
    assert "snapshot_payload" not in candidate.text

    tasks = await route_context.client.get(
        f"{GOVERNANCE_PATH}/verification-tasks",
        params={"status": "open", "limit": 100, "offset": 0},
    )
    assert tasks.status_code == 200
    task_id = created_payload["candidates"][0]["verification_task_id"]
    task = await route_context.client.get(f"{GOVERNANCE_PATH}/verification-tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["task"]["id"] == task_id

    invalid_page = await route_context.client.get(
        f"{GOVERNANCE_PATH}/candidates",
        params={"limit": 101},
    )
    assert invalid_page.status_code == 422


@pytest.mark.asyncio
async def test_review_conflicts_and_publication_rollback_are_append_only(
    route_context: GovernanceRouteContext,
) -> None:
    preview = _preview()
    imported = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=_import_payload(preview),
        headers={"Idempotency-Key": "route-publication-import-0001"},
    )
    assert imported.status_code == 201
    task_by_key = {
        item["candidate_key"]: item["verification_task_id"]
        for item in imported.json()["candidates"]
    }
    reviewed: tuple[str, str] | None = None
    for candidate in preview.candidate_assertions:
        candidate_key = compute_candidate_key(candidate)
        if candidate_key not in task_by_key:
            continue
        try:
            review_payload = _verify_payload(preview, candidate)
        except AssertionError:
            continue
        task_id = task_by_key[candidate_key]
        response = await route_context.client.post(
            f"{GOVERNANCE_PATH}/verification-tasks/{task_id}/decisions",
            json=review_payload,
            headers={"Idempotency-Key": "route-review-success-0001"},
        )
        assert response.status_code == 200
        reviewed = (response.json()["decision_id"], task_id)
        break
    assert reviewed is not None
    decision_id, task_id = reviewed

    conflict = await route_context.client.post(
        f"{GOVERNANCE_PATH}/verification-tasks/{task_id}/decisions",
        json={
            "schema_version": "capability_governance_review_request.v1",
            "expected_task_version": 1,
            "action": "reject",
            "reason": "A second decision is forbidden.",
            "canonical_implementation": None,
            "canonical_assertion": None,
        },
        headers={"Idempotency-Key": "route-review-conflict-0001"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "verification_task_conflict"

    first_publish = await route_context.client.post(
        f"{GOVERNANCE_PATH}/publications",
        json={
            "schema_version": "capability_governance_publication_request.v1",
            "expected_parent_revision_id": None,
            "reason": "Publish reviewed route evidence.",
            "operations": [
                {
                    "operation": "upsert_verified_assertion",
                    "verification_decision_id": decision_id,
                }
            ],
        },
        headers={"Idempotency-Key": "route-publish-first-0001"},
    )
    assert first_publish.status_code == 201
    first_revision_id = first_publish.json()["revision_id"]

    parent_conflict = await route_context.client.post(
        f"{GOVERNANCE_PATH}/publications",
        json={
            "schema_version": "capability_governance_publication_request.v1",
            "expected_parent_revision_id": None,
            "reason": "Stale parent must fail.",
            "operations": [
                {
                    "operation": "upsert_verified_assertion",
                    "verification_decision_id": decision_id,
                }
            ],
        },
        headers={"Idempotency-Key": "route-publish-conflict-0001"},
    )
    assert parent_conflict.status_code == 409
    assert parent_conflict.json()["detail"] == "publication_parent_conflict"

    second_publish = await route_context.client.post(
        f"{GOVERNANCE_PATH}/publications",
        json={
            "schema_version": "capability_governance_publication_request.v1",
            "expected_parent_revision_id": first_revision_id,
            "reason": "Append equal-content revision.",
            "operations": [
                {
                    "operation": "upsert_verified_assertion",
                    "verification_decision_id": decision_id,
                }
            ],
        },
        headers={"Idempotency-Key": "route-publish-second-0001"},
    )
    assert second_publish.status_code == 201
    second_revision_id = second_publish.json()["revision_id"]

    rollback = await route_context.client.post(
        f"{GOVERNANCE_PATH}/publications/rollback",
        json={
            "schema_version": "capability_governance_rollback_request.v1",
            "expected_current_revision_id": second_revision_id,
            "target_revision_id": first_revision_id,
            "reason": "Append a restoring revision.",
        },
        headers={"Idempotency-Key": "route-rollback-success-0001"},
    )
    assert rollback.status_code == 201
    assert rollback.json()["restored_from_revision_id"] == first_revision_id
    assert rollback.json()["revision_number"] == 3

    revisions = await route_context.client.get(
        f"{GOVERNANCE_PATH}/publications",
        params={"limit": 100, "offset": 0},
    )
    assert revisions.status_code == 200
    assert [item["revision_number"] for item in revisions.json()["items"]] == [
        3,
        2,
        1,
    ]
    current_revision_id = rollback.json()["revision_id"]
    detail = await route_context.client.get(f"{GOVERNANCE_PATH}/publications/{current_revision_id}")
    assert detail.status_code == 200
    assert detail.json()["revision"]["is_current"] is True
    assert detail.json()["revision"]["restored_from_revision_id"] == first_revision_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raised_error", "expected_status", "expected_detail"),
    [
        (CapabilityGovernancePreviewStaleError(), 409, "preview_stale"),
        (
            CapabilityGovernanceIdempotencyConflictError(),
            409,
            "idempotency_conflict",
        ),
        (
            CapabilityGovernanceTransactionStateError(),
            503,
            "persistence_unavailable",
        ),
        (
            CapabilityGovernanceCatalogSnapshotInvalidError(),
            500,
            "catalog_snapshot_invalid",
        ),
    ],
)
async def test_governance_write_errors_use_stable_allowlist_and_request_id(
    route_context: GovernanceRouteContext,
    monkeypatch: pytest.MonkeyPatch,
    raised_error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    async def fail_import(*_args: object, **_kwargs: object) -> object:
        raise raised_error

    monkeypatch.setattr(
        governance_routes,
        "import_capability_candidates",
        fail_import,
    )
    response = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=_import_payload(_preview()),
        headers={"Idempotency-Key": "route-error-mapping-0001"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_governance_unknown_error_is_sanitized_in_response_and_log(
    route_context: GovernanceRouteContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = RecordingLogger(exception_events=[])
    monkeypatch.setattr(governance_routes, "logger", logger)

    async def fail_import(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("raw-token=secret raw fixture body")

    monkeypatch.setattr(
        governance_routes,
        "import_capability_candidates",
        fail_import,
    )
    raw_key = "route-secret-error-key-0001"
    response = await route_context.client.post(
        f"{GOVERNANCE_PATH}/imports",
        json=_import_payload(_preview()),
        headers={"Idempotency-Key": raw_key},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "internal_server_error"
    assert response.headers["X-Request-ID"]
    rendered = repr(logger.exception_events)
    assert "raw-token" not in rendered
    assert "fixture body" not in rendered
    assert raw_key not in rendered
    assert logger.exception_events[0][0] == "capability_governance_request_failed"
    assert set(logger.exception_events[0][1]) == {
        "request_id",
        "action",
        "error_type",
        "exc_info",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"{GOVERNANCE_PATH}/verification-tasks/{uuid.UUID(int=0)}",
        f"{GOVERNANCE_PATH}/publications/{uuid.UUID(int=0)}",
    ],
)
async def test_governance_authorized_missing_resources_return_stable_404(
    route_context: GovernanceRouteContext,
    path: str,
) -> None:
    response = await route_context.client.get(path)

    assert response.status_code == 404
    assert response.json()["detail"] == "governance_resource_not_found"
    assert response.headers["X-Request-ID"]

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    QueryTerm,
    WorkflowPlan,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
    WorkflowVersionScope,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workflow_plans import (
    add_query_term,
    add_workflow_plan,
    add_workflow_plan_save_request,
    add_workflow_version,
    add_workflow_version_scope,
    count_monitoring_scopes,
    count_workflow_plans,
    count_workflow_versions,
    get_monitoring_scope_by_key,
    get_workflow_plan,
    get_workflow_plan_for_update,
    get_workflow_plan_save_request,
    get_workflow_version,
    insert_monitoring_scope_on_conflict,
    list_monitoring_scopes,
    list_query_terms_for_version,
    list_workflow_plans,
    list_workflow_version_scopes,
    list_workflow_versions,
    lock_project_for_workflow_plan_save,
)
from data_intelligence_hub.schemas.capability_catalog import PlatformId
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeListResponse,
    MonitoringScopeResponse,
    WorkflowPlanCloneRequest,
    WorkflowPlanCloneResponse,
    WorkflowPlanCreateRequest,
    WorkflowPlanDetailResponse,
    WorkflowPlanListResponse,
    WorkflowPlanResponse,
    WorkflowPlanSaveResponse,
    WorkflowPlanStatus,
    WorkflowPlanTransitionRequest,
    WorkflowPlanTransitionResponse,
    WorkflowPlanVersionCompareResponse,
    WorkflowVersionCreateRequest,
    WorkflowVersionDetailResponse,
    WorkflowVersionListResponse,
    WorkflowVersionResponse,
    WorkflowVersionSummaryResponse,
    normalize_idempotency_key,
    serialize_preview_snapshot,
)
from data_intelligence_hub.schemas.workflow_planner import (
    NormalizedMonitoringScope,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.exceptions import (
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanFlowModeConflictError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlanInvalidTransitionError,
    WorkflowPlanNotFoundError,
    WorkflowPlanPersistenceTransactionStateError,
    WorkflowPlanPreviewStaleError,
    WorkflowPlanScopeConflictError,
    WorkflowPlanStatusConflictError,
    WorkflowPlanVersionConflictError,
    WorkflowVersionNotFoundError,
)
from data_intelligence_hub.services.workflow_execution.integrity import (
    WorkflowVersionSnapshotInvalidError,
    validate_workflow_version_snapshot,
)
from data_intelligence_hub.services.workflow_planner.comparison import (
    compare_workflow_plan_previews,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    sha256_id,
)
from data_intelligence_hub.services.workflow_planner.lifecycle import (
    WorkflowPlanTransitionError,
)
from data_intelligence_hub.services.workflow_planner.lifecycle import (
    transition_workflow_plan_status as _transition_plan_status,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    build_scope_key,
    normalize_text,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    WorkflowPlanBuildResult,
    build_workflow_plan_result,
)

_PLATFORM_ORDER = {platform.value: index for index, platform in enumerate(PlatformId)}


async def _prepare_service_transaction(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise WorkflowPlanPersistenceTransactionStateError
    if session.in_transaction():
        await session.rollback()


def _key_hash(idempotency_key: str) -> str:
    normalized_key = normalize_idempotency_key(idempotency_key)
    return sha256_id(cast(JsonValue, normalized_key))


def _create_request_hash(
    *,
    project_id: uuid.UUID,
    payload: WorkflowPlanCreateRequest,
) -> str:
    request_payload = cast(
        JsonValue,
        {
            "method": "POST",
            "route": {
                "project_id": str(project_id),
                "resource": "workflow_plans",
            },
            "body": payload.model_dump(mode="json"),
        },
    )
    return sha256_id(request_payload)


def _version_request_hash(
    *,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    payload: WorkflowVersionCreateRequest,
) -> str:
    request_payload = cast(
        JsonValue,
        {
            "method": "POST",
            "route": {
                "project_id": str(project_id),
                "workflow_plan_id": str(workflow_plan_id),
                "resource": "workflow_plan_versions",
            },
            "body": payload.model_dump(mode="json"),
        },
    )
    return sha256_id(request_payload)


def _clone_request_hash(
    *,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    payload: WorkflowPlanCloneRequest,
) -> str:
    request_payload = cast(
        JsonValue,
        {
            "method": "POST",
            "route": {
                "project_id": str(project_id),
                "workflow_plan_id": str(workflow_plan_id),
                "resource": "workflow_plan_clone",
            },
            "body": payload.model_dump(mode="json"),
        },
    )
    return sha256_id(request_payload)


def _replay_response(
    save_request: WorkflowPlanSaveRequest,
    *,
    request_hash: str,
) -> WorkflowPlanSaveResponse:
    if save_request.request_hash != request_hash:
        raise WorkflowPlanIdempotencyConflictError
    original = WorkflowPlanSaveResponse.model_validate(save_request.response_payload)
    return original.model_copy(
        update={
            "database_write": False,
            "plan_changed": False,
            "idempotent_replay": True,
        },
        deep=True,
    )


def _replay_clone_response(
    save_request: WorkflowPlanSaveRequest,
    *,
    request_hash: str,
) -> WorkflowPlanCloneResponse:
    if save_request.request_hash != request_hash:
        raise WorkflowPlanIdempotencyConflictError
    original = WorkflowPlanCloneResponse.model_validate(save_request.response_payload)
    return original.model_copy(
        update={
            "database_write": False,
            "plan_changed": False,
            "idempotent_replay": True,
        },
        deep=True,
    )


def _is_idempotency_unique_violation(exc: IntegrityError) -> bool:
    origin = exc.orig
    if origin is None:
        return False
    cause = origin.__cause__
    sqlstate = getattr(origin, "sqlstate", None) or getattr(
        origin,
        "pgcode",
        None,
    )
    if sqlstate is None and cause is not None:
        sqlstate = getattr(cause, "sqlstate", None) or getattr(
            cause,
            "pgcode",
            None,
        )
    if sqlstate != "23505":
        return False

    constraint_name = getattr(origin, "constraint_name", None)
    if constraint_name is None:
        diagnostic = getattr(origin, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name is None and cause is not None:
        constraint_name = getattr(cause, "constraint_name", None)
        if constraint_name is None:
            diagnostic = getattr(cause, "diag", None)
            constraint_name = getattr(diagnostic, "constraint_name", None)
    return constraint_name == "uq_workflow_plan_save_requests_idempotency"


async def _recover_idempotency_race(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    error: IntegrityError,
) -> WorkflowPlanSaveResponse:
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)
    raise error


async def _run_with_idempotency_race_recovery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    attempt: Callable[[], Awaitable[WorkflowPlanSaveResponse]],
) -> WorkflowPlanSaveResponse:
    try:
        return await attempt()
    except IntegrityError as exc:
        if not _is_idempotency_unique_violation(exc):
            raise
        return await _recover_idempotency_race(
            session,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            error=exc,
        )


def _semantic_texts(values: Sequence[str]) -> list[str]:
    return sorted({normalized for value in values if (normalized := normalize_text(value))})


def _scope_semantic_payload(scope: MonitoringScope) -> dict[str, JsonValue]:
    platforms = sorted(
        set(scope.effective_platforms),
        key=lambda value: _PLATFORM_ORDER.get(value, len(_PLATFORM_ORDER)),
    )
    return cast(
        dict[str, JsonValue],
        {
            "scope_type": scope.scope_type,
            "canonical_term": (
                normalize_text(scope.canonical_term) if scope.canonical_term is not None else None
            ),
            "aliases": _semantic_texts(scope.aliases),
            "include_terms": _semantic_texts(scope.include_terms),
            "exclude_terms": _semantic_texts(scope.exclude_terms),
            "official_accounts": _semantic_texts(scope.official_accounts),
            "seed_urls": sorted(set(scope.seed_urls)),
            "effective_languages": _semantic_texts(scope.effective_languages),
            "effective_regions": _semantic_texts(scope.effective_regions),
            "effective_platforms": platforms,
            "match_mode": scope.match_mode,
        },
    )


def _scope_values(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    scope: NormalizedMonitoringScope,
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "workspace_id": workspace_id,
        "project_id": project_id,
        "created_by_user_id": created_by_user_id,
        "scope_key": scope.scope_key,
        "scope_type": scope.scope_type.value,
        "canonical_term": scope.canonical_term,
        "aliases": list(scope.aliases),
        "include_terms": list(scope.include_terms),
        "exclude_terms": list(scope.exclude_terms),
        "official_accounts": list(scope.official_accounts),
        "seed_urls": list(scope.seed_urls),
        "effective_languages": list(scope.effective_languages),
        "effective_regions": list(scope.effective_regions),
        "effective_platforms": [item.value for item in scope.effective_platforms],
        "match_mode": scope.match_mode.value,
        "created_at": created_at,
    }


async def _persist_scopes(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    scopes: Sequence[NormalizedMonitoringScope],
    created_at: datetime,
) -> dict[str, uuid.UUID]:
    scope_ids: dict[str, uuid.UUID] = {}
    for scope in scopes:
        inserted_id = await insert_monitoring_scope_on_conflict(
            session,
            _scope_values(
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                scope=scope,
                created_at=created_at,
            ),
        )
        if inserted_id is not None:
            scope_ids[scope.scope_key] = inserted_id
            continue

        existing = await get_monitoring_scope_by_key(
            session,
            workspace_id,
            project_id,
            scope.scope_key,
        )
        if (
            existing is None
            or build_scope_key(_scope_semantic_payload(existing)) != scope.scope_key
        ):
            raise WorkflowPlanScopeConflictError
        scope_ids[scope.scope_key] = existing.id
    return scope_ids


async def _persist_version_graph(
    session: AsyncSession,
    *,
    plan: WorkflowPlan,
    build_result: WorkflowPlanBuildResult,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    version_number: int,
    created_at: datetime,
    workflow_template_id: uuid.UUID | None = None,
    workflow_template_revision_id: uuid.UUID | None = None,
) -> WorkflowVersion:
    preview = build_result.preview
    preview_snapshot = serialize_preview_snapshot(preview)
    version = WorkflowVersion(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan.id,
        workflow_template_id=workflow_template_id
        if workflow_template_id is not None
        else plan.workflow_template_id,
        workflow_template_revision_id=workflow_template_revision_id
        if workflow_template_revision_id is not None
        else plan.workflow_template_revision_id,
        created_by_user_id=created_by_user_id,
        version_number=version_number,
        planning_status=preview.planning_status.value,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions={key.value: value for key, value in preview.query_versions.items()},
        fingerprint_payload=build_result.fingerprint_payload.model_dump(mode="json"),
        normalized_input=preview.normalized_input.model_dump(mode="json"),
        plan_payload=preview_snapshot,
        preview_fingerprint=preview.preview_fingerprint,
        created_at=created_at,
    )
    await add_workflow_version(session, version)

    scope_ids = await _persist_scopes(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=created_by_user_id,
        scopes=preview.normalized_input.scopes,
        created_at=created_at,
    )
    for ordinal, scope in enumerate(preview.normalized_input.scopes):
        await add_workflow_version_scope(
            session,
            WorkflowVersionScope(
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_version_id=version.id,
                monitoring_scope_id=scope_ids[scope.scope_key],
                ordinal=ordinal,
                created_at=created_at,
            ),
        )
    for ordinal, term in enumerate(preview.query_terms):
        matched_scope_id = scope_ids.get(term.scope_key)
        if matched_scope_id is None:
            raise WorkflowPlanScopeConflictError
        await add_query_term(
            session,
            QueryTerm(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_version_id=version.id,
                ordinal=ordinal,
                term=term.term,
                normalized_term=term.normalized_term,
                origin=term.origin,
                status=term.status,
                reason=term.reason,
                source=term.source,
                score=term.score,
                conflict_codes=list(term.conflict_codes),
                matched_scope_id=matched_scope_id,
                created_at=created_at,
            ),
        )
    return version


def _version_response(
    version: WorkflowVersion,
    preview: WorkflowPlanPreview,
) -> WorkflowVersionResponse:
    validated = validate_workflow_version_snapshot(version)
    if validated.preview != preview:
        raise WorkflowVersionSnapshotInvalidError(
            "workflow_plan_version_fingerprint_mismatch"
        )
    return WorkflowVersionResponse(
        id=version.id,
        workspace_id=version.workspace_id,
        project_id=version.project_id,
        workflow_plan_id=version.workflow_plan_id,
        workflow_template_id=version.workflow_template_id,
        workflow_template_revision_id=version.workflow_template_revision_id,
        created_by_user_id=version.created_by_user_id,
        version_number=version.version_number,
        planning_status=preview.planning_status,
        planner_contract_version=version.planner_contract_version,
        catalog_snapshot_id=version.catalog_snapshot_id,
        policy_version=version.policy_version,
        mode_template_version=version.mode_template_version,
        query_versions=preview.query_versions,
        preview_fingerprint=version.preview_fingerprint,
        editable_input=validated.editable_input,
        preview=validated.preview,
        created_at=version.created_at,
    )


def _plan_response(
    plan: WorkflowPlan,
    version: WorkflowVersion,
    preview: WorkflowPlanPreview,
    *,
    created_at: datetime,
    updated_at: datetime,
) -> WorkflowPlanResponse:
    return WorkflowPlanResponse(
        id=plan.id,
        workspace_id=plan.workspace_id,
        project_id=plan.project_id,
        created_by_user_id=plan.created_by_user_id,
        name=plan.name,
        flow_mode=preview.flow_mode,
        status=cast(WorkflowPlanStatus, plan.status),
        current_version_id=version.id,
        source_plan_id=plan.source_workflow_plan_id,
        source_version_id=plan.source_workflow_version_id,
        workflow_template_id=plan.workflow_template_id,
        workflow_template_revision_id=plan.workflow_template_revision_id,
        current_version_number=version.version_number,
        planning_status=preview.planning_status,
        scope_count=len(preview.normalized_input.scopes),
        query_term_count=len(preview.query_terms),
        created_at=created_at,
        updated_at=updated_at,
    )


async def _persist_save_request(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    response: WorkflowPlanSaveResponse,
    response_status: int,
    created_at: datetime,
) -> None:
    await add_workflow_plan_save_request(
        session,
        WorkflowPlanSaveRequest(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            workflow_plan_id=response.plan.id,
            workflow_version_id=response.version.id,
            outcome=response.outcome,
            response_status=response_status,
            response_payload=response.model_dump(mode="json"),
            created_at=created_at,
        ),
    )


async def _persist_clone_save_request(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    response: WorkflowPlanCloneResponse,
    created_at: datetime,
) -> None:
    await add_workflow_plan_save_request(
        session,
        WorkflowPlanSaveRequest(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            workflow_plan_id=response.plan.id,
            workflow_version_id=response.version.id,
            outcome="created",
            response_status=201,
            response_payload=response.model_dump(mode="json"),
            created_at=created_at,
        ),
    )


async def _create_workflow_plan_attempt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowPlanCreateRequest,
    request_id: str,
    timestamp: datetime,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
) -> WorkflowPlanSaveResponse:
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)

        project = await get_project(session, workspace_id, project_id)
        if project is None:
            raise ProjectNotFoundError
        if project.status != "active":
            raise ProjectNotActiveError

        build_result = build_workflow_plan_result(
            project_id=project_id,
            planning_input=payload.preview_input,
            catalog=await resolve_current_capability_catalog(session),
            generated_at=timestamp,
            request_id=request_id,
        )
        if build_result.preview.preview_fingerprint != payload.expected_preview_fingerprint:
            raise WorkflowPlanPreviewStaleError

        locked_project = await lock_project_for_workflow_plan_save(
            session,
            workspace_id,
            project_id,
        )
        if locked_project is None:
            raise ProjectNotFoundError
        if locked_project.status != "active":
            raise ProjectNotActiveError

        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)

        plan = WorkflowPlan(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            name=payload.name,
            flow_mode=build_result.preview.flow_mode.value,
            status="previewed",
            current_version_id=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
        await add_workflow_plan(session, plan)
        version = await _persist_version_graph(
            session,
            plan=plan,
            build_result=build_result,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            version_number=1,
            created_at=timestamp,
        )
        plan.current_version_id = version.id
        await add_workflow_plan(session, plan)
        await session.refresh(plan, attribute_names=["updated_at"])

        response = WorkflowPlanSaveResponse(
            database_write=True,
            plan_changed=True,
            outcome="created",
            idempotent_replay=False,
            plan=_plan_response(
                plan,
                version,
                build_result.preview,
                created_at=timestamp,
                updated_at=plan.updated_at,
            ),
            version=_version_response(version, build_result.preview),
        )
        await _persist_save_request(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            response=response,
            response_status=201,
            created_at=timestamp,
        )
        return response


async def create_workflow_plan(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowPlanCreateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowPlanSaveResponse:
    idempotency_scope = f"workflow_plan.create:{project_id}"
    idempotency_key_hash = _key_hash(idempotency_key)
    request_hash = _create_request_hash(project_id=project_id, payload=payload)
    timestamp = generated_at or datetime.now(UTC)

    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowPlanSaveResponse:
        return await _create_workflow_plan_attempt(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            payload=payload,
            request_id=request_id,
            timestamp=timestamp,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
        )

    return await _run_with_idempotency_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


async def _recover_clone_idempotency_race(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    error: IntegrityError,
) -> WorkflowPlanCloneResponse:
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_clone_response(completed, request_hash=request_hash)
    raise error


async def _run_clone_with_idempotency_race_recovery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    attempt: Callable[[], Awaitable[WorkflowPlanCloneResponse]],
) -> WorkflowPlanCloneResponse:
    try:
        return await attempt()
    except IntegrityError as exc:
        if not _is_idempotency_unique_violation(exc):
            raise
        return await _recover_clone_idempotency_race(
            session,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            error=exc,
        )


async def _clone_workflow_plan_attempt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowPlanCloneRequest,
    request_id: str,
    timestamp: datetime,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
) -> WorkflowPlanCloneResponse:
    del request_id
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_clone_response(completed, request_hash=request_hash)

        project = await get_project(session, workspace_id, project_id)
        if project is None:
            raise ProjectNotFoundError
        if project.status != "active":
            raise ProjectNotActiveError

        source_plan = await get_workflow_plan(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )
        if source_plan is None:
            raise WorkflowPlanNotFoundError
        source_version = await get_workflow_version(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
            payload.source_version_id,
        )
        if source_version is None:
            raise WorkflowVersionNotFoundError
        source_preview = _preview_from_version(source_version)

        locked_project = await lock_project_for_workflow_plan_save(
            session,
            workspace_id,
            project_id,
        )
        if locked_project is None:
            raise ProjectNotFoundError
        if locked_project.status != "active":
            raise ProjectNotActiveError

        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_clone_response(completed, request_hash=request_hash)

        target_plan = WorkflowPlan(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            name=payload.name,
            flow_mode=source_plan.flow_mode,
            status="previewed",
            current_version_id=None,
            source_workflow_plan_id=source_plan.id,
            source_workflow_version_id=source_version.id,
            workflow_template_id=source_plan.workflow_template_id,
            workflow_template_revision_id=source_plan.workflow_template_revision_id,
            created_at=timestamp,
            updated_at=timestamp,
        )
        await add_workflow_plan(session, target_plan)

        target_version = WorkflowVersion(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_plan_id=target_plan.id,
            workflow_template_id=source_version.workflow_template_id,
            workflow_template_revision_id=source_version.workflow_template_revision_id,
            created_by_user_id=created_by_user_id,
            version_number=1,
            planning_status=source_version.planning_status,
            planner_contract_version=source_version.planner_contract_version,
            catalog_snapshot_id=source_version.catalog_snapshot_id,
            policy_version=source_version.policy_version,
            mode_template_version=source_version.mode_template_version,
            query_versions=dict(source_version.query_versions),
            fingerprint_payload=dict(source_version.fingerprint_payload),
            normalized_input=dict(source_version.normalized_input),
            plan_payload=dict(source_version.plan_payload),
            preview_fingerprint=source_version.preview_fingerprint,
            created_at=timestamp,
        )
        await add_workflow_version(session, target_version)

        source_associations = await list_workflow_version_scopes(
            session,
            workspace_id,
            project_id,
            source_version.id,
        )
        for association in source_associations:
            await add_workflow_version_scope(
                session,
                WorkflowVersionScope(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    workflow_version_id=target_version.id,
                    monitoring_scope_id=association.monitoring_scope_id,
                    ordinal=association.ordinal,
                    created_at=timestamp,
                ),
            )

        source_terms = await list_query_terms_for_version(
            session,
            workspace_id,
            project_id,
            source_version.id,
        )
        for term in source_terms:
            await add_query_term(
                session,
                QueryTerm(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    project_id=project_id,
                    workflow_version_id=target_version.id,
                    ordinal=term.ordinal,
                    term=term.term,
                    normalized_term=term.normalized_term,
                    origin=term.origin,
                    status=term.status,
                    reason=term.reason,
                    source=term.source,
                    score=term.score,
                    conflict_codes=list(term.conflict_codes),
                    matched_scope_id=term.matched_scope_id,
                    created_at=timestamp,
                ),
            )

        target_plan.current_version_id = target_version.id
        await add_workflow_plan(session, target_plan)
        await session.refresh(target_plan, attribute_names=["updated_at"])

        response = WorkflowPlanCloneResponse(
            database_write=True,
            plan_changed=True,
            outcome="created",
            idempotent_replay=False,
            source_plan_id=source_plan.id,
            source_version_id=source_version.id,
            plan=_plan_response(
                target_plan,
                target_version,
                source_preview,
                created_at=timestamp,
                updated_at=target_plan.updated_at,
            ),
            version=_version_response(target_version, source_preview),
        )
        await _persist_clone_save_request(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            response=response,
            created_at=timestamp,
        )
        return response


async def clone_workflow_plan(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowPlanCloneRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowPlanCloneResponse:
    idempotency_scope = f"workflow_plan.clone:{project_id}:{workflow_plan_id}"
    idempotency_key_hash = _key_hash(idempotency_key)
    request_hash = _clone_request_hash(
        project_id=project_id,
        workflow_plan_id=workflow_plan_id,
        payload=payload,
    )
    timestamp = generated_at or datetime.now(UTC)

    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowPlanCloneResponse:
        return await _clone_workflow_plan_attempt(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_plan_id=workflow_plan_id,
            created_by_user_id=created_by_user_id,
            payload=payload,
            request_id=request_id,
            timestamp=timestamp,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
        )

    return await _run_clone_with_idempotency_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


async def transition_workflow_plan_status(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowPlanTransitionRequest,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowPlanTransitionResponse:
    del created_by_user_id, request_id
    timestamp = generated_at or datetime.now(UTC)
    await _prepare_service_transaction(session)

    async with session.begin():
        project = await lock_project_for_workflow_plan_save(
            session,
            workspace_id,
            project_id,
        )
        if project is None:
            raise ProjectNotFoundError
        if project.status != "active":
            raise ProjectNotActiveError

        plan = await get_workflow_plan_for_update(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )
        if plan is None:
            raise WorkflowPlanNotFoundError

        current_status = cast(WorkflowPlanStatus, plan.status)
        if current_status != payload.expected_status:
            raise WorkflowPlanStatusConflictError
        try:
            target_status = _transition_plan_status(
                current_status,
                payload.to_status,
            )
        except WorkflowPlanTransitionError as exc:
            raise WorkflowPlanInvalidTransitionError from exc

        current_version = await _get_current_workflow_version_for_read(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            plan=plan,
        )
        preview = _preview_from_version(current_version)
        plan_created_at = plan.created_at
        if target_status == current_status:
            response = WorkflowPlanTransitionResponse(
                database_write=False,
                plan_changed=False,
                from_status=current_status,
                to_status=target_status,
                reason=payload.reason,
                plan=_plan_response(
                    plan,
                    current_version,
                    preview,
                    created_at=plan_created_at,
                    updated_at=plan.updated_at,
                ),
            )
            return response

        plan.status = target_status
        plan.updated_at = timestamp
        await add_workflow_plan(session, plan)
        await session.refresh(plan, attribute_names=["updated_at"])
        return WorkflowPlanTransitionResponse(
            database_write=True,
            plan_changed=True,
            from_status=current_status,
            to_status=target_status,
            reason=payload.reason,
            plan=_plan_response(
                plan,
                current_version,
                preview,
                created_at=plan_created_at,
                updated_at=plan.updated_at,
            ),
        )


async def _create_workflow_version_attempt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowVersionCreateRequest,
    request_id: str,
    timestamp: datetime,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
) -> WorkflowPlanSaveResponse:
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)

        project = await get_project(session, workspace_id, project_id)
        if project is None:
            raise ProjectNotFoundError
        if project.status != "active":
            raise ProjectNotActiveError

        plan = await get_workflow_plan(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )
        if plan is None:
            raise WorkflowPlanNotFoundError

        build_result = build_workflow_plan_result(
            project_id=project_id,
            planning_input=payload.preview_input,
            catalog=await resolve_current_capability_catalog(session),
            generated_at=timestamp,
            request_id=request_id,
        )
        if build_result.preview.preview_fingerprint != payload.expected_preview_fingerprint:
            raise WorkflowPlanPreviewStaleError

        locked_project = await lock_project_for_workflow_plan_save(
            session,
            workspace_id,
            project_id,
        )
        if locked_project is None:
            raise ProjectNotFoundError
        if locked_project.status != "active":
            raise ProjectNotActiveError

        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)

        locked_plan = await get_workflow_plan_for_update(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )
        if locked_plan is None:
            raise WorkflowPlanNotFoundError
        if locked_plan.flow_mode != build_result.preview.flow_mode.value:
            raise WorkflowPlanFlowModeConflictError
        if locked_plan.current_version_id != payload.expected_current_version_id:
            raise WorkflowPlanVersionConflictError

        current_version = await get_workflow_version(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
            payload.expected_current_version_id,
        )
        if current_version is None:
            raise WorkflowPlanVersionConflictError
        current_preview = WorkflowPlanPreview.model_validate(current_version.plan_payload)
        plan_created_at = locked_plan.created_at
        plan_updated_at = locked_plan.updated_at

        if current_version.preview_fingerprint == build_result.preview.preview_fingerprint:
            response = WorkflowPlanSaveResponse(
                database_write=True,
                plan_changed=False,
                outcome="semantic_no_op",
                idempotent_replay=False,
                plan=_plan_response(
                    locked_plan,
                    current_version,
                    current_preview,
                    created_at=plan_created_at,
                    updated_at=plan_updated_at,
                ),
                version=_version_response(current_version, current_preview),
            )
            await _persist_save_request(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=idempotency_scope,
                idempotency_key_hash=idempotency_key_hash,
                request_hash=request_hash,
                response=response,
                response_status=200,
                created_at=timestamp,
            )
            return response

        version = await _persist_version_graph(
            session,
            plan=locked_plan,
            build_result=build_result,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            version_number=current_version.version_number + 1,
            created_at=timestamp,
        )
        locked_plan.current_version_id = version.id
        locked_plan.updated_at = timestamp
        await add_workflow_plan(session, locked_plan)
        await session.refresh(locked_plan, attribute_names=["updated_at"])
        response = WorkflowPlanSaveResponse(
            database_write=True,
            plan_changed=True,
            outcome="created",
            idempotent_replay=False,
            plan=_plan_response(
                locked_plan,
                version,
                build_result.preview,
                created_at=plan_created_at,
                updated_at=locked_plan.updated_at,
            ),
            version=_version_response(version, build_result.preview),
        )
        await _persist_save_request(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            response=response,
            response_status=201,
            created_at=timestamp,
        )
        return response


async def create_workflow_version(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowVersionCreateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowPlanSaveResponse:
    idempotency_scope = f"workflow_plan.create_version:{project_id}:{workflow_plan_id}"
    idempotency_key_hash = _key_hash(idempotency_key)
    request_hash = _version_request_hash(
        project_id=project_id,
        workflow_plan_id=workflow_plan_id,
        payload=payload,
    )
    timestamp = generated_at or datetime.now(UTC)

    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowPlanSaveResponse:
        return await _create_workflow_version_attempt(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_plan_id=workflow_plan_id,
            created_by_user_id=created_by_user_id,
            payload=payload,
            request_id=request_id,
            timestamp=timestamp,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
        )

    return await _run_with_idempotency_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


def _project_read_status(project: Project) -> ProjectStatus:
    return cast(ProjectStatus, project.status)


async def _get_project_for_workflow_plan_read(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    if session.new or session.dirty or session.deleted:
        raise WorkflowPlanPersistenceTransactionStateError
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise ProjectNotFoundError
    return project


async def _get_workflow_plan_for_read(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> WorkflowPlan:
    plan = await get_workflow_plan(session, workspace_id, project_id, plan_id)
    if plan is None:
        raise WorkflowPlanNotFoundError
    return plan


async def _get_current_workflow_version_for_read(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan: WorkflowPlan,
) -> WorkflowVersion:
    if plan.current_version_id is None:
        raise WorkflowVersionNotFoundError
    version = await get_workflow_version(
        session,
        workspace_id,
        project_id,
        plan.id,
        plan.current_version_id,
    )
    if version is None:
        raise WorkflowVersionNotFoundError
    return version


def _preview_from_version(version: WorkflowVersion) -> WorkflowPlanPreview:
    return validate_workflow_version_snapshot(version).preview


def _version_summary_response(
    version: WorkflowVersion,
) -> WorkflowVersionSummaryResponse:
    return WorkflowVersionSummaryResponse.model_validate(version)


def _version_read_response(
    version: WorkflowVersion,
) -> WorkflowVersionResponse:
    return _version_response(version, _preview_from_version(version))


def _plan_read_response(
    plan: WorkflowPlan,
    current_version: WorkflowVersion,
) -> WorkflowPlanResponse:
    return _plan_response(
        plan,
        current_version,
        _preview_from_version(current_version),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


async def list_workflow_plans_for_project(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowPlanListResponse:
    project = await _get_project_for_workflow_plan_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    plans = await list_workflow_plans(
        session,
        workspace_id,
        project_id,
        limit=limit,
        offset=offset,
    )
    items: list[WorkflowPlanResponse] = []
    for plan in plans:
        current_version = await _get_current_workflow_version_for_read(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            plan=plan,
        )
        items.append(_plan_read_response(plan, current_version))
    total = await count_workflow_plans(session, workspace_id, project_id)
    return WorkflowPlanListResponse(
        project_status=_project_read_status(project),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_workflow_plan_detail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> WorkflowPlanDetailResponse:
    project = await _get_project_for_workflow_plan_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    plan = await _get_workflow_plan_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
    )
    current_version = await _get_current_workflow_version_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan=plan,
    )
    return WorkflowPlanDetailResponse(
        project_status=_project_read_status(project),
        plan=_plan_read_response(plan, current_version),
        current_version=_version_read_response(current_version),
    )


async def list_workflow_plan_versions(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowVersionListResponse:
    project = await _get_project_for_workflow_plan_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    await _get_workflow_plan_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
    )
    versions = await list_workflow_versions(
        session,
        workspace_id,
        project_id,
        plan_id,
        limit=limit,
        offset=offset,
    )
    total = await count_workflow_versions(
        session,
        workspace_id,
        project_id,
        plan_id,
    )
    return WorkflowVersionListResponse(
        project_status=_project_read_status(project),
        items=[_version_summary_response(version) for version in versions],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_workflow_version_detail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
) -> WorkflowVersionDetailResponse:
    project = await _get_project_for_workflow_plan_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    plan = await _get_workflow_plan_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
    )
    version = await get_workflow_version(
        session,
        workspace_id,
        project_id,
        plan_id,
        version_id,
    )
    if version is None:
        raise WorkflowVersionNotFoundError
    current_version = await _get_current_workflow_version_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan=plan,
    )
    return WorkflowVersionDetailResponse(
        project_status=_project_read_status(project),
        plan=_plan_read_response(plan, current_version),
        version=_version_read_response(version),
    )


async def compare_workflow_plan_versions(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    base_version_id: uuid.UUID,
    target_version_id: uuid.UUID,
) -> WorkflowPlanVersionCompareResponse:
    project = await _get_project_for_workflow_plan_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    plan = await _get_workflow_plan_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
    )
    base_version = await get_workflow_version(
        session,
        workspace_id,
        project_id,
        plan_id,
        base_version_id,
    )
    if base_version is None:
        raise WorkflowVersionNotFoundError
    if target_version_id == base_version_id:
        target_version = base_version
    else:
        stored_target_version = await get_workflow_version(
            session,
            workspace_id,
            project_id,
            plan_id,
            target_version_id,
        )
        if stored_target_version is None:
            raise WorkflowVersionNotFoundError
        target_version = stored_target_version

    base_preview = _preview_from_version(base_version)
    target_preview = _preview_from_version(target_version)
    current_version = await _get_current_workflow_version_for_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan=plan,
    )
    return WorkflowPlanVersionCompareResponse(
        project_status=_project_read_status(project),
        plan=_plan_read_response(plan, current_version),
        base_version=_version_summary_response(base_version),
        target_version=_version_summary_response(target_version),
        same_version=base_version.id == target_version.id,
        sections=compare_workflow_plan_previews(base_preview, target_preview),
    )


async def list_monitoring_scopes_for_project(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> MonitoringScopeListResponse:
    project = await _get_project_for_workflow_plan_read(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    scopes = await list_monitoring_scopes(
        session,
        workspace_id,
        project_id,
        limit=limit,
        offset=offset,
    )
    total = await count_monitoring_scopes(session, workspace_id, project_id)
    return MonitoringScopeListResponse(
        project_status=_project_read_status(project),
        items=[MonitoringScopeResponse.model_validate(scope) for scope in scopes],
        total=total,
        limit=limit,
        offset=offset,
    )


__all__ = [
    "clone_workflow_plan",
    "compare_workflow_plan_versions",
    "create_workflow_plan",
    "create_workflow_version",
    "get_workflow_plan_detail",
    "get_workflow_version_detail",
    "list_monitoring_scopes_for_project",
    "list_workflow_plan_versions",
    "list_workflow_plans_for_project",
]

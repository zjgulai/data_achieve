from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_plan import WorkflowPlanSaveRequest
from data_intelligence_hub.models.workflow_scope_template import MonitoringScopeTemplate
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workflow_plans import (
    get_workflow_plan,
    get_workflow_plan_save_request,
    lock_project_for_workflow_plan_save,
)
from data_intelligence_hub.repositories.workflow_scope_templates import (
    add_monitoring_scope_template,
    add_scope_template_copy_request,
    get_monitoring_scope,
    get_workflow_version_by_id,
    get_workflow_version_scope,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeTemplateCopyRequest,
    MonitoringScopeTemplateCopyResponse,
    MonitoringScopeTemplateResponse,
    normalize_idempotency_key,
)
from data_intelligence_hub.services.exceptions import (
    MonitoringScopeNotFoundError,
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlanPersistenceTransactionStateError,
    WorkflowVersionNotFoundError,
)
from data_intelligence_hub.services.workflow_execution.integrity import (
    validate_workflow_version_snapshot,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id


def _key_hash(idempotency_key: str) -> str:
    normalized = normalize_idempotency_key(idempotency_key)
    return sha256_id(cast(JsonValue, normalized))


def _request_hash(
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    payload: MonitoringScopeTemplateCopyRequest,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "method": "POST",
                "route": {
                    "project_id": str(project_id),
                    "scope_id": str(scope_id),
                    "resource": "monitoring_scope_template_copy",
                },
                "body": payload.model_dump(mode="json"),
            },
        )
    )


def _replay(
    request: WorkflowPlanSaveRequest,
    *,
    request_hash: str,
) -> MonitoringScopeTemplateCopyResponse:
    if request.request_hash != request_hash:
        raise WorkflowPlanIdempotencyConflictError
    original = MonitoringScopeTemplateCopyResponse.model_validate(request.response_payload)
    return original.model_copy(
        update={"database_write": False, "idempotent_replay": True},
        deep=True,
    )


def _is_idempotency_unique_violation(exc: IntegrityError) -> bool:
    origin = exc.orig
    if origin is None:
        return False
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    constraint_name = getattr(origin, "constraint_name", None)
    if constraint_name is None:
        diagnostic = getattr(origin, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
    return sqlstate == "23505" and constraint_name == "uq_workflow_plan_save_requests_idempotency"


def _template_response(template: MonitoringScopeTemplate) -> MonitoringScopeTemplateResponse:
    return MonitoringScopeTemplateResponse(
        id=template.id,
        workspace_id=template.workspace_id,
        project_id=template.project_id,
        created_by_user_id=template.created_by_user_id,
        source_scope_id=template.source_scope_id,
        source_plan_id=template.source_workflow_plan_id,
        source_version_id=template.source_workflow_version_id,
        scope_key=template.scope_key,
        scope_type=template.scope_type,
        canonical_term=template.canonical_term,
        aliases=list(template.aliases),
        include_terms=list(template.include_terms),
        exclude_terms=list(template.exclude_terms),
        official_accounts=list(template.official_accounts),
        seed_urls=list(template.seed_urls),
        effective_languages=list(template.effective_languages),
        effective_regions=list(template.effective_regions),
        effective_platforms=list(template.effective_platforms),
        match_mode=template.match_mode,
        created_at=template.created_at,
    )


async def _prepare(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise WorkflowPlanPersistenceTransactionStateError
    if session.in_transaction():
        await session.rollback()


async def _recover_race(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    error: IntegrityError,
) -> MonitoringScopeTemplateCopyResponse:
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay(completed, request_hash=request_hash)
    raise error


async def _run_with_race_recovery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    attempt: Callable[[], Awaitable[MonitoringScopeTemplateCopyResponse]],
) -> MonitoringScopeTemplateCopyResponse:
    try:
        return await attempt()
    except IntegrityError as exc:
        if not _is_idempotency_unique_violation(exc):
            raise
        return await _recover_race(
            session,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            error=exc,
        )


async def _copy_attempt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: MonitoringScopeTemplateCopyRequest,
    timestamp: datetime,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
) -> MonitoringScopeTemplateCopyResponse:
    async with session.begin():
        completed = await get_workflow_plan_save_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay(completed, request_hash=request_hash)

        project = await get_project(session, workspace_id, project_id)
        if project is None:
            raise ProjectNotFoundError
        if project.status != "active":
            raise ProjectNotActiveError

        source_scope = await get_monitoring_scope(
            session,
            workspace_id,
            project_id,
            scope_id,
        )
        source_version = await get_workflow_version_by_id(
            session,
            workspace_id,
            project_id,
            payload.source_version_id,
        )
        if source_scope is None or source_version is None:
            raise MonitoringScopeNotFoundError
        if (
            await get_workflow_version_scope(
                session,
                workspace_id,
                project_id,
                source_version.id,
                source_scope.id,
            )
            is None
        ):
            raise MonitoringScopeNotFoundError
        source_plan = await get_workflow_plan(
            session,
            workspace_id,
            project_id,
            source_version.workflow_plan_id,
        )
        if source_plan is None:
            raise WorkflowVersionNotFoundError
        validate_workflow_version_snapshot(source_version)

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
            return _replay(completed, request_hash=request_hash)

        template = MonitoringScopeTemplate(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            source_scope_id=source_scope.id,
            source_workflow_plan_id=source_plan.id,
            source_workflow_version_id=source_version.id,
            scope_key=source_scope.scope_key,
            scope_type=source_scope.scope_type,
            canonical_term=source_scope.canonical_term,
            aliases=list(source_scope.aliases),
            include_terms=list(source_scope.include_terms),
            exclude_terms=list(source_scope.exclude_terms),
            official_accounts=list(source_scope.official_accounts),
            seed_urls=list(source_scope.seed_urls),
            effective_languages=list(source_scope.effective_languages),
            effective_regions=list(source_scope.effective_regions),
            effective_platforms=list(source_scope.effective_platforms),
            match_mode=source_scope.match_mode,
            created_at=timestamp,
        )
        await add_monitoring_scope_template(session, template)
        response = MonitoringScopeTemplateCopyResponse(
            database_write=True,
            idempotent_replay=False,
            template=_template_response(template),
        )
        await add_scope_template_copy_request(
            session,
            WorkflowPlanSaveRequest(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=idempotency_scope,
                idempotency_key_hash=idempotency_key_hash,
                request_hash=request_hash,
                workflow_plan_id=source_plan.id,
                workflow_version_id=source_version.id,
                outcome="created",
                response_status=201,
                response_payload=response.model_dump(mode="json"),
                created_at=timestamp,
            ),
        )
        return response


async def copy_monitoring_scope_template(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: MonitoringScopeTemplateCopyRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> MonitoringScopeTemplateCopyResponse:
    del request_id
    idempotency_scope = f"monitoring_scope_template.copy:{project_id}:{scope_id}"
    idempotency_key_hash = _key_hash(idempotency_key)
    request_hash = _request_hash(
        project_id=project_id,
        scope_id=scope_id,
        payload=payload,
    )
    timestamp = generated_at or datetime.now(UTC)
    await _prepare(session)

    async def attempt() -> MonitoringScopeTemplateCopyResponse:
        return await _copy_attempt(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            scope_id=scope_id,
            created_by_user_id=created_by_user_id,
            payload=payload,
            timestamp=timestamp,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
        )

    return await _run_with_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=idempotency_scope,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


__all__ = ["copy_monitoring_scope_template"]

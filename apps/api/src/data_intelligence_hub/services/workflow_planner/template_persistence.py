from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import JsonValue, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_plan import WorkflowPlan
from data_intelligence_hub.models.workflow_template import (
    WorkflowTemplate,
    WorkflowTemplateMutationRequest,
    WorkflowTemplateRevision,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workflow_plans import (
    add_workflow_plan,
    get_workflow_plan_save_request,
)
from data_intelligence_hub.repositories.workflow_templates import (
    add_workflow_template,
    add_workflow_template_mutation_request,
    add_workflow_template_revision,
    count_workflow_template_revisions,
    count_workflow_templates,
    get_workflow_template,
    get_workflow_template_by_key,
    get_workflow_template_for_update,
    get_workflow_template_mutation_request,
    get_workflow_template_revision,
    list_workflow_template_revisions,
    list_workflow_templates,
    lock_project_for_workflow_template_mutation,
)
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanSaveResponse,
)
from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.schemas.workflow_template_persistence import (
    WorkflowTemplateCreateRequest,
    WorkflowTemplateDetailResponse,
    WorkflowTemplateInstantiateRequest,
    WorkflowTemplateListResponse,
    WorkflowTemplateMetadataUpdateRequest,
    WorkflowTemplateMutationResponse,
    WorkflowTemplateResponse,
    WorkflowTemplateRevisionCreateRequest,
    WorkflowTemplateRevisionListResponse,
    WorkflowTemplateRevisionResponse,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.exceptions import (
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlanPersistenceTransactionStateError,
    WorkflowTemplateKeyConflictError,
    WorkflowTemplateNotEditableError,
    WorkflowTemplateNotFoundError,
    WorkflowTemplateRevisionConflictError,
    WorkflowTemplateRevisionInvalidError,
    WorkflowTemplateRevisionNotFoundError,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.services.workflow_planner.persistence import (
    _key_hash,
    _persist_save_request,
    _persist_version_graph,
    _plan_response,
    _prepare_service_transaction,
    _replay_response,
    _run_with_idempotency_race_recovery,
    _version_response,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)


def _project_status(project: Any) -> ProjectStatus:
    return cast(ProjectStatus, project.status)


def _definition_json(definition: PlanningInput) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], definition.model_dump(mode="json"))


def _definition_fingerprint(definition: PlanningInput) -> str:
    return sha256_id(cast(JsonValue, _definition_json(definition)))


def _template_revision_response(
    revision: WorkflowTemplateRevision,
) -> WorkflowTemplateRevisionResponse:
    return WorkflowTemplateRevisionResponse.model_validate(revision)


def _template_response(
    template: WorkflowTemplate,
    revision: WorkflowTemplateRevision | None,
) -> WorkflowTemplateResponse:
    return WorkflowTemplateResponse(
        id=template.id,
        workspace_id=template.workspace_id,
        project_id=template.project_id,
        created_by_user_id=template.created_by_user_id,
        name=template.name,
        template_key=template.template_key,
        description=template.description,
        status=cast(Any, template.status),
        current_revision_id=template.current_revision_id,
        current_revision=(
            _template_revision_response(revision) if revision is not None else None
        ),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _ensure_project_active(project: Any) -> None:
    if project.status != "active":
        raise ProjectNotActiveError


def _ensure_template_editable(template: WorkflowTemplate) -> None:
    if template.status != "draft":
        raise WorkflowTemplateNotEditableError


def _template_request_hash(
    *,
    project_id: uuid.UUID,
    resource: str,
    payload: Any,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "method": "WRITE",
                "route": {"project_id": str(project_id), "resource": resource},
                "body": cast(Any, payload.model_dump(mode="json")),
            },
        )
    )


def _replay_template_mutation(
    request: WorkflowTemplateMutationRequest,
    *,
    request_hash: str,
) -> WorkflowTemplateMutationResponse:
    if request.request_hash != request_hash:
        raise WorkflowPlanIdempotencyConflictError
    response = WorkflowTemplateMutationResponse.model_validate(request.response_payload)
    return response.model_copy(
        update={"database_write": False, "idempotent_replay": True},
        deep=True,
    )


def _is_template_idempotency_violation(exc: IntegrityError) -> bool:
    origin = exc.orig
    if origin is None:
        return False
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    diagnostic = getattr(origin, "diag", None)
    constraint_name = getattr(origin, "constraint_name", None) or getattr(
        diagnostic,
        "constraint_name",
        None,
    )
    return (
        sqlstate == "23505"
        and constraint_name == "uq_workflow_template_mutation_requests_idempotency"
    )


async def _recover_template_idempotency_race(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    error: IntegrityError,
) -> WorkflowTemplateMutationResponse:
    async with session.begin():
        completed = await get_workflow_template_mutation_request(
            session,
            workspace_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_template_mutation(completed, request_hash=request_hash)
    raise error


async def _run_template_mutation_with_race_recovery(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    attempt: Callable[[], Awaitable[WorkflowTemplateMutationResponse]],
) -> WorkflowTemplateMutationResponse:
    try:
        return await attempt()
    except IntegrityError as exc:
        if not _is_template_idempotency_violation(exc):
            raise
        return await _recover_template_idempotency_race(
            session,
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            error=exc,
        )


async def _persist_template_mutation(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    response: WorkflowTemplateMutationResponse,
    operation: str,
    response_status: int,
    created_at: datetime,
) -> None:
    await add_workflow_template_mutation_request(
        session,
        WorkflowTemplateMutationRequest(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            workflow_template_id=response.template.id,
            workflow_template_revision_id=(
                response.revision.id if response.revision is not None else None
            ),
            operation=operation,
            outcome=response.outcome,
            response_status=response_status,
            response_payload=response.model_dump(mode="json"),
            created_at=created_at,
        ),
    )


async def create_workflow_template(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowTemplateCreateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowTemplateMutationResponse:
    del request_id
    scope = f"workflow_template.create:{project_id}"
    key_hash = _key_hash(idempotency_key)
    request_hash = _template_request_hash(
        project_id=project_id,
        resource="workflow_templates",
        payload=payload,
    )
    timestamp = generated_at or datetime.now(UTC)
    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowTemplateMutationResponse:
        async with session.begin():
            completed = await get_workflow_template_mutation_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed is not None:
                return _replay_template_mutation(completed, request_hash=request_hash)
            project = await lock_project_for_workflow_template_mutation(
                session,
                workspace_id,
                project_id,
            )
            if project is None:
                raise ProjectNotFoundError
            _ensure_project_active(project)
            completed = await get_workflow_template_mutation_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed is not None:
                return _replay_template_mutation(completed, request_hash=request_hash)
            if await get_workflow_template_by_key(
                session,
                workspace_id,
                project_id,
                payload.template_key,
            ) is not None:
                raise WorkflowTemplateKeyConflictError

            template = WorkflowTemplate(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                name=payload.name,
                template_key=payload.template_key,
                description=payload.description,
                status="draft",
                current_revision_id=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
            await add_workflow_template(session, template)
            revision = WorkflowTemplateRevision(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_template_id=template.id,
                created_by_user_id=created_by_user_id,
                revision_number=1,
                definition=_definition_json(payload.definition),
                definition_fingerprint=_definition_fingerprint(payload.definition),
                created_at=timestamp,
            )
            await add_workflow_template_revision(session, revision)
            template.current_revision_id = revision.id
            template.updated_at = timestamp
            await add_workflow_template(session, template)
            await session.refresh(template, attribute_names=["updated_at"])
            response = WorkflowTemplateMutationResponse(
                database_write=True,
                idempotent_replay=False,
                outcome="created",
                template=_template_response(template, revision),
                revision=_template_revision_response(revision),
            )
            await _persist_template_mutation(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                response=response,
                operation="create",
                response_status=201,
                created_at=timestamp,
            )
            return response

    return await _run_template_mutation_with_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=scope,
        idempotency_key_hash=key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


async def _load_template_and_current_revision(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    lock: bool = False,
) -> tuple[WorkflowTemplate, WorkflowTemplateRevision]:
    template = (
        await get_workflow_template_for_update(
            session,
            workspace_id,
            project_id,
            template_id,
        )
        if lock
        else await get_workflow_template(session, workspace_id, project_id, template_id)
    )
    if template is None:
        raise WorkflowTemplateNotFoundError
    if template.current_revision_id is None:
        raise WorkflowTemplateRevisionInvalidError
    revision = await get_workflow_template_revision(
        session,
        workspace_id,
        project_id,
        template.id,
        template.current_revision_id,
    )
    if revision is None:
        raise WorkflowTemplateRevisionInvalidError
    return template, revision


async def append_workflow_template_revision(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowTemplateRevisionCreateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowTemplateMutationResponse:
    del request_id
    scope = f"workflow_template.revision:{project_id}:{workflow_template_id}"
    key_hash = _key_hash(idempotency_key)
    request_hash = _template_request_hash(
        project_id=project_id,
        resource=f"workflow_templates/{workflow_template_id}/revisions",
        payload=payload,
    )
    timestamp = generated_at or datetime.now(UTC)
    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowTemplateMutationResponse:
        async with session.begin():
            completed = await get_workflow_template_mutation_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed is not None:
                return _replay_template_mutation(completed, request_hash=request_hash)
            project = await lock_project_for_workflow_template_mutation(
                session,
                workspace_id,
                project_id,
            )
            if project is None:
                raise ProjectNotFoundError
            _ensure_project_active(project)
            completed = await get_workflow_template_mutation_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed is not None:
                return _replay_template_mutation(completed, request_hash=request_hash)
            template, current = await _load_template_and_current_revision(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                template_id=workflow_template_id,
                lock=True,
            )
            _ensure_template_editable(template)
            if current.id != payload.expected_revision_id:
                raise WorkflowTemplateRevisionConflictError
            max_number = await session.scalar(
                select(func.max(WorkflowTemplateRevision.revision_number)).where(
                    WorkflowTemplateRevision.workspace_id == workspace_id,
                    WorkflowTemplateRevision.project_id == project_id,
                    WorkflowTemplateRevision.workflow_template_id == template.id,
                )
            )
            revision = WorkflowTemplateRevision(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_template_id=template.id,
                created_by_user_id=created_by_user_id,
                revision_number=int(max_number or 0) + 1,
                definition=_definition_json(payload.definition),
                definition_fingerprint=_definition_fingerprint(payload.definition),
                created_at=timestamp,
            )
            await add_workflow_template_revision(session, revision)
            template.current_revision_id = revision.id
            template.updated_at = timestamp
            await add_workflow_template(session, template)
            await session.refresh(template, attribute_names=["updated_at"])
            response = WorkflowTemplateMutationResponse(
                database_write=True,
                idempotent_replay=False,
                outcome="updated",
                template=_template_response(template, revision),
                revision=_template_revision_response(revision),
            )
            await _persist_template_mutation(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                response=response,
                operation="revision",
                response_status=201,
                created_at=timestamp,
            )
            return response

    return await _run_template_mutation_with_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=scope,
        idempotency_key_hash=key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


async def update_workflow_template_metadata(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowTemplateMetadataUpdateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowTemplateMutationResponse:
    del request_id
    scope = f"workflow_template.metadata:{project_id}:{workflow_template_id}"
    key_hash = _key_hash(idempotency_key)
    request_hash = _template_request_hash(
        project_id=project_id,
        resource=f"workflow_templates/{workflow_template_id}",
        payload=payload,
    )
    timestamp = generated_at or datetime.now(UTC)
    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowTemplateMutationResponse:
        async with session.begin():
            completed = await get_workflow_template_mutation_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed is not None:
                return _replay_template_mutation(completed, request_hash=request_hash)
            project = await lock_project_for_workflow_template_mutation(
                session,
                workspace_id,
                project_id,
            )
            if project is None:
                raise ProjectNotFoundError
            _ensure_project_active(project)
            completed = await get_workflow_template_mutation_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed is not None:
                return _replay_template_mutation(completed, request_hash=request_hash)
            template, current = await _load_template_and_current_revision(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                template_id=workflow_template_id,
                lock=True,
            )
            _ensure_template_editable(template)
            if current.id != payload.expected_revision_id:
                raise WorkflowTemplateRevisionConflictError
            if payload.name is not None:
                template.name = payload.name
            if "description" in payload.model_fields_set:
                template.description = payload.description
            template.updated_at = timestamp
            await add_workflow_template(session, template)
            await session.refresh(template, attribute_names=["updated_at"])
            response = WorkflowTemplateMutationResponse(
                database_write=True,
                idempotent_replay=False,
                outcome="updated",
                template=_template_response(template, current),
            )
            await _persist_template_mutation(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                response=response,
                operation="metadata",
                response_status=200,
                created_at=timestamp,
            )
            return response

    return await _run_template_mutation_with_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=scope,
        idempotency_key_hash=key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


async def list_workflow_templates_for_project(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowTemplateListResponse:
    if session.new or session.dirty or session.deleted:
        raise WorkflowPlanPersistenceTransactionStateError
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise ProjectNotFoundError
    templates = await list_workflow_templates(
        session,
        workspace_id,
        project_id,
        limit=limit,
        offset=offset,
    )
    items: list[WorkflowTemplateResponse] = []
    for template in templates:
        current = None
        if template.current_revision_id is not None:
            current = await get_workflow_template_revision(
                session,
                workspace_id,
                project_id,
                template.id,
                template.current_revision_id,
            )
        items.append(_template_response(template, current))
    return WorkflowTemplateListResponse(
        project_status=_project_status(project),
        items=items,
        total=await count_workflow_templates(session, workspace_id, project_id),
        limit=limit,
        offset=offset,
    )


async def get_workflow_template_detail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
) -> WorkflowTemplateDetailResponse:
    if session.new or session.dirty or session.deleted:
        raise WorkflowPlanPersistenceTransactionStateError
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise ProjectNotFoundError
    template, current = await _load_template_and_current_revision(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        template_id=workflow_template_id,
    )
    return WorkflowTemplateDetailResponse(
        project_status=_project_status(project),
        template=_template_response(template, current),
        current_revision=_template_revision_response(current),
    )


async def list_workflow_template_revisions_for_template(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowTemplateRevisionListResponse:
    if session.new or session.dirty or session.deleted:
        raise WorkflowPlanPersistenceTransactionStateError
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise ProjectNotFoundError
    template, current = await _load_template_and_current_revision(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        template_id=workflow_template_id,
    )
    revisions = await list_workflow_template_revisions(
        session,
        workspace_id,
        project_id,
        workflow_template_id,
        limit=limit,
        offset=offset,
    )
    return WorkflowTemplateRevisionListResponse(
        project_status=_project_status(project),
        template=_template_response(template, current),
        items=[_template_revision_response(item) for item in revisions],
        total=await count_workflow_template_revisions(
            session,
            workspace_id,
            project_id,
            workflow_template_id,
        ),
        limit=limit,
        offset=offset,
    )


async def instantiate_workflow_plan_from_template(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_template_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowTemplateInstantiateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowPlanSaveResponse:
    scope = f"workflow_template.instantiate:{project_id}:{workflow_template_id}"
    key_hash = _key_hash(idempotency_key)
    timestamp = generated_at or datetime.now(UTC)
    request_hash = sha256_id(
        cast(
            JsonValue,
            {
                "method": "POST",
                "route": {
                    "project_id": str(project_id),
                    "template_id": str(workflow_template_id),
                    "resource": "workflow_template_instantiate",
                },
                "body": payload.model_dump(mode="json"),
            },
        )
    )
    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowPlanSaveResponse:
        async with session.begin():
            completed_plan = await get_workflow_plan_save_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed_plan is not None:
                return _replay_response(completed_plan, request_hash=request_hash)

            project = await lock_project_for_workflow_template_mutation(
                session,
                workspace_id,
                project_id,
            )
            if project is None:
                raise ProjectNotFoundError
            _ensure_project_active(project)
            template = await get_workflow_template_for_update(
                session,
                workspace_id,
                project_id,
                workflow_template_id,
            )
            if template is None:
                raise WorkflowTemplateNotFoundError
            if template.status == "archived":
                raise WorkflowTemplateNotEditableError
            revision = await get_workflow_template_revision(
                session,
                workspace_id,
                project_id,
                workflow_template_id,
                payload.revision_id,
            )
            if revision is None:
                raise WorkflowTemplateRevisionNotFoundError
            try:
                definition = PlanningInput.model_validate(revision.definition)
            except ValidationError as exc:
                raise WorkflowTemplateRevisionInvalidError from exc
            build_result = build_workflow_plan_result(
                project_id=project_id,
                planning_input=definition,
                catalog=await resolve_current_capability_catalog(session),
                generated_at=timestamp,
                request_id=request_id,
            )
            completed_plan = await get_workflow_plan_save_request(
                session,
                workspace_id,
                created_by_user_id,
                scope,
                key_hash,
            )
            if completed_plan is not None:
                return _replay_response(completed_plan, request_hash=request_hash)

            plan = WorkflowPlan(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                name=payload.name,
                flow_mode=build_result.preview.flow_mode.value,
                status="previewed",
                current_version_id=None,
                workflow_template_id=template.id,
                workflow_template_revision_id=revision.id,
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
                idempotency_scope=scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                response=response,
                response_status=201,
                created_at=timestamp,
            )
            return response

    # The immutable revision id is part of the route hash, so a replay with a
    # different revision or plan name is rejected by the existing Plan ledger.
    return await _run_with_idempotency_race_recovery(
        session,
        workspace_id=workspace_id,
        created_by_user_id=created_by_user_id,
        idempotency_scope=scope,
        idempotency_key_hash=key_hash,
        request_hash=request_hash,
        attempt=attempt,
    )


__all__ = [
    "append_workflow_template_revision",
    "create_workflow_template",
    "get_workflow_template_detail",
    "instantiate_workflow_plan_from_template",
    "list_workflow_template_revisions_for_template",
    "list_workflow_templates_for_project",
    "update_workflow_template_metadata",
]

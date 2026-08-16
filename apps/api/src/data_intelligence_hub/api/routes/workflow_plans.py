from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from types import TracebackType
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeListResponse,
    MonitoringScopeTemplateCopyRequest,
    MonitoringScopeTemplateCopyResponse,
    WorkflowPlanCloneRequest,
    WorkflowPlanCloneResponse,
    WorkflowPlanCreateRequest,
    WorkflowPlanDetailResponse,
    WorkflowPlanListResponse,
    WorkflowPlanSaveResponse,
    WorkflowPlanTransitionRequest,
    WorkflowPlanTransitionResponse,
    WorkflowPlanVersionCompareResponse,
    WorkflowVersionCreateRequest,
    WorkflowVersionDetailResponse,
    WorkflowVersionListResponse,
    normalize_idempotency_key,
)
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanPreview,
)
from data_intelligence_hub.schemas.workflow_template_persistence import (
    WorkflowTemplateCreateRequest,
    WorkflowTemplateDetailResponse,
    WorkflowTemplateInstantiateRequest,
    WorkflowTemplateListResponse,
    WorkflowTemplateMetadataUpdateRequest,
    WorkflowTemplateMutationResponse,
    WorkflowTemplateRevisionCreateRequest,
    WorkflowTemplateRevisionListResponse,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    CapabilityCatalogResolutionError,
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    MonitoringScopeNotFoundError,
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanFlowModeConflictError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlanInvalidTransitionError,
    WorkflowPlannerDependencyUnavailableError,
    WorkflowPlannerInputError,
    WorkflowPlannerTopologyError,
    WorkflowPlanNotFoundError,
    WorkflowPlanPersistenceTransactionStateError,
    WorkflowPlanPreviewStaleError,
    WorkflowPlanStatusConflictError,
    WorkflowPlanVersionConflictError,
    WorkflowTemplateKeyConflictError,
    WorkflowTemplateNotEditableError,
    WorkflowTemplateNotFoundError,
    WorkflowTemplateRevisionConflictError,
    WorkflowTemplateRevisionInvalidError,
    WorkflowTemplateRevisionNotFoundError,
    WorkflowVersionNotFoundError,
)
from data_intelligence_hub.services.project_service import get_active_project_or_raise
from data_intelligence_hub.services.workflow_planner.persistence import (
    clone_workflow_plan,
    compare_workflow_plan_versions,
    create_workflow_plan,
    create_workflow_version,
    get_workflow_plan_detail,
    get_workflow_version_detail,
    list_monitoring_scopes_for_project,
    list_workflow_plan_versions,
    list_workflow_plans_for_project,
    transition_workflow_plan_status,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)
from data_intelligence_hub.services.workflow_planner.scope_templates import (
    copy_monitoring_scope_template,
)
from data_intelligence_hub.services.workflow_planner.template_persistence import (
    append_workflow_template_revision,
    create_workflow_template,
    get_workflow_template_detail,
    instantiate_workflow_plan_from_template,
    list_workflow_template_revisions_for_template,
    list_workflow_templates_for_project,
    update_workflow_template_metadata,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["workflow-plans"])


def _route_error(
    *,
    status_code: int,
    detail: object,
    request_id: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers={"X-Request-ID": request_id},
    )


def _sanitized_exc_info(
    exc: Exception,
) -> tuple[type[RuntimeError], RuntimeError, TracebackType | None]:
    safe_error = RuntimeError(type(exc).__name__)
    return RuntimeError, safe_error, exc.__traceback__


def _log_internal_failure(
    exc: Exception,
    *,
    request_id: str,
    project_id: uuid.UUID,
    flow_mode: str,
) -> None:
    logger.exception(
        "workflow_plan_preview_failed",
        request_id=request_id,
        project_id=str(project_id),
        flow_mode=flow_mode,
        error_type=type(exc).__name__,
        exc_info=_sanitized_exc_info(exc),
    )


def _log_persistence_failure(
    exc: Exception,
    *,
    request_id: str,
    project_id: uuid.UUID,
) -> None:
    logger.exception(
        "workflow_plan_persistence_failed",
        request_id=request_id,
        project_id=str(project_id),
        error_type=type(exc).__name__,
        exc_info=_sanitized_exc_info(exc),
    )


async def _run_persistence_operation[PersistenceResult](
    operation: Callable[[], Awaitable[PersistenceResult]],
    *,
    request_id: str,
    project_id: uuid.UUID,
) -> PersistenceResult:
    try:
        return await operation()
    except (
        ProjectNotFoundError,
        WorkflowPlanNotFoundError,
        WorkflowVersionNotFoundError,
        WorkflowTemplateNotFoundError,
        WorkflowTemplateRevisionNotFoundError,
        MonitoringScopeNotFoundError,
    ) as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except (
        ProjectNotActiveError,
        WorkflowPlanPreviewStaleError,
        WorkflowPlanVersionConflictError,
        WorkflowPlanIdempotencyConflictError,
        WorkflowPlanFlowModeConflictError,
        WorkflowPlanStatusConflictError,
        WorkflowPlanInvalidTransitionError,
        WorkflowTemplateKeyConflictError,
        WorkflowTemplateRevisionConflictError,
        WorkflowTemplateNotEditableError,
        WorkflowTemplateRevisionInvalidError,
    ) as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except WorkflowPlannerInputError as exc:
        raise _route_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.issues,
            request_id=request_id,
        ) from exc
    except (
        CapabilityCatalogLoadError,
        WorkflowPlannerDependencyUnavailableError,
    ) as exc:
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except CapabilityCatalogResolutionError as exc:
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except (
        SQLAlchemyError,
        WorkflowPlanPersistenceTransactionStateError,
    ) as exc:
        _log_persistence_failure(
            exc,
            request_id=request_id,
            project_id=project_id,
        )
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="persistence_unavailable",
            request_id=request_id,
        ) from exc
    except WorkflowPlannerTopologyError as exc:
        _log_persistence_failure(
            exc,
            request_id=request_id,
            project_id=project_id,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except Exception as exc:
        _log_persistence_failure(
            exc,
            request_id=request_id,
            project_id=project_id,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_planner_internal_error",
            request_id=request_id,
        ) from exc


def _validated_idempotency_key(
    value: Annotated[str, Header(alias="Idempotency-Key")],
) -> str:
    try:
        return normalize_idempotency_key(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["header", "Idempotency-Key"],
                    "msg": "idempotency_key_invalid",
                    "type": "value_error",
                }
            ],
        ) from exc


IdempotencyKeyDep = Annotated[str, Depends(_validated_idempotency_key)]


@router.post(
    "/{project_id}/workflow-templates",
    response_model=WorkflowTemplateMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_template_item(
    project_id: uuid.UUID,
    payload: WorkflowTemplateCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowTemplateMutationResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: create_workflow_template(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if not result.idempotent_replay else status.HTTP_200_OK
    )
    return result


@router.get(
    "/{project_id}/workflow-templates",
    response_model=WorkflowTemplateListResponse,
)
async def list_workflow_template_items(
    project_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowTemplateListResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: list_workflow_templates_for_project(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-templates/{template_id}",
    response_model=WorkflowTemplateDetailResponse,
)
async def get_workflow_template_item(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowTemplateDetailResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: get_workflow_template_detail(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_template_id=template_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.patch(
    "/{project_id}/workflow-templates/{template_id}",
    response_model=WorkflowTemplateMutationResponse,
)
async def update_workflow_template_item(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: WorkflowTemplateMetadataUpdateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowTemplateMutationResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: update_workflow_template_metadata(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_template_id=template_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_200_OK if result.idempotent_replay else status.HTTP_200_OK
    )
    return result


@router.post(
    "/{project_id}/workflow-templates/{template_id}/revisions",
    response_model=WorkflowTemplateMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_workflow_template_revision_item(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: WorkflowTemplateRevisionCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowTemplateMutationResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: append_workflow_template_revision(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_template_id=template_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if not result.idempotent_replay else status.HTTP_200_OK
    )
    return result


@router.get(
    "/{project_id}/workflow-templates/{template_id}/revisions",
    response_model=WorkflowTemplateRevisionListResponse,
)
async def list_workflow_template_revision_items(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowTemplateRevisionListResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: list_workflow_template_revisions_for_template(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_template_id=template_id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.post(
    "/{project_id}/workflow-templates/{template_id}/instantiate",
    response_model=WorkflowPlanSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def instantiate_workflow_template_item(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: WorkflowTemplateInstantiateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowPlanSaveResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: instantiate_workflow_plan_from_template(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_template_id=template_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if not result.idempotent_replay else status.HTTP_200_OK
    )
    return result


@router.post(
    "/{project_id}/workflow-plans/preview",
    response_model=WorkflowPlanPreview,
)
async def preview_workflow_plan_item(
    project_id: uuid.UUID,
    payload: PlanningInput,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowPlanPreview:
    started = perf_counter()
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    try:
        project = await get_active_project_or_raise(
            session,
            context.workspace,
            project_id,
        )
        catalog = await resolve_current_capability_catalog(session)
        generated_at = datetime.now(UTC)
        preview = build_workflow_plan_preview(
            project_id=project.id,
            planning_input=payload,
            catalog=catalog,
            generated_at=generated_at,
            request_id=request_id,
        )
    except ProjectNotFoundError as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except ProjectNotActiveError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except WorkflowPlannerInputError as exc:
        raise _route_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.issues,
            request_id=request_id,
        ) from exc
    except CapabilityCatalogResolutionError as exc:
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except (
        CapabilityCatalogLoadError,
        WorkflowPlannerDependencyUnavailableError,
    ) as exc:
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except WorkflowPlannerTopologyError as exc:
        _log_internal_failure(
            exc,
            request_id=request_id,
            project_id=project_id,
            flow_mode=payload.flow_mode.value,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except Exception as exc:
        _log_internal_failure(
            exc,
            request_id=request_id,
            project_id=project_id,
            flow_mode=payload.flow_mode.value,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_planner_internal_error",
            request_id=request_id,
        ) from exc

    logger.info(
        "workflow_plan_preview_generated",
        request_id=request_id,
        project_id=str(project.id),
        flow_mode=preview.flow_mode.value,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        preview_fingerprint=preview.preview_fingerprint,
        planning_status=preview.planning_status.value,
        route_requirement_count=len(preview.route_plans),
        resolved_count=sum(route.status == "resolved" for route in preview.route_plans),
        held_count=sum(route.status == "held" for route in preview.route_plans),
        duration_ms=round((perf_counter() - started) * 1000, 3),
    )
    return preview


@router.post(
    "/{project_id}/workflow-plans",
    response_model=WorkflowPlanSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_plan_item(
    project_id: uuid.UUID,
    payload: WorkflowPlanCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowPlanSaveResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: create_workflow_plan(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if result.outcome == "created" else status.HTTP_200_OK
    )
    return result


@router.post(
    "/{project_id}/workflow-plans/{plan_id}/clone",
    response_model=WorkflowPlanCloneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_workflow_plan_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: WorkflowPlanCloneRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowPlanCloneResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: clone_workflow_plan(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_plan_id=plan_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if not result.idempotent_replay else status.HTTP_200_OK
    )
    return result


@router.post(
    "/{project_id}/monitoring-scopes/{scope_id}/copy",
    response_model=MonitoringScopeTemplateCopyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def copy_monitoring_scope_template_item(
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    payload: MonitoringScopeTemplateCopyRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> MonitoringScopeTemplateCopyResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: copy_monitoring_scope_template(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            scope_id=scope_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if not result.idempotent_replay else status.HTTP_200_OK
    )
    return result


@router.post(
    "/{project_id}/workflow-plans/{plan_id}/status-transition",
    response_model=WorkflowPlanTransitionResponse,
)
async def transition_workflow_plan_status_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: WorkflowPlanTransitionRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowPlanTransitionResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: transition_workflow_plan_status(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_plan_id=plan_id,
            created_by_user_id=context.user.id,
            payload=payload,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    return result


@router.post(
    "/{project_id}/workflow-plans/{plan_id}/versions",
    response_model=WorkflowPlanSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_version_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: WorkflowVersionCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowPlanSaveResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    result = await _run_persistence_operation(
        lambda: create_workflow_version(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_plan_id=plan_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED if result.outcome == "created" else status.HTTP_200_OK
    )
    return result


@router.get(
    "/{project_id}/workflow-plans",
    response_model=WorkflowPlanListResponse,
)
async def list_workflow_plan_items(
    project_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowPlanListResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: list_workflow_plans_for_project(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-plans/{plan_id}",
    response_model=WorkflowPlanDetailResponse,
)
async def get_workflow_plan_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowPlanDetailResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: get_workflow_plan_detail(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            plan_id=plan_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-plans/{plan_id}/versions",
    response_model=WorkflowVersionListResponse,
)
async def list_workflow_version_items(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowVersionListResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: list_workflow_plan_versions(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            plan_id=plan_id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-plans/{plan_id}/version-compare",
    response_model=WorkflowPlanVersionCompareResponse,
)
async def compare_workflow_plan_version_items(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    base_version_id: Annotated[uuid.UUID, Query()],
    target_version_id: Annotated[uuid.UUID, Query()],
) -> WorkflowPlanVersionCompareResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: compare_workflow_plan_versions(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            plan_id=plan_id,
            base_version_id=base_version_id,
            target_version_id=target_version_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-plans/{plan_id}/versions/{version_id}",
    response_model=WorkflowVersionDetailResponse,
)
async def get_workflow_version_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowVersionDetailResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: get_workflow_version_detail(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/monitoring-scopes",
    response_model=MonitoringScopeListResponse,
)
async def list_monitoring_scope_items(
    project_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MonitoringScopeListResponse:
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    return await _run_persistence_operation(
        lambda: list_monitoring_scopes_for_project(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        project_id=project_id,
    )

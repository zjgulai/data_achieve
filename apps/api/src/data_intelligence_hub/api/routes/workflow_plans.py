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
    WorkflowPlanCreateRequest,
    WorkflowPlanDetailResponse,
    WorkflowPlanListResponse,
    WorkflowPlanSaveResponse,
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
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    ProjectNotActiveError,
    ProjectNotFoundError,
    WorkflowPlanFlowModeConflictError,
    WorkflowPlanIdempotencyConflictError,
    WorkflowPlannerDependencyUnavailableError,
    WorkflowPlannerInputError,
    WorkflowPlannerTopologyError,
    WorkflowPlanNotFoundError,
    WorkflowPlanPersistenceTransactionStateError,
    WorkflowPlanPreviewStaleError,
    WorkflowPlanVersionConflictError,
    WorkflowVersionNotFoundError,
)
from data_intelligence_hub.services.project_service import get_active_project_or_raise
from data_intelligence_hub.services.workflow_planner.persistence import (
    compare_workflow_plan_versions,
    create_workflow_plan,
    create_workflow_version,
    get_workflow_plan_detail,
    get_workflow_version_detail,
    list_monitoring_scopes_for_project,
    list_workflow_plan_versions,
    list_workflow_plans_for_project,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
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
        catalog = get_capability_catalog()
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

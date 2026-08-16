from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.capability_governance import (
    SHA256_FINGERPRINT_PATTERN,
    CapabilityGovernanceCandidateDetailResponse,
    CapabilityGovernanceCandidateListResponse,
    CapabilityGovernanceImportRequest,
    CapabilityGovernanceImportResponse,
    CapabilityGovernancePublicationCreateRequest,
    CapabilityGovernancePublicationDetailResponse,
    CapabilityGovernancePublicationListResponse,
    CapabilityGovernancePublicationResponse,
    CapabilityGovernancePublicationRollbackRequest,
    CapabilityGovernanceReviewRequest,
    CapabilityGovernanceReviewResponse,
    CapabilityGovernanceVerificationTaskDetailResponse,
    CapabilityGovernanceVerificationTaskListResponse,
    CapabilityVerificationTaskStatus,
    normalize_governance_idempotency_key,
)
from data_intelligence_hub.services.capability_governance.authority import (
    CapabilityGovernanceForbiddenError,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    CapabilityCatalogResolutionError,
)
from data_intelligence_hub.services.capability_governance.intake import (
    CapabilityGovernanceDataConflictError,
    CapabilityGovernanceIdempotencyConflictError,
    CapabilityGovernancePreviewStaleError,
    CapabilityGovernanceTransactionStateError,
    import_capability_candidates,
)
from data_intelligence_hub.services.capability_governance.publication import (
    CapabilityGovernanceCatalogSnapshotInvalidError,
    CapabilityGovernanceDecisionNotCurrentError,
    CapabilityGovernancePublicationContractError,
    CapabilityGovernancePublicationIdempotencyConflictError,
    CapabilityGovernancePublicationParentConflictError,
    CapabilityGovernancePublicationTransactionStateError,
    publish_capability_catalog,
    rollback_capability_catalog,
)
from data_intelligence_hub.services.capability_governance.queries import (
    CapabilityGovernanceReadContractError,
    CapabilityGovernanceResourceNotFoundError,
    get_governance_candidate_detail,
    get_governance_publication_detail,
    get_governance_verification_task_detail,
    list_governance_candidates,
    list_governance_publications,
    list_governance_verification_tasks,
)
from data_intelligence_hub.services.capability_governance.verification import (
    CapabilityGovernanceReviewContractError,
    CapabilityGovernanceReviewIdempotencyConflictError,
    CapabilityGovernanceReviewTransactionStateError,
    CapabilityGovernanceVerificationTaskConflictError,
    review_capability_candidate,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    CapabilityDiscoveryContractInvalidError,
    CapabilityDiscoveryFixtureInvalidError,
    CapabilityDiscoveryFixtureUnknownError,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["capability-governance"])


def _route_error(
    *,
    status_code: int,
    detail: str,
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
    action: str,
) -> None:
    logger.exception(
        "capability_governance_request_failed",
        request_id=request_id,
        action=action,
        error_type=type(exc).__name__,
        exc_info=_sanitized_exc_info(exc),
    )


async def _run_governance_operation[OperationResult](
    operation: Callable[[], Awaitable[OperationResult]],
    *,
    request_id: str,
    action: str,
) -> OperationResult:
    try:
        return await operation()
    except CapabilityGovernanceForbiddenError as exc:
        raise _route_error(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except CapabilityGovernanceResourceNotFoundError as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except CapabilityGovernancePreviewStaleError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except (
        CapabilityGovernanceIdempotencyConflictError,
        CapabilityGovernanceReviewIdempotencyConflictError,
        CapabilityGovernancePublicationIdempotencyConflictError,
    ) as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except CapabilityGovernanceVerificationTaskConflictError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except CapabilityGovernancePublicationParentConflictError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except CapabilityDiscoveryFixtureUnknownError as exc:
        raise _route_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.message,
            request_id=request_id,
        ) from exc
    except (
        CapabilityGovernanceReviewContractError,
        CapabilityGovernanceDecisionNotCurrentError,
        CapabilityGovernancePublicationContractError,
    ) as exc:
        raise _route_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except (
        CapabilityGovernanceCatalogSnapshotInvalidError,
        CapabilityCatalogResolutionError,
    ) as exc:
        _log_internal_failure(
            exc,
            request_id=request_id,
            action=action,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="catalog_snapshot_invalid",
            request_id=request_id,
        ) from exc
    except (
        CapabilityGovernanceTransactionStateError,
        CapabilityGovernanceReviewTransactionStateError,
        CapabilityGovernancePublicationTransactionStateError,
        SQLAlchemyError,
    ) as exc:
        _log_internal_failure(
            exc,
            request_id=request_id,
            action=action,
        )
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="persistence_unavailable",
            request_id=request_id,
        ) from exc
    except (
        CapabilityGovernanceDataConflictError,
        CapabilityGovernanceReadContractError,
        CapabilityDiscoveryFixtureInvalidError,
        CapabilityDiscoveryContractInvalidError,
        CapabilityCatalogLoadError,
    ) as exc:
        _log_internal_failure(
            exc,
            request_id=request_id,
            action=action,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal_server_error",
            request_id=request_id,
        ) from exc
    except Exception as exc:
        _log_internal_failure(
            exc,
            request_id=request_id,
            action=action,
        )
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal_server_error",
            request_id=request_id,
        ) from exc


def _validated_idempotency_key(
    value: Annotated[str, Header(alias="Idempotency-Key")],
) -> str:
    try:
        return normalize_governance_idempotency_key(value)
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
    "/imports",
    response_model=CapabilityGovernanceImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_governance_candidates(
    payload: CapabilityGovernanceImportRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> CapabilityGovernanceImportResponse:
    route_request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: import_capability_candidates(
            session,
            actor_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        ),
        request_id=route_request_id,
        action="import",
    )
    response.status_code = (
        status.HTTP_200_OK if result.idempotent_replay else status.HTTP_201_CREATED
    )
    response.headers["X-Request-ID"] = str(result.request_id)
    return result


@router.post(
    "/verification-tasks/{task_id}/decisions",
    response_model=CapabilityGovernanceReviewResponse,
)
async def review_governance_candidate(
    task_id: uuid.UUID,
    payload: CapabilityGovernanceReviewRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> CapabilityGovernanceReviewResponse:
    route_request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: review_capability_candidate(
            session,
            actor_user_id=context.user.id,
            task_id=task_id,
            payload=payload,
            idempotency_key=idempotency_key,
        ),
        request_id=route_request_id,
        action="review",
    )
    response.headers["X-Request-ID"] = str(result.request_id)
    return result


@router.post(
    "/publications",
    response_model=CapabilityGovernancePublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_governance_catalog(
    payload: CapabilityGovernancePublicationCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> CapabilityGovernancePublicationResponse:
    route_request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: publish_capability_catalog(
            session,
            actor_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        ),
        request_id=route_request_id,
        action="publish",
    )
    response.status_code = (
        status.HTTP_200_OK if result.idempotent_replay else status.HTTP_201_CREATED
    )
    response.headers["X-Request-ID"] = str(result.request_id)
    return result


@router.post(
    "/publications/rollback",
    response_model=CapabilityGovernancePublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rollback_governance_catalog(
    payload: CapabilityGovernancePublicationRollbackRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> CapabilityGovernancePublicationResponse:
    route_request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: rollback_capability_catalog(
            session,
            actor_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        ),
        request_id=route_request_id,
        action="rollback",
    )
    response.status_code = (
        status.HTTP_200_OK if result.idempotent_replay else status.HTTP_201_CREATED
    )
    response.headers["X-Request-ID"] = str(result.request_id)
    return result


@router.get(
    "/candidates",
    response_model=CapabilityGovernanceCandidateListResponse,
)
async def list_governance_candidate_items(
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CapabilityGovernanceCandidateListResponse:
    request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: list_governance_candidates(
            session,
            actor_user_id=context.user.id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        action="list_candidates",
    )
    response.headers["X-Request-ID"] = request_id
    return result


@router.get(
    "/candidates/{candidate_key}",
    response_model=CapabilityGovernanceCandidateDetailResponse,
)
async def get_governance_candidate_item(
    candidate_key: Annotated[
        str,
        Path(pattern=SHA256_FINGERPRINT_PATTERN),
    ],
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityGovernanceCandidateDetailResponse:
    request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: get_governance_candidate_detail(
            session,
            actor_user_id=context.user.id,
            candidate_key=candidate_key,
        ),
        request_id=request_id,
        action="get_candidate",
    )
    response.headers["X-Request-ID"] = request_id
    return result


@router.get(
    "/verification-tasks",
    response_model=CapabilityGovernanceVerificationTaskListResponse,
)
async def list_governance_verification_task_items(
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    task_status: Annotated[
        CapabilityVerificationTaskStatus | None,
        Query(alias="status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CapabilityGovernanceVerificationTaskListResponse:
    request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: list_governance_verification_tasks(
            session,
            actor_user_id=context.user.id,
            task_status=task_status,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        action="list_verification_tasks",
    )
    response.headers["X-Request-ID"] = request_id
    return result


@router.get(
    "/verification-tasks/{task_id}",
    response_model=CapabilityGovernanceVerificationTaskDetailResponse,
)
async def get_governance_verification_task_item(
    task_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityGovernanceVerificationTaskDetailResponse:
    request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: get_governance_verification_task_detail(
            session,
            actor_user_id=context.user.id,
            task_id=task_id,
        ),
        request_id=request_id,
        action="get_verification_task",
    )
    response.headers["X-Request-ID"] = request_id
    return result


@router.get(
    "/publications",
    response_model=CapabilityGovernancePublicationListResponse,
)
async def list_governance_publication_items(
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CapabilityGovernancePublicationListResponse:
    request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: list_governance_publications(
            session,
            actor_user_id=context.user.id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        action="list_publications",
    )
    response.headers["X-Request-ID"] = request_id
    return result


@router.get(
    "/publications/{revision_id}",
    response_model=CapabilityGovernancePublicationDetailResponse,
)
async def get_governance_publication_item(
    revision_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityGovernancePublicationDetailResponse:
    request_id = str(uuid.uuid4())
    result = await _run_governance_operation(
        lambda: get_governance_publication_detail(
            session,
            actor_user_id=context.user.id,
            revision_id=revision_id,
        ),
        request_id=request_id,
        action="get_publication",
    )
    response.headers["X-Request-ID"] = request_id
    return result

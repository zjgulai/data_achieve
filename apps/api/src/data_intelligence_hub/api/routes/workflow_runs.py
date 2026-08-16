from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Annotated, cast

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import JsonValue
from sqlalchemy.exc import SQLAlchemyError

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.models.workflow_execution import WorkflowRun
from data_intelligence_hub.repositories.provider_health import (
    list_latest_provider_health_feedbacks,
    list_provider_health_snapshots_for_candidates,
)
from data_intelligence_hub.repositories.workflow_action import (
    get_workflow_run_action_context,
)
from data_intelligence_hub.repositories.workflow_execution import (
    count_workflow_runs,
    get_project,
    get_workflow_budget_account_for_run,
    get_workflow_plan,
    get_workflow_run,
    get_workflow_version,
    list_step_run_attempts_for_run,
    list_step_runs,
    list_workflow_budget_ledger_entries,
    list_workflow_fallback_decisions_for_run,
    list_workflow_runs,
    list_workflow_shadow_comparisons,
    list_workflow_step_checkpoints_for_run,
)
from data_intelligence_hub.repositories.workflow_lineage import (
    get_dataset_version_by_workflow_run,
    get_materialization_request_by_run,
    list_raw_records_by_ids,
)
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.provider_health import (
    ProviderHealthRouteFeedbackResponse,
    ProviderHealthSnapshotResponse,
)
from data_intelligence_hub.schemas.workflow_action_command import (
    WorkflowActionApprovalReceipt,
    WorkflowActionApprovalRequest,
    WorkflowActionReceipt,
    WorkflowRunActionGatesCurrentResponse,
    WorkflowRunActionRequest,
)
from data_intelligence_hub.schemas.workflow_attempt_fallback import (
    WorkflowAttemptFallbackEvidenceResponse,
    WorkflowFallbackDecisionEvidenceResponse,
    WorkflowStepAttemptEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_budget import (
    WorkflowBudgetAccountResponse,
    WorkflowBudgetLedgerEntryResponse,
)
from data_intelligence_hub.schemas.workflow_checkpoint_budget import (
    WorkflowBudgetEvidenceStatus,
    WorkflowBudgetUsageEvidenceResponse,
    WorkflowCheckpointBudgetEvidenceResponse,
    WorkflowCheckpointStepEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
    WorkflowRunDetailResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowStepRunResponse,
    normalize_workflow_execution_idempotency_key,
)
from data_intelligence_hub.schemas.workflow_executor_evidence import (
    WorkflowExecutorEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowLineageMaterializationRequest,
    WorkflowLineageMaterializationResponse,
    WorkflowRunLineagePreview,
)
from data_intelligence_hub.schemas.workflow_planner import RoutePlanPreview
from data_intelligence_hub.schemas.workflow_provider_health import (
    WorkflowProviderHealthCandidateEvidenceResponse,
    WorkflowProviderHealthEvidenceResponse,
    WorkflowProviderHealthRoutingState,
    WorkflowProviderHealthStepEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_resume import WorkflowStepCheckpointResponse
from data_intelligence_hub.schemas.workflow_run_gate import (
    WorkflowFixtureRunGateResponse,
)
from data_intelligence_hub.schemas.workflow_shadow import (
    WorkflowShadowComparisonListResponse,
    WorkflowShadowComparisonResponse,
)
from data_intelligence_hub.services.workflow_execution.action_command import (
    WorkflowActionCommandError,
    execute_workflow_run_action,
    find_workflow_run_action_replay,
    issue_workflow_action_approval,
)
from data_intelligence_hub.services.workflow_execution.action_surface import (
    WorkflowRunActionSurface,
    build_workflow_run_action_surface,
)
from data_intelligence_hub.services.workflow_execution.eligibility import (
    WorkflowVersionNotFixtureRunnableError,
)
from data_intelligence_hub.services.workflow_execution.execution import (
    WorkflowExecutionIdempotencyConflictError,
    WorkflowExecutionLineageInvalidError,
    WorkflowExecutionPlanNotFoundError,
    WorkflowExecutionProjectNotActiveError,
    WorkflowExecutionProjectNotFoundError,
    WorkflowExecutionRunNotFoundError,
    WorkflowExecutionStepFailedError,
    WorkflowExecutionTransactionStateError,
    WorkflowExecutionVersionNotFoundError,
    create_workflow_fixture_run,
)
from data_intelligence_hub.services.workflow_execution.executor_evidence import (
    load_workflow_executor_evidence,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixtureAdapterUnavailableError,
    WorkflowFixtureContractInvalidError,
    WorkflowFixturePayloadUnboundError,
    WorkflowFixtureProfileUnknownError,
    load_workflow_fixture_payload,
    load_workflow_fixture_profile,
)
from data_intelligence_hub.services.workflow_execution.integrity import (
    WorkflowVersionExpectedFingerprintConflictError,
    WorkflowVersionSnapshotInvalidError,
    validate_workflow_version_snapshot,
)
from data_intelligence_hub.services.workflow_execution.lineage_preview import (
    WorkflowLineagePreviewInvalidError,
    build_workflow_lineage_preview,
)
from data_intelligence_hub.services.workflow_execution.materialization import (
    MATERIALIZATION_DATASET_CONFLICT_CODES,
    WorkflowMaterializationDatasetConflictError,
    WorkflowMaterializationIdempotencyConflictError,
    WorkflowMaterializationLedgerInvalidError,
    WorkflowMaterializationLineageDigestConflictError,
    WorkflowMaterializationPayloadInvalidError,
    WorkflowMaterializationProjectNotActiveError,
    WorkflowMaterializationProjectNotFoundError,
    WorkflowMaterializationRunNotCompletedError,
    WorkflowMaterializationRunNotFoundError,
    WorkflowMaterializationTransactionStateError,
    WorkflowRunAlreadyMaterializedError,
    materialize_workflow_lineage,
)
from data_intelligence_hub.services.workflow_execution.run_gate import (
    evaluate_workflow_fixture_run_gate,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["workflow-runs"])


def _request_id(request: Request) -> str:
    value = getattr(request.state, "workflow_execution_request_id", None)
    if isinstance(value, str) and value:
        return value
    value = str(uuid.uuid4())
    request.state.workflow_execution_request_id = value
    return value


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


def _log_failure(
    exc: Exception,
    *,
    request_id: str,
    project_id: uuid.UUID,
) -> None:
    logger.exception(
        "workflow_execution_failed",
        request_id=request_id,
        project_id=str(project_id),
        error_type=type(exc).__name__,
        exc_info=_sanitized_exc_info(exc),
    )


async def _run_operation[Result](
    operation: Callable[[], Awaitable[Result]],
    *,
    request_id: str,
    project_id: uuid.UUID,
) -> Result:
    try:
        return await operation()
    except WorkflowExecutionProjectNotFoundError as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project_not_found",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionPlanNotFoundError as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workflow_plan_not_found",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionVersionNotFoundError as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workflow_version_not_found",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionRunNotFoundError as exc:
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workflow_run_not_found",
            request_id=request_id,
        ) from exc
    except (
        WorkflowMaterializationProjectNotFoundError,
        WorkflowMaterializationRunNotFoundError,
    ) as exc:
        detail = (
            "project_not_found"
            if isinstance(exc, WorkflowMaterializationProjectNotFoundError)
            else "workflow_run_not_found"
        )
        raise _route_error(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            request_id=request_id,
        ) from exc
    except WorkflowExecutionProjectNotActiveError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="project_not_active",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationProjectNotActiveError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="project_not_active",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationRunNotCompletedError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_run_not_completed",
            request_id=request_id,
        ) from exc
    except WorkflowFixturePayloadUnboundError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_payload_unbound",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationLineageDigestConflictError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_lineage_digest_conflict",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationIdempotencyConflictError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency_conflict",
            request_id=request_id,
        ) from exc
    except WorkflowRunAlreadyMaterializedError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_run_already_materialized",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationDatasetConflictError as exc:
        detail = str(exc)
        if detail not in MATERIALIZATION_DATASET_CONFLICT_CODES:
            detail = "dataset_lineage_conflict"
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationTransactionStateError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_materialization_transaction_state_invalid",
            request_id=request_id,
        ) from exc
    except WorkflowVersionExpectedFingerprintConflictError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_version_fingerprint_conflict",
            request_id=request_id,
        ) from exc
    except WorkflowVersionNotFixtureRunnableError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_version_not_fixture_runnable",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionIdempotencyConflictError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency_conflict",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionTransactionStateError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_execution_transaction_state_invalid",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionStepFailedError as exc:
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workflow_step_execution_failed",
            request_id=request_id,
        ) from exc
    except WorkflowFixtureProfileUnknownError as exc:
        raise _route_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="workflow_fixture_profile_unknown",
            request_id=request_id,
        ) from exc
    except WorkflowFixtureContractInvalidError as exc:
        raise _route_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="workflow_fixture_contract_invalid",
            request_id=request_id,
        ) from exc
    except WorkflowFixtureAdapterUnavailableError as exc:
        raise _route_error(
            status_code=status.HTTP_409_CONFLICT,
            detail="workflow_fixture_adapter_unavailable",
            request_id=request_id,
        ) from exc
    except WorkflowVersionSnapshotInvalidError as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_version_snapshot_invalid",
            request_id=request_id,
        ) from exc
    except WorkflowExecutionLineageInvalidError as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_run_lineage_invalid",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationPayloadInvalidError as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_materialization_payload_invalid",
            request_id=request_id,
        ) from exc
    except WorkflowMaterializationLedgerInvalidError as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_materialization_ledger_invalid",
            request_id=request_id,
        ) from exc
    except SQLAlchemyError as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workflow_execution_persistence_unavailable",
            request_id=request_id,
        ) from exc
    except Exception as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_execution_internal_error",
            request_id=request_id,
        ) from exc


async def _run_action_operation[Result](
    operation: Callable[[], Awaitable[Result]],
    *,
    request_id: str,
    project_id: uuid.UUID,
) -> Result:
    try:
        return await operation()
    except WorkflowActionCommandError as exc:
        raise _route_error(
            status_code=exc.status,
            detail=exc.code,
            request_id=request_id,
        ) from exc
    except SQLAlchemyError as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workflow_action_persistence_unavailable",
            request_id=request_id,
        ) from exc
    except Exception as exc:
        _log_failure(exc, request_id=request_id, project_id=project_id)
        raise _route_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="workflow_action_internal_error",
            request_id=request_id,
        ) from exc


def _validated_idempotency_key(
    value: Annotated[str, Header(alias="Idempotency-Key")],
) -> str:
    try:
        return normalize_workflow_execution_idempotency_key(value)
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


async def _run_response_with_template_lineage(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run: WorkflowRun | WorkflowRunResponse,
) -> WorkflowRunResponse:
    if isinstance(run, WorkflowRunResponse):
        return run
    version = await get_workflow_version(
        session,
        workspace_id,
        project_id,
        run.workflow_plan_id,
        run.workflow_version_id,
    )
    if version is None:
        raise WorkflowExecutionLineageInvalidError("workflow_run_lineage_invalid")
    try:
        return WorkflowRunResponse.model_validate(
            {
                **WorkflowRunResponse.model_validate(run).model_dump(mode="json"),
                "workflow_template_id": version.workflow_template_id,
                "workflow_template_revision_id": version.workflow_template_revision_id,
            }
        )
    except ValueError as exc:
        raise WorkflowExecutionLineageInvalidError("workflow_run_lineage_invalid") from exc


async def _list_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID | None,
    workflow_version_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> WorkflowRunListResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    runs = await list_workflow_runs(
        session,
        workspace_id,
        project_id,
        workflow_plan_id=workflow_plan_id,
        workflow_version_id=workflow_version_id,
        limit=limit,
        offset=offset,
    )
    total = await count_workflow_runs(
        session,
        workspace_id,
        project_id,
        workflow_plan_id=workflow_plan_id,
        workflow_version_id=workflow_version_id,
    )
    items: list[WorkflowRunResponse] = []
    for run in runs:
        items.append(
            await _run_response_with_template_lineage(
                session=session,
                workspace_id=workspace_id,
                project_id=project_id,
                run=run,
            )
        )
    return WorkflowRunListResponse(
        project_status=cast(ProjectStatus, project.status),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


async def _detail_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowRunDetailResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    run = await get_workflow_run(session, workspace_id, project_id, run_id)
    if run is None:
        raise WorkflowExecutionRunNotFoundError("workflow_run_not_found")
    steps = await list_step_runs(session, workspace_id, project_id, run_id)
    return WorkflowRunDetailResponse(
        project_status=cast(ProjectStatus, project.status),
        run=await _run_response_with_template_lineage(
            session=session,
            workspace_id=workspace_id,
            project_id=project_id,
            run=run,
        ),
        steps=[WorkflowStepRunResponse.model_validate(item) for item in steps],
    )


async def _lineage_preview_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowRunLineagePreview:
    detail = await _detail_response(
        session=session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
    )
    try:
        loaded = load_workflow_fixture_profile(detail.run.fixture_profile_id)
        payload_bound = loaded.profile_hash == detail.run.fixture_profile_hash
        envelopes = []
        if payload_bound:
            envelopes = [
                load_workflow_fixture_payload(
                    loaded,
                    fixture_case_id=cast(str, step.fixture_case_id),
                    implementation_id=step.implementation_id,
                    platform=step.platform,
                    resource_type=step.resource_type,
                    operation=step.operation,
                    evidence_refs=list(step.evidence_refs),
                    expected_fixture_content_hash=cast(str, step.fixture_content_hash),
                    expected_records_count=step.records_count,
                    expected_output_digest=cast(str, step.output_digest),
                )
                for step in detail.steps
            ]
        version = await get_dataset_version_by_workflow_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        ledger = await get_materialization_request_by_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        if (version is None) != (ledger is None):
            raise WorkflowLineagePreviewInvalidError(
                "workflow_lineage_preview_invalid:materialized_state_partial"
            )
        raw_record_ids: list[uuid.UUID] = []
        ledger_response: WorkflowLineageMaterializationResponse | None = None
        if version is not None and ledger is not None:
            if not payload_bound:
                raise WorkflowLineagePreviewInvalidError(
                    "workflow_lineage_preview_invalid:materialized_payload_unbound"
                )
            expected_step_ids = [item.id for item in detail.steps]
            expected_records = [
                (step.id, record)
                for step, envelope in zip(detail.steps, envelopes, strict=True)
                for record in envelope.records
            ]
            source_step_ids = [
                uuid.UUID(item) for item in version.source_workflow_step_run_ids or []
            ]
            raw_record_ids = [uuid.UUID(item) for item in version.source_raw_record_ids or []]
            if (
                version.source_workflow_run_id != run_id
                or version.lineage_contract_version != "workflow_dataset_version.v1"
                or source_step_ids != expected_step_ids
                or version.row_count != len(raw_record_ids)
                or len(version.rows) != len(raw_record_ids)
                or len(expected_records) != len(raw_record_ids)
                or ledger.outcome != "completed"
                or ledger.response_status != status.HTTP_201_CREATED
                or ledger.dataset_id != version.dataset_id
                or ledger.dataset_version_id != version.id
            ):
                raise WorkflowLineagePreviewInvalidError(
                    "workflow_lineage_preview_invalid:materialized_state_mismatch"
                )
            records = await list_raw_records_by_ids(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                raw_record_ids=raw_record_ids,
            )
            counts: Counter[uuid.UUID] = Counter()
            for record_id, record, row, expected in zip(
                raw_record_ids,
                records,
                version.rows,
                expected_records,
                strict=True,
            ):
                expected_step_id, expected_record = expected
                collected_at = record.collected_at
                if collected_at.utcoffset() is None:
                    collected_at = collected_at.replace(tzinfo=UTC)
                if (
                    record.id != record_id
                    or record.workflow_run_id != run_id
                    or record.workflow_step_run_id != expected_step_id
                    or record.workflow_lineage_contract_version != "workflow_raw_record.v1"
                    or record.record_type != expected_record.record_type
                    or record.source_url != expected_record.source_url
                    or collected_at.astimezone(UTC) != expected_record.collected_at
                    or not isinstance(record.content, dict)
                    or record.content != expected_record.content
                    or record.content != row
                    or record.content_hash
                    != sha256_id(cast(JsonValue, record.content)).removeprefix("sha256:")
                ):
                    raise WorkflowLineagePreviewInvalidError(
                        "workflow_lineage_preview_invalid:raw_record_mismatch"
                    )
                counts[record.workflow_step_run_id] += 1
            if len(records) != len(raw_record_ids) or any(
                counts[step.id] != step.records_count for step in detail.steps
            ):
                raise WorkflowLineagePreviewInvalidError(
                    "workflow_lineage_preview_invalid:raw_record_count_mismatch"
                )
            ledger_response = WorkflowLineageMaterializationResponse.model_validate(
                ledger.response_payload
            )
            if (
                ledger_response.materialization_id != ledger.id
                or ledger_response.workflow_run_id != run_id
                or ledger_response.dataset_id != version.dataset_id
                or ledger_response.dataset_version_id != version.id
                or ledger_response.dataset_version_number != version.version_number
                or ledger_response.raw_record_ids != raw_record_ids
                or ledger_response.records_count != len(raw_record_ids)
                or not ledger_response.database_write
                or ledger_response.idempotent_replay
                or not ledger_response.raw_record_write
                or not ledger_response.dataset_write
            ):
                raise WorkflowLineagePreviewInvalidError(
                    "workflow_lineage_preview_invalid:ledger_response_mismatch"
                )
        preview = build_workflow_lineage_preview(
            detail.run,
            detail.steps,
            payload_bound=payload_bound,
            materialized_raw_record_ids=raw_record_ids,
            dataset_id=version.dataset_id if version is not None else None,
            dataset_version_id=version.id if version is not None else None,
        )
        if ledger_response is not None and ledger_response.lineage_digest != preview.lineage_digest:
            raise WorkflowLineagePreviewInvalidError(
                "workflow_lineage_preview_invalid:ledger_digest_mismatch"
            )
        return preview
    except WorkflowFixturePayloadUnboundError:
        return build_workflow_lineage_preview(
            detail.run,
            detail.steps,
            payload_bound=False,
        )
    except (WorkflowLineagePreviewInvalidError, ValueError) as exc:
        raise WorkflowExecutionLineageInvalidError("workflow_run_lineage_preview_invalid") from exc


async def _shadow_comparison_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowShadowComparisonListResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    run = await get_workflow_run(session, workspace_id, project_id, run_id)
    if run is None:
        raise WorkflowExecutionRunNotFoundError("workflow_run_not_found")
    comparisons = await list_workflow_shadow_comparisons(
        session,
        workspace_id,
        project_id,
        run_id,
    )
    items = [WorkflowShadowComparisonResponse.model_validate(item) for item in comparisons]
    return WorkflowShadowComparisonListResponse(items=items, total=len(items))


async def _attempt_fallback_evidence_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowAttemptFallbackEvidenceResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    run = await get_workflow_run(session, workspace_id, project_id, run_id)
    if run is None:
        raise WorkflowExecutionRunNotFoundError("workflow_run_not_found")
    attempts = await list_step_run_attempts_for_run(
        session,
        workspace_id,
        project_id,
        run_id,
    )
    fallback_decisions = await list_workflow_fallback_decisions_for_run(
        session,
        workspace_id,
        project_id,
        run_id,
    )
    attempt_items = [WorkflowStepAttemptEvidenceResponse.model_validate(item) for item in attempts]
    fallback_items = [
        WorkflowFallbackDecisionEvidenceResponse.model_validate(item) for item in fallback_decisions
    ]
    return WorkflowAttemptFallbackEvidenceResponse(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        attempts=attempt_items,
        fallback_decisions=fallback_items,
        attempt_total=len(attempt_items),
        fallback_decision_total=len(fallback_items),
    )


async def _checkpoint_budget_evidence_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowCheckpointBudgetEvidenceResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    run = await get_workflow_run(session, workspace_id, project_id, run_id)
    if run is None:
        raise WorkflowExecutionRunNotFoundError("workflow_run_not_found")
    steps = await list_step_runs(session, workspace_id, project_id, run_id)
    checkpoints = await list_workflow_step_checkpoints_for_run(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=run.workflow_plan_id,
        workflow_version_id=run.workflow_version_id,
        workflow_run_id=run_id,
    )
    account = await get_workflow_budget_account_for_run(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=run.workflow_plan_id,
        workflow_version_id=run.workflow_version_id,
        workflow_run_id=run_id,
    )
    entries = (
        await list_workflow_budget_ledger_entries(session, account.id)
        if account is not None
        else ()
    )

    try:
        steps_by_ref: dict[str, object] = {}
        for step in steps:
            if step.step_ref in steps_by_ref:
                raise ValueError("workflow_checkpoint_step_ref_ambiguous")
            steps_by_ref[step.step_ref] = step
        checkpoints_by_ref: dict[str, list[WorkflowStepCheckpointResponse]] = {}
        for checkpoint in checkpoints:
            if checkpoint.step_ref not in steps_by_ref:
                raise ValueError("workflow_checkpoint_step_not_found")
            checkpoints_by_ref.setdefault(checkpoint.step_ref, []).append(
                WorkflowStepCheckpointResponse.model_validate(checkpoint)
            )

        checkpoint_steps: list[WorkflowCheckpointStepEvidenceResponse] = []
        for step in steps:
            items = checkpoints_by_ref.get(step.step_ref, [])
            if not items:
                continue
            final = items[-1]
            checkpoint_steps.append(
                WorkflowCheckpointStepEvidenceResponse(
                    step_run_id=step.id,
                    execution_session_id=run_id,
                    step_ref=step.step_ref,
                    requirement_ref=step.requirement_ref,
                    implementation_id=step.implementation_id,
                    checkpoints=items,
                    confirmed_pages=len(items),
                    confirmed_records=sum(item.records_count for item in items),
                    terminal=final.terminal,
                    next_page_number=len(items) + 1,
                    next_cursor=final.cursor_after,
                )
            )

        account_response = (
            WorkflowBudgetAccountResponse.model_validate(account) if account is not None else None
        )
        entry_responses = [
            WorkflowBudgetLedgerEntryResponse.model_validate(entry) for entry in entries
        ]
        if account_response is None:
            budget_status: WorkflowBudgetEvidenceStatus = "not_configured"
            held_reason_code = None
            usage = None
        else:
            final_entry = entry_responses[-1] if entry_responses else None
            if final_entry is None:
                budget_status = "configured"
                held_reason_code = None
                request_count = 0
                item_count = 0
                quota_units = {key: 0 for key in account_response.quota_ceilings}
                cost_usd = Decimal("0")
                time_ms = 0
            else:
                budget_status = "held" if final_entry.status == "blocked" else "within_limit"
                held_reason_code = final_entry.blocker_code
                request_count = final_entry.cumulative_request_count
                item_count = final_entry.cumulative_item_count
                quota_units = final_entry.cumulative_quota_units
                cost_usd = final_entry.cumulative_cost_usd
                time_ms = final_entry.cumulative_time_ms
            usage = WorkflowBudgetUsageEvidenceResponse(
                request_count=request_count,
                request_limit=account_response.max_requests,
                item_count=item_count,
                item_limit=account_response.max_items,
                quota_units=quota_units,
                quota_ceilings=account_response.quota_ceilings,
                cost_usd=cost_usd,
                cost_limit_usd=account_response.max_cost_usd,
                time_ms=time_ms,
                time_limit_ms=account_response.max_time_ms,
            )

        return WorkflowCheckpointBudgetEvidenceResponse(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_plan_id=run.workflow_plan_id,
            workflow_version_id=run.workflow_version_id,
            workflow_run_id=run_id,
            execution_session_id=run_id,
            checkpoint_steps=checkpoint_steps,
            checkpoint_step_total=len(checkpoint_steps),
            checkpoint_page_total=sum(item.confirmed_pages for item in checkpoint_steps),
            budget_status=budget_status,
            budget_account=account_response,
            budget_entries=entry_responses,
            budget_entry_total=len(entry_responses),
            usage=usage,
            held_reason_code=held_reason_code,
        )
    except ValueError as exc:
        raise WorkflowExecutionLineageInvalidError(
            "workflow_checkpoint_budget_evidence_invalid"
        ) from exc


def _provider_health_read_time(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


async def _executor_evidence_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    evaluated_at: datetime | None = None,
) -> WorkflowExecutorEvidenceResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    run = await get_workflow_run(session, workspace_id, project_id, run_id)
    if run is None:
        raise WorkflowExecutionRunNotFoundError("workflow_run_not_found")
    return await load_workflow_executor_evidence(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        evaluated_at=_provider_health_read_time(evaluated_at),
    )


async def _provider_health_evidence_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    read_at: datetime | None = None,
) -> WorkflowProviderHealthEvidenceResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    run = await get_workflow_run(session, workspace_id, project_id, run_id)
    if run is None:
        raise WorkflowExecutionRunNotFoundError("workflow_run_not_found")
    steps = await list_step_runs(session, workspace_id, project_id, run_id)
    feedbacks = await list_latest_provider_health_feedbacks(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        limit=100,
    )
    observed_at = _provider_health_read_time(read_at)

    try:
        step_evidence: list[WorkflowProviderHealthStepEvidenceResponse] = []
        for step in steps:
            route = RoutePlanPreview.model_validate(step.route_plan_snapshot)
            primary = route.primary_implementation
            if primary is None or primary.implementation_id != step.implementation_id:
                raise ValueError("workflow_provider_health_primary_identity_invalid")
            candidate_ids = [
                primary.implementation_id,
                *(item.implementation_id for item in route.fallback_implementations),
            ]
            if len(candidate_ids) != len(set(candidate_ids)):
                raise ValueError("workflow_provider_health_candidate_duplicate")

            snapshots = await list_provider_health_snapshots_for_candidates(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                platform_id=step.platform,
                resource_type=step.resource_type,
                operation=step.operation,
                implementation_ids=candidate_ids,
            )
            snapshots_by_implementation: dict[str, list[ProviderHealthSnapshotResponse]] = {
                candidate_id: [] for candidate_id in candidate_ids
            }
            for persisted_snapshot in snapshots:
                response = ProviderHealthSnapshotResponse.model_validate(persisted_snapshot)
                if response.implementation_id not in snapshots_by_implementation:
                    raise ValueError("workflow_provider_health_snapshot_candidate_invalid")
                snapshots_by_implementation[response.implementation_id].append(response)

            candidate_evidence: list[WorkflowProviderHealthCandidateEvidenceResponse] = []
            for candidate_id in candidate_ids:
                chain = snapshots_by_implementation[candidate_id]
                previous: ProviderHealthSnapshotResponse | None = None
                for expected_version, chain_snapshot in enumerate(chain, start=1):
                    if (
                        chain_snapshot.workspace_id != workspace_id
                        or chain_snapshot.project_id != project_id
                        or chain_snapshot.platform_id != step.platform
                        or chain_snapshot.resource_type != step.resource_type
                        or chain_snapshot.operation != step.operation
                        or chain_snapshot.snapshot_version != expected_version
                        or chain_snapshot.previous_snapshot_digest
                        != (previous.snapshot_digest if previous is not None else None)
                    ):
                        raise ValueError("workflow_provider_health_snapshot_chain_invalid")
                    previous = chain_snapshot
                latest = chain[-1] if chain else None
                routing_state: WorkflowProviderHealthRoutingState = (
                    "not_observed"
                    if latest is None
                    else (
                        "routing_active"
                        if _provider_health_read_time(latest.routing_valid_until) > observed_at
                        else "routing_expired"
                    )
                )
                candidate_evidence.append(
                    WorkflowProviderHealthCandidateEvidenceResponse(
                        implementation_id=candidate_id,
                        selected_for_run=candidate_id == step.implementation_id,
                        health_status=latest.status if latest is not None else "not_observed",
                        routing_state=routing_state,
                        snapshot=latest,
                    )
                )

            matching_feedback = next(
                (
                    ProviderHealthRouteFeedbackResponse.model_validate(feedback)
                    for feedback in feedbacks
                    if feedback.platform_id == step.platform
                    and feedback.resource_type == step.resource_type
                    and feedback.operation == step.operation
                    and feedback.original_candidate_order == candidate_ids
                ),
                None,
            )
            if matching_feedback is not None and (
                matching_feedback.workspace_id != workspace_id
                or matching_feedback.project_id != project_id
            ):
                raise ValueError("workflow_provider_health_feedback_owner_invalid")
            step_evidence.append(
                WorkflowProviderHealthStepEvidenceResponse(
                    step_run_id=step.id,
                    step_ref=step.step_ref,
                    requirement_ref=step.requirement_ref,
                    platform_id=step.platform,
                    resource_type=step.resource_type,
                    operation=step.operation,
                    selected_implementation_id=step.implementation_id,
                    candidates=candidate_evidence,
                    route_feedback=matching_feedback,
                    route_feedback_match=(
                        "ordered_candidate_match"
                        if matching_feedback is not None
                        else "not_available"
                    ),
                )
            )

        candidates = [candidate for step in step_evidence for candidate in step.candidates]
        return WorkflowProviderHealthEvidenceResponse(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            read_at=observed_at,
            steps=step_evidence,
            step_total=len(step_evidence),
            observed_candidate_total=sum(item.snapshot is not None for item in candidates),
            routing_active_candidate_total=sum(
                item.routing_state == "routing_active" for item in candidates
            ),
            attention_candidate_total=sum(
                item.health_status in {"degraded", "unhealthy"} for item in candidates
            ),
            route_feedback_total=sum(item.route_feedback is not None for item in step_evidence),
        )
    except ValueError as exc:
        raise WorkflowExecutionLineageInvalidError(
            "workflow_provider_health_evidence_invalid"
        ) from exc


async def _action_surface_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowRunActionSurface:
    detail = await _detail_response(
        session=session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
    )
    attempt_fallback = await _attempt_fallback_evidence_response(
        session=session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
    )
    checkpoint_budget = await _checkpoint_budget_evidence_response(
        session=session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
    )
    provider_health = await _provider_health_evidence_response(
        session=session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
    )
    action_context = await get_workflow_run_action_context(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
    )
    try:
        return build_workflow_run_action_surface(
            detail=detail,
            attempt_fallback=attempt_fallback,
            checkpoint_budget=checkpoint_budget,
            provider_health=provider_health,
            action_context_version=(
                action_context.action_context_version if action_context is not None else 1
            ),
            evaluated_at=datetime.now(UTC),
        )
    except ValueError as exc:
        raise WorkflowExecutionLineageInvalidError("workflow_run_action_gates_invalid") from exc


async def _action_gates_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowRunActionGatesCurrentResponse:
    surface = await _action_surface_response(
        session=session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
    )
    return surface.response


async def _fixture_run_gate_response(
    *,
    session: SessionDep,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> WorkflowFixtureRunGateResponse:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkflowExecutionProjectNotFoundError("project_not_found")
    plan = await get_workflow_plan(
        session,
        workspace_id,
        project_id,
        workflow_plan_id,
    )
    if plan is None:
        raise WorkflowExecutionPlanNotFoundError("workflow_plan_not_found")
    version = await get_workflow_version(
        session,
        workspace_id,
        project_id,
        workflow_plan_id,
        workflow_version_id,
    )
    if version is None:
        raise WorkflowExecutionVersionNotFoundError("workflow_version_not_found")
    validated = validate_workflow_version_snapshot(
        version,
        expected_workspace_id=workspace_id,
        expected_project_id=project_id,
        expected_workflow_plan_id=workflow_plan_id,
        expected_workflow_version_id=workflow_version_id,
    )
    return evaluate_workflow_fixture_run_gate(
        project_status=cast(ProjectStatus, project.status),
        plan=plan,
        version=version,
        preview=validated.preview,
    ).response


@router.get(
    "/{project_id}/workflow-plans/{plan_id}/versions/{version_id}/fixture-run-gate",
    response_model=WorkflowFixtureRunGateResponse,
)
async def get_workflow_fixture_run_gate_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowFixtureRunGateResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _fixture_run_gate_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_plan_id=plan_id,
            workflow_version_id=version_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.post(
    "/{project_id}/workflow-plans/{plan_id}/versions/{version_id}/fixture-runs",
    response_model=WorkflowFixtureRunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_fixture_run_item(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: WorkflowFixtureRunCreateRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowFixtureRunCreateResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    result = await _run_operation(
        lambda: create_workflow_fixture_run(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_plan_id=plan_id,
            workflow_version_id=version_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_200_OK if result.idempotent_replay else status.HTTP_201_CREATED
    )
    return result


@router.get(
    "/{project_id}/workflow-runs",
    response_model=WorkflowRunListResponse,
)
async def list_workflow_run_items(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    workflow_plan_id: Annotated[uuid.UUID | None, Query()] = None,
    workflow_version_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkflowRunListResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _list_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_plan_id=workflow_plan_id,
            workflow_version_id=workflow_version_id,
            limit=limit,
            offset=offset,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}",
    response_model=WorkflowRunDetailResponse,
)
async def get_workflow_run_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowRunDetailResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _detail_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}/attempt-fallback-evidence",
    response_model=WorkflowAttemptFallbackEvidenceResponse,
)
async def get_workflow_run_attempt_fallback_evidence_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowAttemptFallbackEvidenceResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _attempt_fallback_evidence_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}/checkpoint-budget-evidence",
    response_model=WorkflowCheckpointBudgetEvidenceResponse,
)
async def get_workflow_run_checkpoint_budget_evidence_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowCheckpointBudgetEvidenceResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _checkpoint_budget_evidence_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}/provider-health-evidence",
    response_model=WorkflowProviderHealthEvidenceResponse,
)
async def get_workflow_run_provider_health_evidence_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowProviderHealthEvidenceResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _provider_health_evidence_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}/executor-evidence",
    response_model=WorkflowExecutorEvidenceResponse,
)
async def get_workflow_run_executor_evidence_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowExecutorEvidenceResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _executor_evidence_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}/action-gates",
    response_model=WorkflowRunActionGatesCurrentResponse,
)
async def get_workflow_run_action_gates_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowRunActionGatesCurrentResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _action_gates_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.post(
    "/{project_id}/workflow-runs/{run_id}/action-approval-receipts",
    response_model=WorkflowActionApprovalReceipt,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_run_action_approval_receipt(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: WorkflowActionApprovalRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=12, max_length=200),
    ],
) -> WorkflowActionApprovalReceipt:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    surface = await _run_operation(
        lambda: _action_surface_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    await session.rollback()
    receipt = await _run_action_operation(
        lambda: issue_workflow_action_approval(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=context.user.id,
            idempotency_key=idempotency_key,
            http_request_id=request_id,
            request=payload,
            evidence=surface.evidence,
            evaluated_at=datetime.now(UTC),
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_200_OK if receipt.idempotent_replay else status.HTTP_201_CREATED
    )
    return receipt


@router.post(
    "/{project_id}/workflow-runs/{run_id}/actions",
    response_model=WorkflowActionReceipt,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_run_action(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: WorkflowRunActionRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=12, max_length=200),
    ],
) -> WorkflowActionReceipt:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    replay = await _run_action_operation(
        lambda: find_workflow_run_action_replay(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=context.user.id,
            idempotency_key=idempotency_key,
            request=payload,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    if replay is not None:
        response.status_code = status.HTTP_200_OK
        return replay
    surface = await _run_operation(
        lambda: _action_surface_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    await session.rollback()
    receipt = await _run_action_operation(
        lambda: execute_workflow_run_action(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=context.user.id,
            idempotency_key=idempotency_key,
            http_request_id=request_id,
            request=payload,
            evidence=surface.evidence,
            evaluated_at=datetime.now(UTC),
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_200_OK if receipt.idempotent_replay else status.HTTP_201_CREATED
    )
    return receipt


@router.get(
    "/{project_id}/workflow-runs/{run_id}/shadow-comparisons",
    response_model=WorkflowShadowComparisonListResponse,
)
async def get_workflow_run_shadow_comparisons_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowShadowComparisonListResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _shadow_comparison_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.get(
    "/{project_id}/workflow-runs/{run_id}/lineage-preview",
    response_model=WorkflowRunLineagePreview,
)
async def get_workflow_run_lineage_preview_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowRunLineagePreview:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _run_operation(
        lambda: _lineage_preview_response(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            run_id=run_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )


@router.post(
    "/{project_id}/workflow-runs/{run_id}/materializations",
    response_model=WorkflowLineageMaterializationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_lineage_materialization_item(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: WorkflowLineageMaterializationRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: IdempotencyKeyDep,
) -> WorkflowLineageMaterializationResponse:
    request_id = _request_id(request)
    response.headers["X-Request-ID"] = request_id
    result = await _run_operation(
        lambda: materialize_workflow_lineage(
            session=session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            workflow_run_id=run_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        ),
        request_id=request_id,
        project_id=project_id,
    )
    response.status_code = (
        status.HTTP_200_OK if result.idempotent_replay else status.HTTP_201_CREATED
    )
    return result


__all__ = ["router"]

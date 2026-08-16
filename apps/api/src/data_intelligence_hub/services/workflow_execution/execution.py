from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    StepRunAttempt,
    WorkflowFallbackDecision,
    WorkflowRun,
    WorkflowRunRequest,
    WorkflowShadowComparison,
)
from data_intelligence_hub.repositories.workflow_execution import (
    add_step_run_attempts,
    add_step_runs,
    add_workflow_fallback_decision,
    add_workflow_run,
    add_workflow_run_request,
    add_workflow_shadow_comparisons,
    get_completed_workflow_run_request,
    get_first_workflow_fallback_decision,
    get_project_for_update,
    get_workflow_plan_for_update,
    get_workflow_version_for_update,
)
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
    WorkflowRunResponse,
    WorkflowRunStatus,
    WorkflowStepRunResponse,
    WorkflowStepRunStatus,
    normalize_workflow_execution_idempotency_key,
)
from data_intelligence_hub.schemas.workflow_planner import AuthReadiness, RoutePlanStatus
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
    WorkflowStepFixtureIdentity,
    compute_workflow_step_input_digest,
)
from data_intelligence_hub.services.workflow_execution.fallback import (
    FallbackDecisionDraft,
    FallbackGateReplayInput,
    compile_fallback_gate_replay,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixtureStepReceipt,
    execute_workflow_fixture_step,
    load_workflow_fixture_profile,
)
from data_intelligence_hub.services.workflow_execution.integrity import (
    validate_workflow_version_snapshot,
)
from data_intelligence_hub.services.workflow_execution.retry import (
    WorkflowStepAttemptReceipt,
    WorkflowStepRetryPolicy,
    execute_workflow_step_with_retry,
)
from data_intelligence_hub.services.workflow_execution.run_gate import (
    require_workflow_fixture_run_gate,
)
from data_intelligence_hub.services.workflow_execution.shadow import (
    WorkflowShadowComparisonDraft,
    compile_workflow_fixture_shadow_comparison,
)
from data_intelligence_hub.services.workflow_execution.state_machine import (
    advance_workflow_run_status,
    advance_workflow_step_status,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id


class WorkflowExecutionTransactionStateError(ValueError):
    """The caller Session contains mutations the service must not own."""


class WorkflowExecutionProjectNotFoundError(LookupError):
    """The Project is not visible inside the requested tenant."""


class WorkflowExecutionProjectNotActiveError(ValueError):
    """A new fixture Run requires an active Project."""


class WorkflowExecutionPlanNotFoundError(LookupError):
    """The WorkflowPlan is not visible inside the requested tenant path."""


class WorkflowExecutionVersionNotFoundError(LookupError):
    """The immutable WorkflowVersion is not owned by the requested Plan path."""


class WorkflowExecutionLineageInvalidError(ValueError):
    """The immutable Version cannot provide a complete Template lineage pair."""


class WorkflowExecutionRunNotFoundError(LookupError):
    """The WorkflowRun is not visible inside the requested tenant path."""


class WorkflowExecutionIdempotencyConflictError(ValueError):
    """The same actor/path/key was already bound to a different request."""


class WorkflowExecutionStepFailedError(RuntimeError):
    """A recognized terminal or exhausted step failure stopped the Run."""


class WorkflowExecutionFallbackBlockedError(WorkflowExecutionStepFailedError):
    """Primary failed and the recorded Fallback gate replay did not authorize a switch."""

    def __init__(
        self,
        error_code: str,
        *,
        decision: FallbackDecisionDraft | None,
        step_ref: str,
        requirement_ref: str,
    ) -> None:
        self.decision = decision
        self.step_ref = step_ref
        self.requirement_ref = requirement_ref
        super().__init__(error_code)


FIXTURE_STEP_RETRY_POLICY = WorkflowStepRetryPolicy(
    max_attempts=3,
    attempt_timeout_seconds=5,
    base_backoff_ms=10,
    max_backoff_ms=50,
)


@dataclass(frozen=True, slots=True)
class _PreparedStep:
    contract: PrimaryExecutionContract
    receipt: WorkflowFixtureStepReceipt
    input_digest: str


def _build_shadow_comparison(
    *,
    draft: WorkflowShadowComparisonDraft,
    step: StepRun,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    timestamp: datetime,
) -> WorkflowShadowComparison:
    return WorkflowShadowComparison(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=step.workflow_run_id,
        step_run_id=step.id,
        requirement_ref=step.requirement_ref,
        contract_version=draft.contract_version,
        comparison_digest=draft.comparison_digest,
        primary_implementation_id=draft.primary_implementation_id,
        shadow_implementation_id=draft.shadow_implementation_id,
        fixture_profile_id=draft.fixture_profile_id,
        fixture_profile_hash=draft.fixture_profile_hash,
        primary_fixture_case_id=draft.primary_fixture_case_id,
        primary_fixture_content_hash=draft.primary_fixture_content_hash,
        shadow_fixture_case_id=draft.shadow_fixture_case_id,
        shadow_fixture_content_hash=draft.shadow_fixture_content_hash,
        sample_rate=draft.sample_rate,
        max_items=draft.max_items,
        sampled_items=draft.sampled_items,
        matched_items=draft.matched_items,
        mismatched_items=draft.mismatched_items,
        primary_only_items=draft.primary_only_items,
        shadow_only_items=draft.shadow_only_items,
        equivalence_status=draft.equivalence_status,
        difference_evidence=draft.difference_evidence.model_dump(mode="json"),
        routing_recommendation=draft.routing_recommendation,
        evidence_refs=list(draft.evidence_refs),
        catalog_mutation_applied=False,
        route_ranking_mutation_applied=False,
        provider_call_attempted=False,
        credential_read_attempted=False,
        actor_run=False,
        browser_run=False,
        llm_call=False,
        production_write_allowed=False,
        created_at=timestamp,
    )


def is_workflow_run_idempotency_unique_violation(exc: IntegrityError) -> bool:
    origin = exc.orig
    if origin is None:
        return False
    cause = origin.__cause__
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    if sqlstate is None and cause is not None:
        sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
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
    return constraint_name == "uq_workflow_run_requests_idempotency"


def _replay_response(
    completed: WorkflowRunRequest,
    *,
    request_hash: str,
) -> WorkflowFixtureRunCreateResponse:
    if completed.request_hash != request_hash:
        raise WorkflowExecutionIdempotencyConflictError("idempotency_conflict")
    original = WorkflowFixtureRunCreateResponse.model_validate(completed.response_payload)
    return original.model_copy(
        update={
            "database_write": False,
            "idempotent_replay": True,
        },
        deep=True,
    )


async def _recover_idempotency_race(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    error: IntegrityError,
) -> WorkflowFixtureRunCreateResponse:
    async with session.begin():
        completed = await get_completed_workflow_run_request(
            session,
            workspace_id,
            project_id,
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
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
    attempt: Callable[[], Awaitable[WorkflowFixtureRunCreateResponse]],
) -> WorkflowFixtureRunCreateResponse:
    try:
        return await attempt()
    except IntegrityError as exc:
        if not is_workflow_run_idempotency_unique_violation(exc):
            raise
        return await _recover_idempotency_race(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            error=exc,
        )


async def _prepare_service_transaction(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise WorkflowExecutionTransactionStateError("workflow_execution_transaction_state_invalid")
    if session.in_transaction():
        await session.rollback()


def _request_scope(
    *,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> str:
    return (
        f"POST:/api/projects/{project_id}/workflow-plans/{workflow_plan_id}/"
        f"versions/{workflow_version_id}/fixture-runs"
    )


def _request_hash(
    *,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    payload: WorkflowFixtureRunCreateRequest,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "method": "POST",
                "route": {
                    "project_id": str(project_id),
                    "workflow_plan_id": str(workflow_plan_id),
                    "workflow_version_id": str(workflow_version_id),
                    "resource": "fixture-runs",
                },
                "body": payload.model_dump(mode="json"),
            },
        )
    )


def _idempotency_key_hash(idempotency_key: str) -> str:
    normalized = normalize_workflow_execution_idempotency_key(idempotency_key)
    return sha256_id(cast(JsonValue, normalized))


def _step_idempotency_key_hash(
    *,
    workflow_run_id: uuid.UUID,
    prepared: _PreparedStep,
) -> str:
    contract = prepared.contract
    return sha256_id(
        cast(
            JsonValue,
            {
                "workflow_run_id": str(workflow_run_id),
                "step_ref": contract.step.step_ref,
                "requirement_ref": contract.requirement.requirement_ref,
                "implementation_id": contract.primary.implementation_id,
                "input_digest": prepared.input_digest,
            },
        )
    )


def _retry_step_key_hash(
    *,
    request_idempotency_key_hash: str,
    workflow_version_id: uuid.UUID,
    contract: PrimaryExecutionContract,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "request_idempotency_key_hash": request_idempotency_key_hash,
                "workflow_version_id": str(workflow_version_id),
                "step_ref": contract.step.step_ref,
                "requirement_ref": contract.requirement.requirement_ref,
                "implementation_id": contract.primary.implementation_id,
            },
        )
    )


def _fallback_response_error_code(primary_failure_code: str) -> str:
    if primary_failure_code in {
        "step_network_unavailable",
        "step_rate_limited",
        "step_timeout",
    }:
        return "workflow_step_retry_exhausted"
    return primary_failure_code


def _build_fixture_fallback_decision(
    *,
    contract: PrimaryExecutionContract,
    primary_failure_code: str,
    policy_version: str,
) -> FallbackDecisionDraft:
    route = contract.route_plan
    fallback = next(iter(route.fallback_implementations), None)
    replay = FallbackGateReplayInput(
        primary_failure_code=primary_failure_code,
        primary_assertion_id=contract.primary.assertion_id,
        primary_implementation_id=contract.primary.implementation_id,
        fallback_assertion_id=fallback.assertion_id if fallback is not None else None,
        fallback_implementation_id=(fallback.implementation_id if fallback is not None else None),
        fallback_capability_status=(fallback.capability_status if fallback is not None else None),
        fallback_route_eligible=bool(fallback and fallback.route_eligible),
        credential_status=(
            fallback.readiness_status if fallback is not None else AuthReadiness.NOT_CHECKED
        ),
        policy_authorized=bool(
            fallback and route.status is RoutePlanStatus.RESOLVED and route.route_eligible
        ),
        policy_evidence_refs=[f"policy-version:{policy_version}"],
        budget_evidence_status="unavailable",
        budget_unit_cost_usd=None,
        budget_ceiling_usd=(
            contract.requirement.budget_ceiling.amount
            if contract.requirement.budget_ceiling is not None
            else None
        ),
        field_evidence_status="unavailable",
        required_fields=list(route.required_fields),
        missing_required_fields=[],
        primary_missing_optional_fields=list(contract.primary.missing_optional_fields),
        fallback_missing_optional_fields=(
            list(fallback.missing_optional_fields) if fallback is not None else []
        ),
        fallback_evidence_refs=(list(fallback.evidence_refs) if fallback is not None else []),
        approval_required=bool(fallback and fallback.approval_required),
        approval_status=(
            "pending" if fallback is not None and fallback.approval_required else "not_required"
        ),
        approval_reasons=(
            [item.code for item in fallback.approval_reasons] if fallback is not None else []
        ),
    )
    return compile_fallback_gate_replay(replay)


def _terminal_success_run_status(records_count: int) -> WorkflowRunStatus:
    running = advance_workflow_run_status(
        WorkflowRunStatus.READY,
        WorkflowRunStatus.RUNNING,
    )
    terminal = WorkflowRunStatus.COMPLETED if records_count > 0 else WorkflowRunStatus.EMPTY_VALID
    return advance_workflow_run_status(running, terminal)


def _completed_step_status() -> WorkflowStepRunStatus:
    running = advance_workflow_step_status(
        WorkflowStepRunStatus.PENDING,
        WorkflowStepRunStatus.RUNNING,
    )
    return advance_workflow_step_status(running, WorkflowStepRunStatus.COMPLETED)


def _failed_step_status() -> WorkflowStepRunStatus:
    running = advance_workflow_step_status(
        WorkflowStepRunStatus.PENDING,
        WorkflowStepRunStatus.RUNNING,
    )
    return advance_workflow_step_status(running, WorkflowStepRunStatus.FAILED)


def _failed_step_input_digest(
    *,
    contract: PrimaryExecutionContract,
    workflow_version_id: uuid.UUID,
    preview_fingerprint: str,
    fixture_profile_hash: str,
) -> str:
    return sha256_id(
        cast(
            JsonValue,
            {
                "schema_version": "workflow_failed_step_input.v1",
                "workflow_version_id": str(workflow_version_id),
                "preview_fingerprint": preview_fingerprint,
                "fixture_profile_hash": fixture_profile_hash,
                "step_ref": contract.step.step_ref,
                "requirement_ref": contract.requirement.requirement_ref,
                "assertion_id": contract.primary.assertion_id,
                "implementation_id": contract.primary.implementation_id,
            },
        )
    )


def _build_step_run(
    *,
    prepared: _PreparedStep,
    workflow_run_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    timestamp: datetime,
) -> StepRun:
    contract = prepared.contract
    receipt = prepared.receipt
    return StepRun(
        id=uuid.uuid4(),
        workflow_run_id=workflow_run_id,
        workspace_id=workspace_id,
        project_id=project_id,
        step_ref=contract.step.step_ref,
        requirement_ref=contract.requirement.requirement_ref,
        sequence=contract.step.sequence,
        platform=contract.requirement.platform.value,
        resource_type=contract.requirement.resource_type.value,
        operation=contract.requirement.operation.value,
        assertion_id=contract.primary.assertion_id,
        implementation_id=contract.primary.implementation_id,
        route_plan_snapshot=contract.route_plan.model_dump(mode="json"),
        evidence_refs=list(contract.primary.evidence_refs),
        fixture_case_id=receipt.fixture_case_id,
        fixture_content_hash=receipt.fixture_content_hash,
        input_digest=prepared.input_digest,
        output_digest=receipt.output_digest,
        idempotency_scope=f"workflow_fixture_step:{workflow_run_id}",
        idempotency_key_hash=_step_idempotency_key_hash(
            workflow_run_id=workflow_run_id,
            prepared=prepared,
        ),
        status=_completed_step_status().value,
        records_count=receipt.records_count,
        provider_call_attempted=False,
        credential_read_attempted=False,
        actor_run=False,
        browser_run=False,
        llm_call=False,
        production_write_allowed=False,
        started_at=timestamp,
        finished_at=timestamp,
        created_at=timestamp,
    )


def _build_failed_step_run(
    *,
    contract: PrimaryExecutionContract,
    workflow_run_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    preview_fingerprint: str,
    fixture_profile_hash: str,
    request_idempotency_key_hash: str,
    attempts: tuple[WorkflowStepAttemptReceipt, ...],
    timestamp: datetime,
) -> StepRun:
    started_at = attempts[0].started_at if attempts else timestamp
    finished_at = attempts[-1].finished_at if attempts else timestamp
    return StepRun(
        id=uuid.uuid4(),
        workflow_run_id=workflow_run_id,
        workspace_id=workspace_id,
        project_id=project_id,
        step_ref=contract.step.step_ref,
        requirement_ref=contract.requirement.requirement_ref,
        sequence=contract.step.sequence,
        platform=contract.requirement.platform.value,
        resource_type=contract.requirement.resource_type.value,
        operation=contract.requirement.operation.value,
        assertion_id=contract.primary.assertion_id,
        implementation_id=contract.primary.implementation_id,
        route_plan_snapshot=contract.route_plan.model_dump(mode="json"),
        evidence_refs=list(contract.primary.evidence_refs),
        fixture_case_id=None,
        fixture_content_hash=None,
        input_digest=_failed_step_input_digest(
            contract=contract,
            workflow_version_id=workflow_version_id,
            preview_fingerprint=preview_fingerprint,
            fixture_profile_hash=fixture_profile_hash,
        ),
        output_digest=None,
        idempotency_scope=f"workflow_fixture_step:{workflow_run_id}",
        idempotency_key_hash=_retry_step_key_hash(
            request_idempotency_key_hash=request_idempotency_key_hash,
            workflow_version_id=workflow_version_id,
            contract=contract,
        ),
        status=_failed_step_status().value,
        records_count=0,
        provider_call_attempted=False,
        credential_read_attempted=False,
        actor_run=False,
        browser_run=False,
        llm_call=False,
        production_write_allowed=False,
        started_at=started_at,
        finished_at=finished_at,
        created_at=timestamp,
    )


def _build_step_run_attempts(
    *,
    step: StepRun,
    receipts: tuple[WorkflowStepAttemptReceipt, ...],
) -> tuple[StepRunAttempt, ...]:
    return tuple(
        StepRunAttempt(
            id=uuid.uuid4(),
            workspace_id=step.workspace_id,
            project_id=step.project_id,
            workflow_run_id=step.workflow_run_id,
            step_run_id=step.id,
            attempt_number=receipt.attempt_number,
            attempt_key_hash=receipt.attempt_key_hash,
            status=receipt.status,
            error_code=receipt.error_code,
            backoff_ms=receipt.backoff_ms,
            provider_call_attempted=False,
            credential_read_attempted=False,
            actor_run=False,
            browser_run=False,
            llm_call=False,
            production_write_allowed=False,
            started_at=receipt.started_at,
            finished_at=receipt.finished_at,
            created_at=receipt.finished_at,
        )
        for receipt in receipts
    )


def _create_response(
    run: WorkflowRun,
    steps: tuple[StepRun, ...],
    *,
    workflow_template_id: uuid.UUID | None = None,
    workflow_template_revision_id: uuid.UUID | None = None,
) -> WorkflowFixtureRunCreateResponse:
    run_response = WorkflowRunResponse.model_validate(
        {
            **WorkflowRunResponse.model_validate(run).model_dump(mode="json"),
            "workflow_template_id": workflow_template_id,
            "workflow_template_revision_id": workflow_template_revision_id,
        }
    )
    return WorkflowFixtureRunCreateResponse(
        database_write=True,
        idempotent_replay=False,
        run=run_response,
        steps=[WorkflowStepRunResponse.model_validate(item) for item in steps],
    )


async def _create_workflow_fixture_run_attempt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowFixtureRunCreateRequest,
    timestamp: datetime,
    idempotency_scope: str,
    idempotency_key_hash: str,
    request_hash: str,
) -> WorkflowFixtureRunCreateResponse:
    async with session.begin():
        completed = await get_completed_workflow_run_request(
            session,
            workspace_id,
            project_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)

        fallback_decision = await get_first_workflow_fallback_decision(
            session,
            workspace_id,
            project_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if fallback_decision is not None:
            if fallback_decision.request_hash != request_hash:
                raise WorkflowExecutionIdempotencyConflictError("idempotency_conflict")
            raise WorkflowExecutionFallbackBlockedError(
                _fallback_response_error_code(fallback_decision.primary_failure_code),
                decision=None,
                step_ref=fallback_decision.step_ref,
                requirement_ref=fallback_decision.requirement_ref,
            )

        project = await get_project_for_update(session, workspace_id, project_id)
        if project is None:
            raise WorkflowExecutionProjectNotFoundError("project_not_found")
        if project.status != "active":
            raise WorkflowExecutionProjectNotActiveError("project_not_active")

        completed = await get_completed_workflow_run_request(
            session,
            workspace_id,
            project_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if completed is not None:
            return _replay_response(completed, request_hash=request_hash)

        fallback_decision = await get_first_workflow_fallback_decision(
            session,
            workspace_id,
            project_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
        if fallback_decision is not None:
            if fallback_decision.request_hash != request_hash:
                raise WorkflowExecutionIdempotencyConflictError("idempotency_conflict")
            raise WorkflowExecutionFallbackBlockedError(
                _fallback_response_error_code(fallback_decision.primary_failure_code),
                decision=None,
                step_ref=fallback_decision.step_ref,
                requirement_ref=fallback_decision.requirement_ref,
            )

        plan = await get_workflow_plan_for_update(
            session,
            workspace_id,
            project_id,
            workflow_plan_id,
        )
        if plan is None:
            raise WorkflowExecutionPlanNotFoundError("workflow_plan_not_found")
        version = await get_workflow_version_for_update(
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
            expected_preview_fingerprint=payload.expected_preview_fingerprint,
        )
        contracts = require_workflow_fixture_run_gate(
            project_status=cast(ProjectStatus, project.status),
            plan=plan,
            version=version,
            preview=validated.preview,
        )
        fixture_profile = load_workflow_fixture_profile(payload.fixture_profile_id)
        workflow_run_id = uuid.uuid4()
        prepared_steps: list[_PreparedStep] = []
        prepared_step_attempts: list[tuple[WorkflowStepAttemptReceipt, ...]] = []
        prepared_shadow_comparisons: list[WorkflowShadowComparisonDraft | None] = []
        for contract in contracts:

            async def execute_step(
                attempt_number: int,
                attempt_key_hash: str,
                *,
                target: PrimaryExecutionContract = contract,
            ) -> WorkflowFixtureStepReceipt:
                del attempt_number, attempt_key_hash
                return execute_workflow_fixture_step(fixture_profile, target)

            retry_result = await execute_workflow_step_with_retry(
                step_idempotency_key_hash=_retry_step_key_hash(
                    request_idempotency_key_hash=idempotency_key_hash,
                    workflow_version_id=workflow_version_id,
                    contract=contract,
                ),
                policy=FIXTURE_STEP_RETRY_POLICY,
                executor=execute_step,
                clock=lambda: timestamp,
            )
            if retry_result.status == "failed" or retry_result.value is None:
                primary_failure_code = (
                    retry_result.attempts[-1].error_code
                    if retry_result.attempts and retry_result.attempts[-1].error_code is not None
                    else retry_result.error_code or "workflow_step_failed"
                )
                decision = _build_fixture_fallback_decision(
                    contract=contract,
                    primary_failure_code=primary_failure_code,
                    policy_version=version.policy_version,
                )
                if decision.outcome != "blocked":
                    raise RuntimeError("fixture_fallback_switch_not_implemented")
                completed_steps = tuple(
                    _build_step_run(
                        prepared=item,
                        workflow_run_id=workflow_run_id,
                        workspace_id=workspace_id,
                        project_id=project_id,
                        timestamp=timestamp,
                    )
                    for item in prepared_steps
                )
                failed_step = _build_failed_step_run(
                    contract=contract,
                    workflow_run_id=workflow_run_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    workflow_version_id=workflow_version_id,
                    preview_fingerprint=version.preview_fingerprint,
                    fixture_profile_hash=fixture_profile.profile_hash,
                    request_idempotency_key_hash=idempotency_key_hash,
                    attempts=retry_result.attempts,
                    timestamp=timestamp,
                )
                steps = (*completed_steps, failed_step)
                run = WorkflowRun(
                    id=workflow_run_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    workflow_plan_id=workflow_plan_id,
                    workflow_version_id=workflow_version_id,
                    created_by_user_id=created_by_user_id,
                    execution_contract_version="workflow_execution_fixture.v1",
                    execution_mode="fixture",
                    status=advance_workflow_run_status(
                        WorkflowRunStatus.RUNNING,
                        WorkflowRunStatus.HELD,
                    ).value,
                    planner_contract_version=version.planner_contract_version,
                    preview_fingerprint=version.preview_fingerprint,
                    catalog_snapshot_id=version.catalog_snapshot_id,
                    policy_version=version.policy_version,
                    mode_template_version=version.mode_template_version,
                    query_versions=dict(version.query_versions),
                    fixture_profile_id=fixture_profile.profile.profile_id,
                    fixture_profile_hash=fixture_profile.profile_hash,
                    total_steps=len(contracts),
                    completed_steps=len(completed_steps),
                    records_count=sum(item.receipt.records_count for item in prepared_steps),
                    status_reason_code="fallback_blocked",
                    impact_code="step_not_completed_following_steps_not_started",
                    missing_fields=list(decision.field_difference.missing_required_fields),
                    recovery_action_codes=[
                        "inspect_fallback_gate_evidence",
                        "resolve_primary_failure",
                    ],
                    provider_call_attempted=False,
                    credential_read_attempted=False,
                    actor_run=False,
                    browser_run=False,
                    llm_call=False,
                    production_write_allowed=False,
                    started_at=timestamp,
                    finished_at=None,
                    created_at=timestamp,
                )
                await add_workflow_run(session, run)
                await add_step_runs(session, steps)
                attempts = tuple(
                    attempt
                    for step, receipts in zip(
                        completed_steps,
                        prepared_step_attempts,
                        strict=True,
                    )
                    for attempt in _build_step_run_attempts(
                        step=step,
                        receipts=receipts,
                    )
                ) + _build_step_run_attempts(
                    step=failed_step,
                    receipts=retry_result.attempts,
                )
                await add_step_run_attempts(session, attempts)
                shadow_comparisons = tuple(
                    _build_shadow_comparison(
                        draft=draft,
                        step=step,
                        workspace_id=workspace_id,
                        project_id=project_id,
                        timestamp=timestamp,
                    )
                    for step, draft in zip(
                        completed_steps,
                        prepared_shadow_comparisons,
                        strict=True,
                    )
                    if draft is not None
                )
                await add_workflow_shadow_comparisons(session, shadow_comparisons)
                await add_workflow_fallback_decision(
                    session,
                    WorkflowFallbackDecision(
                        workspace_id=workspace_id,
                        project_id=project_id,
                        workflow_plan_id=workflow_plan_id,
                        workflow_version_id=workflow_version_id,
                        workflow_run_id=workflow_run_id,
                        step_run_id=failed_step.id,
                        created_by_user_id=created_by_user_id,
                        idempotency_scope=idempotency_scope,
                        idempotency_key_hash=idempotency_key_hash,
                        request_hash=request_hash,
                        step_ref=contract.step.step_ref,
                        requirement_ref=contract.requirement.requirement_ref,
                        contract_version=decision.contract_version,
                        decision_digest=decision.decision_digest,
                        primary_failure_code=decision.primary_failure_code,
                        primary_assertion_id=decision.primary_assertion_id,
                        primary_implementation_id=decision.primary_implementation_id,
                        fallback_assertion_id=decision.fallback_assertion_id,
                        fallback_implementation_id=decision.fallback_implementation_id,
                        outcome=decision.outcome,
                        gate_snapshot=[item.model_dump(mode="json") for item in decision.gates],
                        field_difference=decision.field_difference.model_dump(mode="json"),
                        cost_snapshot=decision.cost_snapshot.model_dump(mode="json"),
                        evidence_refs=list(decision.evidence_refs),
                        approval_required=decision.approval_required,
                        approval_status=decision.approval_status,
                        switch_executed=False,
                        provider_call_attempted=False,
                        credential_read_attempted=False,
                        actor_run=False,
                        browser_run=False,
                        llm_call=False,
                        production_write_allowed=False,
                        created_at=timestamp,
                    ),
                )
                response = _create_response(
                    run,
                    steps,
                    workflow_template_id=version.workflow_template_id,
                    workflow_template_revision_id=version.workflow_template_revision_id,
                )
                await add_workflow_run_request(
                    session,
                    WorkflowRunRequest(
                        workspace_id=workspace_id,
                        project_id=project_id,
                        created_by_user_id=created_by_user_id,
                        idempotency_scope=idempotency_scope,
                        idempotency_key_hash=idempotency_key_hash,
                        request_hash=request_hash,
                        workflow_run_id=workflow_run_id,
                        outcome="held",
                        response_status=201,
                        response_payload=response.model_dump(mode="json"),
                        created_at=timestamp,
                    ),
                )
                return response
            receipt = retry_result.value
            fixture_identity = WorkflowStepFixtureIdentity(
                fixture_profile_hash=fixture_profile.profile_hash,
                fixture_case_id=receipt.fixture_case_id,
                fixture_content_hash=receipt.fixture_content_hash,
            )
            prepared_steps.append(
                _PreparedStep(
                    contract=contract,
                    receipt=receipt,
                    input_digest=compute_workflow_step_input_digest(
                        contract,
                        workflow_version_id=workflow_version_id,
                        preview_fingerprint=version.preview_fingerprint,
                        fixture=fixture_identity,
                    ),
                )
            )
            prepared_step_attempts.append(retry_result.attempts)
            prepared_shadow_comparisons.append(
                compile_workflow_fixture_shadow_comparison(
                    fixture_profile,
                    contract,
                    receipt,
                )
            )

        total_records = sum(item.receipt.records_count for item in prepared_steps)
        run = WorkflowRun(
            id=workflow_run_id,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_plan_id=workflow_plan_id,
            workflow_version_id=workflow_version_id,
            created_by_user_id=created_by_user_id,
            execution_contract_version="workflow_execution_fixture.v1",
            execution_mode="fixture",
            status=_terminal_success_run_status(total_records).value,
            planner_contract_version=version.planner_contract_version,
            preview_fingerprint=version.preview_fingerprint,
            catalog_snapshot_id=version.catalog_snapshot_id,
            policy_version=version.policy_version,
            mode_template_version=version.mode_template_version,
            query_versions=dict(version.query_versions),
            fixture_profile_id=fixture_profile.profile.profile_id,
            fixture_profile_hash=fixture_profile.profile_hash,
            total_steps=len(prepared_steps),
            completed_steps=len(prepared_steps),
            records_count=total_records,
            status_reason_code=(None if total_records > 0 else "verified_zero_result"),
            impact_code=(None if total_records > 0 else "no_records_in_scope"),
            missing_fields=[],
            recovery_action_codes=[],
            provider_call_attempted=False,
            credential_read_attempted=False,
            actor_run=False,
            browser_run=False,
            llm_call=False,
            production_write_allowed=False,
            started_at=timestamp,
            finished_at=timestamp,
            created_at=timestamp,
        )
        steps = tuple(
            _build_step_run(
                prepared=item,
                workflow_run_id=workflow_run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                timestamp=timestamp,
            )
            for item in prepared_steps
        )
        await add_workflow_run(session, run)
        for step in steps:
            await add_step_runs(session, (step,))
        attempts = tuple(
            attempt
            for step, receipts in zip(steps, prepared_step_attempts, strict=True)
            for attempt in _build_step_run_attempts(step=step, receipts=receipts)
        )
        await add_step_run_attempts(session, attempts)
        shadow_comparisons = tuple(
            _build_shadow_comparison(
                draft=draft,
                step=step,
                workspace_id=workspace_id,
                project_id=project_id,
                timestamp=timestamp,
            )
            for step, draft in zip(
                steps,
                prepared_shadow_comparisons,
                strict=True,
            )
            if draft is not None
        )
        await add_workflow_shadow_comparisons(session, shadow_comparisons)
        response = _create_response(
            run,
            steps,
            workflow_template_id=version.workflow_template_id,
            workflow_template_revision_id=version.workflow_template_revision_id,
        )
        await add_workflow_run_request(
            session,
            WorkflowRunRequest(
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=created_by_user_id,
                idempotency_scope=idempotency_scope,
                idempotency_key_hash=idempotency_key_hash,
                request_hash=request_hash,
                workflow_run_id=workflow_run_id,
                outcome="completed",
                response_status=201,
                response_payload=response.model_dump(mode="json"),
                created_at=timestamp,
            ),
        )
        return response


async def create_workflow_fixture_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkflowFixtureRunCreateRequest,
    idempotency_key: str,
    request_id: str,
    generated_at: datetime | None = None,
) -> WorkflowFixtureRunCreateResponse:
    del request_id
    timestamp = generated_at or datetime.now(UTC)
    idempotency_scope = _request_scope(
        project_id=project_id,
        workflow_plan_id=workflow_plan_id,
        workflow_version_id=workflow_version_id,
    )
    idempotency_key_hash = _idempotency_key_hash(idempotency_key)
    request_hash = _request_hash(
        project_id=project_id,
        workflow_plan_id=workflow_plan_id,
        workflow_version_id=workflow_version_id,
        payload=payload,
    )
    await _prepare_service_transaction(session)

    async def attempt() -> WorkflowFixtureRunCreateResponse:
        return await _create_workflow_fixture_run_attempt(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_plan_id=workflow_plan_id,
            workflow_version_id=workflow_version_id,
            created_by_user_id=created_by_user_id,
            payload=payload,
            timestamp=timestamp,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
        )

    try:
        return await _run_with_idempotency_race_recovery(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            created_by_user_id=created_by_user_id,
            idempotency_scope=idempotency_scope,
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
            attempt=attempt,
        )
    except WorkflowExecutionFallbackBlockedError as exc:
        if exc.decision is not None:
            decision = exc.decision
            async with session.begin():
                await add_workflow_fallback_decision(
                    session,
                    WorkflowFallbackDecision(
                        workspace_id=workspace_id,
                        project_id=project_id,
                        workflow_plan_id=workflow_plan_id,
                        workflow_version_id=workflow_version_id,
                        created_by_user_id=created_by_user_id,
                        idempotency_scope=idempotency_scope,
                        idempotency_key_hash=idempotency_key_hash,
                        request_hash=request_hash,
                        step_ref=exc.step_ref,
                        requirement_ref=exc.requirement_ref,
                        contract_version=decision.contract_version,
                        decision_digest=decision.decision_digest,
                        primary_failure_code=decision.primary_failure_code,
                        primary_assertion_id=decision.primary_assertion_id,
                        primary_implementation_id=decision.primary_implementation_id,
                        fallback_assertion_id=decision.fallback_assertion_id,
                        fallback_implementation_id=decision.fallback_implementation_id,
                        outcome=decision.outcome,
                        gate_snapshot=[item.model_dump(mode="json") for item in decision.gates],
                        field_difference=decision.field_difference.model_dump(mode="json"),
                        cost_snapshot=decision.cost_snapshot.model_dump(mode="json"),
                        evidence_refs=list(decision.evidence_refs),
                        approval_required=decision.approval_required,
                        approval_status=decision.approval_status,
                        switch_executed=False,
                        provider_call_attempted=False,
                        credential_read_attempted=False,
                        actor_run=False,
                        browser_run=False,
                        llm_call=False,
                        production_write_allowed=False,
                        created_at=timestamp,
                    ),
                )
        raise


__all__ = [
    "WorkflowExecutionIdempotencyConflictError",
    "WorkflowExecutionFallbackBlockedError",
    "WorkflowExecutionLineageInvalidError",
    "WorkflowExecutionPlanNotFoundError",
    "WorkflowExecutionProjectNotActiveError",
    "WorkflowExecutionProjectNotFoundError",
    "WorkflowExecutionRunNotFoundError",
    "WorkflowExecutionStepFailedError",
    "WorkflowExecutionTransactionStateError",
    "WorkflowExecutionVersionNotFoundError",
    "create_workflow_fixture_run",
    "is_workflow_run_idempotency_unique_violation",
]

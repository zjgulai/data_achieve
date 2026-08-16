from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, cast

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionApprovalConsumption,
    WorkflowRunActionApprovalReceiptRecord,
    WorkflowRunActionAuditEvent,
    WorkflowRunActionContext,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowRun,
    WorkflowStepCheckpoint,
)
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.workflow_action_command import (
    BudgetOverrideActionParameters,
    CancelActionParameters,
    ResumeActionParameters,
    RetryActionParameters,
    RouteSwitchActionParameters,
    WorkflowActionApprovalReceipt,
    WorkflowActionApprovalRequest,
    WorkflowActionReceipt,
    WorkflowRunActionRequest,
    canonical_workflow_action_proposal_hash,
    canonical_workflow_action_request_hash,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from data_intelligence_hub.services.workflow_execution.action_authorization import (
    WorkflowActionStateContext,
    authorize_workflow_action,
    compile_workflow_action_state_effect,
)
from data_intelligence_hub.services.workflow_execution.executor_composition import (
    ExecutorCompositionError,
    add_action_dispatches_for_accepted_action,
)

_IDEMPOTENCY_KEY_RE = re.compile(r"^[\x21-\x7e]{1,200}$")


class WorkflowActionCommandError(RuntimeError):
    """A fixed, sanitized Phase C service failure."""

    def __init__(self, code: str, *, status: int) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkflowActionCommandEvidence:
    """Trusted fixture evidence re-evaluated by the local command service."""

    action_gate_digest: str
    evidence_digests: tuple[str, ...]
    retry_policy_available: bool = False
    retry_generation_limit: int = 3
    checkpoint_available: bool = False
    checkpoint_terminal: bool = False
    budget_within_limit: bool = False
    failed_step_requires_retry: bool = False
    budget_held: bool = False
    route_switch_eligible: bool = False
    budget_current_request_count: int = 0
    budget_current_item_count: int = 0
    budget_current_quota_units: int = 0
    budget_current_cost_usd: Decimal = Decimal("0")
    budget_current_elapsed_ms: int = 0
    provider_call: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    execution_started: Literal[False] = False
    production_write_allowed: Literal[False] = False

    def __post_init__(self) -> None:
        values = (self.action_gate_digest, *self.evidence_digests)
        if any(not _is_digest(value) for value in values):
            raise ValueError("workflow_action_evidence_digest_invalid")
        if not self.evidence_digests or len(self.evidence_digests) != len(
            set(self.evidence_digests)
        ):
            raise ValueError("workflow_action_evidence_digests_invalid")
        if self.retry_generation_limit < 0:
            raise ValueError("workflow_action_retry_generation_limit_invalid")
        numeric_values = (
            self.budget_current_request_count,
            self.budget_current_item_count,
            self.budget_current_quota_units,
            self.budget_current_elapsed_ms,
        )
        if any(value < 0 for value in numeric_values) or self.budget_current_cost_usd < 0:
            raise ValueError("workflow_action_budget_usage_invalid")


def _is_digest(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _idempotency_key_hash(value: str) -> str:
    normalized = value.strip()
    if not _IDEMPOTENCY_KEY_RE.fullmatch(normalized):
        raise WorkflowActionCommandError(
            "workflow_action_idempotency_key_invalid",
            status=422,
        )
    return f"sha256:{hashlib.sha256(normalized.encode()).hexdigest()}"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _approval_scope(project_id: uuid.UUID, workflow_run_id: uuid.UUID) -> str:
    return f"workflow_action_approval.v1:{project_id}:{workflow_run_id}"


def _action_scope(project_id: uuid.UUID, workflow_run_id: uuid.UUID) -> str:
    return f"workflow_run_action.v1:{project_id}:{workflow_run_id}"


def _approval_schema(
    record: WorkflowRunActionApprovalReceiptRecord,
    *,
    database_write: bool,
    idempotent_replay: bool,
) -> WorkflowActionApprovalReceipt:
    return WorkflowActionApprovalReceipt(
        id=record.id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        workflow_run_id=record.workflow_run_id,
        approver_user_id=record.approver_user_id,
        action=cast(Any, record.action),
        approval_kind=cast(Any, record.approval_kind),
        proposal_digest=record.proposal_digest,
        expected_action_context_version=record.expected_action_context_version,
        expected_run_status=WorkflowRunStatus(record.expected_run_status),
        action_gate_digest=record.action_gate_digest,
        evidence_digests=record.evidence_digests,
        reason_code=cast(Any, record.reason_code),
        reason=record.reason,
        issued_at=_aware(record.issued_at),
        expires_at=_aware(record.expires_at),
        database_write=database_write,
        idempotent_replay=idempotent_replay,
    )


def _receipt_schema(
    record: WorkflowRunActionReceiptRecord,
    *,
    database_write: bool,
    idempotent_replay: bool,
    created_at: datetime | None = None,
) -> WorkflowActionReceipt:
    timestamp = created_at or record.created_at
    return WorkflowActionReceipt(
        id=record.id,
        request_id=record.request_id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        workflow_run_id=record.workflow_run_id,
        action=cast(Any, record.action),
        outcome=cast(Any, record.outcome),
        before_action_context_version=record.before_action_context_version,
        after_action_context_version=record.after_action_context_version,
        before_run_status=WorkflowRunStatus(record.before_run_status),
        after_run_status=WorkflowRunStatus(record.after_run_status),
        state_changed=record.state_changed,
        database_write=database_write,
        idempotent_replay=idempotent_replay,
        next_action_code=cast(Any, record.next_action_code),
        receipt_digest=record.receipt_digest,
        created_at=_aware(timestamp),
    )


async def _locked_run_and_owner(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowRun, uuid.UUID]:
    result = await session.execute(
        select(WorkflowRun, Workspace.owner_id)
        .join(Workspace, Workspace.id == WorkflowRun.workspace_id)
        .where(
            WorkflowRun.workspace_id == workspace_id,
            WorkflowRun.project_id == project_id,
            WorkflowRun.id == workflow_run_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    row = result.one_or_none()
    if row is None:
        raise WorkflowActionCommandError("workflow_run_not_found", status=404)
    return row[0], row[1]


async def _locked_context(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> WorkflowRunActionContext:
    result = await session.execute(
        select(WorkflowRunActionContext)
        .where(
            WorkflowRunActionContext.workspace_id == workspace_id,
            WorkflowRunActionContext.project_id == project_id,
            WorkflowRunActionContext.workflow_run_id == workflow_run_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    context = result.scalar_one_or_none()
    if context is None:
        context = WorkflowRunActionContext(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            action_context_version=1,
        )
        session.add(context)
        await session.flush()
    return context


def _require_owner(actor_user_id: uuid.UUID, owner_user_id: uuid.UUID) -> None:
    if actor_user_id != owner_user_id:
        raise WorkflowActionCommandError("workflow_action_owner_required", status=403)


def _required_parameter_evidence(
    request: WorkflowActionApprovalRequest | WorkflowRunActionRequest,
) -> frozenset[str]:
    parameters = request.parameters
    if isinstance(parameters, RetryActionParameters):
        return frozenset(
            {
                parameters.attempt_evidence_digest,
                parameters.retry_policy_digest,
            }
        )
    if isinstance(parameters, ResumeActionParameters):
        return frozenset(
            {
                parameters.checkpoint_digest,
                parameters.budget_policy_digest,
                parameters.budget_ledger_digest,
            }
        )
    if isinstance(parameters, RouteSwitchActionParameters):
        return frozenset(
            {
                parameters.fallback_decision_digest,
                parameters.field_difference_digest,
                parameters.cost_digest,
                parameters.provider_health_digest,
            }
        )
    return frozenset()


def _validate_evidence_binding(
    request: WorkflowActionApprovalRequest | WorkflowRunActionRequest,
    evidence: WorkflowActionCommandEvidence,
) -> None:
    if request.action_gate_digest != evidence.action_gate_digest:
        raise WorkflowActionCommandError("workflow_action_gate_conflict", status=409)
    if not _required_parameter_evidence(request).issubset(evidence.evidence_digests):
        raise WorkflowActionCommandError("workflow_action_evidence_conflict", status=409)


def _state_payload(run: WorkflowRun, steps: tuple[StepRun, ...]) -> dict[str, object]:
    return {
        "run": {
            "id": str(run.id),
            "status": run.status,
            "status_reason_code": run.status_reason_code,
            "impact_code": run.impact_code,
            "missing_fields": run.missing_fields,
            "recovery_action_codes": run.recovery_action_codes,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
        "steps": [
            {
                "id": str(step.id),
                "status": step.status,
                "retry_generation": step.retry_generation,
                "finished_at": step.finished_at.isoformat() if step.finished_at else None,
            }
            for step in steps
        ],
    }


def _step_snapshots(steps: tuple[StepRun, ...]) -> list[dict[str, object]]:
    return [
        {
            "step_run_id": str(step.id),
            "status": step.status,
            "retry_generation": step.retry_generation,
        }
        for step in steps
    ]


async def _audit_tail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> WorkflowRunActionAuditEvent | None:
    result = await session.execute(
        select(WorkflowRunActionAuditEvent)
        .where(
            WorkflowRunActionAuditEvent.workspace_id == workspace_id,
            WorkflowRunActionAuditEvent.project_id == project_id,
            WorkflowRunActionAuditEvent.workflow_run_id == workflow_run_id,
        )
        .order_by(desc(WorkflowRunActionAuditEvent.event_number))
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _append_audit_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    event_type: str,
    reason_code: str,
    before_context_version: int,
    after_context_version: int,
    before_state_digest: str,
    after_state_digest: str,
    http_request_id: str,
    occurred_at: datetime,
    approval_receipt_id: uuid.UUID | None,
    action_request_id: uuid.UUID | None = None,
    action_receipt_id: uuid.UUID | None = None,
) -> WorkflowRunActionAuditEvent:
    tail = await _audit_tail(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
    )
    event_number = 1 if tail is None else tail.event_number + 1
    previous_digest = None if tail is None else tail.event_digest
    event_digest = _canonical_digest(
        {
            "scope": "workflow_run_action_audit.v1",
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "workflow_run_id": str(workflow_run_id),
            "event_number": event_number,
            "previous_event_digest": previous_digest,
            "event_type": event_type,
            "reason_code": reason_code,
            "before_action_context_version": before_context_version,
            "after_action_context_version": after_context_version,
            "before_state_digest": before_state_digest,
            "after_state_digest": after_state_digest,
            "approval_receipt_id": (
                str(approval_receipt_id) if approval_receipt_id is not None else None
            ),
            "action_request_id": (
                str(action_request_id) if action_request_id is not None else None
            ),
            "action_receipt_id": (
                str(action_receipt_id) if action_receipt_id is not None else None
            ),
            "occurred_at": occurred_at.isoformat(),
        }
    )
    event = WorkflowRunActionAuditEvent(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        event_number=event_number,
        previous_event_digest=previous_digest,
        event_digest=event_digest,
        action_request_id=action_request_id,
        approval_receipt_id=approval_receipt_id,
        action_receipt_id=action_receipt_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        reason_code=reason_code,
        before_action_context_version=before_context_version,
        after_action_context_version=after_context_version,
        before_state_digest=before_state_digest,
        after_state_digest=after_state_digest,
        http_request_id=http_request_id,
        occurred_at=occurred_at,
    )
    session.add(event)
    await session.flush()
    return event


async def verify_workflow_action_audit_chain(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> None:
    result = await session.execute(
        select(WorkflowRunActionAuditEvent)
        .where(
            WorkflowRunActionAuditEvent.workspace_id == workspace_id,
            WorkflowRunActionAuditEvent.project_id == project_id,
            WorkflowRunActionAuditEvent.workflow_run_id == workflow_run_id,
        )
        .order_by(
            WorkflowRunActionAuditEvent.event_number,
            WorkflowRunActionAuditEvent.id,
        )
    )
    events = tuple(result.scalars().all())
    previous_digest: str | None = None
    for expected_number, event in enumerate(events, start=1):
        expected_digest = _canonical_digest(
            {
                "scope": "workflow_run_action_audit.v1",
                "workspace_id": str(event.workspace_id),
                "project_id": str(event.project_id),
                "workflow_run_id": str(event.workflow_run_id),
                "event_number": event.event_number,
                "previous_event_digest": event.previous_event_digest,
                "event_type": event.event_type,
                "reason_code": event.reason_code,
                "before_action_context_version": event.before_action_context_version,
                "after_action_context_version": event.after_action_context_version,
                "before_state_digest": event.before_state_digest,
                "after_state_digest": event.after_state_digest,
                "approval_receipt_id": (
                    str(event.approval_receipt_id)
                    if event.approval_receipt_id is not None
                    else None
                ),
                "action_request_id": (
                    str(event.action_request_id) if event.action_request_id is not None else None
                ),
                "action_receipt_id": (
                    str(event.action_receipt_id) if event.action_receipt_id is not None else None
                ),
                "occurred_at": _aware(event.occurred_at).isoformat(),
            }
        )
        if (
            event.event_number != expected_number
            or event.previous_event_digest != previous_digest
            or event.event_digest != expected_digest
        ):
            raise WorkflowActionCommandError(
                "workflow_action_audit_chain_invalid",
                status=409,
            )
        previous_digest = event.event_digest


async def issue_workflow_action_approval(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    http_request_id: str,
    request: WorkflowActionApprovalRequest,
    evidence: WorkflowActionCommandEvidence,
    evaluated_at: datetime,
) -> WorkflowActionApprovalReceipt:
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise WorkflowActionCommandError("workflow_action_time_invalid", status=422)
    key_hash = _idempotency_key_hash(idempotency_key)
    scope = _approval_scope(project_id, workflow_run_id)
    canonical_hash = _canonical_digest(
        {
            "request": request.model_dump(mode="json"),
            "evidence_digests": list(evidence.evidence_digests),
        }
    )

    async with session.begin():
        existing_result = await session.execute(
            select(WorkflowRunActionApprovalReceiptRecord)
            .where(
                WorkflowRunActionApprovalReceiptRecord.workspace_id == workspace_id,
                WorkflowRunActionApprovalReceiptRecord.approver_user_id == actor_user_id,
                WorkflowRunActionApprovalReceiptRecord.idempotency_scope == scope,
                WorkflowRunActionApprovalReceiptRecord.idempotency_key_hash == key_hash,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            if existing.canonical_request_hash != canonical_hash:
                raise WorkflowActionCommandError(
                    "workflow_action_idempotency_conflict",
                    status=409,
                )
            return _approval_schema(
                existing,
                database_write=False,
                idempotent_replay=True,
            )

        run, owner_id = await _locked_run_and_owner(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        )
        _require_owner(actor_user_id, owner_id)
        context = await _locked_context(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        )
        if (
            request.expected_action_context_version != context.action_context_version
            or request.expected_run_status.value != run.status
        ):
            raise WorkflowActionCommandError("workflow_action_state_conflict", status=409)

        proposal_digest = canonical_workflow_action_proposal_hash(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            request=request,
        )
        approval = WorkflowRunActionApprovalReceiptRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            approver_user_id=actor_user_id,
            action=request.action,
            approval_kind=request.approval_kind,
            proposal_digest=proposal_digest,
            idempotency_scope=scope,
            idempotency_key_hash=key_hash,
            canonical_request_hash=canonical_hash,
            expected_action_context_version=request.expected_action_context_version,
            expected_run_status=request.expected_run_status.value,
            action_gate_digest=request.action_gate_digest,
            evidence_digests=list(evidence.evidence_digests),
            reason_code=request.reason_code,
            reason=request.reason,
            issued_at=evaluated_at,
            expires_at=evaluated_at + timedelta(minutes=10),
        )
        session.add(approval)
        await session.flush()
        state_digest = _canonical_digest(_state_payload(run, ()))
        await _append_audit_event(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            actor_user_id=actor_user_id,
            event_type="approval_issued",
            reason_code=request.reason_code,
            before_context_version=context.action_context_version,
            after_context_version=context.action_context_version,
            before_state_digest=state_digest,
            after_state_digest=state_digest,
            http_request_id=http_request_id,
            occurred_at=evaluated_at,
            approval_receipt_id=approval.id,
        )
        return _approval_schema(
            approval,
            database_write=True,
            idempotent_replay=False,
        )


async def _locked_target_steps(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    request: WorkflowRunActionRequest,
) -> tuple[StepRun, ...]:
    parameters = request.parameters
    target_ids: tuple[uuid.UUID, ...]
    if isinstance(parameters, RetryActionParameters):
        target_ids = tuple(parameters.target_step_run_ids)
    elif isinstance(parameters, RouteSwitchActionParameters):
        target_ids = (parameters.step_run_id,)
    elif isinstance(parameters, ResumeActionParameters):
        checkpoint_result = await session.execute(
            select(WorkflowStepCheckpoint).where(
                WorkflowStepCheckpoint.workspace_id == workspace_id,
                WorkflowStepCheckpoint.project_id == project_id,
                WorkflowStepCheckpoint.execution_session_id == workflow_run_id,
                WorkflowStepCheckpoint.checkpoint_digest == parameters.checkpoint_digest,
            )
        )
        checkpoints = tuple(checkpoint_result.scalars().all())
        if len(checkpoints) != 1:
            raise WorkflowActionCommandError(
                "workflow_action_resume_checkpoint_unavailable",
                status=409,
            )
        checkpoint = checkpoints[0]
        target_result = await session.execute(
            select(StepRun)
            .where(
                StepRun.workspace_id == workspace_id,
                StepRun.project_id == project_id,
                StepRun.workflow_run_id == workflow_run_id,
                StepRun.step_ref == checkpoint.step_ref,
                StepRun.requirement_ref == checkpoint.requirement_ref,
                StepRun.implementation_id == checkpoint.implementation_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        resume_steps = tuple(target_result.scalars().all())
        if len(resume_steps) != 1:
            raise WorkflowActionCommandError(
                "workflow_action_resume_step_unavailable",
                status=409,
            )
        return resume_steps
    else:
        return ()
    result = await session.execute(
        select(StepRun)
        .where(
            StepRun.workspace_id == workspace_id,
            StepRun.project_id == project_id,
            StepRun.workflow_run_id == workflow_run_id,
            StepRun.id.in_(target_ids),
        )
        .order_by(StepRun.sequence, StepRun.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    steps = tuple(result.scalars().all())
    if {step.id for step in steps} != set(target_ids):
        raise WorkflowActionCommandError(
            "workflow_action_retry_target_unavailable",
            status=409,
        )
    return steps


async def _approval_consumed(
    session: AsyncSession,
    approval_receipt_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(WorkflowRunActionApprovalConsumption.id)
        .where(WorkflowRunActionApprovalConsumption.approval_receipt_id == approval_receipt_id)
        .with_for_update()
    )
    return result.scalar_one_or_none() is not None


def _state_context(
    request: WorkflowRunActionRequest,
    run: WorkflowRun,
    steps: tuple[StepRun, ...],
    evidence: WorkflowActionCommandEvidence,
) -> WorkflowActionStateContext:
    retry_generation = 0
    if isinstance(request.parameters, RetryActionParameters):
        expected = request.parameters.expected_retry_generation
        if any(step.retry_generation != expected for step in steps):
            raise WorkflowActionCommandError(
                "workflow_action_retry_generation_conflict",
                status=409,
            )
        retry_generation = expected
    if isinstance(request.parameters, RouteSwitchActionParameters) and any(
        step.status != WorkflowStepRunStatus.FAILED.value for step in steps
    ):
        raise WorkflowActionCommandError(
            "workflow_action_route_switch_blocked",
            status=409,
        )
    return WorkflowActionStateContext(
        run_status=WorkflowRunStatus(run.status),
        target_step_statuses=tuple(WorkflowStepRunStatus(step.status) for step in steps),
        retry_generation=retry_generation,
        retry_generation_limit=evidence.retry_generation_limit,
        retry_policy_available=evidence.retry_policy_available,
        checkpoint_available=evidence.checkpoint_available,
        checkpoint_terminal=evidence.checkpoint_terminal,
        budget_within_limit=evidence.budget_within_limit,
        failed_step_requires_retry=evidence.failed_step_requires_retry,
        budget_held=evidence.budget_held,
        route_switch_eligible=evidence.route_switch_eligible,
    )


def _validate_budget_override(
    parameters: BudgetOverrideActionParameters,
    evidence: WorkflowActionCommandEvidence,
    evaluated_at: datetime,
) -> None:
    if parameters.expires_at <= evaluated_at:
        raise WorkflowActionCommandError(
            "workflow_action_budget_override_expired",
            status=409,
        )
    if (
        parameters.request_limit < evidence.budget_current_request_count
        or parameters.item_limit < evidence.budget_current_item_count
        or parameters.quota_unit_limit < evidence.budget_current_quota_units
        or parameters.cost_limit_usd < evidence.budget_current_cost_usd
        or parameters.time_limit_ms < evidence.budget_current_elapsed_ms
    ):
        raise WorkflowActionCommandError(
            "workflow_action_budget_override_below_usage",
            status=409,
        )


def _decision_refs(
    request: WorkflowRunActionRequest,
    steps: tuple[StepRun, ...],
    evidence: WorkflowActionCommandEvidence,
) -> list[dict[str, object]]:
    parameters = request.parameters
    base: dict[str, object] = {
        "action": request.action,
        "action_gate_digest": request.action_gate_digest,
        "evidence_digests": list(evidence.evidence_digests),
    }
    if isinstance(parameters, RetryActionParameters):
        base.update(
            {
                "target_step_run_ids": [str(step.id) for step in steps],
                "retry_generation": parameters.expected_retry_generation + 1,
                "attempt_created": False,
            }
        )
    elif isinstance(parameters, ResumeActionParameters):
        base.update(
            {
                "checkpoint_digest": parameters.checkpoint_digest,
                "budget_policy_digest": parameters.budget_policy_digest,
                "budget_ledger_digest": parameters.budget_ledger_digest,
                "cursor_advanced": False,
            }
        )
    elif isinstance(parameters, CancelActionParameters):
        base["cancel_scope"] = parameters.cancel_scope
    elif isinstance(parameters, BudgetOverrideActionParameters):
        base.update(
            {
                "scope": "one_run",
                "one_shot": True,
                "expires_at": parameters.expires_at.isoformat(),
                "replacement_ceilings": parameters.model_dump(mode="json"),
                "original_budget_ledger_unchanged": True,
            }
        )
    else:
        base.update(
            {
                "step_run_id": str(parameters.step_run_id),
                "next_retry_generation": steps[0].retry_generation + 1,
                "primary_implementation_id": parameters.primary_implementation_id,
                "fallback_implementation_id": parameters.fallback_implementation_id,
                "original_route_plan_unchanged": True,
                "catalog_unchanged": True,
            }
        )
    return [base]


def _next_action_code(action: str) -> str:
    return {
        "retry": "await_fixture_executor",
        "resume": "await_fixture_executor",
        "cancel": "workflow_run_cancelled",
        "budget_override": "review_resume_after_budget_override",
        "route_switch": "review_retry_after_route_override",
    }[action]


def _apply_effect(
    request: WorkflowRunActionRequest,
    run: WorkflowRun,
    steps: tuple[StepRun, ...],
    evaluated_at: datetime,
) -> None:
    if request.action == "retry":
        for step in steps:
            step.retry_generation += 1
            step.status = WorkflowStepRunStatus.PENDING.value
            step.fixture_case_id = None
            step.fixture_content_hash = None
            step.output_digest = None
            step.records_count = 0
            step.finished_at = None
        run.status = WorkflowRunStatus.READY.value
        run.status_reason_code = None
        run.impact_code = None
        run.missing_fields = []
        run.recovery_action_codes = []
        run.finished_at = None
    elif request.action == "resume":
        run.status = WorkflowRunStatus.READY.value
        run.status_reason_code = None
        run.impact_code = None
        run.missing_fields = []
        run.recovery_action_codes = []
        run.finished_at = None
    elif request.action == "cancel":
        run.status = WorkflowRunStatus.CANCELLED.value
        run.status_reason_code = "workflow_run_cancelled_by_owner"
        run.impact_code = "workflow_run_cancelled"
        run.missing_fields = []
        run.recovery_action_codes = []
        run.finished_at = evaluated_at


async def _existing_action_replay(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    scope: str,
    key_hash: str,
    canonical_hash: str,
) -> WorkflowActionReceipt | None:
    existing_result = await session.execute(
        select(WorkflowRunActionRequestRecord)
        .where(
            WorkflowRunActionRequestRecord.workspace_id == workspace_id,
            WorkflowRunActionRequestRecord.actor_user_id == actor_user_id,
            WorkflowRunActionRequestRecord.idempotency_scope == scope,
            WorkflowRunActionRequestRecord.idempotency_key_hash == key_hash,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is None:
        return None
    if existing.canonical_request_hash != canonical_hash:
        raise WorkflowActionCommandError(
            "workflow_action_idempotency_conflict",
            status=409,
        )
    receipt_result = await session.execute(
        select(WorkflowRunActionReceiptRecord).where(
            WorkflowRunActionReceiptRecord.workspace_id == workspace_id,
            WorkflowRunActionReceiptRecord.project_id == project_id,
            WorkflowRunActionReceiptRecord.request_id == existing.id,
        )
    )
    stored_receipt = receipt_result.scalar_one_or_none()
    if stored_receipt is None:
        raise WorkflowActionCommandError(
            "workflow_action_receipt_missing",
            status=409,
        )
    return _receipt_schema(
        stored_receipt,
        database_write=False,
        idempotent_replay=True,
    )


async def _execute_workflow_run_action_once(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    http_request_id: str,
    request: WorkflowRunActionRequest,
    evidence: WorkflowActionCommandEvidence,
    evaluated_at: datetime,
    approval_revoked: bool = False,
) -> WorkflowActionReceipt:
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise WorkflowActionCommandError("workflow_action_time_invalid", status=422)
    _validate_evidence_binding(request, evidence)
    key_hash = _idempotency_key_hash(idempotency_key)
    scope = _action_scope(project_id, workflow_run_id)
    canonical_hash = canonical_workflow_action_request_hash(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        request=request,
    )

    async with session.begin():
        replay = await _existing_action_replay(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            scope=scope,
            key_hash=key_hash,
            canonical_hash=canonical_hash,
        )
        if replay is not None:
            return replay

        _validate_evidence_binding(request, evidence)
        run, owner_id = await _locked_run_and_owner(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        )
        _require_owner(actor_user_id, owner_id)
        context = await _locked_context(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        )
        replay = await _existing_action_replay(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            scope=scope,
            key_hash=key_hash,
            canonical_hash=canonical_hash,
        )
        if replay is not None:
            return replay
        if (
            request.expected_action_context_version != context.action_context_version
            or request.expected_run_status.value != run.status
        ):
            raise WorkflowActionCommandError("workflow_action_state_conflict", status=409)

        approval_result = await session.execute(
            select(WorkflowRunActionApprovalReceiptRecord)
            .where(
                WorkflowRunActionApprovalReceiptRecord.workspace_id == workspace_id,
                WorkflowRunActionApprovalReceiptRecord.project_id == project_id,
                WorkflowRunActionApprovalReceiptRecord.workflow_run_id == workflow_run_id,
                WorkflowRunActionApprovalReceiptRecord.id == request.approval_receipt_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        approval_record = approval_result.scalar_one_or_none()
        if approval_record is None:
            raise WorkflowActionCommandError(
                "workflow_action_approval_required",
                status=403,
            )
        consumed = await _approval_consumed(session, approval_record.id)
        approval = _approval_schema(
            approval_record,
            database_write=False,
            idempotent_replay=False,
        )
        authorization = authorize_workflow_action(
            actor_user_id=actor_user_id,
            workspace_owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            request=request,
            approval=approval,
            evaluated_at=evaluated_at,
            approval_consumed=consumed,
            approval_revoked=approval_revoked,
        )
        if not authorization.authorized:
            raise WorkflowActionCommandError(
                authorization.blocker_code or "workflow_action_authorization_failed",
                status=403,
            )
        if tuple(approval_record.evidence_digests) != evidence.evidence_digests:
            raise WorkflowActionCommandError(
                "workflow_action_evidence_conflict",
                status=409,
            )

        steps = await _locked_target_steps(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            request=request,
        )
        state_context = _state_context(request, run, steps, evidence)
        effect = compile_workflow_action_state_effect(
            action=request.action,
            context=state_context,
        )
        if not effect.accepted:
            raise WorkflowActionCommandError(
                effect.blocker_code or "workflow_action_precondition_failed",
                status=409,
            )
        if isinstance(request.parameters, BudgetOverrideActionParameters):
            _validate_budget_override(request.parameters, evidence, evaluated_at)

        before_context_version = context.action_context_version
        after_context_version = before_context_version + 1
        before_status = run.status
        before_steps = _step_snapshots(steps)
        before_state_digest = _canonical_digest(_state_payload(run, steps))
        request_record = WorkflowRunActionRequestRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            actor_user_id=actor_user_id,
            action=request.action,
            schema_version=request.schema_version,
            idempotency_scope=scope,
            idempotency_key_hash=key_hash,
            canonical_request_hash=canonical_hash,
            expected_action_context_version=before_context_version,
            accepted_action_context_version=after_context_version,
            expected_run_status=request.expected_run_status.value,
            observed_run_status=run.status,
            action_gate_digest=request.action_gate_digest,
            approval_receipt_id=request.approval_receipt_id,
            reason_code=request.reason_code,
            reason=request.reason,
            parameters=request.parameters.model_dump(mode="json"),
            outcome="accepted",
            response_status=201,
            response_payload={"outcome": "accepted"},
        )
        session.add(request_record)
        await session.flush()

        _apply_effect(request, run, steps, evaluated_at)
        await session.flush()
        after_steps = _step_snapshots(steps)
        after_state_digest = _canonical_digest(_state_payload(run, steps))
        receipt_id = uuid.uuid4()
        receipt_digest = _canonical_digest(
            {
                "scope": "workflow_action_receipt.v1",
                "id": str(receipt_id),
                "request_id": str(request_record.id),
                "action": request.action,
                "before_action_context_version": before_context_version,
                "after_action_context_version": after_context_version,
                "before_run_status": before_status,
                "after_run_status": run.status,
                "before_step_snapshots": before_steps,
                "after_step_snapshots": after_steps,
                "decision_refs": _decision_refs(request, steps, evidence),
                "created_at": evaluated_at.isoformat(),
            }
        )
        receipt_record = WorkflowRunActionReceiptRecord(
            id=receipt_id,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            request_id=request_record.id,
            action=request.action,
            outcome="accepted",
            before_action_context_version=before_context_version,
            after_action_context_version=after_context_version,
            before_run_status=before_status,
            after_run_status=run.status,
            before_step_snapshots=before_steps,
            after_step_snapshots=after_steps,
            decision_refs=_decision_refs(request, steps, evidence),
            state_changed=effect.state_changed,
            database_write=True,
            idempotent_replay=False,
            next_action_code=_next_action_code(request.action),
            receipt_digest=receipt_digest,
        )
        session.add(receipt_record)
        await session.flush()
        if isinstance(request.parameters, (RetryActionParameters, ResumeActionParameters)):
            try:
                await add_action_dispatches_for_accepted_action(
                    session,
                    run=run,
                    steps=steps,
                    request_record=request_record,
                    receipt_record=receipt_record,
                    parameters=request.parameters,
                    created_at=evaluated_at,
                )
            except ExecutorCompositionError as exc:
                raise WorkflowActionCommandError(exc.code, status=409) from exc
        session.add(
            WorkflowRunActionApprovalConsumption(
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=workflow_run_id,
                approval_receipt_id=approval_record.id,
                action_request_id=request_record.id,
                consumed_at=evaluated_at,
            )
        )
        context.action_context_version = after_context_version
        context.latest_accepted_receipt_id = receipt_record.id
        await session.flush()
        await _append_audit_event(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            actor_user_id=actor_user_id,
            event_type="action_accepted",
            reason_code=request.reason_code,
            before_context_version=before_context_version,
            after_context_version=after_context_version,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            http_request_id=http_request_id,
            occurred_at=evaluated_at,
            approval_receipt_id=approval_record.id,
            action_request_id=request_record.id,
            action_receipt_id=receipt_record.id,
        )
        return _receipt_schema(
            receipt_record,
            database_write=True,
            idempotent_replay=False,
            created_at=evaluated_at,
        )


async def execute_workflow_run_action(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    http_request_id: str,
    request: WorkflowRunActionRequest,
    evidence: WorkflowActionCommandEvidence,
    evaluated_at: datetime,
    approval_revoked: bool = False,
) -> WorkflowActionReceipt:
    try:
        return await _execute_workflow_run_action_once(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
            http_request_id=http_request_id,
            request=request,
            evidence=evidence,
            evaluated_at=evaluated_at,
            approval_revoked=approval_revoked,
        )
    except IntegrityError:
        await session.rollback()

    key_hash = _idempotency_key_hash(idempotency_key)
    scope = _action_scope(project_id, workflow_run_id)
    canonical_hash = canonical_workflow_action_request_hash(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        request=request,
    )
    async with session.begin():
        request_result = await session.execute(
            select(WorkflowRunActionRequestRecord).where(
                WorkflowRunActionRequestRecord.workspace_id == workspace_id,
                WorkflowRunActionRequestRecord.actor_user_id == actor_user_id,
                WorkflowRunActionRequestRecord.idempotency_scope == scope,
                WorkflowRunActionRequestRecord.idempotency_key_hash == key_hash,
            )
        )
        stored_request = request_result.scalar_one_or_none()
        if stored_request is None or stored_request.canonical_request_hash != canonical_hash:
            raise WorkflowActionCommandError(
                "workflow_action_persistence_conflict",
                status=409,
            )
        receipt_result = await session.execute(
            select(WorkflowRunActionReceiptRecord).where(
                WorkflowRunActionReceiptRecord.workspace_id == workspace_id,
                WorkflowRunActionReceiptRecord.project_id == project_id,
                WorkflowRunActionReceiptRecord.request_id == stored_request.id,
            )
        )
        stored_receipt = receipt_result.scalar_one_or_none()
        if stored_receipt is None:
            raise WorkflowActionCommandError(
                "workflow_action_persistence_conflict",
                status=409,
            )
        return _receipt_schema(
            stored_receipt,
            database_write=False,
            idempotent_replay=True,
        )


async def find_workflow_run_action_replay(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_key: str,
    request: WorkflowRunActionRequest,
) -> WorkflowActionReceipt | None:
    key_hash = _idempotency_key_hash(idempotency_key)
    scope = _action_scope(project_id, workflow_run_id)
    canonical_hash = canonical_workflow_action_request_hash(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        request=request,
    )
    async with session.begin():
        request_result = await session.execute(
            select(WorkflowRunActionRequestRecord).where(
                WorkflowRunActionRequestRecord.workspace_id == workspace_id,
                WorkflowRunActionRequestRecord.actor_user_id == actor_user_id,
                WorkflowRunActionRequestRecord.idempotency_scope == scope,
                WorkflowRunActionRequestRecord.idempotency_key_hash == key_hash,
            )
        )
        stored_request = request_result.scalar_one_or_none()
        if stored_request is None:
            return None
        if stored_request.canonical_request_hash != canonical_hash:
            raise WorkflowActionCommandError(
                "workflow_action_idempotency_conflict",
                status=409,
            )
        receipt_result = await session.execute(
            select(WorkflowRunActionReceiptRecord).where(
                WorkflowRunActionReceiptRecord.workspace_id == workspace_id,
                WorkflowRunActionReceiptRecord.project_id == project_id,
                WorkflowRunActionReceiptRecord.request_id == stored_request.id,
            )
        )
        stored_receipt = receipt_result.scalar_one_or_none()
        if stored_receipt is None:
            raise WorkflowActionCommandError(
                "workflow_action_receipt_missing",
                status=409,
            )
        return _receipt_schema(
            stored_receipt,
            database_write=False,
            idempotent_replay=True,
        )


__all__ = [
    "WorkflowActionCommandError",
    "WorkflowActionCommandEvidence",
    "execute_workflow_run_action",
    "find_workflow_run_action_replay",
    "issue_workflow_action_approval",
    "verify_workflow_action_audit_chain",
]

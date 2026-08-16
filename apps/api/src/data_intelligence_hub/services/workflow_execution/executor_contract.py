from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationAcknowledgement,
    WorkflowCancellationOutcome,
    WorkflowCancellationRequest,
    WorkflowCredentialResolutionPermit,
    WorkflowExecutionDispatch,
    WorkflowExecutionDispatchState,
    WorkflowExecutionLeaseToken,
    WorkflowProviderCallAudit,
    WorkflowProviderCallPermit,
)

WorkflowExecutorRecoveryState = Literal[
    "none",
    "held_manual_review",
]
WorkflowExecutorTerminalOutcome = Literal[
    "succeeded",
    "failed",
    "uncertain",
]


class WorkflowExecutorContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class WorkflowExecutionPreflightDecision:
    dispatch_id: UUID
    preflight_id: str
    eligible: bool
    blocker_codes: tuple[str, ...]
    next_required_authority: Literal["credential_resolution_permit"] | None
    provider_call_allowed: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    network_call: Literal[False] = False


@dataclass(frozen=True, slots=True)
class WorkflowExecutionTerminalDecision:
    dispatch_state: WorkflowExecutionDispatchState
    audit: WorkflowProviderCallAudit
    recovery_state: WorkflowExecutorRecoveryState
    retry_allowed: bool


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise WorkflowExecutorContractError("workflow_executor_time_utc_required")


def _require_duration(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 300:
        raise WorkflowExecutorContractError("workflow_executor_lease_duration_invalid")


def _require_dispatch_lease(
    dispatch: WorkflowExecutionDispatch,
    lease: WorkflowExecutionLeaseToken,
) -> None:
    if lease.dispatch_id != dispatch.id or lease.workspace_id != dispatch.workspace_id:
        raise WorkflowExecutorContractError("workflow_executor_lease_scope_mismatch")


def _require_current_lease(
    lease: WorkflowExecutionLeaseToken,
    *,
    presented_fencing_token: int,
    presented_version: int,
    evaluated_at: datetime,
) -> None:
    _require_utc(evaluated_at)
    if lease.state != "active":
        raise WorkflowExecutorContractError("workflow_executor_lease_unavailable")
    if presented_fencing_token != lease.fencing_token:
        raise WorkflowExecutorContractError("workflow_executor_fencing_token_stale")
    if presented_version != lease.version:
        raise WorkflowExecutorContractError("workflow_executor_lease_version_stale")
    if evaluated_at >= lease.expires_at:
        raise WorkflowExecutorContractError("workflow_executor_lease_expired")


def claim_workflow_execution_dispatch(
    dispatch: WorkflowExecutionDispatch,
    *,
    lease_id: UUID,
    worker_id: str,
    claimed_at: datetime,
    lease_duration_seconds: int,
) -> WorkflowExecutionLeaseToken:
    _require_utc(claimed_at)
    _require_duration(lease_duration_seconds)
    if dispatch.state != "claimable":
        raise WorkflowExecutorContractError("workflow_executor_dispatch_unavailable")
    return WorkflowExecutionLeaseToken(
        id=lease_id,
        dispatch_id=dispatch.id,
        workspace_id=dispatch.workspace_id,
        worker_id=worker_id,
        fencing_token=1,
        version=1,
        claimed_at=claimed_at,
        heartbeat_at=claimed_at,
        expires_at=claimed_at + timedelta(seconds=lease_duration_seconds),
        state="active",
    )


def heartbeat_workflow_execution_lease(
    lease: WorkflowExecutionLeaseToken,
    *,
    presented_fencing_token: int,
    presented_version: int,
    heartbeat_at: datetime,
    lease_duration_seconds: int,
) -> WorkflowExecutionLeaseToken:
    _require_duration(lease_duration_seconds)
    _require_current_lease(
        lease,
        presented_fencing_token=presented_fencing_token,
        presented_version=presented_version,
        evaluated_at=heartbeat_at,
    )
    return WorkflowExecutionLeaseToken.model_validate(
        {
            **lease.model_dump(),
            "version": lease.version + 1,
            "heartbeat_at": heartbeat_at,
            "expires_at": heartbeat_at + timedelta(seconds=lease_duration_seconds),
        }
    )


def takeover_workflow_execution_lease(
    lease: WorkflowExecutionLeaseToken,
    *,
    lease_id: UUID,
    worker_id: str,
    taken_over_at: datetime,
    lease_duration_seconds: int,
) -> WorkflowExecutionLeaseToken:
    _require_utc(taken_over_at)
    _require_duration(lease_duration_seconds)
    if lease.state == "active" and taken_over_at < lease.expires_at:
        raise WorkflowExecutorContractError("workflow_executor_lease_unavailable")
    if lease.state not in ("active", "expired"):
        raise WorkflowExecutorContractError("workflow_executor_lease_unavailable")
    return WorkflowExecutionLeaseToken(
        id=lease_id,
        dispatch_id=lease.dispatch_id,
        workspace_id=lease.workspace_id,
        worker_id=worker_id,
        fencing_token=lease.fencing_token + 1,
        version=1,
        claimed_at=taken_over_at,
        heartbeat_at=taken_over_at,
        expires_at=taken_over_at + timedelta(seconds=lease_duration_seconds),
        state="active",
    )


def release_workflow_execution_lease(
    lease: WorkflowExecutionLeaseToken,
    *,
    presented_fencing_token: int,
    presented_version: int,
    released_at: datetime,
) -> WorkflowExecutionLeaseToken:
    _require_current_lease(
        lease,
        presented_fencing_token=presented_fencing_token,
        presented_version=presented_version,
        evaluated_at=released_at,
    )
    return WorkflowExecutionLeaseToken.model_validate(
        {
            **lease.model_dump(),
            "version": lease.version + 1,
            "heartbeat_at": released_at,
            "state": "released",
        }
    )


def compile_workflow_execution_preflight(
    dispatch: WorkflowExecutionDispatch,
    lease: WorkflowExecutionLeaseToken,
    *,
    preflight_id: str,
    eligible: bool,
    blocker_codes: tuple[str, ...],
    evaluated_at: datetime,
) -> WorkflowExecutionPreflightDecision:
    _require_dispatch_lease(dispatch, lease)
    _require_current_lease(
        lease,
        presented_fencing_token=lease.fencing_token,
        presented_version=lease.version,
        evaluated_at=evaluated_at,
    )
    if eligible == bool(blocker_codes):
        raise WorkflowExecutorContractError("workflow_executor_preflight_state_invalid")
    if len(blocker_codes) != len(set(blocker_codes)) or any(not item for item in blocker_codes):
        raise WorkflowExecutorContractError("workflow_executor_preflight_blockers_invalid")
    return WorkflowExecutionPreflightDecision(
        dispatch_id=dispatch.id,
        preflight_id=preflight_id,
        eligible=eligible,
        blocker_codes=blocker_codes,
        next_required_authority=("credential_resolution_permit" if eligible else None),
    )


def _require_permit_available(
    permit: WorkflowCredentialResolutionPermit | WorkflowProviderCallPermit,
    *,
    consumed_at: datetime,
    error_prefix: str,
) -> None:
    _require_utc(consumed_at)
    if permit.consumed_at is not None:
        raise WorkflowExecutorContractError(f"{error_prefix}_consumed")
    if permit.revoked_at is not None:
        raise WorkflowExecutorContractError(f"{error_prefix}_revoked")
    if consumed_at >= permit.expires_at:
        raise WorkflowExecutorContractError(f"{error_prefix}_expired")
    if consumed_at < permit.issued_at:
        raise WorkflowExecutorContractError(f"{error_prefix}_not_active")


def _require_permit_lineage(
    permit: WorkflowCredentialResolutionPermit | WorkflowProviderCallPermit,
    dispatch: WorkflowExecutionDispatch,
) -> None:
    if any(
        (
            permit.dispatch_id != dispatch.id,
            permit.workspace_id != dispatch.workspace_id,
            permit.workflow_run_id != dispatch.workflow_run_id,
            permit.workflow_step_run_id != dispatch.workflow_step_run_id,
            permit.attempt_generation != dispatch.attempt_generation,
        )
    ):
        raise WorkflowExecutorContractError("workflow_executor_permit_scope_mismatch")


def consume_workflow_credential_resolution_permit(
    permit: WorkflowCredentialResolutionPermit,
    dispatch: WorkflowExecutionDispatch,
    *,
    provider_id: str,
    operation_id: str,
    purpose: str,
    environment: str,
    consumed_at: datetime,
) -> WorkflowCredentialResolutionPermit:
    _require_permit_available(
        permit,
        consumed_at=consumed_at,
        error_prefix="workflow_executor_credential_permit",
    )
    _require_permit_lineage(permit, dispatch)
    if permit.environment != environment:
        raise WorkflowExecutorContractError(
            "workflow_executor_credential_permit_environment_mismatch"
        )
    if (
        permit.provider_id != provider_id
        or permit.operation_id != operation_id
        or permit.purpose != purpose
    ):
        raise WorkflowExecutorContractError("workflow_executor_credential_permit_mismatch")
    return WorkflowCredentialResolutionPermit.model_validate(
        {**permit.model_dump(), "consumed_at": consumed_at}
    )


def consume_workflow_provider_call_permit(
    permit: WorkflowProviderCallPermit,
    dispatch: WorkflowExecutionDispatch,
    *,
    preflight_id: str,
    policy_digest: str,
    provider_id: str,
    operation_id: str,
    environment: str,
    reserved_cost_usd: Decimal,
    reserved_quota_units: int,
    consumed_at: datetime,
) -> WorkflowProviderCallPermit:
    _require_permit_available(
        permit,
        consumed_at=consumed_at,
        error_prefix="workflow_executor_provider_permit",
    )
    _require_permit_lineage(permit, dispatch)
    if permit.environment != environment:
        raise WorkflowExecutorContractError(
            "workflow_executor_provider_permit_environment_mismatch"
        )
    if any(
        (
            permit.preflight_id != preflight_id,
            permit.policy_digest != policy_digest,
            permit.provider_id != provider_id,
            permit.operation_id != operation_id,
            permit.side_effect_key != dispatch.provider_side_effect_key,
        )
    ):
        raise WorkflowExecutorContractError("workflow_executor_provider_permit_mismatch")
    if (
        not reserved_cost_usd.is_finite()
        or reserved_cost_usd < 0
        or reserved_cost_usd > permit.max_cost_usd
        or isinstance(reserved_quota_units, bool)
        or reserved_quota_units < 0
        or reserved_quota_units > permit.max_quota_units
    ):
        raise WorkflowExecutorContractError("workflow_executor_provider_permit_budget_exceeded")
    return WorkflowProviderCallPermit.model_validate(
        {**permit.model_dump(), "consumed_at": consumed_at}
    )


def compile_workflow_execution_terminal_outcome(
    dispatch: WorkflowExecutionDispatch,
    lease: WorkflowExecutionLeaseToken,
    audit: WorkflowProviderCallAudit,
    *,
    presented_fencing_token: int,
    presented_version: int,
    outcome: WorkflowExecutorTerminalOutcome,
    completed_at: datetime,
) -> WorkflowExecutionTerminalDecision:
    _require_dispatch_lease(dispatch, lease)
    _require_current_lease(
        lease,
        presented_fencing_token=presented_fencing_token,
        presented_version=presented_version,
        evaluated_at=completed_at,
    )
    if any(
        (
            audit.dispatch_id != dispatch.id,
            audit.workspace_id != dispatch.workspace_id,
            audit.workflow_run_id != dispatch.workflow_run_id,
            audit.workflow_step_run_id != dispatch.workflow_step_run_id,
            audit.attempt_generation != dispatch.attempt_generation,
            audit.lease_id != lease.id,
            audit.fencing_token != lease.fencing_token,
            audit.side_effect_key != dispatch.provider_side_effect_key,
            audit.transport_state != "attempting",
        )
    ):
        raise WorkflowExecutorContractError("workflow_executor_audit_mismatch")
    outcome_code = {
        "succeeded": "workflow_executor_provider_call_succeeded",
        "failed": "workflow_executor_provider_call_failed",
        "uncertain": "workflow_executor_provider_outcome_uncertain",
    }[outcome]
    terminal_audit = WorkflowProviderCallAudit.model_validate(
        {
            **audit.model_dump(),
            "transport_state": outcome,
            "outcome_code": outcome_code,
            "finished_at": completed_at,
        }
    )
    return WorkflowExecutionTerminalDecision(
        dispatch_state="terminal",
        audit=terminal_audit,
        recovery_state="held_manual_review" if outcome == "uncertain" else "none",
        retry_allowed=False,
    )


def acknowledge_workflow_cancellation(
    request: WorkflowCancellationRequest,
    lease: WorkflowExecutionLeaseToken,
    *,
    acknowledgement_id: UUID,
    presented_fencing_token: int,
    presented_version: int,
    safe_point: str,
    outcome: WorkflowCancellationOutcome,
    acknowledged_at: datetime,
) -> WorkflowCancellationAcknowledgement:
    _require_current_lease(
        lease,
        presented_fencing_token=presented_fencing_token,
        presented_version=presented_version,
        evaluated_at=acknowledged_at,
    )
    if request.dispatch_id != lease.dispatch_id or request.workspace_id != lease.workspace_id:
        raise WorkflowExecutorContractError("workflow_executor_cancel_scope_mismatch")
    if acknowledged_at < request.requested_at:
        raise WorkflowExecutorContractError("workflow_executor_cancel_ack_time_invalid")
    return WorkflowCancellationAcknowledgement(
        id=acknowledgement_id,
        request_id=request.id,
        dispatch_id=request.dispatch_id,
        workspace_id=request.workspace_id,
        lease_id=lease.id,
        fencing_token=lease.fencing_token,
        safe_point=safe_point,
        outcome=outcome,
        acknowledged_at=acknowledged_at,
    )


__all__ = [
    "WorkflowExecutionPreflightDecision",
    "WorkflowExecutionTerminalDecision",
    "WorkflowExecutorContractError",
    "acknowledge_workflow_cancellation",
    "claim_workflow_execution_dispatch",
    "compile_workflow_execution_preflight",
    "compile_workflow_execution_terminal_outcome",
    "consume_workflow_credential_resolution_permit",
    "consume_workflow_provider_call_permit",
    "heartbeat_workflow_execution_lease",
    "release_workflow_execution_lease",
    "takeover_workflow_execution_lease",
]

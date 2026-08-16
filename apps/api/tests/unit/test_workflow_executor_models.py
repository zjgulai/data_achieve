from __future__ import annotations

from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_executor import (
    WorkflowCancellationAcknowledgementRecord,
    WorkflowCancellationRequestRecord,
    WorkflowCredentialResolutionPermitRecord,
    WorkflowExecutionDispatchRecord,
    WorkflowExecutionEventRecord,
    WorkflowExecutionLeaseRecord,
    WorkflowProviderCallAuditRecord,
    WorkflowProviderCallPermitRecord,
)

EXECUTOR_MODELS = (
    WorkflowExecutionDispatchRecord,
    WorkflowExecutionLeaseRecord,
    WorkflowExecutionEventRecord,
    WorkflowCredentialResolutionPermitRecord,
    WorkflowProviderCallPermitRecord,
    WorkflowProviderCallAuditRecord,
    WorkflowCancellationRequestRecord,
    WorkflowCancellationAcknowledgementRecord,
)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _unique_sets(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _check_sql(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def test_executor_models_are_eight_relationship_free_tenant_scoped_tables() -> None:
    assert [model.__tablename__ for model in EXECUTOR_MODELS] == [
        "workflow_execution_dispatches",
        "workflow_execution_leases",
        "workflow_execution_events",
        "workflow_credential_resolution_permits",
        "workflow_provider_call_permits",
        "workflow_provider_call_audits",
        "workflow_cancellation_requests",
        "workflow_cancellation_acknowledgements",
    ]
    lineage = {
        "id",
        "workspace_id",
        "project_id",
        "workflow_run_id",
        "workflow_step_run_id",
        "attempt_generation",
    }
    for model in EXECUTOR_MODELS:
        table = _table(model)
        assert lineage <= set(table.c.keys())
        assert not model.__mapper__.relationships
        assert ("workspace_id", "project_id", "id") in _unique_sets(table)
        targets = {
            tuple(element.target_fullname for element in constraint.elements)
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ) in targets
        assert (
            "step_runs.workspace_id",
            "step_runs.project_id",
            "step_runs.workflow_run_id",
            "step_runs.id",
        ) in targets


def test_dispatch_has_semantic_replay_and_fail_closed_local_boundaries() -> None:
    table = _table(WorkflowExecutionDispatchRecord)
    assert ("workspace_id", "project_id", "dispatch_key") in _unique_sets(table)
    assert {
        "source_action_request_id",
        "source_action_receipt_id",
        "workflow_version_digest",
        "execution_policy_digest",
        "provider_side_effect_key",
        "database_write",
        "credential_read_attempted",
        "provider_call",
        "network_call",
        "production_write_allowed",
    } <= set(table.c.keys())
    checks = _check_sql(table)
    assert "source_action_request_id IS NULL" in checks
    assert "NOT credential_read_attempted" in checks
    assert "NOT provider_call" in checks
    assert "NOT network_call" in checks
    assert "NOT production_write_allowed" in checks


def test_lease_is_the_only_mutable_head_and_has_fencing_invariants() -> None:
    lease = _table(WorkflowExecutionLeaseRecord)
    assert "updated_at" in lease.c
    assert ("workspace_id", "project_id", "dispatch_id") in _unique_sets(lease)
    checks = _check_sql(lease)
    assert "fencing_token >= 1" in checks
    assert "version >= 1" in checks
    assert "claimed_at <= heartbeat_at" in checks
    for model in EXECUTOR_MODELS:
        if model is not WorkflowExecutionLeaseRecord:
            assert "updated_at" not in _table(model).c


def test_event_chain_and_single_use_evidence_constraints_are_durable() -> None:
    event = _table(WorkflowExecutionEventRecord)
    assert ("workspace_id", "project_id", "dispatch_id", "sequence") in _unique_sets(event)
    assert (
        "workspace_id",
        "project_id",
        "dispatch_id",
        "event_digest",
    ) in _unique_sets(event)
    assert "sequence = 1" in _check_sql(event)
    event_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in event.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        "workflow_execution_events.workspace_id",
        "workflow_execution_events.project_id",
        "workflow_execution_events.dispatch_id",
        "workflow_execution_events.event_digest",
    ) in event_targets

    for model in (
        WorkflowCredentialResolutionPermitRecord,
        WorkflowProviderCallPermitRecord,
    ):
        checks = _check_sql(_table(model))
        assert "consumed_at IS NULL OR revoked_at IS NULL" in checks
        assert "expires_at > issued_at" in checks

    credential_columns = set(_table(WorkflowCredentialResolutionPermitRecord).c.keys())
    assert "credential_reference_fingerprint" in credential_columns
    assert not {"credential", "credential_reference", "secret", "api_key"} & credential_columns


def test_provider_audit_and_cancellation_are_append_only_evidence() -> None:
    audit = _table(WorkflowProviderCallAuditRecord)
    assert (
        "workspace_id",
        "project_id",
        "dispatch_id",
        "attempt_ordinal",
    ) in _unique_sets(audit)
    assert "transport_state" in _check_sql(audit)

    request = _table(WorkflowCancellationRequestRecord)
    acknowledgement = _table(WorkflowCancellationAcknowledgementRecord)
    assert ("workspace_id", "project_id", "request_key") in _unique_sets(request)
    assert ("workspace_id", "project_id", "request_id") in _unique_sets(acknowledgement)
    assert "acknowledged" not in request.c

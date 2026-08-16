from __future__ import annotations

from typing import cast

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Table,
    UniqueConstraint,
)

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionApprovalConsumption,
    WorkflowRunActionApprovalReceiptRecord,
    WorkflowRunActionAuditEvent,
    WorkflowRunActionContext,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)

APPEND_ONLY_MODELS = (
    WorkflowRunActionApprovalReceiptRecord,
    WorkflowRunActionRequestRecord,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionApprovalConsumption,
    WorkflowRunActionAuditEvent,
)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _unique_sets(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _constraint_names(table: Table) -> set[str]:
    return {
        cast(str, constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def test_action_context_is_one_mutable_tenant_scoped_row_per_run() -> None:
    table = _table(WorkflowRunActionContext)
    assert table.name == "workflow_run_action_contexts"
    assert set(table.c.keys()) == {
        "id",
        "workspace_id",
        "project_id",
        "workflow_run_id",
        "action_context_version",
        "latest_accepted_receipt_id",
        "created_at",
        "updated_at",
    }
    assert (
        "workspace_id",
        "project_id",
        "workflow_run_id",
    ) in _unique_sets(table)
    assert "ck_workflow_run_action_contexts_version" in _constraint_names(table)
    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert tuple(item.target_fullname for item in foreign_keys[0].elements) == (
        "workflow_runs.workspace_id",
        "workflow_runs.project_id",
        "workflow_runs.id",
    )


def test_action_ledgers_are_append_only_and_registered_on_shared_metadata() -> None:
    assert {_table(model).name for model in APPEND_ONLY_MODELS} == {
        "workflow_run_action_approval_receipts",
        "workflow_run_action_requests",
        "workflow_run_action_receipts",
        "workflow_run_action_approval_consumptions",
        "workflow_run_action_audit_events",
    }
    for model in APPEND_ONLY_MODELS:
        table = _table(model)
        assert "created_at" in table.c
        assert "updated_at" not in table.c
        assert model.metadata is Base.metadata
        assert not model.__mapper__.relationships
        assert {
            "workspace_id",
            "project_id",
            "workflow_run_id",
        } <= set(table.c.keys())
        assert any(
            isinstance(constraint, ForeignKeyConstraint)
            and {
                "workspace_id",
                "project_id",
                "workflow_run_id",
            }.issubset({item.parent.name for item in constraint.elements})
            for constraint in table.constraints
        )


def test_request_approval_consumption_receipt_and_audit_uniqueness_is_exact() -> None:
    request = _table(WorkflowRunActionRequestRecord)
    assert (
        "workspace_id",
        "actor_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
    ) in _unique_sets(request)
    assert (
        "workspace_id",
        "project_id",
        "id",
    ) in _unique_sets(request)

    approval = _table(WorkflowRunActionApprovalReceiptRecord)
    assert ("workspace_id", "project_id", "id") in _unique_sets(approval)
    assert (
        "workspace_id",
        "approver_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
    ) in _unique_sets(approval)

    receipt = _table(WorkflowRunActionReceiptRecord)
    assert ("workspace_id", "project_id", "request_id") in _unique_sets(receipt)
    assert ("workspace_id", "project_id", "receipt_digest") in _unique_sets(receipt)

    consumption = _table(WorkflowRunActionApprovalConsumption)
    assert ("approval_receipt_id",) in _unique_sets(consumption)
    assert ("action_request_id",) in _unique_sets(consumption)

    audit = _table(WorkflowRunActionAuditEvent)
    assert (
        "workspace_id",
        "project_id",
        "workflow_run_id",
        "event_number",
    ) in _unique_sets(audit)
    assert (
        "workspace_id",
        "project_id",
        "workflow_run_id",
        "event_digest",
    ) in _unique_sets(audit)


def test_persisted_boundaries_are_non_nullable_and_default_false() -> None:
    for model in (
        WorkflowRunActionApprovalReceiptRecord,
        WorkflowRunActionReceiptRecord,
        WorkflowRunActionAuditEvent,
    ):
        table = _table(model)
        for name in (
            "provider_call_attempted",
            "credential_read_attempted",
            "execution_started",
            "production_write_allowed",
        ):
            column = table.c[name]
            assert isinstance(column.type, Boolean)
            assert column.nullable is False
            assert column.default is not None
            assert cast(bool, column.default.arg) is False
        assert any("fixture_boundaries" in name for name in _constraint_names(table))


def test_receipt_rows_only_persist_newly_accepted_writes() -> None:
    table = _table(WorkflowRunActionReceiptRecord)
    constraints = {
        cast(str, constraint.name): str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }

    outcome = constraints["ck_workflow_run_action_receipts_outcome"]
    assert "accepted" in outcome
    assert "accepted_pending_executor_ack" in outcome
    assert "rejected_" not in outcome

    write_replay = constraints["ck_workflow_run_action_receipts_write_replay"]
    assert "database_write" in write_replay
    assert "idempotent_replay" in write_replay
    assert " OR " not in write_replay


def test_request_outcome_and_accepted_version_are_consistent() -> None:
    table = _table(WorkflowRunActionRequestRecord)
    constraints = {
        cast(str, constraint.name): str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }
    context_version = constraints["ck_workflow_run_action_requests_context_version"]
    assert "outcome IN ('accepted', 'accepted_pending_executor_ack')" in context_version
    assert "accepted_action_context_version = expected_action_context_version + 1" in (
        context_version
    )
    assert "outcome IN ('rejected_conflict'," in context_version
    assert "accepted_action_context_version IS NULL" in context_version


def test_audit_predecessor_is_tenant_and_run_scoped() -> None:
    table = _table(WorkflowRunActionAuditEvent)
    foreign_key_targets = {
        tuple(item.target_fullname for item in constraint.elements)
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        "workflow_run_action_audit_events.workspace_id",
        "workflow_run_action_audit_events.project_id",
        "workflow_run_action_audit_events.workflow_run_id",
        "workflow_run_action_audit_events.event_digest",
    ) in foreign_key_targets

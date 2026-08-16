from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import CheckConstraint, Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "202607270043_workflow_run_actions.py"
)


class RecordingOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, args, kwargs))

        return record


class MigrationModule(Protocol):
    revision: str
    down_revision: str | None
    op: object

    def upgrade(self) -> None: ...

    def downgrade(self) -> None: ...


def _load_migration() -> MigrationModule:
    spec = importlib.util.spec_from_file_location("workflow_run_actions", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_043_is_linear_source_only_and_generation_compatible() -> None:
    assert MIGRATION_PATH.is_file()
    module = _load_migration()
    assert module.revision == "202607270043"
    assert module.down_revision == "202607230042"

    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    names = [name for name, _, _ in recorder.calls]
    assert "execute" not in names
    assert names[:6] == [
        "add_column",
        "create_check_constraint",
        "add_column",
        "drop_constraint",
        "create_unique_constraint",
        "create_check_constraint",
    ]
    assert names.count("create_table") == 6
    assert [args[0] for name, args, _ in recorder.calls if name == "create_table"] == [
        "workflow_run_action_contexts",
        "workflow_run_action_approval_receipts",
        "workflow_run_action_requests",
        "workflow_run_action_receipts",
        "workflow_run_action_approval_consumptions",
        "workflow_run_action_audit_events",
    ]


def test_revision_043_retains_tenant_uniqueness_and_named_constraints() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    names = {
        cast(str, item.name)
        for name, args, _ in recorder.calls
        if name == "create_table"
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }
    assert {
        "pk_workflow_run_action_contexts",
        "uq_workflow_run_action_contexts_run",
        "fk_workflow_run_action_contexts_run_tenant",
        "pk_workflow_run_action_approval_receipts",
        "uq_workflow_run_action_approvals_actor_key",
        "pk_workflow_run_action_requests",
        "uq_workflow_run_action_requests_actor_key",
        "pk_workflow_run_action_receipts",
        "uq_workflow_run_action_receipts_request",
        "pk_workflow_run_action_approval_consumptions",
        "uq_workflow_run_action_consumptions_approval",
        "pk_workflow_run_action_audit_events",
        "uq_workflow_run_action_audit_events_run_number",
    } <= names
    assert (
        sum(
            isinstance(item, ForeignKeyConstraint)
            for name, args, _ in recorder.calls
            if name == "create_table"
            for item in args[1:]
        )
        >= 10
    )


def test_revision_043_downgrade_refuses_evidence_and_reverses_dependencies() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert recorder.calls[0][0] == "execute"
    guard_sql = cast(str, recorder.calls[0][1][0])
    for table in (
        "workflow_run_action_contexts",
        "workflow_run_action_approval_receipts",
        "workflow_run_action_requests",
        "workflow_run_action_receipts",
        "workflow_run_action_approval_consumptions",
        "workflow_run_action_audit_events",
        "step_runs",
        "step_run_attempts",
    ):
        assert table in guard_sql
    assert [args[0] for name, args, _ in recorder.calls if name == "drop_table"] == [
        "workflow_run_action_audit_events",
        "workflow_run_action_approval_consumptions",
        "workflow_run_action_receipts",
        "workflow_run_action_requests",
        "workflow_run_action_approval_receipts",
        "workflow_run_action_contexts",
    ]


def test_revision_043_receipts_only_store_newly_accepted_writes() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    receipt_args = next(
        args
        for name, args, _ in recorder.calls
        if name == "create_table" and args[0] == "workflow_run_action_receipts"
    )
    constraints = {
        cast(str, item.name): str(item.sqltext)
        for item in receipt_args[1:]
        if isinstance(item, CheckConstraint) and item.name is not None
    }

    outcome = constraints["ck_workflow_run_action_receipts_outcome"]
    assert "accepted" in outcome
    assert "accepted_pending_executor_ack" in outcome
    assert "rejected_" not in outcome

    write_replay = constraints["ck_workflow_run_action_receipts_write_replay"]
    assert "database_write" in write_replay
    assert "idempotent_replay" in write_replay
    assert " OR " not in write_replay


def test_revision_043_request_version_and_audit_predecessor_are_fail_closed() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    tables = {
        cast(str, args[0]): args[1:] for name, args, _ in recorder.calls if name == "create_table"
    }

    request_constraints = {
        cast(str, item.name): str(item.sqltext)
        for item in tables["workflow_run_action_requests"]
        if isinstance(item, CheckConstraint) and item.name is not None
    }
    context_version = request_constraints["ck_workflow_run_action_requests_context_version"]
    assert "outcome IN ('accepted', 'accepted_pending_executor_ack')" in context_version
    assert "outcome IN ('rejected_conflict'," in context_version
    assert "accepted_action_context_version IS NULL" in context_version

    audit_foreign_key_targets = {
        tuple(item.target_fullname for item in constraint.elements)
        for constraint in tables["workflow_run_action_audit_events"]
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        "workflow_run_action_audit_events.workspace_id",
        "workflow_run_action_audit_events.project_id",
        "workflow_run_action_audit_events.workflow_run_id",
        "workflow_run_action_audit_events.event_digest",
    ) in audit_foreign_key_targets

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Numeric,
    Table,
    UniqueConstraint,
)

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_execution import (
    WorkflowBudgetAccount,
    WorkflowBudgetLedgerEntry,
)


def _table(model: type[WorkflowBudgetAccount] | type[WorkflowBudgetLedgerEntry]) -> Table:
    return cast(Table, model.__table__)


def test_budget_account_is_immutable_tenant_scoped_and_session_unique() -> None:
    table = _table(WorkflowBudgetAccount)
    assert table.name == "workflow_budget_accounts"
    assert "updated_at" not in table.c
    assert not WorkflowBudgetAccount.__mapper__.relationships
    assert WorkflowBudgetAccount.metadata is Base.metadata

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert {
        ("execution_session_id",),
        ("workspace_id", "project_id", "id"),
    } <= unique_sets

    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        ("workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.workflow_plan_id",
            "workflow_versions.id",
        ),
    ) in foreign_keys
    assert isinstance(table.c.max_cost_usd.type, Numeric)
    assert (table.c.max_cost_usd.type.precision, table.c.max_cost_usd.type.scale) == (
        20,
        8,
    )


def test_budget_ledger_is_append_only_tenant_scoped_and_idempotent() -> None:
    table = _table(WorkflowBudgetLedgerEntry)
    assert table.name == "workflow_budget_ledger_entries"
    assert "updated_at" not in table.c
    assert not WorkflowBudgetLedgerEntry.__mapper__.relationships

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert {
        ("budget_account_id", "entry_number"),
        ("budget_account_id", "step_ref", "page_number"),
        ("budget_account_id", "side_effect_key_hash"),
    } <= unique_sets
    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert tuple(item.target_fullname for item in foreign_keys[0].elements) == (
        "workflow_budget_accounts.workspace_id",
        "workflow_budget_accounts.project_id",
        "workflow_budget_accounts.id",
    )

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_workflow_budget_ledger_entries_contract_version",
        "ck_workflow_budget_ledger_entries_sequence",
        "ck_workflow_budget_ledger_entries_status",
        "ck_workflow_budget_ledger_entries_outcome",
        "ck_workflow_budget_ledger_entries_usage",
        "ck_workflow_budget_ledger_entries_fixture_boundaries",
    } <= constraint_names


def test_budget_fixture_boundary_flags_default_false() -> None:
    for model in (WorkflowBudgetAccount, WorkflowBudgetLedgerEntry):
        table = _table(model)
        for name in (
            "provider_call_attempted",
            "credential_read_attempted",
            "actor_run",
            "browser_run",
            "llm_call",
            "raw_record_write",
            "dataset_write",
            "production_write_allowed",
        ):
            column = table.c[name]
            assert isinstance(column.type, Boolean)
            assert column.nullable is False
            assert column.default is not None
            assert cast(bool, cast(Any, column.default).arg) is False

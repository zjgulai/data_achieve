from __future__ import annotations

from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.dataset import Dataset, DatasetVersion
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest,
)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _unique_sets(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in item.columns)
        for item in table.constraints
        if isinstance(item, UniqueConstraint)
    }


def _foreign_keys(table: Table) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    return {
        (
            tuple(element.parent.name for element in item.elements),
            tuple(element.target_fullname for element in item.elements),
        )
        for item in table.constraints
        if isinstance(item, ForeignKeyConstraint)
    }


def test_dataset_targets_support_tenant_safe_materialization_foreign_keys() -> None:
    assert ("workspace_id", "project_id", "id") in _unique_sets(_table(Dataset))
    assert ("workspace_id", "project_id", "dataset_id", "id") in _unique_sets(
        _table(DatasetVersion)
    )
    assert ("source_workflow_run_id",) in _unique_sets(_table(DatasetVersion))


def test_materialization_ledger_has_exact_replay_and_run_uniqueness() -> None:
    table = _table(WorkflowLineageMaterializationRequest)
    assert {
        "workspace_id",
        "project_id",
        "created_by_user_id",
        "workflow_run_id",
        "dataset_id",
        "dataset_version_id",
        "idempotency_scope",
        "idempotency_key_hash",
        "request_hash",
        "response_payload",
    } <= set(table.c.keys())
    assert (
        "workspace_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
    ) in _unique_sets(table)
    assert ("workflow_run_id",) in _unique_sets(table)
    assert (
        ("workspace_id", "project_id", "workflow_run_id"),
        ("workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"),
    ) in _foreign_keys(table)
    assert (
        ("workspace_id", "project_id", "dataset_id"),
        ("datasets.workspace_id", "datasets.project_id", "datasets.id"),
    ) in _foreign_keys(table)
    assert any(
        isinstance(item, CheckConstraint) and "outcome = 'completed'" in str(item.sqltext)
        for item in table.constraints
    )

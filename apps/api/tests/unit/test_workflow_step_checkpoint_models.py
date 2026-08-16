from __future__ import annotations

from typing import cast

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_execution import WorkflowStepCheckpoint


def _table() -> Table:
    return cast(Table, WorkflowStepCheckpoint.__table__)


def test_checkpoint_is_append_only_tenant_scoped_and_page_idempotent() -> None:
    table = _table()
    assert table.name == "workflow_step_checkpoints"
    assert "updated_at" not in table.c
    assert not WorkflowStepCheckpoint.__mapper__.relationships
    assert WorkflowStepCheckpoint.metadata is Base.metadata

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert {
        ("execution_session_id", "step_ref", "page_number"),
        ("execution_session_id", "step_ref", "cursor_before_digest"),
        ("execution_session_id", "side_effect_key_hash"),
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

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_workflow_step_checkpoints_contract_version",
        "ck_workflow_step_checkpoints_page_number",
        "ck_workflow_step_checkpoints_records_count",
        "ck_workflow_step_checkpoints_cursor_before",
        "ck_workflow_step_checkpoints_cursor_after",
        "ck_workflow_step_checkpoints_fixture_boundaries",
    } <= constraint_names


def test_checkpoint_fixture_boundary_flags_default_false() -> None:
    table = _table()
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
        assert cast(bool, column.default.arg) is False

from __future__ import annotations

from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint, Uuid

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_template import (
    WorkflowTemplate,
    WorkflowTemplateRevision,
)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _checks(table: Table) -> set[str]:
    return {
        str(constraint.sqltext).replace(" ", "")
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_workflow_template_is_project_scoped_and_points_to_revision() -> None:
    table = _table(WorkflowTemplate)
    assert table.name == "workflow_templates"
    assert isinstance(table.c.id.type, Uuid)
    assert "current_revision_id" in table.c
    unique_sets = {
        tuple(column.name for column in item.columns)
        for item in table.constraints
        if isinstance(item, UniqueConstraint)
    }
    assert unique_sets >= {
        ("workspace_id", "project_id", "template_key"),
        ("workspace_id", "project_id", "id"),
    }
    checks = _checks(table)
    assert "statusIN('draft','previewed','approved','active','paused','archived')" in checks

    revision_table = _table(WorkflowTemplateRevision)
    assert "definition" in revision_table.c


def test_workflow_template_does_not_cascade_delete() -> None:
    table = _table(WorkflowTemplate)
    assert all(
        constraint.ondelete is None
        for constraint in table.constraints
        if hasattr(constraint, "ondelete")
    )

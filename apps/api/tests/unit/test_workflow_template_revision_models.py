from __future__ import annotations

from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workflow_template import (
    WorkflowTemplate,
    WorkflowTemplateRevision,
)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _constraint_names(table: Table, kind: type[object]) -> set[str]:
    return {
        str(item.name)
        for item in table.constraints
        if isinstance(item, kind) and item.name is not None
    }


def test_revision_is_immutable_tenant_scoped_and_fingerprinted() -> None:
    table = _table(WorkflowTemplateRevision)

    assert table.name == "workflow_template_revisions"
    assert {
        "pk_workflow_template_revisions",
        "uq_workflow_template_revisions_template_tenant_id",
        "uq_workflow_template_revisions_tenant_number",
    } <= (
        _constraint_names(table, UniqueConstraint)
        | _constraint_names(table, type(table.primary_key))
    )
    assert "ck_workflow_template_revisions_revision_number" in _constraint_names(
        table,
        CheckConstraint,
    )
    assert any(
        isinstance(item, ForeignKeyConstraint)
        and item.name == "fk_workflow_template_revisions_template_tenant"
        for item in table.constraints
    )


def test_plan_and_version_have_optional_template_revision_pairs() -> None:
    for model in (WorkflowPlan, WorkflowVersion):
        table = _table(model)
        assert "workflow_template_id" in table.c
        assert "workflow_template_revision_id" in table.c
        assert any(
            isinstance(item, CheckConstraint)
            and "workflow_template_revision_id" in str(item.sqltext)
            for item in table.constraints
        )


def test_template_points_to_current_revision_without_cascade_delete() -> None:
    table = _table(WorkflowTemplate)
    assert "current_revision_id" in table.c
    assert all(getattr(constraint, "ondelete", None) is None for constraint in table.constraints)

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ColumnDefault,
    ForeignKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.workflow_plan import (
    MonitoringScope,
    QueryTerm,
    WorkflowPlan,
    WorkflowPlanSaveRequest,
    WorkflowVersion,
    WorkflowVersionScope,
)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _unique_column_sets(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_signatures(
    table: Table,
) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    signatures: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for constraint in table.constraints:
        if not isinstance(constraint, ForeignKeyConstraint):
            continue
        signatures.add(
            (
                tuple(element.parent.name for element in constraint.elements),
                tuple(element.target_fullname for element in constraint.elements),
            )
        )
    return signatures


def _check_sql(table: Table) -> set[str]:
    return {
        str(constraint.sqltext).replace(" ", "")
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _assert_no_delete_cascade(tables: Iterable[Table]) -> None:
    for table in tables:
        for constraint in table.constraints:
            if isinstance(constraint, ForeignKeyConstraint):
                assert constraint.ondelete is None


def test_workflow_plan_metadata_contains_exactly_the_six_new_tables() -> None:
    models: tuple[type[Base], ...] = (
        WorkflowPlan,
        WorkflowVersion,
        MonitoringScope,
        WorkflowVersionScope,
        QueryTerm,
        WorkflowPlanSaveRequest,
    )

    assert {_table(model).name for model in models} == {
        "workflow_plans",
        "workflow_versions",
        "monitoring_scopes",
        "workflow_version_scopes",
        "query_terms",
        "workflow_plan_save_requests",
    }


def test_uuid_primary_keys_use_python_defaults() -> None:
    models: tuple[type[Base], ...] = (
        WorkflowPlan,
        WorkflowVersion,
        MonitoringScope,
        QueryTerm,
        WorkflowPlanSaveRequest,
    )
    for model in models:
        id_column = _table(model).c.id
        assert isinstance(id_column.type, Uuid)
        assert id_column.default is not None
        assert id_column.default.is_callable
        assert id_column.server_default is None

    assert tuple(column.name for column in _table(WorkflowVersionScope).primary_key) == (
        "workflow_version_id",
        "monitoring_scope_id",
    )


def test_structured_snapshots_use_generic_json_not_jsonb() -> None:
    json_columns = {
        WorkflowVersion: {
            "query_versions",
            "fingerprint_payload",
            "normalized_input",
            "plan_payload",
        },
        MonitoringScope: {
            "aliases",
            "include_terms",
            "exclude_terms",
            "official_accounts",
            "seed_urls",
            "effective_languages",
            "effective_regions",
            "effective_platforms",
        },
        QueryTerm: {"conflict_codes"},
        WorkflowPlanSaveRequest: {"response_payload"},
    }

    for model, column_names in json_columns.items():
        for column_name in column_names:
            column_type = _table(model).c[column_name].type
            assert isinstance(column_type, JSON)
            assert not isinstance(column_type, JSONB)


def test_history_rows_are_immutable_shaped_and_never_have_updated_at() -> None:
    immutable_models: tuple[type[Base], ...] = (
        WorkflowVersion,
        MonitoringScope,
        WorkflowVersionScope,
        QueryTerm,
        WorkflowPlanSaveRequest,
    )
    assert "updated_at" in _table(WorkflowPlan).c
    for model in immutable_models:
        assert "created_at" in _table(model).c
        assert "updated_at" not in _table(model).c

    all_models: tuple[type[Base], ...] = (*immutable_models, WorkflowPlan)
    _assert_no_delete_cascade(_table(model) for model in all_models)
    for model in all_models:
        for relationship in model.__mapper__.relationships:
            assert "delete" not in relationship.cascade
            assert "delete-orphan" not in relationship.cascade


def test_plan_and_version_constraints_preserve_current_version_ownership() -> None:
    assert ("workspace_id", "id") in _unique_column_sets(_table(Project))
    assert ("workspace_id", "project_id", "id") in _unique_column_sets(
        _table(WorkflowPlan)
    )
    assert ("workflow_plan_id", "version_number") in _unique_column_sets(
        _table(WorkflowVersion)
    )
    assert ("workflow_plan_id", "id") in _unique_column_sets(_table(WorkflowVersion))
    assert ("workspace_id", "project_id", "id") in _unique_column_sets(
        _table(WorkflowVersion)
    )
    assert ("workspace_id", "project_id", "workflow_plan_id", "id") in _unique_column_sets(
        _table(WorkflowVersion)
    )

    plan_foreign_keys = _foreign_key_signatures(_table(WorkflowPlan))
    assert (
        ("workspace_id", "project_id"),
        ("projects.workspace_id", "projects.id"),
    ) in plan_foreign_keys
    assert (
        ("workspace_id", "project_id", "id", "current_version_id"),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.workflow_plan_id",
            "workflow_versions.id",
        ),
    ) in plan_foreign_keys
    assert _table(WorkflowPlan).c.current_version_id.nullable
    status_default = _table(WorkflowPlan).c.status.default
    assert isinstance(status_default, ColumnDefault)
    assert cast(str, status_default.arg) == "previewed"
    assert "status='previewed'" in _check_sql(_table(WorkflowPlan))
    assert (
        "flow_modeIN('periodic_monitoring','batch_research')"
        in _check_sql(_table(WorkflowPlan))
    )

    version_foreign_keys = _foreign_key_signatures(_table(WorkflowVersion))
    assert (
        ("workspace_id", "project_id", "workflow_plan_id"),
        (
            "workflow_plans.workspace_id",
            "workflow_plans.project_id",
            "workflow_plans.id",
        ),
    ) in version_foreign_keys

    version_unique_columns = _unique_column_sets(_table(WorkflowVersion))
    assert ("workflow_plan_id", "preview_fingerprint") not in version_unique_columns
    assert not _table(WorkflowVersion).c.preview_fingerprint.unique
    assert cast(String, _table(WorkflowVersion).c.preview_fingerprint.type).length == 71
    assert (
        "planning_statusIN('resolved','partially_resolved','held')"
        in _check_sql(_table(WorkflowVersion))
    )


def test_scope_association_and_query_term_constraints_close_tenant_boundaries() -> None:
    scope_unique_columns = _unique_column_sets(_table(MonitoringScope))
    assert ("project_id", "scope_key") in scope_unique_columns
    assert cast(String, _table(MonitoringScope).c.scope_key.type).length == 71
    assert ("workspace_id", "project_id", "id") in scope_unique_columns
    assert (
        ("workspace_id", "project_id"),
        ("projects.workspace_id", "projects.id"),
    ) in _foreign_key_signatures(_table(MonitoringScope))

    association_unique_columns = _unique_column_sets(_table(WorkflowVersionScope))
    assert ("workflow_version_id", "ordinal") in association_unique_columns
    assert (
        "workspace_id",
        "project_id",
        "workflow_version_id",
        "monitoring_scope_id",
    ) in association_unique_columns
    association_foreign_keys = _foreign_key_signatures(_table(WorkflowVersionScope))
    assert (
        ("workspace_id", "project_id", "workflow_version_id"),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.id",
        ),
    ) in association_foreign_keys
    assert (
        ("workspace_id", "project_id", "monitoring_scope_id"),
        (
            "monitoring_scopes.workspace_id",
            "monitoring_scopes.project_id",
            "monitoring_scopes.id",
        ),
    ) in association_foreign_keys

    assert ("workflow_version_id", "ordinal") in _unique_column_sets(_table(QueryTerm))
    assert not _table(QueryTerm).c.matched_scope_id.nullable
    assert (
        (
            "workspace_id",
            "project_id",
            "workflow_version_id",
            "matched_scope_id",
        ),
        (
            "workflow_version_scopes.workspace_id",
            "workflow_version_scopes.project_id",
            "workflow_version_scopes.workflow_version_id",
            "workflow_version_scopes.monitoring_scope_id",
        ),
    ) in _foreign_key_signatures(_table(QueryTerm))
    assert "ordinal>=0" in _check_sql(_table(WorkflowVersionScope))
    assert "ordinal>=0" in _check_sql(_table(QueryTerm))
    assert (
        "originIN('canonical','alias','include','official_account','seed_url',"
        "'fixture_candidate_expansion')"
        in _check_sql(_table(QueryTerm))
    )


def test_save_request_has_exact_idempotency_and_tenant_reference_constraints() -> None:
    assert (
        cast(String, _table(WorkflowPlanSaveRequest).c.idempotency_key_hash.type).length
        == 71
    )
    assert cast(String, _table(WorkflowPlanSaveRequest).c.request_hash.type).length == 71
    assert (
        "workspace_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
    ) in _unique_column_sets(_table(WorkflowPlanSaveRequest))

    save_request_foreign_keys = _foreign_key_signatures(_table(WorkflowPlanSaveRequest))
    assert (
        ("workspace_id", "project_id", "workflow_plan_id"),
        (
            "workflow_plans.workspace_id",
            "workflow_plans.project_id",
            "workflow_plans.id",
        ),
    ) in save_request_foreign_keys
    assert (
        ("workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.workflow_plan_id",
            "workflow_versions.id",
        ),
    ) in save_request_foreign_keys
    assert (
        "outcomeIN('created','semantic_no_op')"
        in _check_sql(_table(WorkflowPlanSaveRequest))
    )

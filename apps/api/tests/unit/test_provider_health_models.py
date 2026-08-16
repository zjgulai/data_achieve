from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.provider_health import (
    ProviderHealthRouteFeedback,
    ProviderHealthSnapshot,
)


def _table(
    model: type[ProviderHealthSnapshot] | type[ProviderHealthRouteFeedback],
) -> Table:
    return cast(Table, model.__table__)


def test_provider_health_snapshot_is_append_only_tenant_scoped_and_versioned() -> None:
    table = _table(ProviderHealthSnapshot)
    assert table.name == "provider_health_snapshots"
    assert "updated_at" not in table.c
    assert not ProviderHealthSnapshot.__mapper__.relationships
    assert ProviderHealthSnapshot.metadata is Base.metadata

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert {
        ("workspace_id", "project_id", "scope_key", "snapshot_version"),
        ("workspace_id", "project_id", "aggregation_key"),
        ("workspace_id", "project_id", "snapshot_digest"),
    } <= unique_sets
    foreign_keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert tuple(item.target_fullname for item in foreign_keys[0].elements) == (
        "projects.workspace_id",
        "projects.id",
    )

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_provider_health_snapshots_contract_version",
        "ck_provider_health_snapshots_version",
        "ck_provider_health_snapshots_status",
        "ck_provider_health_snapshots_counts",
        "ck_provider_health_snapshots_metrics",
        "ck_provider_health_snapshots_time_order",
        "ck_provider_health_snapshots_fixture_boundaries",
    } <= constraint_names


def test_route_feedback_is_append_only_and_preserves_version_identity() -> None:
    table = _table(ProviderHealthRouteFeedback)
    assert table.name == "provider_health_route_feedbacks"
    assert "updated_at" not in table.c
    assert not ProviderHealthRouteFeedback.__mapper__.relationships

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert {
        ("workspace_id", "project_id", "route_key", "feedback_version"),
        ("workspace_id", "project_id", "feedback_key"),
        ("workspace_id", "project_id", "feedback_digest"),
    } <= unique_sets


def test_provider_health_fixture_boundary_flags_default_false() -> None:
    common_names = (
        "health_probe_attempted",
        "provider_call_attempted",
        "credential_read_attempted",
        "actor_run",
        "browser_run",
        "llm_call",
        "raw_record_write",
        "dataset_write",
        "production_write_allowed",
    )
    for model in (ProviderHealthSnapshot, ProviderHealthRouteFeedback):
        table = _table(model)
        names: tuple[str, ...] = common_names
        if model is ProviderHealthRouteFeedback:
            names += (
                "catalog_mutation_applied",
                "automatic_route_switch_executed",
            )
        for name in names:
            column = table.c[name]
            assert isinstance(column.type, Boolean)
            assert column.nullable is False
            assert column.default is not None
            assert cast(bool, cast(Any, column.default).arg) is False

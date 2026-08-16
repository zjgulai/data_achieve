from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from data_intelligence_hub.services.workflow_execution.materialization import (
    materialization_unique_violation_constraint,
)


class DriverError(Exception):
    def __init__(self, *, sqlstate: str, constraint_name: str | None) -> None:
        super().__init__(constraint_name)
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


def _error(sqlstate: str, constraint_name: str | None) -> IntegrityError:
    return IntegrityError(
        "INSERT private",
        {"private": "value"},
        DriverError(sqlstate=sqlstate, constraint_name=constraint_name),
    )


def test_only_exact_materialization_23505_constraints_are_recoverable() -> None:
    for constraint in (
        "uq_workflow_lineage_materializations_idempotency",
        "uq_workflow_lineage_materializations_run",
        "uq_dataset_versions_source_workflow_run",
    ):
        assert (
            materialization_unique_violation_constraint(_error("23505", constraint)) == constraint
        )

    assert (
        materialization_unique_violation_constraint(
            _error("23505", "uq_raw_records_workflow_step_content_hash")
        )
        is None
    )
    assert (
        materialization_unique_violation_constraint(
            _error("23503", "uq_workflow_lineage_materializations_run")
        )
        is None
    )

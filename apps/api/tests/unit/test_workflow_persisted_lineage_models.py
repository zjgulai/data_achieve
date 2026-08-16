from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workflow_execution import StepRun
from data_intelligence_hub.schemas.automation import AutomationDatasetVersionResponse
from data_intelligence_hub.schemas.raw_record import RawRecordResponse
from data_intelligence_hub.services.automation_service import _dataset_version_response


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _unique_sets(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_signatures(
    table: Table,
) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    return {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def _constraint_names(table: Table) -> set[str]:
    return {
        cast(str, constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def _constraint_definitions(table: Table) -> set[str]:
    return {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_raw_record_supports_exclusive_legacy_or_workflow_lineage() -> None:
    table = _table(RawRecord)
    assert {
        "workflow_run_id",
        "workflow_step_run_id",
        "workflow_lineage_contract_version",
    } <= set(table.c.keys())
    assert table.c.source_id.nullable is True
    assert table.c.task_run_id.nullable is True
    assert table.c.workflow_run_id.nullable is True
    assert table.c.workflow_step_run_id.nullable is True
    assert isinstance(
        table.c.workflow_lineage_contract_version.type, type(table.c.record_type.type)
    )
    assert (
        "workflow_step_run_id",
        "content_hash",
    ) in _unique_sets(table)
    assert (
        ("workspace_id", "project_id", "workflow_run_id"),
        (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ),
    ) in _foreign_key_signatures(table)
    assert (
        ("workspace_id", "project_id", "workflow_run_id", "workflow_step_run_id"),
        (
            "step_runs.workspace_id",
            "step_runs.project_id",
            "step_runs.workflow_run_id",
            "step_runs.id",
        ),
    ) in _foreign_key_signatures(table)
    assert {
        "ck_raw_records_source_provenance",
        "ck_raw_records_workflow_lineage_contract",
    } <= _constraint_names(table)
    assert any(
        "workflow_lineage_contract_version IS NOT NULL" in definition
        for definition in _constraint_definitions(table)
    )


def test_step_run_has_composite_target_for_raw_record_tenant_fk() -> None:
    assert ("workspace_id", "project_id", "workflow_run_id", "id") in _unique_sets(_table(StepRun))


def test_dataset_version_supports_workflow_lineage_without_legacy_task_ids() -> None:
    table = _table(DatasetVersion)
    assert {
        "source_workflow_run_id",
        "source_workflow_step_run_ids",
        "source_raw_record_ids",
        "lineage_contract_version",
    } <= set(table.c.keys())
    assert table.c.source_workflow_run_id.nullable is True
    assert isinstance(table.c.source_workflow_step_run_ids.type, JSON)
    assert isinstance(table.c.source_raw_record_ids.type, JSON)
    assert (
        ("workspace_id", "project_id", "source_workflow_run_id"),
        (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ),
    ) in _foreign_key_signatures(table)
    assert "ck_dataset_versions_workflow_lineage_contract" in _constraint_names(table)
    assert any(
        "lineage_contract_version IS NOT NULL" in definition
        for definition in _constraint_definitions(table)
    )


def test_api_asset_schemas_accept_nullable_legacy_ids_and_v2_lineage() -> None:
    workspace_id = uuid4()
    project_id = uuid4()
    run_id = uuid4()
    step_id = uuid4()
    now = datetime.now(UTC)
    raw = RawRecordResponse(
        id=uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=None,
        task_run_id=None,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        workflow_lineage_contract_version="workflow_raw_record.v1",
        record_type="social_raw.v1",
        source_url=None,
        content={},
        content_hash="a" * 64,
        screenshot_url=None,
        collected_at=now,
        created_at=now,
    )
    version = AutomationDatasetVersionResponse(
        id=uuid4(),
        dataset_id=uuid4(),
        version_number=1,
        source_task_run_ids=[],
        source_workflow_run_id=run_id,
        source_workflow_step_run_ids=[str(step_id)],
        source_raw_record_ids=[str(raw.id)],
        lineage_contract_version="workflow_dataset_version.v1",
        selected_fields=[],
        cleaning_script=[],
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=now,
        export_preview={},
    )
    assert raw.task_run_id is None
    assert raw.workflow_run_id == run_id
    assert version.source_workflow_run_id == run_id
    assert version.source_raw_record_ids == [str(raw.id)]


def test_dataset_version_response_preserves_workflow_lineage() -> None:
    run_id = uuid4()
    step_id = uuid4()
    raw_record_id = uuid4()
    now = datetime.now(UTC)
    version = DatasetVersion(
        id=uuid4(),
        dataset_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        created_by_user_id=uuid4(),
        cleaning_plan_id=None,
        source_workflow_run_id=run_id,
        source_workflow_step_run_ids=[str(step_id)],
        source_raw_record_ids=[str(raw_record_id)],
        lineage_contract_version="workflow_dataset_version.v1",
        version_number=1,
        source_task_run_ids=[],
        selected_fields=["title"],
        cleaning_script=[],
        rows=[{"title": "fixture"}],
        export_preview={},
        row_count=1,
        average_completeness_percent=100,
        status="saved",
        created_at=now,
    )

    response = _dataset_version_response(version)

    assert response.source_workflow_run_id == run_id
    assert response.source_workflow_step_run_ids == [str(step_id)]
    assert response.source_raw_record_ids == [str(raw_record_id)]
    assert response.lineage_contract_version == "workflow_dataset_version.v1"

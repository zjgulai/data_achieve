from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest,
    WorkflowRun,
)
from data_intelligence_hub.models.workspace import Workspace


def workspace_lock_statement(workspace_id: uuid.UUID) -> Select[tuple[Workspace]]:
    return (
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def workflow_run_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> Select[tuple[WorkflowRun]]:
    return (
        select(WorkflowRun)
        .where(
            WorkflowRun.workspace_id == workspace_id,
            WorkflowRun.project_id == project_id,
            WorkflowRun.id == workflow_run_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def lock_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> Workspace | None:
    return (await session.execute(workspace_lock_statement(workspace_id))).scalar_one_or_none()


async def get_workflow_run_for_update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> WorkflowRun | None:
    result = await session.execute(
        workflow_run_lock_statement(workspace_id, project_id, workflow_run_id)
    )
    return result.scalar_one_or_none()


async def get_completed_materialization_request(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowLineageMaterializationRequest | None:
    result = await session.execute(
        select(WorkflowLineageMaterializationRequest).where(
            WorkflowLineageMaterializationRequest.workspace_id == workspace_id,
            WorkflowLineageMaterializationRequest.project_id == project_id,
            WorkflowLineageMaterializationRequest.created_by_user_id == created_by_user_id,
            WorkflowLineageMaterializationRequest.idempotency_scope == idempotency_scope,
            WorkflowLineageMaterializationRequest.idempotency_key_hash == idempotency_key_hash,
            WorkflowLineageMaterializationRequest.outcome == "completed",
        )
    )
    return result.scalar_one_or_none()


async def get_materialization_request_by_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> WorkflowLineageMaterializationRequest | None:
    result = await session.execute(
        select(WorkflowLineageMaterializationRequest).where(
            WorkflowLineageMaterializationRequest.workspace_id == workspace_id,
            WorkflowLineageMaterializationRequest.project_id == project_id,
            WorkflowLineageMaterializationRequest.workflow_run_id == workflow_run_id,
        )
    )
    return result.scalar_one_or_none()


async def get_dataset_version_by_workflow_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> DatasetVersion | None:
    result = await session.execute(
        select(DatasetVersion).where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.project_id == project_id,
            DatasetVersion.source_workflow_run_id == workflow_run_id,
        )
    )
    return result.scalar_one_or_none()


async def get_dataset_version_for_materialization_replay(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
) -> DatasetVersion | None:
    result = await session.execute(
        select(DatasetVersion).where(
            DatasetVersion.workspace_id == workspace_id,
            DatasetVersion.project_id == project_id,
            DatasetVersion.source_workflow_run_id == workflow_run_id,
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.id == dataset_version_id,
        )
    )
    return result.scalar_one_or_none()


async def list_raw_records_by_ids(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    raw_record_ids: Sequence[uuid.UUID],
) -> list[RawRecord]:
    if not raw_record_ids:
        return []
    result = await session.execute(
        select(RawRecord).where(
            RawRecord.workspace_id == workspace_id,
            RawRecord.project_id == project_id,
            RawRecord.id.in_(raw_record_ids),
        )
    )
    indexed = {item.id: item for item in result.scalars().all()}
    return [indexed[item] for item in raw_record_ids if item in indexed]


async def add_raw_records(
    session: AsyncSession,
    records: Sequence[RawRecord],
) -> tuple[RawRecord, ...]:
    frozen = tuple(records)
    session.add_all(frozen)
    await session.flush()
    return frozen


async def add_dataset_version(
    session: AsyncSession,
    version: DatasetVersion,
) -> DatasetVersion:
    session.add(version)
    await session.flush()
    return version


async def add_materialization_request(
    session: AsyncSession,
    request: WorkflowLineageMaterializationRequest,
) -> WorkflowLineageMaterializationRequest:
    session.add(request)
    await session.flush()
    return request


__all__ = [
    "add_dataset_version",
    "add_materialization_request",
    "add_raw_records",
    "get_completed_materialization_request",
    "get_dataset_version_for_materialization_replay",
    "get_dataset_version_by_workflow_run",
    "get_materialization_request_by_run",
    "get_workflow_run_for_update",
    "list_raw_records_by_ids",
    "lock_workspace",
    "workflow_run_lock_statement",
    "workspace_lock_statement",
]

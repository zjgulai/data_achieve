from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.raw_records import get_raw_record, list_raw_records
from data_intelligence_hub.services.exceptions import RawRecordNotFoundError


async def get_raw_records(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID | None,
    task_run_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> list[RawRecord]:
    return await list_raw_records(
        session,
        workspace.id,
        source_id=source_id,
        task_run_id=task_run_id,
        limit=limit,
        offset=offset,
    )


async def get_raw_record_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    raw_record_id: uuid.UUID,
) -> RawRecord:
    raw_record = await get_raw_record(session, workspace.id, raw_record_id)
    if raw_record is None:
        raise RawRecordNotFoundError
    return raw_record

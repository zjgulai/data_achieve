from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.raw_records import get_raw_record, list_raw_records
from data_intelligence_hub.services.exceptions import RawRecordNotFoundError

# 回执里的单条内容上限。完整内容仍可按 record id 查询。
RECORD_CONTENT_PREVIEW_CHARS = 4000


def build_record_preview(record: RawRecord) -> dict[str, Any]:
    """构造回执用的记录摘要。超长内容截断并标记。"""
    content: Any = record.content
    truncated = False
    encoded = json.dumps(content, ensure_ascii=False, default=str)
    if len(encoded) > RECORD_CONTENT_PREVIEW_CHARS:
        content = encoded[:RECORD_CONTENT_PREVIEW_CHARS] + "...[truncated]"
        truncated = True
    return {
        "id": str(record.id),
        "record_type": record.record_type,
        "source_url": record.source_url,
        "content": content,
        "content_truncated": truncated,
        "collected_at": record.collected_at.isoformat(),
    }


async def get_raw_records(
    session: AsyncSession,
    workspace: Workspace,
    source_id: uuid.UUID | None,
    task_run_id: uuid.UUID | None,
    limit: int,
    offset: int,
    project_id: uuid.UUID | None = None,
    domain: str | None = None,
) -> list[RawRecord]:
    return await list_raw_records(
        session,
        workspace.id,
        source_id=source_id,
        task_run_id=task_run_id,
        project_id=project_id,
        domain=domain,
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

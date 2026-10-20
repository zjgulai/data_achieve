"""工作区成员写入。

提交权按 ADR-007 D4 放在 service 层：repository 只 flush，
这里在业务步骤结束后 commit，再刷新对象。
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workspace import WorkspaceMember
from data_intelligence_hub.repositories.workspaces import (
    add_workspace_member,
    remove_workspace_member,
)


async def add_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = "member",
) -> WorkspaceMember:
    member = await add_workspace_member(session, workspace_id, user_id, role)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    removed = await remove_workspace_member(session, workspace_id, user_id)
    if removed:
        await session.commit()
    return removed

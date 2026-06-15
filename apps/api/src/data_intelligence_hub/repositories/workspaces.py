from __future__ import annotations

import uuid

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

DEMO_WORKSPACE_SLUG = "data-achieve-demo"


async def get_workspace_by_slug(session: AsyncSession, slug: str) -> Workspace | None:
    result = await session.execute(select(Workspace).where(Workspace.slug == slug))
    return result.scalar_one_or_none()


async def get_default_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Workspace | None:
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(
            case((Workspace.slug == DEMO_WORKSPACE_SLUG, 0), else_=1),
            Workspace.created_at.asc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_demo_workspace(session: AsyncSession) -> Workspace | None:
    return await get_workspace_by_slug(session, DEMO_WORKSPACE_SLUG)


async def ensure_demo_workspace_membership(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Workspace | None:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        return None

    if await user_belongs_to_workspace(session, user_id, workspace.id):
        return workspace

    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role="member"))
    await session.flush()
    return workspace


async def user_belongs_to_workspace(
    session: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(WorkspaceMember.id).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none() is not None

from __future__ import annotations

import uuid

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember

DEMO_WORKSPACE_SLUG = "data-achieve-demo"


async def get_workspace_by_slug(session: AsyncSession, slug: str) -> Workspace | None:
    result = await session.execute(select(Workspace).where(Workspace.slug == slug))
    return result.scalar_one_or_none()


async def get_workspace_by_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> Workspace | None:
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    return result.scalar_one_or_none()


async def get_default_workspace_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    prefer_demo: bool = False,
) -> Workspace | None:
    """用户的默认工作区。

    prefer_demo 为真时 demo 工作区排第一，保持演示与开发环境的行为。
    为假时个人工作区排第一，demo 只作兜底。生产环境用假值，避免
    所有用户默认共享同一个租户。
    """
    demo_rank = 0 if prefer_demo else 1
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(
            case((Workspace.slug == DEMO_WORKSPACE_SLUG, demo_rank), else_=1 - demo_rank),
            Workspace.created_at.asc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_workspace_for_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Workspace | None:
    """按成员关系取工作区。非成员返回 None，用于隔离校验。"""
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_workspaces_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[tuple[Workspace, str]]:
    """用户的全部工作区与角色，按创建时间排序。"""
    result = await session.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.created_at.asc())
    )
    return [(row[0], row[1]) for row in result.all()]


async def list_workspace_members(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[tuple[WorkspaceMember, User]]:
    """工作区成员与用户资料。"""
    result = await session.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    return [(row[0], row[1]) for row in result.all()]


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


async def add_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = "member",
) -> WorkspaceMember:
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
    session.add(member)
    # 提交权在 service 与 route 层，repository 只 flush。见 ADR-007 D4。
    await session.flush()
    await session.refresh(member)
    return member


async def remove_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return False
    await session.delete(member)
    # 提交权在 service 与 route 层，repository 只 flush。见 ADR-007 D4。
    await session.flush()
    return True

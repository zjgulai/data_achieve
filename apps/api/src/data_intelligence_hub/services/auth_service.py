from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.security import create_access_token, hash_password, verify_password
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.users import get_user_by_email
from data_intelligence_hub.repositories.workspaces import (
    ensure_demo_workspace_membership,
    get_default_workspace_for_user,
    get_workspace_by_slug,
)
from data_intelligence_hub.schemas.auth import LoginRequest, RegisterRequest
from data_intelligence_hub.services.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    WorkspaceNotFoundError,
)

TRAINING_WORKSPACE_NOTIFICATION_TYPE = "training_workspace_ready"


@dataclass(frozen=True)
class AuthSession:
    user: User
    workspace: Workspace
    access_token: str


async def register_user(session: AsyncSession, payload: RegisterRequest) -> AuthSession:
    existing_user = await get_user_by_email(session, str(payload.email))
    if existing_user is not None:
        raise DuplicateEmailError

    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        status="active",
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(
        name=f"{user.name}'s Workspace",
        slug=await _create_unique_workspace_slug(session, user.email),
        owner_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    demo_workspace = await ensure_demo_workspace_membership(session, user.id)
    if demo_workspace is not None:
        await _ensure_training_workspace_notification(session, user, demo_workspace)
    auth_workspace = demo_workspace or workspace

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateEmailError from exc

    await session.refresh(user)
    await session.refresh(auth_workspace)
    return AuthSession(
        user=user,
        workspace=auth_workspace,
        access_token=create_access_token(user.id),
    )


async def login_user(session: AsyncSession, payload: LoginRequest) -> AuthSession:
    user = await get_user_by_email(session, str(payload.email))
    if user is None or user.status != "active":
        raise InvalidCredentialsError
    if not verify_password(payload.password, user.password_hash):
        raise InvalidCredentialsError

    workspace = await _get_or_join_demo_workspace(session, user)
    if workspace is None:
        workspace = await get_default_workspace_for_user(session, user.id)
    if workspace is None:
        raise WorkspaceNotFoundError

    return AuthSession(user=user, workspace=workspace, access_token=create_access_token(user.id))


async def get_session_for_user(session: AsyncSession, user: User) -> AuthSession:
    workspace = await _get_or_join_demo_workspace(session, user)
    if workspace is None:
        workspace = await get_default_workspace_for_user(session, user.id)
    if workspace is None:
        raise WorkspaceNotFoundError
    return AuthSession(user=user, workspace=workspace, access_token=create_access_token(user.id))


async def _create_unique_workspace_slug(session: AsyncSession, email: str) -> str:
    base = _slugify(email.split("@", maxsplit=1)[0]) or "workspace"
    candidate = base
    if await get_workspace_by_slug(session, candidate) is None:
        return candidate

    while True:
        candidate = f"{base}-{uuid.uuid4().hex[:8]}"
        if await get_workspace_by_slug(session, candidate) is None:
            return candidate


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized[:80]


async def _get_or_join_demo_workspace(session: AsyncSession, user: User) -> Workspace | None:
    workspace = await ensure_demo_workspace_membership(session, user.id)
    if workspace is None:
        return None

    await _ensure_training_workspace_notification(session, user, workspace)
    await session.commit()
    await session.refresh(user)
    await session.refresh(workspace)
    return workspace


async def _ensure_training_workspace_notification(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
) -> None:
    existing_result = await session.execute(
        select(Notification.id)
        .where(
            Notification.user_id == user.id,
            Notification.notification_type == TRAINING_WORKSPACE_NOTIFICATION_TYPE,
            Notification.reference_type == "workspace",
            Notification.reference_id == workspace.id,
        )
        .limit(1)
    )
    if existing_result.scalar_one_or_none() is not None:
        return

    session.add(
        Notification(
            user_id=user.id,
            title="培训情报工作台已就绪",
            body="已接入项目、采集源、任务、信号、情报、报告和预警数据，可直接用于演示和培训。",
            notification_type=TRAINING_WORKSPACE_NOTIFICATION_TYPE,
            reference_type="workspace",
            reference_id=workspace.id,
            is_read=False,
        )
    )
    await session.flush()

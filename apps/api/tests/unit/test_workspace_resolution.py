"""工作区解析与租户隔离。

守四条边界：

1. 生产默认工作区是个人工作区，demo 只作兜底。
2. active_workspace Cookie 只在用户是成员时生效。
3. 生产注册与登录不再自动加入 demo 工作区。
4. 建项目的所有者是发起请求的用户，不是工作区所有者。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import (
    get_auth_context,
    get_authenticated_context,
    resolve_workspace_for_user,
)
from data_intelligence_hub.api.routes.projects import create_project_item
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.security import create_access_token, hash_password
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workspaces import (
    DEMO_WORKSPACE_SLUG,
    get_default_workspace_for_user,
)
from data_intelligence_hub.schemas.auth import LoginRequest, RegisterRequest
from data_intelligence_hub.schemas.project import ProjectCreateRequest
from data_intelligence_hub.services.auth_service import login_user, register_user


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    ids = {
        "demo_owner": uuid.uuid4(),
        "demo_ws": uuid.uuid4(),
        "member": uuid.uuid4(),
        "personal_ws": uuid.uuid4(),
        "shared_owner": uuid.uuid4(),
        "shared_ws": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["demo_owner"],
                    email="demo-owner@example.com",
                    password_hash=hash_password("test-secret-1"),
                    name="Demo Owner",
                    status="active",
                ),
                Workspace(
                    id=ids["demo_ws"],
                    name="Demo",
                    slug=DEMO_WORKSPACE_SLUG,
                    owner_id=ids["demo_owner"],
                ),
                User(
                    id=ids["member"],
                    email="member@example.com",
                    password_hash=hash_password("test-secret-1"),
                    name="Member",
                    status="active",
                ),
                Workspace(
                    id=ids["personal_ws"],
                    name="Personal",
                    slug="personal-ws",
                    owner_id=ids["member"],
                ),
                WorkspaceMember(
                    workspace_id=ids["personal_ws"], user_id=ids["member"], role="owner"
                ),
                # 该用户同时是 demo 成员：生产里默认仍应回个人工作区。
                WorkspaceMember(workspace_id=ids["demo_ws"], user_id=ids["member"], role="member"),
                User(
                    id=ids["shared_owner"],
                    email="shared-owner@example.com",
                    password_hash=hash_password("test-secret-1"),
                    name="Shared Owner",
                    status="active",
                ),
                Workspace(
                    id=ids["shared_ws"],
                    name="Shared",
                    slug="shared-ws",
                    owner_id=ids["shared_owner"],
                ),
                WorkspaceMember(
                    workspace_id=ids["shared_ws"], user_id=ids["shared_owner"], role="owner"
                ),
            ]
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch):
    for key in ("DEMO_MODE", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_default_workspace_prefers_personal_when_demo_not_preferred(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await get_default_workspace_for_user(
            session, _ids()["member"], prefer_demo=False
        )
    assert workspace is not None
    assert workspace.id == _ids()["personal_ws"]


@pytest.mark.asyncio
async def test_default_workspace_prefers_demo_when_asked(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await get_default_workspace_for_user(
            session, _ids()["member"], prefer_demo=True
        )
    assert workspace is not None
    assert workspace.id == _ids()["demo_ws"]


@pytest.mark.asyncio
async def test_resolve_workspace_honors_active_cookie(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        workspace = await resolve_workspace_for_user(
            session, _ids()["member"], str(_ids()["personal_ws"])
        )
    assert workspace is not None
    assert workspace.id == _ids()["personal_ws"]


@pytest.mark.asyncio
async def test_resolve_workspace_ignores_non_member_cookie(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """member 不是 shared_ws 成员，Cookie 必须被忽略。"""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    async with session_factory() as session:
        workspace = await resolve_workspace_for_user(
            session, _ids()["member"], str(_ids()["shared_ws"])
        )
    assert workspace is not None
    assert workspace.id == _ids()["personal_ws"]


@pytest.mark.asyncio
async def test_resolve_workspace_ignores_malformed_cookie(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    async with session_factory() as session:
        workspace = await resolve_workspace_for_user(
            session, _ids()["member"], "not-a-uuid"
        )
    assert workspace is not None
    assert workspace.id == _ids()["personal_ws"]


@pytest.mark.asyncio
async def test_auth_context_uses_active_workspace_cookie(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    token = create_access_token(_ids()["member"])
    async with session_factory() as session:
        context = await get_auth_context(
            session, token, str(_ids()["personal_ws"])
        )
    assert context.workspace.id == _ids()["personal_ws"]


@pytest.mark.asyncio
async def test_strict_context_uses_active_workspace_cookie(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    token = create_access_token(_ids()["shared_owner"])
    async with session_factory() as session:
        context = await get_authenticated_context(
            session, token, str(_ids()["shared_ws"])
        )
    assert context.workspace.id == _ids()["shared_ws"]


@pytest.mark.asyncio
async def test_production_register_does_not_join_demo(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    async with session_factory() as session:
        auth_session = await register_user(
            session,
            RegisterRequest(
                email="new-user@example.com",
                password="test-secret-1",
                name="New User",
            ),
        )
        demo_memberships = (
            await session.execute(
                select(WorkspaceMember)
                .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
                .where(
                    Workspace.slug == DEMO_WORKSPACE_SLUG,
                    WorkspaceMember.user_id == auth_session.user.id,
                )
            )
        ).all()
    assert auth_session.workspace.slug != DEMO_WORKSPACE_SLUG
    assert demo_memberships == []


@pytest.mark.asyncio
async def test_production_login_prefers_personal_workspace(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """member 同时是 demo 成员，生产登录仍回个人工作区。"""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    async with session_factory() as session:
        auth_session = await login_user(
            session,
            LoginRequest(email="member@example.com", password="test-secret-1"),
        )
    assert auth_session.workspace.id == _ids()["personal_ws"]


@pytest.mark.asyncio
async def test_create_project_owner_is_requesting_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """共享工作区里建项目，owner 是发起请求的人，不是工作区所有者。"""
    from data_intelligence_hub.api.deps import AuthContext

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        requesting_user = await session.get(User, _ids()["member"])
        assert shared_workspace is not None
        assert requesting_user is not None
        response = await create_project_item(
            ProjectCreateRequest(name="Isolation Check", domain="mixed"),
            session,
            AuthContext(user=requesting_user, workspace=shared_workspace),
        )
    assert response.owner_id == _ids()["member"]


@pytest.mark.asyncio
async def test_list_projects_does_not_leak_across_workspaces(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """在 shared_ws 建项目，personal_ws 的列表必须看不到。"""
    from data_intelligence_hub.api.deps import AuthContext
    from data_intelligence_hub.api.routes.projects import list_project_items

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        personal_workspace = await session.get(Workspace, _ids()["personal_ws"])
        requesting_user = await session.get(User, _ids()["shared_owner"])
        assert shared_workspace is not None
        assert personal_workspace is not None
        assert requesting_user is not None
        await create_project_item(
            ProjectCreateRequest(name="Tenant Scoped", domain="mixed"),
            session,
            AuthContext(user=requesting_user, workspace=shared_workspace),
        )
        visible = await list_project_items(session, personal_workspace, None, None)
    assert visible == []


@pytest.mark.asyncio
async def test_activate_workspace_sets_cookie(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from fastapi import Response

    from data_intelligence_hub.api.deps import WORKSPACE_COOKIE_NAME, AuthContext
    from data_intelligence_hub.api.routes.workspaces import activate_workspace_item

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        requesting_user = await session.get(User, _ids()["member"])
        assert shared_workspace is not None
        assert requesting_user is not None
        # 先让 member 加入 shared_ws。
        session.add(
            WorkspaceMember(
                workspace_id=shared_workspace.id,
                user_id=requesting_user.id,
                role="member",
            )
        )
        await session.commit()
        response = Response()
        await activate_workspace_item(
            shared_workspace.id,
            session,
            AuthContext(user=requesting_user, workspace=shared_workspace),
            response,
        )
    cookie = response.headers.get("set-cookie", "")
    assert f"{WORKSPACE_COOKIE_NAME}={shared_workspace.id}" in cookie


@pytest.mark.asyncio
async def test_activate_workspace_rejects_non_member(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from fastapi import HTTPException, Response

    from data_intelligence_hub.api.deps import AuthContext
    from data_intelligence_hub.api.routes.workspaces import activate_workspace_item

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        requesting_user = await session.get(User, _ids()["member"])
        assert shared_workspace is not None
        assert requesting_user is not None
        with pytest.raises(HTTPException) as exc:
            await activate_workspace_item(
                shared_workspace.id,
                session,
                AuthContext(user=requesting_user, workspace=shared_workspace),
                Response(),
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_add_member_requires_owner(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from fastapi import HTTPException

    from data_intelligence_hub.api.deps import AuthContext
    from data_intelligence_hub.api.routes.workspaces import (
        add_current_workspace_member,
    )
    from data_intelligence_hub.schemas.workspace import AddWorkspaceMemberRequest

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        requesting_user = await session.get(User, _ids()["member"])
        assert shared_workspace is not None
        assert requesting_user is not None
        with pytest.raises(HTTPException) as exc:
            await add_current_workspace_member(
                AddWorkspaceMemberRequest(email="shared-owner@example.com"),
                session,
                AuthContext(user=requesting_user, workspace=shared_workspace),
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_owner_adds_and_removes_member(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from data_intelligence_hub.api.deps import AuthContext
    from data_intelligence_hub.api.routes.workspaces import (
        add_current_workspace_member,
        remove_current_workspace_member,
    )
    from data_intelligence_hub.schemas.workspace import AddWorkspaceMemberRequest

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        owner = await session.get(User, _ids()["shared_owner"])
        assert shared_workspace is not None
        assert owner is not None
        context = AuthContext(user=owner, workspace=shared_workspace)
        added = await add_current_workspace_member(
            AddWorkspaceMemberRequest(email="member@example.com"),
            session,
            context,
        )
        assert added.user.email == "member@example.com"
        await remove_current_workspace_member(_ids()["member"], session, context)
        remaining = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == shared_workspace.id,
                WorkspaceMember.user_id == _ids()["member"],
            )
        )
        assert remaining.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_owner_cannot_remove_owner(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from fastapi import HTTPException

    from data_intelligence_hub.api.deps import AuthContext
    from data_intelligence_hub.api.routes.workspaces import (
        remove_current_workspace_member,
    )

    async with session_factory() as session:
        shared_workspace = await session.get(Workspace, _ids()["shared_ws"])
        owner = await session.get(User, _ids()["shared_owner"])
        assert shared_workspace is not None
        assert owner is not None
        with pytest.raises(HTTPException) as exc:
            await remove_current_workspace_member(
                owner.id,
                session,
                AuthContext(user=owner, workspace=shared_workspace),
            )
    assert exc.value.status_code == 403

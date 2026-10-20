"""鉴权依赖的两种模式。

守两条边界：

1. get_authenticated_context 严格拒绝。无 token、坏 token、非活跃用户都 401，
   与 DEMO_MODE 无关。
2. get_auth_context 在 demo_mode 关闭时同样 401；开启时才回退 demo workspace。

这两个函数的分工是 B1-07 的核心。写接口用前者，读接口暂用后者。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import (
    get_auth_context,
    get_authenticated_context,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.security import create_access_token, hash_password
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG


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
    """种两个 workspace：一个 demo，一个普通用户自己的。"""
    demo_owner_id = uuid.uuid4()
    demo_workspace_id = uuid.uuid4()
    member_id = uuid.uuid4()
    member_workspace_id = uuid.uuid4()

    async with factory() as session:
        session.add_all(
            [
                User(
                    id=demo_owner_id,
                    email="demo@example.com",
                    password_hash=hash_password("x"),
                    name="Demo Owner",
                    status="active",
                ),
                Workspace(
                    id=demo_workspace_id,
                    name="Demo",
                    slug=DEMO_WORKSPACE_SLUG,
                    owner_id=demo_owner_id,
                ),
                User(
                    id=member_id,
                    email="member@example.com",
                    password_hash=hash_password("x"),
                    name="Member",
                    status="active",
                ),
                Workspace(
                    id=member_workspace_id,
                    name="Member WS",
                    slug="member-ws",
                    owner_id=member_id,
                ),
                WorkspaceMember(
                    workspace_id=member_workspace_id,
                    user_id=member_id,
                    role="owner",
                ),
            ]
        )
        await session.commit()

    # 记下给用例用
    _seed.events = {  # type: ignore[attr-defined]
        "demo_workspace_id": demo_workspace_id,
        "member_id": member_id,
        "member_workspace_id": member_workspace_id,
    }


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch):
    """每个用例从干净的设置开始。"""
    for key in ("DEMO_MODE", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── get_authenticated_context：严格拒绝 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_strict_context_rejects_missing_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(Exception) as exc:
            await get_authenticated_context(session, None)
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_strict_context_rejects_invalid_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(Exception) as exc:
            await get_authenticated_context(session, "not-a-jwt")
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_strict_context_accepts_valid_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    member_id = _seed.events["member_id"]  # type: ignore[attr-defined]
    token = create_access_token(member_id)
    async with session_factory() as session:
        context = await get_authenticated_context(session, token)
    assert context.user.id == member_id
    assert context.workspace.id == _seed.events["member_workspace_id"]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_strict_context_ignores_demo_mode(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """开启 demo_mode 也不能让严格依赖放行无 token 请求。"""
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    async with session_factory() as session:
        with pytest.raises(Exception) as exc:
            await get_authenticated_context(session, None)
    assert getattr(exc.value, "status_code", None) == 401


# ── get_auth_context：受 demo_mode 控制 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_demo_context_rejects_when_demo_mode_disabled(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    async with session_factory() as session:
        with pytest.raises(Exception) as exc:
            await get_auth_context(session, None)
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_demo_context_falls_back_when_demo_mode_enabled(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    async with session_factory() as session:
        context = await get_auth_context(session, None)
    assert context.workspace.id == _seed.events["demo_workspace_id"]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_demo_context_uses_token_even_when_demo_enabled(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有 token 时不走 demo，落到 token 自己的工作区。"""
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    member_id = _seed.events["member_id"]  # type: ignore[attr-defined]
    token = create_access_token(member_id)
    async with session_factory() as session:
        context = await get_auth_context(session, token)
    assert context.workspace.id == _seed.events["member_workspace_id"]  # type: ignore[attr-defined]


def test_effective_demo_mode_defaults_closed_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    assert get_settings().effective_demo_mode is False


def test_effective_demo_mode_defaults_open_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    assert get_settings().effective_demo_mode is True

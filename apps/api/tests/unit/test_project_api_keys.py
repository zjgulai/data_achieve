"""项目级 API 密钥的单元守卫。

覆盖六件事：

1. 签发只返回一次明文，库里只存哈希。
2. 同一工作区的两个项目互不可见。
3. 撤销后鉴权失败。
4. 跨工作区查不到、撤不掉对方的密钥。
5. 迁移单 head，且接在最新版本之后。
6. MCP 中间件接受项目密钥，并把身份写入调用上下文。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import importlib.util
import inspect as python_inspect
import re
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType
from typing import NamedTuple

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from starlette.types import Receive, Scope, Send

import data_intelligence_hub.mcp_runtime.auth as auth_module
from data_intelligence_hub.core import config
from data_intelligence_hub.mcp_runtime.auth import (
    PROJECT_KEY_STATE_KEY,
    BearerTokenMiddleware,
    ProjectApiKeyContext,
)
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.project_api_keys import (
    list_keys,
    revoke_key,
)
from data_intelligence_hub.services.project_api_keys import (
    IssuedProjectApiKey,
    authenticate_key,
    hash_key,
    issue_key,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610200048_project_api_keys.py"
PLAINTEXT_PATTERN = re.compile(r"^dih_[0-9a-f]{8}_[0-9a-f]{32}$")

Scenario = Callable[[AsyncSession], Awaitable[None]]


class Seed(NamedTuple):
    """一段用例需要的租户数据。"""

    owner: User
    workspace_a: Workspace
    workspace_b: Workspace
    project_a1: Project
    project_a2: Project
    project_b1: Project


def _make_engine() -> AsyncEngine:
    return create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


async def _seed(session: AsyncSession) -> Seed:
    """建两个工作区与三个项目。工作区 A 有两个项目。"""
    owner = User(
        email=f"owner-{uuid.uuid4().hex}@example.com",
        password_hash="x",
        name="Owner",
    )
    session.add(owner)
    await session.flush()
    workspace_a = Workspace(
        name="Workspace A",
        slug=f"ws-a-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    workspace_b = Workspace(
        name="Workspace B",
        slug=f"ws-b-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    session.add_all([workspace_a, workspace_b])
    await session.flush()
    project_a1 = Project(
        workspace_id=workspace_a.id,
        name="Project A1",
        domain="mother_baby",
        owner_id=owner.id,
    )
    project_a2 = Project(
        workspace_id=workspace_a.id,
        name="Project A2",
        domain="mother_baby",
        owner_id=owner.id,
    )
    project_b1 = Project(
        workspace_id=workspace_b.id,
        name="Project B1",
        domain="mother_baby",
        owner_id=owner.id,
    )
    session.add_all([project_a1, project_a2, project_b1])
    await session.flush()
    return Seed(
        owner=owner,
        workspace_a=workspace_a,
        workspace_b=workspace_b,
        project_a1=project_a1,
        project_a2=project_a2,
        project_b1=project_b1,
    )


async def _with_session(callback: Scenario) -> None:
    """在内存 SQLite 上跑一段用例。"""
    engine = _make_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(session)
    finally:
        await engine.dispose()


ALLOWLIST = ("list_platforms", "collect", "list_records")


async def _issue(
    session: AsyncSession,
    seed: Seed,
    *,
    project: Project,
    label: str = "default",
    tool_allowlist: tuple[str, ...] = ALLOWLIST,
    daily_collect_quota: int = 100,
) -> IssuedProjectApiKey:
    """按项目签发一把密钥。工作区取自项目自身。"""
    return await issue_key(
        session,
        project_id=project.id,
        workspace_id=project.workspace_id,
        label=label,
        created_by_user_id=seed.owner.id,
        tool_allowlist=tool_allowlist,
        daily_collect_quota=daily_collect_quota,
    )


@pytest.mark.anyio
async def test_issue_returns_plaintext_once_and_stores_only_hash() -> None:
    """明文只在返回值里出现。行里只有 sha256 摘要与可读前缀。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await _issue(session, seed, project=seed.project_a1, label="  CI  ")
        await session.commit()
        stored = await session.scalar(
            select(ProjectApiKey).where(ProjectApiKey.id == issued.record.id)
        )
        assert stored is not None
        values = {
            column.name: getattr(stored, column.name) for column in ProjectApiKey.__table__.columns
        }
        observed["plaintext"] = issued.plaintext
        observed["repr"] = repr(issued)
        observed["prefix"] = stored.key_prefix
        observed["label"] = stored.label
        observed["key_hash"] = stored.key_hash
        observed["hash_matches"] = stored.key_hash == hash_key(issued.plaintext)
        observed["plaintext_in_columns"] = any(
            issued.plaintext == str(value) for value in values.values()
        )

    await _with_session(scenario)

    plaintext = str(observed["plaintext"])
    assert PLAINTEXT_PATTERN.fullmatch(plaintext) is not None
    assert plaintext not in str(observed["repr"])
    assert plaintext.startswith(f"{observed['prefix']}_")
    assert observed["label"] == "CI"
    assert observed["hash_matches"] is True
    assert observed["plaintext_in_columns"] is False
    assert len(str(observed["key_hash"])) == 64


@pytest.mark.anyio
async def test_two_projects_resolve_to_their_own_identity() -> None:
    """同一工作区的两个项目各签一把，解析结果互不相同。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued_a1 = await _issue(session, seed, project=seed.project_a1, label="A1")
        issued_a2 = await _issue(session, seed, project=seed.project_a2, label="A2")
        await session.commit()

        identity_a1 = await authenticate_key(session, issued_a1.plaintext)
        identity_a2 = await authenticate_key(session, issued_a2.plaintext)
        listed_a1 = await list_keys(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a1.id,
        )
        listed_a2 = await list_keys(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a2.id,
        )
        observed["identity_a1"] = None if identity_a1 is None else identity_a1.project_id
        observed["identity_a2"] = None if identity_a2 is None else identity_a2.project_id
        observed["listed_a1"] = [row.id for row in listed_a1]
        observed["listed_a2"] = [row.id for row in listed_a2]
        observed["project_a1"] = seed.project_a1.id
        observed["project_a2"] = seed.project_a2.id
        observed["key_a1"] = issued_a1.record.id
        observed["key_a2"] = issued_a2.record.id

    await _with_session(scenario)

    assert observed["identity_a1"] == observed["project_a1"]
    assert observed["identity_a2"] == observed["project_a2"]
    assert observed["identity_a1"] != observed["identity_a2"]
    assert observed["listed_a1"] == [observed["key_a1"]]
    assert observed["listed_a2"] == [observed["key_a2"]]


@pytest.mark.anyio
async def test_revoked_key_is_rejected() -> None:
    """撤销写入时间戳，之后的鉴权必须失败。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await _issue(session, seed, project=seed.project_a1)
        await session.commit()
        before = await authenticate_key(session, issued.plaintext)
        revoked = await revoke_key(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a1.id,
            key_id=issued.record.id,
        )
        await session.commit()
        after = await authenticate_key(session, issued.plaintext)
        observed["before"] = before is not None
        observed["revoked_at"] = None if revoked is None else revoked.revoked_at
        observed["after"] = after

    await _with_session(scenario)

    assert observed["before"] is True
    assert observed["revoked_at"] is not None
    assert observed["after"] is None


@pytest.mark.anyio
async def test_cross_workspace_reads_and_revokes_are_blocked() -> None:
    """跨工作区与跨项目都查不到、撤不掉目标密钥。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await _issue(session, seed, project=seed.project_a1)
        await session.commit()

        foreign_list = await list_keys(
            session,
            workspace_id=seed.workspace_b.id,
            project_id=seed.project_b1.id,
        )
        wrong_project_list = await list_keys(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a2.id,
        )
        foreign_revoke = await revoke_key(
            session,
            workspace_id=seed.workspace_b.id,
            project_id=seed.project_b1.id,
            key_id=issued.record.id,
        )
        await session.commit()
        still_valid = await authenticate_key(session, issued.plaintext)

        observed["foreign_list"] = list(foreign_list)
        observed["wrong_project_list"] = list(wrong_project_list)
        observed["foreign_revoke"] = foreign_revoke
        observed["still_valid"] = still_valid

    await _with_session(scenario)

    assert observed["foreign_list"] == []
    assert observed["wrong_project_list"] == []
    assert observed["foreign_revoke"] is None
    assert observed["still_valid"] is not None


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "project_api_keys_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_single_head_and_follows_latest_revision() -> None:
    """迁移必须接在 202610200047 之后，且全仓只有一个 head。"""
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1
    assert heads[0] == "202610200048"
    module = _load_migration()
    assert module.revision == "202610200048"
    assert module.down_revision == "202610200047"
    assert "This revision is source-only." in MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_downgrade_drops_project_api_keys() -> None:
    """downgrade 必须先删索引，再删表。"""
    module = _load_migration()
    downgrade_source = python_inspect.getsource(module.downgrade)
    assert 'drop_index("ix_project_api_keys_workspace_project"' in downgrade_source
    assert 'drop_table("project_api_keys")' in downgrade_source


@pytest.mark.anyio
async def test_middleware_accepts_project_key_and_attaches_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥通过鉴权后，scope.state 里带着工作区与项目。"""
    engine = _make_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    captured: dict[str, object] = {}

    async def ok_app(scope: Scope, receive: Receive, send: Send) -> None:
        del receive
        state = scope.get("state")
        captured["state"] = dict(state) if isinstance(state, dict) else {}
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    try:
        async with factory() as session:
            seed = await _seed(session)
            issued = await _issue(session, seed, project=seed.project_a1)
            workspace_id = seed.workspace_a.id
            project_id = seed.project_a1.id
            await session.commit()
        settings = config.Settings(SCRAPY_MCP_TOKEN="")
        monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
        transport = ASGITransport(app=BearerTokenMiddleware(ok_app, session_factory=factory))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/",
                headers={"Authorization": f"Bearer {issued.plaintext}"},
            )
    finally:
        await engine.dispose()

    assert response.status_code == 200
    state = captured["state"]
    assert isinstance(state, dict)
    identity = state.get(PROJECT_KEY_STATE_KEY)
    assert isinstance(identity, ProjectApiKeyContext)
    assert identity.workspace_id == workspace_id
    assert identity.project_id == project_id


@pytest.mark.anyio
async def test_middleware_rejects_unknown_project_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未知的 ``dih_`` 密钥必须返回 401，不回落到全局 token 的放行逻辑。"""
    engine = _make_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def ok_app(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    try:
        settings = config.Settings(SCRAPY_MCP_TOKEN="")
        monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
        transport = ASGITransport(app=BearerTokenMiddleware(ok_app, session_factory=factory))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/",
                headers={"Authorization": f"Bearer dih_deadbeef_{'0' * 32}"},
            )
    finally:
        await engine.dispose()

    assert response.status_code == 401
    assert response.json()["detail"] == "mcp_authentication_required"


@pytest.mark.anyio
async def test_allowlist_and_quota_are_persisted_and_authenticated() -> None:
    """白名单与额度必须落库，并从鉴权身份读回。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        issued = await _issue(
            session,
            seed,
            project=seed.project_a1,
            tool_allowlist=("list_platforms", "collect"),
            daily_collect_quota=7,
        )
        await session.commit()
        identity = await authenticate_key(session, issued.plaintext)
        assert identity is not None
        observed["allowlist"] = identity.tool_allowlist
        observed["quota"] = identity.daily_collect_quota
        observed["allows_collect"] = identity.allows_tool("collect")
        observed["allows_create_report"] = identity.allows_tool("create_report")

    await _with_session(scenario)
    assert observed["allowlist"] == ("list_platforms", "collect")
    assert observed["quota"] == 7
    assert observed["allows_collect"] is True
    assert observed["allows_create_report"] is False, "白名单外的工具必须被拒绝"


@pytest.mark.anyio
async def test_issue_rejects_empty_allowlist_and_non_positive_quota() -> None:
    """空白名单与零额度按配置错误拒绝，不静默放行。"""

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        with pytest.raises(ValueError, match="allowlist"):
            await _issue(session, seed, project=seed.project_a1, tool_allowlist=())
        with pytest.raises(ValueError, match="quota"):
            await _issue(session, seed, project=seed.project_a1, daily_collect_quota=0)

    await _with_session(scenario)


@pytest.mark.anyio
async def test_second_active_key_on_same_project_is_rejected() -> None:
    """每个项目最多一把未撤销的密钥。轮换必须先撤销后签发。"""
    rejected: dict[str, bool] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        # rollback 会让 ORM 对象过期，之后再读属性会触发惰性 IO。
        # 因此先把需要的标识全部取出。
        project_id = seed.project_a1.id
        workspace_id = seed.project_a1.workspace_id
        owner_id = seed.owner.id

        async def issue_second(label: str) -> IssuedProjectApiKey:
            return await issue_key(
                session,
                project_id=project_id,
                workspace_id=workspace_id,
                label=label,
                created_by_user_id=owner_id,
                tool_allowlist=ALLOWLIST,
                daily_collect_quota=100,
            )

        first = await issue_second("first")
        await session.commit()
        first_key_id = first.record.id

        try:
            await issue_second("second")
            await session.commit()
        except (IntegrityError, OperationalError):
            rejected["value"] = True
            await session.rollback()
        else:
            rejected["value"] = False
            return

        # 撤销第一把之后，可以再签一把。
        await revoke_key(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            key_id=first_key_id,
        )
        await session.commit()
        second = await issue_second("second")
        await session.commit()
        assert second.record.id != first_key_id

    await _with_session(scenario)
    assert rejected["value"] is True, "同一项目的第二把活跃密钥未被拒绝"

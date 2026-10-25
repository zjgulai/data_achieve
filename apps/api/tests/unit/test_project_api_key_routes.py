"""项目 API 密钥：签发、列表、撤销、权限与日额度。

覆盖 P0-C 的 REST 行为与额度硬拦。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import AuthContext
from data_intelligence_hub.api.routes.project_api_keys import (
    issue_project_api_key,
    list_project_api_keys,
    patch_project_api_key,
    revoke_project_api_key,
)
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.project_api_keys import (
    consume_daily_quota,
    create_key,
)
from data_intelligence_hub.schemas.project_api_key import (
    IssueProjectApiKeyRequest,
    ProjectApiKeyPatchRequest,
)


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
        "owner": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "member": uuid.uuid4(),
        "project": uuid.uuid4(),
        "other_user": uuid.uuid4(),
        "other_workspace": uuid.uuid4(),
        "other_project": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["owner"],
                    email="pk-owner@example.com",
                    password_hash="x",
                    name="Owner",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="PK WS",
                    slug="pk-ws",
                    owner_id=ids["owner"],
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"],
                    user_id=ids["owner"],
                    role="owner",
                ),
                User(
                    id=ids["member"],
                    email="pk-member@example.com",
                    password_hash="x",
                    name="Member",
                    status="active",
                ),
                WorkspaceMember(
                    workspace_id=ids["workspace"],
                    user_id=ids["member"],
                    role="member",
                ),
                Project(
                    id=ids["project"],
                    workspace_id=ids["workspace"],
                    name="PK Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["owner"],
                ),
                User(
                    id=ids["other_user"],
                    email="pk-other@example.com",
                    password_hash="x",
                    name="Other",
                    status="active",
                ),
                Workspace(
                    id=ids["other_workspace"],
                    name="Other WS",
                    slug="other-ws",
                    owner_id=ids["other_user"],
                ),
                Project(
                    id=ids["other_project"],
                    workspace_id=ids["other_workspace"],
                    name="Other Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["other_user"],
                ),
            ]
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


async def _context(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> AuthContext:
    user = await session.get(User, user_id)
    workspace = await session.get(Workspace, workspace_id)
    assert user is not None
    assert workspace is not None
    return AuthContext(user=user, workspace=workspace)


@pytest.mark.asyncio
async def test_issue_list_and_revoke_flow(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="质量检查",
                tool_allowlist=["web_search", "web_fetch"],
                daily_collect_quota=3,
            ),
            session,
            context,
        )
        assert issued.plaintext.startswith("dih_")
        assert issued.key_prefix.startswith("dih_")

        listed = await list_project_api_keys(_ids()["project"], session, context)
        assert len(listed) == 1
        assert listed[0].tool_allowlist == ["web_search", "web_fetch"]
        assert listed[0].daily_collect_quota == 3
        assert not hasattr(listed[0], "plaintext")

        await revoke_project_api_key(_ids()["project"], issued.id, session, context)

    async with session_factory() as fresh:
        context = await _context(fresh, _ids()["owner"], _ids()["workspace"])
        listed = await list_project_api_keys(_ids()["project"], fresh, context)
    assert listed[0].revoked_at is not None


@pytest.mark.asyncio
async def test_second_active_key_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="first",
                tool_allowlist=["web_search"],
                daily_collect_quota=5,
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await issue_project_api_key(
                _ids()["project"],
                IssueProjectApiKeyRequest(
                    label="second",
                    tool_allowlist=["web_search"],
                    daily_collect_quota=5,
                ),
                session,
                context,
            )
    assert exc.value.status_code == 409
    assert exc.value.detail == "project_api_key_active_exists"


@pytest.mark.asyncio
async def test_rotation_requires_revoke_first(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        first = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="v1", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        await revoke_project_api_key(_ids()["project"], first.id, session, context)
        rotated = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="v2", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )

    assert rotated.plaintext != first.plaintext
    assert rotated.id != first.id


@pytest.mark.asyncio
async def test_plain_member_cannot_manage_keys(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["member"], _ids()["workspace"])
        with pytest.raises(HTTPException) as exc:
            await issue_project_api_key(
                _ids()["project"],
                IssueProjectApiKeyRequest(
                    label="nope", tool_allowlist=["web_search"], daily_collect_quota=1
                ),
                session,
                context,
            )
    assert exc.value.status_code == 403
    assert exc.value.detail == "project_key_management_forbidden"


@pytest.mark.asyncio
async def test_project_of_other_workspace_is_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        with pytest.raises(HTTPException) as exc:
            await list_project_api_keys(_ids()["other_project"], session, context)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_daily_quota_is_atomic_and_resets_next_day(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        record = await create_key(
            session,
            project_id=_ids()["project"],
            workspace_id=_ids()["workspace"],
            label="quota",
            key_prefix="dih_test",
            key_hash="a" * 64,
            created_by_user_id=_ids()["owner"],
            tool_allowlist=["web_search"],
            daily_collect_quota=2,
        )
        await session.commit()

        assert await consume_daily_quota(session, record.id) is True
        assert await consume_daily_quota(session, record.id) is True
        assert await consume_daily_quota(session, record.id) is False
        await session.commit()

        # 模拟跨日：把 quota_date 拨到昨天，计数应重新开始。
        await session.execute(
            update(type(record))
            .where(type(record).id == record.id)
            .values(quota_date=datetime.now(UTC).date() - timedelta(days=1))
        )
        await session.commit()
        assert await consume_daily_quota(session, record.id) is True
        await session.commit()

        row = (
            await session.execute(select(type(record)).where(type(record).id == record.id))
        ).scalar_one()
        assert row.quota_used == 1


@pytest.mark.asyncio
async def test_patch_updates_allowlist_and_quota(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="ops", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        patched = await patch_project_api_key(
            _ids()["project"],
            issued.id,
            ProjectApiKeyPatchRequest(
                tool_allowlist=["web_search", "answer"], daily_collect_quota=10
            ),
            session,
            context,
        )
        assert patched.tool_allowlist == ["web_search", "answer"]
        assert patched.daily_collect_quota == 10


@pytest.mark.asyncio
async def test_issue_rejects_unknown_tool(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """签发与 PATCH 对齐：未登记的工具名在签发时就被拒。"""
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        with pytest.raises(HTTPException) as exc:
            await issue_project_api_key(
                _ids()["project"],
                IssueProjectApiKeyRequest(
                    label="bad", tool_allowlist=["not_a_tool"], daily_collect_quota=5
                ),
                session,
                context,
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "unknown_tool_in_allowlist"


@pytest.mark.asyncio
async def test_issue_accepts_every_registered_tool(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """注册表里的任何工具名都能签发（校验只拒未登记的，不擅自收窄）。"""
    from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES

    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="all",
                tool_allowlist=sorted(TOOL_POLICIES),
                daily_collect_quota=5,
            ),
            session,
            context,
        )
    assert sorted(issued.tool_allowlist) == sorted(TOOL_POLICIES)


@pytest.mark.asyncio
async def test_patch_rejects_unknown_tool(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="x", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["project"],
                issued.id,
                ProjectApiKeyPatchRequest(tool_allowlist=["not_a_tool"]),
                session,
                context,
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "unknown_tool_in_allowlist"


@pytest.mark.asyncio
async def test_patch_rejects_empty_allowlist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """PATCH 把白名单改成空列表与签发时空白名单同罪：400。"""
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="a", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["project"],
                issued.id,
                ProjectApiKeyPatchRequest(tool_allowlist=[]),
                session,
                context,
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "project_api_key_allowlist_required"


@pytest.mark.asyncio
async def test_patch_quota_out_of_range_is_422(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """schema 层 ge=1/le=100000 由 pydantic 拒绝，走 422 校验错误。"""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ProjectApiKeyPatchRequest(daily_collect_quota=0)
    with pytest.raises(pydantic.ValidationError):
        ProjectApiKeyPatchRequest(daily_collect_quota=100001)


@pytest.mark.asyncio
async def test_patch_all_none_is_400(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """两个可更新字段都缺省时没有可执行的更新，必须显式拒绝。"""
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="a", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["project"],
                issued.id,
                ProjectApiKeyPatchRequest(),
                session,
                context,
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "no_fields_to_update"


@pytest.mark.asyncio
async def test_patch_quota_only_keeps_allowlist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """只改额度时白名单保持不变。"""
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="a", tool_allowlist=["web_search", "web_fetch"], daily_collect_quota=5
            ),
            session,
            context,
        )
        patched = await patch_project_api_key(
            _ids()["project"],
            issued.id,
            ProjectApiKeyPatchRequest(daily_collect_quota=7),
            session,
            context,
        )
        assert patched.daily_collect_quota == 7
        assert patched.tool_allowlist == ["web_search", "web_fetch"]


@pytest.mark.asyncio
async def test_patch_key_of_other_project_is_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """key 必须同时命中 workspace+project 复合归属。

    同一工作区内造第二个项目：A 项目签的 key 拿到 B 项目路径下改，
    即使 key_id 真实存在也必须 404 project_api_key_not_found。
    """
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        second_project = Project(
            id=uuid.uuid4(),
            workspace_id=_ids()["workspace"],
            name="Second Project",
            domain="mixed",
            status="active",
            owner_id=_ids()["owner"],
        )
        session.add(second_project)
        await session.commit()
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="a", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                second_project.id,
                issued.id,
                ProjectApiKeyPatchRequest(daily_collect_quota=9),
                session,
                context,
            )
    assert exc.value.status_code == 404
    assert exc.value.detail == "project_api_key_not_found"


@pytest.mark.asyncio
async def test_patch_via_other_workspace_project_is_project_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """跨工作区项目在 _project_or_404 就被拒：project_not_found 先于 key 查找。"""
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        issued = await issue_project_api_key(
            _ids()["project"],
            IssueProjectApiKeyRequest(
                label="a", tool_allowlist=["web_search"], daily_collect_quota=5
            ),
            session,
            context,
        )
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["other_project"],
                issued.id,
                ProjectApiKeyPatchRequest(daily_collect_quota=9),
                session,
                context,
            )
    assert exc.value.status_code == 404
    assert exc.value.detail == "project_not_found"


@pytest.mark.asyncio
async def test_patch_unknown_key_is_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        context = await _context(session, _ids()["owner"], _ids()["workspace"])
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["project"],
                uuid.uuid4(),
                ProjectApiKeyPatchRequest(daily_collect_quota=9),
                session,
                context,
            )
    assert exc.value.status_code == 404
    assert exc.value.detail == "project_api_key_not_found"


@pytest.mark.asyncio
async def test_patch_by_plain_member_is_forbidden(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """非所有者不能改密钥：复用 _project_or_404 的 403 语义。"""
    async with session_factory() as session:
        context = await _context(session, _ids()["member"], _ids()["workspace"])
        with pytest.raises(HTTPException) as exc:
            await patch_project_api_key(
                _ids()["project"],
                uuid.uuid4(),
                ProjectApiKeyPatchRequest(daily_collect_quota=9),
                session,
                context,
            )
    assert exc.value.status_code == 403
    assert exc.value.detail == "project_key_management_forbidden"


# 旧 tool_policy.enforce_quota 耗尽硬拦测试已随模块删除（N1 Task 3 接线）。
# 等价覆盖在 tests/unit/test_mcp_tiktok_access.py::test_per_call_quota_exhaustion_rejects，
# 走 governed_mcp_tool 的端到端路径。

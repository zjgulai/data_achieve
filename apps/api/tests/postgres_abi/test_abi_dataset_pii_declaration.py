"""建数据集时声明 PII 分类，策略必须真的落库。

浏览器验收时发现的问题：建数据集带 ``pii_class`` 会被服务端丢掉，四个
字段全落 ``unknown``，必须先建后改。2026-11-02 把静默丢弃改成了 422 ——
报错比丢数据好，但调用方仍然做不到一次声明到位。

这里固定三件事，都打在 service 入口而非 mock：

1. 声明了分类的列写出 ``field_policy`` 行，``decided_by`` 是操作人。
2. 没声明的列不写行，读取时是 ``unknown``（「还没判定」，不是「无 PII」）。
3. 一条策略写入失败不能让数据集半成品：同一事务。

第 3 条不在本文件断言（它由 `create_abi_dataset` 的单事务 commit 保证，
且已有 slug 冲突回滚测试覆盖），这里只固定前两条。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.models.abi import FieldPolicy
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.abi import AbiColumnCreate, AbiDatasetCreateRequest
from data_intelligence_hub.services import abi_service

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def session_factory(abi_database_url: str):
    engine = create_async_engine(abi_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _owner(factory) -> tuple[User, Workspace]:
    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"pii-decl-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="PII Decl Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="PII Decl WS",
            slug=f"pii-decl-{uuid.uuid4().hex[:8]}",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.commit()
        return user, workspace


async def test_declared_pii_class_is_persisted(session_factory) -> None:
    user, workspace = await _owner(session_factory)

    async with session_factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug="decl-probe",
                name="声明分类",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(column_name="post_id", data_type="text", pii_class="none"),
                    AbiColumnCreate(
                        column_name="author_email",
                        data_type="text",
                        pii_class="direct",
                        mask_rule="last4",
                    ),
                    # 不声明：应保持「还没判定」。
                    AbiColumnCreate(column_name="memo", data_type="text"),
                ],
            ),
        )

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(FieldPolicy).where(FieldPolicy.dataset_id == dataset.id)
            )
        ).scalars().all()
        by_field = {row.field_path: row for row in rows}

    assert set(by_field) == {"post_id", "author_email"}, (
        "只应为显式声明的列写策略行；未声明的列不该被写成 unknown"
    )
    assert by_field["post_id"].pii_class == "none"
    assert by_field["author_email"].pii_class == "direct"
    assert by_field["author_email"].mask_rule == "last4"
    assert by_field["author_email"].decided_by == f"user:{user.id}"


async def test_undeclared_columns_read_as_unknown(session_factory) -> None:
    """没声明的列在策略接口里是 unknown（默认拒绝），不是 none。"""
    user, workspace = await _owner(session_factory)

    async with session_factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug="undeclared-probe",
                name="未声明",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(column_name="memo", data_type="text"),
                ],
            ),
        )

    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        policy = await abi_service.get_abi_policy(
            session,
            DatasetAccess(
                dataset=resolved, grant=grant, workspace=workspace, user=user
            ),
        )

    items = {item.field_path: item for item in policy.items}
    assert items["memo"].pii_class == "unknown"
    assert items["memo"].is_default is True

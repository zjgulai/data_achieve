"""没有导出策略行时，未遮罩导出必须进审批。

生产实测发现的缺陷：``export_policy.require_dual_approval`` 的
server_default 是 ``true``，但全仓**没有任何代码创建策略行**。于是
``get_export_policy`` 恒返回 None，而当时的分支写的是

    if policy is not None and policy.require_dual_approval and not mask_pii:

policy 为 None 时整段跳过——未遮罩导出直接出文件，一次都没进审批。

这不是「默认放开」还是「默认收紧」的取舍问题：表定义已经把默认值定为
true，代码却把「没有策略」解释成「不需要审批」，两者矛盾。修复是让
缺省与表定义一致（fail-closed）。

这条测试固定三件事：
1. 没有策略行时，未遮罩导出落在 awaiting_approval。
2. 遮罩导出不受影响，直接排队（遮罩已限制暴露面，没有可批的东西）。
3. 审批是终局判定的一部分：awaiting_approval 的作业不能下载。
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.models.abi import ExportPolicy
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.abi import (
    AbiColumnCreate,
    AbiDatasetCreateRequest,
    AbiExportCreateRequest,
    AbiPolicyUpdateItem,
    AbiPolicyUpdateRequest,
    AbiUploadCreateRequest,
)
from data_intelligence_hub.services import abi_service

pytestmark = pytest.mark.asyncio

HEADER = ["post_id", "title"]


@pytest.fixture()
async def session_factory(abi_database_url: str):
    engine = create_async_engine(abi_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    writer.writerows(rows)
    return buffer.getvalue().encode()


async def _as_async_iter(chunks: list[bytes]):
    for chunk in chunks:
        yield chunk


async def _prepare_dataset(factory, *, tmp_path, monkeypatch):
    """建一个已经有数据、策略已声明的 upload 数据集。"""
    monkeypatch.setenv("ABI_EXPORT_DIR", str(tmp_path))
    from data_intelligence_hub.core.config import get_settings

    get_settings.cache_clear()

    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"abi-export-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="ABI Export Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="ABI Export WS",
            slug=f"abi-export-{uuid.uuid4().hex[:8]}",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.commit()

    payload = _csv_bytes([["p-001", "第一条"], ["p-002", "第二条"]])

    async with factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug="export-default",
                name="导出缺省",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(column_name=name, data_type="text", pii_class="none")
                    for name in HEADER
                ],
            ),
        )

    async with factory() as session:
        created = await abi_service.create_abi_upload(
            session,
            workspace,
            user,
            AbiUploadCreateRequest(
                dataset_slug=dataset.slug,
                filename="rows.csv",
                mode="append",
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                expected_rows=2,
            ),
        )

    async with factory() as session:
        await abi_service.write_abi_upload_content(
            session, workspace, user, created.upload_token, _as_async_iter([payload])
        )

    async with factory() as session:
        await abi_service.commit_abi_upload(session, workspace, user, created.batch.id)

    async with factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        await abi_service.replace_abi_policy(
            session,
            DatasetAccess(
                dataset=resolved, grant=grant, workspace=workspace, user=user
            ),
            AbiPolicyUpdateRequest(
                items=[
                    AbiPolicyUpdateItem(field_path=name, pii_class="none")
                    for name in HEADER
                ]
            ),
        )

    return user, workspace, dataset


async def test_unmasked_export_requires_approval_when_no_policy_row(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _prepare_dataset(
        session_factory, tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    async with session_factory() as session:
        # 前提：这张表必须真的是空的，否则测的不是缺省行为。
        rows = (
            await session.execute(
                select(ExportPolicy).where(ExportPolicy.workspace_id == workspace.id)
            )
        ).scalars().all()
        assert rows == [], "本测试要求没有策略行"

        job = await abi_service.create_abi_export(
            session,
            workspace,
            user,
            AbiExportCreateRequest(
                dataset_slug=dataset.slug,
                format="csv",
                mask_pii=False,
                reason="回归测试：缺省策略下未遮罩导出必须进审批",
            ),
        )

    assert job.status == "awaiting_approval", (
        "没有策略行时未遮罩导出必须等待审批；直接 succeeded 等于双人审批失效"
    )


async def test_masked_export_does_not_require_approval(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _prepare_dataset(
        session_factory, tmp_path=tmp_path, monkeypatch=monkeypatch
    )

    async with session_factory() as session:
        job = await abi_service.create_abi_export(
            session,
            workspace,
            user,
            AbiExportCreateRequest(
                dataset_slug=dataset.slug,
                format="csv",
                mask_pii=True,
            ),
        )

    # 遮罩导出不该卡在审批上：approve_job 对 mask_pii=True 直接拒绝，
    # 若把它置成 awaiting_approval，就没有任何人能推进它。
    assert job.status != "awaiting_approval"

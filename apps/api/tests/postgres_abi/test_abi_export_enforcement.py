"""导出执行侧的策略与下载分级。

三个缺口，都在 worker / 下载路径上，同步创建路径拦得住、执行路径拦不住：

1. ``run_job`` 不读 ``ExportPolicy``。``allowed_formats`` 与
   ``max_rows_masked`` 只在创建时检查，任何直接写 ``ExportJob`` 的入口
   都能绕过；而 ``prepare_query(limit=None)`` 意味着导出可以拉走整张表。
2. 未分类（``unknown``）字段在未遮罩导出里原样明文写出。同步路径有
   ``_resolve_selection`` 拦，worker 路径没有。
3. 已撤销 grant 的创建人仍能下载自己此前的导出——包括未遮罩的。

这些断言都打在最外层入口（``run_job`` / ``get_abi_export_download``），
不测内部辅助函数，否则等于测了一条生产不会走的路径。
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.models.abi import ExportJob, ExportPolicy
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.abi import (
    AbiColumnCreate,
    AbiDatasetCreateRequest,
    AbiPolicyUpdateItem,
    AbiPolicyUpdateRequest,
    AbiUploadCreateRequest,
)
from data_intelligence_hub.services import abi_export, abi_service
from data_intelligence_hub.services.abi_errors import AbiServiceError

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


async def _dataset(factory, tmp_path, monkeypatch, *, rows: int = 2, policy=True):
    monkeypatch.setenv("ABI_EXPORT_DIR", str(tmp_path))
    from data_intelligence_hub.core.config import get_settings

    get_settings.cache_clear()

    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"exp-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="Export Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Export WS",
            slug=f"exp-{uuid.uuid4().hex[:8]}",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.commit()

    payload = _csv_bytes([[f"p-{i:03d}", f"标题{i}"] for i in range(rows)])

    async with factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug="export-side",
                name="导出执行侧",
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
                expected_rows=rows,
            ),
        )

    async with factory() as session:
        await abi_service.write_abi_upload_content(
            session, workspace, user, created.upload_token, _as_async_iter([payload])
        )

    async with factory() as session:
        await abi_service.commit_abi_upload(session, workspace, user, created.batch.id)

    if policy:
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


async def _queue_job(factory, workspace, dataset, **overrides) -> ExportJob:
    """直接写一条 queued 作业，绕过创建路径的策略检查。

    这正是要固定的攻击面：只要有人能写这张表，执行侧就必须自己把关。
    """
    async with factory() as session:
        job = ExportJob(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            dataset_id=dataset.id,
            created_by=overrides.pop("created_by", workspace.owner_id),
            format=overrides.pop("format", "csv"),
            mask_pii=overrides.pop("mask_pii", True),
            # create_job 存的是序列化后的 list，不是 {"filters": [...]} 包裹。
            filters=[],
            columns=list(HEADER),
            reason=overrides.pop("reason", None),
            status="queued",
            **overrides,
        )
        session.add(job)
        await session.commit()
        return job


async def test_run_job_rejects_format_not_allowed_by_policy(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _dataset(session_factory, tmp_path, monkeypatch)

    async with session_factory() as session:
        session.add(
            ExportPolicy(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                dataset_id=dataset.id,
                allowed_formats=["csv"],
                require_dual_approval=True,
            )
        )
        await session.commit()

    job = await _queue_job(session_factory, workspace, dataset, format="jsonl")

    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_export.run_job(session, job.id)


async def test_run_job_enforces_max_rows_masked(
    session_factory, tmp_path, monkeypatch
) -> None:
    """策略把上限压到 1，而数据有 2 行：必须失败，不能产出部分文件。"""
    user, workspace, dataset = await _dataset(
        session_factory, tmp_path, monkeypatch, rows=2
    )

    async with session_factory() as session:
        session.add(
            ExportPolicy(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                dataset_id=dataset.id,
                max_rows_masked=1,
                require_dual_approval=True,
            )
        )
        await session.commit()

    job = await _queue_job(session_factory, workspace, dataset, mask_pii=True)

    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_export.run_job(session, job.id)

    # 失败必须留下 failed 状态与错误码，而不是一个 succeeded 的半份文件。
    async with session_factory() as session:
        stored = await session.scalar(
            select(ExportJob).where(ExportJob.id == job.id)
        )
    assert stored is not None
    assert stored.status == "failed"
    assert stored.artifact_path is None


async def test_run_job_denies_unknown_pii_in_unmasked_export(
    session_factory, tmp_path, monkeypatch
) -> None:
    """未遮罩导出不得包含未分类字段。

    ``unknown`` 不等于「没有 PII」，它等于「还没判定」。遮罩导出输出
    ``***`` 是安全的；未遮罩导出会原样写出。
    """
    # policy=False：建数据集但不写策略，于是所有列都是 unknown。
    user, workspace, dataset = await _dataset(
        session_factory, tmp_path, monkeypatch, policy=False
    )

    job = await _queue_job(
        session_factory,
        workspace,
        dataset,
        mask_pii=False,
        reason="回归测试：未遮罩导出必须拒绝未分类字段",
    )

    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_export.run_job(session, job.id)


async def test_masked_export_allows_unknown_columns(
    session_factory, tmp_path, monkeypatch
) -> None:
    """反向确认：遮罩导出对 unknown 列是允许的（输出 ***）。"""
    user, workspace, dataset = await _dataset(
        session_factory, tmp_path, monkeypatch, policy=False
    )
    job = await _queue_job(session_factory, workspace, dataset, mask_pii=True)

    async with session_factory() as session:
        ran = await abi_export.run_job(session, job.id)

    assert ran.status == "succeeded"
    async with session_factory() as session:
        path = (
            await session.scalar(select(ExportJob).where(ExportJob.id == job.id))
        ).artifact_path
    assert path is not None
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert "标题0" not in text, "unknown 列在遮罩导出里必须是 ***"


async def test_revoked_creator_cannot_download(
    session_factory, tmp_path, monkeypatch
) -> None:
    """撤销 grant 后，创建人也不能再下载自己此前的导出。

    撤权必须同时切断历史产物的访问，否则「收回权限」只挡住新请求。
    """
    user, workspace, dataset = await _dataset(session_factory, tmp_path, monkeypatch)

    async with session_factory() as session:
        job = await abi_service.create_abi_export(
            session,
            workspace,
            user,
            __import__(
                "data_intelligence_hub.schemas.abi", fromlist=["AbiExportCreateRequest"]
            ).AbiExportCreateRequest(
                dataset_slug=dataset.slug, format="csv", mask_pii=True
            ),
        )

    async with session_factory() as session:
        await abi_export.run_job(session, job.id)

    # 撤掉 owner 在该 dataset 上的 grant。
    async with session_factory() as session:
        from sqlalchemy import delete

        from data_intelligence_hub.models.abi import AccessGrant

        await session.execute(
            delete(AccessGrant).where(
                AccessGrant.dataset_id == dataset.id,
                AccessGrant.user_id == user.id,
            )
        )
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_service.get_abi_export_download(
                session, workspace, user, job.id
            )

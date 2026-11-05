"""数据集删除端点。

删除不可逆，所以这里固定的不是「能删」而是**边界**：

1. 有进行中的导出/上传时 409 —— 否则 worker 会在表被删之后继续写，
   落到一个已不存在的 dataset 上，变成没人能再清理的孤儿行。
2. 只删 ``upload`` 型的物理表。``local_table`` 指向共享 raw 表，
   删数据集不等于删那张表里的数据。
3. 级联真的生效：列、策略、授权、批次、作业全部随目录行消失。
4. 磁盘产物同步清掉，不留孤儿文件。
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.models.abi import (
    AccessGrant,
    AuditLog,
    CatalogDataset,
    DatasetColumn,
    ExportJob,
    FieldPolicy,
    UploadBatch,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.abi import (
    AbiColumnCreate,
    AbiDatasetCreateRequest,
    AbiUploadBatchResponse,
    AbiUploadCreateRequest,
)
from data_intelligence_hub.services import abi_service
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


async def _setup(factory, tmp_path, monkeypatch, *, slug: str = "del-probe"):
    monkeypatch.setenv("ABI_EXPORT_DIR", str(tmp_path))
    from data_intelligence_hub.core.config import get_settings

    get_settings.cache_clear()

    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"del-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="Del Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Del WS",
            slug=f"del-{uuid.uuid4().hex[:8]}",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.commit()

    async with factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug=slug,
                name="删除探针",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(column_name="post_id", data_type="text", pii_class="none"),
                    AbiColumnCreate(column_name="title", data_type="text", pii_class="none"),
                ],
            ),
        )

    async with factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        access = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )
    return user, workspace, dataset, access


async def _upload_and_commit(factory, workspace, user, dataset) -> AbiUploadBatchResponse:
    # commit_abi_upload 返回的是响应 schema,不是 ORM UploadBatch;
    # 返回值只用于断言 batch 走完,计数断言直接查 ORM 模型。
    payload = _csv_bytes([["p-1", "第一条"], ["p-2", "第二条"]])
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
        return await abi_service.commit_abi_upload(
            session, workspace, user, created.batch.id
        )


async def _count(factory, model) -> int:
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def test_delete_removes_dataset_and_all_children(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset, access = await _setup(
        session_factory, tmp_path, monkeypatch
    )
    await _upload_and_commit(session_factory, workspace, user, dataset)

    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        fresh = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )
        result = await abi_service.delete_abi_dataset(session, fresh)

    assert result.deleted is True
    assert result.id == dataset.id

    for model in (CatalogDataset, DatasetColumn, FieldPolicy, AccessGrant, UploadBatch):
        assert await _count(session_factory, model) == 0, f"{model.__name__} 未级联删除"

    # 物理表也必须消失，否则下次建同名 slug 会撞到残留数据。
    async with session_factory() as session:
        from sqlalchemy import text as _text

        exists = await session.scalar(
            _text(
                "select count(*) from pg_tables "
                "where schemaname='raw' and tablename=:t"
            ),
            {"t": f"abi_upload_{dataset.id.hex}"},
        )
    assert exists == 0, "upload 物理表必须随数据集删除"

    # 审计:删除必须落 meta.audit_log(分区键与 occurred_at 同月)。
    async with session_factory() as session:
        audits = (
            (await session.execute(select(AuditLog).where(AuditLog.action == "abi_dataset_delete")))
            .scalars()
            .all()
        )
    assert len(audits) == 1, "删除必须写一条 audit_log"
    audit = audits[0]
    assert audit.object_id == str(dataset.id)
    assert audit.workspace_id == workspace.id
    assert audit.detail.get("slug") == "del-probe"
    assert audit.occurred_month == audit.occurred_at.date().replace(day=1)


async def test_delete_rejected_while_export_is_active(
    session_factory, tmp_path, monkeypatch
) -> None:
    """有排队/进行中的导出时拒绝删除。

    否则 worker 会在表被删之后继续写，落到已不存在的 dataset 上，
    变成没有任何入口能清理的孤儿行。
    """
    user, workspace, dataset, access = await _setup(
        session_factory, tmp_path, monkeypatch
    )

    async with session_factory() as session:
        session.add(
            ExportJob(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                dataset_id=dataset.id,
                created_by=user.id,
                format="csv",
                mask_pii=True,
                filters=[],
                columns=list(HEADER),
                status="queued",
            )
        )
        await session.commit()

    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        fresh = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )
        with pytest.raises(AbiServiceError) as exc:
            await abi_service.delete_abi_dataset(session, fresh)

    assert exc.value.detail == "dataset_has_active_exports"
    # 数据集必须还在。
    assert await _count(session_factory, CatalogDataset) == 1


async def test_delete_rejected_while_upload_is_pending(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset, access = await _setup(
        session_factory, tmp_path, monkeypatch
    )
    payload = _csv_bytes([["p-1", "第一条"]])

    async with session_factory() as session:
        await abi_service.create_abi_upload(
            session,
            workspace,
            user,
            AbiUploadCreateRequest(
                dataset_slug=dataset.slug,
                filename="pending.csv",
                mode="append",
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                expected_rows=1,
            ),
        )

    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        fresh = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )
        with pytest.raises(AbiServiceError) as exc:
            await abi_service.delete_abi_dataset(session, fresh)

    assert exc.value.detail == "dataset_has_active_uploads"
    assert await _count(session_factory, CatalogDataset) == 1


async def test_local_table_dataset_never_drops_shared_raw_table(
    session_factory, tmp_path, monkeypatch
) -> None:
    """``local_table`` 指向共享 raw 表，删数据集不得删那张表。

    这是删除最危险的一条：删掉 raw 表会连带毁掉别的工作区/采集链路
    写入的数据，而那些数据无法从本仓库恢复。
    """
    user, workspace, _, _ = await _setup(
        session_factory, tmp_path, monkeypatch, slug="shared-probe"
    )

    from sqlalchemy import text as _text

    # 造一张「共享」raw 表，让数据集挂上去。
    shared = "shared_raw_probe"
    async with session_factory() as session:
        await session.execute(_text(f'CREATE TABLE raw."{shared}" (id text)'))
        await session.execute(
            _text(f'INSERT INTO raw."{shared}" (id) VALUES (\'keep-me\')')
        )
        await session.commit()

    async with session_factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug="local-probe",
                name="共享表探针",
                source_kind="local_table",
                source_table=f"raw.{shared}",
                origin="test-origin",
            ),
        )

    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        from data_intelligence_hub.api.deps import DatasetAccess

        fresh = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )
        await abi_service.delete_abi_dataset(session, fresh)

    async with session_factory() as session:
        still_there = await session.scalar(
            _text("select to_regclass(:n) is not null"), {"n": f'raw."{shared}"'}
        )
        rows = await session.scalar(_text(f'SELECT count(*) FROM raw."{shared}"'))
    assert still_there is True, "共享 raw 表必须保留"
    assert rows == 1, "共享 raw 表的数据必须原样保留"

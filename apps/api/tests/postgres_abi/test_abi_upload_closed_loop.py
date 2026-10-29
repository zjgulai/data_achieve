"""上传闭环：上传 → commit 落库 → 可查询。

这条测试存在的理由：`commit_abi_upload` 曾经只把 ``upload_batch.status``
置成 ``committed`` 就返回，一行数据都没进表。接口报成功，紧接着查询
必然 409 ``dataset_source_not_ready``——因为 ``source_table`` 只由
``_upload_table_name()`` 在 commit 时回填，而 create 阶段对 upload 类型
禁止传入。

「不落库」和「查不到」是同一个缺陷的两端。只测其中一端都会漏：
- 只断言 status=committed → 旧实现也能过；
- 只断言查询有返回 → 前置没造对时失败原因指向别处。

所以这条测试断言三件事：commit 后 status、catalog 的 row_count 与
source_table、以及查询真的返回上传的那些行。
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.api.deps import DatasetAccess
from data_intelligence_hub.models.abi import CatalogDataset
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.abi import (
    AbiColumnCreate,
    AbiDatasetCreateRequest,
    AbiPolicyUpdateItem,
    AbiPolicyUpdateRequest,
    AbiQueryRequest,
    AbiUploadCreateRequest,
)
from data_intelligence_hub.services import abi_service

pytestmark = pytest.mark.asyncio

API_ROOT_MARKER = "abi_contract_test"


@pytest.fixture()
async def session_factory(abi_database_url: str):
    engine = create_async_engine(abi_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_owner_and_workspace(factory) -> tuple[User, Workspace]:
    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"abi-upload-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="ABI Upload Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="ABI Upload WS",
            slug=f"abi-upload-{uuid.uuid4().hex[:8]}",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.commit()
        return user, workspace


def _csv_bytes(header: list[str], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode()


async def _as_async_iter(chunks: list[bytes]):
    """把内存里的字节块包成路由层传给 service 的异步流。"""
    for chunk in chunks:
        yield chunk


async def test_upload_commit_loads_rows_and_makes_dataset_queryable(
    session_factory, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ABI_EXPORT_DIR", str(tmp_path))
    from data_intelligence_hub.core.config import get_settings

    get_settings.cache_clear()

    user, workspace = await _seed_owner_and_workspace(session_factory)

    header = ["post_id", "title", "view_count"]
    payload = _csv_bytes(
        header,
        [["p-001", "第一个帖子", "120"], ["p-002", "第二个帖子", "340"]],
    )

    async with session_factory() as session:
        dataset = await abi_service.create_abi_dataset(
            session,
            workspace,
            user,
            AbiDatasetCreateRequest(
                slug="upload-e2e",
                name="上传闭环",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(
                        column_name=name, data_type=dtype, pii_class="none"
                    )
                    for name, dtype in [
                        ("post_id", "text"),
                        ("title", "text"),
                        ("view_count", "bigint"),
                    ]
                ],
            ),
        )

    async with session_factory() as session:
        created = await abi_service.create_abi_upload(
            session,
            workspace,
            user,
            AbiUploadCreateRequest(
                dataset_slug=dataset.slug,
                filename="posts.csv",
                mode="append",
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                expected_rows=2,
            ),
        )

    # 走 HTTP 路由实际调用的那个函数，而不是 abi_upload.append_content。
    #
    # 这两条路径曾经是两份独立的写盘实现：append_content 记 actual_rows，
    # write_abi_upload_content 不记。commit 的前置检查要求 actual_rows 非空，
    # 于是经由 HTTP 的每一次上传都在 commit 阶段失败，报的还是误导性的
    # abi_upload_checksum_missing。这条测试原先直接调 append_content，
    # 正好绕开了缺陷，so 单测全绿而生产必然失败。
    async with session_factory() as session:
        await abi_service.write_abi_upload_content(
            session,
            workspace,
            user,
            created.upload_token,
            _as_async_iter([payload]),
        )

    async with session_factory() as session:
        committed = await abi_service.commit_abi_upload(
            session, workspace, user, created.batch.id
        )

    # 1) 批次状态与行数
    assert committed.status == "committed"
    assert committed.rows_loaded == 2, "commit 必须真的写进 2 行"
    assert committed.rows_rejected == 0

    # 2) catalog 被回写。source_table 只在 commit 时填，
    #    没有它查询必 409——这正是旧实现的断裂点。
    async with session_factory() as session:
        stored = await session.scalar(
            select(CatalogDataset).where(CatalogDataset.id == dataset.id)
        )
        assert stored is not None
        # 必须是两段式：上传表建在 raw，查询侧 _parse_source_table
        # 只接受 schema.table。单段名会让查询报 source_table_invalid。
        assert stored.source_table == f"raw.abi_upload_{dataset.id.hex}"
        assert stored.row_count == 2
        assert stored.last_loaded_at is not None

    # 3) 写 PII 策略。
    #
    # 这一步不是测试凑数，而是产品口径：没有策略行的字段按 unknown 处理，
    # 查询端一律 403 pii_policy_not_configured。fail-closed 是对的——
    # unknown 不等于「没有 PII」，它等于「还没判定」。测试必须显式声明，
    # 就像真实用户建完数据集要过一遍策略。
    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        access = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )
        await abi_service.replace_abi_policy(
            session,
            access,
            AbiPolicyUpdateRequest(
                items=[
                    AbiPolicyUpdateItem(field_path=name, pii_class="none")
                    for name in header
                ]
            ),
        )

    # 4) 查询真的能读到这些行
    #
    # access 由 service 层解析（api/deps 里的 require_dataset_role 是
    # FastAPI 依赖，测试不能直接调用）。DatasetAccess 只是一个 frozen
    # dataclass，手工组装即可。
    async with session_factory() as session:
        resolved_dataset, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "viewer"
        )
        access = DatasetAccess(
            dataset=resolved_dataset,
            grant=grant,
            workspace=workspace,
            user=user,
        )
        result = await abi_service.query_abi_dataset(
            session,
            access,
            AbiQueryRequest(limit=10, offset=0),
        )

    assert result.total == 2
    assert len(result.rows) == 2
    titles = sorted(row["title"] for row in result.rows)
    assert titles == ["第一个帖子", "第二个帖子"]

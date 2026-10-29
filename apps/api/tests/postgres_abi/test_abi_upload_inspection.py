"""上传批次检视与重试。

这条链路此前是断的：批次失败后 `failed` 是死路——既不能重新 PUT（状态
不允许），也不能重试（没有端点），只能新建批次再传一次。而失败原因
存在 `upload_error` 表里却没有任何接口能读，用户只看到「拒绝 N 行」。

三个断言方向：

1. 列表按 dataset 隔离，别的 dataset 的批次不能混进来。
2. 错误明细给出定位（行号/列/规则），且跨租户一律 404——不区分
   「不存在」与「无权」，否则状态码差异本身泄露存在性。
3. 重试只接受 `failed`，且不需要重新上传字节：文件已落盘并校验过。
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories import abi as abi_repo
from data_intelligence_hub.schemas.abi import (
    AbiColumnCreate,
    AbiDatasetCreateRequest,
    AbiPolicyUpdateItem,
    AbiPolicyUpdateRequest,
    AbiUploadCreateRequest,
)
from data_intelligence_hub.services import abi_service
from data_intelligence_hub.services.abi_errors import AbiServiceError

pytestmark = pytest.mark.asyncio

HEADER = ["post_id", "view_count"]


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


async def _setup(factory, tmp_path, monkeypatch, *, slug: str = "u5-probe"):
    monkeypatch.setenv("ABI_EXPORT_DIR", str(tmp_path))
    from data_intelligence_hub.core.config import get_settings

    get_settings.cache_clear()

    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"u5-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="U5 Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="U5 WS",
            slug=f"u5-{uuid.uuid4().hex[:8]}",
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
                name="上传检视",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(column_name="post_id", data_type="text", pii_class="none"),
                    AbiColumnCreate(
                        column_name="view_count", data_type="bigint", pii_class="none"
                    ),
                ],
            ),
        )

    # 策略未声明时查询会 403，这里只为让后续断言不被 PII 门禁挡住。
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


async def _upload(factory, workspace, user, dataset, payload: bytes):
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
                expected_rows=None,
            ),
        )
    async with factory() as session:
        await abi_service.write_abi_upload_content(
            session, workspace, user, created.upload_token, _as_async_iter([payload])
        )
    return created


async def test_list_uploads_is_scoped_to_dataset(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)
    other, other_workspace, other_dataset = await _setup(
        session_factory, tmp_path, monkeypatch, slug="u5-other"
    )

    await _upload(session_factory, workspace, user, dataset, _csv_bytes([["a", "1"]]))
    await _upload(
        session_factory, other_workspace, other, other_dataset, _csv_bytes([["b", "2"]])
    )

    async with session_factory() as session:
        listing = await abi_service.list_abi_uploads(
            session, workspace, user, dataset.slug
        )

    assert listing.total == 1
    assert listing.items[0].filename == "rows.csv"
    assert all(item.dataset_id == dataset.id for item in listing.items)


async def test_upload_errors_expose_location_not_values(
    session_factory, tmp_path, monkeypatch
) -> None:
    """全行被拒时批次进入 failed，且错误明细可读。"""
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)

    # view_count 声明为 bigint，塞非数字 → 该行被拒 → rows_loaded=0 → failed。
    created = await _upload(
        session_factory, workspace, user, dataset, _csv_bytes([["a", "not-a-number"]])
    )

    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_service.commit_abi_upload(
                session, workspace, user, created.batch.id
            )

    async with session_factory() as session:
        errors = await abi_service.get_abi_upload_errors(
            session, workspace, user, created.batch.id
        )

    assert errors.total >= 1
    first = errors.items[0]
    assert first.row_number == 1
    # 只给定位与规则名，不回显原始值。
    assert "not-a-number" not in (first.message or "")
    assert "not-a-number" not in first.rule_id


async def test_upload_errors_cross_workspace_is_404(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)
    _, other_ws, _ = await _setup(
        session_factory, tmp_path, monkeypatch, slug="u5-other"
    )
    created = await _upload(
        session_factory, workspace, user, dataset, _csv_bytes([["a", "1"]])
    )

    async with session_factory() as session:
        with pytest.raises(AbiServiceError) as exc:
            await abi_service.get_abi_upload_errors(
                session, other_ws, user, created.batch.id
            )

    # 必须是 404 而不是 403：区分二者等于承认这个 id 存在。
    assert exc.value.status_code == 404


async def test_retry_rejects_non_failed_batch(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)
    created = await _upload(
        session_factory, workspace, user, dataset, _csv_bytes([["a", "1"]])
    )

    async with session_factory() as session:
        with pytest.raises(AbiServiceError) as exc:
            await abi_service.retry_abi_upload(
                session, workspace, user, created.batch.id
            )

    assert exc.value.detail == "upload_not_retryable"


async def test_retry_is_repeatable_and_refreshes_errors(
    session_factory, tmp_path, monkeypatch
) -> None:
    """失败的批次必须可以反复重试，而不是死状态。

    重试能救的是**瞬时失败**（数据库抖动、锁冲突），不是数据本身不合格：
    ``commit_batch`` 会复核文件 sha256，落盘内容不能在重试时被替换，
    所以同一份坏数据重试仍然失败——这正是预期行为。

    这条测试固定两件事：
    1. 重试失败后批次回到 ``failed``，仍可再试，用户不会卡死。
    2. 重试前清空了旧错误，明细不会新旧混在一起。
    """
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)

    created = await _upload(
        session_factory, workspace, user, dataset, _csv_bytes([["a", "not-a-number"]])
    )

    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_service.commit_abi_upload(
                session, workspace, user, created.batch.id
            )

    async with session_factory() as session:
        first_errors = await abi_service.get_abi_upload_errors(
            session, workspace, user, created.batch.id
        )
    assert first_errors.total >= 1

    # 同一份坏数据重试：仍失败，但批次必须留在 failed 而不是变成不可推进的状态。
    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_service.retry_abi_upload(
                session, workspace, user, created.batch.id
            )

    async with session_factory() as session:
        batch = await abi_repo.get_upload_batch(
            session, workspace.id, created.batch.id
        )
    assert batch is not None
    assert batch.status == "failed", "重试失败后必须仍可再次重试"

    async with session_factory() as session:
        second_errors = await abi_service.get_abi_upload_errors(
            session, workspace, user, created.batch.id
        )
    # 清空重写后条数应与第一次相同，而不是累加成两倍。
    assert second_errors.total == first_errors.total


async def test_retry_never_touches_a_committed_batch(
    session_factory, tmp_path, monkeypatch
) -> None:
    """已提交的批次不能被重试改回 uploaded。

    这是并发复核抓到的 critical：先前 ``retry`` 在锁外用无条件 ORM UPDATE
    翻状态，两个并发重试能把 committed 打回 uploaded，随后失败清理按
    batch id 删掉第一次成功写入的全部行。数据静默消失，而 catalog 的
    row_count 仍停在旧值。

    状态转换现在只在 ``commit_batch`` 的行锁内发生，且只接受 failed。
    这条测试从外部固定那个不变量：committed 的批次重试后被拒，且状态、
    行数一概不变。
    """
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)
    created = await _upload(
        session_factory, workspace, user, dataset, _csv_bytes([["a", "1"], ["b", "2"]])
    )

    async with session_factory() as session:
        committed = await abi_service.commit_abi_upload(
            session, workspace, user, created.batch.id
        )
    assert committed.status == "committed"
    assert committed.rows_loaded == 2

    async with session_factory() as session:
        with pytest.raises(AbiServiceError) as exc:
            await abi_service.retry_abi_upload(
                session, workspace, user, created.batch.id
            )
    assert exc.value.detail == "upload_not_retryable"

    async with session_factory() as session:
        batch = await abi_repo.get_upload_batch(
            session, workspace.id, created.batch.id
        )
    assert batch is not None
    assert batch.status == "committed", "重试不得改写已提交批次的状态"
    assert batch.rows_loaded == 2, "计数不得被清零"


async def test_retry_denied_keeps_batch_failed_and_errors_intact(
    session_factory, tmp_path, monkeypatch
) -> None:
    """权限不足时重试必须在改任何状态之前拒绝。

    先前 retry 先删 upload_error、把状态改成 uploaded 并提交，再去
    commit_batch 里做 publisher 复核。于是 replace 模式的批次被降权后
    重试：返回 403，但批次已停在 uploaded——重试再拒、commit 也拒、
    同一份文件又因唯一约束无法重新上传，数据集对该文件永久卡死，
    失败明细也一起没了。

    现在权限判定在前，且状态转换在 commit_batch 行锁内。
    """
    user, workspace, dataset = await _setup(session_factory, tmp_path, monkeypatch)

    created = await _upload(
        session_factory, workspace, user, dataset, _csv_bytes([["a", "not-a-number"]])
    )
    async with session_factory() as session:
        with pytest.raises(AbiServiceError):
            await abi_service.commit_abi_upload(
                session, workspace, user, created.batch.id
            )

    async with session_factory() as session:
        before = await abi_service.get_abi_upload_errors(
            session, workspace, user, created.batch.id
        )
    assert before.total >= 1

    # 造一个只读成员：他既不是上传人，也没有 admin，重试必须 403。
    other = User(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        name="U5 Viewer",
        status="active",
    )
    async with session_factory() as session:
        session.add(other)
        await session.commit()

    from data_intelligence_hub.api.deps import DatasetAccess
    from data_intelligence_hub.schemas.abi import AbiGrantCreateRequest

    async with session_factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, "admin"
        )
        await abi_service.create_abi_grant(
            session,
            DatasetAccess(
                dataset=resolved, grant=grant, workspace=workspace, user=user
            ),
            AbiGrantCreateRequest(user_id=other.id, role="viewer"),
        )

    async with session_factory() as session:
        with pytest.raises(AbiServiceError) as exc:
            await abi_service.retry_abi_upload(
                session, workspace, other, created.batch.id
            )
    assert exc.value.status_code == 403

    async with session_factory() as session:
        batch = await abi_repo.get_upload_batch(
            session, workspace.id, created.batch.id
        )
    assert batch is not None
    assert batch.status == "failed", "被拒的重试不得改动状态"

    async with session_factory() as session:
        after = await abi_service.get_abi_upload_errors(
            session, workspace, user, created.batch.id
        )
    assert after.total == before.total, "被拒的重试不得删掉失败明细"

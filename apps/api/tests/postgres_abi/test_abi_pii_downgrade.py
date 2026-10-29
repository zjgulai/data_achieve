"""PII 策略的降级保护与遮罩一致性。

三条控制，每条都对应一个真实可被利用的缺口：

1. **降级需要 admin + 理由。** 未遮罩导出要 admin 校验、双人审批、
   >= 10 字理由。而把字段从 ``direct`` 改成 ``none`` 只需 publisher——
   改一行策略就能拿到明文，三重门禁形同虚设。
2. **提交是增量的。** 全量替换会把未提交列写成 ``unknown``，于是
   ``direct → unknown → none`` 分两步即可洗掉分类，绕开 1。
3. **遮罩只有一份实现。** worker 路径的 ``PII_MASKED_CLASSES`` 曾不含
   ``quasi``，异步导出对 ``quasi`` 字段**原样明文输出**，而在线查询
   遮成「前 2 后 1」。``direct → quasi`` 因此是一次实质降级。
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
from data_intelligence_hub.models.abi import FieldPolicy
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.abi import (
    AbiColumnCreate,
    AbiDatasetCreateRequest,
    AbiGrantCreateRequest,
    AbiPolicyUpdateItem,
    AbiPolicyUpdateRequest,
    AbiUploadCreateRequest,
)
from data_intelligence_hub.services import abi_service
from data_intelligence_hub.services.abi_errors import AbiServiceError
from data_intelligence_hub.services.abi_query import mask_value

HEADER = ["post_id", "author_email", "note"]


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


async def _dataset_with_rows(factory, tmp_path, monkeypatch):
    monkeypatch.setenv("ABI_EXPORT_DIR", str(tmp_path))
    from data_intelligence_hub.core.config import get_settings

    get_settings.cache_clear()

    async with factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"pii-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            name="PII Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            id=uuid.uuid4(),
            name="PII WS",
            slug=f"pii-{uuid.uuid4().hex[:8]}",
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
                slug="pii-probe",
                name="PII 探针",
                source_kind="upload",
                columns=[
                    AbiColumnCreate(column_name=name, data_type="text", pii_class="none")
                    for name in HEADER
                ],
            ),
        )

    payload = _csv_bytes([["p-1", "a@example.com", "备注一"]])

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
                expected_rows=1,
            ),
        )

    async with factory() as session:
        await abi_service.write_abi_upload_content(
            session, workspace, user, created.upload_token, _as_async_iter([payload])
        )

    async with factory() as session:
        await abi_service.commit_abi_upload(session, workspace, user, created.batch.id)

    return user, workspace, dataset


async def _access(factory, workspace, user, dataset, role: str) -> DatasetAccess:
    async with factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, user, dataset.slug, role
        )
        return DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=user
        )


async def _publisher_member(factory, workspace, owner, dataset):
    """建一个真实的 publisher 成员。

    不能靠给 owner 传 ``min_role="publisher"`` 来「降级」：workspace owner
    的 grant 恒为 admin，``min_role`` 只是最低门槛，不会削弱实际角色。
    要测「publisher 能不能降级」，就必须有一个真正的 publisher。

    授权必须由 owner（admin）发起：``create_abi_grant`` 自己要 admin。
    """
    publisher = User(
        id=uuid.uuid4(),
        email=f"publisher-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        name="PII Publisher",
        status="active",
    )
    async with factory() as session:
        session.add(publisher)
        await session.commit()

    admin_access = await _access(factory, workspace, owner, dataset, "admin")
    async with factory() as session:
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session, workspace, owner, dataset.slug, "admin"
        )
        owner_access = DatasetAccess(
            dataset=resolved, grant=grant, workspace=workspace, user=owner
        )
        await abi_service.create_abi_grant(
            session,
            owner_access,
            AbiGrantCreateRequest(user_id=publisher.id, role="publisher"),
        )
    _ = admin_access
    return publisher


async def _set_classes(factory, access, mapping: dict[str, str], reason=None):
    async with factory() as session:
        # access 里的 ORM 对象来自另一个 session，这里重新取一份，
        # 避免跨 session 实例被误当成已持久化。
        resolved, grant = await abi_service._resolve_dataset_for_user(
            session,
            access.workspace,
            access.user,
            access.dataset.slug,
            access.grant.role,
        )
        fresh = DatasetAccess(
            dataset=resolved, grant=grant, workspace=access.workspace, user=access.user
        )
        return await abi_service.replace_abi_policy(
            session,
            fresh,
            AbiPolicyUpdateRequest(
                items=[
                    AbiPolicyUpdateItem(field_path=name, pii_class=cls)
                    for name, cls in mapping.items()
                ],
                reason=reason,
            ),
        )


@pytest.mark.asyncio
async def test_publisher_cannot_downgrade_direct_to_none(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _dataset_with_rows(
        session_factory, tmp_path, monkeypatch
    )
    admin_access = await _access(session_factory, workspace, user, dataset, "admin")

    # 先由 admin 建立「author_email 是 direct」的基线。
    await _set_classes(
        session_factory,
        admin_access,
        {"post_id": "none", "author_email": "direct", "note": "none"},
    )

    publisher = await _publisher_member(session_factory, workspace, user, dataset)
    publisher_access = await _access(session_factory, workspace, publisher, dataset, "publisher")
    with pytest.raises(AbiServiceError) as exc:
        await _set_classes(
            session_factory,
            publisher_access,
            {"author_email": "none"},
            reason="即使是 admin 也还没到理由检查，publisher 应先被角色拒",
        )

    assert "pii_downgrade_requires_admin" in str(exc.value), (
        "publisher 把 direct 改成 none 必须被拒；这条路径绕过未遮罩导出"
        "所需的 admin + 双人审批 + 理由"
    )


@pytest.mark.asyncio
async def test_admin_downgrade_requires_substantive_reason(
    session_factory, tmp_path, monkeypatch
) -> None:
    user, workspace, dataset = await _dataset_with_rows(
        session_factory, tmp_path, monkeypatch
    )
    access = await _access(session_factory, workspace, user, dataset, "admin")

    await _set_classes(
        session_factory,
        access, {"post_id": "none", "author_email": "secret", "note": "none"}
    )

    with pytest.raises(AbiServiceError) as exc:
        await _set_classes(session_factory, access, {"author_email": "none"}, reason="短")
    assert "pii_downgrade_reason_required" in str(exc.value)

    # 有实质理由时放行。
    result = await _set_classes(
        session_factory,
        access,
        {"author_email": "none"},
        reason="作者要求删除邮箱，已获书面授权，工单 ABI-2026-0042",
    )
    classes = {item.field_path: item.pii_class for item in result.items}
    assert classes["author_email"] == "none"


@pytest.mark.asyncio
async def test_partial_update_keeps_untouched_columns(
    session_factory, tmp_path, monkeypatch
) -> None:
    """只提交一列时，其余列的分类必须原样保留。

    全量替换会把未提交列写成 unknown，而 unknown 被视为「首次分类」，
    于是 direct → unknown → none 可以分两步洗掉分类。
    """
    user, workspace, dataset = await _dataset_with_rows(
        session_factory, tmp_path, monkeypatch
    )
    access = await _access(session_factory, workspace, user, dataset, "admin")

    await _set_classes(
        session_factory,
        access, {"post_id": "none", "author_email": "direct", "note": "quasi"}
    )
    # 只改 note。
    result = await _set_classes(
        session_factory, access, {"note": "none"}, reason="备注不是 PII，误标了"
    )

    classes = {item.field_path: item.pii_class for item in result.items}
    assert classes["author_email"] == "direct", "未提交列不该被清成 unknown"
    assert classes["note"] == "none"


@pytest.mark.asyncio
async def test_direct_to_quasi_is_a_downgrade(
    session_factory, tmp_path, monkeypatch
) -> None:
    """direct → quasi 也是降级：quasi 在 worker 路径曾被原样输出。"""
    user, workspace, dataset = await _dataset_with_rows(
        session_factory, tmp_path, monkeypatch
    )
    access = await _access(session_factory, workspace, user, dataset, "admin")
    await _set_classes(
        session_factory,
        access, {"post_id": "none", "author_email": "direct", "note": "none"}
    )

    publisher = await _publisher_member(session_factory, workspace, user, dataset)
    publisher_access = await _access(session_factory, workspace, publisher, dataset, "publisher")
    with pytest.raises(AbiServiceError) as exc:
        await _set_classes(session_factory, publisher_access, {"author_email": "quasi"})
    assert "pii_downgrade_requires_admin" in str(exc.value)


def test_quasi_is_masked_everywhere() -> None:
    """quasi 必须在遮罩集合内，且默认不是明文。

    这条是纯函数断言，故意不依赖数据库：worker 与在线路径共用这个函数，
    集合一旦漏掉 quasi，异步导出会原样输出明文。
    """
    assert mask_value("张三丰", "quasi", None) != "张三丰"
    assert mask_value("张三丰", "quasi", None) == "***"


def test_unknown_mask_rule_falls_back_to_redact() -> None:
    """规则拼错不能放行。API 层已限枚举，这里防的是历史脏数据。"""
    assert mask_value("secret-value", "direct", "last9typo") == "***"


def test_mask_rule_is_honoured() -> None:
    assert mask_value("13800138000", "direct", "last4") == "***8000"
    # hash 是定长十六进制，不含原值任何子串
    hashed = mask_value("13800138000", "direct", "hash")
    assert isinstance(hashed, str) and len(hashed) == 32
    assert "13800138000" not in hashed


@pytest.mark.asyncio
async def test_policy_rows_are_not_rebuilt_on_every_save(
    session_factory, tmp_path, monkeypatch
) -> None:
    """增量更新不该删掉重插：那会覆盖 decided_by，审计上无法追责。"""
    user, workspace, dataset = await _dataset_with_rows(
        session_factory, tmp_path, monkeypatch
    )
    access = await _access(session_factory, workspace, user, dataset, "admin")

    await _set_classes(
        session_factory,
        access, {"post_id": "none", "author_email": "direct", "note": "none"}
    )

    async with session_factory() as session:
        before = (
            await session.execute(
                select(FieldPolicy).where(FieldPolicy.dataset_id == dataset.id)
            )
        ).scalars().all()
        ids = {row.field_path: row.id for row in before}

    await _set_classes(
        session_factory, access, {"note": "none"}, reason="重复保存同一分类，不是降级"
    )

    async with session_factory() as session:
        after = (
            await session.execute(
                select(FieldPolicy).where(FieldPolicy.dataset_id == dataset.id)
            )
        ).scalars().all()
        ids_after = {row.field_path: row.id for row in after}

    assert ids_after == ids, "重复保存不该改主键，否则等于全量重建"

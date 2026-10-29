"""ABI 相关表的数据访问。

约定：ABI 表（catalog_dataset / access_grant / upload_batch / export_job）
的每个查询第一个过滤条件都是 ``workspace_id``，随后才是 dataset / user 条件。
``dataset_column`` 与 ``field_policy`` 没有 workspace_id 列，用 join 或子查询
把 workspace 约束带上。

物理表查询只接受服务端 allowlist 里的标识符。所有标识符经
:func:`quote_ident` 强制双引号包裹；所有值走绑定参数。
"""

from __future__ import annotations

import base64
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import ColumnElement, Select, and_, delete, desc, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.abi import (
    AccessGrant,
    CatalogDataset,
    DatasetColumn,
    ExportJob,
    ExportPolicy,
    FieldPolicy,
    ScheduleState,
    UploadBatch,
    UploadError,
)

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_FILTER_OPERATORS: dict[str, str] = {
    "eq": "=",
    "ne": "<>",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
}


class UnsafeIdentifierError(ValueError):
    """标识符不在 allowlist 形状内。"""


class QueryColumnNotAllowedError(ValueError):
    """过滤或排序引用了未声明的列。"""


class QueryOperatorNotAllowedError(ValueError):
    """过滤操作符不在白名单内。"""


class QueryFilterValueError(ValueError):
    """过滤值类型不合法。"""


def quote_ident(name: str) -> str:
    """按 PostgreSQL ``quote_ident`` 语义强制引用标识符。

    先做形状校验：只允许小写字母、数字、下划线，且不以数字开头。
    校验通过后仍然加双引号，避免保留字与大小写折叠带来的歧义。
    """
    if not _IDENTIFIER_RE.fullmatch(name):
        raise UnsafeIdentifierError(name)
    return '"' + name.replace('"', '""') + '"'


def build_where_clause(
    filters: list[tuple[str, str, Any]],
    allowed_columns: set[str],
) -> tuple[str, dict[str, Any]]:
    """把结构化过滤条件编译成 SQL 片段与绑定参数。

    列必须属于 allowlist；op 必须属于白名单。值一律绑定，不拼接。
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for index, (column, operator, value) in enumerate(filters):
        if column not in allowed_columns:
            raise QueryColumnNotAllowedError(column)
        quoted = quote_ident(column)
        parameter = f"abi_filter_{index}"
        if operator == "is_null":
            clauses.append(f"{quoted} IS NULL")
        elif operator == "not_null":
            clauses.append(f"{quoted} IS NOT NULL")
        elif operator == "in":
            if not isinstance(value, list) or not value:
                raise QueryFilterValueError(operator)
            if len(value) > 200:
                raise QueryFilterValueError(operator)
            clauses.append(f"{quoted} = ANY(:{parameter})")
            params[parameter] = value
        elif operator == "contains":
            if not isinstance(value, str):
                raise QueryFilterValueError(operator)
            clauses.append(f"{quoted}::text ILIKE :{parameter}")
            params[parameter] = f"%{value}%"
        elif operator in _FILTER_OPERATORS:
            if value is None:
                raise QueryFilterValueError(operator)
            clauses.append(f"{quoted} {_FILTER_OPERATORS[operator]} :{parameter}")
            params[parameter] = value
        else:
            raise QueryOperatorNotAllowedError(operator)
    return " AND ".join(clauses), params


def build_order_clause(
    order_by: list[tuple[str, str]],
    allowed_columns: set[str],
) -> str:
    """编译排序片段。方向只接受 asc / desc。"""
    parts: list[str] = []
    for column, direction in order_by:
        if column not in allowed_columns:
            raise QueryColumnNotAllowedError(column)
        if direction not in ("asc", "desc"):
            raise QueryOperatorNotAllowedError(direction)
        parts.append(f"{quote_ident(column)} {direction.upper()}")
    return ", ".join(parts)


async def query_dataset_rows(
    session: AsyncSession,
    *,
    schema: str,
    table: str,
    columns: list[str],
    filters: list[tuple[str, str, Any]],
    order_by: list[tuple[str, str]],
    limit: int,
    offset: int,
    allowed_columns: set[str] | None = None,
) -> list[dict[str, Any]]:
    """查询物理表的一页数据。标识符全部经过 allowlist 与双引号处理。

    ``allowed_columns`` 是过滤/排序可用的完整列集合，通常大于 ``columns``
    （例如按 id 过滤但只返回 name）。不给时退化为只允许选中列。
    """
    allowed = allowed_columns if allowed_columns is not None else set(columns)
    where_sql, params = build_where_clause(filters, allowed)
    select_sql = ", ".join(quote_ident(column) for column in columns)
    sql = (
        f"SELECT {select_sql} FROM {quote_ident(schema)}.{quote_ident(table)}"
    )
    if where_sql:
        sql += f" WHERE {where_sql}"
    order_sql = build_order_clause(order_by, allowed)
    if order_sql:
        sql += f" ORDER BY {order_sql}"
    elif columns:
        # 没有显式排序时按第一列排序，保证分页结果稳定。
        sql += " ORDER BY 1 ASC"
    sql += " LIMIT :abi_limit OFFSET :abi_offset"
    params["abi_limit"] = limit
    params["abi_offset"] = offset
    result = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


async def count_dataset_rows(
    session: AsyncSession,
    *,
    schema: str,
    table: str,
    columns: list[str],
    filters: list[tuple[str, str, Any]],
    allowed_columns: set[str] | None = None,
) -> int:
    """统计物理表命中行数，过滤条件与查询端点一致。"""
    allowed = allowed_columns if allowed_columns is not None else set(columns)
    where_sql, params = build_where_clause(filters, allowed)
    sql = f"SELECT count(*) FROM {quote_ident(schema)}.{quote_ident(table)}"
    if where_sql:
        sql += f" WHERE {where_sql}"
    result = await session.execute(text(sql), params)
    return int(result.scalar_one())


async def physical_table_exists(
    session: AsyncSession,
    schema: str,
    table: str,
) -> bool:
    """确认 schema.table 真实存在。"""
    result = await session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table LIMIT 1"
        ),
        {"schema": schema, "table": table},
    )
    return result.scalar_one_or_none() is not None


async def list_physical_columns(
    session: AsyncSession,
    schema: str,
    table: str,
) -> list[dict[str, Any]]:
    """读取物理列。返回值按 ordinal_position 升序。"""
    result = await session.execute(
        text(
            "SELECT column_name, data_type, is_nullable, ordinal_position "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "ORDER BY ordinal_position"
        ),
        {"schema": schema, "table": table},
    )
    return [
        {
            "column_name": str(row[0]),
            "data_type": str(row[1]),
            "nullable": str(row[2]) == "YES",
            "ordinal": int(row[3]),
        }
        for row in result
    ]


def _granted_dataset_ids(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Select[tuple[uuid.UUID]]:
    return select(AccessGrant.dataset_id).where(
        AccessGrant.workspace_id == workspace_id,
        AccessGrant.user_id == user_id,
    )


def _visible_export_condition(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ColumnElement[bool]:
    """导出列表可见性：只按 grant 判定，不看 ``created_by``。

    原先这里有一条 ``ExportJob.created_by == user_id`` 的旁路，于是撤掉
    某人在数据集上的 grant 之后，他此前创建的导出仍出现在列表里——
    而详情与下载（``_export_visible``）已经改为要求 grant。两者不一致
    会让列表显示一条点开就 404 的记录。

    未遮罩导出的列表门槛是 publisher；遮罩导出是 viewer。SQL 里无法
    按行区分，因此这里按最宽（viewer）取，再由详情/下载做精确判定。
    """
    granted = select(AccessGrant.dataset_id).where(
        AccessGrant.workspace_id == workspace_id,
        AccessGrant.user_id == user_id,
        AccessGrant.role.in_(("viewer", "editor", "publisher", "admin")),
    )
    return ExportJob.dataset_id.in_(granted)


async def get_dataset_by_slug(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    slug: str,
) -> CatalogDataset | None:
    result = await session.execute(
        select(CatalogDataset).where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.slug == slug,
        )
    )
    return result.scalar_one_or_none()


async def get_dataset_by_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> CatalogDataset | None:
    result = await session.execute(
        select(CatalogDataset).where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.id == dataset_id,
        )
    )
    return result.scalar_one_or_none()


async def create_dataset(
    session: AsyncSession,
    dataset: CatalogDataset,
) -> CatalogDataset:
    session.add(dataset)
    await session.flush()
    await session.refresh(dataset)
    return dataset


async def add_dataset_columns(
    session: AsyncSession,
    columns: list[DatasetColumn],
) -> None:
    session.add_all(columns)
    await session.flush()


async def list_dataset_columns(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> list[DatasetColumn]:
    result = await session.execute(
        select(DatasetColumn)
        .join(CatalogDataset, DatasetColumn.dataset_id == CatalogDataset.id)
        .where(
            CatalogDataset.workspace_id == workspace_id,
            DatasetColumn.dataset_id == dataset_id,
        )
        .order_by(DatasetColumn.ordinal)
    )
    return list(result.scalars().all())


async def list_field_policies(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> list[FieldPolicy]:
    result = await session.execute(
        select(FieldPolicy)
        .join(CatalogDataset, FieldPolicy.dataset_id == CatalogDataset.id)
        .where(
            CatalogDataset.workspace_id == workspace_id,
            FieldPolicy.dataset_id == dataset_id,
        )
        .order_by(FieldPolicy.field_path)
    )
    return list(result.scalars().all())


async def replace_field_policies(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    policies: list[FieldPolicy],
) -> None:
    """全量替换策略。删除也带 workspace 子查询，防止跨租户误删。"""
    dataset_ids = select(CatalogDataset.id).where(
        CatalogDataset.workspace_id == workspace_id,
        CatalogDataset.id == dataset_id,
    )
    await session.execute(
        delete(FieldPolicy).where(FieldPolicy.dataset_id.in_(dataset_ids))
    )
    session.add_all(policies)
    await session.flush()


async def list_datasets_for_user(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int = 0,
    cursor_created_at: datetime | None = None,
    cursor_id: uuid.UUID | None = None,
) -> list[CatalogDataset]:
    statement = select(CatalogDataset).where(
        CatalogDataset.workspace_id == workspace_id,
        CatalogDataset.id.in_(_granted_dataset_ids(workspace_id, user_id)),
    )
    if cursor_created_at is not None and cursor_id is not None:
        statement = statement.where(
            or_(
                CatalogDataset.created_at < cursor_created_at,
                and_(
                    CatalogDataset.created_at == cursor_created_at,
                    CatalogDataset.id < cursor_id,
                ),
            )
        )
    statement = (
        statement.order_by(desc(CatalogDataset.created_at), desc(CatalogDataset.id))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_datasets_for_user(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count(CatalogDataset.id)).where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.id.in_(_granted_dataset_ids(workspace_id, user_id)),
        )
    )
    return int(result.scalar_one())


async def dataset_overview(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[int, int, int]:
    """返回 (dataset 数, 总行数, 未完成 PII 扫描的 dataset 数)。"""
    result = await session.execute(
        select(
            func.count(CatalogDataset.id),
            func.coalesce(func.sum(CatalogDataset.row_count), 0),
            func.count(CatalogDataset.id).filter(CatalogDataset.pii_scanned.is_(False)),
        ).where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.id.in_(_granted_dataset_ids(workspace_id, user_id)),
        )
    )
    dataset_count, row_count, pii_pending = result.one()
    return int(dataset_count), int(row_count), int(pii_pending)


async def get_access_grant(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AccessGrant | None:
    result = await session.execute(
        select(AccessGrant).where(
            AccessGrant.workspace_id == workspace_id,
            AccessGrant.dataset_id == dataset_id,
            AccessGrant.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_access_grants(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> list[AccessGrant]:
    result = await session.execute(
        select(AccessGrant)
        .where(
            AccessGrant.workspace_id == workspace_id,
            AccessGrant.dataset_id == dataset_id,
        )
        .order_by(AccessGrant.created_at, AccessGrant.id)
    )
    return list(result.scalars().all())


async def get_access_grant_by_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    grant_id: uuid.UUID,
) -> AccessGrant | None:
    result = await session.execute(
        select(AccessGrant).where(
            AccessGrant.workspace_id == workspace_id,
            AccessGrant.dataset_id == dataset_id,
            AccessGrant.id == grant_id,
        )
    )
    return result.scalar_one_or_none()


async def count_admin_grants(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count(AccessGrant.id)).where(
            AccessGrant.workspace_id == workspace_id,
            AccessGrant.dataset_id == dataset_id,
            AccessGrant.role == "admin",
        )
    )
    return int(result.scalar_one())


async def create_access_grant(
    session: AsyncSession,
    grant: AccessGrant,
) -> AccessGrant:
    session.add(grant)
    await session.flush()
    await session.refresh(grant)
    return grant


async def delete_access_grant(
    session: AsyncSession,
    grant: AccessGrant,
) -> None:
    await session.delete(grant)
    await session.flush()


async def create_upload_batch(
    session: AsyncSession,
    batch: UploadBatch,
) -> UploadBatch:
    session.add(batch)
    await session.flush()
    await session.refresh(batch)
    return batch


async def get_upload_batch(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
) -> UploadBatch | None:
    result = await session.execute(
        select(UploadBatch).where(
            UploadBatch.workspace_id == workspace_id,
            UploadBatch.id == batch_id,
        )
    )
    return result.scalar_one_or_none()


async def get_upload_batch_by_token_hash(
    session: AsyncSession,
    token_hash: bytes,
) -> UploadBatch | None:
    """令牌本身就是能力凭据，先按哈希定位，再在服务层校验 workspace。"""
    result = await session.execute(
        select(UploadBatch).where(UploadBatch.upload_token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def export_status_counts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    see_all: bool,
) -> dict[str, int]:
    statement = select(ExportJob.status, func.count(ExportJob.id)).where(
        ExportJob.workspace_id == workspace_id
    )
    if not see_all:
        statement = statement.where(_visible_export_condition(workspace_id, user_id))
    result = await session.execute(statement.group_by(ExportJob.status))
    return {str(status): int(count) for status, count in result.all()}


async def count_pending_uploads(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    see_all: bool,
) -> int:
    statement = select(func.count(UploadBatch.id)).where(
        UploadBatch.workspace_id == workspace_id,
        UploadBatch.status == "pending",
    )
    if not see_all:
        statement = statement.where(UploadBatch.uploaded_by == user_id)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def get_export_policy(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> ExportPolicy | None:
    """dataset 级策略优先于工作区级策略（dataset_id 为空的兜底行）。"""
    result = await session.execute(
        select(ExportPolicy)
        .where(
            ExportPolicy.workspace_id == workspace_id,
            or_(
                ExportPolicy.dataset_id == dataset_id,
                ExportPolicy.dataset_id.is_(None),
            ),
        )
        .order_by(ExportPolicy.dataset_id.is_(None), ExportPolicy.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def upsert_export_policy(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID | None,
    *,
    max_rows_masked: int | None,
    require_dual_approval: bool,
    allowed_formats: list[str] | None,
) -> ExportPolicy:
    """建或改一条导出策略。

    数据集级与工作区级（``dataset_id`` 为空）各只有一条。唯一性靠
    ``(workspace_id, dataset_id)`` 的查询保证——表上没有唯一约束，
    所以这里先查后改，不依赖 ON CONFLICT。
    """
    existing = await session.scalar(
        select(ExportPolicy).where(
            ExportPolicy.workspace_id == workspace_id,
            (
                ExportPolicy.dataset_id.is_(None)
                if dataset_id is None
                else ExportPolicy.dataset_id == dataset_id
            ),
        )
    )
    if existing is None:
        existing = ExportPolicy(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            dataset_id=dataset_id,
        )
        session.add(existing)
    existing.max_rows_masked = max_rows_masked
    existing.require_dual_approval = require_dual_approval
    existing.allowed_formats = allowed_formats
    await session.flush()
    await session.refresh(existing)
    return existing


async def create_export_job(
    session: AsyncSession,
    job: ExportJob,
) -> ExportJob:
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


async def claim_queued_export_jobs(
    session: AsyncSession,
    *,
    limit: int = 5,
) -> list[uuid.UUID]:
    """列出待执行的导出作业 id。

    **纯读候选，不抢锁、不改状态。** 并发控制全部交给
    ``abi_export.run_job``：它在 ``FOR UPDATE`` 下重查 ``status='queued'``，
    抢输的 worker 会看到 running 并得到 ``AbiExportNotReady``。

    这里刻意不用 ``FOR UPDATE SKIP LOCKED``：那会在本会话持锁，而调用方
    随后要开新事务跑 run_job，两个事务对同一行的锁会互相等待。
    也不用「先改 status 抢占」：run_job 见到非 queued 会直接拒绝，
    等于把自己饿死。
    """
    if limit < 1:
        return []
    result = await session.execute(
        select(ExportJob.id)
        .where(
            ExportJob.status == "queued",
            or_(
                ExportJob.expires_at.is_(None),
                ExportJob.expires_at > func.now(),
            ),
        )
        .order_by(ExportJob.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_export_job(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
) -> ExportJob | None:
    result = await session.execute(
        select(ExportJob).where(
            ExportJob.workspace_id == workspace_id,
            ExportJob.id == job_id,
        )
    )
    return result.scalar_one_or_none()


async def list_export_jobs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    see_all: bool,
    limit: int,
    offset: int,
) -> list[ExportJob]:
    statement = select(ExportJob).where(ExportJob.workspace_id == workspace_id)
    if not see_all:
        statement = statement.where(_visible_export_condition(workspace_id, user_id))
    statement = (
        statement.order_by(desc(ExportJob.created_at), desc(ExportJob.id))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_export_jobs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    see_all: bool,
) -> int:
    statement = select(func.count(ExportJob.id)).where(
        ExportJob.workspace_id == workspace_id
    )
    if not see_all:
        statement = statement.where(_visible_export_condition(workspace_id, user_id))
    result = await session.execute(statement)
    return int(result.scalar_one())


# ---------------------------------------------------------------- 分页与总览


class DatasetPage(NamedTuple):
    """一页数据集与下一页游标。``next_cursor`` 为空表示没有更多数据。"""

    items: list[CatalogDataset]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class OverviewCounts:
    """ABI 总览需要的聚合计。"""

    datasets: int
    total_rows: int
    pii_unscanned: int
    last_loaded_at: datetime | None
    grants: int
    active_uploads: int
    queued_exports: int


_PAGE_MAX = 200
_CURSOR_MAX_LENGTH = 512
_GRANT_ROLES = ("viewer", "editor", "publisher", "admin")
_UPLOAD_STATUSES = (
    "pending",
    "uploaded",
    "validating",
    "committed",
    "failed",
    "expired",
)
_EXPORT_STATUSES = (
    "queued",
    "awaiting_approval",
    "running",
    "succeeded",
    "failed",
    "expired",
    "rejected",
)
_ACTIVE_UPLOAD_STATUSES = ("pending", "uploaded", "validating")
_ACTIVE_EXPORT_STATUSES = ("queued", "awaiting_approval", "running")
_UPLOAD_BATCH_PATCH_FIELDS = frozenset(
    {
        "status",
        "actual_sha256",
        "actual_rows",
        "bytes_total",
        "rows_loaded",
        "rows_rejected",
        "storage_path",
        "upload_token_hash",
        "token_expires_at",
        "committed_at",
    }
)
_EXPORT_JOB_PATCH_FIELDS = frozenset(
    {
        "status",
        "approved_by",
        "approved_at",
        "artifact_path",
        "filename",
        "content_type",
        "bytes_total",
        "rows_total",
        "error",
        "started_at",
        "finished_at",
        "expires_at",
    }
)
_SCHEDULE_STATE_FIELDS = frozenset(
    {
        "last_target_date",
        "last_success_at",
        "last_sweep_at",
    }
)


def _require_choice(field: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"{field}_invalid: {value}")


def _validate_limit_offset(limit: int, offset: int = 0) -> None:
    if limit < 1 or limit > _PAGE_MAX:
        raise ValueError(f"limit_out_of_range: {limit}")
    if offset < 0:
        raise ValueError(f"offset_out_of_range: {offset}")


def encode_dataset_cursor(dataset: CatalogDataset) -> str:
    """把一行的排序键编码成不透明游标。"""
    raw = f"{dataset.created_at.isoformat()}|{dataset.id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_dataset_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """解析游标。格式不合法时抛 ``ValueError``，由路由层转成 400。"""
    if not cursor or len(cursor) > _CURSOR_MAX_LENGTH:
        raise ValueError("dataset_cursor_invalid")
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        created_text, separator, id_text = raw.partition("|")
        if not separator:
            raise ValueError("dataset_cursor_invalid")
        created_at = datetime.fromisoformat(created_text)
        dataset_id = uuid.UUID(id_text)
    except ValueError as exc:
        raise ValueError("dataset_cursor_invalid") from exc
    if created_at.tzinfo is None:
        raise ValueError("dataset_cursor_invalid")
    return created_at, dataset_id


def _apply_allowed_values(
    instance: Any,
    values: Mapping[str, Any],
    allowed: frozenset[str],
    label: str,
) -> None:
    """把补丁字段写进 ORM 实例，字段名必须在白名单内。"""
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"{label}_field_not_allowed: {', '.join(unknown)}")
    for key, value in values.items():
        setattr(instance, key, value)


async def list_datasets(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 50,
) -> DatasetPage:
    """按 ``created_at DESC, id DESC`` keyset 分页列出当前版本数据集。

    workspace 过滤始终存在；调用方仍需在端点层校验 grant。
    """
    _validate_limit_offset(limit)
    statement = select(CatalogDataset).where(
        CatalogDataset.workspace_id == workspace_id,
        CatalogDataset.is_current.is_(True),
    )
    if cursor is not None:
        created_at, dataset_id = decode_dataset_cursor(cursor)
        statement = statement.where(
            or_(
                CatalogDataset.created_at < created_at,
                and_(
                    CatalogDataset.created_at == created_at,
                    CatalogDataset.id < dataset_id,
                ),
            )
        )
    statement = (
        statement.order_by(desc(CatalogDataset.created_at), desc(CatalogDataset.id))
        .limit(limit + 1)
    )
    result = await session.execute(statement)
    rows = list(result.scalars().all())
    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_dataset_cursor(rows[-1])
    return DatasetPage(items=rows, next_cursor=next_cursor)


async def list_columns(
    session: AsyncSession,
    dataset_id: uuid.UUID,
) -> list[DatasetColumn]:
    """按物理顺序列出列。调用方已校验 workspace 与 grant。"""
    result = await session.execute(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.ordinal, DatasetColumn.id)
    )
    return list(result.scalars().all())


async def get_grant(
    session: AsyncSession,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AccessGrant | None:
    """按 dataset + user 取显式授权。没有 grant 行即无权访问。

    ``get_access_grant`` 是带 workspace 过滤的变体。本函数按任务契约只收
    ``dataset_id`` / ``user_id``，调用方必须先确认数据集属于请求的 workspace。
    """
    result = await session.execute(
        select(AccessGrant).where(
            AccessGrant.dataset_id == dataset_id,
            AccessGrant.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_grants(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AccessGrant]:
    """列出授权。可按数据集过滤，但 workspace 过滤始终存在。"""
    _validate_limit_offset(limit, offset)
    statement = select(AccessGrant).where(AccessGrant.workspace_id == workspace_id)
    if dataset_id is not None:
        statement = statement.where(AccessGrant.dataset_id == dataset_id)
    statement = (
        statement.order_by(desc(AccessGrant.created_at), desc(AccessGrant.id))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def upsert_grant(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = "viewer",
    granted_by: uuid.UUID | None = None,
) -> AccessGrant:
    """新增或更新一条授权。唯一键是 ``(dataset_id, user_id)``。"""
    _require_choice("grant_role", role, _GRANT_ROLES)
    statement = (
        pg_insert(AccessGrant)
        .values(
            dataset_id=dataset_id,
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            granted_by=granted_by,
        )
        .on_conflict_do_update(
            index_elements=["dataset_id", "user_id"],
            set_={"role": role, "granted_by": granted_by},
        )
        .returning(AccessGrant)
    )
    grant: AccessGrant = (await session.execute(statement)).scalar_one()
    await session.flush()
    return grant


async def delete_grant(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """删除授权。返回是否真的删掉了一行。"""
    result = await session.execute(
        delete(AccessGrant)
        .where(
            AccessGrant.workspace_id == workspace_id,
            AccessGrant.dataset_id == dataset_id,
            AccessGrant.user_id == user_id,
        )
        .returning(AccessGrant.id)
    )
    deleted_id = result.scalar_one_or_none()
    await session.flush()
    return deleted_id is not None


async def update_upload_batch(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
    values: Mapping[str, Any],
) -> UploadBatch | None:
    """按白名单更新批次字段。批次不存在或跨租户返回 ``None``。"""
    if "status" in values:
        _require_choice("upload_status", str(values["status"]), _UPLOAD_STATUSES)
    batch = await get_upload_batch(session, workspace_id, batch_id)
    if batch is None:
        return None
    _apply_allowed_values(batch, values, _UPLOAD_BATCH_PATCH_FIELDS, "upload_batch")
    await session.flush()
    await session.refresh(batch)
    return batch


async def list_upload_errors(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[UploadError]:
    """列出批次校验错误。join 批次表保证 workspace 隔离。"""
    _validate_limit_offset(limit, offset)
    result = await session.execute(
        select(UploadError)
        .join(UploadBatch, UploadBatch.id == UploadError.batch_id)
        .where(
            UploadBatch.workspace_id == workspace_id,
            UploadError.batch_id == batch_id,
        )
        .order_by(UploadError.row_number, UploadError.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def delete_upload_errors(
    session: AsyncSession,
    batch_id: uuid.UUID,
) -> int:
    """清掉一个批次的全部错误行。重试前调用，避免新旧原因混在一起。

    不按 workspace 过滤：``batch_id`` 已经由调用方在上层用
    ``get_upload_batch(workspace_id, ...)`` 校验过归属，这里再 join 一次
    只会让删除条件更难读。
    """
    result = await session.execute(
        delete(UploadError).where(UploadError.batch_id == batch_id)
    )
    return int(result.rowcount or 0)


async def count_upload_errors(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    batch_id: uuid.UUID,
) -> int:
    """批次错误总数。

    单独计数而不是 ``len(list_upload_errors(...))``：错误可能上千条，
    分页只取一页时前端仍要知道总数才有意义。
    """
    result = await session.execute(
        select(func.count(UploadError.id))
        .join(UploadBatch, UploadBatch.id == UploadError.batch_id)
        .where(
            UploadBatch.workspace_id == workspace_id,
            UploadError.batch_id == batch_id,
        )
    )
    return int(result.scalar() or 0)


async def list_upload_batches(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[UploadBatch]:
    """某 dataset 的批次，按创建时间倒序。

    租户隔离靠 ``workspace_id`` 与 ``dataset_id`` 双条件，不依赖调用方
    先做过校验——批次列表是最容易被拼错的查询点。
    """
    _validate_limit_offset(limit, offset)
    result = await session.execute(
        select(UploadBatch)
        .where(
            UploadBatch.workspace_id == workspace_id,
            UploadBatch.dataset_id == dataset_id,
        )
        .order_by(UploadBatch.created_at.desc(), UploadBatch.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_upload_batches(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count(UploadBatch.id)).where(
            UploadBatch.workspace_id == workspace_id,
            UploadBatch.dataset_id == dataset_id,
        )
    )
    return int(result.scalar() or 0)


async def update_export_job(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    values: Mapping[str, Any],
) -> ExportJob | None:
    """按白名单更新导出任务。任务不存在或跨租户返回 ``None``。"""
    if "status" in values:
        _require_choice("export_status", str(values["status"]), _EXPORT_STATUSES)
    job = await get_export_job(session, workspace_id, job_id)
    if job is None:
        return None
    _apply_allowed_values(job, values, _EXPORT_JOB_PATCH_FIELDS, "export_job")
    await session.flush()
    await session.refresh(job)
    return job


async def overview_counts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> OverviewCounts:
    """总览计数。只统计当前版本数据集，避免多版本重复累计行数。"""
    dataset_rollup = (
        select(
            func.count(CatalogDataset.id).label("datasets"),
            func.coalesce(func.sum(CatalogDataset.row_count), 0).label("total_rows"),
            func.count(CatalogDataset.id)
            .filter(CatalogDataset.pii_scanned.is_(False))
            .label("pii_unscanned"),
            func.max(CatalogDataset.last_loaded_at).label("last_loaded_at"),
        )
        .where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.is_current.is_(True),
        )
        .subquery()
    )
    statement = select(
        dataset_rollup.c.datasets,
        dataset_rollup.c.total_rows,
        dataset_rollup.c.pii_unscanned,
        dataset_rollup.c.last_loaded_at,
        select(func.count(AccessGrant.id))
        .where(AccessGrant.workspace_id == workspace_id)
        .scalar_subquery()
        .label("grants"),
        select(func.count(UploadBatch.id))
        .where(
            UploadBatch.workspace_id == workspace_id,
            UploadBatch.status.in_(_ACTIVE_UPLOAD_STATUSES),
        )
        .scalar_subquery()
        .label("active_uploads"),
        select(func.count(ExportJob.id))
        .where(
            ExportJob.workspace_id == workspace_id,
            ExportJob.status.in_(_ACTIVE_EXPORT_STATUSES),
        )
        .scalar_subquery()
        .label("queued_exports"),
    )
    row = (await session.execute(statement)).one()
    return OverviewCounts(
        datasets=int(row.datasets),
        total_rows=int(row.total_rows),
        pii_unscanned=int(row.pii_unscanned),
        last_loaded_at=row.last_loaded_at,
        grants=int(row.grants),
        active_uploads=int(row.active_uploads),
        queued_exports=int(row.queued_exports),
    )


# ---------------------------------------------------------------- 采集水位


async def upsert_schedule_state(
    session: AsyncSession,
    account_id: uuid.UUID,
    values: Mapping[str, Any],
) -> ScheduleState:
    """按账号更新采集水位。``account_id`` 唯一，冲突时只更新给定字段。

    ``meta.schedule_state`` 是采集侧全局表，没有 workspace_id；
    这是本仓库里唯一不按租户过滤的表。
    """
    unknown = sorted(set(values) - _SCHEDULE_STATE_FIELDS)
    if unknown:
        raise ValueError(f"schedule_state_field_not_allowed: {', '.join(unknown)}")
    if not values:
        raise ValueError("schedule_state_values_empty")
    statement = (
        pg_insert(ScheduleState)
        .values(account_id=account_id, **values)
        .on_conflict_do_update(
            index_elements=["account_id"],
            set_={**values, "updated_at": func.now()},
        )
        .returning(ScheduleState)
    )
    state: ScheduleState = (await session.execute(statement)).scalar_one()
    await session.flush()
    return state


async def get_schedule_state(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> ScheduleState | None:
    """按账号取采集水位。"""
    result = await session.execute(
        select(ScheduleState).where(ScheduleState.account_id == account_id)
    )
    return result.scalar_one_or_none()


__all__ = [
    "DatasetPage",
    "OverviewCounts",
    "QueryColumnNotAllowedError",
    "QueryFilterValueError",
    "QueryOperatorNotAllowedError",
    "UnsafeIdentifierError",
    "add_dataset_columns",
    "build_order_clause",
    "build_where_clause",
    "count_admin_grants",
    "count_dataset_rows",
    "count_datasets_for_user",
    "count_export_jobs",
    "count_upload_batches",
    "count_upload_errors",
    "count_pending_uploads",
    "create_access_grant",
    "create_dataset",
    "create_export_job",
    "create_upload_batch",
    "dataset_overview",
    "decode_dataset_cursor",
    "delete_access_grant",
    "delete_grant",
    "delete_upload_errors",
    "encode_dataset_cursor",
    "export_status_counts",
    "get_access_grant",
    "get_access_grant_by_id",
    "get_dataset_by_id",
    "get_dataset_by_slug",
    "get_export_job",
    "get_export_policy",
    "upsert_export_policy",
    "get_grant",
    "get_schedule_state",
    "get_upload_batch",
    "get_upload_batch_by_token_hash",
    "list_access_grants",
    "list_columns",
    "list_dataset_columns",
    "list_datasets",
    "list_datasets_for_user",
    "list_export_jobs",
    "list_field_policies",
    "list_grants",
    "list_physical_columns",
    "list_upload_batches",
    "list_upload_errors",
    "overview_counts",
    "physical_table_exists",
    "query_dataset_rows",
    "quote_ident",
    "replace_field_policies",
    "update_export_job",
    "update_upload_batch",
    "upsert_grant",
    "upsert_schedule_state",
]

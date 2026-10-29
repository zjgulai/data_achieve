"""ABI 目录、查询、授权、上传与导出的业务逻辑。

安全边界：

- dataset 一律先按 ``workspace_id + slug`` 定位，再按 ``workspace + grant``
  校验；workspace owner 不构成 dataset 级 bypass。
- 查询只接受 ``abi.dataset_column`` 声明且在物理表中真实存在的列；
  过滤与排序列还必须有已知的 PII 策略。
- ``pii_class='unknown'`` 的字段默认拒绝出现在查询结果与导出中。
- 遮罩在序列化层完成，前端拿不到未遮罩值。
- CSV 导出对 ``= + - @ \\t \\r`` 五种前缀做公式注入转义。
- 下载路径必须落在 ``abi_export_dir`` 根目录内。
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.abi import (
    AccessGrant,
    CatalogDataset,
    DatasetColumn,
    ExportJob,
    FieldPolicy,
    role_rank,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories import abi as abi_repo
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.schemas.abi import (
    AbiColumnResponse,
    AbiDatasetCreateRequest,
    AbiDatasetDetailResponse,
    AbiDatasetListResponse,
    AbiDatasetSummary,
    AbiDeleteResponse,
    AbiExportCreateRequest,
    AbiExportJobResponse,
    AbiExportListResponse,
    AbiExportPolicyResponse,
    AbiExportPolicyUpdateRequest,
    AbiGrantCreateRequest,
    AbiGrantListResponse,
    AbiGrantResponse,
    AbiOverviewResponse,
    AbiPolicyItem,
    AbiPolicyResponse,
    AbiPolicyUpdateItem,
    AbiPolicyUpdateRequest,
    AbiQueryFilter,
    AbiQueryOrder,
    AbiQueryRequest,
    AbiQueryResponse,
    AbiUploadBatchResponse,
    AbiUploadCreateRequest,
    AbiUploadCreateResponse,
    AbiUploadErrorItem,
    AbiUploadErrorListResponse,
    AbiUploadListResponse,
    PiiClass,
)

# 错误类型统一在 abi_errors 定义。routes/abi.py:43 仍从本模块导入，
# 这里用 as 形式重导出，保证路由与查询层捕获的是同一个类对象。
from data_intelligence_hub.services.abi_errors import (
    AbiServiceError as AbiServiceError,
)

if TYPE_CHECKING:
    from data_intelligence_hub.api.deps import DatasetAccess

_ALLOWED_SOURCE_SCHEMAS = frozenset({"raw"})
_SOURCE_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_UPLOAD_BYTES = 512 * 1024 * 1024
_UPLOAD_TOKEN_TTL = timedelta(hours=1)
_EXPORT_TTL = timedelta(days=7)
_EXPORT_MAX_ROWS = 50_000
# 这些物理类型不能当标量过滤/排序列：json/jsonb 需要类型化绑定，
# bytea 与数组的行为也不适合暴露成通用 eq/contains。
_NON_SCALAR_TYPES = frozenset({"json", "jsonb", "bytea", "array", "user-defined"})
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_EXPORT_CONTENT_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "jsonl": "application/x-ndjson; charset=utf-8",
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
}


@dataclass(frozen=True)
class _Selection:
    """一次查询/导出解析出的物理表与列。"""

    schema: str
    table: str
    all_columns: list[str]
    selected: list[str]
    policies: dict[str, str]
    mask_rules: dict[str, str | None]
    filterable: frozenset[str]
    sortable: frozenset[str]
    types: dict[str, str]


def _now() -> datetime:
    return datetime.now(UTC)


# PII 敏感度序。降级判定用它比较前后等级。
#
# ``unknown`` 单独处理，不进这个序：它等于「还没判定」，不是「已判定为
# 某一档」。把 unknown 当最低档会让「首次分类」被误判成降级。
#
# ``none`` < ``quasi`` < ``direct`` < ``secret``。
_PII_RANK: Final[dict[str, int]] = {
    "none": 0,
    "quasi": 1,
    "direct": 2,
    "secret": 3,
}


def _pii_rank(pii_class: str) -> int:
    """敏感度等级。未知取值按最高档处理——fail-closed。"""
    return _PII_RANK.get(pii_class, max(_PII_RANK.values()))


def _abi_root() -> Path:
    return Path(get_settings().abi_export_dir).expanduser().resolve()


def _export_root() -> Path:
    return _abi_root()


def _upload_root() -> Path:
    # 与 services/abi_upload.py 共用同一个根目录下的 _uploads 子树。
    return _abi_root() / "_uploads"


def _ensure_under_root(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AbiServiceError("path_outside_storage_root", 404) from exc


def _safe_filename(value: str) -> str:
    base = Path(value).name
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    return (cleaned or "upload.bin")[:200]


def _export_path(workspace_id: uuid.UUID, job_id: uuid.UUID, filename: str) -> Path:
    root = _export_root()
    path = (root / str(workspace_id) / str(job_id) / filename).resolve()
    _ensure_under_root(path, root)
    return path


def _parse_source_table(value: str, *, status_code: int = 400) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) != 2:
        raise AbiServiceError("source_table_invalid", status_code)
    schema, table = parts
    if schema not in _ALLOWED_SOURCE_SCHEMAS:
        raise AbiServiceError("source_table_not_allowed", status_code)
    if not _SOURCE_IDENTIFIER_RE.fullmatch(table):
        raise AbiServiceError("source_table_invalid", status_code)
    return schema, table


def _is_scalar_type(data_type: str) -> bool:
    return data_type.lower() not in _NON_SCALAR_TYPES


def _encode_cursor(dataset: CatalogDataset) -> str:
    payload = f"{dataset.created_at.isoformat()}|{dataset.id}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    padded = value + "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        created_at_text, dataset_id_text = raw.split("|", 1)
        created_at = datetime.fromisoformat(created_at_text)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return created_at, uuid.UUID(dataset_id_text)
    except ValueError as exc:
        raise AbiServiceError("invalid_cursor", 422) from exc


def _policy_item(policy: FieldPolicy, *, is_default: bool) -> AbiPolicyItem:
    return AbiPolicyItem(
        field_path=policy.field_path,
        pii_class=cast(PiiClass, policy.pii_class),
        mask_rule=policy.mask_rule,
        decided_by=policy.decided_by,
        is_default=is_default,
    )


def _effective_policy(
    columns: list[DatasetColumn],
    policies: list[FieldPolicy],
) -> list[AbiPolicyItem]:
    by_field = {policy.field_path: policy for policy in policies}
    items: list[AbiPolicyItem] = []
    for column in columns:
        policy = by_field.pop(column.column_name, None)
        if policy is None:
            items.append(
                AbiPolicyItem(
                    field_path=column.column_name,
                    pii_class="unknown",
                    mask_rule=None,
                    decided_by="system",
                    is_default=True,
                )
            )
        else:
            items.append(_policy_item(policy, is_default=False))
    for path in sorted(by_field):
        items.append(_policy_item(by_field[path], is_default=False))
    return items


async def _require_grant(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID,
    min_role: str,
) -> AccessGrant:
    grant = await abi_repo.get_access_grant(session, workspace_id, dataset_id, user_id)
    if grant is None:
        raise AbiServiceError("dataset_forbidden", 403)
    if role_rank(grant.role) < role_rank(min_role):
        raise AbiServiceError("insufficient_role", 403)
    return grant


async def _resolve_dataset_for_user(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    slug: str,
    min_role: str,
) -> tuple[CatalogDataset, AccessGrant]:
    dataset = await abi_repo.get_dataset_by_slug(session, workspace.id, slug)
    if dataset is None:
        raise AbiServiceError("dataset_not_found", 404)
    grant = await _require_grant(session, workspace.id, dataset.id, user.id, min_role)
    return dataset, grant


async def get_abi_overview(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
) -> AbiOverviewResponse:
    dataset_count, row_count, pii_pending = await abi_repo.dataset_overview(
        session, workspace.id, user.id
    )
    status_counts = await abi_repo.export_status_counts(
        session, workspace.id, user.id, see_all=False
    )
    uploads_pending = await abi_repo.count_pending_uploads(
        session, workspace.id, user.id, see_all=False
    )
    return AbiOverviewResponse(
        dataset_count=dataset_count,
        row_count=row_count,
        pii_pending_datasets=pii_pending,
        exports_queued=status_counts.get("queued", 0)
        + status_counts.get("awaiting_approval", 0),
        exports_running=status_counts.get("running", 0),
        exports_succeeded=status_counts.get("succeeded", 0),
        uploads_pending=uploads_pending,
        generated_at=_now(),
    )


async def list_abi_datasets(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    *,
    limit: int,
    offset: int,
    cursor: str | None,
) -> AbiDatasetListResponse:
    cursor_created_at: datetime | None = None
    cursor_id: uuid.UUID | None = None
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        offset = 0
    rows = await abi_repo.list_datasets_for_user(
        session,
        workspace.id,
        user.id,
        limit=limit + 1,
        offset=offset,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1]) if has_more and page else None
    total = await abi_repo.count_datasets_for_user(session, workspace.id, user.id)
    return AbiDatasetListResponse(
        items=[AbiDatasetSummary.model_validate(row) for row in page],
        total=total,
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def create_abi_dataset(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AbiDatasetCreateRequest,
) -> AbiDatasetSummary:
    if workspace.owner_id != user.id:
        raise AbiServiceError("workspace_owner_required", 403)
    existing = await abi_repo.get_dataset_by_slug(session, workspace.id, payload.slug)
    if existing is not None:
        raise AbiServiceError("dataset_slug_exists", 409)

    source_parts: tuple[str, str] | None = None
    if payload.source_table is not None:
        source_parts = _parse_source_table(payload.source_table)
        if not await abi_repo.physical_table_exists(session, *source_parts):
            raise AbiServiceError("source_table_not_found", 400)
    if payload.source_kind == "local_table" and source_parts is None:
        raise AbiServiceError("source_table_required", 400)
    if payload.source_kind == "upload" and source_parts is not None:
        raise AbiServiceError("source_table_not_allowed", 400)

    dataset = CatalogDataset(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        source_kind=payload.source_kind,
        source_table=payload.source_table,
        platform=payload.platform,
        object_type=payload.object_type,
        origin=payload.origin,
        row_count=0,
        version=1,
        is_current=True,
        pii_scanned=False,
        owner_id=user.id,
    )
    await abi_repo.create_dataset(session, dataset)

    columns: list[DatasetColumn] = []
    if payload.columns is not None:
        seen: set[str] = set()
        for ordinal, item in enumerate(payload.columns):
            if item.column_name in seen:
                raise AbiServiceError("duplicate_dataset_column", 400)
            seen.add(item.column_name)
            columns.append(
                DatasetColumn(
                    id=uuid.uuid4(),
                    dataset_id=dataset.id,
                    column_name=item.column_name,
                    data_type=item.data_type,
                    ordinal=ordinal,
                    nullable=item.nullable,
                    filterable=item.filterable,
                    sortable=item.sortable,
                )
            )
    elif source_parts is not None:
        physical = await abi_repo.list_physical_columns(session, *source_parts)
        for ordinal, physical_column in enumerate(physical):
            data_type = str(physical_column["data_type"])
            scalar = _is_scalar_type(data_type)
            columns.append(
                DatasetColumn(
                    id=uuid.uuid4(),
                    dataset_id=dataset.id,
                    column_name=str(physical_column["column_name"]),
                    data_type=data_type,
                    ordinal=ordinal,
                    nullable=bool(physical_column["nullable"]),
                    filterable=scalar,
                    sortable=scalar,
                )
            )
    if columns:
        await abi_repo.add_dataset_columns(session, columns)

    grant = AccessGrant(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
        granted_by=user.id,
    )
    await abi_repo.create_access_grant(session, grant)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AbiServiceError("dataset_slug_exists", 409) from exc
    return AbiDatasetSummary.model_validate(dataset)


async def get_abi_dataset_detail(
    session: AsyncSession,
    access: DatasetAccess,
) -> AbiDatasetDetailResponse:
    columns = await abi_repo.list_dataset_columns(
        session, access.workspace.id, access.dataset.id
    )
    policies = await abi_repo.list_field_policies(
        session, access.workspace.id, access.dataset.id
    )
    return AbiDatasetDetailResponse(
        dataset=AbiDatasetSummary.model_validate(access.dataset),
        columns=[AbiColumnResponse.model_validate(column) for column in columns],
        policy=_effective_policy(columns, policies),
    )


async def _resolve_selection(
    session: AsyncSession,
    dataset: CatalogDataset,
    requested_columns: list[str] | None,
) -> _Selection:
    if dataset.source_table is None:
        raise AbiServiceError("dataset_source_not_ready", 409)
    schema, table = _parse_source_table(dataset.source_table, status_code=409)
    if not await abi_repo.physical_table_exists(session, schema, table):
        raise AbiServiceError("dataset_source_missing", 409)

    physical = await abi_repo.list_physical_columns(session, schema, table)
    physical_names = {str(item["column_name"]) for item in physical}
    physical_types = {
        str(item["column_name"]): str(item["data_type"]) for item in physical
    }
    declared = await abi_repo.list_dataset_columns(
        session, dataset.workspace_id, dataset.id
    )
    if not declared:
        raise AbiServiceError("dataset_columns_not_configured", 409)
    all_columns = [
        column.column_name for column in declared if column.column_name in physical_names
    ]
    if not all_columns:
        raise AbiServiceError("dataset_columns_not_configured", 409)

    policy_rows = await abi_repo.list_field_policies(
        session, dataset.workspace_id, dataset.id
    )
    policies = {policy.field_path: policy.pii_class for policy in policy_rows}
    mask_rules = {policy.field_path: policy.mask_rule for policy in policy_rows}

    if requested_columns is None:
        selected = [
            column for column in all_columns if policies.get(column, "unknown") != "unknown"
        ]
        if not selected:
            raise AbiServiceError("pii_policy_not_configured", 403)
    else:
        if not requested_columns:
            raise AbiServiceError("columns_empty", 400)
        selected = []
        seen: set[str] = set()
        for column in requested_columns:
            if column not in all_columns:
                raise AbiServiceError("query_column_not_allowed", 400)
            if column in seen:
                raise AbiServiceError("duplicate_query_column", 400)
            seen.add(column)
            selected.append(column)

    denied = [
        column for column in selected if policies.get(column, "unknown") == "unknown"
    ]
    if denied:
        raise AbiServiceError("pii_unknown_denied", 403)

    filterable = frozenset(
        column.column_name
        for column in declared
        if column.filterable
        and column.column_name in all_columns
        and _is_scalar_type(physical_types.get(column.column_name, ""))
        and policies.get(column.column_name, "unknown") != "unknown"
    )
    sortable = frozenset(
        column.column_name
        for column in declared
        if column.sortable
        and column.column_name in all_columns
        and _is_scalar_type(physical_types.get(column.column_name, ""))
        and policies.get(column.column_name, "unknown") != "unknown"
    )
    return _Selection(
        schema=schema,
        table=table,
        all_columns=all_columns,
        selected=selected,
        policies=policies,
        mask_rules=mask_rules,
        filterable=filterable,
        sortable=sortable,
        types={
            column: physical_types[column]
            for column in all_columns
            if column in physical_types
        },
    )


def _validate_filter_columns(
    selection: _Selection,
    filters: list[AbiQueryFilter],
    order_by: list[AbiQueryOrder],
) -> None:
    for item in filters:
        if item.column not in selection.all_columns:
            raise AbiServiceError("query_column_not_allowed", 400)
        if selection.policies.get(item.column, "unknown") == "unknown":
            raise AbiServiceError("pii_unknown_denied", 403)
        if item.column not in selection.filterable:
            raise AbiServiceError("query_column_not_filterable", 400)
        if item.op == "in":
            if not isinstance(item.value, list) or not item.value:
                raise AbiServiceError("query_filter_invalid", 400)
            if len(item.value) > 200:
                raise AbiServiceError("query_filter_invalid", 400)
        elif item.op == "contains":
            if not isinstance(item.value, str):
                raise AbiServiceError("query_filter_invalid", 400)
        elif item.op not in ("is_null", "not_null") and item.value is None:
            raise AbiServiceError("query_filter_invalid", 400)
    for order_item in order_by:
        if order_item.column not in selection.all_columns:
            raise AbiServiceError("query_column_not_allowed", 400)
        if selection.policies.get(order_item.column, "unknown") == "unknown":
            raise AbiServiceError("pii_unknown_denied", 403)
        if order_item.column not in selection.sortable:
            raise AbiServiceError("query_column_not_sortable", 400)


def _coerce_scalar(value: Any, data_type: str) -> Any:
    """按物理列类型转换过滤值。

    前端只对数字与布尔做转换，日期/时间/UUID 仍以字符串发送。
    asyncpg 对 ``date = $1`` 这类参数要求 Python date 对象，不转换会 500。
    """
    if value is None:
        return None
    kind = data_type.lower()
    try:
        if kind in ("smallint", "integer", "bigint"):
            return int(value)
        if kind in ("numeric", "decimal"):
            return Decimal(str(value))
        if kind in ("real", "double precision"):
            return float(value)
        if kind == "boolean":
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in ("true", "1"):
                return True
            if text in ("false", "0"):
                return False
            raise ValueError(value)
        if kind == "date":
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            return date.fromisoformat(str(value))
        if kind.startswith("timestamp"):
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if kind.startswith("time"):
            if isinstance(value, time):
                return value
            return time.fromisoformat(str(value).replace("Z", "+00:00"))
        if kind == "uuid":
            if isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))
        if kind in ("text", "character varying", "character", "name", "citext"):
            return str(value)
    except (TypeError, ValueError) as exc:
        raise AbiServiceError("query_filter_invalid", 400) from exc
    return value


def _coerced_filter_tuples(
    selection: _Selection,
    filters: list[AbiQueryFilter],
) -> list[tuple[str, str, Any]]:
    result: list[tuple[str, str, Any]] = []
    for item in filters:
        data_type = selection.types.get(item.column, "")
        if item.op in ("is_null", "not_null", "contains"):
            result.append((item.column, item.op, item.value))
        elif item.op == "in" and isinstance(item.value, list):
            result.append(
                (
                    item.column,
                    item.op,
                    [_coerce_scalar(value, data_type) for value in item.value],
                )
            )
        else:
            result.append(
                (item.column, item.op, _coerce_scalar(item.value, data_type))
            )
    return result


def _order_tuples(order_by: list[AbiQueryOrder]) -> list[tuple[str, str]]:
    return [(item.column, item.direction) for item in order_by]


async def _fetch_rows(
    session: AsyncSession,
    selection: _Selection,
    filters: list[AbiQueryFilter],
    order_by: list[AbiQueryOrder],
    *,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    try:
        return await abi_repo.query_dataset_rows(
            session,
            schema=selection.schema,
            table=selection.table,
            columns=selection.selected,
            filters=_coerced_filter_tuples(selection, filters),
            order_by=_order_tuples(order_by),
            limit=limit,
            offset=offset,
            allowed_columns=set(selection.filterable) | set(selection.sortable),
        )
    except (
        abi_repo.UnsafeIdentifierError,
        abi_repo.QueryColumnNotAllowedError,
        abi_repo.QueryOperatorNotAllowedError,
        abi_repo.QueryFilterValueError,
    ) as exc:
        raise AbiServiceError("query_invalid", 400) from exc


async def _count_rows(
    session: AsyncSession,
    selection: _Selection,
    filters: list[AbiQueryFilter],
) -> int:
    try:
        return await abi_repo.count_dataset_rows(
            session,
            schema=selection.schema,
            table=selection.table,
            columns=selection.selected,
            filters=_coerced_filter_tuples(selection, filters),
            allowed_columns=set(selection.filterable) | set(selection.sortable),
        )
    except (
        abi_repo.UnsafeIdentifierError,
        abi_repo.QueryColumnNotAllowedError,
        abi_repo.QueryOperatorNotAllowedError,
        abi_repo.QueryFilterValueError,
    ) as exc:
        raise AbiServiceError("query_invalid", 400) from exc


def _mask_value(value: Any, pii_class: str, mask_rule: str | None = None) -> Any:
    """按策略遮罩单个值。

    实现委托给 ``abi_query.mask_value``——查询、同步导出、异步 worker
    三条路径必须用同一份代码。此前这里是独立的一份，只认 pii_class、
    不看 mask_rule，于是：
    - 策略里配了 ``last4`` / ``hash``，在线查询完全无视，仍返回 ``***``；
    - ``quasi`` 这里遮成「前 2 后 1」，worker 那边因不在
      ``PII_MASKED_CLASSES`` 而**原样明文输出**。

    同一份策略在两条路径上产出不同结果，用户无法预期自己拿到什么。
    """
    from data_intelligence_hub.services.abi_query import mask_value

    return mask_value(value, pii_class, mask_rule)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, int | float):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).hex()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_json_safe(item) for item in value]
    return str(value)


def _serialize_row(
    row: dict[str, Any],
    columns: list[str],
    policies: dict[str, str],
    *,
    mask_pii: bool,
    mask_rules: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    rules = mask_rules or {}
    serialized: dict[str, Any] = {}
    for column in columns:
        pii_class = policies.get(column, "unknown")
        value = row.get(column)
        if mask_pii:
            value = _mask_value(value, pii_class, rules.get(column))
        serialized[column] = _json_safe(value)
    return serialized


def _masked_columns(selection: _Selection) -> list[str]:
    return sorted(
        column for column in selection.selected if selection.policies[column] != "none"
    )


async def query_abi_dataset(
    session: AsyncSession,
    access: DatasetAccess,
    payload: AbiQueryRequest,
) -> AbiQueryResponse:
    selection = await _resolve_selection(session, access.dataset, payload.columns)
    _validate_filter_columns(selection, payload.filters, payload.order_by)
    rows = await _fetch_rows(
        session,
        selection,
        payload.filters,
        payload.order_by,
        limit=payload.limit,
        offset=payload.offset,
    )
    total = await _count_rows(session, selection, payload.filters)
    return AbiQueryResponse(
        dataset_id=access.dataset.id,
        columns=selection.selected,
        rows=[
            _serialize_row(
                row,
                selection.selected,
                selection.policies,
                mask_pii=True,
                mask_rules=selection.mask_rules,
            )
            for row in rows
        ],
        total=total,
        limit=payload.limit,
        offset=payload.offset,
        masked_fields=_masked_columns(selection),
    )


async def list_abi_grants(
    session: AsyncSession,
    access: DatasetAccess,
) -> AbiGrantListResponse:
    grants = await abi_repo.list_access_grants(
        session, access.workspace.id, access.dataset.id
    )
    return AbiGrantListResponse(
        items=[AbiGrantResponse.model_validate(grant) for grant in grants],
        total=len(grants),
    )


async def create_abi_grant(
    session: AsyncSession,
    access: DatasetAccess,
    payload: AbiGrantCreateRequest,
) -> AbiGrantResponse:
    target = await get_user_by_id(session, payload.user_id)
    if target is None or target.status != "active":
        raise AbiServiceError("user_not_found", 404)
    existing = await abi_repo.get_access_grant(
        session,
        access.workspace.id,
        access.dataset.id,
        payload.user_id,
    )
    if existing is not None:
        raise AbiServiceError("grant_exists", 409)
    grant = AccessGrant(
        id=uuid.uuid4(),
        dataset_id=access.dataset.id,
        workspace_id=access.workspace.id,
        user_id=payload.user_id,
        role=payload.role,
        granted_by=access.user.id,
    )
    await abi_repo.create_access_grant(session, grant)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AbiServiceError("grant_exists", 409) from exc
    return AbiGrantResponse.model_validate(grant)


async def delete_abi_grant(
    session: AsyncSession,
    access: DatasetAccess,
    grant_id: uuid.UUID,
) -> AbiDeleteResponse:
    grant = await abi_repo.get_access_grant_by_id(
        session, access.workspace.id, access.dataset.id, grant_id
    )
    if grant is None:
        raise AbiServiceError("grant_not_found", 404)
    if grant.role == "admin":
        admins = await abi_repo.count_admin_grants(
            session, access.workspace.id, access.dataset.id
        )
        if admins <= 1:
            raise AbiServiceError("last_admin_grant", 409)
    await abi_repo.delete_access_grant(session, grant)
    await session.commit()
    return AbiDeleteResponse(deleted=True, id=grant_id)


async def get_abi_policy(
    session: AsyncSession,
    access: DatasetAccess,
) -> AbiPolicyResponse:
    columns = await abi_repo.list_dataset_columns(
        session, access.workspace.id, access.dataset.id
    )
    policies = await abi_repo.list_field_policies(
        session, access.workspace.id, access.dataset.id
    )
    return AbiPolicyResponse(
        dataset_id=access.dataset.id,
        pii_scanned=access.dataset.pii_scanned,
        items=_effective_policy(columns, policies),
    )


async def replace_abi_policy(
    session: AsyncSession,
    access: DatasetAccess,
    payload: AbiPolicyUpdateRequest,
) -> AbiPolicyResponse:
    """按提交项更新 PII 策略，并拦截降级。

    两条控制，缺一不可：

    1. **增量而非全量。** 未提交的列保留原分类。此前是全量替换、未提交列
       写成 ``unknown``：只改一个字段会顺手清空其余字段，而
       ``direct → unknown → none`` 分两步即可把敏感列洗成明文。
    2. **降级需要 admin + 理由。** 否则 publisher 把 ``secret`` 改成
       ``none`` 就能拿到明文，完全绕过未遮罩导出的
       admin 校验 + 双人审批 + 理由三重门禁——而那三条门禁的成本
       远高于改一行策略。

    ``quasi`` 与 ``direct``/``secret`` 同属敏感侧：worker 遮罩路径
    （``abi_export.mask_row``）依赖 ``PII_MASKED_CLASSES``，``quasi``
    此前不在其中，等于明文返回。降级比较必须把它算作敏感。
    """

    columns = await abi_repo.list_dataset_columns(
        session, access.workspace.id, access.dataset.id
    )
    column_names = {column.column_name for column in columns}
    provided: dict[str, AbiPolicyUpdateItem] = {}
    for item in payload.items:
        if item.field_path not in column_names:
            raise AbiServiceError("policy_field_not_column", 400)
        if item.field_path in provided:
            raise AbiServiceError("duplicate_policy_field", 400)
        provided[item.field_path] = item

    existing_rows = await abi_repo.list_field_policies(
        session, access.workspace.id, access.dataset.id
    )
    existing = {row.field_path: row for row in existing_rows}

    is_admin = role_rank(access.grant.role) >= role_rank("admin")
    reason = (payload.reason or "").strip()

    # 先整体判定，再落库：任何一项被拒都不该留下半套策略。
    downgrades: list[str] = []
    for field_path, item in provided.items():
        current = existing.get(field_path)
        if current is None or current.pii_class == "unknown":
            # 首次分类不是降级——unknown 等于「还没判定」，不是「已判定为敏感」。
            continue
        if _pii_rank(item.pii_class) < _pii_rank(current.pii_class):
            downgrades.append(field_path)
    if downgrades:
        if not is_admin:
            raise AbiServiceError("pii_downgrade_requires_admin", 403)
        if len(reason) < 10:
            # 与未遮罩导出的理由要求一致：过短的理由没有审计价值。
            raise AbiServiceError("pii_downgrade_reason_required", 400)

    decided_by = f"user:{access.user.id}"
    now = _now()
    for field_path, item in provided.items():
        current = existing.get(field_path)
        if current is None:
            session.add(
                FieldPolicy(
                    id=uuid.uuid4(),
                    dataset_id=access.dataset.id,
                    field_path=field_path,
                    pii_class=item.pii_class,
                    mask_rule=item.mask_rule,
                    decided_by=decided_by,
                )
            )
            continue
        current.pii_class = item.pii_class
        current.mask_rule = item.mask_rule
        current.decided_by = decided_by
        current.created_at = now

    await session.flush()
    rows = await abi_repo.list_field_policies(
        session, access.workspace.id, access.dataset.id
    )
    # 只有真的覆盖到全部列，才算「已扫描」。此前无条件置 True，
    # 导致 overview 的「待 PII 处理」计数长期失真。
    covered = {row.field_path for row in rows if row.pii_class != "unknown"}
    access.dataset.pii_scanned = column_names.issubset(covered)
    await session.commit()
    return AbiPolicyResponse(
        dataset_id=access.dataset.id,
        pii_scanned=access.dataset.pii_scanned,
        items=[_policy_item(row, is_default=False) for row in rows],
    )


async def create_abi_upload(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AbiUploadCreateRequest,
) -> AbiUploadCreateResponse:
    dataset, _grant = await _resolve_dataset_for_user(
        session, workspace, user, payload.dataset_slug, "editor"
    )
    if dataset.source_kind != "upload":
        raise AbiServiceError("dataset_not_upload_target", 400)

    # 建批次交给 abi_upload.create_batch。
    #
    # 这里原来自己拼一个 UploadBatch，漏了两件事：
    # 1. 不设 storage_path —— append_content 立刻报 abi_upload_storage_path_missing；
    # 2. 不回填 dataset.source_table —— 即使写入成功，查询也因
    #    dataset_source_not_ready 报 409。
    # 两处都是「A 套自己实现、B 套才是完整版」的具体表现。
    from data_intelligence_hub.services.abi_upload import create_batch

    batch, token = await create_batch(
        session,
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        user_id=user.id,
        filename=payload.filename,
        mode=payload.mode,
        expected_sha256=payload.expected_sha256,
        expected_rows=payload.expected_rows,
    )
    return AbiUploadCreateResponse(
        batch=AbiUploadBatchResponse.model_validate(batch),
        upload_token=token,
        upload_url="/api/abi/uploads/content",
        token_expires_at=batch.token_expires_at,
    )


async def write_abi_upload_content(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    upload_token: str,
    chunks: AsyncIterator[bytes],
) -> AbiUploadBatchResponse:
    """接收上传字节流。

    写盘、sha256、**行数统计**全部交给 ``abi_upload.append_content``。
    本函数只负责把「按 token 查批次」翻译成它的入参。

    这里原先有一份自己的写盘实现，漏写 ``actual_rows``。commit 的前置检查
    要求该列非空，于是**每一次走 HTTP 的上传都会在 commit 阶段失败**，
    报的还是 ``abi_upload_checksum_missing``——名字指向 sha256，真实原因却是
    行数没记。postgres 闭环测试直接调 ``append_content``，刚好绕开这条路径，
    所以单测全绿而生产必然失败。

    行为差异（都是收紧，不是放宽）：
    - 已写过内容的批次不能再写。旧实现放行 ``status='uploaded'``，等于允许
      静默覆盖已校验的字节。
    - 只允许原上传人写入。上传 token 本就一次性发给创建者。
    """
    from data_intelligence_hub.services.abi_upload import append_content

    token_hash = hashlib.new("sha256", upload_token.encode()).digest()
    batch = await abi_repo.get_upload_batch_by_token_hash(session, token_hash)
    if batch is None or batch.workspace_id != workspace.id:
        raise AbiServiceError("upload_batch_not_found", 404)

    updated = await append_content(
        session,
        batch_id=batch.id,
        token=upload_token,
        chunks=chunks,
        user_id=user.id,
    )
    return AbiUploadBatchResponse.model_validate(updated)


def _sha256_file(path: Path) -> bytes:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.digest()


def _count_file_rows(path: Path, filename: str) -> int:
    """统计数据行数。CSV/TSV 用 csv 解析，正确处理字段内的换行。"""
    lower = filename.lower()
    if lower.endswith((".csv", ".tsv")):
        delimiter = "\t" if lower.endswith(".tsv") else ","
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            parsed_rows = sum(1 for _ in csv.reader(handle, delimiter=delimiter))
        return max(0, parsed_rows - 1)
    newline_count = 0
    last_byte = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            newline_count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if last_byte not in (b"\n", b""):
        newline_count += 1
    return newline_count


async def commit_abi_upload(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    batch_id: uuid.UUID,
) -> AbiUploadBatchResponse:
    batch = await abi_repo.get_upload_batch(session, workspace.id, batch_id)
    if batch is None:
        raise AbiServiceError("upload_batch_not_found", 404)
    grant = await _require_grant(
        session, workspace.id, batch.dataset_id, user.id, "editor"
    )
    if batch.uploaded_by != user.id and role_rank(grant.role) < role_rank("admin"):
        raise AbiServiceError("upload_commit_forbidden", 403)
    if batch.status != "uploaded":
        raise AbiServiceError("upload_not_uploaded", 409)
    if batch.storage_path is None:
        raise AbiServiceError("upload_file_missing", 409)

    root = _upload_root() / str(batch.id)
    path = Path(batch.storage_path).resolve()
    _ensure_under_root(path, root)
    if not path.is_file():
        raise AbiServiceError("upload_file_missing", 409)
    if batch.actual_sha256 is not None and _sha256_file(path) != batch.actual_sha256:
        raise AbiServiceError("upload_file_corrupted", 409)
    rows = _count_file_rows(path, batch.filename)
    if batch.expected_rows is not None and rows != batch.expected_rows:
        raise AbiServiceError("upload_row_count_mismatch", 409)

    # 真正的落库交给 abi_upload.commit_batch：它建物理表、逐行校验、
    # 按 mode 写 append/upsert/replace，并回写 catalog 的 row_count /
    # version / last_loaded_at。
    #
    # 改动前这里只把 batch.status 置成 committed 就返回——上传接口报成功，
    # 数据一行都没进去，紧接着查询必然 409 (dataset_source_not_ready)。
    # 这是上传闭环断裂的根因。
    #
    # 上面的所有前置校验（权限、状态、路径、sha256、行数）保留：
    # commit_batch 内部会再查一遍，但那几次查询比让用户传完 200MB 才发现
    # 权限不够要便宜得多。
    from data_intelligence_hub.services.abi_upload import commit_batch

    committed = await commit_batch(
        session,
        batch_id=batch.id,
        user_id=user.id,
    )
    return AbiUploadBatchResponse.model_validate(committed)


async def list_abi_uploads(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    dataset_slug: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> AbiUploadListResponse:
    """列出某 dataset 的上传批次。

    权限是 viewer：看到自己的历史批次是基本可观测性需求，不涉及数据内容。
    """
    dataset, _grant = await _resolve_dataset_for_user(
        session, workspace, user, dataset_slug, "viewer"
    )
    rows = await abi_repo.list_upload_batches(
        session, workspace.id, dataset.id, limit=limit, offset=offset
    )
    total = await abi_repo.count_upload_batches(session, workspace.id, dataset.id)
    return AbiUploadListResponse(
        items=[AbiUploadBatchResponse.model_validate(row) for row in rows],
        total=total,
    )


async def get_abi_upload_errors(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    batch_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> AbiUploadErrorListResponse:
    """列出一个批次的校验错误。

    批次不存在与跨租户一律 404，不区分——否则 404/403 的差异本身就是
    「这个 id 存在」的信息泄露。
    """
    batch = await abi_repo.get_upload_batch(session, workspace.id, batch_id)
    if batch is None:
        raise AbiServiceError("upload_batch_not_found", 404)
    await _require_grant(session, workspace.id, batch.dataset_id, user.id, "viewer")

    rows = await abi_repo.list_upload_errors(
        session, workspace.id, batch_id, limit=limit, offset=offset
    )
    total = await abi_repo.count_upload_errors(session, workspace.id, batch_id)
    return AbiUploadErrorListResponse(
        items=[AbiUploadErrorItem.model_validate(row) for row in rows],
        total=total,
    )


async def retry_abi_upload(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    batch_id: uuid.UUID,
) -> AbiUploadBatchResponse:
    """重跑一个 failed 批次的 commit。

    **不需要重新上传字节。** 失败发生在 commit 阶段时，文件已经完整落盘
    并通过 sha256 校验；让用户重传 200MB 只是为了重跑一次解析，代价与
    收益不匹配。

    前置条件逐条收紧：

    - 只允许 ``failed``。其它状态重试没有意义：``committed`` 已经成功，
      ``pending``/``uploaded`` 该走正常的 commit 流程。
    - 文件必须还在，且 sha256 与记录一致。不一致说明落盘内容已被替换，
      这时重跑等于拿未知数据入库。
    - 权限与 commit 一致：``replace`` 模式需要 publisher，其余 editor；
      非上传人需要 admin。

    **本函数不修改任何状态。** ``failed → uploaded`` 的转换由
    ``commit_batch(retry=True)`` 在行锁内完成。先前这里在锁外用无条件
    ORM UPDATE 翻转状态并先行提交，有三个后果，都是实测复核确认的：

    1. 两个并发重试可以把已 ``committed`` 的批次打回 ``uploaded``，
       随后失败清理按 batch id 删掉第一次成功写入的全部行——数据静默消失。
    2. ``commit_batch`` 入场阶段（权限、建表）抛错时不会走它的
       ``_mark_failed``，批次永久停在 ``uploaded``：重试拒绝、commit 也拒绝。
    3. 旧 ``upload_error`` 在确定能继续跑之前就被删掉，403 之后失败原因
       再也找不回来。

    ``replace`` 模式的权限判定也必须在这里与 ``commit_batch`` 一致：
    否则 editor 能通过本函数，却在 ``commit_batch`` 里 403。
    """
    batch = await abi_repo.get_upload_batch(session, workspace.id, batch_id)
    if batch is None:
        raise AbiServiceError("upload_batch_not_found", 404)

    # 与 commit_batch 的门槛保持一致：replace 要 publisher。
    required_role = "publisher" if batch.mode == "replace" else "editor"
    grant = await _require_grant(
        session, workspace.id, batch.dataset_id, user.id, required_role
    )
    if batch.uploaded_by != user.id and role_rank(grant.role) < role_rank("admin"):
        raise AbiServiceError("upload_retry_forbidden", 403)
    if batch.status != "failed":
        raise AbiServiceError("upload_not_retryable", 409)
    if batch.storage_path is None:
        raise AbiServiceError("upload_file_missing", 409)

    root = _upload_root() / str(batch.id)
    path = Path(batch.storage_path).resolve()
    _ensure_under_root(path, root)
    if not path.is_file():
        raise AbiServiceError("upload_file_missing", 409)
    if batch.actual_sha256 is not None and _sha256_file(path) != batch.actual_sha256:
        raise AbiServiceError("upload_file_corrupted", 409)

    from data_intelligence_hub.services.abi_upload import commit_batch

    retried = await commit_batch(
        session, batch_id=batch.id, user_id=user.id, retry=True
    )
    return AbiUploadBatchResponse.model_validate(retried)


async def get_abi_export_policy(
    session: AsyncSession,
    access: DatasetAccess,
) -> AbiExportPolicyResponse:
    """读 dataset 级导出策略。没有策略行时返回表定义的默认值。"""
    policy = await abi_repo.get_export_policy(
        session, access.workspace.id, access.dataset.id
    )
    if policy is None:
        # 与 export_policy 的 server_default 保持一致：默认要求双人审批。
        # 格式与行数没有默认限制——那是代码里的 MAX_EXPORT_ROWS。
        return AbiExportPolicyResponse(
            dataset_id=None,
            max_rows_masked=None,
            require_dual_approval=True,
            allowed_formats=None,
            is_default=True,
        )
    return AbiExportPolicyResponse(
        dataset_id=policy.dataset_id,
        max_rows_masked=policy.max_rows_masked,
        require_dual_approval=policy.require_dual_approval,
        allowed_formats=list(policy.allowed_formats)
        if policy.allowed_formats is not None
        else None,
        is_default=policy.dataset_id is None,
    )


async def set_abi_export_policy(
    session: AsyncSession,
    access: DatasetAccess,
    payload: AbiExportPolicyUpdateRequest,
) -> AbiExportPolicyResponse:
    """写入 dataset 级导出策略。需要 admin。

    策略直接决定「未遮罩导出要不要审批」「能不能导出某种格式」「最多
    导出多少行」，放宽其中任何一条都等于削弱管控，所以门槛与 PII 降级
    同级：admin。
    """
    if role_rank(access.grant.role) < role_rank("admin"):
        raise AbiServiceError("export_policy_requires_admin", 403)

    policy = await abi_repo.upsert_export_policy(
        session,
        access.workspace.id,
        access.dataset.id,
        max_rows_masked=payload.max_rows_masked,
        require_dual_approval=payload.require_dual_approval,
        allowed_formats=list(payload.allowed_formats)
        if payload.allowed_formats is not None
        else None,
    )
    await session.commit()
    return AbiExportPolicyResponse(
        dataset_id=policy.dataset_id,
        max_rows_masked=policy.max_rows_masked,
        require_dual_approval=policy.require_dual_approval,
        allowed_formats=list(policy.allowed_formats)
        if policy.allowed_formats is not None
        else None,
        is_default=False,
    )


def _filters_hmac(payload: dict[str, Any]) -> bytes:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode()
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, b"abi.export.filters.v1:" + canonical, hashlib.sha256).digest()


def _to_csv_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _csv_safe(value: str) -> str:
    """阻断 CSV 公式注入的 5 种前缀。"""
    if value.startswith(_CSV_INJECTION_PREFIXES):
        return "'" + value
    return value


def _to_xlsx_value(value: Any) -> Any:
    """xlsx 单元格值。字符串同样做公式注入转义。"""
    if isinstance(value, str):
        return _csv_safe(value)
    if isinstance(value, dict | list):
        return _csv_safe(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return value


def _render_export(
    export_format: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> bytes:
    if export_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow(
                [_csv_safe(_to_csv_text(row.get(column))) for column in columns]
            )
        return buffer.getvalue().encode("utf-8")
    if export_format == "jsonl":
        return b"".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            + b"\n"
            for row in rows
        )
    if export_format == "xlsx":
        # 延迟导入：只有 xlsx 导出才加载 openpyxl。
        from openpyxl import Workbook  # type: ignore[import-untyped]

        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title="abi")
        sheet.append(columns)
        for row in rows:
            sheet.append([_to_xlsx_value(row.get(column)) for column in columns])
        binary_buffer = io.BytesIO()
        workbook.save(binary_buffer)
        return binary_buffer.getvalue()
    raise AbiServiceError("export_format_unsupported", 422)


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(path)


def _export_filename(slug: str, job_id: uuid.UUID, export_format: str) -> str:
    return f"abi-{slug}-{job_id.hex[:8]}.{export_format}"


async def create_abi_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AbiExportCreateRequest,
) -> AbiExportJobResponse:
    dataset, grant = await _resolve_dataset_for_user(
        session, workspace, user, payload.dataset_slug, "publisher"
    )
    if not payload.mask_pii and role_rank(grant.role) < role_rank("admin"):
        raise AbiServiceError("export_unmasked_requires_admin", 403)
    reason = (payload.reason or "").strip()
    if not payload.mask_pii and len(reason) < 10:
        # 未遮罩导出必须留下可审计的理由；过短的理由没有审计价值。
        raise AbiServiceError("export_reason_required", 400)

    selection = await _resolve_selection(session, dataset, payload.columns)
    _validate_filter_columns(selection, payload.filters, payload.order_by)
    policy = await abi_repo.get_export_policy(session, workspace.id, dataset.id)

    # 没有策略行时，按「表定义的默认值」行事，而不是当成「无策略、放行」。
    #
    # 这两者差别很大：``export_policy.require_dual_approval`` 的
    # server_default 是 true，说明设计意图就是默认要求双人审批。但本函数
    # 此前写的是 ``policy is not None and policy.require_dual_approval``，
    # 而全仓**没有任何代码创建策略行**——于是 policy 恒为 None，双人审批
    # 整段被跳过，未遮罩导出直接出文件。
    #
    # 生产实测确认过：admin 发起 mask_pii=false 的导出，返回 status=succeeded，
    # 一次都没进 awaiting_approval。这不是配置问题，是代码路径缺失。
    require_dual_approval = (
        policy.require_dual_approval if policy is not None else True
    )

    if (
        policy is not None
        and policy.allowed_formats is not None
        and payload.format not in policy.allowed_formats
    ):
        raise AbiServiceError("export_format_not_allowed", 403)

    total = await _count_rows(session, selection, payload.filters)
    row_limit = _EXPORT_MAX_ROWS
    if payload.mask_pii and policy is not None and policy.max_rows_masked is not None:
        row_limit = min(row_limit, policy.max_rows_masked)
    if total > row_limit:
        raise AbiServiceError("export_row_limit_exceeded", 413)

    job_filters: dict[str, Any] = {
        "filters": [
            {"column": item.column, "op": item.op, "value": item.value}
            for item in payload.filters
        ],
        "order_by": [
            {"column": item.column, "direction": item.direction}
            for item in payload.order_by
        ],
        "columns": selection.selected,
    }
    now = _now()
    job = ExportJob(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        created_by=user.id,
        format=payload.format,
        mask_pii=payload.mask_pii,
        filters=job_filters,
        filters_hmac=_filters_hmac(job_filters),
        columns=selection.selected,
        reason=reason or None,
        status="queued",
        expires_at=now + _EXPORT_TTL,
    )
    await abi_repo.create_export_job(session, job)

    # 双人审批只针对「关闭遮罩」的导出。
    #
    # approve_job 的契约就是「审批一个关闭遮罩的作业」，对 mask_pii=True
    # 直接抛 abi_export_approval_not_required。此前这里不看 mask_pii，
    # 把带遮罩的作业也置成 awaiting_approval——而没有任何人能批准它，
    # 作业永久卡死。策略要求双人审批时，遮罩导出直接放行：
    # 遮罩本身已经把暴露面限制了，再要求审批是无解的。
    if require_dual_approval and not payload.mask_pii:
        job.status = "awaiting_approval"
        await session.commit()
        return AbiExportJobResponse.model_validate(job)

    job.status = "running"
    job.started_at = now
    path: Path | None = None
    try:
        rows = await _fetch_rows(
            session,
            selection,
            payload.filters,
            payload.order_by,
            limit=row_limit,
            offset=0,
        )
        serialized = [
            _serialize_row(
                row,
                selection.selected,
                selection.policies,
                mask_pii=payload.mask_pii,
                mask_rules=selection.mask_rules,
            )
            for row in rows
        ]
        content = _render_export(payload.format, selection.selected, serialized)
        filename = _export_filename(dataset.slug, job.id, payload.format)
        path = _export_path(workspace.id, job.id, filename)
        _write_atomic(path, content)
        job.status = "succeeded"
        job.artifact_path = str(path)
        job.filename = filename
        job.content_type = _EXPORT_CONTENT_TYPES[payload.format]
        job.bytes_total = len(content)
        job.rows_total = len(serialized)
        job.finished_at = _now()
        await session.commit()
    except BaseException:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    return AbiExportJobResponse.model_validate(job)


def _export_visible(
    job: ExportJob,
    grant: AccessGrant | None,
) -> bool:
    """按 grant 与导出是否遮罩判定可见性。

    遮罩导出对任意角色放行；未遮罩导出只放行 publisher/admin，
    避免 viewer 通过下载拿到未遮罩的 PII。

    **创建人不再自动放行。** 原先 ``job.created_by == user.id`` 直接返回
    True，于是撤掉某人的 grant 之后，他此前创建的导出仍然可以下载——
    包括未遮罩的。撤权应当同时切断历史产物的访问，否则「收回权限」
    只挡住了新请求，挡不住已经发出去的东西。

    这条规则对列表与下载同时生效（两者都走 ``_get_visible_export``），
    避免出现「列表看不到但能直接按 id 下载」的不一致。
    """
    if grant is None:
        return False
    if job.mask_pii:
        return role_rank(grant.role) >= role_rank("viewer")
    return role_rank(grant.role) >= role_rank("publisher")


async def _get_visible_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    job_id: uuid.UUID,
) -> ExportJob:
    job = await abi_repo.get_export_job(session, workspace.id, job_id)
    if job is None:
        raise AbiServiceError("export_not_found", 404)
    grant = await abi_repo.get_access_grant(
        session, workspace.id, job.dataset_id, user.id
    )
    if not _export_visible(job, grant):
        raise AbiServiceError("export_not_found", 404)
    return job


def _ensure_export_not_expired(job: ExportJob) -> None:
    if job.status == "expired":
        raise AbiServiceError("export_expired", 410)
    if job.expires_at is not None and job.expires_at <= _now():
        raise AbiServiceError("export_expired", 410)


async def list_abi_exports(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    *,
    limit: int,
    offset: int,
) -> AbiExportListResponse:
    jobs = await abi_repo.list_export_jobs(
        session,
        workspace.id,
        user.id,
        see_all=False,
        limit=limit,
        offset=offset,
    )
    total = await abi_repo.count_export_jobs(
        session, workspace.id, user.id, see_all=False
    )
    return AbiExportListResponse(
        items=[AbiExportJobResponse.model_validate(job) for job in jobs],
        total=total,
    )


async def get_abi_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    job_id: uuid.UUID,
) -> AbiExportJobResponse:
    job = await _get_visible_export(session, workspace, user, job_id)
    _ensure_export_not_expired(job)
    return AbiExportJobResponse.model_validate(job)


async def approve_abi_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    job_id: uuid.UUID,
) -> AbiExportJobResponse:
    """批准一个等待双人审批的导出作业。

    权限、非自批、状态由 ``abi_export.approve_job`` 校验——它写在事务内
    并带 ``FOR UPDATE``，重复批准与并发批准都不会产生两份产物。
    这里只补一层可见性：用户看不到的作业不该以「审批」的形式暴露存在。
    """
    from data_intelligence_hub.services.abi_export import approve_job

    await _get_visible_export(session, workspace, user, job_id)
    job = await approve_job(
        session,
        job_id=job_id,
        workspace_id=workspace.id,
        approver_id=user.id,
    )
    return AbiExportJobResponse.model_validate(job)


async def reject_abi_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    job_id: uuid.UUID,
    reason: str | None = None,
) -> AbiExportJobResponse:
    """驳回一个等待审批的导出作业。

    驳回只改状态，不删产物（此时还没有产物）。``rejected`` 是终态：
    想要数据得重新发起导出，这样审计链上留得下「谁驳了、为什么」。
    """
    job = await _get_visible_export(session, workspace, user, job_id)
    if job.status != "awaiting_approval":
        raise AbiServiceError("export_not_awaiting_approval", 409)
    if job.created_by == user.id:
        # 自批自驳都不算控制：申请人自己驳回没有审计价值，且会掩盖
        # 「没人处理」这件事。
        raise AbiServiceError("export_self_review_denied", 403)
    grant = await abi_repo.get_access_grant(
        session, workspace.id, job.dataset_id, user.id
    )
    if grant is None or role_rank(grant.role) < role_rank("publisher"):
        raise AbiServiceError("export_reject_requires_publisher", 403)

    job.status = "rejected"
    job.finished_at = _now()
    if reason:
        job.error = reason.strip()[:500]
    await session.commit()
    return AbiExportJobResponse.model_validate(job)


async def get_abi_export_download(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    job_id: uuid.UUID,
) -> tuple[ExportJob, Path]:
    job = await _get_visible_export(session, workspace, user, job_id)
    _ensure_export_not_expired(job)
    if job.status != "succeeded":
        raise AbiServiceError("export_not_ready", 409)
    if job.artifact_path is None:
        raise AbiServiceError("export_file_missing", 404)
    root = _export_root()
    path = Path(job.artifact_path).resolve()
    _ensure_under_root(path, root)
    if not path.is_file():
        raise AbiServiceError("export_file_missing", 404)
    return job, path


__all__ = [
    "AbiServiceError",
    "commit_abi_upload",
    "create_abi_dataset",
    "create_abi_export",
    "get_abi_export_policy",
    "create_abi_grant",
    "create_abi_upload",
    "delete_abi_grant",
    "get_abi_dataset_detail",
    "get_abi_export",
    "get_abi_export_download",
    "get_abi_overview",
    "get_abi_policy",
    "list_abi_datasets",
    "list_abi_exports",
    "list_abi_grants",
    "query_abi_dataset",
    "replace_abi_policy",
    "set_abi_export_policy",
    "write_abi_upload_content",
]

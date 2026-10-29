"""ABI 导出服务。

职责：

- ``create_job`` 建异步导出作业，默认遮罩 PII。关闭遮罩需要 publisher
  角色、不少于 10 个字的理由，且审批人不能是申请人。
- ``approve_job`` 完成双人审批；审批人同样必须有 publisher grant。
- ``run_job`` 流式生成 csv / xlsx / jsonl 文件。xlsx 用 openpyxl 惰性导入，
  只使用 write_only 模式，避免 50 万行全量加载进内存。
- 下载授权在 ``abi_service.get_abi_export_download`` 里做：按 grant 与
  是否遮罩分级，再校验过期时间与 ``Path.resolve().relative_to(export_root)``，
  越界一律 404。此模块只提供 ``artifact_path_for`` 做纯路径校验。

  曾经这里还有一个 ``build_download_path``，无任何调用方，且判定比线上
  路径宽松（任意 grant 即可下载未遮罩导出）。留着就是等人误用，已删除。

CSV 注入处理五种前缀：``=``、``+``、``-``、``@``、制表符、回车符。
遮罩在服务层执行，不在前端执行。
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import hmac
import io
import json
import os
import re
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.abi import (
    CatalogDataset,
    DatasetColumn,
    ExportJob,
)
from data_intelligence_hub.repositories import abi as abi_repo
from data_intelligence_hub.services.abi_query import (
    AbiQueryPlan,
    AbiServiceError,
    mask_row,
    normalize_filters,
    prepare_query,
    require_dataset_access,
)

# ---------------------------------------------------------------- 常量

EXPORT_TTL_DAYS: Final[int] = 7
EXPORT_FORMATS: Final[frozenset[str]] = frozenset({"csv", "xlsx", "jsonl"})
UNMASKED_REASON_MIN_CHARS: Final[int] = 10
CSV_INJECTION_PREFIXES: Final[tuple[str, ...]] = ("=", "+", "-", "@", "\t", "\r")
CSV_FLUSH_BYTES: Final[int] = 64 * 1024

# 单次导出的硬上限。``prepare_query(limit=None)`` 会生成无行数约束的
# SELECT，导出因此可以拉走整张表——同步创建路径有 ``_EXPORT_MAX_ROWS``
# 拦着，但执行侧从来没有。worker 捡起任何 job 都会照单全收。
MAX_EXPORT_ROWS: Final[int] = 50_000

CONTENT_TYPES: Final[dict[str, str]] = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "jsonl": "application/x-ndjson; charset=utf-8",
}

_FILENAME_UNSAFE_RE: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9_.-]+")
_SLUG_MAX_CHARS: Final[int] = 80


# ---------------------------------------------------------------- 领域异常


class AbiExportError(AbiServiceError):
    """导出服务错误基类。"""

    code = "abi_export_error"
    status_code = 400


class AbiExportNotFound(AbiExportError):
    code = "abi_export_not_found"
    status_code = 404


class AbiExportValidationError(AbiExportError):
    code = "abi_export_invalid"
    status_code = 400


class AbiExportNotReady(AbiExportError):
    code = "abi_export_not_ready"
    status_code = 409


class AbiExportExpired(AbiExportError):
    code = "abi_export_expired"
    status_code = 410


class AbiExportApprovalError(AbiExportError):
    code = "abi_export_approval_invalid"
    status_code = 403


# ---------------------------------------------------------------- 路径


def export_root() -> Path:
    """ABI 导出根目录。上传与导出共用同一个可配置根。"""

    settings = get_settings()
    configured = getattr(settings, "abi_export_dir", None) or "tmp/abi-exports"
    root = Path(configured).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _resolve_under(root: Path, candidate: Path) -> Path:
    # macOS 的 /var -> /private/var 这类符号链接要求两边都 resolve，
    # 否则 same-path 检查会误判越界。
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise AbiExportNotFound("abi_export_artifact_outside_root") from exc
    return resolved


def artifact_path_for(job: ExportJob, *, export_root_path: Path | None = None) -> Path:
    """校验 job.artifact_path 在导出根内，并返回解析后的绝对路径。

    这是纯路径校验，不做授权。授权由
    ``abi_service.get_abi_export_download`` 负责。
    """

    if not job.artifact_path:
        raise AbiExportNotFound("abi_export_artifact_missing")
    root = (export_root_path or export_root()).resolve()
    path = _resolve_under(root, Path(job.artifact_path))
    if not path.is_file():
        raise AbiExportNotFound("abi_export_artifact_missing")
    return path


def _artifact_path(job: ExportJob, filename: str) -> Path:
    root = export_root()
    directory = _resolve_under(root, root / job.id.hex)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return _resolve_under(root, directory / filename)


def _safe_slug(dataset: CatalogDataset) -> str:
    slug = _FILENAME_UNSAFE_RE.sub("_", dataset.slug).strip("._") or "dataset"
    return slug[: _SLUG_MAX_CHARS]


def _export_filename(job: ExportJob, dataset: CatalogDataset) -> str:
    suffix = "jsonl" if job.format == "jsonl" else job.format
    return f"abi_{_safe_slug(dataset)}_{job.id.hex[:8]}.{suffix}"


# ---------------------------------------------------------------- 指纹


def _hmac_key() -> bytes:
    secret = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, b"abi.export.filters.v1", hashlib.sha256).digest()


def filters_hmac(filters_payload: object) -> bytes:
    """对过滤条件做 HMAC，而不是裸哈希。

    邮箱、handle 这类低熵值可以被字典反查；裸 sha256 等于把过滤值
    以可枚举的形式留在导出作业表里。
    """

    raw = json.dumps(
        filters_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hmac.new(_hmac_key(), raw, hashlib.sha256).digest()


# ---------------------------------------------------------------- 创建作业


def _serialize_filters(filters: Sequence[object] | None) -> list[dict[str, object]]:
    """校验并序列化过滤条件。只存结构化条件，不存 SQL 片段。"""

    normalized = normalize_filters(filters)
    return [
        {
            "column": item.column,
            "op": item.op,
            "value": _json_safe_value(item.value),
        }
        for item in normalized
    ]


def _json_safe_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_value(item) for key, item in value.items()
        }
    if isinstance(value, (set, frozenset)):
        return [
            _json_safe_value(item) for item in sorted(value, key=repr)
        ]
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _validate_reason(reason: str | None) -> str:
    text_value = (reason or "").strip()
    if len(text_value) < UNMASKED_REASON_MIN_CHARS:
        raise AbiExportApprovalError("abi_export_reason_too_short")
    return text_value


async def _validate_columns(
    session: AsyncSession,
    *,
    dataset: CatalogDataset,
    columns: Sequence[str] | None,
) -> tuple[str, ...]:
    rows = (
        await session.scalars(
            select(DatasetColumn)
            .where(DatasetColumn.dataset_id == dataset.id)
            .order_by(DatasetColumn.ordinal, DatasetColumn.column_name)
        )
    ).all()
    if not rows:
        raise AbiExportValidationError("abi_export_dataset_has_no_columns")
    available = [row.column_name for row in rows]
    requested_input = [columns] if isinstance(columns, str) else columns
    if not requested_input:
        return tuple(available)
    requested: list[str] = []
    for name in requested_input:
        if not isinstance(name, str) or name not in available:
            raise AbiExportValidationError("abi_export_column_not_registered")
        if name not in requested:
            requested.append(name)
    if not requested:
        raise AbiExportValidationError("abi_export_columns_empty")
    return tuple(requested)


async def create_job(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    export_format: str = "csv",
    columns: Sequence[str] | None = None,
    filters: Sequence[object] | None = None,
    mask_pii: bool = True,
    reason: str | None = None,
    approved_by: uuid.UUID | None = None,
    **options: object,
) -> ExportJob:
    """创建导出作业。

    默认 ``mask_pii=True``。关闭遮罩时：

    - 申请人必须有 publisher grant；
    - ``reason`` 去掉首尾空白后至少 10 个字；
    - ``approved_by`` 不能等于申请人；未给审批人时作业停在
      ``awaiting_approval``，由 ``approve_job`` 推进。
    """

    # 兼容 ``create_job(..., format="csv")`` 的写法。format 是内置名，
    # 用 **options 接收，避免把内置名当参数名。
    format_alias = options.pop("format", None)
    if format_alias is not None:
        if export_format not in {"", "csv"}:
            raise AbiExportValidationError("abi_export_format_conflict")
        export_format = str(format_alias)
    if options:
        unexpected = ", ".join(sorted(options))
        raise TypeError(f"unexpected keyword arguments: {unexpected}")

    normalized_format = (export_format or "").strip().lower()
    if normalized_format not in EXPORT_FORMATS:
        raise AbiExportValidationError("abi_export_format_invalid")

    session.sync_session.expire_on_commit = False
    reason_text: str | None

    min_role = "viewer" if mask_pii else "publisher"
    dataset, _grant = await require_dataset_access(
        session,
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        user_id=user_id,
        min_role=min_role,
    )
    resolved_columns = await _validate_columns(
        session,
        dataset=dataset,
        columns=columns,
    )
    serialized_filters = _serialize_filters(filters)

    if not mask_pii:
        reason_text = _validate_reason(reason)
        if approved_by is not None:
            if approved_by == user_id:
                raise AbiExportApprovalError("abi_export_self_approval_denied")
            # 审批人必须在同一个数据集上有 publisher grant。
            await require_dataset_access(
                session,
                dataset_id=dataset_id,
                workspace_id=workspace_id,
                user_id=approved_by,
                min_role="publisher",
            )
        status = "queued" if approved_by is not None else "awaiting_approval"
    else:
        reason_text = reason
        approved_by = None
        status = "queued"

    now = datetime.now(UTC)
    job = ExportJob(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        dataset_id=dataset.id,
        created_by=user_id,
        format=normalized_format,
        mask_pii=mask_pii,
        filters=cast("dict[str, Any] | None", serialized_filters),
        filters_hmac=filters_hmac(serialized_filters),
        columns=list(resolved_columns),
        reason=reason_text,
        status=status,
        approved_by=approved_by,
        approved_at=now if approved_by is not None else None,
        expires_at=now + timedelta(days=EXPORT_TTL_DAYS),
    )
    session.add(job)
    await session.flush()
    await session.commit()
    return job


async def approve_job(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    workspace_id: uuid.UUID,
    approver_id: uuid.UUID,
) -> ExportJob:
    """审批一个关闭遮罩的导出作业。

    审批人必须有 publisher grant，且不能是申请人。单人自批只是自证，
    不是控制。
    """

    job = await session.scalar(
        select(ExportJob)
        .where(
            ExportJob.workspace_id == workspace_id,
            ExportJob.id == job_id,
        )
        .with_for_update()
    )
    if job is None:
        raise AbiExportNotFound()
    session.sync_session.expire_on_commit = False
    if job.mask_pii:
        await session.rollback()
        raise AbiExportApprovalError("abi_export_approval_not_required")
    if job.status != "awaiting_approval":
        await session.rollback()
        raise AbiExportNotReady("abi_export_not_awaiting_approval")
    if approver_id == job.created_by:
        await session.rollback()
        raise AbiExportApprovalError("abi_export_self_approval_denied")
    try:
        await require_dataset_access(
            session,
            dataset_id=job.dataset_id,
            workspace_id=workspace_id,
            user_id=approver_id,
            min_role="publisher",
        )
    except BaseException:
        await session.rollback()
        raise
    job.approved_by = approver_id
    job.approved_at = datetime.now(UTC)
    job.status = "queued"
    await session.commit()
    return job


# ---------------------------------------------------------------- 生成文件


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def sanitize_csv_cell(value: object) -> str:
    """转义 CSV 注入前缀。

    五种前缀都要处理：``=`` ``+`` ``-`` ``@`` 制表符 回车符。
    以单引号开头会让 Excel 把单元格当文本，而不是公式。
    """

    text_value = _cell_text(value)
    # BOM 可能被表格软件忽略；检测时先剥掉，防止 "﻿=..." 绕过。
    probe = text_value.lstrip("\ufeff")
    if probe and probe[0] in CSV_INJECTION_PREFIXES:
        return "'" + text_value
    return text_value


def _xlsx_cell(value: object) -> object:
    if isinstance(value, str):
        # xlsx 同样会被表格软件当公式解释，沿用与 CSV 相同的注入前缀处理。
        return sanitize_csv_cell(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, Decimal):
        # openpyxl 不保证 Decimal 精度，按文本写出。
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return value


async def _write_csv(
    path: Path,
    *,
    columns: Sequence[str],
    rows: AsyncIterator[Mapping[str, object]],
) -> int:
    """用 csv.DictWriter + io.StringIO 写 CSV。"""

    count = 0
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(columns),
        extrasaction="ignore",
        lineterminator="\r\n",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        # 表头也是单元格，同样处理注入前缀。
        writer.writerow(
            {column: sanitize_csv_cell(column) for column in columns}
        )
        _flush_text_buffer(handle, buffer)
        async for row in rows:
            writer.writerow(
                {column: sanitize_csv_cell(row.get(column)) for column in columns}
            )
            count += 1
            if buffer.tell() >= CSV_FLUSH_BYTES:
                _flush_text_buffer(handle, buffer)
        _flush_text_buffer(handle, buffer)
    return count


def _flush_text_buffer(handle: Any, buffer: io.StringIO) -> None:
    handle.write(buffer.getvalue())
    buffer.seek(0)
    buffer.truncate(0)


async def _write_jsonl(
    path: Path,
    *,
    columns: Sequence[str],
    rows: AsyncIterator[Mapping[str, object]],
) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        async for row in rows:
            payload = {column: row.get(column) for column in columns}
            handle.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=_json_default,
                )
            )
            handle.write("\n")
            count += 1
    return count


def _json_default(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return str(value)


async def _write_xlsx(
    path: Path,
    *,
    columns: Sequence[str],
    rows: AsyncIterator[Mapping[str, object]],
) -> int:
    """openpyxl 惰性导入，只用 write_only 模式。

    不使用 xlsxwriter：项目依赖里只有 openpyxl。
    """

    from openpyxl import Workbook  # type: ignore[import-untyped]

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("data")
    sheet.append([_xlsx_cell(column) for column in columns])
    count = 0
    async for row in rows:
        sheet.append([_xlsx_cell(row.get(column)) for column in columns])
        count += 1
    await asyncio.to_thread(workbook.save, path)
    return count


async def _iter_masked_rows(
    session: AsyncSession,
    plan: AbiQueryPlan,
    *,
    mask_pii: bool,
    max_rows: int | None = None,
) -> AsyncGenerator[dict[str, object], None]:
    """按计划流式读取行并按需遮罩。

    查询在调用方事务内执行；导出作业持有 FOR UPDATE 锁，保证同一作业
    不会被两个 worker 同时写。
    """

    result = await session.stream(plan.statement)
    emitted = 0
    try:
        async for row in result:
            emitted += 1
            if max_rows is not None and emitted > max_rows:
                # 超限就明确失败，不产出部分文件。静默截断的导出看起来完整，
                # 用户会拿它当全量做判断。``prepare_query`` 的分页上限
                # （MAX_PAGE_SIZE）远小于导出的行数预算，所以行数控制只能
                # 在这里做，不能靠 SELECT LIMIT。
                raise AbiExportValidationError("abi_export_row_limit_exceeded")
            mapping = row._mapping
            raw = {column: mapping[column] for column in plan.columns}
            if mask_pii:
                yield mask_row(raw, plan.pii_classes, plan.mask_rules)
            else:
                yield raw
    finally:
        await result.close()


async def _mark_failed(
    session: AsyncSession,
    job_id: uuid.UUID,
    error_code: str,
) -> None:
    await session.execute(
        update(ExportJob)
        .where(ExportJob.id == job_id)
        .values(
            status="failed",
            error=error_code[:1000],
            finished_at=datetime.now(UTC),
        )
    )
    await session.commit()


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, AbiServiceError):
        return exc.code
    return "abi_export_failed"


async def run_job(
    session: AsyncSession,
    job_id: uuid.UUID,
) -> ExportJob:
    """执行一个已排队的导出作业。

    作业状态机：queued → running → succeeded / failed。已成功的作业重复
    调用直接返回，不重复生成文件。
    """

    job = await session.scalar(
        select(ExportJob).where(ExportJob.id == job_id).with_for_update()
    )
    if job is None:
        raise AbiExportNotFound()
    session.sync_session.expire_on_commit = False
    if job.status == "succeeded":
        await session.commit()
        return job
    if job.status == "expired":
        await session.rollback()
        raise AbiExportExpired()
    if job.status != "queued":
        await session.rollback()
        raise AbiExportNotReady("abi_export_not_queued")
    now = datetime.now(UTC)
    if job.expires_at is None:
        job.expires_at = now + timedelta(days=EXPORT_TTL_DAYS)
    elif _ensure_aware(job.expires_at) <= now:
        job.status = "expired"
        await session.commit()
        raise AbiExportExpired()
    if not job.mask_pii:
        if job.approved_by is None:
            await session.rollback()
            raise AbiExportApprovalError("abi_export_approval_required")
        if job.approved_by == job.created_by:
            await session.rollback()
            raise AbiExportApprovalError("abi_export_self_approval_denied")

    min_role = "viewer" if job.mask_pii else "publisher"
    try:
        dataset, _grant = await require_dataset_access(
            session,
            dataset_id=job.dataset_id,
            workspace_id=job.workspace_id,
            user_id=job.created_by,
            min_role=min_role,
        )
    except BaseException:
        await session.rollback()
        raise

    # 执行侧也要读策略。此前只有创建路径读，worker 捡起 job 后完全不看：
    # allowed_formats 与 max_rows_masked 在 queued→running 阶段失效，
    # 任何直接写 ExportJob 的路径都能绕过它们。
    #
    # 缺省与表定义一致（require_dual_approval 的 server_default 是 true），
    # 但这里执行的是格式与行数两条，缺省分别是「不限制」——所以只在
    # policy 存在时收紧，不凭空造限制。
    policy = await abi_repo.get_export_policy(session, job.workspace_id, job.dataset_id)
    if (
        policy is not None
        and policy.allowed_formats is not None
        and job.format not in policy.allowed_formats
    ):
        await session.rollback()
        raise AbiExportValidationError("abi_export_format_not_allowed")

    row_limit = MAX_EXPORT_ROWS
    if (
        job.mask_pii
        and policy is not None
        and policy.max_rows_masked is not None
    ):
        row_limit = min(row_limit, policy.max_rows_masked)

    job.status = "running"
    job.started_at = datetime.now(UTC)
    job.error = None
    await session.flush()

    filename = _export_filename(job, dataset)
    artifact_path: Path | None = None
    temp_path: Path | None = None
    try:
        columns = tuple(job.columns or ())
        plan = await prepare_query(
            session,
            dataset,
            columns=columns or None,
            filters=cast("Sequence[object] | None", job.filters),
            order_by=None,
            order_dir="asc",
            # 行数上限不在这里做：prepare_query 的分页上限是 200，
            # 而导出预算远大于它。由 _iter_masked_rows 计数并中断。
            limit=None,
        )
        # 未分类字段不允许明文导出。
        #
        # ``unknown`` 的意思是「还没判定」，不是「没有 PII」。遮罩导出对它
        # 输出 ``***`` 是安全的；但 ``mask_pii=False`` 的导出会把它原样写出。
        # 同步创建路径有 ``_resolve_selection`` 拦 unknown，worker 路径没有——
        # 任何直接写 ExportJob 的入口都能绕过。
        if not job.mask_pii:
            unknown = sorted(
                name
                for name in plan.columns
                if plan.pii_classes.get(name, "unknown") == "unknown"
            )
            if unknown:
                raise AbiExportValidationError("abi_export_unknown_pii_denied")

        artifact_path = _artifact_path(job, filename)
        temp_path = artifact_path.with_name(artifact_path.name + ".tmp")
        rows = _iter_masked_rows(
            session, plan, mask_pii=job.mask_pii, max_rows=row_limit
        )
        try:
            if job.format == "csv":
                rows_total = await _write_csv(
                    temp_path, columns=plan.columns, rows=rows
                )
            elif job.format == "xlsx":
                rows_total = await _write_xlsx(
                    temp_path, columns=plan.columns, rows=rows
                )
            else:
                rows_total = await _write_jsonl(
                    temp_path, columns=plan.columns, rows=rows
                )
        finally:
            # 关闭服务端游标，避免异常路径把连接留在 streaming 状态。
            with contextlib.suppress(Exception):
                await rows.aclose()

        os.replace(temp_path, artifact_path)
        now = datetime.now(UTC)
        job.status = "succeeded"
        job.artifact_path = str(artifact_path)
        job.filename = filename
        job.content_type = CONTENT_TYPES[job.format]
        job.bytes_total = artifact_path.stat().st_size
        job.rows_total = rows_total
        job.finished_at = now
        job.expires_at = now + timedelta(days=EXPORT_TTL_DAYS)
        job.error = None
        await session.commit()
        return job
    except BaseException as exc:
        await session.rollback()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        try:
            await _mark_failed(session, job_id, _error_code(exc))
        except Exception:
            await session.rollback()
        if isinstance(exc, AbiServiceError):
            raise
        raise AbiExportError("abi_export_run_failed") from exc


# ---------------------------------------------------------------- 下载


__all__ = [
    "AbiExportApprovalError",
    "AbiExportError",
    "AbiExportExpired",
    "AbiExportNotFound",
    "AbiExportNotReady",
    "AbiExportValidationError",
    "CSV_INJECTION_PREFIXES",
    "EXPORT_FORMATS",
    "approve_job",
    "artifact_path_for",
    "create_job",
    "export_root",
    "filters_hmac",
    "run_job",
    "sanitize_csv_cell",
]

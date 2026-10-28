"""ABI 上传服务。

上传分三步：``create_batch`` → ``append_content`` → ``commit_batch``。

关键约束：

- 文件流式写入 ``settings.abi_export_dir/_uploads/{batch_id}/``，边写边算
  sha256，不把 200MB 读进内存。
- 单批上限 200MB / 500,000 行。超限立即失败，不落半批数据。
- commit 复核 sha256 与行数，不一致直接拒绝。
- 表头必须与 ``abi.dataset_column`` 对齐；类型、主键重复、PII 逐行校验。
  命中信用卡或私钥的行拒收。``abi.upload_error`` 只存定位信息，
  **绝不存原始值**。
- ``replace`` 写新版本并切 ``abi.catalog_dataset.version``，旧版本行保留，
  可以按版本回切。``replace`` 需要 publisher。
- 迁移没有通用上传行表。首次 commit 按数据集 UUID 在 ``raw`` 建
  ``abi_upload_<uuid>``，行带 ``__abi_version`` / ``__abi_row`` /
  ``__abi_batch_id``。批次 id 只用于失败清理，查询按 version 过滤。
- 每 10,000 行一批事务。50 万行单事务会在共享 OLTP 库上产生长事务与 WAL 尖峰。
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import re
import secrets
import uuid
from collections.abc import AsyncIterable, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
    delete,
    func,
    insert,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql import quoted_name

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.abi import (
    CatalogDataset,
    DatasetColumn,
    UploadBatch,
    UploadError,
)
from data_intelligence_hub.services.abi_query import (
    LOCAL_TABLE_COLUMNS,
    LOCAL_TABLE_PRIMARY_KEYS,
    AbiServiceError,
    load_dataset_columns,
    require_dataset_access,
)

# ---------------------------------------------------------------- 常量

MAX_UPLOAD_BYTES: Final[int] = 200 * 1024 * 1024
MAX_UPLOAD_ROWS: Final[int] = 500_000
UPLOAD_BATCH_ROWS: Final[int] = 10_000
UPLOAD_TOKEN_TTL_SECONDS: Final[int] = 3600
# PostgreSQL 单条语句的绑定参数上限是 65535。留出余量，按行宽切 INSERT。
MAX_BIND_PARAMETERS: Final[int] = 60_000
MAX_ERROR_ROWS_PER_INSERT: Final[int] = 2_000
UPLOAD_MODES: Final[frozenset[str]] = frozenset({"append", "upsert", "replace"})
UPLOAD_SOURCE_KINDS: Final[frozenset[str]] = frozenset({"upload", "local_table"})
UPLOAD_TABLE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^abi_upload_[0-9a-f]{32}$")
# 物化表建在 raw schema（见 _build_upload_table 的 schema="raw"）。
# dataset.source_table 必须写成两段式 "raw.abi_upload_<hex>"：
# 查询侧的 _parse_source_table 只接受 schema.table，单段名会被判
# source_table_invalid。两者一度不一致，导致 commit 成功但查询 400。
_UPLOAD_TABLE_SCHEMA: Final[str] = "raw"
UPLOAD_INTERNAL_PREFIX: Final[str] = "__"
_UPLOAD_DIR_NAME: Final[str] = "_uploads"

_LOCAL_PROVENANCE_COLUMNS: Final[frozenset[str]] = frozenset(
    {"origin", "load_batch_id", "src_file", "src_row_ordinal", "content_hash", "loaded_at"}
)

# 上传表内部列。与 abi_query 的 UPLOAD_INTERNAL_COLUMNS 保持一致。
_UPLOAD_VERSION_COLUMN: Final[str] = "__abi_version"
_UPLOAD_ROW_COLUMN: Final[str] = "__abi_row"
_UPLOAD_BATCH_COLUMN: Final[str] = "__abi_batch_id"
_UPLOAD_HASH_COLUMN: Final[str] = "__abi_content_hash"

_DATA_TYPE_ALIASES: Final[dict[str, str]] = {
    "text": "text",
    "string": "text",
    "str": "text",
    "varchar": "text",
    "char": "text",
    "integer": "integer",
    "int": "integer",
    "int4": "integer",
    "smallint": "integer",
    "bigint": "bigint",
    "int8": "bigint",
    "long": "bigint",
    "numeric": "numeric",
    "decimal": "numeric",
    "number": "numeric",
    "float": "numeric",
    "double": "numeric",
    "real": "numeric",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "timestamp": "timestamp",
    "datetime": "timestamp",
    "timestamptz": "timestamp",
    "uuid": "uuid",
    "json": "json",
    "jsonb": "json",
    "object": "json",
    "array": "array",
    "list": "array",
    "text[]": "array",
}

_PRIVATE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----"
)
_CARD_CANDIDATE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)(?:\d[ -]?){12,19}\d(?!\d)"
)


# ---------------------------------------------------------------- 领域异常


class AbiUploadError(AbiServiceError):
    """上传服务错误基类。"""

    code = "abi_upload_error"
    status_code = 400


class AbiUploadNotFound(AbiUploadError):
    code = "abi_upload_batch_not_found"
    status_code = 404


class AbiUploadTokenError(AbiUploadError):
    code = "abi_upload_token_invalid"
    status_code = 403


class AbiUploadStateError(AbiUploadError):
    code = "abi_upload_state_invalid"
    status_code = 409


class AbiUploadLimitExceeded(AbiUploadError):
    code = "abi_upload_limit_exceeded"
    status_code = 413


class AbiUploadChecksumError(AbiUploadError):
    code = "abi_upload_checksum_mismatch"
    status_code = 422


class AbiUploadSchemaError(AbiUploadError):
    code = "abi_upload_schema_mismatch"
    status_code = 422


class AbiUploadValidationError(AbiUploadError):
    code = "abi_upload_validation_failed"
    status_code = 400


# ---------------------------------------------------------------- 路径与令牌


def export_root() -> Path:
    """ABI 导出/上传根目录。上传与导出共用，下载校验也用同一个根。"""

    settings = get_settings()
    configured = getattr(settings, "abi_export_dir", None) or "tmp/abi-exports"
    root = Path(configured).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _upload_root() -> Path:
    root = export_root()
    # _uploads 必须是 export_root 内的真实路径；符号链接指向外部就拒绝。
    return _resolve_under(root, root / _UPLOAD_DIR_NAME)


def _resolve_under(root: Path, candidate: Path) -> Path:
    """越界即拒绝。Path.resolve() 会折叠 ``..`` 与符号链接。"""

    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise AbiUploadValidationError("abi_upload_path_outside_root") from exc
    return resolved


def _safe_filename(filename: str) -> str:
    candidate = filename.strip()
    if (
        not candidate
        or candidate in {".", ".."}
        or "/" in candidate
        or "\\" in candidate
        or "\x00" in candidate
        or any(ord(char) < 32 for char in candidate)
        or len(candidate) > 255
    ):
        raise AbiUploadValidationError("abi_upload_filename_invalid")
    name = Path(candidate).name
    if name in {"", ".", ".."}:
        raise AbiUploadValidationError("abi_upload_filename_invalid")
    return name


def _bare_source_table(value: str) -> str:
    """把 ``raw.foo`` 归一成 ``foo``。其他 schema 或带点的表名一律无效。"""

    text_value = (value or "").strip()
    if text_value.startswith("raw."):
        return text_value[4:]
    if "." in text_value:
        return ""
    return text_value


def _batch_dir(batch_id: uuid.UUID) -> Path:
    return _resolve_under(_upload_root(), _upload_root() / str(batch_id))


def _batch_storage_path(batch: UploadBatch) -> Path:
    if not batch.storage_path:
        raise AbiUploadStateError("abi_upload_storage_path_missing")
    batch_root = _batch_dir(batch.id)
    return _resolve_under(batch_root, Path(batch.storage_path))


def _token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _now() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _require_token(batch: UploadBatch, token: str) -> None:
    if not token or batch.upload_token_hash is None:
        raise AbiUploadTokenError()
    if not secrets.compare_digest(_token_digest(token), batch.upload_token_hash):
        raise AbiUploadTokenError()
    if batch.token_expires_at is None or _ensure_aware(batch.token_expires_at) <= _now():
        raise AbiUploadTokenError("abi_upload_token_expired")


def _normalize_sha256(value: str | bytes | bytearray | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        if len(raw) != 32:
            raise AbiUploadValidationError("abi_upload_sha256_invalid")
        return raw
    text_value = value.strip().lower()
    if text_value.startswith("sha256:"):
        text_value = text_value[7:]
    if len(text_value) != 64:
        raise AbiUploadValidationError("abi_upload_sha256_invalid")
    try:
        return bytes.fromhex(text_value)
    except ValueError as exc:
        raise AbiUploadValidationError("abi_upload_sha256_invalid") from exc


# ---------------------------------------------------------------- 行计数


class _CsvRowCounter:
    """流式统计 CSV 逻辑行数。

    只跟踪引号状态，不在内存里保留整行。``""`` 会连续翻转两次，
    因此引号内的逗号、换行不会被误计。
    """

    __slots__ = ("in_quotes", "last_byte", "rows")

    def __init__(self) -> None:
        self.in_quotes = False
        self.last_byte = -1
        self.rows = 0

    def feed(self, chunk: bytes) -> None:
        for byte in chunk:
            if byte == 0x22:  # "
                self.in_quotes = not self.in_quotes
            elif byte == 0x0A and not self.in_quotes:  # \n
                self.rows += 1
            self.last_byte = byte

    def finish(self) -> int:
        if self.last_byte != -1 and self.last_byte != 0x0A and not self.in_quotes:
            self.rows += 1
        return self.rows


# ---------------------------------------------------------------- 创建批次


async def create_batch(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    mode: str = "append",
    expected_sha256: str | bytes | bytearray | None = None,
    expected_rows: int | None = None,
    token_ttl_seconds: int = UPLOAD_TOKEN_TTL_SECONDS,
) -> tuple[UploadBatch, str]:
    """创建上传批次并返回一次性 token。

    token 只在本函数返回时出现一次。库里存 sha256 摘要。
    """

    session.sync_session.expire_on_commit = False
    normalized_mode = mode.strip().lower()
    if normalized_mode not in UPLOAD_MODES:
        raise AbiUploadValidationError("abi_upload_mode_invalid")
    if expected_rows is not None and expected_rows < 0:
        raise AbiUploadValidationError("abi_upload_expected_rows_invalid")
    if token_ttl_seconds < 60 or token_ttl_seconds > 24 * 3600:
        raise AbiUploadValidationError("abi_upload_token_ttl_invalid")

    min_role = "publisher" if normalized_mode == "replace" else "editor"
    dataset, _grant = await require_dataset_access(
        session,
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        user_id=user_id,
        min_role=min_role,
    )
    if dataset.source_kind not in UPLOAD_SOURCE_KINDS:
        raise AbiUploadValidationError("abi_upload_source_kind_unsupported")
    if normalized_mode == "replace" and dataset.source_kind != "upload":
        # 固定本地表的行没有版本列，无法保留旧版本。
        raise AbiUploadValidationError("abi_upload_replace_requires_upload_dataset")

    source_table = _bare_source_table(dataset.source_table or "")
    if dataset.source_kind == "upload":
        expected_table = f"abi_upload_{dataset.id.hex}"
        if source_table and source_table != expected_table:
            raise AbiUploadValidationError("abi_upload_source_table_invalid")
        # 带 schema 前缀：表建在 raw，查询侧按 schema.table 解析。
        dataset.source_table = f"{_UPLOAD_TABLE_SCHEMA}.{expected_table}"
    else:
        if source_table not in LOCAL_TABLE_COLUMNS:
            raise AbiUploadValidationError("abi_upload_source_table_not_allowed")
        if not dataset.origin:
            # 本地 raw 表没有 workspace_id，origin 是唯一来源隔离键。
            raise AbiUploadValidationError("abi_upload_dataset_origin_required")
        dataset.source_table = source_table

    safe_name = _safe_filename(filename)
    batch_id = uuid.uuid4()
    storage_path = _batch_dir(batch_id) / safe_name
    token = secrets.token_urlsafe(32)
    batch = UploadBatch(
        id=batch_id,
        dataset_id=dataset.id,
        workspace_id=dataset.workspace_id,
        uploaded_by=user_id,
        filename=safe_name,
        mode=normalized_mode,
        expected_sha256=_normalize_sha256(expected_sha256),
        expected_rows=expected_rows,
        bytes_total=0,
        status="pending",
        storage_path=str(storage_path),
        upload_token_hash=_token_digest(token),
        token_expires_at=_now() + timedelta(seconds=token_ttl_seconds),
        rows_loaded=0,
        rows_rejected=0,
    )
    session.add(batch)
    await session.flush()
    await session.commit()
    return batch, token


# ---------------------------------------------------------------- 写入内容


async def _write_chunks(
    handle: Any,
    chunks: Iterable[bytes] | AsyncIterable[bytes],
    counter: _CsvRowCounter,
) -> tuple[int, str]:
    """流式写文件，同时统计字节数、行数与 sha256。"""

    digest = hashlib.sha256()
    total = 0
    if isinstance(chunks, AsyncIterable):
        async for chunk in chunks:
            data = _as_bytes(chunk)
            total = _check_size(total, data)
            digest.update(data)
            counter.feed(data)
            _check_rows(counter)
            await asyncio.to_thread(handle.write, data)
    else:
        for chunk in chunks:
            data = _as_bytes(chunk)
            total = _check_size(total, data)
            digest.update(data)
            counter.feed(data)
            _check_rows(counter)
            await asyncio.to_thread(handle.write, data)
    return total, digest.hexdigest()


def _check_rows(counter: _CsvRowCounter) -> None:
    if counter.rows > MAX_UPLOAD_ROWS + 1:
        raise AbiUploadLimitExceeded("abi_upload_rows_exceeded")


def _as_bytes(chunk: bytes | bytearray | memoryview) -> bytes:
    if isinstance(chunk, bytes):
        return chunk
    if isinstance(chunk, (bytearray, memoryview)):
        return bytes(chunk)
    raise AbiUploadValidationError("abi_upload_chunk_not_bytes")


def _check_size(current: int, chunk: bytes) -> int:
    total = current + len(chunk)
    if total > MAX_UPLOAD_BYTES:
        raise AbiUploadLimitExceeded("abi_upload_bytes_exceeded")
    return total


def _normalize_chunks(
    chunks: Iterable[bytes] | AsyncIterable[bytes],
) -> Iterable[bytes] | AsyncIterable[bytes]:
    """接受 bytes、文件对象或同步/异步迭代器三种输入。"""

    if isinstance(chunks, (bytes, bytearray, memoryview)):
        return [bytes(chunks)]
    reader = getattr(chunks, "read", None)
    if callable(reader):
        return _sync_file_chunks(chunks)
    if isinstance(chunks, (Iterable, AsyncIterable)):
        return chunks
    raise AbiUploadValidationError("abi_upload_chunks_invalid")


def _sync_file_chunks(handle: Any) -> Iterable[bytes]:
    while True:
        data = handle.read(1024 * 1024)
        if not data:
            return
        yield data


async def append_content(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    token: str | None = None,
    chunks: Iterable[bytes] | AsyncIterable[bytes],
    user_id: uuid.UUID | None = None,
) -> UploadBatch:
    """把请求体流式写入批次目录，并记录 sha256 与行数。

    两种鉴权方式二选一：

    - 给 ``token``：校验一次性上传 token；再给 ``user_id`` 时还要求
      调用者是原上传人且仍有 editor grant。
    - 不给 token：必须给 ``user_id``，按 batch 所属数据集校验 editor grant。

    同一批次只能成功写入一次。失败时清理临时文件，批次保持 pending。
    """

    batch = await session.scalar(
        select(UploadBatch)
        .where(UploadBatch.id == batch_id)
        .with_for_update()
    )
    if batch is None:
        raise AbiUploadNotFound()
    if token is not None:
        _require_token(batch, token)
    elif user_id is None:
        raise AbiUploadTokenError("abi_upload_token_required")
    if batch.status != "pending":
        raise AbiUploadStateError("abi_upload_content_already_written")
    if user_id is not None:
        if user_id != batch.uploaded_by:
            raise AbiUploadTokenError("abi_upload_token_user_mismatch")
        await require_dataset_access(
            session,
            dataset_id=batch.dataset_id,
            workspace_id=batch.workspace_id,
            user_id=user_id,
            min_role="editor",
        )
    session.sync_session.expire_on_commit = False

    final_path = _batch_storage_path(batch)
    final_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp_path = final_path.with_name(final_path.name + ".part")
    _resolve_under(export_root(), temp_path)
    chunk_stream = _normalize_chunks(chunks)

    counter = _CsvRowCounter()
    try:
        with temp_path.open("wb") as handle:
            total, digest_hex = await _write_chunks(handle, chunk_stream, counter)
        rows = counter.finish()
        if counter.in_quotes:
            raise AbiUploadSchemaError("abi_upload_csv_unterminated_quote")
        if rows > MAX_UPLOAD_ROWS + 1:
            raise AbiUploadLimitExceeded("abi_upload_rows_exceeded")
        os.replace(temp_path, final_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    batch.actual_sha256 = bytes.fromhex(digest_hex)
    batch.bytes_total = total
    batch.actual_rows = max(rows - 1, 0)
    batch.status = "uploaded"
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        final_path.unlink(missing_ok=True)
        raise AbiUploadStateError("abi_upload_duplicate_content") from exc
    return batch


# ---------------------------------------------------------------- PII 扫描


def _luhn_valid(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = ord(char) - 48
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _contains_credit_card(text: str) -> bool:
    for match in _CARD_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            return True
    return False


def scan_pii(value: object) -> str | None:
    """返回命中的 PII 规则名，未命中返回 None。

    只检测两类明确禁止入库的内容：信用卡号与私钥。邮箱、handle 等
    不在这里拒收，它们由 field_policy 遮罩。
    """

    if value is None:
        return None
    if isinstance(value, str):
        text_value = value
    elif isinstance(value, bytes):
        text_value = value.decode("utf-8", "ignore")
    elif isinstance(value, (dict, list, tuple)):
        text_value = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text_value = str(value)
    if _PRIVATE_KEY_RE.search(text_value):
        return "pii_private_key"
    if _contains_credit_card(text_value):
        return "pii_credit_card"
    return None


# ---------------------------------------------------------------- 类型与行校验


def _canonical_type(data_type: str | None) -> str:
    if not data_type:
        return "text"
    return _DATA_TYPE_ALIASES.get(data_type.strip().lower(), "text")


def _coerce_upload_value(raw: str, column: DatasetColumn) -> object:
    """把 CSV 文本转成列类型。转换失败只报规则，不回显值。"""

    canonical = _canonical_type(column.data_type)
    if raw == "":
        return None
    try:
        if canonical == "integer":
            return int(raw)
        if canonical == "bigint":
            return int(raw)
        if canonical == "numeric":
            return Decimal(raw)
        if canonical == "boolean":
            lowered = raw.strip().lower()
            if lowered in {"true", "t", "1", "yes", "y"}:
                return True
            if lowered in {"false", "f", "0", "no", "n"}:
                return False
            raise ValueError
        if canonical == "date":
            return date.fromisoformat(raw.strip())
        if canonical == "timestamp":
            normalized = raw.strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return datetime.fromisoformat(normalized)
        if canonical == "uuid":
            return uuid.UUID(raw.strip())
        if canonical == "array":
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError
            return parsed
        if canonical == "json":
            return json.loads(raw)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AbiUploadValidationError("abi_upload_value_type_invalid") from exc
    return raw


def _validate_row(
    *,
    raw_values: dict[str, str],
    columns: Sequence[DatasetColumn],
) -> tuple[dict[str, object] | None, list[tuple[str | None, str, str]]]:
    """校验一行并转成可插入的字典。

    返回 ``(values, errors)``。errors 的每项是
    ``(column_name, rule_id, message)``，message 不含原始值。
    """

    errors: list[tuple[str | None, str, str]] = []
    values: dict[str, object] = {}
    for column in columns:
        name = column.column_name
        raw = raw_values.get(name, "")
        if "\x00" in raw:
            errors.append((name, "invalid_null_byte", "值含 NUL 字节，PostgreSQL 拒绝"))
            continue
        rule = scan_pii(raw)
        if rule is not None:
            errors.append((name, rule, "命中禁止入库的 PII 规则"))
            continue
        try:
            value = _coerce_upload_value(raw, column)
        except AbiUploadValidationError:
            errors.append((name, "invalid_type", "值无法转换为声明类型"))
            continue
        if value is None and not column.nullable:
            errors.append((name, "required", "非空列缺少值"))
            continue
        values[name] = value
    if errors:
        return None, errors
    return values, []


def _row_content_hash(values: dict[str, object]) -> bytes:
    payload = json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


# ---------------------------------------------------------------- 物理表


def _pg_type(data_type: str) -> Any:
    raw = (data_type or "").strip().lower()
    if raw in {"float", "double", "real", "double precision"}:
        return Float()
    if raw in {"array", "list", "text[]"}:
        return ARRAY(Text())
    if raw == "jsonb":
        return JSONB()
    if raw in {"json", "object"}:
        # 本地 raw 表里 JSON 与 JSONB 混用；按声明类型区分，
        # 避免把 jsonb 绑定参数写进 json 列。
        return JSON()
    canonical = _canonical_type(data_type)
    if canonical == "integer":
        return Integer()
    if canonical == "bigint":
        return BigInteger()
    if canonical == "numeric":
        return Numeric()
    if canonical == "boolean":
        return Boolean()
    if canonical == "date":
        return Date()
    if canonical == "timestamp":
        return DateTime(timezone=True)
    if canonical == "uuid":
        return Uuid(as_uuid=True)
    if canonical == "json":
        return JSONB()
    return Text()


def _upload_table_name(dataset: CatalogDataset) -> str:
    expected_table = f"abi_upload_{dataset.id.hex}"
    source_table = _bare_source_table(dataset.source_table or "")
    if not source_table:
        source_table = expected_table
    if source_table != expected_table or not UPLOAD_TABLE_PATTERN.fullmatch(
        source_table
    ):
        raise AbiUploadValidationError("abi_upload_source_table_invalid")
    # 与 create_batch 同口径：落库值必须带 schema 前缀。
    dataset.source_table = f"{_UPLOAD_TABLE_SCHEMA}.{source_table}"
    return source_table


def _build_upload_table(
    table_name: str, columns: Sequence[DatasetColumn]
) -> Table:
    """按 dataset_column 构造通用上传表定义。

    表名来自数据集 UUID，列名来自已在查询层校验过的 dataset_column。
    两者都用 quoted_name 强制引用，不拼接用户输入。
    """

    metadata = MetaData()
    table_columns: list[Column[Any]] = [
        Column(
            quoted_name(_UPLOAD_VERSION_COLUMN, True),
            Integer,
            nullable=False,
            primary_key=True,
        ),
        Column(
            quoted_name(_UPLOAD_ROW_COLUMN, True),
            BigInteger,
            nullable=False,
            primary_key=True,
        ),
        # 批次 id 用于失败清理。只删本批写入的行，不会误删并发批次。
        Column(
            quoted_name(_UPLOAD_BATCH_COLUMN, True),
            Uuid(as_uuid=True),
            nullable=False,
        ),
    ]
    for column in columns:
        table_columns.append(
            Column(
                quoted_name(column.column_name, True),
                _pg_type(column.data_type),
                nullable=True,
            )
        )
    table_columns.append(
        Column(
            quoted_name(_UPLOAD_HASH_COLUMN, True),
            LargeBinary(32),
            nullable=False,
        )
    )
    return Table(
        quoted_name(table_name, True),
        metadata,
        *table_columns,
        schema="raw",
    )


def _local_table(
    source_table: str, columns: Sequence[DatasetColumn] | None = None
) -> Table:
    """固定本地表的核心表对象。

    已知 dataset_column 类型的列用真实类型，保证 JSON/数组参数按正确
    codec 编码；其余物理列交给数据库推断。
    """

    if source_table not in LOCAL_TABLE_COLUMNS:
        source_table = _bare_source_table(source_table)
    if source_table not in LOCAL_TABLE_COLUMNS:
        raise AbiUploadValidationError("abi_upload_source_table_not_allowed")
    type_by_name = {
        column.column_name: _pg_type(column.data_type)
        for column in columns or ()
        if column.column_name not in _LOCAL_PROVENANCE_COLUMNS
    }
    metadata = MetaData()
    table_columns: list[Column[Any]] = []
    for name in sorted(LOCAL_TABLE_COLUMNS[source_table]):
        column_type = type_by_name.get(name)
        if column_type is None:
            table_columns.append(Column(quoted_name(name, True)))
        else:
            table_columns.append(
                Column(quoted_name(name, True), column_type)
            )
    return Table(
        quoted_name(source_table, True),
        metadata,
        *table_columns,
        schema="raw",
    )


def _primary_key_index_name(table_name: str, pk_names: Sequence[str]) -> str:
    digest = hashlib.sha256(",".join(pk_names).encode("utf-8")).hexdigest()[:8]
    return f"ux_{table_name}_{digest}"


async def _ensure_upload_table(
    session: AsyncSession,
    table: Table,
    pk_names: Sequence[str],
) -> None:
    """建通用上传表与主键唯一索引。表名与列名都已校验。"""

    await session.execute(CreateTable(table, if_not_exists=True))
    index_columns = [
        table.c[quoted_name(_UPLOAD_VERSION_COLUMN, True)],
        *[table.c[quoted_name(name, True)] for name in pk_names],
    ]
    index = Index(
        _primary_key_index_name(table.name, pk_names),
        *index_columns,
        unique=True,
    )
    await session.execute(CreateIndex(index, if_not_exists=True))


async def _next_upload_row(
    session: AsyncSession, table: Table, version: int
) -> int:
    value = await session.scalar(
        select(
            func.coalesce(
                func.max(table.c[quoted_name(_UPLOAD_ROW_COLUMN, True)]),
                -1,
            )
        ).where(
            table.c[quoted_name(_UPLOAD_VERSION_COLUMN, True)] == version
        )
    )
    return int(value or 0) + 1


# ---------------------------------------------------------------- 数据写入


async def _existing_keys(
    session: AsyncSession,
    *,
    table: Table,
    pk_names: Sequence[str],
    version: int | None,
    origin: str | None,
    keys: Sequence[tuple[object, ...]],
) -> set[tuple[object, ...]]:
    """查本批 key 在目标表里是否已存在。分批控制绑定参数数量。"""

    if not keys:
        return set()
    key_columns = [table.c[quoted_name(name, True)] for name in pk_names]
    found: set[tuple[object, ...]] = set()
    unique_keys = list(dict.fromkeys(keys))
    window_size = max(
        1, min(5000, MAX_BIND_PARAMETERS // max(1, len(key_columns)))
    )
    for start in range(0, len(unique_keys), window_size):
        window = unique_keys[start : start + window_size]
        conditions: list[Any] = []
        if version is not None:
            conditions.append(
                table.c[quoted_name(_UPLOAD_VERSION_COLUMN, True)] == version
            )
        if origin is not None and "origin" in table.c:
            conditions.append(table.c[quoted_name("origin", True)] == origin)
        if len(key_columns) == 1:
            statement = select(key_columns[0]).where(
                *conditions,
                key_columns[0].in_([key[0] for key in window]),
            )
        else:
            statement = select(*key_columns).where(
                *conditions,
                tuple_(*key_columns).in_(window),
            )
        rows = (await session.execute(statement)).all()
        for row in rows:
            found.add(tuple(row))
    return found


async def _flush_rows(
    session: AsyncSession,
    *,
    table: Table,
    rows: Sequence[tuple[int, dict[str, object]]],
    mode: str,
    version: int | None,
    origin: str | None,
    pk_names: Sequence[str],
    data_columns: Sequence[str],
) -> tuple[int, list[tuple[int, str, str, str]]]:
    """插入一个 10k 块，返回 (插入行数, 重复主键错误)。

    append 先查重，重复行拒收；upsert 用 ON CONFLICT DO UPDATE；
    replace 已经换了版本，不可能撞旧行。
    """

    if not rows:
        return 0, []
    values = [item for _, item in rows]
    duplicates: list[tuple[int, str, str, str]] = []

    if mode == "append":
        keys = [tuple(item[name] for name in pk_names) for item in values]
        existing = await _existing_keys(
            session,
            table=table,
            pk_names=pk_names,
            version=version,
            origin=origin,
            keys=keys,
        )
        kept_rows: list[tuple[int, dict[str, object]]] = []
        for (row_number, item), key in zip(rows, keys, strict=True):
            if key in existing:
                duplicates.append(
                    (
                        row_number,
                        pk_names[0],
                        "primary_key_duplicate",
                        "主键已存在",
                    )
                )
            else:
                kept_rows.append((row_number, item))
        rows = kept_rows
        values = [item for _, item in rows]
        if not rows:
            return 0, duplicates

    if mode == "upsert":
        update_columns = [
            name for name in data_columns if name not in set(pk_names)
        ]
        conflict_columns: list[Any] = (
            [
                table.c[quoted_name(_UPLOAD_VERSION_COLUMN, True)],
                *[table.c[quoted_name(name, True)] for name in pk_names],
            ]
            if version is not None
            else [table.c[quoted_name(name, True)] for name in pk_names]
        )
        for batch in _value_batches(values):
            statement = pg_insert(table).values(batch)
            if update_columns:
                statement = statement.on_conflict_do_update(
                    index_elements=conflict_columns,
                    set_={
                        quoted_name(name, True): statement.excluded[
                            quoted_name(name, True)
                        ]
                        for name in update_columns
                    },
                )
            else:
                statement = statement.on_conflict_do_nothing(
                    index_elements=conflict_columns
                )
            await session.execute(statement)
    else:
        for batch in _value_batches(values):
            await session.execute(insert(table).values(batch))
    # 行号只用于错误定位，不写进数据表。
    return len(values), duplicates


def _value_batches(
    values: Sequence[dict[str, object]],
) -> list[list[dict[str, object]]]:
    """按绑定参数上限切分 INSERT。

    10k 行 × 几十列会超过 PostgreSQL 的 65535 参数上限。
    事务仍按 10k 行提交，但语句要再切小。
    """

    if not values:
        return []
    width = max(len(item) for item in values)
    rows_per_statement = max(1, MAX_BIND_PARAMETERS // max(1, width))
    return [
        list(values[start : start + rows_per_statement])
        for start in range(0, len(values), rows_per_statement)
    ]


async def _flush_errors(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    errors: Sequence[tuple[int, str | None, str, str]],
) -> None:
    if not errors:
        return
    for start in range(0, len(errors), MAX_ERROR_ROWS_PER_INSERT):
        window = errors[start : start + MAX_ERROR_ROWS_PER_INSERT]
        session.add_all(
            [
                UploadError(
                    id=uuid.uuid4(),
                    batch_id=batch_id,
                    row_number=row_number,
                    column_name=column_name,
                    rule_id=rule_id,
                    message=message,
                )
                for row_number, column_name, rule_id, message in window
            ]
        )
        await session.flush()


# ---------------------------------------------------------------- 提交批次


def _read_header(path: Path, expected_names: Sequence[str]) -> dict[str, int]:
    """读表头并建立名称→列序号映射。允许列顺序不同，但不允许缺失或多余。"""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise AbiUploadSchemaError("abi_upload_csv_unreadable") from exc
    if header is None:
        raise AbiUploadSchemaError("abi_upload_csv_empty")
    normalized = [cell.lstrip("\ufeff") for cell in header]
    if len(set(normalized)) != len(normalized):
        raise AbiUploadSchemaError("abi_upload_header_duplicate")
    if set(normalized) != set(expected_names):
        raise AbiUploadSchemaError("abi_upload_header_mismatch")
    return {name: index for index, name in enumerate(normalized)}


async def _hash_file(path: Path) -> tuple[bytes, int]:
    def _compute() -> tuple[bytes, int]:
        digest = hashlib.sha256()
        total = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
        return digest.digest(), total

    return await asyncio.to_thread(_compute)


async def _count_file_rows(path: Path) -> int:
    def _compute() -> int:
        counter = _CsvRowCounter()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                counter.feed(chunk)
        return counter.finish()

    return await asyncio.to_thread(_compute)


def _resolve_primary_key_columns(
    *,
    dataset: CatalogDataset,
    columns: Sequence[DatasetColumn],
    requested: Sequence[str] | None,
) -> tuple[str, ...]:
    """确定主键列。

    固定本地表用迁移里声明的物理主键；通用上传表默认第一列，
    调用方可以在 commit 时显式传入。
    """

    names = [column.column_name for column in columns]
    by_name = {column.column_name: column for column in columns}

    def check_supported(name: str) -> None:
        column = by_name.get(name)
        if column is not None and _canonical_type(column.data_type) in {
            "json",
            "array",
        }:
            # JSON/JSONB/数组值不可哈希，不能做 Python 侧主键去重。
            raise AbiUploadValidationError("abi_upload_primary_key_unsupported")

    if dataset.source_kind == "local_table":
        source_table = _bare_source_table(dataset.source_table or "")
        keys = LOCAL_TABLE_PRIMARY_KEYS.get(source_table)
        if not keys:
            raise AbiUploadValidationError("abi_upload_source_table_not_allowed")
        for key in keys:
            if key not in names and key not in _LOCAL_PROVENANCE_COLUMNS:
                raise AbiUploadSchemaError("abi_upload_primary_key_missing")
            check_supported(key)
        return keys
    if requested:
        resolved = tuple(dict.fromkeys(requested))
        missing = [name for name in resolved if name not in names]
        if missing:
            raise AbiUploadValidationError("abi_upload_primary_key_unknown")
        for name in resolved:
            check_supported(name)
        return resolved
    if not names:
        raise AbiUploadSchemaError("abi_upload_dataset_has_no_columns")
    check_supported(names[0])
    return (names[0],)


def _validate_upload_columns(columns: Sequence[DatasetColumn]) -> None:
    seen: set[str] = set()
    for column in columns:
        name = column.column_name
        if (
            not name
            or "\x00" in name
            or name.startswith(UPLOAD_INTERNAL_PREFIX)
            or len(name) > 128
            or len(name.encode("utf-8")) > 63
        ):
            raise AbiUploadSchemaError("abi_upload_column_name_invalid")
        if name in seen:
            raise AbiUploadSchemaError("abi_upload_column_duplicate")
        seen.add(name)


async def _cleanup_partial(
    session: AsyncSession,
    *,
    is_local: bool,
    batch_id: uuid.UUID,
    table: Table,
) -> None:
    """清理本批已经提交的块。best effort，不掩盖原始异常。

    上传表按 ``__abi_batch_id`` 删除，只删本批的行；本地表按
    ``load_batch_id`` 删除。两者都不会碰到并发批次的已提交数据。

    只接收标量参数：调用前 session 可能刚 rollback，ORM 对象已经过期，
    此时访问 ``dataset.source_kind`` 会触发异步环境不允许的懒加载。
    """

    try:
        if is_local:
            await session.execute(
                delete(table).where(
                    table.c[quoted_name("load_batch_id", True)] == batch_id
                )
            )
        else:
            await session.execute(
                delete(table).where(
                    table.c[quoted_name(_UPLOAD_BATCH_COLUMN, True)] == batch_id
                )
            )
        await session.commit()
    except Exception:
        await session.rollback()


async def _mark_failed(session: AsyncSession, batch_id: uuid.UUID) -> None:
    await session.execute(
        update(UploadBatch)
        .where(UploadBatch.id == batch_id)
        .values(
            status="failed",
            upload_token_hash=None,
            token_expires_at=None,
        )
    )
    await session.commit()


async def commit_batch(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    token: str | None = None,
    primary_key_columns: Sequence[str] | None = None,
    user_id: uuid.UUID | None = None,
) -> UploadBatch:
    """复核文件并装入目标表。

    失败时分两步：先回滚，再清理本批已提交的块，最后把批次标成 failed。
    进程崩在块提交之间也不会把半批数据留在当前版本里。

    ``token`` 可选：给出时校验一次性 token；不给时按 batch 原上传人
    （或显式 ``user_id``）的 grant 校验。两条路径都要求 editor，
    ``replace`` 还要求 publisher。
    """

    batch = await session.scalar(
        select(UploadBatch)
        .where(UploadBatch.id == batch_id)
        .with_for_update()
    )
    if batch is None:
        raise AbiUploadNotFound()
    if token is not None:
        _require_token(batch, token)
    if batch.status != "uploaded":
        raise AbiUploadStateError("abi_upload_content_not_uploaded")
    if batch.actual_sha256 is None or batch.actual_rows is None:
        raise AbiUploadChecksumError("abi_upload_checksum_missing")

    # 先做权限校验。权限失败不把批次标 failed，换有权限的人可以继续 commit。
    committer_id = user_id if user_id is not None else batch.uploaded_by
    min_role = "publisher" if batch.mode == "replace" else "editor"
    dataset, _grant = await require_dataset_access(
        session,
        dataset_id=batch.dataset_id,
        workspace_id=batch.workspace_id,
        user_id=committer_id,
        min_role=min_role,
    )
    if dataset.source_kind not in UPLOAD_SOURCE_KINDS:
        raise AbiUploadValidationError("abi_upload_source_kind_unsupported")
    if dataset.source_kind == "local_table" and batch.mode == "replace":
        raise AbiUploadValidationError("abi_upload_replace_requires_upload_dataset")
    if dataset.source_kind == "local_table" and not dataset.origin:
        raise AbiUploadValidationError("abi_upload_dataset_origin_required")

    columns = await load_dataset_columns(session, dataset.id)
    _validate_upload_columns(columns)
    if dataset.source_kind == "local_table":
        source_table = _bare_source_table(dataset.source_table or "")
        allowed = LOCAL_TABLE_COLUMNS.get(source_table)
        if allowed is None:
            raise AbiUploadValidationError("abi_upload_source_table_not_allowed")
        if any(column.column_name not in allowed for column in columns):
            # 不在物理表里的列会被 INSERT 静默丢弃，必须拒绝。
            raise AbiUploadSchemaError("abi_upload_column_not_in_source_table")
    expected_names = [column.column_name for column in columns]
    pk_names = _resolve_primary_key_columns(
        dataset=dataset,
        columns=columns,
        requested=primary_key_columns,
    )
    path = _batch_storage_path(batch)
    if not path.is_file():
        raise AbiUploadStateError("abi_upload_content_missing")
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise AbiUploadLimitExceeded("abi_upload_bytes_exceeded")

    version = dataset.version + 1 if batch.mode == "replace" else dataset.version
    replace = batch.mode == "replace"
    is_local = dataset.source_kind == "local_table"
    if dataset.source_kind == "upload":
        table_name = _upload_table_name(dataset)
        table = _build_upload_table(table_name, columns)
        await _ensure_upload_table(session, table, pk_names)
        start_row = 0 if replace else await _next_upload_row(session, table, version)
    else:
        table = _local_table(dataset.source_table or "", columns)
        start_row = 0

    session.sync_session.expire_on_commit = False
    rows_loaded = 0
    rows_rejected = 0
    parsed_rows = 0
    chunk: list[tuple[int, dict[str, object]]] = []
    error_chunk: list[tuple[int, str | None, str, str]] = []
    seen_keys: set[tuple[object, ...]] = set()
    row_cursor = start_row

    try:
        digest, size = await _hash_file(path)
        if batch.actual_sha256 is not None and digest != batch.actual_sha256:
            raise AbiUploadChecksumError("abi_upload_sha256_mismatch")
        if batch.expected_sha256 is not None and digest != batch.expected_sha256:
            raise AbiUploadChecksumError("abi_upload_expected_sha256_mismatch")
        counted_rows = await _count_file_rows(path)
        parsed_rows = max(counted_rows - 1, 0)
        if batch.actual_rows is not None and parsed_rows != batch.actual_rows:
            raise AbiUploadChecksumError("abi_upload_row_count_mismatch")
        if batch.expected_rows is not None and parsed_rows != batch.expected_rows:
            raise AbiUploadChecksumError("abi_upload_expected_rows_mismatch")
        if parsed_rows > MAX_UPLOAD_ROWS:
            raise AbiUploadLimitExceeded("abi_upload_rows_exceeded")

        header_map = _read_header(path, expected_names)
        batch.status = "validating"
        await session.flush()

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            for row_number, row in enumerate(reader, start=1):
                if len(row) != len(header_map):
                    error_chunk.append(
                        (
                            row_number,
                            None,
                            "row_width_mismatch",
                            "列数与表头不一致",
                        )
                    )
                    rows_rejected += 1
                else:
                    raw_values = {
                        name: row[header_map[name]] for name in expected_names
                    }
                    values, row_errors = _validate_row(
                        raw_values=raw_values,
                        columns=columns,
                    )
                    if row_errors:
                        rows_rejected += 1
                        for column_name, rule_id, message in row_errors:
                            error_chunk.append(
                                (row_number, column_name, rule_id, message)
                            )
                    elif values is not None:
                        values = _with_provenance(
                            values,
                            dataset=dataset,
                            batch=batch,
                            row_number=row_number,
                            row_cursor=row_cursor,
                            version=version,
                        )
                        key = tuple(values[name] for name in pk_names)
                        if any(item is None for item in key):
                            rows_rejected += 1
                            error_chunk.append(
                                (
                                    row_number,
                                    pk_names[0],
                                    "primary_key_null",
                                    "主键不能为空",
                                )
                            )
                        elif key in seen_keys:
                            rows_rejected += 1
                            error_chunk.append(
                                (
                                    row_number,
                                    pk_names[0],
                                    "primary_key_duplicate",
                                    "文件内主键重复",
                                )
                            )
                        else:
                            seen_keys.add(key)
                            chunk.append((row_number, values))
                            if dataset.source_kind == "upload":
                                row_cursor += 1

                if len(chunk) >= UPLOAD_BATCH_ROWS or len(error_chunk) >= UPLOAD_BATCH_ROWS:
                    inserted, duplicates = await _flush_rows(
                        session,
                        table=table,
                        rows=chunk,
                        mode=batch.mode,
                        version=version if dataset.source_kind == "upload" else None,
                        origin=dataset.origin or f"upload:{batch.workspace_id}",
                        pk_names=pk_names,
                        data_columns=expected_names,
                    )
                    rows_loaded += inserted
                    for duplicate_row, duplicate_column, rule_id, message in duplicates:
                        rows_rejected += 1
                        error_chunk.append(
                            (
                                duplicate_row,
                                duplicate_column,
                                rule_id,
                                message,
                            )
                        )
                    await _flush_errors(
                        session,
                        batch_id=batch.id,
                        errors=error_chunk,
                    )
                    await session.commit()
                    chunk = []
                    error_chunk = []
                if row_number % 1000 == 0:
                    await asyncio.sleep(0)

        inserted, duplicates = await _flush_rows(
            session,
            table=table,
            rows=chunk,
            mode=batch.mode,
            version=version if dataset.source_kind == "upload" else None,
            origin=dataset.origin or f"upload:{batch.workspace_id}",
            pk_names=pk_names,
            data_columns=expected_names,
        )
        rows_loaded += inserted
        for duplicate_row, duplicate_column, rule_id, message in duplicates:
            rows_rejected += 1
            error_chunk.append(
                (duplicate_row, duplicate_column, rule_id, message)
            )
        await _flush_errors(session, batch_id=batch.id, errors=error_chunk)

        if rows_loaded == 0:
            # 先把拒收明细与计数提交，否则 except 里的 rollback 会把
            # upload_error 一起回滚，用户看不到拒收原因。
            batch.rows_loaded = 0
            batch.rows_rejected = rows_rejected
            batch.actual_rows = parsed_rows
            batch.actual_sha256 = digest
            batch.bytes_total = size
            batch.status = "failed"
            batch.upload_token_hash = None
            batch.token_expires_at = None
            await session.commit()
            raise AbiUploadSchemaError("abi_upload_all_rows_rejected")

        batch.rows_loaded = rows_loaded
        batch.rows_rejected = rows_rejected
        batch.actual_rows = parsed_rows
        batch.actual_sha256 = digest
        batch.bytes_total = size
        batch.committed_at = _now()
        batch.status = "committed"
        batch.upload_token_hash = None
        batch.token_expires_at = None
        dataset.last_loaded_at = _now()
        dataset.pii_scanned = True
        dataset.is_current = True
        if replace:
            dataset.version = version
        dataset.row_count = await _count_dataset_rows(
            session,
            dataset=dataset,
            table=table,
            version=version if dataset.source_kind == "upload" else None,
        )
        await session.commit()
        return batch
    except BaseException as exc:
        await session.rollback()
        await _cleanup_partial(
            session,
            is_local=is_local,
            batch_id=batch_id,
            table=table,
        )
        await _mark_failed(session, batch_id)
        if isinstance(exc, AbiServiceError):
            raise
        raise AbiUploadError("abi_upload_commit_failed") from exc


def _with_provenance(
    values: dict[str, object],
    *,
    dataset: CatalogDataset,
    batch: UploadBatch,
    row_number: int,
    row_cursor: int,
    version: int,
) -> dict[str, object]:
    """补齐内部列与本地表的溯源列。用户提供的同名值一律被覆盖。"""

    content_hash = _row_content_hash(values)
    values = dict(values)
    if dataset.source_kind == "local_table":
        values["origin"] = dataset.origin or f"upload:{batch.workspace_id}"
        values["load_batch_id"] = batch.id
        values["src_file"] = batch.filename
        values["src_row_ordinal"] = row_number - 1
        values["content_hash"] = content_hash
        return values

    values[_UPLOAD_VERSION_COLUMN] = version
    values[_UPLOAD_ROW_COLUMN] = row_cursor
    values[_UPLOAD_BATCH_COLUMN] = batch.id
    values[_UPLOAD_HASH_COLUMN] = content_hash
    return values


async def _count_dataset_rows(
    session: AsyncSession,
    *,
    dataset: CatalogDataset,
    table: Table,
    version: int | None,
) -> int:
    statement = select(func.count()).select_from(table)
    if version is not None:
        statement = statement.where(
            table.c[quoted_name(_UPLOAD_VERSION_COLUMN, True)] == version
        )
    elif dataset.origin:
        statement = statement.where(
            table.c[quoted_name("origin", True)] == dataset.origin
        )
    else:
        statement = statement.where(
            table.c[quoted_name("origin", True)]
            == f"upload:{dataset.workspace_id}"
        )
    value = await session.scalar(statement)
    return int(value or 0)


__all__ = [
    "UploadBatch",
    "AbiUploadChecksumError",
    "AbiUploadError",
    "UploadError",
    "AbiUploadLimitExceeded",
    "AbiUploadNotFound",
    "AbiUploadSchemaError",
    "AbiUploadStateError",
    "AbiUploadTokenError",
    "AbiUploadValidationError",
    "append_content",
    "commit_batch",
    "create_batch",
    "export_root",
    "scan_pii",
]

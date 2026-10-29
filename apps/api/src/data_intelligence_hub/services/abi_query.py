"""ABI 查询服务。

本模块只做三件事：

1. 解析目录数据集与访问授权。取数必须同时满足 ``workspace_id`` 与
   ``abi.access_grant`` 两个条件；没有显式 grant 一律拒绝。admin 不是
   万能旁路，它同样需要一条 admin grant。
2. 用 SQLAlchemy 表达式构造查询。列名只能来自 ``abi.dataset_column``
   与服务端常量 allowlist；物理标识符统一 quote，绝不拼接 SQL 字符串。
3. 在序列化前按 ``abi.field_policy`` 遮罩 PII。

分页用 keyset cursor，不用 offset。cursor 是 HMAC-SHA256 签名串，
绑定 ``dataset_id``、``user_id``、列指纹、过滤指纹、排序与过期时间。
客户端改一个字节都会被拒绝。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    LargeBinary,
    Numeric,
    Select,
    Text,
    Uuid,
    and_,
    cast,
    column,
    or_,
    select,
    table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import quoted_name

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.abi import (
    ABI_ROLE_ORDER,
    AccessGrant,
    CatalogDataset,
    DatasetColumn,
    FieldPolicy,
    role_rank,
)
from data_intelligence_hub.services.abi_errors import (
    AbiAccessDenied,
    AbiDatasetNotFound,
    AbiQueryValidationError,
)

# upload/export 一直从本模块取 AbiServiceError，保留这条转出口，
# 用 as 形式声明「这是有意重导出」而不是漏删。
from data_intelligence_hub.services.abi_errors import (
    AbiServiceError as AbiServiceError,
)

# ---------------------------------------------------------------- 常量

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200
CURSOR_TTL_SECONDS: Final[int] = 3600
QUERY_TIMEOUT: Final[str] = "15s"
IDLE_TRANSACTION_TIMEOUT_MS: Final[int] = 60_000
MAX_IN_VALUES: Final[int] = 100
MAX_CURSOR_KEY_CHARS: Final[int] = 4096

# 角色等级来自模型层，服务层不再维护第二份顺序。
ROLE_RANK: Final[dict[str, int]] = ABI_ROLE_ORDER

# 这些 PII 等级默认遮罩。
#
# ``quasi`` 必须在内。此前它被排除，注释理由是「导出策略仍可按需处理」，
# 但 worker 路径（``mask_row``）只按这个集合判断，没有任何地方真的去
# 「按需处理」——结果是 ``quasi`` 字段在异步导出里**原样明文输出**，
# 而在线查询路径却把它遮成「前 2 后 1」。同一个策略、两条路径、两种结果。
#
# 后果不只是不一致：``direct``/``secret`` 降级到 ``quasi`` 看似「仍然敏感」，
# 实际把值从 ``***`` 换成了可读明文，是一次实质降级。
PII_MASKED_CLASSES: Final[frozenset[str]] = frozenset(
    {"unknown", "quasi", "direct", "secret"}
)
PII_CLASSES: Final[frozenset[str]] = frozenset(
    {"unknown", "none", "quasi", "direct", "secret"}
)

# 过滤 op 白名单。未列出的 op 一律拒绝。
FILTER_OPS: Final[frozenset[str]] = frozenset(
    {
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "between",
        "is_null",
        "not_null",
        "contains",
        "starts_with",
        "ends_with",
    }
)

_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_JSON_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")
_UPLOAD_TABLE_RE: Final[re.Pattern[str]] = re.compile(r"^abi_upload_[0-9a-f]{32}$")

UPLOAD_INTERNAL_COLUMNS: Final[frozenset[str]] = frozenset(
    {"__abi_version", "__abi_row", "__abi_batch_id", "__abi_content_hash"}
)

# raw.apify_item 的物理列。由于主表是声明的分区表，这里只列权威列名。
APIFY_ITEM_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "collected_month",
        "dataset_id",
        "item_index",
        "account_id",
        "platform",
        "object_type",
        "item",
        "content_hash",
        "pii_class",
        "item_status",
        "fetched_at",
        "fetch_batch_id",
    }
)

# raw schema 中可作为数据集来源的本地表。load_file / load_error 是装载支撑表，
# 不对外开放查询，所以不在此列。
LOCAL_TABLE_COLUMNS: Final[dict[str, frozenset[str]]] = {
    "si_tiktok_video": frozenset(
        {
            "video_id", "hashtag", "snapshot_date", "rank_in_tag", "author_unique_id",
            "author_nickname", "author_id", "descr", "published_at", "is_ad", "music_id",
            "music_title", "music_author", "play_count", "digg_count", "comment_count",
            "share_count", "collect_count", "snap_days", "peak_play", "first_seen",
            "last_seen", "play_gain_total", "play_gain_daily_avg", "parse_level",
            "recommendation", "analysis_status", "evidence_state", "analysis_version",
            "summary_original", "target_audience", "hook_visual", "hook_audio", "hook_formula",
            "n_mechanisms", "n_timeline_segments", "n_transcript_segments", "brand_borrow_n",
            "brand_replace_n", "analysis_created_at", "has_deepread", "deepread_model",
            "deepread_at", "theme_tags", "mechanism_tags", "life_stage", "one_liner",
            "media_playable", "media_size_bytes", "comment_rows", "comment_top_digg",
            "built_at", "origin", "load_batch_id", "src_file", "src_row_ordinal",
            "content_hash", "loaded_at",
        }
    ),
    "si_tiktok_comment": frozenset(
        {
            "platform", "video_id", "comment_id", "parent_id", "text", "digg_count",
            "reply_count", "author_handle", "author_id", "author_avatar", "liked_by_author",
            "pinned_by_author", "platform_created_at", "fetched_at", "source_tier", "run_id",
            "sample_rank", "origin", "load_batch_id", "src_file", "src_row_ordinal",
            "content_hash", "loaded_at",
        }
    ),
    "si_tiktok_hashtag_snapshot": frozenset(
        {
            "snapshot_date", "captured_at", "hashtag_id", "hashtag", "source_actor",
            "rank_in_tag", "video_id", "author_id", "author_unique_id", "author_nickname",
            "author_avatar_url", "play_count", "digg_count", "comment_count", "share_count",
            "collect_count", "published_at", "is_ad", "descr", "run_id", "cover_url",
            "music_id", "music_title", "music_author", "music_duration_sec",
            "music_is_original", "music_is_commerce", "hashtags", "origin", "load_batch_id",
            "src_file", "src_row_ordinal", "content_hash", "loaded_at",
        }
    ),
    "si_metric_snapshot": frozenset(
        {
            "snapshot_date", "captured_at", "platform_code", "object_type", "object_id",
            "view_count", "like_count", "comment_count", "share_count", "collect_count",
            "source_actor", "run_id", "origin", "load_batch_id", "src_file", "src_row_ordinal",
            "content_hash", "loaded_at",
        }
    ),
    "si_music_platform_snapshot": frozenset(
        {
            "id", "origin", "load_batch_id", "src_file", "src_row_ordinal", "content_hash",
            "loaded_at",
        }
    ),
    "si_author_video_snapshot": frozenset(
        {
            "id", "origin", "load_batch_id", "src_file", "src_row_ordinal", "content_hash",
            "loaded_at",
        }
    ),
    "si_social_post": frozenset(
        {
            "id", "origin", "load_batch_id", "src_file", "src_row_ordinal", "content_hash",
            "loaded_at",
        }
    ),
    "apify_tweet": frozenset(
        {
            "snapshot_date", "tweet_id", "conversation_id", "author_id", "author_user_name",
            "author_name", "author_followers", "author_verified", "author_description",
            "author_location", "created_at", "full_text", "lang", "like_count", "reply_count",
            "retweet_count", "quote_count", "bookmark_count", "view_count", "is_reply",
            "is_quote", "is_retweet", "is_pinned", "possibly_sensitive", "in_reply_to_id",
            "in_reply_to_user_id", "in_reply_to_username", "quoted_id", "hashtags", "urls",
            "media", "is_no_results", "raw", "origin", "load_batch_id", "src_file",
            "src_row_ordinal", "content_hash", "loaded_at",
        }
    ),
    "probe_instagram_post": frozenset(
        {
            "probe_date", "short_code", "post_id", "post_type", "url", "input_url", "caption",
            "owner_id", "owner_username", "owner_full_name", "posted_at", "likes_count",
            "comments_count", "video_view_count", "video_duration", "dimensions_width",
            "dimensions_height", "display_url", "video_url", "images", "child_posts",
            "latest_comments", "first_comment", "hashtags", "mentions", "tagged_users",
            "location_id", "location_name", "music_info", "paid_partnership", "product_type",
            "is_pinned", "raw", "origin", "load_batch_id", "src_file", "src_row_ordinal",
            "content_hash", "loaded_at",
        }
    ),
    "probe_tiktok_video": frozenset(
        {
            "probe_date", "arm", "video_id", "text", "create_time", "create_time_iso",
            "web_video_url", "search_query", "author_id", "author_name", "author_nickname",
            "author_signature", "author_fans", "author_following", "author_heart",
            "author_verified", "author_avatar_url", "author_bio_link", "author_profile_url",
            "author_private", "music_id", "music_name", "music_author", "music_original",
            "music_play_url", "music_cover_url", "video_height", "video_width",
            "video_duration", "video_definition", "video_format", "video_cover_url",
            "video_cover_original_url", "transcription_link", "play_count", "digg_count",
            "comment_count", "share_count", "collect_count", "repost_count", "is_ad",
            "is_sponsored", "is_pinned", "is_slideshow", "is_story", "is_muted",
            "location_created", "hashtags", "mentions", "detailed_mentions", "effect_stickers",
            "media_urls", "slideshow_image_links", "has_tiktok_shop_product",
            "comments_dataset_url", "raw", "origin", "load_batch_id", "src_file",
            "src_row_ordinal", "content_hash", "loaded_at",
        }
    ),
    "probe_youtube_video": frozenset(
        {
            "probe_date", "arm", "video_id", "title", "description", "url", "from_yt_url",
            "channel_id", "channel_name", "channel_username", "channel_url",
            "number_of_subscribers", "published_at", "duration", "view_count", "likes",
            "comments_count", "comments_turned_off", "is_members_only", "is_paid_content",
            "is_monetized", "hashtags", "description_links", "thumbnail_url", "order_index",
            "input", "video_type", "translated_title", "translated_text", "ai_video_summary",
            "ai_video_description", "collaborators", "subtitles", "transcription_url",
            "location", "raw", "origin", "load_batch_id", "src_file", "src_row_ordinal",
            "content_hash", "loaded_at",
        }
    ),
    "pmo_collection_record": frozenset(
        {
            "record_id", "project_id", "workspace_id", "source_id", "task_run_id",
            "record_type", "source_url", "screenshot_url", "collected_at", "created_at",
            "snapshot_date", "schema_version", "provider", "platform", "actor_id",
            "content_text", "content", "origin", "load_batch_id", "src_file",
            "src_row_ordinal", "content_hash", "loaded_at",
        }
    ),
    "amazon_review": frozenset(
        {
            "review_key", "file_date", "asin", "rating", "title", "body", "author",
            "review_date", "verified_purchase", "helpful_votes", "total_votes",
            "source_description", "origin", "load_batch_id", "src_file", "src_row_ordinal",
            "content_hash", "loaded_at",
        }
    ),
    "product_catalog": frozenset(
        {
            "product_key", "file_date", "category", "brand", "product_name", "origin",
            "load_batch_id", "src_file", "src_row_ordinal", "content_hash", "loaded_at",
        }
    ),
}

# 本地表的物理主键。keyset 分页用它做最终 tiebreaker。
LOCAL_TABLE_PRIMARY_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "si_tiktok_video": ("video_id",),
    "si_tiktok_comment": ("platform", "video_id", "comment_id"),
    "si_tiktok_hashtag_snapshot": ("snapshot_date", "hashtag_id", "video_id"),
    "si_metric_snapshot": (
        "snapshot_date",
        "platform_code",
        "object_type",
        "object_id",
        "source_actor",
    ),
    "si_music_platform_snapshot": ("id",),
    "si_author_video_snapshot": ("id",),
    "si_social_post": ("id",),
    "apify_tweet": ("origin", "src_file", "src_row_ordinal"),
    "probe_instagram_post": ("origin", "src_file", "src_row_ordinal"),
    "probe_tiktok_video": ("origin", "src_file", "src_row_ordinal"),
    "probe_youtube_video": ("origin", "src_file", "src_row_ordinal"),
    "pmo_collection_record": ("record_id",),
    "amazon_review": ("review_key",),
    "product_catalog": ("product_key",),
}

# 服务端常量 allowlist。dataset_column 是数据，用户上传的表头会流进去，
# 不能单独作为可信来源。物理列还必须命中这张常量表。
SERVER_COLUMN_ALLOWLIST: Final[frozenset[str]] = frozenset().union(
    APIFY_ITEM_COLUMNS, *LOCAL_TABLE_COLUMNS.values()
)

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

_CAST_TYPES: Final[dict[str, Any]] = {
    "integer": Integer,
    "bigint": BigInteger,
    "numeric": Numeric,
    "boolean": Boolean,
    "date": Date,
    "timestamp": DateTime(timezone=True),
    "uuid": Uuid,
}

_APIFY_ITEM: Final[Any] = table(
    "apify_item",
    column(quoted_name("collected_month", True), Date),
    column(quoted_name("dataset_id", True), Text),
    column(quoted_name("item_index", True), Integer),
    column(quoted_name("account_id", True), Uuid(as_uuid=True)),
    column(quoted_name("platform", True), Text),
    column(quoted_name("object_type", True), Text),
    # item 必须声明 JSONB，才能用 -> / ->> 访问 actor 字段。
    column(quoted_name("item", True), JSONB),
    column(quoted_name("content_hash", True), LargeBinary),
    column(quoted_name("pii_class", True), Text),
    column(quoted_name("item_status", True), Text),
    column(quoted_name("fetched_at", True), DateTime(timezone=True)),
    column(quoted_name("fetch_batch_id", True), Uuid(as_uuid=True)),
    schema="raw",
)


# ---------------------------------------------------------------- 领域异常


# 错误类型统一在 abi_errors 里定义。此处重新导出，保证既有 import
# （from ...services.abi_query import AbiServiceError）继续可用，同时让
# abi_service 的路由层与查询层捕获的是**同一个类对象**。
class AbiQueryCursorError(AbiQueryValidationError):
    """游标签名、绑定或过期时间不通过。"""

    code = "abi_query_cursor_invalid"


# ---------------------------------------------------------------- 数据结构

@dataclass(frozen=True, slots=True)
class AbiFilter:
    """一个结构化过滤条件。值永远是绑定参数，不进 SQL 文本。"""

    column: str
    op: str = "eq"
    value: object = None


@dataclass(frozen=True, slots=True)
class AbiQueryPage:
    """一页查询结果。"""

    columns: tuple[str, ...]
    rows: list[dict[str, object]]
    next_cursor: str | None
    has_more: bool
    masked_columns: tuple[str, ...]
    pii_classes: dict[str, str]

    def __iter__(self) -> Iterator[object]:
        """允许 ``rows, next_cursor = page`` 这种轻量解包。"""

        yield self.rows
        yield self.next_cursor


@dataclass(frozen=True, slots=True)
class AbiQueryPlan:
    """已经校验过的查询计划。导出服务复用同一份构造逻辑。"""

    statement: Select[Any]
    columns: tuple[str, ...]
    order_names: tuple[str, ...]
    order_dir: str
    columns_hash: str
    filters_hash: str
    pii_classes: dict[str, str]
    mask_rules: dict[str, str | None]
    masked_columns: tuple[str, ...]


# ---------------------------------------------------------------- 通用工具


def _canonical_type(data_type: str | None) -> str:
    """把 dataset_column.data_type 收敛到服务端支持的九种类型。"""

    if not data_type:
        return "text"
    return _DATA_TYPE_ALIASES.get(data_type.strip().lower(), "text")


def _coerce_filter_value(value: object, data_type: str) -> object:
    """按列类型转换过滤值。转换失败抛查询校验错误，不把原始值写进消息。"""

    canonical = _canonical_type(data_type)
    if value is None:
        return None
    try:
        if canonical in {"integer", "bigint"}:
            if isinstance(value, bool):
                raise ValueError
            return int(str(value))
        if canonical == "numeric":
            if isinstance(value, bool):
                raise ValueError
            return Decimal(str(value))
        if canonical == "boolean":
            if isinstance(value, bool):
                return value
            text_value = str(value).strip().lower()
            if text_value in {"true", "t", "1", "yes", "y"}:
                return True
            if text_value in {"false", "f", "0", "no", "n"}:
                return False
            raise ValueError
        if canonical == "date":
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            return date.fromisoformat(str(value))
        if canonical == "timestamp":
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))
        if canonical == "uuid":
            return uuid.UUID(str(value))
        if canonical == "array":
            if isinstance(value, (list, tuple, set, frozenset)):
                return list(value)
            parsed = json.loads(str(value))
            if not isinstance(parsed, list):
                raise ValueError
            return parsed
        if canonical == "json":
            if isinstance(value, (dict, list)):
                return value
            return json.loads(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AbiQueryValidationError("abi_filter_value_invalid") from exc
    return value


def _json_safe(value: object) -> object:
    """把值转成可稳定 JSON 序列化的形态。时间与金额用类型标签保留语义。"""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return {"__abi_type__": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"__abi_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__abi_type__": "date", "value": value.isoformat()}
    if isinstance(value, uuid.UUID):
        return {"__abi_type__": "uuid", "value": str(value)}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "__abi_type__": "bytes",
            "value": base64.urlsafe_b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_json_safe(item) for item in sorted(value, key=repr)]
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return str(value)


def _json_restore(value: object) -> object:
    """``_json_safe`` 的逆操作，用于游标里的 last_key。"""

    if isinstance(value, list):
        return [_json_restore(item) for item in value]
    if isinstance(value, dict):
        marker = value.get("__abi_type__")
        raw = value.get("value")
        if marker == "decimal" and isinstance(raw, str):
            return Decimal(raw)
        if marker == "datetime" and isinstance(raw, str):
            return datetime.fromisoformat(raw)
        if marker == "date" and isinstance(raw, str):
            return date.fromisoformat(raw)
        if marker == "uuid" and isinstance(raw, str):
            return uuid.UUID(raw)
        if marker == "bytes" and isinstance(raw, str):
            return base64.urlsafe_b64decode(raw.encode("ascii"))
        return {str(key): _json_restore(item) for key, item in value.items()}
    return value


def _fingerprint_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _columns_fingerprint(columns: Sequence[str]) -> str:
    return hashlib.sha256("\x1f".join(columns).encode("utf-8")).hexdigest()


def _cursor_key() -> bytes:
    """从 jwt_secret 派生独立用途的 HMAC 密钥。

    不新增配置项，也不直接复用 JWT 签名密钥原文；用途域分开，
    游标签名泄露不能反推 JWT 签名能力。
    """

    secret = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, b"abi.query.cursor.v1", hashlib.sha256).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _normalize_role(role: str) -> int:
    return role_rank(role)


def _dedupe_columns(columns: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for column_name in columns:
        if column_name not in seen:
            seen.add(column_name)
            ordered.append(column_name)
    return tuple(ordered)


def _normalize_order_names(order_by: str | Sequence[str] | None) -> tuple[str, ...]:
    if order_by is None:
        return ()
    if isinstance(order_by, str):
        return (order_by,)
    return _dedupe_columns(tuple(order_by))


def _normalize_order_dir(order_dir: str) -> str:
    normalized = (order_dir or "asc").strip().lower()
    if normalized not in {"asc", "desc"}:
        raise AbiQueryValidationError("abi_order_dir_invalid")
    return normalized


# ---------------------------------------------------------------- 过滤器解析


def normalize_filters(filters: Sequence[object] | None) -> list[AbiFilter]:
    """接受 dataclass、映射与元组三种写法，统一成 ``AbiFilter``。

    支持：
    - ``AbiFilter(column, op, value)``
    - ``{"column": "...", "op": "eq", "value": ...}``
    - ``{"column_name": value}``（单键等值简写）
    - ``("column", "op", value)`` / ``("column", value)``
    """

    normalized: list[AbiFilter] = []
    if filters is None:
        items: Sequence[object] = ()
    elif isinstance(filters, AbiFilter | Mapping):
        items = (filters,)
    elif (
        isinstance(filters, (tuple, list))
        and len(filters) in (2, 3)
        and filters
        and isinstance(filters[0], str)
    ):
        # 单个过滤条件写成 ("column", value) / ("column", "op", value)。
        items = (filters,)
    else:
        items = filters
    for item in items:
        parsed = _parse_filter(item)
        _validate_filter(parsed)
        normalized.append(parsed)
    return normalized


def _parse_filter(item: object) -> AbiFilter:
    if isinstance(item, AbiFilter):
        return item
    if isinstance(item, Mapping):
        if "column" in item:
            column = item.get("column")
            if not isinstance(column, str):
                raise AbiQueryValidationError("abi_filter_column_invalid")
            op = item.get("op", "eq")
            if not isinstance(op, str):
                raise AbiQueryValidationError("abi_filter_op_invalid")
            return AbiFilter(column=column, op=op, value=item.get("value"))
        if len(item) == 1:
            column, value = next(iter(item.items()))
            if not isinstance(column, str):
                raise AbiQueryValidationError("abi_filter_column_invalid")
            return AbiFilter(column=column, value=value)
        raise AbiQueryValidationError("abi_filter_shape_invalid")
    if isinstance(item, (tuple, list)):
        if len(item) == 2:
            column, value = item
            if not isinstance(column, str):
                raise AbiQueryValidationError("abi_filter_column_invalid")
            return AbiFilter(column=column, value=value)
        if len(item) == 3:
            column, op, value = item
            if not isinstance(column, str) or not isinstance(op, str):
                raise AbiQueryValidationError("abi_filter_shape_invalid")
            return AbiFilter(column=column, op=op, value=value)
        raise AbiQueryValidationError("abi_filter_shape_invalid")
    raise AbiQueryValidationError("abi_filter_shape_invalid")


def _validate_filter(parsed: AbiFilter) -> None:
    if not parsed.column or len(parsed.column) > 128:
        raise AbiQueryValidationError("abi_filter_column_invalid")
    if parsed.op not in FILTER_OPS:
        raise AbiQueryValidationError("abi_filter_op_not_allowed")
    if parsed.op in {"is_null", "not_null"}:
        return
    if parsed.op in {"in", "not_in"}:
        if not isinstance(parsed.value, (list, tuple, set, frozenset)):
            raise AbiQueryValidationError("abi_filter_value_invalid")
        if len(parsed.value) == 0 or len(parsed.value) > MAX_IN_VALUES:
            raise AbiQueryValidationError("abi_filter_value_invalid")
        return
    if parsed.op == "between":
        if not isinstance(parsed.value, (list, tuple)) or len(parsed.value) != 2:
            raise AbiQueryValidationError("abi_filter_value_invalid")
        return
    if parsed.op in {"contains", "starts_with", "ends_with"}:
        if not isinstance(parsed.value, str):
            raise AbiQueryValidationError("abi_filter_value_invalid")
        return
    if parsed.value is None and parsed.op not in {"eq", "ne"}:
        raise AbiQueryValidationError("abi_filter_value_invalid")


def _filters_fingerprint(filters: Sequence[AbiFilter]) -> str:
    payload = [
        {
            "column": item.column,
            "op": item.op,
            "value": _json_safe(item.value),
        }
        for item in filters
    ]
    return _fingerprint_json(payload)


# ---------------------------------------------------------------- 授权


async def require_dataset_access(
    session: AsyncSession,
    *,
    dataset_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    min_role: str = "viewer",
) -> tuple[CatalogDataset, AccessGrant]:
    """按 workspace + grant 双条件取数据集，并校验角色下限。

    没有 grant 就是 403，不区分「数据集不存在」与「没有授权」之外的情况：
    数据集必须在当前 workspace，否则按 404 处理，避免跨租户枚举。
    """

    if min_role not in ROLE_RANK:
        raise AbiQueryValidationError("abi_role_invalid")
    dataset = await session.scalar(
        select(CatalogDataset).where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.id == dataset_id,
        )
    )
    if dataset is None:
        raise AbiDatasetNotFound()
    grant = await session.scalar(
        select(AccessGrant).where(
            AccessGrant.workspace_id == workspace_id,
            AccessGrant.dataset_id == dataset_id,
            AccessGrant.user_id == user_id,
        )
    )
    if grant is None:
        raise AbiAccessDenied("abi_access_grant_required")
    if _normalize_role(grant.role) < _normalize_role(min_role):
        raise AbiAccessDenied("abi_access_role_insufficient")
    return dataset, grant


async def load_dataset_by_slug(
    session: AsyncSession,
    *,
    slug: str,
    workspace_id: uuid.UUID,
) -> CatalogDataset | None:
    """按 workspace + slug 读目录行。路由注册阶段使用。"""

    dataset = await session.scalar(
        select(CatalogDataset).where(
            CatalogDataset.workspace_id == workspace_id,
            CatalogDataset.slug == slug,
        )
    )
    return dataset if isinstance(dataset, CatalogDataset) else None


async def load_dataset_columns(
    session: AsyncSession, dataset_id: uuid.UUID
) -> list[DatasetColumn]:
    """按 ordinal 顺序读列清单。"""

    result = await session.scalars(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.ordinal, DatasetColumn.column_name)
    )
    return list(result.all())


async def load_field_policies(
    session: AsyncSession, dataset_id: uuid.UUID
) -> dict[str, FieldPolicy]:
    """读字段策略。没有策略行的列按 unknown 处理。"""

    result = await session.scalars(
        select(FieldPolicy).where(FieldPolicy.dataset_id == dataset_id)
    )
    return {policy.field_path: policy for policy in result.all()}


def _policy_for(
    policies: Mapping[str, FieldPolicy], column_name: str
) -> FieldPolicy | None:
    """字段策略的 path 可能是裸列名、``item.<name>`` 或 ``$.<name>``。"""

    for candidate in (column_name, f"item.{column_name}", f"$.{column_name}"):
        policy = policies.get(candidate)
        if policy is not None:
            return policy
    return None


def pii_class_for(
    policies: Mapping[str, FieldPolicy], column_name: str
) -> str:
    """返回字段的 PII 等级。无策略行默认 unknown，绝不 fail-open。"""

    policy = _policy_for(policies, column_name)
    if policy is None:
        return "unknown"
    return policy.pii_class if policy.pii_class in PII_CLASSES else "unknown"


def mask_rule_for(
    policies: Mapping[str, FieldPolicy], column_name: str
) -> str | None:
    policy = _policy_for(policies, column_name)
    return policy.mask_rule if policy is not None else None


def mask_value(value: object, pii_class: str, mask_rule: str | None) -> object:
    """按策略遮罩单个值。遮罩在这里做，不在前端做。

    ``secret`` / ``direct`` / ``unknown`` 默认返回 ``***``。规则只支持
    固定枚举，任何未知规则都退回 ``redact``，不会因为拼错规则而放行。
    """

    if pii_class not in PII_MASKED_CLASSES:
        return value
    if value is None:
        return None
    rule = (mask_rule or "redact").strip().lower()
    if rule == "null":
        return None
    if rule == "hash":
        raw = (
            bytes(value)
            if isinstance(value, (bytes, bytearray, memoryview))
            else str(value).encode("utf-8")
        )
        return hashlib.sha256(raw).hexdigest()[:32]
    if rule == "last4":
        text_value = str(value)
        return f"***{text_value[-4:]}" if len(text_value) > 4 else "***"
    if rule == "partial":
        text_value = str(value)
        if len(text_value) <= 4:
            return "***"
        return f"{text_value[0]}***{text_value[-1]}"
    return "***"


def mask_row(
    row: Mapping[str, object],
    pii_classes: Mapping[str, str],
    mask_rules: Mapping[str, str | None],
) -> dict[str, object]:
    """对一行做遮罩。导出与查询共用，避免两条路径策略漂移。"""

    masked: dict[str, object] = {}
    for column_name, value in row.items():
        pii_class = pii_classes.get(column_name, "unknown")
        if pii_class in PII_MASKED_CLASSES:
            masked[column_name] = mask_value(value, pii_class, mask_rules.get(column_name))
        else:
            masked[column_name] = value
    return masked


# ---------------------------------------------------------------- 游标


def encode_cursor(
    *,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID | None,
    columns_hash: str,
    filters_hash: str,
    order_names: Sequence[str],
    order_dir: str,
    last_key: Sequence[object],
    now: datetime | None = None,
) -> str:
    """生成 HMAC-SHA256 签名的 keyset 游标。"""

    encoded_key = [_json_safe(value) for value in last_key]
    encoded_length = len(
        json.dumps(encoded_key, ensure_ascii=False, separators=(",", ":"))
    )
    if encoded_length > MAX_CURSOR_KEY_CHARS:
        raise AbiQueryValidationError("abi_cursor_key_too_large")
    issued_at = now or datetime.now(UTC)
    payload = {
        "v": 1,
        "d": str(dataset_id),
        "u": str(user_id) if user_id is not None else "",
        "ch": columns_hash,
        "fh": filters_hash,
        "o": list(order_names),
        "od": order_dir,
        "k": encoded_key,
        "exp": int((issued_at + timedelta(seconds=CURSOR_TTL_SECONDS)).timestamp()),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(_cursor_key(), raw, hashlib.sha256).digest()
    return f"{_b64encode(raw)}.{_b64encode(signature)}"


def decode_cursor(
    cursor: str,
    *,
    dataset_id: uuid.UUID,
    user_id: uuid.UUID | None,
    columns_hash: str,
    filters_hash: str,
    order_names: Sequence[str],
    order_dir: str,
    now: datetime | None = None,
) -> list[object]:
    """校验并解出游标。任何不一致都按非法游标处理。"""

    if not cursor or len(cursor) > MAX_CURSOR_KEY_CHARS * 2:
        raise AbiQueryCursorError("abi_query_cursor_invalid")
    try:
        payload_part, signature_part = cursor.split(".", 1)
        raw = _b64decode(payload_part)
        signature = _b64decode(signature_part)
    except (ValueError, TypeError) as exc:
        raise AbiQueryCursorError("abi_query_cursor_invalid") from exc
    expected = hmac.new(_cursor_key(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise AbiQueryCursorError("abi_query_cursor_invalid")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AbiQueryCursorError("abi_query_cursor_invalid") from exc
    if not isinstance(payload, dict):
        raise AbiQueryCursorError("abi_query_cursor_invalid")
    if payload.get("v") != 1:
        raise AbiQueryCursorError("abi_query_cursor_invalid")
    current_time = now or datetime.now(UTC)
    try:
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AbiQueryCursorError("abi_query_cursor_invalid") from exc
    if expires_at < int(current_time.timestamp()):
        raise AbiQueryCursorError("abi_query_cursor_expired")
    expected_binding = {
        "d": str(dataset_id),
        "u": str(user_id) if user_id is not None else "",
        "ch": columns_hash,
        "fh": filters_hash,
        "o": list(order_names),
        "od": order_dir,
    }
    for key, expected_value in expected_binding.items():
        if payload.get(key) != expected_value:
            raise AbiQueryCursorError("abi_query_cursor_mismatch")
    raw_key = payload.get("k")
    if not isinstance(raw_key, list) or len(raw_key) != len(order_names):
        raise AbiQueryCursorError("abi_query_cursor_invalid")
    return [_json_restore(item) for item in raw_key]


# ---------------------------------------------------------------- 列解析


def _apify_dataset_id(dataset: CatalogDataset) -> str:
    """Apify 数据集在 raw.apify_item 里的键。

    目录注册约定把 Apify dataset id 写进 ``source_table``；若为空或写成
    物理表名，则退回 ``slug``。两种情况都不会把用户输入当 SQL 标识符。
    """

    source_table = (dataset.source_table or "").strip()
    if source_table.startswith("raw."):
        source_table = source_table[4:]
    if source_table and source_table != "apify_item":
        return source_table
    return dataset.slug


def _bare_source_table(value: str) -> str:
    """把 ``raw.foo`` 归一成 ``foo``。其他 schema 或带点的表名一律无效。"""

    text_value = (value or "").strip()
    if text_value.startswith("raw."):
        return text_value[4:]
    if "." in text_value:
        return ""
    return text_value


def _local_table(source_table: str) -> Any:
    """按服务端常量允许的表名构造轻量表对象。"""

    source_table = _bare_source_table(source_table)
    if source_table not in LOCAL_TABLE_COLUMNS:
        raise AbiQueryValidationError("abi_source_table_not_allowed")
    columns: list[Any] = [
        column(quoted_name(name, True))
        for name in sorted(LOCAL_TABLE_COLUMNS[source_table])
    ]
    return table(quoted_name(source_table, True), *columns, schema="raw")


def _upload_table(dataset: CatalogDataset, column_names: Sequence[str]) -> Any:
    """构造惰性创建的通用上传表。

    迁移里没有通用上传行表。上传服务在首次 commit 时按 dataset_column
    建表，表名由数据集 UUID 决定，不含任何用户输入。查询只读该物理表。
    """

    source_table = _bare_source_table(dataset.source_table or "")
    expected_table = f"abi_upload_{dataset.id.hex}"
    # 表名必须由数据集 UUID 推出。允许任意合法表名会让一个数据集
    # 通过 source_table 指向另一个数据集的物理表，绕过 grant。
    if source_table != expected_table or not _UPLOAD_TABLE_RE.fullmatch(
        source_table
    ):
        raise AbiQueryValidationError("abi_upload_table_not_ready")
    names: list[Any] = [
        column(quoted_name("__abi_version", True)),
        column(quoted_name("__abi_row", True)),
        column(quoted_name("__abi_batch_id", True)),
        column(quoted_name("__abi_content_hash", True)),
        *[column(quoted_name(name, True)) for name in column_names],
    ]
    return table(quoted_name(source_table, True), *names, schema="raw")


def _validate_registered_column(
    *,
    dataset: CatalogDataset,
    column: DatasetColumn,
) -> None:
    name = column.column_name
    # PostgreSQL 标识符与结果列别名都限制 63 字节；超过会被截断，
    # 导致 RowMapping 键与请求列名对不上。
    if not name or "\x00" in name or len(name.encode("utf-8")) > 63:
        raise AbiQueryValidationError("abi_column_name_invalid")

    if dataset.source_kind == "apify_platform":
        if name in APIFY_ITEM_COLUMNS:
            return
        # JSONB 字段名只作为绑定参数使用，不进入 SQL 文本。
        # 仍限制长度并禁止内部保留前缀。
        if name.startswith("__"):
            raise AbiQueryValidationError("abi_column_name_invalid")
        return

    if dataset.source_kind == "local_table":
        source_table = _bare_source_table(dataset.source_table or "")
        allowed = LOCAL_TABLE_COLUMNS.get(source_table)
        if allowed is None:
            raise AbiQueryValidationError("abi_source_table_not_allowed")
        if name not in allowed or name not in SERVER_COLUMN_ALLOWLIST:
            raise AbiQueryValidationError("abi_column_not_allowed")
        return

    if dataset.source_kind == "upload":
        if name.startswith("__"):
            raise AbiQueryValidationError("abi_column_name_invalid")
        return

    raise AbiQueryValidationError("abi_source_kind_not_supported")


def _column_expression(
    *,
    dataset: CatalogDataset,
    table_expr: Any,
    column: DatasetColumn,
) -> Any:
    """返回列表达式。值仍是 SQLAlchemy 表达式，不是字符串。"""

    name = column.column_name
    if dataset.source_kind == "apify_platform":
        if name in APIFY_ITEM_COLUMNS:
            return table_expr.c[quoted_name(name, True)]
        expression = _json_field_expression(table_expr.c["item"], name)
        # 非 JSON 字段取文本；JSON/数组字段保留 jsonb，交给序列化层处理。
        if _canonical_type(column.data_type) in {"json", "array"}:
            return expression
        return expression.astext
    return table_expr.c[quoted_name(name, True)]


def _json_field_expression(item_column: Any, field_name: str) -> Any:
    """把 JSONB 字段名转成表达式。

    字段名只作为 ``->>`` / ``->`` 的绑定参数。点号仅在所有分段都符合
    安全标识符时视为嵌套路径；否则按单键处理，避免误拆合法字段名。
    """

    parts = field_name.split(".")
    if not parts or not all(_JSON_KEY_RE.fullmatch(part) for part in parts):
        parts = [field_name]
    expression = item_column
    for part in parts:
        expression = expression[part]
    return expression


def _typed_expression(expression: Any, data_type: str) -> Any:
    canonical = _canonical_type(data_type)
    if canonical in {"text", "array"}:
        return expression
    if canonical == "json":
        # 让比较/排序的绑定参数按 JSONB 编码；本地表的 json 列也能安全比较。
        return cast(expression, JSONB)
    cast_type = _CAST_TYPES.get(canonical)
    if cast_type is None:
        return expression
    return cast(expression, cast_type)


def _source_primary_key_expression(
    *,
    dataset: CatalogDataset,
    table_expr: Any,
    name: str,
) -> Any:
    """物理主键表达式。用于 keyset 分页的最终 tiebreaker。"""

    if dataset.source_kind == "apify_platform":
        if name not in APIFY_ITEM_COLUMNS:
            raise AbiQueryValidationError("abi_order_column_not_allowed")
        return table_expr.c[quoted_name(name, True)]
    if dataset.source_kind == "local_table":
        source_table = _bare_source_table(dataset.source_table or "")
        if name not in LOCAL_TABLE_COLUMNS.get(source_table, frozenset()):
            raise AbiQueryValidationError("abi_order_column_not_allowed")
        return table_expr.c[quoted_name(name, True)]
    if dataset.source_kind == "upload":
        if name not in UPLOAD_INTERNAL_COLUMNS:
            raise AbiQueryValidationError("abi_order_column_not_allowed")
        return table_expr.c[quoted_name(name, True)]
    raise AbiQueryValidationError("abi_source_kind_not_supported")


def _default_order_names(dataset: CatalogDataset) -> tuple[str, ...]:
    if dataset.source_kind == "apify_platform":
        return ("item_index",)
    if dataset.source_kind == "local_table":
        source_table = _bare_source_table(dataset.source_table or "")
        keys = LOCAL_TABLE_PRIMARY_KEYS.get(source_table)
        if not keys:
            raise AbiQueryValidationError("abi_source_table_not_allowed")
        return keys
    if dataset.source_kind == "upload":
        return ("__abi_row",)
    raise AbiQueryValidationError("abi_source_kind_not_supported")


# ---------------------------------------------------------------- 过滤表达式


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符。反斜杠自身必须先转义。"""

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_comparison(expression: Any, item: AbiFilter, data_type: str) -> Any:
    """把白名单 op 映射成 SQLAlchemy 表达式。"""

    canonical = _canonical_type(data_type)
    if item.op == "is_null":
        return expression.is_(None)
    if item.op == "not_null":
        return expression.is_not(None)
    if item.op in {"contains", "starts_with", "ends_with"}:
        if canonical != "text":
            raise AbiQueryValidationError("abi_filter_op_type_mismatch")
        pattern = _escape_like(str(item.value))
        if item.op == "contains":
            pattern = f"%{pattern}%"
        elif item.op == "starts_with":
            pattern = f"{pattern}%"
        else:
            pattern = f"%{pattern}"
        return expression.like(pattern, escape="\\")
    if item.op in {"in", "not_in"}:
        raw_values = item.value
        if not isinstance(raw_values, (list, tuple, set, frozenset)):
            raise AbiQueryValidationError("abi_filter_value_invalid")
        values = [
            _coerce_filter_value(value, data_type) for value in raw_values
        ]
        return expression.in_(values) if item.op == "in" else expression.not_in(values)
    if item.op == "between":
        bounds = item.value
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise AbiQueryValidationError("abi_filter_value_invalid")
        low, high = bounds
        return expression.between(
            _coerce_filter_value(low, data_type),
            _coerce_filter_value(high, data_type),
        )

    value = _coerce_filter_value(item.value, data_type)
    if item.op == "eq":
        if value is None:
            return expression.is_(None)
        return expression == value
    if item.op == "ne":
        if value is None:
            return expression.is_not(None)
        return expression != value
    if item.op == "gt":
        return expression > value
    if item.op == "gte":
        return expression >= value
    if item.op == "lt":
        return expression < value
    if item.op == "lte":
        return expression <= value
    raise AbiQueryValidationError("abi_filter_op_not_allowed")


def _keyset_condition(
    key_expressions: Sequence[Any],
    last_key: Sequence[object],
    order_dir: str,
) -> Any:
    """构造 NULLS LAST 语义下的 keyset 条件。

    所有排序列统一按 NULLS LAST 排序。对某一位：
    - 游标值为 NULL 时，该位已无可排在其后的非空值；
    - 其余情况按 asc/desc 比较，并把前面各位固定为相等。
    """

    terms: list[Any] = []
    equal_prefix: list[Any] = []
    for index, expression in enumerate(key_expressions):
        value = last_key[index]
        if value is None:
            equal_prefix.append(expression.is_(None))
            continue
        if order_dir == "desc":
            # DESC 也统一 NULLS LAST：非空值之后紧跟全部 NULL 行。
            greater = or_(expression < value, expression.is_(None))
        else:
            greater = or_(expression > value, expression.is_(None))
        terms.append(and_(*equal_prefix, greater))
        equal_prefix.append(expression == value)
    if not terms:
        return None
    return or_(*terms)


# ---------------------------------------------------------------- 查询计划


async def _resolve_dataset_for_query(
    session: AsyncSession,
    dataset: CatalogDataset | uuid.UUID | str,
    *,
    workspace_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    min_role: str,
) -> CatalogDataset:
    """把 build_query 的第一个参数统一成已校验的目录行。"""

    if isinstance(dataset, CatalogDataset):
        if (workspace_id is None) != (user_id is None):
            raise AbiQueryValidationError("abi_access_context_required")
        if workspace_id is not None and user_id is not None:
            authorized, _grant = await require_dataset_access(
                session,
                dataset_id=dataset.id,
                workspace_id=workspace_id,
                user_id=user_id,
                min_role=min_role,
            )
            return authorized
        # 调用方已经通过 require_dataset_access 解析过数据集；这里保留
        # 这一分支是为了让 build_query 仍可作为纯查询构造器被复用。
        return dataset
    if workspace_id is None or user_id is None:
        raise AbiQueryValidationError("abi_access_context_required")
    if isinstance(dataset, str):
        by_slug = await load_dataset_by_slug(
            session, slug=dataset, workspace_id=workspace_id
        )
        if by_slug is None:
            raise AbiDatasetNotFound()
        dataset_id = by_slug.id
    else:
        dataset_id = dataset
    authorized, _grant = await require_dataset_access(
        session,
        dataset_id=dataset_id,
        workspace_id=workspace_id,
        user_id=user_id,
        min_role=min_role,
    )
    return authorized


async def prepare_query(
    session: AsyncSession,
    dataset: CatalogDataset,
    columns: Sequence[str] | None = None,
    filters: Sequence[object] | None = None,
    order_by: str | Sequence[str] | None = None,
    order_dir: str = "asc",
    limit: int | None = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    *,
    user_id: uuid.UUID | None = None,
) -> AbiQueryPlan:
    """校验列/过滤/排序并构造 SELECT。导出服务也复用这里。"""

    if limit is not None and not 1 <= limit <= MAX_PAGE_SIZE:
        raise AbiQueryValidationError("abi_query_limit_invalid")
    normalized_dir = _normalize_order_dir(order_dir)
    normalized_filters = normalize_filters(filters)
    column_rows = await load_dataset_columns(session, dataset.id)
    if not column_rows:
        raise AbiQueryValidationError("abi_dataset_has_no_columns")
    by_name = {row.column_name: row for row in column_rows}

    if columns:
        requested = _dedupe_columns([str(name) for name in columns])
    else:
        requested = tuple(row.column_name for row in column_rows)
    if not requested:
        raise AbiQueryValidationError("abi_dataset_has_no_columns")
    for name in requested:
        row = by_name.get(name)
        if row is None:
            raise AbiQueryValidationError("abi_column_not_registered")
        _validate_registered_column(dataset=dataset, column=row)
    if dataset.source_kind == "upload":
        # 上传表的物理列由全部 dataset_column 构成，不能只校验被选中的列。
        for row in column_rows:
            _validate_registered_column(dataset=dataset, column=row)

    # ---- 数据源与不可移除的数据集条件
    dataset_column_names = tuple(row.column_name for row in column_rows)
    if dataset.source_kind == "apify_platform":
        table_expr = _APIFY_ITEM
        base_conditions: list[Any] = [
            table_expr.c[quoted_name("dataset_id", True)] == _apify_dataset_id(dataset)
        ]
    elif dataset.source_kind == "local_table":
        table_expr = _local_table(dataset.source_table or "")
        if not dataset.origin:
            # 本地 raw 表没有 workspace_id；origin 是唯一的租户内来源隔离键。
            # 没有 origin 就拒绝，避免两个 workspace 注册同一张表后互相看见。
            raise AbiQueryValidationError("abi_dataset_origin_required")
        base_conditions = [
            table_expr.c[quoted_name("origin", True)] == dataset.origin
        ]
    elif dataset.source_kind == "upload":
        table_expr = _upload_table(dataset, dataset_column_names)
        base_conditions = [
            table_expr.c[quoted_name("__abi_version", True)] == dataset.version
        ]
    else:
        raise AbiQueryValidationError("abi_source_kind_not_supported")

    # ---- 过滤器
    policies = await load_field_policies(session, dataset.id)
    conditions: list[Any] = list(base_conditions)
    for item in normalized_filters:
        row = by_name.get(item.column)
        if row is None:
            raise AbiQueryValidationError("abi_column_not_registered")
        _validate_registered_column(dataset=dataset, column=row)
        if not row.filterable:
            raise AbiQueryValidationError("abi_column_not_filterable")
        if pii_class_for(policies, item.column) == "secret":
            # secret 字段不能做等值/模糊探测，否则过滤结果就是明文预言机。
            raise AbiQueryValidationError("abi_filter_on_secret_denied")
        expression = _column_expression(
            dataset=dataset, table_expr=table_expr, column=row
        )
        expression = _typed_expression(expression, row.data_type)
        conditions.append(_build_comparison(expression, item, row.data_type))

    # ---- 排序与 keyset tiebreaker
    explicit_order = _normalize_order_names(order_by)
    order_names: list[str] = []
    key_expressions: list[Any] = []
    for name in explicit_order:
        row = by_name.get(name)
        if row is None:
            raise AbiQueryValidationError("abi_order_column_not_registered")
        _validate_registered_column(dataset=dataset, column=row)
        if not row.sortable:
            raise AbiQueryValidationError("abi_column_not_sortable")
        if pii_class_for(policies, name) == "secret":
            # 排序结果同样是预言机：secret 列不允许出现在 ORDER BY。
            raise AbiQueryValidationError("abi_order_on_secret_denied")
        if _canonical_type(row.data_type) in {"json", "array"}:
            raise AbiQueryValidationError("abi_order_by_json_unsupported")
        order_names.append(name)
        key_expressions.append(
            _typed_expression(
                _column_expression(dataset=dataset, table_expr=table_expr, column=row),
                row.data_type,
            )
        )

    for name in _default_order_names(dataset):
        if name in order_names:
            continue
        order_names.append(name)
        key_expressions.append(
            _source_primary_key_expression(
                dataset=dataset, table_expr=table_expr, name=name
            )
        )

    columns_hash = _columns_fingerprint(requested)
    filters_hash = _filters_fingerprint(normalized_filters)

    # ---- 游标
    condition = and_(*conditions) if conditions else None
    if cursor:
        if limit is None:
            raise AbiQueryValidationError("abi_cursor_without_limit")
        last_key = decode_cursor(
            cursor,
            dataset_id=dataset.id,
            user_id=user_id,
            columns_hash=columns_hash,
            filters_hash=filters_hash,
            order_names=order_names,
            order_dir=normalized_dir,
        )
        keyset = _keyset_condition(key_expressions, last_key, normalized_dir)
        if keyset is not None:
            condition = and_(condition, keyset) if condition is not None else keyset

    # ---- SELECT 表达式。排序列可能不在返回列里，用 __abi_key_i 隐藏标签。
    selected: list[Any] = []
    for name in requested:
        row = by_name[name]
        expression = _column_expression(
            dataset=dataset, table_expr=table_expr, column=row
        )
        if dataset.source_kind == "apify_platform":
            # JSONB 字段的 ->> 结果是 text；按 dataset_column 的声明类型
            # 转回数字/时间。本地表与上传表保留物理列的原生类型。
            expression = _typed_expression(expression, row.data_type)
        selected.append(
            expression.label(quoted_name(name, True))
        )
    for index, expression in enumerate(key_expressions):
        selected.append(expression.label(f"__abi_key_{index}"))

    statement = select(*selected).select_from(table_expr)
    if condition is not None:
        statement = statement.where(condition)
    order_clauses = [
        expression.desc().nulls_last()
        if normalized_dir == "desc"
        else expression.asc().nulls_last()
        for expression in key_expressions
    ]
    statement = statement.order_by(*order_clauses)
    if limit is not None:
        # 多取一行用于判断 has_more，不把 off-by-one 推给路由。
        statement = statement.limit(limit + 1)

    pii_classes = {
        name: pii_class_for(policies, name) for name in requested
    }
    mask_rules = {name: mask_rule_for(policies, name) for name in requested}
    masked_columns = tuple(
        name for name in requested if pii_classes[name] in PII_MASKED_CLASSES
    )
    return AbiQueryPlan(
        statement=statement,
        columns=requested,
        order_names=tuple(order_names),
        order_dir=normalized_dir,
        columns_hash=columns_hash,
        filters_hash=filters_hash,
        pii_classes=pii_classes,
        mask_rules=mask_rules,
        masked_columns=masked_columns,
    )


async def _enter_read_only(session: AsyncSession) -> None:
    """开只读事务并设置超时。

    若调用方已经开了事务，``SET TRANSACTION`` 会报错。这时只设
    statement_timeout，避免把异常抛给调用方；正常路由路径都是干净会话。
    """

    if not session.in_transaction():
        await session.execute(text("SET TRANSACTION READ ONLY"))
    await session.execute(
        text(f"SET LOCAL statement_timeout = '{QUERY_TIMEOUT}'")
    )
    await session.execute(
        text(
            "SET LOCAL idle_in_transaction_session_timeout = "
            f"'{IDLE_TRANSACTION_TIMEOUT_MS}ms'"
        )
    )


async def build_query(
    session: AsyncSession,
    dataset: CatalogDataset | uuid.UUID | str,
    columns: Sequence[str] | None = None,
    filters: Sequence[object] | None = None,
    order_by: str | Sequence[str] | None = None,
    order_dir: str = "asc",
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    *,
    workspace_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    min_role: str = "viewer",
) -> AbiQueryPage:
    """查询一页数据。

    授权：``dataset`` 是 UUID 时，``workspace_id`` 与 ``user_id`` 必填，
    本函数会做 workspace + grant 双条件校验；``dataset`` 是目录行对象时，
    若同时给出上下文也会再次校验。路由层应先调用
    :func:`require_dataset_access`，不要依赖本函数的可选参数。

    事务：**调用方持有**。本函数不 commit、不 rollback。独立事务请用
    :func:`run_query_page`，它包一层只读会话。
    """

    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise AbiQueryValidationError("abi_query_limit_invalid")
    await _enter_read_only(session)
    resolved = await _resolve_dataset_for_query(
        session,
        dataset,
        workspace_id=workspace_id,
        user_id=user_id,
        min_role=min_role,
    )
    plan = await prepare_query(
        session,
        resolved,
        columns=columns,
        filters=filters,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
        cursor=cursor,
        user_id=user_id,
    )
    result = await session.execute(plan.statement)
    mappings = result.mappings().all()

    has_more = len(mappings) > limit
    visible = mappings[:limit]
    rows: list[dict[str, object]] = []
    for mapping in visible:
        raw_row = {name: mapping[name] for name in plan.columns}
        rows.append(
            mask_row(raw_row, plan.pii_classes, plan.mask_rules)
        )

    next_cursor: str | None = None
    if has_more and visible:
        last = visible[-1]
        last_key = [
            last[f"__abi_key_{index}"]
            for index in range(len(plan.order_names))
        ]
        next_cursor = encode_cursor(
            dataset_id=resolved.id,
            user_id=user_id,
            columns_hash=plan.columns_hash,
            filters_hash=plan.filters_hash,
            order_names=plan.order_names,
            order_dir=plan.order_dir,
            last_key=last_key,
        )
    # 不 commit、不 rollback：事务归调用方。
    # 原来在这里 commit 会让「只读查询」结束掉调用方的事务，
    # 调用方后续再做写入时会落在一个意外的新事务里。
    return AbiQueryPage(
        columns=plan.columns,
        rows=rows,
        next_cursor=next_cursor,
        has_more=has_more,
        masked_columns=plan.masked_columns,
        pii_classes=plan.pii_classes,
    )


# ---------------------------------------------------------------- 独立只读会话


def _default_session_factory() -> sessionmaker[AsyncSession]:
    """延迟取全局工厂。

    不在模块顶层 import ``async_session_factory`` 有两个原因：
    1. 会形成 core.database -> ... -> abi_query 的循环风险；
    2. 测试要替换工厂时，顶层绑定会把替换结果锁死。
    """
    from data_intelligence_hub.core.database import async_session_factory

    return async_session_factory


@asynccontextmanager
async def read_only_session(
    *,
    statement_timeout: str = QUERY_TIMEOUT,
    session_factory: sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[AsyncSession]:
    """开一个只读事务的会话。

    为什么要独立会话而不是复用请求会话：
    - ``SET TRANSACTION READ ONLY`` 只能在事务开始前设置。请求会话往往已经
      因为鉴权查询开了事务，在那里设置只会报错或者被静默跳过。
    - 导出要跑 ``statement_timeout='300s'``，而普通查询是 15s。同一个会话
      改超时会影响同请求的其它语句。

    ``session_factory`` 可注入：测试用 ``dependency_overrides`` 换掉的引擎
    必须能影响到这里，否则测试代码会打到真实库上。
    """
    factory = session_factory or _default_session_factory()
    async with factory() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        await session.execute(text(f"SET LOCAL statement_timeout = '{statement_timeout}'"))
        await session.execute(
            text(
                "SET LOCAL idle_in_transaction_session_timeout = "
                f"'{IDLE_TRANSACTION_TIMEOUT_MS}ms'"
            )
        )
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()


async def run_query_page(
    *,
    dataset_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    columns: Sequence[str] | None = None,
    filters: Sequence[object] | None = None,
    order_by: str | Sequence[str] | None = None,
    order_dir: str = "asc",
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    min_role: str = "viewer",
    session_factory: sessionmaker[AsyncSession] | None = None,
) -> AbiQueryPage:
    """在独立只读事务里查询一页。这是查询端点的正式入口。

    与直接调 :func:`build_query` 的差别：本函数自己开、自己关事务，
    调用方不需要关心事务边界。
    """
    async with read_only_session(session_factory=session_factory) as session:
        return await build_query(
            session,
            dataset_id,
            columns=columns,
            filters=filters,
            order_by=order_by,
            order_dir=order_dir,
            limit=limit,
            cursor=cursor,
            workspace_id=workspace_id,
            user_id=user_id,
            min_role=min_role,
        )

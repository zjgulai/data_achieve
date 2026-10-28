"""ABI 外部数据中心三个 schema 的 ORM 模型。

覆盖迁移 ``202610280060`` 到 ``202610280063`` 建的 42 张表：

- ``meta``：账号、token、actor 注册、摄取作业、分区登记与审计，共 11 张。
- ``raw``：Apify 清单与条目 3 张、本地历史表 14 张、装载支撑 2 张，共 19 张。
- ``abi``：目录、字段策略、授权、上传、导出与统计，共 12 张。

迁移里另有 6 个预建分区（``raw.apify_item`` 5 个、``meta.audit_log`` 1 个）。
分区是父表的物理分片，不是独立表，因此不单独建模。分区由
``meta.ensure_partitions()`` 与 ``meta.partition_registry`` 维护。

为什么继承 ``AbiBase`` 而不是 ``Base``：见 ``models/abi_base.py``。
``Base.metadata`` 被 80 多个测试用 ``create_all`` 建到 sqlite，
带 schema 的表会让那批测试全部报 unknown database。

列名、类型、可空性与默认值逐列照迁移写，不照早期方案文档写。已知差异：
``abi`` 层没有方案里的 ``item_current`` / ``record`` / ``upload_row``；
本地表的公共列是迁移 ``_common_cols()`` 的 6 列，不含方案里的 ``src_pk``。

约定：

- uuid 主键用 ``default=uuid.uuid4``。迁移里除 ``meta.audit_log`` 外都没有
  ``server_default``；``audit_log.id`` 照迁移用 ``gen_random_uuid()``。
- 单列唯一约束写 ``unique=True``，命名约定生成的约束名与迁移逐字一致。
  多列唯一约束在 ``__table_args__`` 里显式写迁移中的名字。
- CHECK 约束名用 ``conv()`` 包裹，阻止命名约定再叠一层表名前缀。
- ``JSON`` 与 ``JSONB`` 分开：迁移写 ``sa.JSON()`` 的列用 ``JSON``，
  迁移写 ``jsonb`` 的列用 PostgreSQL ``JSONB``。
- 来源载荷形状不稳定的 JSON 列标成 ``Any``，模型层不替来源假设结构。
- 模型不定义 ``relationship``。跨 schema 的懒加载最容易绕过租户过滤，
  ABI 的取数一律由 repository 显式 join，并带上 ``workspace_id`` 条件。

跨 metadata 外键：``abi`` 有 6 张表的外键指向 ``workspaces.id`` / ``users.id``，
这两张表属于 ``Base.metadata``。SQLAlchemy 的字符串外键只能在同一 MetaData 内
解析，否则 ``session.flush()`` 的依赖排序会抛 ``NoReferencedTableError``。
因此本模块在 ``AbiBase.metadata`` 里登记两张只含 ``id`` 的占位表。占位表只服务
外键解析：ABI 的 DDL 只由迁移负责，``AbiBase.metadata`` 不用于 ``create_all``。
如果将来把 ``AbiBase.metadata`` 接进 alembic autogenerate，必须排除这两张占位表，
否则会生成 drop_table 噪声。

分层与租户（安全要求，端点由后续任务实现）：

- ``meta`` / ``raw`` 是内部采集层，没有 ``workspace_id``。例外是
  ``raw.apify_dataset.workspace_id`` 与 ``raw.pmo_collection_record.workspace_id``，
  两者可空，用于把来源挂到租户。
- ``abi`` 每张表都带 ``workspace_id``。端点必须同时按 ``workspace_id`` 与
  ``access_grant`` 过滤，无 grant 一律 403。
- 角色顺序 viewer < editor < publisher < admin，admin 不是万能 bypass。
- ``abi.field_policy.pii_class`` 默认 ``unknown``。导出与视图默认拒绝
  ``unknown``；遮罩在 API 序列化层做，不在前端做。
- 查询与导出的列名只能取自服务端物理列 allowlist，不能接受客户端 SQL。

分区表 ``raw.apify_item``：主键是 ``(collected_month, dataset_id, item_index)``。
``collected_month`` 是分区键，取 dataset 的 ``createdAt`` 月首，不是入仓日。
同一 dataset 在任何日期重抓都落同一分区，主键天然去重。写入必须显式给
``collected_month``：PostgreSQL 不会替你补分区键。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from data_intelligence_hub.models.abi_base import AbiBase

# ---------------------------------------------------------------------------
# 跨 metadata 外键的占位表
#
# ``workspaces`` / ``users`` 在 ``Base.metadata`` 里。SQLAlchemy 的字符串外键
# 只在同一 MetaData 内解析，跨 MetaData 会让 ``session.flush()`` 的表依赖排序
# 抛 ``NoReferencedTableError``。这里登记两张只含主键的占位表，仅供外键解析。
# ---------------------------------------------------------------------------
Table("workspaces", AbiBase.metadata, Column("id", Uuid(as_uuid=True), primary_key=True))
Table("users", AbiBase.metadata, Column("id", Uuid(as_uuid=True), primary_key=True))

# ---------------------------------------------------------------------------
# CHECK 约束的取值集合
#
# 约束名用 ``conv()`` 包裹后传给 CheckConstraint。命名约定里有
# ``ck_%(table_name)s_%(constraint_name)s``，不包裹会变成
# ``ck_apify_token_ck_apify_token_status``。
# ---------------------------------------------------------------------------
_APIFY_TOKEN_STATUS_CHECK = "status IN ('active', 'invalid', 'retired')"
_ACTOR_REGISTRY_SOURCE_CHECK = (
    "source IN ('catalog', 'run_input', 'task_log', 'field_signature', 'manual')"
)
_INGEST_JOB_STATE_CHECK = (
    "state IN ('queued', 'running', 'succeeded', 'failed', 'dead', 'skipped')"
)
_INGEST_RUN_MODE_CHECK = "mode IN ('sweep', 'incremental', 'backfill', 'repair')"
_ACTOR_REGISTRY_CONFIDENCE_CHECK = "confidence IN ('high', 'medium', 'low', 'unknown')"
_INGEST_RUN_STATUS_CHECK = "status IN ('running', 'succeeded', 'failed', 'aborted')"
_APIFY_DATASET_STATUS_CHECK = (
    "status IN ('active', 'complete', 'expired', 'missing', 'partial', 'error')"
)
_PII_CLASS_CHECK = "pii_class IN ('unknown', 'none', 'quasi', 'direct', 'secret')"
_APIFY_ITEM_STATUS_CHECK = "item_status IN ('content', 'empty', 'error')"
_LOAD_FILE_STATUS_CHECK = "status IN ('pending', 'loaded', 'partial', 'failed')"
_AMAZON_REVIEW_RATING_CHECK = "rating IS NULL OR (rating >= 1 AND rating <= 5)"
_CATALOG_SOURCE_KIND_CHECK = "source_kind IN ('apify_platform', 'local_table', 'upload')"
_ACCESS_GRANT_ROLE_CHECK = "role IN ('viewer', 'editor', 'publisher', 'admin')"
_UPLOAD_BATCH_MODE_CHECK = "mode IN ('append', 'upsert', 'replace')"
_UPLOAD_BATCH_STATUS_CHECK = (
    "status IN ('pending', 'uploaded', 'validating', 'committed', 'failed', 'expired')"
)
_EXPORT_JOB_FORMAT_CHECK = "format IN ('csv', 'xlsx', 'jsonl')"
_EXPORT_JOB_STATUS_CHECK = (
    "status IN ('queued', 'awaiting_approval', 'running', 'succeeded', "
    "'failed', 'expired', 'rejected')"
)

# ---------------------------------------------------------------------------
# 角色序
#
# 角色顺序 viewer < editor < publisher < admin。admin 只是某个 dataset 上的
# 最高角色，不是 workspace 级万能 bypass：取数仍要同时匹配 workspace_id 与 grant。
# 服务层与路由层都用 ``role_rank`` 比较，不在各处再维护一份顺序。
# ---------------------------------------------------------------------------
ABI_ROLE_ORDER: dict[str, int] = {
    "viewer": 0,
    "editor": 1,
    "publisher": 2,
    "admin": 3,
}

# 未知角色返回的值。必须小于 viewer，调用方用 ``role_rank(min_role) < 0``
# 判断入参是否合法，用 ``role_rank(grant.role) < minimum`` 拒绝脏数据。
_UNKNOWN_ROLE_RANK = -1


def role_rank(role: str) -> int:
    """返回角色等级，未知角色返回 -1。

    ``-1`` 比 viewer 还低，因此未知角色既不能通过最小角色校验，
    也不会因为比较运算被误判为合法。fail-closed，不做兜底提升。
    """
    return ABI_ROLE_ORDER.get(role, _UNKNOWN_ROLE_RANK)


class LocalRawProvenanceMixin:
    """本地原始表共用的溯源列，对应迁移 062 的 ``_common_cols()``。

    迁移把这 6 列写在每张表的最后，mixin 复制到子类时也排在子类自有列之后，
    与迁移的列顺序一致。``src_pk`` 只出现在早期方案里，没有进迁移，故不写。

    主键含这三列的 4 张表（``apify_tweet`` / ``probe_*``）在 ``__table_args__``
    里用 ``PrimaryKeyConstraint`` 声明复合主键，不在 mixin 上标 ``primary_key``，
    因为 ``si_*`` 表用的是自己的主键列。
    """

    origin: Mapped[str] = mapped_column(Text, nullable=False)
    load_batch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    src_file: Mapped[str] = mapped_column(Text, nullable=False)
    src_row_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("clock_timestamp()"),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# meta：内部采集层
# ---------------------------------------------------------------------------


class ApifyAccount(AbiBase):
    """一个 Apify 账号。

    限流按账号计算。实测 5 个 token 只对应 2 个账号，所以 token 不能当限流主体。
    """

    __tablename__ = "apify_account"
    __table_args__ = {"schema": "meta"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    label: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    apify_user_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    plan: Mapped[str | None] = mapped_column(Text)
    data_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("31")
    )
    max_concurrency: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("8")
    )
    max_rps: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("8.0")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApifyToken(AbiBase):
    """Apify token 的密文行。

    明文不落库：只存 Fernet 密文、sha256 指纹与前四位。
    没有 ``cooldown`` 状态：429 换 token 无效，把 token 打进冷却只会制造抖动。
    """

    __tablename__ = "apify_token"
    __table_args__ = (
        UniqueConstraint("account_id", "label", name="uq_apify_token_account_id_label"),
        CheckConstraint(_APIFY_TOKEN_STATUS_CHECK, name=conv("ck_apify_token_status")),
        Index("ix_apify_token_account_status", "account_id", "status"),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meta.apify_account.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    token_fingerprint: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False, unique=True
    )
    token_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'abi.fernet.v1'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    last_error_code: Mapped[int | None] = mapped_column(Integer)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApifyTokenDaily(AbiBase):
    """按账号按日的用量记账，不是按 token 记账。"""

    __tablename__ = "apify_token_daily"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "usage_date", name="uq_apify_token_daily_account_id_usage_date"
        ),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meta.apify_account.id", ondelete="CASCADE"), nullable=False
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rate_limited: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    items_fetched: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class ActorRegistry(AbiBase):
    """``actor_id`` 到平台、对象类型与端点类型的映射。

    ``actor_id`` 不能当归因主键：同一个 actor 会服务多个 endpoint。
    """

    __tablename__ = "actor_registry"
    __table_args__ = (
        CheckConstraint(_ACTOR_REGISTRY_SOURCE_CHECK, name=conv("ck_actor_registry_source")),
        CheckConstraint(
            _ACTOR_REGISTRY_CONFIDENCE_CHECK, name=conv("ck_actor_registry_confidence")
        ),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    actor_name: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_type: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    license: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    deprecated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ActorSchemaVersion(AbiBase):
    """actor 的字段集版本，用于字段漂移检测。"""

    __tablename__ = "actor_schema_version"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "schema_hash", name="uq_actor_schema_version_actor_id_schema_hash"
        ),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_type: Mapped[str | None] = mapped_column(Text)
    input_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    schema_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    field_names: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    # 与 field_names 逐位对应，元素是类型名。
    field_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    field_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sample_dataset_id: Mapped[str | None] = mapped_column(Text)


class IngestJob(AbiBase):
    """摄取作业队列。

    ``lease_version`` 是 fencing 令牌。租约过期后两个 worker 可能同时持锁，
    写入方必须带 ``WHERE lease_version = :mine``。
    """

    __tablename__ = "ingest_job"
    __table_args__ = (
        CheckConstraint(_INGEST_JOB_STATE_CHECK, name=conv("ck_ingest_job_state")),
        Index("ix_ingest_job_state_not_before", "state", "not_before"),
        Index("ix_ingest_job_account_state", "account_id", "state"),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    target_date: Mapped[date | None] = mapped_column(Date)
    dataset_id: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("6")
    )
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    last_error_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestRun(AbiBase):
    """一次 sweep 的汇总，按 ``sweep_id`` 归组。"""

    __tablename__ = "ingest_run"
    __table_args__ = (
        CheckConstraint(_INGEST_RUN_MODE_CHECK, name=conv("ck_ingest_run_mode")),
        CheckConstraint(_INGEST_RUN_STATUS_CHECK, name=conv("ck_ingest_run_status")),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sweep_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    datasets_total: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    datasets_done: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    items_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    bytes_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'running'")
    )
    tool_version: Mapped[str | None] = mapped_column(Text)
    config_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))


class ScheduleState(AbiBase):
    """每个账号一行的调度水位，不是全局一行。"""

    __tablename__ = "schedule_state"
    __table_args__ = {"schema": "meta"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meta.apify_account.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    last_target_date: Mapped[date | None] = mapped_column(Date)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sweep_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PartitionRegistry(AbiBase):
    """分区登记。``ensure_partitions()`` 建分区时同步写这一行。"""

    __tablename__ = "partition_registry"
    __table_args__ = (
        UniqueConstraint(
            "parent_table", "partition_name", name="uq_partition_registry_parent_name"
        ),
        {"schema": "meta"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parent_table: Mapped[str] = mapped_column(Text, nullable=False)
    partition_name: Mapped[str] = mapped_column(Text, nullable=False)
    range_start: Mapped[date] = mapped_column(Date, nullable=False)
    range_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeat(AbiBase):
    """worker 存活心跳。主键是 ``worker_id``，没有代理 id。"""

    __tablename__ = "worker_heartbeat"
    __table_args__ = {"schema": "meta"}

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)


class AuditLog(AbiBase):
    """审计日志。按月 RANGE 分区，主键含分区键 ``occurred_month``。"""

    __tablename__ = "audit_log"
    __table_args__ = (
        PrimaryKeyConstraint("occurred_month", "id"),
        Index("ix_audit_log_occurred_at", "occurred_at"),
        {"schema": "meta", "postgresql_partition_by": "RANGE (occurred_month)"},
    )

    occurred_month: Mapped[date] = mapped_column(Date, nullable=False)
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[str | None] = mapped_column(Text)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


# ---------------------------------------------------------------------------
# raw：Apify 原始层
# ---------------------------------------------------------------------------


class ApifyDataset(AbiBase):
    """账号内每个 dataset 一行的清单，含保留期估算。

    ``created_at`` 是 dataset 在 Apify 的创建时间；本行入库时间是
    ``created_row_at``。两者都不是 ``raw.apify_item.collected_month`` 的来源，
    后者只按 ``created_at`` 取月首。
    """

    __tablename__ = "apify_dataset"
    __table_args__ = (
        CheckConstraint(_APIFY_DATASET_STATUS_CHECK, name=conv("ck_apify_dataset_status")),
        Index("ix_apify_dataset_account_created", "account_id", "created_at"),
        Index("ix_apify_dataset_platform_type", "platform", "object_type"),
        Index(
            "ix_apify_dataset_retention",
            "retention_deadline",
            # 必须与 061 的建索引语句逐字一致，否则 compare_metadata 会报差异。
            # 谓词只排除终态：complete 的 dataset 同样会过期，用 status='active'
            # 会把已入仓但面临删除的数据集排除在风险查询之外。
            postgresql_where=text("status NOT IN ('expired', 'missing')"),
        ),
        {"schema": "raw"},
    )

    dataset_id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meta.apify_account.id"), nullable=False
    )
    run_id: Mapped[str | None] = mapped_column(Text)
    act_id: Mapped[str | None] = mapped_column(Text)
    actor_name: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'other'")
    )
    object_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    endpoint_type: Mapped[str | None] = mapped_column(Text)
    endpoint_source: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    confidence: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    dataset_name: Mapped[str | None] = mapped_column(Text)
    named: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 保留期只是估算：API 没有 expiresAt 字段，命名 dataset 永久保留。
    retention_deadline: Mapped[date | None] = mapped_column(Date)
    retention_estimated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    item_count_head: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    item_count_local: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    schema_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_batch: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    storage_path: Mapped[str | None] = mapped_column(Text)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_row_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApifyRun(AbiBase):
    """Apify 运行记录。

    ``usage_total_usd`` 只对终态 run 取值：RUNNING 的 run 费用仍在变化。
    是否可信看 ``usage_final`` 与 ``finished_at``。
    """

    __tablename__ = "apify_run"
    __table_args__ = (
        Index("ix_apify_run_act_started", "act_id", "started_at"),
        {"schema": "raw"},
    )

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meta.apify_account.id"), nullable=False
    )
    act_id: Mapped[str | None] = mapped_column(Text)
    actor_name: Mapped[str | None] = mapped_column(Text)
    build_id: Mapped[str | None] = mapped_column(Text)
    build_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    default_dataset_id: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_total_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    usage_final: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    input_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    input_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApifyItem(AbiBase):
    """Apify dataset 的原始条目。按月 RANGE 分区，只追加。

    主键是 ``(collected_month, dataset_id, item_index)``。``collected_month``
    是分区键，取 dataset 的 ``createdAt`` 月首，不是入仓日；同一 dataset 在任何
    日期重抓都落同一分区，主键天然去重。写入必须显式给 ``collected_month``。

    ``item`` 写入前必须剔除 ``\\u0000``：PostgreSQL 的 jsonb 拒绝 NUL 字节。
    """

    __tablename__ = "apify_item"
    __table_args__ = (
        PrimaryKeyConstraint("collected_month", "dataset_id", "item_index"),
        CheckConstraint("item_index >= 0", name=conv("ck_apify_item_index")),
        CheckConstraint(_PII_CLASS_CHECK, name=conv("ck_apify_item_pii")),
        CheckConstraint(_APIFY_ITEM_STATUS_CHECK, name=conv("ck_apify_item_status")),
        Index("ix_apify_item_dataset", "dataset_id", "item_index"),
        Index("ix_apify_item_platform_month", "platform", "collected_month"),
        Index("ix_apify_item_content_hash", "content_hash"),
        {"schema": "raw", "postgresql_partition_by": "RANGE (collected_month)"},
    )

    collected_month: Mapped[date] = mapped_column(Date, nullable=False)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    platform: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'other'")
    )
    object_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    item: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    pii_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    item_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'content'")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("clock_timestamp()"),
    )
    fetch_batch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)


# ---------------------------------------------------------------------------
# raw：装载支撑表
# ---------------------------------------------------------------------------


class LoadFile(AbiBase):
    """一次本地文件装载的清单。``sha256`` 唯一，用于幂等重放。"""

    __tablename__ = "load_file"
    __table_args__ = (
        CheckConstraint(_LOAD_FILE_STATUS_CHECK, name=conv("ck_load_file_status")),
        {"schema": "raw"},
    )

    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False, unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_total: Mapped[int | None] = mapped_column(Integer)
    rows_loaded: Mapped[int | None] = mapped_column(Integer)
    rows_rejected: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoadError(AbiBase):
    """装载错误。只存定位信息，不存原始值：PII 不能落进错误表。"""

    __tablename__ = "load_error"
    __table_args__ = (
        Index("ix_load_error_batch", "load_batch_id", "src_row_ordinal"),
        {"schema": "raw"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    load_batch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    src_file: Mapped[str] = mapped_column(Text, nullable=False)
    src_row_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str | None] = mapped_column(Text)
    rule_id: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# raw：本地历史表（SI duckdb）
# ---------------------------------------------------------------------------


class SiTiktokVideo(LocalRawProvenanceMixin, AbiBase):
    """SI duckdb ``dw_video_wide`` 的宽表快照。

    ``snapshot_date`` 实测 31,316 行全为 NULL，不能当时间维度。
    """

    __tablename__ = "si_tiktok_video"
    __table_args__ = (
        Index("ix_si_tiktok_video_author", "author_id"),
        {"schema": "raw"},
    )

    video_id: Mapped[str] = mapped_column(Text, primary_key=True)
    hashtag: Mapped[str | None] = mapped_column(Text)
    snapshot_date: Mapped[date | None] = mapped_column(Date)
    rank_in_tag: Mapped[int | None] = mapped_column(Integer)
    author_unique_id: Mapped[str | None] = mapped_column(Text)
    author_nickname: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[str | None] = mapped_column(Text)
    descr: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_ad: Mapped[bool | None] = mapped_column(Boolean)
    music_id: Mapped[str | None] = mapped_column(Text)
    music_title: Mapped[str | None] = mapped_column(Text)
    music_author: Mapped[str | None] = mapped_column(Text)
    play_count: Mapped[int | None] = mapped_column(BigInteger)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    snap_days: Mapped[int | None] = mapped_column(Integer)
    peak_play: Mapped[int | None] = mapped_column(BigInteger)
    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)
    play_gain_total: Mapped[int | None] = mapped_column(BigInteger)
    play_gain_daily_avg: Mapped[float | None] = mapped_column(Double)
    parse_level: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[str | None] = mapped_column(Text)
    evidence_state: Mapped[str | None] = mapped_column(Text)
    analysis_version: Mapped[str | None] = mapped_column(Text)
    summary_original: Mapped[str | None] = mapped_column(Text)
    target_audience: Mapped[str | None] = mapped_column(Text)
    hook_visual: Mapped[str | None] = mapped_column(Text)
    hook_audio: Mapped[str | None] = mapped_column(Text)
    hook_formula: Mapped[str | None] = mapped_column(Text)
    n_mechanisms: Mapped[int | None] = mapped_column(Integer)
    n_timeline_segments: Mapped[int | None] = mapped_column(Integer)
    n_transcript_segments: Mapped[int | None] = mapped_column(Integer)
    brand_borrow_n: Mapped[int | None] = mapped_column(Integer)
    brand_replace_n: Mapped[int | None] = mapped_column(Integer)
    analysis_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    has_deepread: Mapped[bool | None] = mapped_column(Boolean)
    deepread_model: Mapped[str | None] = mapped_column(Text)
    deepread_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    theme_tags: Mapped[str | None] = mapped_column(Text)
    mechanism_tags: Mapped[str | None] = mapped_column(Text)
    life_stage: Mapped[str | None] = mapped_column(Text)
    one_liner: Mapped[str | None] = mapped_column(Text)
    media_playable: Mapped[bool | None] = mapped_column(Boolean)
    media_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    comment_rows: Mapped[int | None] = mapped_column(Integer)
    comment_top_digg: Mapped[int | None] = mapped_column(BigInteger)
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class SiTiktokComment(LocalRawProvenanceMixin, AbiBase):
    """SI duckdb ``fact_video_comment`` 的评论快照。

    实测 46,953 行，不是早期方案写的 46,633 行。
    ``author_avatar`` 入库前只保留 ``scheme://host/path``，query 里的 token 已剔除。
    """

    __tablename__ = "si_tiktok_comment"
    __table_args__ = (
        Index("ix_si_tiktok_comment_video", "video_id"),
        {"schema": "raw"},
    )

    platform: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, server_default=text("'tiktok'")
    )
    video_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    comment_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    reply_count: Mapped[int | None] = mapped_column(BigInteger)
    author_handle: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[str | None] = mapped_column(Text)
    author_avatar: Mapped[str | None] = mapped_column(Text)
    liked_by_author: Mapped[bool | None] = mapped_column(Boolean)
    pinned_by_author: Mapped[bool | None] = mapped_column(Boolean)
    platform_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_tier: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(Text)
    sample_rank: Mapped[int | None] = mapped_column(Integer)


class SiTiktokHashtagSnapshot(LocalRawProvenanceMixin, AbiBase):
    """SI duckdb ``fact_tag_video_snapshot`` 的话题快照。

    实测 102,153 行，不是早期方案写的行数。
    """

    __tablename__ = "si_tiktok_hashtag_snapshot"
    __table_args__ = (
        Index("ix_si_tag_snapshot_video", "video_id"),
        Index("ix_si_tag_snapshot_date", "snapshot_date"),
        {"schema": "raw"},
    )

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hashtag_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    hashtag: Mapped[str | None] = mapped_column(Text)
    source_actor: Mapped[str | None] = mapped_column(Text)
    rank_in_tag: Mapped[int | None] = mapped_column(Integer)
    video_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    author_id: Mapped[str | None] = mapped_column(Text)
    author_unique_id: Mapped[str | None] = mapped_column(Text)
    author_nickname: Mapped[str | None] = mapped_column(Text)
    author_avatar_url: Mapped[str | None] = mapped_column(Text)
    play_count: Mapped[int | None] = mapped_column(BigInteger)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_ad: Mapped[bool | None] = mapped_column(Boolean)
    descr: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    music_id: Mapped[str | None] = mapped_column(Text)
    music_title: Mapped[str | None] = mapped_column(Text)
    music_author: Mapped[str | None] = mapped_column(Text)
    music_duration_sec: Mapped[int | None] = mapped_column(Integer)
    music_is_original: Mapped[bool | None] = mapped_column(Boolean)
    music_is_commerce: Mapped[bool | None] = mapped_column(Boolean)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class SiMetricSnapshot(LocalRawProvenanceMixin, AbiBase):
    """SI duckdb ``fact_metric_snapshot`` 的指标快照。主键含来源 actor。"""

    __tablename__ = "si_metric_snapshot"
    __table_args__ = {"schema": "raw"}

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    platform_code: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    object_id: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    source_actor: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    run_id: Mapped[str | None] = mapped_column(Text)


class SiMusicPlatformSnapshot(LocalRawProvenanceMixin, AbiBase):
    """SI 音乐平台快照，按 ``(snapshot_date, music_id)`` 唯一。

    列与顺序对齐迁移 062；主键是复合键，不能只挂 ``id``——迁移里没有这一列。
    """

    __tablename__ = "si_music_platform_snapshot"
    __table_args__ = (
        PrimaryKeyConstraint("snapshot_date", "music_id"),
        {"schema": "raw"},
    )

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    music_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_count: Mapped[int | None] = mapped_column(BigInteger)
    platform_title: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    source: Mapped[str | None] = mapped_column(Text)


class SiAuthorVideoSnapshot(LocalRawProvenanceMixin, AbiBase):
    """SI 达人视频快照，按 ``(snapshot_date, video_id)`` 唯一。"""

    __tablename__ = "si_author_video_snapshot"
    __table_args__ = (
        PrimaryKeyConstraint("snapshot_date", "video_id"),
        {"schema": "raw"},
    )

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    account_handle: Mapped[str | None] = mapped_column(Text)
    brand_key: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    sec_uid: Mapped[str | None] = mapped_column(Text)
    rank_in_account: Mapped[int | None] = mapped_column(Integer)
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[str | None] = mapped_column(Text)
    author_unique_id: Mapped[str | None] = mapped_column(Text)
    author_nickname: Mapped[str | None] = mapped_column(Text)
    author_avatar_url: Mapped[str | None] = mapped_column(Text)
    play_count: Mapped[int | None] = mapped_column(BigInteger)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_ad: Mapped[bool | None] = mapped_column(Boolean)
    descr: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[float | None] = mapped_column(Double)


class SiSocialPost(LocalRawProvenanceMixin, AbiBase):
    """SI 社媒帖子宽表，主键是 ``post_id``。

    这张表列最多（43 列），是全库最容易与迁移漂移的地方；
    契约测试会逐列比对，改动迁移时必须同步这里。
    """

    __tablename__ = "si_social_post"
    __table_args__ = {"schema": "raw"}

    post_id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform_code: Mapped[str | None] = mapped_column(Text)
    account_handle: Mapped[str | None] = mapped_column(Text)
    account_type: Mapped[str | None] = mapped_column(Text)
    competitor_brand: Mapped[str | None] = mapped_column(Text)
    creator_id: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    bgm_title: Mapped[str | None] = mapped_column(Text)
    bgm_author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    like_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    engagement_rate: Mapped[float | None] = mapped_column(Double)
    view_velocity_24h: Mapped[int | None] = mapped_column(BigInteger)
    is_viral_flag: Mapped[bool | None] = mapped_column(Boolean)
    sentiment_label: Mapped[str | None] = mapped_column(Text)
    topics: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    pain_points: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_paid_collab: Mapped[bool | None] = mapped_column(Boolean)
    brand_mentions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    country_code: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    is_processed: Mapped[bool | None] = mapped_column(Boolean)
    content_quality_score: Mapped[float | None] = mapped_column(Double)
    sev_level: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    traffic_type: Mapped[str | None] = mapped_column(Text)
    is_cross_region: Mapped[bool | None] = mapped_column(Boolean)
    cover_url: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    completion_rate: Mapped[float | None] = mapped_column(Double)
    source_tier: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str | None] = mapped_column(Text)
    traffic_basis: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# raw：探针与缓存表
# ---------------------------------------------------------------------------


class ApifyTweet(LocalRawProvenanceMixin, AbiBase):
    """pr-agent ``apify_cache`` 的推文快照。

    ``is_no_results`` 标 76 条 ``{"noResults": true}`` 哨兵行：保留而不是丢弃。
    """

    __tablename__ = "apify_tweet"
    __table_args__ = (
        PrimaryKeyConstraint("origin", "src_file", "src_row_ordinal"),
        Index("ix_apify_tweet_id", "tweet_id", "snapshot_date"),
        {"schema": "raw"},
    )

    snapshot_date: Mapped[date | None] = mapped_column(Date)
    tweet_id: Mapped[str | None] = mapped_column(Text)
    conversation_id: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[str | None] = mapped_column(Text)
    author_user_name: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(Text)
    author_followers: Mapped[int | None] = mapped_column(BigInteger)
    author_verified: Mapped[bool | None] = mapped_column(Boolean)
    author_description: Mapped[str | None] = mapped_column(Text)
    author_location: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    full_text: Mapped[str | None] = mapped_column(Text)
    lang: Mapped[str | None] = mapped_column(Text)
    like_count: Mapped[int | None] = mapped_column(Integer)
    reply_count: Mapped[int | None] = mapped_column(Integer)
    retweet_count: Mapped[int | None] = mapped_column(Integer)
    quote_count: Mapped[int | None] = mapped_column(Integer)
    bookmark_count: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    is_reply: Mapped[bool | None] = mapped_column(Boolean)
    is_quote: Mapped[bool | None] = mapped_column(Boolean)
    is_retweet: Mapped[bool | None] = mapped_column(Boolean)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean)
    possibly_sensitive: Mapped[bool | None] = mapped_column(Boolean)
    in_reply_to_id: Mapped[str | None] = mapped_column(Text)
    in_reply_to_user_id: Mapped[str | None] = mapped_column(Text)
    in_reply_to_username: Mapped[str | None] = mapped_column(Text)
    quoted_id: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    urls: Mapped[Any | None] = mapped_column(JSON)
    media: Mapped[Any | None] = mapped_column(JSON)
    is_no_results: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    raw: Mapped[Any | None] = mapped_column(JSON)


class ProbeInstagramPost(LocalRawProvenanceMixin, AbiBase):
    """Instagram 探针结果。``short_code`` 唯一。"""

    __tablename__ = "probe_instagram_post"
    __table_args__ = (
        PrimaryKeyConstraint("origin", "src_file", "src_row_ordinal"),
        {"schema": "raw"},
    )

    probe_date: Mapped[date | None] = mapped_column(Date)
    short_code: Mapped[str | None] = mapped_column(Text, unique=True)
    post_id: Mapped[str | None] = mapped_column(Text)
    post_type: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    input_url: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(Text)
    owner_username: Mapped[str | None] = mapped_column(Text)
    owner_full_name: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    likes_count: Mapped[int | None] = mapped_column(Integer)
    comments_count: Mapped[int | None] = mapped_column(Integer)
    video_view_count: Mapped[int | None] = mapped_column(Integer)
    video_duration: Mapped[float | None] = mapped_column(Double)
    dimensions_width: Mapped[int | None] = mapped_column(Integer)
    dimensions_height: Mapped[int | None] = mapped_column(Integer)
    display_url: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(Text)
    images: Mapped[Any | None] = mapped_column(JSON)
    child_posts: Mapped[Any | None] = mapped_column(JSON)
    latest_comments: Mapped[Any | None] = mapped_column(JSON)
    first_comment: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    mentions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    tagged_users: Mapped[Any | None] = mapped_column(JSON)
    location_id: Mapped[str | None] = mapped_column(Text)
    location_name: Mapped[str | None] = mapped_column(Text)
    music_info: Mapped[Any | None] = mapped_column(JSON)
    paid_partnership: Mapped[bool | None] = mapped_column(Boolean)
    product_type: Mapped[str | None] = mapped_column(Text)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean)
    raw: Mapped[Any | None] = mapped_column(JSON)


class ProbeTiktokVideo(LocalRawProvenanceMixin, AbiBase):
    """TikTok 探针结果。

    ``author_signature`` 是 PII 最集中的字段，实测已含 ``{{EMAIL_...}}`` 占位符。
    """

    __tablename__ = "probe_tiktok_video"
    __table_args__ = (
        PrimaryKeyConstraint("origin", "src_file", "src_row_ordinal"),
        Index("ix_probe_tiktok_video_id", "video_id"),
        {"schema": "raw"},
    )

    probe_date: Mapped[date | None] = mapped_column(Date)
    arm: Mapped[str | None] = mapped_column(Text)
    video_id: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    create_time: Mapped[int | None] = mapped_column(BigInteger)
    create_time_iso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    web_video_url: Mapped[str | None] = mapped_column(Text)
    search_query: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[str | None] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(Text)
    author_nickname: Mapped[str | None] = mapped_column(Text)
    author_signature: Mapped[str | None] = mapped_column(Text)
    author_fans: Mapped[int | None] = mapped_column(BigInteger)
    author_following: Mapped[int | None] = mapped_column(BigInteger)
    author_heart: Mapped[int | None] = mapped_column(BigInteger)
    author_verified: Mapped[bool | None] = mapped_column(Boolean)
    author_avatar_url: Mapped[str | None] = mapped_column(Text)
    author_bio_link: Mapped[str | None] = mapped_column(Text)
    author_profile_url: Mapped[str | None] = mapped_column(Text)
    author_private: Mapped[bool | None] = mapped_column(Boolean)
    music_id: Mapped[str | None] = mapped_column(Text)
    music_name: Mapped[str | None] = mapped_column(Text)
    music_author: Mapped[str | None] = mapped_column(Text)
    music_original: Mapped[bool | None] = mapped_column(Boolean)
    music_play_url: Mapped[str | None] = mapped_column(Text)
    music_cover_url: Mapped[str | None] = mapped_column(Text)
    video_height: Mapped[int | None] = mapped_column(Integer)
    video_width: Mapped[int | None] = mapped_column(Integer)
    video_duration: Mapped[int | None] = mapped_column(Integer)
    video_definition: Mapped[str | None] = mapped_column(Text)
    video_format: Mapped[str | None] = mapped_column(Text)
    video_cover_url: Mapped[str | None] = mapped_column(Text)
    video_cover_original_url: Mapped[str | None] = mapped_column(Text)
    transcription_link: Mapped[str | None] = mapped_column(Text)
    play_count: Mapped[int | None] = mapped_column(BigInteger)
    digg_count: Mapped[int | None] = mapped_column(BigInteger)
    comment_count: Mapped[int | None] = mapped_column(BigInteger)
    share_count: Mapped[int | None] = mapped_column(BigInteger)
    collect_count: Mapped[int | None] = mapped_column(BigInteger)
    repost_count: Mapped[int | None] = mapped_column(BigInteger)
    is_ad: Mapped[bool | None] = mapped_column(Boolean)
    is_sponsored: Mapped[bool | None] = mapped_column(Boolean)
    is_pinned: Mapped[bool | None] = mapped_column(Boolean)
    is_slideshow: Mapped[bool | None] = mapped_column(Boolean)
    is_story: Mapped[bool | None] = mapped_column(Boolean)
    is_muted: Mapped[bool | None] = mapped_column(Boolean)
    location_created: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[Any | None] = mapped_column(JSON)
    mentions: Mapped[Any | None] = mapped_column(JSON)
    detailed_mentions: Mapped[Any | None] = mapped_column(JSON)
    effect_stickers: Mapped[Any | None] = mapped_column(JSON)
    media_urls: Mapped[Any | None] = mapped_column(JSON)
    slideshow_image_links: Mapped[Any | None] = mapped_column(JSON)
    has_tiktok_shop_product: Mapped[bool | None] = mapped_column(Boolean)
    comments_dataset_url: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[Any | None] = mapped_column(JSON)


class ProbeYoutubeVideo(LocalRawProvenanceMixin, AbiBase):
    """YouTube 探针结果。"""

    __tablename__ = "probe_youtube_video"
    __table_args__ = (
        PrimaryKeyConstraint("origin", "src_file", "src_row_ordinal"),
        Index("ix_probe_youtube_video_id", "video_id"),
        {"schema": "raw"},
    )

    probe_date: Mapped[date | None] = mapped_column(Date)
    arm: Mapped[str | None] = mapped_column(Text)
    video_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    from_yt_url: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[str | None] = mapped_column(Text)
    channel_name: Mapped[str | None] = mapped_column(Text)
    channel_username: Mapped[str | None] = mapped_column(Text)
    channel_url: Mapped[str | None] = mapped_column(Text)
    number_of_subscribers: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration: Mapped[str | None] = mapped_column(Text)
    view_count: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments_count: Mapped[int | None] = mapped_column(BigInteger)
    comments_turned_off: Mapped[bool | None] = mapped_column(Boolean)
    is_members_only: Mapped[bool | None] = mapped_column(Boolean)
    is_paid_content: Mapped[bool | None] = mapped_column(Boolean)
    is_monetized: Mapped[bool | None] = mapped_column(Boolean)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    description_links: Mapped[Any | None] = mapped_column(JSON)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int | None] = mapped_column(Integer)
    input: Mapped[str | None] = mapped_column(Text)
    video_type: Mapped[str | None] = mapped_column(Text)
    translated_title: Mapped[str | None] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text)
    ai_video_summary: Mapped[str | None] = mapped_column(Text)
    ai_video_description: Mapped[str | None] = mapped_column(Text)
    collaborators: Mapped[Any | None] = mapped_column(JSON)
    subtitles: Mapped[Any | None] = mapped_column(JSON)
    transcription_url: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[Any | None] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# raw：PMO 与 Desktop
# ---------------------------------------------------------------------------


class PmoCollectionRecord(LocalRawProvenanceMixin, AbiBase):
    """PMO 采集快照。``content`` 是 JSON 对象，5 种 ``schema_version`` 共存。"""

    __tablename__ = "pmo_collection_record"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_pmo_collection_record_content_hash"),
        Index("ix_pmo_record_schema_version", "schema_version"),
        {"schema": "raw"},
    )

    record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    task_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    record_type: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    screenshot_url: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AmazonReview(LocalRawProvenanceMixin, AbiBase):
    """Desktop 亚马逊评论。

    Amazon 评论没有原生评论 id，``review_key`` 是
    ``md5(asin|作者|日期|标题|正文)`` 的前 16 字节。
    """

    __tablename__ = "amazon_review"
    __table_args__ = (
        CheckConstraint(_AMAZON_REVIEW_RATING_CHECK, name=conv("ck_amazon_review_rating")),
        Index("ix_amazon_review_asin", "asin"),
        {"schema": "raw"},
    )

    review_key: Mapped[bytes] = mapped_column(LargeBinary(16), primary_key=True)
    file_date: Mapped[date] = mapped_column(Date, nullable=False)
    asin: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    review_date: Mapped[date | None] = mapped_column(Date)
    verified_purchase: Mapped[bool | None] = mapped_column(Boolean)
    helpful_votes: Mapped[int | None] = mapped_column(Integer)
    total_votes: Mapped[int | None] = mapped_column(Integer)
    source_description: Mapped[str | None] = mapped_column(Text)


class ProductCatalog(LocalRawProvenanceMixin, AbiBase):
    """Desktop 产品目录。

    ``product_name`` 有 17,128 行为空（29.2%），唯一约束必须用
    ``NULLS NOT DISTINCT`` 才去得掉重；默认语义会把每行空值都当成不同值。
    """

    __tablename__ = "product_catalog"
    __table_args__ = (
        UniqueConstraint(
            "category",
            "brand",
            "product_name",
            name="uq_product_catalog_natural",
            postgresql_nulls_not_distinct=True,
        ),
        {"schema": "raw"},
    )

    product_key: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    file_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    product_name: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# abi：目录层
# ---------------------------------------------------------------------------


class CatalogDataset(AbiBase):
    """ABI 目录里的一行数据集。

    表名用 ``catalog_dataset`` 而不是 ``dataset``：仓库已有 ``datasets`` /
    ``dataset_versions`` / ``dataset_export_jobs``，同名不同义会让 ORM 与迁移混淆。
    """

    __tablename__ = "catalog_dataset"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_catalog_dataset_workspace_slug"),
        CheckConstraint(
            _CATALOG_SOURCE_KIND_CHECK, name=conv("ck_catalog_dataset_source_kind")
        ),
        Index("ix_catalog_dataset_platform", "workspace_id", "platform"),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_table: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(Text)
    object_type: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    last_loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    pii_scanned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    quality_status: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DatasetColumn(AbiBase):
    """目录数据集的物理列清单。

    ``nullable`` 是列名，来自迁移，不是 SQLAlchemy 的 ``nullable`` 参数。
    ``filterable`` / ``sortable`` 是查询列 allowlist 的第一层；服务端仍要
    再对照物理列，不能只信这张表。
    """

    __tablename__ = "dataset_column"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "column_name", name="uq_dataset_column_dataset_name"
        ),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    nullable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    filterable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    sortable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class FieldPolicy(AbiBase):
    """PII 遮罩的唯一依据。

    没有策略行的字段默认拒绝导出，与「未知即遮罩」一致。
    ``pii_class`` 默认 ``unknown`` 而不是 ``none``：默认 ``none`` 是 fail-open。
    """

    __tablename__ = "field_policy"
    __table_args__ = (
        UniqueConstraint("dataset_id", "field_path", name="uq_field_policy_dataset_field"),
        CheckConstraint(_PII_CLASS_CHECK, name=conv("ck_field_policy_pii_class")),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    field_path: Mapped[str] = mapped_column(Text, nullable=False)
    pii_class: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unknown'")
    )
    mask_rule: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'system'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# abi：授权
# ---------------------------------------------------------------------------


class AccessGrant(AbiBase):
    """数据集级授权。

    角色顺序 viewer < editor < publisher < admin。admin 不是万能 bypass：
    取数仍要同时匹配 ``workspace_id`` 与 grant。
    """

    __tablename__ = "access_grant"
    __table_args__ = (
        UniqueConstraint("dataset_id", "user_id", name="uq_access_grant_dataset_user"),
        CheckConstraint(_ACCESS_GRANT_ROLE_CHECK, name=conv("ck_access_grant_role")),
        Index("ix_access_grant_user", "user_id", "workspace_id"),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'viewer'")
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# abi：上传
# ---------------------------------------------------------------------------


class UploadBatch(AbiBase):
    """一次上传批次。``(dataset_id, actual_sha256)`` 唯一，用于幂等重传。"""

    __tablename__ = "upload_batch"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "actual_sha256", name="uq_upload_batch_dataset_sha256"
        ),
        CheckConstraint(_UPLOAD_BATCH_MODE_CHECK, name=conv("ck_upload_batch_mode")),
        CheckConstraint(_UPLOAD_BATCH_STATUS_CHECK, name=conv("ck_upload_batch_status")),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    expected_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    actual_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    expected_rows: Mapped[int | None] = mapped_column(BigInteger)
    actual_rows: Mapped[int | None] = mapped_column(BigInteger)
    bytes_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    storage_path: Mapped[str | None] = mapped_column(Text)
    upload_token_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_loaded: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    rows_rejected: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadError(AbiBase):
    """上传校验错误。只存定位信息，不存原始值。"""

    __tablename__ = "upload_error"
    __table_args__ = (
        Index("ix_upload_error_batch_row", "batch_id", "row_number"),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.upload_batch.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str | None] = mapped_column(Text)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# abi：导出
# ---------------------------------------------------------------------------


class ExportPolicy(AbiBase):
    """导出策略。``dataset_id`` 为空表示 workspace 级默认策略。"""

    __tablename__ = "export_policy"
    __table_args__ = {"schema": "abi"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE")
    )
    max_rows_masked: Mapped[int | None] = mapped_column(BigInteger)
    require_dual_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    allowed_formats: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExportJob(AbiBase):
    """导出作业。

    记录 ``filters_hmac`` 而不是裸哈希：邮箱、handle 这类低熵值可被字典反查。
    下载端点必须校验 ``(job_id, workspace_id, created_by/grant)``，
    且 ``Path.resolve().relative_to(export_root)`` 越界即 404。
    """

    __tablename__ = "export_job"
    __table_args__ = (
        CheckConstraint(_EXPORT_JOB_FORMAT_CHECK, name=conv("ck_export_job_format")),
        CheckConstraint(_EXPORT_JOB_STATUS_CHECK, name=conv("ck_export_job_status")),
        Index("ix_export_job_workspace_created", "workspace_id", "created_at"),
        Index(
            "ix_export_job_expires",
            "expires_at",
            postgresql_where=text("status = 'succeeded'"),
        ),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    mask_pii: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    filters: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    filters_hmac: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    columns: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_path: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    bytes_total: Mapped[int | None] = mapped_column(BigInteger)
    rows_total: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# abi：保存查询与统计
# ---------------------------------------------------------------------------


class SavedQuery(AbiBase):
    """保存的查询。只存结构化过滤，不存 SQL 片段。"""

    __tablename__ = "saved_query"
    __table_args__ = {"schema": "abi"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DatasetDailyStat(AbiBase):
    """数据集按日的行数与空值率统计。"""

    __tablename__ = "dataset_daily_stat"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "stat_date", name="uq_dataset_daily_stat_dataset_date"
        ),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abi.catalog_dataset.id", ondelete="CASCADE"), nullable=False
    )
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    bytes_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    null_rate: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CastError(AbiBase):
    """类型转换错误。集中记录，避免一页查询因坏行 500。"""

    __tablename__ = "cast_error"
    __table_args__ = {"schema": "abi"}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    row_key: Mapped[str | None] = mapped_column(Text)
    column_name: Mapped[str | None] = mapped_column(Text)
    raw_value: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlatformObject(AbiBase):
    """跨源实体。同一视频在不同来源里 id 不同，视图靠它 join。"""

    __tablename__ = "platform_object"
    __table_args__ = (
        Index("ix_platform_object_canonical", "platform", "object_type", "canonical_id"),
        {"schema": "abi"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_id: Mapped[str] = mapped_column(Text, nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    origin: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "AccessGrant",
    "ActorRegistry",
    "ActorSchemaVersion",
    "AmazonReview",
    "ApifyAccount",
    "ApifyDataset",
    "ApifyItem",
    "ApifyRun",
    "ApifyToken",
    "ApifyTokenDaily",
    "ApifyTweet",
    "AuditLog",
    "CastError",
    "CatalogDataset",
    "DatasetColumn",
    "DatasetDailyStat",
    "ExportJob",
    "ExportPolicy",
    "FieldPolicy",
    "IngestJob",
    "IngestRun",
    "LoadError",
    "LoadFile",
    "PartitionRegistry",
    "PlatformObject",
    "PmoCollectionRecord",
    "ProbeInstagramPost",
    "ProbeTiktokVideo",
    "ProbeYoutubeVideo",
    "ProductCatalog",
    "SavedQuery",
    "ScheduleState",
    "SiAuthorVideoSnapshot",
    "SiMetricSnapshot",
    "SiMusicPlatformSnapshot",
    "SiSocialPost",
    "SiTiktokComment",
    "SiTiktokHashtagSnapshot",
    "SiTiktokVideo",
    "UploadBatch",
    "UploadError",
    "WorkerHeartbeat",
]

"""``/api/abi`` 的请求与响应模型。

PII 分类与角色取值只在这里定义一次，服务层与路由层共用。
响应模型全部显式声明，路由不直接返回 ORM 对象。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AbiRole = Literal["viewer", "editor", "publisher", "admin"]
PiiClass = Literal["unknown", "none", "quasi", "direct", "secret"]
SourceKind = Literal["apify_platform", "local_table", "upload"]
UploadMode = Literal["append", "upsert", "replace"]
ExportFormat = Literal["csv", "xlsx", "jsonl"]
FilterOperator = Literal[
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "in",
    "contains",
    "is_null",
    "not_null",
]


class AbiOverviewResponse(BaseModel):
    """工作区 ABI 概览。只统计当前用户有授权的 dataset。"""

    dataset_count: int
    row_count: int
    pii_pending_datasets: int
    exports_queued: int
    exports_running: int
    exports_succeeded: int
    uploads_pending: int
    generated_at: datetime


class AbiDatasetSummary(BaseModel):
    """数据集目录项。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    name: str
    description: str | None
    source_kind: str
    source_table: str | None
    platform: str | None
    object_type: str | None
    origin: str | None
    row_count: int
    last_loaded_at: datetime | None
    version: int
    is_current: bool
    pii_scanned: bool
    quality_status: str | None
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AbiColumnCreate(BaseModel):
    """创建数据集时声明的列。"""

    column_name: str = Field(min_length=1, max_length=63, pattern=r"^[a-z_][a-z0-9_]*$")
    data_type: str = Field(default="text", min_length=1, max_length=100)
    nullable: bool = True
    filterable: bool = True
    sortable: bool = True


class AbiDatasetCreateRequest(BaseModel):
    """建 dataset。``columns`` 为空时从 ``source_table`` 物理列自动导入。"""

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source_kind: SourceKind
    source_table: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=100)
    object_type: str | None = Field(default=None, max_length=100)
    origin: str | None = Field(default=None, max_length=100)
    columns: list[AbiColumnCreate] | None = Field(default=None, max_length=500)


class AbiColumnResponse(BaseModel):
    """数据集列定义。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    column_name: str
    data_type: str
    ordinal: int
    nullable: bool
    filterable: bool
    sortable: bool


class AbiPolicyItem(BaseModel):
    """一个字段的有效 PII 策略。没有策略行时 ``pii_class`` 为 unknown。"""

    field_path: str
    pii_class: PiiClass
    mask_rule: str | None
    decided_by: str
    is_default: bool


class AbiDatasetDetailResponse(BaseModel):
    """dataset 详情 + 列 + 有效策略。"""

    dataset: AbiDatasetSummary
    columns: list[AbiColumnResponse]
    policy: list[AbiPolicyItem]


class AbiDatasetListResponse(BaseModel):
    """keyset 分页的 dataset 列表。``next_cursor`` 为空表示没有下一页。"""

    items: list[AbiDatasetSummary]
    total: int
    next_cursor: str | None
    has_more: bool


class AbiQueryFilter(BaseModel):
    """结构化过滤条件。``op`` 只接受白名单里的值。"""

    column: str = Field(min_length=1, max_length=63)
    op: FilterOperator
    value: Any = None


class AbiQueryOrder(BaseModel):
    """排序项。"""

    column: str = Field(min_length=1, max_length=63)
    direction: Literal["asc", "desc"] = "asc"


class AbiQueryRequest(BaseModel):
    """查询请求。``columns`` 为空时只返回 PII 策略已知的列。"""

    columns: list[str] | None = Field(default=None, max_length=100)
    filters: list[AbiQueryFilter] = Field(default_factory=list, max_length=20)
    order_by: list[AbiQueryOrder] = Field(default_factory=list, max_length=5)
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AbiQueryResponse(BaseModel):
    """查询结果。``masked_fields`` 列出本页做过遮罩的列。"""

    dataset_id: uuid.UUID
    columns: list[str]
    rows: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    masked_fields: list[str]


class AbiGrantCreateRequest(BaseModel):
    """新增 dataset 授权。"""

    user_id: uuid.UUID
    role: AbiRole


class AbiGrantResponse(BaseModel):
    """一条 dataset 授权。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    granted_by: uuid.UUID | None
    created_at: datetime


class AbiGrantListResponse(BaseModel):
    """dataset 授权列表。"""

    items: list[AbiGrantResponse]
    total: int


class AbiDeleteResponse(BaseModel):
    """删除操作的统一响应。"""

    deleted: bool
    id: uuid.UUID


class AbiPolicyUpdateItem(BaseModel):
    """写入单个字段的 PII 分类。"""

    field_path: str = Field(min_length=1, max_length=200)
    pii_class: PiiClass
    mask_rule: str | None = Field(default=None, max_length=200)


class AbiPolicyUpdateRequest(BaseModel):
    """全量写入 dataset 的有效策略。未提交的列写成 unknown。"""

    items: list[AbiPolicyUpdateItem] = Field(default_factory=list, max_length=500)


class AbiPolicyResponse(BaseModel):
    """dataset 的有效 PII 策略。"""

    dataset_id: uuid.UUID
    pii_scanned: bool
    items: list[AbiPolicyItem]


class AbiUploadCreateRequest(BaseModel):
    """创建上传批次。"""

    dataset_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    filename: str = Field(min_length=1, max_length=255)
    mode: UploadMode
    expected_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    expected_rows: int | None = Field(default=None, ge=0)


class AbiUploadBatchResponse(BaseModel):
    """上传批次状态。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    workspace_id: uuid.UUID
    uploaded_by: uuid.UUID
    filename: str
    mode: str
    status: str
    bytes_total: int
    expected_rows: int | None
    actual_rows: int | None
    rows_loaded: int
    rows_rejected: int
    created_at: datetime
    committed_at: datetime | None


class AbiUploadCreateResponse(BaseModel):
    """创建批次后一次性返回上传令牌。明文令牌不落库。"""

    batch: AbiUploadBatchResponse
    upload_token: str
    upload_url: str
    token_expires_at: datetime


class AbiExportCreateRequest(BaseModel):
    """创建导出任务。"""

    dataset_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    format: ExportFormat
    mask_pii: bool = True
    columns: list[str] | None = Field(default=None, max_length=100)
    filters: list[AbiQueryFilter] = Field(default_factory=list, max_length=20)
    order_by: list[AbiQueryOrder] = Field(default_factory=list, max_length=5)
    reason: str | None = Field(default=None, max_length=500)


class AbiExportJobResponse(BaseModel):
    """导出任务详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    dataset_id: uuid.UUID
    created_by: uuid.UUID
    format: str
    mask_pii: bool
    status: str
    filename: str | None
    content_type: str | None
    bytes_total: int | None
    rows_total: int | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None


class AbiExportListResponse(BaseModel):
    """导出任务列表。"""

    items: list[AbiExportJobResponse]
    total: int


__all__ = [
    "AbiColumnCreate",
    "AbiColumnResponse",
    "AbiDatasetCreateRequest",
    "AbiDatasetDetailResponse",
    "AbiDatasetListResponse",
    "AbiDatasetSummary",
    "AbiDeleteResponse",
    "AbiExportCreateRequest",
    "AbiExportJobResponse",
    "AbiExportListResponse",
    "AbiGrantCreateRequest",
    "AbiGrantListResponse",
    "AbiGrantResponse",
    "AbiOverviewResponse",
    "AbiPolicyItem",
    "AbiPolicyResponse",
    "AbiPolicyUpdateItem",
    "AbiPolicyUpdateRequest",
    "AbiQueryFilter",
    "AbiQueryOrder",
    "AbiQueryRequest",
    "AbiQueryResponse",
    "AbiUploadBatchResponse",
    "AbiUploadCreateRequest",
    "AbiUploadCreateResponse",
]

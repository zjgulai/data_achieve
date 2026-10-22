"""``/api/runs`` 的请求与响应模型。

响应里的状态与结果直接使用 ``models/run.py`` 的 StrEnum。
这样枚举取值只有一处定义，不会漂移。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from data_intelligence_hub.models.run import RunOutcome, RunStatus, RunStepStatus


class RunCreateRequest(BaseModel):
    """创建运行的请求体。

    ``task_id`` 可为空。创建端点负责校验绑定来源。
    绑定的采集任务决定对应执行步骤的 ``endpoint_type`` 与采集器配置。
    ``endpoint_type`` 必须非空，最长 80 字符。
    ``trigger`` 只允许三个来源。
    ``idempotency_key`` 由客户端提供。同一工作区内同一个键只建一行。
    """

    project_id: uuid.UUID
    task_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "当前版本只接受 `task_id` 作为绑定来源。"
            "一次运行可以包含多个采集步骤。后续批次加入带 `plan_id` 的运行。"
        ),
    )
    endpoint_type: str = Field(min_length=1, max_length=80)
    trigger: Literal["manual", "schedule", "api"] = "api"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class RunResponse(BaseModel):
    """一次运行的详情。

    字段来自 ``runs`` 表。状态与结果枚举与模型层一致。
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    workflow_version_id: uuid.UUID | None
    status: RunStatus
    outcome: RunOutcome | None
    execution_mode: str
    trigger: str
    evidence_grade: str | None
    records_count: int
    total_cost_usd: Decimal | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    lease_expires_at: datetime | None
    provider_run_id: str | None
    created_at: datetime


class RunStepResponse(BaseModel):
    """一个运行步骤的详情。

    字段来自 ``run_steps`` 表。状态与结果枚举与模型层一致。
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    endpoint_type: str
    collector_type: str
    task_run_id: uuid.UUID | None
    status: RunStepStatus
    outcome: RunOutcome | None
    records_count: int
    unit: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_cost_usd: Decimal | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class RunOutcomeResponse(BaseModel):
    """运行结果的聚合视图。

    ``step_counts`` 必须包含七个步骤状态。没有步骤的状态取 0。
    """

    run_id: uuid.UUID
    status: RunStatus
    outcome: RunOutcome | None
    records_count: int
    evidence_grade: str | None
    total_cost_usd: Decimal | None
    step_counts: dict[str, int]
    total_steps: int
    finished_at: datetime | None


__all__ = [
    "RunCreateRequest",
    "RunOutcomeResponse",
    "RunResponse",
    "RunStepResponse",
]

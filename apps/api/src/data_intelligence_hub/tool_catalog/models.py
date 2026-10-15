"""统一工具描述契约。

本模块定义面向用户与 Agent 的只读工具视图。
它不复制采集目录的存储，也不改变采集执行链路。
来源是 ``platform_packages`` 的现有目录与状态投影。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ToolRiskClass = Literal["read", "generate", "outbound", "compute"]
ToolRunMode = Literal["sync", "async"]
ToolAvailability = Literal[
    "verified", "config-gated", "degraded", "empty", "untested", "disabled"
]
ToolOutputKind = Literal["records", "text", "image", "audio", "video", "file", "action"]

TOOL_CONTRACT_VERSION = "tool.v1"


class ToolParameter(BaseModel):
    """单个输入参数。

    现有目录只有参数名，没有类型。本契约在补齐前只声明名称与是否必填。
    不虚构类型、默认值或取值范围。
    """

    model_config = ConfigDict(frozen=True)

    name: str
    required: bool
    typed: bool = False
    value_type: str | None = None


class ToolCostHint(BaseModel):
    """成本声明。

    ``source`` 区分成本信息的来源。
    上游估算不是平台售价，两者不得混用。
    """

    model_config = ConfigDict(frozen=True)

    summary: str | None
    source: Literal["upstream_estimate", "platform_price", "unknown"] = "unknown"


class ToolAvailabilityView(BaseModel):
    """可用性证据视图。

    静态目录声明与运行证据分开。
    ``verified`` 必须来自真实测试证据，不能来自目录静态字段。
    """

    model_config = ConfigDict(frozen=True)

    availability: ToolAvailability
    catalog_status: str
    last_test_status: str | None = None
    last_test_at: datetime | None = None
    last_records_count: int | None = None
    missing_configuration: tuple[str, ...] = ()
    block_reason: str | None = None


class ToolDescriptor(BaseModel):
    """一个可发现工具的完整只读描述。"""

    model_config = ConfigDict(frozen=True)

    tool_id: str
    contract_version: str = TOOL_CONTRACT_VERSION
    label: str
    description: str
    category: str
    platform: str
    provider: str
    provider_group: str
    method: str
    content_type: str
    risk_class: ToolRiskClass
    output_kind: ToolOutputKind
    run_mode: ToolRunMode
    cancellable: bool
    parameters: tuple[ToolParameter, ...]
    required_parameters: tuple[str, ...]
    optional_parameters: tuple[str, ...]
    cost: ToolCostHint
    availability_view: ToolAvailabilityView
    is_alias_view: bool
    canonical_tool_id: str
    executable: bool


class ToolCategory(BaseModel):
    """目录分类聚合。"""

    model_config = ConfigDict(frozen=True)

    category: str
    tool_count: int
    executable_count: int


class ToolCatalog(BaseModel):
    """统一只读工具目录。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "tool-catalog.v1"
    contract_version: str = TOOL_CONTRACT_VERSION
    catalog_digest: str
    tool_count: int
    executable_count: int
    canonical_tool_count: int
    categories: tuple[ToolCategory, ...]
    tools: tuple[ToolDescriptor, ...]

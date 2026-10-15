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

# 工具调用所需的授权强度。
# 目前只用于声明与校验策略制定，不改变任何执行路径的行为。
ToolAuthRequirement = Literal[
    "anonymous_read",  # 可匿名读取，不产生副作用与费用
    "identified_user",  # 需要真实登录身份
    "project_member",  # 还需要调用者属于该项目
    "operator_only",  # 仅运维可执行
]

# 调用方声明的「为何可以执行」。
# 2026-10-15 侦察证实多数执行接口当前不校验身份，
# 因此该字段目前只记录事实，不构成强制。
ToolAuthBasis = Literal[
    "demo_workspace",  # 回退到共享演示工作区
    "session_user",  # 来自有效登录会话
    "mcp_token",  # 来自 MCP Bearer token
    "unverified",  # 未发现任何鉴权依据
]

TOOL_CONTRACT_VERSION = "tool.v1"


class ToolAuthorization(BaseModel):
    """一次工具调用的授权声明。

    本契约记录「需要什么授权」与「当前提供了什么依据」。
    它不执行强制，只让授权现状可被审计与投影。

    背景：2026-10-15 侦察确认 POST /api/quick-collect、
    POST /api/tasks/{id}/run、POST /api/sources/{id}/enable
    等执行入口没有鉴权依赖，匿名调用被当作 demo workspace 业主。
    在补齐强制之前，把事实显式声明出来，
    以免「看起来有鉴权」掩盖真实缺口。
    详见 docs/architecture/【审计报告】DIH参数类型声明审计.md 与侦察记录。
    """

    model_config = ConfigDict(frozen=True)

    requirement: ToolAuthRequirement
    basis: ToolAuthBasis
    enforced: bool = False
    note: str | None = None


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
    authorization: ToolAuthorization
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

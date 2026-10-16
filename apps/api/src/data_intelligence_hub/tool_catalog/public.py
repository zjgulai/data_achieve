"""工具目录的对外只读视图。

内部契约（`ToolDescriptor`）含治理字段，不适合对外：
``authorization`` 会说明「执行入口当前不校验身份」这类缺口，
``reachability.block_reason`` 会带上策略拒绝的内部文案。
把这些原样发布到匿名可读的端点上，等于对外公告自身弱点。

因此对外另设一份投影：只保留发现与使用所需的元数据，
治理细节留在内部契约里，由需要它的调用方在服务端读取。

本模块只做投影，不改变任何执行路径。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.tool_catalog.models import (
    ToolCatalog,
    ToolCategory,
    ToolCostHint,
    ToolDescriptor,
    ToolOutputKind,
    ToolParameter,
    ToolRiskClass,
    ToolRunMode,
)


class PublicToolParameter(BaseModel):
    """对外可见的单个参数。

    含类型与约束，但不含任何治理判断。
    未登记规格的参数 ``typed`` 为 False，此时类型字段均为空——
    消费方应把它当作「只知道名称」处理。
    """

    model_config = ConfigDict(frozen=True)

    name: str
    required: bool
    typed: bool
    value_type: str | None = None
    description: str | None = None
    default: object | None = None
    allowed_values: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    type_enforced: bool = True


class PublicToolAvailability(BaseModel):
    """对外可见的可用性视图。

    刻意不含 ``block_reason``：内部契约在那里放的是策略拒绝原文
    （例如「collection_policy_denied: X 未具备受控出口，禁止执行」）。
    把它发布到匿名可读的端点上，等于对外公告自身弱点。
    消费方需要的「能不能跑」由 ``executable_now`` 与
    ``permanently_blocked`` 两个布尔回答，不需要原文。
    """

    model_config = ConfigDict(frozen=True)

    availability: str
    catalog_status: str
    last_test_status: str | None = None
    last_test_at: datetime | None = None
    last_records_count: int | None = None
    missing_configuration: tuple[str, ...] = ()


class PublicTool(BaseModel):
    """对外可见的单个工具描述。"""

    model_config = ConfigDict(frozen=True)

    tool_id: str
    contract_version: str
    label: str
    description: str
    category: str
    platform: str
    provider: str
    provider_group: str
    content_type: str
    risk_class: ToolRiskClass
    output_kind: ToolOutputKind
    run_mode: ToolRunMode
    cancellable: bool
    parameters: tuple[PublicToolParameter, ...]
    required_parameters: tuple[str, ...]
    optional_parameters: tuple[str, ...]
    cost: ToolCostHint
    availability: PublicToolAvailability
    execution_kind: str
    # 当前是否可执行。含环境因素，与 permanently_blocked 不同：
    # 前者可能是离线模式所致，切到受限联网即变真。
    executable_now: bool
    # 策略层无条件拒绝，切换环境也不会放行。
    permanently_blocked: bool
    is_alias_view: bool
    canonical_tool_id: str
    executable: bool


class PublicToolCatalog(BaseModel):
    """对外可见的工具目录。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    contract_version: str
    catalog_digest: str
    tool_count: int
    canonical_tool_count: int
    executable_count: int
    categories: tuple[ToolCategory, ...]
    tools: tuple[PublicTool, ...]


def _public_parameter(parameter: ToolParameter) -> PublicToolParameter:
    return PublicToolParameter(
        name=parameter.name,
        required=parameter.required,
        typed=parameter.typed,
        value_type=parameter.value_type,
        description=parameter.description,
        default=parameter.default,
        allowed_values=parameter.allowed_values,
        minimum=parameter.minimum,
        maximum=parameter.maximum,
        max_length=parameter.max_length,
        type_enforced=parameter.type_enforced,
    )


def to_public_tool(descriptor: ToolDescriptor) -> PublicTool:
    """把内部描述投影为对外视图。

    刻意丢弃 ``authorization``：它记录的是执行入口的鉴权现状与缺口，
    属于服务端治理信息，不属于对外元数据。
    ``reachability`` 只保留可执行性与「是否永久拒绝」两个布尔，
    不转发策略拒绝的原文。
    """
    reachability = descriptor.reachability
    return PublicTool(
        tool_id=descriptor.tool_id,
        contract_version=descriptor.contract_version,
        label=descriptor.label,
        description=descriptor.description,
        category=descriptor.category,
        platform=descriptor.platform,
        provider=descriptor.provider,
        provider_group=descriptor.provider_group,
        content_type=descriptor.content_type,
        risk_class=descriptor.risk_class,
        output_kind=descriptor.output_kind,
        run_mode=descriptor.run_mode,
        cancellable=descriptor.cancellable,
        parameters=tuple(_public_parameter(item) for item in descriptor.parameters),
        required_parameters=descriptor.required_parameters,
        optional_parameters=descriptor.optional_parameters,
        cost=descriptor.cost,
        availability=PublicToolAvailability(
            availability=descriptor.availability_view.availability,
            catalog_status=descriptor.availability_view.catalog_status,
            last_test_status=descriptor.availability_view.last_test_status,
            last_test_at=descriptor.availability_view.last_test_at,
            last_records_count=descriptor.availability_view.last_records_count,
            missing_configuration=descriptor.availability_view.missing_configuration,
        ),
        execution_kind=reachability.execution_kind,
        executable_now=reachability.allowed_now,
        permanently_blocked=reachability.permanently_blocked,
        is_alias_view=descriptor.is_alias_view,
        canonical_tool_id=descriptor.canonical_tool_id,
        executable=descriptor.executable,
    )


def to_public_catalog(catalog: ToolCatalog) -> PublicToolCatalog:
    """投影整份工具目录。"""
    return PublicToolCatalog(
        schema_version=catalog.schema_version,
        contract_version=catalog.contract_version,
        catalog_digest=catalog.catalog_digest,
        tool_count=catalog.tool_count,
        canonical_tool_count=catalog.canonical_tool_count,
        executable_count=catalog.executable_count,
        categories=catalog.categories,
        tools=tuple(to_public_tool(item) for item in catalog.tools),
    )

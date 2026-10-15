"""把现有采集目录投影为统一工具目录。

本模块只读。它不修改 ``platform_packages`` 的任何对象，
也不改变采集执行链路。
"""

from __future__ import annotations

from data_intelligence_hub.platform_packages.models import (
    PackageEndpoint,
    PlatformPackageCatalog,
)
from data_intelligence_hub.platform_packages.status import ProviderStatusResponse
from data_intelligence_hub.tool_catalog.models import (
    TOOL_CONTRACT_VERSION,
    ToolAvailabilityView,
    ToolCatalog,
    ToolCategory,
    ToolCostHint,
    ToolDescriptor,
    ToolOutputKind,
    ToolParameter,
    ToolRiskClass,
    ToolRunMode,
)

# 当前目录里的条目全部是采集类，即只读获取。
# 生成、外发与计算类工具的映射在对应适配器落地时加入。
# 在适配器存在之前，不得凭条目名称推断其他风险类别。
_DEFAULT_RISK_CLASS: ToolRiskClass = "read"

# 采集结果统一落入 RawRecord，因此默认输出形态是 records。
# 其他输出形态来自生成类工具，当前目录没有。
_DEFAULT_OUTPUT_KIND: ToolOutputKind = "records"

# 采集走 quick-collect 同步等待结果。
_DEFAULT_RUN_MODE: ToolRunMode = "sync"


def _parameters(endpoint: PackageEndpoint) -> tuple[ToolParameter, ...]:
    """按名称构造参数列表。

    现有目录只有参数名，没有类型信息。
    因此 ``typed`` 一律为 False。
    不补类型、默认值或取值范围。
    """
    parameters = [
        ToolParameter(name=name, required=True)
        for name in endpoint.required_params
    ]
    parameters.extend(
        ToolParameter(name=name, required=False)
        for name in endpoint.optional_params
        if name not in endpoint.required_params
    )
    return tuple(parameters)


def _cost(endpoint: PackageEndpoint) -> ToolCostHint:
    """成本声明。

    ``cost_hint`` 是上游估算文案，不是平台售价。
    没有该字段时标为 unknown，不填猜测值。
    """
    if endpoint.cost_hint is None:
        return ToolCostHint(summary=None, source="unknown")
    return ToolCostHint(summary=endpoint.cost_hint, source="upstream_estimate")


def _availability(
    endpoint: PackageEndpoint,
    status_by_endpoint: dict[str, ToolAvailabilityView],
) -> ToolAvailabilityView:
    """合并目录静态声明与运行证据。

    ``catalog_status`` 始终来自端点本身。
    ``availability`` 来自运行证据；没有证据时保守处理。
    两者必须分开，避免把静态声明当成运行可用性。
    """
    catalog_status = endpoint.status
    existing = status_by_endpoint.get(endpoint.endpoint_type)
    if existing is None:
        return ToolAvailabilityView(
            availability="disabled" if catalog_status == "disabled" else "untested",
            catalog_status=catalog_status,
        )
    return existing.model_copy(update={"catalog_status": catalog_status})


def build_availability_views(
    status: ProviderStatusResponse,
) -> dict[str, ToolAvailabilityView]:
    """把 Provider 状态转成按端点索引的运行证据视图。

    这里不填 ``catalog_status``。它由投影在合并端点时补齐。
    ``policy_block_reason`` 是策略阻断的说明，映射到 ``block_reason``。
    它与 ``missing_configuration`` 不同：前者是策略拒绝，后者是缺配置。
    """
    return {
        item.endpoint_type: ToolAvailabilityView(
            availability=item.availability,
            catalog_status="",
            last_test_status=item.last_test_status,
            last_test_at=item.last_test_at,
            last_records_count=item.last_records_count,
            missing_configuration=item.missing_configuration,
            block_reason=item.policy_block_reason,
        )
        for item in status.endpoints
    }


def build_tool_catalog(
    catalog: PlatformPackageCatalog,
    status: ProviderStatusResponse | None = None,
) -> ToolCatalog:
    """构造统一只读工具目录。

    目录按唯一端点去重。
    别名视图保留，并以 ``canonical_tool_id`` 指回主条目。
    没有传入状态证据时，所有条目按 untested 或 disabled 处理。
    """
    status_by_endpoint = build_availability_views(status) if status else {}
    seen: set[str] = set()
    tools: list[ToolDescriptor] = []
    for package in catalog.packages:
        for endpoint in package.endpoints:
            availability_view = _availability(endpoint, status_by_endpoint)
            canonical_tool_id = endpoint.endpoint_type
            described = ToolDescriptor(
                tool_id=endpoint.endpoint_type,
                contract_version=TOOL_CONTRACT_VERSION,
                label=endpoint.label,
                description=endpoint.description,
                category=endpoint.platform,
                platform=endpoint.platform,
                provider=endpoint.provider,
                provider_group=endpoint.provider_group,
                method=endpoint.method,
                content_type=endpoint.content_type,
                risk_class=_DEFAULT_RISK_CLASS,
                output_kind=_DEFAULT_OUTPUT_KIND,
                run_mode=_DEFAULT_RUN_MODE,
                cancellable=False,
                parameters=_parameters(endpoint),
                required_parameters=endpoint.required_params,
                optional_parameters=endpoint.optional_params,
                cost=_cost(endpoint),
                availability_view=availability_view,
                is_alias_view=endpoint.is_alias_view,
                canonical_tool_id=canonical_tool_id,
                executable=availability_view.availability
                not in {"disabled", "config-gated"},
            )
            if canonical_tool_id in seen:
                continue
            seen.add(canonical_tool_id)
            tools.append(described)
    tools.sort(key=lambda item: item.tool_id)
    return ToolCatalog(
        catalog_digest=catalog.catalog_digest,
        tool_count=len(tools),
        executable_count=sum(item.executable for item in tools),
        canonical_tool_count=len(seen),
        categories=_categories(tools),
        tools=tuple(tools),
    )


def _categories(tools: list[ToolDescriptor]) -> tuple[ToolCategory, ...]:
    """按平台聚合计入目录的条目数。"""
    counts: dict[str, list[int]] = {}
    for tool in tools:
        bucket = counts.setdefault(tool.category, [0, 0])
        bucket[0] += 1
        bucket[1] += int(tool.executable)
    return tuple(
        ToolCategory(
            category=category,
            tool_count=values[0],
            executable_count=values[1],
        )
        for category, values in sorted(counts.items())
    )

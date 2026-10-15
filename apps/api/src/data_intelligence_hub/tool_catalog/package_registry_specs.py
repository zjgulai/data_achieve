"""包注册类采集器的参数规格。

本表只有 16 个包注册类类型。它们是 2026-10-15 参数审计中唯一被判定
「声明与实现一致」的一组，因此作为参数契约的首批可采信来源。

规格来源是各采集器的 ``validate_config()`` 实现，不是
``COLLECTOR_CATALOG`` 的 ``config_schema`` 声明。
后者已证实在其他采集器族里与实现不符（例如声明 ``limit`` 而实现读
``max_items``），且结构上不支持上下界与枚举。

审计结论见 docs/architecture/【审计报告】DIH参数类型声明审计.md。

本模块不修改采集目录，也不触发任何执行。
"""

from __future__ import annotations

from data_intelligence_hub.tool_catalog.parameters import (
    ParameterSpec,
    ToolParameterContract,
)

# 各 *__search 类型共用的上限差异。
# 审计实测：仅 npm_search 上限是 250，其余搜索类均为 100。
# 默认值全族一致为 20，与上限是两个不同的数。
_NPM_MAX_ITEMS = 250
_OTHER_MAX_ITEMS = 100
_DEFAULT_MAX_ITEMS = 20

# 16 个类型的共同结构：
# - *_package 只接受 package（必填非空字符串）
# - *_search 接受 query（必填）+ max_items（整数，有上下界）
_PACKAGE_TYPES = (
    "npm_package",
    "pypi_package",
    "crates_package",
    "rubygems_package",
    "go_package",
    "packagist_package",
    "nuget_package",
    "pubdev_package",
)
_SEARCH_TYPES = (
    "npm_search",
    "pypi_search",
    "crates_search",
    "rubygems_search",
    "go_search",
    "packagist_search",
    "nuget_search",
    "pubdev_search",
)


def _package_specs() -> tuple[ParameterSpec, ...]:
    """``*_package`` 的参数：只接受包名。

    实现用 ``require_text``，即非字符串或 strip 后为空即拒绝。
    注意：实现不校验包名的字符集或长度，直接拼进 URL 路径。
    本规格如实反映这一点，不添加实现没有的约束。
    """
    return (
        ParameterSpec(
            name="package",
            value_type="string",
            required=True,
            source="collector_validation",
            description="包名；实现只校验非空字符串，不校验字符集或格式",
        ),
    )


def _search_specs(collector_type: str) -> tuple[ParameterSpec, ...]:
    """``*_search`` 的参数：查询词加结果上限。

    实现用 ``isinstance(x, int)`` 加范围检查，而非 ``int()`` 强转，
    因此数字字符串会被拒绝。
    """
    maximum = _NPM_MAX_ITEMS if collector_type == "npm_search" else _OTHER_MAX_ITEMS
    return (
        ParameterSpec(
            name="query",
            value_type="string",
            required=True,
            source="collector_validation",
            description="查询词",
        ),
        ParameterSpec(
            name="max_items",
            value_type="integer",
            required=False,
            source="collector_validation",
            description=f"返回条数上限；实现要求 1 到 {maximum} 之间的整数",
            default=_DEFAULT_MAX_ITEMS,
            minimum=1,
            maximum=maximum,
        ),
    )


def build_package_registry_contracts() -> dict[str, ToolParameterContract]:
    """构造 16 个包注册类类型的参数契约。

    键是 ``collector_type``，与目录里的 ``endpoint_type`` 同名。
    """
    contracts: dict[str, ToolParameterContract] = {}
    for collector_type in _PACKAGE_TYPES:
        contracts[collector_type] = ToolParameterContract(
            tool_id=collector_type,
            specs=_package_specs(),
        )
    for collector_type in _SEARCH_TYPES:
        contracts[collector_type] = ToolParameterContract(
            tool_id=collector_type,
            specs=_search_specs(collector_type),
        )
    return contracts


CONTRACTS = build_package_registry_contracts()

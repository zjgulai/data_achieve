from __future__ import annotations

import asyncio

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.tool_catalog.package_registry_specs import (
    CONTRACTS,
    build_package_registry_contracts,
)
from data_intelligence_hub.tool_catalog.parameters import validate_parameters


def _catalog_endpoints() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    source = asyncio.run(get_collector_catalog())
    return {
        endpoint.endpoint_type: (
            tuple(endpoint.required_params),
            tuple(endpoint.optional_params),
        )
        for group in source.collectors
        for endpoint in group.endpoints
    }


def test_contracts_cover_sixteen_package_registry_types() -> None:
    assert len(CONTRACTS) == 16
    package_types = {k for k in CONTRACTS if k.endswith("_package")}
    search_types = {k for k in CONTRACTS if k.endswith("_search")}
    assert len(package_types) == 8
    assert len(search_types) == 8


def test_every_contract_matches_a_real_catalog_endpoint() -> None:
    endpoints = _catalog_endpoints()
    missing = sorted(set(CONTRACTS) - set(endpoints))
    assert missing == [], f"契约里的类型不在目录中: {missing}"


def test_declared_required_matches_catalog_required_params() -> None:
    """本表声明的必填必须与端点元数据一致。

    端点元数据在本族被审计判定与实现一致，
    因此它可以作为独立交叉验证，而不是重复 config_schema 的声明。
    """
    endpoints = _catalog_endpoints()
    for tool_id, contract in CONTRACTS.items():
        required, _ = endpoints[tool_id]
        declared = {s.name for s in contract.specs if s.required}
        assert declared == set(required), f"{tool_id}: 契约 {declared} != 目录 {set(required)}"


def test_declared_optional_matches_catalog_optional_params() -> None:
    endpoints = _catalog_endpoints()
    for tool_id, contract in CONTRACTS.items():
        _, optional = endpoints[tool_id]
        declared = {s.name for s in contract.specs if not s.required}
        assert declared == set(optional), f"{tool_id}: 契约 {declared} != 目录 {set(optional)}"


def test_search_upper_bounds_reflect_implementation_not_the_stale_schema() -> None:
    """npm_search 的上限是 250，其余搜索类是 100。

    这个差异只存在于 validate_config 实现里，
    COLLECTOR_CATALOG 的声明只有 "integer"，看不到上下界。
    """
    npm = CONTRACTS["npm_search"].spec_for("max_items")
    assert npm is not None and npm.maximum == 250

    others = [c for k, c in CONTRACTS.items() if k.endswith("_search") and k != "npm_search"]
    assert len(others) == 7
    for contract in others:
        spec = contract.spec_for("max_items")
        assert spec is not None
        assert spec.maximum == 100, contract.tool_id

    # 下界与默认值全族一致
    for contract in CONTRACTS.values():
        if not contract.tool_id.endswith("_search"):
            continue
        spec = contract.spec_for("max_items")
        assert spec is not None
        assert spec.minimum == 1
        assert spec.default == 20


def test_specs_are_sourced_from_implementation_not_schema_guess() -> None:
    for contract in CONTRACTS.values():
        assert contract.specs, contract.tool_id
        for spec in contract.specs:
            assert spec.source == "collector_validation", f"{contract.tool_id}.{spec.name}"


def test_validation_rejects_out_of_range_and_accepts_valid() -> None:
    endpoints = _catalog_endpoints()

    ok = validate_parameters(
        CONTRACTS["npm_search"],
        {"query": "requests", "max_items": 50},
        required_names=endpoints["npm_search"][0],
        optional_names=endpoints["npm_search"][1],
    )
    assert ok.ok is True
    assert ok.untyped_names == ()

    above = validate_parameters(
        CONTRACTS["npm_search"],
        {"query": "requests", "max_items": 5000},
        required_names=endpoints["npm_search"][0],
        optional_names=endpoints["npm_search"][1],
    )
    assert [v.code for v in above.violations] == ["above_maximum"]

    # 数字字符串必须被拒：实现用 isinstance 而非 int() 强转。
    stringly = validate_parameters(
        CONTRACTS["npm_search"],
        {"query": "requests", "max_items": "50"},
        required_names=endpoints["npm_search"][0],
        optional_names=endpoints["npm_search"][1],
    )
    assert [v.code for v in stringly.violations] == ["wrong_type"]


def test_package_only_types_reject_extra_parameters() -> None:
    endpoints = _catalog_endpoints()
    result = validate_parameters(
        CONTRACTS["npm_package"],
        {"package": "express", "max_items": 10},
        required_names=endpoints["npm_package"][0],
        optional_names=endpoints["npm_package"][1],
    )
    assert result.ok is False
    assert [v.code for v in result.violations] == ["unknown_parameter"]
    assert result.violations[0].name == "max_items"


def test_builder_returns_a_fresh_mapping_each_call() -> None:
    first = build_package_registry_contracts()
    second = build_package_registry_contracts()
    assert set(first) == set(second) == set(CONTRACTS)

"""collector_specs 契约的单元测试。

覆盖四件事：

1. 契约的键是注册表里真实存在的 ``collector_type``。
2. 契约内容与审计判定一致（44 个不一致类型，规格来自实现）。
3. 复核推翻过的条目已被修正（避免把已证伪的声明写进可采信来源）。
4. 三个契约模块合起来覆盖全部已注册类型，互不重叠。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
from data_intelligence_hub.tool_catalog.collector_specs import (
    CONTRACTS,
    build_collector_contracts,
)
from data_intelligence_hub.tool_catalog.collector_specs_baseline import (
    CONTRACTS as BASELINE_CONTRACTS,
)
from data_intelligence_hub.tool_catalog.package_registry_specs import (
    CONTRACTS as PACKAGE_CONTRACTS,
)

# 2026-10-15 审计结论：86 个类型中 44 个声明与实现不一致。
_AUDITED_MISMATCH_COUNT = 44
# 16 个包注册类类型判定一致，作为首批可采信来源。
_PACKAGE_REGISTRY_COUNT = 16
# 其余 26 个（审计判定一致或未被逐条核验），2026-10-16 补登记。
_BASELINE_COUNT = 26


def _registry_types() -> set[str]:
    return set(COLLECTOR_REGISTRY)


def test_covers_exactly_the_forty_four_mismatched_types() -> None:
    assert len(CONTRACTS) == _AUDITED_MISMATCH_COUNT


def test_every_key_is_a_real_collector_type() -> None:
    """键必须是注册表里的类型，不能是端点名或凭空造的名字。

    目录按 ``endpoint_type`` 索引，契约按 ``collector_type`` 索引，
    两者不同名（例如组名 github 管辖端点 github_repo）。
    这里断言契约用的确实是后者。
    """
    unknown = sorted(set(CONTRACTS) - _registry_types())
    assert unknown == [], f"契约里的键不是注册表类型: {unknown}"


def test_three_contract_modules_do_not_overlap() -> None:
    """三个契约模块的键必须两两不相交，否则登记会互相覆盖。"""
    a, b, c = set(CONTRACTS), set(PACKAGE_CONTRACTS), set(BASELINE_CONTRACTS)
    for left, right, name in (
        (a, b, "collector_specs ∩ package_registry_specs"),
        (a, c, "collector_specs ∩ collector_specs_baseline"),
        (b, c, "package_registry_specs ∩ collector_specs_baseline"),
    ):
        assert not (left & right), f"{name} 重复登记: {sorted(left & right)}"


def test_registry_coverage_is_complete() -> None:
    """三个模块合起来覆盖全部已注册类型，一个不漏、一个不多。

    2026-10-16 补齐第三批后覆盖率达到 100%。此前是 60/86，
    剩下 26 个未登记。这个断言把「全覆盖」这个状态钉住：
    新增采集器类型而忘记登记契约时，它会失败。
    """
    covered = set(CONTRACTS) | set(PACKAGE_CONTRACTS) | set(BASELINE_CONTRACTS)
    registry = _registry_types()
    assert covered <= registry, f"契约里有非注册表类型: {sorted(covered - registry)}"
    assert len(covered) == len(registry), (
        f"覆盖率不是 100%：已登记 {len(covered)}/{len(registry)}，"
        f"缺 {sorted(registry - covered)}"
    )
    assert len(covered) == (
        _AUDITED_MISMATCH_COUNT + _PACKAGE_REGISTRY_COUNT + _BASELINE_COUNT
    )


def test_every_spec_is_sourced_from_implementation() -> None:
    """规格来源必须是采集器校验实现，不是目录的 config_schema。

    审计已证实 config_schema 与实现不符，把它当来源会引入假约束。
    """
    for tool_id, contract in CONTRACTS.items():
        assert contract.specs, f"{tool_id} 没有规格"
        for spec in contract.specs:
            assert spec.source == "collector_validation", f"{tool_id}.{spec.name}"


def test_no_contract_registers_untyped_or_unknown_value_types() -> None:
    allowed = {"string", "integer", "number", "boolean", "enum", "string_list", "list"}
    for tool_id, contract in CONTRACTS.items():
        for spec in contract.specs:
            assert spec.value_type in allowed, f"{tool_id}.{spec.name}={spec.value_type}"


def test_conflicts_are_recorded_rather_than_silently_resolved() -> None:
    """分歧必须留痕。

    同一参数在服务层与类级各有一份校验。擅自合并会掩盖
    「标准路径拒绝、直连路径放行」这类真实缺口。
    """
    with_conflicts = [t for t, c in CONTRACTS.items() if c.conflicts]
    assert with_conflicts, "审计发现了多处两站分歧，不应为空"
    for tool_id in with_conflicts:
        for conflict in CONTRACTS[tool_id].conflicts:
            assert conflict.param
            assert conflict.difference
            assert conflict.impact
            assert CONTRACTS[tool_id].conflict_for(conflict.param) is conflict


def test_adversarial_review_corrections_are_applied() -> None:
    """复核推翻过的条目必须按修正后的版本登记。

    每一条都对应复核给出的 evidence，若有人回退成抽取原稿，
    这里会失败。
    """

    # exa：实现只查 isinstance(list)，元素不校验。
    # 按 string_list 登记会拒绝运行时实际放行的 [1, 2]。
    for name in ("include_domains", "exclude_domains"):
        spec = CONTRACTS["exa_search"].spec_for(name)
        assert spec is not None
        assert spec.value_type == "list", name

    # exa：num_results 上界随 search_type 变化（10 或 25），不得写死。
    num_results = CONTRACTS["exa_search"].spec_for("num_results")
    assert num_results is not None
    assert num_results.minimum == 1
    assert num_results.maximum is None, "上界随搜索类型变化，不能写成固定值"

    # osint：maigret 的上界是 3000，不是 CLI 默认的 500。
    max_sites = CONTRACTS["maigret"].spec_for("max_sites")
    assert max_sites is not None
    assert (max_sites.minimum, max_sites.maximum) == (1, 3000)

    # apify：run_timeout_seconds 在标准路径上被白名单丢弃，
    # 该事实必须留在分歧记录里，而不是只登记一条看似可用的规格。
    assert CONTRACTS["apify_actor"].conflict_for("run_timeout_seconds") is not None

    # apify：max_total_charge_usd 两处默认值不同（1.0 与 3.0）。
    charge = CONTRACTS["apify_actor"].spec_for("max_total_charge_usd")
    assert charge is not None
    assert charge.minimum == 0
    assert CONTRACTS["apify_actor"].conflict_for("max_total_charge_usd") is not None


def test_tikhub_conflicts_surface_the_metadata_whitelist_gap() -> None:
    """tikhub 元数据声明、白名单放行、实现三者仍有未对齐处。

    userId 曾属此类：元数据声明必填，白名单却先剥掉它，
    实现里的 ``config.get("userId")`` 回退因此在标准路径不可达。
    2026-10-16 已把 userId 加入白名单，缺口关闭，
    对应的分歧记录也随之移除——契约只记当前仍然成立的差异。

    oid 仍未决：元数据声明必填，白名单没有它，
    实现消费的是 bvid/video_id，且上游实际参数名还需实测确认。
    """
    tikhub = CONTRACTS["tikhub_social"]

    # 已修复：userId 不再记为分歧，且确实能穿过白名单。
    assert tikhub.conflict_for("userId") is None, (
        "userId 的白名单缺口已修，不应再作为分歧登记"
    )
    from data_intelligence_hub.services.collector_catalog import (
        validate_collector_config,
    )

    validated = validate_collector_config(
        "tikhub_social",
        {"endpoint_type": "tikhub_kuaishou_user_posts", "userId": "probe"},
    )
    assert validated["userId"] == "probe"

    # 仍未决：oid 必须继续留在分歧记录里。
    assert tikhub.conflict_for("oid") is not None


def test_builder_returns_a_fresh_mapping_each_call() -> None:
    first = build_collector_contracts()
    second = build_collector_contracts()
    assert set(first) == set(second) == set(CONTRACTS)
    first["__probe__"] = first["exa_search"]
    assert "__probe__" not in CONTRACTS


def test_contracts_are_frozen() -> None:
    for contract in CONTRACTS.values():
        assert contract.model_config.get("frozen") is True
        for spec in contract.specs:
            assert spec.model_config.get("frozen") is True


@pytest.mark.parametrize(
    "tool_id,param,expected",
    [
        ("bilibili_user_videos", "max_items", (1, 200)),
        ("bilibili_video_comments", "max_items", (1, 500)),
        ("weibo_keyword_search", "max_items", (1, 200)),
        ("robin_darkweb_search", "max_results", (None, 100)),
        ("firecrawl_crawl", "max_pages", (1, 500)),
        ("apify_actor", "max_items", (1, 1000)),
        ("exa_find_similar", "num_results", (1, 25)),
        ("browser_use_task", "max_steps", (1, 50)),
    ],
)
def test_numeric_bounds_match_implementation(
    tool_id: str, param: str, expected: tuple[int | None, int | None]
) -> None:
    """上下界必须来自实现，且与实现一致。

    这些界只存在于 validate_config / 服务层校验函数里，
    目录的 config_schema 结构上无法表达它们。
    """
    spec = CONTRACTS[tool_id].spec_for(param)
    assert spec is not None, f"{tool_id}.{param}"
    assert (spec.minimum, spec.maximum) == expected


def test_enum_values_are_the_implementation_set() -> None:
    level = CONTRACTS["aliens_eye_advanced"].spec_for("level")
    assert level is not None
    assert set(level.allowed_values) == {"basic", "intermediate", "advanced"}

    wait_for = CONTRACTS["playwright_browser"].spec_for("wait_for")
    assert wait_for is not None
    assert set(wait_for.allowed_values) == {"load", "networkidle", "domcontentloaded"}

    # tikhub 的 endpoint_type 枚举就是它管辖的 62 个端点。
    endpoint_enum = CONTRACTS["tikhub_social"].spec_for("endpoint_type")
    assert endpoint_enum is not None
    assert len(endpoint_enum.allowed_values) == 62
    assert all(v.startswith("tikhub_") for v in endpoint_enum.allowed_values)

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.status import (
    EndpointEvidence,
    build_provider_status,
)
from data_intelligence_hub.tool_catalog.projection import build_tool_catalog


@pytest.fixture()
def restricted_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """在受限联网模式下运行。

    采集外访策略规定本地与测试环境默认 offline，
    provider_api 类采集器会被整体拦下，无法验证「按证据判断可用性」的行为。
    这里显式切到 restricted，让固定 Provider 端点具备执行资格。
    策略本身的行为由 outbound 系列测试覆盖，不在本文件重复。
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _catalog():
    source = asyncio.run(get_collector_catalog())
    return build_platform_package_catalog(source)


def test_catalog_deduplicates_alias_views_by_endpoint_type() -> None:
    catalog = _catalog()
    tools = build_tool_catalog(catalog)
    tool_ids = [item.tool_id for item in tools.tools]

    assert len(tool_ids) == len(set(tool_ids)), "tool_id 必须唯一"
    assert tools.canonical_tool_count == tools.tool_count
    assert tools.tool_count == catalog.unique_endpoint_count


def test_catalog_does_not_claim_verified_without_evidence() -> None:
    catalog = _catalog()
    tools = build_tool_catalog(catalog)
    by_id = {item.tool_id: item for item in tools.tools}

    assert by_id
    for item in tools.tools:
        assert item.availability_view.availability in {"untested", "disabled"}
        assert item.availability_view.last_test_at is None

    # 关键点：目录静态声明为 verified 的条目，没有运行证据时
    # 也不得投影为 verified。
    statically_verified = [
        item for item in tools.tools if item.availability_view.catalog_status == "verified"
    ]
    assert statically_verified, "样本里应存在静态 verified 条目"
    assert all(
        item.availability_view.availability == "untested" for item in statically_verified
    )


def test_catalog_reports_executable_only_for_non_blocked_tools(
    restricted_network: None,
) -> None:
    catalog = _catalog()
    status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=12,
            ),
        },
    )
    tools = build_tool_catalog(catalog, status)
    by_id = {item.tool_id: item for item in tools.tools}

    verified = by_id["tikhub_tiktok_video_search"]
    assert verified.availability_view.availability == "verified"
    assert verified.availability_view.last_records_count == 12
    assert verified.executable is True

    # 缺配置或已禁用的条目可见，但不能执行。
    for item in tools.tools:
        if item.availability_view.availability in {"config-gated", "disabled"}:
            assert item.executable is False, item.tool_id

    # 成功但零条记录不得算作已验证。
    empty_status = build_provider_status(
        catalog,
        configured={"TIKHUB_API_KEY": True},
        evidence={
            "tikhub_tiktok_video_search": EndpointEvidence(
                status="success",
                records_count=0,
            ),
        },
    )
    empty_tool = {
        item.tool_id: item for item in build_tool_catalog(catalog, empty_status).tools
    }["tikhub_tiktok_video_search"]
    assert empty_tool.availability_view.availability == "empty"


def test_catalog_does_not_invent_parameter_types() -> None:
    catalog = _catalog()
    tools = build_tool_catalog(catalog)
    by_id = {item.tool_id: item for item in tools.tools}
    endpoint = by_id["tikhub_tiktok_video_search"]

    assert endpoint.required_parameters == ("keyword",)
    assert [item.name for item in endpoint.parameters][0] == "keyword"
    required = {item.name for item in endpoint.parameters if item.required}
    assert required == set(endpoint.required_parameters)
    # 现有目录没有类型信息，投影不得凭名称编造。
    for item in endpoint.parameters:
        assert item.typed is False
        assert item.value_type is None


def test_catalog_marks_upstream_cost_as_estimate_not_platform_price() -> None:
    catalog = _catalog()
    tools = build_tool_catalog(catalog)
    by_id = {item.tool_id: item for item in tools.tools}
    endpoint = by_id["tikhub_tiktok_video_search"]

    assert endpoint.cost.source == "upstream_estimate"
    assert endpoint.cost.summary is not None
    assert all(item.cost.source != "platform_price" for item in tools.tools)


def test_catalog_declares_authorization_without_claiming_enforcement() -> None:
    """授权字段必须如实描述现状，不得伪装成已保护。

    2026-10-15 侦察确认执行入口没有鉴权依赖，
    匿名调用被当作共享演示工作区的业主。
    契约把「应然要求」与「实然依据」分开声明，
    并且 enforced 必须为 False——在强制落地之前。
    """
    catalog = _catalog()
    tools = build_tool_catalog(catalog)

    assert tools.tools
    for item in tools.tools:
        authorization = item.authorization
        assert authorization.requirement == "project_member", item.tool_id
        assert authorization.basis == "demo_workspace", item.tool_id
        # 核心断言：没有强制就不能声称有。
        assert authorization.enforced is False, item.tool_id
        assert authorization.note, item.tool_id


def test_authorization_contract_rejects_unknown_basis() -> None:
    """未知的授权依据必须被拒，避免写入无法解释的字符串。"""
    from pydantic import ValidationError

    from data_intelligence_hub.tool_catalog.models import ToolAuthorization

    with pytest.raises(ValidationError):
        ToolAuthorization(requirement="project_member", basis="trust_me")  # type: ignore[arg-type]


def test_catalog_categories_match_tool_totals() -> None:
    catalog = _catalog()
    tools = build_tool_catalog(catalog)

    assert sum(item.tool_count for item in tools.categories) == tools.tool_count
    assert sum(item.executable_count for item in tools.categories) == tools.executable_count
    assert tools.catalog_digest == catalog.catalog_digest

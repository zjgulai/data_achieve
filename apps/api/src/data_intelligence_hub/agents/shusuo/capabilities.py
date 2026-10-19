"""把控制台的能力目录翻译成飞书对话可用的文本与调用。

数据来源与 MCP `/mcp/` 完全一致：
- 目录：`platform_packages.service`
- 实时可用性：`get_provider_status`（与 `/providers/status` 同一口径）
- 采集：`mcp_runtime.collect_service.collect_capability`
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

import structlog

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.collect_service import collect_capability
from data_intelligence_hub.platform_packages.models import PackageEndpoint, PlatformPackage
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    get_capability,
    get_platform_package_catalog,
    get_provider_status,
)
from data_intelligence_hub.platform_packages.status import EndpointAvailability

from .config import get_shushuo_config

logger = structlog.get_logger(__name__)

_STATUS_LABELS = {
    "verified": "可用",
    "empty": "可用但最近为空",
    "degraded": "最近失败",
    "config-gated": "缺配置/受限",
    "disabled": "已下线",
    "untested": "未实测",
}

_RANK = {"verified": 0, "empty": 1, "degraded": 2, "config-gated": 3, "untested": 4, "disabled": 5}

_STATUS_TTL_SECONDS = 60
_status_cache: dict[str, Any] = {"at": 0.0, "items": {}}

_MAX_LIST_LINES = 30


@dataclass(frozen=True)
class CollectOutcome:
    ok: bool
    text: str


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


async def live_status() -> dict[str, EndpointAvailability]:
    """实时可用性，60 秒缓存，避免每条消息都扫 task_runs。"""
    now = time.time()
    cached = _status_cache["items"]
    if cached and now - float(_status_cache["at"]) < _STATUS_TTL_SECONDS:
        return cached
    try:
        async with async_session_factory() as session:
            response = await get_provider_status(session)
    except Exception as exc:  # noqa: BLE001 - 状态不可用时退回静态目录
        logger.warning("shusuo_live_status_failed", error=str(exc))
        return {}
    items = {item.endpoint_type: item for item in response.endpoints}
    _status_cache["at"] = now
    _status_cache["items"] = items
    return items


def _sorted_packages(packages: tuple[PlatformPackage, ...]) -> list[PlatformPackage]:
    return sorted(packages, key=lambda item: item.platform_id)


def _sort_endpoints(
    endpoints: list[PackageEndpoint], statuses: dict[str, EndpointAvailability]
) -> list[PackageEndpoint]:
    def key(endpoint: PackageEndpoint) -> tuple[int, str]:
        availability = statuses.get(endpoint.endpoint_type)
        rank = _RANK.get(availability.availability if availability else endpoint.status, 9)
        return rank, endpoint.endpoint_type

    return sorted(endpoints, key=key)


def _availability_suffix(
    endpoint: PackageEndpoint, statuses: dict[str, EndpointAvailability]
) -> str:
    item = statuses.get(endpoint.endpoint_type)
    if item is None:
        return status_label(endpoint.status)
    label = status_label(item.availability)
    if item.policy_block_reason:
        return f"{label}·外访策略限制"
    if item.availability == "config-gated" and item.missing_configuration:
        return f"{label}·缺 {'/'.join(item.missing_configuration)}"
    return label


async def overview_text() -> str:
    catalog = await get_platform_package_catalog()
    statuses = await live_status()
    if statuses:
        counts = Counter(item.availability for item in statuses.values())
        total = len(statuses)
        source = "实时可用性（最近一次实测）"
    else:
        counts = Counter(
            endpoint.status for package in catalog.packages for endpoint in package.endpoints
        )
        total = catalog.unique_endpoint_count
        source = "目录声明状态"

    lines = [
        "数说 · 能力总览",
        f"平台包：{catalog.platform_count}",
        f"能力视图：{catalog.capability_count}",
        f"唯一端点：{total}",
        f"口径：{source}",
        "",
        "状态分布：",
    ]
    for status, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {status_label(status)}：{count}")
    lines.extend(
        [
            "",
            "发「平台」看全部平台；发「能力 <平台或关键词>」看具体端点。",
            "只有「可用」的端点会直接执行；缺配置或受外访策略限制的端点会说明原因。",
        ]
    )
    return "\n".join(lines)


def _matches_package(package: PlatformPackage, query: str) -> bool:
    haystack = f"{package.platform_id} {package.display_name} {package.description}".casefold()
    return query in haystack


async def platforms_text(query: str = "") -> str:
    catalog = await get_platform_package_catalog()
    statuses = await live_status()
    normalized = query.casefold().strip()
    packages = [
        package
        for package in _sorted_packages(catalog.packages)
        if not normalized or _matches_package(package, normalized)
    ]
    if not packages:
        return f"没有找到与「{query}」匹配的平台。发「平台」查看全部。"

    total = len(packages)
    shown = packages[:_MAX_LIST_LINES]
    lines = [f"平台（{total} 个）"]
    for package in shown:
        if statuses:
            verified = sum(
                1
                for endpoint in package.endpoints
                if statuses.get(endpoint.endpoint_type) is not None
                and statuses[endpoint.endpoint_type].availability == "verified"
            )
        else:
            verified = package.verified_count
        lines.append(
            f"- {package.display_name}（{package.platform_id}）："
            f"{package.endpoint_count} 个能力，{verified} 个实测可用"
        )
    if total > len(shown):
        lines.append(f"…另有 {total - len(shown)} 个，请加关键词缩小范围。")
    return "\n".join(lines)


def _endpoint_lines(
    endpoints: list[PackageEndpoint], statuses: dict[str, EndpointAvailability]
) -> list[str]:
    lines = []
    for endpoint in endpoints[:_MAX_LIST_LINES]:
        params = ", ".join(endpoint.required_params) if endpoint.required_params else "无必填"
        lines.append(
            f"- {endpoint.endpoint_type}｜{endpoint.label}｜"
            f"{_availability_suffix(endpoint, statuses)}｜必填：{params}"
        )
    if len(endpoints) > _MAX_LIST_LINES:
        lines.append(f"…另有 {len(endpoints) - _MAX_LIST_LINES} 个端点，请加关键词缩小范围。")
    return lines


async def capabilities_text(query: str = "") -> str:
    catalog = await get_platform_package_catalog()
    statuses = await live_status()
    normalized = query.casefold().strip()
    if not normalized:
        return "请指定平台或关键词，例如：能力 github"

    matched_packages = [
        p for p in _sorted_packages(catalog.packages) if _matches_package(p, normalized)
    ]
    if matched_packages:
        package = matched_packages[0]
        endpoints = _sort_endpoints(list(package.endpoints), statuses)
        lines = [
            f"{package.display_name}（{package.platform_id}）",
            package.description,
            f"共 {len(endpoints)} 个能力：",
            *_endpoint_lines(endpoints, statuses),
        ]
        if len(matched_packages) > 1:
            others = "、".join(p.platform_id for p in matched_packages[1:6])
            lines.append(f"其他匹配平台：{others}")
        return "\n".join(lines)

    matched: dict[str, PackageEndpoint] = {}
    for package in catalog.packages:
        for endpoint in package.endpoints:
            haystack = (
                f"{endpoint.endpoint_type} {endpoint.label} {endpoint.description} "
                f"{endpoint.platform}"
            ).casefold()
            if normalized in haystack:
                matched.setdefault(endpoint.endpoint_type, endpoint)
    if not matched:
        return f"没有找到与「{query}」匹配的能力。发「平台」查看平台清单。"

    endpoints = _sort_endpoints(list(matched.values()), statuses)
    lines = [
        f"匹配「{query}」的能力（{len(endpoints)} 个）：",
        *_endpoint_lines(endpoints, statuses),
    ]
    return "\n".join(lines)


async def describe_text(endpoint_type: str) -> str:
    try:
        endpoint = await get_capability(endpoint_type)
    except CapabilityNotFoundError:
        return f"没有找到端点：{endpoint_type}"
    statuses = await live_status()
    live = statuses.get(endpoint_type)
    required = ", ".join(endpoint.required_params) or "无"
    optional = ", ".join(endpoint.optional_params) or "无"
    lines = [
        f"{endpoint.endpoint_type}",
        f"名称：{endpoint.label}",
        f"平台：{endpoint.platform}",
        f"状态：{_availability_suffix(endpoint, statuses)}",
        f"说明：{endpoint.description}",
        f"必填参数：{required}",
        f"可选参数：{optional}",
        f"计费提示：{endpoint.cost_hint or '未标注'}",
    ]
    if live is not None:
        if live.last_test_at:
            lines.append(f"最近实测：{live.last_test_at.isoformat()}")
        if live.last_records_count is not None:
            lines.append(f"最近记录数：{live.last_records_count}")
        if live.last_error_message:
            lines.append(f"最近错误：{live.last_error_message[:200]}")
        if live.missing_configuration:
            lines.append(f"缺少配置：{'/'.join(live.missing_configuration)}")
        if live.policy_block_reason:
            lines.append(f"策略限制：{live.policy_block_reason}")
    for note in endpoint.notes:
        lines.append(f"坑点（{note.severity}）：{note.symptom}；规避：{note.workaround}")
    return "\n".join(lines)


def _block_reason(endpoint_type: str, live: EndpointAvailability | None) -> str | None:
    if live is None:
        return None
    if live.availability == "disabled":
        return f"{endpoint_type} 已下线，不能调用。"
    if live.policy_block_reason:
        return f"{endpoint_type} 当前受外访策略限制：{live.policy_block_reason}"
    if live.availability == "config-gated":
        missing = "、".join(live.missing_configuration) or "未提供原因"
        return f"{endpoint_type} 当前不可执行，缺少配置：{missing}"
    return None


async def collect(endpoint_type: str, params: dict[str, Any]) -> CollectOutcome:
    config = get_shushuo_config()
    try:
        endpoint = await get_capability(endpoint_type)
    except CapabilityNotFoundError:
        return CollectOutcome(False, f"没有找到端点：{endpoint_type}")

    statuses = await live_status()
    blocked = _block_reason(endpoint_type, statuses.get(endpoint_type))
    if blocked:
        return CollectOutcome(False, blocked)
    if endpoint.status == "disabled":
        return CollectOutcome(False, f"{endpoint_type} 已下线，不能调用。")

    try:
        project_id = uuid.UUID(config.default_project_id)
    except ValueError:
        return CollectOutcome(False, "服务端默认 project_id 配置无效。")

    try:
        result = await collect_capability(endpoint_type, project_id, params)
    except Exception as exc:  # noqa: BLE001 - 采集端错误要回给用户，不要吞掉
        logger.exception("shushuo_collect_failed", endpoint_type=endpoint_type)
        return CollectOutcome(False, f"采集失败：{type(exc).__name__}: {exc}")

    if result.status == "success" and result.records_count > 0:
        text = (
            f"采集完成\n"
            f"端点：{endpoint_type}\n"
            f"记录数：{result.records_count}\n"
            f"运行 ID：{result.task_run_id}\n"
            f"查看：{config.console_base_url}/collect/{result.task_run_id}"
        )
        return CollectOutcome(True, text)

    reason = result.error_message or "上游没有返回记录"
    return CollectOutcome(
        False,
        f"采集未返回数据\n端点：{endpoint_type}\n状态：{result.status}\n原因：{reason}\n"
        f"运行 ID：{result.task_run_id}",
    )

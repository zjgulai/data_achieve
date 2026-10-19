"""把控制台的能力目录翻译成飞书对话可用的文本与调用。

数据来源与 MCP `/mcp/` 完全一致：
- 目录：`platform_packages.service`
- 采集：`mcp_runtime.collect_service.collect_capability`
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

import structlog

from data_intelligence_hub.mcp_runtime.collect_service import collect_capability
from data_intelligence_hub.platform_packages.models import PackageEndpoint, PlatformPackage
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    get_capability,
    get_platform_package_catalog,
)

from .config import get_shushuo_config

logger = structlog.get_logger(__name__)

_STATUS_LABELS = {
    "verified": "可用",
    "empty": "可用但最近为空",
    "degraded": "最近失败",
    "config-gated": "缺配置",
    "disabled": "已下线",
    "untested": "未实测",
}

_MAX_LIST_LINES = 30


@dataclass(frozen=True)
class CollectOutcome:
    ok: bool
    text: str


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def _sorted_packages(packages: tuple[PlatformPackage, ...]) -> list[PlatformPackage]:
    return sorted(packages, key=lambda item: item.platform_id)


async def overview_text() -> str:
    catalog = await get_platform_package_catalog()
    counts = Counter(
        endpoint.status for package in catalog.packages for endpoint in package.endpoints
    )
    lines = [
        "数说 · 能力总览",
        f"平台包：{catalog.platform_count}",
        f"能力视图：{catalog.capability_count}",
        f"唯一端点：{catalog.unique_endpoint_count}",
        "",
        "状态分布：",
    ]
    for status, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {status_label(status)}：{count}")
    lines.extend(
        [
            "",
            "发「平台」看全部平台；发「能力 <平台或关键词>」看具体端点。",
        ]
    )
    return "\n".join(lines)


def _matches_package(package: PlatformPackage, query: str) -> bool:
    haystack = f"{package.platform_id} {package.display_name} {package.description}".casefold()
    return query in haystack


async def platforms_text(query: str = "") -> str:
    catalog = await get_platform_package_catalog()
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
        lines.append(
            f"- {package.display_name}（{package.platform_id}）："
            f"{package.endpoint_count} 个能力，{package.verified_count} 个实测可用"
        )
    if total > len(shown):
        lines.append(f"…另有 {total - len(shown)} 个，请加关键词缩小范围。")
    return "\n".join(lines)


def _endpoint_lines(endpoints: list[PackageEndpoint]) -> list[str]:
    lines = []
    for endpoint in endpoints[:_MAX_LIST_LINES]:
        params = ", ".join(endpoint.required_params) if endpoint.required_params else "无必填"
        lines.append(
            f"- {endpoint.endpoint_type}｜{endpoint.label}｜"
            f"{status_label(endpoint.status)}｜必填：{params}"
        )
    if len(endpoints) > _MAX_LIST_LINES:
        lines.append(f"…另有 {len(endpoints) - _MAX_LIST_LINES} 个端点，请加关键词缩小范围。")
    return lines


async def capabilities_text(query: str = "") -> str:
    catalog = await get_platform_package_catalog()
    normalized = query.casefold().strip()
    if not normalized:
        return "请指定平台或关键词，例如：能力 github"

    matched_packages = [
        p for p in _sorted_packages(catalog.packages) if _matches_package(p, normalized)
    ]
    if matched_packages:
        package = matched_packages[0]
        endpoints = list(package.endpoints)
        lines = [
            f"{package.display_name}（{package.platform_id}）",
            package.description,
            f"共 {len(endpoints)} 个能力：",
            *_endpoint_lines(endpoints),
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

    endpoints = sorted(matched.values(), key=lambda item: item.endpoint_type)
    lines = [f"匹配「{query}」的能力（{len(endpoints)} 个）：", *_endpoint_lines(endpoints)]
    return "\n".join(lines)


async def describe_text(endpoint_type: str) -> str:
    try:
        endpoint = await get_capability(endpoint_type)
    except CapabilityNotFoundError:
        return f"没有找到端点：{endpoint_type}"
    required = ", ".join(endpoint.required_params) or "无"
    optional = ", ".join(endpoint.optional_params) or "无"
    lines = [
        f"{endpoint.endpoint_type}",
        f"名称：{endpoint.label}",
        f"平台：{endpoint.platform}",
        f"状态：{status_label(endpoint.status)}",
        f"说明：{endpoint.description}",
        f"必填参数：{required}",
        f"可选参数：{optional}",
        f"计费提示：{endpoint.cost_hint or '未标注'}",
    ]
    for note in endpoint.notes:
        lines.append(f"坑点（{note.severity}）：{note.symptom}；规避：{note.workaround}")
    return "\n".join(lines)


async def collect(endpoint_type: str, params: dict[str, Any]) -> CollectOutcome:
    config = get_shushuo_config()
    try:
        endpoint = await get_capability(endpoint_type)
    except CapabilityNotFoundError:
        return CollectOutcome(False, f"没有找到端点：{endpoint_type}")

    if endpoint.status == "disabled":
        return CollectOutcome(False, f"{endpoint_type} 已下线，不能调用。")

    try:
        project_id = uuid.UUID(config.default_project_id)
    except ValueError:
        return CollectOutcome(False, "服务端默认 project_id 配置无效。")

    try:
        result = await collect_capability(endpoint_type, project_id, params)
    except Exception as exc:  # noqa: BLE001 - 采集端错误要回给用户，不要吞掉
        logger.exception("shusuo_collect_failed", endpoint_type=endpoint_type)
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

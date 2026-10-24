"""把控制台的能力目录翻译成飞书对话可用的文本与调用。

数据来源与 MCP `/mcp/` 完全一致：
- 目录：`platform_packages.service`
- 实时可用性：`get_provider_status`（与 `/providers/status` 同一口径）
- 采集：`mcp_runtime.collect_service.collect_capability`
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

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
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.services.raw_record_service import get_raw_records

from .collector_params import ParamContract, contract_for
from .config import get_shushuo_config
from .intents import Proposal

logger = logging.getLogger(__name__)

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


def _cached_status() -> dict[str, EndpointAvailability]:
    """读缓存并收窄类型：dict[str, Any] 里的 items 只能是端点可用性映射。"""
    items = _status_cache["items"]
    if not isinstance(items, dict):
        return {}
    return {str(key): value for key, value in items.items()}


def _store_status(items: dict[str, EndpointAvailability]) -> None:
    _status_cache["items"] = items

_MAX_LIST_LINES = 30

# 数量语义的参数键（不同采集器叫法不同）。预检统一检查 1..50；
# 不改名，键原样保留给采集器。
_QUANTITY_PARAM_KEYS = frozenset({"max_items", "maxItems", "num_results", "commentsPerPost"})
_QUANTITY_MIN = 1
_QUANTITY_MAX = 50

# 任何端点都允许传的键：数量通用键 + 执行元数据（quick-collect 采集开关）。
# num_results / commentsPerPost 等其余数量键必须由端点 optional_params 声明。
_UNIVERSAL_PARAM_KEYS = frozenset(
    {"max_items", "maxItems", "max_total_charge_usd", "run_timeout_seconds"}
)

UNKNOWN_COST_NOTICE = "费用未知，按上游实际计费"
UNKNOWN_COST_WARNING = "费用未知，按上游实际计费。"
# 只有出现具体金额才算已知费用：`$0.001/条`、`~$0.001/条`、`$0.5+`、`0.001 美元`。
_COST_AMOUNT_PATTERN = re.compile(r"[$¥€£]\s?\d|\d+(?:\.\d+)?\s*(?:美元|USD|usd)", re.IGNORECASE)
_POLICY_BLOCK_TEXT = "当前受安全策略限制，无法执行该端点。"


@dataclass(frozen=True)
class CollectOutcome:
    """一次采集的结构化结果。

    text 是给用户的兜底文案；新代码应改用 replies.collect_success_text /
    collect_failure_text 由结构化字段渲染回复。
    """

    ok: bool
    text: str
    endpoint_type: str = ""
    task_run_id: str = ""
    records_count: int = 0
    duration_ms: int | None = None
    total_cost_usd: str | None = None
    records: tuple[dict[str, Any], ...] = ()
    error_message: str | None = None


@dataclass(frozen=True)
class PreflightResult:
    """提案预检结果：allowed=False 时 errors 面向用户，不含内部原因。"""

    allowed: bool
    availability: str
    normalized_params: dict[str, Any]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    cost_notice: str = ""


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


async def live_status(*, force: bool = False) -> dict[str, EndpointAvailability]:
    """实时可用性，60 秒缓存，避免每条消息都扫 task_runs。

    force=True 跳过缓存读，但成功后仍回写缓存。
    """
    now = time.time()
    cached = _cached_status()
    if not force and cached and now - float(_status_cache["at"]) < _STATUS_TTL_SECONDS:
        return cached
    try:
        async with async_session_factory() as session:
            response = await get_provider_status(session)
    except Exception as exc:  # noqa: BLE001 - 状态不可用时退回静态目录
        logger.warning("shusuo_live_status_failed: %s", exc)
        return {}
    items = {item.endpoint_type: item for item in response.endpoints}
    _status_cache["at"] = now
    _store_status(items)
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
    counts: Counter[str]
    if statuses:
        counts = Counter(item.availability for item in statuses.values())
        total = len(statuses)
        source = "实时可用性（最近一次实测）"
    else:
        # 静态目录的 status 是 str，不是 Availability 字面量；Counter 统一按 str 计。
        counts = Counter(
            str(endpoint.status)
            for package in catalog.packages
            for endpoint in package.endpoints
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


def _resolve_availability(
    endpoint: PackageEndpoint, live: EndpointAvailability | None
) -> tuple[str, bool]:
    """返回 (availability, is_policy_blocked)。

    实时状态缺失时回退静态 endpoint.status；两者都不是 verified 就不放行。
    policy_block_reason 只决定文案开关，原文绝不进入结果。
    """
    if live is not None:
        if live.policy_block_reason:
            return live.availability, True
        return live.availability, False
    if endpoint.policy_block_reason:
        return endpoint.status, True
    return endpoint.status, False


def _cost_notice_and_warnings(cost_hint: str | None) -> tuple[str, tuple[str, ...]]:
    """只有带具体金额的 cost_hint 才算已知费用。

    `按事件计费`、`按结果计费`、`按量`、`按上游` 和任何没有金额的自由文本
    都是"费用未知"：用户看不到钱数，就只能按未知处理。
    """
    normalized = (cost_hint or "").strip()
    if not normalized or not _COST_AMOUNT_PATTERN.search(normalized):
        return UNKNOWN_COST_NOTICE, (UNKNOWN_COST_WARNING,)
    return f"费用约 {normalized}", ()


def _quantity_error(key: str) -> str:
    return f"参数 {key} 必须在 {_QUANTITY_MIN} 到 {_QUANTITY_MAX} 之间。"


def _missing_group_error(group: tuple[str, ...]) -> str:
    if len(group) == 1:
        return f"缺少必填参数：{group[0]}"
    return f"缺少必填参数：{' 或 '.join(group)}"


def _validate_params(
    endpoint: PackageEndpoint, params: dict[str, Any]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """按「目录 + 采集器」合成契约校验，并原样归一化（不改键名）。

    采集器文档里的别名（`query` 之于 reddit/x/youtube 搜索）与配置键
    （`order` 之于 B 站搜索）都放行；任意键仍然拒绝。
    """
    contract = contract_for(
        endpoint.endpoint_type, endpoint.required_params, endpoint.optional_params
    )
    return _validate_with_contract(contract, params)


def _validate_with_contract(
    contract: ParamContract, params: dict[str, Any]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    errors: list[str] = []
    allowed = set(contract.accepted) | _UNIVERSAL_PARAM_KEYS
    normalized: dict[str, Any] = {}

    for key, value in params.items():
        if key not in allowed:
            errors.append(f"未知参数：{key}")
            continue
        if key in _QUANTITY_PARAM_KEYS:
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(_quantity_error(key))
                continue
            if not _QUANTITY_MIN <= value <= _QUANTITY_MAX:
                errors.append(_quantity_error(key))
                continue
        normalized[key] = value

    for group in contract.required_groups:
        if any(_has_value(params.get(key)) for key in group):
            continue
        errors.append(_missing_group_error(group))
        # 缺参回填：保留首个候选键的占位，方便调用方看懂缺的是哪一组。
        if group[0] not in normalized:
            normalized[group[0]] = params.get(group[0])

    return normalized, tuple(errors)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


async def preflight_proposal(
    proposal: Proposal,
    *,
    force_status: bool = False,
) -> PreflightResult:
    """结构化预检：只有实时 verified 的端点可执行；失败时不调用采集。"""
    try:
        endpoint = await get_capability(proposal.endpoint_type)
    except CapabilityNotFoundError:
        return PreflightResult(
            allowed=False,
            availability="unknown",
            normalized_params=dict(proposal.params),
            errors=(f"没有找到端点：{proposal.endpoint_type}",),
        )

    statuses = await live_status(force=force_status)
    availability, policy_blocked = _resolve_availability(
        endpoint, statuses.get(proposal.endpoint_type)
    )

    normalized_params, param_errors = _validate_params(endpoint, proposal.params)

    errors: list[str] = []
    if policy_blocked:
        errors.append(_POLICY_BLOCK_TEXT)
    elif availability != "verified":
        label = status_label(availability)
        errors.append(f"端点 {proposal.endpoint_type} 当前不可执行（{label}）。")
    errors.extend(param_errors)

    cost_notice, cost_warnings = _cost_notice_and_warnings(endpoint.cost_hint)
    return PreflightResult(
        allowed=not errors,
        availability=availability,
        normalized_params=normalized_params,
        errors=tuple(errors),
        warnings=cost_warnings,
        cost_notice=cost_notice,
    )


async def collect(endpoint_type: str, params: dict[str, Any]) -> CollectOutcome:
    config = get_shushuo_config()
    try:
        endpoint = await get_capability(endpoint_type)
    except CapabilityNotFoundError:
        reason = f"没有找到端点：{endpoint_type}"
        return CollectOutcome(False, reason, endpoint_type=endpoint_type, error_message=reason)

    statuses = await live_status()
    live = statuses.get(endpoint_type)
    blocked = _block_reason(endpoint_type, live)
    if blocked:
        # policy_block_reason 原文绝不进 CollectOutcome；只回固定安全文案。
        reason = _POLICY_BLOCK_TEXT if (live is not None and live.policy_block_reason) else blocked
        return CollectOutcome(False, reason, endpoint_type=endpoint_type, error_message=reason)
    if endpoint.status == "disabled":
        reason = f"{endpoint_type} 已下线，不能调用。"
        return CollectOutcome(False, reason, endpoint_type=endpoint_type, error_message=reason)

    try:
        project_id = uuid.UUID(config.default_project_id)
    except ValueError:
        reason = "服务端默认 project_id 配置无效。"
        return CollectOutcome(False, reason, endpoint_type=endpoint_type, error_message=reason)

    try:
        result = await collect_capability(endpoint_type, project_id, params)
    except Exception as exc:  # noqa: BLE001 - 采集端错误要回给用户，不要吞掉
        logger.exception("shushuo_collect_failed endpoint_type=%s", endpoint_type)
        # 异常类名只保留在日志里；用户可见字段只带 str(exc)，由 replies 脱敏。
        return CollectOutcome(
            False,
            f"采集失败：{exc}",
            endpoint_type=endpoint_type,
            error_message=str(exc),
        )

    timing = result.timing if isinstance(result.timing, dict) else {}
    usage = result.usage if isinstance(result.usage, dict) else {}
    duration_raw = timing.get("duration_ms")
    duration_ms = duration_raw if isinstance(duration_raw, int) else None
    cost_raw = usage.get("total_cost_usd")
    total_cost_usd = str(cost_raw) if cost_raw is not None else None
    records = tuple(item for item in result.records if isinstance(item, dict))

    if result.status == "success" and result.records_count > 0:
        text = (
            f"采集完成\n"
            f"端点：{endpoint_type}\n"
            f"记录数：{result.records_count}\n"
            f"运行 ID：{result.task_run_id}\n"
            f"查看：{config.console_base_url}/runs/{result.task_run_id}"
        )
        return CollectOutcome(
            True,
            text,
            endpoint_type=endpoint_type,
            task_run_id=str(result.task_run_id),
            records_count=result.records_count,
            duration_ms=duration_ms,
            total_cost_usd=total_cost_usd,
            records=records,
            error_message=result.error_message,
        )

    reason = result.error_message or "上游没有返回记录"
    return CollectOutcome(
        False,
        f"采集未返回数据\n端点：{endpoint_type}\n状态：{result.status}\n原因：{reason}\n"
        f"运行 ID：{result.task_run_id}",
        endpoint_type=endpoint_type,
        task_run_id=str(result.task_run_id),
        records_count=result.records_count,
        duration_ms=duration_ms,
        total_cost_usd=total_cost_usd,
        records=records,
        error_message=result.error_message,
    )


def _record_title(record: Any) -> tuple[str, str]:
    content = record.content
    title = ""
    url = record.source_url or ""
    if isinstance(content, dict):
        for key in ("title", "name", "text", "content", "post_title", "description"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                title = value.strip()
                break
        for key in ("url", "link", "source_url", "post_url"):
            value = content.get(key)
            if isinstance(value, str) and value.startswith("http"):
                url = value
                break
    elif isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            for key in ("title", "name", "text"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break
    if not title:
        title = json.dumps(content, ensure_ascii=False)[:160]
    return title.replace("\n", " "), url


async def run_records_text(run_id: str, limit: int = 5) -> str:
    """读取一次运行的原始记录，给飞书返回前 N 条。"""
    try:
        parsed_run_id = uuid.UUID(run_id)
    except ValueError:
        return "运行 ID 格式不对。请从采集结果的「运行 ID」复制。"
    try:
        async with async_session_factory() as session:
            workspace = await get_demo_workspace(session)
            if workspace is None:
                return "demo workspace 不可用。"
            records = await get_raw_records(
                session, workspace, None, parsed_run_id, limit, 0
            )
    except Exception as exc:  # noqa: BLE001 - 回给用户，不要吞掉
        logger.exception("shusuo_run_records_failed run_id=%s", run_id)
        return f"读取运行记录失败：{type(exc).__name__}: {exc}"

    if not records:
        return f"运行 {run_id} 没有记录，或运行 ID 不存在。"
    config = get_shushuo_config()
    lines = [f"运行 {run_id} 的前 {len(records)} 条："]
    for index, record in enumerate(records, 1):
        title, url = _record_title(record)
        lines.append(f"{index}. {title[:160]}")
        if url:
            lines.append(f"   {url}")
    lines.append(f"控制台：{config.console_base_url}/runs/{run_id}")
    return "\n".join(lines)

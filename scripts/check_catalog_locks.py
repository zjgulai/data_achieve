#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/check_catalog_locks.py --json
# cd apps/api && uv run python ../../scripts/check_catalog_locks.py --json --require-generated
#
# 只读守卫：实时构建目录，比较两份 lock 与生成的索引。
# 不联网，不写 lock，不写 generated。
#
# 退出码：0 通过，1 漂移，2 输入错误。
# CI 先运行生成命令，再加 --require-generated。

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

REPORT_SCHEMA_VERSION = "catalog-guard-report.v1"
TOOL_LOCK_SCHEMA = "tool-catalog.v1"
TOOL_CONTRACT_VERSION = "tool.v1"
PACKAGE_LOCK_SCHEMA = "platform-packages.v1"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# 已知且被接受的采集器账本差集。
# 这些 Apify 采集器只有声明，没有注册实现。
KNOWN_DECLARED_WITHOUT_IMPL: frozenset[str] = frozenset(
    {
        "apify_1688_advanced",
        "apify_1688_product_detail",
        "apify_1688_product_search",
        "apify_alibaba_product_detail",
        "apify_alibaba_product_search",
        "apify_aliexpress_product_search_v2",
        "apify_amazon_bestsellers",
        "apify_amazon_bsr_tracker",
        "apify_amazon_competitor_research",
        "apify_amazon_price_tracker",
        "apify_shopify_full_catalog",
        "apify_shopify_products_monitor",
        "bilibili_video_info",
    }
)
# 反向缺口：有实现但缺 COLLECTOR_CATALOG 声明。
# 2026-10-25 清空：exa_agent 已在 main 上补声明，三层账本现无反向缺口。
# 再有新增时必须显式更新本表并说明原因。
KNOWN_REGISTERED_WITHOUT_DECLARATION: frozenset[str] = frozenset()


class GuardInputError(RuntimeError):
    """输入文件缺失或 JSON 非法。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check catalog lock consistency")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    parser.add_argument(
        "--require-generated",
        action="store_true",
        help="生成物缺失即失败。CI 必须使用。",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardInputError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise GuardInputError(f"{path} 必须是 JSON 对象")
    return data


def _add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    *,
    ok: bool,
    severity: str = "blocker",
    layer: str = "live",
    field: str | None = None,
    expected: Any = None,
    actual: Any = None,
    message: str = "",
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "ok": bool(ok),
            "severity": severity,
            "layer": layer,
            "field": field,
            "expected": expected,
            "actual": actual,
            "message": message if message or ok else f"{check_id} 不通过",
        }
    )


def _expect(
    checks: list[dict[str, Any]],
    check_id: str,
    *,
    actual: Any,
    expected: Any,
    layer: str,
    field: str,
    severity: str = "blocker",
    message: str = "",
) -> None:
    _add_check(
        checks,
        check_id,
        ok=actual == expected,
        severity=severity,
        layer=layer,
        field=field,
        expected=expected,
        actual=actual,
        message=message,
    )


async def _build_live() -> tuple[Any, Any]:
    from data_intelligence_hub.api.routes.collectors import get_collector_catalog
    from data_intelligence_hub.platform_packages.builder import (
        build_platform_package_catalog,
    )
    from data_intelligence_hub.tool_catalog.projection import build_tool_catalog

    source = await get_collector_catalog()
    catalog = build_platform_package_catalog(source)
    return catalog, build_tool_catalog(catalog)


def _build_ledger() -> dict[str, Any]:
    from data_intelligence_hub.collectors.endpoint_catalog import (
        _APIFY_ENDPOINT_DEFAULTS,
        _ENDPOINT_TO_COLLECTOR,
    )
    from data_intelligence_hub.collectors.outbound_policy import (
        GUARDED_HTTP_COLLECTORS,
        OFFLINE_COLLECTORS,
        PROVIDER_API_COLLECTORS,
        UNSUPPORTED_COLLECTORS,
    )
    from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
    from data_intelligence_hub.services.collector_catalog import COLLECTOR_CATALOG

    declared = {definition.type for definition in COLLECTOR_CATALOG}
    registry = set(COLLECTOR_REGISTRY)
    policy = {
        "offline": set(OFFLINE_COLLECTORS),
        "guarded_http": set(GUARDED_HTTP_COLLECTORS),
        "provider_api": set(PROVIDER_API_COLLECTORS),
        "unsupported": set(UNSUPPORTED_COLLECTORS),
    }
    classified: set[str] = set()
    for group in policy.values():
        classified |= group
    mapped = {key for key, value in _ENDPOINT_TO_COLLECTOR.items() if value == "apify_actor"}
    return {
        "declared": declared,
        "registry": registry,
        "policy": policy,
        "classified": classified,
        "mapping": _ENDPOINT_TO_COLLECTOR,
        "apify_defaults": set(_APIFY_ENDPOINT_DEFAULTS),
        "apify_mapped": mapped,
    }


def _live_summary(catalog: Any, tools: Any, ledger: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": catalog.schema_version,
        "contract_version": tools.contract_version,
        "catalog_digest": catalog.catalog_digest,
        "tool_catalog_digest": tools.catalog_digest,
        "source_entry_count": catalog.source_entry_count,
        "capability_count": catalog.capability_count,
        "unique_endpoint_count": catalog.unique_endpoint_count,
        "platform_count": catalog.platform_count,
        "tool_count": tools.tool_count,
        "canonical_tool_count": tools.canonical_tool_count,
        "executable_count": tools.executable_count,
        "endpoint_mappings": len(ledger["mapping"]),
        "collector_definitions": len(ledger["declared"]),
        "collector_registered": len(ledger["registry"]),
        "declared_without_impl": sorted(ledger["declared"] - ledger["registry"]),
        "registered_without_declaration": sorted(ledger["registry"] - ledger["declared"]),
        "apify_defaults": len(ledger["apify_defaults"]),
        "apify_mapped": len(ledger["apify_mapped"]),
        "policy_counts": {name: len(group) for name, group in ledger["policy"].items()},
        "policy_unclassified": sorted(ledger["registry"] - ledger["classified"]),
        "policy_unknown_types": sorted(ledger["classified"] - ledger["registry"]),
    }


def _check_digest_format(
    checks: list[dict[str, Any]], layer: str, digest: Any
) -> None:
    if digest is None:
        return
    ok = isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest) is not None
    _add_check(
        checks,
        f"digest.format.{layer}",
        ok=ok,
        layer=layer,
        field="catalog_digest",
        expected="^[0-9a-f]{64}$",
        actual=digest,
        message="" if ok else f"{layer} 的 catalog_digest 不是 sha256 十六进制",
    )


def _check_live(summary: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    _expect(
        checks,
        "live.schema_version",
        actual=summary["schema_version"],
        expected=PACKAGE_LOCK_SCHEMA,
        layer="live",
        field="schema_version",
        message="平台包目录版本必须是 platform-packages.v1",
    )
    _expect(
        checks,
        "live.contract_version",
        actual=summary["contract_version"],
        expected=TOOL_CONTRACT_VERSION,
        layer="live",
        field="contract_version",
        message="工具契约版本必须是 tool.v1",
    )
    _expect(
        checks,
        "live.tool_count_eq_unique_endpoint_count",
        actual=summary["tool_count"],
        expected=summary["unique_endpoint_count"],
        layer="live",
        field="tool_count",
        message="工具数必须等于唯一端点数",
    )
    _expect(
        checks,
        "live.unique_endpoint_count_eq_endpoint_mappings",
        actual=summary["unique_endpoint_count"],
        expected=summary["endpoint_mappings"],
        layer="live",
        field="unique_endpoint_count",
        message="唯一端点数必须等于端点映射数",
    )
    _expect(
        checks,
        "live.capability_count_eq_source_entry_count",
        actual=summary["capability_count"],
        expected=summary["source_entry_count"],
        layer="live",
        field="capability_count",
        message="视图条目数必须等于源条目数",
    )
    _expect(
        checks,
        "live.canonical_tool_count_eq_tool_count",
        actual=summary["canonical_tool_count"],
        expected=summary["tool_count"],
        layer="live",
        field="canonical_tool_count",
        message="规范工具数必须等于工具数",
    )
    _expect(
        checks,
        "live.tool_digest_eq_package_digest",
        actual=summary["tool_catalog_digest"],
        expected=summary["catalog_digest"],
        layer="live",
        field="catalog_digest",
        message="工具目录必须复制平台包 digest",
    )
    policy_total = sum(summary["policy_counts"].values())
    _expect(
        checks,
        "live.policy_sum_eq_registered",
        actual=policy_total,
        expected=summary["collector_registered"],
        layer="live",
        field="policy_counts",
        message="策略四组合计必须等于注册实现数",
    )
    coverage = {
        "unclassified": summary["policy_unclassified"],
        "unknown_types": summary["policy_unknown_types"],
    }
    _add_check(
        checks,
        "live.policy_covers_registry",
        ok=not summary["policy_unclassified"] and not summary["policy_unknown_types"],
        layer="live",
        field="policy",
        expected={"unclassified": [], "unknown_types": []},
        actual=coverage,
        message="策略组必须无遗漏、无未知类型地覆盖注册表",
    )
    _expect(
        checks,
        "live.collector_declared_without_impl",
        actual=summary["declared_without_impl"],
        expected=sorted(KNOWN_DECLARED_WITHOUT_IMPL),
        layer="ledger",
        field="declared_without_impl",
        severity="blocker",
        message="采集器账本变化：只声明未实现集合与已知白名单不同",
    )
    _expect(
        checks,
        "live.collector_registered_without_declaration",
        actual=summary["registered_without_declaration"],
        expected=sorted(KNOWN_REGISTERED_WITHOUT_DECLARATION),
        layer="ledger",
        field="registered_without_declaration",
        severity="blocker",
        message="采集器账本变化：已实现未声明集合与已知白名单不同",
    )
    _expect(
        checks,
        "live.apify_defaults_eq_mapped",
        actual=summary["apify_mapped"],
        expected=summary["apify_defaults"],
        layer="live",
        field="apify",
        message="Apify Actor 配置数必须等于映射数",
    )


def _check_tool_lock(
    lock: dict[str, Any] | None,
    live: dict[str, Any],
    checks: list[dict[str, Any]],
) -> None:
    if lock is None:
        _add_check(
            checks,
            "tool_lock.present",
            ok=False,
            layer="tool_lock",
            expected="configs/tool-catalog.lock.json",
            actual=None,
            message="缺少工具锁文件",
        )
        return
    _add_check(checks, "tool_lock.present", ok=True, layer="tool_lock")
    _check_digest_format(checks, "tool_lock", lock.get("catalog_digest"))
    pairs = (
        (
            "tool_lock.schema_version",
            "schema_version",
            TOOL_LOCK_SCHEMA,
        ),
        (
            "tool_lock.contract_version_eq_live",
            "contract_version",
            TOOL_CONTRACT_VERSION,
        ),
        ("tool_lock.digest_eq_live", "catalog_digest", live["catalog_digest"]),
        ("tool_lock.tool_count_eq_live", "tool_count", live["tool_count"]),
        (
            "tool_lock.canonical_tool_count_eq_live",
            "canonical_tool_count",
            live["canonical_tool_count"],
        ),
        (
            "tool_lock.executable_count_eq_live",
            "executable_count",
            live["executable_count"],
        ),
    )
    for check_id, field, expected in pairs:
        _expect(
            checks,
            check_id,
            actual=lock.get(field),
            expected=expected,
            layer="tool_lock",
            field=field,
        )


def _check_package_lock(
    lock: dict[str, Any] | None,
    live: dict[str, Any],
    checks: list[dict[str, Any]],
) -> None:
    if lock is None:
        _add_check(
            checks,
            "package_lock.present",
            ok=False,
            layer="package_lock",
            expected="configs/platform-packages.lock.json",
            actual=None,
            message="缺少平台包锁文件",
        )
        return
    _add_check(checks, "package_lock.present", ok=True, layer="package_lock")
    _check_digest_format(checks, "package_lock", lock.get("catalog_digest"))
    pairs = (
        (
            "package_lock.schema_version",
            "schema_version",
            PACKAGE_LOCK_SCHEMA,
        ),
        ("package_lock.digest_eq_live", "catalog_digest", live["catalog_digest"]),
        (
            "package_lock.platform_count_eq_live",
            "platform_count",
            live["platform_count"],
        ),
        (
            "package_lock.capability_count_eq_live",
            "capability_count",
            live["capability_count"],
        ),
        (
            "package_lock.unique_endpoint_count_eq_live",
            "unique_endpoint_count",
            live["unique_endpoint_count"],
        ),
    )
    for check_id, field, expected in pairs:
        _expect(
            checks,
            check_id,
            actual=lock.get(field),
            expected=expected,
            layer="package_lock",
            field=field,
        )


def _generated_summary(index: dict[str, Any]) -> dict[str, Any]:
    summary = {
        key: index.get(key)
        for key in (
            "schema_version",
            "catalog_digest",
            "source_entry_count",
            "capability_count",
            "unique_endpoint_count",
            "platform_count",
        )
    }
    packages = index.get("packages")
    summary["package_count"] = len(packages) if isinstance(packages, list) else None
    return summary


def _check_generated(
    index: dict[str, Any] | None,
    live: dict[str, Any],
    checks: list[dict[str, Any]],
    skips: list[dict[str, str]],
    *,
    require_generated: bool,
) -> None:
    if index is None:
        if require_generated:
            _add_check(
                checks,
                "generated.present",
                ok=False,
                layer="generated_index",
                expected="generated/platform-packages.json",
                actual=None,
                message="--require-generated 已开启，但生成物不存在",
            )
        else:
            skips.append(
                {
                    "check_id": "generated.present",
                    "reason": "生成物不存在；未加 --require-generated",
                }
            )
        return
    _add_check(checks, "generated.present", ok=True, layer="generated_index")
    _check_digest_format(checks, "generated_index", index.get("catalog_digest"))
    pairs = (
        (
            "generated.schema_version",
            "schema_version",
            PACKAGE_LOCK_SCHEMA,
        ),
        (
            "generated.digest_eq_live",
            "catalog_digest",
            live["catalog_digest"],
        ),
        (
            "generated.source_entry_count_eq_live_capability_count",
            "source_entry_count",
            live["capability_count"],
        ),
        (
            "generated.capability_count_eq_live",
            "capability_count",
            live["capability_count"],
        ),
        (
            "generated.unique_endpoint_count_eq_live",
            "unique_endpoint_count",
            live["unique_endpoint_count"],
        ),
        (
            "generated.platform_count_eq_live",
            "platform_count",
            live["platform_count"],
        ),
    )
    for check_id, field, expected in pairs:
        _expect(
            checks,
            check_id,
            actual=index.get(field),
            expected=expected,
            layer="generated_index",
            field=field,
        )

    from pydantic import ValidationError

    from data_intelligence_hub.platform_packages.builder import compute_catalog_digest
    from data_intelligence_hub.platform_packages.models import PlatformPackageCatalog

    try:
        generated_catalog = PlatformPackageCatalog.model_validate(index)
    except ValidationError as exc:
        _add_check(
            checks,
            "generated.valid",
            ok=False,
            layer="generated_index",
            field="packages",
            expected="PlatformPackageCatalog",
            actual=str(exc),
            message="生成物结构非法，无法重算内容摘要",
        )
        return
    # 重算内容摘要时剔除环境派生字段。label、endpoint_type 等稳定字段
    # 被改动时，这里给出字段级 expected/actual，不依赖顶层声明的 digest。
    _expect(
        checks,
        "generated.recomputed_digest_eq_live",
        actual=compute_catalog_digest(generated_catalog.packages),
        expected=live["catalog_digest"],
        layer="generated_index",
        field="packages",
        message="生成物内容摘要与运行时不一致；label/endpoint_type 等字段被改动",
    )


def build_report(root: Path, *, require_generated: bool) -> dict[str, Any]:
    catalog, tools = asyncio.run(_build_live())
    ledger = _build_ledger()
    live = _live_summary(catalog, tools, ledger)

    checks: list[dict[str, Any]] = []
    skips: list[dict[str, str]] = []
    _check_digest_format(checks, "live", live["catalog_digest"])
    _check_live(live, checks)

    tool_lock_path = root / "configs/tool-catalog.lock.json"
    package_lock_path = root / "configs/platform-packages.lock.json"
    generated_path = root / "generated/platform-packages.json"
    tool_lock = _read_json(tool_lock_path) if tool_lock_path.is_file() else None
    package_lock = _read_json(package_lock_path) if package_lock_path.is_file() else None
    generated = _read_json(generated_path) if generated_path.is_file() else None

    _check_tool_lock(tool_lock, live, checks)
    _check_package_lock(package_lock, live, checks)
    _check_generated(
        generated,
        live,
        checks,
        skips,
        require_generated=require_generated,
    )

    violations = [
        check for check in checks if not check["ok"] and check["severity"] == "blocker"
    ]
    warnings = [
        check for check in checks if not check["ok"] and check["severity"] == "warning"
    ]
    problems = [f"{check['check_id']}: {check['message']}" for check in violations]
    layers_present = {
        "live": "present",
        "tool_lock": "present" if tool_lock is not None else "missing",
        "package_lock": "present" if package_lock is not None else "missing",
        "generated_index": "present" if generated is not None else "missing",
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "failed" if violations else "passed",
        "exit_code": 1 if violations else 0,
        "require_generated": require_generated,
        "layers_present": layers_present,
        "counts": {
            "live": live,
            "tool_lock": tool_lock,
            "package_lock": package_lock,
            "generated_index": _generated_summary(generated) if generated else None,
        },
        "layers": {
            "live": live,
            "tool_lock": tool_lock,
            "package_lock": package_lock,
            "generated_index": _generated_summary(generated) if generated else None,
        },
        "checks": checks,
        "violations": violations,
        "warnings": warnings,
        "skips": skips,
        "problems": problems,
    }


def _error_report(require_generated: bool, message: str) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "error",
        "exit_code": 2,
        "require_generated": require_generated,
        "layers_present": {
            "live": "missing",
            "tool_lock": "missing",
            "package_lock": "missing",
            "generated_index": "missing",
        },
        "counts": {},
        "layers": {},
        "checks": [],
        "violations": [],
        "warnings": [],
        "skips": [],
        "problems": [message],
    }


def _emit(report: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"catalog guard: {report['status']}")
    for layer, state in report["layers_present"].items():
        print(f"  {layer}: {state}")
    for problem in report["problems"]:
        print(f"  FAIL {problem}")
    for check in report["warnings"]:
        print(f"  WARN {check['check_id']}: {check['message']}")
    for skip in report["skips"]:
        print(f"  SKIP {skip['check_id']}: {skip['reason']}")
    if report["status"] == "passed":
        print("OK: 目录锁全部一致。")


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args.root, require_generated=args.require_generated)
    except GuardInputError as exc:
        report = _error_report(args.require_generated, str(exc))
        _emit(report, args.json)
        return 2
    _emit(report, args.json)
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())

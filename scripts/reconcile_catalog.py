#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/reconcile_catalog.py
#
# 对账四套目录数字，输出结构化摘要。
#
# 单位说明：source_entry_count 是视图条目数（312）。
# unique_endpoint_count 是唯一端点数（284）。
# endpoint_mappings 也是唯一端点数（284）。
# 两者不能混用。
#
# 本脚本只读地算差集与计数，供 CI 与人工复核使用。
# 锁文件请用 scripts/test_tool_catalog.py --update-lock 更新。
# 平台包锁请用 scripts/generate_platform_packages.py --update-lock 更新。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

OUTCOME_KINDS = ("offline", "guarded_http", "provider_api", "unsupported")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile catalog counts")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    return parser.parse_args()


def build_summary(root: Path) -> dict[str, object]:
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

    mapping = _ENDPOINT_TO_COLLECTOR
    apify_defaults = _APIFY_ENDPOINT_DEFAULTS
    apify_mapped = {key for key, value in mapping.items() if value == "apify_actor"}

    declared_types = {definition.type for definition in COLLECTOR_CATALOG}

    summary: dict[str, object] = {
        "collector_definitions": len(COLLECTOR_CATALOG),
        "collector_registered": len(COLLECTOR_REGISTRY),
        "collector_declared_without_impl": sorted(declared_types - set(COLLECTOR_REGISTRY)),
        "collector_registered_without_declaration": sorted(
            set(COLLECTOR_REGISTRY) - declared_types
        ),
        "endpoint_mappings": len(mapping),
        "apify_defaults": len(apify_defaults),
        "apify_mapped": len(apify_mapped),
        "apify_defaults_without_mapping": sorted(set(apify_defaults) - set(mapping)),
        "apify_mapped_without_actor": sorted(apify_mapped - set(apify_defaults)),
        "policy": {
            "offline": len(OFFLINE_COLLECTORS),
            "guarded_http": len(GUARDED_HTTP_COLLECTORS),
            "provider_api": len(PROVIDER_API_COLLECTORS),
            "unsupported": len(UNSUPPORTED_COLLECTORS),
        },
    }

    classified = (
        set(OFFLINE_COLLECTORS)
        | set(GUARDED_HTTP_COLLECTORS)
        | set(PROVIDER_API_COLLECTORS)
        | set(UNSUPPORTED_COLLECTORS)
    )
    summary["policy_classified_total"] = len(classified)
    summary["policy_unclassified"] = sorted(set(COLLECTOR_REGISTRY) - classified)
    summary["policy_unknown_types"] = sorted(classified - set(COLLECTOR_REGISTRY))

    generated_path = root / "generated/platform-packages.json"
    if generated_path.exists():
        generated = json.loads(generated_path.read_text(encoding="utf-8"))
        summary["generated"] = {
            "source_entry_count": generated.get("source_entry_count"),
            "capability_count": generated.get("capability_count"),
            "unique_endpoint_count": generated.get("unique_endpoint_count"),
            "platform_count": generated.get("platform_count"),
            "catalog_digest": generated.get("catalog_digest"),
        }
    else:
        summary["generated"] = None

    return summary


def check_invariants(summary: dict[str, object]) -> list[str]:
    """返回违规项。空列表表示全部通过。"""
    problems: list[str] = []

    if summary["apify_defaults_without_mapping"]:
        problems.append(
            "apify 有 Actor 配置但无端点映射："
            + ", ".join(summary["apify_defaults_without_mapping"])  # type: ignore[arg-type]
        )
    if summary["apify_mapped_without_actor"]:
        problems.append(
            "端点映射到 apify_actor 但无 Actor 配置："
            + ", ".join(summary["apify_mapped_without_actor"])  # type: ignore[arg-type]
        )
    if summary["policy_unclassified"]:
        problems.append(
            "已注册 collector 未分类到任何策略组："
            + ", ".join(summary["policy_unclassified"])  # type: ignore[arg-type]
        )
    if summary["policy_unknown_types"]:
        problems.append(
            "策略组含未注册 collector："
            + ", ".join(summary["policy_unknown_types"])  # type: ignore[arg-type]
        )

    policy = summary["policy"]
    total = sum(policy.values())  # type: ignore[arg-type]
    if total != summary["policy_classified_total"]:
        problems.append(f"策略组合计 {total} 与去重后 {summary['policy_classified_total']} 不符")

    generated = summary.get("generated")
    if isinstance(generated, dict):
        # 生成物的唯一端点数与端点映射同单位，必须相等。
        # 不要拿 source_entry_count（视图条目）与 endpoint_mappings 比较。
        if generated.get("unique_endpoint_count") != summary["endpoint_mappings"]:
            problems.append(
                "generated 唯一端点数 "
                f"{generated.get('unique_endpoint_count')} "
                f"与端点映射 {summary['endpoint_mappings']} 不一致；生成物可能过期"
            )
        if generated.get("capability_count") != generated.get("source_entry_count"):
            problems.append(
                "generated capability_count "
                f"{generated.get('capability_count')} "
                f"与 source_entry_count {generated.get('source_entry_count')} 不一致"
            )
    return problems


def main() -> int:
    args = parse_args()
    summary = build_summary(args.root)
    problems = check_invariants(summary)

    if args.json:
        print(json.dumps({"summary": summary, "problems": problems}, ensure_ascii=False, indent=2))
    else:
        print("== 采集器 ==")
        print(f"  声明  {summary['collector_definitions']}")
        print(f"  注册  {summary['collector_registered']}")
        print(f"  只声明未实现 {len(summary['collector_declared_without_impl'])}")  # type: ignore[arg-type]
        print("== 端点 ==")
        print(f"  映射  {summary['endpoint_mappings']}")
        print(f"  Apify Actor 配置 {summary['apify_defaults']}")
        print(f"  Apify 映射 {summary['apify_mapped']}")
        print("== 策略 ==")
        for kind, count in summary["policy"].items():  # type: ignore[union-attr]
            print(f"  {kind:14s} {count}")
        generated = summary.get("generated")
        if isinstance(generated, dict):
            print("== 生成物 ==")
            print(
                f"  条目 {generated.get('source_entry_count')} / "
                f"唯一端点 {generated.get('unique_endpoint_count')} / "
                f"平台 {generated.get('platform_count')}"
            )
        if problems:
            print("\n== 违规 ==")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print("\nOK: 全部不变量通过。")


    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

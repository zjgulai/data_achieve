#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/test_tool_catalog.py
#
# 校验统一工具目录契约。
# 只读：不写 generated/，不触发采集。

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate unified tool catalog contract")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--update-lock",
        action="store_true",
        help="写入 configs/tool-catalog.lock.json（仅在契约有意变更时使用）",
    )
    return parser.parse_args()


def _lock_payload(tools) -> dict[str, object]:
    return {
        "schema_version": tools.schema_version,
        "contract_version": tools.contract_version,
        "catalog_digest": tools.catalog_digest,
        "tool_count": tools.tool_count,
        "canonical_tool_count": tools.canonical_tool_count,
        "executable_count": tools.executable_count,
    }


async def _build(root: Path):
    from data_intelligence_hub.api.routes.collectors import get_collector_catalog
    from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
    from data_intelligence_hub.tool_catalog.projection import build_tool_catalog

    source = await get_collector_catalog()
    catalog = build_platform_package_catalog(source)
    return catalog, build_tool_catalog(catalog)


def validate(root: Path) -> dict[str, object]:
    failures: list[str] = []
    catalog, tools = asyncio.run(_build(root))
    lock_path = root / "configs/tool-catalog.lock.json"

    # 1. 唯一性：tool_id 必须唯一，且与唯一端点一致。
    tool_ids = [item.tool_id for item in tools.tools]
    if len(tool_ids) != len(set(tool_ids)):
        failures.append("tool_id_not_unique")
    if tools.tool_count != catalog.unique_endpoint_count:
        failures.append(
            f"tool_count:{tools.tool_count}:{catalog.unique_endpoint_count}"
        )

    # 2. 别名必须指回一个存在的规范标识。
    known = set(tool_ids)
    for item in tools.tools:
        if item.canonical_tool_id not in known:
            failures.append(f"dangling_canonical:{item.tool_id}")

    # 3. 摘要必须与来源目录一致。
    if tools.catalog_digest != catalog.catalog_digest:
        failures.append("digest_mismatch")

    # 4. 不得凭空出现非采集风险类别或非记录输出。
    risk = {item.risk_class for item in tools.tools}
    if risk != {"read"}:
        failures.append(f"unexpected_risk_class:{','.join(sorted(risk))}")
    output = {item.output_kind for item in tools.tools}
    if output != {"records"}:
        failures.append(f"unexpected_output_kind:{','.join(sorted(output))}")

    # 5. 可用性只允许已定义的取值。
    allowed = {"verified", "config-gated", "degraded", "empty", "untested", "disabled"}
    for item in tools.tools:
        if item.availability_view.availability not in allowed:
            failures.append(f"bad_availability:{item.tool_id}")

    # 6. 契约锁比对（锁文件存在时）。
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        for key in ("schema_version", "contract_version", "catalog_digest"):
            if lock.get(key) != getattr(tools, key, None):
                failures.append(f"tool_lock_mismatch:{key}")
        for key in ("tool_count", "canonical_tool_count"):
            if lock.get(key) != getattr(tools, key):
                failures.append(f"tool_lock_mismatch:{key}")

    return {
        "status": "passed" if not failures else "failed",
        "contract_version": tools.contract_version,
        "schema_version": tools.schema_version,
        "tool_count": tools.tool_count,
        "canonical_tool_count": tools.canonical_tool_count,
        "executable_count": tools.executable_count,
        "catalog_digest": tools.catalog_digest,
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    if args.update_lock:
        _, tools = asyncio.run(_build(args.root))
        lock_path = args.root / "configs/tool-catalog.lock.json"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(_lock_payload(tools), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = validate(args.root)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

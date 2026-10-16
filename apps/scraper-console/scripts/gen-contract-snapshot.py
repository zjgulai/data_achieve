#!/usr/bin/env python3
"""生成快速采集表单的契约快照。

用途：给 scripts/acceptance-quick-collect-form.ts 提供输入。
快照入库，使验收可在不启动后端的情况下复现。

运行（必须用 api 的虚拟环境）：

    cd apps/scraper-console
    pnpm snapshot

输出：generated/console-contract-snapshot.json

该目录不入库。快照随用随生成，避免过期文件静默通过检查。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 允许从任意工作目录运行。
REPO = Path(__file__).resolve().parents[3]
API_SRC = REPO / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from data_intelligence_hub.api.routes.collectors import get_collector_catalog  # noqa: E402
from data_intelligence_hub.platform_packages.builder import (  # noqa: E402
    build_platform_package_catalog,
)
from data_intelligence_hub.tool_catalog.projection import build_tool_catalog  # noqa: E402
from data_intelligence_hub.tool_catalog.public import to_public_tool  # noqa: E402

# 输出到 generated/。该目录被 gitignore，不入库。
OUT = REPO / "generated" / "console-contract-snapshot.json"


async def main() -> int:
    source = await get_collector_catalog()
    tools = build_tool_catalog(build_platform_package_catalog(source))
    rows = [endpoint for group in source.collectors for endpoint in group.endpoints]

    # 端点级提示。同一类型取首个非空。
    hints: dict[str, dict[str, str]] = {}
    for endpoint in rows:
        if endpoint.param_fields and endpoint.endpoint_type not in hints:
            hints[endpoint.endpoint_type] = dict(endpoint.param_fields)

    snapshot = {
        "generated_from": "apps/api 的 get_collector_catalog 与 build_tool_catalog",
        "tools": [json.loads(to_public_tool(tool).model_dump_json()) for tool in tools.tools],
        "endpoints": [
            {
                "endpoint_type": endpoint.endpoint_type,
                "label": endpoint.label,
                "status": endpoint.status,
                "required_params": list(endpoint.required_params),
                "optional_params": list(endpoint.optional_params),
                "policy_block_reason": endpoint.policy_block_reason,
                "param_fields": hints.get(endpoint.endpoint_type, {}),
            }
            for endpoint in rows
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )

    print(f"工具 {len(snapshot['tools'])} 个")
    print(f"端点 {len(snapshot['endpoints'])} 行")
    print(f"带提示的端点 {len(hints)} 个")
    print(f"写入 {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

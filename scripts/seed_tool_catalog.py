#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/seed_tool_catalog.py
# cd apps/api && uv run python ../../scripts/seed_tool_catalog.py --json
#
# 把只读工具目录写入 tool_catalog 表。
# 脚本可重复执行。已存在的 tool_id 会更新，不存在的会插入。
# 提交权在脚本入口。仓储只调用 flush。
#
# 运行前必须先执行 alembic upgrade head，让表存在。

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the tool_catalog table")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    return parser.parse_args()


async def _seed() -> dict[str, object]:
    """取目录、写表、提交，并返回计数摘要。"""
    from data_intelligence_hub.core.database import async_session_factory, engine
    from data_intelligence_hub.repositories.tool_catalog import count_tools, upsert_tools
    from data_intelligence_hub.tool_catalog.service import get_tool_catalog

    try:
        async with async_session_factory() as session:
            catalog = await get_tool_catalog(session)
            written = await upsert_tools(
                session,
                catalog.tools,
                schema_version=catalog.schema_version,
            )
            await session.commit()
            total = await count_tools(session)
    finally:
        await engine.dispose()

    return {
        "inserted": written.inserted,
        "updated": written.updated,
        "written": written.total,
        "total": total,
        "tool_count": catalog.tool_count,
        "executable_count": catalog.executable_count,
        "catalog_digest": catalog.catalog_digest,
        "schema_version": catalog.schema_version,
        "contract_version": catalog.contract_version,
    }


def main() -> int:
    args = parse_args()
    try:
        summary = asyncio.run(_seed())
    except SQLAlchemyError as exc:
        message = (
            "种子失败：数据库不可用，或 tool_catalog 表不存在。"
            "先执行 alembic upgrade head。"
        )
        print(f"{message}\n{exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print("== tool_catalog 种子 ==")
    print(f"  插入  {summary['inserted']}")
    print(f"  更新  {summary['updated']}")
    print(f"  表内  {summary['total']}")
    print(f"  目录  {summary['tool_count']}")
    print(f"  可执行 {summary['executable_count']}")
    print(f"  摘要  {summary['catalog_digest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/generate_platform_packages.py

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.generator import generate_platform_packages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate platform Skill packages")
    parser.add_argument("--update-lock", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    source = await get_collector_catalog()
    catalog = build_platform_package_catalog(source)
    generate_platform_packages(catalog, project_root)
    if args.update_lock:
        lock = {
            "schema_version": catalog.schema_version,
            "catalog_digest": catalog.catalog_digest,
            "platform_count": catalog.platform_count,
            "capability_count": catalog.capability_count,
            "unique_endpoint_count": catalog.unique_endpoint_count,
        }
        (project_root / "configs/platform-packages.lock.json").write_text(
            json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        f"generated {catalog.platform_count} platform packages "
        f"covering {catalog.unique_endpoint_count} unique endpoints"
    )


if __name__ == "__main__":
    asyncio.run(main())

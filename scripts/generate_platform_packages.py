#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/generate_platform_packages.py

from __future__ import annotations

import asyncio
from pathlib import Path

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.generator import generate_platform_packages


async def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = await get_collector_catalog()
    catalog = build_platform_package_catalog(source)
    generate_platform_packages(catalog, project_root)
    print(
        f"generated {catalog.platform_count} platform packages "
        f"covering {catalog.unique_endpoint_count} unique endpoints"
    )


if __name__ == "__main__":
    asyncio.run(main())

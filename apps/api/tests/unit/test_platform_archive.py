from __future__ import annotations

import asyncio

from data_intelligence_hub.platform_packages.service import build_platform_skill_archive


def test_platform_archive_is_deterministic() -> None:
    first = asyncio.run(build_platform_skill_archive("tiktok"))
    second = asyncio.run(build_platform_skill_archive("tiktok"))

    assert first == second

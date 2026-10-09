from __future__ import annotations

import asyncio
import json
from pathlib import Path

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.platform_packages.notes import (
    SECRET_VALUE_RE,
    _PRIVATE_KEY_RE,
)
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.generator import generate_platform_packages


def test_generator_writes_complete_safe_packages(tmp_path: Path) -> None:
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)

    generate_platform_packages(catalog, tmp_path)

    index = json.loads((tmp_path / "generated/platform-packages.json").read_text())
    skill_dirs = sorted((tmp_path / "generated/platform-skills").iterdir())
    playbooks = sorted((tmp_path / "docs/playbooks/platforms").glob("*.md"))
    assert len(index["packages"]) == 70
    assert len(skill_dirs) == 70
    assert len(playbooks) == 70
    for skill_dir in skill_dirs:
        required = {
            "SKILL.md",
            "README.md",
            "manifest.json",
            "evals/trigger_cases.json",
            "references/playbook.md",
        }
        actual = {
            str(path.relative_to(skill_dir))
            for path in skill_dir.rglob("*")
            if path.is_file()
        }
        assert required <= actual
        skill_text = (skill_dir / "SKILL.md").read_text()
        assert skill_text.startswith("---\nname:")
        assert "https://scrapy.luteos.com" in skill_text
        # 只拦“疑似真实密钥值”，占位符如 `EXA_API_KEY=<key>` 不算泄漏
        assert SECRET_VALUE_RE.search(skill_text) is None
        assert _PRIVATE_KEY_RE.search(skill_text) is None
        cases = json.loads((skill_dir / "evals/trigger_cases.json").read_text())
        assert sum(case["should_trigger"] for case in cases) >= 2
        assert sum(not case["should_trigger"] for case in cases) >= 2


def test_generator_is_idempotent(tmp_path: Path) -> None:
    source = asyncio.run(get_collector_catalog())
    catalog = build_platform_package_catalog(source)
    generate_platform_packages(catalog, tmp_path)
    first = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    generate_platform_packages(catalog, tmp_path)

    second = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert first == second

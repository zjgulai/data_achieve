from __future__ import annotations

import json
import shutil
from pathlib import Path

from data_intelligence_hub.platform_packages.models import PlatformPackageCatalog
from data_intelligence_hub.platform_packages.renderers import (
    render_playbook,
    render_readme,
    render_skill,
    render_trigger_cases,
)


def generate_platform_packages(
    catalog: PlatformPackageCatalog,
    root: Path,
) -> None:
    generated_root = root / "generated"
    skill_root = generated_root / "platform-skills"
    playbook_root = root / "docs/playbooks/platforms"
    if skill_root.exists():
        shutil.rmtree(skill_root)
    if playbook_root.exists():
        shutil.rmtree(playbook_root)
    skill_root.mkdir(parents=True)
    playbook_root.mkdir(parents=True)
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "platform-packages.json").write_text(
        catalog.model_dump_json(indent=2),
        encoding="utf-8",
    )
    for package in catalog.packages:
        package_root = skill_root / package.platform_id
        (package_root / "evals").mkdir(parents=True)
        (package_root / "references").mkdir(parents=True)
        manifest = {
            "schema_version": catalog.schema_version,
            "catalog_digest": catalog.catalog_digest,
            **package.model_dump(mode="json"),
        }
        (package_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (package_root / "SKILL.md").write_text(render_skill(package), encoding="utf-8")
        (package_root / "README.md").write_text(render_readme(package), encoding="utf-8")
        playbook = render_playbook(package)
        (package_root / "references/playbook.md").write_text(playbook, encoding="utf-8")
        (package_root / "evals/trigger_cases.json").write_text(
            render_trigger_cases(package),
            encoding="utf-8",
        )
        (playbook_root / f"{package.platform_id}.md").write_text(
            playbook,
            encoding="utf-8",
        )

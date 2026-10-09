from __future__ import annotations

import json
import shutil
from pathlib import Path

from data_intelligence_hub.platform_packages.models import CapabilityNote, PlatformPackageCatalog
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

    (playbook_root.parent / "【坑点库】DIH-平台采集坑点汇总.md").write_text(
        _render_notes_library(catalog),
        encoding="utf-8",
    )


def _render_notes_library(catalog: PlatformPackageCatalog) -> str:
    """把所有平台的策展坑点汇总为一份可提交的项目文档。"""
    entries: list[tuple[str, CapabilityNote]] = []
    for package in catalog.packages:
        for note in package.platform_notes:
            entries.append((package.platform_id, note))
        for endpoint in package.endpoints:
            for note in endpoint.notes:
                entries.append((package.platform_id, note))

    lines = [
        "---",
        "name: dih-platform-pitfalls",
        "description: Data Intelligence Hub 全平台采集坑点与限制汇总，由平台工具包生成器自动生成，"
        "按失败分类分组。当排查采集失败或评估能力边界时使用。",
        "---",
        "",
        "# 平台采集坑点库",
        "",
        f"> 自动生成，请勿手工编辑。catalog_digest：`{catalog.catalog_digest}`",
        f"> 坑点总数：{len(entries)} · 覆盖平台：{len({p for p, _ in entries})}",
        "",
    ]
    if not entries:
        lines.append("_当前没有已策展的坑点。_")
        return "\n".join(lines) + "\n"

    by_class: dict[str, list[tuple[str, CapabilityNote]]] = {}
    for platform_id, note in entries:
        by_class.setdefault(note.failure_class or "uncategorized", []).append((platform_id, note))

    for failure_class in sorted(by_class):
        lines.append(f"## {failure_class}")
        lines.append("")
        lines.append("| 平台 | 范围 | 症状 | 原因 | 规避/修复 | 严重度 | 已验证 | 来源 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for platform_id, note in sorted(by_class[failure_class], key=lambda item: item[0]):
            def esc(v: str) -> str:
                return v.replace("|", "/").replace("\n", " ").strip()

            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    platform_id,
                    note.target,
                    esc(note.symptom),
                    esc(note.cause),
                    esc(note.workaround),
                    note.severity,
                    note.verified_at.isoformat() if note.verified_at else "—",
                    esc(note.source_ref or "—"),
                )
            )
        lines.append("")
    return "\n".join(lines) + "\n"

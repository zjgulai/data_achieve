#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/test_platform_packages.py

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

# 与 data_intelligence_hub.platform_packages.notes 保持一致：只拦“疑似真实密钥值”，
# 占位符（如 `EXA_API_KEY=...`）不算。
SECRET_VALUE_RE = re.compile(
    r"(api[_-]?key|apikey|password|passwd|secret|bearer|private\s+key)"
    r"\s*[:=]\s*([A-Za-z0-9_\-]{16,})",
    re.IGNORECASE,
)
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated platform packages")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base-url", default="https://scrapy.luteos.com")
    parser.add_argument("--platform")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _note_failures(note: dict, known_endpoints: set[str], platform_id: str) -> list[str]:
    out: list[str] = []
    for field in ("symptom", "cause", "workaround"):
        if not str(note.get(field, "")).strip():
            out.append(f"note_empty_field:{platform_id}:{note.get('target')}:{field}")
    if note.get("scope") == "endpoint" and note.get("target") not in known_endpoints:
        out.append(f"note_unknown_target:{platform_id}:{note.get('target')}")
    if note.get("severity") not in {"info", "warning", "blocker"}:
        out.append(f"note_bad_severity:{platform_id}:{note.get('target')}")
    return out


def validate_packages(root: Path, platform_filter: str | None) -> dict[str, object]:
    index_path = root / "generated/platform-packages.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    lock = json.loads((root / "configs/platform-packages.lock.json").read_text())
    packages = [
        package
        for package in index["packages"]
        if platform_filter is None or package["platform_id"] == platform_filter
    ]
    failures: list[str] = []
    capability_ids: set[str] = set()
    endpoint_types: set[str] = set()
    note_count = 0
    for package in packages:
        platform_id = package["platform_id"]
        skill_root = root / "generated/platform-skills" / platform_id
        required_paths = (
            skill_root / "SKILL.md",
            skill_root / "README.md",
            skill_root / "manifest.json",
            skill_root / "evals/trigger_cases.json",
            skill_root / "references/playbook.md",
            root / "docs/playbooks/platforms" / f"{platform_id}.md",
        )
        failures.extend(
            f"missing:{path.relative_to(root)}" for path in required_paths if not path.is_file()
        )
        known = {endpoint["endpoint_type"] for endpoint in package["endpoints"]}
        for note in package.get("platform_notes", []):
            note_count += 1
            failures.extend(_note_failures(note, known, platform_id))
        for endpoint in package["endpoints"]:
            capability_ids.add(endpoint["capability_id"])
            endpoint_types.add(endpoint["endpoint_type"])
            for note in endpoint.get("notes", []):
                note_count += 1
                failures.extend(_note_failures(note, known, platform_id))
            if not endpoint["required_params"] and not endpoint["optional_params"]:
                continue
            if endpoint["status"] not in {"verified", "pending", "disabled"}:
                failures.append(f"invalid_status:{endpoint['capability_id']}")
        if skill_root.is_dir():
            combined = "\n".join(
                path.read_text(encoding="utf-8")
                for path in skill_root.rglob("*")
                if path.is_file()
            )
            if SECRET_VALUE_RE.search(combined) or _PRIVATE_KEY_RE.search(combined):
                failures.append(f"secret_marker:{platform_id}")
    expected_platforms = 1 if platform_filter else 74
    if len(packages) != expected_platforms:
        failures.append(f"platform_count:{len(packages)}:{expected_platforms}")
    if platform_filter is None:
        if len(capability_ids) != 278:
            failures.append(f"capability_count:{len(capability_ids)}:278")
        if len(endpoint_types) != 250:
            failures.append(f"endpoint_count:{len(endpoint_types)}:250")
        for key in (
            "schema_version",
            "catalog_digest",
            "platform_count",
            "capability_count",
            "unique_endpoint_count",
        ):
            if lock[key] != index[key]:
                failures.append(f"catalog_lock_mismatch:{key}")
        if note_count and not (root / "docs/playbooks/【坑点库】DIH-平台采集坑点汇总.md").is_file():
            failures.append("missing:pitfalls_library")
    return {
        "status": "passed" if not failures else "failed",
        "platform_count": len(packages),
        "capability_count": len(capability_ids),
        "unique_endpoint_count": len(endpoint_types),
        "note_count": note_count,
        "failures": failures,
    }


def validate_live(base_url: str) -> dict[str, object]:
    with urllib.request.urlopen(f"{base_url}/api/platform-packages", timeout=30) as response:
        catalog = json.load(response)
    with urllib.request.urlopen(f"{base_url}/api/health", timeout=30) as response:
        health = json.load(response)
    return {
        "status": "passed",
        "health": health["status"],
        "platform_count": catalog["platform_count"],
        "catalog_digest": catalog["catalog_digest"],
    }


def main() -> int:
    args = parse_args()
    report: dict[str, object] = {
        "contract": validate_packages(args.root, args.platform),
        "live": validate_live(args.base_url) if args.live else {"status": "not_run"},
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["contract"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

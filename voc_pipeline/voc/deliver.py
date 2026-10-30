"""Artifact registry and delivery manifest.

The handoff must say what is local, uncommitted, unpublished, and not yet
executed.  This module computes hashes instead of trusting filenames.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(run_dir: Path, gate_status: dict[str, str]) -> dict[str, Any]:
    artifacts = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if "raw" in path.parts:
            continue
        artifacts.append(
            {
                "path": str(path.relative_to(run_dir)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    raw_files = [p for p in (run_dir / "raw").rglob("*") if p.is_file()] if (run_dir / "raw").exists() else []
    executed = [g for g, status in gate_status.items() if status in {"PASS", "CONDITIONAL"}]
    return {
        "schema_version": "voc_delivery_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_dir.name,
        "artifacts": artifacts,
        "raw_artifact_count": len(raw_files),
        "delivery_state": {
            "local_only": True,
            "committed": False,
            "published": False,
            "external_claims": False,
        },
        "gates_executed": executed,
        "gates_not_executed": [g for g, status in gate_status.items() if status in {"BLOCKED", "NOT_STARTED"}],
        "not_executed": [
            "G7 双盲编码与 agreement",
            "G8 正式 metric rows",
            "G9 实验审批与 owner 签名",
            "G10 结果复盘",
        ],
    }


def write_manifest(run_dir: Path, gate_status: dict[str, str]) -> Path:
    path = run_dir / "delivery-manifest.json"
    path.write_text(json.dumps(build_manifest(run_dir, gate_status), ensure_ascii=False, indent=1), encoding="utf-8")
    return path

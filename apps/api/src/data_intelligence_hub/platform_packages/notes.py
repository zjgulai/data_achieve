"""策展坑点源的加载器。

策展源位于包内 `platform_packages/notes/<platform_id>.json`（稀疏，可为空目录），
这样 API 容器运行时（playbook 是请求时实时渲染）也能读到。每条 note 含：

    {
      "scope": "platform" | "endpoint",
      "target": "<platform_id>" | "<endpoint_type>",
      "symptom": "...", "cause": "...", "workaround": "...",
      "failure_class": "config_gated", "severity": "warning",
      "verified_at": "2026-10-09", "source_ref": "run:<id>", "tags": ["..."]
    }

顶层可以是 `{"platform_id": "...", "notes": [...]}` 或直接是数组。
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from data_intelligence_hub.platform_packages.models import CapabilityNote

NOTES_DIR = Path(__file__).resolve().parent / "notes"

# 疑似真实密钥（带足够长度的值）；占位符如 `EXA_API_KEY=...` 不匹配。
SECRET_VALUE_PATTERN = (
    r"(api[_-]?key|apikey|password|passwd|secret|bearer|private\s+key)"
    r"\s*[:=]\s*([A-Za-z0-9_\-]{16,})"
)
SECRET_VALUE_RE = re.compile(SECRET_VALUE_PATTERN, re.IGNORECASE)
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

_cache: dict[str, Any] = {"signature": None, "value": None}


class PlatformNotes:
    __slots__ = ("platform_id", "platform_notes", "endpoint_notes")

    def __init__(
        self,
        platform_id: str,
        platform_notes: tuple[CapabilityNote, ...],
        endpoint_notes: Mapping[str, tuple[CapabilityNote, ...]],
    ) -> None:
        self.platform_id = platform_id
        self.platform_notes = platform_notes
        self.endpoint_notes = dict(endpoint_notes)


def _iter_note_files() -> list[Path]:
    if not NOTES_DIR.is_dir():
        return []
    return sorted(NOTES_DIR.glob("*.json"))


def _signature(files: list[Path]) -> tuple[tuple[str, float], ...]:
    return tuple((p.name, p.stat().st_mtime) for p in files)


def _load_file(path: Path) -> PlatformNotes:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        notes_raw: list[dict[str, Any]] = raw
        platform_id = path.stem
    else:
        platform_id = str(raw.get("platform_id") or path.stem)
        notes_raw = list(raw.get("notes", []))

    platform_notes: list[CapabilityNote] = []
    endpoint_notes: dict[str, list[CapabilityNote]] = {}
    for idx, item in enumerate(notes_raw):
        blob = json.dumps(item, ensure_ascii=False)
        if SECRET_VALUE_RE.search(blob) or _PRIVATE_KEY_RE.search(blob):
            raise ValueError(f"note looks like it contains a real secret: {path.name}#{idx}")
        try:
            note = CapabilityNote.model_validate(item)
        except ValidationError as exc:
            raise ValueError(f"invalid note in {path.name}#{idx}: {exc}") from exc
        if note.scope == "platform":
            platform_notes.append(note)
        else:
            endpoint_notes.setdefault(note.target, []).append(note)

    return PlatformNotes(
        platform_id=platform_id,
        platform_notes=tuple(platform_notes),
        endpoint_notes={k: tuple(v) for k, v in endpoint_notes.items()},
    )


def load_platform_notes() -> dict[str, PlatformNotes]:
    """读取全部策展坑点，按 platform_id 索引；带 mtime 缓存。"""
    files = _iter_note_files()
    sig = _signature(files)
    if _cache["signature"] == sig and _cache["value"] is not None:
        return _cache["value"]

    result: dict[str, PlatformNotes] = {}
    for path in files:
        loaded = _load_file(path)
        result[loaded.platform_id] = loaded

    _cache["signature"] = sig
    _cache["value"] = result
    return result


def notes_version() -> str:
    """用于 service 缓存键：note 文件变化即改版本。"""
    files = _iter_note_files()
    return "|".join(f"{p.name}:{int(p.stat().st_mtime)}" for p in files)

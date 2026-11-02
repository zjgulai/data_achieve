#!/usr/bin/env python3
"""Extract per-session user turns from Claude Code transcripts for a retro.

Why this exists: a weekly retro starts from what the user actually asked and
corrected. Those turns are buried in JSONL transcripts that can reach tens of
megabytes. Reading them by hand is slow and easy to get wrong (for example by
matching an 8-character session prefix against a full session id).

What it does:
  1. Finds transcript files whose mtime is inside the window.
  2. Keeps only real user text turns: drops tool results, system reminders,
     skill boilerplate, and empty turns.
  3. Redacts secrets and personal identifiers before writing anything.
  4. Writes one markdown file per session plus an index.

Exit codes: 0 success (even with zero sessions), 2 usage error.

Usage:
  python3 scripts/extract_retro_sessions.py --since 2026-10-26 \
      --transcripts ~/.claude/projects/-Users-lute-Project-data-scrapy

  # Auto-detect the transcript directory from the repository name:
  python3 scripts/extract_retro_sessions.py --since 2026-10-26
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

SKIP_PREFIXES = (
    "<",
    "# Workflow authoring reference",
    "Base directory for this skill",
    "This session is being continued from a previous conversation",
)

# Do not write secrets or personal identifiers into retro artifacts.
REDACTIONS = (
    (re.compile(r"apify_api_[A-Za-z0-9]{20,}"), "apify_api_<redacted>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-<redacted>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA<redacted>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "gh<redacted>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"), "Bearer <redacted>"),
    (re.compile(r"postgresql(?:\+asyncpg)?://[^\s\"']+"), "postgresql://<redacted>"),
    (re.compile(r"ou_[a-f0-9]{16,}"), "ou_<redacted>"),
    (re.compile(r"(?i)(password|passwd|secret|token)\s*[:=]\s*[^\s,;\"']+"), r"\1=<redacted>"),
)


def redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def slug_for(path: Path) -> str:
    resolved = str(path.resolve())
    return resolved.replace(os.sep, "-")


def find_transcripts(project_dir: Path, explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_dir():
            raise SystemExit(f"transcript directory not found: {candidate}")
        return candidate

    root = Path.home() / ".claude" / "projects"
    expected = slug_for(project_dir)
    direct = root / expected
    if direct.is_dir():
        return direct

    # Fallback: match by repository directory name, e.g. "-data-scrapy".
    # The transcript directory may encode a different home path than the current
    # one, so compare only the trailing repository segment.
    repo_name = project_dir.name.replace("_", "-").lower()
    matches = [
        p
        for p in root.iterdir()
        if p.is_dir() and p.name.lower().replace("_", "-").endswith(repo_name)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(
            "cannot auto-detect transcript directory. "
            "Pass --transcripts ~/.claude/projects/<dir> explicitly."
        )
    raise SystemExit(f"multiple transcript directories match: {[str(m) for m in matches]}")


def parse_since(value: str) -> dt.datetime:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(f"--since must be YYYY-MM-DD, got {value!r}") from exc


def user_texts(path: Path) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "user":
                continue
            message = record.get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            else:
                continue
            text = text.strip()
            if not text or "tool_result" in text[:80]:
                continue
            if any(text.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue
            stamp = (record.get("timestamp") or "")[:19]
            turns.append((stamp, redact(text)))
    return turns


def write_verified(path: Path, text: str) -> None:
    data = text.encode("utf-8")
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    actual = path.stat().st_size
    if actual != len(data):
        # The editor layer can transiently report a padded size. Rewrite once.
        with path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        actual = path.stat().st_size
    if actual != len(data):
        raise SystemExit(f"write verification failed for {path}: stat={actual} read={len(data)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, help="window start, YYYY-MM-DD")
    parser.add_argument("--transcripts", help="Claude transcript directory")
    parser.add_argument("--project-dir", default=".", help="repository root")
    parser.add_argument("--out", help="output directory (default: tmp/retro-<today>)")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    since = parse_since(args.since)
    transcript_dir = find_transcripts(project_dir, args.transcripts)

    today = dt.date.today().strftime("%Y%m%d")
    out_dir = Path(args.out) if args.out else project_dir / "tmp" / f"retro-{today}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions = []
    for path in sorted(transcript_dir.glob("*.jsonl")):
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
        if mtime < since:
            continue
        turns = user_texts(path)
        if not turns:
            continue
        sessions.append((path, mtime, turns))

    sessions.sort(key=lambda item: item[1])
    index_lines = [
        f"# Retro session index ({since.date()} to {dt.date.today()})",
        "",
        f"Transcript directory: `{transcript_dir}`",
        f"Sessions: {len(sessions)}",
        "",
        "| session | first turn | mtime | user turns | file |",
        "|---|---|---|---|---|",
    ]

    for path, mtime, turns in sessions:
        short = path.stem.split("-")[0]
        name = f"session-{short}.md"
        body = [f"# session {path.stem}", ""]
        for stamp, text in turns:
            body.extend([f"--- [{stamp}] ---", text, ""])
        write_verified(out_dir / name, "\n".join(body))
        first = turns[0][1].replace("\n", " ")[:80]
        index_lines.append(
            f"| `{short}` | {first} | {mtime:%Y-%m-%d %H:%M} | {len(turns)} | `{name}` |"
        )

    write_verified(out_dir / "INDEX.md", "\n".join(index_lines) + "\n")
    print(f"transcripts: {transcript_dir}")
    print(f"sessions: {len(sessions)}")
    print(f"output: {out_dir}")
    for path, _, turns in sessions:
        print(f"  {path.stem[:8]}  {len(turns):>3} user turns")
    return 0


if __name__ == "__main__":
    sys.exit(main())

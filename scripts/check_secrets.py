#!/usr/bin/env python3
"""Fail-closed secret scanner for tracked files.

Scans tracked files (default) or explicit paths for common credential shapes.
Output is redacted: the scanner never prints a full match.

Usage:
    python3 scripts/check_secrets.py --tracked
    python3 scripts/check_secrets.py --path path/to/file ...

Exit codes: 0 clean, 1 findings, 2 invalid input.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("apify_token", re.compile(r"apify_api_[A-Za-z0-9]{20,}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
]

ALLOW_MARKERS = (
    "example",
    "placeholder",
    "redacted",
    "dummy",
    "not-a-real",
    "xxxx",
    "<token>",
    "{{",
    "}}",
    "secret-scan: allow",
)

SKIP_NAMES = {
    "uv.lock",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
}


def _invalid(message: str) -> NoReturn:
    print(f"INVALID: {message}", file=sys.stderr)
    raise SystemExit(2)


def _tracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        _invalid("git ls-files failed; run from the repository")
    names = [item for item in completed.stdout.decode("utf-8").split("\0") if item]
    return [ROOT / name for name in names]


def _walk(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*") if item.is_file())
    _invalid(f"path not found: {path}")


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:1024]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}…{value[-2:]} (len={len(value)})"


def scan(paths: list[Path]) -> list[tuple[Path, int, str, str]]:
    findings: list[tuple[Path, int, str, str]] = []
    for path in paths:
        if path.name in SKIP_NAMES or any(part == ".git" for part in path.parts):
            continue
        text = _read_text(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if any(marker in line.lower() for marker in ALLOW_MARKERS):
                continue
            for name, pattern in PATTERNS:
                match = pattern.search(line)
                if match is not None:
                    findings.append((path, number, name, _redact(match.group(0))))
                    break
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed secret scanner")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tracked", action="store_true", help="scan git tracked files")
    source.add_argument("--path", action="append", type=Path, help="scan a file or directory")
    args = parser.parse_args(argv)

    if args.tracked:
        paths = _tracked_files()
    else:
        paths = [item for path in args.path or [] for item in _walk(path.resolve())]

    findings = scan(paths)
    if not findings:
        print(f"OK: no secrets in {len(paths)} file(s)")
        return 0
    print(f"FAIL: {len(findings)} secret finding(s)")
    for path, line, name, redacted in findings:
        try:
            display = path.relative_to(ROOT)
        except ValueError:
            display = path
        print(f"  {display}:{line}: {name} {redacted}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
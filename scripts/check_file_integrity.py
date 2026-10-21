#!/usr/bin/env python3
"""Detect truncated, sparse, or NUL-corrupted text files.

The editor used in this project has twice produced files whose ``st_size`` is
larger than the bytes Python can read, or which contain embedded NUL bytes.
Both make ruff, iconv, and git behave inconsistently. This check is cheap and
runs before every commit and in CI.

Exit codes: 0 clean, 1 corruption found, 2 usage error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".woff", ".woff2",
    ".ttf", ".otf", ".mp3", ".mp4", ".mov", ".avi", ".sqlite", ".db",
    ".heic", ".bin", ".so", ".dylib", ".dll", ".exe",
}


def _git_files(staged: bool) -> list[Path]:
    if staged:
        cmd = ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"]
    else:
        cmd = ["git", "ls-files", "-z"]
    raw = subprocess.check_output(cmd)
    return [Path(item) for item in raw.decode("utf-8").split("\0") if item]


def _is_binary(path: Path) -> bool:
    return path.suffix.lower() in BINARY_SUFFIXES


def check(path: Path) -> tuple[str, str] | None:
    try:
        stat_size = path.stat().st_size
        data = path.read_bytes()
    except OSError as exc:
        return ("unreadable", str(exc))
    if stat_size != len(data):
        return (
            "size_mismatch",
            f"st_size={stat_size} read={len(data)} delta={stat_size - len(data)}",
        )
    nul_count = data.count(b"\x00")
    if nul_count and not _is_binary(path):
        return ("nul_bytes", f"count={nul_count}")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="check staged files instead of every tracked file",
    )
    args = parser.parse_args()
    failures: list[tuple[str, str, str]] = []
    files = _git_files(args.staged)
    for path in files:
        if not path.exists() or _is_binary(path):
            continue
        result = check(path)
        if result is not None:
            kind, detail = result
            failures.append((str(path), kind, detail))
    if not failures:
        print(f"file integrity OK ({len(files)} files)")
        return 0
    print("file integrity FAILED", file=sys.stderr)
    for path, kind, detail in failures:
        print(f"  {path}: {kind} ({detail})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

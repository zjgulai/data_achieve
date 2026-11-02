#!/usr/bin/env python3
"""Claim and audit write scopes for concurrent workflows.

Usage:
    python3 scripts/workflow_scope_guard.py claim --id wf-a \
      --write staging/a --read docs/
    python3 scripts/workflow_scope_guard.py audit --claim wf-a

Claims live in ``tmp/workflow-claims/<id>.json`` and expire after four hours.
``audit`` fails when the working tree has changes outside the write set, when
the read set includes a secret file, or when paid calls lack approval.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLAIMS_DIR = ROOT / "tmp" / "workflow-claims"
STALE_AFTER = timedelta(hours=4)
SECRET_SUFFIXES = (".env", ".pem", ".key")
SECRET_NAMES = {".env"}


@dataclass(frozen=True)
class Claim:
    claim_id: str
    created_at: datetime
    write: tuple[Path, ...]
    read: tuple[Path, ...]
    paid_calls: bool

    @property
    def stale(self) -> bool:
        return datetime.now(UTC) - self.created_at > STALE_AFTER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.claim_id,
            "created_at": self.created_at.isoformat(),
            "write": [str(path) for path in self.write],
            "read": [str(path) for path in self.read],
            "paid_calls": self.paid_calls,
        }


def _root(value: Path | None) -> Path:
    return (value or ROOT).resolve()


def _normalize(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _overlaps(left: Path, right: Path) -> bool:
    if left == right:
        return True
    return left.is_relative_to(right) or right.is_relative_to(left)


def _claim_path(claims_dir: Path, claim_id: str) -> Path:
    return claims_dir / f"{claim_id}.json"


def _load_claims(claims_dir: Path) -> list[Claim]:
    claims: list[Claim] = []
    if not claims_dir.is_dir():
        return claims
    for path in sorted(claims_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            claims.append(
                Claim(
                    claim_id=str(payload["id"]),
                    created_at=datetime.fromisoformat(str(payload["created_at"])),
                    write=tuple(Path(item) for item in payload.get("write", [])),
                    read=tuple(Path(item) for item in payload.get("read", [])),
                    paid_calls=bool(payload.get("paid_calls", False)),
                )
            )
        except (OSError, KeyError, ValueError, TypeError):
            continue
    return claims


def claim(args: argparse.Namespace) -> int:
    root = _root(args.root)
    claims_dir = root / "tmp" / "workflow-claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    claim_id = args.id.strip()
    if not claim_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in claim_id):
        print("INVALID: claim id may contain only letters, digits, dot, underscore, dash", file=sys.stderr)
        return 2
    if not args.write:
        print("INVALID: --write is required", file=sys.stderr)
        return 2

    write = tuple(_normalize(root, item) for item in args.write)
    read = tuple(_normalize(root, item) for item in args.read)
    path = _claim_path(claims_dir, claim_id)
    existing = _load_claims(claims_dir)
    for other in existing:
        if other.claim_id == claim_id:
            if other.stale or args.force:
                continue
            print(f"FAIL: claim {claim_id} already exists and is not stale", file=sys.stderr)
            return 1
        if other.stale:
            continue
        for mine in write:
            for theirs in other.write:
                if _overlaps(mine, theirs):
                    print(
                        f"FAIL: write scope overlaps claim {other.claim_id}: "
                        f"{_relative(root, mine)} vs {_relative(root, theirs)}",
                        file=sys.stderr,
                    )
                    return 1

    record = Claim(
        claim_id=claim_id,
        created_at=datetime.now(UTC),
        write=write,
        read=read,
        paid_calls=args.paid_calls,
    )
    path.write_text(
        json.dumps(
            {
                "id": record.claim_id,
                "created_at": record.created_at.isoformat(),
                "write": [str(item) for item in write],
                "read": [str(item) for item in read],
                "paid_calls": record.paid_calls,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"OK: claimed {claim_id} write={len(write)} read={len(read)}")
    return 0


def _changed_paths(root: Path) -> list[Path]:
    claims_dir = (root / "tmp" / "workflow-claims").resolve()
    commands = [
        ["git", "diff", "--name-only", "-z"],
        ["git", "diff", "--cached", "--name-only", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ]
    paths: set[Path] = set()
    for command in commands:
        completed = subprocess.run(
            command, cwd=root, capture_output=True, check=False
        )
        if completed.returncode != 0:
            raise SystemExit(f"INVALID: {' '.join(command)} failed")
        for name in completed.stdout.decode("utf-8").split("\0"):
            if name:
                path = (root / name).resolve()
                if path.is_relative_to(claims_dir):
                    continue
                paths.add(path)
    return sorted(paths)


def _is_secret(path: Path) -> bool:
    name = path.name
    return name in SECRET_NAMES or name.startswith(".env") or name.endswith(SECRET_SUFFIXES)


def audit(args: argparse.Namespace) -> int:
    root = _root(args.root)
    claims_dir = root / "tmp" / "workflow-claims"
    matches = [item for item in _load_claims(claims_dir) if item.claim_id == args.claim]
    if not matches:
        print(f"FAIL: claim not found: {args.claim}", file=sys.stderr)
        return 1
    record = matches[0]
    failures: list[str] = []

    if record.stale:
        failures.append("claim is older than 4 hours; refresh it")
    for path in record.read:
        if _is_secret(path) and not args.allow_secret_read:
            failures.append(f"read set includes secret file: {_relative(root, path)}")
    if record.paid_calls and os.environ.get("ALLOW_PAID_API") != "1":
        failures.append("claim declares paid calls but ALLOW_PAID_API is not 1")

    changed = _changed_paths(root)
    outside = [
        path
        for path in changed
        if not any(path.is_relative_to(write) or path == write for write in record.write)
    ]
    for path in outside:
        failures.append(f"changed outside write scope: {_relative(root, path)}")

    payload = {
        "claim": record.claim_id,
        "changed": len(changed),
        "outside": [_relative(root, path) for path in outside],
        "failures": failures,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif failures:
        print(f"FAIL: {len(failures)} issue(s) for claim {record.claim_id}")
        for failure in failures:
            print(f"  {failure}")
    else:
        print(f"OK: claim {record.claim_id} covers {len(changed)} changed path(s)")
    return 1 if failures else 0


def clean(args: argparse.Namespace) -> int:
    root = _root(args.root)
    claims_dir = root / "tmp" / "workflow-claims"
    removed = 0
    for claim in _load_claims(claims_dir):
        if claim.stale:
            _claim_path(claims_dir, claim.claim_id).unlink(missing_ok=True)
            removed += 1
    print(f"OK: removed {removed} stale claim(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow write-scope claim and audit")
    parser.add_argument("--root", type=Path, help="repository root (tests)")
    sub = parser.add_subparsers(dest="command", required=True)

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--id", required=True)
    claim_parser.add_argument("--write", action="append", default=[])
    claim_parser.add_argument("--read", action="append", default=[])
    claim_parser.add_argument("--paid-calls", action="store_true")
    claim_parser.add_argument("--force", action="store_true")
    claim_parser.set_defaults(func=claim)

    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--claim", required=True)
    audit_parser.add_argument("--allow-secret-read", action="store_true")
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.set_defaults(func=audit)

    clean_parser = sub.add_parser("clean")
    clean_parser.set_defaults(func=clean)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
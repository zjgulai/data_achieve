#!/usr/bin/env python3
"""Check Alembic migration numbers against the chain and against plans.

Why this exists: on 2026-10-31 the contract plan for C2 still asserted
``down_revision = "202610220059"``, but ABI and insight migrations had already
extended the chain to ``202610310068``. The plan could not start, and nothing
in CI noticed. Sequence numbers 060-068 were also reused across dates, which
makes a human read the filenames as one chain when they are not.

What it checks:
  1. Every migration file parses and has a revision.
  2. There is exactly one head, unless --allow-multiple-heads is given.
  3. No two migrations share the same sequence suffix (last four digits).
  4. Optional: the current head equals --expect-head.
  5. Every ``down_revision = "X"`` found in the scanned docs points at a
     revision that exists in the chain.

Exit codes: 0 clean, 1 failed check, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REVISION_RE = re.compile(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
DOWN_REVISION_RE = re.compile(
    r'^down_revision(?::\s*[^=]+)?\s*=\s*(?:["\']([^"\']+)["\']|None)', re.MULTILINE
)
DOC_DOWN_REVISION_RE = re.compile(r'down_revision\s*=\s*["\']([0-9]{12})["\']')
DOC_REVISION_RE = re.compile(r"\b(2026[0-9]{8})\b")


def parse_versions(versions_dir: Path) -> tuple[dict[str, Path], dict[str, str | None], list[str]]:
    revisions: dict[str, Path] = {}
    parents: dict[str, str | None] = {}
    problems: list[str] = []

    for path in sorted(versions_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        revision_match = REVISION_RE.search(text)
        if not revision_match:
            problems.append(f"{path.name}: no revision assignment")
            continue
        revision = revision_match.group(1)
        if revision in revisions:
            problems.append(
                f"duplicate revision {revision}: {revisions[revision].name} and {path.name}"
            )
            continue
        revisions[revision] = path
        down_match = DOWN_REVISION_RE.search(text)
        parents[revision] = down_match.group(1) if down_match and down_match.group(1) else None

    return revisions, parents, problems


def find_heads(revisions: dict[str, Path], parents: dict[str, str | None]) -> list[str]:
    referenced = {parent for parent in parents.values() if parent}
    return sorted(revision for revision in revisions if revision not in referenced)


def duplicate_sequences(revisions: dict[str, Path]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for revision in revisions:
        groups.setdefault(revision[-4:], []).append(revision)
    return {suffix: values for suffix, values in groups.items() if len(values) > 1}


def scan_docs(docs: list[Path]) -> list[tuple[str, int, str]]:
    references: list[tuple[str, int, str]] = []
    for doc in docs:
        paths = [doc] if doc.is_file() else sorted(doc.rglob("*.md"))
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                references.append((str(path), 0, "not-valid-utf8"))
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                for revision in DOC_DOWN_REVISION_RE.findall(line):
                    references.append((str(path), line_number, revision))
    return references


def load_allowlist(path: Path | None) -> set[tuple[str, str]]:
    """Historical plan references that are deliberately grandfathered.

    The file is a list of ``{"path", "revision", "owner", "reason", "expires"}``
    entries. A new doc reference that is not listed still fails.
    """
    if path is None or not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        (Path(item["path"]).as_posix(), str(item["revision"]))
        for item in data.get("entries", [])
        if item.get("path") and item.get("revision")
    }


def check_doc_references(
    references: list[tuple[str, int, str]],
    revisions: dict[str, Path],
    allowlist: set[tuple[str, str]] | None = None,
) -> list[str]:
    problems: list[str] = []
    allowlist = allowlist or set()
    by_suffix = {revision[-4:]: revision for revision in revisions}
    for path, line_number, revision in references:
        if revision == "not-valid-utf8":
            problems.append(f"{path}: not valid UTF-8")
            continue
        if revision in revisions:
            continue
        if (Path(path).as_posix(), revision) in allowlist:
            continue
        collision = by_suffix.get(revision[-4:])
        if collision:
            problems.append(
                f"{path}:{line_number}: down_revision {revision} is not in the chain; "
                f"sequence {revision[-4:]} is used by {collision}"
            )
        else:
            problems.append(f"{path}:{line_number}: down_revision {revision} is not in the chain")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--versions",
        default="apps/api/alembic/versions",
        help="Alembic versions directory",
    )
    parser.add_argument(
        "--docs",
        nargs="*",
        default=["docs/superpowers/plans", "docs/design"],
        help="docs or directories to scan for down_revision references",
    )
    parser.add_argument("--expect-head", help="fail unless this is the only head")
    parser.add_argument(
        "--allowlist",
        default="configs/contracts/migration-allowlist.json",
        help="JSON file with grandfathered historical plan references",
    )
    parser.add_argument(
        "--no-allowlist",
        action="store_true",
        help="ignore the allowlist and report every doc reference",
    )
    parser.add_argument(
        "--allow-multiple-heads",
        action="store_true",
        help="do not fail when the chain has more than one head",
    )
    args = parser.parse_args()

    versions_dir = Path(args.versions)
    if not versions_dir.is_dir():
        print(f"versions directory not found: {versions_dir}", file=sys.stderr)
        return 2

    revisions, parents, problems = parse_versions(versions_dir)
    heads = find_heads(revisions, parents)

    print(f"migrations: {len(revisions)}")
    print(f"heads: {', '.join(heads) if heads else 'none'}")

    duplicates = duplicate_sequences(revisions)
    for suffix, values in sorted(duplicates.items()):
        print(f"WARN  sequence {suffix} is shared by: {', '.join(values)}")

    references = scan_docs([Path(item) for item in args.docs])
    allowlist = set() if args.no_allowlist else load_allowlist(Path(args.allowlist))
    problems.extend(check_doc_references(references, revisions, allowlist))

    if len(heads) > 1 and not args.allow_multiple_heads:
        problems.append(f"multiple heads: {', '.join(heads)}")
    if args.expect_head and heads != [args.expect_head]:
        problems.append(f"expected head {args.expect_head}, got {', '.join(heads) or 'none'}")

    if problems:
        print("migration number check FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print("migration number check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

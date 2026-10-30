#!/usr/bin/env python3
"""Apply a taxonomy code migration to a frozen coded JSONL artifact.

Decision B keeps every SUP code, so ``taxonomy-migration.json`` contains an
identity ``code_map``.  This tool still exists so the mapping is executable:
it fails on an unknown code, reports how many annotations would change, and
only rewrites the file when at least one code actually changes.

    python3 tools/apply_taxonomy_migration.py --check
    python3 tools/apply_taxonomy_migration.py --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

VOC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATION = (
    VOC_ROOT / "artifacts" / "run-20261029" / "llm-coding" / "taxonomy-migration.json"
)
DEFAULT_CODED = (
    VOC_ROOT / "artifacts" / "run-20261029" / "llm-coding" / "coded" / "ALL.jsonl"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migration", type=Path, default=DEFAULT_MIGRATION)
    parser.add_argument("--coded", type=Path, default=DEFAULT_CODED)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report without writing (default)")
    mode.add_argument("--write", action="store_true", help="rewrite only if a code changes")
    args = parser.parse_args()

    migration = json.loads(args.migration.read_text(encoding="utf-8"))
    code_map = migration["code_map"]
    rows = [json.loads(line) for line in args.coded.open(encoding="utf-8") if line.strip()]

    unknown: list[str] = []
    changes = 0
    annotations = 0
    for row in rows:
        for aspect in row.get("aspects") or []:
            annotations += 1
            code = aspect.get("code")
            if code not in code_map:
                unknown.append(f"{row.get('canonical_id')}:{code}")
                continue
            if code_map[code] != code:
                changes += 1
                aspect["code"] = code_map[code]

    before = hashlib.sha256(args.coded.read_bytes()).hexdigest()
    print(f"migration: {migration['from_taxonomy']} -> {migration['to_taxonomy']}")
    print(f"records: {len(rows)}  aspect annotations: {annotations}")
    print(f"code map: {len(code_map)} entries  unknown codes: {len(unknown)}")
    print(f"annotations changed by map: {changes}")
    print(f"sha256 before: {before}")

    if unknown:
        for item in unknown[:20]:
            print(f"  UNKNOWN {item}", file=sys.stderr)
        return 2
    if changes == 0:
        print("result: identity migration; coded artifact left untouched")
        return 0
    if not args.write:
        print("result: changes pending; re-run with --write to rewrite")
        return 0

    tmp = args.coded.with_suffix(args.coded.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(args.coded)
    after = hashlib.sha256(args.coded.read_bytes()).hexdigest()
    print(f"sha256 after:  {after}")
    print("result: coded artifact rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())

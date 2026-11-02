"""CLI for the shared report language gate.

Usage:
    python -m data_intelligence_hub.report_quality.cli \\
      --html report.html --manifest manifest.json --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_intelligence_hub.report_quality import check_html_report, check_text_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Business report language and number gate")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--html", type=Path)
    source.add_argument("--text", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        source_text = (args.html or args.text).read_text(encoding="utf-8")
        manifest = None
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2

    if args.html:
        result = check_html_report(source_text, manifest=manifest, strict=args.strict)
    else:
        result = check_text_report(source_text, manifest=manifest, strict=args.strict)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    elif result.ok:
        print(
            f"OK: percentages={result.checked_percentages} "
            f"figures={result.checked_figures} evidence={result.evidence}"
        )
    else:
        print(f"FAIL: {len(result.hits)} violation(s)")
        for hit in result.hits:
            location = f"{args.html or args.text}:{hit.line}"
            print(f"  {location}: [{hit.kind}] {hit.message}")
            if hit.snippet:
                print(f"    {hit.snippet}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
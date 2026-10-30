#!/usr/bin/env python3
"""render.py — report-data.json to a single self-contained HTML file.

Fail-closed:
  1. validate the data (schema + semantic + anti-patterns)
  2. render the shell, sections, exhibits, claims, omissions, prohibited list
  3. validate the rendered HTML
  4. write report.html only when both validations pass

Usage:
  python3 render.py --data out/report-data.json --out out/report.html
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import validate as V
from templates.sections import SECTION_MODULES
from templates.hero import render_hero
from templates.omissions import render_omissions
from templates.prohibited import render_prohibited
from templates.shell import render_shell


def render(data: dict, validate_output: bool = True) -> tuple[str, V.Suite, list[dict]]:
    data_suite = V.validate_data(data)
    if not data_suite.passed:
        return "", data_suite, []

    hero_html = render_hero(data.get("report", {}))
    sections_html = []
    omissions = []
    for spec, module in SECTION_MODULES:
        result = module.render(data)
        if result.html is None:
            omissions.append({
                "index": spec["index"],
                "id": spec["id"],
                "kicker": spec["kicker"],
                "zh": spec["zh"],
                "reason": result.reason or "required 数据缺失。",
            })
        else:
            sections_html.append(result.html)

    omissions_html = render_omissions(omissions, len(SECTION_MODULES))
    prohibited_html = render_prohibited(data.get("report", {}))
    html = render_shell(data, hero_html, "".join(sections_html), omissions_html, prohibited_html)

    if not validate_output:
        return html, V.Suite(), omissions
    html_suite = V.validate_html(html, data)
    return html, html_suite, omissions


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False, suffix=".tmp")
    try:
        tmp.write(content)
        tmp.flush()
        tmp.close()
        Path(tmp.name).replace(path)
    finally:
        if Path(tmp.name).exists():
            Path(tmp.name).unlink()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render report-data.json to report.html")
    ap.add_argument("--data", required=True, help="path to report-data.json")
    ap.add_argument("--out", required=True, help="path to report.html")
    ap.add_argument("--json", action="store_true", help="print machine-readable summary")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    html, suite, omissions = render(data)
    if not html:
        if args.json:
            print(json.dumps({"status": "FAIL", "stage": "data", "validation": suite.as_dict()}, ensure_ascii=False, indent=2))
        else:
            suite.print_human(f"DATA {args.data}")
            print("BUILD FAILED: report.html was not written.")
        return 1
    if not suite.passed:
        if args.json:
            print(json.dumps({"status": "FAIL", "stage": "html", "validation": suite.as_dict()}, ensure_ascii=False, indent=2))
        else:
            suite.print_human("RENDERED HTML")
            print("BUILD FAILED: report.html was not written.")
        return 1

    out = Path(args.out)
    write_atomic(out, html)
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    summary = {
        "status": "PASS",
        "path": str(out),
        "bytes": len(html.encode("utf-8")),
        "sha256": digest,
        "sections": len([s for s in data.get("report", {}).get("sections", [])]),
        "omissions": omissions,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"PASS  wrote {out}")
        print(f"      {summary['bytes']} bytes · sha256 {digest}")
        for o in omissions:
            print(f"      omitted {o['index']} {o['kicker']}: {o['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""build.py — one command: run artifacts → report-data.json → report.html.

    python3 build.py --run /path/to/artifacts/run-20261029 --out out/run-20261029

Steps (fail-closed):
  1. assemble report-data.json from the run directory
  2. validate the data contract
  3. render the single-file HTML
  4. validate the rendered HTML
  5. write report-data.json, report.html, validation-result.json,
     delivery-manifest.json

If any step fails, report.html is not written and the exit code is non-zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import assemble as A
import render as R
import validate as V


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, obj) -> bytes:
    raw = json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")
    path.write_bytes(raw)
    return raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the VOC insight report from one run directory")
    ap.add_argument("--run", default=A.DEFAULT_RUN, help="run artifact directory")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--json", action="store_true", help="print machine-readable summary")
    args = ap.parse_args(argv)

    run = Path(args.run)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data_path = out / "report-data.json"
    html_path = out / "report.html"
    validation_path = out / "validation-result.json"
    manifest_path = out / "delivery-manifest.json"

    # 1. assemble ----------------------------------------------------------
    if not run.is_dir():
        print(f"FAIL: run directory not found: {run}", file=sys.stderr)
        return 1
    data = A.assemble(run)

    # 2. validate data -----------------------------------------------------
    data_suite = V.validate_data(data)
    if not data_suite.passed:
        write_json(validation_path, {"status": "FAIL", "stage": "data", "report": data_suite.as_dict()})
        if args.json:
            print(json.dumps({"status": "FAIL", "stage": "data", "validation": data_suite.as_dict()},
                             ensure_ascii=False, indent=2))
        else:
            data_suite.print_human("DATA CONTRACT")
            print("BUILD FAILED: report.html was not written.")
        return 1

    # 3. render ------------------------------------------------------------
    html, _, omissions = R.render(data, validate_output=False)

    # 4. validate HTML -----------------------------------------------------
    html_suite = V.validate_html(html, data)
    if not html_suite.passed:
        write_json(validation_path, {"status": "FAIL", "stage": "html", "report": data_suite.as_dict(),
                                     "spec": html_suite.as_dict()})
        if args.json:
            print(json.dumps({"status": "FAIL", "stage": "html", "validation": html_suite.as_dict()},
                             ensure_ascii=False, indent=2))
        else:
            html_suite.print_human("RENDERED HTML")
            print("BUILD FAILED: report.html was not written.")
        return 1

    # 5. write -------------------------------------------------------------
    data_raw = write_json(data_path, data)
    html_raw = html.encode("utf-8")
    tmp_html = html_path.with_suffix(".html.tmp")
    tmp_html.write_bytes(html_raw)
    tmp_html.replace(html_path)

    data_sha = sha256_bytes(data_raw)
    html_sha = sha256_bytes(html_raw)
    validation = {
        "status": "PASS",
        "report": data_suite.as_dict(),
        "spec": html_suite.as_dict(),
        "report_data_sha256": data_sha,
        "report_html_sha256": html_sha,
        "report_html_bytes": len(html_raw),
        "validator_version": V.C.VALIDATOR_VERSION,
        "omissions": omissions,
    }
    write_json(validation_path, validation)
    manifest = {
        "schema_version": "insight_report_delivery_manifest_v1",
        "run_id": data["report_id"],
        "generated_at": data["generated_at"],
        "artifacts": [
            {"path": "report-data.json", "bytes": len(data_raw), "sha256": data_sha},
            {"path": "report.html", "bytes": len(html_raw), "sha256": html_sha},
            {"path": "validation-result.json", "bytes": validation_path.stat().st_size,
             "sha256": sha256_bytes(validation_path.read_bytes())},
        ],
    }
    write_json(manifest_path, manifest)

    summary = {
        "status": "PASS",
        "run": str(run),
        "out": str(out),
        "report_data": str(data_path),
        "report_html": str(html_path),
        "bytes": len(html_raw),
        "sha256": html_sha,
        "sections": len(data["report"]["sections"]),
        "exhibits": sum(1 for s in data["report"]["sections"] for b in s["blocks"] if b["type"] == "exhibit"),
        "claims": len(data["report"]["claims"]),
        "omissions": omissions,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"PASS  {html_path}")
        print(f"      {len(html_raw)} bytes · sha256 {html_sha}")
        print(f"      {summary['sections']} sections · {summary['exhibits']} exhibits · {summary['claims']} claims")
        for o in omissions:
            print(f"      omitted {o['index']} {o['kicker']}: {o['reason']}")
        print(f"      validation: {validation_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

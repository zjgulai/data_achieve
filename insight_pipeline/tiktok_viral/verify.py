#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only checks for the archived TikTok viral pipeline.

Exit 0 only when the inputs, generated artifacts and report bundle agree.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = (ROOT.parent.parent / "tools" / "insight-reports" /
          "tiktok-viral-topic" / "2026-10-31")

failures = []
TMP_PREFIX = "/" + "tmp/"


def check(condition, message):
    if not condition:
        failures.append(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# Input TSV: 288 rows, 9 columns.
tsv_lines = [line for line in (ROOT / "deepread288.tsv").read_text(
    encoding="utf-8").splitlines() if line.strip()]
check(len(tsv_lines) == 288, f"deepread288.tsv rows = {len(tsv_lines)}, expected 288")
check(all(len(line.split("\t")) == 9 for line in tsv_lines),
      "deepread288.tsv has a row without 9 columns")

# Curated theme mapping.
theme = json.loads((ROOT / "theme-clusters.json").read_text(encoding="utf-8"))
check(len(theme.get("motifs", [])) == 13, "theme-clusters.json motifs != 13")
check(len(theme.get("mapping", {})) == 993, "theme-clusters.json mapping != 993")

# Mechanism clusters.
mech = json.loads((ROOT / "mech-clusters.json").read_text(encoding="utf-8"))
check(mech["meta"]["source"] == "deepread288.tsv", "mech-clusters source label")
check(len(mech.get("families", [])) == 10, "mech-clusters families != 10")
check(len(mech.get("mapping", {})) == 806, "mech-clusters mapping != 806")

# Replicability.
repl = json.loads((ROOT / "replicability.json").read_text(encoding="utf-8"))
check(len(repl.get("videos", [])) == 288, "replicability videos != 288")
check(sum(x["n"] for x in repl["stats"]["tiers"].values()) == 288,
      "replicability tier counts do not sum to 288")

# Saturation.
sat = json.loads((ROOT / "saturation.json").read_text(encoding="utf-8"))
check(sat["meta"]["sources"]["corpus"].startswith("deepread288.tsv"),
      "saturation corpus label")
check(bool(sat.get("key_findings")), "saturation key_findings is empty")

# Comments.
comments = json.loads((ROOT / "comments.json").read_text(encoding="utf-8"))
check(comments["meta"]["corpus"]["comments"] == 47073,
      "comments.json corpus.comments != 47073")

# Report bundle and manifest.
manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
source = (BUNDLE / "report.html").read_bytes()
content = source.decode("utf-8")
for rule in manifest["content"]["normalize"]:
    content = content.replace(rule["find"], rule["replace"])
content_bytes = content.encode("utf-8")
check(len(source) == manifest["content"]["source_bytes"],
      "report source_bytes mismatch")
check(sha256(source) == manifest["content"]["source_sha256"],
      "report source_sha256 mismatch")
check(len(content_bytes) == manifest["content"]["content_bytes"],
      "report content_bytes mismatch")
check(sha256(content_bytes) == manifest["content"]["content_sha256"],
      "report content_sha256 mismatch")
check(TMP_PREFIX not in content, "report content still contains /tmp/")
check(content.lstrip().startswith("<!DOCTYPE html>"), "report is not HTML")
check(len(re.findall(r"<svg\b", source.decode("utf-8"))) == 6,
      "report SVG count != 6")

allowed_scripts = {
    "d63f12e445a8317edc925644d31dca93c3f4107b06dc74d5fed67ce62281b56f",
    "43158db65a7984b9ac2044505ef49ae1565e1ffb13b0271acd987d093950b4c6",
}
scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",
                     source.decode("utf-8"), re.S | re.I)
check(len(scripts) == 2, f"report inline scripts = {len(scripts)}, expected 2")
for script in scripts:
    check(sha256(script.encode("utf-8")) in allowed_scripts,
          "report inline script hash not in whitelist")

# Generated text must not keep absolute /tmp paths.
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or "__pycache__" in path.parts:
        continue
    if path.suffix not in {".py", ".json", ".md"} or path.name in {"README.md", "verify.py"}:
        continue
    text = path.read_text(encoding="utf-8")
    check(TMP_PREFIX not in text, f"{path.relative_to(ROOT)} contains /tmp/")

if failures:
    print("FAIL")
    for failure in failures:
        print(f"- {failure}")
    sys.exit(1)

print("PASS: 288 input rows; 13 theme motifs; 10 mechanism families; "
      "288 replicability rows; 47,073 comments; report bundle hashes match.")

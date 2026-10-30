#!/usr/bin/env python3
"""selftest.py — no-dependency checks for the generator.

Run from this directory:

    python3 selftest.py

It assembles the real run in memory, validates it, renders the HTML in memory,
and then proves the fail-closed paths actually fail:

  * hero raw total is rejected
  * missing four-question column is rejected
  * cross-frame percentage is rejected
  * pie chart is rejected
  * metric rows > 0 with G7 BLOCKED is rejected
  * a chart with missing Basis/Unit/Limit/Status renders UNKNOWN

Exit code 0 only when every check passes.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import assemble as A
import charts
import render as R
import validate as V
from templates import components as c
from templates.hero import assert_hero_proofs


def check(name: str, fn) -> bool:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - selftest surfaces the failure
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
        return False
    print(f"PASS  {name}")
    return True


def expect_fail(suite: V.Suite, rule_prefix: str) -> None:
    assert not suite.passed, "validator unexpectedly passed"
    rules = [chk.rule for chk in suite.checks if not chk.passed]
    rules += [issue.rule for chk in suite.checks if not chk.passed for issue in chk.issues]
    assert any(r.startswith(rule_prefix) for r in rules), f"expected a {rule_prefix} failure, got {rules}"


def main() -> int:
    snapshot = Path(__file__).resolve().parent / "input" / "run-20261029"
    data = A.assemble(snapshot if snapshot.is_dir() else Path(A.DEFAULT_RUN))
    rendered = R.render(data, validate_output=False)[0]
    checks = []

    def data_passes():
        suite = V.validate_data(data)
        assert suite.passed, [c.rule for c in suite.checks if not c.passed]

    def html_passes():
        suite = V.validate_html(rendered, data)
        assert suite.passed, [c.rule for c in suite.checks if not c.passed]

    def section_count():
        n = len(re.findall(r'class="report-section"', rendered))
        assert n == 10, f"got {n} sections"

    def exhibit_count():
        n = len(re.findall(r'<figure[^>]*class="[^"]*\bexhibit\b', rendered))
        assert n == 9, f"got {n} exhibits"

    def chart_meta_count():
        n = len(re.findall(r'class="chart"', rendered))
        m = len(re.findall(r'class="chart-meta"', rendered))
        assert n == m and n >= 8, f"{m} metas for {n} charts"

    def no_external():
        bad = [p for p in ("http://", "https://", "<link", "<script src", "<img", "<svg",
                           "<canvas", "<iframe", "@import", "url(", "/Users/") if p in rendered]
        assert not bad, bad

    def hero_total():
        broken = copy.deepcopy(data)
        broken["report"]["hero"]["proofs"][0]["value"] = "18"
        expect_fail(V.validate_data(broken), "HERO")

    def missing_readout():
        broken = copy.deepcopy(data)
        broken["report"]["claims"][0].pop("observed", None)
        expect_fail(V.validate_data(broken), "CLM")

    def cross_frame():
        broken = copy.deepcopy(data)
        chart = broken["report"]["sections"][1]["blocks"][0]["chart"]
        chart["encoding"] = "share_with_denominator"
        chart["denominator"] = 27
        chart["frame_scope"] = ["natural", "diagnostic"]
        expect_fail(V.validate_data(broken), "AP")

    def pie():
        broken = copy.deepcopy(data)
        chart = broken["report"]["sections"][1]["blocks"][0]["chart"]
        chart["type"] = "pie"
        expect_fail(V.validate_data(broken), "SCHEMA")

    def metric_rows():
        broken = copy.deepcopy(data)
        broken["evidence"]["corpus"]["metric_rows"]["value"] = 5
        expect_fail(V.validate_data(broken), "GATE")

    def chart_unknown():
        out = charts.chart_nested_bar({
            "type": "nested_bar",
            "series": [{"group": "g", "n": 10, "with_friction": 2, "without_friction": 8}],
        })
        assert out.count("UNKNOWN") >= 4, out[:500]

    def readout_placeholder():
        out = c.readout({"observed": "只有观察值"}, "TEST")
        assert out.count('class="readout-item') == 4, out[:500]
        assert "EVIDENCE INCOMPLETE" in out, out[:800]

    def hero_assert():
        try:
            assert_hero_proofs([{"value": "18"}, {"value": "1 / 2"}, {"value": "0"}, {"value": "3 / 4"}])
        except AssertionError:
            return
        raise AssertionError("hero assert did not fire")

    for name, fn in [
        ("assembled data passes the data contract", data_passes),
        ("rendered HTML passes post-render checks", html_passes),
        ("report has 10 sections because social is omitted", section_count),
        ("report has 9 complete exhibits", exhibit_count),
        ("every chart has a four-row chart-meta", chart_meta_count),
        ("zero external resources", no_external),
        ("validator rejects a raw total in Hero", hero_total),
        ("validator rejects a missing four-question column", missing_readout),
        ("validator rejects a cross-frame percentage", cross_frame),
        ("validator rejects a pie chart", pie),
        ("validator rejects metric rows while G7 is blocked", metric_rows),
        ("missing chart meta renders UNKNOWN (not omitted)", chart_unknown),
        ("missing readout column renders EVIDENCE INCOMPLETE", readout_placeholder),
        ("hero renderer assert-fails on a raw total", hero_assert),
    ]:
        checks.append(check(name, fn))

    print(f"\nRESULT: {sum(checks)}/{len(checks)} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())

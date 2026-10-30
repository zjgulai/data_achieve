"""Smoke and contract tests for the insight-report pipeline (stdlib unittest)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_report  # noqa: E402
from insight_report import coding, contract, counting, evidence, metrics, validate  # noqa: E402

DEFAULT_RUN = ROOT.parent.parent / "voc_pipeline" / "artifacts" / "run-20261029"


class TestCodingRules(unittest.TestCase):
    def test_negation_flips_polarity(self) -> None:
        self.assertEqual(coding.polarity_of("it is not comfortable at all"), "negative")
        self.assertEqual(coding.polarity_of("the band doesn't slip"), "positive")

    def test_severity_marks_qualifiers_and_intensifiers(self) -> None:
        self.assertEqual(coding.severity_of("a bit uncomfortable", "negative"), "minor")
        self.assertEqual(coding.severity_of("severe pain and unbearable pressure", "negative"), "severe")
        self.assertEqual(coding.severity_of("it slipped once", "negative"), "moderate")

    def test_grade_order_first_match_wins(self) -> None:
        cases = [
            (evidence.not_authorized_inputs("medical_efficacy"), "not_authorized"),
            (evidence.blocked_inputs("G7", "BLOCKED"), "blocked"),
            (evidence.gap_inputs(), "evidence_gap"),
            (evidence.confirmed_inputs("a" * 64), "confirmed"),
            (evidence.hypothesis_inputs(3, 3, 1.0), "hypothesis"),
        ]
        for payload, expected in cases:
            self.assertEqual(evidence.assign_grade(evidence.grade_input_from_dict(payload)), expected)

    def test_count_block_rejects_missing_gap_reason(self) -> None:
        with self.assertRaises(contract.ContractError):
            contract.count_block(None, "annotation", "missing value", "x.json#/x")


class TestPipelineEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="insight-report-test-"))
        builder = build_report.ReportBuilder(DEFAULT_RUN, cls.tmp)
        cls.result = builder.run()
        cls.report_data = json.loads((cls.tmp / "report-data.json").read_text(encoding="utf-8"))
        cls.html = (cls.tmp / "report.html").read_text(encoding="utf-8")
        cls.validation = json.loads((cls.tmp / "validation-result.json").read_text(encoding="utf-8"))

    def test_pipeline_status(self) -> None:
        self.assertEqual(self.result["status"], "PASS")
        self.assertEqual(self.validation["status"], "PASS")
        self.assertTrue(all(check["passed"] for check in self.validation["checks"]))

    def test_sections_and_exhibits(self) -> None:
        sections = self.report_data["report"]["sections"]
        self.assertEqual(len(sections), 11)
        self.assertEqual([section["id"] for section in sections], contract.SECTION_IDS)
        exhibits = [
            block for section in sections for block in section["blocks"] if block.get("type") == "exhibit"
        ]
        self.assertEqual(len(exhibits), 9)
        self.assertEqual([block["number"] for block in exhibits], ["01", "02", "03", "04", "05", "06", "08", "09", "10"])

    def test_counts_are_reconciled(self) -> None:
        corpus = self.report_data["evidence"]["corpus"]
        self.assertLessEqual(corpus["canonical_records"]["value"], corpus["occurrences"]["value"])
        self.assertLessEqual(corpus["occurrences"]["value"], corpus["raw_objects"]["value"])
        self.assertGreaterEqual(corpus["frame_memberships"]["value"], corpus["canonical_records"]["value"])
        for row in corpus["reconciliation"]:
            expected = row["deducted"] if row["deducted"] >= 0 else -row["deducted"]
            self.assertEqual(sum(row["reasons"].values()), expected)
            self.assertEqual(row["input_count"] - row["deducted"], row["output_count"])

    def test_metric_rows_fail_closed(self) -> None:
        self.assertEqual(self.report_data["evidence"]["corpus"]["metric_rows"]["value"], 0)
        gates = {item["gate_id"]: item["status"] for item in self.report_data["evidence"]["gate"]["gates"]}
        self.assertNotEqual(gates.get("G7"), "PASS")

    def test_number_refs_resolve(self) -> None:
        resolver = metrics.Resolver(self.tmp)
        for claim in self.report_data["report"]["claims"]:
            for number in claim["numbers"]:
                self.assertEqual(resolver.resolve(number["source_path"]), number["value"])

    def test_counterevidence_never_empty(self) -> None:
        for claim in self.report_data["report"]["claims"]:
            counter = claim["counterevidence"]
            text = counter["text"] if isinstance(counter, dict) else counter
            self.assertTrue(text.strip())
        joined = json.dumps(self.report_data, ensure_ascii=False)
        self.assertIn("NO_COUNTEREVIDENCE_FOUND", joined)

    def test_prohibited_outputs_cover_required_categories(self) -> None:
        labels = " ".join(item["label"] for item in self.report_data["report"]["prohibited_outputs"])
        for token in ("总体情绪率", "饼图", "跨 frame", "annotation", "星级", "ROI", "医学", "覆盖"):
            self.assertIn(token, labels)

    def test_html_shell(self) -> None:
        self.assertEqual(self.html.count("<h1"), 1)
        self.assertEqual(self.html.count('<section class="section"'), 11)
        self.assertEqual(self.html.count("<h2>"), 11)
        self.assertGreaterEqual(self.html.count('<figure class="exhibit"'), 1)
        self.assertIn('<details class="evidence-drawer">', self.html)
        self.assertIn("font-variant-numeric:tabular-nums", self.html)
        for pattern in ("<link", "<script src", "http://", "https://", "<img", "<iframe", "<svg"):
            self.assertNotIn(pattern, self.html)

    def test_no_banned_words_outside_prohibited_block(self) -> None:
        suite = validate.validate_html(self.html)
        failures = [check for check in suite.checks if not check.passed]
        self.assertEqual(failures, [])

    def test_derivations_present(self) -> None:
        derivations = self.report_data["evidence"]["coverage"]["derivations"]
        self.assertIn("annotation_totals", derivations)
        self.assertIn("cooccurrence.comfort_positive_records", derivations)
        self.assertEqual(
            self.report_data["evidence"]["identity"]["variants"]["items"][0]["review_count"],
            None,
        )
        self.assertIn("gap_reason", self.report_data["evidence"]["identity"]["variants"]["items"][0])


if __name__ == "__main__":
    unittest.main()
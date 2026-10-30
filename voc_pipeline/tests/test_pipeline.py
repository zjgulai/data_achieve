"""Behavioral tests: success paths and failure paths.

Run with: python3 -m unittest discover -s voc_pipeline/tests -v
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voc import canonical, coder, counting, evidence, llm_coder, metrics, creator_video, report as report_mod, validate_report  # noqa: E402
from voc.contracts import (  # noqa: E402
    FORBIDDEN_CONCLUSIONS,
    Claim,
    CountingLevel,
    DeductionReason,
    EvidenceGrade,
    LedgerRow,
)
from voc.taxonomy import ALL_CODES, taxonomy_dict  # noqa: E402


class CountingTests(unittest.TestCase):
    def test_reconciliation_must_balance(self) -> None:
        row = LedgerRow(CountingLevel.OCCURRENCE, CountingLevel.CANONICAL_RECORD, 96, 95, {DeductionReason.CROSS_SOURCE_SYNDICATED.value: 1})
        row.check()
        with self.assertRaises(ValueError):
            LedgerRow(CountingLevel.OCCURRENCE, CountingLevel.CANONICAL_RECORD, 96, 95, {}).check()

    def test_six_levels_declared(self) -> None:
        self.assertEqual(len(counting.COUNTING_LEVELS), 6)
        levels = {lvl["level"] for lvl in counting.COUNTING_LEVELS}
        self.assertEqual(len(levels), 6)

    def test_every_deduction_has_a_code(self) -> None:
        for rule in counting.DEDUCTION_RULES:
            self.assertTrue(rule["code"])
            self.assertIn(rule["code"], [r.value for r in DeductionReason])


class EvidenceTests(unittest.TestCase):
    def test_medical_is_not_authorized_before_anything_else(self) -> None:
        grade = evidence.assign_grade(evidence.GradeInput(topic="medical_efficacy"))
        self.assertEqual(grade, evidence.EvidenceGrade.NOT_AUTHORIZED)

    def test_missing_gate_blocks_even_with_large_n(self) -> None:
        grade = evidence.assign_grade(
            evidence.GradeInput(required_gate="G7", gate_status="BLOCKED", n_independent=500, n_authors=50, direction_share=0.99)
        )
        self.assertEqual(grade, evidence.EvidenceGrade.BLOCKED)

    def test_prevalence_from_diagnostic_is_blocked(self) -> None:
        grade = evidence.assign_grade(
            evidence.GradeInput(is_prevalence_claim=True, denominator=28, frame="diagnostic", n_independent=28, n_authors=10, direction_share=0.9)
        )
        self.assertEqual(grade, evidence.EvidenceGrade.BLOCKED)

    def test_empty_cell_is_gap(self) -> None:
        grade = evidence.assign_grade(evidence.GradeInput(required_cell_count=0))
        self.assertEqual(grade, evidence.EvidenceGrade.GAP)

    def test_comparative_support_gate_failure_is_gap(self) -> None:
        grade, reason = evidence.explain_grade(
            evidence.GradeInput(
                required_support_gate="creator_video_layer_support",
                support_gate_status="FAILED",
                n_independent=48,
                n_authors=42,
            )
        )
        self.assertEqual(grade, evidence.EvidenceGrade.GAP)
        self.assertIn("support_gate=creator_video_layer_support", reason)
        self.assertIn("status=FAILED", reason)

    def test_confirmed_requires_artifact_and_no_inference(self) -> None:
        grade = evidence.assign_grade(evidence.GradeInput(is_direct_fact=True, artifact_sha256="abc", exact_identity=True, inference=False))
        self.assertEqual(grade, evidence.EvidenceGrade.CONFIRMED)
        downgraded = evidence.assign_grade(evidence.GradeInput(is_direct_fact=True, artifact_sha256=None, exact_identity=True, inference=False))
        self.assertNotEqual(downgraded, evidence.EvidenceGrade.CONFIRMED)

    def test_directional_threshold(self) -> None:
        grade = evidence.assign_grade(evidence.GradeInput(n_independent=8, n_authors=2, direction_share=0.70))
        self.assertEqual(grade, evidence.EvidenceGrade.DIRECTIONAL)
        lower = evidence.assign_grade(evidence.GradeInput(n_independent=7, n_authors=2, direction_share=0.70))
        self.assertEqual(lower, evidence.EvidenceGrade.SUPPORTED_HYPOTHESIS)

    def test_single_author_is_supported_hypothesis(self) -> None:
        grade = evidence.assign_grade(evidence.GradeInput(n_independent=30, n_authors=1, direction_share=0.95))
        self.assertEqual(grade, evidence.EvidenceGrade.SUPPORTED_HYPOTHESIS)

    def test_grade_reason_quotes_the_counts_that_fired(self) -> None:
        grade, reason = evidence.explain_grade(
            evidence.GradeInput(n_independent=9, n_authors=3, direction_share=0.78)
        )
        self.assertEqual(grade, evidence.EvidenceGrade.DIRECTIONAL)
        self.assertIn("n_records=9", reason)
        self.assertIn("n_authors=3", reason)
        self.assertIn("78%", reason)

    def test_grade_reason_names_the_rule_in_order(self) -> None:
        _, reason = evidence.explain_grade(evidence.GradeInput(topic="safety"))
        self.assertIn("规则1", reason)
        _, blocked = evidence.explain_grade(
            evidence.GradeInput(required_gate="G7", gate_status="BLOCKED", n_independent=500)
        )
        self.assertIn("规则2", blocked)
        _, gap = evidence.explain_grade(evidence.GradeInput(required_cell_count=0))
        self.assertIn("规则3", gap)

    def test_hypothesis_reason_names_only_the_trigger_that_fired(self) -> None:
        grade, reason = evidence.explain_grade(
            evidence.GradeInput(n_independent=14, n_authors=14, direction_share=0.667)
        )
        self.assertEqual(grade, evidence.EvidenceGrade.SUPPORTED_HYPOTHESIS)
        self.assertIn("agreement=67% 落在 55–70%", reason)
        self.assertNotIn("n_records=14 落在 3–7", reason)

    def test_large_n_with_low_agreement_is_hypothesis_with_the_missing_condition(self) -> None:
        grade, reason = evidence.explain_grade(
            evidence.GradeInput(n_independent=40, n_authors=10, direction_share=0.30)
        )
        self.assertEqual(grade, evidence.EvidenceGrade.SUPPORTED_HYPOTHESIS)
        self.assertIn("差在方向一致度", reason)
        self.assertNotIn("兜底", reason)

    def test_unclassified_counts_fall_to_gap_not_supported_hypothesis(self) -> None:
        # 8+ records and 2+ authors with a direction share that passes the
        # Directional threshold, but single_coded=False: no rule covers it.
        # Fail closed to Evidence gap; never grant the lowest positive grade.
        grade, reason = evidence.explain_grade(
            evidence.GradeInput(
                n_independent=8,
                n_authors=2,
                direction_share=0.70,
                single_coded=False,
            )
        )
        self.assertEqual(grade, evidence.EvidenceGrade.GAP)
        self.assertNotIn("兜底", reason)

    def test_zero_evidence_is_gap_even_with_one_author(self) -> None:
        grade = evidence.assign_grade(
            evidence.GradeInput(n_independent=0, n_authors=1, direction_share=0.60)
        )
        self.assertEqual(grade, evidence.EvidenceGrade.GAP)

    def test_all_six_grades_are_reachable_and_distinct(self) -> None:
        samples = [
            evidence.GradeInput(topic="diagnosis"),
            evidence.GradeInput(required_gate="G7", gate_status="BLOCKED"),
            evidence.GradeInput(required_cell_count=0),
            evidence.GradeInput(is_direct_fact=True, artifact_sha256="abc", exact_identity=True, inference=False),
            evidence.GradeInput(n_independent=8, n_authors=2, direction_share=0.70),
            evidence.GradeInput(n_independent=4, n_authors=2, direction_share=0.60),
        ]
        grades = [evidence.assign_grade(sample) for sample in samples]
        self.assertEqual(len(set(grades)), 6)
        self.assertEqual(
            [g.value for g in grades],
            ["Not authorized", "Blocked", "Evidence gap", "Confirmed", "Directional", "Supported hypothesis"],
        )


def _occ(eid, frame, text, author="a", created=1):
    return canonical.Occurrence(
        occurrence_id=f"reddit:post:{eid}:{frame}",
        source="reddit",
        kind="post",
        external_id=eid,
        frame=frame,
        subreddit="BabyBumps",
        author=author,
        created_utc=created,
        url=f"https://example/{eid}",
        title="",
        text=text,
        score=1,
        num_comments=0,
        raw_id="raw",
    )


def _reddit_rec(cid, title, text, product_match="category_adjacent"):
    return canonical.CanonicalRecord(
        canonical_id=cid,
        representative="o",
        memberships=[],
        source="reddit",
        external_id=cid,
        subreddit="BabyBumps",
        author="a",
        created_utc=1,
        url="u",
        title=title,
        text=text,
        content_hash="h",
        duplicate_group_id="d",
        dedup_status="unique",
        frames=["natural"],
        product_match=product_match,
        data_layer="consumer_observation_fact",
        content_role="consumer_experience",
        commerciality="no_signal_observed",
        organic_confidence="high",
        metric_eligibility="natural_sample_candidate",
        quality_flags=[],
    )


class CanonicalTests(unittest.TestCase):
    def test_same_content_in_two_frames_is_one_canonical_two_memberships(self) -> None:
        text = "The belly band is comfortable but it slips down when I walk."
        records, summary = canonical.build_canonical(
            [_occ("1", "natural", text), _occ("1", "diagnostic", text)]
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(sorted(records[0].frames), ["diagnostic", "natural"])
        self.assertEqual(summary["frame_memberships"], 2)
        self.assertEqual(summary["canonical_records"], 1)

    def test_same_author_crosspost_merges_with_reason(self) -> None:
        text = "belly band support is okay but the strap digs into my ribs after an hour of wearing it"
        records, summary = canonical.build_canonical(
            [_occ("1", "natural", text), _occ("2", "natural", text, created=2)]
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(summary["deduction_reasons"]["crosspost_same_author"], 1)

    def test_different_content_stays_separate(self) -> None:
        records, _ = canonical.build_canonical(
            [
                _occ("1", "natural", "belly band saved my back on long walks"),
                _occ("2", "natural", "the sizing runs small and the velcro scratches"),
            ]
        )
        self.assertEqual(len(records), 2)


class CoderTests(unittest.TestCase):
    def test_negation_not_treated_as_positive(self) -> None:
        rec = canonical.CanonicalRecord(
            canonical_id="c-1", representative="o", memberships=[], source="reddit", external_id="1",
            subreddit="x", author="a", created_utc=1, url="u", title="", text="The belly band is not comfortable at all.",
            content_hash="h", duplicate_group_id="d", dedup_status="unique", frames=["natural"],
            product_match="category_adjacent", data_layer="consumer_observation_fact",
            content_role="consumer_experience", commerciality="no_signal_observed",
            organic_confidence="high", metric_eligibility="natural_sample_candidate", quality_flags=[],
        )
        coded = coder.code_record(rec)
        com = [a for a in coded.annotations if a.code == "COM.GENERAL" and a.axis == "aspect"]
        self.assertTrue(com)
        self.assertIn(com[0].polarity, {"negative", "qualified_negative"})

    def test_unknown_is_not_negative(self) -> None:
        rec = canonical.CanonicalRecord(
            canonical_id="c-2", representative="o", memberships=[], source="reddit", external_id="2",
            subreddit="x", author="a", created_utc=1, url="u", title="", text="Does anyone use a belly band?",
            content_hash="h", duplicate_group_id="d", dedup_status="unique", frames=["natural"],
            product_match="category_adjacent", data_layer="consumer_observation_fact",
            content_role="consumer_experience", commerciality="no_signal_observed",
            organic_confidence="high", metric_eligibility="natural_sample_candidate", quality_flags=[],
        )
        coded = coder.code_record(rec)
        self.assertNotIn("COM.GENERAL", [a.code for a in coded.annotations])

    def test_negation_scope_does_not_leak_to_later_cues(self) -> None:
        self.assertEqual(
            coder.polarity_of("not a lot of support very soft wobbly expensive"), "mixed"
        )
        self.assertEqual(coder.polarity_of("no support at all, uncomfortable"), "negative")

    def test_not_only_and_emphatic_idioms_are_positive(self) -> None:
        self.assertEqual(
            coder.polarity_of("not only provided me with back support but also confidence"), "positive"
        )
        self.assertEqual(coder.polarity_of("I have never felt so comfortable"), "positive")
        self.assertEqual(coder.polarity_of("I can't believe how comfortable this is"), "positive")

    def test_pain_relief_is_not_a_product_fault(self) -> None:
        self.assertEqual(coder.polarity_of("helps with back pain and very comfortable"), "positive")
        self.assertEqual(coder.polarity_of("it hurts my back"), "negative")

    def test_customer_support_is_not_product_support(self) -> None:
        rec = canonical.CanonicalRecord(
            canonical_id="c-3", representative="o", memberships=[], source="tiktok_shop", external_id="3",
            subreddit="", author="a", created_utc=1, url="u", title="", text="Does not fit well. customer support was great.",
            content_hash="h", duplicate_group_id="d", dedup_status="unique", frames=["tiktok_shop_verified"],
            product_match="exact_current_family", data_layer="consumer_observation_fact",
            content_role="consumer_experience", commerciality="no_signal_observed",
            organic_confidence="high", metric_eligibility="tiktok_verified_candidate", quality_flags=[],
        )
        coded = coder.code_record(rec)
        self.assertNotIn("SUP.GENERAL", [a.code for a in coded.annotations if a.axis == "aspect"])

    def test_third_party_picketing_post_has_no_aspect_annotations(self) -> None:
        rec = _reddit_rec(
            "c-picket",
            "picketing in third trimester",
            "I’m a member of a union that is currently striking. "
            "I did EVERYTHING I could think of to prepare—I requested accomodations ahead of time "
            "to sit in a chair whenever I needed (and this was provided for me no questions asked), "
            "I wore comfortable sneakers with supportive insoles, I brought tons of water to stay "
            "hydrated paired with snacks and electrolytes, I wore a belly band, I took ample breaks "
            "to sit, I took it relatively easy in regards to movement, and I’m STILL in pain.",
        )
        coded = coder.code_record(rec)
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])

    def test_store_availability_post_has_no_aspect_annotations(self) -> None:
        rec = _reddit_rec(
            "c-store",
            "Why is nothing pregnancy related sold instore?!",
            "I am SO frustrated by the fact no one sells maternity things in store. "
            "I’ve searched everyplace I can online for a maternity/pregnancy belly band support belt "
            "and cannot find a single one within an hour of me! "
            "My back is in a ton of pain, it’ll take Amazon or any other place 5 plus days to get "
            "a belly band by mail. It’s insane to me that no pharmacy, no target, no Walmart sells "
            "a support belt for pregnant women.",
        )
        coded = coder.code_record(rec)
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_reason, "help_seeking")

    def test_question_title_with_substantive_evaluation_is_full(self) -> None:
        rec = _reddit_rec(
            "c-best",
            "Which pregnancy belly band is the best?",
            "Frida Mom pregnancy belly band. The fabric is really soft and the design is super simple. "
            "Momcozy pregnancy belly band. It has a patented back support that actually works and "
            "really helps with lower back pain.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        # A2: the question title does not enter the scope calculation.  Two
        # named products with several attributes are a substantive review, so
        # the record is full even though it asks "which is the best?".
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "full")
        self.assertTrue([a for a in coded.annotations if a.axis == "aspect"])
        co = metrics.cooccurrence([rec], [coded])
        self.assertEqual(co["total_annotated_records"], 1)
        self.assertEqual(co["comfort_positive_records"], 1)
        self.assertEqual(co["full"]["comfort_positive_records"], 1)
        self.assertEqual(co["partial"]["comfort_positive_records"], 0)

    def test_cooccurrence_rejects_cross_product_spans(self) -> None:
        rec = _reddit_rec(
            "c-cross",
            "Which pregnancy belly band is the best?",
            "Frida Mom pregnancy belly band. The fabric is really soft.\n\n"
            "Momcozy pregnancy belly band. The support is bad.",
            product_match="exact_current_family",
        )
        source = f"{rec.title}. {rec.text}"
        soft_at = source.find("really soft")
        bad_at = source.find("support is bad")
        annotations = [
            coder.Annotation(
                rec.canonical_id,
                "aspect",
                "COM.SOFTNESS",
                "positive",
                source[soft_at:soft_at + len("really soft")],
                span_start=soft_at,
                span_end=soft_at + len("really soft"),
                span_text=source[soft_at:soft_at + len("really soft")],
            ),
            coder.Annotation(
                rec.canonical_id,
                "aspect",
                "SUP.GENERAL",
                "negative",
                source[bad_at:bad_at + len("support is bad")],
                span_start=bad_at,
                span_end=bad_at + len("support is bad"),
                span_text=source[bad_at:bad_at + len("support is bad")],
            ),
        ]
        coded = coder.CodedRecord(
            canonical_id=rec.canonical_id,
            annotations=annotations,
            product_match="exact_current_family",
            experience_scope="full",
        )
        co = metrics.cooccurrence([rec], [coded])
        self.assertEqual(co["full"]["comfort_positive_records"], 1)
        self.assertEqual(co["full"]["comfort_positive_with_friction"], 0)
        self.assertTrue(co["rows"][0]["cross_product"])
        self.assertFalse(co["rows"][0]["both"])

    def test_help_seeking_with_only_previous_unnamed_band_is_not_experience(self) -> None:
        rec = _reddit_rec(
            "c-b17",
            "Someone help me find a good belly band please!",
            "Are there any that are particularly good for diastasis recti during pregnancy? "
            "I honestly hated my belly band my first pregnancy because it felt so restrictive "
            "and uncomfortable. Thanks!!",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_reason, "help_seeking")
        self.assertEqual(coded.experience_scope, "none")
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])

    def test_undetermined_current_use_is_partial(self) -> None:
        rec = _reddit_rec(
            "c-jury",
            "How are we managing round ligament pain?",
            "I just started using a belly band, but the jury is still out on if it's helping.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "partial")

    def test_help_seeking_with_current_evaluation_is_partial(self) -> None:
        rec = _reddit_rec(
            "c-b06",
            "Turning in my sleep is excruciating",
            "I wore my belly band while sleeping, which helped support my muscles when turning. "
            "Looking for any advice from people who might've experienced this.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "partial")
        self.assertTrue([a for a in coded.annotations if a.axis == "aspect"])

    def test_scope_symptom_relief_after_product_is_full(self) -> None:
        rec = _reddit_rec(
            "c-relief",
            "Band update",
            "I ordered the band last week. By day two my pain was gone. "
            "I feel great and I am back to walking the dog every morning.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "full")

    def test_scope_zero_support_and_comparator_is_full(self) -> None:
        rec = _reddit_rec(
            "c-comparator",
            "",
            "I bought two bands and felt zero support. "
            "KT tape though got me through a 5k.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.experience_scope, "full")

    def test_scope_decisive_result_in_long_narrative_is_full(self) -> None:
        rec = _reddit_rec(
            "c-long-result",
            "",
            "I am 30 weeks and have been active all pregnancy. I walk every morning and do "
            "prenatal yoga twice a week. I had pelvic pain earlier but it eased with rest. "
            "The difference with the band has been night and day, and with it I was back to "
            "running with ease. I hope this helps someone else.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.experience_scope, "full")

    def test_scope_generic_endorsement_stays_partial(self) -> None:
        rec = _reddit_rec(
            "c-generic-praise",
            "",
            "Someone asked for a gift idea. I personally love my belly band, very supportive. "
            "Otherwise a picture frame works.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.experience_scope, "partial")

    def test_scope_hearsay_and_generic_advice_are_none(self) -> None:
        rec = _reddit_rec(
            "c-hearsay",
            "",
            "Does anyone have a band recommendation? For some people a band can help. "
            "My friend used one and swears by it.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "none")

    def test_scope_past_pregnancy_effect_is_partial(self) -> None:
        rec = _reddit_rec(
            "c-past-effect",
            "Rest matters",
            "Rest is important. I did use a belly band in my second pregnancy and it helped "
            "a lot with back pain. My third pregnancy was easier.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.experience_scope, "partial")

    def test_scope_low_density_remedy_list_is_partial(self) -> None:
        rec = _reddit_rec(
            "c-remedy-list",
            "",
            "I got a belly band and it helps a bit. I also use a heating pad, an ice pack, "
            "and warm baths; those feel good too.",
            product_match="exact_current_family",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.experience_scope, "partial")

    def test_irrelevant_product_record_is_not_experience(self) -> None:
        rec = _reddit_rec(
            "c-irrelevant",
            "Help building a pregnancy care package?",
            "I need ideas for a care package for a friend.",
            product_match="irrelevant",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.annotations, [])
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_reason, "product_mismatch")

    def test_mixed_clause_abstains_and_records_reason(self) -> None:
        records, _ = canonical.build_canonical(
            [_tiktok_occ("mixed", "not a lot of support very soft wobbly expensive")]
        )
        coded = coder.code_record(records[0])
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])
        reasons = {item["reason"] for item in coded.unknown_aspects}
        self.assertIn("mixed_clause", reasons)
        self.assertTrue(any(item["code"] == "SUP.GENERAL" for item in coded.unknown_aspects))

    def test_aspect_annotations_quote_the_source_text(self) -> None:
        records, _ = canonical.build_canonical(
            [_tiktok_occ("spans", "Very comfortable and very supportive for your back and belly. Worth it!")]
        )
        rec = records[0]
        coded = coder.code_record(rec)
        aspects = [a for a in coded.annotations if a.axis == "aspect"]
        self.assertTrue(aspects)
        source_text = rec.text if not rec.title else f"{rec.title}. {rec.text}"
        for annotation in aspects:
            self.assertGreaterEqual(annotation.span_start, 0)
            self.assertGreater(annotation.span_end, annotation.span_start)
            self.assertLessEqual(len(annotation.span_text), 120)
            self.assertEqual(
                source_text[annotation.span_start : annotation.span_end], annotation.span_text
            )

    def test_real_tiktok_product_reviews_still_code(self) -> None:
        texts = [
            "Fits good, great quality and support",
            "Very comfortable and very supportive for your back and belly. Worth it!",
            "This has helped so much with hip and lower back pain. I have a sit down job and it’s "
            "comfortable sitting as well. Doesn’t dig in and I love the top bad as well for extra support.",
            "Bought it because my daughter has a school trip coming up that requires a lot of walking. "
            "I tried the belly band while walking on the treadmill and it does help and is comfortable.",
            "I never wore a belly band with my first pregnancy. But I have so much pelvic pressure, "
            "& hip pain at 27 weeks I thought I would try! Loooove the stretch, the comfort & support "
            "and it definitely helps relieve pressure.",
        ]
        records, _ = canonical.build_canonical(
            [_tiktok_occ(str(index), text, author=f"buyer-{index}") for index, text in enumerate(texts)]
        )
        coded = coder.code_corpus(records)
        for record, coded_record in zip(records, coded):
            aspects = [a for a in coded_record.annotations if a.axis == "aspect"]
            self.assertTrue(aspects, f"{record.canonical_id} lost all aspect annotations")

    def test_agreement_refuses_to_invent_second_coder(self) -> None:
        with self.assertRaises(RuntimeError):
            coder.agreement_report([], [])


class TaxonomyTests(unittest.TestCase):
    def test_every_code_has_definition_and_rules(self) -> None:
        for code in ALL_CODES:
            self.assertTrue(code.definition, code.code)
            self.assertTrue(code.include, code.code)
            self.assertTrue(code.exclude, code.code)
            self.assertTrue(code.lexicon, code.code)

    def test_unknown_polarity_is_legal(self) -> None:
        self.assertIn("unknown", taxonomy_dict()["polarity_enum"])

    def test_metric_rows_zero_when_g7_blocked(self) -> None:
        result = metrics.materialize_metrics([], [], g7_status="BLOCKED")
        self.assertEqual(result["metric_rows"], [])
        self.assertIn("G7", result["zero_metric_row_reason"])


def _forbidden_block() -> str:
    rows = "".join(
        f'<tr data-fc-row="{fc.id}"><td>{fc.id}</td><td>{fc.pattern}</td></tr>'
        for fc in FORBIDDEN_CONCLUSIONS
    )
    return (
        f'<details class="forbidden-zone" id="forbidden-conclusions" '
        f'data-forbidden-count="{len(FORBIDDEN_CONCLUSIONS)}">'
        f"<summary>这份报告不能说的事：{len(FORBIDDEN_CONCLUSIONS)} 类</summary>"
        f"<table><tbody>{rows}</tbody></table></details>"
    )


def _inline_cites(*ids: str) -> str:
    return "".join(f'<span class="fc-cite" data-fc="{fid}">禁写 {fid}</span>' for fid in ids)


class ReportFailureTests(unittest.TestCase):
    def _write(self, doc: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "r.html"
        path.write_text(doc, encoding="utf-8")
        return path

    def test_noun_heading_fails(self) -> None:
        doc = "<h2>概览</h2><article class='claim'><b>Observed</b><b>Interpretation</b><b>Counterevidence</b><b>Decision implication</b></article>"
        suite = validate_report.validate_report(self._write(doc))
        failed = {c.name for c in suite.checks if not c.passed}
        self.assertIn("h2_are_claim_sentences", failed)

    def test_pie_chart_language_fails(self) -> None:
        doc = "<h2>这是一个完整的结论句子。</h2><div>饼图</div>"
        suite = validate_report.validate_report(self._write(doc))
        failed = {c.name for c in suite.checks if not c.passed}
        self.assertIn("no_anti_patterns", failed)

    def test_fallback_grade_reason_fails(self) -> None:
        doc = "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
        path = self._write(doc)
        claims = [
            {
                "claim_id": "C99",
                "grade": "Supported hypothesis",
                "grade_reason": "规则6 兜底：未达 Directional 阈值，按最低可用档记录。",
                "numbers": {"n": 1},
                "counts": {"n_records": 8, "n_authors": 8, "agreement_pct": 0.0},
            }
        ]
        claims_path = path.with_name("claims.json")
        claims_path.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
        suite = validate_report.validate_report(path, claims_path)
        check = {c.name: c for c in suite.checks}["claims_have_no_fallback_grade"]
        self.assertFalse(check.passed)
        self.assertIn("C99", check.detail)
        with self.assertRaises(validate_report.ForbiddenConclusionError):
            validate_report.assert_report_clean(path, claims_path)

    def test_valid_minimal_report_passes_core_checks(self) -> None:
        fig = (
            "<figure data-basis='分母 = 1 条记录' data-unit='u' data-limit='l' data-status='Confirmed'>"
            "<figcaption>EXHIBIT 01 一个完整的图表标题句子。</figcaption>"
            "<b>Basis</b><b>Unit</b><b>Limit</b><b>Status</b></figure>"
        )
        claim = (
            "<article class='claim'><b>Observed</b><b>Interpretation</b><b>Counterevidence</b>"
            "<b>Decision implication</b></article>"
        )
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>" + claim + fig
            + "<div>Confirmed Directional Supported hypothesis Evidence gap Blocked Not authorized</div>"
            + _inline_cites("FC-01", "FC-09", "FC-10")
            + _forbidden_block()
        )
        suite = validate_report.validate_report(self._write(doc))
        required = {
            "h2_are_claim_sentences",
            "claim_four_cells",
            "figure_contract",
            "figure_captions_are_claims",
            "figure_status_is_grade",
            "figure_basis_declares_denominator",
            "forbidden_catalog_complete",
            "forbidden_list_rendered",
            "inline_citations_three",
            "no_forbidden_conclusions",
            "no_anti_patterns",
            "six_evidence_states",
            "forbidden_list_at_end",
        }
        failed = {c.name for c in suite.checks if not c.passed} & required
        self.assertEqual(failed, set())

    def test_exhibit_status_must_be_a_grade_not_prose(self) -> None:
        fig = (
            "<figure data-basis='分母 = 1' data-unit='u' data-limit='l' data-status='Confirmed · 手写状态'>"
            "<figcaption>EXHIBIT 01 一个完整的图表标题句子。</figcaption>"
            "<b>Basis</b><b>Unit</b><b>Limit</b><b>Status</b></figure>"
        )
        suite = validate_report.validate_report(self._write("<h2>这是一个完整的结论句子，带足够的长度。</h2>" + fig))
        failed = {c.name for c in suite.checks if not c.passed}
        self.assertIn("figure_status_is_grade", failed)

    def test_exhibit_basis_without_denominator_fails(self) -> None:
        fig = (
            "<figure data-basis='某个 artifact' data-unit='u' data-limit='l' data-status='Confirmed'>"
            "<figcaption>EXHIBIT 01 一个完整的图表标题句子。</figcaption>"
            "<b>Basis</b><b>Unit</b><b>Limit</b><b>Status</b></figure>"
        )
        suite = validate_report.validate_report(self._write("<h2>这是一个完整的结论句子，带足够的长度。</h2>" + fig))
        failed = {c.name for c in suite.checks if not c.passed}
        self.assertIn("figure_basis_declares_denominator", failed)


class ClaimGradeTextTests(unittest.TestCase):
    """Headline and status must name the computed grade, never a stale literal."""

    def _paths(self, claims: list[dict]) -> tuple[Path, Path]:
        tmp = Path(tempfile.mkdtemp())
        html_path = tmp / "r.html"
        html_path.write_text(
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>", encoding="utf-8"
        )
        claims_path = tmp / "claims.json"
        claims_path.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
        return html_path, claims_path

    def _check(self, claims: list[dict]) -> validate_report.Check:
        html_path, claims_path = self._paths(claims)
        checks = {
            c.name: c for c in validate_report.validate_report(html_path, claims_path).checks
        }
        return checks["claim_text_matches_grade"]

    def _claim(self, grade: str, headline: str, status: str) -> dict:
        return {
            "claim_id": "C13",
            "grade": grade,
            "headline": headline,
            "status": status,
        }

    def test_stale_directional_text_fails_after_downgrade(self) -> None:
        check = self._check([
            self._claim(
                "Supported hypothesis",
                "方向一致度 64%，达到 Directional 门槛。",
                "Directional · single-coded, pre-G7",
            )
        ])
        self.assertFalse(check.passed)
        self.assertIn("C13.headline", check.detail)
        self.assertIn("C13.status", check.detail)

    def test_negated_threshold_is_not_a_false_claim(self) -> None:
        check = self._check([
            self._claim(
                "Supported hypothesis",
                "方向一致度 64%，未达 Directional 门槛，按 Supported hypothesis 记录。",
                "Supported hypothesis · single-coded, pre-G7",
            )
        ])
        self.assertTrue(check.passed, check.detail)

    def test_other_negation_forms_are_not_false_claims(self) -> None:
        for headline in (
            "方向一致度 64%，没有达到 Directional 门槛。",
            "方向一致度 64%，尚未达到 Directional 门槛。",
        ):
            check = self._check([
                self._claim(
                    "Supported hypothesis",
                    headline,
                    "Supported hypothesis · single-coded, pre-G7",
                )
            ])
            self.assertTrue(check.passed, f"{headline} -> {check.detail}")

    def test_directional_text_matches_directional_grade(self) -> None:
        check = self._check([
            self._claim(
                "Directional",
                "方向一致度 81%，达到 Directional 门槛。",
                "Directional · single-coded, pre-G7",
            )
        ])
        self.assertTrue(check.passed, check.detail)

    def test_build_gate_rejects_stale_grade_text(self) -> None:
        html_path, claims_path = self._paths([
            self._claim(
                "Supported hypothesis",
                "方向一致度 64%，达到 Directional 门槛。",
                "Supported hypothesis · single-coded, pre-G7",
            )
        ])
        with self.assertRaises(validate_report.ForbiddenConclusionError) as ctx:
            validate_report.assert_report_clean(html_path, claims_path)
        self.assertIn("C13.headline", str(ctx.exception))

    def test_claim_status_helpers_render_from_grade(self) -> None:
        from voc import claims as claims_mod

        self.assertEqual(
            claims_mod._status_for(
                EvidenceGrade.SUPPORTED_HYPOTHESIS, "single-coded, pre-G7"
            ),
            "Supported hypothesis · single-coded, pre-G7",
        )
        self.assertEqual(
            claims_mod._direction_threshold_clause(EvidenceGrade.DIRECTIONAL),
            "达到 Directional 门槛",
        )
        self.assertEqual(
            claims_mod._direction_threshold_clause(EvidenceGrade.SUPPORTED_HYPOTHESIS),
            "未达 Directional 门槛，按 Supported hypothesis 记录",
        )
        self.assertEqual(
            claims_mod._direction_threshold_clause(EvidenceGrade.GAP),
            "档位为 Evidence gap",
        )
        self.assertIn(
            "把支撑方向抬到 Directional",
            report_mod._c13_hero_clause(EvidenceGrade.DIRECTIONAL),
        )
        self.assertIn(
            "未达 Directional 门槛",
            report_mod._c13_hero_clause(EvidenceGrade.SUPPORTED_HYPOTHESIS),
        )
        self.assertIn(
            "Supported hypothesis",
            report_mod._c13_hero_clause(EvidenceGrade.SUPPORTED_HYPOTHESIS),
        )


class ModelDiversityWordingTests(unittest.TestCase):
    """A bare "模型家族 / 独立盲标" claim must not pass as independent validation."""

    def _write(self, doc: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "r.html"
        path.write_text(doc, encoding="utf-8")
        return path

    def _check(self, doc: str):
        suite = validate_report.validate_report(self._write(doc))
        return {c.name: c for c in suite.checks}["no_false_model_diversity"]

    def test_false_model_diversity_fails_with_snippet(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            "<p>本轮由 5 个模型家族独立盲标完成。</p>"
        )
        check = self._check(doc)
        self.assertFalse(check.passed)
        self.assertIn("模型家族", check.detail)
        self.assertIn("独立盲标", check.detail)
        self.assertIn("5 个模型家族独立盲标完成", check.detail)

    def test_family_caveat_in_same_paragraph_passes(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            "<p>5 个标注身份不是模型家族，而是同一底座 deepseek-flash 的同族自一致。</p>"
        )
        self.assertTrue(self._check(doc).passed)

    def test_caveat_in_next_paragraph_does_not_rescue(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            "<p>本轮由 5 个模型家族独立盲标完成。</p>"
            "<p>这是同族自一致，不是独立验证。</p>"
        )
        check = self._check(doc)
        self.assertFalse(check.passed)
        self.assertIn("5 个模型家族独立盲标完成", check.detail)
        self.assertNotIn("这是同族自一致", check.detail)

    def test_build_gate_rejects_model_diversity(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            "<p>5 个模型家族独立盲标。</p>"
        )
        with self.assertRaises(validate_report.ForbiddenConclusionError) as ctx:
            validate_report.assert_report_clean(self._write(doc))
        self.assertIn("模型家族", str(ctx.exception))
        self.assertIn("5 个模型家族独立盲标", str(ctx.exception))


class EmptyGroupStatsRuleTests(unittest.TestCase):
    """C16 fail-open: an empty/small stratum must never carry a statistic."""

    def _checks(self, body: str, claims: list[dict] | None = None):
        tmp = Path(tempfile.mkdtemp())
        html_path = tmp / "r.html"
        html_path.write_text(
            "<h2>这是一个完整的结论句子，带足够的长度。</h2><p>" + body + "</p>",
            encoding="utf-8",
        )
        claims_path = None
        if claims is not None:
            claims_path = tmp / "claims.json"
            claims_path.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
        suite = validate_report.validate_report(html_path, claims_path)
        return {c.name: c for c in suite.checks}

    def test_exact_counting_sentence_passes(self) -> None:
        body = (
            "10 条基线视频在预定义维度上没有可用分层。时长档：<=15s 1 条、"
            "16-30s 4 条、31-60s 4 条、>60s 1 条，四层均小于 8。"
            "has_link：true 10 条、false 0 条。ad_disclosure：true 10 条、false 0 条。"
            "platform_is_ad：true 9 条、false 1 条，false 组小于 8。"
            "没有任何维度同时满足层内 n>=8 与对照组 n>=8，"
            "因此本轮不产出任何分层中位数、倍数、p 值或置信区间。"
            "结论是样本不足以检验，不是已证明没有内容形态跑赢。"
        )
        checks = self._checks(body)
        self.assertTrue(checks["no_empty_group_stats"].passed, checks["no_empty_group_stats"].detail)
        self.assertTrue(checks["strata_require_min_n"].passed, checks["strata_require_min_n"].detail)

    def test_valid_stratum_n18_passes(self) -> None:
        checks = self._checks(
            "时长档 31-60s 的中位互动率为 2.85%（n=18），倍数 2.24x，p=0.409"
        )
        self.assertTrue(checks["no_empty_group_stats"].passed)
        self.assertTrue(checks["strata_require_min_n"].passed)

    def test_zero_group_statistics_fail(self) -> None:
        checks = self._checks(
            "时长档的中位互动率为 0.00%（n=0），倍数 0.00x，p=0.000"
        )
        self.assertFalse(checks["no_empty_group_stats"].passed)
        self.assertIn("0.00x", checks["no_empty_group_stats"].detail)
        self.assertIn("p=0.000", checks["no_empty_group_stats"].detail)

    def test_has_link_zero_multiple_and_ci_fail(self) -> None:
        checks = self._checks(
            "has_link=false 为 0.00x（p=0.000，CI [0.00, 0.00]）"
        )
        self.assertFalse(checks["no_empty_group_stats"].passed)
        self.assertIn("CI [0.00, 0.00]", checks["no_empty_group_stats"].detail)

    def test_stratum_statistic_without_n_fails(self) -> None:
        checks = self._checks("时长档 31-60s 的中位互动率为 2.85%，倍数 2.24x")
        self.assertFalse(checks["strata_require_min_n"].passed)
        self.assertIn("n>=8", checks["strata_require_min_n"].detail)

    def test_conclusion_without_n_fails(self) -> None:
        checks = self._checks("没有任何内容形态跑赢它")
        self.assertFalse(checks["strata_require_min_n"].passed)

    def test_exempt_counting_paragraph_passes(self) -> None:
        checks = self._checks(
            "本轮不产出任何分层中位数、倍数、p 值或置信区间，只报各层计数。"
        )
        self.assertTrue(checks["no_empty_group_stats"].passed)
        self.assertTrue(checks["strata_require_min_n"].passed)

    def test_claims_statistics_must_be_null_when_no_stratified_baseline(self) -> None:
        claims = [{
            "claim_id": "C16",
            "grade": "Evidence gap",
            "grade_reason": "规则 样本不足",
            "counts": {"n_records": 10, "n_authors": 10, "agreement_pct": 0.0},
            "numbers": {
                "stratified_baseline_available": False,
                "top_layer_median_interaction_rate": None,
                "median_multiple": 0.0,
                "mann_whitney_p": 0.0,
            },
        }]
        checks = self._checks("本轮无可用分层，只报各层计数。", claims)
        self.assertFalse(checks["no_empty_group_stats"].passed)
        self.assertIn("median_multiple", checks["no_empty_group_stats"].detail)
        self.assertIn("mann_whitney_p", checks["no_empty_group_stats"].detail)


def _demo_claim(grade: EvidenceGrade = EvidenceGrade.GAP) -> Claim:
    return Claim(
        claim_id="C99",
        section="demo",
        headline="这是一条用于测试的结论句子。",
        grade=grade,
        observed="observed",
        interpretation="interpretation",
        counterevidence="counterevidence",
        decision="decision",
        basis="demo artifact",
        unit="records",
        limit="demo limit",
        status="hand-written status that must not win",
        grade_reason="规则3 命中：required_cell_count=0。",
        counts={"n_records": 0, "n_authors": 0, "agreement_pct": 0.0},
    )


class ExhibitFootnoteTests(unittest.TestCase):
    def test_status_comes_from_the_linked_claim_grade(self) -> None:
        log = report_mod.ExhibitLog()
        html = report_mod.figure(
            "EXHIBIT 99",
            "这是一张完整的图表标题句子。",
            "note",
            "<div>body</div>",
            basis="分母 = 0 条记录",
            unit="records",
            limit="demo",
            status="Confirmed · 手写状态不应生效",
            claim=_demo_claim(EvidenceGrade.GAP),
            log=log,
        )
        self.assertIn('data-status="Evidence gap"', html)
        self.assertNotIn("手写状态", html)
        self.assertEqual(log.summary(), {"exhibits": 1, "declared": 1, "undeclared": 0, "coverage_pct": 100.0})

    def test_missing_parts_render_unknown_and_are_listed(self) -> None:
        log = report_mod.ExhibitLog()
        html = report_mod.figure(
            "EXHIBIT 98",
            "这是一张完整的图表标题句子。",
            "note",
            "<div>body</div>",
            unit="records",
            log=log,
        )
        for label in ("Basis", "Limit", "Status"):
            self.assertIn(f"<b>{label}</b>UNKNOWN", html)
        self.assertIn("<b>Unit</b>records", html)
        self.assertEqual(log.summary()["undeclared"], 1)
        self.assertIn("Basis", log.undeclared[0]["missing"])
        self.assertIn("Status", log.undeclared[0]["missing"])
        self.assertIn("EXHIBIT 98", log.undeclared_html())

    def test_claim_to_dict_carries_reason_and_counts(self) -> None:
        payload = _demo_claim(EvidenceGrade.BLOCKED).to_dict()
        self.assertEqual(payload["grade"], "Blocked")
        self.assertTrue(payload["grade_reason"])
        self.assertEqual(set(payload["counts"]), {"n_records", "n_authors", "agreement_pct"})


class ClaimBlockTests(unittest.TestCase):
    """The rendered report, not just claims.json, must carry grade + reason + counts."""

    def _validate(self, block: str):
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "r.html"
        path.write_text("<h2>这是一个完整的结论句子，带足够的长度。</h2>" + block, encoding="utf-8")
        return {c.name: c for c in validate_report.validate_report(path).checks}

    def test_block_renders_grade_reason_and_counts(self) -> None:
        block = report_mod.claim_block(_demo_claim(EvidenceGrade.DIRECTIONAL))
        self.assertIn('data-grade="Directional"', block)
        self.assertIn("规则3 命中", block)
        self.assertIn("<b>Why this grade</b>", block)
        self.assertIn("n_records=0", block)
        self.assertIn("n_authors=0", block)
        self.assertIn("agreement=0%", block)

    def test_block_passes_the_three_new_checks(self) -> None:
        checks = self._validate(report_mod.claim_block(_demo_claim(EvidenceGrade.GAP)))
        for name in ("claim_blocks_carry_grade", "claim_blocks_have_grade_reason", "claim_blocks_have_counts"):
            self.assertTrue(checks[name].passed, checks[name].detail)

    def test_count_fact_renders_na_instead_of_fake_agreement(self) -> None:
        claim = dataclasses.replace(
            _demo_claim(EvidenceGrade.CONFIRMED),
            counts={"n_records": 21, "n_authors": 19, "agreement_pct": None},
        )
        block = report_mod.claim_block(claim)
        self.assertIn("agreement=N/A", block)
        checks = self._validate(block)
        self.assertTrue(checks["claim_blocks_have_counts"].passed, checks["claim_blocks_have_counts"].detail)

    def test_empty_reason_and_counts_fail_the_block_checks(self) -> None:
        stripped = dataclasses.replace(
            _demo_claim(EvidenceGrade.GAP), grade_reason="", counts={}
        )
        checks = self._validate(report_mod.claim_block(stripped))
        self.assertFalse(checks["claim_blocks_have_grade_reason"].passed)
        self.assertFalse(checks["claim_blocks_have_counts"].passed)

class SourcePrecisionTests(unittest.TestCase):
    """Precision is published per source; a merged number never stands alone."""

    def _write(self, doc: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "r.html"
        path.write_text(doc, encoding="utf-8")
        return path

    def test_precision_table_has_three_rows_and_per_source_values(self) -> None:
        html = report_mod.precision_source_table()
        self.assertIn('data-precision-table="source-split"', html)
        self.assertIn('data-source="tiktok_shop"', html)
        self.assertIn('data-precision="90.5"', html)
        self.assertIn('data-source="reddit"', html)
        self.assertIn('data-precision="50.0"', html)
        self.assertIn('data-source="all"', html)
        self.assertIn('data-precision="87.0"', html)
        self.assertIn("不足以编码（样本过小）", html)

    def test_inherited_v2_precision_is_marked_unverified(self) -> None:
        precision = {
            "gate": "high",
            "verification": {"status": "unverified_inherited_from_v1"},
            "sources": {
                "tiktok_shop": {
                    "label": "TikTok Shop",
                    "high_aspects": 42,
                    "precision_pct": 90.5,
                    "recall_pct": 49.4,
                },
                "reddit": {
                    "label": "Reddit",
                    "high_aspects": 4,
                    "precision_pct": 50.0,
                    "recall_pct": 25.0,
                },
                "all": {
                    "label": "合并",
                    "high_aspects": 46,
                    "precision_pct": 87.0,
                    "recall_pct": 47.1,
                },
            },
        }
        table = report_mod.precision_source_table(precision)
        self.assertIn("v2 未做人工 gold 评测", table)
        self.assertIn("沿用 v1", table)
        self.assertIn("未验证", table)
        basis = report_mod.evidence_basis_table(precision)
        self.assertIn("v2 沿用 v1，未验证", basis)

    def test_evidence_basis_table_has_three_distinct_rows(self) -> None:
        cross = {
            "n_items": 20,
            "n_cells": 680,
            "fleiss_all": {"kappa": 0.8354, "prevalence": 0.0538},
            "fleiss_by_source": {
                "TikTok": {"kappa": 0.8525},
                "Reddit": {"kappa": 0.7357},
            },
            "consensus": {"strong": 31, "weak": 4, "disagreement": 14},
        }
        html = report_mod.evidence_basis_table(cross_model=cross)
        self.assertIn('data-cross-model-table="evidence-basis"', html)
        for row in ("llm-gold", "cross-model", "human"):
            self.assertIn(f'data-evidence-basis="{row}"', html)
        self.assertIn('data-cross-model-agreement="true"', html)
        self.assertIn("LLM vs LLM gold set（旧）", html)
        self.assertIn("TikTok Shop 90.5% / Reddit 50.0% / ALL 87.0%", html)
        self.assertIn("Fleiss κ=0.8354", html)
        self.assertIn("TikTok 0.8525 / Reddit 0.7357", html)
        self.assertIn("强共识 31/49 = 63.3%", html)
        self.assertIn("人工验证", html)
        self.assertIn("G7 仍 BLOCKED", html)
        self.assertIn("自证", html)
        self.assertIn("不是人工准确率", html)

    def test_reddit_coded_claim_is_low_confidence(self) -> None:
        claim = dataclasses.replace(
            _demo_claim(EvidenceGrade.CONFIRMED),
            claim_id="C04",
            numbers={"friction_records": 3},
        )
        profiles = report_mod.build_claim_source_profiles([claim])
        block = report_mod.claim_block(claim, profiles["C04"])
        self.assertIn("低可信", block)
        self.assertIn("50.0%", block)
        self.assertIn("4 个 high aspect", block)

    def test_tiktok_coded_claim_shows_the_905_basis(self) -> None:
        claim = dataclasses.replace(
            _demo_claim(EvidenceGrade.DIRECTIONAL),
            claim_id="C13",
            numbers={"support_decisive": 32},
        )
        profiles = report_mod.build_claim_source_profiles([claim])
        block = report_mod.claim_block(claim, profiles["C13"])
        self.assertIn("90.5%", block)
        self.assertNotIn("低可信", block)

    def test_validator_fails_on_merged_precision_without_split(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            "<p>合并 strict precision 87.0%。</p>"
        )
        path = self._write(doc)
        suite = validate_report.validate_report(path)
        check = {c.name: c for c in suite.checks}["precision_split_required"]
        self.assertFalse(check.passed)
        self.assertIn("source-split", check.detail)
        with self.assertRaises(validate_report.ForbiddenConclusionError):
            validate_report.assert_report_clean(path)

    def test_validator_fails_when_only_the_merged_row_exists(self) -> None:
        table = (
            '<table data-precision-table="source-split"><thead><tr><th>信源</th></tr></thead>'
            '<tbody><tr data-source="all" data-precision="87.0"><td>合并</td></tr></tbody></table>'
        )
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            "<p>合并 strict precision 87.0%。</p>" + table
        )
        suite = validate_report.validate_report(self._write(doc))
        check = {c.name: c for c in suite.checks}["precision_split_required"]
        self.assertFalse(check.passed)
        self.assertIn("tiktok_shop", check.detail)
        self.assertIn("reddit", check.detail)

    def test_validator_fails_on_precision_without_cross_model_row(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            + report_mod.precision_source_table()
        )
        suite = validate_report.validate_report(self._write(doc))
        checks = {c.name: c for c in suite.checks}
        self.assertTrue(checks["precision_split_required"].passed)
        self.assertFalse(checks["cross_model_agreement_required"].passed)
        self.assertIn("data-cross-model-agreement", checks["cross_model_agreement_required"].detail)
        with self.assertRaises(validate_report.ForbiddenConclusionError):
            validate_report.assert_report_clean(self._write(doc))

    def test_validator_passes_with_split_and_cross_model_rows(self) -> None:
        cross = {
            "n_items": 20,
            "n_cells": 680,
            "fleiss_all": {"kappa": 0.8354, "prevalence": 0.0538},
            "fleiss_by_source": {
                "TikTok": {"kappa": 0.8525},
                "Reddit": {"kappa": 0.7357},
            },
            "consensus": {"strong": 31, "weak": 4, "disagreement": 14},
        }
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            + report_mod.evidence_basis_table(cross_model=cross)
            + report_mod.precision_source_table()
        )
        suite = validate_report.validate_report(self._write(doc))
        checks = {c.name: c for c in suite.checks}
        self.assertTrue(checks["precision_split_required"].passed, checks["precision_split_required"].detail)
        self.assertTrue(
            checks["cross_model_agreement_required"].passed,
            checks["cross_model_agreement_required"].detail,
        )


class ForbiddenConclusionTests(unittest.TestCase):
    def _minimal(self) -> str:
        return (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            + _inline_cites("FC-01", "FC-09", "FC-10")
            + _forbidden_block()
        )

    def _write(self, doc: str, claims: list[dict] | None = None):
        tmp = Path(tempfile.mkdtemp())
        html_path = tmp / "r.html"
        html_path.write_text(doc, encoding="utf-8")
        claims_path = None
        if claims is not None:
            claims_path = tmp / "claims.json"
            claims_path.write_text(json.dumps(claims, ensure_ascii=False), encoding="utf-8")
        return html_path, claims_path

    def test_catalog_has_twelve_structured_entries(self) -> None:
        self.assertEqual(len(FORBIDDEN_CONCLUSIONS), 12)
        self.assertEqual(
            [fc.id for fc in FORBIDDEN_CONCLUSIONS],
            [f"FC-{i:02d}" for i in range(1, 13)],
        )
        for fc in FORBIDDEN_CONCLUSIONS:
            self.assertTrue(fc.pattern and fc.why and fc.ref_origin, fc.id)
            self.assertTrue(fc.detected_by.text_regex or fc.detected_by.data_keys, fc.id)
            if fc.detected_by.text_regex:
                re.compile(fc.detected_by.text_regex)

    def test_required_classes_are_covered(self) -> None:
        blob = " ".join(f"{fc.pattern} {fc.why} {fc.ref_origin}" for fc in FORBIDDEN_CONCLUSIONS)
        for needle in ("总体", "饼图", "NPS", "ROI", "净", "漏斗", "frame", "prevalence", "医学", "求助帖", "estimate", "因果"):
            self.assertIn(needle, blob)

    def test_content_format_causality_is_caught(self) -> None:
        html_path, _ = self._write(self._minimal() + "<p>长视频带来更高互动。</p>")
        suite = validate_report.validate_report(html_path)
        check = {c.name: c for c in suite.checks}["no_forbidden_conclusions"]
        self.assertFalse(check.passed)
        self.assertIn("FC-12", check.detail)

    def test_normative_causality_warning_is_not_a_hit(self) -> None:
        html_path, _ = self._write(
            self._minimal() + "<p>内容形态与互动率只是相关，不写成因果。</p>"
        )
        suite = validate_report.validate_report(html_path)
        check = {c.name: c for c in suite.checks}["no_forbidden_conclusions"]
        self.assertTrue(check.passed, check.detail)

    def test_sentiment_percentage_is_caught_with_snippet(self) -> None:
        html_path, _ = self._write(self._minimal() + "<p>67% 的用户不满意现有支撑带。</p>")
        suite = validate_report.validate_report(html_path)
        check = {c.name: c for c in suite.checks}["no_forbidden_conclusions"]
        self.assertFalse(check.passed)
        self.assertIn("FC-01", check.detail)
        self.assertIn("67%", check.detail)

    def test_medical_assertion_is_caught(self) -> None:
        html_path, _ = self._write(self._minimal() + "<p>本产品对孕晚期腰背痛疗效显著。</p>")
        suite = validate_report.validate_report(html_path)
        check = {c.name: c for c in suite.checks}["no_forbidden_conclusions"]
        self.assertFalse(check.passed)
        self.assertIn("FC-09", check.detail)

    def test_estimated_sales_data_is_caught(self) -> None:
        claims = [
            {
                "claim_id": "C99",
                "grade": "Confirmed",
                "numbers": {"sales_units": 12000, "product_snapshot": {"is_estimated": True}},
            }
        ]
        html_path, claims_path = self._write(self._minimal(), claims)
        suite = validate_report.validate_report(html_path, claims_path)
        check = {c.name: c for c in suite.checks}["no_forbidden_conclusions"]
        self.assertFalse(check.passed)
        self.assertIn("FC-11", check.detail)
        self.assertIn("is_estimated=true", check.detail)

    def test_catalog_quote_inside_details_is_masked(self) -> None:
        # The catalog itself contains 饼图 / NPS / ROI; it must not self-trigger.
        suite = validate_report.validate_report(self._write(self._minimal())[0])
        check = {c.name: c for c in suite.checks}["no_forbidden_conclusions"]
        self.assertTrue(check.passed, check.detail)

    def test_build_gate_raises_on_injected_report(self) -> None:
        html_path, _ = self._write(self._minimal() + "<p>NPS 达到 42 分。</p>")
        with self.assertRaises(validate_report.ForbiddenConclusionError) as ctx:
            validate_report.assert_report_clean(html_path)
        self.assertIn("FC-03", str(ctx.exception))
        self.assertIn("NPS 达到 42 分", str(ctx.exception))

    def test_inline_citations_must_be_exactly_three(self) -> None:
        doc = (
            "<h2>这是一个完整的结论句子，带足够的长度。</h2>"
            + _inline_cites("FC-01", "FC-09", "FC-10", "FC-02")
            + _forbidden_block()
        )
        suite = validate_report.validate_report(self._write(doc)[0])
        failed = {c.name for c in suite.checks if not c.passed}
        self.assertIn("inline_citations_three", failed)


class CreatorVideoSectionTests(unittest.TestCase):
    """The creator/video section is a separate population with its own gate."""

    def _run_dir(self) -> Path:
        run = Path(tempfile.mkdtemp())
        base = run / "creator-video"
        (base / "baseline").mkdir(parents=True)
        (base / "features").mkdir(parents=True)
        (base / "relations").mkdir(parents=True)

        def write(path: Path, payload: object) -> None:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        write(
            base / "baseline" / "baseline.json",
            {
                "generated_at": "2026-10-30T00:00:00+00:00",
                "population": {
                    "n": 4,
                    "confidence_counts": {"high": 2, "medium": 2},
                    "relation_type_counts": {
                        "target_exact": 2,
                        "duplicate_listing_anchor": 1,
                        "text_brand_and_category": 1,
                    },
                },
                "video_level": [
                    {"video_id": "v1"},
                    {"video_id": "v2"},
                    {"video_id": "v3"},
                    {"video_id": "v4"},
                ],
                "layers": {
                    "duration_bucket": {
                        "label_zh": "时长档",
                        "dimension_status": "ok",
                        "groups": {
                            "<=15s": {
                                "n": 1,
                                "status": "insufficient_sample",
                                "metrics": None,
                                "lift_vs_complement": None,
                            },
                            "16-30s": {
                                "n": 4,
                                "status": "ok",
                                "metrics": {
                                    "play_count": {"median": 1200},
                                    "interaction_rate": {"median": 0.02},
                                },
                                "lift_vs_complement": {
                                    "complement_n": 0,
                                    "complement_median": 0.0,
                                    "median_multiple": 2.0,
                                    "mann_whitney_u_p_two_sided": 0.5,
                                    "bootstrap_median_ratio_ci95": [0.5, 4.0],
                                },
                            },
                        },
                    },
                    "has_link": {
                        "label_zh": "购买链接",
                        "dimension_status": "ok",
                        "groups": {
                            "true": {
                                "n": 3,
                                "status": "ok",
                                "metrics": {
                                    "play_count": {"median": 1200},
                                    "interaction_rate": {"median": 0.02},
                                },
                                "lift_vs_complement": {
                                    "complement_n": 1,
                                    "complement_median": 0.01,
                                    "median_multiple": 1.5,
                                    "mann_whitney_u_p_two_sided": 0.6,
                                    "bootstrap_median_ratio_ci95": [0.4, 3.0],
                                },
                            }
                        },
                    },
                    "ad_disclosure": {
                        "label_zh": "广告披露",
                        "dimension_status": "ok",
                        "groups": {
                            "true": {
                                "n": 3,
                                "status": "ok",
                                "metrics": {
                                    "play_count": {"median": 1200},
                                    "interaction_rate": {"median": 0.02},
                                },
                                "lift_vs_complement": {
                                    "complement_n": 1,
                                    "complement_median": 0.01,
                                    "median_multiple": 1.2,
                                    "mann_whitney_u_p_two_sided": 0.7,
                                    "bootstrap_median_ratio_ci95": [0.3, 2.0],
                                },
                            }
                        },
                    },
                },
                "overall": {
                    "metrics": {
                        "play_count": {"median": 1200},
                        "interaction_rate": {"median": 0.02},
                    }
                },
                "high_performers": {
                    "count": 1,
                    "threshold_multiple": 2.0,
                    "videos": [
                        {
                            "video_id": "v1",
                            "duration_bucket": "16-30s",
                            "play_count": 1200,
                            "interaction_rate": 0.04,
                            "multiple_vs_duration_bucket_median": 2.0,
                            "relation_confidence": "high",
                            "relation_type": "target_exact",
                            "has_link": "true",
                            "ad_disclosure": "true",
                            "low_denominator_flag": False,
                        }
                    ],
                    "common_features": {
                        "items": [
                            {
                                "field": "ad_disclosure",
                                "value": "true",
                                "count_in_high_performers": 1,
                                "share_in_high_performers": 1.0,
                                "count_in_population": 3,
                                "share_in_population": 0.75,
                            }
                        ]
                    },
                    "low_denominator_sensitivity": {"count": 1},
                },
                "strongest_single_feature": {
                    "top_layer": {
                        "dimension": "duration_bucket",
                        "dimension_label_zh": "时长档",
                        "layer": ">60s",
                        "n": 4,
                        "layer_median_interaction_rate": 0.02,
                        "complement_n": 0,
                        "complement_median_interaction_rate": 0.0,
                        "median_multiple": 2.0,
                        "mann_whitney_u_p_two_sided": 0.5,
                        "bootstrap_median_ratio_ci95": [0.5, 4.0],
                    },
                    "top_layer_relation_type_counts": {"text_brand_and_category": 2},
                    "top_layer_sensitivity": {
                        "exclude_relation_type_text_brand_and_category": {"n": 1},
                        "play_count_floor_5000": {"n": 1},
                    },
                    "verdict": "not_supported",
                },
                "sufficiency_assessment": {"statement": "not supported"},
                "evidence_gaps": ["gap"],
                "caveats": ["caveat"],
            },
        )
        write(
            base / "relations" / "coverage.json",
            {
                "video_inventory": {
                    "unique_videos": 4,
                    "videos_with_detail_snapshot": 3,
                    "videos_without_detail_snapshot": 1,
                    "unique_authors_in_search_sample": 3,
                    "creators_with_profile": 2,
                    "creators_profile_exact": 2,
                    "creators_profile_partial": 0,
                },
                "video_product_target": {
                    "confidence_distribution": {
                        "high": 2,
                        "medium": 2,
                        "low": 1,
                        "none": 0,
                    },
                    "target_coverage": {
                        "exact_product_id_high": 2,
                        "category_anchor_verified": 3,
                    },
                },
            },
        )
        write(
            base / "features" / "feature-distribution.json",
            {
                "field_availability": {
                    "caption": 4,
                    "hashtags": 4,
                    "duration": 4,
                    "product_anchor": 3,
                    "transcript_or_audio": 0,
                },
                "features": {
                    "comparison": {"true": 0, "false": 0, "unknown": 4, "total": 4},
                    "demo": {"true": 0, "false": 0, "unknown": 4, "total": 4},
                    "before_after": {"true": 0, "false": 0, "unknown": 4, "total": 4},
                    "unboxing": {"true": 0, "false": 0, "unknown": 4, "total": 4},
                    "visual_only": {"true": 0, "false": 0, "unknown": 4, "total": 4},
                },
                "duration_buckets": {},
            },
        )
        write(
            base / "relations" / "comment-video-gap.json",
            {
                "relation_count": 0,
                "coverage_rate": 0.0,
                "evidence": {
                    "canonical_tiktok_shop_rows": 10,
                    "raw_review_rows": 10,
                },
            },
        )
        write(base / "collect-summary.json", {"evidence_gaps": []})
        creator_rows = [
            {"video_id": "v1", "creator_id": "c1"},
            {"video_id": "v2", "creator_id": "c1"},
            {"video_id": "v3", "creator_id": "c2"},
            {"video_id": "v4", "creator_id": "c3"},
        ]
        (base / "relations" / "video-creator.jsonl").write_text(
            "\n".join(json.dumps(row) for row in creator_rows) + "\n",
            encoding="utf-8",
        )
        return run

    def test_loader_derives_counts_and_creators(self) -> None:
        summary = creator_video.load_summary(self._run_dir())
        self.assertTrue(summary["available"])
        self.assertEqual(summary["videos_total"], 4)
        self.assertEqual(summary["creators_total"], 3)
        self.assertEqual(summary["baseline_n"], 4)
        self.assertEqual(summary["baseline_creators"], 3)
        self.assertEqual(summary["target_exact_n"], 2)
        self.assertEqual(
            summary["relation_confidence"],
            {"high": 2, "medium": 2, "low": 1, "none": 0},
        )
        self.assertEqual(len(summary["input_sha256"]), 64)

    def test_missing_artifacts_become_one_gap_claim(self) -> None:
        from voc import claims as claims_mod

        summary = creator_video.load_summary(Path(tempfile.mkdtemp()))
        self.assertFalse(summary["available"])
        claims = claims_mod.build_creator_video_claims(summary)
        self.assertEqual([c.claim_id for c in claims], ["C15"])
        self.assertEqual(claims[0].grade, EvidenceGrade.GAP)
        self.assertEqual(claims[0].numbers["creator_video_available"], 0)

    def test_four_claims_and_three_figures_render(self) -> None:
        from voc import claims as claims_mod

        summary = creator_video.load_summary(self._run_dir())
        claims = claims_mod.build_creator_video_claims(summary)
        self.assertEqual([c.claim_id for c in claims], ["C15", "C16", "C17", "C18"])
        self.assertEqual(
            [c.grade for c in claims],
            [EvidenceGrade.CONFIRMED, EvidenceGrade.GAP, EvidenceGrade.CONFIRMED, EvidenceGrade.GAP],
        )
        self.assertIn("support_gate=creator_video_layer_support", claims[1].grade_reason)
        by_id = {c.claim_id: c for c in claims}

        def cb(claim_id: str) -> str:
            return report_mod.claim_block(by_id[claim_id])

        log = report_mod.ExhibitLog()
        html = report_mod.creator_video_section(summary, cb, by_id, log)
        self.assertIn('id="creator-video"', html)
        self.assertEqual(html.count('<article class="claim"'), 4)
        self.assertEqual(html.count("<figure"), 3)
        self.assertIn("EXHIBIT 07", html)
        self.assertIn("EXHIBIT 08", html)
        self.assertIn("EXHIBIT 09", html)
        self.assertEqual(
            log.summary(),
            {"exhibits": 3, "declared": 3, "undeclared": 0, "coverage_pct": 100.0},
        )
        for figure_html in re.findall(r"<figure[^>]*>.*?</figure>", html, re.S):
            for attr in ("data-basis", "data-unit", "data-limit", "data-status"):
                self.assertRegex(figure_html, rf'{attr}="[^"]+"')
            self.assertIn("分母", re.search(r'data-basis="([^"]*)"', figure_html).group(1))
            for cell in ("<b>Basis</b>", "<b>Unit</b>", "<b>Limit</b>", "<b>Status</b>"):
                self.assertIn(cell, figure_html)

    def test_section_lead_claim_is_a_complete_sentence(self) -> None:
        summary = creator_video.load_summary(self._run_dir())
        from voc import claims as claims_mod

        lead = claims_mod.build_creator_video_claims(summary)[1]
        self.assertGreaterEqual(len(lead.headline), 12)
        self.assertIn(lead.headline[-1], "。？！")
        self.assertEqual(lead.grade, EvidenceGrade.GAP)


def _tiktok_occ(eid, text, author="buyer-a", rating=5, minutes=0, **meta):
    base = {
        "product_id": "1729474995478630680",
        "sku_id": "sku-1",
        "variant": "Beige, Medium",
        "rating": rating,
        "verified_purchase": True,
        "incentivized": False,
        "helpful_count": None,
        "region": "US",
        "product_name": "Momcozy Pregnancy Belly Band YB001",
        "reviewer_masked": author,
        "review_time": f"2026-10-0{1 + minutes // 1000}T00:00:00+00:00",
        "text_language": "en",
        "quarantine_reason": None,
    }
    base.update(meta)
    return canonical.Occurrence(
        occurrence_id=f"tiktok:review:{eid}:tiktok_shop_verified",
        source="tiktok_shop",
        kind="review",
        external_id=eid,
        frame="tiktok_shop_verified",
        subreddit="",
        author=author,
        created_utc=1 + minutes,
        url="https://www.tiktok.com/shop/pdp/1729474995478630680",
        title="",
        text=text,
        score=0,
        num_comments=0,
        raw_id="raw-tt",
        source_meta=base,
    )


class TikTokShopTests(unittest.TestCase):
    def test_required_fields_are_normalized(self) -> None:
        from voc import tiktok_shop

        raw = {
            "review_id": "r1",
            "product_id": "1729474995478630680",
            "sku_id": "sku",
            "sku_specification": "Beige, Medium",
            "review_rating": 4,
            "review_text": "Very comfortable and supportive for my back.",
            "review_time": "1783375968420",
            "is_verified_purchase": True,
            "is_incentivized_review": False,
            "review_country": "US",
            "reviewer_name": "A**",
            "product_name": "Momcozy Pregnancy Belly Band YB001",
        }
        row = tiktok_shop.normalize_review(
            raw, run_id="r", captured_at="2026-10-29T00:00:00+00:00", product_id="1729474995478630680"
        )
        required = {
            "review_id",
            "product_id",
            "sku_id",
            "variant",
            "rating",
            "text",
            "text_language",
            "review_time",
            "verified_purchase",
            "incentivized",
            "helpful_count",
            "region",
            "run_id",
            "captured_at",
        }
        self.assertTrue(required <= set(row))
        self.assertEqual(row["text_language"], "en")
        self.assertIsNone(row["helpful_count"])
        self.assertIsNone(row["quarantine_reason"])

    def test_yb003_is_quarantined(self) -> None:
        from voc import tiktok_shop

        reason = tiktok_shop.identity_noise_reason(
            {
                "product_id": "1729474995478630680",
                "sku_specification": "YB003 Oyster Pink, 3XL-PRO",
                "product_name": "Momcozy Pregnancy Belly Band YB001",
            },
            "1729474995478630680",
        )
        self.assertIsNotNone(reason)
        self.assertIn("YB003", reason)
        clean = tiktok_shop.identity_noise_reason(
            {"product_id": "1729474995478630680", "sku_specification": "Beige, Medium"},
            "1729474995478630680",
        )
        self.assertIsNone(clean)

    def test_language_heuristic_separates_spanish(self) -> None:
        from voc import tiktok_shop

        self.assertEqual(tiktok_shop.detect_language(""), "none")
        self.assertEqual(tiktok_shop.detect_language("Great belt"), "en")
        self.assertEqual(tiktok_shop.detect_language("No me gustó no la puedo acomodar bien en mi vientre"), "non_en")

    def test_empty_text_reviews_are_not_merged(self) -> None:
        records, summary = canonical.build_canonical(
            [
                _tiktok_occ("1", "", author="a"),
                _tiktok_occ("2", "", author="b"),
                _tiktok_occ("3", "   ", author="c"),
            ]
        )
        self.assertEqual(len(records), 3)
        self.assertEqual(summary["canonical_by_source"]["tiktok_shop"], 3)

    def test_identical_generic_text_from_two_buyers_stays_two_records(self) -> None:
        text = "Love love love love love love love love love love"
        records, summary = canonical.build_canonical(
            [
                _tiktok_occ("1", text, author="a"),
                _tiktok_occ("2", text, author="b"),
            ]
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(summary["deduction_reasons"]["cross_source_syndicated_duplicate"], 0)

    def test_quarantined_and_out_of_window_are_deducted_with_reasons(self) -> None:
        records, summary = canonical.build_canonical(
            [
                _tiktok_occ("1", "support is great", author="a"),
                _tiktok_occ(
                    "2",
                    "different model",
                    author="b",
                    quarantine_reason="sku_variant_mismatch:YB003 Oyster Pink, 3XL-PRO",
                ),
                _tiktok_occ("3", "old review", author="c", review_time="2026-06-01T00:00:00+00:00"),
            ]
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(summary["deduction_reasons"]["product_mismatch"], 1)
        self.assertEqual(summary["deduction_reasons"]["out_of_window"], 1)
        self.assertEqual(summary["reconciliation"]["deducted"], 2)

    def test_shop_review_is_coded_without_a_product_noun(self) -> None:
        records, _ = canonical.build_canonical([_tiktok_occ("1", "Very comfortable and supportive for my back")])
        coded = coder.code_record(records[0])
        codes = {a.code for a in coded.annotations if a.axis == "aspect"}
        self.assertTrue({"COM.GENERAL", "SUP.BACK"} & codes, codes)

    def test_direction_stats_counts_one_direction_per_record(self) -> None:
        from voc import claims as claims_mod

        records, _ = canonical.build_canonical(
            [
                _tiktok_occ("1", "Great support and comfortable", author="a"),
                _tiktok_occ("2", "Support is good, very comfortable", author="b"),
                _tiktok_occ("3", "No support at all, uncomfortable", author="c"),
                _tiktok_occ("4", "Support is great. It hurts my back", author="d"),
                _tiktok_occ("5", "Nice color", author="e"),
            ]
        )
        coded = coder.code_corpus(records)
        stats = claims_mod.direction_stats(records, coded, claims_mod.SUPPORT_CODES, "tiktok_shop_verified")
        self.assertEqual(stats["same_direction_records"], 2)
        self.assertEqual(stats["opposite_direction_records"], 1)
        self.assertGreaterEqual(stats["mixed_records"], 1)
        self.assertEqual(stats["decisive_records"], 3)
        self.assertEqual(stats["agreement_pct"], 66.7)
        self.assertEqual(stats["dominant_direction"], "positive")

    def test_direction_stats_full_scope_excludes_partial_layer(self) -> None:
        """C13's 32 decisive records: flipping 5 to partial must give 27.

        The fixture reproduces the published C13 split (26 same, 6 opposite)
        so the pooled numbers equal production (32 / 81.2%) without touching
        the frozen corpus.  If ``scope`` were ignored, the full-layer call
        would still return 32 and the assertion would fail.
        """
        from voc import claims as claims_mod

        positives = [
            _tiktok_occ(
                f"scope-pos-{i}",
                "Great support and comfortable for daily wear",
                author=f"buyer-pos-{i}",
            )
            for i in range(26)
        ]
        negatives = [
            _tiktok_occ(
                f"scope-neg-{i}",
                "No support at all and uncomfortable",
                author=f"buyer-neg-{i}",
            )
            for i in range(6)
        ]
        records, _ = canonical.build_canonical(positives + negatives)
        coded = coder.code_corpus(records)

        pooled = claims_mod.direction_stats(
            records, coded, claims_mod.SUPPORT_CODES, "tiktok_shop_verified"
        )
        self.assertEqual(pooled["scope"], "all")
        self.assertEqual(pooled["decisive_records"], 32)
        self.assertEqual(pooled["same_direction_records"], 26)
        self.assertEqual(pooled["opposite_direction_records"], 6)
        self.assertEqual(pooled["agreement_pct"], 81.2)

        # With no partial records yet, the full layer equals the pooled count
        # and the rendered sentence may say "全部属于 full 层".
        full_all = claims_mod.direction_stats(
            records,
            coded,
            claims_mod.SUPPORT_CODES,
            "tiktok_shop_verified",
            scope="full",
        )
        self.assertEqual(full_all["decisive_records"], 32)
        self.assertEqual(full_all["excluded_partial_records"], 0)
        self.assertEqual(
            claims_mod._direction_scope_note(full_all), "全部属于 full 层。"
        )

        partial_ids = set(pooled["same_ids"][:5])
        flipped = [
            dataclasses.replace(rec, experience_scope="partial")
            if rec.canonical_id in partial_ids
            else rec
            for rec in coded
        ]
        full = claims_mod.direction_stats(
            records,
            flipped,
            claims_mod.SUPPORT_CODES,
            "tiktok_shop_verified",
            scope="full",
        )
        self.assertEqual(full["scope"], "full")
        self.assertEqual(full["excluded_partial_records"], 5)
        self.assertEqual(full["excluded_full_records"], 0)
        self.assertEqual(full["excluded_none_records"], 0)
        self.assertEqual(full["decisive_records"], 27)
        self.assertEqual(full["same_direction_records"], 21)
        self.assertEqual(full["opposite_direction_records"], 6)
        self.assertEqual(full["agreement_pct"], 77.8)
        self.assertFalse(partial_ids & set(full["same_ids"]))
        self.assertEqual(
            claims_mod._direction_scope_note(full),
            "统计口径为 full 层，已排除 5 条 partial 层记录。",
        )

        # Symmetry: the partial layer sees exactly the 5 flipped records.
        partial = claims_mod.direction_stats(
            records,
            flipped,
            claims_mod.SUPPORT_CODES,
            "tiktok_shop_verified",
            scope="partial",
        )
        self.assertEqual(partial["decisive_records"], 5)
        self.assertEqual(partial["excluded_full_records"], 27)

        # The legacy pooled call still sees all 32: scope=None is unchanged.
        still_pooled = claims_mod.direction_stats(
            records,
            flipped,
            claims_mod.SUPPORT_CODES,
            "tiktok_shop_verified",
            scope=None,
        )
        self.assertEqual(still_pooled["decisive_records"], 32)
        self.assertEqual(still_pooled["agreement_pct"], 81.2)

    def test_mixed_clause_is_mixed_not_two_votes(self) -> None:
        from voc import claims as claims_mod

        records, _ = canonical.build_canonical(
            [_tiktok_occ("1", "It’s ok not a lot of support very soft wobbly expensive", author="a")]
        )
        coded = coder.code_record(records[0])
        aspects = [a for a in coded.annotations if a.axis == "aspect"]
        self.assertEqual(aspects, [])
        stats = claims_mod.direction_stats(
            records, [coded], claims_mod.SUPPORT_CODES, "tiktok_shop_verified"
        )
        self.assertEqual(stats["mixed_records"], 1)
        self.assertEqual(stats["decisive_records"], 0)
        self.assertEqual(stats["same_direction_records"], 0)
        self.assertEqual(stats["opposite_direction_records"], 0)


class ProductMatchTests(unittest.TestCase):
    """E-merge §2.1 / §4.3: word boundaries and other product lines."""

    def test_husband_is_not_a_band_mention(self) -> None:
        self.assertEqual(
            canonical.classify_product("My husband liked it, but the Momcozy box was plain.")[0],
            "brand_other_product",
        )
        self.assertEqual(
            canonical.classify_product("My husband helped me all week.")[0],
            "irrelevant",
        )

    def test_band_extender_belongs_to_the_bra_not_the_support_band(self) -> None:
        text = (
            "I found the Momcozy nursing/pumping bra with the mesh inset is the most "
            "comfortable, even with a band extender."
        )
        self.assertEqual(canonical.classify_product(text)[0], "brand_other_product")

    def test_same_brand_other_product_lines_are_not_exact(self) -> None:
        cases = {
            "diaper pail": "I LOVE my momcozy diaper pail. My husband likes it too.",
            "nursing bra": "The Momcozy nursing bra is comfortable and the band extender helps.",
            "pregnancy pillow": "I bought a full wrap around momcozy one; we call it the mommy pillow.",
            "breast pump": "My sister gave me a Momcozy pump and my husband bought a second.",
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertEqual(
                    canonical.classify_product(text)[0],
                    "brand_other_product",
                )

    def test_non_momcozy_support_band_is_category_adjacent(self) -> None:
        text = (
            "Also get a belly band (not the Momcozy one, a single band one that "
            "has compression)."
        )
        self.assertEqual(canonical.classify_product(text)[0], "category_adjacent")

    def test_momcozy_support_band_is_exact(self) -> None:
        self.assertEqual(
            canonical.classify_product("I use the Momcozy belly band every day.")[0],
            "exact_current_family",
        )

    def test_override_ledger_rejects_unknown_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overrides.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "voc-product-match-overrides/1",
                        "overrides": {
                            "c-x": {"product_match": "unknown", "reason": "test"}
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                canonical.load_product_match_overrides(path)

    def test_shipped_override_ledger_covers_the_six_contract_records(self) -> None:
        overrides = canonical.load_product_match_overrides(
            ROOT / "product_match_overrides.json"
        )
        self.assertEqual(
            set(overrides),
            {
                "c-1u7ofya",
                "c-19rnylotzfmkh",
                "c-19rg8fid9ublx",
                "c-ph09yrn",
                "c-pdjzq5u",
                "c-pdp6hz8",
            },
        )
        for entry in overrides.values():
            self.assertTrue(entry["reason"])

    def test_emit_aspects_gate_matrix(self) -> None:
        self.assertTrue(coder.emits_aspects("exact_current_family", "full", "text"))
        self.assertTrue(coder.emits_aspects("category_adjacent", "partial", "text"))
        self.assertFalse(coder.emits_aspects("brand_other_product", "full", "text"))
        self.assertFalse(coder.emits_aspects("irrelevant", "partial", "text"))
        self.assertFalse(coder.emits_aspects("exact_current_family", "none", "text"))
        self.assertFalse(coder.emits_aspects("exact_current_family", "full", "   "))

    def test_off_target_record_keeps_scope_but_never_emits_aspects(self) -> None:
        rec = _reddit_rec(
            "c-off-target-eval",
            "",
            "I have the Momcozy nursing bra and it helps with my back pain.",
            product_match="brand_other_product",
        )
        coded = coder.code_record(rec)
        self.assertEqual(coded.experience_scope, "partial")
        self.assertTrue(coded.has_evaluation)
        self.assertFalse(coded.in_cohort)
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])


class LlmConfidenceGateTests(unittest.TestCase):
    """The high-only gate is the published default; dropped aspects stay auditable."""

    TEXT = "Great support and comfortable for daily wear, but the fit runs small."

    def _record_and_row(self):
        records, _ = canonical.build_canonical([_tiktok_occ("confidence-gate", self.TEXT)])
        record = records[0]
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": True,
            "experience_reason": "first_person_use",
            "aspects": [
                {
                    "code": "SUP.GENERAL",
                    "polarity": "positive",
                    "evidence_span": "Great support",
                    "confidence": "high",
                },
                {
                    "code": "COM.GENERAL",
                    "polarity": "positive",
                    "evidence_span": "comfortable for daily wear",
                    "confidence": "medium",
                },
                {
                    "code": "FIT.SIZE_ACCURACY",
                    "polarity": "negative",
                    "evidence_span": "the fit runs small",
                    "confidence": "low",
                },
            ],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "none",
        }
        return record, row

    def _write_artifact(self, directory: str, row: dict) -> Path:
        path = Path(directory) / "ALL.jsonl"
        path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def _code(self, minimum: str):
        record, row = self._record_and_row()
        with tempfile.TemporaryDirectory() as tmp:
            coded_file = self._write_artifact(tmp, row)
            dropped_file = Path(tmp) / "confidence-dropped.jsonl"
            coded = llm_coder.code_corpus(
                [record],
                coded_file=coded_file,
                dropped_file=dropped_file,
                min_confidence=minimum,
            )
            audit_text = dropped_file.read_text(encoding="utf-8")
        return coded[0], audit_text

    def test_default_threshold_is_high_and_env_can_override(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop(llm_coder.CONFIDENCE_ENV, None)
            self.assertEqual(llm_coder.resolve_min_confidence(None), "high")
        with mock.patch.dict(os.environ, {llm_coder.CONFIDENCE_ENV: "all"}):
            self.assertEqual(llm_coder.resolve_min_confidence(None), "all")
        with self.assertRaises(ValueError):
            llm_coder.resolve_min_confidence("bogus")

    def test_high_gate_drops_medium_and_low_into_unknown_and_audit(self) -> None:
        record, _ = self._record_and_row()
        coded, audit_text = self._code("high")
        aspects = [a for a in coded.annotations if a.axis == "aspect"]
        self.assertEqual([(a.code, a.polarity) for a in aspects], [("SUP.GENERAL", "positive")])
        unknown = [
            item
            for item in coded.unknown_aspects
            if item["reason"] == llm_coder.CONFIDENCE_DROP_REASON
        ]
        self.assertEqual({item["code"] for item in unknown}, {"COM.GENERAL", "FIT.SIZE_ACCURACY"})
        for item in unknown:
            self.assertIn(item["confidence"], {"medium", "low"})
            self.assertIn(item["evidence_span"], self.TEXT)
        audit = [json.loads(line) for line in audit_text.splitlines()]
        self.assertEqual(len(audit), 2)
        for item in audit:
            for key in ("canonical_id", "code", "polarity", "confidence", "evidence_span"):
                self.assertIn(key, item)
            self.assertEqual(item["canonical_id"], record.canonical_id)
            self.assertEqual(item["reason"], llm_coder.CONFIDENCE_DROP_REASON)
            self.assertEqual(item["threshold"], "high")
            self.assertIn(item["evidence_span"], self.TEXT)
        self.assertEqual({item["confidence"] for item in audit}, {"medium", "low"})

    def test_all_mode_keeps_every_aspect_and_empties_the_audit(self) -> None:
        coded, audit_text = self._code("all")
        aspects = [a for a in coded.annotations if a.axis == "aspect"]
        self.assertEqual(len(aspects), 3)
        self.assertFalse(
            [u for u in coded.unknown_aspects if u["reason"] == llm_coder.CONFIDENCE_DROP_REASON]
        )
        self.assertEqual(audit_text, "")

    def test_medium_gate_drops_only_low(self) -> None:
        coded, audit_text = self._code("medium")
        aspects = [a for a in coded.annotations if a.axis == "aspect"]
        self.assertEqual(
            [(a.code, a.polarity) for a in aspects],
            [("SUP.GENERAL", "positive"), ("COM.GENERAL", "positive")],
        )
        audit = [json.loads(line) for line in audit_text.splitlines()]
        self.assertEqual([item["confidence"] for item in audit], ["low"])

    def test_llm_coder_marks_help_seeking_evaluation_partial(self) -> None:
        record = _reddit_rec(
            "c-llm-partial",
            "Which belly band is the best?",
            "I use the Momcozy band and the support is great, but I want to compare it.",
            product_match="exact_current_family",
        )
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": True,
            "experience_reason": "first_person_use",
            "aspects": [
                {
                    "code": "SUP.GENERAL",
                    "polarity": "positive",
                    "evidence_span": "the support is great",
                    "confidence": "high",
                }
            ],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "also asks which is best",
        }
        coded = llm_coder.code_record(record, row, min_confidence="high")
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "partial")
        self.assertTrue([a for a in coded.annotations if a.axis == "aspect"])

    def test_llm_coder_past_unnamed_help_seeking_is_false(self) -> None:
        record = _reddit_rec(
            "c-llm-false",
            "Someone help me find a good belly band please!",
            "Are there any good ones? I hated my belly band my first pregnancy because it felt "
            "so uncomfortable.",
            product_match="exact_current_family",
        )
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": True,
            "experience_reason": "first_person_use",
            "aspects": [
                {
                    "code": "COM.GENERAL",
                    "polarity": "negative",
                    "evidence_span": "it felt so uncomfortable",
                    "confidence": "high",
                }
            ],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "previous band",
        }
        audit = {"downgrades": [], "admit_candidates": [], "off_target_evaluations": []}
        coded = llm_coder.code_record(
            record, row, min_confidence="high", audit=audit
        )
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_reason, "help_seeking")
        self.assertEqual(coded.experience_scope, "none")
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])
        self.assertEqual(len(audit["downgrades"]), 1)
        self.assertTrue(audit["downgrades"][0]["aspects_suppressed"])

    def test_frozen_false_with_evaluation_is_an_off_target_evaluation(self) -> None:
        record = _reddit_rec(
            "c-llm-frozen-false",
            "Belly band?",
            "I have the Momcozy band and it helps with my back pain, but I still want to try "
            "other brands.",
            product_match="brand_other_product",
        )
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": False,
            "experience_reason": "product_mismatch",
            "aspects": [
                {
                    "code": "SUP.BACK",
                    "polarity": "positive",
                    "evidence_span": "it helps with my back pain",
                    "confidence": "high",
                }
            ],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "another product",
        }
        audit = {"downgrades": [], "admit_candidates": [], "off_target_evaluations": []}
        coded = llm_coder.code_record(
            record, row, min_confidence="high", audit=audit
        )
        # Off-target evaluation: the scope survives, the aspects do not.
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_reason, "product_mismatch")
        self.assertEqual([a for a in coded.annotations if a.axis == "aspect"], [])
        self.assertEqual(coded.experience_scope, "partial")
        self.assertTrue(coded.has_evaluation)
        self.assertEqual(len(audit["off_target_evaluations"]), 1)
        self.assertEqual(audit["off_target_evaluations"][0]["assessed_scope"], "partial")
        self.assertFalse(audit["off_target_evaluations"][0]["on_topic"])
        self.assertTrue(audit["off_target_evaluations"][0]["aspects_suppressed"])

    def test_frozen_false_full_scope_is_an_admit_candidate(self) -> None:
        record = _reddit_rec(
            "c-llm-frozen-false-full",
            "Belly band?",
            "I have the Momcozy band. The support is great and the fabric is soft.",
            product_match="exact_current_family",
        )
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": False,
            "experience_reason": "other",
            "aspects": [],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "frozen false but substantive evaluation",
        }
        audit = {"downgrades": [], "admit_candidates": [], "off_target_evaluations": []}
        coded = llm_coder.code_record(
            record, row, min_confidence="high", audit=audit
        )
        # The old boolean no longer erases the evaluation; the record passes
        # the E-merge gate and is marked as a human-review candidate.
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "full")
        self.assertEqual(len(audit["admit_candidates"]), 1)
        self.assertTrue(audit["admit_candidates"][0]["in_cohort"])

    def test_frozen_false_without_evaluation_has_no_audit_entry(self) -> None:
        record = _reddit_rec(
            "c-llm-frozen-false-none",
            "Belly band?",
            "I am 20 weeks pregnant and looking for recommendations. Any ideas?",
            product_match="category_adjacent",
        )
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": False,
            "experience_reason": "help_seeking",
            "aspects": [],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "pure question",
        }
        audit = {"downgrades": [], "admit_candidates": [], "off_target_evaluations": []}
        coded = llm_coder.code_record(
            record, row, min_confidence="high", audit=audit
        )
        self.assertFalse(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "none")
        self.assertEqual(audit["downgrades"], [])
        self.assertEqual(audit["admit_candidates"], [])
        self.assertEqual(audit["off_target_evaluations"], [])

    def test_scope_audit_file_is_written_for_frozen_false_rows(self) -> None:
        record = _reddit_rec(
            "c-llm-conflict-file",
            "Belly band?",
            "I have the Momcozy band and it helps with my back pain, but I still want to try "
            "other brands.",
            product_match="brand_other_product",
        )
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": False,
            "experience_reason": "product_mismatch",
            "aspects": [],
            "contexts": [],
            "journey": None,
            "outcome": None,
            "medical_self_report": False,
            "notes": "another product",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            coded_file = self._write_artifact(tmp, row)
            dropped_file = tmp_path / "confidence-dropped.jsonl"
            audit_file = tmp_path / "scope-audit.json"
            llm_coder.code_corpus(
                [record],
                coded_file=coded_file,
                dropped_file=dropped_file,
                scope_audit_file=audit_file,
            )
            payload = json.loads(audit_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "voc-scope-audit/2")
        self.assertEqual(len(payload["off_target_evaluations"]), 1)
        self.assertEqual(
            payload["off_target_evaluations"][0]["canonical_id"],
            record.canonical_id,
        )
        self.assertEqual(payload["in_experience_cohort"], 0)

    def test_llm_coder_relayed_purchase_is_full_but_relayed(self) -> None:
        records, _ = canonical.build_canonical(
            [
                _tiktok_occ(
                    "relay",
                    "Bought for my daughter and she said the material is soft and supportive.",
                )
            ]
        )
        record = records[0]
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": True,
            "experience_reason": "first_person_use",
            "aspects": [
                {
                    "code": "COM.SOFTNESS",
                    "polarity": "positive",
                    "evidence_span": "the material is soft",
                    "confidence": "high",
                }
            ],
            "contexts": [],
            "journey": "purchase",
            "outcome": None,
            "medical_self_report": False,
            "notes": "Bought for daughter; her experience relayed.",
        }
        coded = llm_coder.code_record(record, row, min_confidence="high")
        self.assertTrue(coded.in_cohort)
        self.assertEqual(coded.experience_scope, "full")
        self.assertEqual(coded.experience_source, "relayed")
        self.assertEqual(coded.experience_reason, "relayed_third_party")
        self.assertNotEqual(coded.experience_reason, "first_person_use")

    def test_environment_variable_controls_code_corpus_default(self) -> None:
        record, row = self._record_and_row()
        with tempfile.TemporaryDirectory() as tmp:
            coded_file = self._write_artifact(tmp, row)
            dropped_file = Path(tmp) / "confidence-dropped.jsonl"
            with mock.patch.dict(os.environ, {llm_coder.CONFIDENCE_ENV: "all"}):
                coded = llm_coder.code_corpus(
                    [record], coded_file=coded_file, dropped_file=dropped_file
                )
            self.assertEqual(
                len([a for a in coded[0].annotations if a.axis == "aspect"]), 3
            )

    def test_coder_mode_llm_v2_reads_the_v2_artifact_and_keeps_v1_default(self) -> None:
        from voc import build as build_mod

        record, row = self._record_and_row()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            source_dir = Path(tmp) / "source"
            v1_row = json.loads(json.dumps(row))
            v1_row["aspects"][0]["polarity"] = "positive"
            v1_dir = out_dir / "llm-coding" / "coded"
            v1_dir.mkdir(parents=True)
            (v1_dir / "ALL.jsonl").write_text(
                json.dumps(v1_row, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            v2_row = json.loads(json.dumps(row))
            v2_row["aspects"][0]["polarity"] = "negative"
            v2_row["experience_scope"] = "full"
            v2_row["experience_source"] = "first_person"
            v2_dir = source_dir / "llm-coding-v2" / "coded"
            v2_dir.mkdir(parents=True)
            (v2_dir / "ALL.jsonl").write_text(
                json.dumps(v2_row, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            default_coded, default_id, _ = build_mod._code_corpus(
                [record], out_dir, None, "high", source_dir
            )
            v2_coded, v2_id, _ = build_mod._code_corpus(
                [record], out_dir, "llm-v2", "high", source_dir
            )
        self.assertEqual(default_id, "llm-v1")
        self.assertEqual(v2_id, "llm-v2")
        default_aspects = [a for a in default_coded[0].annotations if a.axis == "aspect"]
        v2_aspects = [a for a in v2_coded[0].annotations if a.axis == "aspect"]
        self.assertEqual(default_aspects[0].polarity, "positive")
        self.assertEqual(v2_aspects[0].polarity, "negative")

    def test_v2_eval_path_is_separate_from_v1(self) -> None:
        run = Path("/tmp/run")
        self.assertEqual(
            llm_coder.eval_result_path(run),
            Path("/tmp/run/llm-coding/eval-result-high.json"),
        )
        self.assertEqual(
            llm_coder.eval_result_path_v2(run),
            Path("/tmp/run/llm-coding-v2/eval-result-high.json"),
        )

    def test_missing_confidence_fails_closed_under_the_gate(self) -> None:
        record, row = self._record_and_row()
        for aspect in row["aspects"]:
            aspect.pop("confidence")
        with self.assertRaises(ValueError):
            llm_coder.code_record(record, row, min_confidence="high")
        # ``all`` is the legacy reproduction mode: it never inspects confidence.
        coded = llm_coder.code_record(record, row, min_confidence="all")
        self.assertEqual(len([a for a in coded.annotations if a.axis == "aspect"]), 3)


class QualifiedPolarityTests(unittest.TestCase):
    """Decision C: qualified_positive is a first-class value, symmetric to qualified_negative."""

    def _code(self, eid: str, text: str, polarity: str):
        records, _ = canonical.build_canonical([_tiktok_occ(eid, text, author=eid)])
        record = records[0]
        row = {
            "canonical_id": record.canonical_id,
            "is_product_experience": True,
            "experience_reason": "first_person_use",
            "aspects": [
                {
                    "code": "SUP.GENERAL",
                    "polarity": polarity,
                    "evidence_span": text,
                    "confidence": "high",
                }
            ],
            "contexts": [],
            "journey": "repeat_use",
            "outcome": "relief",
            "medical_self_report": False,
            "notes": "none",
        }
        return record, llm_coder.code_record(record, row, min_confidence="high")

    def test_taxonomy_defines_both_qualified_values_as_mirror_images(self) -> None:
        tax = taxonomy_dict()
        self.assertIn("qualified_positive", tax["polarity_enum"])
        self.assertIn("qualified_negative", tax["polarity_enum"])
        rules = " ".join(tax["rules"])
        self.assertIn("qualified_positive", rules)
        self.assertIn("qualified_negative", rules)
        self.assertIn("positive family", rules)
        self.assertIn("negative family", rules)

    def test_qualified_polarities_are_annotations_in_their_own_family(self) -> None:
        from voc import claims as claims_mod

        pos_rec, pos = self._code("qp-1", "Great support all day", "qualified_positive")
        neg_rec, neg = self._code("qn-1", "Weak support all day", "qualified_negative")
        for coded, expected in ((pos, "qualified_positive"), (neg, "qualified_negative")):
            aspects = [a for a in coded.annotations if a.axis == "aspect"]
            self.assertEqual([(a.code, a.polarity) for a in aspects], [("SUP.GENERAL", expected)])
            self.assertFalse(
                [u for u in coded.unknown_aspects if u["code"] == "SUP.GENERAL"],
                "qualified_* must not be treated as mixed/unknown abstention",
            )
        stats = claims_mod.direction_stats(
            [pos_rec, neg_rec], [pos, neg], claims_mod.SUPPORT_CODES, "tiktok_shop_verified"
        )
        self.assertEqual(stats["same_direction_records"], 1)
        self.assertEqual(stats["opposite_direction_records"], 1)
        self.assertEqual(stats["decisive_records"], 2)
        counts = metrics.aspect_polarity_counts([pos, neg])
        self.assertEqual(counts["SUP.GENERAL"], {"positive": 1, "negative": 1})


if __name__ == "__main__":
    unittest.main()

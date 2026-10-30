"""Rule-based coding: free text -> aspect / polarity / severity / context.

Implements SOP skill ``voc-coding-calibration`` (G7) partially.  The rule
coder is deterministic and replayable, so every annotation can be audited.
The calibration half is NOT implemented: ``agreement_report`` raises until a
second independent human coder exists, and the report therefore keeps G7
BLOCKED and metric rows at zero.

The coder interface is intentionally small (``Coder.code_record``) so a model
coder can replace ``RuleCoder`` later without touching counting, evidence or
report assembly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from .counting import CanonicalRecord

TAXONOMY_VERSION = "VOC-BAND-v1.0"

NEGATIVE_CUES = (
    "uncomfortable",
    "hurt",
    "hurts",
    "hurting",
    "pain",
    "painful",
    "ache",
    "aches",
    "slipped",
    "slips",
    "slip",
    "slides",
    "slid",
    "rolled down",
    "rolls down",
    "roll down",
    "bunch",
    "bunches",
    "dig",
    "digs",
    "digging",
    "cut into",
    "cuts into",
    "chafe",
    "chafed",
    "chafing",
    "rash",
    "itchy",
    "itch",
    "sweaty",
    "too hot",
    "too tight",
    "too loose",
    "too small",
    "too big",
    "too large",
    "too short",
    "too long",
    "useless",
    "waste",
    "waste of money",
    "disappointed",
    "disappointing",
    "not worth",
    "overpriced",
    "expensive",
    "cheap",
    "returned",
    "returning",
    "refund",
    "didn't work",
    "doesn't work",
    "didn't help",
    "doesn't help",
    "no difference",
    "no support",
    "not supportive",
    "lack of support",
    "fell apart",
    "wore out",
    "stretched out",
    "lost elasticity",
    "regret",
    "hate",
    "bad",
    "poor",
    "annoying",
)

POSITIVE_CUES = (
    "comfortable",
    "comfy",
    "soft",
    "cozy",
    "supportive",
    "support",
    "supports",
    "helped",
    "helps",
    "relief",
    "relieved",
    "relieves",
    "great",
    "love",
    "loved",
    "perfect",
    "amazing",
    "works",
    "worked",
    "worth",
    "recommend",
    "recommended",
    "stays in place",
    "stayed in place",
    "doesn't slip",
    "didn't slip",
    "breathable",
    "invisible",
    "discreet",
    "durable",
    "cute",
    "favorite",
    "saved",
)

QUALIFIERS = ("sometimes", "a bit", "a little", "kind of", "mostly", "somewhat", "occasionally", "slight", "slightly")
MINOR_CUES = QUALIFIERS + ("minor", "mild", "small amount")
SEVERE_CUES = (
    "severe",
    "severely",
    "extreme",
    "extremely",
    "unbearable",
    "terrible",
    "horrible",
    "awful",
    "worst",
    "so much",
    "very painful",
    "constant",
    "debilitating",
)
NEGATORS = ("not", "n't", "no", "never", "hardly", "without", "isn't", "wasn't", "doesn't", "didn't", "don't")

CLAUSE_SPLIT = re.compile(r"[.!?;\n]|,\s*(?:but|however|although|though)\s+", re.I)
ANCHOR_RE = re.compile(r"\b(band|belt|strap|velcro|wrap|momcozy|maternity|ergonest|cozysupport|garment)\b", re.I)
PRONOUN_RE = re.compile(r"\b(it|this|that|they|them|its|one)\b", re.I)

JOURNEY_ORDER = [
    "JNY.RETURN",
    "JNY.CARE",
    "JNY.FIRST_FITTING",
    "JNY.SIZE_SELECTION",
    "JNY.RECOMMEND",
    "JNY.CONSIDERATION",
    "JNY.USE",
]
OUTCOME_ORDER = [
    "OUT.RETURN_INTENT",
    "OUT.REGRET",
    "OUT.NO_BENEFIT",
    "OUT.LIMITED_USE",
    "OUT.RELIEF",
    "OUT.ACTIVITY_ENABLED",
    "OUT.RECOMMEND",
    "OUT.CONTINUED_USE",
]

ASPECT_FAMILY = {
    "SUP": "support",
    "SAF": "support",
    "FIT": "fit",
    "ADJ": "fit",
    "STB": "fit",
    "ACT": "fit",
    "USE": "fit",
    "COM": "wearability",
    "APP": "wearability",
    "MAT": "wearability",
    "GEN": "wearability",
    "VAL": "value",
    "FUL": "value",
    "CX": "value",
}

MIXED_FAMILY = {
    "SUP": "support",
    "SAF": "support",
    "FIT": "fit",
    "ADJ": "fit",
    "STB": "fit",
    "ACT": "fit",
    "USE": "fit",
    "COM": "comfort",
    "APP": "comfort",
    "MAT": "comfort",
    "GEN": "comfort",
    "VAL": "value",
    "FUL": "value",
    "CX": "value",
}


def clauses(text: str) -> list[str]:
    parts = [p.strip() for p in CLAUSE_SPLIT.split(text or "") if p.strip()]
    return parts or [text or ""]


def anchored_clauses(text: str) -> list[str]:
    parts = clauses(text)
    anchored: list[str] = []
    last_anchor = -99
    for index, clause in enumerate(parts):
        if ANCHOR_RE.search(clause):
            last_anchor = index
        if ANCHOR_RE.search(clause) or (PRONOUN_RE.search(clause) and index - last_anchor <= 1):
            anchored.append(clause)
    return anchored


def has_negation(clause: str, start: int) -> bool:
    window = clause[max(0, start - 28) : start].lower()
    return any(f" {neg} " in f" {window} " for neg in NEGATORS)


def polarity_of(clause: str) -> str:
    low = clause.lower()
    if clause.strip().endswith("?") or any(
        key in low
        for key in ("any suggestions", "recommendations", "which one", "looking for", "should i", "any advice")
    ):
        return "unknown"
    negative = any(cue in low for cue in NEGATIVE_CUES)
    positive = any(cue in low for cue in POSITIVE_CUES)

    # "not comfortable" must read as negative; "doesn't slip" as positive.
    for cue in POSITIVE_CUES:
        match = re.search(cue, low)
        if match and has_negation(low, match.start()):
            negative, positive = True, False
            break
    for cue in NEGATIVE_CUES:
        match = re.search(cue, low)
        if match and has_negation(low, match.start()):
            negative, positive = False, True
            break

    if negative and positive:
        return "mixed"
    if negative:
        return "qualified_negative" if any(q in low for q in QUALIFIERS) else "negative"
    if positive:
        return "qualified_positive" if any(q in low for q in QUALIFIERS) else "positive"
    return "unknown"


def severity_of(clause: str, polarity: str) -> str:
    if polarity == "unknown":
        return "unknown"
    low = clause.lower()
    if any(cue in low for cue in SEVERE_CUES):
        return "severe"
    if any(cue in low for cue in MINOR_CUES):
        return "minor"
    return "moderate"


@dataclass
class Annotation:
    canonical_id: str
    axis: str
    code: str
    polarity: str
    severity: str
    evidence_span: str
    rule_id: str
    taxonomy_version: str = TAXONOMY_VERSION
    coder_id: str = "rule-v1"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CodedRecord:
    canonical_id: str
    annotations: list[Annotation] = field(default_factory=list)
    unknown_aspects: list[str] = field(default_factory=list)
    medical_flags: list[str] = field(default_factory=list)
    journey_stage: str = "unknown"
    outcome: str = "OUT.UNKNOWN"
    gap: str = "unknown"
    claim_relation: str = "not_assessed_at_G7"
    codes_hit: list[str] = field(default_factory=list)

    @property
    def annotation_count(self) -> int:
        return len(self.annotations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "annotations": [a.to_dict() for a in self.annotations],
            "unknown_aspects": self.unknown_aspects,
            "medical_flags": self.medical_flags,
            "journey_stage": self.journey_stage,
            "outcome": self.outcome,
            "gap": self.gap,
            "claim_relation": self.claim_relation,
            "codes_hit": self.codes_hit,
        }


class Coder(Protocol):
    name: str

    def code_record(self, record: CanonicalRecord) -> CodedRecord:
        ...


def load_taxonomy(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    codes = payload.get("codes")
    if not isinstance(codes, list) or not codes:
        raise ValueError(f"taxonomy has no codes: {path}")
    for code in codes:
        if not all(key in code for key in ("code", "axis", "label", "definition", "include", "exclude")):
            raise ValueError(f"taxonomy code missing required fields: {code.get('code')}")
        if "lexicon" not in code:
            code["lexicon"] = []
    return payload


def taxonomy_by_axis(taxonomy: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for code in taxonomy["codes"]:
        out.setdefault(code["axis"], []).append(code)
    return out


def _match_codes(text: str, codes: Iterable[dict[str, Any]], *, anchored_only: bool = False) -> list[tuple[dict[str, Any], str]]:
    pool = anchored_clauses(text) if anchored_only else clauses(text)
    hits: list[tuple[dict[str, Any], str]] = []
    for code in codes:
        patterns = code.get("lexicon") or []
        for clause in pool:
            low = clause.lower()
            for pattern in patterns:
                try:
                    if re.search(pattern, low):
                        hits.append((code, clause))
                        break
                except re.error:
                    continue
    return hits


class RuleCoder:
    """Deterministic lexicon coder.  One annotation per code/polarity per record."""

    name = "rule-v1"

    def __init__(self, taxonomy: dict[str, Any]):
        self.taxonomy = taxonomy
        self.by_axis = taxonomy_by_axis(taxonomy)
        self.label_by_code = {c["code"]: c.get("label", c["code"]) for c in taxonomy["codes"]}

    def code_record(self, record: CanonicalRecord) -> CodedRecord:
        text = f"{record.title}. {record.text}".strip()
        out = CodedRecord(canonical_id=record.canonical_id)
        if record.product_match in {"irrelevant", "brand_other_product"}:
            return out

        aspect_hits: dict[tuple[str, str], tuple[str, str]] = {}
        for code, clause in _match_codes(text, self.by_axis.get("aspect", []), anchored_only=True):
            polarity = polarity_of(clause)
            if polarity == "unknown":
                if code["code"] not in out.unknown_aspects:
                    out.unknown_aspects.append(code["code"])
                continue
            if polarity == "mixed":
                for side in ("positive", "negative"):
                    aspect_hits.setdefault((code["code"], side), (clause, "mixed"))
            else:
                aspect_hits.setdefault((code["code"], polarity), (clause, "single"))
        for (code, polarity), (span, rule_id) in sorted(aspect_hits.items()):
            out.annotations.append(
                Annotation(
                    canonical_id=record.canonical_id,
                    axis="aspect",
                    code=code,
                    polarity=polarity,
                    severity=severity_of(span, polarity),
                    evidence_span=span[:180],
                    rule_id=rule_id,
                )
            )

        for axis, anchored in (("context", False), ("journey", True), ("outcome", True), ("gap", True), ("medical", True)):
            seen: set[str] = set()
            for code, clause in _match_codes(text, self.by_axis.get(axis, []), anchored_only=anchored):
                if code["code"] in seen:
                    continue
                seen.add(code["code"])
                out.annotations.append(
                    Annotation(
                        canonical_id=record.canonical_id,
                        axis=axis,
                        code=code["code"],
                        polarity="present",
                        severity="unknown",
                        evidence_span=clause[:180],
                        rule_id="lexicon",
                    )
                )
                if axis == "medical":
                    out.medical_flags.append(code["code"])

        journey_codes = {a.code for a in out.annotations if a.axis == "journey"}
        out.journey_stage = next((code for code in JOURNEY_ORDER if code in journey_codes), "unknown")
        outcome_codes = {a.code for a in out.annotations if a.axis == "outcome"}
        out.outcome = next((code for code in OUTCOME_ORDER if code in outcome_codes), "OUT.UNKNOWN")
        gap_codes = {a.code for a in out.annotations if a.axis == "gap"}
        if "GAP.FIT_MISMATCH" in gap_codes:
            out.gap = "fit_mismatch"
        elif "GAP.SUPPORT_MISMATCH" in gap_codes:
            out.gap = "support_mismatch"
        elif "GAP.VALUE_MISMATCH" in gap_codes:
            out.gap = "value_mismatch"
        elif "GAP.MATCHED" in gap_codes:
            out.gap = "matched"
        out.codes_hit = sorted({a.code for a in out.annotations})
        if out.medical_flags:
            out.claim_relation = "review_required"
        return out

    def label(self, code: str) -> str:
        return self.label_by_code.get(code, code)


class ModelCoder:
    """Placeholder for a future model-backed coder.

    It deliberately raises instead of silently returning an LLM guess: a model
    coder needs its own calibration and agreement run before it may produce
    report evidence.
    """

    name = "model-unconfigured"

    def code_record(self, record: CanonicalRecord) -> CodedRecord:
        raise RuntimeError("model coder is not configured; use RuleCoder")


def code_corpus(records: list[CanonicalRecord], taxonomy: dict[str, Any], coder: Coder | None = None) -> list[CodedRecord]:
    active = coder or RuleCoder(taxonomy)
    return [active.code_record(record) for record in records]


def agreement_report(coded_a: list[CodedRecord], coded_b: list[CodedRecord], field: str = "aspect_code") -> dict[str, Any]:
    raise RuntimeError(
        "G7 requires two independent human coders; no second coder artifact exists in this run"
    )


def family_of(code: str, *, mixed: bool = False) -> str:
    prefix = code.split(".")[0]
    table = MIXED_FAMILY if mixed else ASPECT_FAMILY
    return table.get(prefix, "wearability")


def aggregate(coded: list[CodedRecord]) -> dict[str, Any]:
    annotation_totals: dict[str, int] = {}
    aspect_polarity: dict[str, int] = {}
    aspect_code: dict[str, int] = {}
    context_code: dict[str, int] = {}
    journey_stage: dict[str, int] = {}
    outcome: dict[str, int] = {}
    gap: dict[str, int] = {}
    medical: dict[str, int] = {}
    severity: dict[str, int] = {}
    records_by_code: dict[str, set[str]] = {}
    aspect_positive_records: set[str] = set()
    comfort_positive_records: set[str] = set()
    friction_negative_records: set[str] = set()
    both_records: set[str] = set()
    mixed_pairs: list[dict[str, Any]] = []

    for record in coded:
        per_record_comfort = False
        per_record_friction = False
        record_positive_codes: set[str] = set()
        record_negative_codes: set[str] = set()
        for ann in record.annotations:
            annotation_totals[ann.axis] = annotation_totals.get(ann.axis, 0) + 1
            severity[ann.severity] = severity.get(ann.severity, 0) + 1
            records_by_code.setdefault(ann.code, set()).add(record.canonical_id)
            if ann.axis == "aspect":
                key = f"{ann.code}|{ann.polarity}"
                aspect_polarity[key] = aspect_polarity.get(key, 0) + 1
                aspect_code[ann.code] = aspect_code.get(ann.code, 0) + 1
                if ann.polarity.startswith("positive"):
                    aspect_positive_records.add(record.canonical_id)
                    record_positive_codes.add(ann.code)
                    if ann.code.startswith(("COM.", "APP.")):
                        per_record_comfort = True
                if ann.polarity.startswith("negative"):
                    record_negative_codes.add(ann.code)
                    if ann.code.startswith(("SUP.", "FIT.", "STB.")):
                        per_record_friction = True
            elif ann.axis == "context":
                context_code[ann.code] = context_code.get(ann.code, 0) + 1
            elif ann.axis == "journey":
                journey_stage[ann.code] = journey_stage.get(ann.code, 0) + 1
            elif ann.axis == "outcome":
                outcome[ann.code] = outcome.get(ann.code, 0) + 1
            elif ann.axis == "gap":
                gap[ann.code] = gap.get(ann.code, 0) + 1
            elif ann.axis == "medical":
                medical[ann.code] = medical.get(ann.code, 0) + 1
        if per_record_comfort:
            comfort_positive_records.add(record.canonical_id)
        if per_record_friction:
            friction_negative_records.add(record.canonical_id)
        if per_record_comfort and per_record_friction:
            both_records.add(record.canonical_id)
            positive_codes = sorted(record_positive_codes)
            negative_codes = sorted(record_negative_codes)
            positive_families = sorted({family_of(code, mixed=True) for code in positive_codes})
            core_negative = [code for code in negative_codes if code.startswith(("SUP.", "FIT.", "STB."))]
            negative_families = sorted({family_of(code, mixed=True) for code in (core_negative or negative_codes)})
            mixed_pairs.append(
                {
                    "canonical_id": record.canonical_id,
                    "positive_family": "comfort" if "comfort" in positive_families else (positive_families[0] if positive_families else "comfort"),
                    "negative_family": negative_families[0] if negative_families else "support",
                    "positive_codes": positive_codes,
                    "negative_codes": negative_codes,
                }
            )
    return {
        "annotation_totals": annotation_totals,
        "aspect_polarity_counts": aspect_polarity,
        "aspect_code_counts": aspect_code,
        "context_code_counts": context_code,
        "journey_stage_counts": journey_stage,
        "outcome_counts": outcome,
        "gap_counts": gap,
        "medical_self_report_code_counts": medical,
        "severity_counts": severity,
        "records_by_code": {code: sorted(ids) for code, ids in records_by_code.items()},
        "aspect_positive_records": sorted(aspect_positive_records),
        "comfort_positive_records": sorted(comfort_positive_records),
        "friction_negative_records": sorted(friction_negative_records),
        "both_records": sorted(both_records),
        "mixed_pairs": mixed_pairs,
    }


def folded_aspect_counts(aggregate_result: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Fold qualified_* into positive/negative, exactly as key_aspects requires."""
    out: dict[str, dict[str, int]] = {}
    for key, value in aggregate_result["aspect_polarity_counts"].items():
        code, polarity = key.split("|", 1)
        item = out.setdefault(code, {"positive": 0, "negative": 0})
        if polarity in {"positive", "qualified_positive"}:
            item["positive"] += value
        elif polarity in {"negative", "qualified_negative"}:
            item["negative"] += value
        elif polarity == "mixed":
            item["positive"] += value
            item["negative"] += value
    return out


def key_aspects(
    aggregate_result: dict[str, Any],
    taxonomy: dict[str, Any],
    *,
    limit: int = 12,
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    labels = {c["code"]: c.get("label", c["code"]) for c in taxonomy["codes"]}
    folded = folded_aspect_counts(aggregate_result)
    ranked = sorted(folded.items(), key=lambda item: (-(item[1]["positive"] + item[1]["negative"]), item[0]))
    out = []
    for code, counts in ranked[:limit]:
        total = counts["positive"] + counts["negative"]
        out.append(
            {
                "code": code,
                "label": labels.get(code, code),
                "family": family_of(code),
                "positive": {
                    "value": counts["positive"],
                    "unit": "annotation",
                    "basis": f"positive + qualified_positive annotations for {code}",
                    "denominator": None,
                    "multi_label": True,
                    "partition": False,
                    "as_of": as_of or "2026-10-29",
                    "source_path": f"metric-summary.json#/key_aspects/{code}",
                },
                "negative": {
                    "value": counts["negative"],
                    "unit": "annotation",
                    "basis": f"negative + qualified_negative annotations for {code}",
                    "denominator": None,
                    "multi_label": True,
                    "partition": False,
                    "as_of": as_of or "2026-10-29",
                    "source_path": f"metric-summary.json#/key_aspects/{code}",
                },
                "derived_from": "coverage.aspect_polarity_counts",
                "basis": f"{total} aspect annotations for {code}; folded qualified_* into the matching sign",
            }
        )
    return out


def frame_lenses(
    coded: list[CodedRecord],
    records: list[CanonicalRecord],
    taxonomy: dict[str, Any],
    frame_counts: dict[str, int],
) -> list[dict[str, Any]]:
    labels = {c["code"]: c.get("label", c["code"]) for c in taxonomy["codes"]}
    by_id = {record.canonical_id: record for record in records}
    lenses = []
    for frame, name in (
        ("natural", "自然镜头"),
        ("diagnostic", "诊断镜头"),
        ("qualitative_seed", "定性种子镜头"),
    ):
        positive: dict[str, int] = {}
        negative: dict[str, int] = {}
        for coded_record in coded:
            record = by_id.get(coded_record.canonical_id)
            if not record or frame not in record.frames:
                continue
            for ann in coded_record.annotations:
                if ann.axis != "aspect":
                    continue
                if ann.polarity.startswith("positive"):
                    positive[ann.code] = positive.get(ann.code, 0) + 1
                elif ann.polarity.startswith("negative"):
                    negative[ann.code] = negative.get(ann.code, 0) + 1
        love = [
            {"label": labels.get(code, code), "count": count, "codes": [code]}
            for code, count in sorted(positive.items(), key=lambda item: (-item[1], item[0]))[:3]
        ]
        complaint = [
            {"label": labels.get(code, code), "count": count, "codes": [code]}
            for code, count in sorted(negative.items(), key=lambda item: (-item[1], item[0]))[:3]
        ]
        lenses.append(
            {
                "id": frame,
                "name": name,
                "n": {
                    "value": frame_counts.get(frame, 0),
                    "unit": "canonical_record",
                    "basis": f"canonical records with {frame} frame membership",
                    "denominator": None,
                    "multi_label": False,
                    "partition": False,
                    "as_of": "2026-10-29",
                    "source_path": f"corpus-summary.json#/frame_counts/{frame}",
                },
                "note": "frames 可重叠；n 之和可以大于 248 个 canonical records；禁止跨 frame 比较百分比。",
                "love": love,
                "complaint": complaint,
                "basis": f"{frame} frame; annotation hits are multi-label and not people",
            }
        )
    return lenses


def journey_rollups(coded: list[CodedRecord], canonical_total: int) -> dict[str, Any]:
    stage_counts: dict[str, int] = {}
    independent: dict[str, int] = {code: 0 for code in JOURNEY_ORDER}
    for record in coded:
        if record.journey_stage != "unknown":
            independent[record.journey_stage] = independent.get(record.journey_stage, 0) + 1
        for ann in record.annotations:
            if ann.axis == "journey":
                stage_counts[ann.code] = stage_counts.get(ann.code, 0) + 1
    independent["unknown"] = canonical_total - sum(independent.values())
    gap_counts: dict[str, int] = {}
    for record in coded:
        key = record.gap
        gap_counts[key] = gap_counts.get(key, 0) + 1
    gap_counts["unknown"] = gap_counts.get("unknown", 0) + (canonical_total - len(coded))
    return {
        "stage_counts": stage_counts,
        "independent_unit_counts": independent,
        "gap_counts": gap_counts,
    }

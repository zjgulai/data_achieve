#!/usr/bin/env python3
"""Check whether the v1.1 SUP include/exclude rules are mutually exclusive.

Decision B keeps four SUP codes but rewrites their boundaries and adds a
mandatory priority order.  This script measures the boundary on the real
corpus instead of trusting the prose:

* Unit of analysis is one clause (``voc.coder.clause_spans``) from
  ``canonical-records.jsonl``.  A clause is a candidate when any v1.0 or
  v1.1 SUP lexicon matches it.
* v1.0 had no priority rule, so every clause with two or more matching SUP
  codes is ambiguous by construction.
* v1.1 keeps the same lexical overlap in some clauses.  The priority order in
  ``voc.taxonomy.SUP_RESOLUTION_ORDER`` must reduce every same-aspect overlap
  to exactly one code.  Two coordinated predicates in one clause (for example
  "holding up her bundle and easing her pelvic pain") are separate aspects and
  are counted separately, not as ambiguity.

Run from the repository root:

    python3 tools/check_support_exclusivity.py
    python3 tools/check_support_exclusivity.py --json-out /tmp/sup-check.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

VOC_ROOT = Path(__file__).resolve().parents[1]
if str(VOC_ROOT) not in sys.path:
    sys.path.insert(0, str(VOC_ROOT))

from voc.coder import _lexicon_pattern, clause_spans  # noqa: E402
from voc.taxonomy import ASPECTS, SUP_RESOLUTION_ORDER, TAXONOMY_VERSION  # noqa: E402

DEFAULT_CANONICAL = (
    VOC_ROOT / "artifacts" / "run-20261029" / "canonical-records.jsonl"
)
DEFAULT_CODED = (
    VOC_ROOT / "artifacts" / "run-20261029" / "llm-coding" / "coded" / "ALL.jsonl"
)

# v1.0 SUP lexicons, copied verbatim from the frozen module before decision B.
OLD_LEXICONS: dict[str, tuple[str, ...]] = {
    "SUP.GENERAL": (
        "support",
        "supportive",
        r"holds? (?:my |the )?belly",
        "belly support",
        "lift",
    ),
    "SUP.BACK": ("back pain", "lower back", "back support", "my back"),
    "SUP.PRESSURE_OFFLOAD": (
        "pressure off",
        r"off my (?:back|hips|pelvis)",
        r"take (?:the )?weight",
        "relieve pressure",
        "relief",
    ),
    "SUP.BELLY_LIFT": (
        r"lift (?:my |the )?belly",
        r"hold (?:up )?(?:my |the )?bump",
        "belly lift",
    ),
}

SUP_CODES = [code for code in ASPECTS if code.code.startswith("SUP.")]
NEW_LEXICONS: dict[str, tuple[str, ...]] = {
    code.code: code.lexicon for code in SUP_CODES
}

# A non-product subject that supplies the relief or offload.  Decision B §3.3
# says the cue must be attributable to the support band; a swimming pool, bath,
# husband or ice pack does not count.
NON_PRODUCT_SUBJECT_RE = re.compile(
    r"\b(?:swimming pool|pool|warm salt baths?|bath|ice pack|heated blanket|"
    r"tylenol|husband|wife|pregnancy ball|exercise ball)\b",
    re.I,
)
PRODUCT_NOUN_RE = re.compile(
    r"\b(?:belly bands?|bands?|belts?|straps?|waistbands?|support belts?|"
    r"product|item|momcozy|ergonest)\b",
    re.I,
)

# Independent predicates inside one clause, e.g. "holding up her bundle and
# easing her pelvic pain".  ``support`` is excluded because it is often a noun
# ("back support"), which would split one aspect into two.
ACTION_RE = re.compile(
    r"\b(?:lift|hold|eas\w*|reliev|help|take|reduce|lessen|gave|gives|give|"
    r"provide|provides|soothe|alleviate|carry)\w*",
    re.I,
)


def _hits(text: str, lexicons: dict[str, tuple[str, ...]]) -> dict[str, list[tuple[int, int, str]]]:
    out: dict[str, list[tuple[int, int, str]]] = {}
    for code, patterns in lexicons.items():
        spans = []
        for pattern in patterns:
            for match in re.finditer(_lexicon_pattern(pattern), text, re.I):
                spans.append((match.start(), match.end(), match.group(0)))
        if spans:
            out[code] = spans
    return out


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(_lexicon_pattern(pattern), text, re.I) for pattern in patterns)


def _resolve(text: str) -> tuple[str | None, int | None]:
    """Apply the v1.1 priority order; first matching step wins."""
    for rule in SUP_RESOLUTION_ORDER:
        if _matches_any(text, rule["lexicon"]):
            return rule["code"], int(rule["step"])
    return None, None


def _attribution_excluded(text: str) -> bool:
    """True when the cue's source is a non-product object or behaviour."""
    return bool(NON_PRODUCT_SUBJECT_RE.search(text)) and not PRODUCT_NOUN_RE.search(text)


def _coordinated_aspects(
    text: str, lexicons: dict[str, tuple[str, ...]]
) -> list[dict[str, object]]:
    """Return independent predicate chunks if the clause has two aspects."""
    chunks = re.split(r"\band\b", text)
    if len(chunks) < 2:
        return []
    found: list[dict[str, object]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or not ACTION_RE.search(chunk):
            continue
        codes = sorted(_hits(chunk, lexicons))
        if codes:
            found.append({"chunk": chunk, "codes": codes})
    return found if len(found) >= 2 else []


def _pair_counts(cases: list[dict[str, list[tuple[int, int, str]]]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for hits in cases:
        for left, right in itertools.combinations(sorted(hits), 2):
            counts[f"{left} x {right}"] += 1
    return dict(sorted(counts.items()))


def _record_text(record: dict) -> str:
    title = (record.get("title") or "").strip()
    body = (record.get("text") or "").strip()
    text = f"{title}. {body}" if title else body
    # Service praise is not product support.  The rule coder applies the same
    # substitution before matching; keep the checker on the same footing.
    return re.sub(r"\bcustomer support\b", "customer service", text, flags=re.I)


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _find_clause(text: str, needle: str) -> str | None:
    low = text.lower()
    position = low.find(needle.lower())
    if position < 0:
        return None
    for span in clause_spans(text):
        if span.start <= position < span.end:
            return span.clause
    return None


CASES = [
    ("1", "c-1mdp0wu", "the weight off my pelvis and lower back is incredible", "SUP.PRESSURE_OFFLOAD"),
    ("2", "c-7659507976003651341", "excellent support for my lower back", "SUP.BACK"),
    ("2b", "c-7659507976003651341", "offers noticeable relief", "SUP.PRESSURE_OFFLOAD"),
    ("3", "c-7690266633513518861", "helped so much with hip and lower back pain", "SUP.BACK"),
    ("4", "c-7658003601176119053", "Almost fully takes away the sciatica", "SUP.PRESSURE_OFFLOAD"),
    ("5", "c-7665021905910384398", "helps relieve the pain", "SUP.PRESSURE_OFFLOAD"),
    ("6", "c-7667963659528931085", "did not find that it provided optimal relief", "SUP.PRESSURE_OFFLOAD"),
    ("7", "c-7671622567216498445", "saving my back", "SUP.BACK"),
    ("7b", "c-7671622567216498445", "lift and support the baby", "SUP.BELLY_LIFT"),
    ("8", "c-7674647274773759757", "it takes the weight of the baby", "SUP.PRESSURE_OFFLOAD"),
    ("8b", "c-7674647274773759757", "Very good support system", "SUP.GENERAL"),
    ("9", "c-7667984767955748622", "it feels like a weight is lifted", "SUP.PRESSURE_OFFLOAD"),
    ("9b", "c-7667984767955748622", "lifts that big belly effortlessly", "SUP.BELLY_LIFT"),
    ("9c", "c-7667984767955748622", "would support my big belly but it does", "SUP.GENERAL"),
    ("10", "c-7677755508020528910", "very comfortable and weightless but supports the belly just enough", "SUP.GENERAL"),
    ("11", "c-19rjykcrivso1", "take the extra weight off my joints", None),
    ("12", "c-1svdohq", "takes pressure off my pelvis/lower back", None),
]


def _same_clause(left: dict, right: dict) -> bool:
    return (
        left["canonical_id"] == right["canonical_id"]
        and left["clause"] == right["clause"]
    )


def _outcome_for(row: dict, allowed: list[dict], resolved: list[dict], unresolved: list[dict]) -> str:
    for bucket, default in (
        (allowed, "coordinated_multi_aspect"),
        (resolved, "priority_resolved"),
        (unresolved, "unresolved"),
    ):
        for item in bucket:
            if _same_clause(item, row):
                return str(item.get("kind", default))
    return "unresolved"


def _resolved_value(row: dict, resolved: list[dict], field: str):
    for item in resolved:
        if _same_clause(item, row):
            return item.get(field)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--coded", type=Path, default=DEFAULT_CODED)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    records = _load_jsonl(args.canonical)
    coded = {row["canonical_id"]: row for row in _load_jsonl(args.coded)} if args.coded.exists() else {}

    candidates: list[dict] = []
    support_word_clauses = 0
    relief_word_clauses = 0
    for record in records:
        text = _record_text(record)
        for span in clause_spans(text):
            clause = span.clause
            old_hits = _hits(clause, OLD_LEXICONS)
            new_hits = _hits(clause, NEW_LEXICONS)
            if not old_hits and not new_hits:
                continue
            if _matches_any(clause, ("support", "supportive")):
                support_word_clauses += 1
            if _matches_any(
                clause,
                ("relief", r"reliev(?:e|es|ed|ing)", r"eas(?:e|es|ed|ing)", "weight off"),
            ):
                relief_word_clauses += 1
            candidates.append(
                {
                    "canonical_id": record["canonical_id"],
                    "clause": clause,
                    "old_hits": old_hits,
                    "new_hits": new_hits,
                }
            )

    total = len(candidates)
    old_ambiguous = [row for row in candidates if len(row["old_hits"]) > 1]
    new_multi = [row for row in candidates if len(row["new_hits"]) > 1]

    allowed: list[dict] = []
    resolved: list[dict] = []
    unresolved: list[dict] = []
    for row in new_multi:
        clause = row["clause"]
        if _attribution_excluded(clause):
            code, step = None, None
            outcome = "attribution_excluded"
        else:
            chunks = _coordinated_aspects(clause, NEW_LEXICONS)
            if chunks:
                code, step = None, None
                outcome = "coordinated_multi_aspect"
                allowed.append({**row, "chunks": chunks, "kind": outcome})
                continue
            code, step = _resolve(clause)
            outcome = "priority_resolved" if code in row["new_hits"] else "unresolved"
            if outcome == "priority_resolved":
                resolved.append({**row, "resolved_code": code, "step": step})
            else:
                unresolved.append({**row, "resolved_code": code, "step": step})
        if outcome == "attribution_excluded":
            allowed.append(
                {
                    **row,
                    "chunks": [],
                    "kind": "attribution_excluded",
                    "note": "relief attributed to non-product subject",
                }
            )

    # A single-code clause can still be wrongly attributed; count those too.
    attribution_skipped = [
        row
        for row in candidates
        if len(row["new_hits"]) == 1 and _attribution_excluded(row["clause"])
    ]

    def pct(part: int, whole: int) -> float:
        return round(100.0 * part / whole, 1) if whole else 0.0

    # Case-level audit for the examples named in decision B §4.
    by_id = {record["canonical_id"]: record for record in records}
    case_rows = []
    for label, canonical_id, needle, expected in CASES:
        record = by_id.get(canonical_id)
        text = _record_text(record) if record else ""
        clause = _find_clause(text, needle) if text else None
        if clause is None:
            case_rows.append(
                {
                    "case": label,
                    "canonical_id": canonical_id,
                    "evidence": needle,
                    "expected": expected,
                    "clause": None,
                    "resolved": None,
                    "step": None,
                    "actual_coded": [],
                    "match": False,
                }
            )
            continue
        excluded = _attribution_excluded(clause)
        # Resolve the named evidence span, not the whole clause: one clause can
        # hold two legitimate aspects ("weight is lifted ... and lifts that big
        # belly").  The priority order applies per evidence span.
        code, step = (None, None) if excluded else _resolve(needle)
        actual = [
            aspect
            for aspect in (coded.get(canonical_id) or {}).get("aspects", [])
            if aspect.get("code", "").startswith("SUP.")
        ]
        experience_gated = (
            expected is None and code is not None and not actual
        )
        match = (
            (expected is None and (code is None or experience_gated))
            or code == expected
        )
        case_rows.append(
            {
                "case": label,
                "canonical_id": canonical_id,
                "evidence": needle,
                "expected": expected,
                "clause": clause,
                "resolved": code,
                "step": step,
                "attribution_excluded": excluded,
                "experience_gated": experience_gated,
                "actual_coded": [
                    {"code": item["code"], "polarity": item["polarity"]} for item in actual
                ],
                "match": match,
            }
        )

    b05 = next((row for row in case_rows if row["case"] == "1"), None)

    coded_sup = [
        (row["canonical_id"], aspect)
        for row in coded.values()
        for aspect in row.get("aspects", [])
        if aspect.get("code", "").startswith("SUP.")
    ]
    coded_pairs = 0
    same_span_pairs: list[dict] = []
    for row in coded.values():
        sup = [
            aspect
            for aspect in row.get("aspects", [])
            if aspect.get("code", "").startswith("SUP.")
        ]
        for left, right in itertools.combinations(sup, 2):
            coded_pairs += 1
            if left.get("evidence_span") == right.get("evidence_span"):
                same_span_pairs.append(
                    {
                        "canonical_id": row["canonical_id"],
                        "span": left.get("evidence_span"),
                        "codes": [left["code"], right["code"]],
                    }
                )

    summary = {
        "taxonomy_version": TAXONOMY_VERSION,
        "canonical_records": len(records),
        "candidate_clauses": total,
        "candidate_clauses_with_literal_support_words": support_word_clauses,
        "candidate_clauses_with_relief_or_weight_words": relief_word_clauses,
        "v1_0": {
            "ambiguous_clauses": len(old_ambiguous),
            "ambiguous_pct": pct(len(old_ambiguous), total),
            "pair_counts": _pair_counts([row["old_hits"] for row in candidates]),
        },
        "v1_1": {
            "raw_lexical_overlap_clauses": len(new_multi),
            "raw_lexical_overlap_pct": pct(len(new_multi), total),
            "priority_resolved_clauses": len(resolved),
            "coordinated_multi_aspect_clauses": len(allowed),
            "unresolved_ambiguous_clauses": len(unresolved),
            "unresolved_ambiguous_pct": pct(len(unresolved), total),
            "pair_counts": _pair_counts([row["new_hits"] for row in candidates]),
        },
        "attribution_excluded_single_code_clauses": len(attribution_skipped),
        "coded_artifact": {
            "path": str(args.coded),
            "records": len(coded),
            "records_with_sup": len({cid for cid, _ in coded_sup}),
            "sup_aspects": len(coded_sup),
            "records_with_two_or_more_sup": sum(
                1
                for row in coded.values()
                if sum(
                    1
                    for aspect in row.get("aspects", [])
                    if aspect.get("code", "").startswith("SUP.")
                )
                >= 2
            ),
            "sup_pairs_same_record": coded_pairs,
            "sup_pairs_same_evidence_span": len(same_span_pairs),
            "same_span_ambiguous_cases": same_span_pairs,
        },
        "b05": b05,
        "cases": case_rows,
        "case_mismatches": [row for row in case_rows if not row["match"]],
        "old_ambiguous_cases": [
            {
                "canonical_id": row["canonical_id"],
                "clause": row["clause"],
                "codes": sorted(row["old_hits"]),
            }
            for row in old_ambiguous
        ],
        "new_multi_cases": [
            {
                "canonical_id": row["canonical_id"],
                "clause": row["clause"],
                "raw_codes": sorted(row["new_hits"]),
                "outcome": _outcome_for(row, allowed, resolved, unresolved),
                "resolved_code": _resolved_value(row, resolved, "resolved_code"),
                "resolved_step": _resolved_value(row, resolved, "step"),
            }
            for row in new_multi
        ],
    }

    print(f"canonical records: {len(records)}")
    print(f"candidate clauses: {total} "
          f"(literal support words {support_word_clauses}, relief/weight words {relief_word_clauses})")
    print()
    print("v1.0 (no priority rule)")
    print(f"  ambiguous clauses: {len(old_ambiguous)}/{total} ({pct(len(old_ambiguous), total)}%)")
    for pair, count in summary["v1_0"]["pair_counts"].items():
        print(f"    {pair}: {count}")
    print()
    print("v1.1 (priority order)")
    print(f"  raw lexical overlap: {len(new_multi)}/{total} ({pct(len(new_multi), total)}%)")
    print(f"  resolved by priority: {len(resolved)}")
    print(f"  coordinated multi-aspect (allowed): {len(allowed)}")
    print(f"  unresolved ambiguity: {len(unresolved)}/{total} ({pct(len(unresolved), total)}%)")
    artifact = summary["coded_artifact"]
    print()
    print("frozen coded artifact")
    print(f"  records: {artifact['records']}  SUP aspects: {artifact['sup_aspects']} "
          f"in {artifact['records_with_sup']} records")
    print(f"  records with >=2 SUP codes: {artifact['records_with_two_or_more_sup']}")
    print(f"  SUP pairs in one record: {artifact['sup_pairs_same_record']} "
          f"(distinct evidence spans are legitimate)")
    print(f"  SUP pairs on the same evidence span: {artifact['sup_pairs_same_evidence_span']}")
    for item in artifact["same_span_ambiguous_cases"]:
        print(f"    AMBIGUOUS {item}")
    print()
    print("B05 c-1mdp0wu")
    if b05 and b05["clause"]:
        print(f"  clause: {b05['clause']}")
        print(f"  resolved: {b05['resolved']} (step {b05['step']})")
        print(f"  coded ALL.jsonl: {b05['actual_coded']}")
    print()
    print("decision B §4 case audit")
    for row in case_rows:
        expected = row["expected"] or "(no SUP)"
        observed = row["resolved"] or "(no SUP)"
        flag = "OK" if row["match"] else "MISMATCH"
        print(
            f"  [{flag}] {row['case']:>2} {row['canonical_id']}: "
            f"expected {expected}, resolver {observed} (step {row['step']})"
        )
    if summary["case_mismatches"]:
        print()
        print("case mismatches:")
        for row in summary["case_mismatches"]:
            print(f"  {row}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"\nwrote {args.json_out}")

    return 1 if unresolved or summary["case_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())

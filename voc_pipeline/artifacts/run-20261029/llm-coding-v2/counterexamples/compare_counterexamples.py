#!/usr/bin/env python3
"""Compare hand judgment, LLM encoder runs, and the formal SUP resolver."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOC_ROOT = HERE.parents[3]
sys.path.insert(0, str(VOC_ROOT / "tools"))
sys.path.insert(0, str(VOC_ROOT))
import check_support_exclusivity as checker  # noqa: E402

HAND = json.loads((HERE / "hand-judgment.json").read_text(encoding="utf-8"))
ITEMS = {json.loads(line)["canonical_id"]: json.loads(line) for line in (HERE / "items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
POLARITIES = {"positive", "qualified_positive", "negative", "qualified_negative", "mixed", "unknown"}

RUNS = [
    ("gpt6-sol-lex", "coded-gpt6-sol-lex.raw.txt", "group/auto-gpt-6-sol", "lexicon-inclusive"),
    ("kimi-k3-lex", "coded-kimi-k3-lex.raw.txt", "group/auto-kimi-k3", "lexicon-inclusive"),
    ("deepseek-flash-lex", "coded-deepseek-flash-lex.raw.txt", "group/auto-deepseek-flash", "lexicon-inclusive"),
    ("gpt6-sol-compact", "coded-gpt6-sol.raw.txt", "group/auto-gpt-6-sol", "compact"),
    ("kimi-k3-compact", "coded-kimi-k3.raw.txt", "group/auto-kimi-k3", "compact"),
    ("deepseek-flash-compact", "coded-deepseek-flash.raw.txt", "group/auto-deepseek-flash", "compact"),
    ("gpt6-sol-v12", "coded-gpt6-sol-v12.raw.txt", "group/auto-gpt-6-sol", "v1.2-proposed lexicon-inclusive"),
    ("kimi-k3-v12", "coded-kimi-k3-v12.raw.txt", "group/auto-kimi-k3", "v1.2-proposed lexicon-inclusive"),
    ("deepseek-flash-v12", "coded-deepseek-flash-v12.raw.txt", "group/auto-deepseek-flash", "v1.2-proposed lexicon-inclusive"),
]


def parse_raw(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:jsonl|json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def span_pos(text: str, span: str) -> tuple[int, int] | None:
    i = text.find(span)
    return (i, i + len(span)) if i >= 0 else None


def validate(rows: list[dict]) -> list[str]:
    errors = []
    if len(rows) != len(ITEMS):
        errors.append(f"row count {len(rows)} != {len(ITEMS)}")
    expected_ids = list(ITEMS)
    for idx, row in enumerate(rows):
        cid = row.get("canonical_id")
        if idx < len(expected_ids) and cid != expected_ids[idx]:
            errors.append(f"row {idx} id {cid} != {expected_ids[idx]}")
        if cid not in ITEMS:
            errors.append(f"unknown id {cid}")
            continue
        src = (ITEMS[cid].get("title") or "") + "\n" + (ITEMS[cid].get("text") or "")
        # Legacy input convention (pre-E-merge).  The merged coder suppresses
        # off-target aspects downstream, so this is not the published gate.
        if not row.get("is_product_experience") and row.get("aspects"):
            errors.append(f"{cid}: aspects on non-experience")
        seen = set()
        for a in row.get("aspects") or []:
            if a.get("code") not in {c.code for c in checker.ASPECTS}:
                errors.append(f"{cid}: bad code {a.get('code')}")
            if a.get("polarity") not in POLARITIES:
                errors.append(f"{cid}: bad polarity {a.get('polarity')}")
            span = a.get("evidence_span") or ""
            if not span or span not in src:
                errors.append(f"{cid}: span not verbatim: {span!r}")
            if len(span) > 120:
                errors.append(f"{cid}: span >120: {span!r}")
            if span in seen:
                errors.append(f"{cid}: duplicate span {span!r}")
            seen.add(span)
    return errors


def sup_aspects(row: dict) -> list[dict]:
    return [a for a in row.get("aspects") or [] if a.get("code", "").startswith("SUP.")]


def compare_case(case: dict, row: dict) -> dict:
    cid = case["canonical_id"]
    text = ITEMS[cid]["text"]
    expected = {e["code"]: e["polarity"] for e in case["expected_sup"]}
    expected_families = {code.split(".")[0] for code in expected}
    actual_sup = sup_aspects(row)
    actual_all = list(row.get("aspects") or [])
    actual = {}
    for a in actual_all:
        actual.setdefault(a["code"], []).append(a["polarity"])
    missing = [code for code in expected if code not in actual]
    extra = [code for code in actual if code not in expected and code.split(".")[0] in expected_families]
    polarity_bad = [code for code in expected if code in actual and expected[code] not in actual[code]]
    # same-span / overlapping-span SUP conflicts
    positions = []
    for a in actual_sup:
        pos = span_pos(text, a["evidence_span"])
        positions.append((a["code"], a["evidence_span"], pos))
    conflicts = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            c1, s1, p1 = positions[i]
            c2, s2, p2 = positions[j]
            if c1 == c2 or p1 is None or p2 is None:
                continue
            if p1[0] < p2[1] and p2[0] < p1[1]:
                conflicts.append({"left": c1, "left_span": s1, "right": c2, "right_span": s2,
                                  "kind": "same_span" if p1 == p2 else "overlap"})
    ok = not missing and not extra and not polarity_bad and not conflicts
    return {
        "canonical_id": cid,
        "case_no": case["case_no"],
        "expected": [{"code": k, "polarity": v} for k, v in expected.items()],
        "actual_sup": [{"code": a["code"], "polarity": a["polarity"], "span": a["evidence_span"]} for a in actual_sup],
        "missing": missing,
        "extra": extra,
        "polarity_mismatch": polarity_bad,
        "same_span_or_overlap_conflicts": conflicts,
        "matches_hand": ok,
    }


def formal_check(case: dict) -> dict:
    text = ITEMS[case["canonical_id"]]["text"]
    whole_raw = sorted(checker._hits(text, checker.NEW_LEXICONS))
    whole_resolved, whole_step = checker._resolve(text)
    out = []
    for e in case["expected_sup"]:
        if not e["code"].startswith("SUP."):
            continue
        span = e["span"]
        raw = sorted(checker._hits(span, checker.NEW_LEXICONS))
        resolved, step = checker._resolve(span)
        out.append({"span": span, "expected": e["code"], "raw_codes": raw,
                    "resolved": resolved, "step": step, "correct": resolved == e["code"],
                    "raw_overlap": len(raw) > 1})
    return {"expected_spans": out,
            "whole_text": {"raw_codes": whole_raw, "resolved": whole_resolved, "step": whole_step}}


def formal_check_rules(case: dict, rules: list[dict]) -> dict:
    text = ITEMS[case["canonical_id"]]["text"]

    def matches(t: str, rule: dict) -> bool:
        return any(re.search(checker._lexicon_pattern(p), t, re.I) for p in rule["lexicon"])

    def raw_codes(t: str) -> list[str]:
        return sorted({r["code"] for r in rules if matches(t, r)})

    def resolve(t: str):
        for rule in rules:
            if matches(t, rule):
                return rule["code"], int(rule["step"])
        return None, None

    whole_resolved, whole_step = resolve(text)
    out = []
    for e in case["expected_sup"]:
        if not e["code"].startswith("SUP."):
            continue
        span = e["span"]
        raw = raw_codes(span)
        resolved, step = resolve(span)
        out.append({"span": span, "expected": e["code"], "raw_codes": raw,
                    "resolved": resolved, "step": step, "correct": resolved == e["code"],
                    "raw_overlap": len(raw) > 1})
    return {"expected_spans": out,
            "whole_text": {"raw_codes": raw_codes(text), "resolved": whole_resolved, "step": whole_step}}


def main() -> int:
    report = {"hand_cases": len(HAND["cases"]), "encoders": {}, "formal": {}, "formal_v12": {}, "summary": {}}
    for case in HAND["cases"]:
        report["formal"][case["canonical_id"]] = formal_check(case)
    proposed = json.loads((HERE / "taxonomy-v1.2-proposed.json").read_text(encoding="utf-8"))
    for case in HAND["cases"]:
        report["formal_v12"][case["canonical_id"]] = formal_check_rules(case, proposed["resolution_rules"])

    aggregate = {}
    for name, filename, model, prompt_style in RUNS:
        path = HERE / filename
        if not path.exists():
            continue
        rows = parse_raw(path)
        errors = validate(rows)
        by_id = {r["canonical_id"]: r for r in rows}
        cases = [compare_case(c, by_id[c["canonical_id"]]) for c in HAND["cases"] if c["canonical_id"] in by_id]
        same_span = sum(1 for c in cases if c["same_span_or_overlap_conflicts"])
        matches = sum(1 for c in cases if c["matches_hand"])
        extra_only = sum(1 for c in cases if c["extra"] and not c["missing"] and not c["polarity_mismatch"] and not c["same_span_or_overlap_conflicts"])
        report["encoders"][name] = {
            "model": model, "prompt_style": prompt_style, "file": filename,
            "validation_errors": errors, "cases": cases,
            "same_span_conflict_cases": same_span,
            "matches_hand_cases": matches,
            "extra_only_cases": extra_only,
        }
        aggregate[name] = {"same_span_conflict_cases": same_span, "matches_hand_cases": matches, "extra_only_cases": extra_only, "validation_errors": len(errors)}

    official = [n for n in aggregate if n.endswith("-lex")]
    compact = [n for n in aggregate if n.endswith("-compact")]
    v12 = [n for n in aggregate if n.endswith("-v12")]
    report["summary"] = {
        "official_runs": official,
        "sensitivity_runs": compact,
        "per_run": aggregate,
        "official_same_span_conflict_total": sum(aggregate[n]["same_span_conflict_cases"] for n in official),
        "official_full_match_runs": {n: aggregate[n]["matches_hand_cases"] for n in official},
        "compact_full_match_runs": {n: aggregate[n]["matches_hand_cases"] for n in compact},
        "v12_runs": v12,
        "v12_full_match_runs": {n: aggregate[n]["matches_hand_cases"] for n in v12},
    }
    (HERE / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    for name, data in report["encoders"].items():
        print(f"\n== {name} ({data['model']}, {data['prompt_style']}) errors={data['validation_errors']}")
        for c in data["cases"]:
            flags = []
            if c["missing"]: flags.append("MISS " + ",".join(c["missing"]))
            if c["extra"]: flags.append("EXTRA " + ",".join(c["extra"]))
            if c["polarity_mismatch"]: flags.append("POL " + ",".join(c["polarity_mismatch"]))
            if c["same_span_or_overlap_conflicts"]: flags.append("SAME_SPAN")
            print(f"  {c['canonical_id']} {'PASS' if c['matches_hand'] else 'FAIL'} {'; '.join(flags)}")
    print("\n== formal per-span resolver")
    span_total = span_correct = span_overlap = 0
    whole_correct = 0
    for cid, data in report["formal"].items():
        for r in data["expected_spans"]:
            span_total += 1
            span_correct += int(r["correct"])
            span_overlap += int(r["raw_overlap"])
            print(f"  {cid} {r['expected']} raw={r['raw_codes']} -> {r['resolved']} step={r['step']} correct={r['correct']}")
        w = data["whole_text"]
        primary = next(iter([e["code"] for e in next(c for c in HAND["cases"] if c["canonical_id"] == cid)["expected_sup"]]))
        whole_ok = w["resolved"] == primary
        whole_correct += int(whole_ok)
        print(f"       whole_text raw={w['raw_codes']} -> {w['resolved']} step={w['step']} primary={primary} correct={whole_ok}")
    report["summary"]["formal_expected_span_total"] = span_total
    report["summary"]["formal_expected_span_correct"] = span_correct
    report["summary"]["formal_expected_span_raw_overlap"] = span_overlap
    report["summary"]["formal_whole_text_primary_correct"] = whole_correct
    v12_span_total = v12_span_correct = v12_span_overlap = 0
    v12_whole_correct = 0
    for cid, data in report["formal_v12"].items():
        for r in data["expected_spans"]:
            v12_span_total += 1
            v12_span_correct += int(r["correct"])
            v12_span_overlap += int(r["raw_overlap"])
        w = data["whole_text"]
        primary = next(iter([e["code"] for e in next(c for c in HAND["cases"] if c["canonical_id"] == cid)["expected_sup"]]))
        v12_whole_correct += int(w["resolved"] == primary)
    report["summary"]["formal_v12_expected_span_total"] = v12_span_total
    report["summary"]["formal_v12_expected_span_correct"] = v12_span_correct
    report["summary"]["formal_v12_expected_span_raw_overlap"] = v12_span_overlap
    report["summary"]["formal_v12_whole_text_primary_correct"] = v12_whole_correct
    (HERE / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nformal summary:", {k: report["summary"][k] for k in ("formal_expected_span_total","formal_expected_span_correct","formal_expected_span_raw_overlap","formal_whole_text_primary_correct")})
    print("formal v1.2 summary:", {k: report["summary"][k] for k in ("formal_v12_expected_span_total","formal_v12_expected_span_correct","formal_v12_expected_span_raw_overlap","formal_v12_whole_text_primary_correct")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
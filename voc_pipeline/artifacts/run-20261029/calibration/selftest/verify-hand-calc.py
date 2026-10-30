#!/usr/bin/env python3
"""Independently recompute kappa for the self-test fixture and check the report.

This script does not import ``compute-kappa.py``.  It re-reads the raw files,
recounts every 2x2 table from scratch, and compares the result with the
machine-readable metrics produced by the main script.  It also prints one
hand calculation step by step.

Usage:
    python3 selftest/verify-hand-calc.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALIBRATION = HERE.parent
SAMPLE = CALIBRATION / "blind-sample.jsonl"
MAPPING = CALIBRATION / "mapping.json"
CODED = CALIBRATION.parent / "llm-coding" / "coded" / "ALL.jsonl"
TAXONOMY = CALIBRATION.parent / "llm-coding" / "taxonomy.json"
HUMAN = HERE / "fake-human-labels.json"
METRICS = HERE / "kappa-metrics-selftest.json"
REPORT = HERE / "kappa-report-selftest.md"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def kappa(a: int, b: int, c: int, d: int):
    n = a + b + c + d
    if n == 0:
        return None, None, None
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    if abs(1.0 - pe) < 1e-12:
        return po, pe, None
    return po, pe, (po - pe) / (1.0 - pe)


def close(left, right, tol=1e-9):
    if left is None or right is None:
        return left is None and right is None
    return abs(left - right) <= tol


def main() -> int:
    sample = load_jsonl(SAMPLE)
    mapping = {row["item_id"]: row for row in load_json(MAPPING)["items"]}
    coded = {row["canonical_id"]: row for row in load_jsonl(CODED)}
    taxonomy = load_json(TAXONOMY)["aspects"]
    human_raw = load_json(HUMAN)
    human = {row["item_id"]: row for row in human_raw["items"]}
    metrics = load_json(METRICS)
    report = REPORT.read_text(encoding="utf-8")

    codes = [aspect["code"] for aspect in taxonomy]
    labels = {aspect["code"]: aspect["label"] for aspect in taxonomy}

    # Build independent sets from the raw files.
    human_sets: dict[str, dict[str, dict]] = {}
    llm_sets: dict[str, dict[str, dict]] = {}
    for item in sample:
        item_id = item["item_id"]
        human_sets[item_id] = {
            aspect["code"]: {"polarity": aspect["polarity"], "evidence": aspect.get("evidence", "")}
            for aspect in human[item_id]["aspects"]
        }
        row = coded[mapping[item_id]["canonical_id"]]
        llm_sets[item_id] = {
            aspect["code"]: {
                "polarity": aspect["polarity"],
                "evidence": aspect.get("evidence_span", ""),
            }
            for aspect in row["aspects"]
            if aspect.get("confidence") == "high"
        }

    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if condition:
            print(f"PASS  {message}")
        else:
            print(f"FAIL  {message}")
            failures.append(message)

    # 1. Per-aspect ALL kappa, independently counted.
    print("\n== Per-aspect ALL kappa: independent recount vs metrics JSON ==")
    per_aspect_independent = {}
    for code in codes:
        a = b = c = d = 0
        for item in sample:
            item_id = item["item_id"]
            has_human = code in human_sets[item_id]
            has_llm = code in llm_sets[item_id]
            if has_human and has_llm:
                a += 1
            elif has_human:
                b += 1
            elif has_llm:
                c += 1
            else:
                d += 1
        po, pe, k = kappa(a, b, c, d)
        per_aspect_independent[code] = {
            "a": a, "b": b, "c": c, "d": d, "po": po, "pe": pe, "kappa": k
        }
        reported = metrics["per_aspect"][code]["ALL"]["kappa"]
        check(close(k, reported), f"{code}: independent kappa={k!r}, metrics={reported!r}")

    # 2. Micro kappa, independently pooled.
    print("\n== Micro kappa: independent recount vs metrics JSON ==")
    for source_name, source_key in (("TikTok", "tiktok_shop"), ("Reddit", "reddit"), ("ALL", None)):
        items = [
            item for item in sample
            if source_key is None or item["source"] == source_key
        ]
        a = b = c = d = 0
        for item in items:
            item_id = item["item_id"]
            for code in codes:
                has_human = code in human_sets[item_id]
                has_llm = code in llm_sets[item_id]
                if has_human and has_llm:
                    a += 1
                elif has_human:
                    b += 1
                elif has_llm:
                    c += 1
                else:
                    d += 1
        po, pe, k = kappa(a, b, c, d)
        if source_name == "ALL":
            reported = metrics["overall"]["kappa_micro"]
        else:
            reported = metrics["source_summary"][source_name]["kappa_micro"]
        print(
            f"  {source_name}: a={a} b={b} c={c} d={d} "
            f"po={po:.12f} pe={pe:.12f} kappa={k:.12f}"
        )
        check(close(k, reported), f"{source_name} micro kappa: independent={k!r}, metrics={reported!r}")

    # 3. Hand calculation for the aspect with the most disagreements.
    top_code = metrics["top_disagreements"][0]["code"] if metrics["top_disagreements"] else "SUP.GENERAL"
    stats = per_aspect_independent[top_code]
    a, b, c, d = stats["a"], stats["b"], stats["c"], stats["d"]
    n = a + b + c + d
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    k = (po - pe) / (1 - pe) if abs(1 - pe) > 1e-12 else None
    print(f"\n== Hand calculation: {labels[top_code]} ({top_code}) ==")
    print(f"  n = a+b+c+d = {a}+{b}+{c}+{d} = {n}")
    print(f"  a (both present) = {a}; b (human only) = {b}; c (LLM only) = {c}; d (both absent) = {d}")
    print(f"  po = (a+d)/n = ({a}+{d})/{n} = {po:.12f}")
    print(f"  pe = ((a+b)(a+c)+(c+d)(b+d))/n^2")
    print(f"     = (({a + b})({a + c})+({c + d})({b + d}))/{n ** 2} = {pe:.12f}")
    print(f"  kappa = (po-pe)/(1-pe) = ({po:.12f}-{pe:.12f})/(1-{pe:.12f}) = {k:.12f}")
    print(f"  metrics JSON kappa = {metrics['per_aspect'][top_code]['ALL']['kappa']!r}")
    check(close(k, metrics["per_aspect"][top_code]["ALL"]["kappa"]), "hand calculation matches metrics JSON")

    # 4. Top-5 ranking, independently reproduced.
    print("\n== Top-5 disagreement ranking ==")
    ranked = []
    for code in codes:
        stats = per_aspect_independent[code]
        presence = stats["b"] + stats["c"]
        both = stats["a"]
        both_polarity_exact = 0
        for item in sample:
            item_id = item["item_id"]
            if code in human_sets[item_id] and code in llm_sets[item_id]:
                if human_sets[item_id][code]["polarity"] == llm_sets[item_id][code]["polarity"]:
                    both_polarity_exact += 1
        polarity = both - both_polarity_exact
        total = presence + polarity
        if total > 0:
            k = stats["kappa"] if stats["kappa"] is not None else 2.0
            ranked.append((-total, k, -presence, code))
    ranked.sort()
    independent_top5 = [entry[3] for entry in ranked[:5]]
    reported_top5 = [entry["code"] for entry in metrics["top_disagreements"]]
    print(f"  independent: {independent_top5}")
    print(f"  reported:    {reported_top5}")
    check(independent_top5 == reported_top5, "top-5 aspect order matches independent ranking")
    check(len(reported_top5) == 5, "report lists 5 disagreement aspects")

    # 5. Report structure.
    print("\n== Report structure ==")
    required = [
        "## 1 结论摘要",
        "## 2 分信源",
        "## 3 逐 aspect",
        "## 4 分信源逐 aspect",
        "## 5 极性一致率",
        "## 6 产品体验判定一致性",
        "## 7 分歧最大的 top 5 aspect",
    ]
    for heading in required:
        check(heading in report, f"report contains {heading!r}")
    top_section = report.split("## 7 分歧最大的 top 5 aspect", 1)[1]
    top_section = top_section.split("## 8", 1)[0]
    check(top_section.count("### ") == 5, "top-5 section contains exactly 5 aspect subsections")
    check("| 题目 | 人工标注 | LLM 标注 |" in top_section, "top-5 section contains side-by-side table")
    check("TikTok" in report and "Reddit" in report, "report separates TikTok and Reddit")
    check("一致率" in report and "κ (micro)" in report, "report reports raw agreement and micro kappa")

    # 6. Experience gate, independently counted.
    print("\n== Experience gate (is_product_experience) ==")
    a = b = c = d = 0
    for item in sample:
        item_id = item["item_id"]
        human_yes = bool(human[item_id]["is_product_experience"])
        llm_yes = bool(coded[mapping[item_id]["canonical_id"]]["is_product_experience"])
        if human_yes and llm_yes:
            a += 1
        elif human_yes and not llm_yes:
            b += 1
        elif (not human_yes) and llm_yes:
            c += 1
        else:
            d += 1
    gate_po, gate_pe, gate_k = kappa(a, b, c, d)
    reported_gate = metrics["experience_gate"]
    print(f"  a={a} b={b} c={c} d={d}; kappa={gate_k}")
    check(close(gate_k, reported_gate["kappa"]), "experience-gate kappa matches metrics JSON")

    print("\n== Result ==")
    if failures:
        print(f"FAILED: {len(failures)} check(s) failed")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

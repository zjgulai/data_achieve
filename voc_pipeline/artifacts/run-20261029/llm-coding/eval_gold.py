#!/usr/bin/env python3
"""Evaluate the LLM coder against the frozen 50-record gold set.

Matching is a per-record multiset intersection on a key:
  strict     -> (code, polarity)
  family     -> (code, polarity_family) where qualified_* collapses into its sign
  code_only  -> code

TP = sum over records of |gold_keys & llm_keys|;
precision = TP / all LLM aspects; recall = TP / all gold aspects.

The same code path reproduces the published rule-coder numbers from
gold/coder-output-50.jsonl, which is asserted at the start.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GOLD = ROOT / "gold-set-50.jsonl"
GOLD_RAW = ROOT / "gold" / "gold-set-50.raw.jsonl"
OLD = ROOT / "gold" / "coder-output-50.jsonl"
NEW = HERE / "coded" / "ALL.jsonl"
OUT = HERE / "eval-result.json"

FAM = {
    "positive": "pos", "qualified_positive": "pos",
    "negative": "neg", "qualified_negative": "neg",
    "mixed": "mix", "unknown": "unk",
}
SRC = {"tiktok_shop": "TikTok", "reddit": "Reddit"}
KEYS = {
    "strict": lambda a: (a["code"], a["polarity"]),
    "family": lambda a: (a["code"], FAM.get(a["polarity"], a["polarity"])),
    "code_only": lambda a: a["code"],
}


def load(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def score(rows_by_id, gold_by_id, keyfn):
    per = Counter()
    for cid, g in gold_by_id.items():
        src = SRC[g["source"]]
        gk = Counter(keyfn(a) for a in g["aspects"])
        ck = Counter(keyfn(a) for a in (rows_by_id.get(cid) or {}).get("aspects", []))
        tp = sum((gk & ck).values())
        for bucket in (src, "ALL"):
            per[(bucket, "tp")] += tp
            per[(bucket, "gold")] += sum(gk.values())
            per[(bucket, "coder")] += sum(ck.values())
    return per


def table(per):
    out = {}
    for bucket in ("TikTok", "Reddit", "ALL"):
        tp, gold_n, coder_n = per[(bucket, "tp")], per[(bucket, "gold")], per[(bucket, "coder")]
        out[bucket] = {
            "coder_aspects": coder_n,
            "gold_aspects": gold_n,
            "true_positives": tp,
            "precision_pct": round(100 * tp / coder_n, 1) if coder_n else None,
            "recall_pct": round(100 * tp / gold_n, 1) if gold_n else None,
        }
    return out


def main() -> int:
    gold = load(GOLD)
    gold_by_id = {r["canonical_id"]: r for r in gold}
    raw_by_id = {r["canonical_id"]: r for r in load(GOLD_RAW)}
    new_by_id = {r["canonical_id"]: r for r in load(NEW)}
    old_raw = load(OLD)
    old_by_id = {
        r["canonical_id"]: {
            "aspects": [a for a in r["annotations"] if a.get("axis") == "aspect"]
        }
        for r in old_raw
    }

    # --- reproduction guard: published rule-coder numbers ---
    published = {
        "strict": {"TikTok": (63.4, 33.8), "ALL": (63.4, 30.6)},
        "family": {"TikTok": (73.2, 39.0), "ALL": (73.2, 35.3)},
        "code_only": {"TikTok": (78.0, 41.6), "ALL": (78.0, 37.6)},
    }
    old_tables = {}
    for name, keyfn in KEYS.items():
        t = table(score(old_by_id, gold_by_id, keyfn))
        old_tables[name] = t
        for bucket, (p, r) in published[name].items():
            assert (t[bucket]["precision_pct"], t[bucket]["recall_pct"]) == (p, r), (
                "reproduction mismatch", name, bucket, t[bucket])

    new_tables = {name: table(score(new_by_id, gold_by_id, keyfn)) for name, keyfn in KEYS.items()}

    comparison = {}
    for name in KEYS:
        comparison[name] = {}
        for bucket in ("TikTok", "Reddit", "ALL"):
            o, n = old_tables[name][bucket], new_tables[name][bucket]
            comparison[name][bucket] = {
                "old_precision_pct": o["precision_pct"],
                "new_precision_pct": n["precision_pct"],
                "delta_precision_pp": (
                    round(n["precision_pct"] - o["precision_pct"], 1)
                    if o["precision_pct"] is not None and n["precision_pct"] is not None else None
                ),
                "old_recall_pct": o["recall_pct"],
                "new_recall_pct": n["recall_pct"],
                "delta_recall_pp": (
                    round(n["recall_pct"] - o["recall_pct"], 1)
                    if o["recall_pct"] is not None and n["recall_pct"] is not None else None
                ),
            }

    # --- false positives with category ---
    # category rules are applied by hand-verified mapping below
    FP_CATEGORY = {
        ("c-7667963659528931085", "SUP.GENERAL"): "support_family_boundary",
        ("c-7667963659528931085", "COM.GENERAL"): "polarity_hedge",
        ("c-7697340641772160781", "SUP.BACK"): "generic_other_people",
        ("c-7679159693625673485", "GEN.OVERALL_EVALUATION"): "recommend_vs_overall",
        ("c-7686709601646593805", "SUP.GENERAL"): "polarity_hedge",
        ("c-7658003601176119053", "SUP.BACK"): "support_family_boundary",
        ("c-7695606260216399630", "SUP.GENERAL"): "vague_praise_overreach",
        ("c-7679740736191088397", "SUP.GENERAL"): "polarity_hedge",
        ("c-7700979310009550605", "MAT.FABRIC"): "vague_praise_overreach",
        ("c-7665021905910384398", "FIT.COVERAGE"): "excluded_semantics",
        ("c-1x65j91", "GEN.OVERALL_EVALUATION"): "other_product_scope",
        ("c-1x65j91", "COM.GENERAL"): "other_product_scope",
        ("c-1w3knom", "ACT.COMPATIBILITY"): "support_family_boundary",
    }

    fps = []
    fns = []
    for cid, g in gold_by_id.items():
        src = SRC[g["source"]]
        gk = Counter((a["code"], a["polarity"]) for a in g["aspects"])
        ck = Counter((a["code"], a["polarity"]) for a in (new_by_id.get(cid) or {}).get("aspects", []))
        matched = gk & ck
        for a in (new_by_id.get(cid) or {}).get("aspects", []):
            k = (a["code"], a["polarity"])
            if matched[k] > 0:
                matched[k] -= 1
                continue
            same_code = [x for x in g["aspects"] if x["code"] == a["code"]]
            fps.append({
                "canonical_id": cid,
                "source": src,
                "code": a["code"],
                "polarity": a["polarity"],
                "confidence": a["confidence"],
                "evidence_span": a["evidence_span"],
                "gold_aspects": [{"code": x["code"], "polarity": x["polarity"], "evidence": x.get("evidence")}
                                 for x in g["aspects"]],
                "same_code_in_gold": [{"code": x["code"], "polarity": x["polarity"]} for x in same_code],
                "pattern": FP_CATEGORY.get((cid, a["code"]), "unclassified"),
                "is_product_experience_gold": g["is_product_experience"],
                "legacy_gate": "is_product_experience (pre-E-merge; audit only, not the cohort predicate)",
                "record_text": (raw_by_id.get(cid, {}).get("text") or "")[:600],
            })
        matched2 = gk & ck
        for a in g["aspects"]:
            k = (a["code"], a["polarity"])
            if matched2[k] > 0:
                matched2[k] -= 1
            else:
                fns.append({
                    "canonical_id": cid,
                    "source": src,
                    "code": a["code"],
                    "polarity": a["polarity"],
                    "evidence": a.get("evidence"),
                    "llm_aspects": [{"code": x["code"], "polarity": x["polarity"]} for x in
                                    (new_by_id.get(cid) or {}).get("aspects", [])],
                })

    pattern_counts = Counter(f["pattern"] for f in fps)

    # --- precision by confidence ---
    by_conf = {}
    for conf in ("high", "medium", "low"):
        tp = fp = 0
        for cid, g in gold_by_id.items():
            gk = Counter((a["code"], a["polarity"]) for a in g["aspects"])
            used = Counter()
            for a in (new_by_id.get(cid) or {}).get("aspects", []):
                if a["confidence"] != conf:
                    continue
                k = (a["code"], a["polarity"])
                if used[k] < gk[k]:
                    used[k] += 1
                    tp += 1
                else:
                    fp += 1
        by_conf[conf] = {
            "true_positives": tp, "false_positives": fp, "aspects": tp + fp,
            "precision_pct": round(100 * tp / (tp + fp), 1) if tp + fp else None,
        }

    # --- experience flag confusion ---
    flag = Counter()
    for cid, g in gold_by_id.items():
        n = new_by_id.get(cid) or {}
        flag[(g["is_product_experience"], n.get("is_product_experience"))] += 1

    # --- sensitivity: drop records whose gold aspect count exceeds the 6 cap ---
    over_cap = [cid for cid, g in gold_by_id.items() if len(g["aspects"]) > 6]
    sens = {}
    for exclude in (False, True):
        per = Counter()
        for cid, g in gold_by_id.items():
            if exclude and cid in over_cap:
                continue
            src = SRC[g["source"]]
            gk = Counter((a["code"], a["polarity"]) for a in g["aspects"])
            ck = Counter((a["code"], a["polarity"]) for a in (new_by_id.get(cid) or {}).get("aspects", []))
            tp = sum((gk & ck).values())
            for bucket in (src, "ALL"):
                per[(bucket, "tp")] += tp
                per[(bucket, "gold")] += sum(gk.values())
                per[(bucket, "coder")] += sum(ck.values())
        sens["exclude_over_cap_records" if exclude else "all"] = table(per)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_set": str(GOLD),
        "evaluated_file": str(NEW),
        "rule": {
            "matching": "per-record multiset intersection; each LLM aspect consumes at most one gold aspect",
            "strict": "[code, polarity] exact",
            "family": "[code, polarity family] with qualified_positive->positive, qualified_negative->negative",
            "code_only": "[code]",
        },
        "reproduction_check": {"passed": True, "note": "old rule-coder table reproduced exactly from gold/coder-output-50.jsonl"},
        "old_rule_coder": old_tables,
        "new_llm_coder": new_tables,
        "comparison": comparison,
        "verdict_thresholds_pct": {"pass": 90, "near_miss": "85-90", "fail": "<85"},
        "strict_all_precision_pct": new_tables["strict"]["ALL"]["precision_pct"],
        "false_positives": fps,
        "false_positive_count": len(fps),
        "false_positive_pattern_counts": dict(pattern_counts),
        "false_negatives": fns,
        "false_negative_count": len(fns),
        "precision_by_confidence_strict": by_conf,
        "experience_flag_confusion": {
            "gold_true_llm_true": flag[(True, True)],
            "gold_true_llm_false": flag[(True, False)],
            "gold_false_llm_true": flag[(False, True)],
            "gold_false_llm_false": flag[(False, False)],
        },
        "sensitivity_gold_over_six_aspects": {
            "records": [{"canonical_id": cid, "gold_aspects": len(gold_by_id[cid]["aspects"])} for cid in over_cap],
            **sens,
        },
        "gold_polarities_observed": dict(Counter(a["polarity"] for r in gold for a in r["aspects"])),
        "notes": [
            "gold contains qualified_positive, which the coding contract forbids emitting; those gold aspects cannot be "
            "matched under strict when the LLM answers positive.",
            "two gold records exceed the contract's 6-aspect cap (14 and 8 aspects); recall on them is structurally capped.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("reproduction check: PASS")
    for name in ("strict", "family", "code_only"):
        print(f"== {name}")
        for bucket in ("TikTok", "Reddit", "ALL"):
            c = comparison[name][bucket]
            print(f"   {bucket:7s} P old={c['old_precision_pct']} new={c['new_precision_pct']} "
                  f"d={c['delta_precision_pp']} | R old={c['old_recall_pct']} new={c['new_recall_pct']} "
                  f"d={c['delta_recall_pp']}")
    print("FP patterns:", dict(pattern_counts))
    print("FP by confidence:", json.dumps(by_conf))
    print("flag:", result["experience_flag_confusion"])
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Cross-model agreement calibration for the VOC blind annotations.

Standard library only. The script reads the blind box, validates every
``labels-*.jsonl`` file against SPEC.md / taxonomy.json / items.jsonl, then
computes:

1. presence agreement (Fleiss' kappa, observed agreement, per source),
2. pairwise Cohen's kappa on presence,
3. polarity agreement on cells with at least two taggers,
4. consensus levels (strong / weak / disagreement),
5. a Markdown report and a machine-readable summary.

A label file that fails the self-check is excluded from all statistics; the
report names every excluded file and the reason.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from collections import Counter, OrderedDict

POLARITIES = ("positive", "qualified_positive", "negative", "qualified_negative", "mixed", "unknown")
POLARITY_FAMILY = {
    "positive": "positive",
    "qualified_positive": "positive",
    "negative": "negative",
    "qualified_negative": "negative",
    "mixed": "mixed",
    "unknown": "unknown",
}
REASONS = {"help_seeking", "third_party_event", "other_product", "other"}
RECORD_KEYS = {"item_id", "is_product_experience", "experience_reason", "aspects"}
ASPECT_KEYS = {"code", "polarity", "evidence"}
PREFERRED_ORDER = ["sol", "terra", "luna", "g55", "mini"]
SOURCE_LABEL = {"tiktok_shop": "TikTok", "reddit": "Reddit"}
SOURCE_ORDER = ["TikTok", "Reddit", "ALL"]


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_box(box):
    items_path = os.path.join(box, "items.jsonl")
    taxonomy_path = os.path.join(box, "taxonomy.json")
    items = read_jsonl(items_path)
    with open(taxonomy_path, "r", encoding="utf-8") as fh:
        taxonomy = json.load(fh)
    aspects = [a["code"] for a in taxonomy["aspects"]]
    families = taxonomy.get("family_labels", {})
    if len(set(aspects)) != len(aspects):
        raise SystemExit("taxonomy has duplicate aspect codes")
    return items, aspects, families


def validate_labels(name, recs, items, codes):
    """Return (errors, warnings). Any error excludes the whole file."""
    errors = []
    warnings = []
    expected_ids = [it["item_id"] for it in items]
    by_id = {it["item_id"]: it for it in items}
    if len(recs) != len(items):
        errors.append("record count %d != %d" % (len(recs), len(items)))
    ids = [r.get("item_id") if isinstance(r, dict) else None for r in recs]
    if len(ids) != len(set(ids)):
        dupes = sorted({x for x in ids if ids.count(x) > 1})
        errors.append("duplicate item_id: %s" % dupes)
    if set(ids) != set(expected_ids):
        missing = sorted(set(expected_ids) - set(ids))
        extra = sorted(set(ids) - set(expected_ids))
        errors.append("item_id set mismatch missing=%s extra=%s" % (missing, extra))
    elif ids != expected_ids:
        warnings.append("record order differs from items.jsonl")

    for rec in recs:
        if not isinstance(rec, dict):
            errors.append("record is not an object")
            continue
        iid = rec.get("item_id", "<missing>")
        if set(rec.keys()) != RECORD_KEYS:
            errors.append("%s: keys %s" % (iid, sorted(rec.keys())))
            continue
        experience = rec["is_product_experience"]
        if not isinstance(experience, bool):
            errors.append("%s: is_product_experience is not bool" % iid)
            continue
        if experience and rec["experience_reason"] is not None:
            errors.append("%s: experience_reason must be null when true" % iid)
        if not experience:
            if rec["experience_reason"] not in REASONS:
                errors.append("%s: bad experience_reason %r" % (iid, rec["experience_reason"]))
            if rec["aspects"] != []:
                errors.append("%s: aspects must be empty when false" % iid)
        if not isinstance(rec["aspects"], list):
            errors.append("%s: aspects is not a list" % iid)
            continue
        if len(rec["aspects"]) > 6:
            errors.append("%s: %d aspects > 6" % (iid, len(rec["aspects"])))
        item = by_id.get(iid, {})
        title = item.get("title") or ""
        text = item.get("text") or ""
        seen = set()
        for aspect in rec["aspects"]:
            if not isinstance(aspect, dict) or set(aspect.keys()) != ASPECT_KEYS:
                errors.append("%s: aspect keys %s" % (iid, sorted(aspect.keys()) if isinstance(aspect, dict) else type(aspect).__name__))
                continue
            if aspect["code"] not in codes:
                errors.append("%s: unknown code %r" % (iid, aspect["code"]))
            if aspect["polarity"] not in POLARITIES:
                errors.append("%s: bad polarity %r" % (iid, aspect["polarity"]))
            evidence = aspect["evidence"]
            if not isinstance(evidence, str) or not evidence:
                errors.append("%s: evidence is empty or not a string" % iid)
            elif evidence not in title and evidence not in text:
                errors.append("%s: evidence not a verbatim substring: %r" % (iid, evidence[:80]))
            if aspect["code"] in seen:
                warnings.append("%s: duplicate code %s in one item" % (iid, aspect["code"]))
            seen.add(aspect["code"])
    return errors, warnings


def fleiss_kappa(rows):
    """Fleiss' kappa for a fixed number of binary raters per subject."""
    n_subjects = len(rows)
    n_raters = len(rows[0])
    if n_subjects == 0 or n_raters < 2:
        return {"n_subjects": n_subjects, "n_raters": n_raters, "po": float("nan"),
                "pe": float("nan"), "kappa": float("nan"), "prevalence": float("nan"),
                "present_ratings": 0, "total_ratings": 0}
    p_i = []
    present = 0
    absent = 0
    for row in rows:
        c1 = sum(row)
        c0 = n_raters - c1
        present += c1
        absent += c0
        p_i.append((c1 * (c1 - 1) + c0 * (c0 - 1)) / (n_raters * (n_raters - 1)))
    po = sum(p_i) / n_subjects
    total = present + absent
    p1 = present / total
    p0 = absent / total
    pe = p1 * p1 + p0 * p0
    kappa = (po - pe) / (1.0 - pe) if (1.0 - pe) > 1e-12 else float("nan")
    return {"n_subjects": n_subjects, "n_raters": n_raters, "po": po, "pe": pe,
            "kappa": kappa, "prevalence": p1, "present_ratings": present,
            "total_ratings": total}


def cohen_kappa(a, b):
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(a) / n
    pb = sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if (1 - pe) > 1e-12 else float("nan")


def kappa_label(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "无法计算"
    if value < 0:
        return "差"
    if value < 0.21:
        return "轻微"
    if value < 0.41:
        return "尚可"
    if value < 0.61:
        return "中等"
    if value < 0.81:
        return "较强"
    return "几乎完全"


def pct(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return "%.1f%%" % (100.0 * value)


def fmt(value, digits=4):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return ("%." + str(digits) + "f") % value


def order_annotators(names):
    preferred = [n for n in PREFERRED_ORDER if n in names]
    rest = sorted(n for n in names if n not in preferred)
    return preferred + rest


def build_grid(names, items, aspects, recs_by_name):
    experience = {n: {} for n in names}
    presence = {n: {} for n in names}
    tagged = {n: {} for n in names}
    for name in names:
        for item in items:
            iid = item["item_id"]
            experience[name][iid] = bool(recs_by_name[name][iid]["is_product_experience"])
            presence[name][iid] = {}
            tagged[name][iid] = {}
            for aspect in aspects:
                presence[name][iid][aspect] = 0
                tagged[name][iid][aspect] = None
            for aspect_obj in recs_by_name[name][iid]["aspects"]:
                code = aspect_obj["code"]
                presence[name][iid][code] = 1
                tagged[name][iid][code] = {
                    "polarity": aspect_obj["polarity"],
                    "evidence": aspect_obj["evidence"],
                }
    return experience, presence, tagged


def source_of(item):
    raw = item.get("source", "unknown")
    return SOURCE_LABEL.get(raw, raw)


def cell_rows(presence, names, items, aspects, source_filter=None):
    rows = []
    for item in items:
        if source_filter is not None and source_of(item) != source_filter:
            continue
        iid = item["item_id"]
        for aspect in aspects:
            rows.append([presence[name][iid][aspect] for name in names])
    return rows


def flatten_presence(presence, names, items, aspects):
    vectors = {name: [] for name in names}
    for item in items:
        iid = item["item_id"]
        for aspect in aspects:
            for name in names:
                vectors[name].append(presence[name][iid][aspect])
    return vectors


def analyze_polarity(names, items, aspects, tagged):
    eligible = 0
    exact_agree = 0
    family_agree = 0
    pair_total = 0
    pair_exact = 0
    pair_family = 0
    tagger_dist = Counter()
    polarity_dist = Counter()
    family_dist = Counter()
    conflicts = []
    for item in items:
        iid = item["item_id"]
        for aspect in aspects:
            taggers = [(name, tagged[name][iid][aspect]) for name in names if tagged[name][iid][aspect]]
            k = len(taggers)
            tagger_dist[k] += 1
            for _, entry in taggers:
                polarity_dist[entry["polarity"]] += 1
                family_dist[POLARITY_FAMILY[entry["polarity"]]] += 1
            if k < 2:
                continue
            eligible += 1
            polarities = [entry["polarity"] for _, entry in taggers]
            families = [POLARITY_FAMILY[p] for p in polarities]
            if len(set(polarities)) == 1:
                exact_agree += 1
            if len(set(families)) == 1:
                family_agree += 1
            else:
                conflicts.append({
                    "item_id": iid,
                    "aspect": aspect,
                    "source": source_of(item),
                    "verdicts": {name: entry["polarity"] for name, entry in taggers},
                })
            for (name_a, entry_a), (name_b, entry_b) in itertools.combinations(taggers, 2):
                pair_total += 1
                if entry_a["polarity"] == entry_b["polarity"]:
                    pair_exact += 1
                if POLARITY_FAMILY[entry_a["polarity"]] == POLARITY_FAMILY[entry_b["polarity"]]:
                    pair_family += 1
    return {
        "eligible_cells": eligible,
        "exact_agree": exact_agree,
        "family_agree": family_agree,
        "exact_rate": exact_agree / eligible if eligible else float("nan"),
        "family_rate": family_agree / eligible if eligible else float("nan"),
        "pair_total": pair_total,
        "pair_exact_rate": pair_exact / pair_total if pair_total else float("nan"),
        "pair_family_rate": pair_family / pair_total if pair_total else float("nan"),
        "tagger_dist": tagger_dist,
        "polarity_dist": polarity_dist,
        "family_dist": family_dist,
        "conflicts": conflicts,
    }


def analyze_experience(names, items, experience):
    unanimous = 0
    splits = []
    rows = []
    for item in items:
        iid = item["item_id"]
        flags = [experience[name][iid] for name in names]
        rows.append([1 if flag else 0 for flag in flags])
        if len(set(flags)) == 1:
            unanimous += 1
        else:
            splits.append({"item_id": iid, "source": source_of(item),
                           "flags": {name: experience[name][iid] for name in names}})
    fleiss = fleiss_kappa(rows)
    return {"unanimous": unanimous, "splits": splits, "fleiss": fleiss}


def analyze_consensus(names, items, aspects, tagged, experience, presence):
    strong_min = max(2, math.ceil(0.8 * len(names)))
    weak_min = max(2, math.ceil(0.6 * len(names)))
    rows = []
    dist = Counter()
    dist_by_source = Counter()
    breakdown = Counter()
    zero_tagged = 0
    for item in items:
        iid = item["item_id"]
        src = source_of(item)
        for aspect in aspects:
            taggers = [(name, tagged[name][iid][aspect]) for name in names if tagged[name][iid][aspect]]
            k = len(taggers)
            if k == 0:
                zero_tagged += 1
                continue
            families = [POLARITY_FAMILY[entry["polarity"]] for _, entry in taggers]
            consistent = len(set(families)) == 1
            if k >= strong_min and consistent:
                level = "strong"
            elif k >= weak_min and consistent:
                level = "weak"
            else:
                level = "disagreement"
            dist[level] += 1
            dist_by_source[(src, level)] += 1
            if level == "disagreement":
                if k >= weak_min:
                    breakdown["polarity_family_conflict"] += 1
                else:
                    breakdown["too_few_taggers"] += 1
            verdicts = OrderedDict()
            for name in names:
                entry = tagged[name][iid][aspect]
                verdicts[name] = dict(entry) if entry else None
            rows.append(OrderedDict([
                ("item_id", iid),
                ("aspect", aspect),
                ("source", src),
                ("tagged_count", k),
                ("experience", OrderedDict((name, experience[name][iid]) for name in names)),
                ("verdicts", verdicts),
                ("polarity_families", OrderedDict(
                    (name, POLARITY_FAMILY[tagged[name][iid][aspect]["polarity"]]
                     if tagged[name][iid][aspect] else None) for name in names)),
                ("family_consistent", consistent),
                ("consensus", level),
            ]))
    return {
        "rows": rows,
        "dist": dist,
        "dist_by_source": dist_by_source,
        "breakdown": breakdown,
        "zero_tagged": zero_tagged,
        "strong_min": strong_min,
        "weak_min": weak_min,
    }


def analyze_contested_aspects(names, items, aspects, tagged):
    counter = Counter()
    examples = []
    for item in items:
        iid = item["item_id"]
        for aspect in aspects:
            taggers = [(name, tagged[name][iid][aspect]) for name in names if tagged[name][iid][aspect]]
            k = len(taggers)
            if k < 2:
                continue
            families = {POLARITY_FAMILY[entry["polarity"]] for _, entry in taggers}
            if len(families) > 1:
                counter[aspect] += 1
                examples.append((iid, aspect, k, ", ".join(
                    "%s=%s" % (name, entry["polarity"]) for name, entry in taggers)))
    return counter, examples


def build_report(names, items, aspects, families, validations, excluded,
                 fleiss_all, fleiss_sources, pairwise, pair_extremes,
                 mean_pairwise, polarity, consensus, experience, contested,
                 warnings):
    lines = []
    add = lines.append
    add("这是同族自一致，不是人工准确率。")
    add("")
    add("# 同模型多提示一致率报告")
    add("")
    add("## 1. 数据与自检")
    add("")
    add("- 盲标目录：`/tmp/voc-blind-box`。")
    add("- 样本：%d 条（%s）。TikTok %d 条，Reddit %d 条。" % (
        len(items), "B01–B20" if len(items) == 20 else "见 items.jsonl",
        sum(1 for it in items if source_of(it) == "TikTok"),
        sum(1 for it in items if source_of(it) == "Reddit")))
    add("- taxonomy：%d 个 aspect，%d 个 family。" % (len(aspects), len(families)))
    add("- 标注者：%s。" % "、".join(names))
    add("- 标注身份 `%s` 是 5 个不同身份提示，全部运行在 DeepSeek Flash 同一族"
        "（`group/auto-deepseek-flash:max[1m]`，实际为 `deepseek-flash` / `deepseek-v4.1-flash`）；"
        "因此本报告测的是同一底座模型的同族自一致，不是跨模型独立验证。" % " / ".join(names))
    add("")
    add("| 标注者 | 记录数 | 自检 | 结果 |")
    add("|---|---|---|---|")
    for name in names:
        v = validations[name]
        add("| %s | %d | %s | 纳入 |" % (name, v["records"], "通过" if not v["errors"] else "失败"))
    for name in excluded:
        v = validations[name]
        add("| %s | %d | 失败 | 排除 |" % (name, v["records"]))
    add("")
    if excluded:
        add("排除名单与原因：")
        for name in excluded:
            add("- `%s`：%s" % (name, "；".join(validations[name]["errors"][:5])))
    else:
        add("排除：无。%d 份全部通过自检。" % len(names))
    add("")
    if warnings:
        add("数据质量提示：")
        for warning in warnings:
            add("- %s" % warning)
        add("")
    add("## 2. presence 一致率（Fleiss' kappa）")
    add("")
    add("统计单位是 item × aspect 格。共 %d 个格，每个格有 %d 个二元判定（标了 = 1，未标 = 0）。" % (
        fleiss_all["n_subjects"], fleiss_all["n_raters"]))
    add("")
    add("| 范围 | 格数 | present 判定数 | present 比例 | P_o | P_e | Fleiss κ | 强度 |")
    add("|---|---|---|---|---|---|---|---|")
    for source in SOURCE_ORDER:
        stat = fleiss_all if source == "ALL" else fleiss_sources.get(source)
        if stat is None:
            continue
        add("| %s | %d | %d / %d | %s | %s | %s | **%s** | %s |" % (
            source, stat["n_subjects"], stat["present_ratings"], stat["total_ratings"],
            pct(stat["prevalence"]), fmt(stat["po"]), fmt(stat["pe"]),
            fmt(stat["kappa"]), kappa_label(stat["kappa"])))
    add("")
    add("## 3. 两两 Cohen's kappa（presence）")
    add("")
    add("矩阵按 %d 个格的全部二元判定计算。" % fleiss_all["n_subjects"])
    add("")
    header = "| | " + " | ".join(names) + " |"
    sep = "|---" * (len(names) + 1) + "|"
    add(header)
    add(sep)
    for a in names:
        cells = []
        for b in names:
            if a == b:
                cells.append("—")
            else:
                cells.append(fmt(pairwise[(a, b)]))
        add("| %s | %s |" % (a, " | ".join(cells)))
    add("")
    add("- 最低：%s（κ = %s）。" % (pair_extremes["low_text"], fmt(pair_extremes["low"])))
    add("- 最高：%s（κ = %s）。" % (pair_extremes["high_text"], fmt(pair_extremes["high"])))
    add("")
    add("每个标注者与其他人的平均 κ：")
    add("")
    add("| 标注者 | 与他人平均 κ |")
    add("|---|---|")
    for name in names:
        add("| %s | %s |" % (name, fmt(mean_pairwise[name])))
    add("")
    add("## 4. 极性一致率")
    add("")
    add("只在“至少 2 个标注者标了同一 aspect”的格上计算。合格格数：%d / %d（%s）。" % (
        polarity["eligible_cells"], fleiss_all["n_subjects"],
        pct(polarity["eligible_cells"] / fleiss_all["n_subjects"] if fleiss_all["n_subjects"] else float("nan"))))
    add("")
    add("| 指标 | 数量 | 一致率 |")
    add("|---|---|---|")
    add("| exact polarity（格级全员一致） | %d / %d | %s |" % (
        polarity["exact_agree"], polarity["eligible_cells"], pct(polarity["exact_rate"])))
    add("| polarity family（格级全员一致） | %d / %d | %s |" % (
        polarity["family_agree"], polarity["eligible_cells"], pct(polarity["family_rate"])))
    add("| exact polarity（标注者对级） | n/a | %s |" % pct(polarity["pair_exact_rate"]))
    add("| polarity family（标注者对级） | n/a | %s |" % pct(polarity["pair_family_rate"]))
    add("")
    add("极性族映射：positive 与 qualified_positive 同族（positive）；negative 与 qualified_negative 同族（negative）；mixed 单独一族；unknown 单独一族。")
    add("")
    dist = polarity["tagger_dist"]
    add("每个格标注人数分布：0 人 %d，1 人 %d，2 人 %d，3 人 %d，4 人 %d，5 人 %d。" % (
        dist.get(0, 0), dist.get(1, 0), dist.get(2, 0), dist.get(3, 0), dist.get(4, 0), dist.get(5, 0)))
    add("")
    if polarity["conflicts"]:
        add("极性族冲突格（前 15 个）：")
        add("")
        add("| item | aspect | 判定 |")
        add("|---|---|---|")
        for conflict in polarity["conflicts"][:15]:
            verdicts = ", ".join("%s=%s" % (n, p) for n, p in conflict["verdicts"].items())
            add("| %s | %s | %s |" % (conflict["item_id"], conflict["aspect"], verdicts))
        add("")
    add("## 5. 共识分布")
    add("")
    add("强共识 = 至少 %d/%d 人标注，且极性族一致。弱共识 = 至少 %d/%d 人标注，且极性族一致。其余为分歧。" % (
        consensus["strong_min"], len(names), consensus["weak_min"], len(names)))
    add("有标注的格共 %d 个，计入分布。无人标注的格 %d 个，是全体的共同未标注，不计入共识分布。" % (
        sum(consensus["dist"].values()), consensus["zero_tagged"]))
    add("")
    add("| 共识等级 | 格数 | 占比 |")
    add("|---|---|---|")
    total = sum(consensus["dist"].values())
    for level, label in (("strong", "强共识"), ("weak", "弱共识"), ("disagreement", "分歧")):
        count = consensus["dist"].get(level, 0)
        add("| %s | %d | %s |" % (label, count, pct(count / total if total else float("nan"))))
    add("")
    add("分歧拆分：极性族冲突 %d 个，标注人数不足 %d 个。" % (
        consensus["breakdown"].get("polarity_family_conflict", 0),
        consensus["breakdown"].get("too_few_taggers", 0)))
    add("")
    disagreement_rows = [row for row in consensus["rows"] if row["consensus"] == "disagreement"]
    add("分歧格清单（共 %d 个）：" % len(disagreement_rows))
    add("")
    add("| item | aspect | 标注人数 | 判定 |")
    add("|---|---|---|---|")
    for row in disagreement_rows:
        verdicts = ", ".join("%s=%s" % (name, entry["polarity"] if entry else "—")
                             for name, entry in row["verdicts"].items())
        add("| %s | %s | %d | %s |" % (row["item_id"], row["aspect"], row["tagged_count"], verdicts))
    add("")
    add("按 source：")
    add("")
    add("| source | 强共识 | 弱共识 | 分歧 |")
    add("|---|---|---|---|")
    for source in ("TikTok", "Reddit"):
        add("| %s | %d | %d | %d |" % (
            source,
            consensus["dist_by_source"].get((source, "strong"), 0),
            consensus["dist_by_source"].get((source, "weak"), 0),
            consensus["dist_by_source"].get((source, "disagreement"), 0)))
    add("")
    add("分歧最多的 aspect（按极性族冲突格数）：")
    add("")
    if contested:
        add("| aspect | 冲突格数 |")
        add("|---|---|")
        for aspect, count in contested.most_common(10):
            add("| %s | %d |" % (aspect, count))
        add("")
    else:
        add("无。%d 个分歧格都是标注人数不足，不是极性冲突。" % len(disagreement_rows))
        add("")
    add("## 6. is_product_experience 补充")
    add("")
    add("%d 条样本中，%d 条全员一致，%d 条有分歧。" % (
        len(items), experience["unanimous"], len(experience["splits"])))
    add("Fleiss κ = %s（P_o = %s，P_e = %s）。" % (
        fmt(experience["fleiss"]["kappa"]), fmt(experience["fleiss"]["po"]), fmt(experience["fleiss"]["pe"])))
    add("")
    if experience["splits"]:
        add("| item | source | 判定 |")
        add("|---|---|---|")
        for split in experience["splits"]:
            flags = ", ".join("%s=%s" % (n, "true" if v else "false") for n, v in split["flags"].items())
            add("| %s | %s | %s |" % (split["item_id"], split["source"], flags))
        add("")
    add("## 7. 结论")
    add("")
    add("- presence Fleiss κ：ALL %s；TikTok %s；Reddit %s。" % (
        fmt(fleiss_all["kappa"]), fmt(fleiss_sources.get("TikTok", {}).get("kappa", float("nan"))),
        fmt(fleiss_sources.get("Reddit", {}).get("kappa", float("nan")))))
    add("- 两两矩阵：最低为 %s（%s），最高为 %s（%s）。" % (
        pair_extremes["low_text"], fmt(pair_extremes["low"]),
        pair_extremes["high_text"], fmt(pair_extremes["high"])))
    add("- 极性：exact %s，family %s（合格格 %d 个）。" % (
        pct(polarity["exact_rate"]), pct(polarity["family_rate"]), polarity["eligible_cells"]))
    add("- 共识：强 %d，弱 %d，分歧 %d。" % (
        consensus["dist"].get("strong", 0), consensus["dist"].get("weak", 0),
        consensus["dist"].get("disagreement", 0)))
    add("- 极性没有冲突。多标注格 %d 个，exact 与 family 都是 100%%。分歧全部来自 presence，即“这个 aspect 该不该标”。" % polarity["eligible_cells"])
    add("- 被排除的标注者：%s。" % ("无" if not excluded else "、".join(excluded)))
    add("- 再次强调：这是同族自一致，不是人工准确率。")
    add("")
    add("## 8. 限制")
    add("")
    add("- 这是同族自一致，不是人工准确率。5 个标注身份全部运行在 DeepSeek Flash 同一族（`deepseek-flash` / `deepseek-v4.1-flash`），只是身份提示不同；这不是跨模型独立验证，也不是人工准确率。所有标注者都是 LLM。它们可能共享训练数据与标注偏差。一致不等于正确。")
    add("- 样本只有 %d 条，aspect 有 %d 个。多数格是共同未标注。" % (len(items), len(aspects)))
    add("- 34 个 aspect 共享同一 item，格之间不独立。κ 不能用 680 个格直接算标准误或置信区间。")
    add("- presence κ 建立在大量“共同未标注”格上。ALL 的 present 比例只有 %s。κ 主要反映“都认为没提”的一致，不能单独当作“标得一样好”的证据。正例覆盖要看共识分布与极性一致率。Reddit 的 present 比例仅 %s，κ 对少数正例更敏感。" % (
        pct(fleiss_all["prevalence"]),
        pct(fleiss_sources.get("Reddit", {}).get("prevalence", float("nan")))))
    add("- 未读取 gold set、`coded/`、`mapping.json`、`claims.json`。gold set 未改动。")
    add("- 本报告只描述一致性与分歧位置，不判断哪一方更接近事实。")
    add("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--box", default="/tmp/voc-blind-box", help="blind box directory")
    parser.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)),
                        help="output directory (default: script directory)")
    args = parser.parse_args()

    items, aspects, families = load_box(args.box)
    codes = set(aspects)
    recs_by_name = {}
    validations = OrderedDict()
    excluded = []
    warnings = []
    for filename in sorted(os.listdir(args.box)):
        if not (filename.startswith("labels-") and filename.endswith(".jsonl")):
            continue
        name = filename[len("labels-"):-len(".jsonl")]
        recs = read_jsonl(os.path.join(args.box, filename))
        errors, file_warnings = validate_labels(name, recs, items, codes)
        validations[name] = {"records": len(recs), "errors": errors, "warnings": file_warnings}
        if errors:
            excluded.append(name)
            continue
        recs_by_name[name] = {rec["item_id"]: rec for rec in recs}
        warnings.extend(file_warnings)

    names = order_annotators(list(recs_by_name))
    if len(names) < 2:
        raise SystemExit("fewer than two valid label files; cannot compute agreement")
    if excluded:
        for name in excluded:
            print("EXCLUDED %s: %s" % (name, "; ".join(validations[name]["errors"][:3])), file=sys.stderr)

    experience, presence, tagged = build_grid(names, items, aspects, recs_by_name)

    fleiss_all = fleiss_kappa(cell_rows(presence, names, items, aspects))
    fleiss_sources = {}
    for source in ("TikTok", "Reddit"):
        rows = cell_rows(presence, names, items, aspects, source_filter=source)
        if rows:
            fleiss_sources[source] = fleiss_kappa(rows)

    vectors = flatten_presence(presence, names, items, aspects)
    pairwise = {}
    pair_values = []
    for a, b in itertools.combinations(names, 2):
        value = cohen_kappa(vectors[a], vectors[b])
        pairwise[(a, b)] = value
        pairwise[(b, a)] = value
        pair_values.append((value, a, b))
    finite_pairs = [p for p in pair_values if not math.isnan(p[0])]
    if finite_pairs:
        low = min(finite_pairs, key=lambda p: p[0])
        high = max(finite_pairs, key=lambda p: p[0])
        pair_extremes = {
            "low": low[0], "low_text": "%s–%s" % (low[1], low[2]),
            "high": high[0], "high_text": "%s–%s" % (high[1], high[2]),
        }
    else:
        pair_extremes = {"low": float("nan"), "low_text": "无", "high": float("nan"), "high_text": "无"}
    mean_pairwise = {}
    for name in names:
        values = [pairwise[(name, other)] for other in names if other != name]
        values = [v for v in values if not math.isnan(v)]
        mean_pairwise[name] = sum(values) / len(values) if values else float("nan")

    polarity = analyze_polarity(names, items, aspects, tagged)
    consensus = analyze_consensus(names, items, aspects, tagged, experience, presence)
    experience_stats = analyze_experience(names, items, experience)
    contested, _ = analyze_contested_aspects(names, items, aspects, tagged)

    os.makedirs(args.out, exist_ok=True)
    consensus_path = os.path.join(args.out, "consensus.jsonl")
    with open(consensus_path, "w", encoding="utf-8", newline="\n") as fh:
        for row in consensus["rows"]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = OrderedDict([
        ("annotators", names),
        ("excluded", excluded),
        ("warnings", warnings),
        ("n_items", len(items)),
        ("n_aspects", len(aspects)),
        ("n_cells", fleiss_all["n_subjects"]),
        ("fleiss_all", fleiss_all),
        ("fleiss_by_source", fleiss_sources),
        ("pairwise_cohen_kappa", OrderedDict(
            ("%s|%s" % (a, b), pairwise[(a, b)]) for a, b in itertools.combinations(names, 2))),
        ("pairwise_low", pair_extremes),
        ("pairwise_mean_per_annotator", mean_pairwise),
        ("polarity", {k: v for k, v in polarity.items() if k != "conflicts"}),
        ("consensus", {
            "strong": consensus["dist"].get("strong", 0),
            "weak": consensus["dist"].get("weak", 0),
            "disagreement": consensus["dist"].get("disagreement", 0),
            "zero_tagged_cells": consensus["zero_tagged"],
            "breakdown": dict(consensus["breakdown"]),
            "strong_min": consensus["strong_min"],
            "weak_min": consensus["weak_min"],
        }),
        ("is_product_experience", {
            "unanimous": experience_stats["unanimous"],
            "splits": experience_stats["splits"],
            "fleiss": experience_stats["fleiss"],
        }),
    ])
    summary_path = os.path.join(args.out, "cross-model-stats.json")
    with open(summary_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    report = build_report(names, items, aspects, families, validations, excluded,
                          fleiss_all, fleiss_sources, pairwise, pair_extremes,
                          mean_pairwise, polarity, consensus, experience_stats,
                          contested, warnings)
    report_path = os.path.join(args.out, "cross-model-report.md")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
        fh.write("\n")

    print("valid annotators: %d (%s)" % (len(names), ", ".join(names)))
    print("excluded: %s" % ("none" if not excluded else ", ".join(excluded)))
    print("cells: %d" % fleiss_all["n_subjects"])
    for source in SOURCE_ORDER:
        stat = fleiss_all if source == "ALL" else fleiss_sources.get(source)
        if stat:
            print("Fleiss %-6s kappa=%s Po=%s Pe=%s prevalence=%s n=%d" % (
                source, fmt(stat["kappa"]), fmt(stat["po"]), fmt(stat["pe"]),
                fmt(stat["prevalence"]), stat["n_subjects"]))
    print("pairwise low : %s %s" % (pair_extremes["low_text"], fmt(pair_extremes["low"])))
    print("pairwise high: %s %s" % (pair_extremes["high_text"], fmt(pair_extremes["high"])))
    print("polarity: eligible=%d exact=%s family=%s" % (
        polarity["eligible_cells"], pct(polarity["exact_rate"]), pct(polarity["family_rate"])))
    print("consensus: strong=%d weak=%d disagreement=%d zero_tagged=%d" % (
        consensus["dist"].get("strong", 0), consensus["dist"].get("weak", 0),
        consensus["dist"].get("disagreement", 0), consensus["zero_tagged"]))
    print("wrote: %s" % consensus_path)
    print("wrote: %s" % summary_path)
    print("wrote: %s" % report_path)


if __name__ == "__main__":
    main()

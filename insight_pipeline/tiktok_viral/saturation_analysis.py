#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞争饱和与空白分析
输入:
  deepread288.tsv                 288 条 deepread 爆款
  _si_tag_stats.tsv               392 个 tag 的采样池统计（raw.si_tiktok_video）
  _competitor_videos.tsv          9 个竞品账号 136 条去重视频
  _brand_snapshot_summary.tsv
  theme-clusters.json             993 theme -> 13 motif 映射
  mech-clusters.json              806 mechanism -> 10 family 映射
输出:
  saturation.json
只读数据，不改数据库。
"""
import csv
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "deepread288.tsv"
OUT = ROOT / "saturation.json"
COMP = ROOT / "_competitor_videos.tsv"
BRAND_SUMMARY = ROOT / "_brand_snapshot_summary.tsv"
TAG_STATS = ROOT / "_si_tag_stats.tsv"
THEME_CLUSTERS = ROOT / "theme-clusters.json"
MECH_CLUSTERS = ROOT / "mech-clusters.json"
GENERATED_AT = "2026-10-31"

SAMPLE_MIN = 8
CORPUS_MEDIAN_FULL = 2550000
CORPUS_MEDIAN_EX_HW = 2350000
POOL_MEDIAN = 21850

# ---------------------------------------------------------------- helpers
def percentile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def i(x):
    if x is None:
        return None
    return int(round(x))


def r4(x):
    if x is None:
        return None
    return round(x, 4)


def describe(vals):
    return {
        "n": len(vals),
        "median_play": i(statistics.median(vals)) if vals else None,
        "p25_play": i(percentile(vals, 0.25)),
        "p75_play": i(percentile(vals, 0.75)),
        "mean_play": i(sum(vals) / len(vals)) if vals else None,
        "max_play": max(vals) if vals else None,
    }


def sample_status(n):
    return "足够(n>=8)" if n >= SAMPLE_MIN else "样本不足(n<8)"


def fragility(n):
    if n < SAMPLE_MIN:
        return "样本不足"
    if n < 12:
        return "n 接近下限，结论脆弱"
    return "样本量可"


def wilson_lower(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (centre - margin) / denom


# ---------------------------------------------------------------- load corpus
rows = []
with open(SRC, encoding="utf-8") as f:
    for r in csv.reader(f, delimiter="\t"):
        rows.append({
            "video_id": r[0],
            "hashtag": r[1],
            "play": int(r[2]),
            "digg": int(r[3]),
            "comment": int(r[4]),
            "share": int(r[5]),
            "themes": json.loads(r[6]),
            "mechs": json.loads(r[7]),
            "descr": r[8],
        })
for r in rows:
    r["hw"] = any("万圣" in t for t in r["themes"])

N = len(rows)
ALL_PLAY = [r["play"] for r in rows]
CORPUS_MEDIAN_FULL = i(statistics.median(ALL_PLAY))
non_hw_rows = [r for r in rows if not r["hw"]]
N_NON_HW = len(non_hw_rows)
NON_HW_PLAY = [r["play"] for r in non_hw_rows]
CORPUS_MEDIAN_EX_HW = i(statistics.median(NON_HW_PLAY))

# ---------------------------------------------------------------- mappings
with open(THEME_CLUSTERS, encoding="utf-8") as f:
    tc = json.load(f)
with open(MECH_CLUSTERS, encoding="utf-8") as f:
    mc = json.load(f)

theme_motif = {k: v["motif"] for k, v in tc["mapping"].items()}
motif_names = {m["key"]: m["name"] for m in tc["motifs"]}
motif_keys = [m["key"] for m in tc["motifs"]]
mech_family = mc["mapping"]
family_names = {f["id"]: f["name"] for f in mc["families"]}
family_keys = [f["id"] for f in mc["families"]]

for r in rows:
    r["motif_set"] = set(theme_motif[t] for t in r["themes"])
    r["family_set"] = set(mech_family[m] for m in r["mechs"])

# ---------------------------------------------------------------- corpus profile
tiers = {
    ">=1e8": sum(1 for p in ALL_PLAY if p >= 100000000),
    "1e7-1e8": sum(1 for p in ALL_PLAY if 10000000 <= p < 100000000),
    "1e6-1e7": sum(1 for p in ALL_PLAY if 1000000 <= p < 10000000),
    "<1e6": sum(1 for p in ALL_PLAY if p < 1000000),
}
motif_memberships = Counter(len(r["motif_set"]) for r in rows)
theme_counts = Counter(t for r in rows for t in r["themes"])
mech_counts = Counter(m for r in rows for m in r["mechs"])

corpus_profile = {
    "n_videos": N,
    "play": {**describe(ALL_PLAY), "min_play": min(ALL_PLAY)},
    "play_tiers": tiers,
    "unique_hashtags": len({r["hashtag"] for r in rows}),
    "unique_theme_tags": len(theme_counts),
    "theme_tag_occurrences": sum(theme_counts.values()),
    "unique_mechanism_tags": len(mech_counts),
    "mechanism_tag_occurrences": sum(mech_counts.values()),
    "avg_themes_per_video": round(sum(len(r["themes"]) for r in rows) / N, 2),
    "avg_mechanisms_per_video": round(sum(len(r["mechs"]) for r in rows) / N, 2),
    "theme_frequency_once": sum(1 for v in theme_counts.values() if v == 1),
    "theme_frequency_once_share": r4(sum(1 for v in theme_counts.values() if v == 1) / len(theme_counts)),
    "mechanism_frequency_once": sum(1 for v in mech_counts.values() if v == 1),
    "mechanism_frequency_once_share": r4(sum(1 for v in mech_counts.values() if v == 1) / len(mech_counts)),
    "motif_memberships_per_video": {str(k): v for k, v in sorted(motif_memberships.items())},
    "halloween": {
        "n_videos": len([r for r in rows if r["hw"]]),
        "share": r4(len([r for r in rows if r["hw"]]) / N),
        "median_play": i(statistics.median([r["play"] for r in rows if r["hw"]])),
        "non_halloween_n": N_NON_HW,
        "non_halloween_median_play": CORPUS_MEDIAN_EX_HW,
    },
}

# ---------------------------------------------------------------- tag pool stats
pool = {}
with open(TAG_STATS, encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t", fieldnames=[
        "tag", "n", "med", "p25", "p75", "mx", "ge100k", "ge1m", "ge10m"
    ]):
        pool[r["tag"]] = {
            "pool_videos": int(r["n"]),
            "pool_median_play": i(float(r["med"])),
            "pool_p25_play": i(float(r["p25"])),
            "pool_p75_play": i(float(r["p75"])),
            "pool_max_play": int(r["mx"]),
            "pool_ge100k": int(r["ge100k"]),
            "pool_ge1m": int(r["ge1m"]),
            "pool_ge10m": int(r["ge10m"]),
        }

# ---------------------------------------------------------------- tag family rules
FAMILY_LABELS = {
    "halloween_seasonal": "万圣节/节日装扮",
    "newborn_pregnancy": "新生儿与孕产",
    "parenting_humor_trend": "育儿幽默与热点",
    "other_local": "其他/本地语言",
    "product_brand": "品牌与好物",
    "other_generic": "其他杂项",
    "school_routine": "上学/接送日常",
    "toddler_kid": "幼儿与儿童",
    "baby_cute": "萌娃可爱",
    "mom_identity": "妈妈身份",
    "ai_animation": "AI/动画",
    "feeding": "喂养",
    "vlog_lifestyle": "Vlog/生活方式",
}


def family_of(tag):
    s = tag.lower().lstrip("#")
    if any(k in s for k in ["halloween", "spooky", "boobasket", "boo basket",
                            "trick or treat", "costume", "october1st"]):
        return "halloween_seasonal"
    if any(k in s for k in ["beforeschool", "schoolpickup", "schooldropoff",
                            "schoolmorning", "afterschool", "скоровшколу", "backtoschool"]):
        return "school_routine"
    if any(k in s for k in ["newborn", "cryingbaby", "crybaby", "newparent",
                            "firsttimemom", "postpartum", "sleeptraining", "selfsoothing",
                            "hospitalstay", "birthplan", "pregnancy", "expectingmoms",
                            "momstobe", "kehamilan", "januarybaby"]):
        return "newborn_pregnancy"
    if any(k in s for k in ["toddler", "kidsteeth", "babyteeth", "potty",
                            "kidsoutfit", "biggirlroom", "sensorybin"]):
        return "toddler_kid"
    if any(k in s for k in ["breastfed", "bottlefeeding", "babybottles"]):
        return "feeding"
    if any(k in s for k in ["dyson", "fisherprice", "babylist", "walmart",
                            "wearableblanket", "babyessential", "giftideas", "giftsforkids",
                            "imaginationlibrary", "musicforkids", "momcozy"]):
        return "product_brand"
    if any(k in s for k in ["aibaby", "cartoon", "funnyanimation"]):
        return "ai_animation"
    if any(k in s for k in ["vlogtok", "morningvlogs", "familylife", "familymoments"]):
        return "vlog_lifestyle"
    if any(k in s for k in ["momsoftiktok", "mamastiktok", "boymom", "studentmom", "mommybaby"]):
        return "mom_identity"
    if any(k in s for k in ["cutebabies", "adorablebaby", "babycute", "babiesoftiktok",
                            "babyphotos", "babydancing", "babytime"]):
        return "baby_cute"
    if any(k in s for k in ["funnybaby", "momstruggles", "parenthood", "familytrend",
                            "ukfunny", "truce", "himm", "movements", "bounceit",
                            "viraltiktok", "freedurkioo", "ropadefrio", "tkb"]):
        return "parenting_humor_trend"
    if any(k in s for k in ["bayi", "bayilucu", "miprincesa", "vidademae", "mespatrio",
                            "hellokitty", "teddybear", "reborn", "pediatriccancer",
                            "sickkids", "quadruplets", "grandparentsday", "holidaycrafts",
                            "navidad"]):
        return "other_local"
    return "other_generic"


# ---------------------------------------------------------------- tag level
tag_rows = defaultdict(list)
for r in rows:
    tag_rows[r["hashtag"]].append(r)

tag_level = []
for tag, rs in tag_rows.items():
    plays = [r["play"] for r in rs]
    p = pool.get(tag, {})
    n = len(plays)
    med = i(statistics.median(plays))
    if n >= SAMPLE_MIN:
        cls = "饱和候选" if med < CORPUS_MEDIAN_FULL else "有空间候选"
    else:
        cls = "样本不足"
    item = {
        "tag": tag,
        "n_hits": n,
        "median_play": med,
        "median_minus_corpus": med - CORPUS_MEDIAN_FULL,
        "p25_play": i(percentile(plays, 0.25)),
        "p75_play": i(percentile(plays, 0.75)),
        "max_play": max(plays),
        "halloween_hits": sum(1 for r in rs if r["hw"]),
        "halloween_share": r4(sum(1 for r in rs if r["hw"]) / n),
        "pool_videos": p.get("pool_videos"),
        "pool_median_play": p.get("pool_median_play"),
        "hit_share_of_pool": r4(n / p["pool_videos"]) if p.get("pool_videos") else None,
        "sample_status": sample_status(n),
        "fragility": fragility(n),
        "classification": cls,
    }
    tag_level.append(item)

tag_level.sort(key=lambda x: (-x["n_hits"], -(x["median_play"] or 0)))

valid_tags = [t for t in tag_level if t["n_hits"] >= SAMPLE_MIN]
saturated_tags = [t for t in valid_tags if t["classification"] == "饱和候选"]
headroom_tags = [t for t in valid_tags if t["classification"] == "有空间候选"]
valid_tags_non_hw = [t for t in valid_tags if t["halloween_share"] < 1.0]

# directional watch list: n=5-7, explicitly sample-insufficient
watch_5_7 = [t for t in tag_level if 5 <= t["n_hits"] < SAMPLE_MIN]
watch_5_7_high = [t for t in watch_5_7 if t["median_play"] >= CORPUS_MEDIAN_FULL]
watch_5_7_low = [t for t in watch_5_7 if t["median_play"] < CORPUS_MEDIAN_FULL]

# descriptive correlation between tag pool size and deepread hit count
_pairs = [(t["pool_videos"], t["n_hits"]) for t in tag_level if t["pool_videos"]]
_x = [p[0] for p in _pairs]
_y = [p[1] for p in _pairs]
_mx = sum(_x) / len(_x)
_my = sum(_y) / len(_y)
_cov = sum((a - _mx) * (b - _my) for a, b in _pairs) / len(_pairs)
_r = _cov / (statistics.pstdev(_x) * statistics.pstdev(_y)) if _pairs else None
pool_hit_correlation = {
    "pearson_r": r4(_r),
    "n_tags": len(_pairs),
    "interpretation": "中等正相关；爆款数不是池大小的线性函数，且受 deepread 选取配额影响。",
}

# ---------------------------------------------------------------- tag family level
fam_rows = defaultdict(list)
for r in rows:
    fam_rows[family_of(r["hashtag"])].append(r)

family_level = []
for fam, rs in fam_rows.items():
    plays = [r["play"] for r in rs]
    ex_plays = [r["play"] for r in rs if not r["hw"]]
    tags = sorted({r["hashtag"] for r in rs})
    pool_videos = sum(pool[t]["pool_videos"] for t in tags if t in pool)
    pool_ge100k = sum(pool[t]["pool_ge100k"] for t in tags if t in pool)
    pool_ge1m = sum(pool[t]["pool_ge1m"] for t in tags if t in pool)
    n = len(plays)
    med = i(statistics.median(plays))
    ex_n = len(ex_plays)
    ex_med = i(statistics.median(ex_plays)) if ex_plays else None
    cls_full = ("饱和候选" if med < CORPUS_MEDIAN_FULL else "有空间候选") if n >= SAMPLE_MIN else "样本不足"
    if ex_n >= SAMPLE_MIN:
        cls_ex = "饱和候选" if ex_med < CORPUS_MEDIAN_EX_HW else "有空间候选"
    else:
        cls_ex = "样本不足"
    if cls_full == "样本不足":
        stability = "样本不足"
    elif cls_ex == "样本不足":
        stability = "去季节后样本不足"
    elif cls_full == cls_ex:
        stability = "方向稳定"
    else:
        stability = "去季节后翻转"
    if fam == "other_generic":
        interpretability = "归并残差，不用于结论"
    elif fam == "other_local":
        interpretability = "混合/本地语言，谨慎解读"
    else:
        interpretability = "可解读"
    family_level.append({
        "family": fam,
        "label": FAMILY_LABELS.get(fam, fam),
        "interpretability": interpretability,
        "n_hits": n,
        "median_play": med,
        "median_minus_corpus": med - CORPUS_MEDIAN_FULL,
        "p25_play": i(percentile(plays, 0.25)),
        "p75_play": i(percentile(plays, 0.75)),
        "max_play": max(plays),
        "ex_halloween_n": ex_n,
        "ex_halloween_median_play": ex_med,
        "ex_halloween_median_minus_corpus": (ex_med - CORPUS_MEDIAN_EX_HW) if ex_med is not None else None,
        "halloween_hits": sum(1 for r in rs if r["hw"]),
        "halloween_share": r4(sum(1 for r in rs if r["hw"]) / n),
        "n_tags": len(tags),
        "tags": tags,
        "pool_videos": pool_videos,
        "pool_ge100k": pool_ge100k,
        "pool_ge1m": pool_ge1m,
        "hit_share_of_pool": r4(n / pool_videos) if pool_videos else None,
        "sample_status": sample_status(n),
        "fragility": fragility(n),
        "classification_full": cls_full,
        "classification_ex_halloween": cls_ex,
        "stability": stability,
    })

family_level.sort(key=lambda x: -x["n_hits"])

# ---------------------------------------------------------------- component stats
def component_stats(subset, key, mapping, names, total_n, baseline_median):
    groups = defaultdict(list)
    for r in subset:
        for k in set(mapping(x) for x in r[key]):
            groups[k].append(r["play"])
    out = []
    for k, vals in groups.items():
        n = len(vals)
        med = i(statistics.median(vals))
        if n < SAMPLE_MIN:
            cls = "样本不足"
        else:
            cls = "高于语料中位" if med >= baseline_median else "低于语料中位"
        out.append({
            "key": k,
            "name": names.get(k, k),
            "n_videos": n,
            "share_of_corpus": r4(n / total_n),
            "median_play": med,
            "median_minus_corpus": med - baseline_median,
            "p25_play": i(percentile(vals, 0.25)),
            "p75_play": i(percentile(vals, 0.75)),
            "sample_status": sample_status(n),
            "vs_corpus_median": cls,
        })
    out.sort(key=lambda x: -x["n_videos"])
    return out


motif_stats_full = component_stats(
    rows, "themes", lambda t: theme_motif[t], motif_names, N, CORPUS_MEDIAN_FULL)
motif_stats_ex = component_stats(
    non_hw_rows, "themes", lambda t: theme_motif[t], motif_names, N_NON_HW, CORPUS_MEDIAN_EX_HW)
family_stats_full = component_stats(
    rows, "mechs", lambda m: mech_family[m], family_names, N, CORPUS_MEDIAN_FULL)
family_stats_ex = component_stats(
    non_hw_rows, "mechs", lambda m: mech_family[m], family_names, N_NON_HW, CORPUS_MEDIAN_EX_HW)

# ---------------------------------------------------------------- matrix
def build_matrix(subset, key_motif, key_family, baseline_median, total_n):
    mg = defaultdict(list)
    fg = defaultdict(list)
    sets = []
    for r in subset:
        A = set(key_motif(t) for t in r["themes"])
        B = set(key_family(m) for m in r["mechs"])
        sets.append((A, B, r["play"]))
        for a in A:
            mg[a].append(r["play"])
        for b in B:
            fg[b].append(r["play"])
    cells = []
    for a in motif_keys:
        for b in family_keys:
            vals = [p for A, B, p in sets if a in A and b in B]
            n = len(vals)
            exp = len(mg.get(a, [])) * len(fg.get(b, [])) / total_n if total_n else 0
            ratio = (n / exp) if exp else None
            med = i(statistics.median(vals)) if vals else None
            motif_med = i(statistics.median(mg[a])) if mg.get(a) else None
            fam_med = i(statistics.median(fg[b])) if fg.get(b) else None
            synergy = (med - max(motif_med, fam_med)
                       if med is not None and motif_med is not None and fam_med is not None else None)
            synergy_weak = (med - min(motif_med, fam_med)
                            if med is not None and motif_med is not None and fam_med is not None else None)
            below_both = (synergy_weak is not None and synergy_weak < 0)
            cells.append({
                "motif": a,
                "motif_name": motif_names.get(a, a),
                "family": b,
                "family_name": family_names.get(b, b),
                "n_videos": n,
                "expected_independence": r4(exp),
                "observed_over_expected": r4(ratio),
                "median_play": med,
                "motif_marginal_median": motif_med,
                "family_marginal_median": fam_med,
                "synergy_vs_best_component": synergy,
                "synergy_vs_weakest_component": synergy_weak,
                "below_both_components": below_both,
                "p25_play": i(percentile(vals, 0.25)) if vals else None,
                "p75_play": i(percentile(vals, 0.75)) if vals else None,
                "sample_status": sample_status(n),
                "fragility": fragility(n),
                "vs_corpus_median": (
                    "样本不足" if n < SAMPLE_MIN else
                    ("高于语料中位" if med >= baseline_median else "低于语料中位")
                ),
                "interpretation_note": (
                    "近义标签组合：motif 与 mechanism family 的标签定义高度重叠，共现高应视为标注定义的结果，不代表内容策略"
                    if (a, b) in (("diy", "F6"), ("seasonal", "F4")) else None
                ),
            })
    return cells, mg, fg


matrix_full, motif_marg_full, fam_marg_full = build_matrix(
    rows, lambda t: theme_motif[t], lambda m: mech_family[m], CORPUS_MEDIAN_FULL, N)
matrix_ex, motif_marg_ex, fam_marg_ex = build_matrix(
    non_hw_rows, lambda t: theme_motif[t], lambda m: mech_family[m],
    CORPUS_MEDIAN_EX_HW, N_NON_HW)

# red ocean: high usage and below corpus median (ex-Halloween primary)
red_ocean_ex = [
    c for c in matrix_ex
    if c["n_videos"] >= 20 and c["median_play"] is not None
    and c["median_play"] < CORPUS_MEDIAN_EX_HW
]
red_ocean_ex.sort(key=lambda c: (-c["n_videos"], c["median_play"]))

# stricter: cell median below BOTH component marginals -> the combination itself underperforms its own base
true_red_ocean_ex = [
    c for c in matrix_ex
    if c["n_videos"] >= 20 and c["below_both_components"]
]
true_red_ocean_ex.sort(key=lambda c: c["synergy_vs_weakest_component"])

# potential gaps: n>=8, observed below independence expectation, both components
# individually at/above the ex-Halloween corpus median
motif_med_ex = {s["key"]: s["median_play"] for s in motif_stats_ex}
fam_med_ex = {s["key"]: s["median_play"] for s in family_stats_ex}
gaps_ex = []
half_gaps_ex = []
watch_insufficient_ex = []
for c in matrix_ex:
    if c["observed_over_expected"] is None:
        continue
    both_ok = (motif_med_ex.get(c["motif"], 0) >= CORPUS_MEDIAN_EX_HW
               and fam_med_ex.get(c["family"], 0) >= CORPUS_MEDIAN_EX_HW)
    if c["n_videos"] >= SAMPLE_MIN and c["observed_over_expected"] < 0.85 and both_ok \
            and c["median_play"] is not None and c["median_play"] >= CORPUS_MEDIAN_EX_HW \
            and c["synergy_vs_best_component"] is not None and c["synergy_vs_best_component"] > 0:
        gaps_ex.append(c)
    elif c["n_videos"] >= SAMPLE_MIN and c["observed_over_expected"] < 0.85 and not both_ok:
        half_gaps_ex.append(c)
    if c["n_videos"] < SAMPLE_MIN and c["observed_over_expected"] < 0.5 and c["median_play"]:
        watch_insufficient_ex.append(c)
gaps_ex.sort(key=lambda c: c["observed_over_expected"])
half_gaps_ex.sort(key=lambda c: c["observed_over_expected"])
watch_insufficient_ex.sort(key=lambda c: -(c["median_play"] or 0))

high_payoff_ex = [
    c for c in matrix_ex
    if c["n_videos"] >= SAMPLE_MIN and c["median_play"] is not None
    and c["median_play"] >= 3500000
    and c["observed_over_expected"] is not None
    and c["observed_over_expected"] >= 0.85
]
high_payoff_ex.sort(key=lambda c: -c["median_play"])

# ---------------------------------------------------------------- tag-level matrix
themes_ge8 = [t for t, v in theme_counts.items() if v >= SAMPLE_MIN]
tag_cells = []
for theme in themes_ge8:
    sub = [r for r in rows if theme in r["themes"]]
    for fam in family_keys:
        vals = [r["play"] for r in sub if fam in r["family_set"]]
        n = len(vals)
        tag_cells.append({
            "theme_tag": theme,
            "theme_n": len(sub),
            "mechanism_family": fam,
            "mechanism_family_name": family_names.get(fam, fam),
            "n_videos": n,
            "median_play": i(statistics.median(vals)) if vals else None,
            "p25_play": i(percentile(vals, 0.25)) if vals else None,
            "p75_play": i(percentile(vals, 0.75)) if vals else None,
            "sample_status": sample_status(n),
        })
tag_cells_valid = [c for c in tag_cells if c["n_videos"] >= SAMPLE_MIN]
tag_cells_valid.sort(key=lambda c: (-c["n_videos"], -c["median_play"]))

# mechanism tags with n>=8
mech_ge8 = [{"mechanism_tag": m, "n_videos": c,
             "median_play": i(statistics.median([r["play"] for r in rows if m in r["mechs"]]))}
            for m, c in mech_counts.items() if c >= SAMPLE_MIN]
mech_ge8.sort(key=lambda x: -x["n_videos"])
theme_ge8_list = [{"theme_tag": t, "n_videos": c,
                   "median_play": i(statistics.median([r["play"] for r in rows if t in r["themes"]]))}
                  for t, c in theme_counts.items() if c >= SAMPLE_MIN]
theme_ge8_list.sort(key=lambda x: -x["n_videos"])

# exact tag-pair gap analysis (sparse)
exact_pairs = []
for t in themes_ge8:
    for m in [x["mechanism_tag"] for x in mech_ge8]:
        vals = [r["play"] for r in rows if t in r["themes"] and m in r["mechs"]]
        exp = len([r for r in rows if t in r["themes"]]) * len([r for r in rows if m in r["mechs"]]) / N
        exact_pairs.append({
            "theme_tag": t,
            "mechanism_tag": m,
            "n_videos": len(vals),
            "expected_independence": r4(exp),
            "median_play": i(statistics.median(vals)) if vals else None,
            "sample_status": sample_status(len(vals)),
        })
exact_pairs.sort(key=lambda x: (x["n_videos"], -(x["expected_independence"] or 0)))

# ---------------------------------------------------------------- competitors
comp_rows = []
with open(COMP, encoding="utf-8") as f:
    for r in csv.reader(f, delimiter="\t"):
        comp_rows.append({
            "brand_key": r[0],
            "video_id": r[1],
            "play": int(r[2]) if r[2] else 0,
            "digg": int(r[3]) if r[3] else 0,
            "comment": int(r[4]) if r[4] else 0,
            "share": int(r[5]) if r[5] else 0,
            "published_at": r[6],
            "is_ad": r[7] == "t",
            "descr": r[8],
        })

brand_summary = {}
with open(BRAND_SUMMARY, encoding="utf-8") as f:
    for r in csv.reader(f, delimiter="\t"):
        brand_summary[r[0]] = {
            "account_handle": r[1],
            "snapshot_rows": int(r[2]),
            "videos": int(r[3]),
            "date_from": r[4],
            "date_to": r[5],
            "ad_rows": int(r[6]),
        }

TOPIC_LABELS = {
    "product_offer": "产品卖点/购买",
    "feeding_pumping": "喂养/泵奶",
    "postpartum_newborn_care": "产后/新生儿护理",
    "identity_emotion": "身份/情绪",
    "humor": "幽默",
    "campaign_seasonal": "节点/公益",
    "education_tips": "知识/教程",
    "community_giveaway": "互动/活动/赠品",
    "lifestyle_routine": "日常/生活方式",
    "family_moment": "家庭时刻",
    "cute_baby": "萌娃",
    "visual_demo": "视觉演示/开箱",
}
TOPIC_COMPARABILITY = {
    "product_offer": (True, "话题词较直接；仍是 caption 代理"),
    "feeding_pumping": (True, "话题词较直接；与 care motif 部分对应"),
    "postpartum_newborn_care": (True, "话题词较直接；与 care motif 部分对应"),
    "identity_emotion": (True, "话题词较直接；仍是 caption 代理"),
    "humor": (True, "幽默标记较直接；但只能捕捉文本幽默"),
    "campaign_seasonal": (True, "节点/公益词较直接"),
    "education_tips": (False, "caption 只能捕捉显式教程词，份额是下限"),
    "community_giveaway": (False, "没有直接对应的 deepread motif，不参与超配/低配结论"),
    "lifestyle_routine": (True, "话题词较直接；仍是 caption 代理"),
    "family_moment": (True, "话题词较直接；仍是 caption 代理"),
    "cute_baby": (False, "caption 只能捕捉 cute/adorable 等显式词，份额是下限"),
    "visual_demo": (False, "caption 只能捕捉显式演示词，无法覆盖视觉机制，份额是下限"),
}
TOPIC_TO_MOTIF = {
    "product_offer": "product",
    "feeding_pumping": "care",
    "postpartum_newborn_care": "care",
    "identity_emotion": "identity",
    "humor": "comedy",
    "campaign_seasonal": "seasonal",
    "education_tips": "diy",
    "community_giveaway": "identity",
    "lifestyle_routine": "lifestyle",
    "family_moment": "family",
    "cute_baby": "cute",
    "visual_demo": "visual",
}
TOPIC_RULES = {
    "product_offer": r"link in bio|\bshop\b|\bbuy\b|\bgrab\b|available|coming soon|launch|gift set|registry|\bsale\b|discount|\bcode\b|% off|tiktok shop|get yours|now available|designed|engineered|bpa-free|3-in-1|hands-free|self-cleaning|one cycle",
    "feeding_pumping": r"breastfeed|pumping|\bpump\b|\bpumps\b|bottle feed|bottle-feeding|formula|breast ?milk|milk supply|latch|flange|output|colostrum|nursing|exclusive(?:ly)? pump|storage bag|\bmilk\b",
    "postpartum_newborn_care": r"postpartum|c-section|cesarean|peri bottle|perineal|recovery|hospital bag|newborn|sleep training|diaper|\bnasal\b|congestion|humidifier|teething|pacifier|steriliz|colic|reflux|sooth|infant",
    "identity_emotion": r"motherhood|\bmother\b|\bmama\b|\bwomen\b|\bright to\b|judgement|judgment|society|support|\bstrongest\b|deserve|\bcommunity\b|you are doing|you got this|all moms|girlhood|iconic|main character",
    "humor": r"😂|🤣|jokes aside|\bpov\b|we.ve all been there|mom brain|management said|never specified|what about this one|avengers|honestly\?|funny|humor|😭",
    "campaign_seasonal": r"halloween|spooky|costume|boo basket|christmas|holiday|prime ?day|black friday|internationalwomensday|breastfeedingawarenessmonth|worldbreastfeedingweek|nicu awareness month|back to (?:school|daycare)|back-to-daycare|world breastfeeding|#wbw|mom swap|awareness month",
    "education_tips": r"did you know|\btips?\b|how to\b|here are|reasons?\b|\bsteps?\b|guide|\blearn\b|myth|\bfact\b|follow these|save this|pro tip|checklist|hack|normal\b|you need to|explained|understanding",
    "community_giveaway": r"giveaway|\bcomment\b|\btag\b|share it|drop your|tell us|which one|win\b|winner|\bevent\b|swap|join us|where should we",
    "lifestyle_routine": r"morning|\broutine\b|day in|slow morning|\bhome\b|coffee|bedside|nursery|cozy|cosy|aesthetic|on the go|travel|out and about|weekend|evening|bedtime",
    "family_moment": r"\bpartner\b|\bdad\b|husband|family|together|\bmom of\b|parents?\b|\bbaby #|big sister|siblings|team",
    "cute_baby": r"\bcute\b|adorable|little one|tiny human|snuggle|cuddle",
    "visual_demo": r"unboxing|\bdemo\b|\bwatch\b|see how|before and after|transformation|glow-up|glow up|✨",
}
for r in comp_rows:
    s = " " + r["descr"].lower() + " "
    r["topics"] = [k for k, p in TOPIC_RULES.items() if re.search(p, s)]
    r["primary_topic"] = r["topics"][0] if r["topics"] else "unknown"

# per-brand stats
brand_stats = []
for brand, rs in sorted(
        ((b, [r for r in comp_rows if r["brand_key"] == b]) for b in {r["brand_key"] for r in comp_rows}),
        key=lambda kv: -statistics.median([r["play"] for r in kv[1]])):
    plays = [r["play"] for r in rs]
    n = len(plays)
    med = i(statistics.median(plays))
    meta = brand_summary.get(brand, {})
    topic_counts = Counter()
    for r in rs:
        topic_counts.update(set(r["topics"]))
    top_topics = [{"topic": k, "label": TOPIC_LABELS[k], "count": v,
                   "share_of_brand_videos": r4(v / n)}
                  for k, v in topic_counts.most_common()]
    motif_counts = Counter()
    for r in rs:
        motif_counts.update(set(TOPIC_TO_MOTIF[t] for t in r["topics"]))
    top_motifs = [{"motif": k, "motif_name": motif_names.get(k, k), "count": v,
                   "share_of_brand_videos": r4(v / n)}
                  for k, v in motif_counts.most_common()]
    brand_stats.append({
        "brand_key": brand,
        "account_handle": meta.get("account_handle"),
        "n_videos": n,
        "snapshot_rows": meta.get("snapshot_rows"),
        "snapshot_date_from": meta.get("date_from"),
        "snapshot_date_to": meta.get("date_to"),
        "median_play": med,
        "p25_play": i(percentile(plays, 0.25)),
        "p75_play": i(percentile(plays, 0.75)),
        "max_play": max(plays),
        "total_play": sum(plays),
        "median_digg": i(statistics.median([r["digg"] for r in rs])),
        "median_comment": i(statistics.median([r["comment"] for r in rs])),
        "median_share": i(statistics.median([r["share"] for r in rs])),
        "ad_share": r4(sum(1 for r in rs if r["is_ad"]) / n),
        "n_ge_100k": sum(1 for p in plays if p >= 100000),
        "n_ge_1m": sum(1 for p in plays if p >= 1000000),
        "n_ge_10m": sum(1 for p in plays if p >= 10000000),
        "relative_to_pool_median": r4(med / POOL_MEDIAN) if POOL_MEDIAN else None,
        "relative_to_hit_corpus_median": r4(med / CORPUS_MEDIAN_FULL) if CORPUS_MEDIAN_FULL else None,
        "top_topics": top_topics,
        "top_motifs_caption_proxy": top_motifs,
        "sample_status": sample_status(n),
        "fragility": fragility(n),
    })

all_comp_play = [r["play"] for r in comp_rows]
competitor_overall = {
    "n_videos": len(all_comp_play),
    **describe(all_comp_play),
    "n_ge_100k": sum(1 for p in all_comp_play if p >= 100000),
    "n_ge_1m": sum(1 for p in all_comp_play if p >= 1000000),
    "n_ge_10m": sum(1 for p in all_comp_play if p >= 10000000),
}

# topic stats
topic_stats = []
for topic, pat in TOPIC_RULES.items():
    vals = [r["play"] for r in comp_rows if topic in r["topics"]]
    by_brand = Counter(r["brand_key"] for r in comp_rows if topic in r["topics"])
    top_brand_share = (max(by_brand.values()) / len(vals)) if vals else None
    topic_stats.append({
        "topic": topic,
        "label": TOPIC_LABELS[topic],
        "n_videos": len(vals),
        "share_of_136": r4(len(vals) / len(comp_rows)),
        "median_play": i(statistics.median(vals)) if vals else None,
        "p25_play": i(percentile(vals, 0.25)) if vals else None,
        "p75_play": i(percentile(vals, 0.75)) if vals else None,
        "brands_covered": len(by_brand),
        "top_brand_share": r4(top_brand_share) if top_brand_share is not None else None,
        "by_brand_counts": dict(sorted(by_brand.items())),
        "mapped_motif": TOPIC_TO_MOTIF[topic],
        "sample_status": sample_status(len(vals)),
        "fragility": fragility(len(vals)),
    })
topic_stats.sort(key=lambda x: -x["n_videos"])

care_union = [r for r in comp_rows if ("feeding_pumping" in r["topics"] or "postpartum_newborn_care" in r["topics"])]
care_union_stat = {
    "topic": "care_union",
    "label": "喂养+产后/新生儿护理（并集）",
    "n_videos": len(care_union),
    "share_of_136": r4(len(care_union) / len(comp_rows)),
    "median_play": i(statistics.median([r["play"] for r in care_union])) if care_union else None,
    "mapped_motif": "care",
    "sample_status": sample_status(len(care_union)),
}

# topic vs corpus motif comparison
corpus_motif_share = {s["key"]: s for s in motif_stats_full}
topic_vs_motif = []
for ts in topic_stats:
    motif = ts["mapped_motif"]
    cm = corpus_motif_share.get(motif, {})
    delta = (ts["share_of_136"] - cm.get("share_of_corpus", 0)) if cm else None
    comparable, comp_note = TOPIC_COMPARABILITY[ts["topic"]]
    if delta is None:
        direction = "无直接对应"
    elif not comparable:
        direction = "仅下限，不比较方向"
    elif delta > 0.05:
        direction = "超配"
    elif delta < -0.05:
        direction = "低配"
    else:
        direction = "接近"
    topic_vs_motif.append({
        "topic": ts["topic"],
        "topic_label": ts["label"],
        "topic_n": ts["n_videos"],
        "topic_share": ts["share_of_136"],
        "mapped_motif": motif,
        "corpus_motif_name": cm.get("name"),
        "corpus_motif_n": cm.get("n_videos"),
        "corpus_motif_share": cm.get("share_of_corpus"),
        "difference_pp": r4(delta * 100) if delta is not None else None,
        "direction": direction,
        "comparable": comparable,
        "comparability_note": comp_note,
        "note": "caption 关键词代理 vs deepread motif 标注，口径不同，只作构成方向参考",
    })

# add non-overlapping care union row (feeding + postpartum/newborn care)
_care_cm = corpus_motif_share.get("care", {})
_care_delta = care_union_stat["share_of_136"] - _care_cm.get("share_of_corpus", 0)
topic_vs_motif.append({
    "topic": "care_union",
    "topic_label": care_union_stat["label"],
    "topic_n": care_union_stat["n_videos"],
    "topic_share": care_union_stat["share_of_136"],
    "mapped_motif": "care",
    "corpus_motif_name": _care_cm.get("name"),
    "corpus_motif_n": _care_cm.get("n_videos"),
    "corpus_motif_share": _care_cm.get("share_of_corpus"),
    "difference_pp": r4(_care_delta * 100),
    "direction": "超配" if _care_delta > 0.05 else ("低配" if _care_delta < -0.05 else "接近"),
    "comparable": True,
    "comparability_note": "并集；话题词较直接，但仍是 caption 代理",
    "note": "并集，避免 feeding 与 postpartum 两行重复计数；caption 代理 vs deepread motif 标注，口径不同。",
})

# within-brand topic medians (n>=5)
within_brand = []
for brand, rs in ((b, [r for r in comp_rows if r["brand_key"] == b]) for b in {r["brand_key"] for r in comp_rows}):
    for topic in TOPIC_RULES:
        vals = [r["play"] for r in rs if topic in r["topics"]]
        if len(vals) >= 5:
            within_brand.append({
                "brand_key": brand,
                "topic": topic,
                "topic_label": TOPIC_LABELS[topic],
                "n_videos": len(vals),
                "median_play": i(statistics.median(vals)),
                "sample_status": sample_status(len(vals)),
            })

# benchmarks
pool_total = sum(v["pool_videos"] for v in pool.values())
benchmarks = {
    "hit_corpus": {
        "n": N,
        "median_play": CORPUS_MEDIAN_FULL,
        "p25_play": i(percentile(ALL_PLAY, 0.25)),
        "p75_play": i(percentile(ALL_PLAY, 0.75)),
    },
    "tag_sampling_pool": {
        "n": 31366,
        "median_play": POOL_MEDIAN,
        "n_ge_100k": 10648,
        "n_ge_1m": 3350,
        "n_ge_10m": 410,
        "share_ge_100k": r4(10648 / 31366),
        "share_ge_1m": r4(3350 / 31366),
        "share_ge_10m": r4(410 / 31366),
        "note": "392 tag x 43 天的 top20/天采样池；不是 TikTok 全量，也不是随机样本",
    },
    "competitor_accounts": {
        **competitor_overall,
        "share_ge_100k": r4(competitor_overall["n_ge_100k"] / competitor_overall["n_videos"]),
        "share_ge_1m": r4(competitor_overall["n_ge_1m"] / competitor_overall["n_videos"]),
        "share_ge_10m": r4(competitor_overall["n_ge_10m"] / competitor_overall["n_videos"]),
        "note": "9 个竞品品牌账号的全部视频快照，不是爆款筛选样本",
    },
    "comparability": "爆款语料是已筛选高播放样本；品牌账号是全量快照；采样池是 tag 榜单 top20。三者口径不同，不能直接当因果对照。",
}

# ---------------------------------------------------------------- seasonality sensitivity
def pair_median(stat_full, stat_ex):
    return {
        "full_median": stat_full["median_play"],
        "ex_halloween_median": stat_ex["median_play"],
        "delta": (stat_ex["median_play"] - stat_full["median_play"])
        if stat_ex["median_play"] is not None and stat_full["median_play"] is not None else None,
    }


motif_sensitivity = []
for sf in motif_stats_full:
    se = next((x for x in motif_stats_ex if x["key"] == sf["key"]), None)
    if se:
        d = pair_median(sf, se)
        motif_sensitivity.append({
            "motif": sf["key"],
            "motif_name": sf["name"],
            "n_full": sf["n_videos"],
            "n_ex_halloween": se["n_videos"],
            **d,
            "direction": ("下降" if d["delta"] is not None and d["delta"] < 0 else
                          ("上升" if d["delta"] is not None and d["delta"] > 0 else "不变")),
        })

family_sensitivity = []
for sf in family_stats_full:
    se = next((x for x in family_stats_ex if x["key"] == sf["key"]), None)
    if se:
        d = pair_median(sf, se)
        family_sensitivity.append({
            "family": sf["key"],
            "family_name": sf["name"],
            "n_full": sf["n_videos"],
            "n_ex_halloween": se["n_videos"],
            **d,
            "direction": ("下降" if d["delta"] is not None and d["delta"] < 0 else
                          ("上升" if d["delta"] is not None and d["delta"] > 0 else "不变")),
        })

seasonality = {
    "halloween_definition": "video 的 theme 标签中含「万圣」即计为万圣节相关；288 条中 64 条，与既有 theme-clusters.json 的 64 条一致。",
    "halloween_videos": len([r for r in rows if r["hw"]]),
    "halloween_share": r4(len([r for r in rows if r["hw"]]) / N),
    "halloween_median_play": i(statistics.median([r["play"] for r in rows if r["hw"]])),
    "non_halloween_n": N_NON_HW,
    "non_halloween_median_play": CORPUS_MEDIAN_EX_HW,
    "median_difference": i(statistics.median([r["play"] for r in rows if r["hw"]])) - CORPUS_MEDIAN_EX_HW,
    "motif_sensitivity": motif_sensitivity,
    "mechanism_family_sensitivity": family_sensitivity,
    "tag_family_sensitivity": [
        {
            "family": f["family"],
            "label": f["label"],
            "n_full": f["n_hits"],
            "n_ex_halloween": f["ex_halloween_n"],
            "full_median": f["median_play"],
            "ex_halloween_median": f["ex_halloween_median_play"],
            "stability": f["stability"],
        } for f in family_level
    ],
    "note": "所有去季节对照都保留样本量；n<8 的对照标样本不足，不据此下结论。",
}

# ---------------------------------------------------------------- findings
findings = []


def add_finding(text, n, status="描述性", evidence=None):
    findings.append({"finding": text, "n": n, "status": status,
                     "evidence": evidence or []})


add_finding(
    "121 个 hashtag 中只有 4 个的爆款数达到 8 条，且全部是万圣节相关；其余 117 个 tag 均为样本不足，不能按 hashtag 排出可靠的饱和/空白清单。",
    121, "样本不足",
    [f"{t['tag']} n={t['n_hits']}" for t in valid_tags],
)
add_finding(
    "4 个可判定 tag 中，饱和候选是 #halloweenshirt（n=9，中位 230 万，池 137 条）和 #diyhalloween（n=9，中位 220 万，池 317 条）；有空间候选是 #halloweencostumeideas（n=14，中位 405 万，池 384 条）和 #october1st（n=10，中位 565 万，池 127 条）。全部受万圣节窗口影响，不能外推到非季节内容。",
    42, "描述性",
    [f"{t['tag']} n={t['n_hits']} median={t['median_play']} pool={t['pool_videos']}" for t in valid_tags],
)
add_finding(
    "tag 家族层面，最像「挤爆」的是 school_routine（n=20，中位 145 万，采样池 429 条视频）；newborn_pregnancy（n=36，中位 205 万）和 product_brand（n=23，中位 220 万）也低于语料中位 255 万。这里「挤爆」只指爆款多而中位低，池大小是供给背景，不是因果。",
    79, "描述性",
    [f"{f['family']} n={f['n_hits']} median={f['median_play']} pool={f['pool_videos']}" for f in family_level
     if f["family"] in ("school_routine", "newborn_pregnancy", "product_brand")],
)
add_finding(
    "tag 家族中有空间的是 baby_cute（n=11，中位 550 万）、mom_identity（n=9，中位 370 万）、toddler_kid（n=17，中位 330 万），三者在去万圣节后中位不变或基本不变。",
    37, "描述性",
    [f"{f['family']} n={f['n_hits']} median={f['median_play']} ex_median={f['ex_halloween_median_play']}"
     for f in family_level if f["family"] in ("baby_cute", "mom_identity", "toddler_kid")],
)
add_finding(
    f"爆款数与该 tag 在采样池中的视频数只有中等相关（r={pool_hit_correlation['pearson_r']}，n=121 个 tag），且 hit share 受 deepread 选取配额影响；因此「爆款占池比例」不能当作自然爆款率。",
    121, "方法限制",
)
add_finding(
    "13 motif × 10 mechanism family 的粗矩阵几乎全满：全样本 130 个格子中 129 个有视频，唯一空格是 cute×F10（萌娃治愈×争议猎奇，0 条）；去万圣节后同样 129/130。因此在聚类层不存在「从未出现」的组合，空白只能从「低于独立性期望」的格子里找；cute×F10 的期望只有约 3.9 条，0 条也不能当作空白结论（样本不足）。",
    288, "方法限制",
)
add_finding(
    "去万圣节后的红海格子（n>=20 且中位低于非万圣节语料中位 235 万）：visual×F7（n=38，中位 160 万，observed/expected=1.48）、identity×F2（n=20，中位 175 万，1.08）、meme×F5（n=27，中位 200 万，1.58）、family×F5（n=27，中位 210 万，1.09）、visual×F1（n=35，中位 210 万，1.10）、meme×F7（n=44，中位 215 万，1.28）。各格 n 在 20-47 之间；格子重叠，不是 288 条互斥分组。",
    288, "描述性",
    [f"{c['motif']}×{c['family']} n={c['n_videos']} med={c['median_play']} ratio={c['observed_over_expected']}"
     for c in red_ocean_ex[:8]],
)
add_finding(
    "更严格的「低于自身两个成分」清单（去万圣节，n>=20，格子中位 < min(motif 边际, family 边际)）：visual×F7（n=38，160 万 vs 210/210 万）、identity×F2（n=20，175 万 vs 245/270 万）、family×F5（n=27，210 万 vs 255/250 万）、anxiety×F1（n=37，220 万 vs 240/260 万）。这四格不仅低于语料中位，也低于自身两个成分的边际中位，是更可信的低效/挤爆信号。",
    224, "描述性",
    [f"{c['motif']}×{c['family']} n={c['n_videos']} med={c['median_play']} motif_med={c['motif_marginal_median']} fam_med={c['family_marginal_median']}"
     for c in true_red_ocean_ex],
)
add_finding(
    "去万圣节后满足「两个成分各自中位不低于 235 万 + 观测低于独立性期望 + n>=8」的潜在空白：cute×F5（n=8，中位 515 万，期望 11.4，ratio 0.70）和 diy×F3（n=14，中位 460 万，期望 16.7，ratio 0.84）。两格合计 22 次共现（非互斥）；cute×F5 刚好 8 条，结论脆弱。",
    22, "描述性",
    [f"{c['motif']}×{c['family']} n={c['n_videos']} med={c['median_play']} exp={c['expected_independence']} ratio={c['observed_over_expected']}"
     for c in gaps_ex],
)
add_finding(
    "visual×F3（n=14，中位 355 万，ratio 0.67）方向类似，但 visual motif 去万圣节后的中位只有 210 万，低于 235 万基线，只能算半满足，不能作为结论。",
    14, "半满足条件",
    [f"{c['motif']}×{c['family']} n={c['n_videos']} med={c['median_play']} ratio={c['observed_over_expected']}"
     for c in half_gaps_ex if c["motif"] == "visual" and c["family"] == "F3"],
)
add_finding(
    "高播放但不算「少用」的组合：cute×F2（n=11，中位 550 万）、comedy×F9（n=11，中位 500 万）、meme×F2（n=16，中位 420 万）、comedy×F5（n=18，中位 395 万）。四格合计 56 次共现（非互斥）；它们是「用得不少、中位也高」，不是空白。",
    56, "描述性",
    [f"{c['motif']}×{c['family']} n={c['n_videos']} med={c['median_play']} ratio={c['observed_over_expected']}"
     for c in high_payoff_ex],
)
add_finding(
    "tag 粒度上 n>=8 的具体组合里，中位最高的是 萌娃日常×F1 反差反转（n=9，620 万）、萌娃日常×F3 情绪共鸣（n=8，415 万）、万圣节装扮×F4 节点借势（n=10，390 万）、反差萌×F1（n=11，350 万）。这些是已在使用且中位高的组合，不是空白。母婴好物×F7 视听感官（n=8，245 万）低于 母婴好物 自身中位 310 万，是产品内容里相对低效的组合（描述性，n 刚好 8）。",
    46, "描述性",
    [f"{c['theme_tag']}×{c['mechanism_family']} n={c['n_videos']} med={c['median_play']}"
     for c in tag_cells_valid
     if (c["theme_tag"], c["mechanism_family"]) in (
         ("萌娃日常", "F1"), ("萌娃日常", "F3"), ("万圣节装扮", "F4"),
         ("反差萌", "F1"), ("母婴好物", "F7"))],
)
add_finding(
    "机制家族层面，去万圣节后中位最高的是 F3 情绪共鸣（n=96，280 万）、F2 悬念揭秘（n=52，270 万）、F1 反差反转（n=145，260 万）；最低的是 F6 教程实用（n=46，180 万）和 F8 真实实证（n=22，165 万）。F4 节点借势从 310 万降到 240 万，F7 视听感官从 240 万降到 210 万；去万圣节后回落，提示这部分表观优势与万圣节视频重叠（共现描述，不是因果）。",
    224, "描述性",
    [f"{s['key']} n={s['n_videos']} full={next((x['median_play'] for x in family_stats_full if x['key']==s['key']), None)} ex={s['median_play']}"
     for s in family_stats_ex],
)
add_finding(
    "竞品 9 个账号 136 条去重视频的中位播放从 756（willow）到 63,600（grownsy），组中位 10,800；爆款语料中位 255 万。两者口径不同（品牌全量 vs 已筛选爆款），不能直接当作内容优劣。对照 392-tag 采样池中位 21,850：只有 grownsy（2.91×）和 frida（1.52×）高于池中位；baby_brezza（0.04×）、willow（0.03×）等 7 个低于池中位。",
    136, "描述性",
    [f"{b['brand_key']} n={b['n_videos']} med={b['median_play']} pool_ratio={b['relative_to_pool_median']}"
     for b in brand_stats],
)
add_finding(
    "竞品 caption 关键词代理显示：feeding/pumping 45%（61/136）、postpartum/newborn care 35%（47/136）、product offer 29%（39/136）、identity/emotion 24%（32/136）、education 20%（27/136）、family 18%（24/136）、visual demo 14%（19/136）、campaign 14%（19/136）、humor 8%（11/136）、cute 8%（11/136）。与爆款语料 motif 占比相比，品牌在 care/feeding（并集 72.1%，98/136 vs 语料 care 19.8%）和 product（29% vs 21.9%）上超配，在 family（18% vs 37.5%）、comedy（8% vs 29.2%）、visual（14% vs 28.8%）、cute（8% vs 17.0%）、seasonal（14% vs 35.8%）上低配；identity（24% vs 28.1%）和 education（20% vs 20.8%）接近。注意这是 caption 代理，不是同一套 deepread 标签；visual/cute/education/community 的 caption 份额只能算下限，方向只作参考。",
    136, "描述性",
    [f"{t['topic']} n={t['n_videos']} share={t['share_of_136']} -> {t['mapped_motif']} "
     f"(corpus {corpus_motif_share.get(t['mapped_motif'], {}).get('share_of_corpus')})"
     for t in topic_stats],
)
add_finding(
    "账号内话题差异小于账号间差异：grownsy 内 lifestyle（n=11，中位 109,500）约为 product（n=13，中位 55,100）的 2 倍；而账号间中位差约 84 倍（756 vs 63,600）。9 个账号、136 条，无法把差距归因于母题、机制或发帖量；缺少粉丝量、曝光量、投流数据。广告标记与中位播放没有同向关系：grownsy 100% 广告但中位 63,600，baby_brezza 88% 广告但中位 821。",
    136, "无法归因",
    [f"{x['brand_key']} {x['topic']} n={x['n_videos']} med={x['median_play']}" for x in within_brand
     if x["brand_key"] == "grownsy"],
)
add_finding(
    "竞品 caption 里可判断的机制线索很有限：POV/叙事提示 8%（11/136）、明确 CTA 15%（21/136）、数字清单 4%（6/136）、疑问句 27%（37/136）。反差、悬念、视觉奇观、剪辑节奏等机制在文本里基本不可见，不能据此判断「机制不对」。",
    136, "方法限制",
)
add_finding(
    "万圣节敏感性：64/288（22.2%）视频带万圣节 theme；万圣节视频中位 320 万，非万圣节 235 万。去掉万圣节后 visual motif 中位 270→210 万、seasonal 300→210 万、meme 240→200 万，cute 350→330 万、comedy 280→280 万、family 280→255 万。报告中的空白/红海结论以去万圣节版本为主，全样本版本只作对照。",
    288, "方法",
    [f"{m['motif']} full={m['full_median']} ex={m['ex_halloween_median']}" for m in motif_sensitivity
     if m["motif"] in ("visual", "seasonal", "meme", "cute", "comedy", "family")],
)

# ---------------------------------------------------------------- assemble output
out = {
    "meta": {
        "title": "竞争饱和与空白：288 条 deepread 爆款 × 9 个竞品账号",
        "generated_at": GENERATED_AT,
        "sources": {
            "corpus": "deepread288.tsv（288 行，121 个 hashtag）",
            "database": "docker exec abi_migtest psql -U test -d abitest（只读）",
            "tables": [
                "raw.si_author_video_snapshot：904 行 / 136 条去重视频 / 9 个品牌账号 / 34 个快照日",
                "raw.si_tiktok_video：31,366 条视频 / 392 个 tag / 43 天；其中 288 条带 deepread theme/mechanism 标签",
            ],
            "cluster_mappings": [
                "theme-clusters.json：993 个 theme -> 13 个 motif",
                "mech-clusters.json：806 个 mechanism -> 10 个 family",
            ],
            "competitor_export": "_competitor_videos.tsv（按 video_id 取最新快照去重）",
        },
        "constraints": {
            "sample_rule": "每个结论带 n；n<8 一律标「样本不足」，不输出结论。",
            "causality": "只写「在 N 条里出现 M 次 / 中位播放是多少」，不写「因为 X 所以爆」。",
            "seasonality": "万圣节 64/288（22.2%）显式披露；核心矩阵同时给全样本与去万圣节两版，结论以去万圣节版为主。",
            "multi_membership": "一条视频可属于多个 motif / mechanism family / hashtag；矩阵是共现计数，不是互斥分组。",
            "hashtag_supply": "hashtag 层面的供给来自 392-tag x 43 天采样池，不是 TikTok 全量；爆款数是 deepread 选取结果，受选取配额影响。",
            "scope": "品类为母婴/喂养；采集窗口以 10 月为主；数据最后写入 2026-10-28；没有字幕/画面分析，只有 caption 文本与已有标签。",
        },
        "definitions": {
            "saturated": "n>=8 且中位播放低于同口径语料中位（全样本 255 万；去万圣节 235 万）。",
            "headroom": "n>=8 且中位播放不低于同口径语料中位。",
            "potential_gap": "去万圣节后，n>=8，两个成分各自中位>=235 万，格子中位>=235 万，observed/expected<0.85，且 synergy_vs_best_component>0；只表示本次采样中该组合相对少、且成分本身表现不差，不表示市场没人做。",
            "red_ocean": "去万圣节后，n>=20 且中位<235 万；表示本次采样中用得多、典型播放偏低。更严格版另要求 below_both_components=true（格子中位低于两个成分边际中位的较小值）。",
            "expected_independence": "n_motif × n_family / N，假设两个维度独立时的期望共现数；因多标签重叠，只是近似。",
            "pool_hit_share": "该 tag 的 deepread 爆款数 / 该 tag 在采样池中的视频数；受 deepread 选取配额影响，不是自然爆款率。",
        },
    },
    "corpus_profile": corpus_profile,
    "supply_density": {
        "tag_level": {
            "method": "以 deepread288.tsv 的 hashtag 列计数；每个 tag 的中位播放是该 tag 下爆款的中位 peak_play。pool_videos 来自 raw.si_tiktok_video 同一 tag 的视频数。",
            "valid_tags_n_ge_8": valid_tags,
            "saturated_tags_n_ge_8": saturated_tags,
            "headroom_tags_n_ge_8": headroom_tags,
            "valid_non_seasonal_tags": [],
            "valid_tags_with_non_halloween_videos": valid_tags_non_hw,
            "non_seasonal_note": "4 个 n>=8 的 tag 全部属于 halloween_seasonal 家族（#october1st 也按万圣节季处理）；不存在非季节的可判定 tag。",
            "pool_size_vs_hit_count": pool_hit_correlation,
            "insufficient_sample": {
                "count": sum(1 for t in tag_level if t["n_hits"] < SAMPLE_MIN),
                "note": "117 个 tag 的爆款数 <8；其中位播放仅作描述，不能据此判断饱和或空白。",
            },
            "directional_watch_n_5_to_7": {
                "note": "n=5-7，仍属样本不足，只作方向观察，不进入结论。",
                "high_median": watch_5_7_high,
                "low_median": watch_5_7_low,
            },
            "all_tags": tag_level,
        },
        "tag_family_level": {
            "method": "把 121 个 hashtag 按关键词人工归并为 13 个 tag 家族（互斥；每个 tag 只进一个家族）。归并规则是本次分析构造，不是平台分类。",
            "headline_filter": "以下饱和/有空间清单只列 interpretability=可解读 且方向稳定的家族；other_generic（归并残差）、other_local（混合/本地语言，去季节后翻转）保留在 families 全表，不进入结论。halloween_seasonal 因去万圣节后 n=7，单列在 seasonal_only_headroom_candidates。",
            "families": family_level,
            "saturated_families_n_ge_8": [
                f for f in family_level
                if f["n_hits"] >= SAMPLE_MIN and f["classification_full"] == "饱和候选"
                and f["interpretability"] == "可解读"
            ],
            "headroom_families_n_ge_8": [
                f for f in family_level
                if f["n_hits"] >= SAMPLE_MIN and f["classification_full"] == "有空间候选"
                and f["interpretability"] == "可解读" and f["stability"] == "方向稳定"
            ],
            "seasonal_only_headroom_candidates": [
                f for f in family_level
                if f["n_hits"] >= SAMPLE_MIN and f["classification_full"] == "有空间候选"
                and f["stability"] == "去季节后样本不足"
            ],
            "flips_after_halloween": [
                f for f in family_level if f["stability"] == "去季节后翻转"
            ],
        },
    },
    "motif_mechanism": {
        "method": "theme 标签经 theme-clusters.json 映射到 13 个 motif；mechanism 标签经 mech-clusters.json 映射到 10 个 family。矩阵为共现计数；median_play 是该格子内视频的 peak_play 中位；expected_independence 为两个边际计数相乘 / N。",
        "motif_stats_full": motif_stats_full,
        "motif_stats_ex_halloween": motif_stats_ex,
        "mechanism_family_stats_full": family_stats_full,
        "mechanism_family_stats_ex_halloween": family_stats_ex,
        "matrix_full": {
            "n_cells": len(matrix_full),
            "n_cells_nonzero": sum(1 for c in matrix_full if c["n_videos"] > 0),
            "cells": matrix_full,
        },
        "matrix_ex_halloween": {
            "n_cells": len(matrix_ex),
            "n_cells_nonzero": sum(1 for c in matrix_ex if c["n_videos"] > 0),
            "cells": matrix_ex,
        },
        "red_ocean_cells_ex_halloween": red_ocean_ex,
        "true_underperforming_cells_ex_halloween": {
            "criteria": "去万圣节；n>=20；格子中位低于该 motif 与 family 两个边际中位的较小值（below_both_components=true）",
            "note": "比「低于语料中位」更严格：格子表现低于自身两个成分的基线。",
            "cells": true_red_ocean_ex,
        },
        "potential_gaps_ex_halloween": {
            "criteria": "去万圣节；n>=8；两个成分各自中位>=235 万；格子中位>=235 万；observed/expected<0.85；synergy_vs_best_component>0",
            "caveat": "本次采样中相对少，不等于市场没人做；只说明在这 288 条、121 个 tag、10 月窗口的采样里，这种组合的出现次数低于独立性期望。",
            "cells": gaps_ex,
        },
        "half_satisfied_gaps_ex_halloween": {
            "criteria": "去万圣节；n>=8；observed/expected<0.85；但至少一个成分的边际中位低于 235 万",
            "caveat": "只作方向参考，不能作为空白结论。",
            "cells": half_gaps_ex,
        },
        "watch_insufficient_sample": {
            "criteria": "去万圣节；n<8；observed/expected<0.5；中位播放高；只作观察，不出结论",
            "caveat": "全部 n<8，按硬约束不得作为结论。",
            "cells": watch_insufficient_ex,
        },
        "high_payoff_cells_ex_halloween": {
            "criteria": "去万圣节；n>=8；中位>=350 万；observed/expected>=0.85",
            "cells": high_payoff_ex,
        },
        "tag_level_matrix": {
            "method": "只对 n>=8 的 10 个 theme tag 做 theme × mechanism family 分布；每个格子样本量小，n<8 标样本不足。",
            "themes_n_ge_8": theme_ge8_list,
            "mechanism_tags_n_ge_8": mech_ge8,
            "valid_cells_n_ge_8": tag_cells_valid,
            "all_cells": tag_cells,
            "exact_pair_gap_analysis": {
                "status": "不成立",
                "reason": "806 个 mechanism 标签中只有 3 个达到 n>=8；10 个 theme × 3 个 mechanism 的 30 个精确配对期望值只有 0.3-2.4 条。零共现在这个样本量下不可解释，不能当作空白。",
                "pairs": exact_pairs,
            },
        },
        "seasonal_sensitivity": {
            "motifs": motif_sensitivity,
            "mechanism_families": family_sensitivity,
        },
    },
    "competitor_comparison": {
        "method": "raw.si_author_video_snapshot 按 video_id 取最新快照去重（904 行 -> 136 条视频，9 个账号）。中位播放用视频级 peak（最新快照的 play_count）；与爆款语料/采样池分别对照，三者口径不同。",
        "brand_stats": brand_stats,
        "competitor_overall": competitor_overall,
        "topic_method": "caption 关键词代理：12 个话题多标签匹配；同一条视频可命中多个话题。不是 deepread 标签，也不是人工逐条编码。",
        "topic_stats": topic_stats,
        "care_union": care_union_stat,
        "topic_vs_corpus_motif": topic_vs_motif,
        "within_brand_topic_medians_n_ge_5": sorted(
            within_brand, key=lambda x: (x["brand_key"], -x["median_play"])),
        "benchmarks": benchmarks,
        "gap_assessment": {
            "composition": "品牌 caption 明显超配 care/feeding（并集 72.1%，98/136）和 product（28.7%），低配 family（17.6%）、comedy（8.1%）、visual（14.0%）、cute（8.1%）、seasonal（14.0%）；identity（23.5%）和 education（19.9%）与爆款语料接近。方向上是「母题构成不同」，但这是 caption 代理。",
            "account_baseline": "9 个账号中位播放 756..63,600，账号间差约 84 倍；只有 grownsy（2.91×）和 frida（1.52×）高于 392-tag 采样池中位 21,850。账号基线差远大于账号内话题差；粉丝量/分发/账号阶段等未观测因素无法排除。",
            "volume": "每个账号在快照窗口内只有 13-31 条视频（motif_medical 1 条）；缺少粉丝量、曝光量、同类账号发帖频率基线，无法判断「量不够」。",
            "mechanism": "caption 只能看到 POV/叙事 8%、明确 CTA 15%、数字清单 4%、疑问句 27%；反差、悬念、视觉奇观、剪辑节奏等核心机制在文本里不可见。不能判断「机制不对」。",
            "answer": "在本数据里不能把竞品与爆款的差距归因于母题、机制或发帖量。可观测的是：账号级播放基线差约 84 倍，母题构成偏向 care/feeding 与产品卖点，而爆款语料偏向 family/comedy/visual/cute/seasonal；这两条都只是描述性关联，不是因果。",
        },
    },
    "seasonality": seasonality,
    "action_hypotheses": [
        {
            "hypothesis": "测试「萌娃治愈 × 社交裂变」：可爱幼崽内容 + 明确的评论/合拍/转发指令，而不是纯展示。",
            "basis": "去万圣节后 cute×F5 n=8，中位 515 万，observed/expected=0.70，synergy_vs_best_component=+185 万；方向是「相对少用、播放不差」。",
            "n": 8,
            "status": "假设，待小样本测试；n=8 脆弱，不是因果结论",
        },
        {
            "hypothesis": "测试「实用教程 × 情绪共鸣」：把育儿/喂养教程包在真实情绪故事里，而不是纯步骤清单。",
            "basis": "去万圣节后 diy×F3 n=14，中位 460 万，observed/expected=0.84，synergy_vs_best_component=+180 万；F6 教程实用家族本身中位仅 180 万。",
            "n": 14,
            "status": "假设，待测试；描述性关联，不是因果结论",
        },
        {
            "hypothesis": "测试「萌娃治愈 × 悬念揭秘」的 wait-for-it 结构：先卖关子再给萌点/反转。",
            "basis": "去万圣节后 cute×F2 n=11，中位 550 万；不是低使用组合（ratio 1.08），但中位在 n>=8 格子里最高。",
            "n": 11,
            "status": "假设，待测试；n=11 接近下限",
        },
        {
            "hypothesis": "测试「家庭搞笑 × 叙事冲突」的 POV/短剧结构：家庭冲突 + 喜剧收尾。",
            "basis": "去万圣节后 comedy×F9 n=11，中位 500 万；ratio 1.10，使用量正常但中位高。",
            "n": 11,
            "status": "假设，待测试；n=11 接近下限",
        },
        {
            "hypothesis": "谨慎做「纯视觉奇观 × 视听感官」：变装/视觉冲击如果没有情绪、悬念或社交钩子，本次采样中中位偏低。",
            "basis": "去万圣节后 visual×F7 n=38，中位 160 万，低于 visual 边际 210 万和 F7 边际 210 万（below_both_components=true）。",
            "n": 38,
            "status": "描述性警示，不是禁令；需用新内容验证",
        },
        {
            "hypothesis": "谨慎做「身份共鸣 × 悬念」：身份/权利类内容配悬念机制，本次采样中中位偏低；身份内容配反差或情绪更常见。",
            "basis": "去万圣节后 identity×F2 n=20，中位 175 万，低于 identity 边际 245 万和 F2 边际 270 万；identity×F1 中位 280 万、identity×F3 中位 280 万（同为去万圣节后）。",
            "n": 20,
            "status": "描述性警示，不是禁令；需用新内容验证",
        },
        {
            "hypothesis": "品牌账号可小样本测试家庭/萌娃/幽默角度，而不是继续加产品演示；但先把账号基线差异当作首要混淆。",
            "basis": "竞品 caption 中 care/feeding 并集 72.1%、product 28.7%，family 17.6%、humor 8.1%、cute 8.1%；爆款语料 family 37.5%、comedy 29.2%、cute 17.0%。但 9 个账号中位差约 84 倍，账号基线无法排除。",
            "n": 136,
            "status": "假设，需按账号分层测试；不是因果结论",
        },
    ],
    "key_findings": findings,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- console summary
print("wrote", OUT, os.path.getsize(OUT), "bytes")
print("corpus", N, "median", CORPUS_MEDIAN_FULL, "non-hw", N_NON_HW, "median", CORPUS_MEDIAN_EX_HW)
print("valid tags", len(valid_tags), "saturated", len(saturated_tags), "headroom", len(headroom_tags))
print("tag families", [(f["family"], f["n_hits"], f["median_play"], f["classification_full"], f["stability"]) for f in family_level])
print("matrix full nonzero", sum(1 for c in matrix_full if c["n_videos"] > 0), "/", len(matrix_full))
print("matrix ex nonzero", sum(1 for c in matrix_ex if c["n_videos"] > 0), "/", len(matrix_ex))
print("red ocean ex", [(c["motif"], c["family"], c["n_videos"], c["median_play"], c["observed_over_expected"]) for c in red_ocean_ex[:12]])
print("gaps ex", [(c["motif"], c["family"], c["n_videos"], c["median_play"], c["observed_over_expected"]) for c in gaps_ex])
print("half gaps ex", [(c["motif"], c["family"], c["n_videos"], c["median_play"], c["observed_over_expected"]) for c in half_gaps_ex])
print("high payoff ex", [(c["motif"], c["family"], c["n_videos"], c["median_play"], c["observed_over_expected"]) for c in high_payoff_ex])
print("brands", [(b["brand_key"], b["n_videos"], b["median_play"], b["relative_to_pool_median"]) for b in brand_stats])
print("topics", [(t["topic"], t["n_videos"], t["share_of_136"]) for t in topic_stats])
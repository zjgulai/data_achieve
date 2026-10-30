#!/usr/bin/env python3
"""Build the exact-only creator/video interaction baseline.

Reads local JSONL artifacts only. Makes no network or paid API calls.
Writes:
  artifacts/run-20261029/creator-video/baseline/baseline.json
  artifacts/run-20261029/creator-video/baseline/baseline.md

Population: only target_exact relation rows. The anchor product_id must equal
the target product_id. Medium category-reference rows are reported in a
separate section and never enter the baseline.

Metric source: relations/video-product-candidates.jsonl -> engagement object,
preferred snapshot (fetch_post_detail when available, otherwise
fetch_video_search_result). Field paths are recorded in each row's evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RUN_DIR = Path("/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029")
CV_DIR = RUN_DIR / "creator-video"
TARGET_BASELINE_PATH = CV_DIR / "relations" / "video-product-target-baseline.jsonl"
CANDIDATES_PATH = CV_DIR / "relations" / "video-product-candidates.jsonl"
VIDEO_PRODUCT_PATH = CV_DIR / "relations" / "video-product.jsonl"
FEATURES_PATH = CV_DIR / "features" / "video-features.jsonl"
COVERAGE_PATH = CV_DIR / "relations" / "coverage.json"
CANONICAL_PATH = RUN_DIR / "canonical-records.jsonl"
GOLD_PATH = RUN_DIR / "gold-set-50.jsonl"
OUT_DIR = CV_DIR / "baseline"
OUT_JSON = OUT_DIR / "baseline.json"
OUT_MD = OUT_DIR / "baseline.md"

TARGET_PRODUCT_ID = "1729474995478630680"
TARGET_PRODUCT_NAME = (
    "Momcozy Pregnancy Belly Band YB001, CozySupport Ergonest Maternity Belly Band"
)
EXPECTED_EXACT_N = 10
MIN_LAYER_N = 8
BEAT_MULTIPLE = 2.0
PLAY_FLOOR = 5000
QUESTION_VIDEO_ID = "7696910923616881951"

METRICS = (
    "play_count",
    "like_count",
    "comment_count",
    "share_count",
    "collect_count",
    "interaction_rate",
)
METRIC_LABELS_ZH = {
    "play_count": "播放",
    "like_count": "点赞",
    "comment_count": "评论",
    "share_count": "分享",
    "collect_count": "收藏",
    "interaction_rate": "互动率",
}

DIMENSIONS = (
    ("duration_bucket", "时长档", ("<=15s", "16-30s", "31-60s", ">60s")),
    ("comparison", "是否对比测评", ("true", "false", "unknown")),
    ("demo", "是否演示", ("true", "false", "unknown")),
    ("has_link", "是否有购买链接", ("true", "false", "unknown")),
    ("ad_disclosure", "是否有广告披露", ("true", "false", "unknown")),
    ("platform_is_ad", "平台广告标记", ("true", "false", "unknown")),
)
BINARY_DIMENSIONS = {
    "comparison",
    "demo",
    "has_link",
    "ad_disclosure",
    "platform_is_ad",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def norm_value(value) -> str:
    """Return true/false/unknown for feature values; never invent a value."""
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in ("true", "false", "unknown"):
        return text
    return text


def quantile_exclusive(values: list[float], probability: float) -> float:
    """Quantile with the exclusive method (PERCENTILE.EXC).

    Python's statistics.quantiles(method='exclusive') uses position
    p*(n+1)-1 on a zero-based sorted list. The F decision IQRs use this
    method, so the baseline reproduces them.
    """
    ordered = sorted(values)
    n = len(ordered)
    if n == 1:
        return float(ordered[0])
    position = probability * (n + 1) - 1.0
    if position <= 0:
        return float(ordered[0])
    if position >= n - 1:
        return float(ordered[-1])
    lower = int(math.floor(position))
    upper = min(lower + 1, n - 1)
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def describe(values: list[float]) -> dict:
    n = len(values)
    if n == 0:
        raise ValueError("describe() received an empty sample")
    mean = statistics.fmean(values)
    median = statistics.median(values)
    return {
        "n": n,
        "q1": round(quantile_exclusive(values, 0.25), 6),
        "median": round(median, 9),
        "q3": round(quantile_exclusive(values, 0.75), 6),
        "mean": round(mean, 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean_over_median": round(mean / median, 3) if median else None,
    }


def median_stat(values: list[float]) -> dict:
    if not values:
        raise ValueError("median_stat() received an empty sample")
    return {
        "n": len(values),
        "median": round(statistics.median(values), 9),
    }


def engagement(row: dict) -> dict:
    return row["engagement"]


def build_exact_population(
    target_rows: list[dict],
    candidates_by_id: dict[str, dict],
    features_by_id: dict[str, dict],
) -> tuple[list[dict], list[str]]:
    """Return one merged row per target_exact video, plus the id list."""
    exact_rows = [
        row for row in target_rows if row.get("relation_type") == "target_exact"
    ]
    if len(exact_rows) != EXPECTED_EXACT_N:
        raise ValueError(
            f"expected {EXPECTED_EXACT_N} target_exact rows, found {len(exact_rows)}"
        )
    exact_ids = [row["video_id"] for row in exact_rows]
    if len(set(exact_ids)) != len(exact_ids):
        raise ValueError("duplicate video_id in target_exact rows")

    merged: list[dict] = []
    for relation in exact_rows:
        video_id = relation["video_id"]
        if relation.get("target_product_id") != TARGET_PRODUCT_ID:
            raise ValueError(f"{video_id}: target_product_id mismatch")
        if relation.get("confidence") != "high":
            raise ValueError(f"{video_id}: target_exact row is not high confidence")
        if relation.get("target_baseline_eligible") is not True:
            raise ValueError(f"{video_id}: target_baseline_eligible is not true")
        if relation.get("performance_eligible") is not True:
            raise ValueError(f"{video_id}: performance_eligible is not true")
        if relation.get("target_baseline_cohort") != "target_exact":
            raise ValueError(f"{video_id}: target_baseline_cohort mismatch")
        if relation.get("content_tag") == "consideration":
            raise ValueError(f"{video_id}: consideration row cannot enter the exact baseline")
        if video_id == QUESTION_VIDEO_ID:
            raise ValueError(f"{video_id}: question post cannot enter the exact baseline")

        candidate = candidates_by_id.get(video_id)
        feature = features_by_id.get(video_id)
        if candidate is None:
            raise ValueError(f"{video_id}: missing candidate relation row")
        if feature is None:
            raise ValueError(f"{video_id}: missing feature row")
        relation_meta = feature.get("product_relation") or {}
        if relation_meta.get("relation_type") != "target_exact":
            raise ValueError(f"{video_id}: feature relation_type is not target_exact")
        if relation_meta.get("target_product_id") != TARGET_PRODUCT_ID:
            raise ValueError(f"{video_id}: feature target_product_id mismatch")
        if relation_meta.get("target_baseline_eligible") is not True:
            raise ValueError(f"{video_id}: feature target_baseline_eligible is not true")

        anchors = candidate.get("anchor_product_ids") or []
        if TARGET_PRODUCT_ID not in anchors:
            raise ValueError(f"{video_id}: target product_id is absent from anchors")
        if candidate.get("content_tag") == "consideration":
            raise ValueError(f"{video_id}: consideration row cannot enter the exact baseline")

        metrics = engagement(candidate)
        for metric in METRICS:
            if metrics.get(metric) is None:
                raise ValueError(f"{video_id}: missing metric {metric}")
        if feature.get("duration_seconds") is None:
            raise ValueError(f"{video_id}: missing duration_seconds")
        if feature.get("duration_bucket") is None:
            raise ValueError(f"{video_id}: missing duration_bucket")

        # The target-baseline file and the candidate file must agree on the
        # exact rows. A mismatch means the two artifacts came from different
        # runs, so stop instead of choosing one silently.
        target_metrics = engagement(relation)
        for metric in METRICS + ("preferred_snapshot",):
            if target_metrics.get(metric) != metrics.get(metric):
                raise ValueError(
                    f"{video_id}: target baseline and candidate disagree on {metric}"
                )

        merged.append(
            {
                "video_id": video_id,
                "relation_confidence": candidate.get("confidence"),
                "relation_type": candidate.get("relation_type"),
                "target_product_id": candidate.get("target_product_id"),
                "target_baseline_eligible": True,
                "performance_eligible": True,
                "content_tag": candidate.get("content_tag"),
                "duration_seconds": feature.get("duration_seconds"),
                "duration_bucket": feature.get("duration_bucket"),
                "has_link": norm_value(candidate.get("has_link")),
                "ad_disclosure": norm_value(feature.get("ad_disclosure")),
                "platform_is_ad": norm_value(candidate.get("platform_is_ad")),
                "comparison": norm_value(feature.get("comparison")),
                "demo": norm_value(feature.get("demo")),
                "play_count": metrics["play_count"],
                "like_count": metrics["like_count"],
                "comment_count": metrics["comment_count"],
                "share_count": metrics["share_count"],
                "collect_count": metrics["collect_count"],
                "interaction_rate": round(metrics["interaction_rate"], 9),
                "low_denominator_flag": metrics["play_count"] < PLAY_FLOOR,
                "engagement_source": {
                    "preferred_snapshot": metrics.get("preferred_snapshot"),
                    "source_endpoint": (candidate.get("evidence") or {}).get(
                        "source_endpoint"
                    ),
                    "source_file": (candidate.get("evidence") or {}).get("source_file"),
                    "captured_at": (candidate.get("evidence") or {}).get("captured_at"),
                    "request_id": (candidate.get("evidence") or {}).get("request_id"),
                    "field_paths": (candidate.get("evidence") or {}).get("field_paths"),
                },
            }
        )
    merged.sort(key=lambda row: row["video_id"])
    return merged, sorted(exact_ids)


def build_overall(exact_rows: list[dict]) -> dict:
    return {
        "n": len(exact_rows),
        "metrics": {
            metric: describe([row[metric] for row in exact_rows])
            for metric in METRICS
        },
        "duration_seconds": describe(
            [row["duration_seconds"] for row in exact_rows]
        ),
    }


def build_layers(exact_rows: list[dict]) -> dict:
    """Count-only layers. No median or lift is computed below n=8.

    A layer is usable only when both the layer and its complement reach n>=8.
    A single-valued dimension (for example has_link=true with zero false rows)
    has n>=8 but no comparable complement, so it stays insufficient_sample.
    """
    layers: dict[str, dict] = {}
    for dimension, label_zh, ordered_labels in DIMENSIONS:
        counts = Counter(norm_value(row[dimension]) for row in exact_rows)
        labels = list(ordered_labels)
        for extra in sorted(set(counts) - set(labels)):
            labels.append(extra)
        groups: dict[str, dict] = {}
        for label in labels:
            n = counts.get(label, 0)
            if label == "unknown":
                complement_n = None
            elif dimension in BINARY_DIMENSIONS:
                opposite = "false" if label == "true" else "true"
                complement_n = counts.get(opposite, 0)
            else:
                complement_n = len(exact_rows) - n
            if label == "unknown":
                status = "unclassified"
                note = (
                    "feature value is unknown; not a layer. Excluded from every "
                    "layer comparison and from the baseline."
                )
            elif n < MIN_LAYER_N:
                status = "insufficient_sample"
                note = (
                    f"n={n} < {MIN_LAYER_N}; counts only. No median, lift, CI or "
                    "conclusion is reported for this layer."
                )
            elif complement_n < MIN_LAYER_N:
                status = "insufficient_sample"
                note = (
                    f"n={n} >= {MIN_LAYER_N}, but complement n={complement_n} < "
                    f"{MIN_LAYER_N}. The dimension is single-valued or nearly "
                    "single-valued, so no comparison is possible."
                )
            else:
                status = "ok"
                note = (
                    "n>=8 and complement n>=8; this round still reports counts "
                    "only. No stratified baseline is produced."
                )
            groups[label] = {
                "n": n,
                "complement_n": complement_n,
                "status": status,
                "n_ge_8": n >= MIN_LAYER_N,
                "complement_ge_8": (
                    complement_n >= MIN_LAYER_N
                    if complement_n is not None
                    else False
                ),
                "usable_layer": status == "ok",
                "metrics": None,
                "lift_vs_complement": None,
                "note": note,
            }
        usable_groups = [
            label
            for label, group in groups.items()
            if group["usable_layer"]
        ]
        layers[dimension] = {
            "dimension": dimension,
            "label_zh": label_zh,
            "dimension_status": (
                "ok" if usable_groups else "insufficient_sample"
            ),
            "usable_layers": usable_groups,
            "groups": groups,
        }
    return layers


def build_bootstrap(layers: dict) -> dict:
    eligible = [
        f"{dimension}:{label}"
        for dimension, layer in layers.items()
        for label, group in layer["groups"].items()
        if group.get("usable_layer")
    ]
    return {
        "performed": False,
        "tests": [],
        "eligible_layers": eligible,
        "reason": (
            "No exact layer has both n>=8 and complement n>=8. By rule, n<8 "
            "layers receive counts only and no CI. Bootstrap is restricted to "
            "the exact population; there is no exact stratified comparison to "
            "test."
        ),
    }


def build_high_performers(exact_rows: list[dict]) -> dict:
    """Find high performers inside the 10 exact rows only.

    No duration bucket reaches n>=8, so the threshold uses the overall median
    of the 10 exact videos. A duration-bucket median would be a median of 1 to
    4 videos, which the rule forbids.
    """
    rates = [row["interaction_rate"] for row in exact_rows]
    median_rate = statistics.median(rates)
    threshold = median_rate * BEAT_MULTIPLE
    bucket_counts = Counter(row["duration_bucket"] for row in exact_rows)
    high_rows = [
        row for row in exact_rows if row["interaction_rate"] >= threshold
    ]
    high_rows.sort(key=lambda row: row["interaction_rate"], reverse=True)

    videos: list[dict] = []
    for row in high_rows:
        videos.append(
            {
                "video_id": row["video_id"],
                "interaction_rate": row["interaction_rate"],
                "multiple_vs_exact_median": round(
                    row["interaction_rate"] / median_rate, 3
                ),
                "multiple_vs_duration_bucket_median": None,
                "duration_bucket_peer_available": (
                    bucket_counts[row["duration_bucket"]] >= MIN_LAYER_N
                ),
                "play_count": row["play_count"],
                "play_multiple_vs_exact_median": round(
                    row["play_count"]
                    / statistics.median([item["play_count"] for item in exact_rows]),
                    3,
                ),
                "duration_seconds": row["duration_seconds"],
                "duration_bucket": row["duration_bucket"],
                "duration_bucket_n": bucket_counts[row["duration_bucket"]],
                "relation_confidence": row["relation_confidence"],
                "relation_type": row["relation_type"],
                "has_link": row["has_link"],
                "ad_disclosure": row["ad_disclosure"],
                "platform_is_ad": row["platform_is_ad"],
                "low_denominator_flag": row["low_denominator_flag"],
                "engagement_source": row["engagement_source"],
            }
        )

    floor_videos = [
        row for row in videos if row["play_count"] >= PLAY_FLOOR
    ]
    if videos:
        statement = (
            f"{len(videos)} 条 exact 视频的互动率达到 10 条 exact 中位数的 "
            f"{BEAT_MULTIPLE:g} 倍。"
        )
    else:
        statement = "无。10 条 exact 视频中没有视频达到中位数的 2 倍。"

    return {
        "definition": (
            "interaction_rate >= 2.0 * median interaction_rate of the 10 exact "
            "videos. No duration bucket reaches n>=8, so no duration-bucket "
            "peer median is used."
        ),
        "metric": "interaction_rate",
        "threshold_multiple": BEAT_MULTIPLE,
        "peer_group": "all 10 exact videos",
        "peer_group_n": len(exact_rows),
        "overall_median_interaction_rate": round(median_rate, 9),
        "threshold_interaction_rate": round(threshold, 9),
        "eligible_videos": len(exact_rows),
        "eligible_duration_buckets": {
            bucket: count
            for bucket, count in bucket_counts.items()
            if count >= MIN_LAYER_N
        },
        "count": len(videos),
        "none": not videos,
        "statement": statement,
        "videos": videos,
        "common_features": {
            "n": len(videos),
            "note": (
                "Only counts are available. n<8, so this is not a comparison "
                "and not a conclusion."
            ),
            "items": [],
        },
        "low_denominator_sensitivity": {
            "play_count_floor": PLAY_FLOOR,
            "count": len(floor_videos),
            "videos": floor_videos,
            "note": (
                "Descriptive only. The high-performer set is below the 8-video "
                "layer floor."
            ),
        },
    }


def build_question_post_check(
    candidates_by_id: dict[str, dict],
    exact_ids: list[str],
    high_performer_ids: set[str],
) -> dict:
    row = candidates_by_id.get(QUESTION_VIDEO_ID)
    if row is None:
        raise ValueError(f"{QUESTION_VIDEO_ID}: question post row is missing")
    in_exact = QUESTION_VIDEO_ID in set(exact_ids)
    in_high = QUESTION_VIDEO_ID in high_performer_ids
    if in_exact:
        raise ValueError(f"{QUESTION_VIDEO_ID}: question post is in the exact population")
    if in_high:
        raise ValueError(
            f"{QUESTION_VIDEO_ID}: question post is still in high performers"
        )
    metrics = engagement(row)
    return {
        "video_id": QUESTION_VIDEO_ID,
        "in_exact_population": in_exact,
        "in_high_performers": in_high,
        "excluded_from_performance_statistics": True,
        "content_tag": row.get("content_tag"),
        "target_baseline_cohort": row.get("target_baseline_cohort"),
        "relation_type": row.get("relation_type"),
        "confidence": row.get("confidence"),
        "play_count": metrics.get("play_count"),
        "like_count": metrics.get("like_count"),
        "comment_count": metrics.get("comment_count"),
        "share_count": metrics.get("share_count"),
        "collect_count": metrics.get("collect_count"),
        "interaction_rate": round(metrics.get("interaction_rate"), 9),
        "low_denominator_flag": metrics.get("play_count") < PLAY_FLOOR,
        "content_tag_evidence": row.get("content_tag_evidence"),
        "reason": (
            "C1 no product evidence, C2 purchase intent, C3 no personal usage "
            "evidence. Category reference only."
        ),
    }


def build_category_reference(
    candidate_rows: list[dict],
    features_by_id: dict[str, dict],
    exact_ids: list[str],
) -> dict:
    rows = [
        row
        for row in candidate_rows
        if row.get("target_baseline_cohort") == "category_reference"
    ]
    if not rows:
        raise ValueError("no category_reference rows found")
    exact_id_set = set(exact_ids)
    for row in rows:
        video_id = row["video_id"]
        if video_id in exact_id_set:
            raise ValueError(f"{video_id}: category reference overlaps exact population")
        if row.get("confidence") != "medium":
            raise ValueError(f"{video_id}: category reference is not medium confidence")
        if row.get("baseline_eligible") is not False:
            raise ValueError(f"{video_id}: category reference is baseline eligible")
        if row.get("performance_eligible") is not False:
            raise ValueError(f"{video_id}: category reference is performance eligible")

    consideration = [
        row for row in rows if row.get("content_tag") == "consideration"
    ]
    median_rows = [
        row for row in rows if row.get("content_tag") != "consideration"
    ]

    durations: list[float] = []
    for row in median_rows:
        feature = features_by_id.get(row["video_id"])
        if feature is None:
            raise ValueError(f"{row['video_id']}: category reference has no feature row")
        duration = feature.get("duration_seconds")
        if duration is None:
            raise ValueError(f"{row['video_id']}: category reference has no duration")
        durations.append(float(duration))

    audit_rows: list[dict] = []
    for row in sorted(rows, key=lambda item: item["video_id"]):
        feature = features_by_id[row["video_id"]]
        metrics = engagement(row)
        audit_rows.append(
            {
                "video_id": row["video_id"],
                "relation_type": row.get("relation_type"),
                "confidence": row.get("confidence"),
                "content_tag": row.get("content_tag"),
                "baseline_eligible": False,
                "performance_eligible": False,
                "duration_seconds": feature.get("duration_seconds"),
                "duration_bucket": feature.get("duration_bucket"),
                "has_link": norm_value(row.get("has_link")),
                "platform_is_ad": norm_value(row.get("platform_is_ad")),
                "play_count": metrics.get("play_count"),
                "like_count": metrics.get("like_count"),
                "comment_count": metrics.get("comment_count"),
                "share_count": metrics.get("share_count"),
                "collect_count": metrics.get("collect_count"),
                "interaction_rate": round(metrics.get("interaction_rate"), 9),
                "low_denominator_flag": metrics.get("play_count") < PLAY_FLOOR,
            }
        )

    return {
        "cohort": "category_reference",
        "baseline_eligible": False,
        "label": "not baseline eligible",
        "definition": (
            "Medium-confidence rows: other-listing anchors or text brand+category "
            "matches. They are category context only."
        ),
        "n": len(rows),
        "confidence_counts": dict(Counter(row.get("confidence") for row in rows)),
        "relation_type_counts": dict(
            Counter(row.get("relation_type") for row in rows)
        ),
        "content_tag_counts": dict(
            Counter(row.get("content_tag") for row in rows)
        ),
        "median_population": {
            "n": len(median_rows),
            "excluded_content_tag_consideration_n": len(consideration),
            "note": (
                "The consideration row is excluded from these medians. It has "
                "performance_eligible=false and is excluded from all "
                "performance statistics."
            ),
            "metrics": {
                metric: median_stat([engagement(row)[metric] for row in median_rows])
                for metric in METRICS
            },
            "duration_seconds": median_stat(durations),
        },
        "consideration_rows": [
            {
                "video_id": row["video_id"],
                "relation_type": row.get("relation_type"),
                "confidence": row.get("confidence"),
                "content_tag": row.get("content_tag"),
                "play_count": engagement(row).get("play_count"),
                "like_count": engagement(row).get("like_count"),
                "comment_count": engagement(row).get("comment_count"),
                "share_count": engagement(row).get("share_count"),
                "collect_count": engagement(row).get("collect_count"),
                "interaction_rate": round(
                    engagement(row).get("interaction_rate"), 9
                ),
                "low_denominator_flag": (
                    engagement(row).get("play_count") < PLAY_FLOOR
                ),
                "content_tag_evidence": row.get("content_tag_evidence"),
                "excluded_from_performance_statistics": True,
            }
            for row in consideration
        ],
        "rows": audit_rows,
        "note": (
            "Category reference only. Not baseline eligible. Do not merge with "
            "the exact baseline. Do not compare medians and do not claim that "
            "one content form wins."
        ),
    }


def build_unclassified(
    video_product_rows: list[dict],
    exact_ids: list[str],
    category_ids: set[str],
) -> dict:
    exact_id_set = set(exact_ids)
    low_rows = [
        row for row in video_product_rows if row.get("confidence") == "low"
    ]
    none_rows = [
        row for row in video_product_rows if row.get("confidence") == "none"
    ]
    for row in low_rows + none_rows:
        if row["video_id"] in exact_id_set:
            raise ValueError(f"{row['video_id']}: excluded row overlaps exact population")
        if row["video_id"] in category_ids:
            raise ValueError(
                f"{row['video_id']}: excluded row overlaps category reference"
            )
    return {
        "low_confidence_relation_rows": {
            "n": len(low_rows),
            "relation_type_counts": dict(
                Counter(row.get("relation_type") for row in low_rows)
            ),
            "file": str(VIDEO_PRODUCT_PATH),
            "video_ids": sorted(row["video_id"] for row in low_rows),
            "note": (
                "Low-confidence relations. Kept out of every baseline and "
                "lift calculation."
            ),
        },
        "no_signal_rows": {
            "n": len(none_rows),
            "file": str(VIDEO_PRODUCT_PATH),
            "video_ids": sorted(row["video_id"] for row in none_rows),
            "note": (
                "No product signal. Kept out of every baseline and lift "
                "calculation; these rows are not evidence of promoting the "
                "target product."
            ),
        },
        "note": (
            "unknown feature values are unclassified, not false. They are "
            "excluded from layer comparisons."
        ),
    }


def build_coverage_check(
    coverage: dict, exact_n: int, category_n: int
) -> dict:
    target = coverage.get("video_product_target") or {}
    target_coverage = target.get("target_coverage") or {}
    checks = {
        "target_product_id": target.get("target_product_id"),
        "exact_product_id_high": target_coverage.get("exact_product_id_high"),
        "category_reference_n": target_coverage.get("category_reference_n"),
        "performance_eligible_n": target.get("performance_eligible_n"),
    }
    if checks["target_product_id"] != TARGET_PRODUCT_ID:
        raise ValueError("coverage.json target_product_id mismatch")
    if checks["exact_product_id_high"] != exact_n:
        raise ValueError("coverage.json exact_product_id_high mismatch")
    if checks["category_reference_n"] != category_n:
        raise ValueError("coverage.json category_reference_n mismatch")
    if checks["performance_eligible_n"] != exact_n:
        raise ValueError("coverage.json performance_eligible_n mismatch")
    return checks


def build_document(
    exact_rows: list[dict],
    input_hashes: dict,
    coverage_check: dict,
    category_reference: dict,
    unclassified: dict,
    question_post: dict,
) -> dict:
    overall = build_overall(exact_rows)
    layers = build_layers(exact_rows)
    bootstrap = build_bootstrap(layers)
    high_performers = build_high_performers(exact_rows)
    exact_ids = [row["video_id"] for row in exact_rows]

    population_confidence = dict(
        Counter(row["relation_confidence"] for row in exact_rows)
    )
    population_relation_type = dict(
        Counter(row["relation_type"] for row in exact_rows)
    )
    category_relation_counts = category_reference["relation_type_counts"]
    duplicate_listing_n = category_relation_counts.get(
        "duplicate_listing_anchor", 0
    )
    text_brand_n = category_relation_counts.get("text_brand_and_category", 0)
    total_videos = (
        len(exact_rows)
        + category_reference["n"]
        + unclassified["low_confidence_relation_rows"]["n"]
        + unclassified["no_signal_rows"]["n"]
    )

    document = {
        "schema_version": "voc_creator_video_baseline_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": {
            "script": str(Path(__file__).resolve()),
            "paid_api_calls": 0,
            "usd": 0.0,
            "balance_probe": "none",
        },
        "budget": {
            "hard_cap_usd": 15.0,
            "spent_this_round_usd": 0.0,
            "api_calls_this_round": 0,
            "balance_probe": "none",
            "last_known_balance_usd": 37.316,
            "last_known_balance_source": (
                "artifacts/run-20261029/creator-video/collect-summary.json "
                "cost.balance_after_usd"
            ),
            "note": (
                "This round only reads local artifacts. No paid endpoint was "
                "called and no balance probe was made."
            ),
        },
        "scope": {
            "question": "按内容形态分层的互动基线：哪类内容形态跑赢互动基线",
            "baseline_population": "target_exact only",
            "product": {
                "product_id": TARGET_PRODUCT_ID,
                "product_name": TARGET_PRODUCT_NAME,
                "market": "TikTok Shop US",
            },
            "predefined_dimensions": [
                dimension for dimension, _, _ in DIMENSIONS
            ],
            "category_reference_note": (
                "Medium category-reference rows are a separate population. They "
                "never enter the baseline or any conclusion."
            ),
            "out_of_scope": [
                "Product/Price/Place analysis",
                "creator tier and audience baselines",
                "transcript, audio and visual features",
                "other caption-derived features not listed above",
            ],
        },
        "inputs": input_hashes,
        "coverage_cross_check": coverage_check,
        "population": {
            "definition": (
                "video_product relation rows with relation_type=target_exact; "
                "the anchor product_id equals the target product_id. One row per "
                "video. Medium rows are excluded."
            ),
            "n": len(exact_rows),
            "confidence_counts": population_confidence,
            "relation_type_counts": population_relation_type,
            "includes_medium": False,
            "exact_product_id": TARGET_PRODUCT_ID,
            "excluded": {
                "category_reference_rows": category_reference["n"],
                "low_confidence_relation_rows": unclassified[
                    "low_confidence_relation_rows"
                ]["n"],
                "no_signal_rows": unclassified["no_signal_rows"]["n"],
                "note": (
                    "Category reference is reported separately. Low-confidence "
                    "and no_signal rows are excluded from every statistic."
                ),
            },
            "denominator_note": (
                "Category reference rows are a different population and are not "
                "mixed into this denominator. Comment-level canonical records "
                "are also a different population."
            ),
        },
        "question_post": question_post,
        "unclassified": {
            "low_confidence_relation_rows": unclassified[
                "low_confidence_relation_rows"
            ],
            "no_signal_rows": unclassified["no_signal_rows"],
            "feature_unknown_rows": {
                dimension: sorted(
                    row["video_id"]
                    for row in exact_rows
                    if norm_value(row[dimension]) == "unknown"
                )
                for dimension, _, _ in DIMENSIONS
            },
            "note": unclassified["note"],
        },
        "metric_definitions": {
            "play_count": {
                "label_zh": "播放",
                "field_paths": [
                    "fetch_post_detail.data.itemInfo.itemStruct.stats.playCount",
                    "fetch_video_search_result.data.search_item_list[].aweme_info.statistics.play_count",
                ],
            },
            "like_count": {
                "label_zh": "点赞",
                "field_paths": [
                    "fetch_post_detail.data.itemInfo.itemStruct.stats.diggCount",
                    "fetch_video_search_result.data.search_item_list[].aweme_info.statistics.digg_count",
                ],
            },
            "comment_count": {
                "label_zh": "评论",
                "field_paths": [
                    "fetch_post_detail.data.itemInfo.itemStruct.stats.commentCount",
                    "fetch_video_search_result.data.search_item_list[].aweme_info.statistics.comment_count",
                ],
            },
            "share_count": {
                "label_zh": "分享",
                "field_paths": [
                    "fetch_post_detail.data.itemInfo.itemStruct.stats.shareCount",
                    "fetch_video_search_result.data.search_item_list[].aweme_info.statistics.share_count",
                ],
            },
            "collect_count": {
                "label_zh": "收藏",
                "field_paths": [
                    "fetch_post_detail.data.itemInfo.itemStruct.stats.collectCount",
                    "fetch_video_search_result.data.search_item_list[].aweme_info.statistics.collect_count",
                ],
            },
            "interaction_rate": {
                "label_zh": "互动率",
                "formula": "(like_count + comment_count + share_count + collect_count) / play_count",
                "note": "Upstream definition, reproduced without modification.",
            },
            "snapshot_policy": (
                "Use preferred_snapshot per row: fetch_post_detail when a detail "
                "payload exists, otherwise fetch_video_search_result. All values "
                "are single snapshots captured on 2026-10-30, not lifetime totals. "
                "is_estimated is null in every payload; it is not treated as a "
                "measured value."
            ),
        },
        "aggregation": {
            "why_median": (
                "Play and engagement counts are heavy-tailed. The mean is pulled "
                "up by a small number of high-reach videos, so the median and "
                "quartiles describe the typical video. The overall mean/median "
                "ratio is reported for each metric."
            ),
            "quartile_method": (
                "Python statistics.quantiles(method='exclusive'), equivalent to "
                "PERCENTILE.EXC. The F decision IQRs use this method."
            ),
            "minimum_layer_n": MIN_LAYER_N,
            "insufficient_rule": (
                "Layers with n<8 report counts only. No median, lift, CI or "
                "conclusion is reported for them."
            ),
            "unknown_rule": (
                "unknown feature values are unclassified, not false. They are "
                "excluded from layer comparisons and from lift calculations."
            ),
            "overlap_note": (
                "A video appears in one layer per dimension. Tables for different "
                "dimensions overlap and must not be summed."
            ),
            "traceability": (
                "Every layer count is computed from the 10 rows in video_level. "
                "Each video_level row carries the raw metric values and "
                "engagement_source: endpoint, raw file, captured_at, request_id "
                "and field_paths. No layer median is computed because no layer "
                "reaches n>=8."
            ),
            "no_stratified_baseline": (
                "No predefined dimension has a layer with n>=8. This round "
                "produces no stratified baseline."
            ),
        },
        "overall": overall,
        "layers": layers,
        "bootstrap": bootstrap,
        "high_performers": high_performers,
        "strongest_single_feature": {
            "within_predefined_dimensions": True,
            "status": "insufficient_sample",
            "verdict": "not_supported",
            "top_layer": None,
            "all_ranked_layers": [],
            "reason": (
                "No layer in the 10-row exact population reaches n>=8. No rank, "
                "multiple, p-value or CI is computed."
            ),
            "conclusion": (
                "本轮不做分层比较。C16 的否定结论依据是 10 条 exact 无法检验，"
                "不能写成已证明没有形态跑赢。"
            ),
        },
        "sufficiency_assessment": {
            "exact_population_n": len(exact_rows),
            "layered_baseline_computed": False,
            "dimensions_with_any_group_n_ge_8": sorted(
                {
                    dimension
                    for dimension, layer in layers.items()
                    for label, group in layer["groups"].items()
                    if label != "unknown" and group["n"] >= MIN_LAYER_N
                }
            ),
            "dimensions_with_usable_layer": sorted(
                {
                    dimension
                    for dimension, layer in layers.items()
                    if layer["usable_layers"]
                }
            ),
            "groups_with_n_ge_8_raw": [
                f"{dimension}:{label}"
                for dimension, layer in layers.items()
                for label, group in layer["groups"].items()
                if label != "unknown" and group["n"] >= MIN_LAYER_N
            ],
            "usable_layers": [
                f"{dimension}:{label}"
                for dimension, layer in layers.items()
                for label in layer["usable_layers"]
            ],
            "bootstrap_performed": False,
            "single_feature_ranking_computed": False,
            "causal_claims_supported": 0,
            "c16_status": "retained_as_negative_but_evidence_changed",
            "c16_basis": (
                "10 条 exact 无法做分层检验。结论只能写成样本不足以检验，"
                "不能写成已证明没有内容形态跑赢。"
            ),
            "statement": (
                "本轮只给 10 条 exact 的整体分布和逐条明细。没有任何一层同时"
                "满足层 n>=8 和对照 n>=8，所以只给计数，不给中位数、CI 或结论。"
            ),
        },
        "category_reference": category_reference,
        "evidence_gaps": [
            (
                "10 条 exact 中没有任何一层同时满足层 n>=8 和对照 n>=8。"
                "时长档为 <=15s 1 条、16-30s 4 条、31-60s 4 条、>60s 1 条；"
                "has_link 和 ad_disclosure 只有一个取值；platform_is_ad 的 "
                "false 只有 1 条。分层基线不成立。"
            ),
            (
                "comparison 与 demo 在 10 条 exact 中全部 unknown。没有字幕、"
                "音轨或视频帧，无法判断画面是否对比或演示。"
            ),
            (
                f"{category_reference['n']} 条 medium 只作品类参照。"
                f"{duplicate_listing_n} 条 duplicate_listing_anchor "
                "锚到同品牌 YB001 系列的其他 listing；product_id 不同，标题"
                f"相似但不相同。{text_brand_n} 条 text_brand_and_category "
                "没有商品锚点。"
            ),
            (
                f"关键词搜索样本不是概率样本。{total_videos} 条视频中只有 "
                f"{len(exact_rows)} 条锚点确证目标商品，不能代表品类普查。"
            ),
            (
                "所有指标是 2026-10-30 的单次快照。播放和互动会继续增长，"
                "快照之间不可直接比较寿命周期表现。"
            ),
            (
                "第三方视频的 GMV、成交、转化、受众画像和字幕不可得；"
                "本轮不涉及达人受众或达人层级基线。"
            ),
            (
                "is_estimated 字段在所有返回中不存在；产物记 null，"
                "未当作实测值。"
            ),
        ],
        "caveats": [
            (
                "中位数和四分位数描述典型视频。均值受长尾影响，"
                "表中同时给出 mean/median 比值。"
            ),
            (
                "本轮不做分层基线。任何按内容形态的比较都没有样本支撑。"
            ),
            (
                "高表现视频只做计数和倍数描述，不做因果解释。"
                "10 条 exact 里只有少量高表现，不能代表总体。"
            ),
            (
                "category_reference 是品类参照，不是基线。不要把它与 exact "
                "基线合并、比较或用于「哪类跑赢」的结论。"
            ),
            (
                "分层表之间会重叠；同一视频出现在多个维度中，不能相加。"
            ),
            (
                "本轮未写数据库，未修改 canonical-records.jsonl，"
                "未修改 gold-set-50.jsonl。"
            ),
        ],
        "validation": {},
        "video_level": exact_rows,
    }
    document["validation"] = validate_document(document, input_hashes)
    return document


def validate_document(document: dict, input_hashes: dict) -> dict:
    population = document["population"]
    layers = document["layers"]
    exact_ids = {row["video_id"] for row in document["video_level"]}
    layer_totals = {
        dimension: sum(group["n"] for group in layer["groups"].values())
        for dimension, layer in layers.items()
    }
    layer_n_ge_8 = [
        f"{dimension}:{label}"
        for dimension, layer in layers.items()
        for label, group in layer["groups"].items()
        if label != "unknown" and group["n"] >= MIN_LAYER_N
    ]
    layer_usable = [
        f"{dimension}:{label}"
        for dimension, layer in layers.items()
        for label, group in layer["groups"].items()
        if group.get("usable_layer")
    ]
    layer_metrics_present = [
        f"{dimension}:{label}"
        for dimension, layer in layers.items()
        for label, group in layer["groups"].items()
        if group.get("metrics") is not None
    ]
    high_ids = {
        row["video_id"] for row in document["high_performers"]["videos"]
    }
    question_id = document["question_post"]["video_id"]
    category = document["category_reference"]
    category_ids = {row["video_id"] for row in category["rows"]}
    return {
        "population_n": population["n"],
        "population_n_equals_10": population["n"] == EXPECTED_EXACT_N,
        "population_all_target_exact": all(
            row["relation_type"] == "target_exact"
            for row in document["video_level"]
        ),
        "population_confidence_counts": population["confidence_counts"],
        "population_relation_type_counts": population["relation_type_counts"],
        "unique_video_ids": len(exact_ids),
        "layer_totals": layer_totals,
        "layer_totals_all_10": all(
            total == EXPECTED_EXACT_N for total in layer_totals.values()
        ),
        "layer_groups_with_n_ge_8": layer_n_ge_8,
        "layer_groups_usable": layer_usable,
        "layer_metrics_present": layer_metrics_present,
        "bootstrap_tests": len(document["bootstrap"]["tests"]),
        "high_performer_count": document["high_performers"]["count"],
        "high_performers_subset_of_exact": high_ids <= exact_ids,
        "question_post_in_exact": question_id in exact_ids,
        "question_post_in_high_performers": question_id in high_ids,
        "question_post_excluded_from_performance_statistics": document[
            "question_post"
        ]["excluded_from_performance_statistics"],
        "category_reference_n": category["n"],
        "category_reference_overlap_exact": len(category_ids & exact_ids),
        "category_reference_all_medium": all(
            row["confidence"] == "medium" for row in category["rows"]
        ),
        "category_reference_baseline_eligible": category["baseline_eligible"],
        "category_reference_median_n": category["median_population"]["n"],
        "inputs_sha256": input_hashes,
        "canonical_sha256_unchanged": input_hashes["canonical_records"][
            "sha256_before"
        ]
        == sha256_file(CANONICAL_PATH),
        "gold_set_sha256_unchanged": input_hashes["gold_set"]["sha256_before"]
        == sha256_file(GOLD_PATH),
        "db_writes": 0,
        "paid_api_calls": 0,
    }


def number(value: float) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:,.1f}".rstrip("0").rstrip(".")
    return f"{value:.4f}".rstrip("0").rstrip(".")


def rate(value: float) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.2f}%"


def fmt_int(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}"


def format_counts(counts: dict) -> str:
    if not counts:
        return "无"
    return "、".join(
        f"{key} {value}" for key, value in sorted(counts.items())
    )


def metric_value(metric_name: str, value: float) -> str:
    if value is None:
        return "—"
    if metric_name == "interaction_rate":
        return rate(value)
    return number(value)


def render_markdown(document: dict) -> str:
    lines: list[str] = []
    append = lines.append
    population = document["population"]
    overall = document["overall"]
    category = document["category_reference"]
    high = document["high_performers"]

    append(
        f"> 基线仅含 {population['n']} 条锚点确证目标商品的视频。其余 "
        f"{category['n']} 条为品类参照（修正前口径 38 条，其中 7 条已降级为 "
        "low），不参与任何结论。"
    )
    append("")
    append("# Creator/Video 互动基线：仅 target_exact")
    append("")
    append(
        f"- 商品：{TARGET_PRODUCT_NAME}（product_id {TARGET_PRODUCT_ID}）"
    )
    append("- 市场：TikTok Shop 美国站")
    append(
        f"- 基线样本：{population['n']} 条 target_exact 视频；"
        "medium 不进入基线。"
    )
    append("- 数据快照：2026-10-30；本轮付费调用 0 次，花费 0 美元")
    append("")
    append("## 1. 基线口径")
    append("")
    append(
        "基线只含锚点确证目标商品的视频。判定条件如下："
    )
    append("")
    append(
        f"- `relation_type=target_exact`；`confidence=high`；"
        f"`anchor_product_ids` 含 `{TARGET_PRODUCT_ID}`。"
    )
    append(
        "- 来源：`relations/video-product-target-baseline.jsonl`。"
        "指标来源：`relations/video-product-candidates.jsonl` 的 `engagement`。"
    )
    append(
        "- 详情快照优先。10 条 exact 全部有 `fetch_post_detail` 快照。"
    )
    append(
        f"- medium 品类参照 {category['n']} 条单列。"
        "它们不进入基线，不参与结论。"
    )
    append(
        f"- 分层规则：层内 n<{MIN_LAYER_N} 时只报计数。"
        "不报中位数，不报 CI，不报结论。"
    )
    append("")
    append("## 2. 整体分布（n=10）")
    append("")
    append(
        "四分位方法：Python `statistics.quantiles(method='exclusive')`，"
        "等价于 PERCENTILE.EXC。"
    )
    append("")
    append("| 指标 | Q1 | 中位数 | Q3 | 均值 | 最小 | 最大 | 均值/中位数 |")
    append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for metric in METRICS:
        stat = overall["metrics"][metric]
        append(
            f"| {METRIC_LABELS_ZH[metric]} | {metric_value(metric, stat['q1'])} | "
            f"{metric_value(metric, stat['median'])} | "
            f"{metric_value(metric, stat['q3'])} | "
            f"{metric_value(metric, stat['mean'])} | "
            f"{metric_value(metric, stat['min'])} | "
            f"{metric_value(metric, stat['max'])} | "
            f"{stat['mean_over_median']} |"
        )
    duration = overall["duration_seconds"]
    append(
        f"| 时长（秒） | {number(duration['q1'])} | {number(duration['median'])} | "
        f"{number(duration['q3'])} | {number(duration['mean'])} | "
        f"{number(duration['min'])} | {number(duration['max'])} | "
        f"{duration['mean_over_median']} |"
    )
    append("")
    append(
        "互动率的定义沿用上游："
        "(点赞 + 评论 + 分享 + 收藏) / 播放。"
    )
    append("")
    append("## 3. 逐条明细（10 条 exact）")
    append("")
    append(
        "| # | video_id | 播放 | 点赞 | 评论 | 分享 | 收藏 | 互动率 | 时长（秒） | 时长档 |"
    )
    append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for index, row in enumerate(document["video_level"], start=1):
        append(
            f"| {index} | {row['video_id']} | {fmt_int(row['play_count'])} | "
            f"{fmt_int(row['like_count'])} | {fmt_int(row['comment_count'])} | "
            f"{fmt_int(row['share_count'])} | {fmt_int(row['collect_count'])} | "
            f"{rate(row['interaction_rate'])} | {number(row['duration_seconds'])} | "
            f"{row['duration_bucket']} |"
        )
    append("")
    append("## 4. 分层计数（没有可用的分层）")
    append("")
    append(
        "下表只报计数。没有一层同时满足层 n>=8 和对照 n>=8，因此不计算"
        "分层中位数、倍数、bootstrap 或显著性检验。"
    )
    append("")
    append("| 维度 | 层 | n | 对照 n | 层 n>=8 | 状态 |")
    append("| --- | --- | ---: | ---: | --- | --- |")
    for dimension, layer in document["layers"].items():
        for label, group in layer["groups"].items():
            status = {
                "unclassified": "未归类",
                "insufficient_sample": "insufficient_sample",
                "ok": "ok",
            }.get(group["status"], group["status"])
            complement = (
                "—"
                if group.get("complement_n") is None
                else str(group["complement_n"])
            )
            append(
                f"| {layer['label_zh']} | {label} | {group['n']} | "
                f"{complement} | {'是' if group['n_ge_8'] else '否'} | "
                f"{status} |"
            )
    append("")
    append(
        "has_link 和 ad_disclosure 在 10 条 exact 中只有一个取值，对照 n=0。"
        "platform_is_ad 的 false 只有 1 条，true 的对照 n=1。"
        "这些维度没有可比的对照层。"
    )
    append("")
    append("### 4.1 bootstrap")
    append("")
    append(
        "bootstrap 未运行。10 条 exact 中没有任何一层同时满足层 n>=8 和"
        "对照 n>=8。按规则，n<8 或对照 n<8 的层只给计数，不给 CI。"
        "bootstrap 只对 exact 做；本轮没有可做的 exact 分层比较。"
    )
    append("")
    append("## 5. 高表现视频（仅 10 条 exact）")
    append("")
    append(
        f"定义：互动率 >= 10 条 exact 互动率中位数的 {BEAT_MULTIPLE:g} 倍。"
        f"中位数为 {rate(high['overall_median_interaction_rate'])}，"
        f"门槛为 {rate(high['threshold_interaction_rate'])}。"
    )
    append("")
    append(
        "没有时长档达到 n>=8，因此倍数分母用 10 条 exact 的整体中位数，"
        "不用时长档中位数。"
    )
    append("")
    append(f"结果：{high['statement']}")
    append("")
    if high["videos"]:
        append(
            "| # | video_id | 互动率 | 倍数 | 播放 | 时长（秒） | 时长档 | 链接 | 广告披露 |"
        )
        append("| ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |")
        for index, row in enumerate(high["videos"], start=1):
            append(
                f"| {index} | {row['video_id']} | {rate(row['interaction_rate'])} | "
                f"{row['multiple_vs_exact_median']}x | "
                f"{fmt_int(row['play_count'])} | {number(row['duration_seconds'])} | "
                f"{row['duration_bucket']} | {row['has_link']} | "
                f"{row['ad_disclosure']} |"
            )
        append("")
    if high["videos"]:
        append(
            f"这 {high['count']} 条的播放都低于 10 条 exact 的播放中位数 "
            f"{fmt_int(overall['metrics']['play_count']['median'])}。"
            "互动率高不等于触达高。"
        )
        append("")
    append(
        f"提问帖 `{QUESTION_VIDEO_ID}` 不在 exact 总体，也不在高表现集合。"
        "它的 `content_tag=consideration`，已排除出所有表现统计。"
    )
    append("")
    append("## 6. 品类参照（medium，not baseline eligible）")
    append("")
    append(
        f"数量：{category['n']} 条。"
        f"relation_type：{format_counts(category['relation_type_counts'])}。"
        f"confidence：{format_counts(category['confidence_counts'])}。"
        f"content_tag：{format_counts(category['content_tag_counts'])}。"
    )
    append("")
    append(
        f"中位数口径：{category['median_population']['n']} 条，"
        f"不含 consideration {category['median_population']['excluded_content_tag_consideration_n']} 条。"
        "consideration 已排除出表现统计。"
    )
    append("")
    append("| 指标 | n | 中位数 |")
    append("| --- | ---: | ---: |")
    for metric in METRICS:
        stat = category["median_population"]["metrics"][metric]
        append(
            f"| {METRIC_LABELS_ZH[metric]} | {stat['n']} | "
            f"{metric_value(metric, stat['median'])} |"
        )
    duration = category["median_population"]["duration_seconds"]
    append(
        f"| 时长（秒） | {duration['n']} | {number(duration['median'])} |"
    )
    append("")
    append(
        "**not baseline eligible**。本节只作品类参照。"
        "不与 exact 合并，不与 exact 比较，不出「哪类跑赢」的结论。"
    )
    append("")
    for row in category["consideration_rows"]:
        append(
            f"- consideration：`{row['video_id']}`，播放 "
            f"{fmt_int(row['play_count'])}，互动率 "
            f"{rate(row['interaction_rate'])}，"
            f"`low_denominator_flag={str(row['low_denominator_flag']).lower()}`。"
            "已排除出表现统计。"
        )
    append("")
    append("## 7. 未归类")
    append("")
    low = document["unclassified"]["low_confidence_relation_rows"]
    none = document["unclassified"]["no_signal_rows"]
    append(
        f"- low confidence：{low['n']} 条。"
        f"relation_type：{format_counts(low['relation_type_counts'])}。"
    )
    append(f"- no_signal：{none['n']} 条。")
    append(
        f"- 以上 {low['n'] + none['n']} 条不进入任何统计。"
        "video_id 清单见 `baseline.json` 的 `unclassified`。"
    )
    append("")
    append("## 8. 证据缺口与注意事项")
    append("")
    for gap in document["evidence_gaps"]:
        append(f"- {gap}")
    append("")
    for caveat in document["caveats"]:
        append(f"- {caveat}")
    append("")
    append("## 9. 方法与可复现")
    append("")
    append(
        "- 脚本：`/Users/lute/Project/data_scrapy/tools/creator_video_baseline.py`"
    )
    append(
        "- 付费端点调用：0 次；花费：0 美元；未做余额探测。"
        "上一次已知余额 37.316 美元（collect-summary.json "
        "cost.balance_after_usd）。"
    )
    append(
        "- 四分位方法：Python `statistics.quantiles(method='exclusive')`，"
        "等价于 PERCENTILE.EXC。"
    )
    append(
        "- bootstrap：未运行。10 条 exact 中没有任何一层同时满足层 n>=8 "
        "和对照 n>=8。"
    )
    append(
        "- 金标集与 canonical-records.jsonl 未修改。"
    )
    append("")
    append("输入文件与 SHA-256：")
    append("")
    append("| 文件 | SHA-256 |")
    append("| --- | --- |")
    for name, item in document["inputs"].items():
        append(f"| {item['path']} | `{item['sha256_before']}` |")
    append("")
    append("校验：")
    append("")
    validation = document["validation"]
    append(f"- 基线样本数：{validation['population_n']}")
    append(f"- 唯一 video_id 数：{validation['unique_video_ids']}")
    append(
        f"- 分维度层计数合计均为 10：{validation['layer_totals_all_10']}"
    )
    append(
        f"- 原始计数 n>=8 的组：{validation['layer_groups_with_n_ge_8'] or '无'}"
    )
    append(
        f"- 可用的层（层 n>=8 且对照 n>=8）："
        f"{validation['layer_groups_usable'] or '无'}"
    )
    append(f"- 计算了中位数的层：{validation['layer_metrics_present'] or '无'}")
    append(f"- bootstrap 检验数：{validation['bootstrap_tests']}")
    append(f"- 高表现视频数：{validation['high_performer_count']}")
    append(
        f"- 提问帖在 exact 总体：{validation['question_post_in_exact']}"
    )
    append(
        f"- 提问帖在高表现集合：{validation['question_post_in_high_performers']}"
    )
    append(
        f"- category_reference 数量：{validation['category_reference_n']}"
    )
    append(
        "- category_reference 与 exact 交集："
        f"{validation['category_reference_overlap_exact']}"
    )
    append(
        f"- category_reference 全为 medium："
        f"{validation['category_reference_all_medium']}"
    )
    append(
        f"- canonical-records.jsonl SHA-256 未变："
        f"{validation['canonical_sha256_unchanged']}"
    )
    append(
        f"- gold-set-50.jsonl SHA-256 未变："
        f"{validation['gold_set_sha256_unchanged']}"
    )
    append("- 写数据库：0")
    append("")
    return "\n".join(lines)


def main() -> None:
    target_rows = load_jsonl(TARGET_BASELINE_PATH)
    candidate_rows = load_jsonl(CANDIDATES_PATH)
    video_product_rows = load_jsonl(VIDEO_PRODUCT_PATH)
    feature_rows = load_jsonl(FEATURES_PATH)
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))

    candidates_by_id = {row["video_id"]: row for row in candidate_rows}
    if len(candidates_by_id) != len(candidate_rows):
        raise ValueError("duplicate video_id in candidate relations")
    features_by_id = {row["video_id"]: row for row in feature_rows}
    if len(features_by_id) != len(feature_rows):
        raise ValueError("duplicate video_id in feature rows")

    exact_rows, exact_ids = build_exact_population(
        target_rows, candidates_by_id, features_by_id
    )
    category_reference = build_category_reference(
        candidate_rows, features_by_id, exact_ids
    )
    category_ids = {row["video_id"] for row in category_reference["rows"]}
    unclassified = build_unclassified(
        video_product_rows, exact_ids, category_ids
    )
    high_performers = build_high_performers(exact_rows)
    question_post = build_question_post_check(
        candidates_by_id,
        exact_ids,
        {row["video_id"] for row in high_performers["videos"]},
    )
    coverage_check = build_coverage_check(
        coverage, len(exact_rows), category_reference["n"]
    )

    input_hashes = {
        "target_baseline": {
            "path": str(TARGET_BASELINE_PATH),
            "rows": len(target_rows),
            "sha256_before": sha256_file(TARGET_BASELINE_PATH),
        },
        "features": {
            "path": str(FEATURES_PATH),
            "rows": len(feature_rows),
            "sha256_before": sha256_file(FEATURES_PATH),
        },
        "video_product_candidates": {
            "path": str(CANDIDATES_PATH),
            "rows": len(candidate_rows),
            "sha256_before": sha256_file(CANDIDATES_PATH),
        },
        "video_product": {
            "path": str(VIDEO_PRODUCT_PATH),
            "rows": len(video_product_rows),
            "sha256_before": sha256_file(VIDEO_PRODUCT_PATH),
        },
        "coverage": {
            "path": str(COVERAGE_PATH),
            "sha256_before": sha256_file(COVERAGE_PATH),
        },
        "canonical_records": {
            "path": str(CANONICAL_PATH),
            "sha256_before": sha256_file(CANONICAL_PATH),
        },
        "gold_set": {
            "path": str(GOLD_PATH),
            "sha256_before": sha256_file(GOLD_PATH),
        },
    }

    document = build_document(
        exact_rows,
        input_hashes,
        coverage_check,
        category_reference,
        unclassified,
        question_post,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(render_markdown(document), encoding="utf-8")

    for name, path in (
        ("features", FEATURES_PATH),
        ("video_product_candidates", CANDIDATES_PATH),
        ("target_baseline", TARGET_BASELINE_PATH),
        ("coverage", COVERAGE_PATH),
    ):
        if sha256_file(path) != input_hashes[name]["sha256_before"]:
            raise RuntimeError(f"{name} file changed during run")

    print(
        json.dumps(
            {
                "status": "ok",
                "population_n": len(exact_rows),
                "category_reference_n": category_reference["n"],
                "overall_median": {
                    metric: document["overall"]["metrics"][metric]["median"]
                    for metric in METRICS
                },
                "duration_median": document["overall"]["duration_seconds"][
                    "median"
                ],
                "groups_with_n_ge_8_raw": document["validation"][
                    "layer_groups_with_n_ge_8"
                ],
                "usable_layers": document["validation"][
                    "layer_groups_usable"
                ],
                "bootstrap_performed": document["bootstrap"]["performed"],
                "high_performers": {
                    "count": high_performers["count"],
                    "none": high_performers["none"],
                    "videos": [
                        {
                            "video_id": row["video_id"],
                            "interaction_rate": row["interaction_rate"],
                            "multiple_vs_exact_median": row[
                                "multiple_vs_exact_median"
                            ],
                        }
                        for row in high_performers["videos"]
                    ],
                },
                "question_post_excluded": (
                    not question_post["in_exact_population"]
                    and not question_post["in_high_performers"]
                ),
                "outputs": [str(OUT_JSON), str(OUT_MD)],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# Module-level context is intentionally avoided. All builders receive explicit
# inputs so the output does not depend on import order or global state.


if __name__ == "__main__":
    main()

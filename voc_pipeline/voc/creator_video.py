"""Load the creator/video snapshot artifacts for report integration.

The video layer is a separate population from the review corpus.  Its unit is
``video_id``; the review layer's unit is ``review_id``.  There is no join key
between them in this run, so the two layers never share a denominator.

This module only reads artifacts that the creator-video collection produced.
It does not call a paid endpoint, does not write to ``canonical-records.jsonl``
or ``gold-set-50.jsonl``, and does not invent a value when a field is absent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "voc_creator_video_report_summary_v1"

# Fixed input order keeps ``input_sha256`` stable across rebuilds.
INPUT_FILES: tuple[tuple[str, Path], ...] = (
    ("baseline", Path("creator-video/baseline/baseline.json")),
    ("coverage", Path("creator-video/relations/coverage.json")),
    ("features", Path("creator-video/features/feature-distribution.json")),
    ("comment_video_gap", Path("creator-video/relations/comment-video-gap.json")),
    ("collect_summary", Path("creator-video/collect-summary.json")),
    ("video_creator", Path("creator-video/relations/video-creator.jsonl")),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _layer_summary(baseline: dict[str, Any]) -> dict[str, Any]:
    """Keep only the layer fields the report renders.

    The source baseline already applies the n>=8 rule: a group below the floor
    has ``metrics=null`` and ``status=insufficient_sample``.  This function
    preserves that status so the renderer can exclude the group instead of
    printing a median that does not exist.
    """
    out: dict[str, Any] = {}
    for dimension, layer in (baseline.get("layers") or {}).items():
        groups: dict[str, Any] = {}
        for name, group in (layer.get("groups") or {}).items():
            metrics = group.get("metrics") or {}
            lift = group.get("lift_vs_complement") or {}
            ci = lift.get("bootstrap_median_ratio_ci95") or [None, None]
            groups[name] = {
                "n": group.get("n"),
                "status": group.get("status"),
                "confidence_counts": group.get("confidence_counts") or {},
                "relation_type_counts": group.get("relation_type_counts") or {},
                "play_median": (metrics.get("play_count") or {}).get("median"),
                "interaction_median": (metrics.get("interaction_rate") or {}).get("median"),
                "complement_n": lift.get("complement_n"),
                "complement_median": lift.get("complement_median"),
                "multiple": lift.get("median_multiple"),
                "p_value": lift.get("mann_whitney_u_p_two_sided"),
                "ci95": [ci[0], ci[1]] if len(ci) >= 2 else [None, None],
            }
        out[dimension] = {
            "label_zh": layer.get("label_zh"),
            "dimension_status": layer.get("dimension_status"),
            "groups": groups,
        }
    return out


def _feature_counts(features: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, row in (features.get("features") or {}).items():
        out[name] = {
            "true": row.get("true"),
            "false": row.get("false"),
            "unknown": row.get("unknown"),
            "total": row.get("total"),
        }
    return out


def _high_performer_rows(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (baseline.get("high_performers") or {}).get("videos") or []:
        rows.append(
            {
                "video_id": row.get("video_id"),
                "duration_bucket": row.get("duration_bucket"),
                "play_count": row.get("play_count"),
                "interaction_rate": row.get("interaction_rate"),
                "multiple": row.get("multiple_vs_duration_bucket_median"),
                "relation_confidence": row.get("relation_confidence"),
                "relation_type": row.get("relation_type"),
                "has_link": row.get("has_link"),
                "ad_disclosure": row.get("ad_disclosure"),
                "low_denominator_flag": row.get("low_denominator_flag"),
            }
        )
    return rows


def _common_features(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    """Co-occurrence counts, never a causal explanation.

    ``value == "unknown"`` rows say nothing about the high performers and are
    left out of the rendered table; the unknown total is published separately.
    """
    items = (baseline.get("high_performers") or {}).get("common_features") or {}
    rows: list[dict[str, Any]] = []
    for item in items.get("items") or []:
        if item.get("value") == "unknown":
            continue
        rows.append(
            {
                "field": item.get("field"),
                "value": item.get("value"),
                "count": item.get("count_in_high_performers"),
                "share_high": item.get("share_in_high_performers"),
                "population_count": item.get("count_in_population"),
                "share_population": item.get("share_in_population"),
            }
        )
    return rows


def _creator_ids_by_video(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        video_id = str(row.get("video_id") or "")
        creator_id = str(row.get("creator_id") or "")
        if video_id and creator_id:
            out[video_id] = creator_id
    return out


def _evidence_gaps(
    comment_gap: dict[str, Any],
    features: dict[str, Any],
    coverage: dict[str, Any],
    collect: dict[str, Any],
    high_performer_n: int,
) -> list[str]:
    """Short Chinese gap sentences a reader can act on.

    The source artifacts carry longer English notes.  These sentences keep the
    same facts and add no value that is not in the artifacts.
    """
    availability = features.get("field_availability") or {}
    transcript = availability.get("transcript_or_audio", 0)
    comment_evidence = comment_gap.get("evidence") or {}
    canonical_reviews = comment_evidence.get("canonical_tiktok_shop_rows", 0)
    raw_reviews = comment_evidence.get("raw_review_rows", 0)
    inventory = coverage.get("video_inventory") or {}
    videos_total = inventory.get("unique_videos", 0)
    videos_detail = inventory.get("videos_with_detail_snapshot", 0)
    creators_total = inventory.get("unique_authors_in_search_sample", 0)
    creators_profile = inventory.get("creators_with_profile", 0)
    search_queries = (collect.get("counts") or {}).get("search_queries", 12)
    gaps = [
        (
            "商品 → 视频完整列表：TIKHUB_TIKTOK_CREATOR_COOKIE 未配置；"
            "get_product_related_videos 与 get_video_associated_product_list 都返回 no login。"
        ),
        (
            f"评论 → 视频：{canonical_reviews} 条 canonical 评论和 {raw_reviews} 条 raw 评论"
            "都没有 video_id/aweme_id/item_id，可关联率为 0%。"
        ),
        (
            f"搜索分页：cursor=20 会重复第一页；{search_queries} 个关键词各只取 1 页，"
            f"{videos_total} 条视频不是品类普查。"
        ),
        (
            f"视频详情：{videos_detail}/{videos_total} 有 fetch_post_detail；"
            f"{videos_total - videos_detail} 条只有搜索快照。"
        ),
        (
            f"达人档案：{creators_profile}/{creators_total} 有档案；"
            f"{creators_total - creators_profile} 位只有搜索 author 字段，"
            "粉丝数是搜索快照值。"
        ),
        (
            f"视觉与口播：transcript_or_audio={transcript}；"
            "before_after、unboxing、visual_only 全部 unknown 48/48。"
        ),
        (
            "第三方视频 GMV、成交与转化：TikHub 只给登录创作者自己的数据；"
            "第三方视频不可得。"
        ),
        (
            "达人受众性别/年龄/地区：只有登录账号自己的 get_video_audience_stats；"
            "第三方达人不可得。"
        ),
        (
            f"达人层级基线：本轮未做；高表现视频只有 {high_performer_n} 条，"
            "不能按粉丝层级分层。"
        ),
        (
            "18 个 SKU 与销量 22140：现有评论 raw 没有，需商品详情源复核。"
        ),
        (
            "重复 listing：同一标题对应多个 product_id，未合并；"
            "目标商品视频覆盖可能被低估。"
        ),
    ]
    return gaps


def load_summary(run_dir: Path) -> dict[str, Any]:
    """Read one run's creator-video artifacts and derive report inputs.

    Returns ``{"available": False, ...}`` when the baseline artifact is absent.
    A missing artifact is an Evidence gap, never a reason to invent numbers.
    """
    base = Path(run_dir)
    paths = {name: base / rel for name, rel in INPUT_FILES}
    missing = [str(path) for path in paths.values() if not path.exists()]
    core = ("baseline", "coverage", "features", "comment_video_gap", "video_creator")
    missing_core = [name for name in core if not paths[name].exists()]
    if missing_core:
        return {
            "schema_version": SCHEMA_VERSION,
            "available": False,
            "reason": f"creator-video artifacts are missing: {', '.join(missing_core)}",
            "missing": missing,
            "expected_paths": {name: str(path) for name, path in paths.items()},
        }

    baseline = _read_json(paths["baseline"])
    coverage = _read_json(paths["coverage"]) if paths["coverage"].exists() else {}
    features = _read_json(paths["features"]) if paths["features"].exists() else {}
    comment_gap = (
        _read_json(paths["comment_video_gap"]) if paths["comment_video_gap"].exists() else {}
    )
    collect = (
        _read_json(paths["collect_summary"]) if paths["collect_summary"].exists() else {}
    )
    creator_rows = (
        _read_jsonl(paths["video_creator"]) if paths["video_creator"].exists() else []
    )

    digest = hashlib.sha256()
    input_files: dict[str, Any] = {}
    for name, rel in INPUT_FILES:
        path = paths[name]
        if not path.exists():
            input_files[name] = {"path": str(path), "sha256": None, "missing": True}
            continue
        sha = _sha256(path)
        input_files[name] = {"path": str(path), "sha256": sha, "missing": False}
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())

    inventory = coverage.get("video_inventory") or {}
    target = coverage.get("video_product_target") or {}
    confidence = target.get("confidence_distribution") or {}
    population = baseline.get("population") or {}
    baseline_rows = baseline.get("video_level") or []
    baseline_ids = {str(row.get("video_id")) for row in baseline_rows}
    creators_by_video = _creator_ids_by_video(creator_rows)
    baseline_creators = {
        creators_by_video[video_id]
        for video_id in baseline_ids
        if video_id in creators_by_video
    }
    high_rows = _high_performer_rows(baseline)
    high_creators = {
        creators_by_video[str(row.get("video_id"))]
        for row in high_rows
        if str(row.get("video_id")) in creators_by_video
    }
    strongest = baseline.get("strongest_single_feature") or {}
    top_layer = strongest.get("top_layer") or {}
    sensitivity = strongest.get("top_layer_sensitivity") or {}

    def _rate(name: str) -> float | None:
        row = ((baseline.get("overall") or {}).get("metrics") or {}).get(name) or {}
        return row.get("median")

    layers = _layer_summary(baseline)
    duration = layers.get("duration_bucket", {}).get("groups", {})
    link = layers.get("has_link", {}).get("groups", {})
    ad = layers.get("ad_disclosure", {}).get("groups", {})

    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "generated_at": baseline.get("generated_at"),
        "input_sha256": digest.hexdigest(),
        "input_files": input_files,
        "videos_total": inventory.get("unique_videos"),
        "videos_with_detail": inventory.get("videos_with_detail_snapshot"),
        "videos_search_only": inventory.get("videos_without_detail_snapshot"),
        "creators_total": inventory.get("unique_authors_in_search_sample"),
        "creators_with_profile": inventory.get("creators_with_profile"),
        "creators_profile_exact": inventory.get("creators_profile_exact"),
        "creators_profile_partial": inventory.get("creators_profile_partial"),
        "relation_confidence": {
            "high": confidence.get("high", 0),
            "medium": confidence.get("medium", 0),
            "low": confidence.get("low", 0),
            "none": confidence.get("none", 0),
        },
        "relation_types": population.get("relation_type_counts") or {},
        "baseline_n": population.get("n"),
        "baseline_confidence": population.get("confidence_counts") or {},
        "baseline_medium_n": (population.get("confidence_counts") or {}).get("medium"),
        "baseline_creators": len(baseline_creators),
        "target_exact_n": (
            target.get("target_coverage") or {}
        ).get("exact_product_id_high"),
        "category_anchor_verified_n": (
            target.get("target_coverage") or {}
        ).get("category_anchor_verified"),
        "overall": {
            "play_median": _rate("play_count"),
            "interaction_median": _rate("interaction_rate"),
        },
        "layers": layers,
        "high_performers": {
            "n": (baseline.get("high_performers") or {}).get("count"),
            "threshold_multiple": (
                baseline.get("high_performers") or {}
            ).get("threshold_multiple"),
            "creators": len(high_creators),
            "rows": high_rows,
            "common_features": _common_features(baseline),
            "low_play_n": sum(1 for row in high_rows if row.get("low_denominator_flag")),
            "play_floor_n": (
                (baseline.get("high_performers") or {}).get("low_denominator_sensitivity") or {}
            ).get("count"),
            "medium_relation_n": sum(
                1 for row in high_rows if row.get("relation_confidence") == "medium"
            ),
        },
        "strongest": {
            "dimension": top_layer.get("dimension"),
            "dimension_label": top_layer.get("dimension_label_zh"),
            "layer": top_layer.get("layer"),
            "n": top_layer.get("n"),
            "median": top_layer.get("layer_median_interaction_rate"),
            "complement_n": top_layer.get("complement_n"),
            "complement_median": top_layer.get("complement_median_interaction_rate"),
            "multiple": top_layer.get("median_multiple"),
            "p_value": top_layer.get("mann_whitney_u_p_two_sided"),
            "ci95": top_layer.get("bootstrap_median_ratio_ci95") or [None, None],
            "verdict": strongest.get("verdict"),
            "top_layer_relation_type_counts": (
                strongest.get("top_layer_relation_type_counts") or {}
            ),
            "sensitivity_exclude_text_n": (
                sensitivity.get("exclude_relation_type_text_brand_and_category") or {}
            ).get("n"),
            "sensitivity_play_floor_n": (
                sensitivity.get("play_count_floor_5000") or {}
            ).get("n"),
        },
        "layers_seen": {
            "duration_16_30": duration.get("16-30s") or {},
            "duration_31_60": duration.get("31-60s") or {},
            "duration_gt_60": duration.get(">60s") or {},
            "duration_le_15": duration.get("<=15s") or {},
            "has_link_true": link.get("true") or {},
            "has_link_false": link.get("false") or {},
            "ad_true": ad.get("true") or {},
            "ad_false": ad.get("false") or {},
        },
        "feature_availability": features.get("field_availability") or {},
        "feature_counts": _feature_counts(features),
        "duration_buckets": features.get("duration_buckets") or {},
        "comment_video": {
            "rows": comment_gap.get("relation_count", 0),
            "coverage_rate": comment_gap.get("coverage_rate", 0.0),
            "canonical_reviews": (
                (comment_gap.get("evidence") or {}).get("canonical_tiktok_shop_rows")
            ),
            "raw_reviews": ((comment_gap.get("evidence") or {}).get("raw_review_rows")),
        },
        "sufficiency": baseline.get("sufficiency_assessment") or {},
        "gaps": _evidence_gaps(
            comment_gap,
            features,
            coverage,
            collect,
            (baseline.get("high_performers") or {}).get("count") or 0,
        ),
        "caveats": baseline.get("caveats") or [],
        "source_evidence_gaps": {
            "baseline": baseline.get("evidence_gaps") or [],
            "collect": collect.get("evidence_gaps") or [],
        },
    }

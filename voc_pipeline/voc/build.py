"""Build the run artifacts and the report."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import canonical, claims as claims_mod, coder, creator_video, llm_coder, metrics, report, validate_report
from .contracts import forbidden_conclusions_payload
from .gates import GATES
from .taxonomy import taxonomy_dict

ROOT = Path(__file__).resolve().parent.parent
CROSS_MODEL_STATS_PATH = Path("calibration") / "cross-model" / "cross-model-stats.json"
PRODUCT_MATCH_OVERRIDES_PATH = Path("product_match_overrides.json")


def load_identity(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "amazon-identity-raw.json"
    if not path.exists():
        return {"asins": [], "products": {}, "fetched_at": "unavailable"}
    raw = json.loads(path.read_text())
    child = "B0HC2FG4QC" if "B0HC2FG4QC" in raw.get("products", {}) else next(iter(raw.get("products", {})), "")
    product = raw.get("products", {}).get(child, {})
    return {
        "asins": raw.get("asins", []),
        "products": raw.get("products", {}),
        "fetched_at": raw.get("fetched_at"),
        "child_asin": child,
        "title": product.get("title"),
        "variant_count": product.get("variant_count", 0),
        "rating_value": product.get("rating_value"),
        "rating_count_text": product.get("rating_count_text"),
        "ledger": raw.get("ledger", {}),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _frame_chain(
    records: list[Any],
    coded: list[Any],
    corpus: dict[str, Any],
    frame: str,
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Six-level count for one frame, with a reason code on every decrease.

    The chain is deliberately not a funnel: the annotation level counts hits,
    not people, and the metric level stays at zero while G7 is blocked.
    """
    source = "tiktok_shop" if frame == "tiktok_shop_verified" else "reddit"
    frame_records = [r for r in records if frame in r.frames]
    ids = {r.canonical_id for r in frame_records}
    frame_coded = [c for c in coded if c.canonical_id in ids]
    annotations = sum(len(c.annotations) for c in frame_coded)
    decisive_polarities = {"positive", "qualified_positive", "negative", "qualified_negative"}
    aspect_records = sum(
        1
        for c in frame_coded
        if any(a.axis == "aspect" and a.polarity in decisive_polarities for a in c.annotations)
    )
    raw = int(corpus.get("raw_by_source", {}).get(source, 0))
    if frame == "tiktok_shop_verified" and stats:
        raw = int(stats.get("raw_rows", raw))
        occurrence = int(stats.get("unique_reviews", raw - int(stats.get("duplicate_review_ids", 0))))
        product_mismatch = int(stats.get("quarantined", 0))
        out_of_window = int(stats.get("out_of_window", 0))
    else:
        occurrence = raw - int(corpus.get("within_frame_overlap_dropped", 0))
        product_mismatch = 0
        out_of_window = 0
    text_records = [r for r in frame_records if r.text.strip()]
    codable = [r for r in text_records if r.language == "en"]
    return {
        "frame": frame,
        "raw_object": {"count": raw, "note": "成功响应里的 provider rows"},
        "occurrence": {"count": occurrence, "deductions": {"duplicate_external_id": raw - occurrence}},
        "canonical": {
            "count": len(frame_records),
            "deductions": {
                "product_mismatch": product_mismatch,
                "out_of_window": out_of_window,
            },
        },
        "frame_membership": {
            "count": sum(1 for r in records if frame in r.frames),
            "deductions": {},
            "note": "单 frame 记录；跨 frame 重叠不计入本 frame",
        },
        "annotation": {
            "count": annotations,
            "unit": "annotation hits（多标签）",
            "record_deductions": {
                "no_text_low_information": len(frame_records) - len(text_records),
                "language_uncodable": len(text_records) - len(codable),
                "no_decisive_aspect": len(codable) - aspect_records,
            },
            "records_with_decisive_aspect": aspect_records,
        },
        "metric_row": {
            "count": 0,
            "reason": "G7 BLOCKED：没有第二编码员与逐字段 agreement",
        },
        "balance": {
            "occurrence_to_canonical": occurrence - len(frame_records)
            == product_mismatch + out_of_window,
            "annotation_records": len(frame_records)
            == (len(frame_records) - len(text_records))
            + (len(text_records) - len(codable))
            + (len(codable) - aspect_records)
            + aspect_records,
        },
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _code_corpus(
    records: list[Any],
    run_dir: Path,
    coder_mode: str | None,
    min_confidence: str | None = None,
    source_run_dir: Path | None = None,
) -> tuple[list[Any], str, str | None]:
    """Run the selected single coder.  LLM is the default; rule is the baseline.

    The switch exists so the old lexicon coder can be rebuilt for comparison.
    It is intentionally explicit: a missing LLM artifact raises instead of
    silently falling back to the rule coder, which would mix two coders and
    make the published accuracy meaningless.

    ``llm-v2`` replays the re-coded artifact at
    ``<source_run_dir>/llm-coding-v2/coded/ALL.jsonl``.  The default remains
    ``llm`` (v1), so the published run is unchanged unless the caller asks for
    v2 explicitly.  ``source_run_dir`` defaults to ``run_dir``.

    Returns the coded records, the coder id, and the confidence threshold in
    effect (``None`` for the rule coder, which has no confidence field).
    """
    mode = (coder_mode or os.environ.get("VOC_CODER") or "llm").strip().lower()
    source = Path(source_run_dir) if source_run_dir is not None else Path(run_dir)
    if mode == "llm":
        minimum = llm_coder.resolve_min_confidence(min_confidence)
        return (
            llm_coder.code_corpus(
                records,
                run_dir=run_dir,
                min_confidence=minimum,
                scope_audit_file=llm_coder.scope_audit_path(run_dir),
                coder_id=llm_coder.CODER_ID,
            ),
            llm_coder.CODER_ID,
            minimum,
        )
    if mode == "llm-v2":
        minimum = llm_coder.resolve_min_confidence(min_confidence)
        return (
            llm_coder.code_corpus(
                records,
                run_dir=run_dir,
                coded_file=llm_coder.coded_path_v2(source),
                dropped_file=llm_coder.dropped_path(run_dir),
                min_confidence=minimum,
                scope_audit_file=llm_coder.scope_audit_path(run_dir),
                coder_id=llm_coder.CODER_ID_V2,
            ),
            llm_coder.CODER_ID_V2,
            minimum,
        )
    if mode == "rule":
        # The rule coder has no confidence field or frozen experience gate.
        # Remove stale audit files so the run directory never claims another
        # coder's abstentions or scope audit.
        llm_coder.dropped_path(run_dir).unlink(missing_ok=True)
        llm_coder.scope_audit_path(run_dir).unlink(missing_ok=True)
        llm_coder.compat_experience_diff_path(run_dir).unlink(missing_ok=True)
        return coder.code_corpus(records), "rule-v1", None
    raise ValueError(f"unknown coder mode {mode!r}; expected 'llm', 'llm-v2' or 'rule'")


def build(
    run_dir: Path,
    coder_mode: str | None = None,
    min_confidence: str | None = None,
    source_run_dir: Path | None = None,
) -> dict[str, Any]:
    """Build one run into ``run_dir``.

    ``source_run_dir`` supplies the frozen inputs (collection ledgers, PDP
    identity, TikTok stats, eval and cross-model artifacts) when the output is
    a comparison directory such as ``run-20261029-v2``.  It defaults to
    ``run_dir`` so the published build behaves exactly as before.
    """
    run_dir = Path(run_dir)
    source = Path(source_run_dir) if source_run_dir is not None else run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_paths = sorted(source.glob("collection-run-ledger*.json"))
    tiktok_ledger = source / "tiktok-shop-ledger.json"
    if tiktok_ledger.exists():
        ledger_paths.append(tiktok_ledger)
    if not ledger_paths:
        raise FileNotFoundError(f"no collection ledger in {source}")
    identity = load_identity(source)
    occurrences = canonical.occurrences_from_ledger(ledger_paths)
    overrides = canonical.load_product_match_overrides(ROOT / PRODUCT_MATCH_OVERRIDES_PATH)
    records, corpus = canonical.build_canonical(
        occurrences, product_match_overrides=overrides
    )
    # The old conflict audit described a disagreement the merged model cannot
    # express.  Remove it so a run directory never carries two audit schemas.
    (run_dir / "scope-conflicts.json").unlink(missing_ok=True)
    coded, coder_id, min_confidence_applied = _code_corpus(
        records, run_dir, coder_mode, min_confidence, source
    )
    # Fail closed on a forbidden field/aspect combination before any artifact
    # is written (E-merge §2.3).
    validate_report.validate_coded_corpus(records, coded)
    corpus["coder_id"] = coder_id
    # E-merge §3.2: the transition writer still emits ``experience`` on each
    # coded row, but it is a derived view of ``in_experience_cohort``.  The
    # schema metadata says so; consumers must not use it as a gate.
    corpus["coded_contract_version"] = "E-merge/1"
    corpus["deprecated_coded_fields"] = {
        "experience": {
            "deprecated": True,
            "derived_from": "in_experience_cohort",
            "gate": "product_match in {exact_current_family, category_adjacent} AND experience_scope in {full, partial} AND text non-empty",
        },
        "scope_conflict": {"removed": True, "reason": "fields are orthogonal under E-merge"},
    }
    if min_confidence_applied is not None:
        corpus["min_confidence"] = min_confidence_applied
        corpus["confidence_filter"] = {
            "min_confidence": min_confidence_applied,
            "dropped_aspects": sum(
                1
                for record in coded
                for item in record.unknown_aspects
                if item.get("reason") == llm_coder.CONFIDENCE_DROP_REASON
            ),
        }
    metric = metrics.materialize_metrics(records, coded, g7_status="BLOCKED")
    metric["cooccurrence"] = metrics.cooccurrence(records, coded)
    natural_ids = {r.canonical_id for r in records if "natural" in r.frames}
    metric["aspect_polarity_counts_natural"] = metrics.aspect_polarity_counts(
        [c for c in coded if c.canonical_id in natural_ids and c.in_cohort]
    )
    metric["diversity"] = metrics.author_and_thread_diversity(records)
    from collections import Counter as _Counter
    metric["product_match_counts"] = dict(_Counter(r.product_match for r in records))
    metric["eligibility_counts"] = dict(_Counter(r.metric_eligibility for r in records))

    artifact_sha = _identity_sha(identity)
    import hashlib as _hashlib
    corpus_sha = _hashlib.sha256(
        json.dumps([r.to_dict() for r in records], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    tiktok_stats = _load_json(source / "tiktok-shop-collection-stats.json")
    corpus["frame_chains"] = {
        "tiktok_shop_verified": _frame_chain(records, coded, corpus, "tiktok_shop_verified", tiktok_stats),
    }
    quarantine_path = source / "tiktok-shop-quarantine.jsonl"
    quarantine_sha = (
        _hashlib.sha256(quarantine_path.read_bytes()).hexdigest() if quarantine_path.exists() else None
    )
    # The creator/video layer is a separate population.  Load its frozen
    # artifacts, derive a report summary, and pass the summary to claims and
    # the renderer.  A missing artifact becomes an Evidence gap, not a guess.
    creator_video_summary = creator_video.load_summary(source)
    claim_list = claims_mod.build_claims(
        records,
        coded,
        corpus,
        metric,
        {**identity, "variant_count": identity.get("variant_count")},
        taxonomy_id=taxonomy_dict()["taxonomy_id"],
        artifact_sha=artifact_sha,
        corpus_sha=corpus_sha,
        tiktok_stats=tiktok_stats,
        tiktok_quarantine_sha=quarantine_sha,
        creator_video=creator_video_summary,
    )
    # Recommendations are not evidence and must not occupy a claim grade.
    recommendation_list = claims_mod.build_recommendations(claim_list)

    gate_status = {
        "G0": "CONDITIONAL",
        "G1": "PASS",
        "G2": "CONDITIONAL",
        "G3": "PASS",
        "G4": "PASS",
        "G5": "PASS",
        "G6": "PASS",
        "G7": "BLOCKED",
        "G8": "BLOCKED",
        "G9": "BLOCKED",
        "G10": "NOT_STARTED",
    }

    write_json(run_dir / "voc-research-charter.json", _charter())
    write_json(run_dir / "source-rights-matrix.json", _rights_matrix())
    write_json(run_dir / "consumer-metric-view-contract.json", _metric_contract())
    canonical.write_jsonl(run_dir / "occurrences.jsonl", (o.to_dict() for o in occurrences))
    canonical.write_jsonl(run_dir / "canonical-records.jsonl", (r.to_dict() for r in records))
    canonical.write_jsonl(run_dir / "coded-corpus.jsonl", (c.to_dict() for c in coded))
    write_json(run_dir / "corpus-summary.json", corpus)
    write_json(run_dir / "frame-chains.json", corpus.get("frame_chains", {}))
    write_json(run_dir / "metric-summary.json", metric)
    write_json(run_dir / "creator-video-summary.json", creator_video_summary)
    write_json(run_dir / "claims.json", claims_mod.claims_to_dict(claim_list))
    write_json(run_dir / "recommendations.json", recommendation_list)
    write_json(run_dir / "taxonomy.json", taxonomy_dict())
    write_json(run_dir / "gate-ledger.json", _gate_ledger(gate_status, identity, corpus, metric))
    write_json(run_dir / "evidence-grade-report.json", {
        "grades": claims_mod.grade_distribution(claim_list),
        "claims": [{"claim_id": c.claim_id, "grade": c.grade.value} for c in claim_list],
    })
    write_json(run_dir / "forbidden-conclusions.json", forbidden_conclusions_payload())

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    run_id = run_dir.name
    if coder_id == "rule-v1":
        precision = None
    elif coder_id == llm_coder.CODER_ID_V2:
        precision = llm_coder.load_eval_precision(
            source, llm_coder.eval_result_path_v2(source)
        )
    else:
        precision = llm_coder.load_eval_precision(source)
    if coder_id != "rule-v1" and precision is None:
        # The published precision must come from the frozen eval artifact.
        # Falling back to constants here would make the report unrecomputable.
        eval_path = (
            llm_coder.eval_result_path_v2(source)
            if coder_id == llm_coder.CODER_ID_V2
            else llm_coder.eval_result_path(source)
        )
        raise FileNotFoundError(f"missing LLM eval artifact: {eval_path}")
    claim_sources = report.build_claim_source_profiles(
        claim_list, records, coded, corpus, precision
    )
    cross_model = _load_json(source / CROSS_MODEL_STATS_PATH) or None
    out = report.render_report(
        run_dir / "report.html",
        generated_at=generated_at,
        identity=identity,
        corpus=corpus,
        metric=metric,
        claims=claim_list,
        gate_status=gate_status,
        run_id=run_id,
        recommendations=recommendation_list,
        coder_id=coder_id,
        precision=precision,
        cross_model=cross_model,
        claim_sources=claim_sources,
        creator_video=creator_video_summary,
    )
    # Fail closed at render time: a forbidden shape never leaves this process.
    try:
        validate_report.assert_report_clean(out, run_dir / "claims.json")
    except validate_report.ForbiddenConclusionError:
        out.unlink(missing_ok=True)
        raise
    return {
        "report": str(out),
        "corpus": corpus,
        "claims": len(claim_list),
        "recommendations": len(recommendation_list),
        "metric_rows": len(metric["metric_rows"]),
        "creator_video": {
            "available": bool(creator_video_summary.get("available")),
            "videos": creator_video_summary.get("videos_total"),
            "creators": creator_video_summary.get("creators_total"),
            "baseline_videos": creator_video_summary.get("baseline_n"),
        },
        "run_dir": str(run_dir),
    }


def _charter() -> dict[str, Any]:
    return {
        "schema_version": "voc_research_charter_v1",
        "decision_question": (
            "是否继续把“轻薄可穿”作为核心定位，还是先补支撑梯度与选码引导？"
        ),
        "decision_owner": "UNASSIGNED — requires business sign-off",
        "product": {
            "brand": "Momcozy",
            "name": "BumpEase / CozySupport 3D Ergonest Maternity Belly Band",
            "parent_asin": "B0H8LVJ81X",
            "target_child_asin": "B0HC2FG4QC",
            "target_variant": "Oyster Pink / Small",
        },
        "market": "US",
        "language": "en",
        "window": {"start": "2024-01-01", "end": "2026-10-29"},
        "channels": [
            "Reddit public archive",
            "Amazon product detail page",
            "TikTok Shop product reviews (TikHub, verified-purchase)",
            "TikTok public videos and creator profiles (TikHub, keyword-search sample)",
        ],
        "frames": [
            {"frame": "natural", "purpose": "方向性观察", "denominator_rule": "关键词召回的 canonical consumer records；非概率样本"},
            {"frame": "diagnostic", "purpose": "失败模式发现", "denominator_rule": "自然 frame 中含产品失败措辞的子集；不得估计发生率"},
            {"frame": "qualitative_seed", "purpose": "假设与品牌级线索", "denominator_rule": "品牌提及；不进入 consumer metric"},
            {
                "frame": "tiktok_shop_verified",
                "purpose": "购买者方向验证",
                "denominator_rule": (
                    "product_id=1729474995478630680、verified_purchase=true、"
                    "窗口 2026-07-01..2026-10-29 且通过 SKU 身份隔离的评论；"
                    "掩码 reviewer 名，非账号 id；不得跨 frame 比较"
                ),
            },
        ],
        "qa_thresholds": {
            "semantic_core_cohen_kappa_min": 0.80,
            "identity_governance_cohen_kappa_min": 0.90,
            "risk_case_review_coverage": 1.0,
        },
        "budget": {
            "provider_cost_usd_cap": 15.0,
            "soft_cap_usd": 2.0,
            "paid_api": True,
            "note": "TikHub TikTok Shop reviews 与 creator/video 采集；视频层本轮 measured 约 0.13 USD",
        },
        "publication_boundary": "internal_only; no external claims, no full-text republication",
        "stop_conditions": [
            "任一来源 rights 状态变为 denied",
            "产品身份出现无法裁决的 child ASIN 冲突",
            "G7 agreement 未达阈值",
        ],
        "gate_plan": ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10"],
    }


def _rights_matrix() -> dict[str, Any]:
    return {
        "schema_version": "voc_source_rights_matrix_v1",
        "sources": [
            {
                "source": "reddit_public_archive",
                "access_route": "Arctic Shift public API",
                "rights_state": "public_read",
                "privacy_state": "public_usernames; no PII collected beyond author handle",
                "commerciality": "mixed; commercial disclosure detected per record",
                "content_role": "consumer unless brand/creator detected",
                "allowed_use": ["internal research", "aggregate analysis", "short excerpt with attribution"],
                "forbidden_use": ["full-text republication", "user profiling", "external publication of quotes without review"],
                "metric_eligible": True,
            },
            {
                "source": "amazon_pdp",
                "access_route": "public product detail page",
                "rights_state": "public_read",
                "privacy_state": "no personal data",
                "commerciality": "brand-owned listing",
                "content_role": "identity_evidence",
                "allowed_use": ["identity verification", "variant inventory"],
                "forbidden_use": ["review republication", "star distribution as sentiment metric"],
                "metric_eligible": False,
            },
        {
                "source": "tiktok_shop_reviews",
                "access_route": "TikHub GET /api/v1/tiktok/shop/web/fetch_product_reviews_v2",
                "rights_state": "public_read",
                "privacy_state": "reviewer names returned masked; no account ids or avatars stored",
                "commerciality": "mixed; is_incentivized_review recorded per record",
                "content_role": "verified buyer unless incentivized",
                "allowed_use": ["internal research", "aggregate analysis", "direction verification"],
                "forbidden_use": [
                    "review republication",
                    "star distribution as sentiment metric",
                    "treating masked handles as verified unique people",
                ],
                "metric_eligible": True,
            },
            {
                "source": "tiktok_video_public",
                "access_route": (
                    "TikHub GET /api/v1/tiktok/app/v3/fetch_video_search_result; "
                    "GET /api/v1/tiktok/web/fetch_post_detail; "
                    "GET /api/v1/tiktok/web/fetch_user_profile"
                ),
                "rights_state": "public_read",
                "privacy_state": (
                    "public creator handles and follower counts; "
                    "no audience demographics stored"
                ),
                "commerciality": "mixed; platform_is_ad and ad disclosure recorded per video",
                "content_role": "creator_content",
                "allowed_use": [
                    "internal research",
                    "aggregate analysis",
                    "format and creator selection",
                ],
                "forbidden_use": [
                    "video republication",
                    "creator profiling",
                    "causal performance claims",
                    "GMV or conversion estimates",
                ],
                "metric_eligible": True,
            },
        ],
        "blocked_sources": [
            {"source": "amazon_review_text", "reason": "requires authenticated session; current route returns 302"},
        ],
    }


def _metric_contract() -> dict[str, Any]:
    return {
        "schema_version": "voc_consumer_metric_view_contract_v1",
        "taxonomy_id": taxonomy_dict()["taxonomy_id"],
        "eligible_predicate": [
            "duplicate_representative == true",
            "data_layer == consumer_observation_fact",
            "product_match in {exact_current_family, category_adjacent}",
            "content_role == consumer_experience",
            "commerciality == no_signal_observed",
            "metric_eligibility in {natural_sample_candidate, diagnostic_sample_only, qualitative_seed_only, tiktok_verified_candidate}",
            "organic_confidence in {high, medium}",
            "for tiktok_shop_verified: verified_purchase == true AND identity_noise == none",
        ],
        "experience_cohort": {
            "predicate": "product_match in {exact_current_family, category_adjacent} AND experience_scope in {full, partial} AND text non-empty",
            "contract_version": "E-merge/1",
            "note": "Consumers must not filter on experience_scope alone; off-target evaluations exist and never enter a product claim.",
        },
        "frame_denominators": {
            "natural": "eligible natural consumer records",
            "diagnostic": "never used as prevalence denominator",
            "qualitative_seed": "never used as consumer denominator",
            "tiktok_shop_verified": (
                "eligible verified-purchase canonical reviews in the 2026-07-01..2026-10-29 window; "
                "one direction per record; never compared with natural or diagnostic percentages"
            ),
        },
        "video_layer": {
            "population": "unique videos from keyword search with a high/medium product relation",
            "denominator": "48 baseline-eligible videos; not a probability sample",
            "unit": "video_id; one row per video",
            "not_mergeable_with": (
                "tiktok_shop_verified reviews: review_id is the unit and no video join key exists"
            ),
            "support_gate": (
                "layer n>=8 AND bootstrap 95% CI excludes 1 AND sensitivity group n>=8"
            ),
        },
        "qa_state": "blocked_g7_not_executed",
        "metric_rows_authorized": 0,
    }


def _identity_sha(identity: dict[str, Any]) -> str | None:
    rows = identity.get("ledger", {}).get("rows", [])
    for row in rows:
        if row.get("endpoint") == "pdp" and row.get("sha256"):
            return row["sha256"]
    return None


def _gate_ledger(status: dict[str, str], identity: dict[str, Any], corpus: dict[str, Any], metric: dict[str, Any]) -> dict[str, Any]:
    gates = []
    for gate in GATES:
        gates.append(
            {
                "gate_id": gate.gate_id,
                "name": gate.name,
                "status": status.get(gate.gate_id, "NOT_STARTED"),
                "accept": gate.accept,
                "rollback": gate.rollback,
                "fail_closed": gate.fail_closed,
                "owner": gate.owner,
            }
        )
    return {
        "schema_version": "voc_gate_ledger_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gates": gates,
        "stage_boundary": {
            "G6_complete": status.get("G6") == "PASS",
            "G7_executed": False,
            "G8_authorized": False,
            "consumer_metric_rows": len(metric["metric_rows"]),
        },
        "does_not_authorize": [
            "overall consumer sentiment rates",
            "Love versus Complaint prevalence",
            "cross-frame percentage comparison",
            "annotation hits as people",
            "Amazon star distribution as consumer sentiment",
            "medical efficacy, safety, diagnosis or causality",
            "formal strategy prioritization without G9 approval",
        ],
        "evidence_summary": {
            "variant_count_live": identity.get("variant_count", 0),
            "raw_objects": corpus["raw_objects"],
            "occurrences": corpus["occurrences_deduplicated"],
            "canonical_records": corpus["canonical_records"],
            "frame_memberships": corpus["frame_memberships"],
            "annotations": sum(metric["annotation_totals"].values()),
            "metric_rows": len(metric["metric_rows"]),
            "tiktok_shop_verified": corpus.get("frame_chains", {}).get("tiktok_shop_verified", {}),
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the VOC run artifacts and report.")
    parser.add_argument(
        "--run-dir",
        default=str(ROOT / "artifacts" / "run-20261029"),
        help="output run directory (created when missing)",
    )
    parser.add_argument(
        "--source-run-dir",
        default=None,
        help="frozen input run directory; defaults to --run-dir",
    )
    parser.add_argument(
        "--coder",
        choices=["llm", "llm-v2", "rule"],
        default=None,
        help="single coder to use; default llm, VOC_CODER overrides when omitted",
    )
    parser.add_argument(
        "--min-confidence",
        choices=["high", "medium", "all"],
        default=None,
        help="LLM aspect confidence gate; default high",
    )
    args = parser.parse_args(argv)
    result = build(
        Path(args.run_dir),
        coder_mode=args.coder,
        min_confidence=args.min_confidence,
        source_run_dir=Path(args.source_run_dir) if args.source_run_dir else None,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

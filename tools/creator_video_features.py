#!/usr/bin/env python3
"""Extract deterministic content-form features for product-associated videos.

Population:
    Every video with product-relation confidence high or medium in
    relations/video-product-candidates.jsonl. Low-confidence and no-signal
    videos are intentionally excluded.

Inputs (read-only):
    artifacts/run-20261029/creator-video/relations/video-product-candidates.jsonl
    artifacts/run-20261029/creator-video/raw/video-details.json
    artifacts/run-20261029/creator-video/raw/video-search-*.json

Outputs (new files only):
    artifacts/run-20261029/creator-video/features/video-features.jsonl
    artifacts/run-20261029/creator-video/features/feature-rules.json
    artifacts/run-20261029/creator-video/features/feature-distribution.json

The script never writes canonical-records.jsonl or gold-set-50.jsonl. It makes
no network calls and costs nothing.

Feature policy:
    Every feature is three-state: true / false / "unknown".
    - true means an explicit, reproducible cue is present in a named field.
    - false is used only where the named fields can actually exclude the
      feature (platform boolean, missing product anchor with a detail payload,
      absent numeric token in a non-empty caption).
    - "unknown" means the available fields cannot answer. Caption silence is
      NOT treated as evidence of absence for visual/audio content forms,
      because the caption is not the video.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone

SCHEMA_VERSION = "voc_video_features_v1"
FEATURE_ORDER = [
    "comparison",
    "demo",
    "before_after",
    "unboxing",
    "problem_solution",
    "visual_only",
    "has_link",
    "ad_disclosure",
    "opens_with_question",
    "has_number_claim",
]

# ---------------------------------------------------------------------------
# Rule registry. Patterns are applied to the accent-stripped, lowercased
# caption with hashtags, mentions and URLs removed.
# ---------------------------------------------------------------------------

COMPARISON_CAPTION_PATTERNS = [
    ("vs", r"\bvs\.?\b"),
    ("versus", r"\bversus\b"),
    ("compare", r"\bcompar(e|es|ed|ing|ison)\b"),
    ("better_than", r"\bbetter than\b"),
    ("worse_than", r"\bworse than\b"),
    ("which_one", r"\bwhich one\b"),
    ("side_by_side", r"\bside[- ]by[- ]side\b"),
    ("head_to_head", r"\bhead[- ]to[- ]head\b"),
    ("dupe", r"\bdupes?\b"),
    ("comparacion_es", r"\bcomparaci[oó]n\b|\bcomparar\b"),
    ("mejor_que_es", r"\bmejor que\b"),
]
COMPARISON_HASHTAGS = {"vs", "versus", "comparison", "compared", "dupe", "dupes"}

DEMO_CAPTION_PATTERNS = [
    ("how_to", r"\bhow to\b"),
    ("how_i_use", r"\bhow i (use|wear|put|apply)\b"),
    ("tutorial", r"\btutorial\b"),
    ("step_by_step", r"\bstep[- ]by[- ]step\b"),
    ("demonstration", r"\bdemonstrat(e|es|ed|ing|ion)\b"),
    ("demo", r"\bdemos?\b"),
    ("show_you", r"\b(show|shows|showing) you\b"),
    ("we_show", r"\bwe show\b"),
    ("let_me_show", r"\blet me show\b"),
    ("heres_how", r"\bhere'?s how\b"),
    ("in_this_video", r"\bin this video\b"),
    ("watch_how", r"\bwatch how\b"),
    ("como_usar_es", r"\bc[oó]mo (usar|usarlo|poner|ponerlo)\b"),
    ("paso_a_paso_es", r"\bpaso a paso\b"),
    ("te_muestro_es", r"\bte muestro\b"),
]
DEMO_HASHTAGS = {"tutorial", "howto", "howtouse"}

BEFORE_AFTER_CAPTION_PATTERNS = [
    ("before_and_after", r"\bbefore (and|&|/) after\b"),
    ("before_vs_after", r"\bbefore\s*(vs\.?|versus)\s*after\b"),
    ("before_after_joined", r"\bbefore[-/]after\b"),
    ("transformation", r"\btransformation\b"),
    ("then_vs_now", r"\bthen vs\.? now\b"),
    ("results_after", r"\bresults? after\b"),
    ("weeks_apart", r"\bweeks? apart\b"),
    ("antes_y_despues_es", r"\bantes y despu[eé]s\b"),
    ("transformacion_es", r"\btransformaci[oó]n\b"),
]
BEFORE_AFTER_HASHTAGS = {
    "beforeafter",
    "beforeandafter",
    "transformation",
    "bumpprogress",
    "pregnancyprogress",
    "bumpupdate",
}

UNBOXING_CAPTION_PATTERNS = [
    ("unbox", r"\bunbox(ing|ed|es)?\b"),
    ("haul", r"\bhaul\b"),
    ("first_impression", r"\bfirst impression\b"),
    ("mail_call", r"\bmail call\b"),
    ("pr_package", r"\bpr package\b"),
    ("package_arrived", r"\bpackage (came|arrived)\b"),
    ("opening_package", r"\bopening (my|the|a) package\b"),
]
UNBOXING_HASHTAGS = {
    "unboxing",
    "unbox",
    "haul",
    "firstimpression",
    "prpackage",
    "mailcall",
}

PROBLEM_PATTERNS = [
    ("pain", r"\bpain(s|ful|fully)?\b"),
    ("ache", r"\bach(e|es|y|ing)\b"),
    ("hurt", r"\bhurt(s|ing)?\b"),
    ("discomfort", r"\bdiscomfort\b"),
    ("pressure", r"\bpressure\b"),
    ("heavy", r"\bheav(y|ier|iest)\b"),
    ("struggle", r"\bstruggl(e|es|ed|ing)\b"),
    ("problem", r"\bproblems?\b"),
    ("sore", r"\bsore\b"),
    ("uncomfortable", r"\buncomfortable\b"),
    ("killing_me", r"\bkilling me\b"),
    ("hard_to_carry", r"\bhard(er)? to carry\b"),
    ("dolor_es", r"\bdolor\b"),
    ("molestia_es", r"\bmolestia\b"),
    ("presion_es", r"\bpresi[oó]n\b"),
]
SOLUTION_PATTERNS = [
    ("relief", r"\brelief\b"),
    ("relieve", r"\breliev(e|es|ed|ing)\b"),
    ("help", r"\bhelp(s|ed|ing)?\b"),
    ("support", r"\bsupport(s|ed|ing)?\b"),
    ("solve", r"\bsolv(e|es|ed|ing)\b"),
    ("fix", r"\bfix(es|ed)?\b"),
    ("game_changer", r"\bgame changer\b"),
    ("comfort", r"\bcomfort(able)?\b"),
    ("ease", r"\beas(e|es|ed|ing)\b"),
    ("lift", r"\blift(s|ed|ing)?\b"),
    ("saved_my", r"\bsaved my\b"),
    ("lifesaver", r"\blifesaver\b"),
    ("makes_it_easier", r"\bmakes? it easier\b"),
    ("take_pressure_off", r"\btake the pressure off\b"),
    ("alivio_es", r"\balivi(o|a|ar|ado|ada|an)\b"),
    ("ayuda_es", r"\bayud(a|as|an|ar|ado|ada|ando|o|ó)\b"),
    ("soporte_es", r"\bsoport(e|a|as|an|ar|ado|ada)\b"),
    ("comodidad_es", r"\bcomodidad\b|\bc[oó]mod(o|a|os|as)\b"),
    ("sostener_es", r"\bsostener\b|\bsostiene(n)?\b|\bsujet(a|ar|ado|ada)\b"),
]

AD_DISCLOSURE_CAPTION_PATTERNS = [
    ("ad_prefix", r"(^|[\s|])ad(?=[\s|:!.,]|$)"),
    ("sponsored", r"\bsponsored\b"),
    ("paid_partnership", r"\bpaid partnership\b"),
    ("gifted_by", r"\bgifted by\b"),
    ("affiliate", r"\baffiliate\b"),
    ("commission", r"\bcommission\b"),
]
AD_DISCLOSURE_HASHTAGS = {
    "ad",
    "sponsored",
    "paidpartnership",
    "tiktokshoppartner",
    "shoppartner",
    "affiliate",
    "commission",
    "gifted",
}

LINK_CAPTION_PATTERNS = [
    ("url", r"https?://\S+"),
    ("www", r"\bwww\.\S+"),
    ("link_in_bio", r"\blinks? in (my )?bio\b"),
    ("link_below", r"\blink below\b"),
    ("storefront", r"\bstorefront\b"),
]

COUPON_CAPTION_PATTERNS = [
    ("use_code", r"\buse (my |the )?code\b"),
    ("coupon", r"\bcoupon\b"),
    ("promo_code", r"\bpromo code\b"),
    ("discount", r"\bdiscount\b"),
    ("percent_off", r"\b\d+(?:\.\d+)?\s*%\s*off\b"),
    ("code_token", r"\bcode\s+[A-Z0-9]{4,}\b"),
]
COUPON_HASHTAGS = {"discount", "coupon", "promocode", "sale", "deals", "blackfriday"}

CTA_CAPTION_PATTERNS = [
    ("grab_yours", r"\bgrab (yours|your|one|them)\b"),
    ("get_yours", r"\bget yours\b"),
    ("shop_now", r"\bshop now\b"),
    ("order_now", r"\border (yours|now)\b"),
    ("check_out", r"\bcheck (it|them) out\b"),
    ("link_in_bio", r"\blinks? in (my )?bio\b"),
    ("click_link", r"\bclick the link\b"),
    ("use_code", r"\buse (my |the )?code\b"),
    ("available_at", r"\bavailable (at|on)\b"),
]

BRAND_MENTION_RE = re.compile(r"@mom\s?cozy[a-z0-9_.]*", re.IGNORECASE)

INTERROGATIVE_FIRST_WORDS = {
    "what",
    "why",
    "how",
    "which",
    "who",
    "whom",
    "whose",
    "when",
    "where",
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "have",
    "has",
    "had",
}

NUMBER_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])|\d+(?:st|nd|rd|th)(?![A-Za-z0-9]))",
    re.IGNORECASE,
)
HASHTAG_NUMBER_RE = re.compile(r"^(\d+)(weeks?|wks?|months?|days?|st|nd|rd|th)", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#[^\s#]+")
MENTION_RE = re.compile(r"@[^\s@]+")
URL_RE = re.compile(r"https?://\S+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_jsonl(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    return strip_accents(text).lower()


def clean_caption(desc: str) -> str:
    """Remove hashtags, mentions and URLs; keep the prose and punctuation."""
    text = URL_RE.sub(" ", desc or "")
    text = HASHTAG_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_patterns(blob: str, patterns: list[tuple[str, str]]) -> list[str]:
    hits: list[str] = []
    for label, pattern in patterns:
        if re.search(pattern, blob, re.IGNORECASE):
            hits.append(label)
    return hits


def match_hashtags(hashtags: set[str], wanted: set[str]) -> list[str]:
    return sorted(hashtags & wanted)


def feature_source(
    value,
    rule_id: str,
    fields: list[str],
    matched: list[str] | None = None,
    reason: str | None = None,
    detail: dict | None = None,
) -> dict:
    source = {
        "value": value,
        "rule_id": rule_id,
        "fields": fields,
        "matched": matched or [],
        "reason": reason,
    }
    if detail:
        source.update(detail)
    return source


def tri_state(value: bool, true_reason: str | None = None, false_reason: str | None = None) -> bool | str:
    if value:
        return True
    if false_reason is not None:
        return False
    return "unknown"


# ---------------------------------------------------------------------------
# Input assembly
# ---------------------------------------------------------------------------


def parse_detail_products(detail: dict) -> list[dict]:
    """Return product dicts carried by a normalized fetch_post_detail record.

    Path in the normalized payload:
        anchors[].extra (JSON string) -> list[wrapper]
        wrapper.extra (JSON string) -> product object
        product.extra (JSON object) -> {"ad_label_name": "#sponsored", ...}
    """
    products: list[dict] = []
    for anchor in detail.get("anchors") or []:
        cur = anchor.get("extra")
        if isinstance(cur, str):
            try:
                cur = json.loads(cur)
            except (TypeError, ValueError):
                continue
        if not isinstance(cur, list):
            continue
        for wrapper in cur:
            if not isinstance(wrapper, dict):
                continue
            product = wrapper.get("extra")
            if isinstance(product, str):
                try:
                    product = json.loads(product)
                except (TypeError, ValueError):
                    continue
            if not isinstance(product, dict):
                continue
            inner = product.get("extra")
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except (TypeError, ValueError):
                    inner = {}
            if not isinstance(inner, dict):
                inner = {}
            pid = product.get("product_id") or wrapper.get("id")
            if pid is None:
                continue
            products.append(
                {
                    "product_id": str(pid),
                    "keyword": product.get("title") or wrapper.get("keyword"),
                    "ad_label_name": inner.get("ad_label_name"),
                    "source": inner.get("source") or product.get("source"),
                }
            )
    return products


def parse_search_product_ids(aweme_info: dict) -> list[str]:
    ids: list[str] = []
    for anchor in aweme_info.get("anchors") or []:
        cur = anchor.get("extra")
        if isinstance(cur, str):
            try:
                cur = json.loads(cur)
            except (TypeError, ValueError):
                continue
        if isinstance(cur, dict):
            cur = [cur]
        if not isinstance(cur, list):
            continue
        for item in cur:
            if isinstance(item, dict) and item.get("id") is not None:
                ids.append(str(item["id"]))
    return ids


def load_search_index(raw_dir: str) -> dict[str, dict]:
    """Aggregate every search payload per video.

    Duplicate retrievals of the same video across keywords are collapsed.
    Values are checked for consistency; conflicts are recorded, not averaged.
    """
    index: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(raw_dir, "video-search-*.json"))):
        payload = load_json(path)
        data = payload.get("data") or {}
        for item in data.get("search_item_list") or []:
            info = item.get("aweme_info") or {}
            vid = str(info.get("aweme_id") or "")
            if not vid:
                continue
            entry = index.setdefault(
                vid,
                {
                    "desc": set(),
                    "durations_ms": set(),
                    "hashtags": set(),
                    "product_anchor_ids": set(),
                    "captured_at": set(),
                    "raw_files": set(),
                    "request_ids": set(),
                },
            )
            if info.get("desc"):
                entry["desc"].add(info["desc"])
            duration = (info.get("video") or {}).get("duration")
            if duration is not None:
                entry["durations_ms"].add(int(duration))
            for tag in info.get("text_extra") or []:
                name = tag.get("hashtag_name")
                if name:
                    entry["hashtags"].add(name)
            entry["product_anchor_ids"].update(parse_search_product_ids(info))
            entry["captured_at"].add(payload.get("time_iso") or payload.get("time") or "")
            entry["raw_files"].add(path)
            entry["request_ids"].add(str(payload.get("request_id") or ""))
    return index


def resolve_single(values: set, field: str, video_id: str, conflicts: list[dict]):
    values = {v for v in values if v not in (None, "")}
    if not values:
        return None
    if len(values) > 1:
        conflicts.append(
            {
                "video_id": video_id,
                "field": field,
                "values": sorted(str(v) for v in values),
            }
        )
        return sorted(str(v) for v in values)[0]
    return next(iter(values))


def build_records(run_dir: str) -> tuple[list[dict], list[dict], dict]:
    relations_dir = os.path.join(run_dir, "relations")
    raw_dir = os.path.join(run_dir, "raw")
    candidates_path = os.path.join(relations_dir, "video-product-candidates.jsonl")

    candidates = load_jsonl(candidates_path)
    population = [r for r in candidates if r.get("confidence") in ("high", "medium")]
    population.sort(key=lambda r: (r["confidence"] != "high", r["video_id"]))

    details = {
        str(v["video_id"]): v for v in load_json(os.path.join(raw_dir, "video-details.json"))["videos"]
    }
    search_index = load_search_index(raw_dir)

    conflicts: list[dict] = []
    records: list[dict] = []

    for relation in population:
        vid = str(relation["video_id"])
        detail = details.get(vid)
        search = search_index.get(vid, {})
        search_desc = resolve_single(search.get("desc", set()), "desc", vid, conflicts)
        search_duration_ms = resolve_single(
            search.get("durations_ms", set()), "video.duration", vid, conflicts
        )

        caption = (detail or {}).get("desc") or search_desc or ""
        caption_clean = clean_caption(caption)

        detail_tags = [
            tag.get("name")
            for tag in ((detail or {}).get("hashtags") or [])
            if isinstance(tag, dict) and tag.get("name")
        ]
        search_tags = sorted(search.get("hashtags", set()))
        hashtags = sorted({t for t in detail_tags if t} | set(search_tags))
        hashtag_norm = {normalize(t).lstrip("#") for t in hashtags}

        if detail and detail.get("duration_seconds") is not None:
            duration_seconds = float(detail["duration_seconds"])
            duration_source = "fetch_post_detail.duration_seconds"
        elif search_duration_ms is not None:
            duration_seconds = round(int(search_duration_ms) / 1000.0, 3)
            duration_source = "fetch_video_search_result.data.search_item_list[].aweme_info.video.duration / 1000"
        else:
            duration_seconds = None
            duration_source = "absent"

        detail_products = parse_detail_products(detail) if detail else []
        detail_anchor_ids = {p["product_id"] for p in detail_products}
        search_anchor_ids = set(search.get("product_anchor_ids", set()))
        all_anchor_ids = sorted(detail_anchor_ids | search_anchor_ids)
        ad_labels = sorted({p["ad_label_name"] for p in detail_products if p.get("ad_label_name")})

        fields_available = {
            "caption": bool(caption),
            "caption_source": (
                "fetch_post_detail.data.itemInfo.desc"
                if detail and detail.get("desc")
                else "fetch_video_search_result.data.search_item_list[].aweme_info.desc"
            ),
            "hashtags": bool(hashtags),
            "hashtag_source": (
                "union(fetch_post_detail.hashtags[].name, "
                "fetch_video_search_result.data.search_item_list[].aweme_info.text_extra[].hashtag_name)"
                if hashtags
                else "absent"
            ),
            "duration": duration_seconds is not None,
            "duration_source": duration_source,
            "detail_payload": bool(detail),
            "search_payload": bool(search),
            "product_anchor": bool(all_anchor_ids),
            "platform_is_ad": detail is not None,
            "platform_is_ec_video": detail is not None,
        }

        # ---------------- structure features ----------------
        cmp_hits = match_patterns(caption_clean, COMPARISON_CAPTION_PATTERNS)
        cmp_tag_hits = match_hashtags(hashtag_norm, COMPARISON_HASHTAGS)
        cmp_matched = cmp_hits + [f"#{t}" for t in cmp_tag_hits]
        if cmp_matched:
            comparison = True
            comparison_source = feature_source(
                True,
                "comparison_v1",
                ["caption_clean", "hashtags_normalized"],
                cmp_matched,
                reason="explicit comparison cue",
            )
        else:
            comparison = "unknown"
            comparison_source = feature_source(
                "unknown",
                "comparison_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="caption_has_no_comparison_cue",
                detail={"note": "caption silence cannot exclude a visual comparison"},
            )

        demo_hits = match_patterns(caption_clean, DEMO_CAPTION_PATTERNS)
        demo_tag_hits = match_hashtags(hashtag_norm, DEMO_HASHTAGS)
        demo_matched = demo_hits + [f"#{t}" for t in demo_tag_hits]
        if demo_matched:
            demo = True
            demo_source = feature_source(
                True,
                "demo_v1",
                ["caption_clean", "hashtags_normalized"],
                demo_matched,
                reason="explicit how-to/demo cue",
            )
        else:
            demo = "unknown"
            demo_source = feature_source(
                "unknown",
                "demo_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="caption_has_no_demo_cue",
                detail={"note": "caption silence cannot exclude an on-screen demonstration"},
            )

        ba_hits = match_patterns(caption_clean, BEFORE_AFTER_CAPTION_PATTERNS)
        ba_tag_hits = match_hashtags(hashtag_norm, BEFORE_AFTER_HASHTAGS)
        ba_matched = ba_hits + [f"#{t}" for t in ba_tag_hits]
        if ba_matched:
            before_after = True
            before_after_source = feature_source(
                True,
                "before_after_v1",
                ["caption_clean", "hashtags_normalized"],
                ba_matched,
                reason="explicit before/after or progress cue",
            )
        else:
            before_after = "unknown"
            before_after_source = feature_source(
                "unknown",
                "before_after_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="caption_has_no_before_after_cue",
                detail={"note": "caption silence cannot exclude an on-screen before/after"},
            )

        unbox_hits = match_patterns(caption_clean, UNBOXING_CAPTION_PATTERNS)
        unbox_tag_hits = match_hashtags(hashtag_norm, UNBOXING_HASHTAGS)
        unbox_matched = unbox_hits + [f"#{t}" for t in unbox_tag_hits]
        if unbox_matched:
            unboxing = True
            unboxing_source = feature_source(
                True,
                "unboxing_v1",
                ["caption_clean", "hashtags_normalized"],
                unbox_matched,
                reason="explicit unboxing/haul cue",
            )
        else:
            unboxing = "unknown"
            unboxing_source = feature_source(
                "unknown",
                "unboxing_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="caption_has_no_unboxing_cue",
                detail={"note": "caption silence cannot exclude an on-screen unboxing"},
            )

        problem_blob = caption_clean + " " + " ".join(sorted(hashtag_norm))
        problem_hits = match_patterns(problem_blob, PROBLEM_PATTERNS)
        solution_hits = match_patterns(problem_blob, SOLUTION_PATTERNS)
        if problem_hits and solution_hits:
            problem_solution = True
            problem_solution_source = feature_source(
                True,
                "problem_solution_v1",
                ["caption_clean", "hashtags_normalized"],
                [f"problem:{h}" for h in problem_hits] + [f"solution:{h}" for h in solution_hits],
                reason="problem cue and solution cue both present",
            )
        elif problem_hits:
            problem_solution = "unknown"
            problem_solution_source = feature_source(
                "unknown",
                "problem_solution_v1",
                ["caption_clean", "hashtags_normalized"],
                [f"problem:{h}" for h in problem_hits],
                reason="partial_cue_problem_only",
            )
        elif solution_hits:
            problem_solution = "unknown"
            problem_solution_source = feature_source(
                "unknown",
                "problem_solution_v1",
                ["caption_clean", "hashtags_normalized"],
                [f"solution:{h}" for h in solution_hits],
                reason="partial_cue_solution_only",
            )
        else:
            problem_solution = "unknown"
            problem_solution_source = feature_source(
                "unknown",
                "problem_solution_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="caption_has_no_problem_or_solution_cue",
            )

        visual_only = "unknown"
        visual_only_source = feature_source(
            "unknown",
            "visual_only_v1",
            ["audio", "transcript", "subtitle"],
            [],
            reason="no_audio_or_transcript_field",
            detail={
                "note": (
                    "TikHub payloads expose no transcript or audio. "
                    "fetch_post_detail.data.itemInfo.video.claInfo only reports auto-caption "
                    "availability, not whether the creator speaks."
                )
            },
        )

        # ---------------- duration ----------------
        if duration_seconds is None:
            duration_bucket = "unknown"
        elif duration_seconds <= 15:
            duration_bucket = "<=15s"
        elif duration_seconds <= 30:
            duration_bucket = "16-30s"
        elif duration_seconds <= 60:
            duration_bucket = "31-60s"
        else:
            duration_bucket = ">60s"

        # ---------------- link ----------------
        link_hits = match_patterns(caption, LINK_CAPTION_PATTERNS)
        shop_product_flag = bool((detail or {}).get("has_shop_product"))
        if all_anchor_ids or link_hits or shop_product_flag:
            has_link = True
            has_link_evidence = [f"product_anchor:{pid}" for pid in all_anchor_ids] + link_hits
            if shop_product_flag:
                has_link_evidence.append("has_shop_product=True")
            has_link_source = feature_source(
                True,
                "has_link_v1",
                ["anchors", "has_shop_product", "caption"],
                has_link_evidence,
                reason="product anchor, shop-product flag, or explicit link cue",
                detail={"scope": "platform_anchor_or_caption_cue_only; profile bio links are not checked"},
            )
        elif detail is not None:
            has_link = False
            has_link_source = feature_source(
                False,
                "has_link_v1",
                ["anchors", "has_shop_product", "caption"],
                [],
                reason="detail_payload_present_and_no_anchor_or_link_cue",
                detail={"scope": "platform_anchor_or_caption_cue_only; profile bio links are not checked"},
            )
        else:
            has_link = "unknown"
            has_link_source = feature_source(
                "unknown",
                "has_link_v1",
                ["anchors", "caption"],
                [],
                reason="no_detail_payload_and_no_anchor_or_link_cue",
                detail={"scope": "platform_anchor_or_caption_cue_only; profile bio links are not checked"},
            )

        # ---------------- ad disclosure ----------------
        ad_hits = match_patterns(caption, AD_DISCLOSURE_CAPTION_PATTERNS)
        ad_tag_hits = match_hashtags(hashtag_norm, AD_DISCLOSURE_HASHTAGS)
        ad_evidence = ad_hits + [f"#{t}" for t in ad_tag_hits] + [f"anchor_label:{l}" for l in ad_labels]
        if ad_evidence:
            ad_disclosure = True
            ad_disclosure_source = feature_source(
                True,
                "ad_disclosure_v1",
                ["caption", "hashtags_normalized", "anchors[].extra[].extra.ad_label_name"],
                ad_evidence,
                reason="explicit ad/sponsorship disclosure",
                detail={"scope": "text_or_platform_label_only; spoken disclosure is not observable"},
            )
        elif detail is not None:
            ad_disclosure = False
            ad_disclosure_source = feature_source(
                False,
                "ad_disclosure_v1",
                ["caption", "hashtags_normalized", "anchors[].extra[].extra.ad_label_name"],
                [],
                reason="detail_payload_present_and_no_text_disclosure_cue",
                detail={
                    "scope": "text_or_platform_label_only; spoken disclosure is not observable",
                    "platform_is_ad": (detail or {}).get("is_ad"),
                },
            )
        else:
            ad_disclosure = "unknown"
            ad_disclosure_source = feature_source(
                "unknown",
                "ad_disclosure_v1",
                ["caption", "hashtags_normalized", "anchors[].extra[].extra.ad_label_name"],
                [],
                reason="no_detail_payload_and_no_disclosure_cue",
                detail={
                    "scope": "text_or_platform_label_only; spoken disclosure is not observable",
                    "note": (
                        "search is_ads is false for all 220 search records while detail is_ad "
                        "is true for 46/59, so search is_ads is not usable as a negative"
                    ),
                },
            )

        # ---------------- expression ----------------
        first_sentence = caption_clean
        punct = re.search(r"[.!?]", caption_clean)
        if punct:
            first_sentence = caption_clean[: punct.end()]
        first_word_match = re.search(r"[A-Za-zÀ-ÿ']+", first_sentence)
        first_word = normalize(first_word_match.group(0)) if first_word_match else ""
        if not caption_clean:
            opens_with_question = "unknown"
            opens_source = feature_source(
                "unknown", "opens_with_question_v1", ["caption_clean"], [], reason="caption_empty"
            )
        elif first_sentence.rstrip().endswith("?") or first_word in INTERROGATIVE_FIRST_WORDS:
            opens_with_question = True
            opens_source = feature_source(
                True,
                "opens_with_question_v1",
                ["caption_clean"],
                [f"first_sentence:{first_sentence}", f"first_word:{first_word}"],
                reason="caption opens with a question",
                detail={
                    "scope": "caption_text_not_spoken_audio",
                    "first_sentence": first_sentence,
                    "first_word": first_word,
                    "question_mark_terminated": first_sentence.rstrip().endswith("?"),
                },
            )
        else:
            opens_with_question = False
            opens_source = feature_source(
                False,
                "opens_with_question_v1",
                ["caption_clean"],
                [f"first_sentence:{first_sentence}", f"first_word:{first_word}"],
                reason="caption opens declaratively",
                detail={
                    "scope": "caption_text_not_spoken_audio",
                    "first_sentence": first_sentence,
                    "first_word": first_word,
                    "question_mark_terminated": first_sentence.rstrip().endswith("?"),
                },
            )

        prose_number_hits = [m.group(0) for m in NUMBER_TOKEN_RE.finditer(caption_clean)]
        hashtag_number_hits = [
            tag for tag in sorted(hashtag_norm) if HASHTAG_NUMBER_RE.match(tag)
        ]
        number_hits = prose_number_hits + [f"#{tag}" for tag in hashtag_number_hits]
        if number_hits:
            has_number_claim = True
            number_source = feature_source(
                True,
                "has_number_claim_v1",
                ["caption_clean", "hashtags_normalized"],
                number_hits,
                reason="standalone numeric token in caption or numeric unit prefix in a hashtag",
            )
        elif caption_clean:
            has_number_claim = False
            number_source = feature_source(
                False,
                "has_number_claim_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="no_standalone_numeric_token_in_caption_or_numeric_hashtag_prefix",
            )
        else:
            has_number_claim = "unknown"
            number_source = feature_source(
                "unknown", "has_number_claim_v1", ["caption_clean"], [], reason="caption_empty"
            )

        # ---------------- platform flags ----------------
        if detail is None:
            platform_is_ad = "unknown"
            platform_is_ad_source = feature_source(
                "unknown", "platform_is_ad_v1", ["is_ad"], [], reason="detail_payload_absent"
            )
            platform_is_ec_video = "unknown"
            platform_ec_source = feature_source(
                "unknown", "platform_is_ec_video_v1", ["is_ec_video"], [], reason="detail_payload_absent"
            )
        else:
            platform_is_ad = bool(detail.get("is_ad"))
            platform_is_ad_source = feature_source(
                platform_is_ad,
                "platform_is_ad_v1",
                ["fetch_post_detail.data.itemInfo.is_ad"],
                [f"is_ad={detail.get('is_ad')}"],
                reason="platform boolean",
            )
            ec_value = detail.get("is_ec_video")
            if ec_value is None:
                platform_is_ec_video = "unknown"
                platform_ec_source = feature_source(
                    "unknown",
                    "platform_is_ec_video_v1",
                    ["fetch_post_detail.data.itemInfo.is_ec_video"],
                    [],
                    reason="field_absent_in_detail_payload",
                )
            else:
                platform_is_ec_video = bool(ec_value == 1 or ec_value is True)
                platform_ec_source = feature_source(
                    platform_is_ec_video,
                    "platform_is_ec_video_v1",
                    ["fetch_post_detail.data.itemInfo.is_ec_video"],
                    [f"is_ec_video={ec_value}"],
                    reason="platform boolean",
                )

        # ---------------- supplementary commercial-context signals ----------------
        coupon_hits = match_patterns(caption_clean, COUPON_CAPTION_PATTERNS)
        coupon_tag_hits = match_hashtags(hashtag_norm, COUPON_HASHTAGS)
        coupon_matched = coupon_hits + [f"#{t}" for t in coupon_tag_hits]
        if coupon_matched:
            has_coupon_or_discount = True
            coupon_source = feature_source(
                True,
                "has_coupon_or_discount_v1",
                ["caption_clean", "hashtags_normalized"],
                coupon_matched,
                reason="discount or coupon cue",
            )
        elif caption_clean:
            has_coupon_or_discount = False
            coupon_source = feature_source(
                False,
                "has_coupon_or_discount_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="no_discount_or_coupon_cue_in_caption",
            )
        else:
            has_coupon_or_discount = "unknown"
            coupon_source = feature_source(
                "unknown",
                "has_coupon_or_discount_v1",
                ["caption_clean", "hashtags_normalized"],
                [],
                reason="caption_empty",
            )

        cta_hits = match_patterns(caption_clean, CTA_CAPTION_PATTERNS)
        cta_matched = cta_hits
        if cta_matched:
            has_cta = True
            cta_source = feature_source(
                True,
                "has_cta_v1",
                ["caption_clean"],
                cta_matched,
                reason="direct caption call-to-action cue",
            )
        elif caption_clean:
            has_cta = False
            cta_source = feature_source(
                False,
                "has_cta_v1",
                ["caption_clean"],
                [],
                reason="no_direct_call_to_action_cue_in_caption",
            )
        else:
            has_cta = "unknown"
            cta_source = feature_source(
                "unknown",
                "has_cta_v1",
                ["caption_clean"],
                [],
                reason="caption_empty",
            )

        brand_mention_hit = BRAND_MENTION_RE.search(caption)
        if brand_mention_hit:
            mentions_brand = True
            brand_mention_source = feature_source(
                True,
                "mentions_brand_v1",
                ["caption"],
                [brand_mention_hit.group(0)],
                reason="caption @mentions the Momcozy brand account",
            )
        elif caption:
            mentions_brand = False
            brand_mention_source = feature_source(
                False,
                "mentions_brand_v1",
                ["caption"],
                [],
                reason="no_brand_mention_in_caption",
            )
        else:
            mentions_brand = "unknown"
            brand_mention_source = feature_source(
                "unknown", "mentions_brand_v1", ["caption"], [], reason="caption_empty"
            )

        caption_words = caption_clean.split()

        row = {
            "schema_version": SCHEMA_VERSION,
            "video_id": vid,
            "product_relation": {
                "confidence": relation.get("confidence"),
                "relation_type": relation.get("relation_type"),
                "status": relation.get("status"),
                "target_baseline_eligible": bool(relation.get("target_baseline_eligible")),
                "target_product_id": relation.get("target_product_id"),
            },
            "provenance": {
                "relation_file": candidates_path,
                "detail_file": os.path.join(raw_dir, "video-details.json") if detail else None,
                "search_raw_files": sorted(search.get("raw_files", [])),
                "search_request_ids": sorted(r for r in search.get("request_ids", []) if r),
                "detail_endpoint": (detail or {}).get("source_endpoint"),
                "search_endpoint": (
                    "fetch_video_search_result"
                    if search.get("raw_files")
                    else None
                ),
            },
            "fields_available": fields_available,
            "caption": caption,
            "caption_clean": caption_clean,
            "hashtags": hashtags,
            "hashtags_normalized": sorted(hashtag_norm),
            "duration_seconds": duration_seconds,
            "duration_bucket": duration_bucket,
            "duration_bucket_source": feature_source(
                duration_bucket,
                "duration_bucket_v1",
                ["duration_seconds"],
                [f"duration_seconds={duration_seconds}"] if duration_seconds is not None else [],
                reason=None if duration_seconds is not None else "duration_absent",
            ),
            "product_anchor_ids": all_anchor_ids,
            "has_product_anchor": bool(all_anchor_ids),
            "ad_label_names": ad_labels,
            "comparison": comparison,
            "comparison_source": comparison_source,
            "demo": demo,
            "demo_source": demo_source,
            "before_after": before_after,
            "before_after_source": before_after_source,
            "unboxing": unboxing,
            "unboxing_source": unboxing_source,
            "problem_solution": problem_solution,
            "problem_solution_source": problem_solution_source,
            "visual_only": visual_only,
            "visual_only_source": visual_only_source,
            "has_link": has_link,
            "has_link_source": has_link_source,
            "ad_disclosure": ad_disclosure,
            "ad_disclosure_source": ad_disclosure_source,
            "opens_with_question": opens_with_question,
            "opens_with_question_source": opens_source,
            "has_number_claim": has_number_claim,
            "has_number_claim_source": number_source,
            "platform_is_ad": platform_is_ad,
            "platform_is_ad_source": platform_is_ad_source,
            "platform_is_ec_video": platform_is_ec_video,
            "platform_is_ec_video_source": platform_ec_source,
            "supplementary": {
                "has_coupon_or_discount": has_coupon_or_discount,
                "has_coupon_or_discount_source": coupon_source,
                "has_cta": has_cta,
                "has_cta_source": cta_source,
                "mentions_brand": mentions_brand,
                "mentions_brand_source": brand_mention_source,
                "caption_word_count": len(caption_words),
                "caption_word_count_source": {
                    "value": len(caption_words),
                    "rule_id": "caption_word_count_v1",
                    "fields": ["caption_clean"],
                    "matched": [],
                    "reason": None,
                },
                "hashtag_count": len(hashtags),
                "hashtag_count_source": {
                    "value": len(hashtags),
                    "rule_id": "hashtag_count_v1",
                    "fields": [
                        "union(fetch_post_detail.hashtags[].name, "
                        "fetch_video_search_result.text_extra[].hashtag_name)"
                    ],
                    "matched": [],
                    "reason": None,
                },
            },
        }
        records.append(row)

    return records, conflicts, {
        "candidates_total": len(candidates),
        "population_total": len(population),
        "with_detail": sum(1 for r in population if str(r["video_id"]) in details),
        "search_records": len(search_index),
    }


# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------


def distribution(records: list[dict]) -> dict:
    total = len(records)
    per_feature: dict[str, dict] = {}
    for feature in FEATURE_ORDER:
        values = [row[feature] for row in records]
        true_n = sum(1 for v in values if v is True)
        false_n = sum(1 for v in values if v is False)
        unknown_n = sum(1 for v in values if v == "unknown")
        known_n = true_n + false_n
        reasons = Counter(
            row[f"{feature}_source"].get("reason")
            for row in records
            if row[feature] == "unknown"
        )
        by_confidence = {}
        for conf in ("high", "medium"):
            subset = [row[feature] for row in records if row["product_relation"]["confidence"] == conf]
            by_confidence[conf] = {
                "n": len(subset),
                "true": sum(1 for v in subset if v is True),
                "false": sum(1 for v in subset if v is False),
                "unknown": sum(1 for v in subset if v == "unknown"),
            }
        by_relation_type = {}
        for relation_type in sorted({row["product_relation"]["relation_type"] for row in records}):
            subset = [
                row[feature]
                for row in records
                if row["product_relation"]["relation_type"] == relation_type
            ]
            by_relation_type[relation_type] = {
                "n": len(subset),
                "true": sum(1 for v in subset if v is True),
                "false": sum(1 for v in subset if v is False),
                "unknown": sum(1 for v in subset if v == "unknown"),
            }
        eligible_true = sum(
            1
            for row in records
            if row["product_relation"]["target_baseline_eligible"] and row[feature] is True
        )
        eligible_n = sum(
            1 for row in records if row["product_relation"]["target_baseline_eligible"]
        )
        per_feature[feature] = {
            "true": true_n,
            "false": false_n,
            "unknown": unknown_n,
            "total": total,
            "true_pct_of_all": round(true_n / total * 100, 3) if total else None,
            "false_pct_of_all": round(false_n / total * 100, 3) if total else None,
            "unknown_pct_of_all": round(unknown_n / total * 100, 3) if total else None,
            "true_pct_of_known": round(true_n / known_n * 100, 3) if known_n else None,
            "unknown_reasons": dict(sorted(reasons.items())),
            "matched_cue_counts": dict(
                sorted(
                    Counter(
                        cue
                        for row in records
                        for cue in row[f"{feature}_source"].get("matched", [])
                        if not cue.startswith(("first_sentence:", "first_word:"))
                    ).items()
                )
            ),
            "by_confidence": by_confidence,
            "by_relation_type": by_relation_type,
            "target_baseline_eligible": {
                "n": eligible_n,
                "true": eligible_true,
                "true_pct": round(eligible_true / eligible_n * 100, 3) if eligible_n else None,
            },
        }

    top_unknown = sorted(
        (
            (feature, stats["unknown_pct_of_all"], stats["unknown"])
            for feature, stats in per_feature.items()
        ),
        key=lambda item: (-item[1], FEATURE_ORDER.index(item[0])),
    )[:3]

    supplementary_features: dict[str, dict] = {}
    for feature in ("has_coupon_or_discount", "has_cta", "mentions_brand"):
        values = [row["supplementary"][feature] for row in records]
        true_n = sum(1 for v in values if v is True)
        false_n = sum(1 for v in values if v is False)
        unknown_n = sum(1 for v in values if v == "unknown")
        supplementary_features[feature] = {
            "true": true_n,
            "false": false_n,
            "unknown": unknown_n,
            "total": total,
            "true_pct_of_all": round(true_n / total * 100, 3) if total else None,
            "unknown_pct_of_all": round(unknown_n / total * 100, 3) if total else None,
            "matched_cue_counts": dict(
                sorted(
                    Counter(
                        cue
                        for row in records
                        for cue in row["supplementary"][f"{feature}_source"].get("matched", [])
                    ).items()
                )
            ),
        }
    word_counts = sorted(row["supplementary"]["caption_word_count"] for row in records)
    hashtag_counts_per_video = sorted(row["supplementary"]["hashtag_count"] for row in records)

    def median_of(values: list[int]) -> float:
        n = len(values)
        if not n:
            return 0.0
        mid = n // 2
        return float(values[mid]) if n % 2 else (values[mid - 1] + values[mid]) / 2.0

    supplementary_summary = {
        "features": supplementary_features,
        "caption_word_count": {
            "min": word_counts[0] if word_counts else None,
            "median": median_of(word_counts),
            "max": word_counts[-1] if word_counts else None,
        },
        "hashtag_count_per_video": {
            "min": hashtag_counts_per_video[0] if hashtag_counts_per_video else None,
            "median": median_of(hashtag_counts_per_video),
            "max": hashtag_counts_per_video[-1] if hashtag_counts_per_video else None,
        },
    }

    duration_dist = Counter(row["duration_bucket"] for row in records)
    hashtag_counts = Counter()
    for row in records:
        for tag in row["hashtags_normalized"]:
            hashtag_counts[tag] += 1

    return {
        "schema_version": "voc_video_features_distribution_v1",
        "generated_at": utc_now(),
        "population": {
            "total": total,
            "high": sum(1 for r in records if r["product_relation"]["confidence"] == "high"),
            "medium": sum(1 for r in records if r["product_relation"]["confidence"] == "medium"),
        },
        "field_availability": {
            "caption": sum(1 for r in records if r["fields_available"]["caption"]),
            "hashtags": sum(1 for r in records if r["fields_available"]["hashtags"]),
            "duration": sum(1 for r in records if r["fields_available"]["duration"]),
            "detail_payload": sum(1 for r in records if r["fields_available"]["detail_payload"]),
            "product_anchor": sum(1 for r in records if r["fields_available"]["product_anchor"]),
            "transcript_or_audio": 0,
        },
        "features": per_feature,
        "supplementary": supplementary_summary,
        "top_unknown_features": [
            {"feature": feature, "unknown": unknown, "unknown_pct_of_all": pct}
            for feature, pct, unknown in top_unknown
        ],
        "duration_buckets": {
            bucket: {
                "n": duration_dist.get(bucket, 0),
                "pct_of_all": round(duration_dist.get(bucket, 0) / total * 100, 3) if total else None,
            }
            for bucket in ("<=15s", "16-30s", "31-60s", ">60s", "unknown")
        },
        "top_hashtags": [
            {"hashtag": tag, "n": n} for tag, n in hashtag_counts.most_common(25)
        ],
        "notes": [
            "Population is high/medium product-relation videos only; low and no_signal rows are excluded.",
            "Caption silence is treated as unknown, not false, for visual/audio content forms.",
            "visual_only is unknown for every video because no transcript or audio field exists.",
            "has_number_claim counts standalone digits and ordinals in the caption, plus hashtags whose numeric prefix is followed by a unit (for example #36weekspregnant). Coupon codes such as MERCYCOZY20 and prose tokens such as 3D are excluded by the alphanumeric-boundary rule.",
            "duration buckets use exact seconds: <=15, (15,30], (30,60], >60. Labels are shorthand.",
            "Cue matching is surface-form. Negated cues (for example 'not comfortable') are not semantically inverted; those rows stay unknown unless another positive cue exists.",
            "ad_disclosure covers text and platform labels only. A spoken disclosure is not observable. platform_is_ad is reported separately; 10 of the 13 ad_disclosure=false rows carry platform is_ad=true.",
            "has_link covers platform product anchors, the has_shop_product flag, and caption link cues. Profile bio links are not checked.",
            "These strict rules are not comparable to the loose substring format_tags in creator_video_derive.py. For example, that earlier rule tags any caption containing 'weeks' or 'bump' as before_after, which is why its format_before_after cohort is much larger than the strict before_after feature here.",
        ],
    }


def rules_payload() -> dict:
    return {
        "schema_version": "voc_video_features_rules_v1",
        "generated_at": utc_now(),
        "value_model": {
            "true": "an explicit cue is present in a named field",
            "false": "the named fields can exclude the feature",
            "unknown": "the available fields cannot answer; no guessing",
        },
        "preprocessing": {
            "caption_clean": "lowercase + strip accents; remove URLs, hashtags (#...), mentions (@...); collapse whitespace",
            "hashtags_normalized": "lowercase + strip accents + strip leading #",
            "hashtag_merge": "union of detail hashtags[].name and search text_extra[].hashtag_name",
            "first_sentence": "caption_clean up to and including the first . ! or ?; whole caption if no punctuation",
        },
        "rules": {
            "comparison": {
                "pattern_version": "comparison_v1",
                "positive": "caption_clean or hashtags hit any comparison cue",
                "caption_patterns": [p for _, p in COMPARISON_CAPTION_PATTERNS],
                "hashtags": sorted(COMPARISON_HASHTAGS),
                "otherwise": "unknown (caption silence cannot exclude visual comparison)",
            },
            "demo": {
                "pattern_version": "demo_v1",
                "positive": "caption_clean or hashtags hit any how-to/demo cue",
                "caption_patterns": [p for _, p in DEMO_CAPTION_PATTERNS],
                "hashtags": sorted(DEMO_HASHTAGS),
                "otherwise": "unknown",
            },
            "before_after": {
                "pattern_version": "before_after_v1",
                "positive": "caption_clean or hashtags hit any before/after or progress cue",
                "caption_patterns": [p for _, p in BEFORE_AFTER_CAPTION_PATTERNS],
                "hashtags": sorted(BEFORE_AFTER_HASHTAGS),
                "otherwise": "unknown",
            },
            "unboxing": {
                "pattern_version": "unboxing_v1",
                "positive": "caption_clean or hashtags hit any unboxing/haul cue",
                "caption_patterns": [p for _, p in UNBOXING_CAPTION_PATTERNS],
                "hashtags": sorted(UNBOXING_HASHTAGS),
                "otherwise": "unknown",
            },
            "problem_solution": {
                "pattern_version": "problem_solution_v1",
                "positive": "at least one problem cue AND at least one solution cue in caption_clean + hashtags",
                "problem_patterns": [p for _, p in PROBLEM_PATTERNS],
                "solution_patterns": [p for _, p in SOLUTION_PATTERNS],
                "otherwise": "unknown, with reason partial_cue_problem_only / partial_cue_solution_only / no cue",
            },
            "visual_only": {
                "pattern_version": "visual_only_v1",
                "positive": "never detectable from current fields",
                "otherwise": "unknown for every video; no audio or transcript field",
            },
            "duration_bucket": {
                "pattern_version": "duration_bucket_v1",
                "field": "fetch_post_detail.duration_seconds, else search aweme_info.video.duration/1000",
                "buckets": ["<=15s", "16-30s", "31-60s", ">60s"],
                "boundaries": "exact seconds: <=15, (15,30], (30,60], >60",
            },
            "has_link": {
                "pattern_version": "has_link_v1",
                "positive": "any product anchor id in detail or search, or caption URL/link-in-bio/storefront cue",
                "negative": "detail payload present with has_shop_product false and no anchor and no cue",
                "otherwise": "unknown when no detail payload and no anchor/cue",
                "caption_patterns": [p for _, p in LINK_CAPTION_PATTERNS],
                "scope": "platform anchor, shop-product flag, or caption cue only; profile bio links are not checked",
            },
            "ad_disclosure": {
                "pattern_version": "ad_disclosure_v1",
                "positive": "caption disclosure cue OR disclosure hashtag OR anchor ad_label_name",
                "negative": "detail payload present and no cue",
                "otherwise": "unknown when no detail payload and no cue",
                "caption_patterns": [p for _, p in AD_DISCLOSURE_CAPTION_PATTERNS],
                "hashtags": sorted(AD_DISCLOSURE_HASHTAGS),
                "anchor_path": "anchors[].extra -> list[].extra -> product.extra.ad_label_name",
                "scope": "text or platform label only; a spoken disclosure is not observable, so platform_is_ad is reported separately",
            },
            "opens_with_question": {
                "pattern_version": "opens_with_question_v1",
                "positive": "first caption sentence ends with ? or first word is an interrogative",
                "otherwise": "false for a non-empty caption; unknown if caption empty",
                "scope": "caption text only, not spoken audio",
                "interrogatives": sorted(INTERROGATIVE_FIRST_WORDS),
            },
            "has_number_claim": {
                "pattern_version": "has_number_claim_v1",
                "positive": "standalone digit token or ordinal in caption_clean, or a hashtag whose numeric prefix is followed by a unit (weeks/wks/months/days/st/nd/rd/th)",
                "regex": NUMBER_TOKEN_RE.pattern,
                "hashtag_regex": HASHTAG_NUMBER_RE.pattern,
                "exclusions": "digits attached to letters in prose (coupon codes, 3D) and digits inside hashtags without a recognised unit suffix",
                "otherwise": "false for a non-empty caption; unknown if caption empty",
            },
            "platform_is_ad": {
                "pattern_version": "platform_is_ad_v1",
                "field": "fetch_post_detail.data.itemInfo.is_ad",
                "otherwise": "unknown when detail payload absent",
            },
            "platform_is_ec_video": {
                "pattern_version": "platform_is_ec_video_v1",
                "field": "fetch_post_detail.data.itemInfo.is_ec_video",
                "otherwise": "unknown when detail payload absent",
            },
        },
        "supplementary_rules": {
            "has_coupon_or_discount": {
                "pattern_version": "has_coupon_or_discount_v1",
                "positive": "caption discount/coupon cue or discount hashtag",
                "caption_patterns": [p for _, p in COUPON_CAPTION_PATTERNS],
                "hashtags": sorted(COUPON_HASHTAGS),
                "otherwise": "false for a non-empty caption; unknown if caption empty",
            },
            "has_cta": {
                "pattern_version": "has_cta_v1",
                "positive": "direct caption call-to-action cue (imperative or audience-directed). Shoppable hashtags alone do not count.",
                "caption_patterns": [p for _, p in CTA_CAPTION_PATTERNS],
                "otherwise": "false for a non-empty caption; unknown if caption empty",
            },
            "mentions_brand": {
                "pattern_version": "mentions_brand_v1",
                "positive": "caption contains an @handle starting with momcozy (for example @momcozy, @Momcozy US, @momcozyofficial)",
                "regex": BRAND_MENTION_RE.pattern,
                "otherwise": "false for a non-empty caption; unknown if caption empty",
            },
            "caption_word_count": {
                "pattern_version": "caption_word_count_v1",
                "definition": "whitespace token count of caption_clean",
            },
            "hashtag_count": {
                "pattern_version": "hashtag_count_v1",
                "definition": "length of the merged hashtag list",
            },
        },
    }


def validate(records: list[dict], population_ids: set[str]) -> dict:
    errors: list[str] = []
    ids = [r["video_id"] for r in records]
    if len(ids) != len(set(ids)):
        errors.append("duplicate video_id")
    if set(ids) != population_ids:
        missing = sorted(population_ids - set(ids))
        extra = sorted(set(ids) - population_ids)
        errors.append(f"population mismatch missing={missing} extra={extra}")
    for row in records:
        for feature in FEATURE_ORDER:
            value = row.get(feature)
            if value not in (True, False, "unknown"):
                errors.append(f"{row['video_id']}:{feature} invalid value {value!r}")
            src = row.get(f"{feature}_source")
            if not isinstance(src, dict):
                errors.append(f"{row['video_id']}:{feature}_source missing")
                continue
            if src.get("value") != value:
                errors.append(f"{row['video_id']}:{feature}_source value mismatch")
            if not src.get("rule_id"):
                errors.append(f"{row['video_id']}:{feature}_source missing rule_id")
            if not src.get("fields"):
                errors.append(f"{row['video_id']}:{feature}_source missing fields")
            if value == "unknown" and not src.get("reason"):
                errors.append(f"{row['video_id']}:{feature} unknown without reason")
        if row["duration_bucket"] == "unknown" and row["duration_seconds"] is not None:
            errors.append(f"{row['video_id']}: duration bucket unknown but duration present")
        supp = row.get("supplementary") or {}
        for feature in ("has_coupon_or_discount", "has_cta", "mentions_brand"):
            value = supp.get(feature)
            if value not in (True, False, "unknown"):
                errors.append(f"{row['video_id']}:supplementary.{feature} invalid value {value!r}")
            src = supp.get(f"{feature}_source")
            if not isinstance(src, dict) or not src.get("rule_id"):
                errors.append(f"{row['video_id']}:supplementary.{feature}_source missing")
            elif src.get("value") != value:
                errors.append(f"{row['video_id']}:supplementary.{feature}_source value mismatch")
    return {"ok": not errors, "errors": errors, "rows": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_run = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "voc_pipeline",
        "artifacts",
        "run-20261029",
        "creator-video",
    )
    parser.add_argument("--run-dir", default=default_run)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    run_dir = os.path.abspath(args.run_dir)
    output_dir = os.path.abspath(args.output_dir or os.path.join(run_dir, "features"))

    candidates = load_jsonl(os.path.join(run_dir, "relations", "video-product-candidates.jsonl"))
    population_ids = {
        str(r["video_id"]) for r in candidates if r.get("confidence") in ("high", "medium")
    }

    records, conflicts, population_stats = build_records(run_dir)
    dist = distribution(records)
    validation = validate(records, population_ids)

    features_path = os.path.join(output_dir, "video-features.jsonl")
    rules_path = os.path.join(output_dir, "feature-rules.json")
    dist_path = os.path.join(output_dir, "feature-distribution.json")

    write_jsonl(features_path, records)
    write_json(rules_path, rules_payload())

    dist["population"].update(population_stats)
    dist["search_dedup_conflicts"] = conflicts
    dist["validation"] = validation
    dist["outputs"] = {
        "features": features_path,
        "rules": rules_path,
        "distribution": dist_path,
    }
    write_json(dist_path, dist)

    summary = {
        "status": "ok" if validation["ok"] else "validation_failed",
        "output_dir": output_dir,
        "rows": len(records),
        "validation": validation,
        "top_unknown_features": dist["top_unknown_features"],
        "duration_buckets": dist["duration_buckets"],
        "conflicts": len(conflicts),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

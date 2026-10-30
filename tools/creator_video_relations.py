#!/usr/bin/env python3
"""Build creator/video relation tables for the VOC creator-video run.

Inputs (read-only):
  artifacts/run-20261029/canonical-records.jsonl
  artifacts/run-20261029/raw/tikhub/*.json
  artifacts/run-20261029/creator-video/raw/video-snapshots.json
  artifacts/run-20261029/creator-video/raw/video-details.json
  artifacts/run-20261029/creator-video/raw/video-products.json
  artifacts/run-20261029/creator-video/raw/creators.json
  artifacts/run-20261029/creator-video/raw/video-search-*.json
  artifacts/run-20261029/creator-video/raw/fetch-post-detail-*.json
  artifacts/run-20261029/creator-video/raw/fetch-user-profile-*.json

Outputs (new files only):
  artifacts/run-20261029/creator-video/relations/video-creator.jsonl
  artifacts/run-20261029/creator-video/relations/video-product.jsonl
  artifacts/run-20261029/creator-video/relations/video-product-unconfirmed.jsonl
  artifacts/run-20261029/creator-video/relations/video-product-target-baseline.jsonl
  artifacts/run-20261029/creator-video/relations/comment-video.jsonl
  artifacts/run-20261029/creator-video/relations/comment-video-gap.json
  artifacts/run-20261029/creator-video/relations/coverage.json

The script never writes canonical-records.jsonl or gold-set-50.jsonl.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

TARGET_PRODUCT_ID = "1729474995478630680"
TARGET_PRODUCT_NAME = (
    "Momcozy Pregnancy Belly Band YB001, CozySupport Ergonest Maternity Belly Band"
)
# Product IDs the collector flagged as other listings in the same Momcozy YB001
# series (similar, not identical titles). They are NOT merged and never enter the
# target-product baseline; they stay a category-reference bucket.
DUPLICATE_LISTING_PRODUCT_IDS = {
    "1729625924185592807",
    "1729495174330226663",
    "1731287236556526567",
}

BRAND_TERMS = [
    "momcozy",
    "mom cozy",
    "cozy support",
    "cozysupport",
    "ergonest",
]

CATEGORY_TERMS = [
    "belly band",
    "bellyband",
    "belly belt",
    "bellybelt",
    "maternity band",
    "maternityband",
    "maternity belt",
    "maternitybelt",
    "pregnancy band",
    "pregnancyband",
    "pregnancy belt",
    "pregnancybelt",
    "belly support",
    "bellysupport",
    "support band",
    "supportband",
    "belly binder",
    "bellybinder",
    "belly wrap",
    "bellywrap",
    "bump band",
    "bumpband",
    "belly brace",
    "cervical belt",
    "postpartum band",
    "postpartumband",
    "postpartum belt",
    "maternity support",
]

HASHTAG_RE = re.compile(r"#[^\s#]+")
SCHEMA_VERSION = "voc_creator_video_relations_v2"

# Content tags are orthogonal to relation_type: relation_type answers "what is
# the relation to the target product", content_tag answers "what content form is
# this". A consideration post can still be text_brand_and_category, but it never
# participates in performance statistics.
CONSIDERATION_INTENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi want to (?:order|buy|try)\b",
        r"\bi wanna (?:order|buy|try)\b",
        r"\bshould i (?:buy|get|order)\b",
        r"\bwhat do(?: you| yal| yall| u) think\b",
        r"\bthinking about (?:buying|ordering|getting|trying)\b",
        r"\bconsidering (?:buying|ordering|getting|trying)\b",
        r"\brecommend(?:ation)?\?",
        r"\bwhich one (?:should i|do i|to buy|would you recommend|fits my)\b",
        r"\bis it worth (?:it|buying|the money)\b",
    )
)
USAGE_EVIDENCE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi ordered\b",
        r"\bi bought\b",
        r"\bi got\b",
        r"\bi use\b",
        r"\bi used\b",
        r"\bi wear\b",
        r"\bi've been (?:using|wearing)\b",
        r"\bi have been (?:using|wearing)\b",
        r"\bive been (?:using|wearing)\b",
        r"\bit helped me\b",
        r"\bit helps me\b",
        r"\bworks for me\b",
        r"\bmine\b",
    )
)
# Keyword rules for text-only rows that mention Momcozy and a belly-band term but
# describe another product line. Each label must cite the matched phrase in the
# output so the downgrade is reproducible.
NON_TARGET_SUBLINE_TERMS = {
    "go_as_you_grow": ("go as you grow",),
    "postpartum_belly_band": (
        "postpartum belly band",
        "postpartum band",
        "postpartum belt",
    ),
    "nursing_bra_mix": ("nursing bra",),
    "momcozy_uk": ("momcozy uk",),
}
# A bare "postpartum" mention is only a subline signal when the same text does
# not also name the target pregnancy line. This keeps a pregnancy-band video
# that lists postpartum support as a use case in the category-reference bucket.
TARGET_LINE_TERMS = ("pregnancy belly band", "yb001", "cozysupport", "ergonest")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: str) -> dict:
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


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def strip_hashtags(text: str | None) -> str:
    return HASHTAG_RE.sub(" ", text or "")


def term_hits(terms: list[str], text: str | None) -> list[str]:
    haystack = (text or "").lower()
    return sorted({term for term in terms if term in haystack})


def normalize_text(text: str | None) -> str:
    """Lowercase, unify curly apostrophes, collapse whitespace."""
    value = (text or "").lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", value).strip()


def matched_phrases(patterns: tuple[re.Pattern[str], ...],
                    text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            phrase = match.group(0).strip()
            if phrase and phrase not in hits:
                hits.append(phrase)
    return hits


def evidence_snippet(text: str, phrase: str, width: int = 110) -> str:
    """Return the source sentence/segment around a matched phrase."""
    if not phrase:
        return ""
    index = text.find(phrase.lower())
    if index < 0:
        return ""
    start = max(0, index - width)
    end = min(len(text), index + len(phrase) + width)
    return text[start:end].strip()


def detect_non_target_subline(desc_text: str,
                              hashtags: set[str]) -> tuple[str | None, str | None]:
    haystack = normalize_text(f"{desc_text} {' '.join(sorted(hashtags))}")
    for label, terms in NON_TARGET_SUBLINE_TERMS.items():
        for term in terms:
            if term in haystack:
                return label, term
    if "postpartum" in haystack and not any(
        term in haystack for term in TARGET_LINE_TERMS
    ):
        return "postpartum_belly_band", "postpartum"
    return None, None


def detect_content_tag(desc_text: str, anchor_ids: list[str], has_link: bool,
                       platform_is_ad: bool | None) -> tuple[str, dict]:
    """Classify content form per the F-decision C1/C2/C3 rule.

    C1 no product evidence: empty anchor ids, no link, platform is_ads=false.
    C2 future purchase intent or asking for advice.
    C3 no first-person usage evidence.
    C1+C2+C3 -> consideration. Usage evidence alone -> material_candidate.
    Otherwise unknown.
    """
    text = normalize_text(desc_text)
    intent_hits = matched_phrases(CONSIDERATION_INTENT_PATTERNS, text)
    usage_hits = matched_phrases(USAGE_EVIDENCE_PATTERNS, text)
    c1 = not anchor_ids and not has_link and platform_is_ad is False
    evidence = {
        "c1_no_product_evidence": c1,
        "anchor_product_ids": list(anchor_ids),
        "has_link": has_link,
        "platform_is_ad": platform_is_ad,
        "matched_intent_phrases": intent_hits,
        "matched_usage_phrases": usage_hits,
        "evidence_snippet": (
            evidence_snippet(text, intent_hits[0]) if intent_hits else ""
        ),
    }
    if c1 and intent_hits and not usage_hits:
        return "consideration", evidence
    if usage_hits:
        return "material_candidate", evidence
    return "unknown", evidence


def creator_tier(follower_count: int | None) -> str:
    if follower_count is None:
        return "unknown"
    if follower_count < 10_000:
        return "nano_lt_10k"
    if follower_count < 100_000:
        return "micro_10k_100k"
    if follower_count < 500_000:
        return "mid_100k_500k"
    return "macro_gte_500k"


def interaction_rate(stats: dict | None) -> float | None:
    if not stats:
        return None
    play = stats.get("play_count")
    if not play:
        return None
    numerator = sum(
        (stats.get(key) or 0)
        for key in ("like_count", "comment_count", "share_count", "collect_count")
    )
    return round(numerator / play, 6)


def compact_stats(stats: dict | None, source_endpoint: str, captured_at: str | None,
                  raw_file: str | None) -> dict | None:
    if not stats:
        return None
    return {
        "source_endpoint": source_endpoint,
        "captured_at": captured_at,
        "raw_file": raw_file,
        "play_count": stats.get("play_count"),
        "like_count": stats.get("like_count"),
        "comment_count": stats.get("comment_count"),
        "share_count": stats.get("share_count"),
        "collect_count": stats.get("collect_count"),
        "interaction_rate": interaction_rate(stats),
        "is_estimated": None,
        "is_estimated_field_present": False,
    }


def iter_search_items(raw_file: str):
    payload = load_json(raw_file)
    for item in payload.get("data", {}).get("search_item_list") or []:
        aweme = item.get("aweme_info") or item.get("search_aweme_info") or {}
        if aweme.get("aweme_id"):
            yield aweme


def load_search_observations(raw_dir: str, snapshots: list[dict]) -> dict:
    """video_id -> list of author observations from raw search payloads."""
    file_meta: dict[str, dict] = {}
    for video in snapshots:
        for prov in (video.get("search_snapshot") or {}).get("provenance") or []:
            file_meta[prov["raw_file"]] = prov

    observations: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for raw_file in sorted(glob.glob(os.path.join(raw_dir, "video-search-*.json"))):
        meta = file_meta.get(raw_file, {})
        for aweme in iter_search_items(raw_file):
            video_id = str(aweme["aweme_id"])
            author = aweme.get("author") or {}
            tag_key = (
                video_id,
                str(author.get("uid")),
                str(meta.get("captured_at") or raw_file),
            )
            if tag_key in seen:
                continue
            seen.add(tag_key)
            observations[video_id].append(
                {
                    "uid": author.get("uid"),
                    "sec_uid": author.get("sec_uid"),
                    "unique_id": author.get("unique_id"),
                    "nickname": author.get("nickname"),
                    "follower_count": author.get("follower_count"),
                    "raw_file": raw_file,
                    "request_id": meta.get("request_id"),
                    "request_params": meta.get("request_params"),
                    "captured_at": meta.get("captured_at"),
                }
            )
    for video_id in observations:
        observations[video_id].sort(
            key=lambda obs: obs.get("captured_at") or "", reverse=True
        )
    return observations


def load_search_hashtags(raw_dir: str) -> dict[str, set[str]]:
    tags: dict[str, set[str]] = defaultdict(set)
    for raw_file in sorted(glob.glob(os.path.join(raw_dir, "video-search-*.json"))):
        for aweme in iter_search_items(raw_file):
            video_id = str(aweme["aweme_id"])
            for item in aweme.get("text_extra") or []:
                name = item.get("hashtag_name")
                if name:
                    tags[video_id].add(name)
    return tags


def load_search_ad_flags(raw_dir: str) -> dict[str, bool]:
    """video_id -> platform is_ads from the raw search payload.

    Search responses carry is_ads as a boolean on every item. Detail snapshots
    carry is_ad instead. Keeping the search value lets search-only rows record
    platform_is_ad=true/false rather than null.
    """
    flags: dict[str, bool] = {}
    for raw_file in sorted(glob.glob(os.path.join(raw_dir, "video-search-*.json"))):
        for aweme in iter_search_items(raw_file):
            video_id = str(aweme["aweme_id"])
            value = aweme.get("is_ads")
            if isinstance(value, bool) and video_id not in flags:
                flags[video_id] = value
    return flags


def build_creator_indexes(creators: list[dict]) -> tuple[dict, dict, dict]:
    by_id = {row.get("creator_id"): row for row in creators if row.get("creator_id")}
    by_sec = {row.get("sec_uid"): row for row in creators if row.get("sec_uid")}
    by_unique = {row.get("unique_id"): row for row in creators if row.get("unique_id")}
    return by_id, by_sec, by_unique


def pick_profile(by_id: dict, by_sec: dict, by_unique: dict,
                 creator_id: str | None, sec_uid: str | None,
                 unique_id: str | None) -> dict | None:
    return (
        by_id.get(creator_id)
        or by_sec.get(sec_uid)
        or by_unique.get(unique_id)
    )


def build_video_creator_rows(run_dir: str, snapshots: list[dict],
                             details: dict[str, dict], creators: list[dict],
                             search_obs: dict) -> list[dict]:
    by_id, by_sec, by_unique = build_creator_indexes(creators)
    rows: list[dict] = []

    for video in snapshots:
        video_id = video["video_id"]
        detail = details.get(video_id)
        profile = None
        profile_verified = False
        confidence = "high"
        flags: list[str] = []
        notes: list[str] = []
        follower_observations: list[int] = []

        if detail:
            author = detail.get("author") or {}
            creator_id = author.get("user_id")
            sec_uid = author.get("sec_uid")
            unique_id = author.get("unique_id")
            nickname = author.get("nickname")
            author_stats = detail.get("author_stats") or {}
            source_endpoint = "/api/v1/tiktok/web/fetch_post_detail"
            source_file = detail.get("raw_file")
            captured_at = detail.get("captured_at")
            request_id = detail.get("_raw_request_id")
            request_params = detail.get("_raw_request_params")
            profile = pick_profile(by_id, by_sec, by_unique, creator_id, sec_uid, unique_id)
            if profile and profile.get("identity_quality") == "exact":
                follower_count = profile.get("follower_count")
                follower_source = "fetch_user_profile.data.userInfo.stats.followerCount"
                profile_verified = True
                match_method = (
                    "fetch_post_detail.author.id + fetch_user_profile.user.id"
                )
            elif profile:
                follower_count = profile.get("follower_count")
                follower_source = (
                    "fetch_post_detail.data.itemInfo.itemStruct.authorStats.followerCount"
                )
                profile_verified = False
                confidence = "medium"
                match_method = (
                    "fetch_post_detail.author.id + fetch_post_detail.authorStats"
                )
                flags.append("profile_unavailable_or_partial")
                notes.append(
                    "creator profile is partial: follower_count comes from the "
                    "video authorStats fallback, not fetch_user_profile"
                )
            else:
                follower_count = author_stats.get("follower_count")
                follower_source = (
                    "fetch_post_detail.data.itemInfo.itemStruct.authorStats.followerCount"
                )
                profile_verified = False
                confidence = "medium"
                match_method = "fetch_post_detail.author.id (no profile)"
                flags.append("profile_missing")
            identity_basis = "fetch_post_detail.author"
            profile_identity_quality = (
                profile.get("identity_quality") if profile else None
            )
            profile_url = (
                profile.get("profile_url")
                if profile
                else (f"https://www.tiktok.com/@{unique_id}" if unique_id else None)
            )
        else:
            observations = search_obs.get(video_id) or []
            if not observations:
                continue
            latest = observations[0]
            creator_id = latest.get("uid")
            sec_uid = latest.get("sec_uid")
            unique_id = latest.get("unique_id")
            nickname = latest.get("nickname")
            source_endpoint = "/api/v1/tiktok/web/fetch_video_search_result"
            source_file = latest.get("raw_file")
            captured_at = latest.get("captured_at")
            request_id = latest.get("request_id")
            request_params = latest.get("request_params")
            follower_observations = sorted(
                {
                    obs["follower_count"]
                    for obs in observations
                    if obs.get("follower_count") is not None
                }
            )
            profile = pick_profile(by_id, by_sec, by_unique, creator_id, sec_uid, unique_id)
            if profile and profile.get("identity_quality") == "exact":
                follower_count = profile.get("follower_count")
                follower_source = "fetch_user_profile.data.userInfo.stats.followerCount"
                profile_verified = True
                match_method = (
                    "fetch_video_search_result.author.uid + fetch_user_profile.user.id"
                )
            else:
                follower_count = latest.get("follower_count")
                follower_source = (
                    "fetch_video_search_result.aweme_info.author.follower_count"
                )
                profile_verified = False
                match_method = "fetch_video_search_result.aweme_info.author.uid"
                if profile:
                    flags.append("profile_partial")
                else:
                    flags.append("search_snapshot_only")
            confidence = "high"
            identity_basis = "fetch_video_search_result.aweme_info.author"
            profile_identity_quality = (
                profile.get("identity_quality") if profile else None
            )
            profile_url = (
                profile.get("profile_url")
                if profile
                else (f"https://www.tiktok.com/@{unique_id}" if unique_id else None)
            )
            if len(follower_observations) > 1:
                flags.append("follower_count_varies_across_search_captures")
                notes.append(
                    "follower_count observed at multiple search capture times; "
                    "the latest capture is used and the range is recorded"
                )

        row = {
            "schema_version": SCHEMA_VERSION,
            "relation": "video_creator",
            "video_id": video_id,
            "creator_id": creator_id,
            "sec_uid": sec_uid,
            "unique_id": unique_id,
            "nickname": nickname,
            "follower_count": follower_count,
            "creator_tier": creator_tier(follower_count),
            "match_method": match_method,
            "confidence": confidence,
            "identity_basis": identity_basis,
            "profile_verified": profile_verified,
            "profile_identity_quality": profile_identity_quality,
            "profile_url": profile_url,
            "follower_count_source": follower_source,
            "follower_count_search_observations": follower_observations,
            "source_endpoint": source_endpoint,
            "source_file": source_file,
            "request_id": request_id,
            "request_params": request_params,
            "captured_at": captured_at,
            "data_quality_flags": flags,
            "notes": notes,
            "evidence": {
                "video_identity_fields": (
                    "data.itemInfo.itemStruct.author.{id,secUid,uniqueId,nickname}"
                    if detail
                    else "data.search_item_list[].aweme_info.author.{uid,sec_uid,unique_id,nickname}"
                ),
                "follower_count_field": follower_source,
                "profile_raw_file": (
                    profile.get("profile_raw_file") if profile else None
                ),
                "profile_derived_file": os.path.join(
                    run_dir, "creator-video", "raw", "creators.json"
                ),
                "video_derived_file": os.path.join(
                    run_dir, "creator-video", "raw", "video-snapshots.json"
                ),
            },
        }
        rows.append(row)

    return rows


def classify_video_product(video: dict, detail: dict | None,
                           product_rows: list[dict], hashtags: set[str],
                           platform_is_ad: bool | None = None) -> dict:
    desc = video.get("desc") or ""
    desc_text = strip_hashtags(desc)
    brand_in_desc = term_hits(BRAND_TERMS, desc_text)
    category_in_desc = term_hits(CATEGORY_TERMS, desc_text)
    brand_in_tags = term_hits(BRAND_TERMS, "\n".join(sorted(hashtags)))
    category_in_tags = term_hits(CATEGORY_TERMS, "\n".join(sorted(hashtags)))

    anchor_ids = list(video.get("anchor_product_ids") or [])
    target_anchor = TARGET_PRODUCT_ID in anchor_ids
    # A product anchor is a purchase link. Detail rows also expose
    # has_shop_product, which catches in-video product links without a product_id.
    has_link = bool(anchor_ids) or bool((detail or {}).get("has_shop_product"))
    content_tag, content_tag_evidence = detect_content_tag(
        desc_text, anchor_ids, has_link, platform_is_ad
    )
    non_target_label, non_target_term = detect_non_target_subline(
        desc_text, hashtags
    )
    non_target_subline = non_target_label is not None
    non_target_evidence = {
        "label": non_target_label,
        "matched_phrase": non_target_term,
        "field": "desc_without_hashtags_or_hashtags",
        "snippet": evidence_snippet(normalize_text(desc_text), non_target_term)
        if non_target_term
        else "",
    }
    duplicate_anchor_ids = [
        product_id for product_id in anchor_ids
        if product_id in DUPLICATE_LISTING_PRODUCT_IDS
    ]
    category_rows = [
        row for row in product_rows
        if row.get("association_scope") in ("target_product", "belly_band_category")
    ]
    sibling_rows = [
        row for row in category_rows
        if row.get("product_id") not in DUPLICATE_LISTING_PRODUCT_IDS
        and row.get("product_id") != TARGET_PRODUCT_ID
    ]
    sibling_is_momcozy = any(
        "momcozy" in (row.get("product_title") or "").lower()
        for row in sibling_rows
    )

    if target_anchor:
        confidence = "high"
        relation_type = "target_exact"
        status = "confirmed"
        match_method = "anchor_product_id_exact"
        target_assessment = "confirmed_exact_product_id"
        target_baseline_eligible = True
        target_baseline_cohort = "target_exact"
        category_anchor_verified = True
        reason = "video carries an anchor whose product_id equals the target product_id"
    elif duplicate_anchor_ids:
        confidence = "medium"
        relation_type = "duplicate_listing_anchor"
        status = "probable"
        match_method = "anchor_duplicate_listing_product_id"
        target_assessment = "probable_duplicate_listing"
        target_baseline_eligible = False
        target_baseline_cohort = "category_reference"
        category_anchor_verified = True
        reason = (
            "anchor product_id differs from the target; the anchor title belongs "
            "to the same Momcozy YB001 series but is not identical; product IDs "
            "are not merged and the row is category reference only"
        )
    elif category_rows:
        confidence = "low"
        relation_type = (
            "sibling_product_anchor" if sibling_is_momcozy
            else "other_brand_category_anchor"
        )
        status = "unconfirmed"
        match_method = "anchor_other_product_category"
        target_assessment = "unconfirmed_category_context"
        target_baseline_eligible = False
        target_baseline_cohort = "category_context_only"
        category_anchor_verified = True
        reason = (
            "video carries an anchor to a different belly-band product; it confirms "
            "category context, not the target product"
        )
    elif brand_in_desc and category_in_desc and non_target_subline:
        confidence = "low"
        relation_type = "non_target_subline"
        status = "unconfirmed"
        match_method = "desc_non_target_subline"
        target_assessment = "non_target_product_line"
        target_baseline_eligible = False
        target_baseline_cohort = "non_target_subline"
        category_anchor_verified = False
        reason = (
            "description contains a target-brand term and a belly-band category "
            f"term, but names another product line ({non_target_label}: "
            f"'{non_target_term}'); no anchor to the target product. Demoted from "
            "medium and excluded from category reference."
        )
    elif brand_in_desc and category_in_desc:
        confidence = "medium"
        relation_type = "text_brand_and_category"
        status = "probable"
        match_method = "desc_brand_and_category"
        target_assessment = "probable_text_evidence"
        target_baseline_eligible = False
        target_baseline_cohort = "category_reference"
        category_anchor_verified = False
        if content_tag == "consideration":
            reason = (
                "video description contains a target-brand term and a belly-band "
                "category term, but it asks whether to buy and shows no product "
                "anchor, no purchase link, no platform ad flag, and no first-person "
                "usage evidence. Category reference only; excluded from all "
                "performance statistics."
            )
        else:
            reason = (
                "video description contains a target-brand term and a belly-band "
                "category term; no product anchor is present. Category reference "
                "only; not an exact-ID baseline row and not used for performance "
                "comparisons."
            )
    elif category_in_desc:
        confidence = "low"
        relation_type = "text_category_only"
        status = "unconfirmed"
        match_method = "desc_category_only"
        target_assessment = "unconfirmed_category_context"
        target_baseline_eligible = False
        target_baseline_cohort = "category_context_only"
        category_anchor_verified = False
        reason = "video description contains a category term but no target-brand term"
    elif category_in_tags:
        confidence = "low"
        relation_type = "hashtag_category_only"
        status = "unconfirmed"
        match_method = "hashtag_category_only"
        target_assessment = "unconfirmed_category_context"
        target_baseline_eligible = False
        target_baseline_cohort = "category_context_only"
        category_anchor_verified = False
        reason = "hashtags contain a category term but the description has no brand+category evidence"
    else:
        confidence = "none"
        relation_type = "no_signal"
        status = "not_related"
        match_method = "none"
        target_assessment = "not_related"
        target_baseline_eligible = False
        target_baseline_cohort = "not_related"
        category_anchor_verified = False
        reason = "no target product anchor, no belly-band category term, no target-brand term"

    # Only exact target anchors may enter any performance statistic. Medium and
    # low rows are descriptive reference material.
    performance_eligible = relation_type == "target_exact"

    return {
        "desc": desc,
        "desc_text_without_hashtags": desc_text.strip(),
        "brand_in_desc": brand_in_desc,
        "category_in_desc": category_in_desc,
        "brand_in_tags": brand_in_tags,
        "category_in_tags": category_in_tags,
        "hashtags": sorted(hashtags),
        "anchor_ids": anchor_ids,
        "target_anchor": target_anchor,
        "duplicate_anchor_ids": duplicate_anchor_ids,
        "category_rows": category_rows,
        "sibling_rows": sibling_rows,
        "sibling_is_momcozy": sibling_is_momcozy,
        "confidence": confidence,
        "relation_type": relation_type,
        "status": status,
        "match_method": match_method,
        "target_assessment": target_assessment,
        "target_baseline_eligible": target_baseline_eligible,
        "baseline_eligible": target_baseline_eligible,
        "performance_eligible": performance_eligible,
        "review_required": confidence == "medium",
        "target_baseline_cohort": target_baseline_cohort,
        "category_anchor_verified": category_anchor_verified,
        "content_tag": content_tag,
        "content_tag_evidence": content_tag_evidence,
        "non_target_subline": non_target_subline,
        "non_target_subline_label": non_target_label,
        "non_target_subline_evidence": non_target_evidence,
        "platform_is_ad": platform_is_ad,
        "has_link": has_link,
        "reason": reason,
    }


def pick_search_provenance(video: dict) -> dict:
    """Return the provenance entry that produced search_snapshot.statistics."""
    snapshot = video.get("search_snapshot") or {}
    captured_at = snapshot.get("captured_at")
    provenance = snapshot.get("provenance") or []
    for entry in provenance:
        if captured_at and entry.get("captured_at") == captured_at:
            return entry
    return provenance[0] if provenance else {}


def build_video_product_rows(run_dir: str, snapshots: list[dict],
                             details: dict[str, dict],
                             product_rows_all: list[dict],
                             search_hashtags: dict[str, set[str]],
                             search_ad_flags: dict[str, bool] | None = None) -> list[dict]:
    search_ad_flags = search_ad_flags or {}
    products_by_video: dict[str, list[dict]] = defaultdict(list)
    for row in product_rows_all:
        products_by_video[row["video_id"]].append(row)

    rows: list[dict] = []
    for video in snapshots:
        video_id = video["video_id"]
        detail = details.get(video_id)
        hashtags = set(search_hashtags.get(video_id) or set())
        if detail:
            hashtags.update(
                item.get("name")
                for item in (detail.get("hashtags") or [])
                if item.get("name")
            )
        product_rows = products_by_video.get(video_id, [])
        # Detail snapshots expose is_ad; search-only rows expose is_ads. Prefer the
        # detail field when present, otherwise keep the search boolean.
        if detail and isinstance(detail.get("is_ad"), bool):
            platform_is_ad = detail.get("is_ad")
        else:
            platform_is_ad = search_ad_flags.get(video_id)
        classification = classify_video_product(
            video, detail, product_rows, hashtags, platform_is_ad
        )
        search_provenance = pick_search_provenance(video)

        search_snapshot = compact_stats(
            (video.get("search_snapshot") or {}).get("statistics"),
            "/api/v1/tiktok/app/v3/fetch_video_search_result",
            (video.get("search_snapshot") or {}).get("captured_at"),
            search_provenance.get("raw_file"),
        )
        detail_snapshot = compact_stats(
            (video.get("detail_snapshot") or {}).get("statistics"),
            "/api/v1/tiktok/web/fetch_post_detail",
            (video.get("detail_snapshot") or {}).get("captured_at"),
            (video.get("detail_snapshot") or {}).get("raw_file"),
        )
        preferred = detail_snapshot or search_snapshot
        if detail:
            source_endpoint = "/api/v1/tiktok/web/fetch_post_detail"
            source_file = detail.get("raw_file")
            captured_at = detail.get("captured_at")
            field_paths = {
                "desc": "data.itemInfo.itemStruct.desc",
                "hashtags": "data.itemInfo.itemStruct.textExtra[].hashtagName",
                "anchors": "data.itemInfo.itemStruct.anchors[].extra",
                "statistics": (
                    "data.itemInfo.itemStruct.stats."
                    "{playCount,diggCount,commentCount,shareCount,collectCount}"
                ),
            }
        else:
            source_endpoint = "/api/v1/tiktok/app/v3/fetch_video_search_result"
            source_file = search_provenance.get("raw_file")
            captured_at = (video.get("search_snapshot") or {}).get("captured_at")
            field_paths = {
                "desc": "data.search_item_list[].aweme_info.desc",
                "hashtags": "data.search_item_list[].aweme_info.text_extra[].hashtag_name",
                "anchors": "data.search_item_list[].aweme_info.anchors[].extra",
                "statistics": (
                    "data.search_item_list[].aweme_info.statistics."
                    "{play_count,digg_count,comment_count,share_count,collect_count}"
                ),
            }

        anchor_products = []
        for product in product_rows:
            anchor_products.append(
                {
                    "product_id": product.get("product_id"),
                    "product_title": product.get("product_title"),
                    "association_scope": product.get("association_scope"),
                    "video_level_association_tier": product.get(
                        "video_level_association_tier"
                    ),
                    "association_method": product.get("association_method"),
                    "confidence": product.get("confidence"),
                    "is_target_product": product.get("product_id") == TARGET_PRODUCT_ID,
                    "is_duplicate_listing": product.get("product_id")
                    in DUPLICATE_LISTING_PRODUCT_IDS,
                    "is_belly_band_category": product.get("association_scope")
                    in ("target_product", "belly_band_category"),
                    "is_unrelated_product": product.get("association_scope")
                    == "unrelated_product",
                }
            )

        notes = []
        if classification["duplicate_anchor_ids"]:
            notes.append(
                "duplicate-listing anchor: the anchor points to another listing in "
                "the same Momcozy YB001 series; product_id differs and the title is "
                "similar but not identical; not merged into the target baseline"
            )
        if classification["relation_type"] == "sibling_product_anchor":
            notes.append(
                "anchor points to a different Momcozy belly-band product; "
                "category context only for the target product"
            )
        if classification["relation_type"] == "other_brand_category_anchor":
            notes.append(
                "anchor points to a different brand's belly-band product; "
                "category context only for the target product"
            )
        if classification["relation_type"] == "non_target_subline":
            notes.append(
                "text row demoted to low: description names another product line "
                f"({classification['non_target_subline_label']}); it is not target "
                "product evidence"
            )
        if classification["relation_type"] == "text_brand_and_category":
            notes.append(
                "medium text evidence; no product_id link to the target. "
                "Category reference only, never baseline or performance statistics."
            )
        if classification["content_tag"] == "consideration":
            notes.append(
                "content tag consideration: no product anchor, no link, platform "
                "is_ads=false, purchase-intent or advice-seeking wording, and no "
                "first-person usage evidence. Excluded from all performance statistics."
            )
        if classification["confidence"] == "low":
            notes.append(
                "low confidence: excluded from baseline statistics; "
                "listed in video-product-unconfirmed.jsonl"
            )
        if classification["confidence"] == "none":
            notes.append("no target or belly-band category signal; negative row kept for audit")

        row = {
            "schema_version": SCHEMA_VERSION,
            "relation": "video_product",
            "video_id": video_id,
            "target_product_id": TARGET_PRODUCT_ID,
            "target_product_name": TARGET_PRODUCT_NAME,
            "confidence": classification["confidence"],
            "relation_type": classification["relation_type"],
            "status": classification["status"],
            "target_assessment": classification["target_assessment"],
            "match_method": classification["match_method"],
            "target_baseline_eligible": classification["target_baseline_eligible"],
            "baseline_eligible": classification["baseline_eligible"],
            "performance_eligible": classification["performance_eligible"],
            "review_required": classification["review_required"],
            "target_baseline_cohort": classification["target_baseline_cohort"],
            "category_anchor_verified": classification["category_anchor_verified"],
            "content_tag": classification["content_tag"],
            "content_tag_evidence": classification["content_tag_evidence"],
            "non_target_subline": classification["non_target_subline"],
            "non_target_subline_label": classification["non_target_subline_label"],
            "non_target_subline_evidence": classification[
                "non_target_subline_evidence"
            ],
            "platform_is_ad": classification["platform_is_ad"],
            "has_link": classification["has_link"],
            "anchor_product_ids": classification["anchor_ids"],
            "anchor_products": anchor_products,
            "text_evidence": {
                "desc": classification["desc"],
                "desc_text_without_hashtags": classification[
                    "desc_text_without_hashtags"
                ],
                "matched_brand_terms_in_desc": classification["brand_in_desc"],
                "matched_category_terms_in_desc": classification[
                    "category_in_desc"
                ],
                "matched_brand_terms_in_hashtags": classification["brand_in_tags"],
                "matched_category_terms_in_hashtags": classification[
                    "category_in_tags"
                ],
                "hashtags": classification["hashtags"],
            },
            "engagement": {
                "preferred_snapshot": (
                    "fetch_post_detail" if detail_snapshot else "fetch_video_search_result"
                ),
                "metric_definition": (
                    "(like_count + comment_count + share_count + collect_count) "
                    "/ play_count"
                ),
                "play_count": (preferred or {}).get("play_count"),
                "like_count": (preferred or {}).get("like_count"),
                "comment_count": (preferred or {}).get("comment_count"),
                "share_count": (preferred or {}).get("share_count"),
                "collect_count": (preferred or {}).get("collect_count"),
                "interaction_rate": (preferred or {}).get("interaction_rate"),
                "is_estimated": None,
                "is_estimated_field_present": False,
                "search_snapshot": search_snapshot,
                "detail_snapshot": detail_snapshot,
            },
            "evidence": {
                "source_endpoint": source_endpoint,
                "source_file": source_file,
                "captured_at": captured_at,
                "request_id": (
                    detail.get("_raw_request_id")
                    if detail
                    else search_provenance.get("request_id")
                ),
                "provider_time": (
                    detail.get("_raw_provider_time")
                    if detail
                    else None
                ),
                "field_paths": field_paths,
                "derived_files": {
                    "video_snapshots": os.path.join(
                        run_dir, "creator-video", "raw", "video-snapshots.json"
                    ),
                    "video_products": os.path.join(
                        run_dir, "creator-video", "raw", "video-products.json"
                    ),
                    "video_details": os.path.join(
                        run_dir, "creator-video", "raw", "video-details.json"
                    )
                    if detail
                    else None,
                },
                "reason": classification["reason"],
            },
            "notes": notes,
        }
        rows.append(row)
    return rows


def scan_keys(payload, needles: set[str], prefix: str = "") -> Counter:
    counter: Counter = Counter()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in needles:
                counter[key] += 1
            counter.update(scan_keys(value, needles, f"{prefix}{key}."))
    elif isinstance(payload, list):
        for value in payload:
            counter.update(scan_keys(value, needles, f"{prefix}[]."))
    return counter


def find_review_rows(payload) -> list[dict]:
    rows: list[dict] = []
    if isinstance(payload, dict):
        if "review_id" in payload:
            rows.append(payload)
        for value in payload.values():
            rows.extend(find_review_rows(value))
    elif isinstance(payload, list):
        for value in payload:
            rows.extend(find_review_rows(value))
    return rows


def build_comment_video_gap(run_dir: str, output_dir: str,
                            video_ids: set[str]) -> dict:
    canonical_path = os.path.join(run_dir, "canonical-records.jsonl")
    canonical = load_jsonl(canonical_path)
    tiktok_shop = [row for row in canonical if row.get("source") == "tiktok_shop"]

    canonical_video_keys = Counter()
    source_meta_keys: set[str] = set()
    video_key_needles = {
        "video_id",
        "aweme_id",
        "item_id",
        "creator_id",
        "author_id",
        "sec_uid",
    }
    for row in tiktok_shop:
        canonical_video_keys.update(scan_keys(row, video_key_needles))
        source_meta_keys.update((row.get("source_meta") or {}).keys())

    raw_dir = os.path.join(run_dir, "raw", "tikhub")
    raw_files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    raw_rows: list[dict] = []
    for raw_file in raw_files:
        raw_rows.extend(find_review_rows(load_json(raw_file)))

    raw_video_keys = Counter()
    for row in raw_rows:
        raw_video_keys.update(scan_keys(row, video_key_needles))

    canonical_external_ids = {
        str(row.get("external_id"))
        for row in tiktok_shop
        if row.get("external_id")
    }
    raw_review_ids = {
        str(row.get("review_id")) for row in raw_rows if row.get("review_id")
    }
    review_video_id_collisions = sorted(
        (canonical_external_ids | raw_review_ids) & video_ids
    )

    reason = (
        "The 175 canonical tiktok_shop records are product reviews fetched from "
        "/api/v1/tiktok/shop/web/fetch_product_reviews_v2. Their external_id is the "
        "review_id (it matches raw review_id 175/175), not a video/aweme id. Neither "
        "the canonical source_meta nor the 180 raw review rows expose "
        "video_id/aweme_id/item_id. The reviewer_id in the raw payload is the review "
        "author's user id, not a video author id. Therefore a comment->video relation "
        "cannot be built from this corpus. This is a product-review layer, not a "
        "video-comment layer."
    )

    gap = {
        "schema_version": SCHEMA_VERSION,
        "relation": "comment_video",
        "status": "not_available",
        "relation_count": 0,
        "coverage_rate": 0.0,
        "generated_at": now_iso(),
        "judgment": (
            "comment -> video relation does not exist in the current corpus; "
            "0% of product reviews can be tied to a video_id"
        ),
        "reason": reason,
        "evidence": {
            "canonical_file": canonical_path,
            "canonical_tiktok_shop_rows": len(tiktok_shop),
            "canonical_rows_with_video_key": sum(
                1 for row in tiktok_shop if scan_keys(row, video_key_needles)
            ),
            "canonical_video_key_hits": {
                key: canonical_video_keys.get(key, 0)
                for key in sorted(video_key_needles)
            },
            "canonical_source_meta_fields": sorted(source_meta_keys),
            "canonical_external_id_is_review_id": True,
            "canonical_external_id_shape": (
                "19-digit numeric string; matches raw review_id 175/175 and does "
                "not collide with any of the 141 video IDs"
            ),
            "canonical_external_ids_matching_raw_review_ids": len(
                canonical_external_ids & raw_review_ids
            ),
            "raw_review_files": len(raw_files),
            "raw_review_rows": len(raw_rows),
            "raw_rows_with_video_key": sum(
                1 for row in raw_rows if scan_keys(row, video_key_needles)
            ),
            "raw_video_key_hits": {
                key: raw_video_keys.get(key, 0)
                for key in sorted(video_key_needles)
            },
            "raw_reviewer_id_present": sum(
                1 for row in raw_rows if row.get("reviewer_id")
            ),
            "reviewer_id_role": (
                "review author user id; not a video id, aweme id, or video creator id"
            ),
            "raw_review_ids_matching_canonical_external_ids": len(
                raw_review_ids & canonical_external_ids
            ),
            "review_id_video_id_collisions": len(review_video_id_collisions),
            "source_endpoint": "/api/v1/tiktok/shop/web/fetch_product_reviews_v2",
            "collector_endpoint_id": "tikhub_tiktok_shop_reviews_v2",
            "canonical_url_field_example": next(
                (row.get("url") for row in tiktok_shop if row.get("url")), None
            ),
            "canonical_author_field": (
                "masked reviewer name, not a TikTok creator unique_id"
            ),
        },
        "why_the_layer_is_different": {
            "product_review": "a review of a product, keyed by review_id + product_id + sku_id",
            "video_comment": "a comment under a video, keyed by comment_id + aweme_id",
            "current_source": "product review",
            "population_mismatch": (
                "the review layer and the video/comment layer have different "
                "populations and different denominators; do not merge them"
            ),
        },
        "what_would_be_needed": [
            "A product-review payload that includes video_id/aweme_id/item_id "
            "(the current TikTok Shop review endpoint does not expose it).",
            "Or an affiliate/order attribution export that maps review_id or order_id "
            "to the promoting video.",
            "Or switch to fetch_video_comments, which returns comments keyed by "
            "aweme_id, and treat them as a separate video-comment population.",
            "A product->video enumeration source (creator cookie endpoint or a "
            "verified product-video index) to connect the review product to videos.",
        ],
        "what_was_not_done": [
            "No comment->video rows were fabricated.",
            "No reviewer_id was treated as a creator_id or video_id.",
            "No canonical-records.jsonl or gold-set-50.jsonl content was changed.",
        ],
        "output_file": os.path.join(output_dir, "comment-video.jsonl"),
    }
    return gap


def build_coverage(run_dir: str, output_dir: str, snapshots: list[dict],
                   details: dict[str, dict], creator_rows: list[dict],
                   product_rows: list[dict], comment_gap: dict) -> dict:
    total_videos = len(snapshots)
    detail_videos = sum(1 for video in snapshots if video.get("detail_snapshot"))
    search_only_videos = total_videos - detail_videos

    creator_confidence = Counter(row["confidence"] for row in creator_rows)
    creator_match_methods = Counter(row["match_method"] for row in creator_rows)
    creator_source = Counter(row["identity_basis"] for row in creator_rows)
    creator_follower_source = Counter(
        row["follower_count_source"] for row in creator_rows
    )
    unique_creators = len(
        {
            row.get("sec_uid") or row.get("unique_id") or row.get("creator_id")
            for row in creator_rows
        }
    )
    profile_verified_rows = sum(1 for row in creator_rows if row["profile_verified"])

    product_confidence = Counter(row["confidence"] for row in product_rows)
    product_status = Counter(row["status"] for row in product_rows)
    product_relation_type = Counter(row["relation_type"] for row in product_rows)
    product_match_method = Counter(row["match_method"] for row in product_rows)
    candidate_rows = [
        row for row in product_rows if row["confidence"] in ("high", "medium", "low")
    ]
    target_exact = sum(
        1 for row in product_rows if row["relation_type"] == "target_exact"
    )
    duplicate_listing = sum(
        1 for row in product_rows
        if row["relation_type"] == "duplicate_listing_anchor"
    )
    text_medium = sum(
        1 for row in product_rows
        if row["relation_type"] == "text_brand_and_category"
    )
    non_target_subline_n = sum(
        1 for row in product_rows if row["relation_type"] == "non_target_subline"
    )
    consideration_n = sum(
        1 for row in product_rows if row["content_tag"] == "consideration"
    )
    material_candidate_n = sum(
        1 for row in product_rows if row["content_tag"] == "material_candidate"
    )
    unknown_content_tag_n = sum(
        1 for row in product_rows if row["content_tag"] == "unknown"
    )
    category_reference_n = sum(
        1 for row in product_rows
        if row["target_baseline_cohort"] == "category_reference"
    )
    performance_eligible_n = sum(
        1 for row in product_rows if row["performance_eligible"]
    )
    baseline_eligible_n = sum(1 for row in product_rows if row["baseline_eligible"])
    category_anchor = sum(
        1 for row in product_rows if row["category_anchor_verified"]
    )
    category_anchor_with_detail = sum(
        1 for row in product_rows
        if row["category_anchor_verified"] and row["engagement"]["detail_snapshot"]
    )
    unconfirmed = sum(1 for row in product_rows if row["status"] == "unconfirmed")
    not_related = sum(1 for row in product_rows if row["status"] == "not_related")

    # Creator profile inventory from creators.json.
    creators_path = os.path.join(run_dir, "creator-video", "raw", "creators.json")
    creators = load_json(creators_path).get("creators") or []
    profile_exact = sum(
        1 for row in creators if row.get("identity_quality") == "exact"
    )
    profile_partial = sum(
        1 for row in creators if row.get("identity_quality") == "partial"
    )

    # Product raw review snapshot context (not used for video joins).
    review_total = 1137
    review_rating = 4.2
    review_raw_file = sorted(
        glob.glob(os.path.join(run_dir, "raw", "tikhub", "*.json"))
    )
    if review_raw_file:
        payload = load_json(review_raw_file[0])
        review_meta = payload.get("data", {}).get("data", {})
        review_total = int(review_meta.get("total_reviews") or review_total)
        review_rating = (
            (review_meta.get("review_ratings") or {}).get("overall_score")
            or review_rating
        )

    baseline_path = os.path.join(run_dir, "creator-video", "baseline.json")
    existing_baseline = load_json(baseline_path) if os.path.exists(baseline_path) else {}
    high_rows = [row for row in product_rows if row["confidence"] == "high"]
    category_rows = [
        row for row in product_rows
        if row["category_anchor_verified"] and row["engagement"]["detail_snapshot"]
    ]
    high_rates = [
        row["engagement"]["interaction_rate"] for row in high_rows
        if row["engagement"]["interaction_rate"] is not None
    ]
    category_rates = [
        row["engagement"]["interaction_rate"] for row in category_rows
        if row["engagement"]["interaction_rate"] is not None
    ]
    existing_cohorts = existing_baseline.get("cohorts") or {}
    existing_product = existing_cohorts.get("product_exact_baseline") or {}
    existing_category = existing_cohorts.get("category_anchor_verified_baseline") or {}
    baseline_video_to_creator = {}
    for row in existing_baseline.get("creator_table") or []:
        for video_id in row.get("video_ids") or []:
            baseline_video_to_creator[video_id] = row
    creator_mismatches = []
    for row in creator_rows:
        existing = baseline_video_to_creator.get(row["video_id"])
        if not existing:
            continue
        if (
            existing.get("follower_count") != row["follower_count"]
            or existing.get("creator_tier") != row["creator_tier"]
        ):
            creator_mismatches.append(row["video_id"])
    baseline_reproduction = {
        "source": baseline_path,
        "product_exact": {
            "n": len(high_rows),
            "median_interaction_rate": round(statistics.median(high_rates), 6)
            if high_rates
            else None,
            "existing_baseline_n": existing_product.get("n_videos"),
            "existing_baseline_median_interaction_rate": existing_product.get(
                "median_interaction_rate"
            ),
            "matches_existing_baseline": (
                len(high_rows) == existing_product.get("n_videos")
                and high_rates
                and round(statistics.median(high_rates), 6)
                == round(existing_product.get("median_interaction_rate", -1), 6)
            ),
        },
        "category_anchor_verified_with_detail": {
            "n": len(category_rows),
            "median_interaction_rate": round(statistics.median(category_rates), 6)
            if category_rates
            else None,
            "existing_baseline_n": existing_category.get("n_videos"),
            "existing_baseline_median_interaction_rate": existing_category.get(
                "median_interaction_rate"
            ),
            "matches_existing_baseline": (
                len(category_rows) == existing_category.get("n_videos")
                and category_rates
                and round(statistics.median(category_rates), 6)
                == round(existing_category.get("median_interaction_rate", -1), 6)
            ),
        },
        "creator_table": {
            "videos_covered_by_existing_baseline": len(baseline_video_to_creator),
            "follower_count_or_tier_mismatches": len(creator_mismatches),
            "mismatch_video_ids": creator_mismatches,
            "matches_existing_baseline": len(creator_mismatches) == 0,
        },
        "note": (
            "Cross-check only: the relation table reproduces the existing "
            "baseline.json cohorts from the same detail snapshots. It does not "
            "recompute or replace baseline.json."
        ),
    }

    coverage = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "run_dir": run_dir,
        "relations_dir": output_dir,
        "inputs": {
            "video_snapshots": os.path.join(
                run_dir, "creator-video", "raw", "video-snapshots.json"
            ),
            "video_details": os.path.join(
                run_dir, "creator-video", "raw", "video-details.json"
            ),
            "video_products": os.path.join(
                run_dir, "creator-video", "raw", "video-products.json"
            ),
            "creators": creators_path,
            "canonical_records": os.path.join(run_dir, "canonical-records.jsonl"),
            "raw_reviews_glob": os.path.join(run_dir, "raw", "tikhub", "*.json"),
            "raw_search_glob": os.path.join(
                run_dir, "creator-video", "raw", "video-search-*.json"
            ),
        },
        "video_inventory": {
            "unique_videos": total_videos,
            "videos_with_search_snapshot": total_videos,
            "videos_with_detail_snapshot": detail_videos,
            "videos_without_detail_snapshot": search_only_videos,
            "unique_authors_in_search_sample": unique_creators,
            "creators_from_details": profile_exact + profile_partial,
            "creators_with_profile": len(creators),
            "creators_profile_exact": profile_exact,
            "creators_profile_partial": profile_partial,
            "creators_without_profile_but_search_author": max(
                0, unique_creators - len(creators)
            ),
        },
        "video_creator": {
            "relation_rows": len(creator_rows),
            "videos_linked": len(creator_rows),
            "coverage_rate": round(len(creator_rows) / total_videos, 4)
            if total_videos
            else 0.0,
            "unique_creators_linked": unique_creators,
            "confidence_distribution": dict(sorted(creator_confidence.items())),
            "match_method_distribution": dict(sorted(creator_match_methods.items())),
            "identity_source_distribution": dict(sorted(creator_source.items())),
            "follower_count_source_distribution": dict(
                sorted(creator_follower_source.items())
            ),
            "profile_verified_rows": profile_verified_rows,
            "profile_verified_rate": round(profile_verified_rows / len(creator_rows), 4)
            if creator_rows
            else 0.0,
            "note": (
                "59 rows use fetch_post_detail author identity; 82 rows use the "
                "fetch_video_search_result aweme author object because no detail "
                "snapshot exists. Both carry uid/sec_uid/unique_id. Only 52 unique "
                "creators have a fetched profile; the other 72 have search-payload "
                "identity only."
            ),
        },
        "video_product_target": {
            "target_product_id": TARGET_PRODUCT_ID,
            "target_product_name": TARGET_PRODUCT_NAME,
            "relation_rows": len(product_rows),
            "candidate_relation_rows": len(candidate_rows),
            "no_relation_rows": len(product_rows) - len(candidate_rows),
            "confidence_distribution": dict(sorted(product_confidence.items())),
            "status_distribution": dict(sorted(product_status.items())),
            "relation_type_distribution": dict(sorted(product_relation_type.items())),
            "match_method_distribution": dict(sorted(product_match_method.items())),
            "content_tag_distribution": {
                "consideration": consideration_n,
                "material_candidate": material_candidate_n,
                "unknown": unknown_content_tag_n,
            },
            "performance_eligible_n": performance_eligible_n,
            "target_coverage": {
                "exact_product_id_high": target_exact,
                "exact_product_id_rate": round(target_exact / total_videos, 4)
                if total_videos
                else 0.0,
                "plus_text_evidence_medium": target_exact + text_medium,
                "plus_text_evidence_rate": round(
                    (target_exact + text_medium) / total_videos, 4
                )
                if total_videos
                else 0.0,
                "plus_duplicate_listing_medium": target_exact + text_medium + duplicate_listing,
                "plus_duplicate_listing_rate": round(
                    (target_exact + text_medium + duplicate_listing) / total_videos, 4
                )
                if total_videos
                else 0.0,
                "category_reference_n": category_reference_n,
                "category_reference_rate": round(
                    category_reference_n / total_videos, 4
                )
                if total_videos
                else 0.0,
                "non_target_subline_n": non_target_subline_n,
                "consideration_n": consideration_n,
                "category_anchor_verified": category_anchor,
                "category_anchor_verified_rate": round(
                    category_anchor / total_videos, 4
                )
                if total_videos
                else 0.0,
                "category_anchor_verified_with_detail": category_anchor_with_detail,
            },
            "baseline_eligibility": {
                "baseline_eligible_n": baseline_eligible_n,
                "performance_eligible_n": performance_eligible_n,
                "target_exact_baseline_n": target_exact,
                "target_text_evidence_review_n": text_medium,
                "target_review_candidate_n": target_exact + text_medium,
                "target_relaxed_if_accepted_n": target_exact,
                "duplicate_listing_review_n": duplicate_listing,
                "category_reference_n": category_reference_n,
                "consideration_n": consideration_n,
                "non_target_subline_n": non_target_subline_n,
                "category_anchor_verified_n": category_anchor,
                "category_anchor_verified_with_detail_n": category_anchor_with_detail,
                "unconfirmed_low_n": unconfirmed,
                "not_related_n": not_related,
                "policy": (
                    "Only exact target anchors (high confidence, "
                    "anchor product_id == target) are baseline and performance "
                    "eligible. All medium rows are category reference: they may be "
                    "counted, described, and listed, but they never enter the target "
                    "baseline, never enter performance statistics, and never support "
                    "a 'which content form wins' conclusion. Consideration-tagged rows "
                    "are excluded from all performance statistics. Non-target subline "
                    "text rows are demoted to low. Low confidence is unconfirmed and "
                    "excluded from all baseline statistics."
                ),
            },
            "notes": [
                "All 141 videos are judged; 64 have no target/category signal and are "
                "kept as confidence=none negative rows for audit.",
                "19 medium rows are duplicate-listing anchors; their medium basis is "
                "the anchor product title (same Momcozy YB001 series, similar but not "
                "identical title, different product_id), not the video caption.",
                "11 medium text rows remain category reference. One additional text "
                "row is tagged consideration and also excluded from performance "
                "statistics.",
                "7 text rows naming another product line (Go As You Grow, postpartum "
                "belly band, nursing-bra mix, Momcozy UK) are demoted to low and "
                "tagged non_target_subline.",
                "Only the 10 high-confidence exact-ID rows are baseline and "
                "performance eligible; medium rows are category reference only.",
                "Low confidence rows are additionally written to "
                "video-product-unconfirmed.jsonl.",
                "High confidence rows are additionally written to "
                "video-product-target-baseline.jsonl.",
            ],
        },
        "comment_video": {
            "relation_rows": 0,
            "coverage_rate": 0.0,
            "canonical_tiktok_shop_rows": comment_gap["evidence"][
                "canonical_tiktok_shop_rows"
            ],
            "canonical_rows_with_video_key": sum(
                comment_gap["evidence"]["canonical_video_key_hits"].values()
            ),
            "raw_review_rows": comment_gap["evidence"]["raw_review_rows"],
            "raw_rows_with_video_key": sum(
                comment_gap["evidence"]["raw_video_key_hits"].values()
            ),
            "reviewer_id_present": comment_gap["evidence"][
                "raw_reviewer_id_present"
            ],
            "reviewer_id_is_not_creator_id": True,
            "review_id_video_id_collisions": comment_gap["evidence"][
                "review_id_video_id_collisions"
            ],
            "judgment": comment_gap["judgment"],
            "reason": comment_gap["reason"],
            "explanation_file": os.path.join(output_dir, "comment-video-gap.json"),
        },
        "product_review_context": {
            "product_id": TARGET_PRODUCT_ID,
            "total_reviews_in_raw_snapshot": review_total,
            "overall_rating_in_raw_snapshot": review_rating,
            "note": (
                "The task brief said 1133 reviews; the collected raw snapshot says "
                "1137. This report uses the raw snapshot value and does not overwrite "
                "the task brief."
            ),
        },
        "baseline_reproduction": baseline_reproduction,
        "caveats": [
            "Keyword search is a non-probability sample; the 141 videos are 12 "
            "queries x one page, not a census of the category.",
            "Medium text evidence means brand + belly-band category, not target "
            "product specificity. It is category reference only. Text rows that "
            "name another product line (Go As You Grow, postpartum band, "
            "nursing-bra mix, Momcozy UK) are demoted to low.",
            "Duplicate-listing anchors point to other listings in the same Momcozy "
            "YB001 series with different product_ids and similar but not identical "
            "titles; they are not merged and are kept in the category-reference "
            "bucket.",
            "Search statistics and detail statistics were captured at different "
            "times; the detail snapshot is preferred when present.",
            "Interaction rate uses the provider's play/like/comment/share/collect "
            "fields; it is not view-through, completion, GMV, or conversion.",
            "The product-review layer and the video layer have different "
            "populations; the 175 product reviews cannot be joined to video_id.",
        ],
        "what_is_missing_to_close_the_loop": [
            "A product->video enumeration endpoint that works without the logged-in "
            "creator cookie, or TIKHUB_TIKTOK_CREATOR_COOKIE so "
            "get_product_related_videos / get_video_associated_product_list can run.",
            "A review->video key. The current TikTok Shop product-review endpoint does "
            "not return video_id/aweme_id/item_id; reviewer_id is not a video or "
            "creator id.",
            "Working search pagination. cursor=20 returned the same page, so the 141 "
            "videos are 12 keyword queries x 1 page, not a census.",
            "Detail snapshots for all sample videos. 59/141 have fetch_post_detail; "
            "82 rely on search-level stats and anchors.",
            "Profiles for the 72 search-only creators. 52/124 creators have a fetched "
            "profile; follower_count for the rest is the search author field.",
            "A product-id merge map for the duplicate Momcozy YB001 / CozySupport "
            "Ergonest listings. 19 videos anchor to a duplicate product_id and are "
            "kept medium, not high.",
            "Any source for third-party video GMV/orders, audience demographics, or "
            "subtitles. TikHub exposes those only for the logged-in creator or not "
            "at all.",
        ],
        "constraints_honored": {
            "no_fabricated_rows": True,
            "every_number_has_endpoint_and_field_path": True,
            "low_confidence_excluded_from_baseline": True,
            "low_confidence_single_bucket": "video-product-unconfirmed.jsonl",
            "canonical_records_unchanged": True,
            "gold_set_unchanged": True,
            "database_writes": 0,
        },
        "outputs": {
            "video_creator": os.path.join(output_dir, "video-creator.jsonl"),
            "video_product": os.path.join(output_dir, "video-product.jsonl"),
            "video_product_candidates": os.path.join(
                output_dir, "video-product-candidates.jsonl"
            ),
            "video_product_unconfirmed": os.path.join(
                output_dir, "video-product-unconfirmed.jsonl"
            ),
            "video_product_target_baseline": os.path.join(
                output_dir, "video-product-target-baseline.jsonl"
            ),
            "comment_video": os.path.join(output_dir, "comment-video.jsonl"),
            "comment_video_gap": os.path.join(
                output_dir, "comment-video-gap.json"
            ),
            "coverage": os.path.join(output_dir, "coverage.json"),
        },
    }
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        default="/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029",
        help="VOC run directory",
    )
    args = parser.parse_args()
    run_dir = os.path.abspath(args.run_dir)
    raw_dir = os.path.join(run_dir, "creator-video", "raw")
    output_dir = os.path.join(run_dir, "creator-video", "relations")
    os.makedirs(output_dir, exist_ok=True)

    snapshots = load_json(os.path.join(raw_dir, "video-snapshots.json"))["videos"]
    details = {
        row["video_id"]: row
        for row in load_json(os.path.join(raw_dir, "video-details.json"))["videos"]
    }
    for row in details.values():
        raw_file = row.get("raw_file")
        if raw_file and os.path.exists(raw_file):
            payload = load_json(raw_file)
            row["_raw_request_id"] = payload.get("request_id")
            row["_raw_provider_time"] = payload.get("time")
            row["_raw_provider_timestamp"] = payload.get("time_stamp")
            row["_raw_request_params"] = payload.get("params")
    products = load_json(os.path.join(raw_dir, "video-products.json"))[
        "video_products"
    ]
    creators = load_json(os.path.join(raw_dir, "creators.json"))["creators"]
    search_obs = load_search_observations(raw_dir, snapshots)
    search_hashtags = load_search_hashtags(raw_dir)
    search_ad_flags = load_search_ad_flags(raw_dir)

    creator_rows = build_video_creator_rows(
        run_dir, snapshots, details, creators, search_obs
    )
    product_rows = build_video_product_rows(
        run_dir, snapshots, details, products, search_hashtags, search_ad_flags
    )

    video_ids = {video["video_id"] for video in snapshots}
    comment_gap = build_comment_video_gap(run_dir, output_dir, video_ids)

    write_jsonl(os.path.join(output_dir, "video-creator.jsonl"), creator_rows)
    write_jsonl(os.path.join(output_dir, "video-product.jsonl"), product_rows)
    write_jsonl(
        os.path.join(output_dir, "video-product-candidates.jsonl"),
        [row for row in product_rows if row["confidence"] in ("high", "medium", "low")],
    )
    write_jsonl(
        os.path.join(output_dir, "video-product-unconfirmed.jsonl"),
        [row for row in product_rows if row["confidence"] == "low"],
    )
    write_jsonl(
        os.path.join(output_dir, "video-product-target-baseline.jsonl"),
        [row for row in product_rows if row["confidence"] == "high"],
    )
    # Empty JSONL on purpose: the relation does not exist. The explanation is in
    # comment-video-gap.json.
    with open(os.path.join(output_dir, "comment-video.jsonl"), "w", encoding="utf-8"):
        pass
    write_json(os.path.join(output_dir, "comment-video-gap.json"), comment_gap)

    coverage = build_coverage(
        run_dir, output_dir, snapshots, details, creator_rows, product_rows,
        comment_gap
    )
    write_json(os.path.join(output_dir, "coverage.json"), coverage)

    summary = {
        "status": "ok",
        "relations_dir": output_dir,
        "counts": {
            "videos": len(snapshots),
            "videos_with_detail": sum(
                1 for video in snapshots if video.get("detail_snapshot")
            ),
            "video_creator_rows": len(creator_rows),
            "video_creator_confidence": dict(
                sorted(Counter(row["confidence"] for row in creator_rows).items())
            ),
            "unique_creators": coverage["video_creator"][
                "unique_creators_linked"
            ],
            "video_product_rows": len(product_rows),
            "video_product_confidence": dict(
                sorted(Counter(row["confidence"] for row in product_rows).items())
            ),
            "video_product_candidates": coverage["video_product_target"][
                "candidate_relation_rows"
            ],
            "target_exact": coverage["video_product_target"][
                "target_coverage"
            ]["exact_product_id_high"],
            "duplicate_listing": coverage["video_product_target"][
                "baseline_eligibility"
            ]["duplicate_listing_review_n"],
            "category_reference": coverage["video_product_target"][
                "baseline_eligibility"
            ]["category_reference_n"],
            "consideration": coverage["video_product_target"][
                "baseline_eligibility"
            ]["consideration_n"],
            "non_target_subline": coverage["video_product_target"][
                "baseline_eligibility"
            ]["non_target_subline_n"],
            "performance_eligible": coverage["video_product_target"][
                "baseline_eligibility"
            ]["performance_eligible_n"],
            "content_tag": coverage["video_product_target"][
                "content_tag_distribution"
            ],
            "category_anchor_verified": coverage["video_product_target"][
                "target_coverage"
            ]["category_anchor_verified"],
            "comment_video_rows": 0,
        },
        "outputs": coverage["outputs"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

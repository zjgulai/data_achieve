#!/usr/bin/env python3
"""Derive creator/video/snapshot tables and a directional baseline from raw TikHub payloads.

No network calls.  Every output row keeps a path back to the raw file, the
endpoint and the field names used.  Derived categories (creator tier, duration
bucket, caption keyword tag) are labelled ``derived`` and never presented as
provider measurements.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creator_video_collect as cvc  # noqa: E402

TARGET_PRODUCT_ID = cvc.TARGET_PRODUCT_ID
TARGET_PRODUCT_NAME = cvc.TARGET_PRODUCT_NAME

FORMAT_RULES: dict[str, tuple[str, ...]] = {
    "review_testimonial": ("review", "honest", "thoughts", "testimonial", "my experience"),
    "tutorial_howto": ("how to", "how i", "tips", "tutorial", "guide", "wear it", "how to wear"),
    "before_after": ("before", "after", "bump", "progress", "weeks"),
    "vlog_day_in_life": ("day in", "vlog", "week", "routine", "life"),
    "hospital_postpartum": ("hospital", "postpartum", "recovery", "labor", "delivery"),
    "unboxing_haul": ("unbox", "haul", "first impression", "packaging"),
    "pain_relief": ("pain", "relief", "support", "back pain", "sciatica", "round ligament"),
    "sleep_night": ("sleep", "night", "overnight", "bed"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 6) if values else None


def number(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def creator_tier(follower_count: Any) -> str:
    count = number(follower_count)
    if count is None:
        return "unknown"
    if count < 10_000:
        return "nano_lt_10k"
    if count < 100_000:
        return "micro_10k_100k"
    if count < 500_000:
        return "mid_100k_500k"
    return "macro_gte_500k"


def duration_bucket(seconds: Any) -> str:
    value = number(seconds)
    if value is None:
        return "unknown"
    if value < 15:
        return "lt_15s"
    if value < 30:
        return "15_29s"
    if value < 60:
        return "30_59s"
    return "gte_60s"


def format_tags(desc: Any, hashtags: list[dict[str, Any]]) -> list[str]:
    blob = " ".join(
        [str(desc or "")]
        + [str(tag.get("name") or "") for tag in hashtags if isinstance(tag, dict)]
    ).lower()
    tags = [name for name, terms in FORMAT_RULES.items() if any(term in blob for term in terms)]
    return tags or ["untagged"]


def interaction_values(stats: dict[str, Any]) -> tuple[int | None, float | None]:
    plays = number(stats.get("play_count"))
    parts = [
        number(stats.get("like_count")),
        number(stats.get("comment_count")),
        number(stats.get("share_count")),
        number(stats.get("collect_count")),
    ]
    interactions = sum(value for value in parts if value is not None)
    if plays is None or plays <= 0:
        return interactions, None
    return interactions, round(interactions / plays, 6)


def load_call_provenance(log_path: Path) -> dict[str, dict[str, Any]]:
    provenance: dict[str, dict[str, Any]] = {}
    if not log_path.exists():
        return provenance
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw_file = row.get("raw_file")
        if raw_file and row.get("event") == "page_saved" and row.get("endpoint_type"):
            provenance[raw_file] = row
    return provenance


def parse_search_files(
    raw_dir: Path,
    provenance: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return one merged record per video found in any search response."""
    videos: dict[str, dict[str, Any]] = {}
    for path in sorted(raw_dir.glob("video-search-*.json")):
        payload = load_json(path)
        data = payload.get("data") if isinstance(payload, dict) else None
        items = data.get("search_item_list") if isinstance(data, dict) else None
        if not isinstance(items, list):
            continue
        call = provenance.get(str(path)) or {}
        params = call.get("request_params") or {}
        captured_at = call.get("ts") or utc_now()
        for item in items:
            if not isinstance(item, dict):
                continue
            aweme = item.get("aweme_info")
            if not isinstance(aweme, dict) or not aweme:
                continue
            video_id = str(aweme.get("aweme_id") or aweme.get("id") or "")
            if not video_id:
                continue
            author = aweme.get("author") if isinstance(aweme.get("author"), dict) else {}
            stats = aweme.get("statistics") if isinstance(aweme.get("statistics"), dict) else {}
            products = cvc.anchor_products(aweme.get("anchors"))
            products += cvc.anchor_products(aweme.get("anchors_extras"))
            dedup = {product["product_id"]: product for product in products}
            products = list(dedup.values())
            classification = cvc.classify(aweme, products)
            stat_map = {
                "play_count": stats.get("play_count"),
                "like_count": stats.get("digg_count"),
                "comment_count": stats.get("comment_count"),
                "share_count": stats.get("share_count"),
                "collect_count": stats.get("collect_count"),
                "repost_count": stats.get("repost_count"),
                "download_count": stats.get("download_count"),
                "whatsapp_share_count": stats.get("whatsapp_share_count"),
            }
            entry = videos.setdefault(
                video_id,
                {
                    "video_id": video_id,
                    "desc": aweme.get("desc"),
                    "create_time_iso": cvc.epoch_to_iso(aweme.get("create_time")),
                    "author": {
                        "user_id": str(author.get("uid") or ""),
                        "sec_uid": author.get("sec_uid"),
                        "unique_id": author.get("unique_id"),
                        "nickname": author.get("nickname"),
                        "follower_count": author.get("follower_count"),
                        "following_count": author.get("following_count"),
                        "aweme_count": author.get("aweme_count"),
                        "total_favorited": author.get("total_favorited"),
                    },
                    "duration_seconds": (aweme.get("video") or {}).get("duration"),
                    "search_statistics": {},
                    "search_captured_at": captured_at,
                    "search_is_estimated": cvc.find_estimated(aweme),
                    "anchor_products": products,
                    "classification": classification,
                    "search_provenance": [],
                },
            )
            entry["search_provenance"].append(
                {
                    "raw_file": str(path),
                    "request_id": call.get("request_id"),
                    "request_params": params,
                    "captured_at": captured_at,
                }
            )
            for key, value in stat_map.items():
                if value is not None:
                    entry["search_statistics"][key] = value
            entry["search_captured_at"] = captured_at
            if products:
                existing = {product["product_id"] for product in entry["anchor_products"]}
                for product in products:
                    if product["product_id"] not in existing:
                        entry["anchor_products"].append(product)
                entry["classification"] = cvc.classify(aweme, entry["anchor_products"])
    return videos


def parse_detail_files(raw_dir: Path) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for path in sorted(raw_dir.glob("fetch-post-detail-*.json")):
        payload = load_json(path)
        data = payload.get("data") if isinstance(payload, dict) else None
        item_info = data.get("itemInfo") if isinstance(data, dict) else None
        item = item_info.get("itemStruct") if isinstance(item_info, dict) else None
        if not isinstance(item, dict):
            continue
        video_id = str(item.get("id") or path.stem.removeprefix("fetch-post-detail-"))
        detail = cvc.normalize_detail(item, video_id, path)
        video = item.get("video") if isinstance(item.get("video"), dict) else {}
        music = item.get("music") if isinstance(item.get("music"), dict) else {}
        author_stats = item.get("authorStats") if isinstance(item.get("authorStats"), dict) else {}
        text_extra = item.get("textExtra") if isinstance(item.get("textExtra"), list) else []
        hashtags = []
        mentions = []
        for tag in text_extra:
            if not isinstance(tag, dict):
                continue
            if tag.get("type") == 1:
                hashtags.append(
                    {
                        "hashtag_id": tag.get("hashtagId"),
                        "name": tag.get("hashtagName"),
                        "is_commerce": tag.get("isCommerce"),
                    }
                )
            elif tag.get("type") == 0:
                mentions.append(
                    {
                        "user_id": tag.get("userId") or tag.get("user_id"),
                        "sec_uid": tag.get("secUid") or tag.get("sec_uid"),
                    }
                )
        detail.update(
            {
                "creator_id": detail["author"].get("user_id"),
                "duration_ms": (
                    int(video["duration"]) * 1000
                    if isinstance(video.get("duration"), (int, float))
                    else None
                ),
                "cover_url": video.get("cover"),
                "origin_cover_url": video.get("originCover"),
                "video_url": video.get("playAddr"),
                "video_url_expires_at": None,
                "sound_id": music.get("id"),
                "sound_title": music.get("title"),
                "hashtags": hashtags,
                "mentions": mentions,
                "author_stats": {
                    "follower_count": author_stats.get("followerCount"),
                    "following_count": author_stats.get("followingCount"),
                    "friend_count": author_stats.get("friendCount"),
                    "heart_count": author_stats.get("heartCount") or author_stats.get("heart"),
                    "video_count": author_stats.get("videoCount"),
                    "digg_count": author_stats.get("diggCount"),
                },
            }
        )
        details[video_id] = detail
    return details


def parse_profile_files(raw_dir: Path) -> list[dict[str, Any]]:
    profiles = []
    for path in sorted(raw_dir.glob("fetch-user-profile-*.json")):
        payload = load_json(path)
        data = payload.get("data") if isinstance(payload, dict) else None
        user_info = data.get("userInfo") if isinstance(data, dict) else None
        if isinstance(user_info, dict):
            profile = cvc.normalize_profile(user_info, path)
            profile["profile_url"] = (
                f"https://www.tiktok.com/@{profile['unique_id']}"
                if profile.get("unique_id")
                else None
            )
            profile["identity_quality"] = (
                "exact" if profile.get("user_id") and profile.get("sec_uid") else "partial"
            )
            profiles.append(profile)
    return profiles


def merge_creators(
    details: dict[str, dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        keys = [
            profile.get("user_id"),
            profile.get("unique_id"),
            profile.get("sec_uid"),
        ]
        for key in keys:
            if key:
                by_key[str(key)] = profile
    creators: dict[str, dict[str, Any]] = {}
    for detail in details.values():
        author = detail.get("author") or {}
        author_stats = detail.get("author_stats") or {}
        user_id = str(author.get("user_id") or "")
        key = str(author.get("sec_uid") or author.get("unique_id") or user_id)
        if not key:
            continue
        profile = by_key.get(key) or by_key.get(user_id) or by_key.get(str(author.get("unique_id") or ""))
        row = creators.get(key)
        if row is None:
            row = {
                "creator_id": user_id or (profile or {}).get("user_id"),
                "sec_uid": author.get("sec_uid") or (profile or {}).get("sec_uid"),
                "unique_id": author.get("unique_id") or (profile or {}).get("unique_id"),
                "nickname": author.get("nickname") or (profile or {}).get("nickname"),
                "bio": author.get("signature") or (profile or {}).get("signature"),
                "region": (profile or {}).get("region"),
                "language": (profile or {}).get("language"),
                "follower_count": None,
                "following_count": None,
                "friend_count": None,
                "video_count": None,
                "heart_count": None,
                "digg_count": None,
                "is_verified": None,
                "is_private": None,
                "is_seller": None,
                "commerce_user_info": None,
                "profile_url": (profile or {}).get("profile_url"),
                "identity_quality": (profile or {}).get("identity_quality") or "partial",
                "source_endpoints": [cvc.DETAIL_PATH],
                "raw_files": [detail.get("raw_file")],
                "profile_raw_file": (profile or {}).get("raw_file"),
                "derived_creator_tier": None,
            }
            creators[key] = row
        else:
            if detail.get("raw_file") and detail["raw_file"] not in row["raw_files"]:
                row["raw_files"].append(detail["raw_file"])
            if profile and cvc.PROFILE_PATH not in row["source_endpoints"]:
                row["source_endpoints"].append(cvc.PROFILE_PATH)
        if profile:
            row["follower_count"] = profile.get("follower_count")
            row["following_count"] = profile.get("following_count")
            row["friend_count"] = profile.get("friend_count")
            row["video_count"] = profile.get("video_count")
            row["heart_count"] = profile.get("heart_count")
            row["digg_count"] = profile.get("digg_count")
            row["is_verified"] = profile.get("verified")
            row["is_private"] = profile.get("private_account")
            row["is_seller"] = profile.get("tt_seller")
            row["commerce_user_info"] = profile.get("commerce_user_info")
            row["region"] = profile.get("region") or row["region"]
            row["language"] = profile.get("language") or row["language"]
            row["profile_raw_file"] = profile.get("raw_file")
        # Author stats are a fallback only; they never overwrite a profile value.
        for field, source_key in (
            ("follower_count", "follower_count"),
            ("following_count", "following_count"),
            ("friend_count", "friend_count"),
            ("video_count", "video_count"),
            ("heart_count", "heart_count"),
            ("digg_count", "digg_count"),
        ):
            if row.get(field) is None and author_stats.get(source_key) is not None:
                row[field] = author_stats[source_key]
        row["derived_creator_tier"] = creator_tier(row.get("follower_count"))
    return sorted(creators.values(), key=lambda row: str(row.get("unique_id") or row.get("creator_id")))


def reconcile_associations(
    videos: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> None:
    """Merge anchor products seen in search and detail payloads.

    Detail is authoritative for the current anchor set, but search may have
    seen an anchor that the detail response omitted (or vice versa).  The
    union keeps every exact product ID that either endpoint returned.
    """
    for video_id, detail in details.items():
        detail_products = detail.get("anchor_products") or []
        entry = videos.get(video_id)
        if entry is None:
            entry = {
                "video_id": video_id,
                "desc": detail.get("desc"),
                "create_time_iso": detail.get("create_time_iso"),
                "author": {
                    "user_id": detail.get("author", {}).get("user_id"),
                    "sec_uid": detail.get("author", {}).get("sec_uid"),
                    "unique_id": detail.get("author", {}).get("unique_id"),
                    "nickname": detail.get("author", {}).get("nickname"),
                    "follower_count": detail.get("author_stats", {}).get("follower_count"),
                },
                "duration_seconds": detail.get("duration_seconds"),
                "search_statistics": {},
                "search_captured_at": None,
                "search_is_estimated": None,
                "anchor_products": detail_products,
                "classification": cvc.classify(
                    {
                        "desc": detail.get("desc"),
                        "text_extra": [
                            {"hashtag_name": tag.get("name")}
                            for tag in (detail.get("hashtags") or [])
                        ],
                    },
                    detail_products,
                ),
                "search_provenance": [],
            }
            videos[video_id] = entry
            continue
        merged = {product["product_id"]: product for product in entry.get("anchor_products") or []}
        for product in detail_products:
            merged.setdefault(product["product_id"], product)
        if len(merged) != len(entry.get("anchor_products") or []):
            entry["anchor_products"] = list(merged.values())
            entry["classification"] = cvc.classify(
                {
                    "desc": entry.get("desc") or detail.get("desc"),
                    "text_extra": [
                        {"hashtag_name": tag.get("name")}
                        for tag in (detail.get("hashtags") or [])
                    ],
                },
                entry["anchor_products"],
            )


def build_video_products(
    videos: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for video_id, entry in videos.items():
        detail = details.get(video_id) or {}
        products = entry.get("anchor_products") or detail.get("anchor_products") or []
        for product in products:
            pid = str(product.get("product_id"))
            title = str(product.get("title") or "")
            lower_title = title.lower()
            is_target = pid == TARGET_PRODUCT_ID
            is_category = is_target or any(
                term in lower_title for term in cvc.ANCHOR_CATEGORY_TERMS
            )
            rows.append(
                {
                    "video_id": video_id,
                    "product_id": pid,
                    "product_title": product.get("title") or None,
                    "association_method": "anchor_product_id",
                    "confidence": "exact_id",
                    "association_scope": (
                        "target_product"
                        if is_target
                        else ("belly_band_category" if is_category else "unrelated_product")
                    ),
                    "video_level_association_tier": entry["classification"]["association_tier"],
                    "baseline_eligible_product": is_target,
                    "baseline_eligible_category": is_category,
                    "evidence": {
                        "search_endpoint": cvc.SEARCH_PATH,
                        "search_provenance": entry.get("search_provenance"),
                        "detail_endpoint": cvc.DETAIL_PATH if detail else None,
                        "detail_raw_file": detail.get("raw_file"),
                        "field_path": "aweme.anchors[].extra[].product_id",
                    },
                }
            )
    return rows


def build_product_index(
    videos: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Derived product video index with explicit category scope."""
    target = [
        entry
        for entry in videos.values()
        if TARGET_PRODUCT_ID in entry["classification"]["anchor_product_ids"]
    ]
    category_other = [
        entry
        for entry in videos.values()
        if entry["classification"]["association_tier"] == "exact_other_product_category"
    ]
    unrelated = [
        entry
        for entry in videos.values()
        if entry["classification"]["association_tier"] == "exact_other_product_unrelated"
    ]
    target.sort(key=lambda entry: -int((entry.get("search_statistics") or {}).get("play_count") or 0))

    def row(entry: dict[str, Any], *, eligible_product: bool, eligible_category: bool) -> dict[str, Any]:
        detail = details.get(entry["video_id"]) or {}
        return {
            "video_id": entry["video_id"],
            "desc": entry.get("desc"),
            "create_time_iso": entry.get("create_time_iso"),
            "author": entry.get("author"),
            "anchor_product_ids": entry["classification"]["anchor_product_ids"],
            "anchor_products": entry.get("anchor_products"),
            "association": {
                "method": "anchor_product_id",
                "confidence": "exact_id",
                "product_id": TARGET_PRODUCT_ID if eligible_product else None,
                "baseline_eligible_product": eligible_product,
                "baseline_eligible_category": eligible_category,
            },
            "search_statistics": entry.get("search_statistics"),
            "detail_statistics": detail.get("statistics"),
            "evidence": {
                "search_endpoint": cvc.SEARCH_PATH,
                "search_provenance": entry.get("search_provenance"),
                "detail_raw_file": detail.get("raw_file"),
            },
        }

    return {
        "_meta": {
            "derived": True,
            "not_a_provider_endpoint_response": True,
            "product_id": TARGET_PRODUCT_ID,
            "product_name": TARGET_PRODUCT_NAME,
            "generated_at": utc_now(),
            "association_basis": "anchor_product_id from TikTok aweme anchors",
            "confidence": "exact_id",
            "is_exhaustive": False,
            "coverage_note": (
                "TikHub has no product_id-only video-list endpoint. "
                "get_product_related_videos and get_video_associated_product_list "
                "both return provider code 98001002 no login without "
                "TIKHUB_TIKTOK_CREATOR_COOKIE. This file is the anchor-verified "
                "subset found by keyword search, not a complete product video list."
            ),
            "pagination_note": (
                "fetch_video_search_result returned has_more=1 but cursor=20 "
                "returned the same 12 items as cursor=0; pagination is not usable. "
                "Coverage was widened with multiple keywords and sort_type values."
            ),
            "video_count": len(target),
            "other_category_anchor_video_count": len(category_other),
            "unrelated_anchor_video_count": len(unrelated),
            "same_series_note": (
                "Several other product IDs carry similar Momcozy YB001-series "
                "titles. They are kept as separate IDs and are not merged into the "
                "target-product baseline."
            ),
        },
        "videos": [row(entry, eligible_product=True, eligible_category=True) for entry in target],
        "other_category_anchor_videos": [
            row(entry, eligible_product=False, eligible_category=True) for entry in category_other
        ],
        "unrelated_anchor_videos": [
            row(entry, eligible_product=False, eligible_category=False) for entry in unrelated
        ],
    }


def build_snapshots(
    videos: dict[str, dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for video_id, entry in videos.items():
        detail = details.get(video_id) or {}
        search_stats = entry.get("search_statistics") or {}
        detail_stats = detail.get("statistics") or {}
        interactions, rate = interaction_values(detail_stats)
        row = {
            "video_id": video_id,
            "creator_id": detail.get("creator_id"),
            "desc": entry.get("desc") or detail.get("desc"),
            "create_time_iso": entry.get("create_time_iso") or detail.get("create_time_iso"),
            "association_tier": entry["classification"]["association_tier"],
            "anchor_product_ids": entry["classification"]["anchor_product_ids"],
            "search_snapshot": {
                "source_endpoint": cvc.SEARCH_PATH,
                "captured_at": entry.get("search_captured_at"),
                "statistics": search_stats,
                "is_estimated": entry.get("search_is_estimated"),
                "provenance": entry.get("search_provenance"),
            },
            "detail_snapshot": (
                {
                    "source_endpoint": cvc.DETAIL_PATH,
                    "captured_at": detail.get("captured_at"),
                    "statistics": detail_stats,
                    "is_estimated": detail.get("is_estimated"),
                    "raw_file": detail.get("raw_file"),
                }
                if detail
                else None
            ),
            "snapshot_source": "fetch_post_detail" if detail else "search_only",
            "is_estimated": (
                detail.get("is_estimated")
                if detail
                else entry.get("search_is_estimated")
            ),
            "is_estimated_field_present": (
                detail.get("is_estimated_field_present", False)
                if detail
                else entry.get("search_is_estimated") is not None
            ),
            "derived_engagement": (
                {
                    "interactions": interactions,
                    "play_count": number(detail_stats.get("play_count")),
                    "interaction_rate": rate,
                    "derived": True,
                    "formula": "(like+comment+share+collect)/play_count",
                }
                if detail and rate is not None
                else None
            ),
        }
        delta = {}
        for key, value in detail_stats.items():
            base = search_stats.get(key)
            if isinstance(value, (int, float)) and isinstance(base, (int, float)):
                delta[key] = value - base
        row["delta_detail_minus_search"] = delta
        rows.append(row)
    return rows


def group_stats(
    rows: list[dict[str, Any]],
    key_fn,
    cohort_median: float | None,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if isinstance(key, list):
            for value in key:
                groups[value].append(row)
        else:
            groups[key].append(row)
    output = []
    for key, members in sorted(groups.items()):
        rates = [
            member["derived_engagement"]["interaction_rate"]
            for member in members
            if member.get("derived_engagement")
            and member["derived_engagement"].get("interaction_rate") is not None
        ]
        plays = [
            member["derived_engagement"]["play_count"]
            for member in members
            if member.get("derived_engagement")
            and member["derived_engagement"].get("play_count") is not None
        ]
        group_median = median(rates)
        output.append(
            {
                "group": key,
                "n": len(members),
                "n_with_interaction_rate": len(rates),
                "median_play_count": median(plays),
                "median_interaction_rate": group_median,
                "mean_interaction_rate": mean(rates),
                "min_interaction_rate": min(rates) if rates else None,
                "max_interaction_rate": max(rates) if rates else None,
                "lift_vs_cohort_median": (
                    round(group_median / cohort_median - 1, 6)
                    if group_median is not None and cohort_median
                    else None
                ),
                "claim_status": "insufficient_n" if len(rates) < 5 else "directional_only",
                "video_ids": [member["video_id"] for member in members],
                "derived": True,
            }
        )
    return output


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "_detail"}


def baseline_cohort(
    name: str,
    rows: list[dict[str, Any]],
    creators_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    usable = [
        row
        for row in rows
        if row.get("derived_engagement")
        and row["derived_engagement"].get("interaction_rate") is not None
        and row["derived_engagement"].get("play_count")
    ]
    rates = [row["derived_engagement"]["interaction_rate"] for row in usable]
    cohort_median = median(rates)
    enriched = []
    for row in usable:
        creator = creators_by_id.get(str(row.get("creator_id") or "")) or {}
        enriched.append(
            {
                **row,
                "creator_tier": creator.get("derived_creator_tier") or "unknown",
                "follower_count": creator.get("follower_count"),
                "duration_bucket": duration_bucket(
                    (row.get("detail_snapshot") or {}).get("statistics", {}).get("duration_seconds")
                    or row.get("duration_seconds")
                ),
                "format_tags": format_tags(
                    row.get("desc"),
                    [
                        {"name": tag}
                        for tag in (row.get("hashtags") or [])
                        if isinstance(tag, str)
                    ],
                ),
            }
        )
    # Recompute duration/format from the detail record because snapshots do not
    # carry duration or hashtags.
    for row, original in zip(enriched, usable):
        detail = row.get("_detail") or {}
        if detail:
            row["duration_bucket"] = duration_bucket(detail.get("duration_seconds"))
            row["format_tags"] = format_tags(detail.get("desc"), detail.get("hashtags") or [])
    return {
        "cohort": name,
        "n_videos": len(usable),
        "median_interaction_rate": cohort_median,
        "mean_interaction_rate": mean(rates),
        "median_play_count": median(
            [row["derived_engagement"]["play_count"] for row in usable]
        ),
        "by_creator_tier": group_stats(enriched, lambda row: row["creator_tier"], cohort_median),
        "by_duration_bucket": group_stats(enriched, lambda row: row["duration_bucket"], cohort_median),
        "by_format_tag": group_stats(enriched, lambda row: row["format_tags"], cohort_median),
        "top_by_play_count": [
            clean_row(row)
            for row in sorted(
                enriched,
                key=lambda row: -(row["derived_engagement"].get("play_count") or 0),
            )[:15]
        ],
        "top_by_interaction_rate": [
            clean_row(row)
            for row in sorted(
                enriched,
                key=lambda row: -(row["derived_engagement"].get("interaction_rate") or 0),
            )[:15]
        ],
        "derived": True,
    }


def build_baseline(
    snapshots: list[dict[str, Any]],
    details: dict[str, dict[str, Any]],
    creators: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshots = [dict(row) for row in snapshots]
    creators_by_id = {str(creator.get("creator_id")): creator for creator in creators if creator.get("creator_id")}
    for row in snapshots:
        row["_detail"] = details.get(row["video_id"]) or {}
        detail = row["_detail"]
        row["duration_seconds"] = detail.get("duration_seconds")
        row["hashtags"] = detail.get("hashtags")
        row["is_ad"] = detail.get("is_ad")
    product_rows = [
        row for row in snapshots if row.get("association_tier") == "exact_target_product"
    ]
    category_rows = [
        row
        for row in snapshots
        if row.get("association_tier")
        in {"exact_target_product", "exact_other_product_category"}
    ]
    organic_rows = [row for row in category_rows if row.get("is_ad") is not True]
    result = {
        "schema_version": "voc_creator_video_baseline_v1",
        "generated_at": utc_now(),
        "product_id": TARGET_PRODUCT_ID,
        "product_name": TARGET_PRODUCT_NAME,
        "metric_definition": {
            "interaction_rate": "(like_count + comment_count + share_count + collect_count) / play_count",
            "play_count_source": "fetch_post_detail.stats.playCount",
            "interaction_fields_source": "fetch_post_detail.stats.{diggCount,commentCount,shareCount,collectCount}",
            "derived": True,
            "not_available": [
                "view-through rate",
                "completion rate",
                "GMV / orders / conversion",
                "audience demographics",
            ],
        },
        "cohorts": {
            "product_exact_baseline": baseline_cohort(
                "product_exact_baseline", product_rows, creators_by_id
            ),
            "category_anchor_verified_baseline": baseline_cohort(
                "category_anchor_verified_baseline", category_rows, creators_by_id
            ),
            "category_anchor_verified_organic_only": baseline_cohort(
                "category_anchor_verified_organic_only", organic_rows, creators_by_id
            ),
        },
        "creator_table": [],
        "caveats": [
            "Keyword search is a non-probability sample, not a census of the category.",
            "Search pagination is broken: cursor=20 repeated page 1, so coverage is 12 queries x one page.",
            "The product-specific video list is blocked without TIKHUB_TIKTOK_CREATOR_COOKIE; the exact-target cohort is the anchor-verified subset only.",
            "The category baseline includes the target product plus other anchor products whose titles match belly-band terms; unrelated anchored products are excluded.",
            "Multiple product IDs share the same Momcozy YB001 / CozySupport Ergonest title; target-product coverage may be undercounted because IDs are not merged.",
            "Content-format tags are derived from caption and hashtag keywords, not human coding.",
            "Creator tiers are derived from follower_count; missing profile data stays unknown.",
            "Groups with fewer than 5 videos with an interaction rate are marked insufficient_n.",
            "is_ad is the provider field; it is not the same as paid sponsorship.",
            "Do not generalize these medians to the whole category or compare them with review-layer metrics.",
        ],
    }
    creator_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in category_rows:
        if row.get("derived_engagement"):
            creator_groups[str(row.get("creator_id") or "")].append(row)
    creator_table = []
    for creator_id, rows in creator_groups.items():
        creator = creators_by_id.get(creator_id) or {}
        rates = [
            row["derived_engagement"]["interaction_rate"]
            for row in rows
            if row["derived_engagement"].get("interaction_rate") is not None
        ]
        creator_table.append(
            {
                "creator_id": creator_id,
                "unique_id": creator.get("unique_id"),
                "nickname": creator.get("nickname"),
                "follower_count": creator.get("follower_count"),
                "creator_tier": creator.get("derived_creator_tier"),
                "n_videos": len(rows),
                "median_interaction_rate": median(rates),
                "total_play_count": sum(
                    row["derived_engagement"].get("play_count") or 0 for row in rows
                ),
                "video_ids": [row["video_id"] for row in rows],
                "claim_status": "insufficient_n" if len(rates) < 5 else "directional_only",
                "derived": True,
            }
        )
    result["creator_table"] = sorted(
        creator_table,
        key=lambda row: -(row["median_interaction_rate"] or 0),
    )
    return result


def audit_raw_calls(
    raw_dir: Path,
    provenance: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Re-check every saved raw payload for provider-level success.

    The live ledger classifies by HTTP envelope only.  TikTok sometimes
    returns HTTP 200 with a top-level ``detail.code=400``; that is a failed
    call, not a success, and the provider says it is not charged.
    """
    derived_names = {
        "video-details.json",
        "creators.json",
        "video-snapshots.json",
        "video-products.json",
        "product-videos-page-1.json",
    }
    rows = []
    for path in sorted(raw_dir.glob("*.json")):
        if path.name in derived_names:
            continue
        try:
            payload = load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        call = provenance.get(str(path)) or {}
        endpoint_type = call.get("endpoint_type") or path.name
        status = "success"
        code = None
        message = None
        if "video-search-" in path.name:
            data = payload.get("data") if isinstance(payload, dict) else None
            if not (isinstance(data, dict) and isinstance(data.get("search_item_list"), list)):
                status = "provider_error"
                code = (payload.get("code") if isinstance(payload, dict) else None)
        elif "fetch-post-detail-" in path.name:
            data = payload.get("data") if isinstance(payload, dict) else None
            item_info = data.get("itemInfo") if isinstance(data, dict) else None
            item = item_info.get("itemStruct") if isinstance(item_info, dict) else None
            if not isinstance(item, dict):
                status = "provider_error"
                detail = payload.get("detail") if isinstance(payload, dict) else None
                if isinstance(detail, dict):
                    code = detail.get("code")
                    message = detail.get("message")
        elif "fetch-user-profile-" in path.name:
            data = payload.get("data") if isinstance(payload, dict) else None
            if not (isinstance(data, dict) and isinstance(data.get("userInfo"), dict)):
                status = "provider_error"
                code = (
                    data.get("statusCode")
                    if isinstance(data, dict)
                    else (payload.get("code") if isinstance(payload, dict) else None)
                )
                message = data.get("statusMsg") if isinstance(data, dict) else None
        elif "no-cookie-probe" in path.name:
            data = payload.get("data") if isinstance(payload, dict) else None
            inner = data.get("code") if isinstance(data, dict) else None
            status = "provider_error"
            code = inner
            message = data.get("message") if isinstance(data, dict) else None
        rows.append(
            {
                "raw_file": str(path),
                "endpoint_type": endpoint_type,
                "status": status,
                "provider_code": code,
                "provider_message": message,
                "charged_note": (
                    "provider says not charged"
                    if isinstance(message, str) and "won't be charged" in message
                    else None
                ),
            }
        )
    failures = [row for row in rows if row["status"] != "success"]
    return {
        "audited_files": len(rows),
        "audited_success": len(rows) - len(failures),
        "audited_failed": len(failures),
        "failures": failures,
        "note": "raw payload shape audit; HTTP 200 with provider error is counted as failed",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="creator_video_derive")
    parser.add_argument("--out", default=str(cvc.DEFAULT_OUT))
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    raw_dir = out_dir / "raw"

    provenance = load_call_provenance(out_dir / "collect-log.jsonl")
    videos = parse_search_files(raw_dir, provenance)
    details = parse_detail_files(raw_dir)
    profiles = parse_profile_files(raw_dir)
    creators = merge_creators(details, profiles)
    reconcile_associations(videos, details)
    for video_id, detail in details.items():
        entry = videos.get(video_id) or {}
        classification = entry.get("classification") or {}
        detail["association_tier"] = classification.get("association_tier")
        detail["anchor_product_ids"] = classification.get("anchor_product_ids")
        detail["baseline_eligible_product"] = classification.get("baseline_eligible_product")
        detail["baseline_eligible_category"] = classification.get("baseline_eligible_category")
        detail["source_search_provenance"] = entry.get("search_provenance")
    snapshots = build_snapshots(videos, details)
    video_products = build_video_products(videos, details)
    product_index = build_product_index(videos, details)
    baseline = build_baseline(snapshots, details, creators)
    audit = audit_raw_calls(raw_dir, provenance)

    write_json(
        raw_dir / "video-details.json",
        {
            "_meta": {
                "derived": True,
                "source_endpoint": cvc.DETAIL_PATH,
                "generated_at": utc_now(),
                "note": "normalized and enriched from fetch-post-detail-*.json; raw payloads are kept per video",
            },
            "videos": sorted(details.values(), key=lambda row: row["video_id"]),
        },
    )
    write_json(
        raw_dir / "creators.json",
        {
            "_meta": {
                "derived": True,
                "source_endpoint": f"{cvc.PROFILE_PATH} + {cvc.DETAIL_PATH}.authorStats fallback",
                "generated_at": utc_now(),
                "note": "profile values take precedence; authorStats fills gaps; null stays null",
            },
            "creators": creators,
        },
    )
    write_json(
        raw_dir / "video-snapshots.json",
        {
            "_meta": {
                "derived": True,
                "generated_at": utc_now(),
                "note": "search and detail statistics captured at different times; delta is detail minus search",
                "is_estimated": None,
            },
            "videos": snapshots,
        },
    )
    write_json(
        raw_dir / "video-products.json",
        {
            "_meta": {
                "derived": True,
                "generated_at": utc_now(),
                "association_basis": "TikTok aweme anchors[].extra[].product_id",
                "note": "one row per video x anchor product; exact_id confidence; category scope is title-derived",
            },
            "video_products": video_products,
        },
    )
    write_json(raw_dir / "product-videos-page-1.json", product_index)
    write_json(out_dir / "baseline.json", baseline)

    summary_path = out_dir / "collect-summary.json"
    if summary_path.exists():
        summary = load_json(summary_path)
        summary.setdefault("files", {}).update(
            {
                "video_details": str(raw_dir / "video-details.json"),
                "creators": str(raw_dir / "creators.json"),
                "video_snapshots": str(raw_dir / "video-snapshots.json"),
                "video_products": str(raw_dir / "video-products.json"),
                "baseline": str(out_dir / "baseline.json"),
            }
        )
        summary["derived_outputs"] = {
            "video_products_rows": len(video_products),
            "product_index_target_videos": len(product_index["videos"]),
            "product_index_category_other_videos": len(product_index["other_category_anchor_videos"]),
            "product_index_unrelated_videos": len(product_index["unrelated_anchor_videos"]),
            "creators_rows": len(creators),
            "video_snapshot_rows": len(snapshots),
            "baseline_cohorts": {
                name: cohort["n_videos"]
                for name, cohort in baseline["cohorts"].items()
            },
            "note": "baseline is directional only; see baseline.json caveats",
        }
        summary["coverage"] = {
            "search_videos": len(videos),
            "relevant_videos": sum(
                1
                for entry in videos.values()
                if entry.get("classification", {}).get("association_tier") != "none"
            ),
            "detail_call_cap": cvc.MAX_DETAIL_CALLS,
            "videos_with_detail": len(details),
            "videos_without_detail": max(0, len(videos) - len(details)),
            "detail_selection_rule": "exact anchor matches first, then text matches by search play_count",
            "profile_call_cap": cvc.MAX_PROFILE_CALLS,
            "profiles_collected": len(profiles),
            "note": "detail and profile caps are per-run limits, not provider limits",
        }
        summary["calls"]["audited_success"] = audit["audited_success"]
        summary["calls"]["audited_failed"] = audit["audited_failed"]
        summary["calls"]["audit_note"] = audit["note"]
        summary["calls"]["audited_failures"] = audit["failures"]
        pid_video_counts: dict[str, int] = {}
        pid_videos: dict[str, set[str]] = defaultdict(set)
        for row in video_products:
            pid_videos[row["product_id"]].add(row["video_id"])
        pid_video_counts = {
            pid: len(video_ids) for pid, video_ids in pid_videos.items()
        }
        pid_video_counts = dict(
            sorted(pid_video_counts.items(), key=lambda item: -item[1])
        )
        same_series_ids = sorted(
            {
                row["product_id"]
                for row in video_products
                if row["product_id"] != TARGET_PRODUCT_ID
                and row.get("product_title")
                and (
                    "momcozy pregnancy belly band yb001" in row["product_title"].lower()
                    or "momcozy pregnancy belly belt yb001" in row["product_title"].lower()
                    or "cozysupport ergonest" in row["product_title"].lower()
                )
            }
        )
        summary["product_id_ambiguity"] = {
            "target_product_id": TARGET_PRODUCT_ID,
            "same_series_other_product_ids": same_series_ids,
            "anchor_video_counts_by_product_id": pid_video_counts,
            "anchor_video_counts_note": "unique videos per product ID, not row counts",
            "note": (
                "Several product IDs carry similar Momcozy YB001-series titles. "
                "They are kept as separate IDs and are not merged into the "
                "target-product baseline."
            ),
        }
        summary["association_tiers"] = {
            "exact_target_product": "anchor product_id == target; product and category baseline eligible",
            "exact_other_product_category": "anchor product_id is not target but the anchor title matches the belly-band category; category baseline eligible",
            "exact_other_product_unrelated": "anchor product_id is not target and the title is not belly-band; excluded from both baselines",
            "text_match_brand_and_category": "no anchor; brand and category words in caption/hashtags; excluded from baselines",
            "text_match_category_only": "no anchor; category words only; excluded from baselines",
            "text_match_brand_only": "no anchor; brand words only; excluded from baselines",
            "none": "no brand, category or anchor match; excluded",
        }
        existing_gaps = summary.setdefault("evidence_gaps", [])
        duplicate_gap = (
            "duplicate product listings: multiple product IDs share the same "
            "Momcozy YB001 / CozySupport Ergonest title; target-product video "
            "coverage may be undercounted because IDs are not merged"
        )
        if duplicate_gap not in existing_gaps:
            existing_gaps.append(duplicate_gap)
        summary["counts"].update(
            {
                "unique_videos_seen": len(videos),
                "videos_with_search_snapshot": len(snapshots),
                "videos_with_detail_snapshot": sum(
                    1 for row in snapshots if row.get("snapshot_source") == "fetch_post_detail"
                ),
                "videos_with_detail": len(details),
                "unique_creators_from_details": len(
                    {
                        str(detail.get("creator_id"))
                        for detail in details.values()
                        if detail.get("creator_id")
                    }
                ),
                "creators_with_profile": len(profiles),
                "creators_rows": len(creators),
                "unique_authors_in_search_sample": len(
                    {
                        str(
                            entry["author"].get("unique_id")
                            or entry["author"].get("sec_uid")
                            or entry["author"].get("user_id")
                        )
                        for entry in videos.values()
                        if entry.get("author")
                        and (
                            entry["author"].get("unique_id")
                            or entry["author"].get("sec_uid")
                            or entry["author"].get("user_id")
                        )
                    }
                ),
                "anchor_verified_videos": sum(
                    1
                    for entry in videos.values()
                    if entry.get("classification", {}).get("association_tier")
                    in {"exact_target_product", "exact_other_product_category"}
                ),
                "exact_other_product_category_videos": sum(
                    1
                    for entry in videos.values()
                    if entry.get("classification", {}).get("association_tier")
                    == "exact_other_product_category"
                ),
                "exact_other_product_unrelated_videos": sum(
                    1
                    for entry in videos.values()
                    if entry.get("classification", {}).get("association_tier")
                    == "exact_other_product_unrelated"
                ),
                "anchor_verified_any_product_videos": sum(
                    1
                    for entry in videos.values()
                    if entry.get("classification", {}).get("association_tier")
                    in {
                        "exact_target_product",
                        "exact_other_product_category",
                        "exact_other_product_unrelated",
                    }
                ),
                "anchor_verified_authors": len(
                    {
                        str(
                            entry["author"].get("unique_id")
                            or entry["author"].get("sec_uid")
                            or entry["author"].get("user_id")
                        )
                        for entry in videos.values()
                        if entry.get("classification", {}).get("association_tier")
                        in {"exact_target_product", "exact_other_product_category"}
                        and entry.get("author")
                        and (
                            entry["author"].get("unique_id")
                            or entry["author"].get("sec_uid")
                            or entry["author"].get("user_id")
                        )
                    }
                ),
                "videos_with_derived_engagement": sum(
                    1 for row in snapshots if row.get("derived_engagement") is not None
                ),
            }
        )
        audited_assumed = round(
            max(0.0, float(summary.get("cost", {}).get("collection_assumed_usd") or 0) - 0.001),
            6,
        )
        summary["cost"]["audited_assumed_usd"] = audited_assumed
        summary["cost"]["audited_note"] = (
            "one detail call returned detail.code=400 and the provider says it was not charged; "
            "audited_assumed_usd subtracts that one 0.001 assumption"
        )
        write_json(summary_path, summary)

    print(
        json.dumps(
            {
                "videos_from_search": len(videos),
                "details": len(details),
                "creators": len(creators),
                "profiles": len(profiles),
                "video_products": len(video_products),
                "snapshots": len(snapshots),
                "audited_success": audit["audited_success"],
                "audited_failed": audit["audited_failed"],
                "baseline_cohorts": {
                    name: cohort["n_videos"]
                    for name, cohort in baseline["cohorts"].items()
                },
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

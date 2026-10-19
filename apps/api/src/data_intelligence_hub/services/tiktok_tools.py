"""Eight TikTok content tools for Agents and the workbench.

Each tool maps a stable input contract to one or more TikHub/Apify endpoints,
then returns the normalized raw records. The underlying collection path also
projects records into the 12 canonical tables.
"""

from __future__ import annotations

import os
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.services.raw_record_service import get_raw_records

TOOL_IDS = (
    "tiktok_trend_rank",
    "tiktok_hashtag_videos",
    "tiktok_video_search",
    "tiktok_video_detail",
    "tiktok_video_comments",
    "tiktok_creator_profile",
    "tiktok_creator_search",
    "tiktok_transcript",
    "tiktok_product_search",
    "tiktok_product_detail",
    "tiktok_product_reviews",
    "tiktok_creator_commerce",
    "tiktok_video_products",
    "tiktok_creator_showcase",
    "tiktok_ads_top",
    "tiktok_ads_detail",
)

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "tiktok_trend_rank": {
        "label": "TikTok 趋势榜",
        "description": "拉取 Creative Center 热门话题榜。",
        "inputs": ["project_id", "country_code?", "period?", "limit?"],
    },
    "tiktok_hashtag_videos": {
        "label": "TikTok 话题视频",
        "description": "按话题名、App ch_id 或 Web challengeID 拉视频。",
        "inputs": ["project_id", "hashtag?", "ch_id?", "challenge_id?", "limit?"],
    },
    "tiktok_video_search": {
        "label": "TikTok 关键词视频搜索",
        "description": "按关键词搜索公开视频。",
        "inputs": ["project_id", "query", "limit?"],
    },
    "tiktok_video_detail": {
        "label": "TikTok 单视频详情",
        "description": "按视频 ID 或 URL 获取详情。",
        "inputs": ["project_id", "video_id?", "video_url?"],
    },
    "tiktok_video_comments": {
        "label": "TikTok 视频评论",
        "description": "获取评论，可选回复树。",
        "inputs": ["project_id", "video_id", "video_url?", "limit?", "include_replies?"],
    },
    "tiktok_creator_profile": {
        "label": "TikTok 达人资料",
        "description": "获取达人资料，可选作品与粉丝。",
        "inputs": [
            "project_id",
            "handle?",
            "sec_uid?",
            "include_videos?",
            "video_limit?",
            "include_fans?",
        ],
    },
    "tiktok_creator_search": {
        "label": "TikTok 达人搜索",
        "description": "从关键词视频结果中提取达人候选。",
        "inputs": ["project_id", "query", "limit?"],
    },
    "tiktok_transcript": {
        "label": "TikTok 字幕",
        "description": "按视频 URL 提取字幕或转写。",
        "inputs": ["project_id", "video_urls", "limit?"],
    },
    "tiktok_product_search": {
        "label": "TikTok Shop 商品搜索",
        "description": "按关键词搜索 Shop 商品，返回价格、销量、评分与店铺。",
        "inputs": ["project_id", "query", "region?", "limit?"],
    },
    "tiktok_product_detail": {
        "label": "TikTok Shop 商品详情",
        "description": "按商品 ID 或 URL 获取商品详情、GMV、销量与 SKU。",
        "inputs": ["project_id", "product_id?", "product_url?", "region?"],
    },
    "tiktok_product_reviews": {
        "label": "TikTok Shop 商品评论",
        "description": "按商品 ID 获取评论、评分与图片。",
        "inputs": ["project_id", "product_id", "region?", "limit?"],
    },
    "tiktok_creator_commerce": {
        "label": "TikTok 达人带货",
        "description": "按达人 handle 获取带货主页与商业指标。",
        "inputs": ["project_id", "handle", "region?"],
    },
    "tiktok_video_products": {
        "label": "TikTok 视频关联商品",
        "description": "按视频 ID 获取关联商品；需要创作者 Cookie。",
        "inputs": ["project_id", "video_id"],
    },
    "tiktok_creator_showcase": {
        "label": "TikTok 达人橱窗商品",
        "description": "获取达人橱窗商品；需要创作者 Cookie。",
        "inputs": ["project_id", "offset?", "limit?"],
    },
    "tiktok_ads_top": {
        "label": "TikTok 热门广告",
        "description": "获取 TikTok 热门广告素材与互动指标。",
        "inputs": ["project_id", "query?", "period?", "limit?"],
    },
    "tiktok_ads_detail": {
        "label": "TikTok 广告详情",
        "description": "按广告 ID 获取广告主、落地页与素材详情。",
        "inputs": ["project_id", "ad_id"],
    },
}

_VIDEO_ID_RE = re.compile(r"/video/(\d+)")


_CURRENT_TOOL_CALL: ContextVar[dict[str, Any] | None] = ContextVar(
    "tiktok_current_tool_call", default=None
)


def _summarize_params(params: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if any(secret in key.lower() for secret in ("token", "secret", "password", "key")):
            continue
        if isinstance(value, str) and len(value) > 200:
            summary[key] = value[:200] + "…"
        elif isinstance(value, list) and len(value) > 10:
            summary[key] = value[:10]
        else:
            summary[key] = value
    return summary


@dataclass
class ToolResult:
    tool_id: str
    status: str
    records: list[dict[str, Any]] = field(default_factory=list)
    records_count: int = 0
    runs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_call_id": self.tool_call_id,
            "status": self.status,
            "records": self.records,
            "records_count": self.records_count,
            "runs": self.runs,
            "errors": self.errors,
            "metadata": self.metadata,
        }


_ACTOR_TO_ENDPOINT = {
    "pratikdani/tiktok-shop-search-scraper": "apify_tiktok_shop_search_scraper",
    "pratikdani/tiktok-shop-scraper": "apify_tiktok_shop_product_detail",
    "clockworks/tiktok-shop-scraper": "apify_tiktok_shop_scraper",
    "lemur/tiktok-shop-creators": "apify_tiktok_shop_creators",
    "clockworks/tiktok-transcript-extractor": "apify_tiktok_transcript_extractor",
}

_TOOL_ROLE_BY_ENDPOINT = {
    "tikhub_tiktok_user_profile_web": "profile",
    "tikhub_tiktok_user_fans_web": "fan",
    "tikhub_tiktok_user_posts_web": "video",
    "tikhub_tiktok_search_web": "video",
    "tikhub_tiktok_tag_posts_web": "video",
    "tikhub_tiktok_video_detail": "video",
    "tikhub_tiktok_comments_app": "comment",
    "tikhub_tiktok_comment_replies_app": "comment",
    "apify_tiktok_transcript_extractor": "transcript",
    "tikhub_tiktok_shop_search_v2": "product",
    "tikhub_tiktok_shop_hot_products": "product",
    "apify_tiktok_shop_product_detail": "product",
    "apify_tiktok_shop_search_scraper": "product",
    "apify_tiktok_shop_scraper": "product",
    "tikhub_tiktok_shop_reviews_v2": "review",
    "apify_tiktok_shop_creators": "commerce_profile",
}


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount")
    if value is None or value == "":
        return None
    text = str(value).strip()
    multiplier = 1
    if text and text[-1].upper() in {"K", "M", "B"}:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[
            text[-1].upper()
        ]
        text = text[:-1]
    match = re.search(r"[-+]?\d[\d,]*\.?\d*", text)
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", "")) * multiplier
    except ValueError:
        return None


def _money_field(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount")
    if value is None or value == "":
        return None
    text = str(value).replace(",", "")
    multiplier = 1
    if text and text[-1].upper() in {"K", "M", "B"}:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[
            text[-1].upper()
        ]
        text = text[:-1]
    match = re.search(r"[-+]?\d[\d,]*\.?\d*", text)
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", "")) * multiplier
    except ValueError:
        return None


def _canonicalize_product(record: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("raw")
    if not isinstance(raw, dict):
        return record
    out = dict(record)
    region = raw.get("region")
    if isinstance(region, dict):
        region = region.get("key") or region.get("id") or region.get("name")
    seller = raw.get("seller")
    seller = seller if isinstance(seller, dict) else {}
    prices = str(raw.get("real_price") or raw.get("price") or "")
    price_parts = re.findall(r"\d[\d,]*\.?\d*", prices.replace(",", ""))
    price_amount = _money_field(price_parts[0]) if price_parts else None
    max_price = _money_field(price_parts[-1]) if price_parts else None
    out.update(
        {
            "product_id": raw.get("product_id") or raw.get("id"),
            "region": str(region or record.get("region") or "").upper() or None,
            "title": raw.get("product_name") or raw.get("product_title") or raw.get("title"),
            "text": raw.get("product_name") or raw.get("product_title") or raw.get("title"),
            "price_amount": price_amount,
            "min_price_amount": _money_field(raw.get("min_price")),
            "max_price_amount": _money_field(raw.get("max_price")) or max_price,
            "original_price_amount": _money_field(
                str(raw.get("original_price") or "").split(" - ")[0]
            ),
            "currency": "USD" if "$" in prices else raw.get("currency"),
            "sale_count": _number(
                raw.get("total_sale_cnt") or raw.get("sale_cnt")
            ),
            "sale_count_30d": _number(
                raw.get("total_sale_30d_cnt") or raw.get("sale_30d_cnt")
            ),
            "gmv_amount_30d": _money_field(
                raw.get("total_sale_gmv_30d_amt") or raw.get("gmv_30d_amt")
            ),
            "commission_rate": _number(raw.get("commission")),
            "stock_count": _number(raw.get("total_stock_cnt")),
            "review_count": _number(raw.get("review_count")),
            "rating": _number(raw.get("product_rating")),
            "description": raw.get("product_desc"),
            "category_path": raw.get("categories"),
            "seller_id": seller.get("seller_id") or seller.get("id"),
            "shop_name": seller.get("shop_name")
            or seller.get("seller_name")
            or seller.get("name"),
            "shop_id": seller.get("shop_id"),
            "product_url": raw.get("product_url")
            or raw.get("seo_url")
            or raw.get("url"),
            "image_urls": [raw["cover_url"]]
            if isinstance(raw.get("cover_url"), str)
            else raw.get("image_urls"),
            "skus_json": raw.get("skus"),
            "sku_count": len(raw["skus"]) if isinstance(raw.get("skus"), list) else None,
            "free_shipping": bool(raw.get("is_free_shipping"))
            if raw.get("is_free_shipping") is not None
            else None,
            "is_hot": bool(raw.get("is_hot"))
            if raw.get("is_hot") is not None
            else None,
        }
    )
    return out


def _canonicalize_commerce_profile(record: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("raw")
    if not isinstance(raw, dict):
        return record
    stats = raw.get("stats")
    stats = stats if isinstance(stats, dict) else {}
    gmv = stats.get("gmv") if isinstance(stats.get("gmv"), dict) else {}
    gpm = stats.get("gpm") if isinstance(stats.get("gpm"), dict) else {}
    followers = (
        stats.get("followers") if isinstance(stats.get("followers"), dict) else {}
    )
    avg_views = (
        stats.get("avgViews") if isinstance(stats.get("avgViews"), dict) else {}
    )
    avg_likes = (
        stats.get("avgLikes") if isinstance(stats.get("avgLikes"), dict) else {}
    )
    avg_comments = (
        stats.get("avgComments") if isinstance(stats.get("avgComments"), dict) else {}
    )
    avg_shares = (
        stats.get("avgShares") if isinstance(stats.get("avgShares"), dict) else {}
    )
    engagement = (
        stats.get("engagementRate")
        if isinstance(stats.get("engagementRate"), dict)
        else {}
    )
    commission = (
        stats.get("avgCommission")
        if isinstance(stats.get("avgCommission"), dict)
        else {}
    )
    frequency = (
        stats.get("contentFrequency")
        if isinstance(stats.get("contentFrequency"), dict)
        else {}
    )
    out = dict(record)
    out.update(
        {
            "creator_id": raw.get("id"),
            "unique_id": raw.get("username"),
            "nickname": raw.get("nickname"),
            "avatar_url": raw.get("avatar"),
            "signature": raw.get("bio"),
            "region": raw.get("region"),
            "follower_count": _number(followers.get("total")),
            "gmv_amount": _money_field(gmv.get("total")),
            "currency": gmv.get("currency"),
            "units_sold": _number(stats.get("unitsSold")),
            "gpm_amount": _money_field(gpm.get("amount")),
            "avg_commission_rate": _number(commission.get("value")),
            "brand_collaboration_count": _number(
                stats.get("totalBrandCollaborations")
            ),
            "promoted_product_count": _number(stats.get("promotedProducts")),
            "avg_views": _number(avg_views.get("video")),
            "avg_likes": _number(avg_likes.get("video")),
            "avg_comments": _number(avg_comments.get("video")),
            "avg_shares": _number(avg_shares.get("video")),
            "engagement_rate": _number(engagement.get("video")),
            "content_frequency": _number(frequency.get("videos")),
            "post_rate": _number(stats.get("postRate")),
            "rating": _number(stats.get("rating")),
            "promotion_performance_score": _number(
                stats.get("promotionPerformanceScore")
            ),
            "top_brands": stats.get("topBrands"),
            "category_list": stats.get("categoryList"),
            "audience_json": followers.get("topDemographics"),
            "gmv_distribution_json": stats.get("gmvDistribution"),
        }
    )
    return out


def _canonicalize_tool_record(record: dict[str, Any]) -> dict[str, Any]:
    role = record.get("_tool_role")
    if role == "product":
        return _canonicalize_product(record)
    if role == "commerce_profile":
        return _canonicalize_commerce_profile(record)
    return record


async def _fetch_records(task_run_id: uuid.UUID, limit: int) -> list[dict[str, Any]]:
    async with collect_session_factory() as session:
        workspace = await get_demo_workspace(session)
        if workspace is None:
            return []
        raw_records = await get_raw_records(
            session,
            workspace,
            source_id=None,
            task_run_id=task_run_id,
            limit=limit,
            offset=0,
        )
    records: list[dict[str, Any]] = []
    for raw in raw_records:
        if isinstance(raw.content, dict):
            record = dict(raw.content)
            endpoint = str(record.get("collector_type") or "")
            if not endpoint:
                actor = str(record.get("actor_id") or "")
                endpoint = _ACTOR_TO_ENDPOINT.get(actor, "")
            role = _TOOL_ROLE_BY_ENDPOINT.get(endpoint)
            if role:
                record["_tool_role"] = role
            records.append(_canonicalize_tool_record(record))
        elif isinstance(raw.content, list):
            records.append({"items": raw.content})
    return records


def collect_session_factory():
    # Imported lazily so unit tests can patch collect_capability and the fetch path.
    from data_intelligence_hub.core.database import async_session_factory

    return async_session_factory()


async def _collect(
    project_id: uuid.UUID,
    endpoint_type: str,
    params: dict[str, Any],
    limit: int,
    *,
    role: str = "primary",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Lazy import breaks the mcp_runtime -> server -> tiktok_tools cycle.
    from data_intelligence_hub.mcp_runtime.collect_service import collect_capability

    context = _CURRENT_TOOL_CALL.get()
    tool_call = {**context, "role": role} if context else None
    try:
        response = await collect_capability(
            endpoint_type, project_id, params, tool_call=tool_call
        )
    except Exception as exc:
        return [], {
            "endpoint_type": endpoint_type,
            "status": "failed",
            "error": str(exc),
        }
    run = {
        "endpoint_type": endpoint_type,
        "task_id": str(response.task_id),
        "run_id": str(response.task_run_id),
        "status": response.status,
        "records_count": response.records_count,
        "error": response.error_message,
        "tool_call_id": context.get("tool_call_id") if context else None,
        "role": role,
    }
    if response.status == "failed" and not response.records_count:
        return [], run
    records = await _fetch_records(response.task_run_id, limit)
    return records, run


def _result(
    tool_id: str,
    records: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> ToolResult:
    errors = [
        str(run["error"])
        for run in runs
        if run.get("error") and not run.get("superseded_by")
    ]
    if records:
        status = "partial_success" if errors else "success"
    else:
        status = "failed" if errors else "empty"
    context = _CURRENT_TOOL_CALL.get()
    return ToolResult(
        tool_id=tool_id,
        status=status,
        records=records,
        records_count=len(records),
        runs=runs,
        errors=errors,
        metadata=metadata or {},
        tool_call_id=context.get("tool_call_id") if context else None,
    )


def _require_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key}_required")
    return value.strip()


def _limit(params: dict[str, Any], default: int = 50, maximum: int = 100) -> int:
    value = params.get("limit", default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


async def tiktok_trend_rank(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    limit = _limit(params)
    country_code = str(params.get("country_code") or "US")
    period = int(params.get("period") or 7)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_ads_trends",
        {"country_code": country_code, "period": period, "max_items": limit},
        limit,
    )
    return _result("tiktok_trend_rank", records, [run])


async def tiktok_hashtag_videos(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    limit = _limit(params)
    challenge_id = params.get("challenge_id")
    ch_id = params.get("ch_id")
    hashtag = params.get("hashtag")
    metadata: dict[str, Any] = {}
    if challenge_id:
        endpoint = "tikhub_tiktok_tag_posts_web"
        payload = {"challenge_id": str(challenge_id), "max_items": limit}
    elif ch_id:
        endpoint = "tikhub_tiktok_hashtag_posts"
        payload = {"ch_id": str(ch_id), "max_items": limit}
    elif isinstance(hashtag, str) and hashtag.strip():
        endpoint = "tikhub_tiktok_search_web"
        payload = {"keyword": hashtag.strip(), "max_items": limit}
        metadata["proxy"] = "search_web"
    else:
        return ToolResult(
            tool_id="tiktok_hashtag_videos",
            status="failed",
            errors=["hashtag_or_id_required"],
        )
    records, run = await _collect(project_id, endpoint, payload, limit)
    if metadata.get("proxy") == "search_web" and isinstance(hashtag, str):
        target = hashtag.strip().lstrip("#").lower()
        records = [
            record
            for record in records
            if any(
                str(item).strip().lstrip("#").lower() == target
                for item in (record.get("hashtags") or [])
                if isinstance(item, str)
            )
        ]
    return _result("tiktok_hashtag_videos", records, [run], metadata=metadata)


async def tiktok_video_search(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    query = _require_text(params, "query")
    limit = _limit(params)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_search_web",
        {"keyword": query, "max_items": limit},
        limit,
    )
    return _result("tiktok_video_search", records, [run])


def _video_id(params: dict[str, Any]) -> str | None:
    video_id = params.get("video_id")
    if isinstance(video_id, str) and video_id.strip():
        return video_id.strip()
    video_url = params.get("video_url")
    if isinstance(video_url, str):
        match = _VIDEO_ID_RE.search(video_url)
        if match:
            return match.group(1)
    return None


async def tiktok_video_detail(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    video_id = _video_id(params)
    if not video_id:
        return ToolResult(
            tool_id="tiktok_video_detail",
            status="failed",
            errors=["video_id_or_url_required"],
        )
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_video_detail",
        {"item_id": video_id},
        1,
    )
    if not records:
        video_url = params.get("video_url") or f"https://www.tiktok.com/video/{video_id}"
        fallback_records, fallback_run = await _collect(
            project_id,
            "apify_tiktok_scraper",
            {"postURLs": [video_url], "maxItems": 1},
            1,
        )
        run = {**fallback_run, "primary": run}
        records = fallback_records
    return _result("tiktok_video_detail", records, [run])


async def tiktok_video_comments(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    video_id = _video_id(params) or _require_text(params, "video_id")
    limit = _limit(params, default=100)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_comments_app",
        {"aweme_id": video_id, "max_items": limit},
        limit,
    )
    runs = [run]
    if params.get("include_replies", True) and records:
        reply_records: list[dict[str, Any]] = []
        for comment in records[:10]:
            comment_id = comment.get("comment_id")
            if not comment_id or not comment.get("reply_count"):
                continue
            replies, reply_run = await _collect(
                project_id,
                "tikhub_tiktok_comment_replies_app",
                {
                    "item_id": video_id,
                    "comment_id": str(comment_id),
                    "max_items": 10,
                },
                10,
            )
            runs.append(reply_run)
            reply_records.extend(replies)
        records = records + reply_records
    return _result("tiktok_video_comments", records, runs)


async def tiktok_creator_profile(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    handle = str(params.get("handle") or "").strip().lstrip("@")
    sec_uid = str(params.get("sec_uid") or "").strip()
    if not handle and not sec_uid:
        return ToolResult(
            tool_id="tiktok_creator_profile",
            status="failed",
            errors=["handle_or_sec_uid_required"],
        )
    metadata: dict[str, Any] = {}
    if handle and not sec_uid:
        identity, identity_run = await _collect(
            project_id,
            "tikhub_tiktok_sec_uid",
            {"url": f"https://www.tiktok.com/@{handle}"},
            1,
        )
        if identity:
            sec_uid = str(identity[0].get("value") or "")
        metadata["identity"] = identity_run
    profile_params: dict[str, Any] = {}
    if handle:
        profile_params["unique_id"] = handle
    if sec_uid:
        profile_params["sec_user_id"] = sec_uid
    records, profile_run = await _collect(
        project_id,
        "tikhub_tiktok_user_profile_web",
        profile_params,
        1,
    )
    runs = [profile_run]
    video_limit = _limit(
        {"limit": params.get("video_limit", 20)}, default=20
    )
    if params.get("include_videos", True) and sec_uid:
        videos, video_run = await _collect(
            project_id,
            "tikhub_tiktok_user_posts_web",
            {"sec_user_id": sec_uid, "max_items": video_limit},
            video_limit,
        )
        runs.append(video_run)
        records.extend(videos)
    if params.get("include_fans") and sec_uid:
        fan_limit = _limit(
            {"limit": params.get("fan_limit", 50)}, default=50
        )
        fans, fan_run = await _collect(
            project_id,
            "tikhub_tiktok_user_fans_web",
            {"sec_user_id": sec_uid, "max_items": fan_limit},
            fan_limit,
        )
        runs.append(fan_run)
        records.extend(fans)
    if not records and handle:
        fallback, fallback_run = await _collect(
            project_id,
            "apify_tiktok_media_profile_scraper",
            {
                "profiles": [f"https://www.tiktok.com/@{handle}"],
                "resultsPerPage": _limit(params, default=20),
            },
            _limit(params, default=20),
        )
        runs = [
            fallback_run,
            {**profile_run, "superseded_by": fallback_run["endpoint_type"]},
        ]
        records = fallback
    return _result("tiktok_creator_profile", records, runs, metadata=metadata)


async def tiktok_creator_search(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    query = _require_text(params, "query")
    limit = _limit(params)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_search_web",
        {"keyword": query, "max_items": limit},
        limit,
    )
    creators: dict[str, dict[str, Any]] = {}
    for record in records:
        creator_id = record.get("author_id") or record.get("author_username")
        if not creator_id:
            continue
        creators[str(creator_id)] = {
            "uid": record.get("author_id"),
            "unique_id": record.get("author_username"),
            "nickname": record.get("author_nickname"),
        }
    return _result(
        "tiktok_creator_search",
        list(creators.values()),
        [run],
        metadata={"proxy": "video_search_authors"},
    )


async def tiktok_transcript(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    video_urls = params.get("video_urls")
    if not isinstance(video_urls, list) or not video_urls:
        return ToolResult(
            tool_id="tiktok_transcript",
            status="failed",
            errors=["video_urls_required"],
        )
    limit = _limit(params, default=20)
    records, run = await _collect(
        project_id,
        "apify_tiktok_transcript_extractor",
        {"postURLs": [str(url) for url in video_urls], "maxItems": limit},
        limit,
    )
    return _result("tiktok_transcript", records, [run])


async def tiktok_product_search(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    query = _require_text(params, "query")
    region = str(params.get("region") or "US").upper()
    limit = _limit(params, default=20)
    records, run = await _collect(
        project_id,
        "apify_tiktok_shop_search_scraper",
        {
            "keyword": query,
            "country_code": region,
            "limit": min(limit, 10),
            "page": int(params.get("page") or 1),
        },
        limit,
    )
    runs = [run]
    if not records:
        fallback, fallback_run = await _collect(
            project_id,
            "tikhub_tiktok_shop_search_v2",
            {"search_word": query, "region": region, "offset": 0},
            limit,
        )
        fallback_run["superseded_by"] = run.get("run_id")
        runs.append(fallback_run)
        records = fallback
    return _result("tiktok_product_search", records, runs)


async def tiktok_product_detail(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    product_id = str(params.get("product_id") or "").strip()
    product_url = str(params.get("product_url") or "").strip()
    region = str(params.get("region") or "US").upper()
    if not product_url and product_id:
        product_url = f"https://shop.tiktok.com/view/product/{product_id}"
    if not product_url:
        return ToolResult(
            tool_id="tiktok_product_detail",
            status="failed",
            errors=["product_id_or_url_required"],
        )
    records, run = await _collect(
        project_id,
        "apify_tiktok_shop_product_detail",
        {"url": product_url, "region": region, "maxItems": 1},
        1,
    )
    return _result("tiktok_product_detail", records, [run])


async def tiktok_product_reviews(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    product_id = _require_text(params, "product_id")
    region = str(params.get("region") or "US").upper()
    limit = _limit(params, default=20)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_shop_reviews_v2",
        {
            "product_id": product_id,
            "region": region,
            "page_start": int(params.get("page_start") or 1),
        },
        limit,
    )
    return _result("tiktok_product_reviews", records, [run])


async def tiktok_creator_commerce(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    handle = _require_text(params, "handle").lstrip("@")
    region = str(params.get("region") or "US").upper()
    records, run = await _collect(
        project_id,
        "apify_tiktok_shop_creators",
        {"username": handle, "region": region, "maxItems": 1},
        1,
    )
    return _result("tiktok_creator_commerce", records, [run])


def _creator_cookie_configured() -> bool:
    return bool(os.getenv("TIKHUB_TIKTOK_CREATOR_COOKIE", "").strip())


async def tiktok_video_products(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    video_id = _require_text(params, "video_id")
    if not _creator_cookie_configured():
        return ToolResult(
            tool_id="tiktok_video_products",
            status="failed",
            errors=["tikhub_creator_cookie_not_configured"],
        )
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_video_products",
        {"item_ids": [video_id]},
        100,
    )
    return _result("tiktok_video_products", records, [run])


async def tiktok_creator_showcase(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    if not _creator_cookie_configured():
        return ToolResult(
            tool_id="tiktok_creator_showcase",
            status="failed",
            errors=["tikhub_creator_cookie_not_configured"],
        )
    limit = _limit(params, default=20)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_creator_showcase",
        {"offset": int(params.get("offset") or 0)},
        limit,
    )
    return _result("tiktok_creator_showcase", records, [run])


async def tiktok_ads_top(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    query = str(params.get("query") or "").strip()
    limit = _limit(params, default=20)
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_top_ads",
        {
            "query": query,
            "period": int(params.get("period") or 7),
            "page": 1,
            "max_items": limit,
        },
        limit,
    )
    return _result("tiktok_ads_top", records, [run])


async def tiktok_ads_detail(
    project_id: uuid.UUID, params: dict[str, Any]
) -> ToolResult:
    ad_id = _require_text(params, "ad_id")
    records, run = await _collect(
        project_id,
        "tikhub_tiktok_ads_detail",
        {"ads_id": ad_id},
        1,
    )
    return _result("tiktok_ads_detail", records, [run])


TOOL_HANDLERS = {
    "tiktok_trend_rank": tiktok_trend_rank,
    "tiktok_hashtag_videos": tiktok_hashtag_videos,
    "tiktok_video_search": tiktok_video_search,
    "tiktok_video_detail": tiktok_video_detail,
    "tiktok_video_comments": tiktok_video_comments,
    "tiktok_creator_profile": tiktok_creator_profile,
    "tiktok_creator_search": tiktok_creator_search,
    "tiktok_transcript": tiktok_transcript,
    "tiktok_product_search": tiktok_product_search,
    "tiktok_product_detail": tiktok_product_detail,
    "tiktok_product_reviews": tiktok_product_reviews,
    "tiktok_creator_commerce": tiktok_creator_commerce,
    "tiktok_video_products": tiktok_video_products,
    "tiktok_creator_showcase": tiktok_creator_showcase,
    "tiktok_ads_top": tiktok_ads_top,
    "tiktok_ads_detail": tiktok_ads_detail,
}


async def run_tiktok_tool(
    tool_id: str,
    project_id: uuid.UUID,
    params: dict[str, Any],
) -> ToolResult:
    handler = TOOL_HANDLERS.get(tool_id)
    if handler is None:
        raise ValueError(f"unknown_tiktok_tool: {tool_id}")
    tool_call_id = f"tc_{uuid.uuid4().hex[:12]}"
    spec = TOOL_SPECS.get(tool_id, {})
    token = _CURRENT_TOOL_CALL.set(
        {
            "tool_call_id": tool_call_id,
            "tool_id": tool_id,
            "label": spec.get("label", tool_id),
            "params": _summarize_params(params),
        }
    )
    try:
        return await handler(project_id, params)
    except ValueError as exc:
        return ToolResult(
            tool_id=tool_id,
            status="failed",
            errors=[str(exc)],
            tool_call_id=tool_call_id,
        )
    finally:
        _CURRENT_TOOL_CALL.reset(token)

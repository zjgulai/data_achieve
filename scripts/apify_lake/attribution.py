#!/usr/bin/env python3
"""平台-类型归因规则。

设计依据（2026-10-28 对真实数据的字段抽样）：

1. 85 个 actor 中只有 8 个在 catalog 里映射到多个端点，其中 3 个是多端点同义
   （instagram/account ×2、google_news/news ×2、alibaba/product ×3），
   实际歧义只有 5 个：tiktok、youtube、x、facebook 的 post/account，
   以及 google 的 search/ai_answer。
2. **不能默认取第一个候选。** clockworks/tiktok-scraper 同时服务视频与主页，
   账号快照会被误标成帖子。
3. 有两类 item 不是业务数据，必须单独标记：
   - ``{"noResults": true}`` 空结果哨兵。实测 apidojo/tweet-scraper 大量出现。
   - ``{"error", "errorDescription", "url"}`` 错误对象。
     实测 apify/facebook-posts-scraper 会返回。
   把它们当正常行会让「条数」虚高，平台统计失真。
"""

from __future__ import annotations

from typing import Any

# 明确的 actor 唯一归因（catalog 里唯一，或同义重复）
ACTOR_UNIQUE: dict[str, tuple[str, str]] = {
    "clockworks/free-tiktok-scraper": ("tiktok", "post"),
    "clockworks/tiktok-hashtag-scraper": ("tiktok", "post"),
    "clockworks/tiktok-comments-scraper": ("tiktok", "comment"),
    "apify/instagram-hashtag-scraper": ("instagram", "post"),
    "apify/instagram-tagged-scraper": ("instagram", "post"),
    "apify/instagram-scraper": ("instagram", "post"),
    "apify/web-fetch": ("web", "web_page"),
    "data_xplorer/tiktok-trends": ("tiktok", "trend"),
    "clearpath/reddit-subreddit-posts-scraper": ("reddit", "post"),
    "harshmaur/reddit-scraper": ("reddit", "post"),
    "axesso_data/amazon-reviews-scraper": ("amazon", "review"),
    "streamers/youtube-comments-scraper": ("youtube", "comment"),
    "leadsbrary/google-trends-scraper": ("google_trends", "trend"),
    "automation-lab/tiktok-trends-scraper": ("tiktok", "trend"),
    "scraper_one/x-posts-search": ("x", "post"),
    "scraper_one/facebook-posts-search": ("facebook", "post"),
    "apify/facebook-groups-scraper": ("facebook", "post"),
    "apify/instagram-profile-scraper": ("instagram", "account"),
    "data_xplorer/google-news-scraper-fast": ("google_news", "news"),
    # 2026-10-28 实测补录：这些 actor 不在 endpoint_catalog 里，
    # 但在账号内实际产生了数据集，其中 trustpilot 一家占 20,010 条。
    "memo23/trustpilot-scraper-ppe": ("trustpilot", "review"),
    "tri_angle/airbnb-scraper": ("airbnb", "product"),
    "maxcopell/tripadvisor-reviews": ("tripadvisor", "review"),
    "apify/facebook-marketplace-scraper": ("facebook", "product"),
    "apify/facebook-ads-scraper": ("facebook", "ad"),
    "sian.agency/walmart-data-scraper": ("walmart", "product"),
    "voyager/booking-scraper": ("booking", "product"),
    "xmiso_scrapers/shopify-shops-email-leads-scraper": ("shopify", "account"),
    "futurizerush/meta-threads-scraper": ("threads", "post"),
    "automation-lab/etsy-scraper": ("etsy", "product"),
}

# 歧义 actor 的判别规则：(actor, 判别字段, 命中即判定)
# 顺序有意义：先判 account 特征，再落到默认 post
DISAMBIGUATE: dict[str, list[tuple[str, tuple[str, str]]]] = {
    "clockworks/tiktok-scraper": [
        # 主页快照有 fans/heart/video 计数；视频条目有 authorMeta + playCount
        ("fans", ("tiktok", "account")),
        ("heart", ("tiktok", "account")),
        ("authorMeta", ("tiktok", "post")),
        ("playCount", ("tiktok", "post")),
    ],
    "streamers/youtube-scraper": [
        # 频道快照有 subscriberCount；视频有 viewCount + fromYTUrl
        ("subscriberCount", ("youtube", "account")),
        ("fromYTUrl", ("youtube", "post")),
        ("viewCount", ("youtube", "post")),
    ],
    "apidojo/tweet-scraper": [
        ("followers", ("x", "account")),
        ("fullText", ("x", "post")),
        ("retweetCount", ("x", "post")),
    ],
    "apify/facebook-posts-scraper": [
        ("pageName", ("facebook", "account")),
        ("postId", ("facebook", "post")),
        ("feedbackId", ("facebook", "post")),
    ],
    "apify/google-search-scraper": [
        # 只要出现 aiOverview 就是 AI 答案类型；否则是 SERP
        ("aiOverview", ("google", "ai_answer")),
        ("organicResults", ("google", "search_result")),
        ("searchQuery", ("google", "search_result")),
    ],
}

# 字段签名兜底：actId 缺失时用（实测 1,459 个 dataset 无 actId/actRunId）
SIGNATURES: list[tuple[str, str, str]] = [
    ("videoWebUrl", "tiktok", "comment"),
    ("cid", "tiktok", "comment"),
    ("webVideoUrl", "tiktok", "post"),
    ("authorMeta", "tiktok", "post"),
    ("shortCode", "instagram", "post"),
    ("ownerUsername", "instagram", "post"),
    ("fromYTUrl", "youtube", "post"),
    ("channelUsername", "youtube", "post"),
    ("subscriberCount", "youtube", "account"),
    ("fullText", "x", "post"),
    ("twitterUrl", "x", "post"),
    ("subreddit", "reddit", "post"),
    ("communityName", "reddit", "post"),
    ("organicResults", "google", "search_result"),
    ("offerId", "alibaba", "product"),
    ("publishedTimestamp", "google_news", "news"),
    ("markdown", "web", "web_page"),
    ("metadata", "web", "web_page"),
]

# 非业务数据的哨兵。命中即 item_status != 'content'
EMPTY_MARKERS = ("noResults", "noResultsFound", "empty")
ERROR_MARKERS = ("error", "errorDescription", "errorMessage")


def classify_item_status(item: dict[str, Any]) -> str:
    """判定 item 是否为真实业务内容。"""
    if not item:
        return "empty"
    keys = set(item)
    if any(k in keys for k in EMPTY_MARKERS):
        # 只有哨兵字段才算空结果，避免带业务字段的正常行被误判
        if len(keys) <= 3:
            return "empty"
    if "error" in keys and len(keys) <= 4:
        return "error"
    return "content"


def resolve(
    actor_name: str | None,
    first_item: dict[str, Any] | None,
) -> tuple[str, str, str, str]:
    """返回 (platform, object_type, source, confidence)。"""
    if actor_name:
        if actor_name in DISAMBIGUATE and first_item:
            keys = set(first_item)
            for field, target in DISAMBIGUATE[actor_name]:
                if field in keys:
                    return target[0], target[1], "actor_field", "high"
            # 是歧义 actor 但首条判不出：不猜
            return "other", "unknown", "actor_ambiguous", "low"
        if actor_name in ACTOR_UNIQUE:
            p, o = ACTOR_UNIQUE[actor_name]
            return p, o, "actor_unique", "high"

    if first_item:
        keys = set(first_item)
        for field, platform, otype in SIGNATURES:
            if field in keys:
                return platform, otype, "field_signature", "medium"

    return "other", "unknown", "unknown", "unknown"

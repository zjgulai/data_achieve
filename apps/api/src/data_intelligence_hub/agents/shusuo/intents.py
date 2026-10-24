"""数说的场景意图层。

把五类优先场景翻译成确定的端点与参数：
  社媒搜索、评论洞察、账号画像、热点、新闻；另含选品与价格。
自由文本只生成提案，用户回复「确认」后才执行采集。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_MAX_ITEMS = 10
MAX_ITEMS_LIMIT = 50
LIMIT_ERROR = "参数 max_items 必须在 1 到 50 之间。"
_COMMENT_PLATFORM_ERROR = (
    "目前只支持 TikTok、Reddit、YouTube 的评论链接。\n"
    "其他平台请先用「能力 评论」查端点，再用「采集 <端点> ...」。"
)

# 账号画像端点的结果数量参数键（目录已声明，采集器也认）。
# 不传就等于默认上限，卡片上写 10 条就成了谎报。
_ACCOUNT_LIMIT_KEYS: dict[str, str] = {
    "apify_tiktok_media_profile_scraper": "resultsPerPage",
    "apify_instagram_profile_scraper": "resultsLimit",
    "apify_twitter_user_scraper": "maxItems",
}

_PLATFORM_SEARCH: dict[str, tuple[str, str]] = {
    "tiktok": ("tikhub_tiktok_video_search", "TikTok"),
    "抖音": ("tikhub_douyin_video_search", "抖音"),
    "douyin": ("tikhub_douyin_video_search", "抖音"),
    "xhs": ("tikhub_xiaohongshu_search", "小红书"),
    "小红书": ("tikhub_xiaohongshu_search", "小红书"),
    "xiaohongshu": ("tikhub_xiaohongshu_search", "小红书"),
    "weibo": ("tikhub_weibo_search", "微博"),
    "微博": ("tikhub_weibo_search", "微博"),
    "bilibili": ("tikhub_bilibili_video_search", "B 站"),
    "b站": ("tikhub_bilibili_video_search", "B 站"),
    "youtube": ("tikhub_youtube_search", "YouTube"),
    "油管": ("tikhub_youtube_search", "YouTube"),
    "instagram": ("tikhub_instagram_search", "Instagram"),
    "ig": ("tikhub_instagram_search", "Instagram"),
    "x": ("tikhub_x_search", "X"),
    "twitter": ("tikhub_x_search", "X"),
    "推特": ("tikhub_x_search", "X"),
    "reddit": ("tikhub_reddit_search", "Reddit"),
}

_TRENDING: dict[str, str] = {
    "抖音": "tikhub_douyin_hot_search",
    "douyin": "tikhub_douyin_hot_search",
    "x": "tikhub_x_trending",
    "twitter": "tikhub_x_trending",
    "推特": "tikhub_x_trending",
    "youtube": "tikhub_youtube_trending",
    "油管": "tikhub_youtube_trending",
    "reddit": "tikhub_reddit_trending",
}


@dataclass(frozen=True)
class Proposal:
    endpoint_type: str
    params: dict[str, Any]
    title: str
    note: str = ""
    estimated_items: int = DEFAULT_MAX_ITEMS
    cost_notice: str = "费用未知，按上游实际计费"


def _limit(tokens: list[str]) -> tuple[list[str], int] | str:
    """拆出数量参数；无数量默认 10，非法数量返回带键名的固定提示。"""
    kept: list[str] = []
    limit = DEFAULT_MAX_ITEMS
    for token in tokens:
        match = re.fullmatch(r"(?:max_items|maxItems|n|数量)[=:](\d+)", token)
        if match:
            value = int(match.group(1))
            if not 1 <= value <= MAX_ITEMS_LIMIT:
                return LIMIT_ERROR
            limit = value
        else:
            kept.append(token)
    return kept, limit


def _host_matches(host: str, domain: str) -> bool:
    """严格按域名后缀匹配；evil-tiktok.com 不会命中 tiktok.com。"""
    normalized = host.partition(":")[0].rstrip(".").casefold()
    return normalized == domain or normalized.endswith(f".{domain}")


def _youtube_video_id(value: str) -> str:
    """从短链、watch、shorts、embed 形态的 YouTube 链接里取 video_id。"""
    url = value if "://" in value else f"https://{value}"
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    if _host_matches(host, "youtu.be"):
        return parsed.path.strip("/")
    if _host_matches(host, "youtube.com"):
        path = parsed.path.rstrip("/")
        if path.startswith("/watch"):
            return (parse_qs(parsed.query).get("v") or [""])[0]
        for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
            if path.startswith(prefix):
                return path[len(prefix) :]
    return ""


def _proposal_text(proposal: Proposal) -> str:
    import json

    params = json.dumps(proposal.params, ensure_ascii=False)
    lines = [
        f"意图：{proposal.title}",
        f"端点：{proposal.endpoint_type}",
        f"参数：{params}",
    ]
    if proposal.note:
        lines.append(f"说明：{proposal.note}")
    lines.append("回复「确认」执行；回复「取消」放弃。5 分钟内有效。采集会消耗上游额度。")
    return "\n".join(lines)


def build_proposal(text: str) -> Proposal | str:
    """返回 Proposal，或一句可直接回复给用户的说明。"""
    parts = text.split()
    if not parts:
        return "请说明要做什么。发「帮助」查看场景命令。"
    head = parts[0]
    rest = parts[1:]

    if head in {"搜", "搜索"}:
        return _search_proposal(rest)
    if head == "评论":
        return _comment_proposal(rest)
    if head == "账号":
        return _account_proposal(rest)
    if head in {"热点", "热搜"}:
        return _trending_proposal(rest)
    if head == "新闻":
        return _news_proposal(rest)
    if head == "选品":
        return _sourcing_proposal(rest)
    if head == "价格":
        return _price_proposal(rest)
    return "没有识别这个场景。发「帮助」查看可用场景。"


def _search_proposal(tokens: list[str]) -> Proposal | str:
    outcome = _limit(tokens)
    if isinstance(outcome, str):
        return outcome
    tokens, limit = outcome
    if not tokens:
        return "用法：搜 [平台] <关键词> [max_items=10]。平台可省略，省略时走 Exa 语义搜索。"
    platform, keyword_tokens = None, tokens
    if tokens[0].casefold() in _PLATFORM_SEARCH:
        platform = tokens[0].casefold()
        keyword_tokens = tokens[1:]
    if not keyword_tokens:
        return "请补一个关键词。例如：搜 reddit AI"
    keyword = " ".join(keyword_tokens)
    if platform is None:
        return Proposal(
            endpoint_type="exa_search_auto",
            params={"query": keyword, "num_results": limit},
            title=f"通用语义搜索：{keyword}",
            note="未指定平台，使用 Exa；要搜社媒请加平台名，例如「搜 reddit AI」。",
            estimated_items=limit,
        )
    endpoint, label = _PLATFORM_SEARCH[platform]
    return Proposal(
        endpoint_type=endpoint,
        params={"keyword": keyword, "max_items": limit},
        title=f"{label} 关键词搜索：{keyword}",
        estimated_items=limit,
    )


def _comment_proposal(tokens: list[str]) -> Proposal | str:
    outcome = _limit(tokens)
    if isinstance(outcome, str):
        return outcome
    tokens, limit = outcome
    if not tokens:
        return "用法：评论 <URL> [max_items=10]。支持 TikTok、Reddit、YouTube 链接。"
    url = tokens[0]
    host = urlparse(url).netloc.casefold()
    if _host_matches(host, "tiktok.com"):
        return Proposal(
            endpoint_type="apify_tiktok_comments_scraper",
            params={"postURLs": [url], "commentsPerPost": limit},
            title="TikTok 视频评论",
            estimated_items=limit,
        )
    if _host_matches(host, "reddit.com"):
        match = re.search(r"/comments/([a-z0-9]+)", url, re.IGNORECASE)
        if match is None:
            return "无法从 Reddit 链接中识别 post_id。请贴完整的帖子 URL。"
        return Proposal(
            endpoint_type="tikhub_reddit_post_comments",
            params={"post_id": match.group(1), "max_items": limit},
            title="Reddit 帖子评论",
            estimated_items=limit,
        )
    video_id = _youtube_video_id(url)
    if video_id:
        return Proposal(
            endpoint_type="tikhub_youtube_video_comments",
            params={"video_id": video_id, "max_items": limit},
            title="YouTube 视频评论",
            estimated_items=limit,
        )
    if _host_matches(host, "youtube.com") or _host_matches(host, "youtu.be"):
        return "无法从 YouTube 链接中识别 video_id。请贴带 v= 参数的视频 URL。"
    return _COMMENT_PLATFORM_ERROR


def _account_proposal(tokens: list[str]) -> Proposal | str:
    outcome = _limit(tokens)
    if isinstance(outcome, str):
        return outcome
    tokens, limit = outcome
    if len(tokens) < 2:
        return "用法：账号 <平台> <handle>。支持 tiktok、instagram、x。"
    platform = tokens[0].casefold()
    handle = tokens[1].lstrip("@")
    if platform == "tiktok":
        return Proposal(
            endpoint_type="apify_tiktok_media_profile_scraper",
            params={
                "profiles": [handle],
                _ACCOUNT_LIMIT_KEYS["apify_tiktok_media_profile_scraper"]: limit,
            },
            title=f"TikTok 账号资料：@{handle}",
            estimated_items=limit,
        )
    if platform in {"instagram", "ig"}:
        return Proposal(
            endpoint_type="apify_instagram_profile_scraper",
            params={
                "usernames": [handle],
                _ACCOUNT_LIMIT_KEYS["apify_instagram_profile_scraper"]: limit,
            },
            title=f"Instagram 账号资料：@{handle}",
            estimated_items=limit,
        )
    if platform in {"x", "twitter", "推特"}:
        return Proposal(
            endpoint_type="apify_twitter_user_scraper",
            params={
                "twitterHandles": [handle],
                _ACCOUNT_LIMIT_KEYS["apify_twitter_user_scraper"]: limit,
            },
            title=f"X 账号资料：@{handle}",
            estimated_items=limit,
        )
    return "账号画像目前支持 tiktok、instagram、x。其他平台请用「能力 账号」查端点。"


def _trending_proposal(tokens: list[str]) -> Proposal | str:
    platform = tokens[0].casefold() if tokens else "douyin"
    endpoint = _TRENDING.get(platform)
    if endpoint is None:
        return "热点支持：抖音、X、YouTube、Reddit。例如：热点 x"
    params: dict[str, Any] = {}
    estimated = DEFAULT_MAX_ITEMS
    if endpoint == "tikhub_reddit_trending":
        params["max_items"] = DEFAULT_MAX_ITEMS
    return Proposal(
        endpoint_type=endpoint,
        params=params,
        title=f"{platform} 热点/热搜",
        estimated_items=estimated,
    )


def _news_proposal(tokens: list[str]) -> Proposal | str:
    outcome = _limit(tokens)
    if isinstance(outcome, str):
        return outcome
    tokens, limit = outcome
    if not tokens:
        return "用法：新闻 <关键词> [max_items=10]"
    keyword = " ".join(tokens)
    return Proposal(
        endpoint_type="exa_search_news",
        params={"query": keyword, "num_results": limit},
        title=f"新闻搜索：{keyword}",
        estimated_items=limit,
    )


def _sourcing_proposal(tokens: list[str]) -> Proposal | str:
    outcome = _limit(tokens)
    if isinstance(outcome, str):
        return outcome
    tokens, limit = outcome
    if not tokens:
        return "用法：选品 <关键词> [max_items=10]"
    keyword = " ".join(tokens)
    return Proposal(
        endpoint_type="apify_aliexpress_product_search_v2",
        params={"queries": [keyword], "shipTo": "US", "maxPages": 1, "maxItems": limit},
        title=f"AliExpress 选品：{keyword}",
        note="默认收货国 US；1688 采购请用「详情 apify_1688_advanced」后走「采集」。",
        estimated_items=limit,
    )


def _price_proposal(tokens: list[str]) -> Proposal | str:
    if not tokens:
        return "用法：价格 <Amazon 商品 URL 或 ASIN>"
    value = tokens[0]
    if value.startswith("http"):
        url = value
    elif re.fullmatch(r"[A-Z0-9]{10}", value, re.IGNORECASE):
        url = f"https://www.amazon.com/dp/{value.upper()}"
    else:
        return "请提供 Amazon 商品 URL 或 10 位 ASIN。"
    return Proposal(
        endpoint_type="apify_amazon_price_tracker",
        params={"products": [{"url": url}]},
        title="Amazon 价格追踪",
        estimated_items=1,
    )


def proposal_reply(proposal: Proposal) -> str:
    return _proposal_text(proposal)

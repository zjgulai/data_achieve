"""
数据清洗管道：L1 字段过滤 → L2 指标计算 → L3 LLM 摘要洞察
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .config import get_cdo_config
from .intent import TikTokIntent

logger = logging.getLogger(__name__)


# ── L1 保留字段配置 ────────────────────────────────────────────────────────────
_KEEP_FIELDS: dict[str, list[str]] = {
    "search": [
        "id", "desc", "author", "authorMeta", "stats",
        "videoMeta", "createTime", "challenges",
    ],
    "hashtag": [
        "id", "desc", "author", "authorMeta", "stats",
        "videoMeta", "createTime",
    ],
    "user_posts": [
        "id", "desc", "stats", "videoMeta", "createTime",
        "challenges", "duetInfo",
    ],
    "top_ads": [
        "ad_id", "ad_title", "brand_name", "industry_key",
        "cost", "ctr", "impression", "like", "comment", "share",
        "video_info", "landing_page_url", "first_shown_date", "last_shown_date",
    ],
    "ads_search": [
        "ad_id", "ad_title", "brand_name", "keyword_list",
        "ctr", "impression", "like", "first_shown_date",
    ],
    "creator": [
        "user_id", "sec_uid", "nickname", "follower_count",
        "following_count", "heart_count", "video_count",
        "avg_engagement_rate", "avg_views", "audience_countries",
    ],
    "followers": [
        "user_id", "sec_uid", "nickname", "follower_count",
        "following_count", "verified",
    ],
    "live": [
        "room_id", "title", "user_info", "user_count",
        "like_count", "create_time",
    ],
    "sentiment": [
        "title", "url", "published_date", "author", "summary",
    ],
}


def _filter_fields(record: dict[str, Any], action: str) -> dict[str, Any]:
    keep = _KEEP_FIELDS.get(action, [])
    if not keep:
        return record
    return {k: record[k] for k in keep if k in record}


# ── L2 指标计算 ────────────────────────────────────────────────────────────────

def _calc_metrics(record: dict[str, Any], action: str) -> dict[str, Any]:
    """原地（返回新 dict）添加计算指标。"""
    r = dict(record)

    if action in ("search", "hashtag", "user_posts"):
        stats = r.get("stats") or {}
        plays = int(stats.get("playCount", 0) or 0)
        likes = int(stats.get("diggCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        shares = int(stats.get("shareCount", 0) or 0)
        if plays > 0:
            r["_engagement_rate"] = round((likes + comments + shares) / plays * 100, 2)
        else:
            r["_engagement_rate"] = 0.0
        r["_plays"] = plays
        r["_likes"] = likes

    elif action == "top_ads":
        ctr = float(r.get("ctr", 0) or 0)
        imp = int(r.get("impression", 0) or 0)
        # 简单效率分：ctr * log(impression+1) / 10
        import math
        r["_ad_efficiency"] = round(ctr * math.log(imp + 1) / 10, 3)

    elif action == "live":
        user_count = int(r.get("user_count", 0) or 0)
        like_count = int(r.get("like_count", 0) or 0)
        if user_count > 0:
            r["_heat_index"] = round(like_count / user_count, 1)
        else:
            r["_heat_index"] = 0.0

    return r


# ── L3 LLM 摘要 ────────────────────────────────────────────────────────────────

_L3_SYSTEM = """\
你是 TikTok 数据分析专家。用户提供一批 TikTok 采集数据（JSON），你需要用3-5句中文给出专业洞察：
- 指出关键趋势（播放量、互动率、热点话题）
- 点出1-2个值得关注的异常或机会
- 结尾给出1句行动建议
输出纯文本，不要 markdown 符号。
"""

_L3_PROMPTS: dict[str, str] = {
    "search": "以下是关键词视频搜索结果，分析内容趋势和高互动视频特征：\n\n{data}",
    "hashtag": "以下是话题帖子数据，分析该话题的热度趋势和 Top 创作者特征：\n\n{data}",
    "user_posts": "以下是某账号的视频列表，分析该账号的内容策略和互动表现：\n\n{data}",
    "top_ads": "以下是 TikTok 热门广告数据，分析广告主行业分布和创意特点：\n\n{data}",
    "ads_search": "以下是广告搜索结果，分析关键词广告竞争情况：\n\n{data}",
    "creator": "以下是 TikTok 创作者信息，分析该 KOL 的影响力和合作价值：\n\n{data}",
    "followers": "以下是粉丝列表数据，分析粉丝质量和地区分布特征：\n\n{data}",
    "live": "以下是直播间数据，分析直播热度和内容类型：\n\n{data}",
    "sentiment": "以下是关于该品牌/话题的媒体报道，分析舆情走向和情感倾向：\n\n{data}",
}


async def generate_insight(
    records: list[dict[str, Any]], action: str, keyword: str = ""
) -> str:
    config = get_cdo_config()
    if not config.deepseek_api_key:
        return f"共 {len(records)} 条数据，DeepSeek 未配置，无法生成洞察。"
    if not records:
        return "本次采集未获取到数据。"

    # 只取前 10 条压缩传给 LLM，避免超 token
    sample = records[:10]
    data_str = json.dumps(sample, ensure_ascii=False, default=str)[:3000]

    prompt_tmpl = _L3_PROMPTS.get(action, "分析以下数据：\n\n{data}")
    user_prompt = prompt_tmpl.format(data=data_str)
    if keyword:
        user_prompt = f"关键词：{keyword}\n\n" + user_prompt

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{config.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.deepseek_api_key}"},
                json={
                    "model": config.deepseek_model,
                    "messages": [
                        {"role": "system", "content": _L3_SYSTEM},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            return str(resp.json()["choices"][0]["message"]["content"]).strip()
    except Exception as e:
        logger.warning("L3 摘要生成失败: %s", e)
        return f"共 {len(records)} 条数据，洞察生成暂时不可用。"


# ── 主入口 ─────────────────────────────────────────────────────────────────────

async def clean_and_analyze(
    raw_data: dict[str, Any],
    intent: TikTokIntent,
) -> dict[str, Any]:
    """
    返回结构：
    {
        "records": [...],      # L1+L2 处理后
        "insight": "...",      # L3 摘要
        "total": int,
        "error": str | None,
    }
    """
    action = intent.action
    error = raw_data.get("error")
    raw_records: list[dict[str, Any]] = raw_data.get("records", []) or []

    # L1 + L2
    cleaned: list[dict[str, Any]] = []
    for rec in raw_records:
        if not isinstance(rec, dict):
            continue
        r = _filter_fields(rec, action)
        r = _calc_metrics(r, action)
        cleaned.append(r)

    # 按互动率或播放量降序（视频类）
    if action in ("search", "hashtag", "user_posts"):
        cleaned.sort(key=lambda x: x.get("_engagement_rate", 0), reverse=True)
    elif action == "top_ads":
        cleaned.sort(key=lambda x: x.get("_ad_efficiency", 0), reverse=True)
    elif action == "live":
        cleaned.sort(key=lambda x: x.get("user_count", 0), reverse=True)

    # L3
    insight = await generate_insight(cleaned, action, intent.keyword or "")

    return {
        "records": cleaned,
        "insight": insight,
        "total": len(cleaned),
        "error": error,
    }

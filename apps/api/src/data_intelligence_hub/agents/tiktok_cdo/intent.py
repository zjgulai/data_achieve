from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from .config import get_cdo_config

logger = logging.getLogger(__name__)

ActionType = Literal[
    "search",       # 视频搜索
    "hashtag",      # 话题分析
    "user_posts",   # 账号主页视频
    "top_ads",      # 热门广告
    "ads_search",   # 广告搜索
    "creator",      # KOL 分析
    "followers",    # 粉丝分析
    "live",         # 直播监控
    "sentiment",    # 舆情监控（Exa）
    "unknown",      # 识别失败
]


@dataclass
class TikTokIntent:
    action: ActionType
    keyword: str | None = None
    username: str | None = None   # @ 开头的用户名，去掉 @
    limit: int = 10
    time_range: str | None = None # "7d" / "30d" / "24h"
    raw_text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


_SYSTEM_PROMPT = """\
你是 TikTok 数据采集意图识别引擎。用户用中文或英文发送采集请求，你需要解析出以下字段并以 JSON 返回。

action 枚举值（只能取其一）：
- search: 搜索/查找视频、内容
- hashtag: 分析话题/标签，用户提到 # 或"话题"
- user_posts: 查看某账号/用户的视频列表
- top_ads: 查看热门广告/爆款广告
- ads_search: 搜索某类广告
- creator: 分析 KOL/创作者/网红信息
- followers: 分析某用户的粉丝
- live: 搜索/监控直播
- sentiment: 舆情监控、品牌监控、新闻追踪

JSON 格式（严格输出，不加注释）：
{
  "action": "<action>",
  "keyword": "<关键词，没有则 null>",
  "username": "<用户名不含@，没有则 null>",
  "limit": <数字，默认 10，最大 50>,
  "time_range": "<'24h'|'7d'|'30d'|null>"
}

示例：
用户："搜索运动鞋相关视频 top5"
  → {"action":"search","keyword":"运动鞋","username":null,"limit":5,"time_range":null}
用户："分析 #美妆 话题最近7天"
  → {"action":"hashtag","keyword":"美妆","username":null,"limit":10,"time_range":"7d"}
用户："查看 @lilymaymac 的视频"
  → {"action":"user_posts","keyword":null,"username":"lilymaymac","limit":20,"time_range":null}
用户："最近爆火的美妆广告"
  → {"action":"top_ads","keyword":"美妆","username":null,"limit":10,"time_range":null}
用户："监控小米品牌舆情"
  → {"action":"sentiment","keyword":"小米","username":null,"limit":20,"time_range":"7d"}
"""


async def extract_intent(text: str) -> TikTokIntent:
    config = get_cdo_config()
    if not config.deepseek_api_key:
        logger.warning("DEEPSEEK_API_KEY 未配置，使用关键词回退策略")
        return _fallback_intent(text)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.deepseek_api_key}"},
                json={
                    "model": config.deepseek_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 200,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            return TikTokIntent(
                action=parsed.get("action", "unknown"),
                keyword=parsed.get("keyword"),
                username=parsed.get("username"),
                limit=min(int(parsed.get("limit", 10)), 50),
                time_range=parsed.get("time_range"),
                raw_text=text,
            )
    except Exception as e:
        logger.warning("DeepSeek 意图提取失败: %s，使用回退策略", e)
        return _fallback_intent(text)


def _fallback_intent(text: str) -> TikTokIntent:
    """简单关键词匹配回退，DeepSeek 不可用时使用。"""
    text_lower = text.lower()
    action: ActionType = "search"

    if any(w in text_lower for w in ["广告", "ads", "ad "]):
        action = "top_ads" if "热门" in text_lower or "爆" in text_lower else "ads_search"
    elif any(w in text_lower for w in ["话题", "#", "hashtag"]):
        action = "hashtag"
    elif any(w in text_lower for w in ["直播", "live"]):
        action = "live"
    elif any(w in text_lower for w in ["舆情", "新闻", "监控", "sentiment"]):
        action = "sentiment"
    elif any(w in text_lower for w in ["粉丝", "follower"]):
        action = "followers"
    elif any(w in text_lower for w in ["kol", "网红", "创作者", "creator"]):
        action = "creator"
    elif "@" in text:
        action = "user_posts"

    # 简单提取 @ 用户名
    username = None
    if "@" in text:
        parts = text.split("@")
        if len(parts) > 1:
            username = parts[1].split()[0].strip()

    # 简单提取关键词（去掉 @ 用户名和常见指令词后的第一个词组）
    keyword = None
    clean = text.replace(f"@{username}", "").strip() if username else text
    skip_words = {"搜索", "查找", "分析", "监控", "查看", "找", "看看", "帮我", "请", "top", "TOP"}
    words = [w for w in clean.split() if w not in skip_words and not w.isdigit()]
    if words:
        keyword = words[0].lstrip("#")

    return TikTokIntent(action=action, keyword=keyword, username=username, raw_text=text)

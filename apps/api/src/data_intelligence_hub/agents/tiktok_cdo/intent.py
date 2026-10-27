from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from ..prompt_loader import load_prompt
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


_AGENT_ID = "tiktok_cdo"


def _system_prompt() -> str | None:
    """读取意图提示词；文件缺失返回 None。

    不保留内置副本：提示词文件缺失时宁可走确定性的关键词回退
    （_fallback_intent），也不要拿一份可能已漂移的旧提示词去调模型。
    """
    return load_prompt(_AGENT_ID)



async def extract_intent(text: str) -> TikTokIntent:
    config = get_cdo_config()
    if not config.deepseek_api_key:
        logger.warning("DEEPSEEK_API_KEY 未配置，使用关键词回退策略")
        return _fallback_intent(text)

    system_prompt = _system_prompt()
    if system_prompt is None:
        # 提示词文件缺失时不调用模型：没有权威提示词的 JSON 契约，
        # 模型输出不可控，确定性回退比猜测安全。
        logger.warning("tiktok_cdo_prompt_missing，使用关键词回退策略")
        return _fallback_intent(text)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.deepseek_api_key}"},
                json={
                    "model": config.deepseek_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
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

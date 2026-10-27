from __future__ import annotations

import json
import logging
import re
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

# @ 用户名：字母数字下划线点，遇到撇号、逗号、空白即止。
_USERNAME_RE = re.compile(r"@([A-Za-z0-9_.]+)")
# topN：只认英文 topN（「top5」「TOP 5」「TOP10」）。中文「前7天」这类是时间
# 范围而非条数，不能当 limit，所以不纳入。开头也要词边界，避免 "desktop5"。
_TOP_N_RE = re.compile(r"(?<![a-z])top\s*(\d+)", re.IGNORECASE)
# 去掉 @用户名后残留的所有格残片（"'s"）。
_POSSESSIVE_RE = re.compile(r"'s\b", re.IGNORECASE)


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


def _has_keyword(text: str, words: tuple[str, ...]) -> bool:
    """判断文本是否包含任一关键词。

    英文关键词按词边界匹配，并允许复数后缀：子串匹配会让 "live" 命中
    "olive"、"ads" 命中 "headsets"；但只认单数会让 "follower" 匹配不到
    "followers"。中文没有词边界，仍用子串。
    """
    for word in words:
        if not word.isascii():
            if word in text:
                return True
            continue
        # 已经以 s 结尾的词（ads）不再追加可选 s，否则会拼成 adss?。
        plural = "" if word.endswith("s") else "s?"
        if re.search(
            rf"(?<![a-z]){re.escape(word)}{plural}(?![a-z])", text
        ):
            return True
    return False


def _fallback_intent(text: str) -> TikTokIntent:
    """简单关键词匹配回退，DeepSeek 不可用时使用。

    这是确定性降级路径，不追求语义理解，只求「不崩、不误判到无关动作」。
    明显的空输入直接判 unknown，避免把空消息当成搜索请求。
    """
    if not text.strip():
        return TikTokIntent(action="unknown", raw_text=text)

    text_lower = text.lower()
    action: ActionType = "search"

    if _has_keyword(text_lower, ("广告", "ads", "ad")):
        action = "top_ads" if "热门" in text_lower or "爆" in text_lower else "ads_search"
    elif _has_keyword(text_lower, ("话题", "#", "hashtag")):
        action = "hashtag"
    elif _has_keyword(text_lower, ("直播", "live")):
        action = "live"
    elif _has_keyword(text_lower, ("舆情", "新闻", "监控", "sentiment")):
        action = "sentiment"
    elif _has_keyword(text_lower, ("粉丝", "follower")):
        action = "followers"
    elif _has_keyword(text_lower, ("kol", "网红", "创作者", "creator")):
        action = "creator"
    elif "@" in text:
        action = "user_posts"

    # 提取 @ 用户名。用正则而不是 split("@")：'hello @' 会让 split 拿到空串
    # 再取 [0] 直接 IndexError；'@alice\'s' 也不该把撇号算进用户名。
    username = None
    match = _USERNAME_RE.search(text)
    if match:
        username = match.group(1)

    # 提取关键词：去掉 @用户名、常见指令词与 topN 这类数量词后的第一个词。
    clean = _USERNAME_RE.sub("", text) if username else text
    clean = _TOP_N_RE.sub("", clean)
    # 去掉 @用户名后常留下 " 's " 这类所有格残片，它不是关键词。
    clean = _POSSESSIVE_RE.sub(" ", clean).strip()
    skip_words = {
        "搜索", "查找", "分析", "监控", "查看", "找", "看看", "帮我", "请",
        "看", "search", "find", "show", "look", "top", "videos", "video",
    }
    words = [
        w
        for w in clean.split()
        if w.lower() not in skip_words
        and not w.isdigit()
        and w.strip("@#")  # 单独的 @ 或 # 不是关键词
    ]
    keyword = None
    if words:
        # 中文指令词常与关键词粘连（「搜索运动鞋」），剥掉前缀再取值。
        candidate = words[0].lstrip("#")
        for prefix in ("搜索", "查找", "分析", "监控", "查看"):
            if candidate.startswith(prefix) and len(candidate) > len(prefix):
                candidate = candidate[len(prefix):]
                break
        keyword = candidate.strip("@") or None

    # topN 也要能被理解成 limit；提示词承诺了这件事，回退层不该默默丢弃。
    limit = 10
    top_match = _TOP_N_RE.search(text)
    if top_match:
        limit = min(int(top_match.group(1)), 50)

    return TikTokIntent(
        action=action,
        keyword=keyword,
        username=username,
        limit=limit,
        raw_text=text,
    )

"""
飞书卡片 JSON 构建器。
使用飞书卡片 2.0 交互卡片格式。
"""

from __future__ import annotations

from typing import Any

from .intent import ActionType, TikTokIntent

_ACTION_LABEL: dict[ActionType, str] = {
    "search": "视频搜索",
    "hashtag": "话题分析",
    "user_posts": "账号视频",
    "top_ads": "热门广告",
    "ads_search": "广告搜索",
    "creator": "KOL 分析",
    "followers": "粉丝分析",
    "live": "直播监控",
    "sentiment": "舆情监控",
    "unknown": "未知请求",
}


def placeholder_card(intent: TikTokIntent) -> dict[str, Any]:
    """采集中占位卡。"""
    label = _ACTION_LABEL.get(intent.action, intent.action)
    kw = intent.keyword or intent.username or ""
    return {
        "schema": "2.0",
        "config": {"streaming": False},
        "body": {
            "type": "div",
            "elements": [
                {
                    "type": "markdown",
                    "content": f"**⏳ {label}**　`{kw}`\n\n正在采集数据，请稍候…",
                }
            ],
        },
        "header": {
            "title": {"type": "plain_text", "content": f"TikTok CDO · {label}"},
            "template": "blue",
        },
    }


def result_card(intent: TikTokIntent, cleaned: dict[str, Any]) -> dict[str, Any]:
    """结果卡。"""
    label = _ACTION_LABEL.get(intent.action, intent.action)
    kw = intent.keyword or intent.username or ""
    total = cleaned.get("total", 0)
    insight = cleaned.get("insight", "")
    records = cleaned.get("records", [])[:5]  # 卡片最多展示 5 条
    error = cleaned.get("error")

    elements: list[dict[str, Any]] = []

    # 洞察摘要
    if insight:
        elements.append({
            "type": "markdown",
            "content": f"**📊 数据洞察**\n\n{insight}",
        })
        elements.append({"type": "hr"})

    # 错误提示
    if error:
        elements.append({
            "type": "markdown",
            "content": f"⚠️ 部分数据采集失败：{error}",
        })

    # Top 数据列表
    if records:
        elements.append({
            "type": "markdown",
            "content": f"**Top {len(records)} 数据**（共 {total} 条）",
        })
        for i, rec in enumerate(records, 1):
            line = _format_record_line(rec, intent.action, i)
            elements.append({"type": "markdown", "content": line})

    if not records and not error:
        elements.append({"type": "markdown", "content": "本次采集未获取到数据。"})

    # 操作按钮
    actions: list[dict[str, Any]] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "content": "📤 导出到多维表格"},
            "action_type": "callback",
            "value": {"action": "export_bitable", "intent_action": intent.action, "keyword": kw},
        },
        {
            "type": "button",
            "text": {"type": "plain_text", "content": "🔄 重新采集"},
            "action_type": "callback",
            "value": {"action": "re_collect", "raw_text": intent.raw_text},
        },
    ]

    elements.append({"type": "action", "actions": actions})

    return {
        "schema": "2.0",
        "config": {"streaming": False},
        "header": {
            "title": {"type": "plain_text", "content": f"TikTok CDO · {label} · {kw}"},
            "template": "green" if not error else "yellow",
        },
        "body": {"type": "div", "elements": elements},
    }


def error_card(intent: TikTokIntent, error_msg: str) -> dict[str, Any]:
    """错误卡。"""
    label = _ACTION_LABEL.get(intent.action, intent.action)
    return {
        "schema": "2.0",
        "config": {"streaming": False},
        "header": {
            "title": {"type": "plain_text", "content": f"TikTok CDO · {label} · 失败"},
            "template": "red",
        },
        "body": {
            "type": "div",
            "elements": [
                {
                    "type": "markdown",
                    "content": f"❌ **采集失败**\n\n{error_msg}\n\n请检查参数后重试，或联系管理员",
                }
            ],
        },
    }


def _format_record_line(rec: dict[str, Any], action: str, idx: int) -> str:
    """将单条记录格式化为 markdown 行。"""
    if action in ("search", "hashtag", "user_posts"):
        desc = rec.get("desc", "")[:50]
        plays = _fmt_num(rec.get("_plays", 0))
        er = rec.get("_engagement_rate", 0)
        author = (rec.get("authorMeta") or {}).get("nickname", "")
        return f"{idx}. **{desc}** | @{author} | 播放 {plays} | 互动率 {er}%"

    if action == "top_ads":
        title = rec.get("ad_title", "")[:40]
        brand = rec.get("brand_name", "")
        eff = rec.get("_ad_efficiency", 0)
        return f"{idx}. **{title}** | {brand} | 效率分 {eff}"

    if action in ("creator", "followers"):
        name = rec.get("nickname", "")
        fans = _fmt_num(rec.get("follower_count", 0))
        er = rec.get("avg_engagement_rate", "")
        return f"{idx}. **{name}** | 粉丝 {fans} | 互动率 {er}"

    if action == "live":
        title = rec.get("title", "")[:40]
        online = _fmt_num(rec.get("user_count", 0))
        heat = rec.get("_heat_index", 0)
        return f"{idx}. **{title}** | 在线 {online} | 热度 {heat}"

    if action == "sentiment":
        title = rec.get("title", "")[:50]
        pub = rec.get("published_date", "")[:10]
        summary = rec.get("summary", "")[:60]
        url = rec.get("url", "")
        return f"{idx}. [{title}]({url}) | {pub}\n   {summary}"

    # 通用回退
    return f"{idx}. {str(rec)[:80]}"


def _fmt_num(n: int | float) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)

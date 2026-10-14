"""
统一数据采集入口。
- TikHub 端点：通过内部 /api/quick-collect 转发
- Exa.ai：直接 httpx 调用（用于 sentiment action）
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC
from typing import Any

import httpx

from .config import get_cdo_config
from .endpoint_router import build_collect_params
from .intent import TikTokIntent

logger = logging.getLogger(__name__)

# demo workspace，与 AGENTS.md 一致
_DEMO_WORKSPACE = "bf51c6a8-fba5-5528-ac91-89ffd84f85c2"


async def gather_data(intent: TikTokIntent) -> dict[str, Any]:
    """根据 intent 采集数据，返回原始结果字典。"""
    if intent.action == "sentiment":
        return await _call_exa(intent)

    params_list = build_collect_params(intent)
    if not params_list:
        return {"records": [], "error": "未知 action"}

    if len(params_list) == 1:
        endpoint_type, params = params_list[0]
        return await _call_tikhub(endpoint_type, params)

    # creator：并发两个端点，合并结果
    tasks = [_call_tikhub(et, p) for et, p in params_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: dict[str, Any] = {"records": []}
    for r in results:
        if not isinstance(r, dict):
            logger.warning("并发采集异常: %s", r)
            continue
        merged["records"].extend(r.get("records", []))
        # 其他字段直接合并覆盖（creator_info + creator_insights）
        for k, v in r.items():
            if k != "records":
                merged[k] = v
    return merged


async def _call_tikhub(endpoint_type: str, params: dict[str, Any]) -> dict[str, Any]:
    config = get_cdo_config()
    url = f"{config.internal_api_base}/api/quick-collect"
    payload = {
        "workspace_id": _DEMO_WORKSPACE,
        "endpoint_type": endpoint_type,
        "params": params,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
    except httpx.TimeoutException:
        logger.error("TikHub 采集超时: %s", endpoint_type)
        return {"records": [], "error": "采集超时，请稍后重试"}
    except Exception as e:
        logger.error("TikHub 采集失败: %s %s", endpoint_type, e)
        return {"records": [], "error": str(e)}


async def _call_exa(intent: TikTokIntent) -> dict[str, Any]:
    config = get_cdo_config()
    if not config.exa_api_key:
        return {"records": [], "error": "EXA_API_KEY 未配置"}

    query = f"TikTok {intent.keyword or ''} 舆情 新闻"
    payload = {
        "query": query,
        "type": "auto",
        "category": "news",
        "numResults": intent.limit,
        "includeDomains": [],  # 不限制，搜全网新闻
        "useAutoprompt": True,
        "contents": {
            "text": {"maxCharacters": 500},
            "highlights": {"numSentences": 2},
        },
    }
    # 若有时间范围
    if intent.time_range:
        from datetime import datetime, timedelta
        days = {"24h": 1, "7d": 7, "30d": 30}.get(intent.time_range, 7)
        start = (datetime.now(UTC) - timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        payload["startPublishedDate"] = start

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": config.exa_api_key, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            records = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "published_date": r.get("publishedDate", ""),
                    "author": r.get("author", ""),
                    "summary": (r.get("highlights") or [""])[0],
                    "text": r.get("text", ""),
                }
                for r in data.get("results", [])
            ]
            return {"records": records, "total": len(records)}
    except Exception as e:
        logger.error("Exa 采集失败: %s", e)
        return {"records": [], "error": str(e)}

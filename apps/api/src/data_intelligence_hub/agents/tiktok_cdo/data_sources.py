"""
统一数据采集入口。
- TikHub 端点：通过内部 /api/quick-collect 转发
- Exa.ai：直接 httpx 调用（用于 sentiment action）
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC
from typing import Any

import httpx

from .config import get_cdo_config
from .endpoint_router import build_collect_params
from .intent import TikTokIntent
from .tool_router import run_intent_tool, tool_routing_enabled

logger = logging.getLogger(__name__)


async def gather_data(intent: TikTokIntent) -> dict[str, Any]:
    """根据 intent 采集数据，返回原始结果字典。"""
    if intent.action == "sentiment":
        return await _call_exa(intent)

    config = get_cdo_config()
    if tool_routing_enabled(intent):
        try:
            project_id = uuid.UUID(config.project_id)
        except ValueError:
            logger.error("LARK_CDO_PROJECT_ID 不是合法 UUID: %s", config.project_id)
        else:
            adapted = await run_intent_tool(intent, project_id)
            if adapted is not None and adapted.get("status") != "failed":
                return adapted
            if adapted is not None:
                logger.warning(
                    "工具层失败，回退直连: %s %s",
                    adapted.get("tool_id"),
                    adapted.get("error"),
                )

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
    """进程内调用采集服务。

    不走 HTTP 回环。原因：
    1. quick-collect 路由已改为 fail-closed，回环请求不带 token 会 401。
    2. 进程内调用免去自己打自己的网络往返与超时。

    workspace 未传，服务层回退 demo workspace，与改造前行为一致。
    """
    config = get_cdo_config()
    try:
        project_id = uuid.UUID(config.project_id)
    except ValueError:
        logger.error("LARK_CDO_PROJECT_ID 不是合法 UUID: %s", config.project_id)
        return {"records": [], "error": "项目配置无效"}

    from data_intelligence_hub.core.database import async_session_factory
    from data_intelligence_hub.services.quick_collect_service import (
        QuickCollectRequest,
        run_quick_collect,
    )

    body = QuickCollectRequest(
        project_id=project_id,
        endpoint_type=endpoint_type,
        params=params,
    )
    try:
        async with async_session_factory() as session:
            outcome = await run_quick_collect(session, body)
            records = await _fetch_raw_records(session, outcome.run.id)
        data: dict[str, Any] = {
            "task_run_id": str(outcome.run.id),
            "status": outcome.run.status,
            "records_count": outcome.run.records_count,
            "records": records,
        }
        if outcome.run.error_message and not records:
            data["error"] = str(outcome.run.error_message)
        return data
    except Exception as e:
        logger.error("TikHub 采集失败: %s %s", endpoint_type, e)
        return {"records": [], "error": "采集失败，请稍后重试"}


async def _fetch_raw_records(
    session: Any,
    task_run_id: uuid.UUID,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """直接读 RawRecord。

    走仓储层而不是 HTTP，理由同 _call_tikhub。
    """
    from data_intelligence_hub.repositories.raw_records import list_raw_records
    from data_intelligence_hub.repositories.workspaces import get_demo_workspace

    workspace = await get_demo_workspace(session)
    if workspace is None:
        logger.error("读取 RawRecord 失败: demo workspace 不存在")
        return []
    rows = await list_raw_records(
        session,
        workspace.id,
        task_run_id=task_run_id,
        limit=limit,
    )
    records: list[dict[str, Any]] = []
    for row in rows:
        content = getattr(row, "content", None)
        if isinstance(content, dict):
            records.append(content)
        elif isinstance(content, list):
            records.append({"items": content})
    return records


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

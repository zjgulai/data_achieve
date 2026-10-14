"""
飞书 API 客户端。
- tenant_access_token 自动获取与刷新（内存缓存）
- 发送卡片消息、更新卡片、写多维表格
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import get_cdo_config

logger = logging.getLogger(__name__)

_LARK_BASE = "https://open.feishu.cn/open-apis"

# 简单内存缓存 token
_token_cache: dict[str, Any] = {"token": "", "expires_at": 0}


async def get_access_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return str(_token_cache["token"])

    config = get_cdo_config()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{_LARK_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": config.lark_app_id, "app_secret": config.lark_app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书 token 获取失败: {data}")
        token = data["tenant_access_token"]
        expire = int(data.get("expire", 7200))
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + expire
        return str(token)


async def send_card(chat_id: str, card: dict[str, Any]) -> str:
    """发送卡片消息，返回 message_id。"""
    token = await get_access_token()
    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": __import__("json").dumps(card),
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_LARK_BASE}/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            logger.error("发送卡片失败: %s", data)
            return ""
        return str(data.get("data", {}).get("message_id", ""))


async def update_card(message_id: str, card: dict[str, Any]) -> bool:
    """更新已有卡片消息。"""
    if not message_id:
        return False
    token = await get_access_token()
    import json as _json
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.patch(
            f"{_LARK_BASE}/im/v1/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": _json.dumps(card)},
        )
        resp.raise_for_status()
        data = resp.json()
        return bool(data.get("code") == 0)


async def write_bitable(records: list[dict[str, Any]]) -> bool:
    """将记录写入多维表格。"""
    config = get_cdo_config()
    if not config.bitable_app_token or not config.bitable_table_id:
        logger.warning("多维表格 app_token 或 table_id 未配置，跳过写入")
        return False

    token = await get_access_token()
    # 每次最多写 500 条
    batch = records[:500]
    rows = [{"fields": {k: str(v) for k, v in rec.items()}} for rec in batch]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_LARK_BASE}/bitable/v1/apps/{config.bitable_app_token}"
            f"/tables/{config.bitable_table_id}/records/batch_create",
            headers={"Authorization": f"Bearer {token}"},
            json={"records": rows},
        )
        resp.raise_for_status()
        data = resp.json()
        ok = data.get("code") == 0
        if not ok:
            logger.error("写入多维表格失败: %s", data)
        return bool(ok)

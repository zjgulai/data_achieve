"""数说应用的最小飞书客户端。

只实现机器人当前需要的能力：tenant_access_token、回复文本、发送文本/卡片。
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

from .config import get_shushuo_config

logger = structlog.get_logger(__name__)

_LARK_BASE = "https://open.feishu.cn/open-apis"
_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}


class LarkAPIError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"feishu api error {code}: {message}")
        self.code = code
        self.message = message


def _check(data: dict[str, Any], action: str) -> dict[str, Any]:
    if data.get("code") != 0:
        raise LarkAPIError(int(data.get("code", -1)), str(data.get("msg", action)))
    payload = data.get("data")
    return payload if isinstance(payload, dict) else {}


async def get_tenant_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return str(_token_cache["token"])

    config = get_shushuo_config()
    if not config.ready:
        raise LarkAPIError(-1, "LARK_SHUSUO_APP_ID / LARK_SHUSUO_APP_SECRET are not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{_LARK_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": config.app_id, "app_secret": config.app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
    _check(data, "tenant_access_token")
    token = str(data["tenant_access_token"])
    expire = int(data.get("expire", 7200))
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expire
    return token


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    token = await get_tenant_token()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(
            method,
            f"{_LARK_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return _check(data, path)


async def reply_text(message_id: str, text: str) -> str:
    """回复一条消息。返回新消息 ID。"""
    data = await _request(
        "POST",
        f"/im/v1/messages/{message_id}/reply",
        payload={
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
    )
    return str(data.get("message_id", ""))


async def send_text(receive_id: str, text: str, *, receive_id_type: str = "chat_id") -> str:
    data = await _request(
        "POST",
        "/im/v1/messages",
        params={"receive_id_type": receive_id_type},
        payload={
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
    )
    return str(data.get("message_id", ""))


async def send_card(
    receive_id: str, card: dict[str, Any], *, receive_id_type: str = "chat_id"
) -> str:
    data = await _request(
        "POST",
        "/im/v1/messages",
        params={"receive_id_type": receive_id_type},
        payload={
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        },
    )
    return str(data.get("message_id", ""))


async def update_card(message_id: str, card: dict[str, Any]) -> bool:
    data = await _request(
        "PATCH",
        f"/im/v1/messages/{message_id}",
        payload={"content": json.dumps(card, ensure_ascii=False)},
    )
    return bool(data.get("message_id", message_id))

"""出站 Webhook 的登记、签名与投递。

签名格式：``sha256=HMAC_SHA256(secret, f"{timestamp}.{body}")``。
请求头：``X-DIH-Timestamp``、``X-DIH-Signature``、``X-DIH-Event``。
每个事件创建投递行；失败按 0/1/3 秒退避重试三次。
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.webhook import WebhookDelivery, WebhookEndpoint

_MAX_ATTEMPTS = 3
_RETRY_DELAYS = (0.0, 1.0, 3.0)
_TIMEOUT_SECONDS = 10.0


class WebhookError(ValueError):
    """Webhook 配置错误。错误码直接回给调用方。"""


def generate_secret() -> str:
    return secrets.token_hex(16)


def sign_payload(secret: str, timestamp: str, body: str) -> str:
    message = f"{timestamp}.{body}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _validate_url(url: str) -> str:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WebhookError("webhook_url_invalid")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "test"}:
        raise WebhookError("webhook_url_requires_https")
    return normalized


def _http_client() -> httpx.AsyncClient:
    """测试可以替换本函数返回带 MockTransport 的客户端。"""
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


async def create_endpoint(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    url: str,
    description: str | None = None,
    secret: str | None = None,
) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(
        workspace_id=workspace_id,
        url=_validate_url(url),
        description=description,
        secret=secret or generate_secret(),
        enabled=True,
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def list_endpoints(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[WebhookEndpoint]:
    rows = await session.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.workspace_id == workspace_id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    return list(rows.scalars().all())


async def delete_endpoint(
    session: AsyncSession, workspace_id: uuid.UUID, endpoint_id: uuid.UUID
) -> bool:
    endpoint = await session.get(WebhookEndpoint, endpoint_id)
    if endpoint is None or endpoint.workspace_id != workspace_id:
        return False
    await session.delete(endpoint)
    await session.commit()
    return True


async def dispatch_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> list[WebhookDelivery]:
    """给工作区内所有启用的端点投递一次事件。"""
    endpoints = [
        endpoint
        for endpoint in await list_endpoints(session, workspace_id)
        if endpoint.enabled
    ]
    if not endpoints:
        return []

    deliveries: list[WebhookDelivery] = []
    for endpoint in endpoints:
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
            status="pending",
            attempts=0,
        )
        session.add(delivery)
        deliveries.append(delivery)
    await session.flush()

    for delivery, endpoint in zip(deliveries, endpoints, strict=True):
        await _deliver(session, delivery, endpoint)
    await session.commit()
    return deliveries


async def _deliver(
    session: AsyncSession,
    delivery: WebhookDelivery,
    endpoint: WebhookEndpoint,
) -> None:
    body = json.dumps(delivery.payload, ensure_ascii=False, sort_keys=True)
    timestamp = str(int(time.time()))
    signature = sign_payload(endpoint.secret, timestamp, body)
    headers = {
        "Content-Type": "application/json",
        "X-DIH-Event": delivery.event_type,
        "X-DIH-Timestamp": timestamp,
        "X-DIH-Signature": signature,
    }

    last_error: str | None = None
    last_status: int | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        delay = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
        if delay:
            await asyncio.sleep(delay)
        delivery.attempts = attempt
        try:
            async with _http_client() as client:
                response = await client.post(endpoint.url, content=body, headers=headers)
            last_status = response.status_code
            if 200 <= response.status_code < 300:
                delivery.status = "delivered"
                delivery.response_status = response.status_code
                delivery.last_error = None
                delivery.delivered_at = datetime.now(UTC)
                await session.flush()
                return
            last_error = f"http_{response.status_code}"
        except httpx.HTTPError as exc:
            last_error = type(exc).__name__
        await session.flush()

    delivery.status = "failed"
    delivery.response_status = last_status
    delivery.last_error = last_error
    await session.flush()
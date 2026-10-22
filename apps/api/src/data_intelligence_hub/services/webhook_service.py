"""出站 Webhook 的登记、签名与投递。

签名格式：``sha256=HMAC_SHA256(secret, f"{timestamp}.{body}")``。
密钥用平台凭证主密钥加密存储；发送前与重定向后都校验公网地址。
失败按 0/1/3 秒退避重试三次，投递结果保存在数据库。
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
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.generic_web import (
    _assert_public_http_url,
    _parse_ip_literal,
    _resolve_host_ips,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.webhook import WebhookDelivery, WebhookEndpoint
from data_intelligence_hub.services.platform_credentials import PlatformCredentialCipher

_MAX_ATTEMPTS = 3
_RETRY_DELAYS = (0.0, 1.0, 3.0)
_TIMEOUT_SECONDS = 10.0
_MAX_REDIRECTS = 3


class WebhookError(ValueError):
    """Webhook 配置错误。错误码直接回给调用方。"""


def generate_secret() -> str:
    return secrets.token_hex(16)


def sign_payload(secret: str, timestamp: str, body: str) -> str:
    message = f"{timestamp}.{body}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _cipher() -> PlatformCredentialCipher:
    master_key = get_settings().platform_credential_master_key
    if master_key is None:
        raise WebhookError("webhook_vault_unavailable")
    return PlatformCredentialCipher.from_secret(master_key)


def _encrypt_secret(secret: str) -> str:
    return _cipher().encrypt({"secret": secret})


def _decrypt_secret(encrypted: str) -> str:
    payload = _cipher().decrypt(encrypted)
    secret = payload.get("secret")
    if not secret:
        raise WebhookError("webhook_secret_invalid")
    return secret


def _normalize_url(url: str) -> str:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise WebhookError("webhook_url_requires_public_https")
    return normalized


async def _assert_safe_url(url: str) -> str:
    try:
        await _assert_public_http_url(url)
        hostname = urlparse(url).hostname
        if hostname is None:
            raise WebhookError("webhook_url_not_public")
        addresses = _parse_ip_literal(hostname)
        if addresses is None:
            addresses = await _resolve_host_ips(hostname)
        return str(addresses[0])
    except WebhookError:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一翻译成业务错误码
        raise WebhookError("webhook_url_not_public") from exc


def _http_client() -> httpx.AsyncClient:
    """测试可以替换本函数返回带 MockTransport 的客户端。"""
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=False)


async def create_endpoint(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    url: str,
    description: str | None = None,
    secret: str | None = None,
) -> tuple[WebhookEndpoint, str]:
    normalized_url = _normalize_url(url)
    await _assert_safe_url(normalized_url)
    plaintext = secret or generate_secret()
    endpoint = WebhookEndpoint(
        workspace_id=workspace_id,
        url=normalized_url,
        description=description,
        secret=_encrypt_secret(plaintext),
        enabled=True,
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint, plaintext


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
    """禁用端点并覆写密钥。保留投递历史，避免外键阻断删除。"""
    endpoint = await session.get(WebhookEndpoint, endpoint_id)
    if endpoint is None or endpoint.workspace_id != workspace_id:
        return False
    endpoint.enabled = False
    endpoint.secret = _encrypt_secret(generate_secret())
    await session.commit()
    return True


async def dispatch_event(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> list[WebhookDelivery]:
    """把事件写入持久 outbox。网络投递由 WebhookWorkerRuntime 处理。"""
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
    # 先提交 outbox，再由后台 worker 发网络请求。调用方不持有连接等待外部服务。
    await session.commit()
    return deliveries


async def _deliver(
    session: AsyncSession,
    delivery: WebhookDelivery,
    endpoint: WebhookEndpoint,
) -> None:
    body = json.dumps(delivery.payload, ensure_ascii=False, sort_keys=True)
    timestamp = str(int(time.time()))
    secret = _decrypt_secret(endpoint.secret)
    signature = sign_payload(secret, timestamp, body)
    headers = {
        "Content-Type": "application/json",
        "X-DIH-Event": delivery.event_type,
        "X-DIH-Delivery": str(delivery.id),
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
            current_url = endpoint.url
            response: httpx.Response | None = None
            async with _http_client() as client:
                for _redirect in range(_MAX_REDIRECTS + 1):
                    public_ip = await _assert_safe_url(current_url)
                    parsed = httpx.URL(current_url)
                    original_host = str(parsed.host)
                    pinned_url = str(parsed.copy_with(host=public_ip))
                    request_headers = {**headers, "Host": original_host}
                    response = await client.post(
                        pinned_url,
                        content=body,
                        headers=request_headers,
                        follow_redirects=False,
                        extensions={"sni_hostname": original_host},
                    )
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    location = response.headers.get("location", "").strip()
                    if not location:
                        raise WebhookError("webhook_redirect_invalid")
                    current_url = urljoin(str(response.url), location)
                if response is None:
                    raise WebhookError("webhook_response_missing")
            last_status = response.status_code
            if 200 <= response.status_code < 300:
                delivery.status = "delivered"
                delivery.response_status = response.status_code
                delivery.last_error = None
                delivery.delivered_at = datetime.now(UTC)
                await session.flush()
                return
            # 永久 4xx 不重试；429 是限流，可重试。
            last_error = f"http_{response.status_code}"
            if 400 <= response.status_code < 500 and response.status_code != 429:
                break
        except (httpx.HTTPError, WebhookError) as exc:
            last_error = type(exc).__name__
        await session.flush()

    delivery.status = "failed"
    delivery.response_status = last_status
    delivery.last_error = last_error
    await session.flush()

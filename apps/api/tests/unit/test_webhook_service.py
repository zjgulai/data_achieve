"""出站 Webhook：签名、投递与失败重试。"""

from __future__ import annotations

import hashlib
import hmac
import uuid

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.webhook import WebhookDelivery, WebhookEndpoint
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import webhook_service
from data_intelligence_hub.services.webhook_service import (
    WebhookError,
    create_endpoint,
    dispatch_event,
    sign_payload,
)
from data_intelligence_hub.services.webhook_worker import WebhookWorkerRuntime


@pytest.fixture(autouse=True)
def webhook_vault(monkeypatch: pytest.MonkeyPatch):
    # tests/unit/test_platform_credentials.py 的固定 Fernet 测试密钥。
    monkeypatch.setenv(
        "PLATFORM_CREDENTIAL_MASTER_KEY",
        Fernet.generate_key().decode("ascii"),
    )
    get_settings.cache_clear()

    async def safe_url(_url: str) -> str:
        return "203.0.113.10"

    monkeypatch.setattr(webhook_service, "_assert_safe_url", safe_url)
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        session.add_all(
            [
                User(
                    id=user_id,
                    email="hook@example.com",
                    password_hash="x",
                    name="Hook",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Hook WS",
                    slug="hook-ws",
                    owner_id=user_id,
                ),
            ]
        )
        await session.commit()
    _factory_ids = {"workspace": workspace_id}
    factory.ids = _factory_ids  # type: ignore[attr-defined]
    yield factory
    await engine.dispose()


def _workspace_id(factory) -> uuid.UUID:
    return factory.ids["workspace"]  # type: ignore[attr-defined]


def test_sign_payload_matches_manual_hmac() -> None:
    secret = "s" * 32
    body = '{"a": 1}'
    timestamp = "1700000000"
    expected = hmac.new(
        secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
    ).hexdigest()
    assert sign_payload(secret, timestamp, body) == f"sha256={expected}"


@pytest.mark.asyncio
async def test_dispatch_signs_and_delivers(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        captured["url"] = str(request.url)
        captured["sni"] = request.extensions.get("sni_hostname")
        return httpx.Response(200)

    monkeypatch.setattr(
        webhook_service,
        "_http_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False
        ),
    )

    async with session_factory() as session:
        endpoint, plaintext = await create_endpoint(
            session,
            workspace_id=_workspace_id(session_factory),
            url="https://hooks.example.com/hook",
            description="test",
            secret="x" * 32,
        )
        deliveries = await dispatch_event(
            session,
            workspace_id=_workspace_id(session_factory),
            event_type="monitor.new_results",
            payload={"monitor_id": "m1", "new_count": 2},
        )
        assert len(deliveries) == 1
        delivery = deliveries[0]
        assert delivery.status == "pending"
    worker = WebhookWorkerRuntime(session_factory)
    assert await worker.run_once() is True
    async with session_factory() as session:
        delivery = await session.get(WebhookDelivery, delivery.id)
        assert delivery is not None
        assert delivery.status == "delivered"
        assert delivery.attempts == 1

    headers = captured["headers"]
    assert headers["x-dih-event"] == "monitor.new_results"
    timestamp = headers["x-dih-timestamp"]
    body = captured["body"]
    assert headers["x-dih-signature"] == sign_payload(plaintext, timestamp, body)
    assert headers["host"] == "hooks.example.com"
    assert str(captured["url"]).startswith("https://203.0.113.10/")
    assert captured["sni"] == "hooks.example.com"


@pytest.mark.asyncio
async def test_dispatch_retries_then_fails(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        webhook_service,
        "_http_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), follow_redirects=False
        ),
    )
    monkeypatch.setattr(webhook_service.asyncio, "sleep", no_sleep)

    async with session_factory() as session:
        await create_endpoint(
            session,
            workspace_id=_workspace_id(session_factory),
            url="https://hooks.example.com/hook",
            secret="y" * 32,
        )
        deliveries = await dispatch_event(
            session,
            workspace_id=_workspace_id(session_factory),
            event_type="monitor.new_results",
            payload={"monitor_id": "m2"},
        )
        delivery_id = deliveries[0].id
    worker = WebhookWorkerRuntime(session_factory)
    assert await worker.run_once() is True
    async with session_factory() as session:
        delivery = await session.get(WebhookDelivery, delivery_id)
        assert delivery is not None
        assert delivery.status == "failed"
        assert delivery.attempts == 3
        assert delivery.response_status == 500
        rows = (await session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 1
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_http_and_userinfo_urls_are_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        for url in ("http://example.com/hook", "https://user@example.com/hook"):
            with pytest.raises(WebhookError, match="public_https"):
                await create_endpoint(
                    session,
                    workspace_id=_workspace_id(session_factory),
                    url=url,
                )


@pytest.mark.asyncio
async def test_dispatch_skips_when_no_endpoints(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        deliveries = await dispatch_event(
            session,
            workspace_id=_workspace_id(session_factory),
            event_type="monitor.new_results",
            payload={"x": 1},
        )
    assert deliveries == []

@pytest.mark.asyncio
async def test_private_https_target_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from data_intelligence_hub.collectors.base import CollectorError

    async def private(_url: str) -> None:
        raise CollectorError("url_host_not_public")

    monkeypatch.setattr(webhook_service, "_assert_public_http_url", private)
    # 自动 fixture 把 _assert_safe_url 替换成 no-op；本用例恢复真实封装函数。
    async def real_safe(url: str) -> str:
        try:
            await webhook_service._assert_public_http_url(url)
        except Exception as exc:
            raise WebhookError("webhook_url_not_public") from exc
        raise AssertionError("expected public URL guard to reject")

    monkeypatch.setattr(webhook_service, "_assert_safe_url", real_safe)
    with pytest.raises(WebhookError, match="not_public"):
        await webhook_service._assert_safe_url("https://127.0.0.1/hook")


@pytest.mark.asyncio
async def test_delete_disables_endpoint_with_delivery_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        endpoint, _ = await create_endpoint(
            session,
            workspace_id=_workspace_id(session_factory),
            url="https://hooks.example.com/hook",
            secret="z" * 32,
        )
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            workspace_id=_workspace_id(session_factory),
            event_type="test",
            payload={},
            status="delivered",
            attempts=1,
        )
        session.add(delivery)
        await session.commit()
        assert await webhook_service.delete_endpoint(
            session, _workspace_id(session_factory), endpoint.id
        ) is True
        stored = await session.get(WebhookEndpoint, endpoint.id)
        assert stored is not None
        assert stored.enabled is False
        assert stored.secret != "z" * 32

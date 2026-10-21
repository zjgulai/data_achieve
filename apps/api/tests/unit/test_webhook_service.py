"""出站 Webhook：签名、投递与失败重试。"""

from __future__ import annotations

import hashlib
import hmac
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.webhook import WebhookDelivery
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import webhook_service
from data_intelligence_hub.services.webhook_service import (
    WebhookError,
    create_endpoint,
    dispatch_event,
    sign_payload,
)


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
        return httpx.Response(200)

    monkeypatch.setattr(
        webhook_service,
        "_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    async with session_factory() as session:
        endpoint = await create_endpoint(
            session,
            workspace_id=_workspace_id(session_factory),
            url="http://localhost:9999/hook",
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
        assert delivery.status == "delivered"
        assert delivery.attempts == 1

    headers = captured["headers"]
    assert headers["x-dih-event"] == "monitor.new_results"
    timestamp = headers["x-dih-timestamp"]
    body = captured["body"]
    assert headers["x-dih-signature"] == sign_payload(endpoint.secret, timestamp, body)


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
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(webhook_service.asyncio, "sleep", no_sleep)

    async with session_factory() as session:
        await create_endpoint(
            session,
            workspace_id=_workspace_id(session_factory),
            url="http://localhost:9999/hook",
            secret="y" * 32,
        )
        deliveries = await dispatch_event(
            session,
            workspace_id=_workspace_id(session_factory),
            event_type="monitor.new_results",
            payload={"monitor_id": "m2"},
        )
        delivery = deliveries[0]
        assert delivery.status == "failed"
        assert delivery.attempts == 3
        assert delivery.response_status == 500

        rows = (await session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 1
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_http_urls_require_allowed_host(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(WebhookError) as exc:
            await create_endpoint(
                session,
                workspace_id=_workspace_id(session_factory),
                url="http://example.com/hook",
            )
    assert str(exc.value) == "webhook_url_requires_https"


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
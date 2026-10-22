"""Webhook delivery replay worker.

Scans pending/failed rows and retries them outside collection transactions.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.models.webhook import WebhookDelivery, WebhookEndpoint
from data_intelligence_hub.services.webhook_service import _deliver

logger = structlog.get_logger(__name__)


class WebhookWorkerRuntime:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        poll_interval_seconds: float = 15.0,
    ) -> None:
        self._session_factory = session_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._run_forever())
        logger.info("webhook_worker_started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("webhook_worker_stopped")

    async def run_once(self) -> bool:
        delivery_id = await self._claim()
        if delivery_id is None:
            return False
        async with self._session_factory() as session:
            delivery = await session.get(WebhookDelivery, delivery_id)
            if delivery is None:
                return True
            endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
            if endpoint is None or not endpoint.enabled:
                delivery.status = "failed"
                delivery.last_error = "endpoint_disabled"
                await session.commit()
                return True
            try:
                await _deliver(session, delivery, endpoint)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                delivery = await session.get(WebhookDelivery, delivery_id)
                if delivery is not None:
                    delivery.status = "failed"
                    delivery.last_error = type(exc).__name__
                    await session.commit()
                logger.exception("webhook_worker_delivery_failed", delivery_id=str(delivery_id))
        return True

    async def _claim(self) -> uuid.UUID | None:
        async with self._session_factory() as session:
            statement = (
                select(WebhookDelivery)
                .where(
                    WebhookDelivery.status.in_(["pending", "failed"]),
                    WebhookDelivery.attempts < 6,
                )
                .order_by(WebhookDelivery.created_at, WebhookDelivery.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            delivery = (await session.execute(statement)).scalar_one_or_none()
            if delivery is None:
                return None
            delivery.status = "delivering"
            await session.commit()
            return delivery.id

    async def _run_forever(self) -> None:
        while True:
            try:
                processed = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("webhook_worker_iteration_failed")
                processed = False
            if not processed:
                await asyncio.sleep(self._poll_interval_seconds)

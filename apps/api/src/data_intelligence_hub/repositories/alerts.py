from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.alert import AlertEvent, AlertRule


async def list_alert_rules(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    enabled: bool | None = None,
) -> list[AlertRule]:
    statement = select(AlertRule).where(AlertRule.workspace_id == workspace_id)
    if enabled is not None:
        statement = statement.where(AlertRule.enabled == enabled)
    statement = statement.order_by(AlertRule.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_alert_rule(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    rule_id: uuid.UUID,
) -> AlertRule | None:
    result = await session.execute(
        select(AlertRule).where(AlertRule.workspace_id == workspace_id, AlertRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def create_alert_rule(session: AsyncSession, rule: AlertRule) -> AlertRule:
    session.add(rule)
    await session.flush()
    return rule


async def get_alert_event_for_rule_signal(
    session: AsyncSession,
    rule_id: uuid.UUID,
    signal_id: uuid.UUID,
) -> AlertEvent | None:
    result = await session.execute(
        select(AlertEvent).where(
            AlertEvent.rule_id == rule_id,
            AlertEvent.signal_id == signal_id,
        )
    )
    return result.scalar_one_or_none()


async def create_alert_event(session: AsyncSession, event: AlertEvent) -> AlertEvent:
    session.add(event)
    await session.flush()
    return event


async def list_alert_events(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    rule_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[AlertEvent]:
    statement = select(AlertEvent).join(AlertRule, AlertEvent.rule_id == AlertRule.id).where(
        AlertRule.workspace_id == workspace_id
    )
    if rule_id is not None:
        statement = statement.where(AlertEvent.rule_id == rule_id)
    if status is not None:
        statement = statement.where(AlertEvent.status == status)
    statement = statement.order_by(AlertEvent.triggered_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())

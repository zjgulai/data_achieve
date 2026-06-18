from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.intelligence import IntelligenceItem
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.alerts import (
    create_alert_event,
    get_alert_event,
    get_alert_event_for_rule_signal,
    get_alert_rule,
    list_alert_events,
    list_alert_rules,
)
from data_intelligence_hub.repositories.alerts import (
    create_alert_rule as create_alert_rule_record,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.schemas.alert import AlertRuleCreateRequest, AlertRuleUpdateRequest
from data_intelligence_hub.services.exceptions import (
    AlertEventNotFoundError,
    AlertRuleNotFoundError,
    ProjectNotFoundError,
)
from data_intelligence_hub.services.notification_service import create_in_app_notification


async def get_alert_rules(
    session: AsyncSession,
    workspace: Workspace,
    enabled: bool | None = None,
) -> list[AlertRule]:
    return await list_alert_rules(session, workspace.id, enabled=enabled)


async def create_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AlertRuleCreateRequest,
) -> AlertRule:
    if payload.project_id is not None:
        project = await get_project(session, workspace.id, payload.project_id)
        if project is None:
            raise ProjectNotFoundError
    rule = AlertRule(
        workspace_id=workspace.id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        signal_type=payload.signal_type,
        condition=payload.condition,
        channel=payload.channel,
        enabled=payload.enabled,
    )
    await create_alert_rule_record(session, rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    rule_id: uuid.UUID,
    payload: AlertRuleUpdateRequest,
) -> AlertRule:
    rule = await get_alert_rule(session, workspace.id, rule_id)
    if rule is None:
        raise AlertRuleNotFoundError
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("project_id") is not None:
        project = await get_project(session, workspace.id, updates["project_id"])
        if project is None:
            raise ProjectNotFoundError
    if isinstance(updates.get("name"), str):
        updates["name"] = updates["name"].strip()
    for field, value in updates.items():
        setattr(rule, field, value)
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    rule_id: uuid.UUID,
) -> AlertRule:
    rule = await get_alert_rule(session, workspace.id, rule_id)
    if rule is None:
        raise AlertRuleNotFoundError
    rule.enabled = False
    await session.commit()
    await session.refresh(rule)
    return rule


async def get_alert_events(
    session: AsyncSession,
    workspace: Workspace,
    rule_id: uuid.UUID | None,
    status: str | None,
) -> list[AlertEvent]:
    return await list_alert_events(
        session,
        workspace.id,
        rule_id=rule_id,
        status=status,
    )


async def update_alert_event_status(
    session: AsyncSession,
    workspace: Workspace,
    event_id: uuid.UUID,
    status: str,
) -> AlertEvent:
    event = await get_alert_event(session, workspace.id, event_id)
    if event is None:
        raise AlertEventNotFoundError
    event.status = status
    await session.commit()
    await session.refresh(event)
    return event


async def match_alert_rules_for_signal(
    session: AsyncSession,
    workspace: Workspace,
    signal: Signal,
    intelligence: IntelligenceItem | None,
    deliver_notifications: bool = True,
) -> list[AlertEvent]:
    rules = await list_alert_rules(session, workspace.id, enabled=True)
    project = await get_project(session, workspace.id, signal.project_id)
    context = _match_context(signal, intelligence, project.domain if project else None)
    events: list[AlertEvent] = []
    for rule in rules:
        if rule.project_id is not None and rule.project_id != signal.project_id:
            continue
        if rule.signal_type != "*" and rule.signal_type != signal.signal_type:
            continue
        if not condition_matches(rule.condition, context):
            continue
        existing = await get_alert_event_for_rule_signal(session, rule.id, signal.id)
        if existing is not None:
            continue
        event = AlertEvent(
            rule_id=rule.id,
            signal_id=signal.id,
            status="triggered",
            payload=_event_payload(rule, signal, intelligence, context),
            triggered_at=datetime.now(UTC),
        )
        await create_alert_event(session, event)
        if deliver_notifications and rule.channel in {"in_app", "both"}:
            event.status = "sent"
            event.sent_at = datetime.now(UTC)
            await create_in_app_notification(
                session=session,
                user_id=workspace.owner_id,
                title=f"预警命中：{rule.name}",
                body=f"{signal.signal_type} 命中 {rule.condition.get('field', 'condition')}",
                notification_type="alert",
                reference_type="alert_event",
                reference_id=event.id,
            )
        events.append(event)
    return events


def condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    if not _condition_scope_matches(condition, context):
        return False
    field = condition.get("field")
    operator = condition.get("op")
    expected = condition.get("value")
    if not isinstance(field, str) or not isinstance(operator, str):
        return False
    if field not in context:
        return False
    actual = context[field]
    if operator == "eq":
        return bool(actual == expected)
    if operator == "in":
        return isinstance(expected, list) and actual in expected
    if operator == "gt":
        return _compare_number(actual, expected, lambda left, right: left > right)
    if operator == "gte":
        return _compare_number(actual, expected, lambda left, right: left >= right)
    if operator == "lt":
        return _compare_number(actual, expected, lambda left, right: left < right)
    if operator == "lte":
        return _compare_number(actual, expected, lambda left, right: left <= right)
    return False


def _condition_scope_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    for key in ("source", "dataset_id", "dataset_version_id", "event_type"):
        expected = condition.get(key)
        if expected is None:
            continue
        if context.get(key) != expected:
            return False
    return True


def _compare_number(
    actual: Any,
    expected: Any,
    predicate: Callable[[float, float], bool],
) -> bool:
    if not isinstance(actual, int | float) or not isinstance(expected, int | float):
        return False
    return bool(predicate(float(actual), float(expected)))


def _match_context(
    signal: Signal,
    intelligence: IntelligenceItem | None,
    domain: str | None,
) -> dict[str, Any]:
    metadata = signal.metadata_json if isinstance(signal.metadata_json, dict) else {}
    return {
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "confidence": signal.confidence,
        "delta": signal.delta,
        "delta_ratio": signal.delta_ratio,
        "current_value": signal.current_value,
        "previous_value": signal.previous_value,
        "domain": domain,
        "final_score": intelligence.final_score if intelligence is not None else None,
        "intelligence_type": intelligence.intelligence_type if intelligence is not None else None,
        "status": intelligence.status if intelligence is not None else None,
        "source": metadata.get("source"),
        "dataset_id": metadata.get("dataset_id"),
        "dataset_version_id": metadata.get("dataset_version_id"),
        "drift_event_id": metadata.get("drift_event_id"),
        "event_type": metadata.get("event_type"),
    }


def _event_payload(
    rule: AlertRule,
    signal: Signal,
    intelligence: IntelligenceItem | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rule_name": rule.name,
        "signal_id": str(signal.id),
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "project_id": str(signal.project_id),
        "intelligence_id": str(intelligence.id) if intelligence is not None else None,
        "domain": context.get("domain"),
        "final_score": context.get("final_score"),
        "intelligence_type": context.get("intelligence_type"),
        "source": context.get("source"),
        "dataset_id": context.get("dataset_id"),
        "dataset_version_id": context.get("dataset_version_id"),
        "drift_event_id": context.get("drift_event_id"),
        "event_type": context.get("event_type"),
    }

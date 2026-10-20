from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from data_intelligence_hub.api.deps import SessionDep, WorkspaceDep
from data_intelligence_hub.schemas.alert import (
    AlertEventResponse,
    AlertEventStatusUpdateRequest,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
)
from data_intelligence_hub.services.alert_service import (
    create_alert_rule,
    delete_alert_rule,
    get_alert_events,
    get_alert_rules,
    update_alert_event_status,
    update_alert_rule,
)
from data_intelligence_hub.services.exceptions import (
    AlertEventNotFoundError,
    AlertRuleNotFoundError,
    ProjectNotFoundError,
)

alert_rules_router = APIRouter(tags=["alerts"])
alert_events_router = APIRouter(tags=["alerts"])

@alert_rules_router.get("", response_model=list[AlertRuleResponse])
async def list_alert_rule_items(
    session: SessionDep,
    workspace: WorkspaceDep,
    enabled: Annotated[bool | None, Query()] = None,
) -> list[AlertRuleResponse]:
    rules = await get_alert_rules(session, workspace, enabled=enabled)
    return [AlertRuleResponse.from_model(rule) for rule in rules]

@alert_rules_router.post(
    "",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_rule_item(
    payload: AlertRuleCreateRequest,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> AlertRuleResponse:
    try:
        rule = await create_alert_rule(session, workspace, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return AlertRuleResponse.from_model(rule)

@alert_rules_router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule_item(
    rule_id: uuid.UUID,
    payload: AlertRuleUpdateRequest,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> AlertRuleResponse:
    try:
        rule = await update_alert_rule(session, workspace, rule_id, payload)
    except AlertRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return AlertRuleResponse.from_model(rule)

@alert_rules_router.delete("/{rule_id}", response_model=AlertRuleResponse)
async def delete_alert_rule_item(
    rule_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> AlertRuleResponse:
    try:
        rule = await delete_alert_rule(session, workspace, rule_id)
    except AlertRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return AlertRuleResponse.from_model(rule)

@alert_events_router.get("", response_model=list[AlertEventResponse])
async def list_alert_event_items(
    session: SessionDep,
    workspace: WorkspaceDep,
    rule_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[AlertEventResponse]:
    events = await get_alert_events(
        session,
        workspace,
        rule_id=rule_id,
        status=status_filter,
    )
    return [AlertEventResponse.from_model(event) for event in events]

@alert_events_router.patch("/{event_id}/status", response_model=AlertEventResponse)
async def update_alert_event_status_item(
    event_id: uuid.UUID,
    payload: AlertEventStatusUpdateRequest,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> AlertEventResponse:
    try:
        event = await update_alert_event_status(
            session,
            workspace,
            event_id,
            payload.status,
        )
    except AlertEventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return AlertEventResponse.from_model(event)

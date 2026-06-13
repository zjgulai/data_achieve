from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.notification import (
    EmailChannelStatusResponse,
    EmailChannelTestResponse,
    NotificationReadAllResponse,
    NotificationResponse,
)
from data_intelligence_hub.services.exceptions import NotificationNotFoundError
from data_intelligence_hub.services.notification_service import (
    get_email_channel_status,
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    test_email_channel,
)

router = APIRouter(tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notification_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    is_read: Annotated[bool | None, Query()] = None,
) -> list[NotificationResponse]:
    notifications = await get_user_notifications(session, context.user, is_read=is_read)
    return [NotificationResponse.from_model(notification) for notification in notifications]


@router.get("/email-channel", response_model=EmailChannelStatusResponse)
async def get_email_channel_item(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> EmailChannelStatusResponse:
    _ = context
    return EmailChannelStatusResponse.from_status(get_email_channel_status())


@router.post("/email-channel/test", response_model=EmailChannelTestResponse)
async def test_email_channel_item(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> EmailChannelTestResponse:
    result = await test_email_channel(context.user)
    return EmailChannelTestResponse.from_result(result)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_item_read(
    notification_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> NotificationResponse:
    try:
        notification = await mark_notification_read(session, context.user, notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return NotificationResponse.from_model(notification)


@router.post("/read-all", response_model=NotificationReadAllResponse)
async def mark_all_notification_items_read(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> NotificationReadAllResponse:
    updated_count = await mark_all_notifications_read(session, context.user)
    return NotificationReadAllResponse(updated_count=updated_count)

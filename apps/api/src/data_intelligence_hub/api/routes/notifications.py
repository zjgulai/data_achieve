from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.notification import (
    EmailChannelStatusResponse,
    EmailChannelTestRequest,
    EmailChannelTestResponse,
    EmailProviderLiveGateRequest,
    EmailProviderLiveGateResponse,
    EmailProviderLiveSendReadinessResponse,
    EmailProviderLiveSendRequest,
    EmailProviderLiveSendResponse,
    NotificationReadAllResponse,
    NotificationReadBulkRequest,
    NotificationResponse,
)
from data_intelligence_hub.services.exceptions import (
    EmailChannelTestAuthorizationError,
    EmailChannelTestConfirmationRequiredError,
    EmailProviderLiveGateAuthorizationError,
    EmailProviderLiveGateConfirmationRequiredError,
    EmailProviderLiveGateRunNotFoundError,
    EmailProviderLiveSendAuthorizationError,
    EmailProviderLiveSendConfirmationRequiredError,
    EmailProviderLiveSendIdempotencyRequiredError,
    NotificationNotFoundError,
)
from data_intelligence_hub.services.notification_service import (
    execute_email_provider_live_send_gate,
    get_email_channel_status,
    get_email_provider_live_send_readiness,
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    mark_notifications_read,
    prepare_email_provider_live_gate,
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
    payload: EmailChannelTestRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EmailChannelTestResponse:
    try:
        result = await test_email_channel(
            session=session,
            workspace=context.workspace,
            user=context.user,
            authorized=payload.authorized,
            confirm_send=payload.confirm_send,
            idempotency_key=idempotency_key,
        )
    except (
        EmailChannelTestAuthorizationError,
        EmailChannelTestConfirmationRequiredError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return EmailChannelTestResponse.from_result(result)


@router.post(
    "/email-channel/provider-live-gate",
    response_model=EmailProviderLiveGateResponse,
)
async def prepare_email_provider_live_gate_item(
    payload: EmailProviderLiveGateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EmailProviderLiveGateResponse:
    try:
        result = await prepare_email_provider_live_gate(
            session=session,
            workspace=context.workspace,
            user=context.user,
            authorized=payload.authorized,
            confirm_prepare=payload.confirm_prepare,
            operation=payload.operation,
            recipient_email=payload.recipient_email,
            max_provider_calls=payload.max_provider_calls,
            expires_at=payload.expires_at,
            note=payload.note,
            idempotency_key=idempotency_key,
        )
    except (
        EmailProviderLiveGateAuthorizationError,
        EmailProviderLiveGateConfirmationRequiredError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return EmailProviderLiveGateResponse.from_result(result)


@router.get(
    "/email-channel/live-send-readiness",
    response_model=EmailProviderLiveSendReadinessResponse,
)
async def get_email_provider_live_send_readiness_item(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> EmailProviderLiveSendReadinessResponse:
    _ = context
    return EmailProviderLiveSendReadinessResponse.from_readiness(
        get_email_provider_live_send_readiness()
    )


@router.post(
    "/email-channel/live-send",
    response_model=EmailProviderLiveSendResponse,
)
async def execute_email_provider_live_send_item(
    payload: EmailProviderLiveSendRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EmailProviderLiveSendResponse:
    try:
        result = await execute_email_provider_live_send_gate(
            session=session,
            workspace=context.workspace,
            user=context.user,
            authorized=payload.authorized,
            confirm_send=payload.confirm_send,
            gate_run_id=payload.gate_run_id,
            approval_id=payload.approval_id,
            operation=payload.operation,
            recipient_email=payload.recipient_email,
            idempotency_key=idempotency_key,
        )
    except (
        EmailProviderLiveSendAuthorizationError,
        EmailProviderLiveSendConfirmationRequiredError,
        EmailProviderLiveSendIdempotencyRequiredError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except EmailProviderLiveGateRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return EmailProviderLiveSendResponse.from_result(result)


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


@router.post("/read-bulk", response_model=NotificationReadAllResponse)
async def mark_notification_items_read(
    payload: NotificationReadBulkRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> NotificationReadAllResponse:
    updated_count = await mark_notifications_read(
        session=session,
        user=context.user,
        notification_ids=payload.notification_ids,
    )
    return NotificationReadAllResponse(updated_count=updated_count)

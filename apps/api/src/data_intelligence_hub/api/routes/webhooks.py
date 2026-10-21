"""出站 Webhook 管理。

创建时返回一次签名密钥；列表与详情不再返回密钥。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.models.webhook import WebhookDelivery
from data_intelligence_hub.schemas.webhook import (
    CreatedWebhookResponse,
    CreateWebhookRequest,
    WebhookDeliveryResponse,
    WebhookEndpointResponse,
)
from data_intelligence_hub.services.webhook_service import (
    WebhookError,
    create_endpoint,
    delete_endpoint,
    list_endpoints,
)

router = APIRouter(tags=["webhooks"])


@router.post("", response_model=CreatedWebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook_endpoint(
    payload: CreateWebhookRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> CreatedWebhookResponse:
    if context.workspace.owner_id != context.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="webhook_owner_required",
        )
    try:
        endpoint = await create_endpoint(
            session,
            workspace_id=context.workspace.id,
            url=payload.url,
            description=payload.description,
        )
    except WebhookError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return CreatedWebhookResponse(
        **WebhookEndpointResponse.model_validate(endpoint).model_dump(),
        secret=endpoint.secret,
    )


@router.get("", response_model=list[WebhookEndpointResponse])
async def list_webhook_endpoints(
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> list[WebhookEndpointResponse]:
    rows = await list_endpoints(session, context.workspace.id)
    return [WebhookEndpointResponse.model_validate(row) for row in rows]


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_endpoint(
    endpoint_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> None:
    if context.workspace.owner_id != context.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="webhook_owner_required",
        )
    removed = await delete_endpoint(session, context.workspace.id, endpoint_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="webhook_endpoint_not_found"
        )


@router.get("/{endpoint_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    endpoint_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
    limit: int = 50,
) -> list[WebhookDeliveryResponse]:
    rows = await session.execute(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.endpoint_id == endpoint_id,
            WebhookDelivery.workspace_id == context.workspace.id,
        )
        .order_by(WebhookDelivery.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return [WebhookDeliveryResponse.model_validate(row) for row in rows.scalars().all()]
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateWebhookRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=200)


class WebhookEndpointResponse(BaseModel):
    """列表视图。永不包含签名密钥。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    description: str | None
    enabled: bool
    created_at: datetime


class CreatedWebhookResponse(WebhookEndpointResponse):
    """创建响应。secret 只在这里出现一次。"""

    secret: str


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    status: str
    attempts: int
    response_status: int | None
    last_error: str | None
    payload: dict[str, Any]
    created_at: datetime
    delivered_at: datetime | None
"""出站 Webhook。

工作区登记回调地址与签名密钥。事件发生时创建投递行，
按 HMAC-SHA256 签名推送给外部系统。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class WebhookEndpoint(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhook_endpoints"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebhookDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhook_deliveries"

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhook_endpoints.id"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
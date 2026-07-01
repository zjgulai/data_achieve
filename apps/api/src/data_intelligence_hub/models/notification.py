from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship()


class EmailChannelTestRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_channel_test_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120))
    status_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_scope: Mapped[str | None] = mapped_column(String(80))
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship()
    user: Mapped[User] = relationship()


class EmailProviderLiveGateRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_provider_live_gate_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    max_provider_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    request_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decision_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_call_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    email_send_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_scope: Mapped[str | None] = mapped_column(String(80))
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship()
    user: Mapped[User] = relationship()


class EmailProviderLiveSendRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_provider_live_send_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    gate_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_provider_live_gate_runs.id"),
        nullable=False,
    )
    approval_id: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120))
    status_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    request_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decision_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_call_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    email_send_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    send_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    live_approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recipient_allowlisted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_scope: Mapped[str | None] = mapped_column(String(80))
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship()
    user: Mapped[User] = relationship()
    gate_run: Mapped[EmailProviderLiveGateRun] = relationship()

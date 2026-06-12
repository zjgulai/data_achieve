from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.workspace import Workspace


class AlertRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alert_rules"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    condition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project | None] = relationship()


class AlertEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alert_events"

    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alert_rules.id"), nullable=False)
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="triggered", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rule: Mapped[AlertRule] = relationship()
    signal: Mapped[Signal] = relationship()

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.entity import Entity
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.raw_record import RawRecord
    from data_intelligence_hub.models.signal import Signal
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace


class IntelligenceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intelligence_items"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    intelligence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False)
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(10), nullable=False)
    domain: Mapped[str] = mapped_column(String(30), nullable=False)

    workspace: Mapped[Workspace] = relationship()
    project: Mapped[Project] = relationship()
    evidences: Mapped[list[Evidence]] = relationship(
        back_populates="intelligence",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list[IntelligenceFeedback]] = relationship(
        back_populates="intelligence",
        cascade="all, delete-orphan",
    )


class Evidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidences"

    intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_items.id"),
        nullable=False,
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_records.id"))
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    highlighted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    intelligence: Mapped[IntelligenceItem] = relationship(back_populates="evidences")
    signal: Mapped[Signal | None] = relationship()
    entity: Mapped[Entity | None] = relationship()
    raw_record: Mapped[RawRecord | None] = relationship()


class IntelligenceFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "intelligence_feedback"

    intelligence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intelligence_items.id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    intelligence: Mapped[IntelligenceItem] = relationship(back_populates="feedback_items")
    user: Mapped[User] = relationship()

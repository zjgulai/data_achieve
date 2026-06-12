from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.entity import Entity, EntitySnapshot
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.workspace import Workspace


class Signal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signals"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_snapshots.id"),
        nullable=False,
    )
    current_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_snapshots.id"),
        nullable=False,
    )
    current_value: Mapped[float | None] = mapped_column(Float)
    previous_value: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float)
    delta_ratio: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="signals")
    project: Mapped[Project] = relationship(back_populates="signals")
    entity: Mapped[Entity] = relationship(back_populates="signals")
    previous_snapshot: Mapped[EntitySnapshot] = relationship(
        foreign_keys=[previous_snapshot_id],
    )
    current_snapshot: Mapped[EntitySnapshot] = relationship(
        foreign_keys=[current_snapshot_id],
    )

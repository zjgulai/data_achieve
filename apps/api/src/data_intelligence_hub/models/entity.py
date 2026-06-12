from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.raw_record import RawRecord
    from data_intelligence_hub.models.signal import Signal
    from data_intelligence_hub.models.workspace import Workspace


class Entity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "entity_type",
            "external_id",
            name="uq_entities_workspace_type_external",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str] = mapped_column(String(30), nullable=False)
    latest_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity_snapshots.id", use_alter=True),
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="entities")
    project: Mapped[Project] = relationship(back_populates="entities")
    latest_snapshot: Mapped[EntitySnapshot | None] = relationship(
        foreign_keys=[latest_snapshot_id],
        post_update=True,
    )
    snapshots: Mapped[list[EntitySnapshot]] = relationship(
        back_populates="entity",
        foreign_keys="EntitySnapshot.entity_id",
    )
    signals: Mapped[list[Signal]] = relationship(back_populates="entity")


class EntitySnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "entity_snapshots"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id"), nullable=False)
    raw_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_records.id"), nullable=False)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entity: Mapped[Entity] = relationship(
        back_populates="snapshots",
        foreign_keys=[entity_id],
    )
    raw_record: Mapped[RawRecord] = relationship(back_populates="entity_snapshots")

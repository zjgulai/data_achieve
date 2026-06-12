from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.raw_record import RawRecord
    from data_intelligence_hub.models.task import CollectionTask
    from data_intelligence_hub.models.workspace import Workspace


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="sources")
    project: Mapped[Project] = relationship(back_populates="sources")
    collection_task: Mapped[CollectionTask | None] = relationship(
        back_populates="source",
        uselist=False,
    )
    raw_records: Mapped[list[RawRecord]] = relationship(back_populates="source")

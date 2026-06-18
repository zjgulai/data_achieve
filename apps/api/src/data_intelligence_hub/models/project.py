from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.dataset import Dataset
    from data_intelligence_hub.models.entity import Entity
    from data_intelligence_hub.models.raw_record import RawRecord
    from data_intelligence_hub.models.signal import Signal
    from data_intelligence_hub.models.source import Source
    from data_intelligence_hub.models.task import CollectionTask
    from data_intelligence_hub.models.user import User
    from data_intelligence_hub.models.workspace import Workspace


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    owner: Mapped[User] = relationship(
        back_populates="owned_projects",
        foreign_keys=[owner_id],
    )
    sources: Mapped[list[Source]] = relationship(back_populates="project")
    collection_tasks: Mapped[list[CollectionTask]] = relationship(back_populates="project")
    raw_records: Mapped[list[RawRecord]] = relationship(back_populates="project")
    entities: Mapped[list[Entity]] = relationship(back_populates="project")
    signals: Mapped[list[Signal]] = relationship(back_populates="project")
    datasets: Mapped[list[Dataset]] = relationship(back_populates="project")

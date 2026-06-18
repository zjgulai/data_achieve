from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from data_intelligence_hub.models.dataset import Dataset
    from data_intelligence_hub.models.entity import Entity
    from data_intelligence_hub.models.project import Project
    from data_intelligence_hub.models.raw_record import RawRecord
    from data_intelligence_hub.models.signal import Signal
    from data_intelligence_hub.models.source import Source
    from data_intelligence_hub.models.task import CollectionTask
    from data_intelligence_hub.models.user import User


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    owner: Mapped[User] = relationship(
        back_populates="owned_workspaces",
        foreign_keys=[owner_id],
    )
    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list[Project]] = relationship(back_populates="workspace")
    sources: Mapped[list[Source]] = relationship(back_populates="workspace")
    collection_tasks: Mapped[list[CollectionTask]] = relationship(back_populates="workspace")
    raw_records: Mapped[list[RawRecord]] = relationship(back_populates="workspace")
    entities: Mapped[list[Entity]] = relationship(back_populates="workspace")
    signals: Mapped[list[Signal]] = relationship(back_populates="workspace")
    datasets: Mapped[list[Dataset]] = relationship(back_populates="workspace")


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_user"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="workspace_memberships")

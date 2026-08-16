from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlatformCredentialBundle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_credential_bundles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider_id",
            name="uq_platform_credential_bundles_workspace_provider",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    configured_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    key_version: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

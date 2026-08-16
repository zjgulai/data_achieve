from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle


async def list_platform_credential_bundles(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[PlatformCredentialBundle]:
    result = await session.execute(
        select(PlatformCredentialBundle)
        .where(PlatformCredentialBundle.workspace_id == workspace_id)
        .order_by(PlatformCredentialBundle.provider_id.asc())
    )
    return list(result.scalars().all())


async def get_platform_credential_bundle(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    provider_id: str,
) -> PlatformCredentialBundle | None:
    result = await session.execute(
        select(PlatformCredentialBundle).where(
            PlatformCredentialBundle.workspace_id == workspace_id,
            PlatformCredentialBundle.provider_id == provider_id,
        )
    )
    return result.scalar_one_or_none()


async def get_platform_credential_bundle_by_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    bundle_id: uuid.UUID,
) -> PlatformCredentialBundle | None:
    result = await session.execute(
        select(PlatformCredentialBundle).where(
            PlatformCredentialBundle.workspace_id == workspace_id,
            PlatformCredentialBundle.id == bundle_id,
        )
    )
    return result.scalar_one_or_none()

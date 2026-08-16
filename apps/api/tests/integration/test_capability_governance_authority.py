from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityGovernanceMembership,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernancePermission,
)
from data_intelligence_hub.services.capability_governance.authority import (
    CapabilityGovernanceForbiddenError,
    require_governance_permission,
)


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


async def _add_user(session: AsyncSession, *, name: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{name}@example.com",
        password_hash="not-a-real-secret",
        name=name,
        status="active",
    )
    session.add(user)
    await session.flush()
    return user


async def _add_membership(
    session: AsyncSession,
    *,
    name: str,
    can_read: bool,
    can_review: bool,
    can_publish: bool,
    is_active: bool = True,
) -> User:
    user = await _add_user(session, name=name)
    session.add(
        CapabilityGovernanceMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            can_read=can_read,
            can_review=can_review,
            can_publish=can_publish,
            is_active=is_active,
        )
    )
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_workspace_owner_without_governance_membership_is_denied_before_lookup(
    session: AsyncSession,
) -> None:
    owner = await _add_user(session, name="workspace-owner")
    session.add(
        Workspace(
            id=uuid.uuid4(),
            name="Owner workspace",
            slug="owner-workspace",
            owner_id=owner.id,
        )
    )
    await session.commit()
    resource_lookup_count = 0

    async def guarded_resource_lookup() -> None:
        nonlocal resource_lookup_count
        await require_governance_permission(
            session,
            owner.id,
            CapabilityGovernancePermission.READ,
        )
        resource_lookup_count += 1

    with pytest.raises(
        CapabilityGovernanceForbiddenError,
        match="capability_governance_forbidden",
    ):
        await guarded_resource_lookup()

    assert resource_lookup_count == 0


@pytest.mark.asyncio
async def test_read_review_and_publish_permissions_are_independent(
    session: AsyncSession,
) -> None:
    reader = await _add_membership(
        session,
        name="reader",
        can_read=True,
        can_review=False,
        can_publish=False,
    )
    reviewer = await _add_membership(
        session,
        name="reviewer",
        can_read=True,
        can_review=True,
        can_publish=False,
    )
    publisher = await _add_membership(
        session,
        name="publisher",
        can_read=True,
        can_review=False,
        can_publish=True,
    )

    assert (
        await require_governance_permission(
            session,
            reader.id,
            CapabilityGovernancePermission.READ,
        )
    ).user_id == reader.id
    assert (
        await require_governance_permission(
            session,
            reviewer.id,
            CapabilityGovernancePermission.READ,
        )
    ).user_id == reviewer.id
    assert (
        await require_governance_permission(
            session,
            publisher.id,
            CapabilityGovernancePermission.READ,
        )
    ).user_id == publisher.id

    with pytest.raises(CapabilityGovernanceForbiddenError):
        await require_governance_permission(
            session,
            reader.id,
            CapabilityGovernancePermission.REVIEW,
        )
    with pytest.raises(CapabilityGovernanceForbiddenError):
        await require_governance_permission(
            session,
            reviewer.id,
            CapabilityGovernancePermission.PUBLISH,
        )
    with pytest.raises(CapabilityGovernanceForbiddenError):
        await require_governance_permission(
            session,
            publisher.id,
            CapabilityGovernancePermission.REVIEW,
        )

    assert (
        await require_governance_permission(
            session,
            reviewer.id,
            CapabilityGovernancePermission.REVIEW,
        )
    ).user_id == reviewer.id
    assert (
        await require_governance_permission(
            session,
            publisher.id,
            CapabilityGovernancePermission.PUBLISH,
        )
    ).user_id == publisher.id


@pytest.mark.asyncio
async def test_missing_and_inactive_memberships_fail_closed(
    session: AsyncSession,
) -> None:
    missing = await _add_user(session, name="missing")
    inactive = await _add_membership(
        session,
        name="inactive",
        can_read=True,
        can_review=True,
        can_publish=True,
        is_active=False,
    )

    for user_id in (missing.id, inactive.id):
        with pytest.raises(CapabilityGovernanceForbiddenError):
            await require_governance_permission(
                session,
                user_id,
                CapabilityGovernancePermission.READ,
            )

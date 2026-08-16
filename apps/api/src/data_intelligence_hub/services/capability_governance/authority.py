from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.capability_governance import (
    CapabilityGovernanceMembership,
)
from data_intelligence_hub.repositories.capability_governance import (
    get_active_governance_membership,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernancePermission,
)


class CapabilityGovernanceForbiddenError(PermissionError):
    code = "capability_governance_forbidden"

    def __init__(self, permission: CapabilityGovernancePermission) -> None:
        super().__init__(self.code)
        self.permission = permission


def _has_permission(
    membership: CapabilityGovernanceMembership,
    permission: CapabilityGovernancePermission,
) -> bool:
    match permission:
        case CapabilityGovernancePermission.READ:
            return membership.can_read
        case CapabilityGovernancePermission.REVIEW:
            return membership.can_review
        case CapabilityGovernancePermission.PUBLISH:
            return membership.can_publish


async def require_governance_permission(
    session: AsyncSession,
    user_id: uuid.UUID,
    permission: CapabilityGovernancePermission,
) -> CapabilityGovernanceMembership:
    membership = await get_active_governance_membership(session, user_id)
    if membership is None or not _has_permission(membership, permission):
        raise CapabilityGovernanceForbiddenError(permission)
    return membership


__all__ = [
    "CapabilityGovernanceForbiddenError",
    "require_governance_permission",
]

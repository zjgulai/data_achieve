from __future__ import annotations

import uuid

from data_intelligence_hub.api.routes.quick_collect import (
    QuickCollectRequest,
    QuickCollectResponse,
    quick_collect,
)
from data_intelligence_hub.core.database import async_session_factory


async def collect_capability(
    endpoint_type: str,
    project_id: uuid.UUID,
    params: dict[str, object],
) -> QuickCollectResponse:
    body = QuickCollectRequest(
        project_id=project_id,
        endpoint_type=endpoint_type,
        params=params,
    )
    async with async_session_factory() as session:
        return await quick_collect(body, session)

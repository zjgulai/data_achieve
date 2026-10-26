"""MCP 采集入口。

直接调用服务层，不经过 HTTP 路由。
这样 MCP 不再依赖 api.routes，也避免 quick-collect 切到 fail-closed 后
进程内回环请求因缺 token 而 401。
"""

from __future__ import annotations

import uuid

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.repositories.workspaces import get_workspace_by_id
from data_intelligence_hub.services.quick_collect_service import (
    QuickCollectRequest,
    QuickCollectResponse,
    run_quick_collect,
    to_response,
)

__all__ = ["collect_capability"]


async def collect_capability(
    endpoint_type: str,
    project_id: uuid.UUID,
    params: dict[str, object],
    *,
    workspace_id: uuid.UUID | None = None,
    tool_call: dict[str, object] | None = None,
) -> QuickCollectResponse:
    """执行一次采集。

    传入 ``workspace_id`` 时使用该工作区。它属于项目密钥身份。
    不传时回退 demo workspace，保持全局 token 的既有行为。
    传入但查不到时返回 ``workspace_not_found``，不静默回退。
    """
    body = QuickCollectRequest(
        project_id=project_id,
        endpoint_type=endpoint_type,
        params=params,
        tool_call=tool_call,
    )
    async with async_session_factory() as session:
        workspace = None
        if workspace_id is not None:
            workspace = await get_workspace_by_id(session, workspace_id)
            if workspace is None:
                raise ValueError("workspace_not_found")
        outcome = await run_quick_collect(session, body, workspace=workspace)
        return to_response(outcome)

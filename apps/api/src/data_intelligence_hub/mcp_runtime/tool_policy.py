"""MCP 工具级授权（过渡期模块，deprecated）。

.. deprecated:: N1
   统一授权入口已迁移到 :mod:`data_intelligence_hub.mcp_runtime.access_control`
   的 ``governed_mcp_tool`` / ``assert_tool_allowed``。本模块仅保留
   ``enforce_tool_policy`` / ``enforce_quota`` 供 server.py 过渡期接线
   （Task 3 完成后整体删除）。

语义已按 N1 翻转：空白名单拒绝全部工具，白名单外的工具拒绝。
判定不命中一律抛 ValueError，错误码给 MCP 客户端。
"""

from __future__ import annotations

from mcp.server.mcpserver import Context

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.access_control import assert_tool_allowed
from data_intelligence_hub.mcp_runtime.auth import project_api_key_context
from data_intelligence_hub.repositories.project_api_keys import (
    consume_daily_quota,
    find_by_id,
)


def tool_allowed(tool_name: str, allowlist: list[str]) -> bool:
    """显式白名单判定。空白名单拒绝全部（deprecated：用 access_control.assert_tool_allowed）。"""
    return assert_tool_allowed(tool_name, allowlist)


async def enforce_tool_policy(context: Context, tool_name: str) -> None:
    """deprecated：过渡期供 server.py 调用；Task 3 接线 governed_mcp_tool 后删除。"""
    identity = project_api_key_context(context)
    if identity is None:
        return
    async with async_session_factory() as session:
        key = await find_by_id(session, identity.key_id)
    if key is None or key.revoked_at is not None:
        raise ValueError("project_key_not_found")
    allowlist = [str(item) for item in (key.tool_allowlist or [])]
    if not tool_allowed(tool_name, allowlist):
        raise ValueError("tool_not_allowed")


async def enforce_quota(context: Context) -> None:
    """项目密钥的日额度硬拦。超额度拒绝；全局 token 不计数。

    deprecated：过渡期供 server.py 调用；Task 3 接线 governed_mcp_tool 后删除。
    """
    identity = project_api_key_context(context)
    if identity is None:
        return
    async with async_session_factory() as session:
        allowed = await consume_daily_quota(session, identity.key_id)
        await session.commit()
    if not allowed:
        raise ValueError("quota_exceeded")

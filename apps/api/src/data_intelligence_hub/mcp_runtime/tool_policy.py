"""MCP 工具级授权。

项目密钥调用按密钥的 tool_allowlist 判定：
- 贵工具（deep_research）默认关，只有显式写进白名单才放行。
- 便宜工具默认开；白名单非空时按白名单收窄。

全局 token 路径没有项目密钥身份，不设限（运维身份）。
判定不命中一律抛 ValueError，错误码给 MCP 客户端。
"""

from __future__ import annotations

from mcp.server.mcpserver import Context

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.auth import project_api_key_context
from data_intelligence_hub.repositories.project_api_keys import (
    consume_daily_quota,
    find_by_id,
)

EXPENSIVE_TOOLS = frozenset({"deep_research", "deep_research_start"})


def tool_allowed(tool_name: str, allowlist: list[str]) -> bool:
    if tool_name in EXPENSIVE_TOOLS:
        return tool_name in allowlist
    if not allowlist:
        return True
    return tool_name in allowlist


async def enforce_tool_policy(context: Context, tool_name: str) -> None:
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
    """项目密钥的日额度硬拦。超额度拒绝；全局 token 不计数。"""
    identity = project_api_key_context(context)
    if identity is None:
        return
    async with async_session_factory() as session:
        allowed = await consume_daily_quota(session, identity.key_id)
        await session.commit()
    if not allowed:
        raise ValueError("quota_exceeded")
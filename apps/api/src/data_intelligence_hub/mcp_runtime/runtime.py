from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from time import perf_counter

import structlog
from mcp.server.mcpserver import Context

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.mcp_runtime.auth import (
    ProjectApiKeyContext,
    project_api_key_context,
)
from data_intelligence_hub.mcp_runtime.governance import (
    GovernanceCall,
    GovernanceLimits,
    MCPGovernance,
    MCPGovernanceError,
)

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_mcp_governance() -> MCPGovernance:
    settings = get_settings()
    return MCPGovernance(
        GovernanceLimits(
            rate_per_minute=settings.mcp_rate_per_minute,
            concurrent_calls=settings.mcp_concurrent_calls,
            daily_collects=settings.mcp_daily_collects,
        )
    )


def _request_token(context: Context) -> str:
    headers = context.headers or {}
    authorization = headers.get("authorization", "")
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization.removeprefix(prefix)
    return "in-memory-client"


def project_identity(context: Context) -> ProjectApiKeyContext | None:
    """返回项目密钥身份。全局 token 与本地调用返回 None。"""
    return project_api_key_context(context)


def require_project_access(
    context: Context,
    project_id: uuid.UUID,
) -> uuid.UUID:
    """校验调用项目。

    项目密钥只能访问自己的项目。越界时返回 ``project_mismatch``。
    没有项目身份时原样返回，保持全局 token 的既有行为。
    """
    identity = project_identity(context)
    if identity is not None and identity.project_id != project_id:
        raise ValueError("project_mismatch")
    return project_id


def project_workspace_id(context: Context) -> uuid.UUID | None:
    """返回项目密钥绑定的工作区。全局 token 返回 None。"""
    identity = project_identity(context)
    return identity.workspace_id if identity is not None else None


def project_filter(context: Context) -> uuid.UUID | None:
    """返回按项目过滤用的标识。全局 token 返回 None，表示不过滤。"""
    identity = project_identity(context)
    return identity.project_id if identity is not None else None


def _governance_token(context: Context, identity: ProjectApiKeyContext | None) -> str:
    """返回治理用的 token 标识。

    项目密钥按 ``key_id`` 计数。不同项目互不占用额度。
    全局 token 沿用请求头里的 token。
    """
    if identity is not None:
        return f"project:{identity.key_id}"
    return _request_token(context)


@asynccontextmanager
async def governed_tool(
    context: Context,
    tool_name: str,
    *,
    endpoint_type: str | None = None,
    is_collect: bool = False,
) -> AsyncIterator[GovernanceCall]:
    started = perf_counter()
    governance = get_mcp_governance()
    identity = project_identity(context)
    if identity is not None and not identity.allows_tool(tool_name):
        logger.warning(
            "mcp_call_rejected",
            token_id=str(identity.key_id),
            tool_name=tool_name,
            endpoint_type=endpoint_type,
            reason="tool_not_allowed",
        )
        raise ValueError("tool_not_allowed")
    token = _governance_token(context, identity)
    daily_limit = identity.daily_collect_quota if identity is not None else None
    try:
        async with governance.call(
            token,
            tool_name,
            is_collect=is_collect,
            daily_collect_limit=daily_limit,
        ) as call:
            yield call
    except MCPGovernanceError as exc:
        logger.warning(
            "mcp_call_rejected",
            token_id=exc.token_id,
            tool_name=tool_name,
            endpoint_type=endpoint_type,
            reason=exc.code,
        )
        raise ValueError(exc.code) from exc
    except Exception as exc:
        logger.info(
            "mcp_call_completed",
            token_id=call.token_id,
            tool_name=tool_name,
            endpoint_type=endpoint_type,
            outcome="failed",
            error_type=type(exc).__name__,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        raise
    else:
        logger.info(
            "mcp_call_completed",
            token_id=call.token_id,
            tool_name=tool_name,
            endpoint_type=endpoint_type,
            outcome="succeeded",
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )

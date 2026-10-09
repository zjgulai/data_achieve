from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from time import perf_counter

import structlog
from mcp.server.mcpserver import Context

from data_intelligence_hub.core.config import get_settings
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
    try:
        async with governance.call(
            _request_token(context),
            tool_name,
            is_collect=is_collect,
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

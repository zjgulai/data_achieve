from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from data_intelligence_hub.mcp_runtime.governance import (
    GovernanceLimits,
    MCPGovernance,
    MCPGovernanceError,
)


@pytest.mark.anyio
async def test_governance_enforces_rate_limit_without_storing_token() -> None:
    now = datetime(2026, 10, 9, tzinfo=UTC)
    governance = MCPGovernance(
        GovernanceLimits(rate_per_minute=2, concurrent_calls=2, daily_collects=3),
        now=lambda: now,
    )

    async with governance.call("secret-token", "list_platforms") as first:
        assert first.token_id != "secret-token"
        assert len(first.token_id) == 12
    async with governance.call("secret-token", "list_platforms"):
        pass

    with pytest.raises(MCPGovernanceError, match="mcp_rate_limit_exceeded"):
        async with governance.call("secret-token", "list_platforms"):
            pass
    assert "secret-token" not in repr(governance.snapshot())


@pytest.mark.anyio
async def test_governance_releases_concurrency_and_resets_daily_budget() -> None:
    current = datetime(2026, 10, 9, tzinfo=UTC)
    governance = MCPGovernance(
        GovernanceLimits(rate_per_minute=10, concurrent_calls=1, daily_collects=1),
        now=lambda: current,
    )

    async with governance.call("token", "collect", is_collect=True):
        with pytest.raises(MCPGovernanceError, match="mcp_concurrency_limit_exceeded"):
            async with governance.call("token", "collect", is_collect=True):
                pass

    with pytest.raises(MCPGovernanceError, match="mcp_daily_collect_budget_exceeded"):
        async with governance.call("token", "collect", is_collect=True):
            pass

    current += timedelta(days=1)
    async with governance.call("token", "collect", is_collect=True):
        pass

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import anyio


@dataclass(frozen=True, slots=True)
class GovernanceLimits:
    rate_per_minute: int
    concurrent_calls: int
    daily_collects: int


@dataclass(frozen=True, slots=True)
class GovernanceCall:
    token_id: str
    tool_name: str


@dataclass(slots=True)
class _TokenState:
    calls: deque[datetime]
    active: int = 0
    collect_day: date | None = None
    collect_count: int = 0


class MCPGovernanceError(RuntimeError):
    def __init__(self, code: str, token_id: str) -> None:
        super().__init__(code)
        self.code = code
        self.token_id = token_id


class MCPGovernance:
    def __init__(
        self,
        limits: GovernanceLimits,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._limits = limits
        self._now = now or (lambda: datetime.now(UTC))
        self._states: defaultdict[str, _TokenState] = defaultdict(
            lambda: _TokenState(calls=deque())
        )
        self._lock = anyio.Lock()

    @asynccontextmanager
    async def call(
        self,
        token: str,
        tool_name: str,
        *,
        is_collect: bool = False,
        daily_collect_limit: int | None = None,
    ) -> AsyncIterator[GovernanceCall]:
        """执行一次受治理的调用。

        ``daily_collect_limit`` 是项目密钥的每日采集额度。
        它只收紧上限，不放宽全局上限。
        """
        token_id = hashlib.sha256(token.encode()).hexdigest()[:12]
        daily_limit = self._limits.daily_collects
        daily_code = "mcp_daily_collect_budget_exceeded"
        if daily_collect_limit is not None and daily_collect_limit < daily_limit:
            daily_limit = daily_collect_limit
            daily_code = "project_daily_collect_quota_exceeded"
        async with self._lock:
            state = self._states[token_id]
            now = self._now()
            cutoff = now - timedelta(minutes=1)
            while state.calls and state.calls[0] <= cutoff:
                state.calls.popleft()
            if len(state.calls) >= self._limits.rate_per_minute:
                raise MCPGovernanceError("mcp_rate_limit_exceeded", token_id)
            if state.active >= self._limits.concurrent_calls:
                raise MCPGovernanceError("mcp_concurrency_limit_exceeded", token_id)
            if state.collect_day != now.date():
                state.collect_day = now.date()
                state.collect_count = 0
            if is_collect and state.collect_count >= daily_limit:
                raise MCPGovernanceError(daily_code, token_id)
            state.calls.append(now)
            state.active += 1
            if is_collect:
                state.collect_count += 1
        try:
            yield GovernanceCall(token_id=token_id, tool_name=tool_name)
        finally:
            async with self._lock:
                self._states[token_id].active -= 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {
            token_id: {
                "calls": len(state.calls),
                "active": state.active,
                "collect_count": state.collect_count,
            }
            for token_id, state in self._states.items()
        }

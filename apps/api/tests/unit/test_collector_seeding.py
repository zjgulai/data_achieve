"""Tests for `ensure_collectors_seeded`.

Regression guard for the production failure on 2026-10-13: the seeder used to
answer a failed insert with a full `session.rollback()`. That expires every
object in the request's session, so the very next attribute access on an
already-loaded row (``workspace.id`` in ``quick_collect``) triggered a lazy load
outside the async greenlet and the request died with ``MissingGreenlet`` / HTTP
500 — reproducible under concurrency on a cold cache.

These tests use a fake session: they pin the *contract* (failures are contained
in a SAVEPOINT and never roll back the whole session). They do not exercise a
real engine.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from data_intelligence_hub.services import collector_catalog


class _FakeNested:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeNested:
        return self

    async def __aexit__(self, *exc_info: Any) -> bool:
        if self._session.fail_savepoint:
            raise RuntimeError("duplicate key value violates unique constraint")
        return False


class _FakeSession:
    """Minimal stand-in that records which session-level calls were made."""

    def __init__(self, *, fail_savepoint: bool = False) -> None:
        self.fail_savepoint = fail_savepoint
        self.added: list[Any] = []
        self.full_rollback_called = False
        self.savepoints = 0

    def add_all(self, items: list[Any]) -> None:
        self.added.extend(items)

    def begin_nested(self) -> _FakeNested:
        self.savepoints += 1
        return _FakeNested(self)

    async def rollback(self) -> None:
        self.full_rollback_called = True

    async def flush(self) -> None:
        raise AssertionError("ensure_collectors_seeded must not call flush() directly")


def _definitions(*types: str) -> list[collector_catalog.CollectorDefinition]:
    return [
        collector_catalog.CollectorDefinition(
            type=t, name=t, description="", config_schema={"required": []}
        )
        for t in types
    ]


@pytest.mark.asyncio
async def test_seeds_missing_collectors_inside_savepoint():
    session = _FakeSession()
    with (
        patch.object(collector_catalog, "list_collectors", AsyncMock(return_value=[])),
        patch.object(collector_catalog, "COLLECTOR_CATALOG", _definitions("alpha", "beta")),
    ):
        await collector_catalog.ensure_collectors_seeded(session)  # type: ignore[arg-type]

    assert session.savepoints == 1
    assert [c.type for c in session.added] == ["alpha", "beta"]
    assert session.full_rollback_called is False


@pytest.mark.asyncio
async def test_conflicting_insert_does_not_roll_back_the_whole_session():
    """The losing writer must not invalidate objects the caller already loaded."""
    session = _FakeSession(fail_savepoint=True)
    with (
        patch.object(collector_catalog, "list_collectors", AsyncMock(return_value=[])),
        patch.object(collector_catalog, "COLLECTOR_CATALOG", _definitions("alpha")),
    ):
        # Must not raise: the other writer winning the race is expected.
        await collector_catalog.ensure_collectors_seeded(session)  # type: ignore[arg-type]

    assert session.full_rollback_called is False, (
        "a full rollback would expire the caller's loaded objects and cause "
        "MissingGreenlet on the next attribute access"
    )


@pytest.mark.asyncio
async def test_no_write_when_everything_is_already_seeded():
    session = _FakeSession()
    existing = [type("C", (), {"type": "alpha"})()]
    with (
        patch.object(
            collector_catalog, "list_collectors", AsyncMock(return_value=existing)
        ),
        patch.object(collector_catalog, "COLLECTOR_CATALOG", _definitions("alpha")),
    ):
        await collector_catalog.ensure_collectors_seeded(session)  # type: ignore[arg-type]

    assert session.savepoints == 0
    assert session.added == []

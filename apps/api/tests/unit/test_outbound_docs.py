"""Collector docs must show current restrictions independently of historical evidence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from data_intelligence_hub.api.routes.collectors import get_collector_docs
from data_intelligence_hub.core.config import get_settings


@pytest.mark.asyncio
async def test_collector_docs_includes_policy_restriction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    session = AsyncMock()
    rows = MagicMock()
    rows.mappings.return_value = []
    session.execute.return_value = rows
    try:
        docs = await get_collector_docs(session)
        endpoint = next(
            e for g in docs.groups for e in g.endpoints if e.endpoint_type == "aliens_eye_basic"
        )
        assert endpoint.policy_block_reason.startswith("collection_policy_denied:")
        assert endpoint.test_result is None
    finally:
        get_settings.cache_clear()

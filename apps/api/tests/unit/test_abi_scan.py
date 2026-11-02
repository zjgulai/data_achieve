"""Pin the scan helpers before the worker touches Apify.

The expensive parts (network, database) are not tested here. These tests cover
the date/month boundary, NUL stripping, content hashing, and dataset listing
with a mock transport.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

import httpx
import pytest

from data_intelligence_hub.abi.scan import (
    content_hash,
    list_datasets,
    month_start_of,
    strip_nul,
    target_date_of,
)


def test_target_date_uses_beijing_time() -> None:
    # 2026-11-01 20:00 UTC is 2026-11-02 04:00 in Beijing.
    created = datetime(2026, 11, 1, 20, 0, tzinfo=UTC)
    assert target_date_of(created) == date(2026, 11, 2)


def test_month_start_uses_utc() -> None:
    created = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    assert month_start_of(created) == date(2026, 10, 1)


def test_strip_nul_is_recursive() -> None:
    value = {"a": "x\x00y", "b": ["p\x00", {"c": "\x00"}]}
    assert strip_nul(value) == {"a": "xy", "b": ["p", {"c": ""}]}


def test_content_hash_is_stable_across_key_order() -> None:
    left = {"a": 1, "b": 2}
    right = {"b": 2, "a": 1}
    assert (
        content_hash(left)
        == hashlib.sha256(
            json.dumps(left, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).digest()
    )
    assert content_hash(left) == content_hash(right)


def test_content_hash_strips_nul() -> None:
    assert content_hash({"a": "x\x00y"}) == content_hash({"a": "xy"})


@pytest.mark.asyncio
async def test_list_datasets_filters_by_target_date_and_dedupes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        unnamed = request.url.params.get("unnamed")
        offset = request.url.params.get("offset")
        if unnamed == "1" and offset == "0":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "total": 2,
                        "items": [
                            {
                                "id": "d1",
                                "createdAt": "2026-11-01T03:00:00Z",
                                "itemCount": 3,
                            },
                            {
                                "id": "d2",
                                "createdAt": "2026-11-02T03:00:00Z",
                                "itemCount": 4,
                            },
                        ],
                    }
                },
            )
        if unnamed == "0" and offset == "0":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "total": 1,
                        "items": [
                            {
                                "id": "d1",
                                "createdAt": "2026-11-01T03:00:00Z",
                                "itemCount": 3,
                                "name": "named-copy",
                            }
                        ],
                    }
                },
            )
        return httpx.Response(200, json={"data": {"total": 0, "items": []}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        found = await list_datasets(client, "token", date(2026, 11, 1), max_datasets=None)
    assert [item["id"] for item in found] == ["d1"]

"""Commerce tool contract tests."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from data_intelligence_hub.services.tiktok_tools import (
    TOOL_SPECS,
    _canonicalize_commerce_profile,
    _canonicalize_product,
    run_tiktok_tool,
    tiktok_ads_detail,
    tiktok_ads_top,
    tiktok_creator_commerce,
    tiktok_creator_showcase,
    tiktok_product_detail,
    tiktok_product_reviews,
    tiktok_product_search,
    tiktok_video_products,
)

PROJECT_ID = uuid.uuid4()


def _fake_collect_factory(records, calls):
    async def fake_collect(
        project_id, endpoint_type, params, limit, *, role="primary", creator_cookie=None
    ):
        calls.append((endpoint_type, params, role))
        items = records.get(endpoint_type, [])
        return items, {
            "endpoint_type": endpoint_type,
            "task_id": "task-1",
            "run_id": f"run-{len(calls)}",
            "status": "success",
            "records_count": len(items),
            "error": None,
            "role": role,
        }

    return fake_collect


def test_apify_product_raw_is_flattened() -> None:
    record = {
        "_tool_role": "product",
        "raw": {
            "product_id": "p1",
            "product_name": "Breast Pump",
            "real_price": "$454.97 - 926.22",
            "min_price": "$454.97",
            "max_price": "$926.22",
            "product_rating": "4.9",
            "review_count": "253",
            "total_sale_cnt": "1.2K",
            "total_sale_30d_cnt": "192.98K",
            "total_sale_gmv_30d_amt": "$324.98K",
            "region": {"key": "us"},
            "seller": {"seller_id": "s1", "shop_name": "Momcozy"},
            "cover_url": "https://img/cover.webp",
            "is_free_shipping": 1,
        },
    }
    out = _canonicalize_product(record)
    assert out["product_id"] == "p1"
    assert out["region"] == "US"
    assert out["price_amount"] == 454.97
    assert out["max_price_amount"] == 926.22
    assert out["sale_count"] == 1200
    assert out["sale_count_30d"] == 192980
    assert out["gmv_amount_30d"] == 324980.0
    assert out["rating"] == 4.9
    assert out["review_count"] == 253
    assert out["shop_name"] == "Momcozy"
    assert out["free_shipping"] is True


def test_apify_commerce_profile_is_flattened() -> None:
    record = {
        "_tool_role": "commerce_profile",
        "raw": {
            "username": "dealswithty",
            "nickname": "Ty",
            "region": "US",
            "stats": {
                "gmv": {"total": "1098437.17", "currency": "USD"},
                "gpm": {"amount": 41.332},
                "unitsSold": 12428,
                "followers": {"total": 151353},
                "avgViews": {"video": 5022},
                "avgLikes": {"video": 22},
                "avgComments": {"video": 1},
                "avgShares": {"video": 4},
                "engagementRate": {"video": 0.9},
                "avgCommission": {"value": 7.5},
                "postRate": 44.56,
                "rating": "5.0",
                "promotedProducts": 212,
                "totalBrandCollaborations": 48,
                "contentFrequency": {"videos": 187},
            },
        },
    }
    out = _canonicalize_commerce_profile(record)
    assert out["unique_id"] == "dealswithty"
    assert out["follower_count"] == 151353
    assert out["gmv_amount"] == 1098437.17
    assert out["units_sold"] == 12428
    assert out["avg_commission_rate"] == 7.5
    assert out["avg_views"] == 5022
    assert out["promoted_product_count"] == 212


def test_commerce_tools_are_registered() -> None:
    for tool_id in (
        "tiktok_product_search",
        "tiktok_product_detail",
        "tiktok_product_reviews",
        "tiktok_creator_commerce",
    ):
        assert tool_id in TOOL_SPECS


@pytest.mark.asyncio
async def test_product_search_uses_apify_primary(monkeypatch) -> None:
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {"apify_tiktok_shop_search_scraper": [{"product_id": "p1"}]}, calls
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    result = await tiktok_product_search(PROJECT_ID, {"query": "skincare"})
    assert result.status == "success"
    assert result.records_count == 1
    assert calls[0][0] == "apify_tiktok_shop_search_scraper"
    assert calls[0][1]["keyword"] == "skincare"


@pytest.mark.asyncio
async def test_product_search_falls_back_to_tikhub(monkeypatch) -> None:
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {"tikhub_tiktok_shop_search_v2": [{"product_id": "p1"}]}, calls
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    result = await tiktok_product_search(PROJECT_ID, {"query": "skincare"})
    assert result.records_count == 1
    assert [call[0] for call in calls] == [
        "apify_tiktok_shop_search_scraper",
        "tikhub_tiktok_shop_search_v2",
    ]
    assert calls[1][1]["search_word"] == "skincare"


@pytest.mark.asyncio
async def test_product_detail_builds_url_from_id(monkeypatch) -> None:
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {"apify_tiktok_shop_product_detail": [{"product_id": "p1"}]}, calls
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    result = await tiktok_product_detail(PROJECT_ID, {"product_id": "p1"})
    assert result.records_count == 1
    assert calls[0][1]["url"] == "https://shop.tiktok.com/view/product/p1"


@pytest.mark.asyncio
async def test_product_reviews_uses_tikhub(monkeypatch) -> None:
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {"tikhub_tiktok_shop_reviews_v2": [{"review_id": "r1"}]}, calls
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    result = await tiktok_product_reviews(
        PROJECT_ID, {"product_id": "p1", "limit": 5}
    )
    assert result.records_count == 1
    assert calls[0][1]["product_id"] == "p1"
    assert calls[0][1]["region"] == "US"


@pytest.mark.asyncio
async def test_creator_commerce_uses_apify(monkeypatch) -> None:
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {"apify_tiktok_shop_creators": [{"creator_id": "u1"}]}, calls
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    result = await tiktok_creator_commerce(PROJECT_ID, {"handle": "@alice"})
    assert result.records_count == 1
    assert calls[0][1]["username"] == "alice"


@pytest.mark.asyncio
async def test_ads_tools_use_tikhub(monkeypatch) -> None:
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {
            "tikhub_tiktok_top_ads": [{"material_id": "ad1"}],
            "tikhub_tiktok_ads_detail": [{"material_id": "ad1"}],
        },
        calls,
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    top = await tiktok_ads_top(PROJECT_ID, {"query": "beauty", "limit": 3})
    assert top.records_count == 1
    assert calls[0][0] == "tikhub_tiktok_top_ads"
    detail = await tiktok_ads_detail(PROJECT_ID, {"ad_id": "ad1"})
    assert detail.records_count == 1
    assert calls[1][1]["ads_id"] == "ad1"


@pytest.mark.asyncio
async def test_relation_tools_require_cookie(monkeypatch) -> None:
    async def no_cookie(project_id):
        return None

    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._resolve_creator_cookie",
        no_cookie,
    )
    video = await tiktok_video_products(PROJECT_ID, {"video_id": "v1"})
    assert video.status == "failed"
    assert "credential_required:tiktok.creator_cookie" in video.errors
    showcase = await tiktok_creator_showcase(PROJECT_ID, {})
    assert showcase.status == "failed"


@pytest.mark.asyncio
async def test_relation_tools_call_endpoints_with_cookie(monkeypatch) -> None:
    async def cookie(project_id):
        return "sessionid=x"

    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._resolve_creator_cookie",
        cookie,
    )
    calls: list[Any] = []
    fake = _fake_collect_factory(
        {
            "tikhub_tiktok_video_products": [{"product_id": "p1"}],
            "tikhub_tiktok_creator_showcase": [{"product_id": "p2"}],
        },
        calls,
    )
    monkeypatch.setattr("data_intelligence_hub.services.tiktok_tools._collect", fake)
    video = await tiktok_video_products(PROJECT_ID, {"video_id": "v1"})
    assert video.records_count == 1
    assert calls[0][1]["item_ids"] == ["v1"]
    showcase = await tiktok_creator_showcase(PROJECT_ID, {"limit": 2})
    assert showcase.records_count == 1
    assert calls[1][0] == "tikhub_tiktok_creator_showcase"


@pytest.mark.asyncio
async def test_tool_call_metadata_reaches_the_run(monkeypatch) -> None:
    calls: list[Any] = []

    async def fake_collect(
        project_id, endpoint_type, params, limit, *, role="primary", creator_cookie=None
    ):
        calls.append((endpoint_type, params, role))
        return [], {
            "endpoint_type": endpoint_type,
            "task_id": "task-1",
            "run_id": "run-1",
            "status": "empty",
            "records_count": 0,
            "error": None,
        }

    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake_collect
    )
    result = await run_tiktok_tool(
        "tiktok_product_search", PROJECT_ID, {"query": "skincare"}
    )
    assert result.tool_call_id is not None
    assert result.tool_call_id.startswith("tc_")

"""Commerce ingestion tests for the TikTok canonical tables."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.tiktok_commerce import (
    Ad,
    AdCreative,
    CreatorCommerce,
    CreatorProduct,
    Product,
    ProductReview,
    ProductSnapshot,
    Shop,
    VideoProduct,
)
from data_intelligence_hub.models.tiktok_content import Creator
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.tiktok_content_ingestion import (
    IngestionContext,
    ingest_tiktok_content,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
TABLES = [
    "users",
    "workspaces",
    "projects",
    "creator",
    "video",
    "shop",
    "product",
    "product_snapshot",
    "product_review",
    "creator_commerce",
    "video_product",
    "creator_product",
    "ad",
    "ad_creative",
]


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [Base.metadata.tables[name] for name in TABLES]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection, tables=tables
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed_tenant(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="x",
            name="Tester",
            status="active",
        )
    )
    db.add(
        Workspace(
            id=workspace_id,
            slug=f"ws-{workspace_id}",
            name="ws",
            owner_id=user_id,
        )
    )
    db.add(
        Project(
            id=project_id,
            workspace_id=workspace_id,
            name="p",
            domain="test",
            status="active",
            owner_id=user_id,
        )
    )
    await db.commit()
    return workspace_id, project_id


def _context(workspace_id, project_id, endpoint="tikhub_tiktok_shop_search_v2"):
    return IngestionContext(
        workspace_id=workspace_id,
        project_id=project_id,
        provider="tikhub",
        endpoint_type=endpoint,
        schema_version="tikhub_tiktok_commerce.v1",
        captured_at=NOW,
        country_code="US",
    )


def _product_content() -> dict:
    return {
        "record_type": "tiktok_product",
        "provider": "tikhub",
        "platform": "tiktok_shop",
        "product_id": "p1",
        "region": "US",
        "title": "Glass Skin Bundle",
        "price_amount": 148,
        "original_price_amount": 199,
        "currency": "USD",
        "sale_count": 170191,
        "rating": 4.5,
        "review_count": 12018,
        "seller_id": "s1",
        "shop_id": "shop1",
        "shop_name": "Anua Store US",
        "shop_logo_url": "https://img/logo.png",
        "product_url": "https://shop.tiktok.com/us/pdp/x/p1",
        "sku_count": 1,
        "skus_json": [{"SkuId": "sku1"}],
        "free_shipping": True,
    }


@pytest.mark.asyncio
async def test_product_writes_shop_product_and_snapshot(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    result = await ingest_tiktok_content(
        session, [_product_content()], _context(workspace_id, project_id)
    )
    assert result.products == 1
    assert result.product_snapshots == 1
    assert result.shops == 1
    product = await session.get(Product, "US:p1")
    assert product is not None
    assert product.title == "Glass Skin Bundle"
    assert product.shop_key == "shop:US:shop1"
    shop = await session.get(Shop, "shop:US:shop1")
    assert shop is not None
    assert shop.shop_name == "Anua Store US"
    snapshot = await session.scalar(select(ProductSnapshot))
    assert snapshot is not None
    assert snapshot.sale_count == 170191


@pytest.mark.asyncio
async def test_apify_money_dict_is_normalized(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = _product_content()
    content["price_amount"] = {"value": 299, "currency": "USD"}
    content["original_price_amount"] = {"value": 399, "currency": "USD"}
    content["currency"] = None
    content["rating"] = {"score": 4.6, "reviewCount": 12}
    content.pop("review_count", None)
    content["sale_count"] = "192.98K"
    await ingest_tiktok_content(
        session, [content], _context(workspace_id, project_id)
    )
    snapshot = await session.scalar(select(ProductSnapshot))
    assert snapshot is not None
    assert float(snapshot.price_amount) == 299.0
    assert float(snapshot.original_price_amount) == 399.0
    assert snapshot.currency == "USD"
    assert float(snapshot.rating) == 4.6
    assert snapshot.review_count == 12
    assert snapshot.sale_count == 192980


@pytest.mark.asyncio
async def test_review_creates_minimal_product(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    review = {
        "record_type": "tiktok_product_review",
        "provider": "tikhub",
        "review_id": "r1",
        "product_id": "p2",
        "region": "US",
        "rating": 5,
        "text": "great",
        "review_time": "2026-10-06T00:00:00+00:00",
        "verified_purchase": True,
    }
    result = await ingest_tiktok_content(
        session, [review], _context(workspace_id, project_id, "tikhub_tiktok_shop_reviews_v2")
    )
    assert result.product_reviews == 1
    assert await session.get(Product, "US:p2") is not None
    saved = await session.get(ProductReview, "r1")
    assert saved is not None
    assert saved.text == "great"


@pytest.mark.asyncio
async def test_same_product_in_two_regions_has_two_keys(
    session: AsyncSession,
) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    us = _product_content()
    gb = {**_product_content(), "region": "GB", "seller_id": "s1-gb", "shop_id": "shop1-gb"}
    await ingest_tiktok_content(
        session, [us, gb], _context(workspace_id, project_id)
    )
    count = await session.scalar(select(func.count()).select_from(Product))
    assert count == 2
    assert await session.get(Product, "US:p1") is not None
    assert await session.get(Product, "GB:p1") is not None


@pytest.mark.asyncio
async def test_product_ingestion_is_idempotent(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    context = _context(workspace_id, project_id)
    await ingest_tiktok_content(session, [_product_content()], context)
    await ingest_tiktok_content(session, [_product_content()], context)
    count = await session.scalar(select(func.count()).select_from(ProductSnapshot))
    assert count == 1


@pytest.mark.asyncio
async def test_creator_commerce_creates_creator_and_observation(
    session: AsyncSession,
) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_creator_commerce",
        "provider": "apify",
        "actor_id": "lemur/tiktok-shop-creators",
        "creator_id": "u1",
        "unique_id": "alice",
        "nickname": "Alice",
        "region": "US",
        "gmv_amount": 1000,
        "units_sold": 10,
        "commission_rate": 15,
        "engagement_rate": 3.5,
    }
    result = await ingest_tiktok_content(
        session, [content], _context(workspace_id, project_id, "apify_tiktok_shop_creators")
    )
    assert result.creator_commerce == 1
    assert await session.get(Creator, "u1") is not None
    row = await session.scalar(select(CreatorCommerce))
    assert row is not None
    assert row.period_days == 30
    assert float(row.avg_commission_rate) == pytest.approx(0.15)
    assert float(row.engagement_rate) == pytest.approx(0.035)


@pytest.mark.asyncio
async def test_apify_creator_commerce_nested_stats(
    session: AsyncSession,
) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_video",
        "provider": "apify",
        "actor_id": "lemur/tiktok-shop-creators",
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
    await ingest_tiktok_content(
        session,
        [content],
        _context(workspace_id, project_id, "apify_tiktok_shop_creators"),
    )
    row = await session.scalar(select(CreatorCommerce))
    assert row is not None
    assert float(row.gmv_amount) == 1098437.17
    assert row.units_sold == 12428
    assert row.follower_count == 151353
    assert row.avg_views == 5022
    assert float(row.avg_commission_rate) == pytest.approx(0.075)
    assert row.promoted_product_count == 212


@pytest.mark.asyncio
async def test_ad_writes_master_and_creative(session: AsyncSession) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_ad",
        "provider": "tikhub",
        "material_id": "ad1",
        "ad_title": "Perfume repack",
        "brand_name": "microperfumes",
        "highlight_text": "Showcase a real-time comparison",
        "ctr": 0.22,
        "cost": 2,
        "like_count": 33506,
        "comment_count": 845,
        "share_count": 273,
        "landing_page": "https://example.com",
        "country_code": ["US"],
        "objective_key": "campaign_objective_conversion",
        "industry_key": "beauty",
        "video_info": {
            "vid": "vid1",
            "duration": 43.5,
            "cover": "https://img/cover.jpg",
            "video_url": {"720p": "https://video/720.mp4"},
        },
    }
    result = await ingest_tiktok_content(
        session, [content], _context(workspace_id, project_id, "tikhub_tiktok_ads_detail")
    )
    assert result.ads == 1
    assert result.ad_creatives == 1
    ad = await session.get(Ad, "ad1")
    assert ad is not None
    assert ad.advertiser_name == "microperfumes"
    assert ad.landing_url == "https://example.com"
    creative = await session.scalar(select(AdCreative))
    assert creative is not None
    assert creative.asset_hash == "vid1"
    assert creative.video_url == "https://video/720.mp4"


@pytest.mark.asyncio
async def test_video_product_relation_derives_creator_product(
    session: AsyncSession,
) -> None:
    workspace_id, project_id = await _seed_tenant(session)
    content = {
        "record_type": "tiktok_video_product",
        "provider": "tikhub",
        "video_id": "v1",
        "creator_id": "u1",
        "product_id": "p1",
        "region": "US",
        "title": "Product",
    }
    result = await ingest_tiktok_content(
        session,
        [content],
        _context(workspace_id, project_id, "tikhub_tiktok_video_products"),
    )
    assert result.video_products == 1
    assert result.creator_products == 1
    assert await session.scalar(select(VideoProduct)) is not None
    assert await session.scalar(select(CreatorProduct)) is not None

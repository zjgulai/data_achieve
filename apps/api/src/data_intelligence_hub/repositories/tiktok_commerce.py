"""Repositories for the TikTok R1 commerce tables.

Writes are tenant-scoped and idempotent. Master rows use select-then-update or
insert. Observation rows use the shared UUIDv5 snapshot id helper.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.tiktok_commerce import (
    CreatorCommerce,
    CreatorProduct,
    Product,
    ProductReview,
    ProductSnapshot,
    Shop,
    VideoProduct,
)
from data_intelligence_hub.repositories.tiktok_content import (
    BACKFILL_ONLY_IF_NEWER,
    _check_tenant,
    _filter_values,
    _governance,
    _upsert_master,
    make_snapshot_id,
)


def make_product_key(region: str, product_id: str) -> str:
    return f"{region}:{product_id}"


def make_shop_key(
    region: str, shop_id: str | None, seller_id: str | None
) -> str:
    """Region-prefixed key. A bare shop_id can collide across markets."""
    if shop_id:
        return f"shop:{region}:{shop_id}"
    if seller_id:
        return f"seller:{region}:{seller_id}"
    raise ValueError("shop_identity_required")


async def _existing_snapshot(
    session: AsyncSession, model: type[Any], snapshot_id: str
) -> Any | None:
    return await session.get(model, snapshot_id)


async def get_product(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    product_key: str,
) -> Product | None:
    result = await session.execute(
        select(Product).where(
            Product.product_key == product_key,
            Product.workspace_id == workspace_id,
            Product.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_shop(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    shop_key: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Shop:
    return await _upsert_master(
        session,
        Shop,
        "shop_key",
        shop_key,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


async def upsert_product(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    product_key: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> Product:
    return await _upsert_master(
        session,
        Product,
        "product_key",
        product_key,
        workspace_id=workspace_id,
        project_id=project_id,
        values=values,
        governance=_governance(
            provider=provider,
            endpoint_type=endpoint_type,
            schema_version=schema_version,
            captured_at=captured_at,
            run_id=run_id,
            raw_ref=raw_ref,
            quality_flags=quality_flags,
        ),
    )


async def add_product_snapshot(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    product_key: str,
    product_id: str,
    region: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> ProductSnapshot:
    snapshot_id = make_snapshot_id(
        product_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await _existing_snapshot(session, ProductSnapshot, snapshot_id)
    if existing is not None:
        return existing
    governance = _governance(
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        captured_at=captured_at,
        run_id=run_id,
        raw_ref=raw_ref,
        quality_flags=quality_flags,
    )
    clean_values = _filter_values(
        ProductSnapshot,
        values,
        {
            "snapshot_id",
            "workspace_id",
            "project_id",
            "product_key",
            "product_id",
            "region",
            *governance.keys(),
        },
    )
    obj = ProductSnapshot(
        snapshot_id=snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        product_key=product_key,
        product_id=product_id,
        region=region,
        **governance,
        **clean_values,
    )
    session.add(obj)
    await session.flush()
    return obj


async def upsert_product_review(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    review_id: str,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    captured_at: datetime,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> ProductReview:
    governance = _governance(
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        captured_at=captured_at,
        run_id=run_id,
        raw_ref=raw_ref,
        quality_flags=quality_flags,
    )
    clean_values = _filter_values(
        ProductReview,
        values,
        {
            "review_id",
            "workspace_id",
            "project_id",
            "first_seen_at",
            "last_updated_at",
            *governance.keys(),
        },
    )
    obj = await session.get(ProductReview, review_id)
    if obj is None:
        obj = ProductReview(
            review_id=review_id,
            workspace_id=workspace_id,
            project_id=project_id,
            first_seen_at=captured_at,
            last_updated_at=captured_at,
            **governance,
            **clean_values,
        )
        session.add(obj)
    else:
        _check_tenant(obj, workspace_id, project_id)
        if (
            BACKFILL_ONLY_IF_NEWER.get()
            and obj.last_updated_at is not None
            and obj.last_updated_at > captured_at
        ):
            return obj
        for key, value in clean_values.items():
            setattr(obj, key, value)
        for key, value in governance.items():
            setattr(obj, key, value)
        obj.last_updated_at = captured_at
    await session.flush()
    return obj


async def add_creator_commerce(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    creator_id: str,
    market: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> CreatorCommerce:
    entity_key = f"{creator_id}:{market}"
    snapshot_id = make_snapshot_id(
        entity_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await _existing_snapshot(session, CreatorCommerce, snapshot_id)
    if existing is not None:
        return existing
    governance = _governance(
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        captured_at=captured_at,
        run_id=run_id,
        raw_ref=raw_ref,
        quality_flags=quality_flags,
    )
    clean_values = _filter_values(
        CreatorCommerce,
        values,
        {
            "snapshot_id",
            "workspace_id",
            "project_id",
            "creator_id",
            "market",
            *governance.keys(),
        },
    )
    obj = CreatorCommerce(
        snapshot_id=snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        creator_id=creator_id,
        market=market,
        **governance,
        **clean_values,
    )
    session.add(obj)
    await session.flush()
    return obj


async def add_video_product(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    video_id: str,
    product_key: str,
    relation_type: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> VideoProduct:
    entity_key = f"{video_id}:{product_key}:{relation_type}"
    snapshot_id = make_snapshot_id(
        entity_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await _existing_snapshot(session, VideoProduct, snapshot_id)
    if existing is not None:
        return existing
    governance = _governance(
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        captured_at=captured_at,
        run_id=run_id,
        raw_ref=raw_ref,
        quality_flags=quality_flags,
    )
    clean_values = _filter_values(
        VideoProduct,
        values,
        {
            "snapshot_id",
            "workspace_id",
            "project_id",
            "video_id",
            "product_key",
            "relation_type",
            *governance.keys(),
        },
    )
    obj = VideoProduct(
        snapshot_id=snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        video_id=video_id,
        product_key=product_key,
        relation_type=relation_type,
        **governance,
        **clean_values,
    )
    session.add(obj)
    await session.flush()
    return obj


async def add_creator_product(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    creator_id: str,
    product_key: str,
    relation_type: str,
    captured_at: datetime,
    values: dict[str, Any],
    provider: str,
    endpoint_type: str,
    schema_version: str,
    run_id: str | None = None,
    raw_ref: str | None = None,
    quality_flags: list[Any] | None = None,
) -> CreatorProduct:
    entity_key = f"{creator_id}:{product_key}:{relation_type}"
    snapshot_id = make_snapshot_id(
        entity_key, captured_at, provider, endpoint_type, run_id
    )
    existing = await _existing_snapshot(session, CreatorProduct, snapshot_id)
    if existing is not None:
        return existing
    governance = _governance(
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        captured_at=captured_at,
        run_id=run_id,
        raw_ref=raw_ref,
        quality_flags=quality_flags,
    )
    clean_values = _filter_values(
        CreatorProduct,
        values,
        {
            "snapshot_id",
            "workspace_id",
            "project_id",
            "creator_id",
            "product_key",
            "relation_type",
            *governance.keys(),
        },
    )
    obj = CreatorProduct(
        snapshot_id=snapshot_id,
        workspace_id=workspace_id,
        project_id=project_id,
        creator_id=creator_id,
        product_key=product_key,
        relation_type=relation_type,
        **governance,
        **clean_values,
    )
    session.add(obj)
    await session.flush()
    return obj

"""TikTok R1 commerce canonical models.

Seven of the nine commerce tables from the R1 schema. The ``ad`` and
``ad_creative`` tables stay in the migration but have no ORM model yet: the
selected R1 commerce modules are products, reviews and creator commerce.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.tiktok_content import (
    TikTokGovernanceMixin,
    TikTokMasterTimestampsMixin,
    TikTokTenantMixin,
)


class Shop(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "shop"
    __table_args__ = (
        Index(
            "uq_shop_region_shop_id",
            "region",
            "shop_id",
            unique=True,
            postgresql_where=sql_text("shop_id IS NOT NULL"),
        ),
        Index(
            "uq_shop_region_seller_id",
            "region",
            "seller_id",
            unique=True,
            postgresql_where=sql_text("shop_id IS NULL"),
        ),
    )

    shop_key: Mapped[str] = mapped_column(Text, primary_key=True)
    shop_id: Mapped[str | None] = mapped_column(Text)
    seller_id: Mapped[str | None] = mapped_column(Text)
    shop_name: Mapped[str | None] = mapped_column(Text)
    shop_type: Mapped[str | None] = mapped_column(Text)
    seller_type: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    follower_count: Mapped[int | None] = mapped_column(BigInteger)
    product_count: Mapped[int | None] = mapped_column(BigInteger)
    is_mall_recommended: Mapped[bool | None] = mapped_column(Boolean)
    shop_url: Mapped[str | None] = mapped_column(Text)
    identity_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sql_text("'exact'")
    )


class Product(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("region", "product_id", name="uq_product_region_id"),
        Index("ix_product_shop", "region", "shop_key"),
        Index("ix_product_category", "category_l1", "category_l2"),
        Index("ix_product_title", "title"),
    )

    product_key: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    shop_key: Mapped[str | None] = mapped_column(ForeignKey("shop.shop_key"))
    shop_id: Mapped[str | None] = mapped_column(Text)
    seller_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    category_l1: Mapped[str | None] = mapped_column(Text)
    category_l2: Mapped[str | None] = mapped_column(Text)
    category_l3: Mapped[str | None] = mapped_column(Text)
    category_path: Mapped[str | None] = mapped_column(Text)
    product_url: Mapped[str | None] = mapped_column(Text)
    image_urls: Mapped[list[Any] | None] = mapped_column(JSON)
    sku_count: Mapped[int | None] = mapped_column(Integer)
    skus_json: Mapped[list[Any] | None] = mapped_column(JSON)
    currency: Mapped[str | None] = mapped_column(String(3))
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    identity_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sql_text("'exact'")
    )


class ProductSnapshot(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "product_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "product_key",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_product_snapshot_observation",
        ),
        Index("ix_product_snapshot_time", "product_key", "captured_at"),
        Index("ix_product_snapshot_sales", "region", "sale_count_30d"),
        Index("ix_product_snapshot_gmv", "region", "gmv_amount_30d"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_key: Mapped[str] = mapped_column(
        ForeignKey("product.product_key"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    price_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    original_price_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    min_price_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    max_price_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    avg_price_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    discount_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    sale_count: Mapped[int | None] = mapped_column(BigInteger)
    sale_count_30d: Mapped[int | None] = mapped_column(BigInteger)
    sale_delta_7d: Mapped[int | None] = mapped_column(BigInteger)
    gmv_amount_30d: Mapped[float | None] = mapped_column(Numeric(18, 4))
    commission_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    stock_count: Mapped[int | None] = mapped_column(BigInteger)
    review_count: Mapped[int | None] = mapped_column(BigInteger)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    video_count_30d: Mapped[int | None] = mapped_column(BigInteger)
    live_count_30d: Mapped[int | None] = mapped_column(BigInteger)
    ifl_count_30d: Mapped[int | None] = mapped_column(BigInteger)
    is_hot: Mapped[bool | None] = mapped_column(Boolean)
    free_shipping: Mapped[bool | None] = mapped_column(Boolean)
    shipping_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    is_estimated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )


class ProductReview(TikTokTenantMixin, TikTokGovernanceMixin, TikTokMasterTimestampsMixin, Base):
    __tablename__ = "product_review"
    __table_args__ = (
        Index("ix_product_review_time", "product_key", "review_time"),
        Index("ix_product_review_rating", "rating"),
        Index("ix_product_review_quality", "verified_purchase", "incentivized"),
    )

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_key: Mapped[str] = mapped_column(
        ForeignKey("product.product_key"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    shop_id: Mapped[str | None] = mapped_column(Text)
    sku_id: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    text_language: Mapped[str | None] = mapped_column(Text)
    review_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_purchase: Mapped[bool | None] = mapped_column(Boolean)
    incentivized: Mapped[bool | None] = mapped_column(Boolean)
    helpful_count: Mapped[int | None] = mapped_column(BigInteger)
    images: Mapped[list[Any] | None] = mapped_column(JSON)
    variant: Mapped[str | None] = mapped_column(Text)
    sku_specification: Mapped[str | None] = mapped_column(Text)
    reviewer_name_masked: Mapped[str | None] = mapped_column(Text)
    reviewer_avatar_url: Mapped[str | None] = mapped_column(Text)
    review_country: Mapped[str | None] = mapped_column(Text)


class CreatorCommerce(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "creator_commerce"
    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "market",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_creator_commerce_observation",
        ),
        Index("ix_creator_commerce_time", "creator_id", "captured_at"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    creator_id: Mapped[str] = mapped_column(
        ForeignKey("creator.creator_id"), nullable=False
    )
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    gmv_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    units_sold: Mapped[int | None] = mapped_column(BigInteger)
    gpm_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    video_gpm_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    live_gpm_amount: Mapped[float | None] = mapped_column(Numeric(18, 4))
    avg_commission_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    brand_collaboration_count: Mapped[int | None] = mapped_column(Integer)
    promoted_product_count: Mapped[int | None] = mapped_column(Integer)
    avg_views: Mapped[int | None] = mapped_column(BigInteger)
    avg_likes: Mapped[int | None] = mapped_column(BigInteger)
    avg_comments: Mapped[int | None] = mapped_column(BigInteger)
    avg_shares: Mapped[int | None] = mapped_column(BigInteger)
    engagement_rate: Mapped[float | None] = mapped_column(Numeric(6, 5))
    content_frequency: Mapped[float | None] = mapped_column(Numeric(18, 4))
    post_rate: Mapped[float | None] = mapped_column(Numeric(18, 4))
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    promotion_performance_score: Mapped[float | None] = mapped_column(Numeric(18, 4))
    follower_count: Mapped[int | None] = mapped_column(BigInteger)
    top_brands: Mapped[list[Any] | None] = mapped_column(JSON)
    category_list: Mapped[list[Any] | None] = mapped_column(JSON)
    audience_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    gmv_distribution_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_estimated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sql_text("false")
    )


class VideoProduct(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "video_product"
    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "product_key",
            "relation_type",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_video_product_observation",
        ),
        Index("ix_video_product_product", "product_key"),
        Index("ix_video_product_video", "video_id"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("video.video_id"), nullable=False)
    product_key: Mapped[str] = mapped_column(
        ForeignKey("product.product_key"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5))
    match_method: Mapped[str | None] = mapped_column(String(32))


class CreatorProduct(TikTokTenantMixin, TikTokGovernanceMixin, Base):
    __tablename__ = "creator_product"
    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "product_key",
            "relation_type",
            "captured_at",
            "provider",
            "endpoint_type",
            name="uq_creator_product_observation",
        ),
        Index("ix_creator_product_creator", "creator_id"),
        Index("ix_creator_product_product", "product_key"),
    )

    snapshot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    creator_id: Mapped[str] = mapped_column(
        ForeignKey("creator.creator_id"), nullable=False
    )
    product_key: Mapped[str] = mapped_column(
        ForeignKey("product.product_key"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5))
    match_method: Mapped[str | None] = mapped_column(String(32))

"""TikHub TikTok commerce endpoint contract tests."""

from __future__ import annotations

from data_intelligence_hub.collectors.tikhub_social import (
    TIKHUB_COMMERCE_ENDPOINT_MAP,
    _build_params,
    _extract_commerce_items,
    _normalize_commerce_item,
)


def _search_response() -> dict:
    return {
        "code": 200,
        "data": {
            "data": {
                "component_data": {
                    "products": [
                        {
                            "product_id": "p1",
                            "title": "Glass Skin Bundle",
                            "image": {"url_list": ["https://img/1.jpg"]},
                            "product_price_info": {
                                "sale_price_decimal": "148",
                                "raw_origin_price_decimal": "199",
                                "currency_name": "USD",
                            },
                            "rate_info": {"score": 4.5, "review_count": "12018"},
                            "sold_info": {"sold_count": 170191},
                            "seller_info": {
                                "seller_id": "s1",
                                "shop_id": "shop1",
                                "shop_name": "Anua Store US",
                                "shop_logo": {"url_list": ["https://img/logo.png"]},
                            },
                            "seo_url": {
                                "canonical_url": "https://shop.tiktok.com/us/pdp/x/p1"
                            },
                            "sku_info": [{"SkuId": "sku1"}],
                            "product_marketing_info": {
                                "placement_labels": {"3": [{"text": "Free shipping"}]}
                            },
                        }
                    ]
                }
            }
        },
    }


def _review_response() -> dict:
    return {
        "code": 200,
        "data": {
            "data": {
                "product_reviews": [
                    {
                        "review_id": "r1",
                        "product_id": "p1",
                        "sku_id": "sku1",
                        "review_rating": 5,
                        "review_time": "1791461478705",
                        "is_verified_purchase": True,
                        "is_incentivized_review": False,
                        "reviewer_name": "m**0",
                        "review_text": "great",
                        "review_images": ["https://img/review.jpg"],
                        "sku_specification": "Default",
                        "review_country": "US",
                    }
                ]
            }
        },
    }


def test_commerce_endpoint_map_has_expected_endpoints() -> None:
    assert set(TIKHUB_COMMERCE_ENDPOINT_MAP) == {
        "tikhub_tiktok_shop_search_v2",
        "tikhub_tiktok_shop_hot_products",
        "tikhub_tiktok_shop_reviews_v2",
        "tikhub_tiktok_video_products",
        "tikhub_tiktok_creator_showcase",
        "tikhub_tiktok_top_ads",
        "tikhub_tiktok_ads_detail",
    }


def test_search_extracts_component_products() -> None:
    items = _extract_commerce_items(_search_response(), "shop_search")
    assert len(items) == 1
    assert items[0]["product_id"] == "p1"


def test_search_normalizes_product_and_shop_fields() -> None:
    item = _extract_commerce_items(_search_response(), "shop_search")[0]
    record = _normalize_commerce_item(
        item, "shop_search", "tikhub_tiktok_shop_search_v2", "US"
    )
    assert record is not None
    assert record.record_type == "tiktok_product"
    content = record.content
    assert content["product_id"] == "p1"
    assert content["region"] == "US"
    assert content["price_amount"] == 148.0
    assert content["original_price_amount"] == 199.0
    assert content["sale_count"] == 170191
    assert content["review_count"] == 12018
    assert content["seller_id"] == "s1"
    assert content["shop_name"] == "Anua Store US"
    assert content["sku_count"] == 1
    assert content["free_shipping"] is True


def test_reviews_extract_and_normalize() -> None:
    items = _extract_commerce_items(_review_response(), "shop_reviews")
    assert len(items) == 1
    record = _normalize_commerce_item(
        items[0], "shop_reviews", "tikhub_tiktok_shop_reviews_v2", "US"
    )
    assert record is not None
    assert record.record_type == "tiktok_product_review"
    content = record.content
    assert content["review_id"] == "r1"
    assert content["product_id"] == "p1"
    assert content["region"] == "US"
    assert content["rating"] == 5
    assert content["verified_purchase"] is True
    assert content["review_time"].startswith("2026-")
    assert content["images"] == ["https://img/review.jpg"]


def test_hot_products_extract_product_list() -> None:
    data = {
        "data": {
            "code": 0,
            "data": {"productList": [{"product_id": "p2", "title": "Hot"}]},
        }
    }
    items = _extract_commerce_items(data, "shop_hot")
    assert len(items) == 1
    record = _normalize_commerce_item(
        items[0], "shop_hot", "tikhub_tiktok_shop_hot_products", "MY"
    )
    assert record is not None
    assert record.content["region"] == "MY"


def test_hot_products_extract_single_level_fallback() -> None:
    data = {"data": {"productList": [{"product_id": "p3", "title": "Flat"}]}}
    assert len(_extract_commerce_items(data, "shop_hot")) == 1


def test_build_params_for_commerce_endpoints() -> None:
    assert _build_params(
        {
            "endpoint_type": "tikhub_tiktok_shop_search_v2",
            "search_word": "skincare",
            "region": "US",
        },
        max_items=10,
    ) == {
        "search_word": "skincare",
        "offset": 0,
        "page_token": "",
        "region": "US",
    }
    reviews = _build_params(
        {
            "endpoint_type": "tikhub_tiktok_shop_reviews_v2",
            "product_id": "p1",
            "region": "US",
        },
        max_items=10,
    )
    assert reviews["product_id"] == "p1"
    assert reviews["page_start"] == 1

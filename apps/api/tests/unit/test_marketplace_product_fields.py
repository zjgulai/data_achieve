"""商品记录的字段抽取：Apify 负载 -> ECOMMERCE_PRODUCT_FIELDS。

自研 `ecommerce_product_page` 采集器直接写 `content["extracted_fields"]`。
Apify 电商 actor 写的是 actor 自己的 item 形状（`content["raw"]`），
2026-10-09 前这些记录取不到任何字段，所以真实 Apify 电商采集无法落成数据集。

夹具取自生产真实 `amazon_product` 记录（run 5e901a90，junglee/amazon-bestsellers）。
"""

from __future__ import annotations

import uuid

from data_intelligence_hub.models import RawRecord
from data_intelligence_hub.services.automation_service import (
    PRODUCT_RECORD_TYPES,
    _marketplace_extracted_fields,
    _product_page_records,
    _raw_record_extracted_fields,
)

# Trimmed from a real Apify Amazon bestseller item.
AMAZON_RAW = {
    "title": "Apple iPad (9th Generation): with A13 Bionic chip, 64GB, Wi-Fi",
    "price": {"value": 463.55, "currency": "$"},
    "stars": 4.8,
    "reviewsCount": 75633,
    "inStock": True,
    "inStockText": "In Stock  In Stock",
    "originalAsin": "B09G9FPHY6",
    "url": "https://www.amazon.com/dp/B09G9FPHY6",
    "thumbnailImage": "https://m.media-amazon.com/images/I/61NGnpjoRDL.jpg",
    "productOverview": [
        {"key": "Brand", "value": "Apple"},
        {"key": "Model Name", "value": "iPad"},
    ],
}


def _record(record_type: str, content: dict[str, object]) -> RawRecord:
    return RawRecord(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        record_type=record_type,
        source_url="https://www.amazon.com/dp/B09G9FPHY6",
        content=content,
        content_hash="x" * 64,
        collected_at=None,  # type: ignore[arg-type]
        created_at=None,  # type: ignore[arg-type]
    )


def _apify_record(raw: dict[str, object]) -> RawRecord:
    return _record(
        "amazon_product",
        {
            "provider": "apify",
            "platform": "amazon",
            "actor_id": "junglee/amazon-bestsellers",
            "schema_version": "apify_amazon_product.v1",
            "text": "Apple iPad",
            "raw": raw,
        },
    )


def test_apify_payload_maps_onto_canonical_product_fields() -> None:
    fields = _marketplace_extracted_fields(AMAZON_RAW, _apify_record(AMAZON_RAW))

    assert fields["title"] == AMAZON_RAW["title"]
    assert fields["sku"] == "B09G9FPHY6"
    assert fields["image_url"] == AMAZON_RAW["thumbnailImage"]
    # currency rides inside the nested price object
    assert fields["price"] == 463.55
    assert fields["currency"] == "$"
    # brand comes from the labelled product-overview list
    assert fields["brand"] == "Apple"
    assert fields["availability"] == "in_stock"


def test_raw_record_extracted_fields_reads_apify_records() -> None:
    fields = _raw_record_extracted_fields(_apify_record(AMAZON_RAW))
    assert fields["title"] == AMAZON_RAW["title"]
    assert fields["canonical_url"] == "https://www.amazon.com/dp/B09G9FPHY6"


def test_canonical_url_falls_back_to_record_source_url() -> None:
    fields = _raw_record_extracted_fields(_apify_record({"title": "No URL"}))
    assert fields["canonical_url"] == "https://www.amazon.com/dp/B09G9FPHY6"


def test_out_of_stock_flag_is_normalized() -> None:
    raw = {**AMAZON_RAW, "inStock": False}
    del raw["inStockText"]
    fields = _marketplace_extracted_fields(raw, _apify_record(raw))
    assert fields["availability"] == "out_of_stock"


def test_non_apify_record_without_extracted_fields_stays_empty() -> None:
    """门控：github / feed 等记录不得因为兜底而凭空多出字段。"""
    record = _record(
        "github_repo",
        {"repositories": [{"full_name": "x/y"}], "provider": "github"},
    )
    assert _raw_record_extracted_fields(record) == {}


def test_page_collector_extracted_fields_win_over_the_fallback() -> None:
    record = _record(
        "ecommerce_product_page",
        {"extracted_fields": {"title": "From page collector"}, "raw": AMAZON_RAW},
    )
    assert _raw_record_extracted_fields(record) == {"title": "From page collector"}


def test_product_record_types_cover_marketplace_actors() -> None:
    records = [
        _record("ecommerce_product_page", {}),
        _record("amazon_product", {}),
        _record("walmart_product", {}),
        _record("ecommerce_product", {}),
        _record("github_repo", {}),
        _record("product", {}),  # package-registry rows are not marketplace products
    ]
    matched = {record.record_type for record in _product_page_records(records)}
    assert matched == set(PRODUCT_RECORD_TYPES)
    assert "github_repo" not in matched
    assert "product" not in matched

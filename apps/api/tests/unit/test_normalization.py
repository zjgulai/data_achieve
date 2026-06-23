from __future__ import annotations

import uuid
from datetime import UTC, datetime

from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.services.normalization_service import build_snapshot_drafts


def make_raw_record(
    record_type: str,
    content: dict[str, object],
    collected_at: datetime | None = None,
) -> RawRecord:
    now = collected_at or datetime.now(UTC)
    return RawRecord(
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        task_run_id=uuid.uuid4(),
        record_type=record_type,
        source_url=None,
        content=content,
        content_hash="hash",
        screenshot_url=None,
        collected_at=now,
        created_at=now,
    )


def test_build_snapshot_drafts_for_github_repo() -> None:
    collected_at = datetime(2026, 6, 20, tzinfo=UTC)
    raw_record = make_raw_record(
        "github_repo",
        {
            "full_name": "openai/codex",
            "html_url": "https://github.com/openai/codex",
            "stargazers_count": 100,
            "forks_count": 5,
            "open_issues_count": 2,
            "watchers_count": 100,
            "subscribers_count": 30,
            "pushed_at": "2026-06-18T00:00:00Z",
            "license_spdx_id": "Apache-2.0",
            "default_branch": "main",
        },
        collected_at=collected_at,
    )

    drafts = build_snapshot_drafts(raw_record, "osint")

    assert len(drafts) == 1
    assert drafts[0].entity_type == "github_repo"
    assert drafts[0].external_id == "openai/codex"
    assert drafts[0].metrics["stars"] == 100
    assert drafts[0].metrics["subscribers"] == 30
    assert drafts[0].metrics["commit_freshness_days"] == 2
    assert drafts[0].snapshot_data["license_spdx_id"] == "Apache-2.0"


def test_build_snapshot_drafts_for_github_topic() -> None:
    collected_at = datetime(2026, 6, 20, tzinfo=UTC)
    raw_record = make_raw_record(
        "github_topic",
        {
            "topic": "web-scraping",
            "repositories": [
                {
                    "full_name": "example/scraper",
                    "html_url": "https://github.com/example/scraper",
                    "stargazers_count": 42,
                    "forks_count": 3,
                    "open_issues_count": 4,
                    "watchers_count": 42,
                    "pushed_at": "2026-06-19T00:00:00Z",
                    "license_spdx_id": "MIT",
                }
            ],
        },
        collected_at=collected_at,
    )

    drafts = build_snapshot_drafts(raw_record, "osint")

    assert len(drafts) == 1
    assert drafts[0].external_id == "example/scraper"
    assert drafts[0].snapshot_data["topic"] == "web-scraping"
    assert drafts[0].metrics["open_issues"] == 4
    assert drafts[0].metrics["commit_freshness_days"] == 1


def test_build_snapshot_drafts_for_generic_web() -> None:
    raw_record = make_raw_record(
        "generic_web",
        {
            "url": "https://example.com",
            "title": "Example",
            "text_content": "Hello world",
            "html_content": "<html>Hello world</html>",
        },
    )

    drafts = build_snapshot_drafts(raw_record, "competitor")

    assert len(drafts) == 1
    assert drafts[0].entity_type == "web_page"
    assert drafts[0].external_id == "https://example.com"
    assert drafts[0].metrics["text_length"] == 11


def test_build_snapshot_drafts_for_ecommerce_product_page() -> None:
    raw_record = make_raw_record(
        "ecommerce_product_page",
        {
            "provider": "ecommerce",
            "kind": "product_page",
            "url": "https://shop.example/products/demo-bag",
            "extracted_fields": {
                "title": "Demo Carry Bag",
                "price": 129.9,
                "currency": "USD",
                "sku": "BAG-001",
                "canonical_url": "https://shop.example/products/demo-bag",
            },
            "field_schema": [],
            "cleaning_plan": [],
        },
    )

    drafts = build_snapshot_drafts(raw_record, "ecommerce")

    assert len(drafts) == 1
    assert drafts[0].entity_type == "product"
    assert drafts[0].external_id == "BAG-001"
    assert drafts[0].name == "Demo Carry Bag"
    assert drafts[0].metrics["price"] == 129.9
    assert drafts[0].metrics["field_count"] == 5


def test_build_snapshot_drafts_for_ecommerce_product_discovery() -> None:
    raw_record = make_raw_record(
        "ecommerce_product_discovery",
        {
            "provider": "ecommerce",
            "kind": "product_discovery",
            "url": "https://shop.example/collections/summer-bags",
            "page_structure": {
                "page_type": "collection_listing",
                "title": "Summer Bags",
                "canonical_url": "https://shop.example/collections/summer-bags",
                "link_count": 18,
                "product_link_count": 3,
            },
            "product_candidates": [
                {
                    "url": "https://shop.example/products/demo-bag",
                    "title": "Demo Carry Bag",
                    "source": "anchor",
                    "confidence": 0.9,
                },
                {
                    "url": "https://shop.example/products/weekend-tote",
                    "title": "Weekend Tote",
                    "source": "anchor",
                    "confidence": 0.86,
                },
            ],
            "discovery_plan": {
                "next_collector_type": "ecommerce_product_page",
                "candidate_count": 2,
                "max_products": 50,
                "fan_out_requires_review": True,
            },
        },
    )

    drafts = build_snapshot_drafts(raw_record, "ecommerce")

    assert len(drafts) == 1
    assert drafts[0].entity_type == "product_catalog"
    assert drafts[0].external_id == "https://shop.example/collections/summer-bags"
    assert drafts[0].name == "Summer Bags"
    assert drafts[0].metrics["candidate_count"] == 2
    assert drafts[0].metrics["product_link_count"] == 3
    assert drafts[0].metrics["max_products"] == 50


def test_build_snapshot_drafts_for_manual_json_list_payload() -> None:
    raw_record = make_raw_record(
        "manual_json",
        {
            "entity_type": "product",
            "payload": [
                {"sku": "SKU-1", "name": "Product 1", "price": 10},
                {"sku": "SKU-2", "name": "Product 2", "price": 20},
            ],
        },
    )

    drafts = build_snapshot_drafts(raw_record, "ecommerce")

    assert [draft.external_id for draft in drafts] == ["SKU-1", "SKU-2"]
    assert [draft.metrics["price"] for draft in drafts] == [10, 20]

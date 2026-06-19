from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from data_intelligence_hub.services.browser_structure_diagnostic import (
    build_browser_structure_diagnostic,
)


def _raw_snapshot(
    *,
    visible_text: str = "Public product data with title, price, rating, stock and reviews.",
    scripts: int = 2,
    forms: int = 0,
    resources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "page": {
            "url": "https://example.com/products",
            "title": "Example Products",
            "w": 1440,
            "h": 900,
            "pw": 1440,
            "ph": 2200,
        },
        "dom": {
            "title": "Example Products",
            "final_url": "https://example.com/products",
            "visible_text_sample": visible_text,
            "visible_text_length": len(visible_text),
            "visible_line_count": 3,
            "headings": ["Products", "Featured"],
            "meta": {
                "description": "A public product listing.",
                "canonical_url": "https://example.com/products",
            },
            "json_ld_types": ["ItemList"],
            "links": [{"text": "Detail", "href": "https://example.com/products/1"}],
            "forms": [{"name": "Search", "input_count": 1}] if forms else [],
            "counters": {
                "links": 8,
                "same_origin_links": 7,
                "external_links": 1,
                "forms": forms,
                "inputs": forms,
                "buttons": 2,
                "tables": 0,
                "lists": 2,
                "articles": 4,
                "cards": 4,
                "images": 4,
                "scripts": scripts,
                "stylesheets": 1,
                "json_ld_blocks": 1,
            },
            "resources": resources or [],
        },
        "accessibility": {
            "total_nodes": 24,
            "role_counts": {"link": 8, "button": 2, "heading": 2},
            "named_nodes": [{"role": "heading", "name": "Products"}],
        },
        "evidence": {"screenshot_path": "tmp/outputs/browser-diagnostics/example.png"},
        "errors": [],
    }


def test_browser_structure_diagnostic_prefers_generic_web_for_static_public_page() -> None:
    diagnostic = build_browser_structure_diagnostic(
        _raw_snapshot(
            visible_text=(
                "Public catalog page with durable title, price, SKU, availability, rating, "
                "review count and same-origin detail links that are visible without interaction."
            )
        ),
        requested_url="https://example.com/products",
        authorized=True,
        generated_at=datetime(2026, 6, 19, tzinfo=UTC),
    )

    assert diagnostic["schema_version"] == "browser_structure_diagnostic.v1"
    assert diagnostic["run_policy"]["production_write"] is False
    assert diagnostic["dom_counters"]["cards"] == 4
    assert diagnostic["extraction_strategy"]["recommended_path"] == "generic_web"
    assert diagnostic["extraction_strategy"]["field_stability"] == "high"


def test_browser_structure_diagnostic_promotes_api_candidates() -> None:
    diagnostic = build_browser_structure_diagnostic(
        _raw_snapshot(
            resources=[
                {
                    "url": "https://example.com/api/products?page=1&token=secret",
                    "initiator_type": "fetch",
                    "duration_ms": 42,
                    "transfer_size": 2048,
                },
                {
                    "url": "https://cdn.example.net/app.js",
                    "initiator_type": "script",
                },
            ]
        ),
        requested_url="https://example.com/products",
        authorized=True,
        generated_at=datetime(2026, 6, 19, tzinfo=UTC),
    )

    network_summary = diagnostic["network_summary"]
    assert network_summary["api_candidate_count"] == 1
    assert network_summary["api_candidates"][0]["url"] == "https://example.com/api/products?..."
    assert diagnostic["extraction_strategy"]["recommended_path"] == "official_api_or_file"
    assert diagnostic["extraction_strategy"]["fit"] == "medium"


def test_browser_structure_diagnostic_recommends_browser_for_js_shell() -> None:
    diagnostic = build_browser_structure_diagnostic(
        _raw_snapshot(visible_text="Loading", scripts=18),
        requested_url="https://example.com/app",
        authorized=True,
        generated_at=datetime(2026, 6, 19, tzinfo=UTC),
    )

    assert "dynamic_rendering_signal" in diagnostic["risk_flags"]
    assert diagnostic["extraction_strategy"]["recommended_path"] == "browser_automation"
    assert diagnostic["extraction_strategy"]["field_stability"] == "low"


def test_browser_structure_diagnostic_sends_forms_to_manual_review() -> None:
    diagnostic = build_browser_structure_diagnostic(
        _raw_snapshot(forms=1),
        requested_url="https://example.com/search",
        authorized=True,
        generated_at=datetime(2026, 6, 19, tzinfo=UTC),
    )

    assert "form_present" in diagnostic["risk_flags"]
    assert diagnostic["extraction_strategy"]["recommended_path"] == "manual_review"


def test_browser_structure_diagnostic_blocks_without_authorization() -> None:
    diagnostic = build_browser_structure_diagnostic(
        _raw_snapshot(),
        requested_url="https://example.com/products",
        authorized=False,
        generated_at=datetime(2026, 6, 19, tzinfo=UTC),
    )

    assert diagnostic["extraction_strategy"]["recommended_path"] == "blocked_review"
    assert diagnostic["extraction_strategy"]["fit"] == "blocked"

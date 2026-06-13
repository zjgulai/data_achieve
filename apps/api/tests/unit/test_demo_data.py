from __future__ import annotations

from data_intelligence_hub.seed.demo_data import (
    DOMAIN_FRESHNESS_TARGETS,
    _build_context,
)


def test_demo_seed_covers_navigation_domains() -> None:
    context = _build_context()

    assert set(context.project_ids) == {"osint", "ecommerce", "social", "competitor"}
    assert set(context.source_ids) == {"osint", "amazon", "social", "competitor"}
    assert set(context.intelligence_ids) == {
        "osint-scrapy-momentum",
        "amazon-margin-risk",
        "social-method-window",
        "competitor-landing-shift",
    }


def test_demo_freshness_targets_are_collector_backed() -> None:
    assert set(DOMAIN_FRESHNESS_TARGETS) == {"osint", "ecommerce", "social", "competitor"}

    for target in DOMAIN_FRESHNESS_TARGETS.values():
        assert target["collector_type"] in {
            "github_repo",
            "github_topic",
            "generic_web",
            "manual_json",
        }
        assert 1 <= target["target_hours"] <= 24
        assert target["platforms"]

"""Tests for collection timeout resolution and the aliens_eye variation level.

Covers the 2026-10-13 production findings:
  * `aliens_eye_advanced` used upstream's `advanced` level, which generates 123
    username variations; against ~854 sites that is ~105k requests and a run that
    burned the full 1600s subprocess budget without finishing.
  * Endpoints that legitimately run past 300s (selfcheck 444s on the slower host,
    the three heavy spiderfoot scans) need a per-endpoint default, otherwise every
    caller has to pass `run_timeout_seconds` by hand.
"""
from __future__ import annotations

import pytest

from data_intelligence_hub.collectors.aliens_eye_collector import (
    AliensEyeAdvancedCollector,
)
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.services.collector_service import (
    DEFAULT_COLLECTION_TIMEOUT_SECONDS,
    MAX_COLLECTION_TIMEOUT_SECONDS,
    SLOW_ENDPOINT_TIMEOUT_SECONDS,
    _collection_timeout_seconds,
)


class TestCollectionTimeoutSeconds:
    def test_unknown_endpoint_uses_global_default(self):
        config = {"endpoint_type": "sherlock_username_search"}
        assert _collection_timeout_seconds(config) == DEFAULT_COLLECTION_TIMEOUT_SECONDS

    def test_missing_config_uses_global_default(self):
        assert _collection_timeout_seconds(None) == DEFAULT_COLLECTION_TIMEOUT_SECONDS

    @pytest.mark.parametrize("endpoint_type", sorted(SLOW_ENDPOINT_TIMEOUT_SECONDS))
    def test_slow_endpoints_get_their_own_default(self, endpoint_type: str):
        assert _collection_timeout_seconds({"endpoint_type": endpoint_type}) == (
            SLOW_ENDPOINT_TIMEOUT_SECONDS[endpoint_type]
        )

    def test_explicit_value_still_wins(self):
        config = {"endpoint_type": "aliens_eye_selfcheck", "run_timeout_seconds": 120}
        assert _collection_timeout_seconds(config) == 120.0

    def test_explicit_value_is_clamped_to_the_ceiling(self):
        config = {"endpoint_type": "sherlock_username_search", "run_timeout_seconds": 99_999}
        assert _collection_timeout_seconds(config) == MAX_COLLECTION_TIMEOUT_SECONDS

    def test_slow_defaults_stay_below_the_nginx_ceiling(self):
        # The shared and edge nginx allow 1800s for quick-collect; a default at or
        # above that would be cut off before the API could report an error.
        assert max(SLOW_ENDPOINT_TIMEOUT_SECONDS.values()) < 1800.0


class TestRunTimeoutSurvivesServiceValidation:
    """`run_timeout_seconds` 必须穿过服务层白名单。

    2026-10-16 修复的缺陷：quick_collect 构造了该键，但专用校验函数的
    返回白名单不含它，于是值被静默剥除。执行层读不到，回落到全局 300s，
    而采集器内层仍按自己的 600s 自等——内层等 600s，外层 300s 先取消它。

    覆盖全部 17 个专用校验函数。首轮只修了 6 个（apify/tikhub/exa×4），
    其余 10 个仍在丢弃，同批补齐。passthrough 类型本就透传。
    """

    _APIFY = {"actor_id": "apify/instagram-scraper", "actor_input": {}}

    # 17 个专用校验函数各一份最小有效配置。
    _VALID_CONFIGS = {
        "github_repo": {"owner": "a", "repo": "b"},
        "github_topic": {"topic": "python"},
        "generic_web": {"url": "https://example.com"},
        "autoscraper_enhanced_web": {"url": "https://example.com", "wanted_list": ["x"]},
        "public_feed": {"url": "https://example.com/feed"},
        "manual_json": {"entity_type": "t", "json_data": []},
        "ecommerce_product_page": {"url": "https://example.com/p"},
        "ecommerce_product_discovery": {"url": "https://example.com", "max_products": 5},
        "tikhub_social": {
            "endpoint_type": "tikhub_tiktok_video_search",
            "keyword": "k",
        },
        "apify_actor": _APIFY,
        "playwright_browser": {"url": "https://example.com"},
        "anysearch": {"query": "q"},
        "jina_reader": {"url": "https://example.com"},
        "exa_search": {"query": "q"},
        "exa_find_similar": {"url": "https://example.com"},
        "exa_contents": {"urls": ["https://example.com"]},
        "exa_answer": {"query": "q"},
    }

    @pytest.mark.parametrize("collector_type", sorted(_VALID_CONFIGS))
    def test_every_dedicated_validator_keeps_the_key(self, collector_type: str):
        """覆盖全部 17 个专用校验函数，不抽样。

        抽样是首轮漏掉 10 个的原因：当时只挑了 apify 与三个 exa。
        """
        from data_intelligence_hub.services.collector_catalog import (
            validate_collector_config,
        )

        validated = validate_collector_config(
            collector_type, {**self._VALID_CONFIGS[collector_type], "run_timeout_seconds": 700}
        )
        assert validated["run_timeout_seconds"] == 700

    @pytest.mark.parametrize("collector_type", sorted(_VALID_CONFIGS))
    def test_budget_chain_is_connected(self, collector_type: str):
        """端到端：调用方给的预算必须一路到达执行层。"""
        from data_intelligence_hub.services.collector_catalog import (
            validate_collector_config,
        )

        validated = validate_collector_config(
            collector_type, {**self._VALID_CONFIGS[collector_type], "run_timeout_seconds": 700}
        )
        assert _collection_timeout_seconds(validated) == 700.0

    def test_passthrough_types_keep_it_too(self):
        """passthrough 类型没有专用函数，本来就透传；这里防止将来改坏。"""
        from data_intelligence_hub.services.collector_catalog import (
            validate_collector_config,
        )

        validated = validate_collector_config(
            "npm_package", {"package": "express", "run_timeout_seconds": 700}
        )
        assert _collection_timeout_seconds(validated) == 700.0

    def test_absent_key_still_falls_back(self):
        """不传时保持原状，由执行层回落，而不是由校验层替它选值。"""
        from data_intelligence_hub.services.collector_catalog import (
            validate_collector_config,
        )

        validated = validate_collector_config("apify_actor", dict(self._APIFY))
        assert "run_timeout_seconds" not in validated
        assert _collection_timeout_seconds(validated) == DEFAULT_COLLECTION_TIMEOUT_SECONDS

    def test_ceiling_still_applies_after_validation(self):
        from data_intelligence_hub.services.collector_catalog import (
            validate_collector_config,
        )

        validated = validate_collector_config(
            "apify_actor", {**self._APIFY, "run_timeout_seconds": 99_999}
        )
        assert _collection_timeout_seconds(validated) == MAX_COLLECTION_TIMEOUT_SECONDS

    def test_inner_wait_must_not_outlast_the_outer_budget(self):
        """透传修好后仍存在的设计约束：内层自等不得长于外层预算。

        apify 采集器内层默认自等 600s。若调用方给的预算更短，
        外层仍会先取消——这正是原缺陷的形态，只是触发条件变了。
        这条断言把这个边界钉住，避免将来有人把内层默认值调大。
        """
        from data_intelligence_hub.collectors.apify_actor import APIFY_RUN_WAIT_TIMEOUT
        from data_intelligence_hub.services.collector_catalog import (
            validate_collector_config,
        )

        validated = validate_collector_config(
            "apify_actor", {**self._APIFY, "run_timeout_seconds": 300}
        )
        outer = _collection_timeout_seconds(validated)
        assert outer < APIFY_RUN_WAIT_TIMEOUT, (
            "外层预算短于内层自等，长任务会在采集器自己超时前被取消"
        )


class TestAdvancedCollectorLevel:
    def _collector(self, config):
        return AliensEyeAdvancedCollector(config=config)

    def test_default_level_is_intermediate(self):
        """`advanced` means 123 variations — too many to finish synchronously."""
        cfg = self._collector({"username": "torvalds"}).validate_config()
        assert cfg["level"] == "intermediate"

    def test_level_can_be_requested_explicitly(self):
        cfg = self._collector({"username": "t", "level": "advanced"}).validate_config()
        assert cfg["level"] == "advanced"

    def test_level_is_normalised_and_validated(self):
        cfg = self._collector({"username": "t", "level": " Basic "}).validate_config()
        assert cfg["level"] == "basic"
        with pytest.raises(CollectorError, match="level must be one of"):
            self._collector({"username": "t", "level": "deep"}).validate_config()

    def test_username_is_still_required(self):
        with pytest.raises(CollectorError, match="username"):
            self._collector({"level": "basic"}).validate_config()

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

"""Pin the production security defaults that live in compose.

The Python defaults are development-friendly: ``APP_ENV=development``,
``DEMO_MODE`` inferred on, ``AUTH_COOKIE_SECURE`` off. Production safety
depends on the compose file overriding them. Nothing tested that before, so a
compose edit could quietly turn demo fallback on or the cookie insecure.

These tests read the compose file, not a running container. They are a static
contract, not a production probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from data_intelligence_hub.core.config import Settings

COMPOSE = (
    Path(__file__).resolve().parents[4] / "configs" / "deploy" / "scrapy" / "docker-compose.yml"
)


def _api_environment() -> dict[str, object]:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return cast(dict[str, object], data["services"]["api"]["environment"])


def test_api_service_pins_production_environment() -> None:
    assert _api_environment()["APP_ENV"] == "production"


def test_api_service_defaults_cookie_secure_true() -> None:
    value = str(_api_environment()["AUTH_COOKIE_SECURE"])
    assert value.endswith(":-true}"), value


def test_api_service_defaults_collection_network_restricted() -> None:
    value = str(_api_environment()["COLLECTION_NETWORK_MODE"])
    assert "restricted" in value


def test_api_service_does_not_enable_demo_mode() -> None:
    environment = _api_environment()
    if "DEMO_MODE" in environment:
        assert str(environment["DEMO_MODE"]).lower() not in {"true", "1", "yes"}


def test_production_settings_disable_demo_mode() -> None:
    settings = Settings(app_env="production", jwt_secret="x" * 16)
    assert settings.effective_demo_mode is False


def test_production_settings_default_network_mode_is_restricted() -> None:
    settings = Settings(app_env="production", jwt_secret="x" * 16)
    assert settings.effective_collection_network_mode == "restricted"


def test_production_settings_keep_llm_provider_mock_by_default() -> None:
    settings = Settings(app_env="production", jwt_secret="x" * 16)
    assert settings.llm_provider == "mock"

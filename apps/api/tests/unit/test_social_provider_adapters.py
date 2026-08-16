from __future__ import annotations

from typing import get_type_hints

from data_intelligence_hub.social_api.contracts import (
    CredentialHandle,
    CredentialResolver,
    PlatformAdapter,
    build_fixture_operations,
)
from data_intelligence_hub.social_api.reddit import asyncpraw as reddit_adapter
from data_intelligence_hub.social_api.youtube import google_api_client as youtube_adapter
from data_intelligence_hub.social_api.youtube.contracts import YouTubeReadTransport


def test_build_fixture_operations_uses_fixture_mode_without_provider_call() -> None:
    operations = build_fixture_operations(
        provider_id="youtube.v3",
        endpoints=["videos.list"],
        fixture_limit=2,
        sdk_package="google-api-python-client",
    )

    assert operations == [
        {
            "operation_id": "fixture:youtube.v3:videos.list",
            "endpoint": "videos.list",
            "sdk_package": "google-api-python-client",
            "request_mode": "fixture_replay",
            "fixture_record_count": 2,
            "provider_call": False,
        }
    ]


def test_youtube_adapter_metadata_is_fixture_only() -> None:
    metadata = youtube_adapter.adapter_metadata()

    assert metadata.provider_id == "youtube.v3"
    assert metadata.platform == "youtube"
    assert metadata.sdk_package == "google-api-python-client"
    assert metadata.sdk_import_name == "googleapiclient"
    assert metadata.adapter_module == "data_intelligence_hub.social_api.youtube.google_api_client"
    assert metadata.supports_fixture_replay is True
    assert metadata.supports_live_client is False


def test_reddit_adapter_plans_fixture_operations_without_provider_call() -> None:
    metadata = reddit_adapter.adapter_metadata()
    operations = reddit_adapter.plan_fixture_operations(
        endpoints=["search"],
        fixture_limit=3,
    )

    assert metadata.provider_id == "reddit.praw"
    assert metadata.platform == "reddit"
    assert metadata.sdk_package == "asyncpraw"
    assert metadata.sdk_import_name == "asyncpraw"
    assert metadata.adapter_module == "data_intelligence_hub.social_api.reddit.asyncpraw"
    assert metadata.supports_fixture_replay is True
    assert metadata.supports_live_client is False
    assert operations == [
        {
            "operation_id": "fixture:reddit.praw:search",
            "endpoint": "search",
            "sdk_package": "asyncpraw",
            "request_mode": "fixture_replay",
            "fixture_record_count": 3,
            "provider_call": False,
        }
    ]


def test_provider_adapter_objects_conform_without_live_execution() -> None:
    for adapter_module in (youtube_adapter, reddit_adapter):
        adapter = adapter_module.PLATFORM_ADAPTER

        assert isinstance(adapter, PlatformAdapter)
        assert adapter.metadata == adapter_module.adapter_metadata()
        assert adapter.plan_fixture_operations(
            endpoints=["search"],
            fixture_limit=1,
        ) == adapter_module.plan_fixture_operations(
            endpoints=["search"],
            fixture_limit=1,
        )
        assert not hasattr(adapter, "execute")
        assert not hasattr(adapter, "credential_resolver")


def test_credential_protocols_expose_only_an_opaque_handle() -> None:
    handle_members = vars(CredentialHandle)
    resolver_hints = get_type_hints(CredentialResolver.resolve)
    transport_hints = get_type_hints(YouTubeReadTransport.execute)

    assert "reference_fingerprint" in handle_members
    assert {"value", "secret", "token", "api_key"}.isdisjoint(handle_members)
    assert resolver_hints["return"] is CredentialHandle
    assert transport_hints["credential"] is CredentialHandle

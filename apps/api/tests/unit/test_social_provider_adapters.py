from __future__ import annotations

from data_intelligence_hub.social_api.contracts import build_fixture_operations
from data_intelligence_hub.social_api.reddit import asyncpraw as reddit_adapter
from data_intelligence_hub.social_api.youtube import google_api_client as youtube_adapter


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

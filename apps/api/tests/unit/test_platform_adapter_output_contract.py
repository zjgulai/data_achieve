from __future__ import annotations

from inspect import getsource
from typing import Any

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.social_provider import SocialRawPreviewRequest
from data_intelligence_hub.services import social_provider as social_provider_service
from data_intelligence_hub.services.social_provider import prepare_social_raw_preview
from data_intelligence_hub.social_api.contracts import (
    FixtureOnlyPlatformAdapter,
    PlatformAdapter,
    SocialAdapterMetadata,
)
from data_intelligence_hub.social_api.output_contracts import (
    PlatformAdapterFixtureRequest,
    PlatformAdapterNormalizedRecord,
    PlatformAdapterOutputError,
)
from data_intelligence_hub.social_api.reddit import asyncpraw as reddit_adapter
from data_intelligence_hub.social_api.youtube import google_api_client as youtube_adapter


@pytest.mark.parametrize(
    ("adapter", "provider_id", "endpoint", "record_type", "external_post_id"),
    [
        (
            youtube_adapter.PLATFORM_ADAPTER,
            "youtube.v3",
            "videos.list",
            "post",
            "yt_fixture_video_1",
        ),
        (
            reddit_adapter.PLATFORM_ADAPTER,
            "reddit.praw",
            "comments.new",
            "comment",
            "reddit_fixture_post_1",
        ),
    ],
)
def test_youtube_and_reddit_share_one_bounded_normalized_output_contract(
    adapter: PlatformAdapter,
    provider_id: str,
    endpoint: str,
    record_type: str,
    external_post_id: str,
) -> None:
    request = PlatformAdapterFixtureRequest(
        provider_id=provider_id,
        operation_id=f"fixture:{provider_id}:{endpoint}",
        endpoint=endpoint,
        fixture_limit=2,
        max_response_bytes=16_384,
    )

    response = adapter.prepare_fixture_response(request)

    assert response.schema_version == "platform_adapter_fixture_response.v1"
    assert response.request == request
    assert response.provider_id == provider_id
    assert response.response_size_bytes > 0
    assert response.response_size_bytes <= request.max_response_bytes
    assert response.provider_call_attempted is False
    assert len(response.records) == 2
    assert response.records[0].record_type == record_type
    assert response.records[0].external_post_id == external_post_id
    assert response.evidence_refs == tuple(record.evidence_ref for record in response.records)
    assert all(record.payload_digest.startswith("sha256:") for record in response.records)
    assert all(record.provider_call_attempted is False for record in response.records)
    assert {"content_id", "subreddit", "channel_id"}.isdisjoint(response.records[0].model_dump())

    with pytest.raises(ValidationError):
        response.response_size_bytes = 1


def test_adapter_rejects_provider_mismatch_before_building_fixture_response() -> None:
    with pytest.raises(
        PlatformAdapterOutputError,
        match="^platform_adapter_provider_mismatch$",
    ):
        youtube_adapter.PLATFORM_ADAPTER.prepare_fixture_response(
            PlatformAdapterFixtureRequest(
                provider_id="reddit.praw",
                operation_id="fixture:reddit.praw:search",
                endpoint="search",
                fixture_limit=1,
                max_response_bytes=16_384,
            )
        )


def test_adapter_rejects_oversized_response_before_normalization() -> None:
    with pytest.raises(
        PlatformAdapterOutputError,
        match="^platform_adapter_response_too_large$",
    ):
        reddit_adapter.PLATFORM_ADAPTER.prepare_fixture_response(
            PlatformAdapterFixtureRequest(
                provider_id="reddit.praw",
                operation_id="fixture:reddit.praw:search",
                endpoint="search",
                fixture_limit=1,
                max_response_bytes=1,
            )
        )


def test_adapter_maps_internal_payload_failure_to_one_sanitized_error() -> None:
    def leaking_builder(*, endpoint: str, fixture_limit: int) -> dict[str, Any]:
        _ = (endpoint, fixture_limit)
        raise RuntimeError("secret-value-from-provider")

    def unused_normalizer(
        *,
        endpoint: str,
        response_payload: object,
        evidence_refs: tuple[str, ...],
    ) -> tuple[PlatformAdapterNormalizedRecord, ...]:
        _ = (endpoint, response_payload, evidence_refs)
        raise AssertionError("normalizer_should_not_run")

    adapter = FixtureOnlyPlatformAdapter(
        metadata=SocialAdapterMetadata(
            provider_id="fixture.test",
            platform="fixture",
            sdk_package="fixture-sdk",
            sdk_import_name=None,
            adapter_module="fixture.module",
        ),
        fixture_response_builder=leaking_builder,
        fixture_response_normalizer=unused_normalizer,
    )
    request = PlatformAdapterFixtureRequest(
        provider_id="fixture.test",
        operation_id="fixture:fixture.test:search",
        endpoint="search",
        fixture_limit=1,
        max_response_bytes=16_384,
    )

    with pytest.raises(PlatformAdapterOutputError) as exc_info:
        adapter.prepare_fixture_response(request)

    assert str(exc_info.value) == "platform_adapter_response_invalid"
    assert exc_info.value.code == "platform_adapter_response_invalid"
    assert "secret-value-from-provider" not in repr(exc_info.value)


@pytest.mark.parametrize(
    ("platform", "endpoint", "expected_post_id"),
    [
        ("youtube", "videos.list", "yt_fixture_video_1"),
        ("reddit", "comments.new", "reddit_fixture_post_1"),
    ],
)
def test_business_raw_preview_consumes_only_adapter_normalized_records(
    platform: str,
    endpoint: str,
    expected_post_id: str,
) -> None:
    preview = prepare_social_raw_preview(
        SocialRawPreviewRequest(
            platform=platform,
            endpoint=endpoint,
            fixture_limit=1,
        )
    )

    assert preview.blocked_reasons == []
    assert len(preview.records) == 1
    assert preview.records[0].payload["post_id"] == expected_post_id
    assert preview.records[0].payload["provider_call"] is False
    assert {"content_id", "subreddit", "channel_id"}.isdisjoint(preview.records[0].payload)


def test_business_service_does_not_define_youtube_or_reddit_raw_payloads() -> None:
    source = getsource(social_provider_service)

    assert "yt_fixture_video_" not in source
    assert "reddit_fixture_post_" not in source
    assert "PLATFORM_ADAPTER" in source

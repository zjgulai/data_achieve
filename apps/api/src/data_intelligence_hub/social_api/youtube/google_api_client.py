from __future__ import annotations

from typing import Any, Literal

from pydantic import JsonValue

from data_intelligence_hub.social_api.contracts import (
    FixtureOnlyPlatformAdapter,
    PlatformAdapter,
    SocialAdapterMetadata,
    build_fixture_operations,
)
from data_intelligence_hub.social_api.output_contracts import (
    PlatformAdapterNormalizedRecord,
    canonical_platform_payload_digest,
)

_METADATA = SocialAdapterMetadata(
    provider_id="youtube.v3",
    platform="youtube",
    sdk_package="google-api-python-client",
    sdk_import_name="googleapiclient",
    adapter_module="data_intelligence_hub.social_api.youtube.google_api_client",
)


def _fixture_response_builder(*, endpoint: str, fixture_limit: int) -> JsonValue:
    return {
        "kind": "youtube#fixtureListResponse",
        "endpoint": endpoint,
        "items": [
            {
                "content_id": f"yt_fixture_video_{index}",
                "title": f"YouTube fixture video {index}",
                "channel_id": f"yt_fixture_channel_{index}",
                "comment_count": 12 + index,
            }
            for index in range(1, fixture_limit + 1)
        ],
    }


def _required_string(item: dict[str, JsonValue], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError("youtube_fixture_field_invalid")
    return value


def _required_int(item: dict[str, JsonValue], name: str) -> int:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("youtube_fixture_field_invalid")
    return value


def _fixture_response_normalizer(
    *,
    endpoint: str,
    response_payload: JsonValue,
    evidence_refs: tuple[str, ...],
) -> tuple[PlatformAdapterNormalizedRecord, ...]:
    if not isinstance(response_payload, dict):
        raise ValueError("youtube_fixture_response_invalid")
    items = response_payload.get("items")
    if not isinstance(items, list) or len(items) != len(evidence_refs):
        raise ValueError("youtube_fixture_response_invalid")

    records: list[PlatformAdapterNormalizedRecord] = []
    for index, (item, evidence_ref) in enumerate(zip(items, evidence_refs, strict=True), start=1):
        if not isinstance(item, dict):
            raise ValueError("youtube_fixture_item_invalid")
        content_id = _required_string(item, "content_id")
        title = _required_string(item, "title")
        comment_count = _required_int(item, "comment_count")
        record_type: Literal["post", "comment"] = (
            "comment" if "comment" in endpoint.lower() else "post"
        )
        records.append(
            PlatformAdapterNormalizedRecord(
                raw_record_id=f"fixture:{_METADATA.provider_id}:{endpoint}:{index}",
                provider_id=_METADATA.provider_id,
                platform=_METADATA.platform,
                endpoint=endpoint,
                source_ref=f"{_METADATA.provider_id}:{endpoint}",
                evidence_ref=evidence_ref,
                record_type=record_type,
                external_post_id=content_id,
                external_comment_id=(
                    f"{content_id}:comment:{index}" if record_type == "comment" else None
                ),
                text=title,
                metrics={"comment_count": comment_count},
                payload_digest=canonical_platform_payload_digest(item),
            )
        )
    return tuple(records)


PLATFORM_ADAPTER: PlatformAdapter = FixtureOnlyPlatformAdapter(
    metadata=_METADATA,
    fixture_response_builder=_fixture_response_builder,
    fixture_response_normalizer=_fixture_response_normalizer,
)


def adapter_metadata() -> SocialAdapterMetadata:
    return _METADATA


def plan_fixture_operations(
    *,
    endpoints: list[str],
    fixture_limit: int,
) -> list[dict[str, Any]]:
    return build_fixture_operations(
        provider_id=_METADATA.provider_id,
        endpoints=endpoints,
        fixture_limit=fixture_limit,
        sdk_package=_METADATA.sdk_package,
    )

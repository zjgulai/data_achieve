from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue, ValidationError

from data_intelligence_hub.schemas.youtube_read_adapter import (
    YouTubeKeywordVideoQuery,
    YouTubeReadPlanRequest,
)
from data_intelligence_hub.services.social_provider import get_social_provider_catalog
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.social_api.youtube import fixtures as youtube_fixtures
from data_intelligence_hub.social_api.youtube.compiler import (
    build_youtube_quota_plan,
    compile_youtube_keyword_video_query,
)
from data_intelligence_hub.social_api.youtube.contracts import YouTubeQuotaEvidence
from data_intelligence_hub.social_api.youtube.fixtures import (
    YouTubeFixtureContractInvalidError,
    load_youtube_read_fixture,
)
from data_intelligence_hub.social_api.youtube.foundation import (
    YouTubeLiveExecutionDisabledError,
    prepare_youtube_read_adapter_foundation,
    reject_youtube_live_execution,
)
from data_intelligence_hub.social_api.youtube.normalizer import (
    YouTubeNormalizedPayloadInvalidError,
    build_youtube_read_fixture_envelope,
    normalize_youtube_read_fixture,
)

_SOURCE_FIXTURE_ROOT = youtube_fixtures.YOUTUBE_READ_FIXTURE_ROOT


def _query() -> YouTubeKeywordVideoQuery:
    return YouTubeKeywordVideoQuery(
        query="agentic workflows",
        published_after=datetime(2026, 7, 1, tzinfo=UTC),
        published_before=datetime(2026, 7, 17, tzinfo=UTC),
        region_code="US",
        relevance_language="en",
        order="relevance",
        max_items=50,
    )


def _isolated_fixture_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    root = tmp_path / "youtube-fixtures"
    shutil.copytree(_SOURCE_FIXTURE_ROOT, root)
    monkeypatch.setattr(youtube_fixtures, "YOUTUBE_READ_FIXTURE_ROOT", root)
    monkeypatch.setattr(youtube_fixtures, "YOUTUBE_READ_FIXTURE_MANIFEST", root / "manifest.json")
    return root


def _read_fixture_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_fixture_and_refresh_hash(root: Path, *, kind: str, payload: dict[str, Any]) -> None:
    manifest_path = root / "manifest.json"
    manifest = _read_fixture_json(manifest_path)
    entry = next(item for item in manifest["entries"] if item["kind"] == kind)
    target = root / entry["relative_path"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    entry["expected_sha256"] = sha256_id(cast(JsonValue, payload))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_youtube_read_request_is_strict_and_secret_safe() -> None:
    request = YouTubeReadPlanRequest(
        query=_query(),
        credential_reference="env:YOUTUBE_API_KEY",
    )

    assert request.credential_reference == "env:YOUTUBE_API_KEY"

    with pytest.raises(ValidationError):
        YouTubeReadPlanRequest.model_validate(
            {
                "query": {"query": "agentic workflows"},
                "api_key": "must-not-be-accepted",
            }
        )
    with pytest.raises(ValidationError):
        YouTubeReadPlanRequest(query=_query(), credential_reference="raw-secret")
    with pytest.raises(ValidationError):
        YouTubeKeywordVideoQuery(
            query="agentic workflows",
            published_after=datetime(2026, 7, 17, tzinfo=UTC),
            published_before=datetime(2026, 7, 1, tzinfo=UTC),
        )
    for query in ("\nagentic workflows", "agentic\x7fworkflows", "agentic\u200bworkflows"):
        with pytest.raises(ValidationError):
            YouTubeKeywordVideoQuery(query=query)
    with pytest.raises(ValidationError):
        YouTubeReadPlanRequest(query=_query(), credential_reference="\nenv:YOUTUBE_API_KEY")


def test_youtube_compiler_deduplicates_ids_and_bounds_operations() -> None:
    plan = compile_youtube_keyword_video_query(
        _query(),
        video_ids=["video-b", "video-a", "video-b"],
    )

    assert [item.method for item in plan.operations] == ["search.list", "videos.list"]
    assert plan.video_ids == ("video-b", "video-a")
    assert plan.operations[0].max_items == 50
    assert plan.operations[1].item_count == 2
    assert plan.operations[1].conditional is True

    empty = compile_youtube_keyword_video_query(_query(), video_ids=[])
    assert [item.method for item in empty.operations] == ["search.list"]
    assert empty.video_ids == ()

    overflow = compile_youtube_keyword_video_query(
        _query(),
        video_ids=[f"video-{index}" for index in range(60)],
    )
    assert len(overflow.video_ids) == 50
    assert overflow.operations[1].item_count == 50

    with pytest.raises(ValueError, match="youtube_video_id_invalid"):
        compile_youtube_keyword_video_query(_query(), video_ids=["bad/value"])


def test_youtube_quota_plan_is_method_scoped_and_fails_stale() -> None:
    loaded = load_youtube_read_fixture()
    now = datetime(2026, 7, 19, tzinfo=UTC)

    quota = build_youtube_quota_plan(loaded.quota, detail_required=True, now=now)

    assert [item.method for item in quota.entries] == ["search.list", "videos.list"]
    assert [item.units_per_request for item in quota.entries] == [1, 1]
    assert [item.bucket for item in quota.entries] == [
        "youtube_search_queries",
        "youtube_data_daily_units",
    ]
    provider = get_social_provider_catalog(platform="youtube").providers[0]
    assert provider.quota_hint["soft_limits"]["search.list"] == 100
    assert quota.min_requests == 1
    assert quota.max_requests == 2
    assert quota.fresh is True

    stale = build_youtube_quota_plan(
        loaded.quota,
        detail_required=True,
        now=loaded.quota.observed_at + timedelta(days=31),
    )
    assert stale.fresh is False
    assert "youtube_quota_evidence_stale" in stale.blocked_reasons

    with pytest.raises(ValueError, match="youtube_quota_now_timezone_required"):
        build_youtube_quota_plan(
            loaded.quota,
            detail_required=True,
            now=datetime(2026, 7, 17),
        )

    quota_payload = loaded.quota.model_dump(mode="json")
    quota_payload["entries"][0]["units_per_request"] = 0
    with pytest.raises(ValidationError):
        YouTubeQuotaEvidence.model_validate(quota_payload)

    quota_payload = loaded.quota.model_dump(mode="json")
    quota_payload["entries"][0]["bucket"] = "wrong_bucket"
    with pytest.raises(ValidationError):
        YouTubeQuotaEvidence.model_validate(quota_payload)

    legacy_quota_payload = loaded.quota.model_dump(mode="json")
    legacy_quota_payload["entries"][0].update(
        bucket="youtube_data_daily_units",
        units_per_request=100,
    )
    with pytest.raises(ValidationError, match="youtube_quota_fact_invalid"):
        YouTubeQuotaEvidence.model_validate(legacy_quota_payload)


def test_youtube_fixture_loader_rejects_hash_and_absolute_path_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _isolated_fixture_root(tmp_path, monkeypatch)
    search_path = root / "search-list-v1.json"
    search = _read_fixture_json(search_path)
    search["response"]["etag"] = "tampered"
    search_path.write_text(json.dumps(search), encoding="utf-8")
    with pytest.raises(YouTubeFixtureContractInvalidError, match="search_hash"):
        load_youtube_read_fixture()

    root = _isolated_fixture_root(tmp_path / "absolute", monkeypatch)
    manifest_path = root / "manifest.json"
    manifest = _read_fixture_json(manifest_path)
    search_entry = next(item for item in manifest["entries"] if item["kind"] == "search")
    search_entry["relative_path"] = str(root / "search-list-v1.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(YouTubeFixtureContractInvalidError, match="registered_path"):
        load_youtube_read_fixture()

    root = _isolated_fixture_root(tmp_path / "manifest", monkeypatch)
    manifest_path = root / "manifest.json"
    manifest = _read_fixture_json(manifest_path)
    manifest["entries"][1]["kind"] = manifest["entries"][0]["kind"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(YouTubeFixtureContractInvalidError, match="manifest_schema"):
        load_youtube_read_fixture()


def test_youtube_fixture_and_normalizer_fail_closed_on_malformed_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _isolated_fixture_root(tmp_path, monkeypatch)
    videos_path = root / "videos-list-v1.json"
    videos = _read_fixture_json(videos_path)
    videos["response"]["items"][0]["statistics"]["viewCount"] = "9" * 5000
    _write_fixture_and_refresh_hash(root, kind="videos", payload=videos)
    with pytest.raises(YouTubeFixtureContractInvalidError, match="snapshot_schema"):
        load_youtube_read_fixture()

    root = _isolated_fixture_root(tmp_path / "duplicate", monkeypatch)
    videos_path = root / "videos-list-v1.json"
    videos = _read_fixture_json(videos_path)
    videos["response"]["items"][1]["id"] = videos["response"]["items"][0]["id"]
    _write_fixture_and_refresh_hash(root, kind="videos", payload=videos)
    loaded = load_youtube_read_fixture()
    with pytest.raises(YouTubeNormalizedPayloadInvalidError, match="detail_id_duplicate"):
        normalize_youtube_read_fixture(loaded)


def test_youtube_fixture_evidence_cardinality_reaches_foundation_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _isolated_fixture_root(tmp_path, monkeypatch)
    quota = _read_fixture_json(root / "quota-v1.json")
    search = _read_fixture_json(root / "search-list-v1.json")
    videos = _read_fixture_json(root / "videos-list-v1.json")
    quota["entries"][0]["evidence_ref"] = "quota-search"
    quota["entries"][1]["evidence_ref"] = "quota-videos"
    search["evidence_refs"] = [f"search-{index}" for index in range(4)]
    videos["evidence_refs"] = [f"videos-{index}" for index in range(4)]
    _write_fixture_and_refresh_hash(root, kind="quota", payload=quota)
    _write_fixture_and_refresh_hash(root, kind="search", payload=search)
    _write_fixture_and_refresh_hash(root, kind="videos", payload=videos)

    provider = get_social_provider_catalog(platform="youtube").providers[0]
    response = prepare_youtube_read_adapter_foundation(
        YouTubeReadPlanRequest(query=_query()),
        provider=provider,
        dependency_present=False,
        now=datetime(2026, 7, 19, tzinfo=UTC),
    )
    assert len(response.fixture_validation.evidence_refs) == 10

    root = _isolated_fixture_root(tmp_path / "mismatch", monkeypatch)
    videos_path = root / "videos-list-v1.json"
    videos = _read_fixture_json(videos_path)
    videos["response"]["items"][1]["id"] = "yt-video-c"
    _write_fixture_and_refresh_hash(root, kind="videos", payload=videos)
    loaded = load_youtube_read_fixture()
    with pytest.raises(
        YouTubeNormalizedPayloadInvalidError,
        match="search_detail_identity_mismatch",
    ):
        normalize_youtube_read_fixture(loaded)


def test_youtube_recorded_fixture_normalizes_to_existing_envelope() -> None:
    loaded = load_youtube_read_fixture()
    records = normalize_youtube_read_fixture(loaded)
    envelope = build_youtube_read_fixture_envelope(loaded)

    assert [item.content["video_id"] for item in records] == ["yt-video-b", "yt-video-a"]
    assert all(item.record_type == "youtube_video" for item in records)
    assert all(item.collected_at.tzinfo is not None for item in records)
    assert envelope.implementation_id == "youtube.v3"
    assert envelope.platform.value == "youtube"
    assert envelope.records == records
    assert envelope.records_count == len(records)


def test_youtube_foundation_is_ready_without_sdk_or_live_authority() -> None:
    provider = get_social_provider_catalog(platform="youtube").providers[0]
    response = prepare_youtube_read_adapter_foundation(
        YouTubeReadPlanRequest(
            query=_query(),
            credential_reference="env:YOUTUBE_API_KEY",
        ),
        provider=provider,
        dependency_present=False,
        now=datetime(2026, 7, 19, tzinfo=UTC),
    )

    assert response.schema_version == "youtube_read_adapter_foundation.v1"
    assert response.foundation_ready is True
    assert response.declared_readiness is True
    assert response.readiness_basis == "caller_declared"
    assert response.execution_enabled is False
    assert response.live_dependency_present is False
    assert response.provider_call_allowed is False
    assert response.provider_call_attempted is False
    assert response.credential_read_attempted is False
    assert response.live_client_created is False
    assert response.database_write is False
    assert response.credential_reference_present is True
    assert response.credential_reference is None
    assert response.query is None
    assert [operation.method for operation in response.operations] == [
        "search.list",
        "videos.list",
    ]
    assert response.operations[1].conditional is True
    assert response.operations[1].item_count == 0

    with pytest.raises(ValueError, match="youtube_foundation_now_timezone_required"):
        prepare_youtube_read_adapter_foundation(
            YouTubeReadPlanRequest(query=_query()),
            provider=provider,
            dependency_present=False,
            now=datetime(2026, 7, 17),
        )

    blocked_provider = provider.model_copy(update={"supported_endpoints": ["search.list"]})
    blocked = prepare_youtube_read_adapter_foundation(
        YouTubeReadPlanRequest(query=_query()),
        provider=blocked_provider,
        dependency_present=False,
        now=datetime(2026, 7, 19, tzinfo=UTC),
    )
    assert blocked.foundation_ready is False
    assert "scope_missing:videos.list" in blocked.blocked_reasons


def test_youtube_live_execution_fails_before_poison_boundaries() -> None:
    class Poison:
        touched = False

        def __getattribute__(self, name: str) -> object:
            if name == "touched":
                return object.__getattribute__(self, name)
            object.__setattr__(self, "touched", True)
            raise AssertionError("poison boundary touched")

    credential_resolver = Poison()
    transport = Poison()

    with pytest.raises(YouTubeLiveExecutionDisabledError, match="youtube_live_execution_disabled"):
        reject_youtube_live_execution(
            credential_resolver=credential_resolver,
            transport=transport,
        )

    assert credential_resolver.touched is False
    assert transport.touched is False

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pydantic import JsonValue, ValidationError

from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.social_api.youtube.contracts import (
    LoadedYouTubeReadFixture,
    YouTubeQuotaEvidence,
    YouTubeReadFixtureManifest,
    YouTubeRecordedSearchSnapshot,
    YouTubeRecordedVideosSnapshot,
)

YOUTUBE_READ_FIXTURE_ROOT = Path(__file__).resolve().with_name("fixtures")
YOUTUBE_READ_FIXTURE_MANIFEST = YOUTUBE_READ_FIXTURE_ROOT / "manifest.json"


class YouTubeFixtureContractInvalidError(ValueError):
    """A server-owned YouTube recorded fixture failed closed validation."""


def _invalid(reason: str) -> YouTubeFixtureContractInvalidError:
    return YouTubeFixtureContractInvalidError(f"youtube_fixture_contract_invalid:{reason}")


def _read_json(path: Path, *, kind: str) -> JsonValue:
    try:
        return cast(JsonValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _invalid(f"{kind}_unreadable") from exc


def _registered_path(relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise _invalid("registered_path")
    try:
        root = YOUTUBE_READ_FIXTURE_ROOT.resolve(strict=True)
        path = (root / candidate).resolve(strict=True)
        path.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _invalid("registered_path") from exc
    if path == root:
        raise _invalid("registered_path")
    return path


def load_youtube_read_fixture() -> LoadedYouTubeReadFixture:
    try:
        manifest = YouTubeReadFixtureManifest.model_validate(
            _read_json(YOUTUBE_READ_FIXTURE_MANIFEST, kind="manifest")
        )
    except ValidationError as exc:
        raise _invalid("manifest_schema") from exc

    payloads: dict[str, JsonValue] = {}
    for entry in manifest.entries:
        payload = _read_json(_registered_path(entry.relative_path), kind=entry.kind)
        if sha256_id(payload) != entry.expected_sha256:
            raise _invalid(f"{entry.kind}_hash")
        payloads[entry.kind] = payload

    try:
        quota = YouTubeQuotaEvidence.model_validate(payloads["quota"])
        search = YouTubeRecordedSearchSnapshot.model_validate(payloads["search"])
        videos = YouTubeRecordedVideosSnapshot.model_validate(payloads["videos"])
    except (KeyError, ValidationError) as exc:
        raise _invalid("snapshot_schema") from exc

    evidence_refs = tuple(
        dict.fromkeys(
            [
                *search.evidence_refs,
                *videos.evidence_refs,
                *(item.evidence_ref for item in quota.entries),
            ]
        )
    )
    snapshot_payload = cast(
        JsonValue,
        {
            "quota": payloads["quota"],
            "search": payloads["search"],
            "videos": payloads["videos"],
        },
    )
    return LoadedYouTubeReadFixture(
        manifest=manifest,
        quota=quota,
        search=search,
        videos=videos,
        snapshot_digest=sha256_id(snapshot_payload),
        evidence_refs=evidence_refs,
    )


__all__ = [
    "LoadedYouTubeReadFixture",
    "YouTubeFixtureContractInvalidError",
    "load_youtube_read_fixture",
]

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue, ValidationError

from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryFixtureManifest,
    CapabilityDiscoveryFixtureManifestEntry,
    CapabilitySourceSnapshotFixture,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_sha256,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryFixtureInvalidError,
    CapabilityDiscoveryFixtureUnknownError,
)

FIXTURE_ROOT_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "capability_discovery"
)
FIXTURE_MANIFEST_PATH = FIXTURE_ROOT_PATH / "manifest.json"


@dataclass(frozen=True, slots=True)
class LoadedCapabilityDiscoveryFixture:
    snapshot: CapabilitySourceSnapshotFixture
    content_hash: str


def _load_manifest() -> CapabilityDiscoveryFixtureManifest:
    try:
        return CapabilityDiscoveryFixtureManifest.model_validate_json(
            FIXTURE_MANIFEST_PATH.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, ValidationError) as exc:
        raise CapabilityDiscoveryFixtureInvalidError from exc


def _manifest_entry(
    manifest: CapabilityDiscoveryFixtureManifest,
    fixture_id: str,
) -> CapabilityDiscoveryFixtureManifestEntry:
    for entry in manifest.fixtures:
        if entry.fixture_id == fixture_id:
            return entry
    raise CapabilityDiscoveryFixtureUnknownError


def _fixture_path(entry: CapabilityDiscoveryFixtureManifestEntry) -> Path:
    try:
        fixture_root = FIXTURE_MANIFEST_PATH.resolve(strict=True).parent
        fixture_path = (fixture_root / entry.relative_path).resolve(strict=False)
    except OSError as exc:
        raise CapabilityDiscoveryFixtureInvalidError from exc
    if fixture_path == fixture_root or not fixture_path.is_relative_to(fixture_root):
        raise CapabilityDiscoveryFixtureInvalidError
    return fixture_path


def _read_fixture_json(fixture_path: Path) -> JsonValue:
    try:
        value: JsonValue = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapabilityDiscoveryFixtureInvalidError from exc
    return value


def load_capability_discovery_fixture(
    fixture_id: str,
) -> LoadedCapabilityDiscoveryFixture:
    manifest = _load_manifest()
    entry = _manifest_entry(manifest, fixture_id)
    fixture_path = _fixture_path(entry)
    raw_fixture = _read_fixture_json(fixture_path)
    try:
        content_hash = canonical_json_sha256(raw_fixture)
        snapshot = CapabilitySourceSnapshotFixture.model_validate(raw_fixture)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityDiscoveryFixtureInvalidError from exc
    if content_hash != entry.expected_sha256:
        raise CapabilityDiscoveryFixtureInvalidError
    if snapshot.fixture_id != entry.fixture_id or snapshot.parser_id != entry.parser_id:
        raise CapabilityDiscoveryFixtureInvalidError
    return LoadedCapabilityDiscoveryFixture(
        snapshot=snapshot.model_copy(deep=True),
        content_hash=content_hash,
    )


def load_capability_discovery_fixtures(
    fixture_ids: Sequence[str],
) -> list[LoadedCapabilityDiscoveryFixture]:
    return [load_capability_discovery_fixture(fixture_id) for fixture_id in fixture_ids]

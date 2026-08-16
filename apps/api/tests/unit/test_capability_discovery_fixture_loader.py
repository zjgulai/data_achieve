from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryParserId,
    CapabilitySourceSnapshotFixture,
)
from data_intelligence_hub.services.capability_discovery import fixture_loader
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_bytes,
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.fixture_loader import (
    load_capability_discovery_fixture,
    load_capability_discovery_fixtures,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryFixtureInvalidError,
    CapabilityDiscoveryFixtureUnknownError,
)

OBSERVED_AT = "2026-07-14T08:00:00Z"
PARSER_IDS = list(CapabilityDiscoveryParserId)


def _snapshot_payload(index: int) -> dict[str, JsonValue]:
    parser_id = PARSER_IDS[index]
    source_kind = "public_market" if index < 2 else "official_doc"
    return {
        "schema_version": "capability_source_snapshot_fixture.v1",
        "fixture_id": f"fixture-{index}",
        "source_kind": source_kind,
        "source_name": f"Source {index}",
        "source_url": f"https://example.com/source-{index}",
        "source_version": "public-page-2026-07-14",
        "observed_at": OBSERVED_AT,
        "parser_id": parser_id.value,
        "payload": {
            "provider_id": f"provider.{index}",
            "claims": [{"claim_ref": f"claim:{index}"}],
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_valid_fixture_set(root: Path) -> tuple[Path, list[dict[str, JsonValue]]]:
    root.mkdir(parents=True)
    entries: list[dict[str, JsonValue]] = []
    for index, parser_id in enumerate(PARSER_IDS):
        payload = _snapshot_payload(index)
        relative_path = f"fixture-{index}.json"
        _write_json(root / relative_path, payload)
        entries.append(
            {
                "fixture_id": f"fixture-{index}",
                "relative_path": relative_path,
                "parser_id": parser_id.value,
                "expected_sha256": canonical_json_sha256(payload),
            }
        )

    manifest_path = root / "manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries,
        },
    )
    return manifest_path, entries


def _use_manifest(monkeypatch: pytest.MonkeyPatch, manifest_path: Path) -> None:
    monkeypatch.setattr(
        fixture_loader,
        "FIXTURE_MANIFEST_PATH",
        manifest_path,
    )


def test_canonical_json_is_compact_sorted_utf8_and_hash_stable() -> None:
    left: JsonValue = {
        "snow": "雪",
        "nested": {"z": None, "a": [3, True]},
        "count": 2,
    }
    right: JsonValue = {
        "count": 2,
        "nested": {"a": [3, True], "z": None},
        "snow": "雪",
    }
    expected = (
        b'{"count":2,"nested":{"a":[3,true],"z":null},'
        b'"snow":"\xe9\x9b\xaa"}'
    )

    assert canonical_json_bytes(left) == expected
    assert canonical_json_bytes(right) == expected
    assert canonical_json_sha256(left) == hashlib.sha256(expected).hexdigest()
    assert canonical_json_sha256(right) == canonical_json_sha256(left)


def test_default_manifest_loads_exactly_four_registered_snapshots() -> None:
    loaded = load_capability_discovery_fixtures(
        [
            "tikhub-youtube-market-v1",
            "apify-reddit-market-v1",
            "youtube-data-api-doc-v1",
            "reddit-data-api-doc-v1",
        ]
    )

    assert [item.snapshot.fixture_id for item in loaded] == [
        "tikhub-youtube-market-v1",
        "apify-reddit-market-v1",
        "youtube-data-api-doc-v1",
        "reddit-data-api-doc-v1",
    ]
    assert len({item.content_hash for item in loaded}) == 4
    assert all(len(item.content_hash) == 64 for item in loaded)
    assert "expected_sha256" not in CapabilitySourceSnapshotFixture.model_fields


def test_loader_returns_independent_deep_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _ = _write_valid_fixture_set(tmp_path / "fixtures")
    _use_manifest(monkeypatch, manifest_path)

    first = load_capability_discovery_fixture("fixture-0")
    second = load_capability_discovery_fixture("fixture-0")
    first.snapshot.payload["claims"] = [{"claim_ref": "mutated"}]

    assert first is not second
    assert first.snapshot is not second.snapshot
    assert second.snapshot.payload["claims"] == [{"claim_ref": "claim:0"}]
    assert first.content_hash == second.content_hash


def test_loader_rejects_manifest_external_fixture_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, _ = _write_valid_fixture_set(tmp_path / "fixtures")
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureUnknownError):
        load_capability_discovery_fixture("not-registered")


def test_loader_rejects_path_escape_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "fixtures"
    manifest_path, entries = _write_valid_fixture_set(root)
    outside = tmp_path / "outside.json"
    outside_payload = _snapshot_payload(0)
    _write_json(outside, outside_payload)
    entries[0]["relative_path"] = "../outside.json"
    entries[0]["expected_sha256"] = canonical_json_sha256(outside_payload)
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries,
        },
    )
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")


def test_loader_rejects_missing_fixture_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, entries = _write_valid_fixture_set(tmp_path / "fixtures")
    entries[0]["relative_path"] = "missing.json"
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries,
        },
    )
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")


def test_loader_rejects_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "fixtures"
    manifest_path, _ = _write_valid_fixture_set(root)
    (root / "fixture-0.json").write_text("{invalid", encoding="utf-8")
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")


def test_loader_rejects_schema_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "fixtures"
    manifest_path, entries = _write_valid_fixture_set(root)
    invalid_schema: JsonValue = {
        "schema_version": "capability_source_snapshot_fixture.v1",
        "fixture_id": "fixture-0",
    }
    _write_json(root / "fixture-0.json", invalid_schema)
    entries[0]["expected_sha256"] = canonical_json_sha256(invalid_schema)
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries,
        },
    )
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")


def test_loader_rejects_parser_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, entries = _write_valid_fixture_set(tmp_path / "fixtures")
    entries[0]["parser_id"] = CapabilityDiscoveryParserId.APIFY_PUBLIC_MARKET_V1.value
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries,
        },
    )
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")


def test_loader_rejects_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, entries = _write_valid_fixture_set(tmp_path / "fixtures")
    entries[0]["expected_sha256"] = "0" * 64
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries,
        },
    )
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")


def test_loader_rejects_invalid_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, entries = _write_valid_fixture_set(tmp_path / "fixtures")
    _write_json(
        manifest_path,
        {
            "schema_version": "capability_discovery_fixture_manifest.v1",
            "fixtures": entries[:3],
        },
    )
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(CapabilityDiscoveryFixtureInvalidError):
        load_capability_discovery_fixture("fixture-0")

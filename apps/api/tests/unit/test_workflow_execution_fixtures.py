from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.services.workflow_execution import fixtures
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
    build_primary_execution_contracts,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixtureAdapterUnavailableError,
    WorkflowFixtureContractInvalidError,
    WorkflowFixtureProfileUnknownError,
    execute_workflow_fixture_step,
    load_workflow_fixture_profile,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

PLANNER_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = PLANNER_FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = (
    PLANNER_FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
)
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000401")
NOW = datetime(2026, 7, 15, 11, 0, tzinfo=UTC)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _case_payload(**updates: object) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "case_id": "fixture-primary-content-search-v1",
        "implementation_id": "fixture.primary",
        "platform": "youtube",
        "resource_type": "content",
        "operation": "search_discover",
        "records_count": 2,
        "evidence_refs": ["evidence:fixture.primary:content:search_discover"],
        "summary": {
            "result_kind": "fixture_receipt",
            "fields": ["id", "text", "url"],
        },
    }
    payload.update(cast(dict[str, JsonValue], updates))
    return payload


def _profile_payload(*, cases: list[dict[str, JsonValue]] | None = None) -> dict[str, JsonValue]:
    return {
        "schema_version": "workflow_fixture_profile.v1",
        "profile_id": "fixture-primary-v1",
        "cases": cast(JsonValue, cases or [_case_payload()]),
    }


def _write_fixture_set(
    root: Path,
    *,
    profile: dict[str, JsonValue] | None = None,
) -> Path:
    root.mkdir(parents=True)
    profile_payload = profile or _profile_payload()
    profile_path = root / "fixture-primary-v1.json"
    _write_json(profile_path, profile_payload)
    manifest_path = root / "manifest.json"
    _write_json(
        manifest_path,
        {
            "schema_version": "workflow_fixture_manifest.v1",
            "profiles": [
                {
                    "profile_id": "fixture-primary-v1",
                    "relative_path": "fixture-primary-v1.json",
                    "profile_schema_version": "workflow_fixture_profile.v1",
                    "expected_sha256": sha256_id(cast(JsonValue, profile_payload)),
                    "allowed_implementation_ids": ["fixture.primary"],
                }
            ],
        },
    )
    return manifest_path


def _use_manifest(monkeypatch: pytest.MonkeyPatch, manifest_path: Path) -> None:
    monkeypatch.setattr(fixtures, "WORKFLOW_FIXTURE_MANIFEST_PATH", manifest_path)


def _resolved_contracts() -> tuple[PrimaryExecutionContract, ...]:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = ["id", "url", "text"]
    preview = build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=PlanningInput.model_validate(payload),
        catalog=CapabilityCatalog.model_validate_json(
            SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
        ),
        generated_at=NOW,
        request_id="workflow-fixture-test",
    )
    return build_primary_execution_contracts(preview)


def test_default_profile_registers_exact_primary_only_coverage() -> None:
    loaded = load_workflow_fixture_profile("fixture-primary-v1")
    keys = {
        (
            item.implementation_id,
            item.platform.value,
            item.resource_type.value,
            item.operation.value,
        )
        for item in loaded.profile.cases
    }

    assert loaded.profile.profile_id == "fixture-primary-v1"
    assert loaded.profile_hash.startswith("sha256:")
    assert loaded.allowed_implementation_ids == (
        "fixture.primary",
        "reddit.praw",
        "youtube.v3",
    )
    assert len(keys) == len(loaded.profile.cases) == 14
    assert ("youtube.v3", "youtube", "content", "search_discover") in keys
    assert ("reddit.praw", "reddit", "content", "search_discover") in keys
    assert ("fixture.primary", "youtube", "content", "batch_parse") in keys
    assert all("fallback" not in item[0] for item in keys)


def test_exact_primary_contracts_return_deterministic_receipts() -> None:
    loaded = load_workflow_fixture_profile("fixture-primary-v1")
    contracts = build_primary_execution_contracts(
        build_workflow_plan_preview(
            project_id=PROJECT_ID,
            planning_input=PlanningInput.model_validate_json(
                PERIODIC_FIXTURE.read_text(encoding="utf-8")
            ).model_copy(update={"required_fields": ["id", "url", "text"]}),
            catalog=CapabilityCatalog.model_validate_json(
                SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
            ),
            generated_at=NOW,
            request_id="workflow-fixture-receipt-test",
        )
    )

    receipts = [
        execute_workflow_fixture_step(loaded, contract) for contract in contracts
    ]
    repeated = [
        execute_workflow_fixture_step(loaded, contract) for contract in contracts
    ]

    assert receipts == repeated
    assert all(item.records_count >= 1 for item in receipts)
    assert all(item.output_digest.startswith("sha256:") for item in receipts)
    assert all(item.provider_call_attempted is False for item in receipts)
    assert all(item.credential_read_attempted is False for item in receipts)
    assert [item.evidence_refs for item in receipts] == [
        item.primary.evidence_refs for item in contracts
    ]


def test_loader_returns_independent_deep_copies() -> None:
    first = load_workflow_fixture_profile("fixture-primary-v1")
    second = load_workflow_fixture_profile("fixture-primary-v1")
    first.profile.cases[0].summary.fields.append("mutated")

    assert first is not second
    assert first.profile is not second.profile
    assert "mutated" not in second.profile.cases[0].summary.fields
    assert first.profile_hash == second.profile_hash


def test_unknown_profile_is_distinct_from_invalid_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_fixture_set(tmp_path / "fixtures")
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(WorkflowFixtureProfileUnknownError):
        load_workflow_fixture_profile("not-registered")


def test_loader_rejects_path_escape_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "fixtures"
    manifest_path = _write_fixture_set(root)
    outside = tmp_path / "outside.json"
    profile = _profile_payload()
    _write_json(outside, profile)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["profiles"][0]["relative_path"] = "../outside.json"
    manifest["profiles"][0]["expected_sha256"] = sha256_id(
        cast(JsonValue, profile)
    )
    _write_json(manifest_path, manifest)
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(WorkflowFixtureContractInvalidError):
        load_workflow_fixture_profile("fixture-primary-v1")


@pytest.mark.parametrize(
    "invalid_kind",
    ["hash", "schema", "duplicate", "unexpected"],
)
def test_loader_rejects_invalid_profile_contracts(
    invalid_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "fixtures"
    profile = _profile_payload()
    if invalid_kind == "schema":
        profile["schema_version"] = "workflow_fixture_profile.v2"
    elif invalid_kind == "duplicate":
        cases = cast(list[dict[str, JsonValue]], profile["cases"])
        profile["cases"] = [cases[0], dict(cases[0])]
    elif invalid_kind == "unexpected":
        profile["raw_payload"] = {"secret": "forbidden"}
    manifest_path = _write_fixture_set(root, profile=profile)
    if invalid_kind == "hash":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["profiles"][0]["expected_sha256"] = "sha256:" + "0" * 64
        _write_json(manifest_path, manifest)
    _use_manifest(monkeypatch, manifest_path)

    with pytest.raises(WorkflowFixtureContractInvalidError):
        load_workflow_fixture_profile("fixture-primary-v1")


def test_loader_accepts_zero_records_as_verified_empty_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile_payload(cases=[_case_payload(records_count=0)])
    manifest_path = _write_fixture_set(tmp_path / "fixtures", profile=profile)
    _use_manifest(monkeypatch, manifest_path)

    loaded = load_workflow_fixture_profile("fixture-primary-v1")
    case = loaded.profile.cases[0]
    contract = next(
        item
        for item in _resolved_contracts()
        if item.primary.implementation_id == case.implementation_id
        and item.requirement.platform is case.platform
        and item.requirement.resource_type is case.resource_type
        and item.requirement.operation is case.operation
    )
    receipt = execute_workflow_fixture_step(loaded, contract)

    assert receipt.records_count == 0
    assert receipt.output_digest.startswith("sha256:")


def test_exact_case_missing_fails_without_platform_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_fixture_set(tmp_path / "fixtures")
    _use_manifest(monkeypatch, manifest_path)
    loaded = load_workflow_fixture_profile("fixture-primary-v1")
    contract = _resolved_contracts()[1]

    with pytest.raises(WorkflowFixtureAdapterUnavailableError):
        execute_workflow_fixture_step(loaded, contract)


def test_receipt_schema_exposes_no_raw_payload_field() -> None:
    loaded = load_workflow_fixture_profile("fixture-primary-v1")
    receipt = execute_workflow_fixture_step(
        loaded,
        _resolved_contracts()[0],
    )

    serialized = receipt.model_dump(mode="json")
    assert "raw_payload" not in serialized
    assert "fixture_body" not in serialized
    assert serialized["summary"]["result_kind"] == "fixture_receipt"

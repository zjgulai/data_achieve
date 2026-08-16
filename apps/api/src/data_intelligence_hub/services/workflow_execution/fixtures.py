from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast

from pydantic import Field, JsonValue, ValidationError, model_validator

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_execution import (
    FixtureProfileId,
    Sha256Digest,
    WorkflowExecutionContract,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowProviderPayloadEnvelope,
    WorkflowProviderPayloadRecord,
    compute_workflow_provider_payload_digest,
)
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

WORKFLOW_FIXTURE_MANIFEST_PATH = Path(__file__).resolve().with_name("fixtures") / ("manifest.json")


class WorkflowFixtureProfileUnknownError(ValueError):
    """The requested fixture profile is not registered by the server."""


class WorkflowFixtureContractInvalidError(ValueError):
    """A registered fixture manifest or profile failed closed validation."""


class WorkflowFixtureAdapterUnavailableError(ValueError):
    """No exact registered fixture case exists for a Primary contract."""


class WorkflowFixturePayloadUnboundError(ValueError):
    """The historical fixture receipt does not bind canonical record bodies."""


class WorkflowFixtureManifestEntry(WorkflowExecutionContract):
    profile_id: FixtureProfileId
    relative_path: str = Field(min_length=1, max_length=500)
    profile_schema_version: Literal[
        "workflow_fixture_profile.v1",
        "workflow_fixture_profile.v2",
    ]
    expected_sha256: Sha256Digest
    allowed_implementation_ids: list[str] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_implementation_ids(self) -> Self:
        if any(not item or len(item) > 500 for item in self.allowed_implementation_ids):
            raise ValueError("workflow_fixture_implementation_id_invalid")
        if len(self.allowed_implementation_ids) != len(set(self.allowed_implementation_ids)):
            raise ValueError("workflow_fixture_implementation_id_duplicate")
        return self


class WorkflowFixtureManifest(WorkflowExecutionContract):
    schema_version: Literal["workflow_fixture_manifest.v1"]
    profiles: list[WorkflowFixtureManifestEntry] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_profile_registration(self) -> Self:
        profile_ids = [item.profile_id for item in self.profiles]
        relative_paths = [item.relative_path for item in self.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("workflow_fixture_profile_duplicate")
        if len(relative_paths) != len(set(relative_paths)):
            raise ValueError("workflow_fixture_path_duplicate")
        return self


class WorkflowFixtureSummary(WorkflowExecutionContract):
    result_kind: Literal["fixture_receipt"]
    fields: list[str] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_fields(self) -> Self:
        if any(not item or len(item) > 200 for item in self.fields):
            raise ValueError("workflow_fixture_summary_field_invalid")
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("workflow_fixture_summary_field_duplicate")
        return self


class WorkflowFixtureCase(WorkflowExecutionContract):
    case_id: str = Field(min_length=1, max_length=200)
    implementation_id: str = Field(min_length=1, max_length=500)
    platform: PlatformId
    resource_type: ResourceType
    operation: CapabilityOperation
    records_count: int = Field(ge=0)
    evidence_refs: list[str] = Field(min_length=1, max_length=64)
    summary: WorkflowFixtureSummary
    records: list[WorkflowProviderPayloadRecord] | None = Field(
        default=None,
        max_length=1000,
    )

    @model_validator(mode="after")
    def validate_evidence_refs(self) -> Self:
        if any(not item or len(item) > 500 for item in self.evidence_refs):
            raise ValueError("workflow_fixture_evidence_ref_invalid")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_fixture_evidence_ref_duplicate")
        return self


class WorkflowFixtureProfile(WorkflowExecutionContract):
    schema_version: Literal[
        "workflow_fixture_profile.v1",
        "workflow_fixture_profile.v2",
    ]
    profile_id: FixtureProfileId
    cases: list[WorkflowFixtureCase] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_case_registration(self) -> Self:
        case_ids = [item.case_id for item in self.cases]
        case_keys = [
            (
                item.implementation_id,
                item.platform,
                item.resource_type,
                item.operation,
            )
            for item in self.cases
        ]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("workflow_fixture_case_id_duplicate")
        if len(case_keys) != len(set(case_keys)):
            raise ValueError("workflow_fixture_case_key_duplicate")
        if self.schema_version == "workflow_fixture_profile.v1":
            if any(item.records is not None for item in self.cases):
                raise ValueError("workflow_fixture_v1_payload_forbidden")
        else:
            if any(item.records is None for item in self.cases):
                raise ValueError("workflow_fixture_v2_payload_required")
            if any(len(item.records or []) != item.records_count for item in self.cases):
                raise ValueError("workflow_fixture_payload_count_mismatch")
        return self


class WorkflowFixtureStepReceipt(WorkflowExecutionContract):
    fixture_case_id: str = Field(min_length=1, max_length=200)
    fixture_content_hash: Sha256Digest
    records_count: int = Field(ge=0)
    evidence_refs: list[str] = Field(min_length=1, max_length=64)
    summary: WorkflowFixtureSummary
    payload_digest: Sha256Digest | None = None
    output_digest: Sha256Digest
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False


@dataclass(frozen=True, slots=True)
class LoadedWorkflowFixtureProfile:
    profile: WorkflowFixtureProfile
    profile_hash: Sha256Digest
    allowed_implementation_ids: tuple[str, ...]


def _invalid_contract(reason: str) -> WorkflowFixtureContractInvalidError:
    return WorkflowFixtureContractInvalidError(f"workflow_fixture_contract_invalid:{reason}")


def _read_json(path: Path, *, kind: str) -> JsonValue:
    try:
        return cast(JsonValue, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _invalid_contract(f"{kind}_unreadable") from exc


def _load_manifest() -> WorkflowFixtureManifest:
    try:
        return WorkflowFixtureManifest.model_validate(
            _read_json(WORKFLOW_FIXTURE_MANIFEST_PATH, kind="manifest")
        )
    except ValidationError as exc:
        raise _invalid_contract("manifest_schema") from exc


def _registered_profile_path(entry: WorkflowFixtureManifestEntry) -> Path:
    try:
        fixture_root = WORKFLOW_FIXTURE_MANIFEST_PATH.parent.resolve(strict=True)
        profile_path = (fixture_root / entry.relative_path).resolve(strict=False)
        profile_path.relative_to(fixture_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _invalid_contract("profile_path") from exc
    if profile_path == fixture_root:
        raise _invalid_contract("profile_path")
    return profile_path


def load_workflow_fixture_profile(
    profile_id: FixtureProfileId,
) -> LoadedWorkflowFixtureProfile:
    manifest = _load_manifest()
    entry = next(
        (item for item in manifest.profiles if item.profile_id == profile_id),
        None,
    )
    if entry is None:
        raise WorkflowFixtureProfileUnknownError("workflow_fixture_profile_unknown")

    profile_payload = _read_json(_registered_profile_path(entry), kind="profile")
    profile_hash = sha256_id(profile_payload)
    if profile_hash != entry.expected_sha256:
        raise _invalid_contract("profile_hash")
    try:
        profile = WorkflowFixtureProfile.model_validate(profile_payload)
    except ValidationError as exc:
        raise _invalid_contract("profile_schema") from exc
    if (
        profile.profile_id != entry.profile_id
        or profile.schema_version != entry.profile_schema_version
    ):
        raise _invalid_contract("profile_identity")
    implementation_ids = {item.implementation_id for item in profile.cases}
    if implementation_ids != set(entry.allowed_implementation_ids):
        raise _invalid_contract("implementation_registration")

    return LoadedWorkflowFixtureProfile(
        profile=profile.model_copy(deep=True),
        profile_hash=profile_hash,
        allowed_implementation_ids=tuple(sorted(entry.allowed_implementation_ids)),
    )


def execute_workflow_fixture_step(
    loaded: LoadedWorkflowFixtureProfile,
    contract: PrimaryExecutionContract,
) -> WorkflowFixtureStepReceipt:
    case = next(
        (
            item
            for item in loaded.profile.cases
            if item.implementation_id == contract.primary.implementation_id
            and item.platform is contract.requirement.platform
            and item.resource_type is contract.requirement.resource_type
            and item.operation is contract.requirement.operation
        ),
        None,
    )
    if case is None:
        raise WorkflowFixtureAdapterUnavailableError("workflow_fixture_adapter_unavailable")
    if case.implementation_id not in loaded.allowed_implementation_ids:
        raise _invalid_contract("implementation_not_allowed")
    if case.evidence_refs != contract.primary.evidence_refs:
        raise _invalid_contract("evidence_mismatch")

    return _receipt_from_case(case)


def get_workflow_fixture_candidate_case(
    loaded: LoadedWorkflowFixtureProfile,
    *,
    implementation_id: str,
    platform: PlatformId,
    resource_type: ResourceType,
    operation: CapabilityOperation,
    evidence_refs: list[str],
) -> WorkflowFixtureCase:
    case = next(
        (
            item
            for item in loaded.profile.cases
            if item.implementation_id == implementation_id
            and item.platform is platform
            and item.resource_type is resource_type
            and item.operation is operation
        ),
        None,
    )
    if case is None:
        raise WorkflowFixtureAdapterUnavailableError(
            "workflow_fixture_candidate_adapter_unavailable"
        )
    if case.implementation_id not in loaded.allowed_implementation_ids:
        raise _invalid_contract("candidate_implementation_not_allowed")
    if case.evidence_refs != evidence_refs:
        raise _invalid_contract("candidate_evidence_mismatch")
    return case.model_copy(deep=True)


def execute_workflow_fixture_candidate(
    loaded: LoadedWorkflowFixtureProfile,
    *,
    implementation_id: str,
    platform: PlatformId,
    resource_type: ResourceType,
    operation: CapabilityOperation,
    evidence_refs: list[str],
) -> WorkflowFixtureStepReceipt:
    case = get_workflow_fixture_candidate_case(
        loaded,
        implementation_id=implementation_id,
        platform=platform,
        resource_type=resource_type,
        operation=operation,
        evidence_refs=evidence_refs,
    )
    return _receipt_from_case(case)


def _receipt_from_case(case: WorkflowFixtureCase) -> WorkflowFixtureStepReceipt:
    case_payload = cast(JsonValue, case.model_dump(mode="json", exclude_none=True))
    fixture_content_hash = sha256_id(case_payload)
    summary = case.summary.model_copy(deep=True)
    payload_digest = (
        compute_workflow_provider_payload_digest(case.records) if case.records is not None else None
    )
    output: dict[str, JsonValue] = {
        "fixture_case_id": case.case_id,
        "fixture_content_hash": fixture_content_hash,
        "records_count": case.records_count,
        "evidence_refs": list(case.evidence_refs),
        "summary": summary.model_dump(mode="json"),
    }
    if payload_digest is not None:
        output["payload_digest"] = payload_digest
    return WorkflowFixtureStepReceipt(
        fixture_case_id=case.case_id,
        fixture_content_hash=fixture_content_hash,
        records_count=case.records_count,
        evidence_refs=list(case.evidence_refs),
        summary=summary,
        payload_digest=payload_digest,
        output_digest=sha256_id(cast(JsonValue, output)),
    )


def load_workflow_fixture_payload(
    loaded: LoadedWorkflowFixtureProfile,
    *,
    fixture_case_id: str,
    implementation_id: str,
    platform: PlatformId,
    resource_type: ResourceType,
    operation: CapabilityOperation,
    evidence_refs: list[str],
    expected_fixture_content_hash: Sha256Digest,
    expected_records_count: int,
    expected_output_digest: Sha256Digest,
) -> WorkflowProviderPayloadEnvelope:
    case = next(
        (
            item
            for item in loaded.profile.cases
            if item.case_id == fixture_case_id
            and item.implementation_id == implementation_id
            and item.platform is platform
            and item.resource_type is resource_type
            and item.operation is operation
        ),
        None,
    )
    if case is None:
        raise _invalid_contract("payload_case_identity")
    if case.evidence_refs != evidence_refs:
        raise _invalid_contract("payload_evidence_mismatch")
    if case.records is None:
        raise WorkflowFixturePayloadUnboundError("workflow_payload_unbound")
    receipt = _receipt_from_case(case)
    if receipt.fixture_content_hash != expected_fixture_content_hash:
        raise _invalid_contract("payload_fixture_content_hash_mismatch")
    if receipt.records_count != expected_records_count:
        raise _invalid_contract("payload_records_count_mismatch")
    if receipt.output_digest != expected_output_digest or receipt.payload_digest is None:
        raise _invalid_contract("payload_output_digest_mismatch")
    return WorkflowProviderPayloadEnvelope(
        contract_version="workflow_provider_payload.v1",
        fixture_profile_id=loaded.profile.profile_id,
        fixture_case_id=case.case_id,
        implementation_id=case.implementation_id,
        platform=case.platform,
        resource_type=case.resource_type,
        operation=case.operation,
        evidence_refs=list(case.evidence_refs),
        records_count=case.records_count,
        records=[item.model_copy(deep=True) for item in case.records],
        payload_digest=receipt.payload_digest,
    )


__all__ = [
    "LoadedWorkflowFixtureProfile",
    "WORKFLOW_FIXTURE_MANIFEST_PATH",
    "WorkflowFixtureAdapterUnavailableError",
    "WorkflowFixtureCase",
    "WorkflowFixtureContractInvalidError",
    "WorkflowFixtureProfile",
    "WorkflowFixtureProfileUnknownError",
    "WorkflowFixturePayloadUnboundError",
    "WorkflowFixtureStepReceipt",
    "execute_workflow_fixture_candidate",
    "execute_workflow_fixture_step",
    "get_workflow_fixture_candidate_case",
    "load_workflow_fixture_payload",
    "load_workflow_fixture_profile",
]

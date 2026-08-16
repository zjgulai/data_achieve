from __future__ import annotations

from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_sha256,
)


def _sha256_id(payload: JsonValue) -> str:
    return f"sha256:{canonical_json_sha256(payload)}"


def compute_candidate_key(candidate: CapabilityCandidateAssertionPreview) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "schema_version": "capability_governance_candidate_key.v1",
                "proposed_implementation_id": candidate.proposed_implementation_id,
                "platform": candidate.platform.value,
                "access_channel": candidate.access_channel.value,
                "resource_type": candidate.resource_type.value,
                "operation": candidate.operation.value,
            },
        )
    )


def compute_logical_assertion_key(
    *,
    implementation_id: str,
    resource_type: ResourceType,
    operation: CapabilityOperation,
    source_resource_group: str,
) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "schema_version": "capability_governance_logical_assertion_key.v1",
                "implementation_id": implementation_id,
                "resource_type": resource_type.value,
                "operation": operation.value,
                "source_resource_group": source_resource_group,
            },
        )
    )


def hash_governance_idempotency_key(value: str) -> str:
    return _sha256_id(value)


def compute_governance_request_hash(
    *,
    action_scope: str,
    payload: JsonValue,
) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "schema_version": "capability_governance_request_hash.v1",
                "action_scope": action_scope,
                "payload": payload,
            },
        )
    )

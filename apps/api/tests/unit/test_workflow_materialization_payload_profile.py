from __future__ import annotations

import pytest

from data_intelligence_hub.services.workflow_execution.fixtures import (
    WorkflowFixturePayloadUnboundError,
    execute_workflow_fixture_step,
    load_workflow_fixture_payload,
    load_workflow_fixture_profile,
)
from tests.unit.test_workflow_execution_fixtures import _resolved_contracts


def test_payload_profile_is_registered_and_receipts_bind_payload_digest() -> None:
    loaded = load_workflow_fixture_profile("fixture-primary-payload-v1")
    contracts = _resolved_contracts()
    receipts = [execute_workflow_fixture_step(loaded, item) for item in contracts]

    assert loaded.profile.schema_version == "workflow_fixture_profile.v2"
    assert loaded.allowed_implementation_ids == ("fixture.primary",)
    assert all(item.payload_digest is not None for item in receipts)
    for contract, receipt in zip(contracts, receipts, strict=True):
        envelope = load_workflow_fixture_payload(
            loaded,
            fixture_case_id=receipt.fixture_case_id,
            implementation_id=contract.primary.implementation_id,
            platform=contract.requirement.platform,
            resource_type=contract.requirement.resource_type,
            operation=contract.requirement.operation,
            evidence_refs=contract.primary.evidence_refs,
            expected_fixture_content_hash=receipt.fixture_content_hash,
            expected_records_count=receipt.records_count,
            expected_output_digest=receipt.output_digest,
        )
        assert envelope.payload_digest == receipt.payload_digest
        assert envelope.records_count == receipt.records_count


def test_legacy_profile_remains_runnable_but_payload_unbound() -> None:
    loaded = load_workflow_fixture_profile("fixture-primary-v1")
    contract = _resolved_contracts()[0]
    receipt = execute_workflow_fixture_step(loaded, contract)

    assert receipt.payload_digest is None
    with pytest.raises(WorkflowFixturePayloadUnboundError):
        load_workflow_fixture_payload(
            loaded,
            fixture_case_id=receipt.fixture_case_id,
            implementation_id=contract.primary.implementation_id,
            platform=contract.requirement.platform,
            resource_type=contract.requirement.resource_type,
            operation=contract.requirement.operation,
            evidence_refs=contract.primary.evidence_refs,
            expected_fixture_content_hash=receipt.fixture_content_hash,
            expected_records_count=receipt.records_count,
            expected_output_digest=receipt.output_digest,
        )

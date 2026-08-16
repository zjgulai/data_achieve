from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowLineageMaterializationRequest,
    WorkflowLineageMaterializationResponse,
    WorkflowProviderPayloadEnvelope,
    WorkflowProviderPayloadRecord,
)
from data_intelligence_hub.services.workflow_execution.payloads import (
    compute_provider_payload_digest,
)

RUN_ID = UUID("00000000-0000-0000-0000-000000000201")
DATASET_ID = UUID("00000000-0000-0000-0000-000000000202")
VERSION_ID = UUID("00000000-0000-0000-0000-000000000203")
STEP_ID = UUID("00000000-0000-0000-0000-000000000204")
DIGEST = "sha256:" + "a" * 64
NOW = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)


def _record(*, item_id: str = "video-001") -> WorkflowProviderPayloadRecord:
    return WorkflowProviderPayloadRecord(
        record_type="content",
        source_url=f"https://example.invalid/content/{item_id}",
        collected_at=NOW,
        content={"id": item_id, "text": "fixture text"},
    )


def test_provider_payload_digest_is_deterministic_and_order_sensitive() -> None:
    records = [_record(item_id="a"), _record(item_id="b")]
    first = compute_provider_payload_digest(records)
    repeated = compute_provider_payload_digest([item.model_copy(deep=True) for item in records])
    reversed_digest = compute_provider_payload_digest(list(reversed(records)))

    assert first == repeated
    assert first.startswith("sha256:")
    assert reversed_digest != first


def test_provider_payload_envelope_rejects_count_digest_and_duplicate_mismatch() -> None:
    records = [_record(item_id="a"), _record(item_id="b")]
    serialized_records = [item.model_dump(mode="json") for item in records]
    payload = {
        "contract_version": "workflow_provider_payload.v1",
        "fixture_profile_id": "fixture-primary-payload-v1",
        "fixture_case_id": "fixture-primary-content-search-payload-v1",
        "implementation_id": "fixture.primary",
        "platform": "youtube",
        "resource_type": "content",
        "operation": "search_discover",
        "evidence_refs": ["evidence:fixture.primary:content:search_discover"],
        "records_count": 2,
        "records": serialized_records,
        "payload_digest": compute_provider_payload_digest(records),
    }
    envelope = WorkflowProviderPayloadEnvelope.model_validate(payload)
    assert envelope.records_count == len(envelope.records) == 2

    with pytest.raises(ValidationError, match="provider_payload_count_mismatch"):
        WorkflowProviderPayloadEnvelope.model_validate({**payload, "records_count": 1})
    with pytest.raises(ValidationError, match="provider_payload_digest_mismatch"):
        WorkflowProviderPayloadEnvelope.model_validate({**payload, "payload_digest": DIGEST})
    with pytest.raises(ValidationError, match="provider_payload_record_duplicate"):
        WorkflowProviderPayloadEnvelope.model_validate(
            {**payload, "records": [serialized_records[0], serialized_records[0]]}
        )
    same_content_different_metadata = [
        records[0],
        records[0].model_copy(
            update={
                "source_url": "https://example.invalid/another-url",
                "collected_at": NOW + timedelta(minutes=1),
            }
        ),
    ]
    with pytest.raises(ValidationError, match="provider_payload_record_duplicate"):
        WorkflowProviderPayloadEnvelope.model_validate(
            {
                **payload,
                "records": [
                    item.model_dump(mode="json") for item in same_content_different_metadata
                ],
                "payload_digest": compute_provider_payload_digest(same_content_different_metadata),
            }
        )


def test_provider_payload_timestamp_requires_timezone_and_normalizes_to_utc() -> None:
    with pytest.raises(
        ValidationError,
        match="provider_payload_timestamp_timezone_required",
    ):
        WorkflowProviderPayloadRecord(
            record_type="content",
            collected_at=datetime(2026, 7, 17, 9, 0),
            content={"id": "naive"},
        )

    local_time = datetime(
        2026,
        7,
        17,
        17,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    record = WorkflowProviderPayloadRecord(
        record_type="content",
        collected_at=local_time,
        content={"id": "aware"},
    )
    assert record.collected_at == NOW
    assert record.model_dump(mode="json")["collected_at"] == "2026-07-17T09:00:00Z"


def test_materialization_request_is_metadata_only_and_trims_dataset_name() -> None:
    request = WorkflowLineageMaterializationRequest(
        dataset_name="  reddit-market-monitoring  ",
        expected_lineage_digest=DIGEST,
    )
    assert request.dataset_name == "reddit-market-monitoring"
    with pytest.raises(ValidationError):
        WorkflowLineageMaterializationRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "records": [_record().model_dump(mode="json")],
            }
        )


def test_materialization_response_requires_exact_write_replay_pair() -> None:
    payload = {
        "contract_version": "workflow_lineage_materialization.v1",
        "materialization_id": RUN_ID,
        "workflow_run_id": RUN_ID,
        "dataset_id": DATASET_ID,
        "dataset_version_id": VERSION_ID,
        "dataset_version_number": 1,
        "raw_record_ids": [STEP_ID],
        "records_count": 1,
        "lineage_digest": DIGEST,
        "database_write": True,
        "idempotent_replay": False,
        "raw_record_write": True,
        "dataset_write": True,
    }
    assert WorkflowLineageMaterializationResponse.model_validate(payload).database_write
    with pytest.raises(ValidationError, match="materialization_attempt_flags_invalid"):
        WorkflowLineageMaterializationResponse.model_validate({**payload, "database_write": False})

from __future__ import annotations

from collections.abc import Sequence

from data_intelligence_hub.schemas.workflow_execution import Sha256Digest
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowProviderPayloadRecord,
    compute_workflow_provider_payload_digest,
)


def compute_provider_payload_digest(
    records: Sequence[WorkflowProviderPayloadRecord],
) -> Sha256Digest:
    return compute_workflow_provider_payload_digest(list(records))


__all__ = ["compute_provider_payload_digest"]

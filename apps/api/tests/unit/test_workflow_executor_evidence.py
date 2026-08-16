from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from data_intelligence_hub.models.workflow_executor import (
    WorkflowCancellationAcknowledgementRecord,
    WorkflowCancellationRequestRecord,
    WorkflowExecutionDispatchRecord,
    WorkflowExecutionEventRecord,
    WorkflowExecutionLeaseRecord,
    WorkflowProviderCallAuditRecord,
)
from data_intelligence_hub.services.workflow_execution.executor_evidence import (
    compose_workflow_executor_evidence,
)

NOW = datetime(2026, 7, 28, 2, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


def test_executor_evidence_separates_intent_ack_and_live_authority() -> None:
    workspace_id, project_id, plan_id, version_id, run_id, step_id = (
        uuid.uuid4() for _ in range(6)
    )
    dispatch = WorkflowExecutionDispatchRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        source_action_request_id=uuid.uuid4(),
        source_action_receipt_id=uuid.uuid4(),
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
        dispatch_key=DIGEST_C,
        provider_side_effect_key=DIGEST_D,
        state="claimable",
        created_at=NOW,
        database_write=False,
        credential_read_attempted=False,
        provider_call=False,
        network_call=False,
        production_write_allowed=False,
    )
    lease = WorkflowExecutionLeaseRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        dispatch_id=dispatch.id,
        worker_id="fixture-worker",
        fencing_token=2,
        version=3,
        claimed_at=NOW,
        heartbeat_at=NOW + timedelta(seconds=5),
        expires_at=NOW + timedelta(seconds=30),
        state="active",
        created_at=NOW,
        updated_at=NOW,
    )
    event = WorkflowExecutionEventRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        dispatch_id=dispatch.id,
        sequence=1,
        event_type="preflight_eligible",
        lease_id=lease.id,
        fencing_token=2,
        previous_event_digest=None,
        event_digest=DIGEST_A,
        occurred_at=NOW + timedelta(seconds=6),
        created_at=NOW,
    )
    audit = WorkflowProviderCallAuditRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        dispatch_id=dispatch.id,
        lease_id=lease.id,
        fencing_token=2,
        provider_id="youtube.fixture",
        operation_id="search",
        preflight_id=DIGEST_A,
        policy_digest=DIGEST_B,
        side_effect_key=DIGEST_D,
        environment="local",
        attempt_ordinal=1,
        transport_state="not_attempted",
        outcome_code=None,
        started_at=None,
        finished_at=None,
        created_at=NOW,
    )
    request = WorkflowCancellationRequestRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        dispatch_id=dispatch.id,
        requested_by_user_id=uuid.uuid4(),
        request_key=DIGEST_C,
        reason_code="owner_cancelled",
        requested_at=NOW + timedelta(seconds=7),
        created_at=NOW,
    )
    acknowledgement = WorkflowCancellationAcknowledgementRecord(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        request_id=request.id,
        dispatch_id=dispatch.id,
        lease_id=lease.id,
        fencing_token=2,
        safe_point="before.fixture.transport",
        outcome="cancelled_before_effect",
        acknowledged_at=NOW + timedelta(seconds=8),
        created_at=NOW,
    )

    response = compose_workflow_executor_evidence(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        evaluated_at=NOW + timedelta(seconds=10),
        dispatches=(dispatch,),
        leases=(lease,),
        events=(event,),
        audits=(audit,),
        cancellation_requests=(request,),
        cancellation_acknowledgements=(acknowledgement,),
    )

    assert response.evidence_grade == "L2_fixture_local"
    assert response.live_provider_proof is False
    assert response.client_construction is False
    assert response.provider_call is False
    assert response.network_call is False
    assert response.business_cause_code == "executor_waiting_exact_live_authority"
    assert response.next_action_code == "request_exact_live_provider_authorization"
    assert response.dispatch_total == 1
    item = response.dispatches[0]
    assert item.lease is not None and item.lease.fresh is True
    assert item.preflight_state == "eligible"
    assert item.next_required_authority == "exact_live_provider_call_authorization"
    assert item.audit_total == 1
    assert item.audits[0].transport_state == "not_attempted"
    assert item.cancellation.requested is True
    assert item.cancellation.acknowledged is True
    assert item.cancellation.outcome == "cancelled_before_effect"


def test_empty_executor_evidence_is_explicit_not_started_state() -> None:
    workspace_id, project_id, run_id = (uuid.uuid4() for _ in range(3))

    response = compose_workflow_executor_evidence(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        evaluated_at=NOW,
        dispatches=(),
        leases=(),
        events=(),
        audits=(),
        cancellation_requests=(),
        cancellation_acknowledgements=(),
    )

    assert response.dispatch_total == 0
    assert response.business_cause_code == "executor_dispatch_not_created"
    assert response.business_impact_code == "workflow_execution_not_started"
    assert response.next_action_code == "review_action_receipt_and_dispatch_gate"

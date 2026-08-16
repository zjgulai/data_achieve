from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_plan_persistence import (
    MonitoringScopeTemplateCopyRequest,
    WorkflowPlanCloneRequest,
)


def test_workflow_plan_clone_request_requires_trimmed_name_and_source_version() -> None:
    source_version_id = uuid.uuid4()

    request = WorkflowPlanCloneRequest(
        name="  Copied plan  ",
        source_version_id=source_version_id,
    )

    assert request.name == "Copied plan"
    assert request.source_version_id == source_version_id


def test_workflow_plan_clone_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WorkflowPlanCloneRequest.model_validate(
            {
                "name": "Copied plan",
                "source_version_id": uuid.uuid4(),
                "plan_payload": {"trusted": True},
            }
        )


def test_scope_template_copy_request_requires_source_version() -> None:
    with pytest.raises(ValidationError):
        MonitoringScopeTemplateCopyRequest.model_validate({})

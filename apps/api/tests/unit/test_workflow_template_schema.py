from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.schemas.workflow_template_persistence import (
    WorkflowTemplateCreateRequest,
    WorkflowTemplateInstantiateRequest,
    WorkflowTemplateMetadataUpdateRequest,
    WorkflowTemplateRevisionCreateRequest,
)


def _planning_input() -> PlanningInput:
    return PlanningInput.model_validate(
        {
            "flow_mode": "batch_research",
            "scopes": [
                {
                    "scope_ref": "brand",
                    "scope_type": "brand",
                    "canonical_term": "Acme",
                    "platforms": ["reddit"],
                }
            ],
            "purpose": "brand_monitoring",
            "default_platforms": ["reddit"],
        }
    )


def test_template_create_request_trims_metadata_and_forbids_client_fingerprint() -> None:
    payload = WorkflowTemplateCreateRequest(
        name="  Acme template  ",
        template_key="  acme-monitoring  ",
        description="  reusable plan  ",
        definition=_planning_input(),
    )

    assert payload.name == "Acme template"
    assert payload.template_key == "acme-monitoring"
    assert payload.description == "reusable plan"
    assert "definition_fingerprint" not in payload.model_dump()

    with pytest.raises(ValidationError):
        WorkflowTemplateCreateRequest.model_validate(
            {
                "name": "Acme",
                "template_key": "acme",
                "definition": _planning_input(),
                "definition_fingerprint": "sha256:" + "0" * 64,
            }
        )


def test_revision_request_requires_expected_current_revision() -> None:
    revision_id = uuid.uuid4()
    payload = WorkflowTemplateRevisionCreateRequest(
        expected_revision_id=revision_id,
        definition=_planning_input(),
    )
    assert payload.expected_revision_id == revision_id


def test_metadata_update_distinguishes_omitted_description_from_explicit_null() -> None:
    revision_id = uuid.uuid4()
    payload = WorkflowTemplateMetadataUpdateRequest(
        expected_revision_id=revision_id,
        description=None,
    )

    assert payload.description is None
    assert "description" in payload.model_fields_set

    with pytest.raises(ValidationError):
        WorkflowTemplateMetadataUpdateRequest(expected_revision_id=revision_id)


def test_instantiate_request_trims_name_and_requires_revision() -> None:
    revision_id = uuid.uuid4()
    payload = WorkflowTemplateInstantiateRequest(
        revision_id=revision_id,
        name="  Plan from template  ",
    )
    assert payload.name == "Plan from template"

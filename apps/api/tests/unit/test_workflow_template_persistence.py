from __future__ import annotations

import inspect
import uuid
from collections.abc import Callable

import pytest

from data_intelligence_hub.services.workflow_planner.template_persistence import (
    append_workflow_template_revision,
    create_workflow_template,
    instantiate_workflow_plan_from_template,
    list_workflow_templates_for_project,
    update_workflow_template_metadata,
)


def test_template_service_contract_exports_crud_revision_and_instantiate_seams() -> None:
    assert callable(create_workflow_template)
    assert callable(append_workflow_template_revision)
    assert callable(instantiate_workflow_plan_from_template)
    assert callable(list_workflow_templates_for_project)
    assert uuid.UUID(int=0).int == 0


@pytest.mark.parametrize(
    "operation",
    [
        create_workflow_template,
        append_workflow_template_revision,
        update_workflow_template_metadata,
    ],
)
def test_template_mutations_recheck_idempotency_after_project_lock(
    operation: Callable[..., object],
) -> None:
    source = inspect.getsource(operation)
    lock_index = source.index("lock_project_for_workflow_template_mutation(")

    assert source.find("get_workflow_template_mutation_request(", lock_index) > lock_index

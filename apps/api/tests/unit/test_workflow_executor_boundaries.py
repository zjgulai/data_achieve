from __future__ import annotations

from inspect import getsource, signature

from data_intelligence_hub.schemas import workflow_executor as schema_module
from data_intelligence_hub.services.workflow_execution import executor_contract


def test_executor_pure_modules_exclude_side_effect_dependencies() -> None:
    source = "\n".join((getsource(schema_module), getsource(executor_contract))).lower()
    forbidden_source_tokens = (
        "sqlalchemy",
        "asyncsession",
        "os.environ",
        "pydantic_settings",
        "environmentcredentialsource",
        "vault",
        "credentialhandle",
        "googleapiclient",
        "asyncpraw",
        "requests",
        "httpx",
        "socket",
        "transport.invoke",
        "client.create",
    )

    assert all(token not in source for token in forbidden_source_tokens)


def test_executor_compilers_have_explicit_inputs_and_no_runtime_dependencies() -> None:
    expected_parameters = {
        "claim_workflow_execution_dispatch": (
            "dispatch",
            "lease_id",
            "worker_id",
            "claimed_at",
            "lease_duration_seconds",
        ),
        "heartbeat_workflow_execution_lease": (
            "lease",
            "presented_fencing_token",
            "presented_version",
            "heartbeat_at",
            "lease_duration_seconds",
        ),
        "consume_workflow_credential_resolution_permit": (
            "permit",
            "dispatch",
            "provider_id",
            "operation_id",
            "purpose",
            "environment",
            "consumed_at",
        ),
        "consume_workflow_provider_call_permit": (
            "permit",
            "dispatch",
            "preflight_id",
            "policy_digest",
            "provider_id",
            "operation_id",
            "environment",
            "reserved_cost_usd",
            "reserved_quota_units",
            "consumed_at",
        ),
    }

    for function_name, parameters in expected_parameters.items():
        function = getattr(executor_contract, function_name)
        assert tuple(signature(function).parameters) == parameters


def test_executor_contracts_keep_all_live_boundaries_false() -> None:
    assert schema_module.WorkflowExecutionDispatch.model_fields["provider_call"].default is False
    assert (
        schema_module.WorkflowExecutionDispatch.model_fields["credential_read_attempted"].default
        is False
    )
    assert schema_module.WorkflowExecutionDispatch.model_fields["database_write"].default is False
    assert schema_module.WorkflowExecutionDispatch.model_fields["network_call"].default is False
    assert (
        schema_module.WorkflowExecutionDispatch.model_fields["production_write_allowed"].default
        is False
    )

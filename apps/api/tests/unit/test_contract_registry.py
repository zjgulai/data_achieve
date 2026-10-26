from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = PROJECT_ROOT / "scripts/contract_registry.py"

BEGIN = "<!-- contract-registry:begin -->"
END = "<!-- contract-registry:end -->"


def load_module():
    spec = importlib.util.spec_from_file_location("contract_registry", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_registry() -> dict:
    return {
        "registry_version": "contract-registry.v1",
        "contract_version": "v1.1",
        "status": "frozen",
        "source_document": "contract.md",
        "source_section": "附录 A",
        "generated_at": "2026-10-22",
        "canonical_profile": {
            "profile_id": "dih-canonical-json-v1",
            "encoding": "UTF-8",
            "json_rules": "RFC 8785",
            "digest_algorithm": "sha256",
            "digest_encoding": "lowercase-hex",
            "excluded_top_level_keys": ["generated_at", "artifact"],
            "timestamp_format": "RFC3339-UTC-Z",
            "number_rules": "finite-only",
            "unicode_rules": "preserve scalar values",
            "forbidden_language": {
                "profile_id": "dih-descriptive-language-v1",
                "profile_version": "1.0.0",
                "source": (
                    "docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md#5.7"
                ),
                "causal_terms_zh": ["导致", "驱动", "提升", "降低", "造成", "证明"],
                "causal_terms_en": [
                    "cause",
                    "causes",
                    "caused",
                    "drive",
                    "drives",
                    "driven",
                    "improve",
                    "improves",
                    "increase",
                    "increases",
                    "decrease",
                    "decreases",
                    "reduce",
                    "reduces",
                    "lead to",
                    "leads to",
                    "prove",
                    "proves",
                ],
                "prediction_terms_zh": ["预测", "预计", "将会"],
                "prediction_terms_en": [
                    "predict",
                    "predicts",
                    "forecast",
                    "forecasts",
                    "projection",
                    "projections",
                ],
                "prediction_objects_zh": ["销量", "市场份额", "转化率", "营收"],
                "prediction_objects_en": ["sales", "market share", "conversion rate", "revenue"],
                "allowed_relations_zh": ["共同出现", "相关", "描述性差异"],
                "allowed_relations_en": [
                    "co-occurrence",
                    "correlation",
                    "descriptive difference",
                ],
            },
        },
        "audit_actions": {
            "version": "audit-actions.v1",
            "actions": [
                {
                    "name": "project.created",
                    "owner": "C2",
                    "status": "new",
                    "phase": "C2",
                }
            ],
        },
        "phases": [
            {
                "id": f"C{index}",
                "name": f"Phase {index}",
                "scope": "scope",
                "objects": [],
            }
            for index in range(2, 15)
        ],
        "tables": [
            {
                "name": "runs",
                "module": "M10",
                "status": "existing",
                "phase": "C2",
                "purpose": "run",
                "primary_key": ["id"],
                "columns": [
                    {
                        "name": "id",
                        "type": "uuid",
                        "nullable": False,
                        "status": "existing",
                        "phase": "C2",
                    }
                ],
            }
        ],
        "enums": [
            {
                "name": "runs.status",
                "values": ["queued"],
                "status": "frozen",
                "phase": "C2",
                "source": "contract",
            }
        ],
        "paths": [
            {
                "id": "runs.list",
                "method": "GET",
                "path": "/api/runs",
                "audience": "session",
                "status": "existing",
                "phase": "C2",
                "auth": "session",
                "idempotent": False,
                "error_codes": [],
            }
        ],
        "page_routes": [
            {
                "id": "home",
                "path": "/",
                "area": "public",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
            {
                "id": "capabilities",
                "path": "/capabilities",
                "area": "public",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
            {
                "id": "capabilities.detail",
                "path": "/capabilities/[toolId]",
                "area": "public",
                "enabled": True,
                "kind": "dynamic",
                "dynamic_segment": "toolId",
                "phase": "C14",
            },
            {
                "id": "reports.public.detail",
                "path": "/reports/public/[id]",
                "area": "public",
                "enabled": False,
                "kind": "dynamic",
                "dynamic_segment": "id",
                "phase": "C14",
            },
            {
                "id": "docs",
                "path": "/docs",
                "area": "public",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
            {
                "id": "workbench",
                "path": "/workbench",
                "area": "authorized",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
            {
                "id": "workbench.detail",
                "path": "/workbench/[taskId]",
                "area": "authorized",
                "enabled": True,
                "kind": "dynamic",
                "dynamic_segment": "taskId",
                "phase": "C14",
            },
            {
                "id": "reports",
                "path": "/reports",
                "area": "authorized",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
            {
                "id": "reports.detail",
                "path": "/reports/[artifactId]",
                "area": "authorized",
                "enabled": True,
                "kind": "dynamic",
                "dynamic_segment": "artifactId",
                "phase": "C14",
            },
            {
                "id": "connectors",
                "path": "/connectors",
                "area": "authorized",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
            {
                "id": "settings",
                "path": "/settings",
                "area": "authorized",
                "enabled": True,
                "kind": "static",
                "phase": "C14",
            },
        ],
        "primary_nav": [
            {
                "id": "workbench",
                "label": "工作台",
                "path": "/workbench",
                "order": 1,
                "phase": "C14",
            },
            {"id": "reports", "label": "报告", "path": "/reports", "order": 2, "phase": "C14"},
            {
                "id": "connectors",
                "label": "连接器",
                "path": "/connectors",
                "order": 3,
                "phase": "C14",
            },
            {"id": "settings", "label": "设置", "path": "/settings", "order": 4, "phase": "C14"},
        ],
        "mcp": {
            "endpoint": "/mcp/customer",
            "transport": "streamable-http",
            "tools_version": "customer-mcp.v1",
            "schema_file": "customer_mcp.schema.json",
            "tools": [
                {
                    "name": f"tool_{index}",
                    "status": "new",
                    "phase": "C10",
                    "audience": "customer",
                    "read_only": True,
                    "input_ref": f"customer_mcp.schema.json#/$defs/Tool{index}Input",
                    "output_ref": f"customer_mcp.schema.json#/$defs/Tool{index}Output",
                    "error_codes": [],
                }
                for index in range(8)
            ],
            "forbidden_tools": ["collect_endpoint"],
        },
        "error_codes": [
            {
                "code": "tool_not_allowed",
                "kind": "error",
                "http_status": 403,
                "retryable": False,
                "phase": "C10",
                "meaning": "tool not allowed",
            }
        ],
        "schemas": [
            {
                "id": "registry",
                "path": "configs/contracts/v1.1.0/registry.schema.json",
                "kind": "registry",
                "profile": "dih-canonical-json-v1",
                "digest_algorithm": "sha256",
            },
            {
                "id": "registry_copy",
                "path": "configs/contracts/v1.1.0/registry.schema.json",
                "kind": "registry",
                "profile": "dih-canonical-json-v1",
                "digest_algorithm": "sha256",
            },
        ],
        "documents": [
            {
                "path": "docs/design/contract.md",
                "role": "authority",
                "version": "v1.1",
                "must_contain": ["runs"],
            },
            {
                "path": "docs/product/prd.md",
                "role": "derived",
                "version": "v1.1",
                "must_contain": ["runs"],
            },
            {
                "path": "docs/product/playbook.md",
                "role": "derived",
                "version": "v1.1",
                "must_contain": ["runs"],
            },
        ],
        "deferred": [],
    }


def test_extract_registry_block_returns_object() -> None:
    module = load_module()
    payload = minimal_registry()
    markdown = (
        f"# Contract\n\n{BEGIN}\n```json\n{json.dumps(payload, ensure_ascii=False)}\n```\n{END}\n"
    )
    assert module.extract_registry_block(markdown) == payload


def test_extract_registry_block_rejects_missing_markers() -> None:
    module = load_module()
    try:
        module.extract_registry_block("# Contract\n")
    except module.RegistryError as exc:
        assert str(exc) == "registry_block_missing"
    else:
        raise AssertionError("expected RegistryError")


def test_extract_registry_block_rejects_duplicate_markers() -> None:
    module = load_module()
    markdown = f"{BEGIN}\n```json\n{{}}\n```\n{END}\n{BEGIN}\n```json\n{{}}\n```\n{END}\n"
    try:
        module.extract_registry_block(markdown)
    except module.RegistryError as exc:
        assert str(exc) == "registry_block_duplicate"
    else:
        raise AssertionError("expected RegistryError")


def test_validate_registry_accepts_minimal_object() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(encoding="utf-8")
    )
    assert module.validate_registry(minimal_registry(), schema) == []


def test_validate_registry_rejects_wrong_mcp_tool_count() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(encoding="utf-8")
    )
    payload = minimal_registry()
    payload["mcp"]["tools"] = payload["mcp"]["tools"][:7]
    errors = module.validate_registry(payload, schema)
    assert any("mcp" in error and "tools" in error for error in errors)


def test_validate_registry_rejects_audit_action_name_over_max_length() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(encoding="utf-8")
    )
    payload = minimal_registry()
    payload["audit_actions"]["actions"][0]["name"] = "a" * 81
    errors = module.validate_registry(payload, schema)
    assert any("maxLength" in error for error in errors), errors


def test_validate_registry_rejects_primary_nav_order_out_of_range() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(encoding="utf-8")
    )
    payload = minimal_registry()
    payload["primary_nav"][0]["order"] = 9
    errors = module.validate_registry(payload, schema)
    assert any("maximum" in error for error in errors), errors


def test_validate_registry_rejects_error_code_http_status_out_of_range() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(encoding="utf-8")
    )
    payload = minimal_registry()
    payload["error_codes"][0]["http_status"] = 99999
    errors = module.validate_registry(payload, schema)
    assert any("maximum" in error for error in errors), errors


CONTRACT_PATH = PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
SCHEMA_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json"
REGISTRY_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"


def load_contract_registry() -> dict:
    module = load_module()
    return module.extract_registry_block(CONTRACT_PATH.read_text(encoding="utf-8"))


def _table(registry: dict, name: str) -> dict:
    return next(item for item in registry["tables"] if item["name"] == name)


def test_registry_contains_execution_and_budget_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {
        "workbench_tasks",
        "workflow_versions",
        "runs",
        "run_steps",
        "authorizations",
        "task_runs",
        "run_step_attempts",
        "tool_prices",
        "quota_accounts",
        "tool_calls",
    } <= names


def test_tool_prices_matches_c5_pricing_contract() -> None:
    registry = load_contract_registry()
    table = _table(registry, "tool_prices")
    assert {column["name"] for column in table["columns"]} == {
        "id",
        "tool_id",
        "currency",
        "price_book_version",
        "unit_price",
        "unit",
        "quantity_basis",
        "confidence",
        "source",
        "effective_from",
        "effective_to",
        "created_at",
        "updated_at",
    }
    assert {
        "uq_tool_prices_tool_currency_version",
        "ck_tool_prices_unit_price_nonnegative",
        "ck_tool_prices_confidence",
        "ck_tool_prices_effective_window",
        "fk_tool_prices_tool_id_tool_catalog",
    } <= set(table["constraints"])
    indexes = {index["name"]: index for index in table["indexes"]}
    assert indexes["uq_tool_prices_tool_currency_version"]["columns"] == [
        "tool_id",
        "currency",
        "price_book_version",
    ]
    assert indexes["uq_tool_prices_tool_currency_version"]["unique"] is True
    assert indexes["ix_tool_prices_tool_effective"]["columns"] == [
        "tool_id",
        "effective_from",
    ]


def test_deferred_customer_lease_is_not_registered_as_table() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    deferred = {(item["kind"], item["name"]) for item in registry["deferred"]}
    assert ("table", "mcp_customer_request_leases") in deferred
    assert ("table", "report_shares") in deferred
    assert "mcp_customer_request_leases" not in names
    assert "report_shares" not in names
    assert ("table", "tool_prices") not in deferred


def test_workbench_tasks_matches_c4_seven_slots() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "workbench_tasks")["columns"]}
    assert {
        "workspace_id",
        "project_id",
        "created_by_user_id",
        "owner_id",
        "brand",
        "category",
        "competitors",
        "markets",
        "locale_by_market",
        "window_start",
        "window_end",
        "decision_question",
        "does_not_answer",
        "task_type",
        "task_type_confidence",
        "status",
    } <= columns


def test_workbench_tasks_persist_package_type_and_market_roles() -> None:
    registry = load_contract_registry()
    table = _table(registry, "workbench_tasks")
    columns = {column["name"]: column for column in table["columns"]}
    assert {
        "package_type",
        "primary_market",
        "comparison_markets",
        "acceptance_contact_id",
        "max_cost_usd",
        "max_pages",
        "max_records",
        "seed_products",
        "target_price_band",
        "idempotency_key_hash",
    } <= set(columns)
    assert columns["package_type"]["enum"] == "workbench_tasks.package_type"
    assert columns["primary_market"]["enum"] == "market_code"
    assert columns["comparison_markets"]["type"] == "json"
    assert columns["seed_products"]["type"] == "json"
    assert columns["seed_products"]["nullable"] is False
    assert columns["target_price_band"]["type"] == "json"
    assert columns["target_price_band"]["nullable"] is True
    assert columns["idempotency_key_hash"]["type"] == "string(64)"
    assert columns["idempotency_key_hash"]["nullable"] is True
    assert "owner" in columns["acceptance_contact_id"]["notes"]
    assert "admin" in columns["acceptance_contact_id"]["notes"]
    assert {
        "ck_workbench_tasks_package_type",
        "ck_workbench_tasks_primary_market",
        "ck_workbench_tasks_budget_nonnegative",
        "fk_workbench_tasks_acceptance_contact_member",
    } <= set(table["constraints"])
    indexes = {index["name"]: index for index in table["indexes"]}
    assert indexes["uq_workbench_tasks_workspace_idempotency"] == {
        "name": "uq_workbench_tasks_workspace_idempotency",
        "columns": ["workspace_id", "idempotency_key_hash"],
        "unique": True,
        "where": "idempotency_key_hash IS NOT NULL",
    }
    versions = {
        column["name"]: column for column in _table(registry, "workflow_versions")["columns"]
    }
    assert "plan_payload" in versions
    assert "execution_steps" in versions["plan_payload"]["notes"]
    assert "不可变" in versions["plan_payload"]["notes"]
    assert versions["workbench_task_id"]["nullable"] is True
    version_table = _table(registry, "workflow_versions")
    assert "fk_workflow_versions_workbench_task_tenant" in version_table["constraints"]


def test_runs_uses_market_code_and_authorization_binds_run_id() -> None:
    registry = load_contract_registry()
    run_columns = {column["name"] for column in _table(registry, "runs")["columns"]}
    authorization = _table(registry, "authorizations")
    authorization_columns = {column["name"] for column in authorization["columns"]}
    assert "market_code" in run_columns
    assert "market_role" not in run_columns
    assert "package_type" not in run_columns
    assert "run_id" in authorization_columns
    assert "gate_id" in authorization_columns
    assert "uq_authorizations_run_gate" in authorization["constraints"]
    assert {
        "name": "uq_authorizations_run_gate",
        "columns": ["run_id", "gate_id"],
        "unique": True,
        "where": "run_id IS NOT NULL",
    } in authorization["indexes"]


def test_run_step_attempts_matches_c6_columns() -> None:
    registry = load_contract_registry()
    attempt = _table(registry, "run_step_attempts")
    assert {column["name"] for column in attempt["columns"]} == {
        "id",
        "run_id",
        "step_index",
        "attempt_number",
        "status",
        "task_run_id",
        "error_reason_code",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
    }
    assert {
        "uq_run_step_attempts_run_step_attempt",
        "uq_run_step_attempts_task_run_id",
        "ck_run_step_attempts_attempt_number_positive",
        "ck_run_step_attempts_status",
        "fk_run_step_attempts_run_id_runs",
        "fk_run_step_attempts_task_run_id_task_runs",
    } <= set(attempt["constraints"])
    assert {
        "name": "ix_run_step_attempts_run_step",
        "columns": ["run_id", "step_index"],
        "unique": False,
    } in attempt["indexes"]


def test_run_steps_has_c6_extension_columns() -> None:
    registry = load_contract_registry()
    table = _table(registry, "run_steps")
    columns = {column["name"]: column for column in table["columns"]}
    assert {
        "attempt_no",
        "depends_on",
        "tool_id",
        "provider_run_id",
        "idempotency_key_hash",
        "evidence_grade",
        "stage",
    } <= set(columns)
    assert columns["attempt_no"]["nullable"] is False
    assert columns["attempt_no"]["default"] == 1
    assert {
        "name": "uq_run_steps_task_run_id",
        "columns": ["task_run_id"],
        "unique": True,
        "where": "task_run_id IS NOT NULL",
    } in table["indexes"]


def test_registry_contains_identity_audit_key_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {
        "workspace_members",
        "project_members",
        "audit_events",
        "project_api_keys",
        "platform_credential_bundles",
    } <= names


def test_audit_events_has_sequence_and_hash_chain() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "audit_events")["columns"]}
    assert {"sequence_number", "prev_hash", "event_hash", "actor_type", "result"} <= columns


def test_project_api_keys_matches_c3_rotation_columns() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "project_api_keys")["columns"]}
    assert {
        "tool_allowlist",
        "capability_allowlist",
        "daily_budget_usd",
        "status",
        "rotation_group_id",
        "superseded_by_key_id",
        "last_rotated_at",
        "expires_at",
    } <= columns


def test_c3_constraints_are_registered() -> None:
    registry = load_contract_registry()
    project_key_constraints = set(_table(registry, "project_api_keys").get("constraints", []))
    credential_constraints = set(
        _table(registry, "platform_credential_bundles").get("constraints", [])
    )
    assert "fk_project_api_keys_workspace_project_projects" in project_key_constraints
    assert "uq_project_api_keys_active_project" in project_key_constraints
    assert {
        "uq_platform_credential_bundles_workspace_provider",
        "uq_platform_credential_bundles_project_provider",
        "fk_platform_credential_bundles_workspace_project_projects",
    } <= credential_constraints


def test_platform_credentials_has_project_scope() -> None:
    registry = load_contract_registry()
    columns = {
        column["name"] for column in _table(registry, "platform_credential_bundles")["columns"]
    }
    assert {"project_id", "creator_cookie_metadata"} <= columns

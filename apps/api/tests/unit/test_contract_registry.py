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
                    "docs/superpowers/specs/"
                    "2026-10-21-tikhub-governed-task-platform-design.md#5.7"
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

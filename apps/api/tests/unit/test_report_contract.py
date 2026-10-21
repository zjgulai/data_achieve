"""B4-02：报告合同 schema 的单元测试。

覆盖结构校验、序列化、规范化哈希、语义校验与 JSON Schema 互校。
所有用例只使用合同对象。测试不读库、不联网、不调模型。

JSON Schema 互校不依赖 ``jsonschema``。
本项目没有声明该依赖。测试自带最小结构校验器。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from data_intelligence_hub.models.claim import ClaimState, EvidenceRole
from data_intelligence_hub.schemas.report_contract import (
    Claim,
    CoverageStatus,
    Evidence,
    ReportContract,
    canonical_json_bytes,
    contract_sha256,
    to_json,
    validate_contract,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade

API_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = API_ROOT / "schemas" / "report_contract.schema.json"

TASK_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
RUN_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
AUTH_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
RAW_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")

WINDOW = {"start": "2026-01-01", "end": "2026-03-01", "days": 60}

EXPECTED_REQUIRED_FIELDS = [
    "schema_version",
    "template_id",
    "generated_at",
    "identity",
    "decision",
    "gates",
    "coverage",
    "metrics",
    "claims",
    "evidences",
    "run_ledger",
    "limits",
    "unknowns",
    "artifact",
]

PYDANTIC_TO_SCHEMA_DEFS = {
    "Window": "window",
    "FamilyChild": "family_child",
    "Identity": "identity",
    "Decision": "decision",
    "Gate": "gate",
    "CoverageCell": "coverage_cell",
    "CoverageBlock": "coverage",
    "Metric": "metric",
    "ClaimScope": "claim_scope",
    "Claim": "claim",
    "Evidence": "evidence",
    "RunLedgerRow": "run_ledger_row",
    "Artifact": "artifact",
}


def _payload() -> dict[str, Any]:
    """构造一份完整合同。所有顶层字段都出现。"""
    return {
        "schema_version": "1.0.0",
        "template_id": "t1_voc",
        "generated_at": "2026-10-21T08:00:00Z",
        "identity": {
            "task_id": str(TASK_ID),
            "brand": "Acme",
            "category": "baby_bottle",
            "competitors": ["Beta"],
            "markets": ["US"],
            "window": dict(WINDOW),
            "product": "防胀气奶瓶",
            "model": "AC-100",
            "variant_id": "v-1",
            "sku": "SKU-1",
            "asin": "B000000001",
            "parent_asin": "B000000000",
            "bundle": "单支装",
            "offer": "1 件",
            "mapping_confidence": 0.92,
            "family_children": [
                {
                    "variant_id": "v-2",
                    "sku": "SKU-2",
                    "asin": "B000000002",
                    "color": "blue",
                    "size": "260ml",
                }
            ],
        },
        "decision": {
            "decision_question": "T1 新品是否值得加投？",
            "answer": "值得小步加投。",
            "protect": ["品牌安全"],
            "resolve": [],
            "prove": ["复购假设"],
        },
        "gates": [
            {
                "gate_id": "G-Evidence",
                "status": "pass",
                "owner": str(OWNER_ID),
                "decided_at": "2026-10-21T07:00:00Z",
                "note": "通过",
            },
            {"gate_id": "G3", "status": "pending"},
        ],
        "coverage": {
            "cells": [
                {
                    "source_tool_id": "youtube_comments",
                    "market": "US",
                    "window": dict(WINDOW),
                    "record_count": 120,
                    "frame_member_count": 80,
                    "status": "success",
                }
            ]
        },
        "metrics": [
            {
                "metric_id": "mention_rate",
                "label": "提及率",
                "numerator": 12,
                "denominator": 120,
                "count_type": "frame_member",
                "frame": "T1 帧成员",
                "as_of": "2026-03-01",
                "note": "样本来自 2 个来源",
            }
        ],
        "claims": [
            {
                "claim_id": "c-1",
                "text": "防胀气卖点出现频率高。",
                "claim_status": "directional",
                "evidence_grade": "L4_authorized_live",
                "scope": {
                    "market": "US",
                    "window": dict(WINDOW),
                    "sample_n": 80,
                },
                "counterevidence_text": "未发现反证",
                "owner": str(OWNER_ID),
                "evidence_ids": ["e-1", "e-2"],
            }
        ],
        "evidences": [
            {
                "evidence_id": "e-1",
                "claim_id": "c-1",
                "role": "support",
                "raw_record_id": str(RAW_ID),
                "source_tool_id": "youtube_comments",
                "url": "https://example.com/v/1",
                "excerpt": "不胀气",
                "captured_at": "2026-02-01T00:00:00Z",
                "market": "US",
                "locale": "en-US",
                "evidence_grade": "L4_authorized_live",
            },
            {
                "evidence_id": "e-2",
                "claim_id": "c-1",
                "role": "counter",
                "source_tool_id": "youtube_comments",
                "captured_at": "2026-02-02T00:00:00Z",
                "market": "US",
                "locale": "en-US",
                "evidence_grade": "L4_authorized_live",
            },
        ],
        "run_ledger": [
            {
                "run_id": str(RUN_ID),
                "tool_id": "youtube_comments",
                "endpoint_type": "youtube_comments",
                "actor_id": None,
                "unit": "request",
                "quantity": 1,
                "unit_price": "0.010000",
                "total_cost_usd": "0.010000",
                "authorization_id": str(AUTH_ID),
                "evidence_grade": "L4_authorized_live",
                "started_at": "2026-02-01T00:00:00Z",
                "finished_at": "2026-02-01T00:00:05Z",
                "outcome": "success",
            }
        ],
        "limits": ["不能推断长期复购。"],
        "unknowns": ["缺少线下渠道数据。"],
        "artifact": {
            "report_html_sha256": "a" * 64,
            "sop_html_sha256": "b" * 64,
            "contract_sha256": "c" * 64,
        },
    }


def _contract() -> ReportContract:
    return ReportContract.model_validate(_payload())


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema: dict[str, Any] = json.load(handle)
    return schema


def _resolve_ref(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = schema["$ref"]
    assert ref.startswith("#/"), ref
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    assert isinstance(node, dict), ref
    return node


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise AssertionError(f"未支持的 JSON Schema 类型：{expected}")


def _schema_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
) -> list[str]:
    """最小 JSON Schema 校验器。只覆盖手写 schema 用到的关键字。"""
    if "$ref" in schema:
        return _schema_errors(value, _resolve_ref(schema, root), root)
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            if not _schema_errors(value, branch, root):
                return []
        return [f"值不匹配 anyOf：{value!r}"]
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _matches_type(value, expected):
        return [f"类型必须是 {expected}，实际是 {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"值必须是 {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"值 {value!r} 不在枚举内")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"缺少必填字段 {key}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    f"{key}.{error}"
                    for error in _schema_errors(item, properties[key], root)
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"不允许的字段 {key}")
    if isinstance(value, list):
        items = schema.get("items")
        if items is not None:
            for index, item in enumerate(value):
                errors.extend(
                    f"[{index}].{error}"
                    for error in _schema_errors(item, items, root)
                )
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("数组元素太少")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("数组元素太多")
    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append("字符串太短")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("数值小于 minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("数值大于 maximum")
    return errors


def test_claim_and_evidence_reuse_b4_01_enums() -> None:
    assert Claim.model_fields["claim_status"].annotation is ClaimState
    assert Evidence.model_fields["role"].annotation is EvidenceRole


def test_gate_status_accepts_expired() -> None:
    payload = _payload()
    payload["gates"][0]["status"] = "expired"

    contract = ReportContract.model_validate(payload)

    assert contract.gates[0].status == "expired"


def test_run_ledger_accepts_config_gated_outcome() -> None:
    payload = _payload()
    payload["run_ledger"][0]["outcome"] = "config_gated"

    contract = ReportContract.model_validate(payload)

    assert contract.run_ledger[0].outcome == "config_gated"


def test_contract_round_trips_through_json() -> None:
    contract = _contract()
    text = to_json(contract)

    restored = ReportContract.model_validate_json(text)

    assert restored == contract
    assert to_json(restored) == text
    # ensure_ascii=False 让中文直接出现在输出里。
    assert "防胀气奶瓶" in text


def test_extra_field_is_rejected() -> None:
    payload = _payload()
    payload["identity"]["unexpected_field"] = "x"

    with pytest.raises(ValidationError):
        ReportContract.model_validate(payload)


def test_missing_protect_key_is_rejected_but_empty_array_is_allowed() -> None:
    payload = _payload()
    del payload["decision"]["protect"]

    with pytest.raises(ValidationError):
        ReportContract.model_validate(payload)

    payload = _payload()
    payload["decision"]["protect"] = []
    contract = ReportContract.model_validate(payload)
    assert contract.decision.protect == []


def test_schema_version_rejects_empty_string() -> None:
    payload = _payload()
    payload["schema_version"] = ""

    with pytest.raises(ValidationError):
        ReportContract.model_validate(payload)


def test_template_id_must_come_from_b2_thresholds() -> None:
    payload = _payload()
    payload["template_id"] = "t9_unknown"

    with pytest.raises(ValidationError):
        ReportContract.model_validate(payload)


def test_coverage_block_accepts_cells_object() -> None:
    contract = _contract()

    assert contract.coverage.cells[0].source_tool_id == "youtube_comments"


def test_coverage_block_rejects_bare_cell_array() -> None:
    payload = _payload()
    payload["coverage"] = payload["coverage"]["cells"]

    with pytest.raises(ValidationError) as excinfo:
        ReportContract.model_validate(payload)

    message = str(excinfo.value)
    assert "coverage" in message
    assert "cells" in message


def test_contract_sha256_is_stable_and_ignores_generated_at() -> None:
    first = contract_sha256(_contract())
    second = contract_sha256(_contract())

    assert first == second
    assert len(first) == 64

    payload = _payload()
    payload["generated_at"] = "2027-01-01T00:00:00Z"
    assert contract_sha256(ReportContract.model_validate(payload)) == first


def test_contract_sha256_ignores_artifact_and_tracks_content() -> None:
    baseline = contract_sha256(_contract())

    payload = _payload()
    payload["artifact"]["report_html_sha256"] = "d" * 64
    assert contract_sha256(ReportContract.model_validate(payload)) == baseline

    payload = _payload()
    payload["decision"]["answer"] = "另一个结论。"
    assert contract_sha256(ReportContract.model_validate(payload)) != baseline


def test_contract_sha256_matches_between_model_and_mapping() -> None:
    assert contract_sha256(_contract()) == contract_sha256(_payload())


def test_contract_sha256_matches_for_native_mapping_values() -> None:
    payload = _payload()
    payload["evidences"][0]["captured_at"] = datetime(2026, 2, 1, tzinfo=UTC)
    payload["run_ledger"][0]["run_id"] = RUN_ID
    payload["run_ledger"][0]["unit_price"] = Decimal("0.010000")
    payload["claims"][0]["claim_status"] = ClaimState.DIRECTIONAL

    assert contract_sha256(payload) == contract_sha256(_contract())


def test_contract_sha256_matches_when_mapping_omits_defaults() -> None:
    payload = _payload()
    del payload["identity"]["competitors"]
    del payload["identity"]["family_children"]

    assert contract_sha256(payload) == contract_sha256(
        ReportContract.model_validate(payload)
    )


def test_contract_sha256_matches_when_mapping_needs_coercion() -> None:
    payload = _payload()
    payload["identity"]["mapping_confidence"] = 1
    payload["metrics"][0]["numerator"] = "12"
    payload["run_ledger"][0]["unit_price"] = 0.01

    assert contract_sha256(payload) == contract_sha256(
        ReportContract.model_validate(payload)
    )


@pytest.mark.parametrize(
    "captured_at",
    [
        "2026-02-01T00:00:00Z",
        "2026-02-01T00:00:00+00:00",
        "2026-02-01T00:00:00.000+00:00",
        "2026-02-01T08:00:00+08:00",
    ],
)
def test_contract_sha256_normalizes_timezone_text(captured_at: str) -> None:
    baseline = contract_sha256(_payload())

    payload = _payload()
    payload["evidences"][0]["captured_at"] = captured_at

    assert contract_sha256(payload) == baseline
    assert contract_sha256(ReportContract.model_validate(payload)) == baseline


def test_contract_sha256_drops_subsecond_precision() -> None:
    payload = _payload()
    payload["evidences"][0]["captured_at"] = "2026-02-01T00:00:00.123456+00:00"

    assert contract_sha256(payload) == contract_sha256(_payload())


def test_contract_sha256_normalizes_date_fields() -> None:
    baseline = contract_sha256(_payload())

    payload = _payload()
    payload["identity"]["window"]["start"] = "2026-01-01T00:00:00Z"
    payload["metrics"][0]["as_of"] = "2026-03-01T00:00:00+08:00"

    assert contract_sha256(payload) == baseline


def test_contract_sha256_preserves_decimal_precision() -> None:
    baseline = contract_sha256(_payload())

    payload = _payload()
    payload["run_ledger"][0]["unit_price"] = "0.01"
    assert contract_sha256(payload) != baseline

    payload = _payload()
    payload["run_ledger"][0]["unit_price"] = Decimal("0.010000")
    assert contract_sha256(payload) == baseline


def test_contract_sha256_ignores_generated_at_and_artifact_in_mapping() -> None:
    baseline = contract_sha256(_payload())

    payload = _payload()
    payload["generated_at"] = "2030-01-01T00:00:00+08:00"
    payload["artifact"]["report_html_sha256"] = "d" * 64

    assert contract_sha256(payload) == baseline


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_bytes_rejects_non_finite_floats(bad: float) -> None:
    payload = _payload()
    payload["metrics"][0]["numerator"] = bad

    with pytest.raises(ValueError):
        canonical_json_bytes(payload)

    contract = ReportContract.model_validate(payload)
    with pytest.raises(ValueError):
        contract_sha256(contract)


def test_canonical_json_bytes_is_compact_sorted_and_utf8() -> None:
    data = canonical_json_bytes(_payload())
    text = data.decode("utf-8")
    parsed = json.loads(text)

    assert list(parsed) == sorted(parsed)
    assert "generated_at" not in parsed
    assert "artifact" not in parsed
    assert "防胀气奶瓶" in text
    assert data.startswith(b'{"claims":')
    assert b'": ' not in data


def test_validate_contract_accepts_complete_contract() -> None:
    assert validate_contract(_contract()) == []


def test_validate_contract_flags_claim_without_counter_or_gap_evidence() -> None:
    contract = _contract()
    for evidence in contract.evidences:
        evidence.role = EvidenceRole.SUPPORT

    issues = validate_contract(contract)

    assert any("c-1" in issue and "counter" in issue for issue in issues)


def test_validate_contract_flags_unknown_coverage_source_tool() -> None:
    contract = _contract()
    contract.coverage.cells[0].source_tool_id = "unknown_tool"

    issues = validate_contract(contract)

    assert any("unknown_tool" in issue for issue in issues)


def test_validate_contract_accepts_success_coverage_backed_by_run_ledger_only() -> None:
    contract = _contract()
    contract.coverage.cells[0].source_tool_id = "ledger_only_tool"
    contract.run_ledger[0].tool_id = "ledger_only_tool"

    assert all(evidence.source_tool_id != "ledger_only_tool" for evidence in contract.evidences)
    assert validate_contract(contract) == []


@pytest.mark.parametrize("status", ["empty", "failed"])
def test_validate_contract_exempts_non_success_coverage_cells(status: CoverageStatus) -> None:
    contract = _contract()
    contract.coverage.cells[0].source_tool_id = "no_evidence_tool"
    contract.coverage.cells[0].status = status

    assert validate_contract(contract) == []


def test_validate_contract_does_not_treat_metric_id_as_source_tool() -> None:
    contract = _contract()
    contract.coverage.cells[0].source_tool_id = "mention_rate"

    assert all(evidence.source_tool_id != "mention_rate" for evidence in contract.evidences)
    assert all(row.tool_id != "mention_rate" for row in contract.run_ledger)

    issues = validate_contract(contract)

    assert any("mention_rate" in issue for issue in issues)


def test_validate_contract_flags_forbidden_word_below_l4() -> None:
    contract = _contract()
    contract.claims[0].evidence_grade = EvidenceGrade.L3_LIVE_SINGLE
    contract.claims[0].text = "确认防胀气卖点有效。"

    issues = validate_contract(contract)

    assert any("确认" in issue for issue in issues)


def test_validate_contract_allows_forbidden_word_at_l4() -> None:
    contract = _contract()
    contract.claims[0].text = "确认防胀气卖点有效。"

    assert validate_contract(contract) == []


def test_validate_contract_flags_illegal_gate_id() -> None:
    contract = _contract()
    contract.gates[0].gate_id = "G99"

    issues = validate_contract(contract)

    assert any("G99" in issue for issue in issues)


def test_handwritten_schema_has_draft_metadata() -> None:
    schema = _load_schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert isinstance(schema["title"], str) and schema["title"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_handwritten_schema_required_matches_pydantic() -> None:
    schema = _load_schema()
    generated = ReportContract.model_json_schema()

    assert schema["required"] == EXPECTED_REQUIRED_FIELDS
    assert generated["required"] == EXPECTED_REQUIRED_FIELDS
    assert set(schema["required"]) == set(generated["required"])


def test_handwritten_nested_required_sets_match_pydantic() -> None:
    schema = _load_schema()
    generated = ReportContract.model_json_schema()

    for pydantic_name, schema_name in PYDANTIC_TO_SCHEMA_DEFS.items():
        assert set(schema["$defs"][schema_name].get("required", [])) == set(
            generated["$defs"][pydantic_name].get("required", [])
        ), pydantic_name


def test_handwritten_property_sets_match_pydantic() -> None:
    schema = _load_schema()
    generated = ReportContract.model_json_schema()

    assert set(schema["properties"]) == set(generated["properties"])
    for pydantic_name, schema_name in PYDANTIC_TO_SCHEMA_DEFS.items():
        assert set(schema["$defs"][schema_name].get("properties", {})) == set(
            generated["$defs"][pydantic_name].get("properties", {})
        ), pydantic_name


def test_every_schema_object_forbids_additional_properties() -> None:
    schema = _load_schema()
    objects = [schema, *schema["$defs"].values()]

    for node in objects:
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False


def test_valid_contract_passes_pydantic_and_handwritten_schema() -> None:
    payload = _payload()
    schema = _load_schema()

    assert _schema_errors(payload, schema, schema) == []
    ReportContract.model_validate(payload)


def test_handwritten_schema_rejects_bare_coverage_array() -> None:
    payload = _payload()
    payload["coverage"] = payload["coverage"]["cells"]
    schema = _load_schema()

    errors = _schema_errors(payload, schema, schema)

    assert any("coverage" in error for error in errors)


def test_extra_fields_are_rejected_by_pydantic_and_handwritten_schema() -> None:
    payload = _payload()
    payload["unexpected_top_level"] = "x"
    payload["identity"]["unexpected_field"] = "x"
    schema = _load_schema()

    errors = _schema_errors(payload, schema, schema)

    assert any("unexpected_top_level" in error for error in errors)
    assert any("unexpected_field" in error for error in errors)
    with pytest.raises(ValidationError):
        ReportContract.model_validate(payload)

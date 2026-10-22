"""B5：报告模板注册表与合同构建器。

覆盖以下判据：

1. T1 / T5 / T2 三个模板都能构建出通过 ``validate_contract`` 的合同。
2. decision 三个固定槽位缺一个就报错。空数组合法。
3. 模板阈值直接来自 ``evidence_thresholds``。改表后模板跟着变。
4. 三个结构夹具都能经两个渲染器输出 HTML。
5. 结构夹具的证据等级不高于 L2。
6. 构建器不读时钟、不读库。

测试只使用夹具与内存对象。它们不读库、不联网。
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import data_intelligence_hub.services.report_builder as report_builder
import data_intelligence_hub.tool_catalog.evidence_thresholds as evidence_thresholds
from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
    contract_sha256,
    to_json,
    validate_contract,
)
from data_intelligence_hub.services.report_builder import (
    ReportContractBuildError,
    build_contract,
)
from data_intelligence_hub.services.report_renderers import (
    render_report_html,
    render_sop_html,
)
from data_intelligence_hub.services.report_templates import get_template, list_templates
from data_intelligence_hub.tool_catalog.evidence_grade import GRADE_ORDER, EvidenceGrade

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden_reports"
TEMPLATE_IDS = ("t1_voc", "t5_compliance", "t2_competitor")


def _load_payload(template_id: str) -> dict[str, Any]:
    path = FIXTURE_DIR / f"{template_id}.contract.json"
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _generated_at(payload: dict[str, Any]) -> datetime:
    text = str(payload["generated_at"])
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _rebuild(payload: dict[str, Any], **overrides: Any) -> ReportContract:
    """用夹具内容重走一遍构建器。overrides 用于替换单个输入。"""
    identity = overrides.pop("identity", payload["identity"])
    ledger = payload["run_ledger"]
    run = {
        "id": ledger[0]["run_id"],
        "task_id": identity["task_id"],
        "execution_mode": "fixture",
    }
    options: dict[str, Any] = {
        "run": run,
        "claims": payload["claims"],
        "evidences": payload["evidences"],
        "metrics": payload["metrics"],
        "coverage": payload["coverage"],
        "identity": identity,
        "decision": payload["decision"],
        "generated_at": _generated_at(payload),
        "gates": payload["gates"],
        "run_ledger": ledger,
        "limits": payload["limits"],
        "unknowns": payload["unknowns"],
        "artifact": payload["artifact"],
    }
    options.update(overrides)
    return build_contract(payload["template_id"], **options)


def test_list_templates_returns_the_three_b5_templates() -> None:
    assert [template.template_id for template in list_templates()] == list(TEMPLATE_IDS)


def test_get_template_rejects_a_b6_template() -> None:
    with pytest.raises(KeyError):
        get_template("t3_selection")


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_templates_declare_required_inputs(template_id: str) -> None:
    template = get_template(template_id)
    assert template.required_tools
    assert "brand" in template.required_params
    assert "markets" in template.required_params
    assert "window" in template.required_params
    assert "decision_question" in template.required_params


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_build_contract_passes_validate_contract(template_id: str) -> None:
    payload = _load_payload(template_id)
    contract = _rebuild(payload)
    assert contract.template_id == template_id
    assert validate_contract(contract) == []
    assert contract.artifact.contract_sha256 == contract_sha256(contract)


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_builder_reproduces_the_fixture_contract(template_id: str) -> None:
    payload = _load_payload(template_id)
    fixture = ReportContract.model_validate(payload)
    assert to_json(_rebuild(payload)) == to_json(fixture)


@pytest.mark.parametrize("slot", ["protect", "resolve", "prove"])
def test_build_contract_requires_each_decision_slot(slot: str) -> None:
    payload = _load_payload("t1_voc")
    decision = dict(payload["decision"])
    decision.pop(slot)
    with pytest.raises(ReportContractBuildError, match=slot):
        _rebuild(payload, decision=decision)


@pytest.mark.parametrize("slot", ["protect", "resolve", "prove"])
def test_build_contract_rejects_a_none_decision_slot(slot: str) -> None:
    payload = _load_payload("t1_voc")
    decision = dict(payload["decision"])
    decision[slot] = None
    with pytest.raises(ReportContractBuildError, match=slot):
        _rebuild(payload, decision=decision)


def test_build_contract_requires_decision() -> None:
    payload = _load_payload("t1_voc")
    with pytest.raises(ReportContractBuildError, match="decision"):
        _rebuild(payload, decision=None)


def test_build_contract_accepts_empty_decision_slots() -> None:
    payload = _load_payload("t1_voc")
    decision = dict(payload["decision"])
    decision.update({"protect": [], "resolve": [], "prove": []})
    contract = _rebuild(payload, decision=decision)
    assert contract.decision.protect == []
    assert contract.decision.resolve == []
    assert contract.decision.prove == []


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_template_threshold_reads_the_single_table(template_id: str) -> None:
    template = get_template(template_id)
    assert template.threshold is evidence_thresholds.EVIDENCE_THRESHOLDS[template_id]


def test_template_threshold_follows_table_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = evidence_thresholds.EVIDENCE_THRESHOLDS["t1_voc"]
    changed = dataclasses.replace(original, required_n=original.required_n + 1)
    table = dict(evidence_thresholds.EVIDENCE_THRESHOLDS)
    table["t1_voc"] = changed
    monkeypatch.setattr(evidence_thresholds, "EVIDENCE_THRESHOLDS", table)
    assert get_template("t1_voc").threshold.required_n == changed.required_n
    assert get_template("t1_voc").threshold is changed


def test_build_contract_rejects_a_bare_coverage_list() -> None:
    payload = _load_payload("t1_voc")
    with pytest.raises(ReportContractBuildError, match="cells"):
        _rebuild(payload, coverage=payload["coverage"]["cells"])


def test_build_contract_rejects_a_claim_without_counter_or_gap_evidence() -> None:
    payload = _load_payload("t1_voc")
    evidences = [
        evidence
        for evidence in copy.deepcopy(payload["evidences"])
        if evidence["role"] != "gap"
    ]
    with pytest.raises(ReportContractBuildError, match="counter 或 gap"):
        _rebuild(payload, evidences=evidences)


def test_builder_recomputes_the_artifact_contract_hash() -> None:
    payload = _load_payload("t2_competitor")
    artifact = dict(payload["artifact"])
    artifact["contract_sha256"] = "f" * 64
    contract = _rebuild(payload, artifact=artifact)
    assert contract.artifact.contract_sha256 != "f" * 64
    assert contract.artifact.contract_sha256 == contract_sha256(contract)


def test_build_contract_rejects_above_l2_claim_for_a_fixture_run() -> None:
    payload = _load_payload("t1_voc")
    claims = copy.deepcopy(payload["claims"])
    claims[0]["evidence_grade"] = "L3_live_single"
    with pytest.raises(ReportContractBuildError, match="L2"):
        _rebuild(payload, claims=claims)


def test_build_contract_rejects_above_l2_ledger_for_a_fixture_run() -> None:
    payload = _load_payload("t1_voc")
    ledger = copy.deepcopy(payload["run_ledger"])
    ledger[0]["evidence_grade"] = "L4_authorized_live"
    with pytest.raises(ReportContractBuildError, match="L2"):
        _rebuild(payload, run_ledger=ledger)


def _live_run(payload: dict[str, Any]) -> dict[str, Any]:
    """同一份夹具，但 run 标记为 live。用于绕开夹具等级上限。"""
    return {
        "id": payload["run_ledger"][0]["run_id"],
        "task_id": payload["identity"]["task_id"],
        "execution_mode": "live",
    }


def _l3_inputs(
    payload: dict[str, Any],
    status: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把第一条 claim 与全部 evidence 提到 L3，并设置给定状态。"""
    claims = copy.deepcopy(payload["claims"])
    for claim in claims:
        claim["evidence_grade"] = "L3_live_single"
    claims[0]["claim_status"] = status
    evidences = copy.deepcopy(payload["evidences"])
    for evidence in evidences:
        evidence["evidence_grade"] = "L3_live_single"
    return claims, evidences


def test_build_contract_rejects_claim_status_above_the_grade_ceiling() -> None:
    """构建时就要拒绝越级状态，不等渲染。"""
    payload = _load_payload("t1_voc")
    claims, evidences = _l3_inputs(payload, "confirmed")

    with pytest.raises(ReportContractBuildError, match="claim_status"):
        _rebuild(
            payload,
            claims=claims,
            evidences=evidences,
            run=_live_run(payload),
        )


def test_build_contract_accepts_directional_claim_at_l3_for_a_live_run() -> None:
    """directional + L3 在 live 运行下可以构建。"""
    payload = _load_payload("t1_voc")
    claims, evidences = _l3_inputs(payload, "directional")

    contract = _rebuild(
        payload,
        claims=claims,
        evidences=evidences,
        run=_live_run(payload),
    )

    assert contract.claims[0].claim_status == "directional"


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_fixture_contracts_render_both_views(template_id: str) -> None:
    contract = ReportContract.model_validate(_load_payload(template_id))
    report_html = render_report_html(contract)
    sop_html = render_sop_html(contract)
    assert report_html.startswith("<!doctype html>")
    assert sop_html.startswith("<!doctype html>")
    assert template_id in report_html
    assert template_id in sop_html
    assert "__REPORT_HASH__" not in report_html
    assert "__SOP_HASH__" not in sop_html
    assert len(report_html) > 1000
    assert len(sop_html) > 1000


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_fixture_grades_stay_at_or_below_l2(template_id: str) -> None:
    contract = ReportContract.model_validate(_load_payload(template_id))
    ceiling = GRADE_ORDER[EvidenceGrade.L2_FIXTURE_LOCAL]
    grades = [claim.evidence_grade for claim in contract.claims]
    grades.extend(evidence.evidence_grade for evidence in contract.evidences)
    grades.extend(row.evidence_grade for row in contract.run_ledger)
    assert grades
    assert all(GRADE_ORDER[grade] <= ceiling for grade in grades)


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_fixture_limits_mark_the_structural_fixture(template_id: str) -> None:
    contract = ReportContract.model_validate(_load_payload(template_id))
    assert any("fixture" in text.lower() for text in contract.limits)


def test_builder_does_not_read_a_clock_or_open_a_connection() -> None:
    source = inspect.getsource(report_builder)
    assert "datetime.now" not in source
    assert "time.time" not in source
    assert "Session" not in source
    assert "httpx" not in source
    signature = inspect.signature(build_contract)
    forbidden = {"session", "db", "now", "clock", "http_client"}
    assert forbidden.isdisjoint(signature.parameters)

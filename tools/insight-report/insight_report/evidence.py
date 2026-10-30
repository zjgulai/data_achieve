"""Evidence grading and counterevidence slots.

Implements the grading half of SOP skill ``voc-insight-analysis`` (G8) and the
six-state vocabulary used by the report contract.  The rule order is fixed:
Not authorized > Blocked > Evidence gap > Confirmed > Directional >
Supported hypothesis.  First match wins; an author cannot self-select a grade.

``NO_COUNTEREVIDENCE_FOUND`` is a required literal when a search for
contradicting records returns nothing.  An empty counterevidence field is a
build failure, never a silent omission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import contract

NO_COUNTEREVIDENCE = "NO_COUNTEREVIDENCE_FOUND"

STATUS_DISPLAY_CASE = {
    "confirmed": "Confirmed",
    "directional": "Directional",
    "hypothesis": "Supported hypothesis",
    "evidence_gap": "Evidence gap",
    "blocked": "Blocked",
    "not_authorized": "Not authorized",
}


@dataclass
class GradeInput:
    topic: str = "consumer_experience"
    required_gate: str | None = None
    gate_status: str = "PASS"
    denominator: int | None = None
    frame: str = "natural"
    is_prevalence_claim: bool = False
    required_cell_count: int | None = 1
    required_field_missing_rate: float = 0.0
    is_direct_fact: bool = False
    artifact_sha256: str | None = None
    exact_identity: bool = False
    inference: bool = True
    n_independent: int = 0
    n_authors: int = 0
    direction_share: float = 0.0
    single_coded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def assign_grade(ctx: GradeInput) -> str:
    if ctx.topic in {"medical_efficacy", "safety", "causality", "diagnosis"}:
        return "not_authorized"
    if ctx.required_gate and ctx.gate_status != "PASS":
        return "blocked"
    if ctx.is_prevalence_claim and (ctx.denominator in (None, 0) or ctx.frame == "diagnostic"):
        return "blocked"
    if ctx.required_cell_count == 0 or ctx.required_field_missing_rate >= 1.0:
        return "evidence_gap"
    if ctx.is_direct_fact and ctx.artifact_sha256 and ctx.exact_identity and not ctx.inference:
        return "confirmed"
    if ctx.n_independent >= 8 and ctx.n_authors >= 2 and ctx.direction_share >= 0.70 and ctx.single_coded:
        return "directional"
    if 3 <= ctx.n_independent < 8 or 0.55 <= ctx.direction_share < 0.70 or ctx.n_authors == 1:
        return "hypothesis"
    if ctx.n_independent == 0:
        return "evidence_gap"
    return "hypothesis"


def confirmed_inputs(artifact_sha256: str) -> dict[str, Any]:
    return GradeInput(
        is_direct_fact=True,
        artifact_sha256=artifact_sha256,
        exact_identity=True,
        inference=False,
        required_cell_count=1,
    ).to_dict()


def hypothesis_inputs(n_independent: int, n_authors: int, direction_share: float) -> dict[str, Any]:
    return GradeInput(
        n_independent=n_independent,
        n_authors=n_authors,
        direction_share=direction_share,
        single_coded=True,
        required_cell_count=1,
    ).to_dict()


def gap_inputs() -> dict[str, Any]:
    return GradeInput(required_cell_count=0).to_dict()


def blocked_inputs(required_gate: str, gate_status: str, *, denominator: int | None = 0, frame: str = "natural") -> dict[str, Any]:
    return GradeInput(
        required_gate=required_gate,
        gate_status=gate_status,
        denominator=denominator,
        is_prevalence_claim=True,
        frame=frame,
    ).to_dict()


def not_authorized_inputs(topic: str = "medical_efficacy") -> dict[str, Any]:
    return GradeInput(topic=topic).to_dict()


def grade_input_from_dict(payload: dict[str, Any]) -> GradeInput:
    allowed = set(GradeInput.__dataclass_fields__)
    return GradeInput(**{k: v for k, v in payload.items() if k in allowed})


def status_for(grade: str, scope: str, inputs: dict[str, Any], gate: str | None = None) -> dict[str, Any]:
    return contract.evidence_status(grade, scope, inputs, gate=gate)


def no_counterevidence(reason: str) -> str:
    return f"{NO_COUNTEREVIDENCE}: {reason}"


def counterevidence_with_count(counter_count: int, unit: str, what_would_overturn: str) -> str:
    if counter_count <= 0:
        return no_counterevidence(what_would_overturn)
    return f"反向记录 {counter_count} 条（{unit}）存在，不能把方向性结论写成单向事实；{what_would_overturn}"


_VERB_STARTS = (
    "先",
    "补",
    "用",
    "把",
    "停止",
    "验证",
    "重跑",
    "分开",
    "保留",
    "记录",
    "增加",
    "移除",
    "标",
    "在",
    "只",
    "不",
)


def _has_digit(text: str) -> bool:
    return bool(re.search(r"[0-9]", text))


def make_claim(
    claim_id: str,
    section: str,
    headline: str,
    grade: str,
    grade_inputs: dict[str, Any],
    observed: str,
    interpretation: str,
    counterevidence: str,
    decision_implication: str,
    basis: str,
    unit: str,
    limit: str,
    records: list[str],
    numbers: list[dict[str, Any]],
    *,
    status_scope: str = "PRE-G7",
) -> dict[str, Any]:
    contract.require(section in contract.SECTION_IDS, f"claim {claim_id}: bad section {section}")
    contract.require(bool(re.fullmatch(r"C[0-9]{2}", claim_id)), f"claim id must be C00: {claim_id}")
    contract.require(len(headline) >= 12, f"claim {claim_id}: headline too short")
    contract.require(grade in contract.STATUS_ORDER, f"claim {claim_id}: bad grade {grade}")
    computed = assign_grade(grade_input_from_dict(grade_inputs))
    contract.require(computed == grade, f"claim {claim_id}: grade {grade} does not match inputs -> {computed}")
    for field_name, value in (
        ("observed", observed),
        ("interpretation", interpretation),
        ("counterevidence", counterevidence),
        ("decision_implication", decision_implication),
    ):
        contract.require(len(str(value).strip()) >= 8, f"claim {claim_id}: {field_name} too short")
    contract.require(_has_digit(observed), f"claim {claim_id}: observed must contain a number or named cell")
    contract.require(interpretation.strip() != observed.strip(), f"claim {claim_id}: interpretation repeats observed")
    contract.require(not decision_implication.strip().startswith("进一步研究"), f"claim {claim_id}: empty decision action")
    contract.require(any(decision_implication.strip().startswith(v) for v in _VERB_STARTS), f"claim {claim_id}: decision must start with a verb")
    contract.require(len(numbers) >= 1, f"claim {claim_id}: at least one NumberRef is required")
    for number in numbers:
        for key in ("name", "value", "unit", "basis", "denominator", "source_path"):
            contract.require(key in number, f"claim {claim_id}: NumberRef missing {key}")
        contract.require(len(str(number["basis"])) >= 8, f"claim {claim_id}: NumberRef basis too short")
    return {
        "claim_id": claim_id,
        "section": section,
        "headline": headline,
        "grade": grade,
        "grade_inputs": grade_inputs,
        "observed": observed,
        "interpretation": interpretation,
        "counterevidence": counterevidence,
        "decision_implication": decision_implication,
        "basis": basis,
        "unit": unit,
        "limit": limit,
        "status": f"{STATUS_DISPLAY_CASE[grade]} · {status_scope}",
        "records": records,
        "numbers": numbers,
    }


def claim_maturity(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for claim in claims:
        rows.append(
            {
                "claim_id": claim["claim_id"],
                "label": claim["headline"][:26],
                "status": claim["grade"],
                "reason": claim["limit"],
                "gate": "G7" if claim["grade"] in {"blocked", "hypothesis", "directional"} else None,
                "current": True,
            }
        )
    return rows


def status_legend_block() -> dict[str, Any]:
    return {
        "type": "status_legend",
        "title": "六级证据状态：先命中先停",
        "statuses": contract.STATUS_LEGEND,
    }


def prohibited_outputs_block() -> list[dict[str, Any]]:
    return [dict(item) for item in contract.PROHIBITED_OUTPUTS]


def evidence_ledger(claims: list[dict[str, Any]], identity: dict[str, Any], counting: dict[str, Any]) -> dict[str, Any]:
    return {
        "claims": [
            {
                "claim_id": claim["claim_id"],
                "grade": claim["grade"],
                "status": claim["status"],
                "numbers": claim["numbers"],
                "counterevidence": claim["counterevidence"],
            }
            for claim in claims
        ],
        "identity_gaps": identity.get("gaps") or [],
        "counting_levels": counting.get("levels") or [],
        "reconciliation": counting.get("reconciliation") or [],
        "metric_rows": 0,
        "note": "G7 BLOCKED; every consumer-experience claim is capped at Directional or Supported hypothesis.",
    }

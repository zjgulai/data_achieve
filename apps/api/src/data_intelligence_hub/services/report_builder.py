"""报告合同构建器。

本模块把模板、运行事实与证据组装成 ``ReportContract``。
它是纯函数层。它不读库、不联网、不读时钟。
调用方必须传入全部输入。``generated_at`` 也由调用方给出。

构建分四步：

1. 校验模板 ID 与 decision 三槽位。
2. 用 Pydantic 模型做结构校验。
3. 调用 ``validate_contract`` 做语义校验。
4. 重算 ``artifact.contract_sha256``。

任一校验失败时，本模块抛 ``ReportContractBuildError``。
decision 的 ``protect`` / ``resolve`` / ``prove`` 必须由调用方给出。
本模块不填占位文本。空数组是合法取值，缺失的键不是。

夹具运行（``execution_mode='fixture'``）的证据等级不得高于 L2。
这条规则与 Playbook 1.5 一致。夹具只能写方法验证。

``validate_contract`` 同时检查 claim 状态上限。上限表只有一份：
``schemas.report_contract.max_claim_status_for_grade``。
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, Final

from pydantic import ValidationError

from data_intelligence_hub.schemas.report_contract import (
    SCHEMA_VERSION,
    Artifact,
    Decision,
    ReportContract,
    contract_sha256,
    validate_contract,
)
from data_intelligence_hub.services.report_templates import ReportTemplate, get_template
from data_intelligence_hub.tool_catalog.evidence_grade import GRADE_ORDER, EvidenceGrade

_DECISION_SLOTS: Final[tuple[str, ...]] = ("protect", "resolve", "prove")
_MISSING: Final = object()


class ReportContractBuildError(ValueError):
    """合同构建失败。原因见异常文本。"""


def _as_mapping(value: object, *, name: str) -> Mapping[str, Any]:
    """把合同输入转成映射。本函数不修改输入。"""
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump(mode="python")
        except TypeError:
            dumped = dump()
        if isinstance(dumped, Mapping):
            return dumped
        raise ReportContractBuildError(f"{name} 的 model_dump() 必须返回映射")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, Mapping):
        return {
            str(key): item
            for key, item in attributes.items()
            if not str(key).startswith("_")
        }
    raise ReportContractBuildError(f"{name} 必须是映射或对象")


def _run_field(source: object, *names: str, default: Any = _MISSING) -> Any:
    """按候选名从 run 取字段。缺失且无默认值时抛错。"""
    if isinstance(source, Mapping):
        for name in names:
            if name in source:
                return source[name]
    else:
        for name in names:
            if hasattr(source, name):
                return getattr(source, name)
    if default is _MISSING:
        raise ReportContractBuildError(f"run 缺少字段：{names[0]}")
    return default


def _template_or_error(template_id: str) -> ReportTemplate:
    try:
        return get_template(template_id)
    except KeyError:
        raise ReportContractBuildError(f"未知报告模板：{template_id}") from None


def _identity_payload(identity: object, run: object) -> dict[str, Any]:
    """整理 identity。缺 task_id 时从 run 取。"""
    data = dict(_as_mapping(identity, name="identity"))
    if data.get("task_id") is None:
        data["task_id"] = _run_field(run, "task_id")
    return data


def _decision_payload(decision: object) -> dict[str, Any]:
    """整理 decision。三个固定槽位缺一个就抛错。"""
    if decision is None:
        raise ReportContractBuildError("decision 必须由调用方给出")
    if isinstance(decision, Decision):
        return decision.model_dump(mode="python")
    data = dict(_as_mapping(decision, name="decision"))
    for slot in _DECISION_SLOTS:
        if slot not in data or data[slot] is None:
            raise ReportContractBuildError(f"decision 缺少槽位：{slot}")
    for key in ("decision_question", "answer"):
        if key not in data:
            raise ReportContractBuildError(f"decision 缺少字段：{key}")
    return data


def _coverage_payload(coverage: object) -> dict[str, Any]:
    """整理 coverage。只接受 ``{"cells": [...]}`` 对象。"""
    if isinstance(coverage, (list, tuple)):
        raise ReportContractBuildError(
            'coverage 必须是对象 {"cells": [...]}，不接受裸数组'
        )
    data = dict(_as_mapping(coverage, name="coverage"))
    if "cells" not in data:
        raise ReportContractBuildError("coverage 缺少 cells 字段")
    return data


def _artifact_payload(artifact: object | None) -> dict[str, Any]:
    """整理 artifact。

    缺省时两个 HTML 哈希与合同哈希写空串。
    调用方在渲染后填写两个 HTML 哈希。
    构建器最后重算合同哈希。
    """
    if artifact is None:
        return {
            "report_html_sha256": "",
            "sop_html_sha256": "",
            "contract_sha256": "",
        }
    if isinstance(artifact, Artifact):
        return artifact.model_dump(mode="python")
    return dict(_as_mapping(artifact, name="artifact"))


def _run_ledger_payload(
    run: object,
    run_ledger: Iterable[object] | None,
) -> list[object]:
    """整理 run_ledger。

    调用方给出 run_ledger 时原样使用。
    否则用 run 的单行事实构造一行。该 run 必须带账本字段。
    """
    if run_ledger is not None:
        return list(run_ledger)
    endpoint_type = _run_field(run, "endpoint_type", "tool_id")
    return [
        {
            "run_id": _run_field(run, "id", "run_id"),
            "tool_id": _run_field(run, "tool_id", default=endpoint_type),
            "endpoint_type": endpoint_type,
            "actor_id": _run_field(run, "actor_id", default=None),
            "unit": _run_field(run, "unit"),
            "quantity": _run_field(run, "quantity"),
            "unit_price": _run_field(run, "unit_price"),
            "total_cost_usd": _run_field(run, "total_cost_usd"),
            "authorization_id": _run_field(run, "authorization_id", default=None),
            "evidence_grade": _run_field(run, "evidence_grade"),
            "started_at": _run_field(run, "started_at"),
            "finished_at": _run_field(run, "finished_at"),
            "outcome": _run_field(run, "outcome"),
        }
    ]


def _assert_fixture_grades(run: object, contract: ReportContract) -> None:
    """夹具运行的证据等级不得高于 L2。"""
    mode = str(_run_field(run, "execution_mode", default="live")).strip().lower()
    if mode != "fixture":
        return
    ceiling = GRADE_ORDER[EvidenceGrade.L2_FIXTURE_LOCAL]
    offenders: list[str] = []
    for claim in contract.claims:
        if GRADE_ORDER[claim.evidence_grade] > ceiling:
            offenders.append(f"claim {claim.claim_id}")
    for evidence in contract.evidences:
        if GRADE_ORDER[evidence.evidence_grade] > ceiling:
            offenders.append(f"evidence {evidence.evidence_id}")
    for row in contract.run_ledger:
        if GRADE_ORDER[row.evidence_grade] > ceiling:
            offenders.append(f"run {row.run_id}")
    if offenders:
        raise ReportContractBuildError(
            "夹具运行的证据等级不得高于 L2_fixture_local：" + "、".join(offenders)
        )


def build_contract(
    template_id: str,
    *,
    run: object,
    claims: Iterable[object],
    evidences: Iterable[object],
    metrics: Iterable[object],
    coverage: object,
    identity: object,
    decision: object,
    generated_at: datetime,
    gates: Iterable[object] = (),
    run_ledger: Iterable[object] | None = None,
    limits: Iterable[str] = (),
    unknowns: Iterable[str] = (),
    artifact: object | None = None,
) -> ReportContract:
    """构建一份完整报告合同。

    本函数不读库、不联网、不读时钟。全部输入来自参数。

    ``decision`` 必须是映射或 :class:`Decision`。
    映射缺少 ``protect`` / ``resolve`` / ``prove`` 任一键时抛错。
    空数组合法。构建器不填占位文本。

    ``coverage`` 只接受 ``{"cells": [...]}`` 对象。
    裸数组抛错。

    ``run_ledger`` 为 None 时，本函数用 ``run`` 构造一行。
    此时 run 必须带 ``unit``、``quantity``、``unit_price``、
    ``total_cost_usd``、``evidence_grade``、``started_at``、
    ``finished_at`` 与 ``outcome``。

    ``validate_contract`` 会拒绝超过证据等级上限的 claim 状态。
    越级时本函数直接抛 ``ReportContractBuildError``，不等渲染。

    构建器重算 ``artifact.contract_sha256``。调用方传入的值会被覆盖。
    该哈希排除 ``generated_at`` 与 ``artifact``，所以不会自引用。
    """
    template = _template_or_error(template_id)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "template_id": template.template_id,
        "generated_at": generated_at,
        "identity": _identity_payload(identity, run),
        "decision": _decision_payload(decision),
        "gates": list(gates),
        "coverage": _coverage_payload(coverage),
        "metrics": list(metrics),
        "claims": list(claims),
        "evidences": list(evidences),
        "run_ledger": _run_ledger_payload(run, run_ledger),
        "limits": list(limits),
        "unknowns": list(unknowns),
        "artifact": _artifact_payload(artifact),
    }
    try:
        contract = ReportContract.model_validate(payload)
    except ValidationError as exc:
        raise ReportContractBuildError(f"合同结构校验失败：{exc}") from exc
    _assert_fixture_grades(run, contract)
    # validate_contract 按 max_claim_status_for_grade 检查 claim 状态上限。
    issues = validate_contract(contract)
    if issues:
        raise ReportContractBuildError("合同语义校验失败：" + "；".join(issues))
    contract.artifact.contract_sha256 = contract_sha256(contract)
    return contract


__all__ = ["ReportContractBuildError", "build_contract"]

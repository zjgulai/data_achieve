"""Shared contract primitives for the insight-report pipeline.

Implements the Data Contract vocabulary (CountBlock, SourceRef,
EvidenceStatus, Claim, readout, source_foot) and the fixed section table.

SOP coverage for this module: none of the 14 skills is implemented here.
This file only encodes contracts consumed by the other modules.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date, datetime, timezone
from typing import Any

SCHEMA_VERSION = "voc-report-v1.0.0"
VALIDATOR_VERSION = "insight-report-v1.0.0"

# Six evidence states, ordered exactly as the contract requires.
STATUS_ORDER = [
    "confirmed",
    "directional",
    "hypothesis",
    "evidence_gap",
    "blocked",
    "not_authorized",
]

DISPLAY_LABELS = {
    "confirmed": "CONFIRMED",
    "directional": "DIRECTIONAL",
    "hypothesis": "SUPPORTED HYPOTHESIS",
    "evidence_gap": "EVIDENCE GAP",
    "blocked": "BLOCKED",
    "not_authorized": "NOT AUTHORIZED",
}

REASON_CODES = {
    "confirmed": "EVID_CONFIRMED",
    "directional": "EVID_DIRECTIONAL",
    "hypothesis": "EVID_HYPOTHESIS",
    "evidence_gap": "EVID_GAP",
    "blocked": "EVID_BLOCKED",
    "not_authorized": "EVID_NOT_AUTHORIZED",
}

# The old contract's grade spellings that must be normalised on input.
GRADE_ALIASES = {
    "Confirmed": "confirmed",
    "Directional": "directional",
    "Hypothesis": "hypothesis",
    "Supported hypothesis": "hypothesis",
    "Evidence gap": "evidence_gap",
    "Gap": "evidence_gap",
    "Blocked": "blocked",
    "Not authorized": "not_authorized",
}

UNIT_ENUM = [
    "raw_object",
    "occurrence",
    "canonical_record",
    "frame_membership",
    "annotation",
    "metric_row",
    "variant",
    "author",
    "claim",
    "currency_usd",
]

SECTION_SPEC = [
    {"index": "00", "id": "answer", "kicker": "EXECUTIVE ANSWER"},
    {"index": "01", "id": "experience", "kicker": "CORE TENSION"},
    {"index": "02", "id": "aspects", "kicker": "EXPERIENCE SIGNATURE"},
    {"index": "03", "id": "frames", "kicker": "SAMPLE LENSES"},
    {"index": "04", "id": "mixed", "kicker": "MIXED EXPERIENCE"},
    {"index": "05", "id": "contexts", "kicker": "NEED STATES"},
    {"index": "06", "id": "journey", "kicker": "MOMENTS OF TRUTH"},
    {"index": "07", "id": "social", "kicker": "SOCIAL FIREWALL"},
    {"index": "08", "id": "variant", "kicker": "EVIDENCE APPLICABILITY"},
    {"index": "09", "id": "agenda", "kicker": "VALIDATION AGENDA"},
    {"index": "10", "id": "evidence", "kicker": "TRUST & LIMITS"},
]

SECTION_IDS = [s["id"] for s in SECTION_SPEC]

# The 14 SOP skills.  ``status`` is one of: implemented, consumed, partial, not_implemented.
SOP_COVERAGE = [
    {
        "skill": "voc-decision-charter",
        "gate": "G0",
        "status": "not_implemented",
        "note": "决策 owner、预算与发布边界是人工授权；本管线只读取 gate 状态。",
    },
    {
        "skill": "voc-product-identity",
        "gate": "G1",
        "status": "implemented",
        "note": "identity.py 从 PDP HTML 冻结 parent/child/variant，并给每个映射写 confidence。",
    },
    {
        "skill": "voc-source-rights-audit",
        "gate": "G2",
        "status": "not_implemented",
        "note": "权利与隐私判断需要法务；本管线只消费已登记的 blocked/conditional 状态。",
    },
    {
        "skill": "voc-source-pilot",
        "gate": "G3",
        "status": "partial",
        "note": "ingest.py 校验 raw 与 ledger 的血缘；不发起网络 pilot。",
    },
    {
        "skill": "voc-taxonomy-freeze",
        "gate": "G4",
        "status": "consumed",
        "note": "coding.py 读取冻结的 taxonomy.json；不创建或修改 taxonomy。",
    },
    {
        "skill": "voc-stratified-collection",
        "gate": "G5",
        "status": "consumed",
        "note": "ingest.py 读取 collection-run-ledger.json；不执行采集。",
    },
    {
        "skill": "voc-canonicalize",
        "gate": "G6",
        "status": "implemented",
        "note": "counting.py 实现 raw→occurrence→canonical→frame membership 的逐级扣减。",
    },
    {
        "skill": "voc-coding-calibration",
        "gate": "G7",
        "status": "partial",
        "note": "coding.py 实现可复算的规则编码；双人校准与 agreement 未实现，G7 保持 BLOCKED。",
    },
    {
        "skill": "voc-insight-analysis",
        "gate": "G8",
        "status": "implemented",
        "note": "build_report.py 生成 claim/exhibit，并按六级证据状态机械降级。",
    },
    {
        "skill": "voc-strategy-activation",
        "gate": "G9",
        "status": "not_implemented",
        "note": "只生成 proposed 实验；审批、owner 与上线动作不在本管线。",
    },
    {
        "skill": "voc-measurement-review",
        "gate": "G10",
        "status": "not_implemented",
        "note": "没有实验运行数据与结果对账。",
    },
    {
        "skill": "voc-interactive-report",
        "gate": None,
        "status": "implemented",
        "note": "render.py 输出单文件、零外部请求的 report.html。",
    },
    {
        "skill": "voc-research-orchestrator",
        "gate": None,
        "status": "partial",
        "note": "build_report.py 串起 ingest→identity→counting→coding→evidence；不调度人工 gate。",
    },
    {
        "skill": "voc-validation-handoff",
        "gate": None,
        "status": "implemented",
        "note": "validate.py 跑 30 条不变式、反模式扫描与渲染后 HTML 检查。",
    },
]

PROHIBITED_OUTPUTS = [
    {
        "id": "PO1",
        "label": "总体情绪率、满意率或净情绪分",
        "reason": "非概率样本，多标签 annotation，不是总体；任何合计都不能当比率。",
        "gate": "G8",
        "severity": "hard",
        "applies_to_sections": SECTION_IDS,
    },
    {
        "id": "PO2",
        "label": "Love vs Complaint 的饼图或百分比",
        "reason": "多标签、非互斥、没有总体分母；只能并排绝对计数。",
        "gate": "G8",
        "severity": "hard",
        "applies_to_sections": ["aspects", "mixed", "social"],
    },
    {
        "id": "PO3",
        "label": "跨 frame 的情绪比例比较",
        "reason": "natural / diagnostic / qualitative_seed 的选择机制不同，分母不可比。",
        "gate": "G8",
        "severity": "hard",
        "applies_to_sections": ["frames", "evidence"],
    },
    {
        "id": "PO4",
        "label": "把 annotation hits 当作人数或发生率",
        "reason": "一条记录可贡献多个标注，annotation 不是人，也不是独立记录。",
        "gate": "G7",
        "severity": "hard",
        "applies_to_sections": ["experience", "aspects", "mixed"],
    },
    {
        "id": "PO5",
        "label": "Amazon 星级分布当作消费者情绪",
        "reason": "星级不是情绪量表，样本非概率；只能作为商品质量与身份上下文。",
        "gate": "G8",
        "severity": "hard",
        "applies_to_sections": ["variant"],
    },
    {
        "id": "PO6",
        "label": "统计显著性、回归、驱动贡献或 ROI 排名",
        "reason": "未做统计检验，也没有成本与结果口径。",
        "gate": "G9",
        "severity": "hard",
        "applies_to_sections": ["agenda", "evidence"],
    },
    {
        "id": "PO7",
        "label": "医学功效、安全率、诊断或因果结论",
        "reason": "超出授权，需医学与法务 review；只允许记录 self-report。",
        "gate": "G9",
        "severity": "hard",
        "applies_to_sections": ["contexts", "variant", "evidence"],
    },
    {
        "id": "PO8",
        "label": "把样本覆盖写成逐级转化，或用覆盖数推断市场结构",
        "reason": "frame membership 可重叠，覆盖不是转化。",
        "gate": "G6",
        "severity": "hard",
        "applies_to_sections": ["journey", "evidence"],
    },
]

STATUS_LEGEND = [
    {
        "status": "confirmed",
        "label": "Confirmed",
        "rule": "直接事实 + artifact sha256 + 精确身份 + 无推断",
        "may_use": "身份、计数、成本、字段值、血缘",
        "may_not_use": "体验、偏好、因果",
    },
    {
        "status": "directional",
        "label": "Directional",
        "rule": "同一 frame >=8 条、>=2 作者、方向一致 >=70%，仍为单编码",
        "may_use": "方向判断、实验设计",
        "may_not_use": "prevalence、总体比率、对外承诺",
    },
    {
        "status": "hypothesis",
        "label": "Supported hypothesis",
        "rule": "3-7 条，或方向一致 55-70%，或只有 1 个作者",
        "may_use": "提出假设、设计下一轮采集",
        "may_not_use": "写成发现、据此改产品",
    },
    {
        "status": "evidence_gap",
        "label": "Evidence gap",
        "rule": "required cell = 0 或关键字段全缺",
        "may_use": "指出缺口与补证动作",
        "may_not_use": "用其他 variant、family 或相邻来源推断",
    },
    {
        "status": "blocked",
        "label": "Blocked",
        "rule": "所需 gate 未 PASS，或分母为 null/0",
        "may_use": "解释为什么不能说",
        "may_not_use": "任何比率、排名、正式策略",
    },
    {
        "status": "not_authorized",
        "label": "Not authorized",
        "rule": "医学、安全、因果、诊断",
        "may_use": "只记录 self-report",
        "may_not_use": "疗效、安全率、诊断",
    },
]

ANTI_PATTERN_TERMS = [
    "总体情绪率",
    "满意率",
    "净情绪分",
    "净推荐值",
    "NPS",
    "ROI 排名",
    "净值打分",
    "净值",
    "饼图",
    "漏斗图",
    "漏斗",
    "转化率",
    "用户都说",
    "所有人都",
    "显著",
    "证明",
    "导致",
    "行业第一",
    "领先",
]


class ContractError(RuntimeError):
    """Raised when report data violates the frozen contract."""


class DataGap(RuntimeError):
    """Raised when an optional module has no usable data.

    The orchestrator converts this into a visible gap block instead of
    crashing the whole run.
    """

    def __init__(self, section: str, reason: str):
        super().__init__(f"{section}: {reason}")
        self.section = section
        self.reason = reason


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return date.today().isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def count_block(
    value: int | float | None,
    unit: str,
    basis: str,
    source_path: str,
    *,
    denominator: int | None = None,
    multi_label: bool = False,
    partition: bool = False,
    as_of: str | None = None,
    gap_reason: str | None = None,
) -> dict[str, Any]:
    """Build a CountBlock.

    ``value=None`` is allowed only together with ``gap_reason``.  The report
    contract forbids using 0 as a stand-in for missing data, so callers must
    make the gap explicit.  The report assembler replaces such blocks with a
    gap block before writing report-data.json; intermediate artifacts keep the
    null plus reason.
    """
    if value is None:
        require(bool(gap_reason), f"null count requires gap_reason: {source_path}")
        value = None
    require(unit in UNIT_ENUM, f"unknown unit: {unit}")
    require(len(basis) >= 8, f"basis too short for {source_path}")
    if value is not None:
        require(value >= 0, f"negative count: {source_path}")
    return {
        "value": value,
        "unit": unit,
        "basis": basis,
        "denominator": denominator,
        "multi_label": bool(multi_label),
        "partition": bool(partition),
        "as_of": as_of or today_iso(),
        "source_path": source_path,
    }


def source_ref_artifact(path: str, sha256: str, provider: str | None = None) -> dict[str, Any]:
    require(bool(re.fullmatch(r"[0-9a-f]{64}", sha256 or "")), f"bad sha256 for {path}")
    return {
        "kind": "artifact",
        "provider": provider,
        "endpoint": None,
        "table": None,
        "columns": None,
        "path": path,
        "sha256": sha256,
        "blocked_reason": None,
    }


def source_ref_blocked(reason: str, provider: str | None = None) -> dict[str, Any]:
    require(reason.startswith("[BLOCKED: "), "blocked_reason must start with [BLOCKED: ")
    return {
        "kind": "blocked",
        "provider": provider,
        "endpoint": None,
        "table": None,
        "columns": None,
        "path": None,
        "sha256": None,
        "blocked_reason": reason,
    }


def text_provenance(
    text: str,
    claim_id: str | None,
    data_refs: list[str] | None = None,
    *,
    authored_by: str = "template",
    reviewed_by: str = "UNASSIGNED",
) -> dict[str, Any]:
    require(authored_by in {"human", "llm_assisted", "template"}, f"bad authored_by {authored_by}")
    return {
        "text": text,
        "authored_by": authored_by,
        "claim_id": claim_id,
        "data_refs": list(data_refs or []),
        "reviewed_by": reviewed_by,
    }


def evidence_status(
    status: str,
    scope: str,
    inputs: dict[str, Any],
    *,
    gate: str | None = None,
) -> dict[str, Any]:
    require(status in STATUS_ORDER, f"unknown evidence status: {status}")
    label = DISPLAY_LABELS[status]
    return {
        "status": status,
        "badge": f"{label} · {scope}".upper(),
        "reason_code": REASON_CODES[status],
        "inputs": inputs,
        "gate": gate,
    }


def readout(
    observed: dict[str, Any] | str,
    interpretation: dict[str, Any] | str,
    counterevidence: dict[str, Any] | str,
    decision_implication: dict[str, Any] | str,
) -> dict[str, Any]:
    out = {
        "observed": observed,
        "interpretation": interpretation,
        "counterevidence": counterevidence,
        "decision_implication": decision_implication,
    }
    for key, value in out.items():
        text = value["text"] if isinstance(value, dict) else value
        require(len(str(text).strip()) >= 8, f"readout {key} too short")
    return out


def source_foot(basis: str, unit: str, limit: str, status: str) -> dict[str, Any]:
    require(len(basis) >= 8, "source_foot basis too short")
    require(len(unit) >= 3, "source_foot unit too short")
    require(len(limit) >= 8, "source_foot limit too short")
    require(len(status) >= 3, "source_foot status too short")
    return {"basis": basis, "unit": unit, "limit": limit, "status": status}


def gap_block(
    reason: str,
    title: str,
    block_readout: dict[str, Any],
    block_foot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "gap",
        "reason": reason,
        "title": title,
        "readout": block_readout,
        "source_foot": block_foot,
    }


def resolve_pointer(document: Any, pointer: str) -> Any:
    """Resolve a JSON Pointer (RFC 6901) inside a parsed document."""
    if pointer in ("", "/"):
        return document
    require(pointer.startswith("/"), f"pointer must start with /: {pointer}")
    cur = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(token)]
        else:
            cur = cur[token]
    return cur


def parse_source_path(source_path: str) -> tuple[str, str]:
    """Split ``artifact.json#/pointer`` into (artifact, pointer)."""
    if "#" in source_path:
        name, pointer = source_path.split("#", 1)
        return name, pointer
    return source_path, ""


def escape(text: Any) -> str:
    return html.escape(str(text), quote=True)


def dump_json(path: Any, payload: Any) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return data


def dump_jsonl(path: Any, rows: list[dict[str, Any]]) -> bytes:
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    data = text.encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return data

"""报告合同的两个纯渲染器。

一份合同驱动两个视图：

- ``render_report_html``：决策者视图，展示结论切片。
- ``render_sop_html``：执行者视图，展示流程切片。

两个渲染器都只接收合同对象。合同可以是 ``Mapping``，也可以是带
``model_dump()`` 的合同模型。渲染器不读库、不联网、不调用模型、不读时钟。
它也不发起任何文件读写。

所有来自合同的文本都经过 ``html.escape`` 转义。链接只允许 http、https
或相对地址，避免 ``javascript:`` 一类协议注入。

两步哈希协议：

1. 调用 ``render_report_html_unhashed`` 或 ``render_sop_html_unhashed``。
   页脚把占位符写进 ``data-render-hash`` 属性。CSS 用 ``attr()`` 显示。
2. 调用方用产物线的 ``render_sha256`` 计算第一步的渲染哈希，
   再把哈希传给 ``render_report_html`` 或 ``render_sop_html``。

哈希只放在属性里，不放在正文文本里。正文文本不随哈希变化。
产物线的 ``strip_hash_placeholders`` 只还原这个属性。

不能一步到位：页脚要显示最终 HTML 的哈希。哈希写入页脚后字节改变，
新字节的哈希又改变。这个循环没有不动点。所以哈希固定为占位符形态的
sha256。复核时用产物线的 ``strip_hash_placeholders`` 还原同一形态。

验收判据：改一个数字，两页同步变。
两个渲染器共用 ``_build_view`` 与同一组格式化函数，所以同一个数字
不会在两页各自计算。修改合同中的一个 metric，两个 HTML 同时变化。
"""

from __future__ import annotations

import dataclasses
import html
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Final, Protocol
from urllib.parse import urlparse

from data_intelligence_hub.schemas.report_contract import canonical_json_bytes
from data_intelligence_hub.tool_catalog.evidence_grade import GRADE_ORDER, EvidenceGrade

__all__ = [
    "REPORT_HASH_PLACEHOLDER",
    "SOP_HASH_PLACEHOLDER",
    "render_report_html",
    "render_report_html_unhashed",
    "render_sop_html",
    "render_sop_html_unhashed",
]

# 哈希缺失时的文案。不得用另一页的哈希代替。
_UNCOMPUTED: Final[str] = "未计算"
# 两步协议的占位符。产物线的 strip_hash_placeholders 使用同一组字符串。
REPORT_HASH_PLACEHOLDER: Final[str] = "__REPORT_HASH__"
SOP_HASH_PLACEHOLDER: Final[str] = "__SOP_HASH__"

_GRADE_ORDER: Final[dict[str, int]] = {
    grade.value: order for grade, order in GRADE_ORDER.items()
}

_GRADE_LABELS: Final[dict[str, str]] = {
    "L0_unverified": "未验证",
    "L1_contract": "合同已校验",
    "L2_fixture_local": "夹具回放",
    "L3_live_single": "方向性",
    "L4_authorized_live": "已确认",
}

_GRADE_MEANINGS: Final[dict[str, str]] = {
    "L0_unverified": "L0 未实测，只能出现在计划里。",
    "L1_contract": "L1 合同已校验，不能写结论。",
    "L2_fixture_local": "L2 夹具回放，只能写方法验证。",
    "L3_live_single": "L3 单次真实调用，只能写方向性判断。",
    "L4_authorized_live": "L4 授权真实调用且样本达标，可以写确认结论。",
}

_GRADE_CLASSES: Final[dict[str, str]] = {
    "L0_unverified": "state-risk",
    "L1_contract": "state-neutral",
    "L2_fixture_local": "state-neutral",
    "L3_live_single": "state-warn",
    "L4_authorized_live": "state-ok",
}

_CLAIM_STATUS_LABELS: Final[dict[str, str]] = {
    "confirmed": "已确认",
    "directional": "方向性",
    "hypothesis": "假设",
    "evidence_gap": "证据缺口",
    "blocked": "阻断",
}

_CLAIM_STATUS_MEANINGS: Final[dict[str, str]] = {
    "confirmed": "该结论按合同口径已确认。",
    "directional": "该结论只作方向性判断，不得写成发生率。",
    "hypothesis": "该结论是待验证假设，不得当作既成事实。",
    "evidence_gap": "该结论缺少直接证据，不得发布为结论。",
    "blocked": "该结论被门禁阻断，不得发布。",
}

_CLAIM_STATUS_CLASSES: Final[dict[str, str]] = {
    "confirmed": "state-ok",
    "directional": "state-warn",
    "hypothesis": "state-neutral",
    "evidence_gap": "state-warn",
    "blocked": "state-risk",
}

_GATE_STATUS_LABELS: Final[dict[str, str]] = {
    "pending": "待判定",
    "pass": "通过",
    "fail": "失败",
    "blocked": "阻断",
    "expired": "已过期",
}

_GATE_STATUS_CLASSES: Final[dict[str, str]] = {
    "pending": "state-warn",
    "pass": "state-ok",
    "fail": "state-risk",
    "blocked": "state-risk",
    "expired": "state-warn",
}

_COVERAGE_STATUS_LABELS: Final[dict[str, str]] = {
    "success": "有结果",
    "has_result": "有结果",
    "empty": "空结果",
    "failed": "失败",
    "fail": "失败",
    "pending": "未完成",
}

_LEDGER_OUTCOME_LABELS: Final[dict[str, str]] = {
    "success": "成功",
    "empty": "空结果",
    "failed": "失败",
    "config_gated": "配置门控",
}

_ROLE_LABELS: Final[dict[str, str]] = {
    "support": "支持",
    "counter": "反证",
    "context": "背景",
    "gap": "缺口",
}

_ROLE_ORDER: Final[tuple[str, ...]] = ("support", "counter", "context", "gap")


class ContractLike(Protocol):
    """合同对象的最小接口。Pydantic v2 模型满足本协议。"""

    def model_dump(self) -> Mapping[str, Any]:
        """把合同转成字典。本方法必须是纯函数。"""
        ...


ContractInput = Mapping[str, Any] | ContractLike


@dataclass(frozen=True, slots=True)
class _MetricView:
    metric_id: str
    label: str
    numerator: str
    denominator: str
    value_text: str
    count_type: str
    frame: str
    as_of: str
    note: str


@dataclass(frozen=True, slots=True)
class _EvidenceRow:
    evidence_id: str
    claim_id: str
    role: str
    role_label: str
    source_tool_id: str
    url: str | None
    url_text: str
    excerpt: str
    captured_at: str
    market: str
    locale: str
    evidence_grade: str
    evidence_grade_label: str

    @property
    def grade_class(self) -> str:
        return _GRADE_CLASSES.get(self.evidence_grade, "state-neutral")


@dataclass(frozen=True, slots=True)
class _ClaimView:
    claim_id: str
    text: str
    status: str
    status_label: str
    status_class: str
    grade: str
    grade_label: str
    grade_class: str
    grade_meaning: str
    scope_text: str
    counterevidence_text: str
    owner: str
    evidence_ids: str
    role_counts: tuple[tuple[str, int], ...]
    role_total: int
    evidences: tuple[_EvidenceRow, ...]
    sources_text: str
    interpretation: str
    decision_guidance: str


@dataclass(frozen=True, slots=True)
class _GateView:
    gate_id: str
    status: str
    status_label: str
    status_class: str
    owner: str
    decided_at: str
    note: str
    checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CoverageRow:
    index: int
    source_tool_id: str
    market: str
    window: str
    record_count: str
    frame_member_count: str
    status: str
    status_label: str
    status_class: str


@dataclass(frozen=True, slots=True)
class _LedgerRow:
    run_id: str
    tool_id: str
    endpoint_type: str
    actor_id: str
    unit: str
    quantity: str
    unit_price: str
    total_cost_usd: str
    evidence_grade: str
    evidence_grade_label: str
    started_at: str
    finished_at: str
    outcome: str
    outcome_label: str
    outcome_class: str


@dataclass(frozen=True, slots=True)
class _ReportView:
    schema_version: str
    template_id: str
    generated_at: str
    identity_pairs: tuple[tuple[str, str], ...]
    decision_question: str
    answer: str
    protect: tuple[str, ...]
    resolve: tuple[str, ...]
    prove: tuple[str, ...]
    gates: tuple[_GateView, ...]
    gate_status: str
    gate_status_label: str
    gate_status_class: str
    metrics: tuple[_MetricView, ...]
    claims: tuple[_ClaimView, ...]
    evidences: tuple[_EvidenceRow, ...]
    coverage_rows: tuple[_CoverageRow, ...]
    coverage_summary: str
    ledger_rows: tuple[_LedgerRow, ...]
    total_cost_usd: str
    limits: tuple[str, ...]
    unknowns: tuple[str, ...]
    checks: tuple[str, ...]
    lowest_grade: str
    lowest_grade_label: str
    lowest_grade_class: str
    claim_count: int
    contract_sha256: str


def _as_mapping(value: object) -> Mapping[str, Any]:
    """把合同对象转成只读映射。

    依次尝试 ``Mapping``、``model_dump()``、dataclass 与普通对象属性。
    本函数不修改输入，也不发起 I/O。
    """
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump(mode="json")
        except TypeError:
            dumped = dump()
        if isinstance(dumped, Mapping):
            return dumped
        raise TypeError("合同对象的 model_dump() 必须返回 Mapping")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        converted = dataclasses.asdict(value)
        if isinstance(converted, Mapping):
            return converted
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, Mapping):
        return attributes
    slots = getattr(type(value), "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)
    slot_values: dict[str, Any] = {}
    for slot in slots:
        if isinstance(slot, str) and hasattr(value, slot):
            slot_values[slot] = getattr(value, slot)
    if slot_values:
        return slot_values
    raise TypeError("合同必须是 Mapping 或带 model_dump() 的合同对象")


def _mapping(value: object) -> Mapping[str, Any]:
    """把可选对象转成映射。空值与非映射返回空映射。"""
    if value is None:
        return {}
    try:
        return _as_mapping(value)
    except TypeError:
        return {}


def _sequence(value: object) -> tuple[Any, ...]:
    """把可选对象转成元组。字符串按单元素处理。"""
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray)):
        return (value,)
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def _format_number(value: object) -> str:
    """格式化数字。整数值不带小数点。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            return str(value)
        if value == value.to_integral_value():
            return format(value.to_integral_value(), "f")
        return format(value.normalize(), "f")
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(value, ".12g")
    text = _text(value)
    return text


def _text(value: object) -> str:
    """把合同值转成可读文本。调用方负责转义。

    映射走合同模块的规范化入口。本模块不保留第二套 JSON 规则。
    时间不在这里格式化。Pydantic 合同取 ``model_dump(mode="json")``
    后，时间已是字符串。
    """
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, Decimal):
        return _format_number(value)
    if isinstance(value, (int, float)):
        return _format_number(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    if isinstance(value, Mapping):
        return canonical_json_bytes(value).decode("utf-8")
    if isinstance(value, Iterable):
        return "、".join(_text(item) for item in value)
    return str(value)


def _esc(value: object) -> str:
    """转义 HTML 文本。所有合同插值必须经过本函数。"""
    return html.escape(_text(value), quote=True)


def _safe_url(value: object) -> str | None:
    """只允许 http、https 与相对地址。其他协议返回 None。"""
    text = _text(value).strip()
    if not text:
        return None
    if text.startswith("//"):
        return None
    parsed = urlparse(text)
    if parsed.scheme.lower() in {"http", "https"}:
        return text
    if not parsed.scheme:
        return text
    return None


def _decimal(value: object) -> Decimal | None:
    """把可选金额转成 Decimal。无法解析时返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal) -> str:
    """金额保留六位小数。"""
    return format(value.quantize(Decimal("0.000001")), "f")


def _grade_value(value: object) -> str:
    """把等级规范成契约值。未知值原样保留。"""
    text = _text(value).strip()
    if text in _GRADE_ORDER:
        return text
    upper = text.upper()
    for grade in EvidenceGrade:
        if upper == grade.name:
            return grade.value
    return text


def _grade_order(value: str) -> int:
    """返回等级序号。未知等级排在最低。"""
    return _GRADE_ORDER.get(value, -1)


def _grade_label(value: str) -> str:
    return _GRADE_LABELS.get(value, value or "未评级")


def _grade_class(value: str) -> str:
    return _GRADE_CLASSES.get(value, "state-neutral")


def _join_text(value: object, separator: str = "、") -> str:
    items = _sequence(value)
    if not items:
        return ""
    if len(items) == 1:
        return _text(items[0])
    return separator.join(text for item in items if (text := _text(item).strip()))


def _window_text(value: object) -> str:
    """格式化时间窗。支持字符串与 ``{start, end, days}``。"""
    window = _mapping(value)
    if not window:
        return _text(value)
    start = _text(window.get("start")).strip()
    end = _text(window.get("end")).strip()
    days = _text(window.get("days")).strip()
    parts: list[str] = []
    if start or end:
        parts.append(f"{start or '?'} → {end or '?'}")
    if days:
        parts.append(f"{days} 天")
    return " · ".join(parts)


def _scope_text(scope: object) -> str:
    data = _mapping(scope)
    parts: list[str] = []
    market = _join_text(data.get("market"))
    window = _window_text(data.get("window"))
    sample = _text(data.get("sample_n")).strip()
    if market:
        parts.append(f"市场 {market}")
    if window:
        parts.append(f"窗口 {window}")
    if sample:
        parts.append(f"样本 {sample}")
    return " · ".join(parts) if parts else "范围未提供"


def _identity_pairs(identity: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []

    def add(label: str, key: str) -> None:
        text = _text(identity.get(key)).strip()
        if text:
            pairs.append((label, text))

    add("品牌", "brand")
    add("品类", "category")
    markets = _join_text(identity.get("markets"))
    if markets:
        pairs.append(("市场", markets))
    competitors = _join_text(identity.get("competitors"))
    if competitors:
        pairs.append(("竞品", competitors))
    window = _window_text(identity.get("window"))
    if window:
        pairs.append(("时间窗", window))
    add("产品", "product")
    add("型号", "model")
    add("变体", "variant_id")
    add("SKU", "sku")
    add("ASIN", "asin")
    add("父 ASIN", "parent_asin")
    confidence = _text(identity.get("mapping_confidence")).strip()
    if confidence:
        pairs.append(("映射置信度", confidence))
    return tuple(pairs) if pairs else (("身份", "合同未提供身份字段"),)


def _metric_rows(value: object) -> tuple[_MetricView, ...]:
    rows: list[_MetricView] = []
    for index, metric in enumerate(_sequence(value), start=1):
        data = _mapping(metric)
        if not data:
            continue
        metric_id = _text(data.get("metric_id")).strip() or f"metric-{index}"
        label = _text(data.get("label")).strip() or metric_id
        numerator = _format_number(data.get("numerator", data.get("value")))
        denominator = _format_number(data.get("denominator"))
        if numerator and denominator:
            value_text = f"{numerator} / {denominator}"
        else:
            value_text = numerator or denominator or "—"
        rows.append(
            _MetricView(
                metric_id=metric_id,
                label=label,
                numerator=numerator or "—",
                denominator=denominator or "—",
                value_text=value_text,
                count_type=_text(data.get("count_type")).strip() or "未提供",
                frame=_text(data.get("frame")).strip() or "未提供",
                as_of=_text(data.get("as_of")).strip() or "未提供",
                note=_text(data.get("note")).strip(),
            )
        )
    return tuple(rows)


def _build_evidence_row(evidence: Mapping[str, Any]) -> _EvidenceRow:
    grade = _grade_value(evidence.get("evidence_grade"))
    role = _text(evidence.get("role")).strip().lower() or "context"
    return _EvidenceRow(
        evidence_id=_text(evidence.get("evidence_id")).strip(),
        claim_id=_text(evidence.get("claim_id")).strip(),
        role=role,
        role_label=_ROLE_LABELS.get(role, role),
        source_tool_id=_text(evidence.get("source_tool_id")).strip(),
        url=_safe_url(evidence.get("url")),
        url_text=_text(evidence.get("url")).strip(),
        excerpt=_text(evidence.get("excerpt")).strip(),
        captured_at=_text(evidence.get("captured_at")).strip(),
        market=_text(evidence.get("market")).strip(),
        locale=_text(evidence.get("locale")).strip(),
        evidence_grade=grade,
        evidence_grade_label=_grade_label(grade),
    )


def _claim_evidences(
    claim: Mapping[str, Any],
    evidence_by_claim: Mapping[str, tuple[_EvidenceRow, ...]],
    evidence_by_id: Mapping[str, _EvidenceRow],
) -> tuple[_EvidenceRow, ...]:
    claim_id = _text(claim.get("claim_id")).strip()
    collected: list[_EvidenceRow] = list(evidence_by_claim.get(claim_id, ()))
    seen = {(row.evidence_id, row.role, row.excerpt) for row in collected}
    for evidence_id in _sequence(claim.get("evidence_ids")):
        key = _text(evidence_id).strip()
        row = evidence_by_id.get(key)
        if row is None:
            continue
        marker = (row.evidence_id, row.role, row.excerpt)
        if marker not in seen:
            collected.append(row)
            seen.add(marker)
    return tuple(collected)


def _role_counts(evidences: tuple[_EvidenceRow, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for row in evidences:
        counts[row.role] = counts.get(row.role, 0) + 1
    ordered = [(role, counts.pop(role)) for role in _ROLE_ORDER if role in counts]
    ordered.extend(sorted(counts.items()))
    return tuple(ordered)


def _claim_interpretation(status: str, grade: str) -> str:
    status_text = _CLAIM_STATUS_MEANINGS.get(status, "结论状态未定义。")
    grade_text = _GRADE_MEANINGS.get(grade, "证据等级未定义。")
    return f"{status_text}{grade_text}"


def _claim_decision(status: str, grade: str, gate_status: str) -> str:
    if status == "blocked":
        return "保持阻断。关闭阻断原因前不得发布。"
    if status == "evidence_gap" or _grade_order(grade) < _GRADE_ORDER["L4_authorized_live"]:
        return "发布前必须补证到 L4，或把措辞降为方向性。"
    if status == "hypothesis":
        return "先设计可逆实验验证假设，再进入发布流程。"
    if gate_status != "pass":
        return "证据等级满足，但门禁未通过。发布前必须先关闭门禁。"
    return "按当前等级发布，并保留门禁复核记录。"


def _build_claim(
    claim: Mapping[str, Any],
    evidence_by_claim: Mapping[str, tuple[_EvidenceRow, ...]],
    evidence_by_id: Mapping[str, _EvidenceRow],
    gate_status: str,
) -> _ClaimView:
    claim_id = _text(claim.get("claim_id")).strip()
    status = _text(claim.get("claim_status")).strip().lower()
    grade = _grade_value(claim.get("evidence_grade"))
    evidences = _claim_evidences(claim, evidence_by_claim, evidence_by_id)
    counts = _role_counts(evidences)
    sources = sorted({row.source_tool_id for row in evidences if row.source_tool_id})
    evidence_ids = _join_text(claim.get("evidence_ids"))
    return _ClaimView(
        claim_id=claim_id,
        text=_text(claim.get("text")).strip() or "结论文本未提供",
        status=status,
        status_label=_CLAIM_STATUS_LABELS.get(status, status or "未定义"),
        status_class=_CLAIM_STATUS_CLASSES.get(status, "state-neutral"),
        grade=grade,
        grade_label=_grade_label(grade),
        grade_class=_grade_class(grade),
        grade_meaning=_GRADE_MEANINGS.get(grade, "证据等级未定义。"),
        scope_text=_scope_text(claim.get("scope")),
        counterevidence_text=(
            _text(claim.get("counterevidence_text")).strip() or "合同未提供反证字段。"
        ),
        owner=_text(claim.get("owner")).strip() or "未记录",
        evidence_ids=evidence_ids or "未提供",
        role_counts=counts,
        role_total=sum(count for _, count in counts),
        evidences=evidences,
        sources_text="、".join(sources) if sources else "未提供",
        interpretation=_claim_interpretation(status, grade),
        decision_guidance=_claim_decision(status, grade, gate_status),
    )


def _gate_rows(value: object) -> tuple[_GateView, ...]:
    rows: list[_GateView] = []
    for gate in _sequence(value):
        data = _mapping(gate)
        if not data:
            continue
        gate_id = _text(data.get("gate_id")).strip() or "未命名门禁"
        status = _text(data.get("status")).strip().lower()
        status_label = _GATE_STATUS_LABELS.get(status, status or "未记录")
        checks: list[str] = []
        if status == "pass":
            checks.append("本门禁已通过。")
        elif status == "pending":
            checks.append("等待判定人给出结论。")
        elif status == "fail":
            checks.append("本门禁失败。必须修复后重跑。")
        elif status == "blocked":
            checks.append("本门禁阻断。必须补证或降级。")
        else:
            checks.append("门禁状态未记录。")
        note = _text(data.get("note")).strip()
        if note:
            checks.append(note)
        rows.append(
            _GateView(
                gate_id=gate_id,
                status=status,
                status_label=status_label,
                status_class=_GATE_STATUS_CLASSES.get(status, "state-neutral"),
                owner=_text(data.get("owner")).strip() or "未记录",
                decided_at=_text(data.get("decided_at")).strip() or "未记录",
                note=note,
                checks=tuple(checks),
            )
        )
    return tuple(rows)


def _overall_gate_status(data: Mapping[str, Any], gates: tuple[_GateView, ...]) -> str:
    explicit = _text(data.get("gate_status")).strip().lower()
    if explicit:
        return explicit
    statuses = {gate.status for gate in gates if gate.status}
    if not statuses:
        return "unknown"
    for candidate in ("blocked", "fail", "pending", "expired", "pass"):
        if candidate in statuses:
            return candidate
    return "unknown"


def _coverage_status(status: str) -> tuple[str, str]:
    label = _COVERAGE_STATUS_LABELS.get(status, status or "未记录")
    if status in {"failed", "fail"}:
        return label, "state-risk"
    if status in {"empty", "pending"}:
        return label, "state-warn"
    if status in {"success", "has_result"}:
        return label, "state-ok"
    return label, "state-neutral"


def _coverage_rows(value: object) -> tuple[_CoverageRow, ...]:
    """读取合同 ``coverage.cells``。

    契约冻结把 coverage 定义成 ``{"cells": [...]}`` 对象。
    渲染器以这一种形状为准。列表输入按旧调用兼容处理。
    """
    data = _mapping(value)
    raw_cells: object = data.get("cells") if data else value
    rows: list[_CoverageRow] = []
    for index, cell in enumerate(_sequence(raw_cells), start=1):
        item = _mapping(cell)
        if not item:
            continue
        status = _text(item.get("status")).strip().lower()
        status_label, status_class = _coverage_status(status)
        rows.append(
            _CoverageRow(
                index=index,
                source_tool_id=(
                    _text(item.get("source_tool_id")).strip()
                    or _text(item.get("tool_id")).strip()
                    or _text(item.get("source")).strip()
                    or "未提供"
                ),
                market=_text(item.get("market")).strip() or "—",
                window=_window_text(item.get("window")) or "—",
                record_count=_format_number(
                    item.get("record_count", item.get("records_count", item.get("count")))
                )
                or "—",
                frame_member_count=_format_number(
                    item.get("frame_member_count", item.get("frame_members"))
                )
                or "—",
                status=status,
                status_label=status_label,
                status_class=status_class,
            )
        )
    return tuple(rows)


def _coverage_summary(rows: tuple[_CoverageRow, ...]) -> str:
    if not rows:
        return "合同未提供覆盖单元。"
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status_label] = counts.get(row.status_label, 0) + 1
    parts = [f"{label} {count}" for label, count in sorted(counts.items())]
    return f"{len(rows)} 个覆盖单元。" + "；".join(parts) + "。"


def _ledger_rows(value: object) -> tuple[tuple[_LedgerRow, ...], str]:
    rows: list[_LedgerRow] = []
    total = Decimal(0)
    for entry in _sequence(value):
        data = _mapping(entry)
        if not data:
            continue
        grade = _grade_value(data.get("evidence_grade"))
        outcome = _text(data.get("outcome")).strip().lower()
        amount = _decimal(data.get("total_cost_usd"))
        if amount is None:
            amount = _decimal(data.get("amount_usd"))
        if amount is None:
            amount = _decimal(data.get("cost_usd"))
        if amount is not None:
            total += amount
        if outcome in {"failed"}:
            outcome_class = "state-risk"
        elif outcome in {"empty", "config_gated"}:
            outcome_class = "state-warn"
        elif outcome in {"success"}:
            outcome_class = "state-ok"
        else:
            outcome_class = "state-neutral"
        rows.append(
            _LedgerRow(
                run_id=_text(data.get("run_id")).strip() or "—",
                tool_id=_text(data.get("tool_id")).strip() or "—",
                endpoint_type=_text(data.get("endpoint_type")).strip() or "—",
                actor_id=_text(data.get("actor_id")).strip() or "—",
                unit=_text(data.get("unit")).strip() or "—",
                quantity=_format_number(data.get("quantity")) or "—",
                unit_price=_format_number(data.get("unit_price")) or "—",
                total_cost_usd=_money(amount) if amount is not None else "—",
                evidence_grade=grade,
                evidence_grade_label=_grade_label(grade),
                started_at=_text(data.get("started_at")).strip() or "—",
                finished_at=_text(data.get("finished_at")).strip() or "—",
                outcome=outcome,
                outcome_label=_LEDGER_OUTCOME_LABELS.get(outcome, outcome or "未记录"),
                outcome_class=outcome_class,
            )
        )
    return tuple(rows), _money(total)


def _build_checks(
    claims: tuple[_ClaimView, ...],
    coverage_rows: tuple[_CoverageRow, ...],
    gate_status: str,
    limits: tuple[str, ...],
    unknowns: tuple[str, ...],
) -> tuple[str, ...]:
    checks: list[str] = [f"门禁状态是 {gate_status}。"]
    for claim in claims:
        if _grade_order(claim.grade) < _GRADE_ORDER["L4_authorized_live"]:
            checks.append(
                f"Claim {claim.claim_id or '未命名'} 的证据等级是 "
                f"{claim.grade or '未评级'}，不得使用确认类措辞。"
            )
        if claim.status in {"evidence_gap", "blocked"}:
            checks.append(
                f"Claim {claim.claim_id or '未命名'} 的状态是 {claim.status_label}，"
                "必须补证或关闭阻断。"
            )
    for row in coverage_rows:
        if row.status in {"failed", "fail", "empty"}:
            checks.append(
                f"覆盖单元 {row.source_tool_id} 的状态是 {row.status_label}，必须复核。"
            )
    if unknowns:
        checks.append(f"合同列出 {len(unknowns)} 项未知数据。")
    if limits:
        checks.append(f"合同列出 {len(limits)} 项推断边界。")
    return tuple(checks)


def _lowest_grade(
    claims: tuple[_ClaimView, ...],
    evidences: tuple[_EvidenceRow, ...],
    ledger_rows: tuple[_LedgerRow, ...],
) -> str:
    """取整份合同的最低证据等级。

    报告可能引用多次 run。任一 run 的等级都要参与比较。
    三个来源合并后取最小值。未知等级按最低处理。
    """
    grades = [claim.grade for claim in claims if claim.grade]
    grades.extend(row.evidence_grade for row in evidences if row.evidence_grade)
    grades.extend(row.evidence_grade for row in ledger_rows if row.evidence_grade)
    if not grades:
        return ""
    return min(grades, key=_grade_order)


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value).strip()
        if text:
            return text
    return ""


def _build_view(contract: ContractInput) -> _ReportView:
    """从合同构建两个视图共用的数据。

    本函数只读取合同对象。它不读库、不联网、不读时钟。
    """
    data = _as_mapping(contract)
    identity = _mapping(data.get("identity"))
    decision = _mapping(data.get("decision"))
    gates = _gate_rows(data.get("gates"))
    gate_status = _overall_gate_status(data, gates)
    evidences = tuple(
        _build_evidence_row(evidence)
        for evidence in (_mapping(item) for item in _sequence(data.get("evidences")))
        if evidence
    )
    evidence_by_claim: dict[str, list[_EvidenceRow]] = {}
    evidence_by_id: dict[str, _EvidenceRow] = {}
    for row in evidences:
        if row.claim_id:
            evidence_by_claim.setdefault(row.claim_id, []).append(row)
        if row.evidence_id:
            evidence_by_id[row.evidence_id] = row
    claims = tuple(
        _build_claim(
            claim,
            {key: tuple(value) for key, value in evidence_by_claim.items()},
            evidence_by_id,
            gate_status,
        )
        for claim in (_mapping(item) for item in _sequence(data.get("claims")))
        if claim
    )
    coverage_rows = _coverage_rows(data.get("coverage"))
    ledger_rows, total_cost = _ledger_rows(data.get("run_ledger"))
    limits = tuple(
        text for item in _sequence(data.get("limits")) if (text := _text(item).strip())
    )
    unknowns = tuple(
        text for item in _sequence(data.get("unknowns")) if (text := _text(item).strip())
    )
    lowest = _lowest_grade(claims, evidences, ledger_rows)
    artifact = _mapping(data.get("artifact"))
    return _ReportView(
        schema_version=_text(data.get("schema_version")).strip() or "未提供",
        template_id=_text(data.get("template_id")).strip() or "未提供",
        generated_at=_text(data.get("generated_at")).strip() or "时间未提供",
        identity_pairs=_identity_pairs(identity),
        decision_question=_text(decision.get("decision_question")).strip(),
        answer=_text(decision.get("answer")).strip(),
        protect=tuple(
            text
            for item in _sequence(decision.get("protect"))
            if (text := _text(item).strip())
        ),
        resolve=tuple(
            text
            for item in _sequence(decision.get("resolve"))
            if (text := _text(item).strip())
        ),
        prove=tuple(
            text for item in _sequence(decision.get("prove")) if (text := _text(item).strip())
        ),
        gates=gates,
        gate_status=gate_status,
        gate_status_label=_GATE_STATUS_LABELS.get(gate_status, gate_status or "未记录"),
        gate_status_class=_GATE_STATUS_CLASSES.get(gate_status, "state-neutral"),
        metrics=_metric_rows(data.get("metrics")),
        claims=claims,
        evidences=evidences,
        coverage_rows=coverage_rows,
        coverage_summary=_coverage_summary(coverage_rows),
        ledger_rows=ledger_rows,
        total_cost_usd=total_cost,
        limits=limits,
        unknowns=unknowns,
        checks=_build_checks(claims, coverage_rows, gate_status, limits, unknowns),
        lowest_grade=lowest,
        lowest_grade_label=_grade_label(lowest),
        lowest_grade_class=_grade_class(lowest),
        claim_count=len(claims),
        contract_sha256=_first_text(
            artifact.get("contract_sha256"), data.get("contract_sha256")
        ),
    )


def _hash_text(value: str) -> str:
    """返回哈希文本。空值显示「未计算」。不做跨页回退。"""
    text = value.strip()
    return text or _UNCOMPUTED


def _fill_hash_placeholders(
    document: str,
    *,
    report_hash: str,
    sop_hash: str,
) -> str:
    """替换两步协议的两个占位符。哈希文本先转义。"""
    filled = document.replace(
        REPORT_HASH_PLACEHOLDER,
        _esc(_hash_text(report_hash)),
    )
    return filled.replace(
        SOP_HASH_PLACEHOLDER,
        _esc(_hash_text(sop_hash)),
    )


def _badge(label: str, css_class: str, raw: str = "") -> str:
    raw_text = f" · {_esc(raw)}" if raw else ""
    return f'<span class="badge {css_class}">{_esc(label)}{raw_text}</span>'


def _grade_badge(grade: str, label: str, css_class: str) -> str:
    if not grade:
        return '<span class="badge state-neutral">未评级</span>'
    return _badge(label, css_class, grade)


def _render_truth_ribbon(view: _ReportView) -> str:
    return f"""
      <div class="truth-ribbon" id="evidence-status" aria-label="报告证据状态">
        <div class="truth-item">
          <span>最低证据等级</span>
          <b class="{view.lowest_grade_class}">{_esc(view.lowest_grade_label)}</b>
          <code>{_esc(view.lowest_grade or "未评级")}</code>
        </div>
        <div class="truth-item">
          <span>门禁状态</span>
          <b class="{view.gate_status_class}">{_esc(view.gate_status_label)}</b>
          <code>{_esc(view.gate_status)}</code>
        </div>
        <div class="truth-item"><span>Claim 数</span><b>{view.claim_count}</b></div>
        <div class="truth-item"><span>模板</span><b>{_esc(view.template_id)}</b></div>
        <div class="truth-item"><span>合同版本</span><b>{_esc(view.schema_version)}</b></div>
      </div>
    """


def _render_compass(view: _ReportView) -> str:
    slots = (
        ("Protect", "要守住的资产", view.protect),
        ("Resolve", "要解决的矛盾", view.resolve),
        ("Prove", "要验证的假设", view.prove),
    )
    items: list[str] = []
    for name, subtitle, values in slots:
        if values:
            body = "".join(f"<li>{_esc(value)}</li>" for value in values)
            body = f"<ul>{body}</ul>"
        else:
            body = '<p class="empty">空。</p>'
        items.append(
            f'<div class="compass-item"><b>{name} · {subtitle}</b>{body}</div>'
        )
    return f'<div class="decision-compass" aria-label="决策指南">{"".join(items)}</div>'


def _render_metric_cards(metrics: tuple[_MetricView, ...]) -> str:
    if not metrics:
        return ""
    cards: list[str] = []
    for metric in metrics[:4]:
        cards.append(
            '<article class="proof-card">'
            f'<div class="value">{_esc(metric.value_text)}</div>'
            f'<div class="label">{_esc(metric.label)}</div>'
            f'<div class="note">{_esc(metric.count_type)} · {_esc(metric.frame)}</div>'
            "</article>"
        )
    return f'<div class="proof-grid">{"".join(cards)}</div>'


def _render_metrics_table(metrics: tuple[_MetricView, ...]) -> str:
    """两个视图共用的指标表。同一数字只在这里格式化一次。"""
    if not metrics:
        return '<p class="empty">合同未提供 metrics。</p>'
    rows = "".join(
        "<tr>"
        f"<td><code>{_esc(metric.metric_id)}</code></td>"
        f"<td>{_esc(metric.label)}</td>"
        f"<td class=\"num\">{_esc(metric.numerator)}</td>"
        f"<td class=\"num\">{_esc(metric.denominator)}</td>"
        f"<td>{_esc(metric.count_type)}</td>"
        f"<td>{_esc(metric.frame)}</td>"
        f"<td>{_esc(metric.as_of)}</td>"
        f"<td>{_esc(metric.note) or '—'}</td>"
        "</tr>"
        for metric in metrics
    )
    return f"""
      <div class="table-wrap"><table>
        <thead><tr>
          <th>Metric</th><th>标签</th><th>分子</th><th>分母</th>
          <th>计数口径</th><th>Frame</th><th>数据日期</th><th>限制</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table></div>
    """


def _render_identity(pairs: tuple[tuple[str, str], ...]) -> str:
    rows = "".join(
        f"<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>" for label, value in pairs
    )
    return f'<dl class="identity-grid">{rows}</dl>'


def _render_role_chart(claim: _ClaimView) -> str:
    if claim.role_total == 0:
        return '<p class="empty">合同未关联证据记录。</p>'
    bars: list[str] = []
    for role, count in claim.role_counts:
        percent = count / claim.role_total * 100
        bars.append(
            f'<span class="role-bar role-{_esc(role)}" style="width:{percent:.1f}%">'
            f"{_esc(_ROLE_LABELS.get(role, role))} {count}</span>"
        )
    legend = "".join(
        f"<li><b>{_esc(_ROLE_LABELS.get(role, role))}</b> {count}</li>"
        for role, count in claim.role_counts
    )
    return (
        f'<div class="role-track" aria-label="证据角色分布">{"".join(bars)}</div>'
        f'<ul class="role-legend">{legend}</ul>'
    )


def _render_voice(claim: _ClaimView) -> str:
    if not claim.evidences:
        return '<p class="empty">未提供证据摘录。</p>'
    voices: list[str] = []
    for evidence in claim.evidences:
        excerpt = evidence.excerpt or "未提供摘录。"
        if evidence.url:
            link = (
                f'<a href="{_esc(evidence.url)}" rel="noreferrer noopener" '
                f'target="_blank">{_esc(evidence.url_text or evidence.evidence_id)}</a>'
            )
        else:
            link = _esc(evidence.url_text or "未提供链接")
        voices.append(
            '<div class="voice-item">'
            f"<p>{_esc(excerpt)}</p>"
            f"<small>{_esc(evidence.role_label)} · {_esc(evidence.source_tool_id or '来源未提供')}"
            f" · {_esc(evidence.captured_at or '时间未提供')} · {link}</small>"
            "</div>"
        )
    return f'<div class="voice-list">{"".join(voices)}</div>'


def _render_claim_exhibit(claim: _ClaimView, index: int) -> str:
    return f"""
      <figure class="exhibit" id="claim-{index:02d}">
        <figcaption class="exhibit-head">
          <div>
            <div class="exhibit-number">EXHIBIT {index:02d}</div>
            <h3 class="exhibit-title">{_esc(claim.text)}</h3>
          </div>
          <div class="exhibit-scope">
            {_esc(claim.scope_text)}
            {_grade_badge(claim.grade, claim.grade_label, claim.grade_class)}
            {_badge(claim.status_label, claim.status_class, claim.status)}
          </div>
        </figcaption>
        <div class="exhibit-body">
          <div class="chart-box">
            <div class="chart-title">证据角色分布</div>
            {_render_role_chart(claim)}
          </div>
        </div>
        <div class="exhibit-readout">
          <div class="readout-item"><b>Interpretation</b><p>{_esc(claim.interpretation)}</p></div>
          <div class="readout-item"><b>Counterevidence</b>
            <p>{_esc(claim.counterevidence_text)}</p></div>
          <div class="readout-item"><b>Decision</b><p>{_esc(claim.decision_guidance)}</p></div>
        </div>
        <div class="voice-texture">
          <div class="voice-title">声音</div>
          {_render_voice(claim)}
        </div>
        <div class="source-foot">
          <span><b>Claim</b> {_esc(claim.claim_id or "未提供")}</span>
          <span><b>Evidence</b> {claim.role_total}</span>
          <span><b>Sources</b> {_esc(claim.sources_text)}</span>
          <span><b>Owner</b> {_esc(claim.owner)}</span>
          <span><b>Evidence IDs</b> {_esc(claim.evidence_ids)}</span>
        </div>
      </figure>
    """


def _render_evidence_index(evidences: tuple[_EvidenceRow, ...]) -> str:
    if not evidences:
        return '<p class="empty">合同未提供 evidences。</p>'
    rows: list[str] = []
    for evidence in evidences:
        if evidence.url:
            link = (
                f'<a href="{_esc(evidence.url)}" rel="noreferrer noopener" '
                f'target="_blank">{_esc(evidence.url_text or evidence.evidence_id)}</a>'
            )
        else:
            link = _esc(evidence.url_text or "—")
        rows.append(
            "<tr>"
            f"<td><code>{_esc(evidence.evidence_id or '—')}</code></td>"
            f"<td><code>{_esc(evidence.claim_id or '—')}</code></td>"
            f"<td>{_esc(evidence.role_label)}</td>"
            f"<td>{_esc(evidence.source_tool_id or '—')}</td>"
            f"<td>{_esc(evidence.excerpt or '—')}</td>"
            f"<td>{_esc(evidence.captured_at or '—')}</td>"
            f"<td>{link}</td>"
            "</tr>"
        )
    return f"""
      <div class="table-wrap"><table>
        <thead><tr>
          <th>Evidence</th><th>Claim</th><th>角色</th><th>来源</th>
          <th>摘录</th><th>采集时间</th><th>原文</th>
        </tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table></div>
    """


def _render_gate_list(gates: tuple[_GateView, ...], include_checks: bool) -> str:
    if not gates:
        return '<p class="empty">合同未提供 gates。</p>'
    cards: list[str] = []
    for index, gate in enumerate(gates, start=1):
        checks = ""
        if include_checks:
            items = "".join(f"<li>{_esc(item)}</li>" for item in gate.checks)
            checks = f'<ul class="checklist">{items}</ul>'
        cards.append(
            '<article class="gate">'
            "<header>"
            f'<div><span class="gate-index">STEP {index:02d}</span>'
            f"<h3>{_esc(gate.gate_id)}</h3></div>"
            f"{_badge(gate.status_label, gate.status_class, gate.status)}"
            "</header>"
            f"<dl><div><dt>判定人</dt><dd>{_esc(gate.owner)}</dd></div>"
            f"<div><dt>判定时间</dt><dd>{_esc(gate.decided_at)}</dd></div></dl>"
            f"{checks}"
            "</article>"
        )
    return f'<div class="gate-list">{"".join(cards)}</div>'


def _render_coverage_table(rows: tuple[_CoverageRow, ...]) -> str:
    if not rows:
        return '<p class="empty">合同未提供 coverage。</p>'
    body = "".join(
        "<tr>"
        f"<td class=\"num\">{row.index}</td>"
        f"<td>{_esc(row.source_tool_id)}</td>"
        f"<td>{_esc(row.market)}</td>"
        f"<td>{_esc(row.window)}</td>"
        f"<td class=\"num\">{_esc(row.record_count)}</td>"
        f"<td class=\"num\">{_esc(row.frame_member_count)}</td>"
        f"<td>{_badge(row.status_label, row.status_class, row.status)}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
      <div class="table-wrap"><table>
        <thead><tr>
          <th>#</th><th>source_tool_id</th><th>市场</th><th>时间窗</th>
          <th>record_count</th><th>frame_member_count</th><th>状态</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
    """


def _ledger_grade_badge(row: _LedgerRow) -> str:
    """账本行的证据等级徽章。"""
    return _grade_badge(
        row.evidence_grade,
        row.evidence_grade_label,
        _grade_class(row.evidence_grade),
    )


def _render_ledger_table(rows: tuple[_LedgerRow, ...], total: str) -> str:
    if not rows:
        return '<p class="empty">合同未提供 run_ledger。</p>'
    body = "".join(
        "<tr>"
        f"<td><code>{_esc(row.run_id)}</code></td>"
        f"<td>{_esc(row.tool_id)}</td>"
        f"<td>{_esc(row.endpoint_type)}</td>"
        f"<td>{_esc(row.actor_id)}</td>"
        f"<td>{_esc(row.unit)}</td>"
        f"<td class=\"num\">{_esc(row.quantity)}</td>"
        f"<td class=\"num\">{_esc(row.unit_price)}</td>"
        f"<td class=\"num\">{_esc(row.total_cost_usd)}</td>"
        f"<td>{_ledger_grade_badge(row)}</td>"
        f"<td>{_esc(row.started_at)}</td>"
        f"<td>{_esc(row.finished_at)}</td>"
        f"<td>{_badge(row.outcome_label, row.outcome_class, row.outcome)}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
      <div class="table-wrap"><table>
        <thead><tr>
          <th>run_id</th><th>tool_id</th><th>endpoint_type</th><th>actor_id</th>
          <th>单位</th><th>数量</th><th>单价</th><th>成本 USD</th>
          <th>证据等级</th><th>开始</th><th>结束</th><th>结果</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table></div>
      <p class="total-cost">成本合计 <b>USD {_esc(total)}</b></p>
    """


def _render_limits(limits: tuple[str, ...], unknowns: tuple[str, ...]) -> str:
    def render_list(title: str, values: tuple[str, ...], empty: str) -> str:
        if values:
            items = "".join(f"<li>{_esc(value)}</li>" for value in values)
            body = f"<ul>{items}</ul>"
        else:
            body = f'<p class="empty">{_esc(empty)}</p>'
        return f'<article class="panel"><h3>{title}</h3>{body}</article>'

    return (
        '<div class="grid-2">'
        + render_list("Limits · 本次不能推断什么", limits, "合同未提供 limits。")
        + render_list("Unknowns · 本次缺什么数据", unknowns, "合同未提供 unknowns。")
        + "</div>"
    )


def _publish_check(claim: _ClaimView) -> str:
    """按证据等级给出发布检查结论。"""
    if _grade_order(claim.grade) < _GRADE_ORDER["L4_authorized_live"]:
        return '<span class="state-risk">需补证</span>'
    return '<span class="state-ok">可发布</span>'


def _render_claim_checklist(claims: tuple[_ClaimView, ...]) -> str:
    if not claims:
        return '<p class="empty">合同未提供 claims。</p>'
    rows = "".join(
        "<tr>"
        f"<td><code>{_esc(claim.claim_id or '—')}</code></td>"
        f"<td>{_esc(claim.text)}</td>"
        f"<td>{_badge(claim.status_label, claim.status_class, claim.status)}</td>"
        f"<td>{_grade_badge(claim.grade, claim.grade_label, claim.grade_class)}</td>"
        f"<td class=\"num\">{claim.role_total}</td>"
        f"<td>{_esc(claim.owner)}</td>"
        "<td>"
        f"<td>{_publish_check(claim)}</td>"
        "</td>"
        "</tr>"
        for claim in claims
    )
    return f"""
      <div class="table-wrap"><table>
        <thead><tr>
          <th>Claim</th><th>结论</th><th>状态</th><th>证据等级</th>
          <th>证据数</th><th>Owner</th><th>发布检查</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table></div>
    """


def _render_footer(
    view: _ReportView,
    contract_hash: str,
    data_hash: str,
    page_hash_placeholder: str,
) -> str:
    """两个视图共用的页脚。

    存档哈希写占位符。两步协议在第二步替换它们。
    合同哈希与数据哈希在第一步前已知，直接写入。
    """
    return f"""
  <footer class="page-footer">
    <div class="shell">
      <div class="footer-meta">
        <b>Data Intelligence Hub · 报告合同</b>
        <span>模板 {_esc(view.template_id)} · 合同 {_esc(view.schema_version)}</span>
        <span>生成时间 {_esc(view.generated_at)}</span>
      </div>
      <dl class="hash-grid">
        <div><dt>合同哈希</dt><dd><code>{_esc(_hash_text(contract_hash))}</code></dd></div>
        <div><dt>数据哈希</dt><dd><code>{_esc(_hash_text(data_hash))}</code></dd></div>
        <div><dt>渲染哈希</dt>
          <dd><code class="render-hash"
            data-render-hash="{page_hash_placeholder}"></code></dd></div>
      </dl>
      <p class="hash-archive">存档哈希：报告 HTML
        <code class="render-hash" data-render-hash="{REPORT_HASH_PLACEHOLDER}"></code>
        · SOP HTML
        <code class="render-hash" data-render-hash="{SOP_HASH_PLACEHOLDER}"></code></p>
    </div>
  </footer>
"""


_BASE_CSS: Final[str] = """
:root{
  --bg:#f6f6f2;--surface:#ffffff;--ink:#1b2420;--muted:#5d6a64;
  --line:#d8ded9;--line-strong:#bcc7c0;--brand:#0f6b57;--brand-soft:#e2f0eb;
  --ok:#1f6b3a;--ok-soft:#e4f2e8;--warn:#8a5a00;--warn-soft:#fff2d8;
  --risk:#9b2c2c;--risk-soft:#fbe7e5;--neutral-soft:#edf0ee;--radius:14px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;
  background:var(--neutral-soft);padding:2px 5px;border-radius:5px;word-break:break-all}
.shell{max-width:1160px;margin:0 auto;padding:0 28px}
.skip{position:absolute;left:-9999px}
.skip:focus{left:12px;top:12px;background:#fff;padding:8px 12px;z-index:9}
.topbar{border-bottom:1px solid var(--line);background:rgba(255,255,255,.86);
  position:sticky;top:0;z-index:5;backdrop-filter:blur(8px)}
.topbar .shell{display:flex;align-items:center;gap:18px;min-height:58px}
.brand{font-weight:800;letter-spacing:-.02em;color:var(--ink)}
.micro{color:var(--muted);font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.topbar nav{margin-left:auto;display:flex;gap:16px;font-size:13px}
.hero{padding:58px 0 34px}
.eyebrow{color:var(--brand);font-size:12px;font-weight:800;letter-spacing:.12em;
  text-transform:uppercase}
h1{font-size:44px;line-height:1.16;letter-spacing:-.03em;margin:14px 0 14px;max-width:960px}
h2{font-size:30px;line-height:1.25;letter-spacing:-.02em;margin:0}
h3{font-size:19px;line-height:1.35;margin:0}
.hero-lead{font-size:18px;color:var(--muted);max-width:900px;margin:0 0 26px}
.truth-ribbon{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;
  margin:22px 0 24px;padding:14px;border:1px solid var(--line);border-radius:var(--radius);
  background:var(--surface)}
.truth-item{display:flex;flex-direction:column;gap:3px;padding:6px 10px;
  border-left:1px solid var(--line)}
.truth-item:first-child{border-left:0}
.truth-item span{font-size:11px;color:var(--muted);letter-spacing:.08em}
.truth-item b{font-size:17px}
.truth-item code{background:none;padding:0;color:var(--muted)}
.decision-compass{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;
  margin:22px 0}
.compass-item{border:1px solid var(--line);border-radius:var(--radius);
  background:var(--surface);padding:18px}
.compass-item>b{display:block;font-size:12px;letter-spacing:.1em;color:var(--brand);
  text-transform:uppercase;margin-bottom:8px}
.compass-item ul{margin:0;padding-left:18px}
.compass-item li{margin:4px 0}
.proof-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:18px}
.proof-card{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);
  padding:16px}
.proof-card .value{font-size:28px;font-weight:800;letter-spacing:-.03em}
.proof-card .label{font-weight:700;margin-top:4px}
.proof-card .note{font-size:12px;color:var(--muted);margin-top:4px}
section{padding:44px 0;border-top:1px solid var(--line)}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:28px;
  margin-bottom:22px}
.section-head p{max-width:520px;color:var(--muted);margin:0;font-size:14px}
.section-index{font-size:11px;letter-spacing:.14em;color:var(--brand);font-weight:800;
  text-transform:uppercase;margin-bottom:8px}
.exhibit{border:1px solid var(--line);border-radius:18px;background:var(--surface);
  margin:0 0 22px;overflow:hidden}
.exhibit-head{display:flex;justify-content:space-between;gap:24px;padding:22px 24px;
  border-bottom:1px solid var(--line)}
.exhibit-number{font-size:11px;letter-spacing:.14em;color:var(--brand);font-weight:800;
  margin-bottom:7px}
.exhibit-title{max-width:760px}
.exhibit-scope{font-size:12px;color:var(--muted);text-align:right;max-width:320px;
  display:flex;flex-direction:column;align-items:flex-end;gap:7px}
.exhibit-body{padding:22px 24px;background:var(--bg)}
.chart-title{font-size:12px;color:var(--muted);margin-bottom:10px}
.role-track{display:flex;min-height:34px;border-radius:9px;overflow:hidden;
  background:var(--neutral-soft);border:1px solid var(--line)}
.role-bar{display:flex;align-items:center;justify-content:center;font-size:11px;
  font-weight:700;color:#fff;padding:0 6px;white-space:nowrap;overflow:hidden}
.role-support{background:var(--brand)}
.role-counter{background:var(--risk)}
.role-context{background:#6b7780}
.role-gap{background:var(--warn)}
.role-legend{display:flex;flex-wrap:wrap;gap:14px;list-style:none;margin:10px 0 0;padding:0;
  font-size:12px;color:var(--muted)}
.role-legend b{color:var(--ink)}
.exhibit-readout{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;
  border-top:1px solid var(--line)}
.readout-item{padding:18px 24px;border-left:1px solid var(--line)}
.readout-item:first-child{border-left:0}
.readout-item b{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--brand)}
.readout-item p{margin:6px 0 0;font-size:14px}
.voice-texture{border-top:1px solid var(--line);padding:18px 24px}
.voice-title{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--brand);
  font-weight:800;margin-bottom:10px}
.voice-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.voice-item{border:1px solid var(--line);border-radius:10px;padding:12px;background:var(--bg)}
.voice-item p{margin:0 0 6px;font-size:14px}
.voice-item small{color:var(--muted);font-size:11px}
.source-foot{display:flex;flex-wrap:wrap;gap:16px;padding:13px 24px;
  border-top:1px solid var(--line);background:var(--brand-soft);font-size:11px;
  color:var(--muted)}
.source-foot b{color:var(--ink)}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;font-size:11px;
  font-weight:800;white-space:nowrap}
.state-ok{background:var(--ok-soft);color:var(--ok)}
.state-warn{background:var(--warn-soft);color:var(--warn)}
.state-risk{background:var(--risk-soft);color:var(--risk)}
.state-neutral{background:var(--neutral-soft);color:var(--muted)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;
  background:var(--surface)}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:680px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--neutral-soft);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted)}
tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.identity-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden;
  margin:0}
.identity-grid div{background:var(--surface);padding:14px 16px}
.identity-grid dt{font-size:11px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase}
.identity-grid dd{margin:3px 0 0;font-weight:700}
.gate-list{display:grid;gap:10px}
.gate{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:16px 18px}
.gate header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.gate-index{font-size:10px;letter-spacing:.12em;color:var(--brand);font-weight:800}
.gate h3{margin-top:2px}
.gate dl{display:flex;gap:24px;margin:10px 0 0;font-size:12px}
.gate dt{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em}
.gate dd{margin:2px 0 0}
.checklist{margin:10px 0 0;padding-left:18px;font-size:13px}
.panel{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:18px}
.panel h3{margin-bottom:10px}
.panel ul{margin:0;padding-left:18px}
.grid-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.grid-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.empty{color:var(--muted);font-style:italic}
.total-cost{font-size:16px;margin:12px 0 0}
.status-line{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
  border-radius:999px;padding:7px 12px;background:var(--surface);font-size:12px;font-weight:700}
.page-footer{border-top:1px solid var(--line);background:var(--surface);padding:30px 0}
.footer-meta{display:flex;flex-wrap:wrap;gap:16px;align-items:baseline;font-size:12px;
  color:var(--muted);margin-bottom:16px}
.footer-meta b{color:var(--ink);font-size:14px}
.hash-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0}
.hash-grid div{border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.hash-grid dt{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.hash-grid dd{margin:4px 0 0}
.render-hash::before{content:attr(data-render-hash)}
.hash-archive{margin:10px 0 0;font-size:11px;color:var(--muted)}
@media(max-width:900px){
  h1{font-size:34px}
  .truth-ribbon{grid-template-columns:repeat(2,minmax(0,1fr))}
  .truth-item{border-left:0}
  .decision-compass,.proof-grid,.exhibit-readout,.voice-list,.identity-grid,.grid-2,.grid-3,
  .hash-grid{grid-template-columns:1fr}
  .readout-item{border-left:0;border-top:1px solid var(--line)}
  .section-head,.exhibit-head{flex-direction:column;align-items:flex-start}
  .exhibit-scope{align-items:flex-start;text-align:left}
}
@media print{
  .topbar{display:none}
  section{padding:24px 0}
  .exhibit{break-inside:avoid}
  body{background:#fff}
}
"""


def _page_shell(title: str, css_class: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{_esc(title)}</title>
  <style>{_BASE_CSS}</style>
</head>
<body class="{css_class}">
{body}
</body>
</html>
"""


def _render_report_page(contract: ContractInput, *, data_hash: str) -> str:
    """生成决策者视图的未哈希 HTML。页脚保留两个占位符。"""
    view = _build_view(contract)
    lead = ""
    if view.answer and view.decision_question and view.answer != view.decision_question:
        lead = view.decision_question
    elif not view.answer and view.decision_question:
        lead = "合同未提供结论句。"
    claims_html = "".join(
        _render_claim_exhibit(claim, index)
        for index, claim in enumerate(view.claims, start=1)
    )
    if not claims_html:
        claims_html = '<p class="empty">合同未提供 claims。</p>'
    body = f"""
  <a class="skip" href="#main">跳到主要内容</a>
  <header class="topbar">
    <div class="shell">
      <span class="brand">DIH 报告合同</span>
      <span class="micro">决策者视图 · report.html</span>
      <nav aria-label="报告导航">
        <a href="#identity">范围</a><a href="#metrics">指标</a>
        <a href="#claims">结论</a><a href="#gates">门禁</a><a href="#limits">边界</a>
      </nav>
    </div>
  </header>
  <main id="main">
    <section class="hero" id="top">
      <div class="shell">
        <div class="eyebrow">决策者视图 · {_esc(view.generated_at)}</div>
        <h1>{_esc(view.answer or view.decision_question or "报告结论未提供")}</h1>
        {f'<p class="hero-lead">{_esc(lead)}</p>' if lead else ''}
        {_render_truth_ribbon(view)}
        {_render_compass(view)}
        {_render_metric_cards(view.metrics)}
      </div>
    </section>
    <section id="identity">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">00 / SCOPE</div><h2>报告范围与身份</h2></div>
          <p>身份字段来自合同。渲染器不补充任何外部事实。</p>
        </div>
        {_render_identity(view.identity_pairs)}
      </div>
    </section>
    <section id="metrics">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">01 / METRICS</div><h2>共享指标</h2></div>
          <p>每个数字只在这里格式化一次。决策者视图与执行者视图读同一份合同。</p>
        </div>
        {_render_metrics_table(view.metrics)}
      </div>
    </section>
    <section id="claims">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">02 / CLAIMS</div><h2>结论与证据</h2></div>
          <p>每个 claim 是一段六段式展品：结论、范围与徽章、图表、三段导读、声音、来源脚注。</p>
        </div>
        {claims_html}
      </div>
    </section>
    <section id="evidences">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">03 / EVIDENCE INDEX</div><h2>证据索引</h2></div>
          <p>任取一条结论，都可以回到原文链接或原始记录。</p>
        </div>
        {_render_evidence_index(view.evidences)}
      </div>
    </section>
    <section id="gates">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">04 / GATES</div><h2>门禁状态</h2></div>
          <p>首屏只显示汇总。逐门判定见执行者视图。</p>
        </div>
        {_render_gate_list(view.gates, include_checks=False)}
      </div>
    </section>
    <section id="limits">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">05 / BOUNDARIES</div><h2>推断边界与未知</h2></div>
          <p>limits 写本次不能推断什么。unknowns 写本次缺什么数据。</p>
        </div>
        {_render_limits(view.limits, view.unknowns)}
      </div>
    </section>
  </main>
{_render_footer(view, view.contract_sha256, data_hash, REPORT_HASH_PLACEHOLDER)}"""
    return _page_shell(
        f"{view.template_id} · 决策者报告",
        "report-view",
        body,
    )


def render_report_html_unhashed(
    contract: ContractInput,
    *,
    data_hash: str = "",
) -> str:
    """渲染带占位符的 ``report.html``。

    两步协议的第一步。页脚把 ``__REPORT_HASH__`` 与 ``__SOP_HASH__``
    写进 ``data-render-hash`` 属性。调用方对返回值调用产物线的
    ``render_sha256``，再调用 :func:`render_report_html`。

    为什么不能一步到位：页脚要显示最终 HTML 的哈希。哈希写入页脚后
    字节改变，新字节的哈希又改变。这个循环没有不动点。所以哈希固定
    为占位符形态的 sha256。复核时用产物线的 ``strip_hash_placeholders``
    还原同一形态。

    ``data_hash`` 在第一步写入页面。两步必须传同一个值。
    """
    return _render_report_page(contract, data_hash=data_hash)


def render_report_html(
    contract: ContractInput,
    *,
    report_hash: str = "",
    sop_hash: str = "",
    data_hash: str = "",
) -> str:
    """渲染决策者视图 ``report.html``。

    本函数执行两步协议。它先调用 :func:`render_report_html_unhashed`，
    再替换两个哈希占位符。哈希由调用方传入。渲染器不读时钟、不读库。

    任一哈希为空时，页脚显示「未计算」。不得用另一页的哈希代替。

    验收判据：改一个数字，两页同步变。
    """
    document = render_report_html_unhashed(contract, data_hash=data_hash)
    return _fill_hash_placeholders(
        document,
        report_hash=report_hash,
        sop_hash=sop_hash,
    )


def _render_sop_page(contract: ContractInput, *, data_hash: str) -> str:
    """生成执行者视图的未哈希 HTML。页脚保留两个占位符。"""
    view = _build_view(contract)
    checks = "".join(f"<li>{_esc(item)}</li>" for item in view.checks)
    body = f"""
  <a class="skip" href="#main">跳到主要内容</a>
  <header class="topbar">
    <div class="shell">
      <span class="brand">DIH 报告合同</span>
      <span class="micro">执行者视图 · sop.html</span>
      <nav aria-label="SOP 导航">
        <a href="#gates">门禁</a><a href="#coverage">覆盖</a>
        <a href="#metrics">指标</a><a href="#ledger">成本</a><a href="#limits">边界</a>
      </nav>
    </div>
  </header>
  <main id="main">
    <section class="hero" id="top">
      <div class="shell">
        <div class="eyebrow">执行者视图 · {_esc(view.generated_at)}</div>
        <h1>执行流程、证据门禁与成本明细</h1>
        <p class="hero-lead">模板 {_esc(view.template_id)} · 合同版本 {_esc(view.schema_version)}
          · 生成时间 {_esc(view.generated_at)}</p>
        <div class="status-line" id="evidence-status">
          <span class="pill {view.gate_status_class}">门禁 {_esc(view.gate_status_label)}
            · {_esc(view.gate_status)}</span>
          <span class="pill {view.lowest_grade_class}">最低证据等级
            {_esc(view.lowest_grade_label)} · {_esc(view.lowest_grade or "未评级")}</span>
          <span class="pill">Claim {view.claim_count}</span>
          <span class="pill">成本 USD {_esc(view.total_cost_usd)}</span>
        </div>
      </div>
    </section>
    <section id="gates">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">01 / GATES</div><h2>按合同顺序展示门禁</h2></div>
          <p>门禁顺序来自合同 gates 数组。渲染器不重排、不增删。</p>
        </div>
        {_render_gate_list(view.gates, include_checks=True)}
      </div>
    </section>
    <section id="checks">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">02 / CHECKS</div><h2>发布检查项</h2></div>
          <p>检查项由合同状态推导。它们不替代人工判定。</p>
        </div>
        <article class="panel"><ul class="checklist">{checks}</ul></article>
      </div>
    </section>
    <section id="metrics">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">03 / METRICS</div><h2>共享指标</h2></div>
          <p>本表与决策者视图共用同一份合同与同一个格式化函数。</p>
        </div>
        {_render_metrics_table(view.metrics)}
      </div>
    </section>
    <section id="coverage">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">04 / COVERAGE</div><h2>覆盖表</h2></div>
          <p>{_esc(view.coverage_summary)}</p>
        </div>
        {_render_coverage_table(view.coverage_rows)}
      </div>
    </section>
    <section id="ledger">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">05 / RUN LEDGER</div><h2>成本明细</h2></div>
          <p>成本合计来自 run_ledger。两个视图显示同一个合计值。</p>
        </div>
        {_render_ledger_table(view.ledger_rows, view.total_cost_usd)}
      </div>
    </section>
    <section id="claims">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">06 / CLAIM CHECKLIST</div><h2>结论发布检查</h2></div>
          <p>证据等级低于 L4 的 claim 只能写方向性判断。</p>
        </div>
        {_render_claim_checklist(view.claims)}
      </div>
    </section>
    <section id="limits">
      <div class="shell">
        <div class="section-head">
          <div><div class="section-index">07 / LIMITS AND UNKNOWNS</div><h2>边界与未知</h2></div>
          <p>执行者必须把 limits 与 unknowns 原样带入交付记录。</p>
        </div>
        {_render_limits(view.limits, view.unknowns)}
      </div>
    </section>
  </main>
{_render_footer(view, view.contract_sha256, data_hash, SOP_HASH_PLACEHOLDER)}"""
    return _page_shell(
        f"{view.template_id} · 执行者 SOP",
        "sop-view",
        body,
    )


def render_sop_html_unhashed(
    contract: ContractInput,
    *,
    data_hash: str = "",
) -> str:
    """渲染带占位符的 ``sop.html``。

    两步协议的第一步。页脚把 ``__REPORT_HASH__`` 与 ``__SOP_HASH__``
    写进 ``data-render-hash`` 属性。调用方对返回值调用产物线的
    ``render_sha256``，再调用 :func:`render_sop_html`。

    为什么不能一步到位：页脚要显示最终 HTML 的哈希。哈希写入页脚后
    字节改变，新字节的哈希又改变。这个循环没有不动点。所以哈希固定
    为占位符形态的 sha256。复核时用产物线的 ``strip_hash_placeholders``
    还原同一形态。

    ``data_hash`` 在第一步写入页面。两步必须传同一个值。
    """
    return _render_sop_page(contract, data_hash=data_hash)


def render_sop_html(
    contract: ContractInput,
    *,
    report_hash: str = "",
    sop_hash: str = "",
    data_hash: str = "",
) -> str:
    """渲染执行者视图 ``sop.html``。

    本函数执行两步协议。它先调用 :func:`render_sop_html_unhashed`，
    再替换两个哈希占位符。哈希由调用方传入。渲染器不读时钟、不读库。

    任一哈希为空时，页脚显示「未计算」。不得用另一页的哈希代替。

    验收判据：改一个数字，两页同步变。
    """
    document = render_sop_html_unhashed(contract, data_hash=data_hash)
    return _fill_hash_placeholders(
        document,
        report_hash=report_hash,
        sop_hash=sop_hash,
    )

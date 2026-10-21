"""报告合同 ``report_contract`` 的 Pydantic 模型与规范化哈希。

事实源按优先级排列：

1. ``docs/design/【契约冻结】v1-表名-枚举-接口.md``。
2. PRD 5.5.1 的字段表。
3. 迭代计划 2.4 与 D7。

本模块是 L3 纯函数层。它不读库、不联网、不调模型、不读时钟。
调用方必须传入完整合同对象。

字段名 ``claim_status`` 来自 PRD 5.5.1 与架构设计 6.3。
``ClaimState`` 与 ``EvidenceRole`` 直接复用 ``models/claim.py``。
本模块不保留第二份枚举定义。

``coverage`` 只接受对象形状 ``{"cells": [...]}``。
裸数组不是合法合同。

``canonical_json_bytes`` 与 ``contract_sha256`` 是报告合同的唯一哈希入口。
四条 B4 线必须 import 这两个函数。不得各写一份。

``Decimal`` 在 JSON 中写为字符串。这样不丢精度。
``artifact`` 组的三个哈希由调用方写入。本模块不计算 HTML 哈希。
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Final, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from data_intelligence_hub.models.claim import ClaimState, EvidenceRole
from data_intelligence_hub.models.run import RunOutcome
from data_intelligence_hub.tool_catalog.evidence_grade import GRADE_ORDER, EvidenceGrade
from data_intelligence_hub.tool_catalog.evidence_thresholds import EVIDENCE_THRESHOLDS

SCHEMA_VERSION: Final = "1.0.0"

# 模板清单只从 B2 的阈值表派生。不得另写一份。
TEMPLATE_IDS: Final[frozenset[str]] = frozenset(EVIDENCE_THRESHOLDS)

# 契约冻结 §2.8 的五个阻断点。
BLOCKING_GATE_IDS: Final[frozenset[str]] = frozenset(
    {
        "G-Plan",
        "G-Cost",
        "G-Evidence",
        "G-Claim",
        "G-Publish",
    }
)
# G0-G10 是研究阶段编号。PRD 5.5.1 允许它们出现在 gates[]。
STAGE_GATE_IDS: Final[tuple[str, ...]] = tuple(f"G{index}" for index in range(11))
GATE_IDS: Final[frozenset[str]] = BLOCKING_GATE_IDS | frozenset(STAGE_GATE_IDS)

GateStatus = Literal["pending", "pass", "fail", "blocked", "expired"]
CoverageStatus = Literal["success", "empty", "failed"]
CountType = Literal[
    "raw_object",
    "occurrence",
    "canonical_record",
    "frame_member",
    "annotation",
    "metric_row",
]
# 任一 claim 低于 L4 时，text 不得含这三个词。
BELOW_L4_FORBIDDEN_WORDS: Final[tuple[str, ...]] = ("确认", "证明", "必然")

# 指标与数量的 JSON 类型。int 与 float 都接受。
Number = int | float

# 合同里的日期字段。规范化时只保留 ``YYYY-MM-DD``。
_DATE_FIELD_NAMES: Final[frozenset[str]] = frozenset({"start", "end", "as_of"})

# 合同里的时间字段。规范化时按字段名识别 ISO-8601 文本。
_TIMESTAMP_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "generated_at",
        "decided_at",
        "captured_at",
        "started_at",
        "finished_at",
    }
)


class ContractModel(BaseModel):
    """合同模型的公共基类。

    合同是冻结的。出现未定义字段必须报错。
    """

    model_config = ConfigDict(extra="forbid")


class Window(ContractModel):
    """时间窗 ``{start, end, days}``。

    三个键都必填。``days`` 必须大于等于 1。
    ``end`` 必须不早于 ``start``。
    """

    start: date
    end: date
    days: int = Field(ge=1)

    @model_validator(mode="after")
    def _window_is_ordered(self) -> Window:
        if self.end < self.start:
            raise ValueError("window.end 必须不早于 window.start")
        return self


class FamilyChild(ContractModel):
    """家族成员。字段来自 PRD 5.5.1 的 ``family_children``。"""

    variant_id: str | None = None
    sku: str | None = None
    asin: str | None = None
    color: str | None = None
    size: str | None = None


class Identity(ContractModel):
    """报告身份组 ``identity``。

    字段逐条对应 PRD 5.5.1 的 identity 表。
    ``competitors`` 允许空数组，最多 5 个。
    ``mapping_confidence`` 低于 0.8 时由上游写入 quarantine。
    """

    task_id: uuid.UUID
    brand: str
    category: str
    competitors: list[str] = Field(default_factory=list, max_length=5)
    markets: list[str] = Field(min_length=1)
    window: Window
    product: str | None = None
    model: str | None = None
    variant_id: str | None = None
    sku: str | None = None
    asin: str | None = None
    parent_asin: str | None = None
    bundle: str | None = None
    offer: str | None = None
    mapping_confidence: float | None = Field(default=None, ge=0, le=1)
    family_children: list[FamilyChild] = Field(default_factory=list)


class Decision(ContractModel):
    """决策组 ``decision``。

    ``protect`` / ``resolve`` / ``prove`` 是首屏三个固定槽位。
    三者允许空数组，但键不得省略。所以三者没有默认值。
    """

    decision_question: str
    answer: str
    protect: list[str]
    resolve: list[str]
    prove: list[str]


class Gate(ContractModel):
    """门禁组的一个元素 ``gates[]``。

    ``gate_id`` 取契约冻结 §2.8 的五个阻断点，或 PRD 5.5.1 的 G0-G10。
    ``status`` 取契约冻结 §2.7 的五个值。``expired`` 用于授权过期。
    """

    gate_id: str
    status: GateStatus
    owner: uuid.UUID | None = None
    decided_at: datetime | None = None
    note: str | None = None

    @field_validator("gate_id")
    @classmethod
    def _gate_id_is_known(cls, value: str) -> str:
        if value not in GATE_IDS:
            raise ValueError(f"gate_id {value} 非法")
        return value


class CoverageCell(ContractModel):
    """覆盖率的一个单元。

    一个单元按 ``{source_tool_id, market, window}`` 三键聚合。
    ``status`` 对应 PRD 的「有结果 / 空结果 / 失败」。
    """

    source_tool_id: str
    market: str
    window: Window
    record_count: int = Field(ge=0)
    frame_member_count: int = Field(ge=0)
    status: CoverageStatus


class CoverageBlock(ContractModel):
    """覆盖组 ``coverage``。

    合同只接受对象形状 ``{"cells": [...]}``。
    裸数组不是合法合同。拒绝时给出明确报文。
    对象形状允许未来增加 ``summary`` 字段，不破坏形状。
    """

    cells: list[CoverageCell]

    @model_validator(mode="before")
    @classmethod
    def _reject_bare_cell_list(cls, value: Any) -> Any:
        if isinstance(value, list):
            raise ValueError(
                "coverage 必须是对象 {\"cells\": [...]}，不接受裸数组。"
                "请把覆盖单元放进 cells 字段。"
            )
        return value


class Metric(ContractModel):
    """指标组的一个元素 ``metrics[]``。

    ``count_type`` 取 PRD 5.5.1 的六个计数口径。
    """

    metric_id: str
    label: str
    numerator: Number
    denominator: Number
    count_type: CountType
    frame: str
    as_of: date
    note: str | None = None


class ClaimScope(ContractModel):
    """claim 的适用范围 ``{market, window, sample_n}``。三个键都必填。"""

    market: str
    window: Window
    sample_n: int = Field(ge=0)


class Claim(ContractModel):
    """主张组的一个元素 ``claims[]``。

    ``claim_status`` 的五个值与契约冻结 §2.6 一致。
    ``counterevidence_text`` 必填，可以为「未发现反证」。
    ``evidence_ids`` 至少 1 条。
    """

    claim_id: str
    text: str
    claim_status: ClaimState
    evidence_grade: EvidenceGrade
    scope: ClaimScope
    counterevidence_text: str = Field(min_length=1)
    owner: uuid.UUID
    evidence_ids: list[str] = Field(min_length=1)


class Evidence(ContractModel):
    """证据组的一个元素 ``evidences[]``。

    ``role`` 取 ``support`` / ``counter`` / ``context`` / ``gap``。
    ``evidence_grade`` 是该条证据所属 run 的等级。
    """

    evidence_id: str
    claim_id: str
    role: EvidenceRole
    raw_record_id: uuid.UUID | None = None
    source_tool_id: str
    url: str | None = None
    excerpt: str | None = None
    captured_at: datetime
    market: str
    locale: str
    evidence_grade: EvidenceGrade


class RunLedgerRow(ContractModel):
    """运行账本组的一个元素 ``run_ledger[]``。

    字段来自 PRD 5.5.1 的 run_ledger 表。
    ``outcome`` 直接复用 B3 的 ``RunOutcome``。取值只有四个。
    """

    run_id: uuid.UUID
    tool_id: str
    endpoint_type: str
    actor_id: str | None = None
    unit: str
    quantity: Number
    unit_price: Decimal
    total_cost_usd: Decimal
    authorization_id: uuid.UUID | None = None
    evidence_grade: EvidenceGrade
    started_at: datetime
    finished_at: datetime
    outcome: RunOutcome


class Artifact(ContractModel):
    """产物组 ``artifact``。

    三个哈希都由调用方计算并写入。
    ``contract_sha256`` 不参与自身计算。见 :func:`contract_sha256`。
    """

    report_html_sha256: str
    sop_html_sha256: str
    contract_sha256: str


class ReportContract(ContractModel):
    """完整的 ``report_contract.json``。

    顶层字段全部必填。顺序与 PRD 5.5.1 的骨架一致。
    ``schema_version`` 只接受 ``1.0.0``，所以空串会被拒绝。
    ``template_id`` 只接受 B2 阈值表里的五个模板。
    ``coverage`` 是对象，不是数组。
    """

    schema_version: Literal["1.0.0"]
    template_id: str
    generated_at: datetime
    identity: Identity
    decision: Decision
    gates: list[Gate]
    coverage: CoverageBlock
    metrics: list[Metric]
    claims: list[Claim]
    evidences: list[Evidence]
    run_ledger: list[RunLedgerRow]
    limits: list[str]
    unknowns: list[str]
    artifact: Artifact

    @field_validator("template_id")
    @classmethod
    def _template_id_is_known(cls, value: str) -> str:
        if value not in TEMPLATE_IDS:
            raise ValueError(f"template_id {value} 不属于 B2 的五个模板")
        return value


def to_json(contract: ReportContract) -> str:
    """把合同序列化为稳定 JSON。

    规则固定：

    - ``ensure_ascii=False``，中文直接写出。
    - ``sort_keys=True``，键顺序不随构造顺序变化。
    - 缩进固定为 2 个空格。
    - 输出不带尾部换行。

    同一份合同必须得到同一个字符串。报告哈希依赖这一点。
    """
    return json.dumps(
        contract.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
        allow_nan=False,
    )


def _format_timestamp(value: datetime) -> str:
    """把时间收敛成 UTC 的 ``Z`` 形式。毫秒省略。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_date_text(value: str) -> str:
    """把日期文本收敛成 ``YYYY-MM-DD``。

    不是日期文本时原样返回。
    Pydantic 的 date 字段也接受午夜时间文本。本函数统一去掉时间部分。
    """
    text = value.strip()
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return value
    return parsed.date().isoformat()


def _normalize_timestamp_text(value: str) -> str:
    """把 ISO-8601 时间文本收敛成 UTC 的 ``Z`` 形式。

    不是时间文本时原样返回。
    Pydantic 模型路径只产出合法时间文本。
    """
    text = value.strip()
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return value
    return _format_timestamp(parsed)


def _normalize(value: Any, *, field_name: str | None = None) -> Any:
    """递归收敛合同值。

    模型路径先 ``model_dump(mode="json")``。
    两条路径随后走同一套规则。所以结果必须完全相同。
    """
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"), field_name=field_name)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(item, field_name=field_name) for item in value]
    if isinstance(value, datetime):
        return _format_timestamp(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("合同含非有限 Decimal，不能计算规范化哈希")
        return str(value)
    if isinstance(value, Enum):
        return _normalize(value.value, field_name=field_name)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        if field_name in _TIMESTAMP_FIELD_NAMES:
            return _normalize_timestamp_text(value)
        if field_name in _DATE_FIELD_NAMES:
            return _normalize_date_text(value)
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("合同含 NaN 或 Infinity，不能计算规范化哈希")
        return value
    raise TypeError(f"合同含不可序列化的值：{type(value).__name__}")


def _canonical_payload(contract: ReportContract | Mapping[str, Any]) -> dict[str, Any]:
    """把合同收敛成哈希用的普通字典。

    ``Mapping`` 先按 :class:`ReportContract` 校验。
    校验通过时走模型路径。类型收敛与默认值处理因此与模型完全一致。
    校验失败时按通用规则递归规范化。这样部分合同仍可计算哈希。
    """
    if isinstance(contract, BaseModel):
        raw: Any = contract.model_dump(mode="json")
    elif isinstance(contract, Mapping):
        try:
            validated = ReportContract.model_validate(contract)
        except ValidationError:
            raw = contract
        else:
            raw = validated.model_dump(mode="json")
    else:
        raise TypeError("合同必须是 ReportContract 或 Mapping")
    normalized = _normalize(raw)
    if not isinstance(normalized, dict):
        raise TypeError("合同顶层必须是对象")
    payload = cast(dict[str, Any], normalized)
    payload.pop("generated_at", None)
    payload.pop("artifact", None)
    return payload


def canonical_json_bytes(contract: ReportContract | Mapping[str, Any]) -> bytes:
    """生成合同哈希用的规范化 JSON 字节串。

    本函数是报告合同唯一的规范化入口。
    四条 B4 线都必须 import 本函数。
    输入可以是 :class:`ReportContract`，也可以是等价的 ``Mapping``。
    两条路径走同一套 :func:`_normalize`，所以得到完全相同的字节。

    规则固定：

    - 时间一律写 UTC 的 ``Z`` 后缀，毫秒省略。
      例如 ``2026-10-21T00:00:00Z``。
    - ``Decimal`` 写字符串，保留原精度。
    - 日期写 ``YYYY-MM-DD``。
    - 键排序，分隔符固定为 ``,`` 与 ``:``，UTF-8 编码，中文不转义。
    - 排除 ``generated_at`` 与 ``artifact``。
    - 拒绝 float 的 NaN 与 Infinity，抛出 ``ValueError``。

    本函数是 RFC 8785 的近似，不是完整实现。已知差异：

    - ``1e-7`` 写成 ``1e-07``。RFC 8785 要求 ``1e-7``。
    - ``-0.0`` 保留负号。RFC 8785 要求 ``0``。
    - 键排序按 Unicode 码点。RFC 8785 按 UTF-16 码元排序。
      非 BMP 字符与 U+E000-U+FFFF 字符的相对顺序因此不同。
    """
    payload = _canonical_payload(contract)
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def contract_sha256(contract: ReportContract | Mapping[str, Any]) -> str:
    """计算合同的 SHA-256 十六进制摘要。

    输入与 :func:`canonical_json_bytes` 相同。接受模型与 Mapping。
    规范化排除 ``generated_at`` 与 ``artifact``。
    所以改生成时间或产物哈希不改变结果。改任一内容字段都会改变结果。
    """
    return hashlib.sha256(canonical_json_bytes(contract)).hexdigest()


def validate_contract(contract: ReportContract) -> list[str]:
    """检查合同的语义问题。

    返回问题列表。空列表表示通过。
    本函数不重复 Pydantic 的结构校验。
    本函数是纯函数。它不读库、不联网、不调模型。

    检查项：

    1. 每个 claim 至少有一条 ``counter`` 或 ``gap`` 证据。
       证据按 ``evidences[].claim_id`` 归属。
    2. ``coverage`` 中 ``status='success'`` 单元的 ``source_tool_id``
       必须出现在 ``evidences[].source_tool_id`` 或 ``run_ledger[].tool_id`` 里。
       ``metrics[].metric_id`` 不是数据来源，不参与本检查。
       ``status='empty'`` 与 ``status='failed'`` 的单元不要求有对应证据。
    3. claim 等级低于 L4 时，``text`` 不得含「确认」「证明」「必然」。
    4. ``gates[].gate_id`` 必须是合法取值。
    """
    issues: list[str] = []

    roles_by_claim: dict[str, set[str]] = {}
    for evidence in contract.evidences:
        roles_by_claim.setdefault(evidence.claim_id, set()).add(evidence.role)

    for claim in contract.claims:
        roles = roles_by_claim.get(claim.claim_id, set())
        if "counter" not in roles and "gap" not in roles:
            issues.append(f"claim {claim.claim_id} 缺少 counter 或 gap 证据")

    known_source_ids = {evidence.source_tool_id for evidence in contract.evidences}
    known_source_ids.update(row.tool_id for row in contract.run_ledger)
    for cell in contract.coverage.cells:
        if cell.status != "success":
            continue
        if cell.source_tool_id not in known_source_ids:
            issues.append(
                f"coverage 的 source_tool_id {cell.source_tool_id} "
                "未出现在 evidences 或 run_ledger 中"
            )

    l4 = GRADE_ORDER[EvidenceGrade.L4_AUTHORIZED_LIVE]
    for claim in contract.claims:
        if GRADE_ORDER[claim.evidence_grade] >= l4:
            continue
        for word in BELOW_L4_FORBIDDEN_WORDS:
            if word in claim.text:
                issues.append(f"claim {claim.claim_id} 的等级低于 L4，text 不得含「{word}」")

    for index, gate in enumerate(contract.gates):
        if gate.gate_id not in GATE_IDS:
            issues.append(f"gates[{index}] 的 gate_id {gate.gate_id} 非法")

    return issues

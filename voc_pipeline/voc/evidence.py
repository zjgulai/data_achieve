"""Evidence grading: seeing what puts a claim in which grade.

The grades are decision states, not a truth score.  The rules are ordered:
evaluate top to bottom and stop at the first match, so a claim can never be
upgraded by arguing about it.  There is no catch-all that grants Supported
hypothesis: counts that satisfy no rule fall through to Evidence gap.

Six states, in evaluation order:
  1. Not authorized       medical / safety / causality / diagnosis
  2. Blocked              required gate != PASS, denominator missing, or
                          diagnostic frame used for prevalence
  3. Evidence gap         required cell empty, key fields entirely missing, or
                          a stated comparative support gate did not pass
  4. Confirmed            direct fact + artifact sha256 + exact identity + no inference
  5. Directional          >=8 records, >=2 authors, >=70% same direction, single-coded
  6. Supported hypothesis 3-7 records, or 55-70% agreement, or a single author
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import EvidenceGrade


@dataclass(frozen=True)
class GradeRule:
    grade: EvidenceGrade
    seen: str
    mechanical_test: str
    may_be_used_for: str
    may_not_be_used_for: str
    upgrade_path: str


GRADE_ORDER: tuple[EvidenceGrade, ...] = (
    EvidenceGrade.NOT_AUTHORIZED,
    EvidenceGrade.BLOCKED,
    EvidenceGrade.GAP,
    EvidenceGrade.CONFIRMED,
    EvidenceGrade.DIRECTIONAL,
    EvidenceGrade.SUPPORTED_HYPOTHESIS,
)


GRADE_RULES: list[GradeRule] = [
    GradeRule(
        grade=EvidenceGrade.NOT_AUTHORIZED,
        seen="结论涉及医学功效、安全性、因果、诊断，或需要法律/监管判断。",
        mechanical_test="topic ∈ {medical_efficacy, safety, causality, diagnosis} OR claim requires regulated review",
        may_be_used_for="只记录 self-report、claim relation 与 review queue。",
        may_not_be_used_for="疗效、安全率、因果、诊断。",
        upgrade_path="不升级；转 medical/legal review，且结论措辞必须回到描述层。",
    ),
    GradeRule(
        grade=EvidenceGrade.BLOCKED,
        seen="需要的 gate 未通过，或需要的分母不存在。",
        mechanical_test="gate_status(required_gate) != PASS OR denominator is None/0 OR frame is diagnostic and claim is prevalence",
        may_be_used_for="说明为什么不能说，以及缺哪一份证据。",
        may_not_be_used_for="任何比率、排名、总体结论、正式策略。",
        upgrade_path="补 gate artifact；不能用语料规模替代 gate。",
    ),
    GradeRule(
        grade=EvidenceGrade.GAP,
        seen="要求的 cell 里记录数为 0，或关键字段缺失，或声明的对比支持门槛未通过。",
        mechanical_test=(
            "required_cell_count == 0 OR required_field_missing_rate == 1.0 "
            "OR required_support_gate != PASS"
        ),
        may_be_used_for="指出证据缺口与补证动作。",
        may_not_be_used_for="用 family / adjacent / 其他 variant 推断该 cell。",
        upgrade_path="定向补采或换来源；补齐后再评级。",
    ),
    GradeRule(
        grade=EvidenceGrade.CONFIRMED,
        seen="直接观察到的事实，带不可变原始 artifact、精确身份与时间戳，且不含解释。",
        mechanical_test="fact_type ∈ {identity, count, ledger, field_value} AND artifact_sha256 present AND exact_identity true AND no inference",
        may_be_used_for="身份、计数、成本、字段值、血缘。",
        may_not_be_used_for="把事实外推成体验、偏好或因果。",
        upgrade_path="已是最高级；如需解释，另立 Directional 结论。",
    ),
    GradeRule(
        grade=EvidenceGrade.DIRECTIONAL,
        seen="同一 frame 内 ≥8 条独立 canonical records、≥2 个作者、方向一致度 ≥70%，但仍是单编码 / pre-G7。",
        mechanical_test="n_independent >= 8 AND n_authors >= 2 AND direction_share >= 0.70 AND single_coded",
        may_be_used_for="方向性判断、下一步实验设计。",
        may_not_be_used_for="prevalence、总体情绪率、对外承诺、ROI 排序。",
        upgrade_path="完成 G7 双盲 agreement 后，才可能进入 G8 的正式 metric。",
    ),
    GradeRule(
        grade=EvidenceGrade.SUPPORTED_HYPOTHESIS,
        seen=(
            "3–7 条独立记录，或方向一致度 55–70%，或只来自一个 thread / 一个作者，"
            "或有 ≥8 条记录但方向一致度仍低于 70%。"
        ),
        mechanical_test=(
            "3 <= n_independent < 8 OR 0.55 <= direction_share < 0.70 OR n_authors == 1 "
            "OR (n_independent >= 8 AND n_authors >= 2 AND direction_share < 0.70)"
        ),
        may_be_used_for="提出假设、设计下一轮采集。",
        may_not_be_used_for="写成发现，或据此改产品。",
        upgrade_path="扩样到 ≥8 条且 ≥2 作者且方向一致度 ≥70%，或补充第二来源。",
    ),
]


def grade_rule_table() -> list[dict[str, Any]]:
    return [
        {
            "order": i + 1,
            "grade": r.grade.value,
            "seen": r.seen,
            "mechanical_test": r.mechanical_test,
            "may_be_used_for": r.may_be_used_for,
            "may_not_be_used_for": r.may_not_be_used_for,
            "upgrade_path": r.upgrade_path,
        }
        for i, r in enumerate(GRADE_RULES)
    ]


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
    # A comparative claim can name its own support gate.  The gate is a
    # mechanical condition stated in the claim's basis, not a discretionary
    # judgement: when it does not pass, the claim is an Evidence gap even when
    # the descriptive counts are complete.
    required_support_gate: str | None = None
    support_gate_status: str = "PASS"
    is_direct_fact: bool = False
    artifact_sha256: str | None = None
    exact_identity: bool = False
    inference: bool = True
    n_independent: int = 0
    n_authors: int = 0
    direction_share: float = 0.0
    single_coded: bool = True


def _sha_note(sha: str | None) -> str:
    return f"sha256[0:12]={sha[:12]}" if sha else "sha256=missing"


def explain_grade(ctx: GradeInput) -> tuple[EvidenceGrade, str]:
    """Ordered evaluation.  First match wins; no discretionary override.

    Returns the grade and a reason string that quotes the counts which fired
    the rule, so a reader can recompute the decision.
    """
    if ctx.topic in {"medical_efficacy", "safety", "causality", "diagnosis"}:
        return EvidenceGrade.NOT_AUTHORIZED, (
            f"规则1 命中：topic={ctx.topic} 属于医学/安全/因果/诊断，"
            "任何计数都不能把它降级成可发布的结论。"
        )
    if ctx.required_gate and ctx.gate_status != "PASS":
        return EvidenceGrade.BLOCKED, (
            f"规则2 命中：required_gate={ctx.required_gate} status={ctx.gate_status} != PASS；"
            f"n_records={ctx.n_independent}、n_authors={ctx.n_authors} 不能替代 gate。"
        )
    if ctx.is_prevalence_claim and (ctx.denominator in (None, 0) or ctx.frame == "diagnostic"):
        return EvidenceGrade.BLOCKED, (
            f"规则2 命中（分母/诊断分支）：prevalence claim 但 denominator={ctx.denominator}、frame={ctx.frame}"
            "（diagnostic 样本不能估 prevalence）。"
        )
    if ctx.required_cell_count == 0 or ctx.required_field_missing_rate >= 1.0:
        return EvidenceGrade.GAP, (
            f"规则3 命中：required_cell_count={ctx.required_cell_count}、"
            f"required_field_missing_rate={ctx.required_field_missing_rate:.2f}；该格没有记录。"
        )
    if ctx.required_support_gate and ctx.support_gate_status != "PASS":
        return EvidenceGrade.GAP, (
            f"规则3 命中（支持门槛分支）：support_gate={ctx.required_support_gate} "
            f"status={ctx.support_gate_status} != PASS；"
            f"n_records={ctx.n_independent}、n_authors={ctx.n_authors} 不能替代门槛，"
            "分层对比按 Evidence gap 记录。"
        )
    if (
        ctx.is_direct_fact
        and ctx.artifact_sha256
        and ctx.exact_identity
        and not ctx.inference
    ):
        return EvidenceGrade.CONFIRMED, (
            f"规则4 命中：直接事实 + {_sha_note(ctx.artifact_sha256)} + "
            "exact_identity=True + inference=False。"
        )
    if (
        ctx.n_independent >= 8
        and ctx.n_authors >= 2
        and ctx.direction_share >= 0.70
        and ctx.single_coded
    ):
        return EvidenceGrade.DIRECTIONAL, (
            f"规则5 命中：n_records={ctx.n_independent}（≥8）、n_authors={ctx.n_authors}（≥2）、"
            f"agreement={ctx.direction_share:.0%}（≥70%）、single_coded=True。"
        )
    # Zero usable evidence is a gap before any positive grade is considered,
    # even if a stray author count or share would match the hypothesis rule.
    if ctx.n_independent == 0:
        return EvidenceGrade.GAP, (
            "规则3 命中：n_records=0，该格没有任何可用记录。"
        )
    if (
        3 <= ctx.n_independent < 8
        or 0.55 <= ctx.direction_share < 0.70
        or ctx.n_authors == 1
    ):
        triggers = []
        if 3 <= ctx.n_independent < 8:
            triggers.append(f"n_records={ctx.n_independent} 落在 3–7 条")
        if 0.55 <= ctx.direction_share < 0.70:
            triggers.append(f"agreement={ctx.direction_share:.0%} 落在 55–70%")
        if ctx.n_authors == 1:
            triggers.append("n_authors=1（单作者）")
        return EvidenceGrade.SUPPORTED_HYPOTHESIS, (
            "规则6 命中：" + "；".join(triggers)
            + f"（n_records={ctx.n_independent}、n_authors={ctx.n_authors}、"
            f"agreement={ctx.direction_share:.0%}）"
        )
    if ctx.n_independent >= 8 and ctx.n_authors >= 2 and ctx.direction_share < 0.70:
        # Explicit insufficiency, not a catch-all: there is evidence, but the
        # one missing condition is direction agreement.  The reason must name
        # that condition so a reader can see what would upgrade the claim.
        return EvidenceGrade.SUPPORTED_HYPOTHESIS, (
            f"规则6 命中：n_records={ctx.n_independent}（≥8）、n_authors={ctx.n_authors}（≥2）已达标，"
            f"但 agreement={ctx.direction_share:.0%}（<70%）未达 Directional 的方向一致度门槛；"
            "按 Supported hypothesis 记录，差在方向一致度。"
        )
    # Fail closed.  There is no "lowest available grade" fallback: a claim
    # whose counts do not satisfy any rule is a data gap, never a hypothesis.
    return EvidenceGrade.GAP, (
        f"数据不足：n_records={ctx.n_independent}、n_authors={ctx.n_authors}、"
        f"agreement={ctx.direction_share:.0%}、single_coded={ctx.single_coded} "
        "没有满足任何证据档位的机械条件，按 Evidence gap 记录。"
    )


def assign_grade(ctx: GradeInput) -> EvidenceGrade:
    """Grade only; see :func:`explain_grade` for the reason string."""
    return explain_grade(ctx)[0]


def evidence_spec() -> dict[str, Any]:
    return {
        "grade_count": 6,
        "note": (
            "Ref 报告显示 5 个标签但表中有 6 种状态：Confirmed / Directional / "
            "Supported hypothesis / Evidence gap / Blocked / Not authorized。"
            "第六级是医疗与因果禁写区。成熟度是状态，不是评分。"
        ),
        "rules": grade_rule_table(),
        "ordering": "first match wins: " + " > ".join(g.value for g in GRADE_ORDER),
    }

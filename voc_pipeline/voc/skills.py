"""14 atomic skills: inputs, steps, outputs, acceptance, rollback, handoff.

Each skill also declares an automation verdict:

  pure_logic     - can be a function; no judgement, no external authority
  hybrid         - code does the mechanics, a human accepts the judgement
  human_required - the decision is the deliverable; code can only record it

The verdict is the answer to "which skills can we code now".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import Role


@dataclass
class SkillStep:
    action: str
    actor: Role


@dataclass
class Skill:
    name: str
    title: str
    kind: str  # stage | cross-stage
    gate: str | None
    order: int | None
    inputs: list[str]
    steps: list[SkillStep]
    outputs: list[str]
    acceptance: list[str]
    rollback: str
    handoff: str
    consumes: list[str] = field(default_factory=list)
    automation: str = "hybrid"
    automation_reason: str = ""
    code_module: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "kind": self.kind,
            "gate": self.gate,
            "order": self.order,
            "inputs": self.inputs,
            "steps": [{"action": s.action, "actor": s.actor.value} for s in self.steps],
            "outputs": self.outputs,
            "acceptance": self.acceptance,
            "rollback": self.rollback,
            "handoff": self.handoff,
            "consumes": self.consumes,
            "automation": self.automation,
            "automation_reason": self.automation_reason,
            "code_module": self.code_module,
        }


SKILLS: list[Skill] = [
    Skill(
        name="voc-decision-charter",
        title="Decision Charter",
        kind="stage",
        gate="G0",
        order=0,
        inputs=[
            "business question and decision owner",
            "target product, market, time window, channels, variants",
            "available data, access rights, budget, deadline, publication boundary",
        ],
        steps=[
            SkillStep("把业务问题写成一个二选一或可判定的选择", Role.HUMAN),
            SkillStep("指定唯一决策 owner 与唯一决策问题", Role.HUMAN),
            SkillStep("为每个 frame 写 purpose 与 denominator rule", Role.HUMAN),
            SkillStep("写数值化 QA 阈值与 stop condition", Role.HUMAN),
            SkillStep("序列化 charter 并校验必填字段", Role.CODE),
        ],
        outputs=[
            "voc-research-charter.json",
            "metric-intent-and-denominator-rules.json",
            "qa-thresholds.json",
            "decision-question.md",
            "authorization-and-budget-ledger.json",
            "gate-plan.json",
        ],
        acceptance=[
            "one decision owner and one decision question are named",
            "every sample frame has a purpose and denominator rule",
            "exact-variant metrics require verified review-variant evidence",
            "semantic and identity-governance QA thresholds are numeric",
            "all external calls and publication boundaries are explicit",
            "stop conditions are machine-checkable",
        ],
        rollback="Return to G0 whenever product scope, decision owner, market, publication boundary, or budget changes.",
        handoff="voc-product-identity receives voc-research-charter.json + gate-plan.json.",
        automation="human_required",
        automation_reason="决策 owner、预算与发布边界是组织授权，代码只能校验字段齐全，不能替代授权。",
        code_module="gates.G0 + cli.validate_charter",
    ),
    Skill(
        name="voc-product-identity",
        title="Product Identity",
        kind="stage",
        gate="G1",
        order=1,
        inputs=["accepted G0 charter", "official product URL or catalog record", "candidate marketplace and social identifiers"],
        steps=[
            SkillStep("抓取 PDP / catalog 原始响应并记录 hash 与时间", Role.CODE),
            SkillStep("解析 parent / child / variant / legacy / adjacent", Role.CODE),
            SkillStep("模糊匹配候选进入人工裁决并写 confidence", Role.HUMAN),
            SkillStep("隔离 legacy 与 adjacent", Role.HUMAN),
            SkillStep("生成 crosswalk 与 variant matrix", Role.CODE),
        ],
        outputs=[
            "product-identity-crosswalk.json",
            "variant-matrix.csv",
            "identity-evidence-ledger.json",
            "identity-quarantine.json",
        ],
        acceptance=[
            "target SKU and variant are explicit",
            "marketplace parent and child roles are separated",
            "legacy and adjacent products are quarantined",
            "each mapping has evidence, timestamp, confidence, and review status",
        ],
        rollback="Return to G1 if a new child ASIN, SKU, bundle, color, size, or legacy mapping changes product membership.",
        handoff="voc-source-rights-audit receives product-identity-crosswalk.json.",
        consumes=["voc-research-charter.json", "gate-plan.json"],
        automation="hybrid",
        automation_reason="抓取与解析可完全代码化；fuzzy match 与 legacy/adjacent 归类需要人工裁决。",
        code_module="collect.AmazonPDPClient + identity.parse_pdp",
    ),
    Skill(
        name="voc-source-rights-audit",
        title="Source and Rights Audit",
        kind="stage",
        gate="G2",
        order=2,
        inputs=["G0 charter", "G1 identity crosswalk", "candidate source inventory and access constraints"],
        steps=[
            SkillStep("逐源登记 rights / privacy / commerciality / content role", Role.HUMAN),
            SkillStep("写 allowed use 与 forbidden use", Role.HUMAN),
            SkillStep("把 blocked source 写入 register 并阻断下游", Role.CODE),
        ],
        outputs=[
            "source-rights-matrix.json",
            "source-role-contract.json",
            "privacy-and-retention-plan.md",
            "blocked-source-register.json",
        ],
        acceptance=[
            "every source has a rights and privacy state",
            "commercial and creator content is isolated from organic consumer metrics",
            "allowed use and forbidden use are explicit",
            "blocked sources cannot enter a downstream denominator",
        ],
        rollback="Return to G2 when a source endpoint, rights status, disclosure, access route, or intended publication use changes.",
        handoff="voc-source-pilot receives source-rights-matrix.json + source-role-contract.json.",
        consumes=["voc-research-charter.json", "product-identity-crosswalk.json"],
        automation="human_required",
        automation_reason="权利状态、allowed use 与隐私保留期是法律判断；代码只能执行已登记的 blocked 规则。",
        code_module="gates.G2 + contracts.source_role_contract",
    ),
    Skill(
        name="voc-source-pilot",
        title="Source Pilot",
        kind="stage",
        gate="G3",
        order=3,
        inputs=["G0 charter and budget", "G1 identity crosswalk", "G2 approved source contract", "provider or endpoint candidates"],
        steps=[
            SkillStep("inspect：字段、分页、地区、评论层、费用、限制", Role.CODE),
            SkillStep("最小 run：固定参数、固定时间窗、保存不可变 raw", Role.CODE),
            SkillStep("对账 records / zero / errors / cost", Role.CODE),
            SkillStep("写 source scorecard 与 limitation", Role.LLM_ASSISTED),
            SkillStep("接受、条件接受或拒绝来源", Role.HUMAN),
        ],
        outputs=[
            "pilot-raw/",
            "monid-run-ledger.json",
            "pilot-source-scorecard.json",
            "pilot-gate-decision.json",
        ],
        acceptance=[
            "Monid run never precedes inspect",
            "cost remains inside the G0 ceiling",
            "raw responses are immutable and linked to ledger entries",
            "a conditional source has an explicit limitation and next action",
        ],
        rollback="Return to G2 for rights or role problems, G1 for product mismatch, or G0 for a budget and scope change.",
        handoff="voc-taxonomy-freeze receives pilot-raw/ + pilot-gate-decision.json.",
        consumes=["voc-research-charter.json", "product-identity-crosswalk.json", "source-role-contract.json"],
        automation="pure_logic",
        automation_reason="inspect → minimal run → reconcile 是确定性流程；唯一人工点是 scorecard 的 accept/reject，可后置。",
        code_module="collect.ArcticShiftClient + collect.run_pilot",
    ),
    Skill(
        name="voc-taxonomy-freeze",
        title="Taxonomy Freeze",
        kind="stage",
        gate="G4",
        order=4,
        inputs=["G3 pilot records and gate decision", "research questions", "known product and category terminology"],
        steps=[
            SkillStep("从 pilot 归纳候选 aspect / context / journey / outcome / gap", Role.LLM_ASSISTED),
            SkillStep("为每个 code 写定义、include、exclude", Role.HUMAN),
            SkillStep("生成合法枚举与 exact-variant predicate", Role.CODE),
            SkillStep("迁移 pilot 编码并对账", Role.CODE),
            SkillStep("冻结版本并出 gate decision", Role.HUMAN),
        ],
        outputs=[
            "taxonomy.json",
            "codebook.md",
            "alias-map.json",
            "pilot-coded.jsonl",
            "taxonomy-coverage.json",
            "consumer-metric-view-contract.json",
            "social-governance-rules.json",
            "g7-calibration-plan.json",
            "g4-gate-decision.json",
        ],
        acceptance=[
            "definitions and include or exclude rules are complete",
            "unknown is distinct from negative or absent",
            "mixed components retain positive and negative evidence",
            "machine contracts define legal enums and exact-variant predicates",
            "the G7 plan reads G0 thresholds and models risk as coverage",
            "the pilot migration reconciles to the source inventory",
        ],
        rollback="Return to G4 with a new taxonomy version when recurring uncodable evidence or code collision exceeds the charter threshold.",
        handoff="voc-stratified-collection receives taxonomy.json + consumer-metric-view-contract.json.",
        consumes=["pilot-raw/", "pilot-source-scorecard.json", "metric-intent-and-denominator-rules.json", "qa-thresholds.json"],
        automation="hybrid",
        automation_reason="枚举、alias、predicate 可代码化；code 定义与 include/exclude 是可发表判断，必须人写并冻结。",
        code_module="taxonomy.Taxonomy + coder.RuleCoder",
    ),
    Skill(
        name="voc-stratified-collection",
        title="Stratified Collection",
        kind="stage",
        gate="G5",
        order=5,
        inputs=["G0 sample and budget plan", "G1 identity crosswalk", "G2 source contracts", "G3 validated endpoints", "G4 taxonomy version"],
        steps=[
            SkillStep("生成 collection matrix", Role.CODE),
            SkillStep("按 cell 执行并逐条写 ledger", Role.CODE),
            SkillStep("保留 missing / zero-result cell", Role.CODE),
            SkillStep("对账 quota / cost / records", Role.CODE),
        ],
        outputs=["collection-matrix.json", "raw/", "collection-run-ledger.json", "quota-and-gap-report.json", "raw-manifest.sha256"],
        acceptance=[
            "each raw object is traceable to an approved request",
            "missing and zero-result cells remain visible",
            "frame membership is explicit and can overlap without double counting",
            "cost and record totals reconcile",
        ],
        rollback="Return to G3 when endpoint behavior drifts, G2 when rights drift, or G1 when product match deteriorates.",
        handoff="voc-canonicalize receives raw/ + raw-manifest.sha256.",
        consumes=["voc-research-charter.json", "product-identity-crosswalk.json", "source-rights-matrix.json", "taxonomy.json"],
        automation="pure_logic",
        automation_reason="分层的唯一输入是已批准的 matrix 与 quota；执行、记账、缺口保留都是确定性代码。",
        code_module="collect.run_collection",
    ),
    Skill(
        name="voc-canonicalize",
        title="Canonicalize and Deduplicate",
        kind="stage",
        gate="G6",
        order=6,
        inputs=["G5 raw corpus and manifests", "G1 identity crosswalk", "G2 source-role contract", "G4 taxonomy identifiers"],
        steps=[
            SkillStep("raw → occurrence（source + external id + frame）", Role.CODE),
            SkillStep("exact dedup（规范化文本 hash）", Role.CODE),
            SkillStep("fuzzy 候选（Jaccard 阈值）进入 review", Role.CODE),
            SkillStep("确定性选代表并写 duplicate group", Role.CODE),
            SkillStep("写 metric eligibility 与 exclusion", Role.CODE),
            SkillStep("对账四个计数", Role.CODE),
        ],
        outputs=[
            "canonical-voc-record.schema.json",
            "occurrences.jsonl",
            "canonical-records.jsonl",
            "duplicate-groups.json",
            "lineage-edges.jsonl",
            "metric-eligibility-manifest.jsonl",
            "exclusion-quarantine.jsonl",
            "g6-reconciliation.json",
        ],
        acceptance=[
            "raw, occurrence, canonical, and frame-membership counts are distinct",
            "every canonical record links to at least one occurrence",
            "every record satisfies the canonical schema and G4 enum contract",
            "each duplicate group has exactly one representative",
            "metric eligibility and exclusions are machine-readable",
            "representative selection is deterministic",
        ],
        rollback="Return to G6 when new sources reveal duplicate groups or normalization rules change; preserve prior versions.",
        handoff="voc-coding-calibration receives canonical-records.jsonl + metric-eligibility-manifest.jsonl.",
        consumes=["raw/", "raw-manifest.sha256", "product-identity-crosswalk.json", "source-role-contract.json", "taxonomy.json"],
        automation="pure_logic",
        automation_reason="exact dedup 与代表选择可完全确定；只有 fuzzy 候选的最终裁决需要人，且可隔离成 review 队列。",
        code_module="canonical.build_canonical",
    ),
    Skill(
        name="voc-coding-calibration",
        title="Coding Calibration",
        kind="stage",
        gate="G7",
        order=7,
        inputs=["G4 taxonomy, metric contract, and g7-calibration-plan.json", "G6 canonical corpus and eligibility manifest", "G0 qa-thresholds.json"],
        steps=[
            SkillStep("按风险分层抽 calibration sample", Role.CODE),
            SkillStep("coder A / coder B 独立编码", Role.HUMAN),
            SkillStep("计算逐字段 agreement", Role.CODE),
            SkillStep("分歧 adjudication 并写 ledger", Role.HUMAN),
            SkillStep("出 gate decision；未达标字段阻断下游", Role.HUMAN),
        ],
        outputs=["calibration-sample.json", "coder-a.jsonl", "coder-b.jsonl", "agreement-report.json", "adjudication-ledger.json", "production-coded.jsonl", "g7-gate-decision.json"],
        acceptance=[
            "core semantic agreement meets the charter threshold",
            "identity and governance meet their higher threshold",
            "risk and boundary cases have complete review",
            "failed fields block downstream metric views",
        ],
        rollback="Return to G4 for definition failure, G6 for lineage failure, or repeat G7 after a bounded codebook revision.",
        handoff="voc-insight-analysis receives production-coded.jsonl + g7-gate-decision.json.",
        consumes=["taxonomy.json", "codebook.md", "g7-calibration-plan.json", "canonical-records.jsonl", "qa-thresholds.json"],
        automation="human_required",
        automation_reason="双盲编码的本质是两个独立判断者；代码只能抽样、计分、拦截，不能替代第二编码员。",
        code_module="coder.agreement_report（只做计分与阻断）",
    ),
    Skill(
        name="voc-insight-analysis",
        title="Insight Analysis",
        kind="stage",
        gate="G8",
        order=8,
        inputs=["G0 metric rules", "G4 metric view contract and taxonomy", "G6 canonical + eligibility", "G7 production-coded + gate decision"],
        steps=[
            SkillStep("物化 metric definition", Role.CODE),
            SkillStep("计算 metric table 并冻结", Role.CODE),
            SkillStep("写 insight ledger 与 counterevidence ledger", Role.LLM_ASSISTED),
            SkillStep("敏感度与稀疏性检查", Role.CODE),
        ],
        outputs=["materialized-metric-definitions.json", "metric-table.parquet-or-csv", "insight-ledger.json", "counterevidence-ledger.json", "g8-gate-decision.json"],
        acceptance=[
            "all metrics are reproducible from named records",
            "sample-frame denominators never mix silently",
            "no prevalence claim is derived from designed diagnostic samples",
            "every headline insight includes counterevidence and confidence",
        ],
        rollback="Return to G7 for coding reliability, G6 for duplicates, G5 for missing cells, or G0 for a changed decision.",
        handoff="voc-strategy-activation receives insight-ledger.json + counterevidence-ledger.json.",
        consumes=["metric-intent-and-denominator-rules.json", "consumer-metric-view-contract.json", "canonical-records.jsonl", "metric-eligibility-manifest.jsonl", "production-coded.jsonl"],
        automation="hybrid",
        automation_reason="分母锁定与复现是纯代码；'最合理解释是什么' 与反证取舍需要人判断并签名。",
        code_module="metrics.materialize + claims.build_claims",
    ),
    Skill(
        name="voc-strategy-activation",
        title="Strategy Activation",
        kind="stage",
        gate="G9",
        order=9,
        inputs=["G8 insight and counterevidence ledgers", "G0 business decision", "operational constraints and owners"],
        steps=[
            SkillStep("洞察 → 可控 lever 与 lane owner", Role.HUMAN),
            SkillStep("设计最小可逆实验与 baseline", Role.HUMAN),
            SkillStep("写 KPI / guardrail / stop", Role.HUMAN),
            SkillStep("记录 approval", Role.HUMAN),
        ],
        outputs=["strategy-option-ledger.json", "experiment-portfolio.json", "experiment-baseline-plan.json", "owner-and-kpi-map.json", "g9-decision-record.json"],
        acceptance=[
            "every action traces to one or more insights",
            "every experiment has an owner, KPI, guardrail, and stop condition",
            "medical and safety boundaries are reviewed",
            "approval state is explicit",
        ],
        rollback="Return to G8 when evidence interpretation changes and to G0 when the business decision changes.",
        handoff="voc-measurement-review receives experiment-portfolio.json + g9-decision-record.json.",
        consumes=["voc-research-charter.json", "insight-ledger.json", "counterevidence-ledger.json", "g8-gate-decision.json"],
        automation="human_required",
        automation_reason="owner、KPI、guardrail 与审批是组织承诺，不是分析产物。",
        code_module="gates.G9（只做追溯校验）",
    ),
    Skill(
        name="voc-measurement-review",
        title="Measurement Review",
        kind="stage",
        gate="G10",
        order=10,
        inputs=["G9 experiment portfolio and decision record", "baseline metrics", "outcome and guardrail data", "new VOC drift signals"],
        steps=[
            SkillStep("对账 outcome / guardrail", Role.CODE),
            SkillStep("按设计限制因果措辞", Role.HUMAN),
            SkillStep("记录 decision / rollback / refresh", Role.HUMAN),
        ],
        outputs=["experiment-readout.json", "guardrail-report.json", "drift-register.json", "decision-history.json", "refresh-plan.json"],
        acceptance=[
            "outcome and guardrail data reconcile",
            "causal language matches the design",
            "decision and rollback are recorded",
            "refresh triggers have an owner and due date",
        ],
        rollback="Use the earliest affected gate; do not patch a late-stage metric when upstream identity, rights, or taxonomy drifted.",
        handoff="voc-validation-handoff receives decision-history.json + refresh-plan.json.",
        consumes=["experiment-portfolio.json", "experiment-baseline-plan.json", "g9-decision-record.json"],
        automation="hybrid",
        automation_reason="对账可代码化；因果措辞与 scale/revise/stop 是管理判断。",
        code_module="gates.G10",
    ),
    Skill(
        name="voc-interactive-report",
        title="Interactive VOC Report",
        kind="cross-stage",
        gate=None,
        order=None,
        inputs=["approved gate ledger", "artifacts that actually exist", "brand and accessibility requirements"],
        steps=[
            SkillStep("读取 gate ledger 与 claims", Role.CODE),
            SkillStep("按 report_mode 的 minimum gate 过滤可发表结论", Role.CODE),
            SkillStep("渲染 HTML（无第三方运行时）", Role.CODE),
            SkillStep("浏览器与结构校验", Role.CODE),
        ],
        outputs=["interactive-voc-report.html", "voc-workflow-sop.html", "site-data.json", "rendered-qa.json"],
        acceptance=[
            "report_mode and minimum gate are explicit",
            "every headline number has a visible frame or denominator",
            "current gate and forbidden conclusions are prominent",
            "pages work without third-party runtime dependencies",
            "browser checks pass at desktop and mobile widths",
        ],
        rollback="Return to the source artifact rather than editing a derived number in HTML; rebuild and revalidate both pages.",
        handoff="voc-validation-handoff receives interactive-voc-report.html + rendered-qa.json.",
        consumes=["gate-ledger.json", "insight-ledger.json", "strategy-option-ledger.json"],
        automation="pure_logic",
        automation_reason="渲染与校验是确定性代码；文案语气可后置人工编辑，但结构约束必须由验证器强制。",
        code_module="report.render_report + validate_report",
    ),
    Skill(
        name="voc-research-orchestrator",
        title="VOC Research Orchestrator",
        kind="cross-stage",
        gate=None,
        order=None,
        inputs=["stakeholder request", "existing artifacts and gate states", "workspace constraints and authorizations"],
        steps=[
            SkillStep("读取 artifact registry 与 gate ledger", Role.CODE),
            SkillStep("判定每个 gate 的真实状态", Role.CODE),
            SkillStep("发现上游失效时标 stale 并回滚", Role.CODE),
            SkillStep("对外 handoff 前由人确认 scope", Role.HUMAN),
        ],
        outputs=["voc-program-state.json", "artifact-registry.json", "gate-ledger.json", "handoff-summary.md"],
        acceptance=[
            "G0-G10 states match actual artifacts",
            "no stage is marked complete from a plan or local preview",
            "blocked and conditional gates name the missing evidence",
            "downstream skills receive only accepted upstream contracts",
        ],
        rollback="Route to the earliest invalid gate and mark every dependent artifact stale until revalidated.",
        handoff="voc-decision-charter and every stage skill read the gate ledger before running.",
        automation="hybrid",
        automation_reason="状态机与 stale 传播可代码化；scope 与对外 handoff 需要人确认。",
        code_module="orchestrator.build_program_state",
    ),
    Skill(
        name="voc-validation-handoff",
        title="VOC Validation and Handoff",
        kind="cross-stage",
        gate=None,
        order=None,
        inputs=["current delivery scope", "artifact registry and gate ledger", "skill suite manifest and SOP", "artifacts and HTML in scope", "acceptance criteria"],
        steps=[
            SkillStep("运行结构与合同校验", Role.CODE),
            SkillStep("运行报告质量校验（标题/证据/图表/禁用结论）", Role.CODE),
            SkillStep("出 delivery manifest 与 handoff", Role.CODE),
            SkillStep("对未执行项签名确认", Role.HUMAN),
        ],
        outputs=["voc-validation-result.json", "browser-qa.json", "delivery-manifest.json", "handoff.md"],
        acceptance=[
            "all required validators pass",
            "behavioral fixtures cover failure as well as success paths",
            "stage claims match gate artifacts",
            "the handoff states what is local, uncommitted, unpublished, or not yet executed",
        ],
        rollback="Send each defect to its owning gate and keep delivery status failed or conditional until revalidation passes.",
        handoff="Delivery owner receives delivery-manifest.json + handoff.md.",
        consumes=["artifact-registry.json", "gate-ledger.json"],
        automation="hybrid",
        automation_reason="所有 validator 是代码；'未执行/未发布' 的签名必须由人给出。",
        code_module="validate.suite + deliver.build_manifest",
    ),
]


def skill_spec() -> list[dict[str, Any]]:
    return [skill.to_dict() for skill in SKILLS]


def automation_summary() -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {"pure_logic": [], "hybrid": [], "human_required": []}
    for skill in SKILLS:
        summary[skill.automation].append(skill.name)
    return summary

---
title: GOAL-V2-03 MonitoringScope 与 Workflow Planner 设计
doc_type: design
module: workflow-planner
topic: goal-v2-03-monitoring-scope-workflow-planner
status: approved
review_status: approved
created: 2026-07-12
updated: 2026-07-13
owner: self
source: human+ai
product_prd: ../../product/product-prd-social-media-automation-platform-v2.md
parent_design: 2026-07-10-social-media-automation-platform-v2-design.md
depends_on: 2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
evidence_level: L2-local-implementation-and-mock-e2e
provider_call: false
actor_run: false
llm_call: false
database_migration: false
production_boundary: production unchanged
goal_execution: phase_1_locally_complete
---

# GOAL-V2-03 MonitoringScope 与 Workflow Planner 设计

> 本文固化用户已批准的方案 A：以契约优先的纵向切片交付双模式 Workflow Planner。本文记录已完成的阶段一：只生成可解释、可复现、零持久化的 Fixture Preview。阶段二的当前实施状态与持久化合同由后继设计和实施计划维护；任何阶段都不会因生成计划而自动调用 Provider、Actor、浏览器或 LLM。

## 1. 执行摘要

GOAL-V2-03 把 GOAL-V2-02 的只读 Capability Catalog 转化为面向品牌、市场运营和业务分析用户的规划能力。用户从两个业务入口进入同一个 Planner：

1. 周期监测：配置品牌、品类、竞品、话题、账号、平台、地区、语言、周期和交付意图。
2. 批量研究：输入关键词与 Seed URL，生成跨平台查询和解析路线预览。

两种模式共用同一条领域链：

    MonitoringScopeDraft
    -> PlanningInput
    -> Query Compiler
    -> Capability Resolver
    -> WorkflowPlanPreview

阶段一采用 write-free Preview：

- Preview API 可以读取当前用户有权访问的 Project 与 canonical Capability Catalog。
- Preview API 不创建 MonitoringScope、WorkflowPlan、WorkflowVersion 或 WorkflowRun。
- Query Compiler 的候选扩展层只使用固定 Fixture，不调用 Kimi、DeepSeek 或其他模型。
- canonical Catalog 当前只有 candidate Assertion，因此真实目录预览必须返回可解释的 held，而不是虚构 Primary。
- 只有测试专用 synthetic verified/partial Fixture 用于证明 Primary、Fallback 和 Shadow 的确定性合同。
- Web 交付一个双模式 Planner 向导，简单视图与高级视图读取同一后端响应。

阶段二使用阶段一合同作为输入/输出合同，不创建第二套 Planner。当前后继事实源是 [`2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md`](2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md) 与 [`2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md`](../plans/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md)。

### 1.1 当前实现同步（2026-07-13）

本设计继续保持 `status=approved`、`review_status=approved`；GOAL Phase 1 执行状态为 `phase_1_locally_complete`。Tasks 0-13 mandatory steps、完整 API/Web gate、scope/boundary/no-migration gate 已取得 2026-07-13 新鲜本地证据；该状态不等于整个 GOAL 完成，也不授权 Phase 2。

当前已实现事实：

- `POST /api/projects/{project_id}/workflow-plans/preview` 已注册，并通过当前 workspace 的 active Project read path 与 canonical Catalog 生成 write-free Preview。
- `MonitoringScopeDraft -> normalization -> Query Compiler -> mode template -> Capability Resolver -> Catalog Snapshot -> Preview Fingerprint -> WorkflowPlanPreview` 已形成独立模块流水线。
- canonical candidate-only Catalog 返回 `200 held`；Primary、Fallback、Shadow、partial 与 ready snapshot 只由 test-only synthetic Fixture 证明。
- 周期监测与批量研究共用一个四步 Planner；简单/高级视图消费同一后端 Preview 和 Fingerprint，不在 Web 重算路线。
- Project selection 只在一次匹配 Project 的 accepted 200 Preview 后标记 applied；pending、输入/mode/Project 变化和 stale 状态均为 false。
- Preview 仍固定 `database_write=false`、`provider_call=false`、`actor_run=false`、`browser_run=false`、`llm_call=false`、`workflow_run_created=false`、`execution_authorized=false`。
- 历史 Phase One closeout 时，Phase Two 的 MonitoringScope/QueryTerm/WorkflowPlan/WorkflowVersion persistence、migration、Save/Activate/Run 尚未实现且未授权。该历史边界已被后继 Phase Two 本地实施授权取代；当前状态是 `phase_2_persistence_in_progress`，但 Activate/Run 与所有外部执行仍未授权。
- Fresh exit evidence：Planner targeted `240 passed`，API full `439 passed`，Web unit `151 passed`，Web mock E2E `58 passed / 12 expected skipped`，Preview `p95=5.287ms`，Alembic 仍为单一 head `202606110026`；详细原始键值记录在实施计划唯一的 `Execution Evidence` 节。

## 2. 当前基线

### 2.1 产品事实

- 产品第一目标用户是品牌、市场运营和业务分析人员，不是开发者专用工具。
- 现有 Project 是监测项目根对象，不新增平行 MonitoringProject。
- GOAL-V2-03 Exit Gate 要求周期监测与批量研究两条核心 Flow 在 Fixture 下生成确定性、完整可解释的计划。
- WorkflowPlan 必须展示覆盖、步骤、预算、门禁、Primary、Fallback、Shadow、字段合同和局限。
- candidate 不能进入自动执行路线。
- 不含 LLM 调用的 WorkflowPlan Preview 产品目标为 p95 小于 3 秒。

### 2.2 仓库事实

- Project 当前只承载 workspace、名称、描述、业务域、状态和 owner，尚无 MonitoringScope 配置。
- 现有 ExtractionPlan 面向 SiteAnalysis，不具备本 Goal 所需的 Project 级 Scope、Capability Resolver 和不可变 WorkflowVersion 语义，不能复用为 WorkflowPlan V2。
- canonical Capability Catalog 已由 GOAL-V2-01/02 建立；GOAL-V2-02 当前记录的 35 条 Assertion 全部为 candidate。
- 能力矩阵是只读派生模型，可作为 Resolver 输入，但不能把矩阵聚合状态当作执行资格。
- Planner 已成为第一个真实消费 Project 上下文的页面：只有 accepted Project-scoped 200 Preview 才使 data-project-filter-applied=true；其他尚未接入项目过滤的页面继续保持 false，不得宣称已完成项目过滤。
- 后端现有 Project 路由位于 /api/projects；Planner 使用嵌套 Project 资源路径，不创建平行项目 API。
- 现有 Automation Service 职责已经较重。Planner 使用新的聚焦 schema、service 和 route 模块，不继续把 Query Compiler 或 Resolver 塞入大服务文件。

### 2.3 工作区事实

- GOAL-V2-02 已形成用户授权的本地 checkpoint `1e4cc4863c9629e2ff249edc0f7722dafaaf6831`，未 push。
- GOAL-V2-03 Tasks 1-13 的 Backend、Web、测试和文档变更均位于该 checkpoint 之后，当前保持 unstaged/uncommitted。
- 在 Phase 1 closeout 时，Task 13 已完成批准合同与本地 overlay 同步，并通过 fresh API、Web、scope 与 no-migration gate；当时 Phase 2 persistence/versioning 仍未授权。这是历史 checkpoint 事实；当前后继状态见第 1.1 节与 Phase Two 设计/实施计划。
- 本文不授权 stage、commit、push、PR、merge、deploy、生产检查、数据库写入或外部调用。

### 2.4 固定证据边界

    provider_call=false
    provider_call_attempted=false
    actor_run=false
    browser_run=false
    llm_call=false
    credential_read_status=not_read
    database_write=false
    migration_applied=false
    workflow_run_created=false
    production unchanged

## 3. Goal、阶段与非目标

### 3.1 总体 Goal

从品牌词、品类词、竞品词、话题、关键词、官方账号和 Seed URL 生成确定性、可解释、可版本化的 WorkflowPlan。

### 3.2 阶段一：Preview Vertical Slice

阶段一交付：

- MonitoringScopeDraft 与 PlanningInput 合同。
- 品牌 Precision-first、品类 Recall-first 的确定性规范化。
- 确定性词典、Fixture 候选扩展和平台查询编译三层模型。
- Capability Resolver、market_monitoring_balanced 策略、RoutePlan、Fallback 和 Shadow 规则。
- Project 级 write-free Preview API。
- 双模式 Planner 向导、简单视图与高级视图。
- 两条核心 Flow 的 Fixture、合同、API、UI 和 E2E 证据。

阶段一完成状态只能是 GOAL-V2-03 phase_1_locally_complete，不能称为整个 Goal 完成。

### 3.3 阶段二：Persistence and Versioning

阶段二在单独授权后交付：

- 一个 Project 保存多个 MonitoringScope。
- QueryTerm 状态与来源持久化。
- WorkflowPlan 生命周期和不可变 WorkflowVersion。
- Preview 保存、版本历史、版本比较所需的后端合同。
- 可回滚 Alembic migration 和数据库集成测试。

阶段二仍不创建 WorkflowRun，不调用 Provider，不激活调度。

### 3.4 覆盖的 PRD 要求

阶段一覆盖或建立合同：

- PRJ-004、PRJ-005
- QRY-001、QRY-002、QRY-003、QRY-004、QRY-005
- WFL-002、WFL-003、WFL-004、WFL-005、WFL-006、WFL-007
- UI-002、UI-003、UI-007、UI-009

阶段二完成：

- PRJ-002、PRJ-003
- WFL-001 中 Plan 与 Version 的持久化部分
- WFL-008 所需的版本数据基础

WorkflowRun、StepRun 和真实执行部分继续由后续 Goal 交付，不在本 Goal 中冒充完成。

### 3.5 非目标

- 不接入 Kimi、DeepSeek 或其他 LLM 的真实客户端。
- 不安装或调用 Provider SDK、TikHub Endpoint、Apify Actor、自托管 Collector 或授权浏览器。
- 不读取 credential、token、Cookie、密码或私钥。
- 不执行关键词检索、URL 网络解析、内容采集、批量解析、Dataset 写入、Alert、VOC 或 Brief。
- 不实现 WorkflowRun、StepRun、调度、重试、游标、真实 Fallback 切换或 Shadow 调用。
- 不升级任何 candidate Assertion 的状态。
- 不修改 Capability Catalog 的事实治理流程。
- 不把阶段一 Preview 写入数据库、localStorage 历史或后台任务。
- 不删除旧 ExtractionPlan、Automation、Source 或 Task 链。
- 不执行 commit、push、PR、merge、deploy 或生产验证。

## 4. 已确认设计决策

### 4.1 采用契约优先纵向切片

阶段一从 Schema、失败测试和 golden Fixture 开始，依次贯通纯领域服务、Preview API 和 Planner UI。前端 Fixture 不作为独立事实源，前端不重新实现 Query 或 Route 决策。

未选择以下方案：

- 前端原型优先：虽然更快看到页面，但无法证明 Resolver 和 Fingerprint。
- 持久化优先：会提前引入 migration，并在未 checkpoint 的 GOAL-V2-02 工作区上扩大风险。

### 4.2 采用严格能力证据分层

- verified 可以进入 Primary、Fallback 和 Shadow 候选。
- partial 只有在策略允许、请求明确表示愿意查看字段降级且 Required Fields 仍满足时，才可作为 proposed route 参与；它始终带 approval_required=true，客户端布尔值不是审批。
- candidate、unknown、blocked、unsupported 和 deprecated 均不能进入自动路线。
- canonical Catalog 无合格实现时返回 held/unresolved_no_verified_capability。
- synthetic verified/partial 仅存在于测试 Fixture，不写回 canonical Catalog，不进入产品展示事实。

### 4.3 采用双阶段完整目标

- 阶段一证明 Planner 合同、确定性和用户可理解性。
- 阶段二证明持久化、不可变版本和可回滚 migration。
- 两阶段之间使用独立授权门；阶段一验收通过不自动授权阶段二。

### 4.4 采用单一双模式向导

周期监测与批量研究共用 Planner 页面、表单基础组件、Preview API 和结果组件。差异只存在于模式专用字段和计划模板，不复制 Query Compiler 或 Resolver。

## 5. 阶段一系统架构

### 5.1 请求链

    Web Planner
    -> POST /api/projects/{project_id}/workflow-plans/preview
    -> Project access check
    -> MonitoringScopeNormalizer
    -> QueryTermBuilder
    -> CandidateExpansionAdapter(Fixture)
    -> PlatformQueryCompiler
    -> RouteRequirementBuilder
    -> CapabilityResolver
    -> WorkflowPlanPreviewAssembler
    -> response

Preview 请求只读取：

- 当前 workspace 下的 Project。
- canonical Capability Catalog 及其内容哈希。
- 代码内版本化的 Planner 合同和策略配置。

Preview 请求不写数据库，也不创建异步任务。

### 5.2 模块边界

新增职责单一的后端模块：

- schemas/workflow_planner.py：输入、查询、路由、错误和 Preview 响应合同。
- services/workflow_planner/normalization.py：Scope 和词项规范化。
- services/workflow_planner/query_compiler.py：三层查询模型和平台编译。
- services/workflow_planner/policies.py：版本化场景策略和稳定评分权重。
- services/workflow_planner/capability_resolver.py：硬门禁、评分、稳定排序和排除原因。
- services/workflow_planner/planner.py：编排纯函数并组装 Preview。
- api/routes/workflow_plans.py：Project 鉴权、请求调用和 HTTP 错误映射。

模块名可以按仓库最终命名规范微调，但职责不得重新合并进 Automation Service。

### 5.3 前端边界

前端新增共享 Planner page/component，两个入口通过 mode 参数启动：

- periodic_monitoring
- batch_research

前端职责：

- 收集、校验和提交用户输入。
- 展示后端返回的简单视图与高级视图。
- 管理请求取消、过期响应和字段错误。

前端不得：

- 自行计算 route score、Primary、Fallback 或 held。
- 在 API 失败时静默回退到 Mock。
- 把 candidate 显示为可执行。
- 在阶段一保存或激活计划。

## 6. 阶段一领域合同

### 6.1 MonitoringScopeDraft

每个 Scope 至少包含：

    scope_ref
    scope_type
    canonical_term
    aliases
    include_terms
    exclude_terms
    official_accounts
    seed_urls
    languages
    regions
    platforms
    match_mode

规则：

- scope_ref 是本次 Preview 内稳定的客户端引用，不冒充数据库 ID，也不进入 Fingerprint。
- scope_ref 在单次请求内必须唯一；重复 scope_ref 返回 422。客户端提交 scope_key 或其他未知字段同样返回 422。
- 后端根据应用默认值后的 Scope 语义生成 scope_key；scope_key 是规范化内容的 SHA-256，不接受客户端传入。
- 语义完全相同的重复 Scope 合并为一个 scope_key，并在 decision_trace 记录 duplicate_scope_collapsed；原始 scope_ref 全部保留在映射表中。
- scope_type 取 brand、category、competitor、topic、campaign。
- match_mode 可省略，取值为 exact、phrase、semantic、hybrid；默认值由 scope_type 决定并写入 normalized_input。
- canonical_term 可以为空，但 brand、category 和 competitor Scope 必须提供 canonical_term。
- topic 或 campaign Scope 可以是 Seed-URL-only；canonical_term 为空时，aliases、include_terms、official_accounts、seed_urls 至少一项非空。
- canonical_term 非空时必须去除首尾空白；文本比较使用 Unicode 规范化和大小写无关的 normalized value。
- 去重保留用户首次出现的展示文本，规范化值用于比较和 Fingerprint。
- exclude_terms 与可执行确定性词项冲突时，排除优先，并在决策轨迹中记录冲突。
- Seed URL 只做语法规范化、确定性去重和已知平台分类；不发起网络请求。
- 无法分类的 URL 保留为 unclassified，不静默丢弃。

阶段一安全上限：

- 单次 Preview 最多 20 个 Scope。
- 每个 aliases、include_terms、exclude_terms 列表最多 50 项。
- 单次 Preview 最多 100 个 Seed URL。
- platforms 只能使用现有 7 个规范平台枚举。

### 6.2 PlanningInput

PlanningInput 包含：

    flow_mode
    scopes
    default_languages
    default_regions
    default_platforms
    schedule_intent
    delivery_intent
    policy_profile
    purpose
    required_fields
    optional_fields
    budget_ceiling
    rate_limit_intent
    retention_intent
    allow_partial_degradation

规则：

- flow_mode 为 periodic_monitoring 或 batch_research。
- policy_profile 默认 market_monitoring_balanced。
- allow_partial_degradation 默认 false。
- project_id 只来自 URL path 和 AuthContext，不属于 PlanningInput 请求体。请求合同禁止 extra 字段；在 body 重复提交 project_id 返回 422。
- default_languages、default_regions、default_platforms 是全局默认值。Scope 对应列表非空时完整覆盖默认值；为空时继承默认值，不做隐式并集。
- periodic_monitoring 至少包含一个 Scope、一个 schedule_intent，并且每个 Scope 必须得到至少一个 effective platform。
- batch_research 至少包含一个 Scope，且所有 Scope 合计至少提供一个 canonical/alias/include/account/Seed URL 输入。
- batch_research 不接受 schedule_intent；出现时返回 422，避免把批量研究静默升级为周期运行。
- batch_research 的关键词或账号输入必须具有 effective platform；Seed-URL-only 输入可以从已知 URL 分类派生平台。
- 无法分类且没有默认平台的 Seed URL 仍可生成 held Step，以便用户看到 unclassified 原因；不得因此静默丢弃整个输入。
- periodic_monitoring 可以声明 schedule_intent 和 delivery_intent，但阶段一不创建 scheduler 或 delivery。
- batch_research 可以同时包含关键词和 Seed URL，但输出只是未来检索与解析步骤的计划，不产生链接或 Dataset。
- rate_limit_intent 与 retention_intent 只形成声明式约束，不创建 Rate Limiter、Budget Ledger 或保留任务。
- 所有默认值在规范化后进入 Fingerprint。

### 6.3 QueryTerm

QueryTerm 至少包含：

    term
    normalized_term
    scope_ref
    scope_key
    origin
    status
    reason
    source
    score
    conflict_codes

origin 取：

- canonical
- alias
- include
- official_account
- seed_url
- fixture_candidate_expansion

status 取：

- active
- candidate
- rejected

只有确定性层产生的 active 词项进入平台查询编译。Fixture 扩展词保持 candidate，除非测试场景显式提供一份已批准词项输入；产品请求不提供自动批准入口。scope_ref 服务 UI 回显并从 Fingerprint 排除；scope_key 服务语义归因和确定性计算。

### 6.4 CompiledPlatformQuery

每个平台查询至少包含：

    platform
    scope_keys
    source_scope_refs
    resource_type
    operation
    query_version
    normalized_expression
    include_terms
    exclude_terms
    account_filters
    url_inputs
    limitations

排序规则固定：

1. 平台规范枚举顺序。
2. scope_key。
3. normalized_term。
4. resource_type 和 operation。

编译结果禁止依赖 set、数据库自然顺序或字典插入偶然性。

### 6.5 RouteRequirement

每个“平台 × 资源 × 操作”生成独立 RouteRequirement：

    requirement_ref
    scope_keys
    step_refs
    platform
    resource_type
    operation
    purpose
    regions
    required_fields
    optional_fields
    budget_ceiling
    freshness_requirement
    rate_limit_requirement
    retention_requirement
    allow_partial_degradation

平台查询与 RouteRequirement 通过稳定 requirement_ref 关联。

### 6.6 RoutePlanPreview

RoutePlanPreview 至少包含：

    requirement_ref
    status
    primary_implementation
    fallback_implementations
    shadow_rule
    required_fields
    optional_fields
    missing_optional_fields
    budget_status
    rate_limit_policy
    retention_policy
    route_eligible
    readiness_status
    approval_required
    approval_reasons
    policy_gates
    score_breakdown
    exclusion_reasons
    degradation_rule
    limitations

primary_implementation 与 fallback_implementations 使用同一 RouteCandidateDecision：

    implementation_id
    capability_status
    weighted_score
    route_eligible
    readiness_status
    approval_required
    approval_reasons
    missing_optional_fields
    evidence_refs

status 取：

- resolved：Primary 为 verified；Fallback 可以包含通过显式降级门禁的 partial。
- partial：没有 verified Primary，但策略和 allow_partial_degradation 都允许预览降级，且一个 partial 实现满足全部 Required Fields 后被选为 proposed partial Primary；approval_required 必须为 true。
- held：没有任何实现可以成为 Primary。

阶段一 RoutePlanPreview 描述路线资格，不代表执行授权。allow_partial_degradation 只表达用户愿意查看降级方案，不能充当审批凭证。所有响应固定 execution_authorized=false。

### 6.7 WorkflowPlanPreview

顶层至少包含：

    schema_version
    planner_contract_version
    project_id
    flow_mode
    planning_status
    normalized_input
    scope_ref_map
    query_terms
    compiled_queries
    steps
    route_requirements
    route_plans
    coverage
    budget_summary
    limitations
    decision_trace
    attribution_contract
    catalog_snapshot_id
    policy_version
    mode_template_version
    query_versions
    preview_fingerprint
    execution_authorized=false
    provider_call=false
    actor_run=false
    llm_call=false
    generated_at
    request_id

planning_status 取：

- resolved：所有 RouteRequirement 都具有 verified Primary。
- partially_resolved：至少一个 Requirement 获得 resolved 或 partial 路线，并且至少一个 Requirement 为 partial 或 held。
- held：没有生成可路由的 Requirement，或没有任何 Requirement 获得 resolved 或 partial 路线。

generated_at 和 request_id 只用于可观测性，不进入 Fingerprint。

decision_trace 是结构化对象：

    semantic_entries
    input_diagnostics

semantic_entries 只使用 scope_key、requirement_ref 和稳定决策 code；input_diagnostics 可以保留 scope_ref、重复输入和表单回显信息。

attribution_contract 固定未来采集结果必须保留：

    matched_scope_id
    matched_term
    match_reason
    query_version
    requirement_ref
    route_plan_ref

阶段一没有采集结果，因此只冻结字段合同。scope_ref 在阶段二保存后映射为 matched_scope_id，不能在阶段一伪造数据库 ID。

### 6.8 WorkflowStepPreview 与模式模板

WorkflowStepPreview 不是实际 StepRun。每一步至少包含：

    step_ref
    template_key
    sequence
    label
    execution_kind
    depends_on
    platform
    scope_keys
    resource_type
    operation
    requirement_ref
    input_contract
    output_contract
    planning_status
    limitations

规则：

- execution_kind 取 planner_internal 或 future_capability。
- planner_internal 不生成 RouteRequirement。
- future_capability 必须绑定规范 ResourceType、CapabilityOperation 和 requirement_ref。
- step_ref 由 template_key、platform、resource_type、operation 和稳定序号生成，不使用随机 UUID。
- depends_on 只能引用同一 Preview 中更早的 step_ref；Assembler 必须进行拓扑校验。
- input_contract 和 output_contract 只描述字段，不包含采集结果。
- planning_status 取 planned、partial、held、not_applicable。

input_contract 与 output_contract 使用 StepDataContract：

    schema_version
    fields

每个字段包含：

    name
    data_type
    cardinality
    required
    source_step_ref
    description

fields 按 name 稳定排序；source_step_ref 为空表示来自用户输入。future_content_refs、future_raw_record_contract 等名称只标识未来数据形状，不携带 URL、内容或 RawRecord。

periodic_monitoring.v1 使用固定模板：

| 顺序 | template_key | 条件 | execution_kind | Capability Requirement | 声明式输出 |
|---:|---|---|---|---|---|
| 1 | compile_scope_queries | 始终 | planner_internal | 无 | compiled_query_refs |
| 2 | classify_seed_urls | 存在 Seed URL | planner_internal | 无 | classified_seed_contract |
| 3 | discover_content | 存在词项、别名或账号过滤 | future_capability | content / search_discover | future_content_refs |
| 4 | resolve_seed_content | 存在范围内的已分类 Seed URL | future_capability | content / resolve_detail | future_content_details |
| 5 | monitor_incremental | 存在 schedule_intent 且至少有一个上游采集输入 | future_capability | content / monitor_incremental | future_change_cursor、future_content_refs |
| 6 | summarize_delivery_intent | 始终 | planner_internal | 无 | delivery_contract |

batch_research.v1 使用固定模板：

| 顺序 | template_key | 条件 | execution_kind | Capability Requirement | 声明式输出 |
|---:|---|---|---|---|---|
| 1 | compile_scope_queries | 始终 | planner_internal | 无 | compiled_query_refs |
| 2 | classify_seed_urls | 存在 Seed URL | planner_internal | 无 | classified_seed_contract |
| 3 | discover_content | 存在关键词、别名、包含词或账号过滤 | future_capability | content / search_discover | future_content_refs |
| 4 | batch_parse_content | 存在范围内的已分类 Seed URL 或 discover_content 输出合同 | future_capability | content / batch_parse | future_raw_record_contract |
| 5 | validate_field_contract | 始终 | planner_internal | 无 | required/optional field coverage contract |

映射规则：

- 每个 effective platform 独立展开 future_capability Step 和 RouteRequirement。
- 同一平台上语义相同的 Requirement 规范化合并，scope_keys 保留全部来源 Scope。
- 已分类 Seed URL 按其平台进入 resolve_seed_content 或 batch_parse_content。
- default/scope platform 均为空时，Seed URL 的已知分类平台可以成为该 URL 的派生平台。
- 任一显式 platform 列表非空时，URL 分类平台不在 effective platform 列表内不得自动扩张范围；classify_seed_urls 为该输入记录 held item 和 platform_not_selected。
- unclassified URL 由 classify_seed_urls 记录 held item 和 seed_url_unclassified，不生成伪 future_capability Step 或 Capability Requirement。
- classify_seed_urls 全部可进入范围时为 planned，部分可进入时为 partial，没有任何 URL 可进入时为 held。
- periodic 的 monitor_incremental 依赖该平台已生成的 discover_content 或 resolve_seed_content。
- batch 的 batch_parse_content 依赖该平台 discover_content；直接 Seed URL 输入同时作为该 Step 的 input_contract。
- 没有满足条件的可选 Step 不生成空 Requirement，而在 template trace 中记录 not_applicable。
- 两个模板都不生成 Dataset、Alert、VOC、Brief、WorkflowRun 或 StepRun。

## 7. Query Compiler

### 7.1 确定性词典层

品牌 Scope 默认 Precision-first：

- canonical、alias 和 official account 优先。
- 默认 match_mode=phrase；用户可以显式收紧为 exact。
- 宽泛 include term 不单独成为品牌命中依据。
- exclude term 始终生效。

品类 Scope 默认 Recall-first：

- canonical、alias 和 include term 共同参与。
- 默认 match_mode=hybrid；用户可以显式改为 phrase 或 semantic。
- semantic 只表达未来匹配意图；阶段一不会调用向量或 LLM 服务。
- exclude term 用于控制高噪声含义。

competitor、topic 和 campaign 使用用户显式 match_mode；未指定时采用 phrase。

### 7.2 Fixture 候选扩展层

CandidateExpansionAdapter 定义未来 LLM 扩展合同，但阶段一唯一实现是版本化 Fixture：

- 输入为规范化 Scope 和业务上下文。
- 输出必须通过 JSON Schema。
- 每项包含 term、reason、source、score 和 conflict_codes。
- 输出始终为 candidate。
- 适配器不得读取网络、环境凭据或用户 Secret。
- Fixture 版本进入 Planner 合同版本或 Fingerprint 输入。

### 7.3 平台查询编译层

平台编译器只生成声明式查询计划：

- 不调用平台。
- 不保证平台将返回内容。
- 不把未知操作编造成受支持。
- 缺少平台编译器时保留 limitation，并使对应 Requirement held。
- 每个编译器公开自己的 query_version，版本变化必须改变 Fingerprint。

## 8. Capability Resolver

### 8.1 输入事实

Resolver 读取原子 CapabilityAssertion、Implementation、Constraint 和 Evidence。矩阵 summary_status 只用于 UI，不能替代原子 Assertion。

### 8.2 硬门禁

硬门禁固定先于评分，并按以下顺序记录：

1. Capability status
2. Policy
3. Auth readiness
4. Purpose
5. Region
6. Data/resource/operation
7. Required Fields
8. Budget

阶段一不读取 Credential，并把规划路线资格与执行授权分开：

- route_eligible 表示在当前 Capability、Policy 和非 Secret readiness metadata 下可以成为计划路线。
- execution_authorized 表示是否允许真实调用；阶段一固定为 false。

CapabilityReadinessSnapshot 合同：

    implementation_id
    auth_readiness
    source
    credential_read_status=not_read

auth_readiness 取 not_required、ready、missing、not_checked。

- Implementation 的 required_credentials 为空时，Planner 可以本地派生 not_required。
- 产品 Preview 对需要 Credential 的实现固定返回 not_checked，不读取 Secret，也不接受客户端伪造 readiness。
- synthetic golden test 可以通过 service 构造参数注入 source=test_fixture、auth_readiness=ready。
- test-only Snapshot 不进入 HTTP 请求体、canonical Catalog、数据库或产品配置。
- 只有 not_required 或 ready 可以通过 Auth readiness 门禁；missing 或 not_checked 以明确原因排除。
- 即使 route_eligible=true，阶段一也不能把 execution_authorized 改为 true。

### 8.3 状态资格

- verified：通过全部硬门禁后参与评分。
- partial：仅当策略允许、allow_partial_degradation=true、Required Fields 完整且字段差异可解释时参与 proposed route；必须返回 approval_required=true 和字段差异。
- candidate：排除原因 candidate_not_execution_eligible。
- unknown：排除原因 capability_unknown。
- blocked：保留具体 block code。
- unsupported：排除原因 operation_unsupported。
- deprecated：排除原因 implementation_deprecated。

### 8.4 八维评分与稳定排序

market_monitoring_balanced.v1 复用 Catalog 中 1 至 5 的八维分值，并固定为整数权重，避免浮点误差和实现分叉：

| 维度 | 权重 |
|---|---:|
| Coverage | 15 |
| Freshness | 15 |
| History | 5 |
| Reliability | 20 |
| Schema Stability | 15 |
| Cost Efficiency | 10 |
| Maintainability | 5 |
| Evidence Confidence | 15 |

总权重为 100。weighted_score 使用每项分值乘权重后求和，保留整数结果，不做浮点归一化。

market_monitoring_balanced.v1 允许 partial 仅作为 proposed route：必须同时满足 allow_partial_degradation=true 和 Required Fields 完整，并固定 approval_required=true；该策略不提供执行审批。

固定流程：

1. 过滤未通过硬门禁的实现。
2. 未知成本且未设置预算上限时，把有效 Cost Efficiency 设为最低等级 1，并在 decision_trace 记录 cost_score_capped_unknown。
3. 按 market_monitoring_balanced.v1 计算 weighted_score。
4. 按 weighted_score 降序。
5. 同分时按稳定 Implementation ID 升序。

Primary 为第一名；Fallback 为其余合格实现的稳定顺序。Shadow 只在存在合格备用实现时生成声明式抽样规则，否则 disabled 并记录原因。

### 8.5 held 与未知成本

- 无合格实现时返回 held，不抛出技术错误。
- 每个被排除实现都必须有机器可读 code 和用户可读 reason。
- 价格或额度未知时 budget_status=unknown，不能按零成本排序或展示。
- 请求显式设置 budget_ceiling 时，未知成本无法证明满足预算门禁，必须以 budget_unknown_under_ceiling 排除。
- 请求未设置 budget_ceiling 时，未知成本实现可以继续参与其他门禁和评分，但 Cost Efficiency 不得获得正向优势。
- 达到用户预算上限时对应 Requirement held。

## 9. Preview API

### 9.1 Endpoint

    POST /api/projects/{project_id}/workflow-plans/preview

请求必须通过现有 AuthContext，并使用 workspace 限定的 Project lookup。不存在或不属于当前 workspace 的 Project 延续现有 404 语义，避免泄露跨 workspace 对象。只有 active Project 可以生成 Preview；已归档 Project 返回 project_not_active。

父设计中的 /api/workflow-plans/preview 是方向性草案。本 Goal 明确采用嵌套 Project 路径，因为 Project 是必需上下文；请求体不再重复接受 project_id，也不新增平行 alias。

### 9.2 响应语义

- 200：Preview 成功生成，包括 planning_status=held。
- 422：输入合同错误；返回可映射到表单字段的 detail。
- 404：Project 不存在或当前 workspace 不可见。
- 409：Project 存在但不是 active 状态。
- 503：canonical Catalog 无法加载或 Planner 依赖不可用。
- 500：未分类的内部错误；保留 request_id，服务端记录根因。

API 不将 held 映射为 4xx/5xx，也不捕获异常后返回空成功对象。

### 9.3 确定性与 Fingerprint

preview_fingerprint 对 fingerprint_payload 的规范化 JSON 计算。fingerprint_payload 包括：

- planner_contract_version
- fingerprint_input
- catalog_snapshot_id
- policy_version
- mode_template_version
- 各平台 query_version
- Candidate Fixture version
- 使用 scope_key 表达的 query_terms
- 使用 scope_key 表达的 steps
- compiled_queries
- route_plans
- coverage
- budget_summary
- limitations
- semantic decision trace

fingerprint_input 与响应中的 normalized_input 不完全相同：

- normalized_input 保留 UI 所需的 scope_ref。
- scope_ref_map 保留 scope_ref 到 scope_key 的回显关系。
- fingerprint_input 使用 scope_key 替换 scope_ref。
- Scope 按 scope_key 排序。
- 文本列表按 normalized value 排序并去重。
- 枚举使用规范字符串值。
- 所有显式默认值均保留。
- project_id 不进入 Fingerprint；Fingerprint 表达计划语义，阶段二的 Project/Version ID 负责对象身份。
- decision_trace 分为 semantic_entries 与 input_diagnostics。Fingerprint 只包含 semantic_entries；duplicate_scope_collapsed 和原始 scope_ref 等回显诊断只进入 input_diagnostics。

catalog_snapshot_id 的生成规则固定为：

1. 对 CapabilityCatalog 做 JSON mode dump。
2. 排除仅表示装载时间的 generated_at。
3. implementations、assertions、evidence 分别按稳定 ID 排序。
4. required_credentials、supported_endpoints、region_scope、purpose_scope、auth_scope 和 evidence_refs 等集合语义列表按规范字符串排序。
5. Constraint 按 constraint_type、severity、code 和 canonical details 排序。
6. 递归按 key 排序，使用 UTF-8 和紧凑 JSON 分隔符。
7. 对结果计算 SHA-256，并使用 sha256:<hex> 表达。

Capability 字段、Constraint、Evidence 或顺序规范化后的实际内容发生变化时，Snapshot 必须变化；只有 generated_at 变化时 Snapshot 不变。

preview_fingerprint 使用相同的 canonical JSON 规则和 SHA-256。算法规则由 planner_contract_version 管理。

以下字段不进入 Fingerprint：

- generated_at
- request_id
- 日志 trace id
- 响应展示顺序之外的运行时元数据

相同 Fingerprint 的两个响应，其 fingerprint_input 以及使用 scope_key 表达的 compiled_queries、route_plans、coverage、budget_summary、limitations 和 semantic decision trace 必须相同。generated_at、request_id、scope_ref_map、source_scope_refs、input_diagnostics 和 normalized_input 中仅用于回显的 scope_ref 可以不同。

### 9.4 零写入约束

阶段一 route handler 不调用 create、update、delete、commit 或 flush。集成测试必须证明请求前后 MonitoringScope、WorkflowPlan、WorkflowVersion 和 WorkflowRun 均不存在新增行；在这些表尚不存在时，通过 service spy 和现有业务表计数证明无写路径。

## 10. Planner UI

### 10.1 入口与路由

工作台的“创建监测项目”和“批量检索与解析”入口均进入同一 Planner 页面。建议路由：

    /automation/planner?mode=periodic_monitoring
    /automation/planner?mode=batch_research

监测项目页和采集工作流页可以提供上下文入口，但不得复制 Planner。

### 10.2 四步向导

1. 模式与业务目标。
2. Scope、关键词、账号和 Seed URL。
3. 平台、语言、地区、字段、预算和策略约束。
4. WorkflowPlan Preview。

周期模式额外显示 schedule_intent 和 delivery_intent；批量模式不展示伪调度或伪 Dataset 结果。

### 10.3 Project 上下文

- 在 AppShell 内增加共享 ProjectSelectionProvider/useProjectSelection，复用现有 project-selection 存储函数；Planner 和顶部 ProjectSelector 读取同一个状态源。
- ProjectSelector 继续复用现有 data-intelligence-hub:project-selection CustomEvent，Provider 用它处理同页同步，并监听 window storage 事件处理跨标签页同步。
- ProjectSelector 接受 route-aware filterApplied 状态，默认 false；/automation/planner 只有在选中 active Project 且 Preview 请求实际使用该 project_id 时才显示 true。
- Planner 必须读取共享选择并显示 Project 名称。
- 未选择 Project 时禁用 Preview，并引导选择当前 workspace 的 active Project。
- 没有选择、Project 已归档或 Preview 尚未绑定项目时，Planner 页保持 data-project-filter-applied=false。
- 其他未实现项目过滤的页面继续显示 false；本 Goal 不做全站项目化。
- Project 切换后旧 Preview 失效，用户必须重新生成。

### 10.4 简单视图

面向品牌与市场运营用户，展示：

- 覆盖的平台与 Scope。
- 将执行的计划步骤。
- planning_status。
- 预算状态。
- 主要限制。
- 为什么当前计划可以或不能进入未来执行。
- partial proposed route 的字段差异和“仍需审批”状态。

简单视图避免 Provider、Assertion、Policy Gate 等工程术语，但不得隐藏 held 或未知成本。

### 10.5 高级视图

展示：

- QueryTerm 与平台编译结果。
- RouteRequirement。
- Primary、Fallback 和 Shadow。
- Required/Optional Fields。
- Policy Gate、评分拆解和排除原因。
- Evidence、Catalog Snapshot、Policy Version 和 Fingerprint。

简单和高级视图读取同一 WorkflowPlanPreview，不允许前端重新选路。

### 10.6 阶段一操作

仅提供：

- 修改输入。
- 重新生成 Preview。
- 切换简单/高级视图。

保存与激活使用明确说明“将在持久化阶段开放”。不展示可点击但无真实行为的伪按钮。

## 11. 错误、并发与可访问性

### 11.1 业务状态与技术错误

- held 是业务结果，使用正常 Preview 布局和解释信息。
- 字段错误就地显示，并把焦点移动到首个错误。
- unclassified Seed URL 保留在输入和 Preview 中。
- Catalog 或 Planner 故障显示可重试错误，不清空用户输入。
- API 失败禁止回退到前端 Mock。
- Fixture 模式只能由测试环境显式配置。

### 11.2 并发请求

- 新 Preview 请求开始时取消旧请求，或用单调 request sequence 忽略旧响应。
- Project、mode 或输入发生变化后，旧结果标记 stale。
- 较慢的旧响应不得覆盖较新的 Preview。

### 11.3 响应式与无障碍

- 375px 与 1440px 通过布局验收。
- 四步向导支持键盘前进、返回和错误定位。
- 状态不只依赖颜色。
- 简单/高级视图切换保留焦点和当前 Preview。
- 长查询、排除原因和 Fingerprint 可以换行或安全滚动，不产生不可恢复横向溢出。

## 12. 阶段二持久化设计（历史 Phase One 基线）

本节保留 Phase One 完成时的初始占位设计。当前已批准且正在实施的完整合同以 [`2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md`](2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md) 为准；不得用本节较早的四表草案覆盖当前六表、Version–Scope 关联、QueryTerm Version snapshot 或幂等保存合同。

### 12.1 数据对象

monitoring_scopes：

- id
- project_id
- scope_type
- canonical_term
- aliases
- include_terms
- exclude_terms
- official_accounts
- seed_urls
- languages
- regions
- platforms
- match_mode
- status
- created_by
- created_at
- updated_at

query_terms：

- id
- scope_id
- term
- normalized_term
- origin
- status
- reason
- source
- score
- conflict_codes
- created_at

workflow_plans：

- id
- project_id
- flow_mode
- status
- current_version_id
- created_by
- created_at
- updated_at

workflow_versions：

- id
- workflow_plan_id
- version_number
- planner_contract_version
- catalog_snapshot_id
- policy_version
- normalized_input
- plan_payload
- preview_fingerprint
- created_by
- created_at

关系与生命周期字段采用仓库现有 UUID、workspace 隔离和时间戳约定。列表字段和冻结 payload 的具体数据库类型在阶段二 migration 计划中依据现有 PostgreSQL 约定确定，不能在实现时静默改变上述语义。

### 12.2 不可变版本

- WorkflowVersion 创建后不允许 update 或 delete。
- 修改 Scope 或 Plan 生成新 version_number。
- normalized_input 与 plan_payload 使用阶段一相同合同。
- preview_fingerprint 与版本绑定。
- current_version_id 只指向已成功保存的版本。
- 版本比较基于 Scope、Query、Route、预算和限制的结构化差异。

### 12.3 状态边界

历史草案曾把阶段二简化为：

    draft -> previewed

当前实现不持久化编辑中的 `draft`；首次显式 Save 直接创建 `previewed` Plan/v1。approved、active、paused、archived 的完整执行语义留给具备授权和 WorkflowRun 的后续 Goal。阶段二不得通过状态名暗示已经激活真实采集。

### 12.4 Migration 与回滚

- 新 migration 必须保持单一 Alembic head。
- upgrade 只创建本 Goal 的表、索引和约束，不回填旧 ExtractionPlan。
- downgrade 必须删除新增对象，或在无法无损回滚时提供明确恢复步骤并先取得用户批准。
- migration 先在本地测试数据库验证 upgrade、downgrade、upgrade。
- 不在未授权的生产或共享数据库执行。

## 13. 安全、可观测性与性能

### 13.1 安全

- Project lookup 始终限定当前 workspace。
- Preview 请求不接受 Secret、token、Cookie 或私钥。
- Seed URL 只解析字符串，不执行 HTTP 请求，避免 SSRF。
- 错误响应不暴露 Catalog 文件路径、凭据状态细节或跨 workspace ID。
- Fixture 与 synthetic verified 数据只能位于测试路径或显式测试配置。

### 13.2 可观测性

结构化日志记录：

- request_id
- project_id
- flow_mode
- planner_contract_version
- catalog_snapshot_id
- policy_version
- preview_fingerprint
- planning_status
- route requirement count
- resolved/held count
- duration_ms

日志不得记录 Secret；用户输入词项只在现有日志政策允许时记录，否则只记数量和哈希。

### 13.3 性能

- 不含 LLM 的 Fixture Preview 本地目标为 p95 小于 3 秒。
- 性能测量不包含 Web build、测试启动和外部网络。
- Catalog Loader 复用现有只读缓存，但测试必须隔离缓存，避免跨用例污染。
- Planner 纯领域步骤不得执行数据库 N+1 查询。

## 14. 测试设计

### 14.1 Schema 与规范化单测

覆盖：

- brand、category、competitor、topic、campaign。
- Unicode、大小写、首尾空白和重复词。
- include/exclude 冲突与排除优先。
- Seed URL 规范化、去重、已知平台分类和 unclassified。
- 全局 default 与 Scope override 规则。
- periodic 最小 Scope/platform 和 batch 最小输入规则。
- topic/campaign Seed-URL-only Scope。
- Scope 与列表数量边界。
- 默认值进入 normalized_input。

### 14.2 Query Compiler 单测

覆盖：

- 品牌 Precision-first。
- 品类 Recall-first。
- Candidate 不进入 active query。
- 相同输入生成相同排序和 query_version。
- 平台编译器缺失生成 limitation/held。
- Fixture 扩展输出 JSON Schema 验证。
- periodic_monitoring.v1 与 batch_research.v1 生成固定 Step、依赖和输出合同。
- Scope/Input 到 content/search_discover、content/resolve_detail、content/monitor_incremental、content/batch_parse 的映射。
- unclassified 和 platform_not_selected 进入 classify_seed_urls 的 held item，不生成伪 Capability Requirement。

### 14.3 Resolver golden tests

至少提供：

1. canonical candidate-only Catalog -> held。
2. synthetic verified Primary + verified Fallback -> resolved。
3. synthetic verified Primary + partial Fallback，allow_partial_degradation=false -> partial 被排除。
4. 相同场景开启 allow_partial_degradation，Required Fields 完整 -> partial 可作为 Fallback。
5. 同分实现按稳定 ID 排序。
6. Policy、Region、Purpose、Required Fields 和 Budget 分别触发排除。
7. Shadow 有合格备用实现时生成，无备用时 disabled。
8. 未设置预算上限时未知成本保持 unknown，且不获得成本评分优势。
9. 设置预算上限时未知成本以 budget_unknown_under_ceiling 排除。
10. required_credentials 为空时派生 not_required。
11. 需要 Credential 且没有 test Snapshot 时以 auth_readiness_not_checked 排除。
12. test-only ready Snapshot 可以生成 resolved route，但 execution_authorized 仍为 false。
13. partial proposed route 必须 approval_required=true，客户端 allow flag 不能变成执行授权。

### 14.4 Fingerprint tests

- 相同输入重复运行得到相同 Fingerprint 与决策内容。
- generated_at、request_id 变化不改变 Fingerprint。
- Scope、Catalog 内容哈希、Policy Version、Query Version 或 Fixture Version 变化必须改变 Fingerprint。
- 输入列表不同顺序但规范化语义相同时得到相同 Fingerprint。
- scope_ref 不同但 Scope 语义相同时得到相同 Fingerprint。
- CapabilityCatalog 只有 generated_at 变化时 catalog_snapshot_id 不变。
- Assertion、Constraint、Evidence 或 Implementation 语义变化时 catalog_snapshot_id 改变。

### 14.5 API Integration

覆盖：

- 当前 workspace Project 成功预览。
- 不存在或跨 workspace Project 返回 404。
- 无效输入返回 422。
- 请求体重复 project_id 或包含其他 extra 字段返回 422。
- held 返回 200。
- archived Project 返回 409。
- Catalog 加载失败返回 503。
- 请求不产生数据库写入或后台任务。
- 响应固定 provider_call=false、actor_run=false、llm_call=false、execution_authorized=false。

### 14.6 Web Unit/Integration

覆盖：

- 两种 mode 的字段差异。
- Project 未选择、切换、同页 CustomEvent、跨标签页 storage 事件和 route-aware applied 状态。
- 简单/高级视图使用同一响应。
- held、partially_resolved、resolved 和技术错误。
- 字段错误焦点。
- 旧请求不能覆盖新 Preview。
- API 失败不回退 Mock。

### 14.7 Mock E2E

Flow A：

    选择 Project
    -> periodic_monitoring
    -> 添加品牌与品类 Scope
    -> 配置平台、语言、地区和周期意图
    -> 生成 Preview
    -> 查看 held 原因
    -> 简单/高级视图 Fingerprint 一致

Flow B：

    选择 Project
    -> batch_research
    -> 输入关键词与 Seed URL
    -> 保留 unclassified URL
    -> 生成 Preview
    -> 查看编译查询和 RoutePlan
    -> 重复生成结果一致

测试专用 resolved Fixture 另行证明 Primary、Fallback 和 Shadow UI，不替代 canonical held 流。

### 14.8 全量回归 Gate

阶段一完成前重新执行：

- API Ruff。
- API mypy。
- API 全量 pytest。
- Web lint。
- Web unit tests。
- Web production build。
- Web full mock E2E。
- git diff --check。

任何失败都必须按失败层级记录，不能通过删除、跳过或弱化测试制造通过。

## 15. 执行分批

### Task 0：Checkpoint 与 Goal 激活门

- 确认 GOAL-V2-02 的独立 checkpoint 或用户批准的等价隔离方式。
- 重新核对 branch、git status、已有修改和基线测试。
- 同步 GOAL-V2-03 的 plan/TODO/Kiro 状态；在代码开始前仍标记未激活。
- 不自动 commit。

### Task 1：Schema 与失败测试

- 建立阶段一请求/响应合同。
- 建立 Scope、Query、Route、Preview 和错误 Fixture。
- 先写会失败的规范化、Compiler、Resolver、Fingerprint 测试。

### Task 2：纯领域 Planner

- 实现 MonitoringScopeNormalizer。
- 实现 QueryTermBuilder 和 Fixture Candidate Adapter。
- 实现 Platform Query Compiler。
- 实现 Policy 与 Capability Resolver。
- 实现 Preview Assembler 和 Fingerprint。

### Task 3：Preview API

- 新增嵌套 Project Preview endpoint。
- 接入 workspace 鉴权和 canonical Catalog。
- 映射 422、404、503 和内部错误。
- 证明零数据库写入。

### Task 4：双模式 Planner UI

- 接入 Project Selector 上下文。
- 实现四步向导。
- 实现简单和高级视图。
- 实现 held、字段错误、技术错误和 stale response。

### Task 5：阶段一集成验收

- 跑两条核心 Flow。
- 跑 resolved synthetic Fixture UI。
- 跑响应式、键盘、性能和全量回归 Gate。
- 更新 API、架构、产品、TODO 和 Kiro 证据。

### Task 6：阶段一 Closeout

- 只在全部 Gate 通过后标记 GOAL-V2-03 phase_1_locally_complete。
- 保留阶段二未授权和 production unchanged。
- 不自动 stage、commit、push 或 deploy。

### Task 7：阶段二独立授权门

- 根据阶段一实际合同生成持久化实施计划。
- 用户明确批准 migration 和持久化范围后才开始。
- 完成 Scope、QueryTerm、Plan、Version、migration 和版本历史验证。
- 阶段二完成后再评估 GOAL-V2-03 locally_complete。

## 16. 完成定义

### 16.1 阶段一完成

必须同时满足：

- 两条核心 Flow 生成完整 WorkflowPlanPreview。
- 相同规范化输入、Catalog Snapshot 和 Policy Version 生成相同 Fingerprint 与决策内容。
- canonical candidate-only 路径返回可解释 held。
- synthetic verified/partial 路径稳定生成 Primary、Fallback 和 Shadow。
- 简单/高级视图一致。
- Project Selector 在 Planner 页面真实应用，其他页面不被虚构。
- API、Web、E2E、响应式和性能 Gate 通过。
- 无数据库写入、migration、外部调用或生产变化。

阶段一边界：

    GOAL-V2-03 phase_1_locally_complete
    database_write=false
    migration_applied=false
    provider_call=false
    actor_run=false
    llm_call=false
    workflow_run_created=false
    production unchanged

### 16.2 整个 Goal 本地完成

只有阶段二额外满足以下条件后才能评估：

- 一个 Project 可以保存多个 MonitoringScope。
- QueryTerm 来源和状态可追溯。
- WorkflowPlan 可以保存并拥有不可变 WorkflowVersion。
- 新版本不会覆盖旧版本。
- migration upgrade、downgrade、upgrade 通过。
- API、数据库集成、Web 版本历史和全量回归通过。
- 仍未发生未授权 WorkflowRun 或 Provider 调用。

## 17. 风险与控制

| 风险 | 控制 |
|---|---|
| GOAL-V2-02 未 checkpoint 时叠加新代码 | Task 0 独立门禁；未授权只写规格和计划 |
| candidate 被误当作可执行能力 | Resolver 状态硬门禁；canonical 路径必须 held |
| synthetic verified Fixture 泄漏产品事实 | 仅测试路径和显式测试配置；禁止写回 Catalog |
| 前后端各自计算路线导致漂移 | 后端单一 Preview 合同；前端只展示 |
| Fingerprint 被时间戳或顺序污染 | 规范化 JSON、固定排序、排除运行时字段 |
| Project Selector 继续只是装饰 | Planner endpoint 使用 project_id 和 workspace lookup；页面明确 applied=true |
| API 失败被 Mock 掩盖 | 产品模式禁止 fallback；Fixture 模式显式开启 |
| Seed URL 触发 SSRF | 阶段一只做字符串解析和分类，不发网络请求 |
| 未知价格显示为免费 | budget_status=unknown，禁止零成本推断 |
| Scope 扩张到 Run、Dataset、VOC | 非目标与完成定义固定边界 |
| 大 Automation Service 继续膨胀 | 新建职责单一 Planner 模块 |
| 阶段一被误报为整个 Goal 完成 | 固定 phase_1_locally_complete 证据标签 |

## 18. 后继状态与边界

1. Phase 1 保持 `phase_1_locally_complete` 历史基线；它的测试计数不替代 Phase Two 任务或完整 gate 的证据。
2. Phase Two 实施计划已经单独获得用户授权，当前状态为 `phase_2_persistence_in_progress`；最新执行断点和证据位于后继设计、实施计划与 `.kiro/plan/*`。
3. 本设计仍不授权 stage、commit、push、deploy、共享/生产数据库、Provider、Actor、LLM、Activate、Run 或 WorkflowRun。
4. 只有后继实施计划的完整本地 exit gate 全部通过，才可评估 `phase_2_persistence_locally_complete`。

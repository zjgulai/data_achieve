---
title: 全社媒自动化数据采集与能力发现平台 V2.0 需求追踪账本
doc_type: traceability_ledger
status: active
created: 2026-07-14
updated: 2026-07-24
owner: self
source_prd: product-prd-social-media-automation-platform-v2.md
audit_baseline_commit: 1209cc2b0cdfcd6bcbc39c81f22df166f7692f6f
evidence_level: L2-local
provider_call: false
database_write: local-test-only
raw_record_write: local-test-only
dataset_write: local-test-only
ci_dispatch: false
production_boundary: production unchanged
---

# V2.0 需求追踪账本

本账本把 V2.0 PRD 的 92 条功能需求、AT-01~10 与 KPI-01~12 映射到当前仓库证据和后续执行批次。`implemented_local` 只表示当前本地合同已有代码与测试，不表示 CI、real API、Provider、部署、生产或 GA 通过。`fixture_only` 不等于真实执行；历史 PRD2 生产证据不自动升级 V2 verdict。

## 2026-07-17 GOAL-V2-03 payload-bound fixture materialization evidence

当前新增 server-registered `workflow_provider_payload.v1`、payload-bound `fixture-primary-payload-v1`、`workflow_lineage_preview.v2` 和 authenticated/idempotent `POST .../materializations`。本地 SQLite 证明一次 WorkflowRun 原子生成 RawRecord、DatasetVersion 和专用 ledger，exact replay 不重复写；历史 unbound Run fail closed。Revision `202607170034` 已仅在精确授权的 `127.0.0.1:55367/local_workflow_lineage_test` 通过 guarded `033→034→033→034`、约束、rollback、ledger/service concurrency `13/13`，cleanup head 034 且六类 lineage/materialization 表均为 0。最新无数据库 API full 为 `976 passed / 72 skipped / 6 warnings`；warnings 来自 1 个既有 passlib deprecation 和 5 个既有 retention 测试的 aiosqlite event-loop-close warnings。Web compatibility 为 `246 passed`，TypeScript、ESLint 与 26-page mock build 通过。Live Provider 尚未实现或授权，因此 `provider_call=false`、`DAT-003=fixture_only`、`production unchanged`。

## 2026-07-22 P0 baseline delta audit

本轮重新核对了 Workflow Execution、Provider/YouTube 本地边界、revision
030/031/034 迁移链和 Web runner。Provider preflight 已在 2026-07-22 接入唯一
server-side application service，但该 service 固定 execution/client/transport
边界为 false，YouTube transport 仍 fail closed；Workflow runtime 仍只允许 fixture 的
`ready -> running -> completed`。因此 RUN-002~005、RUN-007~010、PAD-001/002、
WFL-001、DAT-003 与 AT-03/04/07 的 verdict 不升级。PAD-005 旧的 Task 10
复审待办已由后续 review 和新鲜 API/Alembic 证据覆盖，remaining gate 改为
credential/live client/authorized Provider Run。Web 通过直接 Node runner 取得
`21 files / 264 tests`、TypeScript、ESLint 和 `26/26` Next build；这是
L2-local 兼容性证据，不是 browser/live/production 验收。追踪总数和 verdict
功能需求的全部 `partial/absent/fixture_only` 行已逐条复核；旧汇总存在事实
漂移，完成 UI-008 本地闭环后的实际计数为 `implemented_local=35`、`partial=36`、
`fixture_only=7`、`absent=14`。其中 INS-002 因已有带 Evidence 引用的
fixture VOC 合同调整为 `fixture_only`，INS-007 因已有持久化反馈链调整为
`partial`；两者均未达到 live/GA 证据。

## 2026-07-22 UX-B03 Planner lifecycle boundary delta

Planner 已增加五阶段导航、Review/Save、blocker cause/impact/missing fields/next action、
版本影响和显式生命周期 gate。Save 仍是唯一可执行动作；Approve、Activate、Run
保持 disabled 并说明缺失 transition、runnable Version 与当时的 RUN-04 runtime 合同，不连接
fixture-only WorkflowRun。Focused Web unit `73/73`、TypeScript、目标 ESLint、26-page
build 与 Planner persistence Playwright desktop/mobile `2/2` 通过；1440/375 本地视觉
检查无横向溢出，外部请求为 0。这只补强 WFL-001 的本地 Web code/test anchor，不改变
当时的功能计数：`WFL-001=partial`、`RUN-004=absent`，也不构成 live、Provider、production
或 GA 证据。

## 2026-07-23 RUN-04 state contract delta

Workflow Run 已补齐 `degraded/held/cancelled/empty_valid` 合法 transition 与 Run/Step
状态快照约束。recognized Primary failure 会原子保存 held Run、failed Step、attempts、
关联 blocked FallbackDecision 与幂等 receipt；成功且 0 records 明确进入 `empty_valid`。
Run list/detail 同步展示 cause、impact、missing fields、recovery direction 与 failed/no-receipt
事实，不新增 retry/cancel/live action。Revision 038 仅为 source，未执行 PostgreSQL。
Scoped API `189 passed / 1 warning`、Ruff、Mypy `6 source files`、Web `5 passed`、TypeScript、ESLint、Next
`27/27` build、Alembic sole head 038 通过；1440/480 视觉检查通过，375 受当前 in-app
runner 最小宽度限制未直接补证。RUN-004 与 RUN-009 因本地合同完整升级为
`implemented_local`；最新功能计数为 `implemented_local=39`、`partial=36`、
`fixture_only=7`、`absent=10`，不构成 live、Provider、PostgreSQL、production 或 GA 证据。

## 2026-07-23 RUN-05 and RUN-07 kernel deltas

RUN-005 已增加受 sample budget 约束的 fixture-only Shadow 对账、append-only comparison
Evidence 与只读查询，且数据库约束禁止自动修改 Catalog/ranking。RUN-007 已增加独立的
per-step pagination checkpoint kernel：每个确认页单独提交 cursor chain、output/checkpoint
digest、Evidence 和确定性 side-effect key；跨 AsyncSession 重启从最后确认 cursor 继续，
终态 replay 不调用 executor 或写库，crash-after-effect fixture 测试证明 key 稳定且物理
effect 不重复。两项均升级为 `implemented_local`，当前功能计数为
`implemented_local=41`、`partial=36`、`fixture_only=7`、`absent=8`。

Revision 039/040 均仅为 source，未执行 PostgreSQL。RUN-007 尚未接现有 fixture-run API、
Run 状态机或 Web，live Provider 对 side-effect key 的幂等支持也未证明，因此不构成
产品 resume、live exactly-once、UIX-09、production 或 GA 证据。

## 2026-07-23 RUN-08 budget ledger kernel delta

RUN-008 已增加 immutable `WorkflowBudgetAccount` 与 append-only
`WorkflowBudgetLedgerEntry`：request/item/quota/cost/time 五类上限和 Policy digest
按 execution session 冻结，每个页级 side-effect key 在 RUN-07 executor 前以独立事务
预留。任何维度超限都会先写 blocked entry，再返回 held，且不会发生新的 executor 调用；
crash-after-effect 重启复用原 reservation，不重复计费，终态 replay 也不追加账本。
策略漂移、未知 quota、账本摘要漂移和 checkpoint 缺少 reservation 均 fail closed。
RUN-008 因此升级为 `implemented_local`，当前功能计数为
`implemented_local=42`、`partial=36`、`fixture_only=7`、`absent=7`。

Revision 041 仅为 source，未执行 PostgreSQL。该 kernel 尚未接产品 Run API/状态机、
Provider runtime 或 Web，因此不构成 live cost enforcement、UIX-09、production 或 GA
证据。新增专项 `14 passed`、Workflow scoped `701 passed / 1 warning`、API full
`1187 passed / 73 skipped / 1 warning`、scoped Ruff/Mypy、Alembic sole head 041 通过。

## 2026-07-23 RUN-10 Provider health kernel delta

RUN-010 已增加 append-only `ProviderHealthSnapshot` 与版本化
`ProviderHealthRouteFeedback`。内核只聚合显式传入的结构化 fixture observations，不执行
active probe；样本数、成功率与 p95 latency 生成 unknown/healthy/degraded/unhealthy
状态，observation digest manifest、Policy、Evidence、原因与 snapshot hash chain 均保留。
快照的 routing TTL 短于 Evidence retention：有效快照可对后续候选 baseline score 施加
健康 penalty，过期快照停止改变排序但仍作为反馈原始依据。Feedback 保存原始/调整顺序、
score/snapshot manifest、原因、Evidence 与 version hash chain，固定禁止 Catalog mutation
和 automatic route switch。RUN-010 因此升级为 `implemented_local`，当前功能计数为
`implemented_local=43`、`partial=36`、`fixture_only=7`、`absent=6`。

Revision 042 仅为 source，未执行 PostgreSQL。该 kernel 尚未接产品 Run API/Planner/Web
或 live Provider，因此不构成实时 Provider health、产品选路、UIX-09、production 或 GA
证据。专项 `17 passed`、Workflow/health scoped `718 passed / 1 warning`、API full
`1204 passed / 73 skipped / 7 warnings`、scoped Ruff/Mypy、Alembic sole head 042 通过；
额外 6 warnings 来自既有平台凭证 aiosqlite 退出清理，隔离复跑为 `1 passed / 1 warning`。

## 2026-07-23 WFL-001A fixture product Run gate delta

WFL-001A 新增 write-free `WorkflowFixtureRunGateResponse` 与
`GET /api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}/fixture-run-gate`。
门禁分别核验 active Project、active Plan、requested Version 是否为 current，以及冻结
Version 是否拥有完整 resolved Primary fixture contract；固定返回 blocker、next action
和 Evidence，明确 `active` 不自动等于 runnable。现有 `POST .../fixture-runs` 复用同一
gate，非 active Plan 或非 current Version 会在任何 Run、Step、attempt 或 request ledger
写入前 fail closed。

该子批没有接入 RUN-07/08/10 standalone kernel，没有开放 Planner 生命周期按钮，也没有
live adapter/Provider。WFL-001 继续为 `partial`，功能计数保持
`implemented_local=43`、`partial=36`、`fixture_only=7`、`absent=6`。本地证据为 focused
`98 passed / 1 warning`、Workflow/Provider-health scoped
`745 passed / 62 skipped / 1 warning`、API full
`1211 passed / 73 skipped / 7 warnings`、scoped Ruff/Mypy、traceability
`6 passed`、Alembic sole head `202607230042` 与 `git diff --check`。GitNexus
刷新为 `23,286 nodes / 40,162 edges / 300 flows`，四个本批 gate 核心符号均为
LOW；最新仓库级 `99 changed files / 482 changed symbols / 248 affected items /
CRITICAL` 来自累计 dirty overlay，不归因于 WFL-001A。

## 2026-07-23 UIX-08 Planner lifecycle fixture actions delta

UIX-08 现已在本地 fixture 产品边界完成。Web Planner 消费 current Version 的
write-free gate，并将 Save、Approve、Activate 与 `fixture-primary-v1` Run 拆为四个
显式动作：每一步只在上一服务端回执和最新上下文通过后开放；未保存草稿、错序状态、
非 current Version 或合同 blocker 均 fail closed。状态 transition 只写 Plan lifecycle，
Run action 使用稳定重试幂等键，界面与响应校验均固定 Provider、credential、browser、
LLM 和 live authorization 为 false。

本地证据为 Web 定向 `125/125`、Planner `70/70`、TypeScript、目标 ESLint、Next
`27/27` build；FastAPI status-transition `4 passed`、fixture gate/create 垂直路由
`3 passed`；Planner persistence Playwright desktop/mobile `2/2` 覆盖 1440/375。
本批未注入 API Key，未调用 Provider/网络，未执行 migration、CI、commit、deploy 或
production action。功能需求计数保持 `implemented_local=43`、`partial=36`、
`fixture_only=7`、`absent=6`；`WFL-001` 仍为 partial，因为 durable actor/reason/
CallAudit、Template lifecycle UI、RUN-07/08/10 产品组合与 live adapter 尚未完成。
GitNexus 强制重建为 `23,306 nodes / 40,259 edges / 300 flows`，关键符号均 LOW；
仓库聚合 `99 changed files / 623 changed symbols / 113 affected items / CRITICAL`
来自累计 dirty overlay，不归因于 UIX-08。

## 2026-07-23 UIX-09 Shadow observability delta

RUN-005 的现有只读 Shadow comparison API 已接入 Web Run 详情。默认层展示样本
一致/差异数、缺失必填字段和人工治理建议，implementation IDs、comparison digest 与
Evidence refs 进入折叠诊断层；空列表明确为“没有 Shadow 对比证据”，不得推断等价。
Web 对 Project/Run ownership、fixture read boundary、total、partition、equivalence/
recommendation 一致性以及 Catalog/route mutation=false 进行 fail-closed 校验。

本地证据为 Web focused `7 passed`、full unit `275 passed`、TypeScript、目标 ESLint、
Next `27/27` build；FastAPI Shadow read/approved-route `2 passed / 1 existing warning`；
Playwright CLI 在隔离端口 3107 验证 desktop 差异/诊断、无证据空态与 390px 响应式，
console error 为 0。功能计数保持 `implemented_local=43`、`partial=36`、
`fixture_only=7`、`absent=6`：UIX-09 仍缺 Step Attempt/Fallback 产品 read model，
RUN-07/08/10 仍未组合进产品 Run API/状态机/Web。未开放 retry/resume/cancel/route
switch，未注入 API Key，未调用 Provider/网络，未执行 migration、CI、commit、deploy
或 production action。GitNexus 强制重建为
`23,320 nodes / 40,300 edges / 300 flows`，定向符号均 LOW；仓库聚合
`99 files / 623 symbols / 113 affected items / CRITICAL` 来自累计 dirty overlay。

## 2026-07-24 UIX-09 Attempt/Fallback observability delta

RUN-002/003 的持久化 Evidence 已通过独立只读
`GET .../workflow-runs/{run_id}/attempt-fallback-evidence` 进入产品 Run 详情；没有扩展
upstream impact 为 HIGH 的共享 `WorkflowRunDetailResponse`。严格 mapper 校验连续 attempt
序列、Run/Step/Plan/Version ownership、七段门禁顺序、outcome/approval 一致性及
`switch_executed=false`，业务层显示尝试/重试和备用路线判断，诊断层显示错误码、hash、
implementation、门禁、字段/成本 Evidence 与 digest。空 Fallback 列表明确表示无证据，
不推断可用或自动切换。

FastAPI focused `12 passed / 48 deselected / 1 existing warning`、full
`1217 passed / 73 skipped / 1 warning`，Web focused `8 passed`、full `276 passed`、
TypeScript、目标 ESLint、Next `27/27` build 均通过。Playwright CLI 在 1440 与 390px
viewport（375px client width）验证 held/complete、诊断展开、空态、无 mutation action、
无横向溢出且 console error 为 0。本增量不改变功能需求 verdict/计数；UIX-09 仍缺
RUN-07/08/10 产品组合与 retry/resume/cancel/switch action，也不构成 PostgreSQL、live
Provider、CI、部署、production 或 GA 证据。

## 2026-07-24 UIX-09 Checkpoint/Budget observability delta

RUN-007/008 的 standalone fixture rows 现可通过 tenant-scoped、write-free
`GET .../workflow-runs/{run_id}/checkpoint-budget-evidence` 绑定到产品 Run 详情；没有
新增 resume 或 budget override endpoint。Schema 与 Web mapper 校验 Run/Plan/Version/Step
ownership、分页 cursor chain、checkpoint-reservation 对应、五维累计值、ledger predecessor、
held reason 与固定 false boundary。默认层展示已确认分页/记录、五维用量与暂停原因，
诊断层折叠 cursor、policy/ledger/checkpoint digest 和 Evidence；空态不推断可安全恢复或
预算无限。

FastAPI focused `13 passed / 50 deselected / 1 existing warning`、full
`1223 passed / 73 skipped / 1 warning`，Web focused `9 passed`、full `277 passed`、
TypeScript、ESLint、Next `27/27` build 通过。Playwright CLI 在 1440/390 验证 held 与
not-configured、无 mutation controls、无横向溢出和 console 0 error/0 warning。该增量不
改变功能需求 verdict/计数；RUN-007/008 执行仍是 fixture kernel，revision 040/041 未获
PostgreSQL 验收，也没有 live Provider exactly-once/cost enforcement。UIX-09 下一缺口为
RUN-010 health 产品读层及 retry/resume/cancel/override/switch action。

## 2026-07-24 UIX-09 Provider Health observability delta

RUN-010 的 standalone fixture Evidence 现可通过 tenant-scoped、write-free
`GET .../workflow-runs/{run_id}/provider-health-evidence` 绑定到产品 Run 详情。组合以 frozen
Step route plan 的 Primary/Fallback 顺序为唯一候选来源，只读取匹配 Project/capability/
implementation 的最新快照并重验 version/hash predecessor；routing TTL 依据 `read_at`
明确为 active/expired。Route feedback 只有 original candidate order 与 capability identity
完全一致才呈现，任何结果都不触发 probe、Catalog/current-route mutation 或自动切路。

FastAPI focused `21 passed / 57 deselected / 1 existing warning`、full
`1225 passed / 73 skipped / 1 warning`、scoped Ruff/Mypy，Web focused `10 passed`、full
`278 passed`、TypeScript、ESLint、Next `27/27` build 通过。Playwright 在 1440/390 验证
active/expired/unobserved、只读 feedback、无横向溢出及 console 0 error/0 warning。该增量
不改变功能需求 verdict/计数。GitNexus 刷新为 `23,756 nodes / 41,082 edges / 300 flows`，
定向符号/route LOW；累计 compare-main `100 files / 630 symbols / 113 affected items /
CRITICAL` 是跨批 overlay。RUN-010 仍缺 revision 042 PostgreSQL、Planner/live Provider
与 action/state-machine 接线。UIX-09 下一缺口为统一的只读 Run action gate，所有
retry/resume/cancel/override/switch mutation 保持关闭。

## Verdict 与证据口径

- `implemented_local`：当前需求合同在本地代码和测试层完整。
- `partial`：存在可复用合同或局部实现，但本需求仍缺关键链路。
- `fixture_only`：只有固定样本、Mock、Dry-run 或 readiness 证据。
- `absent`：当前没有满足该需求的 V2 产品合同。
- `external_gate_after_implementation`：本地实现已足以进入外部/试点验收，但该外部门仍未执行。
- `L2-local`、`L2-fixture`、`L2-partial` 与 `none` 不得解释为 L3/L4/GA。

## 功能需求

| requirement_id | priority | current_verdict | evidence_grade | owning_batch | owner | code_anchor | test_anchor | remaining_gate | authorization_boundary | last_reviewed |
|---|---|---|---|---|---|---|---|---|---|---|
| PRJ-001 | P0 | implemented_local | L2-local | GOAL-V2-03 | product+backend | `apps/api/src/data_intelligence_hub/models/project.py` | `apps/api/tests/integration/test_workflow_planner_preview.py` | V2 cross-flow acceptance | local_only | 2026-07-14 |
| PRJ-002 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/models/workflow_plan.py` | `apps/api/tests/postgres/test_workflow_plan_persistence.py` | V2 cross-flow acceptance | local_only | 2026-07-14 |
| PRJ-003 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py` | `apps/api/tests/unit/test_workflow_planner_normalization.py` | V2 cross-flow acceptance | local_only | 2026-07-14 |
| PRJ-004 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend+web | `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py` | `apps/api/tests/integration/test_workflow_planner_preview.py` | V2 cross-flow acceptance | local_only | 2026-07-14 |
| PRJ-005 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/policies.py` | `apps/api/tests/unit/test_workflow_planner.py` | named PRD acceptance | local_only | 2026-07-14 |
| PRJ-006 | P1 | implemented_local | L2-local | GOAL-V2-03 clone/copy slice | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_planner/scope_templates.py`, `apps/web/src/components/workflow-planner/workflow-plan-detail-workspace.tsx` | `apps/api/tests/unit/test_workflow_plan_persistence.py`, `apps/web/tests/unit/workflow-plan-persistence-mock.test.ts` | Scope template copy creates new ID, preserves source Version and leaves canonical Scope unchanged | revision_030_postgres_pending | 2026-07-16 |
| QRY-001 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/normalization.py` | `apps/api/tests/unit/test_workflow_planner_normalization.py` | runtime attribution acceptance | local_only | 2026-07-14 |
| QRY-002 | P0 | fixture_only | L2-fixture | Batch 3 | backend+ai | `apps/api/src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py` | `apps/api/tests/unit/test_workflow_planner.py` | JSON-Schema-gated Kimi/DeepSeek adapter, runtime binding, and authorization; current expansion remains fixture-only | provider_authorization_required | 2026-07-22 |
| QRY-003 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/policies.py` | `apps/api/tests/unit/test_workflow_planner.py` | execution-layer enforcement | local_only | 2026-07-14 |
| QRY-004 | P0 | partial | L2-partial | Batch 3 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/query_compiler.py` | `apps/api/tests/unit/test_workflow_planner_query_compiler.py` | bind validated compiled queries to executable provider adapters; current compiler stops at planning output | local_implementation_required | 2026-07-22 |
| QRY-005 | P0 | partial | L2-partial | Batch 5 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py` | `apps/api/tests/unit/test_workflow_plan_persistence.py` | persist `matched_scope_id` / term / reason on collected result records, not only planning attribution | local_implementation_required | 2026-07-22 |
| QRY-006 | P1 | absent | none | Batch 5 | backend+analytics | — | — | implement per-query contribution and noise statistics; no runtime analytics anchor found | local_implementation_required | 2026-07-22 |
| CAP-001 | P0 | implemented_local | L2-local | GOAL-V2-02 | backend+web | `apps/api/src/data_intelligence_hub/services/capability_matrix.py` | `apps/api/tests/unit/test_capability_matrix.py` | current UI acceptance | local_only | 2026-07-14 |
| CAP-002 | P0 | implemented_local | L2-local | GOAL-V2-01 | backend+web | `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py` | `apps/api/tests/unit/test_capability_catalog.py` | current UI acceptance | local_only | 2026-07-14 |
| CAP-003 | P0 | implemented_local | L2-local | GOAL-V2-01 | backend | `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py` | `apps/api/tests/unit/test_capability_catalog.py` | dynamic governance successor | local_only | 2026-07-14 |
| CAP-004 | P0 | implemented_local | L2-local | GOAL-V2-04B | backend | `apps/api/src/data_intelligence_hub/services/capability_governance/catalog_resolution.py` | `apps/api/tests/unit/test_capability_governance_catalog_threading.py` | deployed Catalog read-model acceptance | local_only | 2026-07-15 |
| CAP-005 | P0 | implemented_local | L2-local | GOAL-V2-01 | backend+web | `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py` | `apps/api/tests/unit/test_capability_catalog.py` | lifecycle governance successor | local_only | 2026-07-14 |
| CAP-006 | P0 | implemented_local | L2-local | GOAL-V2-04B | backend | `apps/api/src/data_intelligence_hub/services/capability_governance/catalog_resolution.py` | `apps/api/tests/unit/test_capability_governance_catalog_threading.py` | deployed route-scoring acceptance | local_only | 2026-07-15 |
| CAP-007 | P0 | implemented_local | L2-local | GOAL-V2-04B | backend | `apps/api/src/data_intelligence_hub/services/capability_governance/verification.py` | `apps/api/tests/integration/test_capability_governance_verification.py` | deployed governor acceptance | local_only | 2026-07-15 |
| CAP-008 | P0 | implemented_local | L2-local | GOAL-V2-02 | backend+web | `apps/api/src/data_intelligence_hub/services/capability_catalog.py` | `apps/web/tests/unit/api-market.test.ts` | dynamic overlay successor | local_only | 2026-07-14 |
| CAP-009 | P0 | partial | L2-partial | Batch 2 | backend+web | `apps/web/src/components/api-market/capability-detail-drawer.tsx` | `apps/web/tests/e2e/main-flows.spec.ts` | verify Evidence-backed capability selection is consumed by Workflow execution; current drawer exposes evidence and scores only | local_implementation_required | 2026-07-22 |
| CAP-010 | P1 | partial | L2-partial | Batch 2 | web | `apps/web/src/components/api-market/capability-comparison-panel.tsx` | `apps/web/tests/unit/capability-market.test.ts` | complete deployed cost, schema, and evidence comparison; current model compares score profile, constraints, and Evidence | local_implementation_required | 2026-07-22 |
| WFL-001 | P0 | partial | L2-partial | GOAL-V2-03 lifecycle + GOAL-V2-05A | backend+web | `apps/api/src/data_intelligence_hub/models/workflow_template.py`, `apps/api/src/data_intelligence_hub/models/workflow_plan.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_run_gate.py`, `apps/api/src/data_intelligence_hub/services/workflow_planner/lifecycle.py`, `apps/api/src/data_intelligence_hub/services/workflow_planner/template_persistence.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/run_gate.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/execution.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/materialization.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/lineage_preview.py`, `apps/api/src/data_intelligence_hub/models/raw_record.py`, `apps/api/src/data_intelligence_hub/models/dataset.py`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx` | `apps/api/tests/unit/test_workflow_execution_eligibility.py`, `apps/api/tests/unit/test_workflow_plan_lifecycle.py`, `apps/api/tests/unit/test_workflow_template_models.py`, `apps/api/tests/unit/test_workflow_template_persistence_sqlite.py`, `apps/api/tests/integration/test_workflow_execution_service.py`, `apps/api/tests/integration/test_workflow_materialization_service.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/api/tests/unit/test_workflow_lineage_preview.py`, `apps/api/tests/postgres_workflow_lineage/` (`13 passed`), `apps/web/tests/unit/workflow-runs.test.ts` | fixture Run now requires an active Plan's current, complete resolved Version and exposes a read-only gate; Template lifecycle UI, Planner gate/action consumption, RUN-07/08/10 composition and live Provider execution remain | local_only + local_fixture_only + postgres_local_test_only | 2026-07-23 |
| WFL-002 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py` | `apps/api/tests/integration/test_workflow_planner_preview.py` | named cross-layer acceptance | local_only | 2026-07-14 |
| WFL-003 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/fingerprint.py` | `apps/api/tests/unit/test_workflow_planner_fingerprint.py` | runtime version binding | local_only | 2026-07-14 |
| WFL-004 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/templates.py` | `apps/api/tests/unit/test_workflow_planner_templates.py` | runtime version binding | local_only | 2026-07-14 |
| WFL-005 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py` | `apps/api/tests/unit/test_workflow_planner_resolver.py` | execution and fallback replay | local_only | 2026-07-14 |
| WFL-006 | P0 | implemented_local | L2-local | GOAL-V2-03 | backend+web | `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py` | `apps/api/tests/unit/test_workflow_planner_schema.py` | degraded-run proof | local_only | 2026-07-14 |
| WFL-007 | P0 | implemented_local | L2-local | GOAL-V2-03 | web | `apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx` | `apps/web/tests/unit/workflow-planner.test.ts` | current visual acceptance | local_only | 2026-07-14 |
| WFL-008 | P1 | implemented_local | L2-local | GOAL-V2-03 clone/copy slice | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`, `apps/web/src/components/workflow-planner/workflow-plan-detail-workspace.tsx` | `apps/api/tests/unit/test_workflow_plan_persistence.py`, `apps/web/tests/unit/workflow-plan-persistence-api.test.ts` | Plan clone creates independent Plan/v1 with source provenance; Version compare remains available | revision_030_postgres_pending | 2026-07-16 |
| RUN-001 | P0 | implemented_local | L2-local | GOAL-V2-05A | backend | `apps/api/src/data_intelligence_hub/services/workflow_execution/execution.py` | `apps/api/tests/integration/test_workflow_execution_service.py`, `apps/api/tests/postgres_workflow_execution` | PostgreSQL evidence is disposable local schema/concurrency only; live Provider execution remains | local_fixture_only | 2026-07-16 |
| RUN-002 | P0 | implemented_local | L2-fixture | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_execution/retry.py`, `apps/api/src/data_intelligence_hub/models/workflow_execution.py`, `apps/api/src/data_intelligence_hub/repositories/workflow_execution.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_attempt_fallback.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/web/src/lib/api/workflow-runs.ts`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx`, `apps/api/alembic/versions/202607220036_workflow_step_attempts.py` | `apps/api/tests/unit/test_workflow_step_retry.py`, `apps/api/tests/unit/test_workflow_step_attempt_models.py`, `apps/api/tests/unit/test_workflow_attempt_fallback_schema.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/web/tests/unit/workflow-runs.test.ts` | bounded retry/attempt ledger and strict product read model are local; revision 036/038 PostgreSQL, live Provider side-effect idempotency and retry action remain | local_fixture_only + revision_036_038_postgres_pending | 2026-07-24 |
| RUN-003 | P0 | implemented_local | L2-fixture | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_execution/fallback.py`, `apps/api/src/data_intelligence_hub/models/workflow_execution.py`, `apps/api/src/data_intelligence_hub/repositories/workflow_execution.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_attempt_fallback.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/web/src/lib/api/workflow-runs.ts`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx`, `apps/api/alembic/versions/202607220037_workflow_fallback_decisions.py` | `apps/api/tests/unit/test_workflow_fallback_gate_replay.py`, `apps/api/tests/unit/test_workflow_fallback_decision_models.py`, `apps/api/tests/unit/test_workflow_attempt_fallback_schema.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/web/tests/unit/workflow-runs.test.ts` | blocked decision is durable and readable with strict seven-gate/field/cost evidence; fresh live evidence, revision 037/038 PostgreSQL and route-switch action remain | local_fixture_only + revision_037_038_postgres_pending | 2026-07-24 |
| RUN-004 | P0 | implemented_local | L2-fixture | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_execution/state_machine.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/execution.py`, `apps/api/src/data_intelligence_hub/models/workflow_execution.py`, `apps/api/alembic/versions/202607230038_workflow_run_state_semantics.py`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx` | `apps/api/tests/unit/test_workflow_execution_state_machine.py`, `apps/api/tests/unit/test_workflow_run_state_semantics.py`, `apps/api/tests/integration/test_workflow_execution_service.py`, `apps/web/tests/unit/workflow-runs.test.ts` | local state contract, durable held/empty-valid read-only UI and 390px viewport with 375px client-width browser proof are complete; product cancel/degraded commands and revision 038 PostgreSQL remain | local_fixture_only + revision_038_postgres_pending | 2026-07-24 |
| RUN-005 | P0 | implemented_local | L2-fixture | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_execution/shadow.py`, `apps/api/src/data_intelligence_hub/models/workflow_execution.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx`, `apps/api/alembic/versions/202607230039_workflow_shadow_comparisons.py` | `apps/api/tests/integration/test_workflow_execution_service.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/api/tests/unit/test_workflow_shadow_models.py`, `apps/api/tests/unit/test_workflow_shadow_migration_source.py`, `apps/web/tests/unit/workflow-runs.test.ts` | fixture-only comparison is retained and readable in Run detail; revision 039 PostgreSQL, live Provider Shadow, product budget composition and governance approval remain | local_fixture_only + revision_039_postgres_pending | 2026-07-23 |
| RUN-006 | P0 | implemented_local | L2-fixture | GOAL-V2-05A | backend | `apps/api/src/data_intelligence_hub/services/workflow_execution/execution.py` | `apps/api/tests/unit/test_workflow_execution_idempotency.py`, `apps/api/tests/postgres_workflow_execution` | Provider side-effect idempotency and live adapters remain | local_fixture_only | 2026-07-16 |
| RUN-007 | P0 | implemented_local | L2-fixture | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_execution/resume.py`, `apps/api/src/data_intelligence_hub/models/workflow_execution.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_checkpoint_budget.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/web/src/lib/api/workflow-runs.ts`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx`, `apps/api/alembic/versions/202607230040_workflow_step_checkpoints.py` | `apps/api/tests/integration/test_workflow_checkpoint_resume.py`, `apps/api/tests/unit/test_workflow_checkpoint_budget_schema.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/web/tests/unit/workflow-runs.test.ts` | checkpoint kernel and strict product read model are local; resume mutation/Run-state integration, revision 040 PostgreSQL and live Provider idempotency remain | local_fixture_only + revision_040_postgres_pending | 2026-07-24 |
| RUN-008 | P0 | implemented_local | L2-fixture | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/services/workflow_execution/budget.py`, `apps/api/src/data_intelligence_hub/models/workflow_execution.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_checkpoint_budget.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/web/src/lib/api/workflow-runs.ts`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx`, `apps/api/alembic/versions/202607230041_workflow_budget_ledger.py` | `apps/api/tests/integration/test_workflow_budget_ledger.py`, `apps/api/tests/unit/test_workflow_checkpoint_budget_schema.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/web/tests/unit/workflow-runs.test.ts` | five-dimensional kernel and strict product read model are local; budget override/Run-state integration, revision 041 PostgreSQL and live Provider cost enforcement remain | local_fixture_only + revision_041_postgres_pending | 2026-07-24 |
| RUN-009 | P0 | implemented_local | L2-fixture | Batch 3 | backend | `apps/api/src/data_intelligence_hub/services/workflow_execution/state_machine.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/execution.py`, `apps/api/alembic/versions/202607230038_workflow_run_state_semantics.py` | `apps/api/tests/unit/test_workflow_run_state_semantics.py`, `apps/api/tests/integration/test_workflow_execution_service.py` | explicit empty_valid producer is fixture-local; revision 038 PostgreSQL and live no-result evidence remain | local_fixture_only + revision_038_postgres_pending | 2026-07-23 |
| RUN-010 | P1 | implemented_local | L2-fixture | Batch 6 | backend+web | `apps/api/src/data_intelligence_hub/models/provider_health.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/health.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_provider_health.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/web/src/lib/api/workflow-runs.ts`, `apps/web/src/components/workflow-execution/workflow-run-history-workspace.tsx`, `apps/api/alembic/versions/202607230042_provider_health_snapshots.py` | `apps/api/tests/integration/test_provider_health_kernel.py`, `apps/api/tests/unit/test_provider_health_models.py`, `apps/api/tests/unit/test_provider_health_migration_source.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/web/tests/unit/workflow-runs.test.ts` | standalone aggregation plus strict latest-snapshot/TTL/exact-feedback product read model are local; action/state-machine integration, revision 042 PostgreSQL and live Provider health remain | local_fixture_only + revision_042_postgres_pending | 2026-07-24 |
| BATCH-001 | P0 | partial | L2-partial | Batch 5 | backend+web | `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py` | `apps/api/tests/integration/test_workflow_planner_preview.py` | execute the normalized mixed keyword and Seed URL inventory; current path produces planning input and diagnostics | local_implementation_required | 2026-07-22 |
| BATCH-002 | P0 | absent | none | Batch 5 | backend | — | — | implement authorized multi-platform search execution; no execution anchor found | provider_authorization_required | 2026-07-22 |
| BATCH-003 | P0 | partial | L2-partial | Batch 5 | backend | `apps/api/src/data_intelligence_hub/services/automation_service.py` | `apps/api/tests/unit/test_automation_service.py` | preserve canonical/share URL relation in the social result contract; existing canonical handling is generic/product-oriented | local_implementation_required | 2026-07-22 |
| BATCH-004 | P0 | partial | L2-partial | Batch 5 | backend | `apps/api/src/data_intelligence_hub/services/workflow_planner/normalization.py` | `apps/api/tests/unit/test_workflow_planner_normalization.py` | route classified and unclassified social links into an executable platform/resource queue; current path only classifies and diagnoses | local_implementation_required | 2026-07-22 |
| BATCH-005 | P0 | absent | none | Batch 5 | backend | — | — | implement and persist per-link Capability Resolver attribution; no resolver anchor found | local_implementation_required | 2026-07-22 |
| BATCH-006 | P0 | partial | L2-partial | Batch 5 | backend+web | `apps/api/src/data_intelligence_hub/services/automation_service.py` | `apps/api/tests/unit/test_automation_service.py` | implement a V2 social field-quality report; current field completeness paths cover product/GitHub/public-content records | local_implementation_required | 2026-07-22 |
| BATCH-007 | P0 | partial | L2-partial | Batch 5 | backend+web | `apps/api/src/data_intelligence_hub/models/dataset.py` | `apps/web/tests/e2e/main-flows.spec.ts` | persist and expose V2 social task-to-Dataset/Plan lineage across execution output | local_implementation_required | 2026-07-22 |
| BRW-001 | P0 | fixture_only | L2-fixture | Batch 1 | backend+web | `apps/api/src/data_intelligence_hub/api/routes/capability_discovery.py` | `apps/web/tests/e2e/capability-discovery.spec.ts` | authorized live-page capture followed by Verification/Publication; current preview declares `browser_run=false` | product_browser_authorization_required | 2026-07-22 |
| BRW-002 | P0 | partial | L2-partial | Batch 3 | backend | `apps/api/src/data_intelligence_hub/models/automation_plan.py` | `apps/api/tests/unit/test_automation_service.py` | execute the persisted public-content job with an explicitly authorized browser session | product_browser_authorization_required | 2026-07-22 |
| BRW-003 | P0 | partial | L2-partial | Batch 2 | backend | `apps/api/src/data_intelligence_hub/services/browser_structure_diagnostic.py` | `apps/api/tests/unit/test_browser_structure_diagnostic.py` | run and retain an authorized DOM/field drift probe; current diagnostic builds from supplied evidence | product_browser_authorization_required | 2026-07-22 |
| BRW-004 | P0 | implemented_local | L2-local | GOAL-V2-04B | backend | `apps/api/src/data_intelligence_hub/models/capability_governance.py` | `apps/api/tests/integration/test_capability_governance_intake.py` | live Browser Evidence acceptance | local_only | 2026-07-15 |
| BRW-005 | P0 | partial | L2-partial | Batch 3 | backend+web | `apps/api/src/data_intelligence_hub/models/automation_plan.py` | `apps/web/tests/unit/browser-diagnostic.test.ts` | persist and enforce browser session scope, artifact retention, and delete approval across execution | owner_authorization_required | 2026-07-22 |
| BRW-006 | P0 | implemented_local | L2-local | prior browser contract | backend | `apps/api/src/data_intelligence_hub/services/browser_structure_diagnostic.py` | `apps/api/tests/unit/test_browser_structure_diagnostic.py` | product-browser runtime acceptance | local_only | 2026-07-14 |
| PAD-001 | P0 | partial | L2-partial | Batch 4 | backend | `apps/api/src/data_intelligence_hub/social_api/contracts.py`, `apps/api/src/data_intelligence_hub/social_api/output_contracts.py`, `apps/api/src/data_intelligence_hub/social_api/provider_preflight.py`, `apps/api/src/data_intelligence_hub/services/provider_execution_preflight.py`, `apps/api/src/data_intelligence_hub/services/disabled_youtube_execution.py`, `apps/api/src/data_intelligence_hub/services/social_provider.py`, `apps/api/src/data_intelligence_hub/social_api/youtube/contracts.py`, `apps/api/src/data_intelligence_hub/social_api/youtube/foundation.py`, `apps/api/src/data_intelligence_hub/social_api/youtube/google_api_client.py`, `apps/api/src/data_intelligence_hub/social_api/reddit/asyncpraw.py` | `apps/api/tests/unit/test_social_provider_adapters.py`, `apps/api/tests/unit/test_platform_adapter_output_contract.py`, `apps/api/tests/unit/test_social_provider_runtime.py`, `apps/api/tests/unit/test_social_provider_credential_sources.py`, `apps/api/tests/unit/test_social_provider_preflight.py`, `apps/api/tests/unit/test_provider_execution_preflight_service.py`, `apps/api/tests/unit/test_disabled_youtube_execution_service.py`, `apps/api/tests/integration/test_social_provider_routes.py` | YouTube/Reddit fixture responses now cross one bounded, evidence-linked, sanitized PlatformAdapter output contract and business services consume only normalized records; remaining social providers and live execution still need the same boundary | local_implementation_required | 2026-07-22 |
| PAD-002 | P0 | partial | L2-partial | GOAL-V2-05B | backend+web | `apps/api/src/data_intelligence_hub/social_api/contracts.py`, `apps/api/src/data_intelligence_hub/social_api/environment_credentials.py`, `apps/api/src/data_intelligence_hub/social_api/environment_composition.py`, `apps/api/src/data_intelligence_hub/social_api/provider_preflight.py`, `apps/api/src/data_intelligence_hub/services/provider_execution_preflight.py`, `apps/api/src/data_intelligence_hub/services/disabled_youtube_execution.py`, `apps/api/src/data_intelligence_hub/services/platform_credentials.py`, `apps/api/src/data_intelligence_hub/api/routes/platform_credentials.py`, `apps/api/src/data_intelligence_hub/models/platform_credential.py`, `apps/web/src/components/settings/platform-credentials-workspace.tsx` | `apps/api/tests/unit/test_social_provider_credential_sources.py`, `apps/api/tests/unit/test_social_provider_environment_composition.py`, `apps/api/tests/unit/test_platform_credentials.py`, `apps/api/tests/unit/test_platform_credential_migration_source.py`, `apps/web/tests/unit/platform-credentials.test.ts`, `apps/web/tests/e2e/platform-credentials.spec.ts` | seven-platform Workspace-scoped encrypted credential entry and status UI are locally complete without secret echo or Provider call; execute revision 035 in an authorized database, bootstrap the deployment-only master key, bind vault references to the secret resolver, then prove credential reachability separately | database_and_credential_authorization_required | 2026-07-22 |
| PAD-003 | P0 | implemented_local | L2-fixture | existing provider readiness | backend | `apps/api/src/data_intelligence_hub/services/social_provider.py` | `apps/api/tests/integration/test_social_provider_routes.py` | live adapter successor | local_only | 2026-07-14 |
| PAD-004 | P0 | partial | L2-fixture | GOAL-V2-05B | backend | `apps/api/src/data_intelligence_hub/social_api/provider_fixture_runtime.py`, `apps/api/src/data_intelligence_hub/social_api/provider_preflight.py` | `apps/api/tests/unit/test_provider_fixture_runtime.py`, `apps/api/tests/unit/test_social_provider_preflight.py` | bounded retry, timeout, cumulative request/quota/cost stop, rolling rate stop, zero-budget success cache, immutable CallAudit repository interface and expiry cleanup are complete against fake transport; connect an authorized live runtime and durable store separately | provider_and_database_authorization_required | 2026-07-22 |
| PAD-005 | P0 | fixture_only | L2-fixture | GOAL-V2-05B | backend | `apps/api/src/data_intelligence_hub/social_api/youtube/foundation.py`, `apps/api/src/data_intelligence_hub/social_api/youtube/compiler.py`, `apps/api/src/data_intelligence_hub/api/routes/social_provider.py`, `apps/api/src/data_intelligence_hub/services/social_provider.py` | `apps/api/tests/unit/test_youtube_read_adapter_foundation.py`, `apps/api/tests/unit/test_social_provider_runtime.py`, `apps/api/tests/integration/test_social_provider_routes.py`, full API `1056 passed / 73 skipped / 1 warning` | YouTube A1 disabled read foundation, quota compiler, fixture normalization and local review are complete; credential reachability, live client, authorized Run and Provider-derived persistence remain | provider_authorization_required | 2026-07-22 |
| PAD-006 | P0 | fixture_only | L2-fixture | Batch 4 | backend | `apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json` | `apps/api/tests/unit/test_capability_catalog.py` | replace fixture inventory with verified per-platform implementation/readiness records | local_implementation_required | 2026-07-22 |
| PAD-007 | P1 | fixture_only | L2-fixture | Batch 1 | backend | `apps/api/src/data_intelligence_hub/services/capability_discovery/parsers.py` | `apps/api/tests/unit/test_capability_discovery_parsers.py` | verify and publish discovered candidates, then bind runtime Provider adapters | provider_authorization_required | 2026-07-22 |
| PAD-008 | P1 | absent | none | Batch 4 | architecture+security | — | — | select, license-review, security-review, and approve a self-host plugin; no implementation anchor found | owner_authorization_required | 2026-07-22 |
| DAT-001 | P0 | partial | L2-partial | Batch 4 | backend | `apps/api/src/data_intelligence_hub/models/raw_record.py`, `apps/api/src/data_intelligence_hub/schemas/social_provider.py` | `apps/api/tests/integration/test_social_provider_routes.py` | persist `social_raw.v1` with provider/endpoint lineage; current social raw contract is fixture preview and write-disabled | local_implementation_required | 2026-07-22 |
| DAT-002 | P0 | partial | L2-partial | Batch 4 | backend | `apps/api/src/data_intelligence_hub/models/entity.py`, `apps/api/src/data_intelligence_hub/schemas/social_provider.py` | `apps/api/tests/integration/test_social_provider_routes.py` | persist formal Post/Comment/Creator/Topic objects; current versioned normalized items are preview-only | local_implementation_required | 2026-07-22 |
| DAT-003 | P0 | fixture_only | L2-fixture+postgres | GOAL-V2-03 materialization | backend | `apps/api/src/data_intelligence_hub/services/workflow_execution/materialization.py`, `apps/api/src/data_intelligence_hub/api/routes/workflow_runs.py`, `apps/api/src/data_intelligence_hub/models/raw_record.py`, `apps/api/src/data_intelligence_hub/models/dataset.py`, `apps/api/alembic/versions/202607170034_workflow_lineage_materialization.py`, `scripts/verify-workflow-lineage-migration.sh` | `apps/api/tests/integration/test_workflow_materialization_service.py`, `apps/api/tests/integration/test_workflow_execution_routes.py`, `apps/api/tests/integration/test_workflow_execution_boundaries.py`, `apps/api/tests/postgres_workflow_lineage/` (`13 passed`) | Payload-bound fixture RawRecord/DatasetVersion lineage is accepted locally; add live Provider adapter and full Provider/Evidence acceptance | postgres_accepted_local_test_only + provider_authorization_required | 2026-07-22 |
| DAT-004 | P0 | partial | L2-partial | Batch 4 | backend | `apps/api/src/data_intelligence_hub/models/raw_record.py` | `apps/api/tests/unit/test_automation_service.py` | add observation identity and dedup/replay relations for persisted social records | local_implementation_required | 2026-07-22 |
| DAT-005 | P0 | partial | L2-partial | Batch 4 | privacy+backend | `apps/api/src/data_intelligence_hub/schemas/social_provider.py` | `apps/api/tests/unit/test_social_provider_runtime.py` | persist the effective hashed/dropped/retained policy and approval; preview currently fail-closes retained authors to hashed | owner_authorization_required | 2026-07-22 |
| DAT-006 | P0 | partial | L2-partial | Batch 4 | product+backend | `apps/api/src/data_intelligence_hub/schemas/capability_catalog.py` | `apps/api/tests/unit/test_capability_catalog.py` | enforce sensitive-field default-disabled behavior in route and UI, not only catalog metadata | local_implementation_required | 2026-07-22 |
| DAT-007 | P0 | partial | L2-partial | Batch 5 | backend | `apps/api/src/data_intelligence_hub/models/dataset.py`, `apps/api/src/data_intelligence_hub/schemas/workflow_lineage.py` | `apps/api/tests/unit/test_workflow_lineage_preview.py` | extend fixture lineage to live Workflow/Provider/RawRecord field-level lineage | local_implementation_required | 2026-07-22 |
| DAT-008 | P1 | absent | none | Batch 5 | backend+analytics | — | — | implement cross-provider alignment with confidence and source IDs; no contract anchor found | local_implementation_required | 2026-07-22 |
| INS-001 | P0 | partial | L2-partial | Batch 5 | backend | `apps/api/src/data_intelligence_hub/models/signal.py` | `apps/api/tests/unit/test_signals.py` | add explicit MonitoringScope/WorkflowVersion lineage to V2 Signal; current Signal remains project/entity-oriented | local_implementation_required | 2026-07-22 |
| INS-002 | P0 | fixture_only | L2-fixture | Batch 5 | backend+analytics | `apps/api/src/data_intelligence_hub/schemas/social_provider.py`, `apps/api/src/data_intelligence_hub/services/social_provider.py` | `apps/api/tests/unit/test_social_provider_runtime.py` | persist formal VOC objects and Evidence refs; current `social_voc_item.v1` is fixture normalization only | local_implementation_required | 2026-07-22 |
| INS-003 | P0 | partial | L2-partial | Batch 5 | analytics+web | `apps/api/src/data_intelligence_hub/models/workflow_plan.py` | `apps/api/tests/unit/test_workflow_plan_persistence.py` | produce and expose separate brand/category/competitor output tracks | local_implementation_required | 2026-07-22 |
| INS-004 | P0 | partial | L2-partial | Batch 5 | backend+web | `apps/api/src/data_intelligence_hub/api/routes/reports.py` | `apps/web/tests/e2e/main-flows.spec.ts` | implement a formal V2 Brief Preview bound to social Evidence lineage | local_implementation_required | 2026-07-22 |
| INS-005 | P0 | partial | L2-partial | Batch 5 | backend+ai | `apps/api/src/data_intelligence_hub/schemas/social_provider.py` | `apps/api/tests/unit/test_social_provider_runtime.py` | add a unified publish-blocking JSON Schema gate; current versioned preview schemas do not govern publication | local_implementation_required | 2026-07-22 |
| INS-006 | P0 | partial | L2-partial | Batch 5 | governance+backend | `apps/api/src/data_intelligence_hub/services/social_provider.py` | `apps/api/tests/unit/test_social_provider_runtime.py` | freeze insight policy and its approval against WorkflowVersion before execution/publication | local_implementation_required | 2026-07-22 |
| INS-007 | P1 | partial | L2-partial | Batch 5 | backend+web | `apps/api/src/data_intelligence_hub/models/intelligence.py`, `apps/api/src/data_intelligence_hub/api/routes/intelligence.py`, `apps/web/src/components/intelligence/intelligence-workspace.tsx` | `apps/api/tests/integration/test_sources_tasks.py` | emit and aggregate KPI events from persisted useful/not-useful/false-positive feedback | local_implementation_required | 2026-07-22 |
| UI-001 | P0 | implemented_local | L2-local | GOAL-V2-02 | web | `apps/web/src/components/layout/navigation.ts` | `apps/web/tests/unit/navigation.test.ts` | current visual acceptance | local_only | 2026-07-14 |
| UI-002 | P0 | partial | L2-partial | Batch 3+5 | product+web | `apps/web/src/components/dashboard/workflow-planner-entry-cards.tsx`, `apps/web/src/components/dashboard/dashboard-overview.tsx` | `apps/web/tests/e2e/main-flows.spec.ts` | two-primary-job IA and Dashboard outcome hierarchy are local-complete; implement the executable keyword/link batch job before closing the requirement | local_implementation_required | 2026-07-22 |
| UI-003 | P0 | partial | L2-partial | Batch 3 | product+web | `apps/web/src/components/dashboard/dashboard-overview.tsx`, `apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx` | `apps/web/tests/unit/dashboard-presentation.test.ts`, `apps/web/tests/unit/workflow-planner.test.ts` | Dashboard engineering details now default to Advanced; hide engineering terms across remaining planner states and validation messages | local_implementation_required | 2026-07-22 |
| UI-004 | P0 | implemented_local | L2-local | GOAL-V2-02 | web | `apps/web/src/components/api-market/api-market-workspace.tsx` | `apps/web/tests/unit/api-market.test.ts` | current visual acceptance | local_only | 2026-07-14 |
| UI-005 | P0 | implemented_local | L2-local | GOAL-V2-02 | web | `apps/web/src/components/api-market/capability-matrix-view.tsx` | `apps/web/tests/e2e/main-flows.spec.ts` | current visual acceptance | local_only | 2026-07-14 |
| UI-006 | P0 | implemented_local | L2-local | GOAL-V2-02 | web | `apps/web/src/components/api-market/capability-detail-drawer.tsx` | `apps/web/tests/e2e/main-flows.spec.ts` | current visual acceptance | local_only | 2026-07-14 |
| UI-007 | P0 | implemented_local | L2-local | GOAL-V2-03 | web | `apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx` | `apps/web/tests/unit/workflow-planner.test.ts` | current visual acceptance | local_only | 2026-07-14 |
| UI-008 | P0 | implemented_local | L2-local | UX-B02 | web | `apps/web/src/components/layout/project-selection-provider.tsx`, `apps/web/src/components/intelligence/intelligence-workspace.tsx`, `apps/web/src/components/intelligence/intelligence-detail-workspace.tsx`, `apps/web/src/lib/intelligence-navigation.ts`, `apps/web/src/lib/project-selection.ts` | `apps/web/tests/unit/intelligence-navigation.test.ts`, `apps/web/tests/unit/project-selection.test.ts`, `apps/web/tests/e2e/main-flows.spec.ts` | local contract complete: Project/Scope/filters/Intelligence/Evidence survive list-detail-back; complete CI/release acceptance with UI-009/010 | local_only | 2026-07-22 |
| UI-009 | P0 | partial | L2-partial | Batch 6 | web+qa | `apps/web/src/components/api-market/capability-discovery-workspace.tsx` | `apps/web/tests/e2e/capability-discovery.spec.ts` | complete 375/1440 viewport acceptance for every remaining V2 critical flow; current coverage is route-specific | local_implementation_required | 2026-07-22 |
| UI-010 | P1 | partial | L2-partial | Batch 6 | web+qa | `apps/web/src/components/api-market/capability-discovery-workspace.tsx` | `apps/web/tests/e2e/capability-discovery.spec.ts` | add automated accessibility scans for all critical flows; current tests are interaction-focused | local_implementation_required | 2026-07-22 |
| GOV-001 | P0 | absent | none | Batch 3+6 | backend+governance | — | — | implement auditable auto-approval over verified capability, credential readiness, and policy gate; no contract anchor found | database_authorization_required | 2026-07-22 |
| GOV-002 | P0 | partial | L2-partial | Batch 3+6 | backend+governance | `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py` | `apps/api/tests/unit/test_workflow_planner.py` | persist approval state transitions, actor, timestamp, and reasons; current approval facts are planning output | database_authorization_required | 2026-07-22 |
| GOV-003 | P0 | partial | L2-fixture | GOAL-V2-05B | backend | `apps/api/src/data_intelligence_hub/social_api/provider_fixture_runtime.py`, `apps/api/src/data_intelligence_hub/social_api/provider_preflight.py` | `apps/api/tests/unit/test_provider_fixture_runtime.py` | immutable draft/terminal CallAudit contracts and an injected async repository interface are locally proven with an in-memory fake; add the durable model, migration, authorized runtime writes and retention enforcement | database_authorization_required | 2026-07-22 |
| GOV-004 | P0 | partial | L2-partial | Batch 6 | backend+privacy | `apps/api/src/data_intelligence_hub/schemas/social_provider.py` | `apps/api/tests/unit/test_social_provider_runtime.py` | freeze and enforce retention/delete policy by WorkflowVersion; current approval templates are not execution policy records | owner_authorization_required | 2026-07-22 |
| GOV-005 | P0 | implemented_local | L2-local | GOAL-V2-01~03 | backend+governance | `apps/api/src/data_intelligence_hub/services/social_provider.py` | `apps/api/tests/integration/test_social_provider_routes.py` | authorized live successor | local_only | 2026-07-14 |
| GOV-006 | P0 | partial | L2-partial | Batch 6 | release+governance | `docs/workflows/workflow-release-rollback-stable.md` | — | implement and exercise a scoped production authorization control plane; current artifact is documentation only | production_authorization_required | 2026-07-22 |

## Acceptance Scenarios

| acceptance_id | current_verdict | evidence_grade | owning_batch | owner | evidence_anchor | remaining_gate | authorization_boundary | last_reviewed |
|---|---|---|---|---|---|---|---|---|
| AT-01 | partial | L2-partial | GOAL-V2-03+05A | product+qa | `apps/api/tests/integration/test_workflow_planner_preview.py`, `apps/api/tests/integration/test_workflow_execution_service.py` | complete Project→Scope→Query→Plan→Run with product Run UI and authorized live execution | local_fixture_only | 2026-07-22 |
| AT-02 | partial | L2-partial | Batch 5 | product+qa | `apps/api/tests/integration/test_workflow_planner_preview.py`, `apps/api/tests/unit/test_social_provider_runtime.py` | connect keyword/link normalization, dedupe, parsing, persistence, and lineage into one Dataset E2E | local_implementation_required | 2026-07-22 |
| AT-03 | fixture_only | L2-fixture | GOAL-V2-05A | backend+qa | `apps/api/tests/integration/test_workflow_execution_boundaries.py`, `apps/api/tests/unit/test_workflow_execution_state_machine.py`, `apps/api/tests/integration/test_workflow_execution_service.py` | fixture held/fallback audit is durable; authorized live degraded producer, product cancellation and PostgreSQL evidence remain | fixture_only | 2026-07-23 |
| AT-04 | fixture_only | L2-fixture | GOAL-V2-05A | backend+qa | `apps/api/tests/integration/test_workflow_execution_boundaries.py` | Shadow sample/equivalence/route feedback remains deferred | fixture_only | 2026-07-22 |
| AT-05 | fixture_only | L2-fixture | Batch 1 | backend+web+qa | `apps/web/tests/e2e/capability-discovery.spec.ts` | authorized TikHub/Apify page capture plus Verification/Publication successor | product_browser_authorization_required | 2026-07-22 |
| AT-06 | implemented_local | L2-local | GOAL-V2-04B | backend+web+qa | `apps/api/tests/integration/test_capability_governance_verification.py` | deployed governor and production acceptance | local_only | 2026-07-15 |
| AT-07 | fixture_only | L2-fixture | GOAL-V2-05B | backend+qa | `apps/api/tests/unit/test_youtube_read_adapter_foundation.py`, `apps/api/tests/integration/test_social_provider_routes.py`, `apps/api/tests/unit/test_social_provider_preflight.py` | Disabled A1 compile/quota/normalize/preflight proof only; credential reachability, live client, authorized Run, Provider-derived RawRecord and cleanup remain | provider_authorization_required | 2026-07-22 |
| AT-08 | fixture_only | L2-fixture+local-foundation | Batch 4 | backend+qa | `apps/api/src/data_intelligence_hub/social_api/reddit/contracts.py`, `apps/api/src/data_intelligence_hub/social_api/reddit/official_transport.py`, `apps/api/src/data_intelligence_hub/services/disabled_reddit_execution.py`, `apps/api/tests/unit/test_social_provider_adapters.py`, `apps/api/tests/unit/test_reddit_official_transport.py`, `apps/api/tests/unit/test_disabled_reddit_execution_service.py` | Local refresh-token OAuth foundation now fixes purpose, read-only scope, bounded retention, delete-on-expiry policy, minimized output and a separate default-disabled live boundary; complete an independently authorized Reddit run with Provider Evidence and actual persisted-data cleanup proof | provider_authorization_required | 2026-07-22 |
| AT-09 | partial | L2-partial | Batch 5 | product+qa | `apps/web/tests/e2e/main-flows.spec.ts`, `apps/api/tests/unit/test_social_provider_runtime.py` | persist V2 VOC/Brief and prove every conclusion reaches Provider-derived RawRecord Evidence | local_implementation_required | 2026-07-22 |
| AT-10 | partial | L2-partial | Batch 6 | web+qa | `apps/web/tests/e2e/main-flows.spec.ts` | complete WorkflowRun mobile-state viewport and automated accessibility acceptance | local_implementation_required | 2026-07-22 |

## KPI

| kpi_id | current_verdict | evidence_grade | owning_batch | owner | evidence_anchor | remaining_gate | authorization_boundary | last_reviewed |
|---|---|---|---|---|---|---|---|---|
| KPI-01 | external_gate_after_implementation | L2-local | Batch 6 | product+qa | `apps/web/src/app/automation/planner/page.tsx` | measure pilot median time-to-first-plan at no more than 10 minutes | pilot_authorization_required | 2026-07-22 |
| KPI-02 | partial | L2-partial | Batch 3+6 | product+analytics | `apps/api/src/data_intelligence_hub/models/workflow_plan.py` | define activation/save event semantics and pilot instrumentation for the 60% target | local_implementation_required | 2026-07-22 |
| KPI-03 | absent | none | Batch 3+6 | product+analytics | — | implement valid-WorkflowRun and weekly-active-project instrumentation; no KPI anchor found | local_implementation_required | 2026-07-22 |
| KPI-04 | partial | L2-partial | Batch 5+6 | product+analytics | `apps/web/tests/e2e/main-flows.spec.ts`, `apps/api/src/data_intelligence_hub/models/intelligence.py` | measure that 100% of insights resolve through Evidence to source records | local_implementation_required | 2026-07-22 |
| KPI-05 | partial | L2-partial | Batch 5+6 | product+analytics | `apps/api/src/data_intelligence_hub/models/intelligence.py`, `apps/api/src/data_intelligence_hub/api/routes/intelligence.py` | aggregate processed-alert feedback and run the authorized two-week pilot for the 60% target | pilot_authorization_required | 2026-07-22 |
| KPI-06 | partial | L2-partial | Batch 3+6 | backend+analytics | `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py` | expose and measure route/constraint explanation on 100% of WorkflowRuns | local_implementation_required | 2026-07-22 |
| KPI-07 | partial | L2-partial | Batch 4+6 | backend+analytics | `apps/api/src/data_intelligence_hub/services/workflow_execution/lineage_preview.py` | extend fixture lineage to all persisted standard objects and measure 100% coverage | local_implementation_required | 2026-07-22 |
| KPI-08 | partial | L2-partial | Batch 3+6 | governance+analytics | `apps/api/src/data_intelligence_hub/services/social_provider.py`, `apps/api/src/data_intelligence_hub/services/workflow_execution/budget.py` | wire the local durable budget kernel into product/live runtime and instrument zero breaches; Provider integration and KPI telemetry remain | local_implementation_required | 2026-07-23 |
| KPI-09 | partial | L2-partial | Batch 3+6 | backend+analytics | `apps/api/tests/postgres/test_workflow_plan_persistence.py`, `apps/api/tests/postgres_workflow_execution/` | instrument all real side effects and prove zero duplicates beyond local fixture persistence | local_implementation_required | 2026-07-22 |
| KPI-10 | implemented_local | L2-local | GOAL-V2-03 | backend+qa | `apps/api/tests/unit/test_workflow_planner_fingerprint.py` | deployed/canary confirmation | local_only | 2026-07-14 |
| KPI-11 | absent | none | Batch 6 | release+analytics | — | implement scheduled runtime freshness telemetry and run an authorized seven-day Canary; no KPI anchor found | production_authorization_required | 2026-07-22 |
| KPI-12 | partial | L2-partial | Batch 4+6 | security+qa | `apps/api/tests/unit/test_social_provider_runtime.py` | add product-wide secret scanning and production monitoring for zero plaintext credential events | production_authorization_required | 2026-07-22 |

## 当前汇总

- 功能需求：92，`implemented_local=43`、`partial=36`、`fixture_only=7`、`absent=6`；DAT-003 与 INS-002 保持 `fixture_only`，WFL-001 与 INS-007 为 `partial`。WFL-001A 已让 fixture Run 写入口复用 active/current/complete Version gate，UIX-08 也已让 Planner 按回执依次开放 Save/Approve/Activate/fixture Run；durable governance、Template lifecycle 和 live adapter 仍缺失。RUN-002/003 Attempt/Fallback、RUN-007/008 Checkpoint/Budget 与 RUN-010 Provider Health Evidence 已进入独立只读产品层，RUN-004/005/009/010 也已补齐相应本地 fixture state、Shadow、empty-valid 与 Provider health 合同；但 revision 036~042 的新增链未获得本批 PostgreSQL 验收，RUN-007/008/010 仍缺 mutation/state-machine 接线，且没有 live Provider 幂等、成本或健康执行证据，因此不升级 live/GA verdict。
- 验收场景：AT-01 已新增本地 Fixture Run、只读 Run history UI 与 non-materialized lineage preview，但仍未完成 live/持久化链路；AT-03/04 仍为 fixture_only；AT-05 没有 live-page capture；AT-06 已有 reviewer/time/Evidence/Verified/Publication 的 L2-local 证据。其余场景仍为 partial、fixture_only 或 absent。
- KPI：只有 KPI-10 有本地确定性合同证据；KPI-05 已有反馈采集但没有聚合/试点，KPI-07/08 只有 fixture/预执行局部合同；其余仍需实现、仪表或试点/生产门。
- 当前 CI 工作流变更只关闭通用 external-write real E2E 路径；`ci_dispatch=false`，没有远端 CI 通过证据。
- Route A 单独完成时只允许把 BRW-001、PAD-007、AT-05 等更新到 Fixture/local Preview 层；GOAL-V2-04B 的独立 PostgreSQL 与 full local gate 已于 2026-07-15 通过，才允许把 CAP-004、CAP-006、CAP-007、BRW-004 与 AT-06 升级到 L2-local。
- GOAL-V2-04A 与 GOAL-V2-04B 当前均本地完成，但 live-page capture、Provider execution、CI、部署、生产 governor bootstrap 和 GA 仍未通过。
- GOAL-V2-05A Task 13 已在唯一授权的 `127.0.0.1:55367/local_workflow_execution_test` 通过 `028→029→028→029` 与 PostgreSQL `14 passed`；cleanup head 为 `202606110029`，`workflow_runs`、`step_runs`、`workflow_run_requests` 均为 0。后续 Web Run history local gate 为 focused `15 passed`、full unit `246 passed`、TypeScript/ESLint/static build 通过。该证据只证明 disposable local fixture schema/concurrency 与只读 UI regression，不证明 Provider、Fallback、Shadow、RawRecord/Dataset lineage、live execution、CI、部署或 GA。

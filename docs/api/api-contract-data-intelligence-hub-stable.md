---
title: Data Intelligence Hub API 合同
doc_type: api
module: api
topic: data-intelligence-hub
status: stable
created: 2026-06-14
updated: 2026-07-24
owner: self
source: human+ai
---

# Data Intelligence Hub API 合同

## 基础规则

Base URL：

| 环境 | URL |
|---|---|
| 本地 API | `http://localhost:8000` |
| 生产 API | `https://scrapy.lute-tlz-dddd.top` |

通用规则：

1. 所有业务接口以 `/api` 开头。
2. 认证使用 HttpOnly cookie `access_token`。
3. 登录、注册以外的业务接口都要求当前用户和当前 workspace。
4. 早期资源列表接口多返回 JSON array；Automation 与 Dataset 类接口返回带 `items`、`total` 和状态标记的 response object。
5. 创建接口成功通常返回 `200` 或 `201`，以实际 route 声明为准。
6. 未认证返回 `401`，无权限或跨 workspace 资源不可见。
7. 生产环境 cookie 必须启用 secure。
8. 本文件是技术合同，endpoint、schema 和 response model 名称保留英文；面向用户页面应使用“采集任务、数据集版本、清洗计划、试跑”等中文业务文案。

## Auth

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/auth/register` | `email`、`password`、`name` | `AuthSessionResponse` | 创建用户、workspace、owner membership，并设置 cookie |
| `POST` | `/api/auth/login` | `email`、`password` | `AuthSessionResponse` | 设置 cookie |
| `POST` | `/api/auth/logout` | 无 | `204` | 清除 cookie |
| `GET` | `/api/auth/me` | 无 | `AuthSessionResponse` | 返回当前用户与 workspace |

## Health

| 方法 | 路径 | 响应 | 说明 |
|---|---|---|---|
| `GET` | `/api/health` | `service`、`environment`、`status`、`database`、`scheduler_enabled` | 生产健康检查入口 |

## Project

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/projects` | query: `domain`、`status` | `ProjectResponse[]` |
| `POST` | `/api/projects` | `name`、`description?`、`domain` | `ProjectResponse` |
| `GET` | `/api/projects/{project_id}` | 无 | `ProjectResponse` |
| `PATCH` | `/api/projects/{project_id}` | `name?`、`description?`、`domain?`、`status?` | `ProjectResponse` |
| `DELETE` | `/api/projects/{project_id}` | 无 | `ProjectResponse` |

允许的 `domain`：

```text
osint, ecommerce, social, competitor, mixed
```

## Workflow Planner（GOAL-V2-03）

当前执行状态为 `payload_bound_fixture_materialization_postgres_accepted_live_provider_pending`。Phase One 的 Project-scoped write-free Preview 合同保持不变；Phase Two 在同一 Project/Workspace 边界内增加显式 Save、不可变 Version、历史、Compare、Template Revision、Plan instantiation、fixture-only WorkflowRun、lineage-preview v2 与 payload-bound local materialization。Revision-034 已完成 exact disposable PostgreSQL acceptance；该状态仍不代表 live Provider、real API、共享/生产数据库、部署或产品执行验收。以下 Preview 小节记录仍受保护的 Phase One 合同。

### Phase One Preview（保持 write-free）

| 方法 | 路径 | 请求 | 响应 | 副作用边界 |
|---|---|---|---|---|
| `POST` | `/api/projects/{project_id}/workflow-plans/preview` | `PlanningInput` | `WorkflowPlanPreview` | 只读 active Project 与 canonical Capability Catalog；不保存、不激活、不运行 |

### 请求合同

`PlanningInput` 禁止 extra 字段，`project_id` 只来自 URL path。请求体包含：

```text
flow_mode=periodic_monitoring|batch_research
scopes[]: MonitoringScopeDraft
default_languages[]
default_regions[]
default_platforms[]
schedule_intent?
delivery_intent?
policy_profile=market_monitoring_balanced
purpose
required_fields[]
optional_fields[]
budget_ceiling?
rate_limit_intent?
retention_intent?
allow_partial_degradation=false
```

`MonitoringScopeDraft` 包含 `scope_ref`、`scope_type`、`canonical_term?`、`aliases[]`、`include_terms[]`、`exclude_terms[]`、`official_accounts[]`、`seed_urls[]`、`languages[]`、`regions[]`、`platforms[]` 和 `match_mode?`。服务端生成 `scope_key`；请求体提交 `project_id`、`scope_key`、readiness snapshot 或其他未知字段返回 `422`。

模式约束：

1. `periodic_monitoring` 必须有 `schedule_intent`，每个 Scope 必须有声明平台或可分类 Seed URL。
2. `batch_research` 不接受 `schedule_intent`，至少包含关键词、账号或 Seed URL 输入。
3. Seed URL 只做字符串规范化和已知 host 分类，不发送 HTTP 请求；unclassified URL 保留在 diagnostics。

### 响应合同

`WorkflowPlanPreview` 返回同一份后端事实，至少包括：

```text
schema_version=workflow_plan_preview.v1
planner_contract_version
project_id
flow_mode
planning_status=resolved|partially_resolved|held
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
generated_at
request_id
```

响应边界固定为：

```text
execution_authorized=false
provider_call=false
actor_run=false
browser_run=false
llm_call=false
workflow_run_created=false
database_write=false
```

canonical Catalog 当前只有 candidate Assertion，因此正常产品请求可以返回 `200` + `planning_status=held`；`held` 不是 HTTP 错误。Primary、Fallback、Shadow 和 partial 路线由 test-only synthetic Fixture 验证，不写入 canonical Catalog，也不代表真实执行就绪。

### Project read path 与错误

1. Route 复用 AuthContext，并以当前 workspace 限定 `get_active_project_or_raise()`；Project 不存在或跨 workspace 不可见都返回 `404`。
2. archived/inactive Project 返回 `409`，detail 为 `project_not_active`。
3. FastAPI/Pydantic 在进入 handler 前拒绝的 request-schema 错误返回框架原生 `422`；该路径不经过 Preview route，不能保证存在 route 追加的 `X-Request-ID`。
4. 已进入 route 后由 normalizer 抛出的 `WorkflowPlannerInputError` 返回 `422`，detail 保留可映射到表单控件的 `loc`、`msg` 与 `type`，并携带 `X-Request-ID`。
5. Capability Catalog 或 Planner dependency 不可用返回 `503`。
6. 未分类内部错误返回 `500`，detail 为安全错误码。成功响应以及 route 内映射的 `404`、`409`、normalizer `422`、`500`、`503` 均携带 `X-Request-ID`；这不泛化到 handler 前的框架校验错误。
7. Preview 路径不调用 create/update/delete/flush/commit，不创建后台任务；现有集成测试以 SQL capture 和全表计数锁定 0 写入。

### Phase Two persistence/versioning 与 Plan lifecycle（本地实现）

下列两个 POST 是 WorkflowPlan 持久化写入口；它们不创建执行、调度或 WorkflowRun：

| 方法 | 路径 | 必填输入 | 响应 | 语义 |
|---|---|---|---|---|
| `POST` | `/api/projects/{project_id}/workflow-plans` | `Idempotency-Key`、`WorkflowPlanCreateRequest` | `WorkflowPlanSaveResponse` | 创建 Plan 与 v1，或返回语义 no-op/replay |
| `POST` | `/api/projects/{project_id}/workflow-plans/{plan_id}/versions` | `Idempotency-Key`、`WorkflowVersionCreateRequest` | `WorkflowPlanSaveResponse` | 为既有 Plan 创建后续不可变 Version，或返回语义 no-op/replay |
| `POST` | `/api/projects/{project_id}/workflow-plans/{plan_id}/clone` | `Idempotency-Key`、`WorkflowPlanCloneRequest` | `WorkflowPlanCloneResponse` | 复制指定冻结 Version 为独立 Plan/v1，保留 source Plan/Version provenance |
| `POST` | `/api/projects/{project_id}/monitoring-scopes/{scope_id}/copy` | `Idempotency-Key`、`MonitoringScopeTemplateCopyRequest` | `MonitoringScopeTemplateCopyResponse` | 复制为独立 Scope template draft，不插入重复 canonical Scope |
| `POST` | `/api/projects/{project_id}/workflow-plans/{plan_id}/status-transition` | `WorkflowPlanTransitionRequest` | `WorkflowPlanTransitionResponse` | 按 expected status 执行受限生命周期转换；不创建 Run |

`WorkflowPlanCreateRequest` 只接受 `name`（trim 后 `1..200`）、`preview_input` 和 `expected_preview_fingerprint`；`WorkflowVersionCreateRequest` 只接受 `preview_input`、`expected_preview_fingerprint` 和 `expected_current_version_id`。服务端以 `preview_input` 重新计算 Preview 并校验 Fingerprint，客户端不得提交 `plan_payload`、Version number、Scope key 或其他未知字段。Plan 的 `name` 与 `flow_mode` 在创建后不可变；`held` 可保存为审计资产，但不表示 approved、active 或可运行。

`WorkflowPlanCloneRequest` 只接受 `name` 与属于 URL Plan 的 `source_version_id`。首次 clone 创建新 Plan/v1，响应包含 `source_plan_id`、`source_version_id`，并复制冻结 Preview、RoutePlan、Catalog/Policy snapshot、VersionScope 与 QueryTerm；不会重新运行 Planner。`MonitoringScopeTemplateCopyRequest` 只接受属于该 Project 且关联 source Version 的 `source_version_id`；响应返回新 template ID、source Scope/Plan/Version provenance 与完整语义字段。两者均使用同一 Idempotency-Key replay/conflict 语义，首次写入 `database_write=true`，replay 为 write-free。

`WorkflowPlanTransitionRequest` 只接受 `expected_status`、`to_status` 和可选 `reason`。当前本地状态表为 `draft→previewed→approved→active→paused→archived`，另允许 `paused→active`；同状态请求是 write-free no-op，过期 expected status 或未列出的跳转返回 `409`。成功只更新 Plan `status/updated_at`，Version、Scope、QueryTerm 和 current pointer 保持不变。

### WorkflowTemplate Revision 与 Plan association（本地实现）

| 方法 | 路径 | 必填输入 | 语义 |
|---|---|---|---|
| `POST` | `/api/projects/{project_id}/workflow-templates` | `Idempotency-Key`、`WorkflowTemplateCreateRequest` | 原子创建 Template header 与 Revision 1 |
| `GET` | `/api/projects/{project_id}/workflow-templates` | `limit`、`offset` | tenant-safe 列表，带 current Revision |
| `GET` | `/api/projects/{project_id}/workflow-templates/{template_id}` | 无 | header、current Revision 与不可变 fingerprint |
| `PATCH` | `/api/projects/{project_id}/workflow-templates/{template_id}` | `Idempotency-Key`、metadata patch | 只改 draft Template header，不替换 definition |
| `POST` | `/api/projects/{project_id}/workflow-templates/{template_id}/revisions` | `Idempotency-Key`、`expected_revision_id`、`definition` | append-only Revision；过期指针返回 `409` |
| `GET` | `/api/projects/{project_id}/workflow-templates/{template_id}/revisions` | `limit`、`offset` | 稳定 Revision history |
| `POST` | `/api/projects/{project_id}/workflow-templates/{template_id}/instantiate` | `Idempotency-Key`、`revision_id`、`name` | 用选定冻结 Revision 创建新的 `previewed` Plan/v1，并写入 Template/Revision lineage |

definition fingerprint 由服务端生成并固定为 `sha256:<64 hex>`；Plan 与 Version 都绑定同一 `(workflow_template_id, workflow_template_revision_id)`。Revision 不可更新或删除，metadata PATCH 不修改 definition。写入均返回 `X-Request-ID`，同 key replay 为 `database_write=false`；archived/non-draft、stale Revision、跨 Project 资源和损坏 definition fail closed。所有 route 保持 `provider_call=false`、`workflow_run_created=false`、`execution_authorized=false`。

`Idempotency-Key` 是必填 opaque header，trim 后长度为 `12..200`；服务端只使用其 hash，不在响应、日志或持久化记录中保存原始值。相同 key 与相同规范化请求返回原资源快照并标注 `idempotent_replay=true`、`database_write=false`、`plan_changed=false`；同 key 不同请求返回 `409 idempotency_conflict`。新 Plan/v1 或新 Version 返回 `201` 与 `outcome=created`；与当前 Fingerprint 等价的首次请求返回 `200` 与 `outcome=semantic_no_op`、`plan_changed=false`。该 no-op 仍可能写入幂等结果，因此其首次响应的 `database_write=true`；不能把它误报为“无持久化操作”。A→B→A 创建新的 v3，不对 `(workflow_plan_id, preview_fingerprint)` 施加唯一约束。

完整 Version 响应包含服务端从冻结 Fingerprint 输入重建的 `editable_input` 与冻结 `preview`；它使当前或历史 Version 能重新载入 Planner。列表和 Compare 中的 Version summary 不返回完整 Preview。嵌入的 Preview 继续描述规划计算，固定 `database_write=false`；外层 Save response 的 `database_write` 和 `plan_changed` 描述本次保存尝试。

### 读取、分页、归档与 Compare

| 方法 | 路径 | 响应 |
|---|---|---|
| `GET` | `/api/projects/{project_id}/workflow-plans` | `WorkflowPlanListResponse` |
| `GET` | `/api/projects/{project_id}/workflow-plans/{plan_id}` | `WorkflowPlanDetailResponse`（含 current Version） |
| `GET` | `/api/projects/{project_id}/workflow-plans/{plan_id}/versions` | `WorkflowVersionListResponse` |
| `GET` | `/api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}` | `WorkflowVersionDetailResponse` |
| `GET` | `/api/projects/{project_id}/workflow-plans/{plan_id}/version-compare?base_version_id={id}&target_version_id={id}` | `WorkflowPlanVersionCompareResponse` |
| `GET` | `/api/projects/{project_id}/monitoring-scopes` | `MonitoringScopeListResponse` |

三个列表都使用 `limit`（默认 `50`、范围 `1..100`）和 `offset`（默认 `0`），并返回 `items`、`total`、`limit`、`offset`。Plan 按 `updated_at DESC, id DESC`，Version 按 `version_number DESC`，MonitoringScope 按 `created_at DESC, id DESC`。Compare 返回服务端计算的结构化 sections；同一 Version 返回 `same_version=true` 与空 sections，不由 Web 重新计算 diff。

所有读取响应固定 `database_write=false`、`plan_changed=false` 和执行边界 false。当前 Workspace 成员可读取 archived Project 的 Plan、Version、history、Compare 和 Scope；Preview、Save、clone、Scope template copy 与 status-transition 写入口继续将 archived/inactive Project 拒绝为 `409 project_not_active`。Clone/copy/transition 的执行边界固定为 `provider_call=false`、`actor_run=false`、`browser_run=false`、`llm_call=false`、`workflow_run_created=false`、`execution_authorized=false`。

### 错误与明确不存在的接口

| 状态 | 情况 |
|---|---|
| `404` | 当前 Workspace 下不存在或不可见的 Project、Plan 或 Version |
| `409` | `project_not_active`、`preview_stale`、`version_conflict`、`idempotency_conflict` 或 Plan `flow_mode` 冲突 |
| `422` | body/header 校验失败；`Idempotency-Key` 格式无效时返回 header field error |
| `503` | Catalog/Planner dependency 或 persistence transaction 不可用 |
| `500` | 拓扑或其他未分类内部失败，返回安全错误码 |

已进入 Planner route 的成功与映射错误携带 `X-Request-ID`；框架在 handler 前拒绝的校验错误不保证该 header。Plan/Version 仍不存在 `PATCH`、`DELETE`、`/activate`、`/pause`、`/schedule`、`/archive` 或 live Provider 端点；status-transition 只写生命周期状态，不等于 Activate 或 Run。GOAL-V2-05A 的 fixture-only WorkflowRun routes 见下一节，不代表产品 Run/Provider 执行已开放。

2026-07-17 当前本地证据：payload-bound fixture materialization focused gates、full API `976 passed / 72 skipped / 6 warnings`、Ruff、full strict mypy `199 source files` 与 Alembic single head `202607170034` 通过；6 个 warnings 是 1 个既有 passlib deprecation 和 5 个既有 retention 测试的 aiosqlite event-loop-close warnings，不是 materialization failure。Web compatibility `246 passed`，TypeScript、ESLint 与 26-page mock build 通过。`apps/api/tests/postgres_workflow_lineage/` 已仅在 `127.0.0.1:55367/local_workflow_lineage_test` 通过 revision-034 lifecycle/constraint/service-concurrency/cleanup `13/13`；最终 head 034 且 lineage/materialization 业务表零行。

### GOAL-V2-05A Fixture WorkflowRun API（本地 Fixture-only）

这组 route 只执行服务端注册的 Fixture profile，并绑定指定的不可变 `WorkflowVersion`；它不是 Plan Activate、Schedule、live Run 或 Provider API。所有响应保留 `execution_mode=fixture`、`live_execution_authorized=false`、`provider_call=false`、`provider_call_attempted=false`、`credential_read_attempted=false`、`actor_run=false`、`browser_run=false`、`llm_call=false`、`raw_record_write=false`、`dataset_write=false`、`production_write_allowed=false`。创建响应额外返回 `database_write=true|false` 和 `idempotent_replay=true|false`；GET 读取固定 `database_write=false`。

| 方法 | 路径 | 请求/查询 | 响应 | 语义 |
|---|---|---|---|---|
| `GET` | `/api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}/fixture-run-gate` | 无 | `WorkflowFixtureRunGateResponse` | write-free 返回 Project active、Plan active、current Version 与完整 Primary fixture contract 门禁；`active` 不自动等于 runnable |
| `POST` | `/api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}/fixture-runs` | body: `expected_preview_fingerprint`、`fixture_profile_id`; header: `Idempotency-Key`（trim 后 12–200 字符） | `WorkflowFixtureRunCreateResponse` | 复用同一 runnable gate；仅 active Plan 的 current、完整 resolved Version 可首次创建 `WorkflowRun`/`StepRun`；同 key 同 body 返回 `200` replay，不重复 fixture side effect；同 key 不同 body `409` |
| `GET` | `/api/projects/{project_id}/workflow-runs` | `workflow_plan_id?`、`workflow_version_id?`、`limit=50`、`offset=0` | `WorkflowRunListResponse` | tenant-scoped 稳定分页列表，只读历史 Fixture Run |
| `GET` | `/api/projects/{project_id}/workflow-runs/{run_id}` | 无 | `WorkflowRunDetailResponse` | 返回 Run 与按 sequence 排序的 StepRun detail |
| `GET` | `/api/projects/{project_id}/workflow-runs/{run_id}/attempt-fallback-evidence` | 无 | `WorkflowAttemptFallbackEvidenceResponse` | tenant-scoped 只读组合持久化 Step Attempt 与 FallbackDecision，不执行 retry 或 switch |
| `GET` | `/api/projects/{project_id}/workflow-runs/{run_id}/checkpoint-budget-evidence` | 无 | `WorkflowCheckpointBudgetEvidenceResponse` | tenant-scoped 只读组合已确认 checkpoint 与五维 budget ledger，不执行 resume 或 budget override |
| `GET` | `/api/projects/{project_id}/workflow-runs/{run_id}/provider-health-evidence` | 无 | `WorkflowProviderHealthEvidenceResponse` | tenant-scoped 只读匹配 frozen Step route candidates 与最新 Provider health snapshots/feedback，不探测、不改 Catalog、不自动切路 |
| `GET` | `/api/projects/{project_id}/workflow-runs/{run_id}/lineage-preview` | 无 | `WorkflowRunLineagePreview` | 只读返回 payload eligibility、lineage digest；物化后重验 ledger/envelope/RawRecord/DatasetVersion 并返回资产 IDs |
| `POST` | `/api/projects/{project_id}/workflow-runs/{run_id}/materializations` | `dataset_name`, `expected_lineage_digest`; header `Idempotency-Key` | `WorkflowLineageMaterializationResponse` | 首次本地 fixture 写入返回 `201`；same-key exact replay 返回 `200` 且零新增写入 |

`WorkflowFixtureRunGateResponse` 固定包含 `project_status`、`plan_status`、requested/current Version、`planning_status`、`runnable`、allowlisted `blocker_codes`、`next_action_codes` 与 Evidence references，并继承全部 fixture/read-only false flags。`WorkflowRunResponse` 固定包含 Version/Plan IDs、由 immutable Version 派生的 `workflow_template_id` 与 `workflow_template_revision_id`（无 Template 时成对为 `null`）、Preview fingerprint、Catalog/Policy/Template/Query versions、Fixture profile/hash、step/record counts、时间与 non-live flags；`WorkflowStepRunResponse` 固定包含 frozen route、Primary implementation/assertion、Evidence refs、fixture case/content hash、input/output digest、step idempotency hash 与同一组 non-live flags。服务端拒绝 unknown fixture profile、fingerprint mismatch、非 active Plan、非 current Version、非 Primary/partial/held/不完整 Version、archived Project 新建和跨 tenant 资源；读取时若 Version lineage 缺失或成对不一致则返回 sanitized `500 workflow_run_lineage_invalid`；事务失败必须回滚三张新表，不产生 orphan。

`WorkflowAttemptFallbackEvidenceResponse` 固定
`schema_version=workflow_attempt_fallback_evidence.v1`，包含 ownership IDs、按 Step/
attempt number 排序的 `attempts`、按创建时间排序的 `fallback_decisions` 及精确 totals。
Attempt 必须在每个 Step 内从 1 连续编号，状态只允许 succeeded、retryable_error、timeout、
terminal_error，并校验 error/backoff/time 一致性。FallbackDecision 必须包含 trigger、policy、
credential、budget、fields、evidence、approval 七段有序 gate、字段差异、成本快照、审批状态、
Evidence refs 与 decision digest；ownership、gate outcome、approval 和 candidate pair 均 fail
closed。响应继承 fixture read-only flags，并额外固定 `switch_executed=false`、
`database_write=false`、`provider_call=false`；无 Decision 的空数组仅表示没有持久化证据，
不表示 Fallback 可用。该资源没有对应 POST/PATCH/DELETE，也不授权 retry、resume、cancel
或 route switch。

`WorkflowCheckpointBudgetEvidenceResponse` 固定
`schema_version=workflow_checkpoint_budget_evidence.v1`，并要求
`execution_session_id=workflow_run_id`。Checkpoint 按 Step/page 排序，校验 cursor chain、
terminal/next cursor、records total 与 Plan/Version ownership；Budget account 冻结
request/item/quota/cost/time 上限，ledger 按 entry number/previous digest 串联并重算累计值，
每个 checkpoint 必须存在相同 step/page/side-effect key 的 reserved entry。空 account 仅返回
`budget_status=not_configured`，不得推断无限预算；blocked final entry 返回 `held` 与固定原因。
响应继承全部 fixture read-only flags并固定 `resume_action_available=false`、
`budget_override_available=false`。该资源没有 POST/PATCH/DELETE。

`WorkflowProviderHealthEvidenceResponse` 固定
`schema_version=workflow_provider_health_evidence.v1`。每个 Step 的候选顺序必须精确等于
frozen RoutePlan 的 Primary + Fallback，selected candidate 固定为第一项且恰好一个；只读取
同 Project、platform、resource type、operation、implementation ID 的快照，并要求每个
implementation 的 snapshot version 连续、previous digest 指向上一版本。最新快照按
`routing_expires_at` 与响应 `read_at` 标记 active/expired；过期只失去 routing influence，
Evidence 仍可读。Route feedback 只有 capability identity 与 original candidate order 精确
匹配时才返回，且只读展示 adjusted order/reasons。响应固定
`health_probe_attempted=false`、`catalog_mutation=false`、
`automatic_route_switch=false`、`provider_call=false`、`database_write=false`；无快照仅表示
unobserved，不能推断健康或允许切路。该资源没有 POST/PATCH/DELETE。

错误映射为 `401` Auth、`404` tenant-hidden project/plan/version/run、`409` inactive/non-current/non-completed/unbound/digest/idempotency/Dataset/transaction conflict、`422` request/fixture profile contract、`503` persistence unavailable，以及 sanitized `500` payload/ledger/lineage/internal invalid；route 内错误携带 `X-Request-ID`。`fixture-run-gate`、`lineage-preview`、`attempt-fallback-evidence`、`checkpoint-budget-evidence` 与 `provider-health-evidence` 始终 write-free；未物化且 payload-bound 时 `materialization_eligible=true`，历史 unbound Run 返回 blocker，已物化 Run 返回持久化 IDs 与 `workflow_run_already_materialized`。POST 不接受 record bodies，只从 StepRun-bound server registry 重建 envelope，写入 RawRecord、一个 DatasetVersion 与专用 ledger 的同一事务。后端仍没有独立 Activate、Schedule、Retry、Resume、Budget override、Fallback switch 或 live Provider adapter；Shadow、Attempt/Fallback、Checkpoint/Budget 与 Provider Health 均仅为 fixture Evidence 读取。Web `/automation/runs` 保持只读；Planner 只在 active/current/complete fixture gate 回执允许时暴露本地 fixture Run，不开放 live Run。

### V2 persisted lineage storage contract (local PostgreSQL accepted)

`RawRecord` remains the canonical raw asset. Revision `202607160033` adds
nullable `workflow_run_id`, `workflow_step_run_id` and
`workflow_lineage_contract_version`; a named check requires either the legacy
`source_id + task_run_id` pair or the V2 WorkflowRun/StepRun pair, never both.
The V2 StepRun foreign key is tenant-scoped and `(workflow_step_run_id,
content_hash)` is the V2 deduplication key. Provider implementation, route and
Evidence refs remain on immutable StepRun and are not copied into RawRecord.

`DatasetVersion` adds nullable `source_workflow_run_id`, ordered
`source_workflow_step_run_ids`, ordered `source_raw_record_ids` and
`lineage_contract_version=workflow_dataset_version.v1`; legacy
`source_task_run_ids` remains unchanged. The payload-bound fixture route now
consumes this contract, and revision-034 PostgreSQL acceptance passed on the
exact disposable target. No live Provider adapter exists, so `DAT-003` remains
fixture-only rather than production-ready.

PostgreSQL acceptance source is now present at
`scripts/verify-workflow-lineage-migration.sh` and
`tests/postgres_workflow_lineage/`. It requires three independent
`WORKFLOW_LINEAGE_*` inputs, an exact loopback host/port/database target and a
database name ending `_workflow_lineage_test`. With those variables unset the
13 revision-034 database cases skip before engine creation. The explicit Task
13 authorization was then consumed only for
`127.0.0.1:55367/local_workflow_lineage_test`: guarded
`033→034→033→034`, constraints, rollback, ledger/service concurrency and
cleanup passed `13/13`. Final recount is head `202607170034` with Dataset,
DatasetVersion, RawRecord, WorkflowRun, StepRun and materialization ledger at
zero rows. No other database was connected or modified.

Task 13 实测证据（2026-07-16）：仅授权并使用 `127.0.0.1:55367/local_workflow_execution_test`，Alembic `028→029→028→029` 与 PostgreSQL suite `14 passed`；cleanup head `202606110029`，`workflow_runs`、`step_runs`、`workflow_run_requests` 均为 0。该证据是 disposable local PostgreSQL schema/concurrency proof，不是生产或 live Provider 验收；`database_write=local-test-only`、`provider_call=false`、`production unchanged`。

## Collector And Source

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/collectors` | 无 | `CollectorResponse[]` |
| `GET` | `/api/sources` | query: `project_id`、`type`、`enabled` | `SourceResponse[]` |
| `POST` | `/api/sources` | `project_id`、`name`、`type`、`url?`、`config`、`schedule_cron?` | `SourceResponse` |
| `GET` | `/api/sources/{source_id}` | 无 | `SourceResponse` |
| `PATCH` | `/api/sources/{source_id}` | source 可编辑字段 | `SourceResponse` |
| `POST` | `/api/sources/{source_id}/test` | 无 | `SourceTestResponse` |
| `POST` | `/api/sources/{source_id}/enable` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/sources/{source_id}/disable` | 无 | `SourceResponse` |

稳定 collector：

| type | 必填 config | 用途 |
|---|---|---|
| `github_repo` | `owner`、`repo` | GitHub 仓库指标 |
| `github_topic` | `topic` | GitHub topic 趋势 |
| `generic_web` | `url` | 公开网页快照 |
| `public_feed` | `url` | 公开 RSS/Atom feed 更新条目 |
| `manual_json` | `entity_type`、`json_data` | 人工或外部工具导入结构化样本 |
| `ecommerce_product_discovery` | `url` | 从公开独立站 listing、collection 或 sitemap 发现商品 URL |
| `ecommerce_product_page` | `url` | 从公开独立站商品页解析商品字段；优先 JSON-LD/Product，兼容静态 schema.org microdata `itemprop` 字段 |

`ecommerce_product_page` 默认字段合同：

| 字段 | 说明 |
|---|---|
| `title`、`price`、`currency`、`availability`、`sku`、`brand`、`description`、`image_url`、`canonical_url` | 基础商品字段 |
| `price_min`、`price_max` | 从多 offer / variant price 中计算价格区间 |
| `availability_detail` | 保留 offer / variant 级库存状态摘要 |
| `variant` | 商品变体名称或变体维度摘要 |
| `category` | 商品分类或分类层级 |

字段来源优先级：JSON-LD Product / Offer 仍是最高优先级；当真实静态测试站没有 JSON-LD 时，`ecommerce_product_page` 可从 schema.org microdata 的 `itemprop=name/price/priceCurrency/description/image` 中提取基础字段；站点级 `og:image` 不覆盖商品级 microdata image。

## Automation

所有 Automation 接口都要求登录态。写入、运行、导出、发送通知类动作必须在请求体中显式传入 `authorized=true`；部分动作还要求 `confirm_create=true` 或 `confirm_send=true`。

### Platform Package Contract

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `GET` | `/api/automation/platform-packages` | 无 | `AutomationPlatformPackageListResponse` | 返回当前平台包矩阵 |
| `GET` | `/api/automation/platform-packages/{package_id}` | path: `package_id` | `AutomationPlatformPackageResponse` | 返回单个平台包合同，未知 id 返回 `404` |

`AutomationPlatformPackageResponse` 除字段 contract、SOP 和策略矩阵外，还必须返回治理字段：

```text
version
owner
lifecycle_status
evidence_grade
authorization_required
acceptance_registry[]
cleanup_policy
forbidden_actions[]
```

当前平台包：

| id | version | execution boundary | evidence grade | default entrypoint | 说明 |
|---|---|---|---|---|---|
| `shopify-independent-ecommerce` | `2026.06.m4` | `executable` | `L2-fixture-or-dry-run` | `product-discovery` | 独立站/Shopify-style 商品采集，从集合页或商品页进入 Automation 主链路；本地 fixture 和公开测试站 local API E2E 已登记，production/customer-site gate 待授权 |
| `github-api-first` | `2026.06.m3` | `executable` | `L4-authorized-live` | `source-create` | GitHub topic 工具情报采集，使用官方 API 创建 Source、启用 Task 并运行一次；L4 仅代表已授权的小范围 package gate |
| `public-page-structure-preflight` | `2026.06.preflight` | `executable` | `L2-fixture-or-dry-run` | `preflight` | 授权公开网页结构预检，先输出 gate 和结构诊断，再决定是否创建 `generic_web` Source |
| `public-web-rss-docs` | `2026.06.m5` | `executable` | `L4-authorized-live` | `source-create` | 公开 RSS/Atom feed 与 docs/page hash 更新监控；L4 仅代表已完成的 scoped public-content gates 和 retained canary |

平台包不变量：

1. `execution_boundary=executable` 只表示可以从界面启动其声明的低风险路径，不代表绕过授权、rate limit 或平台政策。
2. GitHub/API-first 当前可执行路径是 `github_topic` Topic Radar；单仓库 `github_repo` 仍建议通过 Sources 创建重点仓库监控。
3. `public-page-structure-preflight` 使用 Toolkit preflight，不是 Source collector；只有用户确认后才可继续创建 `generic_web` Source。
4. `public-web-rss-docs` 本地链路已覆盖 RSS/Atom 与 docs/page snapshot 的 Dataset preview/save、content-hash drift、drift event save/list、report preview 和 Report asset；生产调度、provider/email、生产浏览器运行和新增生产写入仍需后续授权 gate。
5. `acceptance_registry[]` 是验收登记，不会自动升级平台状态；`L4-authorized-live` 仍必须按登记项的 scoped 范围理解。

### Capability Probe Contract

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `GET` | `/api/automation/capability-probes` | query: `platform_id?` | `AutomationCapabilityProbeListResponse` | 返回平台能力体检矩阵；只运行允许的本地 doctor/probe，不读取平台内容、不创建采集资源 |

`AutomationCapabilityProbeResponse` 最小字段：

```text
schema_version=capability_probe.v1
platform_id
platform_label
doctor_status
credential_mode
execution_boundary
risk_level
backend_candidates[]
agent_reach?
allowed_outputs[]
forbidden_actions[]
next_actions[]
run_started=false
collection_resources_written=false
evidence_asset
```

`AutomationCapabilityProbeListResponse.evidence_assets[]` 聚合每个 probe 的 `evidence_asset`。`evidence_asset.schema_version=evidence_asset_reference.v1`，`evidence_boundary=no_read_no_search_no_write`，只表示本次 doctor/catalog 结果可被报告或 Evidence 引用；它不表示平台读取、采集运行或写入已发生。

`AutomationAgentReachChannelProbeResponse` 最小字段：

```text
schema_version=agent_reach_channel_probe.v1
installed
command_path
doctor_status
active_backend
requires_login
requires_proxy
blocked_reason
platforms[]
read_invoked=false
search_invoked=false
raw_summary
```

能力探测不变量：

1. `agent-reach` 缺失时返回 `doctor_status=missing_tool`，不能伪装为平台可采集。
2. `agent-reach` 存在时只允许调用 `agent-reach doctor --json`；不得调用 read/search，不得自动安装工具。
3. `browser-harness` 能力只作为 read-only probe 候选，不得直接创建 Source/Task/TaskRun/Dataset。
4. `execution_boundary=sop_only` 或 `import_only` 的平台不得在 UI 中出现默认自动采集按钮。
5. 所有 response 必须保持 `run_started=false`、`collection_resources_written=false`，直到进入单独授权的采集写入链路。
6. CapabilityProbe evidence reference 必须保持 `credentials_captured=false`、`cookies_captured=false`、`headers_captured=false`、`bodies_captured=false`，且 `read_invoked=false`、`search_invoked=false`。

### Browser Diagnostic Evidence Contract

浏览器诊断 gate 与本地诊断运行都属于证据资产链路，不代表正式采集任务。

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/browser-diagnostic-jobs/{job_id}/production-metadata-run-gate` | `authorized`、`confirm_review`、`confirm_production_readonly`、`confirm_metadata_only`、`confirm_no_file_write`、`confirm_no_collection_write`、`target_environment=production`、`max_metadata_events?` | `AutomationBrowserProductionMetadataRunGateResponse` | 只生成生产 metadata-only 手工只读运行预检；`evidence_grade=L2-fixture-or-dry-run`，`run_started=false`、`browser_started=false`、`files_written=false`、`collection_resources_written=false`、`provider_called=false` |
| `POST` | `/api/automation/browser-diagnostic-jobs/{job_id}/local-run` | `authorized`、`confirm_execute`、`run_mode`、`confirm_real_browser_probe?`、`browser_harness_cdp_url?` | `AutomationBrowserLocalRunnerResultResponse` | 只读回放或本机 dedicated-CDP 临时 tab 探测；不创建 Source/Task/TaskRun/Dataset |
| `POST` | `/api/automation/browser-diagnostic-job-runs/{job_run_id}/promotion-preview` | `authorized`、`confirm_review`、`target_source_type`、`enable_task_preview?` | `AutomationBrowserPromotionPreviewResponse` | 只根据本地 run 生成 Source/Task 候选包和阻断原因；不创建 Source/Task/TaskRun/Dataset |
| `POST` | `/api/automation/browser-diagnostic-job-runs/{job_run_id}/promotion-execution-dry-run` | `authorized`、`confirm_review`、`confirm_no_write`、`target_source_type`、`source_name?`、`schedule_cron?` | `AutomationBrowserPromotionExecutionDryRunResponse` | 复用正式 collector config 校验生成执行前预检计划；强制 no-write，不创建 Source/Task/TaskRun/Dataset |
| `POST` | `/api/automation/browser-diagnostic-job-runs/{job_run_id}/promotion-execution` | `authorized`、`confirm_review`、`confirm_write`、`confirm_create_collection_resources`、`confirm_no_task_run`、`target_source_type`、`source_name?`、`schedule_cron?`、`confirm_schedule?`、`idempotency_key` | `AutomationBrowserPromotionExecutionResponse` | 显式授权后创建 Source+Task；强制不启动 TaskRun，不创建 Dataset；同一 idempotency key replay，同 URL/type 不同 key 阻断 |
| `GET` | `/api/automation/browser-diagnostic-job-runs` | query: `project_id?`、`diagnostic_job_id?` | `AutomationBrowserLocalRunnerResultListResponse` | 返回本地诊断运行历史和只读副作用汇总 |

`AutomationBrowserLocalRunnerResultResponse` 在兼容旧字段的基础上新增 M2 证据字段：

```text
selector_results[]
selector_evaluations[]
network_observation_summary
network_metadata_summary
promotion_gate
redaction_summary
evidence_asset
files_written=false
collection_resources_written=false
```

M2 字段约束：

1. `selector_evaluations[]` 是 `selector_results[]` 的规范化视图，包含 `field`、`selector_hint`、`match_count`、`sample_text`、`missing_reason` 和 `browser_started`。
2. `network_metadata_summary` 只允许保留 metadata：`capture_headers=false`、`capture_body=false`、`redacted=true`；URL 必须移除 query 和 fragment。
3. `promotion_gate.can_create_collection_resources=false`，并包含 `m2_read_only_contract_no_direct_promotion`；只有独立的 `promotion-execution` 写 gate 可在显式授权和 idempotency key 下接管 Source+Task 创建。
4. `redaction_summary` 必须显式声明 `cookies_captured=false`、`headers_captured=false`、`bodies_captured=false`、`query_parameters_retained=false`。
5. `run_mode=ephemeral_browser_harness_probe` 只有在提供 dedicated `browser_harness_cdp_url` 时才可进入 browser-harness；缺少该字段必须返回 `blocked_ephemeral_probe` / `browser_harness_isolated_cdp_required`，不得默认连接用户主 Chrome。
6. `run_mode=ephemeral_browser_harness_probe` 可以使 `browser_started=true`，但仍保持 `files_written=false` 和 `collection_resources_written=false`。
7. `AutomationBrowserDiagnosticRunResponse`、`AutomationBrowserDiagnosticJobResponse`、`AutomationBrowserLocalRunnerResultResponse` 及对应 list response 必须携带 `evidence_asset` / `evidence_assets[]`；这些引用只保存 metadata、ID、脱敏 URL 和边界声明，不内嵌 screenshot、trace、HAR、headers、body 或 cookie。
8. `promotion-preview` 必须保持 `can_promote=false`、`source_created=false`、`task_created=false`、`task_run_started=false`、`collection_resources_written=false`；`source_draft` 和 `task_draft` 只供人工复核，不能作为自动写入证据。
9. `promotion-execution-dry-run` 必须要求 `confirm_no_write=true`，并保持 `dry_run=true`、`write_allowed=false`、`can_execute=false`、`source_created=false`、`task_created=false`、`task_run_started=false`、`collection_resources_written=false`；即使 collector config 校验通过，也不能升级为正式执行证据。
10. `promotion-execution` 必须要求 `confirm_write=true`、`confirm_create_collection_resources=true`、`confirm_no_task_run=true` 和 `idempotency_key`；成功时只允许 `source_created=true`、`task_created=true`、`task_run_started=false`，并在 `BrowserDiagnosticJobRun.audit_events` 记录 `browser_promotion_execution_resources_created`、`idempotency_scope=browser_promotion_execution` 和 `idempotency_key_hash`。
11. `promotion-execution` 的重复提交规则：同一 `idempotency_key` 返回 `idempotency_replayed=true` 且不再写入；不同 key 命中同一 `target_source_type + url` 必须返回 `browser_promotion_target_source_already_exists`；缺少必填 selector、collector config invalid 或证据边界异常时必须返回 400。
12. `production-metadata-run-gate` 是 no-run L2 预检；必须保持 `production_read_only_observed=false`、`run_started=false`、`browser_started=false`、`execution_started=false`、`files_written=false`、`collection_resources_written=false`、`provider_called=false`、`source_created=false`、`task_created=false`、`task_run_started=false`、`dataset_created=false`，直到另起授权 L3/L4 gate。
13. Artifact retention 规则以 `docs/workflows/workflow-browser-evidence-artifact-retention-stable.md` 为准；PRD2 M2 当前阶段只允许 metadata 和 `tmp/` 本地验证 JSON。

### GitHub/API-first Topic Radar Flow

GitHub Topic Radar 当前复用既有 Source/Task/Run API，不新增专用写入接口：

| 步骤 | 接口 | 关键字段 | 说明 |
|---|---|---|---|
| 创建 Source | `POST /api/sources` | `type=github_topic`、`config.topic`、`config.max_results` | 创建公开 topic 采集源 |
| 启用 Task | `POST /api/sources/{source_id}/enable` | 无 | 创建或复用采集任务 |
| 执行采集 | `POST /api/tasks/{task_id}/run` | 无 | 调用 GitHub Search API，写入 TaskRun、RawRecord、Entity/Snapshot/Signal |

GitHub 工具数据集化：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/github-tool-dataset-preview` | `authorized`、`task_run_ids`、`fields?`、`max_rows?` | `AutomationProductDatasetPreviewResponse` | 从 GitHub topic/repo 运行记录生成工具情报数据集预览，不保存 DatasetVersion |
| `POST` | `/api/automation/github-tool-dataset-save` | preview request + `name`、`description?` | `AutomationProductDatasetSaveResponse` | 保存 `dataset_type=github_tool_radar` 的 DatasetVersion |

GitHub 工具数据集字段：

```text
repo_full_name, owner_login, owner_type, description, stars, forks, open_issues, watchers,
language, topics, license_spdx_id, default_branch, latest_release_tag,
latest_release_published_at, archived, fork, html_url, homepage, created_at, updated_at, pushed_at
```

字段来源边界：

1. `github_topic` 优先来自 GitHub Search API，可稳定获得仓库基础元数据、license、默认分支、公开 topic 和 freshness 字段；`latest_release_*` 对 topic 结果可能为空。
2. `github_repo` 额外读取 GitHub REST `releases/latest`；公开仓库无 release 时保留 `latest_release=null`，不阻断基础仓库采集。
3. 以上 endpoint 仍为 API-first/read-only 数据集化能力；预览不保存 DatasetVersion，报告生成不启动采集、不创建通知、不发送邮件。

GitHub 工具数据集导出复用 Dataset Export：

1. `POST /api/automation/product-dataset-exports`
2. `GET /api/automation/product-datasets/{dataset_id}/exports`
3. `GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download`

这些导出 endpoint 名称仍保留 `product` 历史命名，但底层按 Dataset/Version 权限和 `dataset_type` 工作；后续可再做无破坏的 alias。

### Public Web/RSS/Docs Content Dataset Flow

公开内容更新当前复用 Source/Task/Run API：

| 步骤 | 接口 | 关键字段 | 说明 |
|---|---|---|---|
| 创建 Source | `POST /api/sources` | `type=public_feed` 或 `type=generic_web`、`url`、`config.url`、`config.feed_type?`、`config.max_items?`、`config.extract_mode?` | 创建公开 RSS/Atom 或公开 docs/page 采集源 |
| 启用 Task | `POST /api/sources/{source_id}/enable` | 无 | 创建或复用 `public_feed` / `generic_web` 采集任务 |
| 执行采集 | `POST /api/tasks/{task_id}/run` | 无 | 写入 TaskRun、RawRecord、Entity/Snapshot；不写 Dataset |

公开内容数据集化：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/public-content-dataset-preview` | `authorized`、`task_run_ids`、`fields?`、`max_rows?` | `AutomationProductDatasetPreviewResponse` | 从 `public_feed` entries 或 `generic_web` docs/page snapshot 生成公开内容数据集预览，不保存 DatasetVersion |
| `POST` | `/api/automation/public-content-dataset-save` | preview request + `name`、`description?` | `AutomationProductDatasetSaveResponse` | 保存 `dataset_type=public_content_update`、`schema_version=public_content_update.v1` 的 DatasetVersion |
| `POST` | `/api/automation/public-content-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、`completeness_drop_threshold_percent?`、`freshness_grace_hours?` | `AutomationProductDriftCheckResponse` | 只读比较最新 `public_feed` / `generic_web` TaskRun；用 `link` 做主键、`content_hash` 做内容漂移信号 |
| `POST` | `/api/automation/public-content-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 从只读 drift check 保存或复用 `event_type=public_content_drift` 的 DatasetDriftEvent |
| `GET` | `/api/automation/public-content-drift-events` | `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出公开内容 DatasetDriftEvent；不启动采集、不创建告警 |
| `POST` | `/api/automation/public-content-report` | `authorized`、`dataset_id`、`dataset_version_id`、`top_limit?` | `AutomationPublicContentReportResponse` | 从已保存 DatasetVersion 生成公开内容更新报告预览，不创建 Report 资产 |
| `POST` | `/api/automation/public-content-report-assets` | report request + `confirm_create`; optional header: `Idempotency-Key` | `AutomationPublicContentReportAssetResponse` | 在明确确认后创建 `report_type=public_content` Report 资产；同 key 重放返回原 Report，不发送通知、不写导出文件 |

公开内容数据集字段：

```text
title, link, published_at, updated_at, author, tags, summary,
content_hash, feed_url, feed_title, feed_type, site_url,
source_type, content_kind, text_length
```

公开内容边界：

1. 只支持已授权公开 RSS/Atom feed 或公开文档更新源；不覆盖登录态、私信、付费墙、验证码或账号后台页面。
2. `public-content-drift-check` 不启动采集、不创建 `DatasetDriftEvent`、不创建告警、不发送通知。
3. `public-content-drift-events` 只保存/复用 drift 快照，不启动采集、不创建告警、不发送通知。
4. `public-content-report` 只返回只读预览；`public-content-report-assets` 只在 `confirm_create=true` 后创建或重放 Report 资产，不写导出文件、不发送邮件；`Idempotency-Key` hash 绑定 `workspace_id`、`dataset_id`、`dataset_version_id` 与 `top_limit`，原始 key 不写入审计事件。
5. Dataset export、生产 Source/Task/TaskRun、scheduler、provider/email 和生产浏览器运行仍需独立授权。

### Public Page Structure Preflight

公开网页结构预检当前挂在 Toolkit API 下：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/toolkit/preflight` | `url`、`authorized` | `ToolkitPreflightReportResponse` | 对公开 URL 做授权 gate、robots、sitemap、DOM 摘要和工具建议 |

预检通过后，如需进入持续采集，前端再复用：

1. `POST /api/sources` 创建 `generic_web` Source。
2. `POST /api/sources/{source_id}/enable` 启用 Task。
3. `POST /api/tasks/{task_id}/run` 执行一次公开网页采集。

### Site Analysis And Product Discovery

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/site-analysis` | `url`、`authorized`、`target=ecommerce_product`、`fields?` | `AutomationSiteAnalysisResponse` | 分析公开商品页，返回平台画像、页面结构、字段候选、工具推荐、清洗草案和 source draft |
| `POST` | `/api/automation/product-discovery` | `url`、`authorized`、`max_products?` | `AutomationProductDiscoveryResponse` | 从 listing、collection 或 sitemap 页面发现商品候选 URL |
| `POST` | `/api/automation/product-fanout-preview` | `parent_url`、`authorized`、`candidates`、`fields?`、`max_sources?` | `AutomationProductFanoutPreviewResponse` | 预览候选商品 URL 是否可转成商品页 source |
| `POST` | `/api/automation/product-fanout-create` | `project_id`、`parent_url`、`authorized`、`candidates`、`fields?`、`max_sources?`、`enable_tasks?` | `AutomationProductFanoutCreateResponse` | 创建或复用商品页采集源，可同时启用采集任务 |

关键边界：

1. 这些接口不支持登录态抓取、风控绕过或反检测能力。
2. `product-fanout-preview` 只预览，不创建采集源或采集任务。
3. `product-fanout-create` 会写入采集源/任务，必须用于授权页面或测试 fixture。

`AutomationProductDiscoveryResponse` 关键字段：

| 字段 | 说明 |
|---|---|
| `product_candidates[].canonical_url` | canonical 去重后的商品 URL；`url` 当前也使用 canonical URL 作为 fan-out 输入 |
| `page_structure.pagination_url_count` | listing/collection 中识别到的分页 URL 数 |
| `page_structure.duplicate_url_count` | 被 canonical 去重折叠的候选 URL 数 |
| `page_structure.skipped_url_count` | 被跳过的 URL 数，包含非商品链接和重复 canonical URL |
| `discovery_plan.pagination_urls` | 分页 URL 样本，供人工确认后继续扩展 |
| `discovery_plan.dedupe_summary` | 输入 URL 数、规范候选数、重复数、跳过数和 `skipped_reasons` 汇总 |

### Batch Run And Dataset

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-batch-run` | `authorized`、`task_ids`、`max_tasks?` | `AutomationProductBatchRunResponse` | 对已审阅商品页采集任务执行小批量采集 |
| `POST` | `/api/automation/product-dataset-preview` | `authorized`、`task_run_ids`、`fields?`、`max_rows?` | `AutomationProductDatasetPreviewResponse` | 从采集运行结果聚合数据集预览和清洗草案 |
| `POST` | `/api/automation/cleaning-plan-dry-run` | `authorized`、`task_run_ids`、`fields?`、`rules`、`max_rows?` | `AutomationCleaningPlanDryRunResponse` | 对样本行执行清洗规则试跑，不保存数据集版本 |
| `POST` | `/api/automation/cleaning-plans` | 试跑请求 + `name` | `AutomationCleaningPlanCreateResponse` | 保存可复用清洗计划草案 |
| `GET` | `/api/automation/cleaning-plans` | query: `project_id?`、`limit?` | `AutomationCleaningPlanListResponse` | 列出清洗计划资产 |
| `POST` | `/api/automation/product-dataset-save` | `authorized`、`task_run_ids`、`fields?`、`max_rows?`、`name`、`description?`、`cleaning_plan_id?` | `AutomationProductDatasetSaveResponse` | 保存数据集版本，可追踪清洗计划 |
| `GET` | `/api/automation/product-datasets` | query: `project_id?`、`limit?` | `AutomationProductDatasetListResponse` | 列出商品数据集资产 |
| `GET` | `/api/automation/product-datasets/{dataset_id}/versions` | query: `limit?` | `AutomationProductDatasetVersionListResponse` | 列出数据集版本 |

数据集不变量：

1. 数据集版本必须保留 `source_task_run_ids`、`selected_fields`、`cleaning_script`、`rows`、`export_preview` 和 completeness 指标。
2. V2 DatasetVersion 可在不填充 `source_task_run_ids` 的情况下保留
   `source_workflow_run_id`、有序 `source_workflow_step_run_ids`、有序
   `source_raw_record_ids` 和 `lineage_contract_version`；四者必须成组出现。
3. 清洗计划是独立草案资产，保存规则、脚本文案、试跑预览和版本号。
4. `cleaning-plan-dry-run` 必须返回 `dataset_version_created=false`、`cleaning_plan_created=false`、`run_started=false`。
5. 数据集版本可选追踪 `cleaning_plan_id`；不传该字段时保持原始预览保存行为。

### Dataset Export

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-dataset-exports` | body: `authorized`、`confirm_create`、`dataset_id`、`dataset_version_id`、`export_format`; optional header: `Idempotency-Key` | `AutomationProductDatasetExportJobResponse` | 生成受控导出文件，格式支持 `csv`、`json`、`jsonl`；同 key 重放返回原 job |
| `GET` | `/api/automation/product-datasets/{dataset_id}/exports` | query: `dataset_version_id?`、`limit?` | `AutomationProductDatasetExportListResponse` | 查看导出历史 |
| `GET` | `/api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download` | 无 | 文件响应 | 下载导出文件 |

导出不变量：

1. 未传 `confirm_create=true` 时必须拒绝导出。
2. ExportJob 必须记录 `filename`、`content_type`、`artifact_size_bytes`、`row_count`、`checksum_sha256`、`audit_events`。
3. 下载接口必须限制 artifact 位于 `Settings.dataset_export_dir` 内，避免路径穿越。
4. `Idempotency-Key` hash 绑定 `workspace_id`、`dataset_id`、`dataset_version_id` 和 `export_format`；首次写入返回 `idempotency_replayed=false`，重复请求返回 `idempotency_replayed=true` 和同一个 `download_url`。

GitHub 工具漂移和报告：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/github-tool-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、阈值字段 | `AutomationProductDriftCheckResponse` | 对 `github_tool_radar` 数据集做同源 GitHub task 只读漂移检查 |
| `POST` | `/api/automation/github-tool-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 保存 `event_type=github_tool_radar_drift` 的漂移快照 |
| `GET` | `/api/automation/github-tool-drift-events` | query: `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出 GitHub 工具数据集漂移事件 |
| `POST` | `/api/automation/github-tool-report` | `authorized`、`dataset_id`、`dataset_version_id`、`min_stars?`、`top_limit?` | `AutomationGitHubToolReportResponse` | 基于已保存版本生成只读工具雷达报告 |
| `POST` | `/api/automation/github-tool-report-assets` | report request + `confirm_create=true`; optional header: `Idempotency-Key` | `AutomationGitHubToolReportAssetResponse` | 将工具雷达报告保存为 `report_type=github_tool_radar` 的 Report 中心资产，成功返回 `201`；同 key 重放返回原 Report |

`AutomationGitHubToolReportResponse.summary` 包含 `repository_count`、`total_stars`、`high_value_repositories`、`languages`、`top_topics`、`report_created=false`、`run_started=false`。

`AutomationGitHubToolReportAssetResponse` 继承只读报告 response，并额外返回 `report`、`notification_created=false`、`idempotency_replayed`、`idempotency_scope` 与 `idempotency_key_hash`；`summary.report_created=true` 仅表示已写入或命中既有 Report 资产，不表示发送或创建通知。

边界：

1. GitHub 工具漂移检查只允许与 DatasetVersion `source_task_run_ids` 同源的 `github_topic` / `github_repo` task 进入比较。
2. GitHub 工具漂移和只读报告接口均不启动采集、不创建告警、不发送通知。
3. `github-tool-report-assets` 只创建 Report 中心资产和审计事件；不会启动采集、创建站内通知或发送邮件。
4. `github-tool-report-assets` 的 `Idempotency-Key` hash 绑定 `workspace_id`、`dataset_id`、`dataset_version_id`、`min_stars` 与 `top_limit`；重复请求返回原 Report，原始 key 不写入审计事件。

### Schedule, Drift And Dataset Alerts

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-schedule-approve` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、调度策略字段 | `AutomationProductScheduleApproveResponse` | 审批数据集关联采集任务的后续刷新策略 |
| `POST` | `/api/automation/product-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、阈值字段 | `AutomationProductDriftCheckResponse` | 检查数据集版本与最新运行结果的字段、目录 presence 和价格漂移 |
| `POST` | `/api/automation/product-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 保存漂移快照 |
| `GET` | `/api/automation/product-drift-events` | query: `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出漂移事件 |
| `POST` | `/api/automation/product-drift-alert-preview` | `authorized`、`dataset_id`、`dataset_version_id?`、`min_status?`、`channel?` | `AutomationProductDriftAlertPreviewResponse` | 预览漂移告警规则 |
| `POST` | `/api/automation/product-drift-alert-rules` | preview request + `confirm_create` | `AutomationProductDriftAlertRuleCreateResponse` | 创建漂移告警规则 |
| `POST` | `/api/automation/product-drift-alert-events` | `authorized`、`confirm_create`、`dataset_id`、`dataset_version_id`、`drift_event_id` | `AutomationProductDriftAlertEventCreateResponse` | 从漂移事件创建 Signal 和 AlertEvent |
| `POST` | `/api/automation/product-drift-alert-notifications` | body: `authorized`、`confirm_send`、`dataset_id`、`dataset_version_id`、`drift_event_id`、`alert_event_ids`; optional header: `Idempotency-Key` | `AutomationProductDriftAlertNotificationSendResponse` | 发送站内通知；同 key 重放返回既有通知 |
| `POST` | `/api/automation/product-drift-alert-emails` | notification request + `recipient_email?`; optional header: `Idempotency-Key` | `AutomationProductDriftAlertEmailSendResponse` | 发送邮件告警；同 key 重放返回既有发送结果且不再次调用 SMTP/provider |

当前已硬化：

1. 漂移快照保存具备 fingerprint 复用，重复提交不会创建重复漂移事件。
2. 漂移告警规则按项目、条件、渠道和启用状态复用既有规则。
3. 采集运行失败日志已记录标准化 `failure_reason`。
4. 商品漂移 item 返回 `row_change`、`added_row_count`、`removed_row_count`、`price_change_percent`；summary 返回 `added_rows`、`removed_rows`、`price_changed_tasks`。
5. `drift_layers` 除 `completeness`、`field_missingness`、`task_freshness` 外，可返回 `catalog_presence` 和 `price_change`；`product_removed` 会使任务状态进入 `critical`。

当前已补：

1. 前端主提交按钮有 submitting / in-flight guard。
2. 采集任务执行有 task row lock、collector `run_timeout_seconds`、scheduler running-task skip。
3. auto freshness 失败重试有 `max_retry_attempts` / `retry_attempts_used` 预算字段；预算耗尽后 `next_run_at=null`，`freshness_status=retry_exhausted`。
4. 手动 Task run 支持 `Idempotency-Key` 首个本地合同：同一 workspace/task/key hash 的重复请求返回原 `TaskRun`，不再启动 collector；原始 key 不写入日志，只保留 `idempotency_key_hash` 证据。
5. Dataset export create 支持 `Idempotency-Key` 本地合同：同一 workspace/dataset/version/export_format/key hash 的重复请求返回原 `DatasetExportJob`，不再重写导出文件；原始 key 不写入 `audit_events`。
6. Report send 支持 `authorized` + `confirm_send` + optional `Idempotency-Key` 本地合同：同一 workspace/report/channels/key hash 的重复请求返回原发送结果，不再创建重复站内通知；原始 key 不写入审计事件。
7. Drift alert notification/email send 支持 optional `Idempotency-Key` 本地合同：站内通知重放返回既有 notification；邮件重放读取 AlertEvent delivery audit，跳过 `send_email_notification` / SMTP/provider 调用；原始 key 不写入 payload。
8. Report asset create 支持 optional `Idempotency-Key` 本地合同：`github-tool-report-assets` 与 `public-content-report-assets` 重放返回原 Report 资产，不重复创建 Report、通知、邮件或导出文件；原始 key 不写入审计事件。
9. Report subscription run/retry 必须显式 `authorized=true` 与 `confirm_run=true` / `confirm_retry=true`，并支持 optional `Idempotency-Key` replay：重复请求返回原 `ReportSubscriptionRun`，不重复生成 Report、不重复创建站内通知或触发 email provider 尝试；原始 key 不写入审计事件。
10. Email channel test 必须显式 `authorized=true` 与 `confirm_send=true`，并支持 optional `Idempotency-Key` replay：重复请求返回原 `EmailChannelTestRun`，不重复调用 SMTP/provider；原始 key 不写入 payload 或测试记录。
11. Email provider-live gate preflight 必须显式 `authorized=true` 与 `confirm_prepare=true`，并支持 optional `Idempotency-Key` replay：重复请求返回原 `EmailProviderLiveGateRun`，始终返回 `provider_call_allowed=false`、`email_send_allowed=false`、`production_write_allowed=false` 和 `provider_call_attempted=false`，不触发 SMTP/provider。
12. Email provider live-send readiness 提供只读清单：返回 `send_enabled`、allowlist 是否配置、allowlist 计数、channel 状态、必填授权字段和 `provider_call_attempted=false`，不触发 SMTP/provider，也不创建 run。
13. Email provider live-send gate 必须显式 `authorized=true`、`confirm_send=true`、`gate_run_id`、`approval_id` 和 `Idempotency-Key`；默认 `EMAIL_LIVE_SEND_ENABLED=false` 且 allowlist 为空时只创建 `EmailProviderLiveSendRun` deny 审计记录，返回 `provider_call_attempted=false`，原始 key 不写入 payload 或 run 记录。

仍需扩展：

1. provider 真实生产发送和调度触发的审批记录、生产只读清单、side-effect 日志；L4 邮件发送 runbook 已有本地文档，生产执行证据仍待授权。
2. Retry budget 的生产门禁和更完整的 operator UI。

## Task And Run

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/tasks` | query: `project_id`、`status`、`collector_type` | `CollectionTaskResponse[]` |
| `GET` | `/api/tasks/{task_id}` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/tasks/{task_id}/run` | optional header: `Idempotency-Key` | `TaskRunResponse` |
| `POST` | `/api/tasks/{task_id}/pause` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/tasks/{task_id}/resume` | 无 | `CollectionTaskResponse` |
| `GET` | `/api/tasks/{task_id}/runs` | 无 | `TaskRunResponse[]` |

运行语义：

1. `run` 会创建 TaskRun，并把采集、归一化、信号、情报链路串起。
2. 失败 run 必须记录 `error_message` 和 logs。
3. pause/resume 只改变 task 状态，不删除历史 run。
4. `CollectionTaskResponse` 暴露 `retry_delay_minutes`、`max_retry_attempts`、`retry_attempts_used`、`retry_budget_exhausted`；这些字段来自 `CollectionTask.config`，当前属于本地运行安全合同，不等于生产调度门禁已完成。
5. `POST /api/tasks/{task_id}/run` 带相同 `Idempotency-Key` 重放时返回 `200` 和原 `TaskRun`，`idempotency_replayed=true`；首次执行仍返回 `201`，并在 `TaskRun.logs` 中记录 `idempotency_key_recorded`、`scope=task_manual_run`、`raw_key_stored=false` 和 hash。

## Raw Record, Entity, Signal

| 方法 | 路径 | 响应 |
|---|---|---|
| `GET` | `/api/raw-records` | `RawRecordResponse[]` |
| `GET` | `/api/raw-records/{raw_record_id}` | `RawRecordResponse` |
| `GET` | `/api/entities` | `EntityResponse[]` |
| `GET` | `/api/entities/{entity_id}` | `EntityResponse` |
| `GET` | `/api/entities/{entity_id}/snapshots` | `EntitySnapshotResponse[]` |
| `GET` | `/api/entities/{entity_id}/signals` | `SignalResponse[]` |
| `GET` | `/api/signals` | `SignalResponse[]` |
| `GET` | `/api/signals/{signal_id}` | `SignalResponse` |

`RawRecordResponse.source_id` 与 `task_run_id` 对 legacy 记录保持有值，对 V2
记录为 `null`；V2 记录额外返回 `workflow_run_id`、`workflow_step_run_id` 和
`workflow_lineage_contract_version`。V2 写入只通过 WorkflowRun-scoped POST 的
server-registered payload-bound fixture materialization；raw-record 资源本身仍保持
只读，不接受客户端上传 record bodies。
| `GET` | `/api/signals/{signal_id}/snapshot-compare` | `SignalSnapshotCompareResponse` |

不变量：

1. RawRecord 是原始事实。
2. EntitySnapshot 是状态快照。
3. Signal 是快照差异或异常，不是最终分析文本。

## Intelligence And Evidence

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/intelligence` | query: `project_id`、`type`、`status`、`domain`、`sort` | `IntelligenceResponse[]` |
| `GET` | `/api/intelligence/{intelligence_id}` | 无 | `IntelligenceResponse` |
| `PATCH` | `/api/intelligence/{intelligence_id}/status` | `status` | `IntelligenceResponse` |
| `GET` | `/api/intelligence/{intelligence_id}/evidences` | 无 | `EvidenceResponse[]` |
| `POST` | `/api/intelligence/{intelligence_id}/feedback` | `feedback_type`、`comment?` | `IntelligenceFeedbackResponse` |

证据要求：

1. 情报详情页必须能回溯 Evidence。
2. Evidence 应带出 Signal、Entity、RawRecord、TaskRun、Source 上下文。
3. LLM 或 mock LLM 输出只允许生成 `title` 和 `summary`。

## Report

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/reports` | query: `project_id`、`report_type` | `ReportResponse[]` |
| `POST` | `/api/reports/generate` | `project_id?`、`report_type`、`period_hours?` | `ReportResponse` |
| `GET` | `/api/reports/subscriptions` | 无 | `ReportSubscriptionResponse[]` |
| `POST` | `/api/reports/subscriptions` | 订阅配置 | `ReportSubscriptionResponse` |
| `POST` | `/api/reports/subscriptions/{subscription_id}/run` | body: `authorized`、`confirm_run`; optional header: `Idempotency-Key` | `ReportSubscriptionResponse` |
| `GET` | `/api/reports/subscriptions/{subscription_id}/runs` | 无 | `ReportSubscriptionRunResponse[]` |
| `POST` | `/api/reports/subscriptions/{subscription_id}/runs/{run_id}/retry` | body: `authorized`、`confirm_retry`; optional header: `Idempotency-Key` | `ReportSubscriptionResponse` |
| `GET` | `/api/reports/{report_id}/evidence-references` | 无 | `ReportEvidenceReferenceResponse[]` |
| `GET` | `/api/reports/{report_id}/download.md` | 无 | Markdown 文件 |
| `GET` | `/api/reports/{report_id}/audit-events` | 无 | `ReportAuditEventResponse[]` |
| `POST` | `/api/reports/{report_id}/audit-events` | 审计事件 | `ReportAuditEventResponse` |
| `GET` | `/api/reports/{report_id}` | 无 | `ReportResponse` |
| `POST` | `/api/reports/{report_id}/send` | body: `authorized`、`confirm_send`、`channels?`; optional header: `Idempotency-Key` | `ReportResponse` |

## Alert And Notification

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/alert-rules` | query: `enabled` | `AlertRuleResponse[]` |
| `POST` | `/api/alert-rules` | 规则配置 | `AlertRuleResponse` |
| `PATCH` | `/api/alert-rules/{rule_id}` | 规则可编辑字段 | `AlertRuleResponse` |
| `DELETE` | `/api/alert-rules/{rule_id}` | 无 | `AlertRuleResponse` |
| `GET` | `/api/alert-events` | query: `rule_id`、`status` | `AlertEventResponse[]` |
| `PATCH` | `/api/alert-events/{event_id}` | `status` | `AlertEventResponse` |
| `GET` | `/api/notifications` | query: `unread_only`、`type` | `NotificationResponse[]` |
| `GET` | `/api/notifications/email-channel` | 无 | `EmailChannelStatusResponse` |
| `POST` | `/api/notifications/email-channel/test` | body: `authorized`、`confirm_send`; optional header: `Idempotency-Key` | `EmailChannelTestResponse` |
| `POST` | `/api/notifications/email-channel/provider-live-gate` | body: `authorized`、`confirm_prepare`、`operation`、`recipient_email?`、`max_provider_calls?`; optional header: `Idempotency-Key` | `EmailProviderLiveGateResponse` |
| `GET` | `/api/notifications/email-channel/live-send-readiness` | 无 | `EmailProviderLiveSendReadinessResponse` |
| `POST` | `/api/notifications/email-channel/live-send` | body: `authorized`、`confirm_send`、`gate_run_id`、`approval_id`、`operation`、`recipient_email?`; required header: `Idempotency-Key` | `EmailProviderLiveSendResponse` |
| `PATCH` | `/api/notifications/{notification_id}/read` | 无 | `NotificationResponse` |
| `POST` | `/api/notifications/read-all` | 无 | `NotificationReadAllResponse` |
| `POST` | `/api/notifications/read-bulk` | `notification_ids` | `NotificationReadAllResponse` |

通知规则：

1. report send 必须显式 `authorized=true`、`confirm_send=true`；带同一 `Idempotency-Key` 重放时返回 `idempotency_replayed=true` 和原 `delivered_channels` / `skipped_channels`，不会重复创建站内通知。
2. report subscription run/retry 必须显式授权与确认；带同一 `Idempotency-Key` 重放时返回同一个 `latest_run`，不会重复生成 Report、创建站内通知或触发 email provider 尝试。
3. email channel test 必须显式授权与确认；带同一 `Idempotency-Key` 重放时返回同一个测试记录，`idempotency_replayed=true`，不会重复调用 SMTP/provider。未配置 SMTP 时 `provider_call_attempted=false`。
4. email provider-live gate preflight 必须显式授权与确认；带同一 `Idempotency-Key` 重放时返回同一个 gate run，`provider_call_allowed=false`、`email_send_allowed=false`、`production_write_allowed=false`、`provider_call_attempted=false`，只形成本地预授权审计包，不发送邮件。
5. email provider live-send readiness 是只读 inventory endpoint；`status=blocked` 表示仍缺配置或 allowlist，`status=ready_pending_l4_authorization` 只表示具备进入人工审批的前置条件，不表示已允许发送。
6. email provider live-send gate 必须引用同 workspace/user 的 gate run，并显式提供 `approval_id` 与 `Idempotency-Key`；默认配置下返回 `blocked`，记录 `send_enabled=false`、`recipient_allowlisted=false`、`provider_call_attempted=false`。只有配置显式开启、recipient 命中 exact allowlist、gate ready、SMTP ready 且审批存在时才允许 sender 分支；测试仅用 fake sender 覆盖该分支。
7. alert match 会生成 alert event，并按 rule channel 生成站内通知。
8. Drift alert notification/email send 支持 `Idempotency-Key` replay；邮件 replay 不再次调用 SMTP/provider。
9. email channel 必须通过环境变量配置，未配置时接口返回禁用状态。

## Capability Read API

All routes require the existing authenticated session and are read-only.

| Method | Route | Filters / result |
|---|---|---|
| GET | `/api/capabilities/matrix` | `capability_matrix.v1`; 7 platforms, 6 channels, 42 explicit cells |
| GET | `/api/capabilities/assertions` | `platform`, `access_channel`, `resource_type`, `operation`, `support_status`; valid zero result is `[]` |
| GET | `/api/capabilities/implementations` | `platform`, `access_channel`; valid zero result is `[]` |
| GET | `/api/capabilities/implementations/{implementation_id}` | Implementation + owned Assertions + referenced Evidence |

Invalid enum query values return `422`. A missing Implementation returns `404` with `capability_implementation_not_found`. Catalog load/parse/validation failure returns `500` with `capability_catalog_load_failed`; there is no static-data fallback.

Every Matrix response carries `provider_call=false` and `production_write_allowed=false`. Evidence retains `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production_write_attempted=false`.

## Capability Discovery Preview API（GOAL-V2-04A）

This authenticated endpoint replays only repository-registered, hash-checked fixtures. It is a sibling of the canonical Capability Catalog read path and does not use the Catalog as discovery input.

| Method | Route | Request | Response | Side effect |
|---|---|---|---|---|
| POST | `/api/capabilities/discovery/preview` | `capability_discovery_preview_request.v1` | `capability_discovery_preview.v1` | AuthContext read plus offline fixture replay only |

Request contract:

```json
{
  "schema_version": "capability_discovery_preview_request.v1",
  "preview_mode": "fixture_replay",
  "fixture_ids": [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1"
  ]
}
```

`fixture_ids` must contain 1–4 unique registered IDs; extra fields, arbitrary URLs, uploaded HTML and `live_capture` are rejected. The Web default requests the four fixed fixtures above.

The response contains `source_snapshots`、`proposed_implementations`、`candidate_assertions`、`evidence`、`diagnostics` and an exact `summary`. Every Candidate is fixed to `support_status=candidate`、`verification_status=unverified`、`executable=false` and `publishable=false`. The complete validated body except `preview_fingerprint` is canonicalized and SHA-256 hashed, so request ordering does not change the deterministic response fingerprint. `generated_from_observed_at` is derived from fixture observation times, never the current clock.

The four-fixture local response currently contains 4 Sources, 4 proposed Implementations, 7 Candidate Assertions, 4 Evidence records, 2 warnings and 0 errors. All responses carry:

```text
evidence_grade=L2-fixture-or-dry-run
provider_call=false
provider_call_attempted=false
actor_run=false
browser_run=false
llm_call=false
credential_read_attempted=false
database_write=false
database_migration=false
workflow_run_created=false
candidate_publish_allowed=false
production_write_allowed=false
```

Error map:

| Status | Detail / condition |
|---|---|
| 401 | existing authentication dependency rejects the request |
| 422 | request validation or `capability_discovery_fixture_unknown` |
| 503 | `capability_discovery_fixture_invalid` for missing/hash/schema/parser dependency failure |
| 500 | `capability_discovery_contract_invalid`; unknown exceptions are sanitized to `internal_server_error` |

The route has no Session parameter. AuthContext performs existing User/Workspace SELECTs; route tests observed only SELECT statements and unchanged table counts around the Preview call. Test registration/login rows use disposable in-memory SQLite and are reported separately as `database_write=local-test-only`; Discovery business behavior remains `database_write=false`.

There are no Verify、Publish、Run、Refresh or Browser Capture operations on the Discovery endpoint itself. Its no-write contract remains unchanged; the separately authorized Governance API below consumes only a server-rebuilt registered-Fixture Preview.

Historical Route A Task 15 closeout passed API Ruff、mypy `212` files、full pytest `610 passed / 40 skipped / 11 warnings` and Alembic head `202606110027`. This evidence remains the L2 Fixture Preview baseline and does not replace the later Governance evidence.

## Platform credential settings API（local vault）

Base path: `/api/settings/platform-credentials`. Authentication uses the existing
AuthContext; update and delete additionally require the current Workspace Owner.

| Method | Route | Request | Response / effect |
|---|---|---|---|
| GET | `/api/settings/platform-credentials` | none | seven-platform configured status; never returns or decrypts a secret |
| PUT | `/api/settings/platform-credentials/{platform}` | `{ "values": { "catalog_field": "secret" } }` | validates catalog fields, encrypts the merged Workspace bundle and returns status only |
| DELETE | `/api/settings/platform-credentials/{platform}` | none | removes the Workspace/provider bundle and returns unconfigured status |

Request values are `SecretStr`; the API never returns plaintext, ciphertext or a reusable
credential reference. Platform and field names must exist in the current social provider
catalog. PUT returns `503 platform_credential_vault_unavailable` until the deployment
environment provides `PLATFORM_CREDENTIAL_MASTER_KEY`; this master key is intentionally
not configurable through the UI. Owner violations return 403, unknown platform/field
contracts return 404/422. Saving does not run a reachability check, construct a client or
call a Provider, and all settings responses fix `provider_call_allowed=false`,
`credential_read_attempted=false` and `live_execution_enabled=false`.

Revision 035 currently exists as migration source only and has not been run against a real
database. The application-managed encrypted bundle is also not yet registered as a
`secret:` runtime source; configured status is not evidence of credential reachability.

## YouTube disabled read Adapter foundation（GOAL-V2-05B）

`POST /api/automation/social-provider-youtube-read-plan` 使用既有 AuthContext 和当前
Capability Catalog resolution。严格 request 只接受：

- `query.query`、可选 UTC-aware `published_after`/`published_before`、两位
  `region_code`、BCP-47-like `relevance_language`、`date|relevance|viewCount`
  排序与 `1..50` 的 `max_items`；
- 可选 opaque `credential_reference`，仅允许 `env:NAME` 或 `secret:name` 语法。

Route 保留 typed `YouTubeReadPlanRequest` OpenAPI requestBody。FastAPI request
validation 仅在该精确 path 返回固定脱敏 422；其他 path 继续委托默认 validation
handler，不改变全局错误合同。

服务不解析、读取、回显或记录该 reference。Response 返回 deterministic
operation plan、per-method/per-bucket quota plan、fixture/hash validation、query 与
reference fingerprint；原 keyword 和 reference 字段固定为 `null`。所有响应固定：

```text
execution_enabled=false
provider_call_allowed=false
provider_call_attempted=false
credential_read_attempted=false
live_client_created=false
database_write=false
workflow_run_created=false
raw_record_write=false
dataset_write=false
production_write_allowed=false
```

`foundation_ready` 只表示 Catalog scope、fixture、quota 和 normalization foundation
完整，不依赖 optional Google SDK 或 credential；`declared_readiness` 另行表达 caller
是否提供 opaque reference。`social-provider-readiness.v2` 与
`social-provider-gate.v2` 同样把 `declared_readiness`、
`readiness_basis=caller_declared` 与 execution permission 分开，后两者的
`execution_enabled`/`provider_call_allowed` 也固定为 false。

当前记录的官方 quota evidence 使用 granular bucket：`search.list=1`
unit/request，归属独立 `youtube_search_queries` bucket，默认上限为每天 100 次调用；
`videos.list=1` unit/request，归属 `youtube_data_daily_units`，与其他非独立 bucket
端点共享默认每天 10,000 units。两个 method 保持独立 ledger entry，不把每日 bucket
上限误写成单次成本，也不压成 USD 或猜测值；Evidence 超过 30 天时返回
`foundation_ready=false` 和稳定 stale blocker。Fixture validation 最多返回 10 条去重
Evidence refs，与 quota/search/videos 三类合法输入上限一致。

Error map：401 由现有认证依赖返回；strict request 返回固定且不含输入的
`422 youtube_read_plan_request_invalid`；unknown/missing YouTube Catalog projection
为 404；Catalog resolution failure 为 500；fixture 与 normalized contract failure
分别返回 sanitized `youtube_fixture_contract_invalid` 与
`youtube_normalized_payload_invalid` 500。端点没有 Provider/network、credential
read 或业务 persistence 路径。

2026-07-19 quota refresh 新鲜证据：focused API `68 passed / 1 existing warning`、
full API `1011 passed / 73 skipped / 1 existing warning`、full Ruff、strict Mypy
`313 source files`、traceability `92/10/12` 与 CI real-E2E boundary GREEN。此前
Task 10 independent review cycle 14 已返回 `No actionable findings.`；source-only
Alembic 仍保持单一 head `202607170034`，本次没有执行 migration 或 PostgreSQL。

## Capability Governance API（GOAL-V2-04B）

Base path: `/api/capabilities/governance`. Authentication uses the existing AuthContext, but authorization is an explicit global governance membership with independent read、review and publish permissions; Workspace membership never grants governance authority.

| Method | Route | Contract | Required permission / effect |
|---|---|---|---|
| POST | `/imports` | registered Fixture IDs + expected Preview fingerprint | read; server rebuilds Preview and persists idempotent Candidate/Evidence lineage |
| POST | `/verification-tasks/{task_id}/decisions` | expected Task version、verify/reject/deprecate、reason、canonical bundle when required | review; appends immutable Decision and resolves the Task |
| POST | `/publications` | expected parent Revision + verified Decision operations | publish; appends content-addressed Snapshot and Revision |
| POST | `/publications/rollback` | expected current Revision + historical target | publish; appends a restoring Revision |
| GET | `/candidates` | pagination | read; Candidate versions only |
| GET | `/candidates/{candidate_key}` | SHA-256 logical key | read; Candidate、Evidence、open Task and latest Decision |
| GET | `/verification-tasks` | status + pagination | read |
| GET | `/verification-tasks/{task_id}` | UUID | read |
| GET | `/publications` | pagination | read; Revision ledger and current head |
| GET | `/publications/{revision_id}` | UUID | read; Revision + complete Snapshot |

Every write requires a normalized `Idempotency-Key`; exact replay returns the frozen result without another domain write, while same key/different body is `409`. All responses include `X-Request-ID`. Import never trusts a client Candidate、Evidence、URL、HTML、filesystem path or Catalog body: it accepts registered Fixture IDs and `expected_preview_fingerprint`, rebuilds the Preview on the server and classifies exact replay、first observation、Evidence refresh or semantic drift.

Candidate verification、canonical `CapabilityStatus` and publication inclusion are separate axes. A review freezes reviewer、reviewed_at、reason、Candidate fingerprint、Evidence refs and canonical bundle. Verification never publishes. Publication accepts only current verified Decisions, locks the Catalog head, materializes a complete content-addressed Snapshot and appends a Revision. Rollback appends another Revision; it never rewinds history and is unrelated to Alembic downgrade. Saved WorkflowVersions keep their frozen `catalog_snapshot_id`.

Error mapping is fail-closed: 403 governance permission、404 resource、409 stale/idempotency/task/head conflict、422 request or business contract、503 persistence unavailable、500 sanitized internal/snapshot failure. Logs retain request/action/error type without raw idempotency key、payload、secret or untrusted exception text.

Historical GOAL-V2-04B evidence (2026-07-15): its exact disposable PostgreSQL target `127.0.0.1:55367/data_scrapy_capability_governance_test` passed Alembic `027→028→027→028` and governance suite `19/19`; this remains historical and is not the 029 execution target. GOAL-V2-05A Task 13 evidence (2026-07-16): exact target `127.0.0.1:55367/local_workflow_execution_test` passed `028→029→028→029` and workflow-execution suite `14 passed`; cleanup head is `202606110029` with the three execution tables at 0 rows. Task 14 API/Web local gates passed Ruff、strict mypy `268` source files、full pytest `836 passed / 59 skipped / 1 warning`、Web unit `238`、static build `25/25` and static mock Playwright `72 passed / 12 expected skipped / 0 failed`; the earlier `next dev` mobile failures were HMR `ERR_ABORTED` and are not product evidence. All are local evidence only: `database_write=local-test-only`、`provider_call=false`、`actor_run=false`、`browser_run=false`、`llm_call=false`、`production unchanged`; CI、deployment、live Provider and production acceptance were not run.

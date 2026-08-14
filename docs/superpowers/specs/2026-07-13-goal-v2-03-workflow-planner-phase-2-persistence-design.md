---
title: GOAL-V2-03 Workflow Planner Phase Two Persistence 设计
doc_type: design
module: workflow-planner
topic: goal-v2-03-workflow-planner-phase-two-persistence
status: approved
review_status: approved
created: 2026-07-13
updated: 2026-07-13
owner: self
source: human+ai
parent_design: 2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md
depends_on: ../plans/2026-07-12-goal-v2-03-workflow-planner-phase-1.md
evidence_level: L2-local-implementation-task-gates
provider_call: false
actor_run: false
llm_call: false
database_migration: created-disposable-postgres-validated
production_boundary: production unchanged
goal_execution: phase_2_persistence_locally_complete
---

# GOAL-V2-03 Workflow Planner Phase Two Persistence 设计

> 本文固化用户在 2026-07-13 逐节确认的 Phase Two 路线 A：只持久化由服务端重新计算并通过 Fingerprint 校验的 Preview，建立 Project 级 MonitoringScope 复用、不可变 WorkflowVersion、版本级 QueryTerm 快照、版本历史和结构化比较。用户随后授权本地实现与 disposable PostgreSQL 15 验证；本文仍不授权共享或生产数据库写入、Provider/Actor/LLM 调用、Activate、Run、commit、push 或 deploy。

## 1. 文档地位与执行摘要

本文是 GOAL-V2-03 Phase Two persistence/versioning 的优先设计事实源。若与父设计第 12 节的早期占位设计冲突，以本文为准，特别是以下三点：

1. 不持久化未完成表单或 `draft` Plan；首次显式保存即为 `previewed`。
2. QueryTerm 是 WorkflowVersion 级不可变快照，不是可变 Scope 词库。
3. MonitoringScope 在 Project 内按 `scope_key` 语义复用，并通过 Version–Scope 关联冻结每个 Version 使用的 Scope 集合。

Phase Two 只把 Phase One 的 write-free Preview 变为可保存、可审计、可比较的资产历史。它不会创建执行系统，也不会使任何候选能力获得执行资格。

当前证据边界：

    phase_2_design_chat_approved=true
    phase_2_spec_file_review=approved
    phase_2_implementation_authorization=true
    phase_2_implementation_started=true
    migration_created=true
    migration_applied=disposable_pg_027_then_026_then_027
    database_write=local_disposable_postgres_only
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    workflow_run_created=false
    live_send=false
    production unchanged

### 1.1 当前实现同步（2026-07-13）

本设计仍是数据模型和产品边界的优先事实源；当前实现进度由后继实施计划记录：[`2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md`](../plans/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md)。Tasks 0-15 已完成本地验证，包含模型/迁移、事务/幂等/并发、路由、Web Save/history/Compare、serial build 与 mock E2E。Task 15 的初始浏览器二进制缺失在用户授权本地 headless-shell 下载后已重跑通过，因此状态是 `phase_2_persistence_locally_complete`。该状态不等于 real API、CI、共享/生产数据库、部署或任何 Provider/Actor/LLM/WorkflowRun 执行验收。

Phase One 的早期持久化占位内容只保留为历史基线；当前 API、架构与产品状态以稳定合同、架构文档、PRD 和本实施计划的执行证据为准。任何后续的共享数据库、生产或外部执行仍需要独立授权。

## 2. 已批准决策

### 2.1 持久化入口

- 不保存编辑中的表单草稿。
- 只有 Phase One Preview 成功返回后才显示保存入口。
- 保存接口使用原始 `preview_input` 在服务端重新计算 Preview。
- 只有重新计算得到的 Fingerprint 与 `expected_preview_fingerprint` 相等时才允许写入。
- `planning_status=resolved | partially_resolved | held` 均可保存；`held` 只代表保留规划和审计历史，不代表可执行。`partial` 只用于 Route/Step 层，不是 Plan 状态。

### 2.2 Scope 与 QueryTerm

- MonitoringScope 以 Project 为复用边界，不跨 Project 或 Workspace 共享。
- 同一 Project 内相同规范化语义产生相同 `scope_key`，复用同一 MonitoringScope。
- WorkflowVersion 通过关联表冻结使用的 Scope 集合与顺序。
- QueryTerm 每个 Version 单独写入；历史 Version 的 QueryTerm 不随新 Version 改变。

### 2.3 版本语义

- Plan 首次保存创建 v1，Plan 生命周期状态为 `previewed`。
- Plan 的 `flow_mode` 从服务端重算 Preview 冻结；同一 Plan 的后续 Version 必须保持相同 mode，切换 mode 必须新建 Plan。
- Plan 名称只在创建 v1 时提交，Phase Two 不提供 rename。
- 后续修订只能创建新 WorkflowVersion，不能覆盖历史 Version。
- 若新 Preview Fingerprint 与当前 Version 相同，返回 `semantic_no_op`，不创建空洞版本。
- A→B→A 必须创建 v3；不能对 `(workflow_plan_id, preview_fingerprint)` 建唯一约束。
- WorkflowVersion、Version–Scope 关联和 QueryTerm 使用应用层与 PostgreSQL 触发器双重不可变保护。

### 2.4 权限与生命周期

- 沿用当前权限模型：任何已登录且属于当前 Workspace 的有效成员可以保存。
- 写入记录 `created_by_user_id`。
- Phase Two 不增加 owner/editor RBAC。
- Phase Two 不提供 Plan 删除、归档、恢复、批准、激活、暂停或运行。

## 3. Goal、范围与非目标

### 3.1 Goal

让用户把当前 Project 下经过验证的 WorkflowPlanPreview 显式保存为一个 WorkflowPlan 及不可变 WorkflowVersion，并能够读取当前版本、浏览历史、查看版本详情和比较任意两个版本。

### 3.2 包含范围

- 新建 WorkflowPlan 与 v1。
- 为既有 WorkflowPlan 创建后续 Version。
- Project 内 MonitoringScope 语义去重和复用。
- Version–Scope 冻结关联。
- Version 级 QueryTerm 快照。
- Plan 列表、Plan 详情、Version 历史、Version 详情和结构化比较。
- 项目内已保存 MonitoringScope 的只读列表。
- Idempotency-Key、乐观并发、Plan 行锁和单事务保存。
- PostgreSQL 约束、不可变触发器与 Alembic migration 设计。
- Web 保存、历史和比较体验。

### 3.3 明确非目标

- 不持久化表单草稿，不自动保存。
- 不实现 Activate、Run、Pause、Approval、Schedule 或 Archive。
- 不创建 WorkflowRun、StepRun、Task、Dataset、Alert、VOC 或 Brief。
- 不调用 Provider、TikHub、Apify Actor、自托管 Collector、授权浏览器或 LLM。
- 不读取 credential、token、Cookie、密码、私钥或 `.env` 内容。
- 不回填或转换 ExtractionPlan、SiteAnalysis 或其他旧对象。
- 不升级 Capability Catalog Assertion 的 evidence status。
- 初始设计阶段不创建 migration、执行数据库写入、部署或生产验证；该历史边界已被后续的本地实施授权部分取代。当前只允许已验证的 disposable PostgreSQL 15 migration 测试，仍不允许共享/生产数据库、部署或生产验证。

## 4. 状态与领域语义

### 4.1 用户流程

    本地表单编辑
    -> POST Preview（database_write=false）
    -> 用户检查 Preview
    -> 显式 Save
    -> 服务端重算并校验 Fingerprint
    -> WorkflowPlan(status=previewed) + WorkflowVersion

表单输入在保存前只存在于前端内存。离开或刷新页面后不恢复未保存草稿。

### 4.2 两类状态不可混用

- `WorkflowPlan.status` 是资产生命周期；Phase Two 只允许 `previewed`。
- `WorkflowVersion.planning_status` 是被冻结 Preview 的规划结果；允许 `resolved`、`partially_resolved`、`held`。
- `held` Version 可以进入历史，但仍包含阻断项，不能被描述为 approved、active 或 runnable。

### 4.3 副作用语义

- Phase One Preview 响应继续固定 `database_write=false`。
- 首次 `created` 与使用新幂等键的 `semantic_no_op` 响应外层返回 `database_write=true`。
- 保存响应内嵌的冻结 Preview 继续保留 `database_write=false`，因为该字段描述规划计算本身。
- `semantic_no_op` 会写入幂等结果，因此返回 `database_write=true`、`plan_changed=false`。
- 同一幂等请求重放只读取已保存响应，返回 `database_write=false`、`plan_changed=false`、`idempotent_replay=true`；`outcome` 仍表示原始结果。
- `preview_stale`、鉴权失败、输入失败和版本冲突必须在业务数据写入前结束。

## 5. 系统架构与数据流

### 5.1 组件职责

- Phase One Planner：继续作为规范化、Query Compiler、Resolver、Preview assembly 和 Fingerprint 的唯一事实源。
- Persistence service：负责重算校验、事务编排、Scope 复用、版本创建、当前指针和幂等结果。
- Repository：负责 tenant 限定查询、行锁、插入和只读历史查询，不重新计算业务语义。
- API route：负责 Project-scoped 鉴权、Header/Schema 校验和错误映射。
- Web：管理 dirty/stale/save 状态，展示后端历史和比较结果，不重算 Fingerprint 或 diff。

### 5.2 新建 Plan 数据流

1. 完成身份与 Workspace 校验，计算 `idempotency_scope`、key hash 和规范化请求摘要。
2. 查询已完成幂等记录；同请求命中时直接重放，不受 Project 后续归档或 Catalog 变化影响。
3. 新请求检查当前 Workspace 的 Project 存在且可写。
4. 调用 Phase One Planner 重新生成 Preview。
5. 校验 `expected_preview_fingerprint`。
6. 开启事务，先锁 Project 行并再次检查状态。
7. 创建 WorkflowPlan，冻结 `name` 和服务端 Preview 的 `flow_mode`。
8. 按 `scope_key` 复用或创建 MonitoringScope。
9. 创建 WorkflowVersion v1、Version–Scope 关联和 QueryTerm 快照。
10. 将 Plan `current_version_id` 指向 v1。
11. 写入包含响应快照的幂等结果并提交。

### 5.3 创建后续 Version 数据流

1. 身份与 Workspace 校验后先查询已完成幂等记录；命中同请求时直接重放。
2. 新请求完成 active Project 检查、服务端 Preview 重算与 Fingerprint 校验。
3. 校验重算 Preview 的 `flow_mode` 与 Plan 冻结 mode 一致。
4. 事务内统一按 Project 行、WorkflowPlan 行顺序执行 `SELECT ... FOR UPDATE` 并再次检查 Project 状态。
5. 校验 `expected_current_version_id`。
6. 若 Fingerprint 与当前 Version 相同，记录 `semantic_no_op` 响应快照并提交，不更新 Plan `updated_at`。
7. 否则在锁内分配下一个 `version_number`。
8. 复用或创建 Scope，写入 Version、关联和 QueryTerm。
9. 更新 `current_version_id`，写入幂等结果并提交。

## 6. 数据模型

Phase Two 增加五张业务表和一张基础设施表。所有主键沿用仓库现有 UUID 约定；结构化快照使用项目现有 JSON 类型，不引入 JSONB 迁移；tenant 对象显式保存 `workspace_id` 和 `project_id`。

### 6.1 workflow_plans

职责：Plan 聚合根和当前版本指针。

建议字段：

- `id`
- `workspace_id`
- `project_id`
- `created_by_user_id`
- `name`
- `flow_mode`
- `status`，Phase Two 只允许 `previewed`
- `current_version_id`
- `created_at`
- `updated_at`

约束：

- `current_version_id` 必须指向属于同一 WorkflowPlan 的 Version。
- 不能只建立 `current_version_id -> workflow_versions.id` 的简单外键。
- Plan 创建事务中指针可短暂为空；事务提交时必须非空且所有权正确。
- `name` 和 `flow_mode` 在 Phase Two 内不可变；mode 不匹配的输入不能保存为该 Plan 的新 Version。
- Plan 不提供 delete 路径，不使用级联删除。

### 6.2 workflow_versions

职责：冻结一次完整、可复现的 Preview。

建议字段：

- `id`
- `workspace_id`
- `project_id`
- `workflow_plan_id`
- `created_by_user_id`
- `version_number`
- `planning_status`
- `planner_contract_version`
- `catalog_snapshot_id`
- `policy_version`
- `mode_template_version`
- `query_versions`
- `fingerprint_payload`，服务端生成的完整 canonical Fingerprint 输入
- `normalized_input`
- `plan_payload`
- `preview_fingerprint`
- `created_at`

约束：

- 唯一 `(workflow_plan_id, version_number)`。
- 为当前版本复合外键提供唯一 `(workflow_plan_id, id)`。
- 不建立 `(workflow_plan_id, preview_fingerprint)` 唯一约束。
- 创建后禁止 UPDATE 和 DELETE。
- 不设置 `updated_at`。

### 6.3 monitoring_scopes

职责：Project 内可复用的规范化 Scope 语义对象。

建议字段：

- `id`
- `workspace_id`
- `project_id`
- `created_by_user_id`
- `scope_key`
- `scope_type`
- 规范化 canonical/include/exclude terms
- 规范化 official accounts 与 seed URLs
- effective languages、regions、platforms
- `match_mode`
- `created_at`

约束：

- 唯一 `(project_id, scope_key)`。
- `scope_key` 来自 Phase One 规范化后的语义内容，不包含数据库 ID、创建时间或展示顺序。
- 相同 key 的并发创建通过唯一约束收敛到同一行。
- Phase Two 不提供 Scope 更新或归档；整行禁止 UPDATE 和 DELETE。
- 不设置会暗示真实采集已启动的 `active` 状态。

### 6.4 workflow_version_scopes

职责：冻结 Version 使用的 Scope 集合和顺序。

建议字段：

- `workspace_id`
- `project_id`
- `workflow_version_id`
- `monitoring_scope_id`
- `ordinal`
- `created_at`

约束：

- 主键或唯一键 `(workflow_version_id, monitoring_scope_id)`。
- 唯一 `(workflow_version_id, ordinal)`。
- 关联双方必须属于相同 Workspace 和 Project。
- 创建后禁止 UPDATE 和 DELETE。

### 6.5 query_terms

职责：冻结 Version 级 QueryTerm 历史。

建议字段：

- `id`
- `workspace_id`
- `project_id`
- `workflow_version_id`
- `ordinal`
- `term`
- `normalized_term`
- `origin`
- `status`
- `reason`
- `source`
- `score`
- `conflict_codes`
- `matched_scope_id`，不可空
- `created_at`

约束：

- 唯一 `(workflow_version_id, ordinal)`，保留 Phase One 确定性顺序。
- 复合外键 `(workflow_version_id, matched_scope_id)` 必须证明该 Scope 已关联到同一 WorkflowVersion。
- QueryTerm 不在不同 Version 间复用。
- 创建后禁止 UPDATE 和 DELETE。
- 所有 `ordinal` 从 0 开始。仅改变被规范化消除的 UI Scope 顺序不会改变 Fingerprint，因此会成为 `semantic_no_op`。

### 6.6 workflow_plan_save_requests

职责：持久化写接口的幂等结果。

建议字段：

- `id`
- `workspace_id`
- `project_id`
- `created_by_user_id`
- `idempotency_scope`
- `idempotency_key_hash`
- `request_hash`
- `workflow_plan_id`
- `workflow_version_id`
- `outcome`，`created | semantic_no_op`
- `response_status`
- `response_payload`，脱敏后的原始资源响应快照
- `created_at`

约束：

- 不保存或记录原始 Idempotency-Key。
- `idempotency_scope` 固定为 `workflow_plan.create:{project_id}` 或 `workflow_plan.create_version:{project_id}:{plan_id}`。
- 唯一 `(workspace_id, created_by_user_id, idempotency_scope, idempotency_key_hash)`。
- `request_hash` 使用 canonical JSON，包含 method、canonical route IDs、创建时的 name、`preview_input`、`expected_preview_fingerprint`，以及创建 Version 时的 `expected_current_version_id`。
- 相同 key 与相同 `request_hash` 返回原始 Plan、Version、outcome 和 HTTP 状态；当前 attempt 的 `database_write`、`plan_changed`、`idempotent_replay` 按 replay 事实覆盖，不能从首次响应照抄。
- 相同 key 与不同 `request_hash` 返回 `409 idempotency_conflict`。
- 创建后禁止 UPDATE 和 DELETE。

## 7. 数据完整性与不可变性

### 7.1 当前版本所有权

`workflow_plans.current_version_id` 必须使用复合所有权约束，确保当前 Version 的 `workflow_plan_id` 等于 Plan 的 `id`，同时 Workspace 和 Project 相等。Migration 可以先创建双方表，再添加该约束；不能因为循环依赖而省略所有权校验。

为闭合 tenant 完整性，Migration 增加以下 supporting UNIQUE/FK 家族：

- `projects(workspace_id, id)` supporting unique；不修改旧列或旧数据。
- Plan/Scope 的 `(workspace_id, project_id)` 复合 FK 指向 Project。
- Version 的 `(workspace_id, project_id, workflow_plan_id)` 复合 FK 指向 Plan。
- Version–Scope 分别以 `(workspace_id, project_id, workflow_version_id)` 和 `(workspace_id, project_id, monitoring_scope_id)` 指向 Version 与 Scope。
- QueryTerm 以 `(workspace_id, project_id, workflow_version_id, matched_scope_id)` 指向同 tenant 的 Version–Scope 关联。
- SaveRequest 以同 tenant 复合 FK 指向 Plan 和 Version。
- Plan 当前指针以 `(workspace_id, project_id, id, current_version_id)` 指向 `(workspace_id, project_id, workflow_plan_id, id)`。

各父表必须提供对应 supporting UNIQUE。不能只在 service 中比较 `workspace_id` 后使用单列 FK。

### 7.2 提交时完整性

首次创建 Plan 需要在同一事务内依次创建 Plan、v1 和当前指针。应用层在 commit 前检查指针；PostgreSQL deferred constraint trigger 在事务结束时按 Plan ID 重新 SELECT 最终行，再拒绝无当前 Version 的 Plan。Trigger 不能直接检查 INSERT 事件捕获的 `NEW.current_version_id=NULL`，否则会错误拒绝合法的 `NULL -> v1 -> current pointer` 单事务流程。

数据库集成测试必须覆盖：合法首次创建可提交、事务结束仍为空指针被拒绝、跨 Plan/Workspace/Project 指针被拒绝。

### 7.3 不可变触发器

数据库触发器拒绝：

- `workflow_versions` 的 UPDATE/DELETE。
- `workflow_version_scopes` 的 UPDATE/DELETE。
- `query_terms` 的 UPDATE/DELETE。
- `workflow_plan_save_requests` 的 UPDATE/DELETE。
- `monitoring_scopes` 的 UPDATE/DELETE。

Repository 不提供上述对象的 update/delete 方法。数据库触发器是越过应用层时的第二道保护，不替代服务层规则。

### 7.4 Scope key 碰撞

命中既有 `scope_key` 后必须比较规范化语义 payload。若 key 相同但内容不同，事务失败并记录不含敏感输入的结构化错误；不得静默复用错误 Scope。

## 8. API 契约

### 8.1 写接口

新建 Plan：

    POST /api/projects/{project_id}/workflow-plans
    Idempotency-Key: <opaque-client-key>

请求：

```json
{
  "name": "Competitor monitoring",
  "preview_input": {},
  "expected_preview_fingerprint": "sha256:..."
}
```

`name` 先 trim，再校验长度 `1..200`。`Idempotency-Key` 必填，trim 后长度 `12..200`；原始值不进入响应、数据库或日志。`expected_preview_fingerprint` 必须匹配 `sha256:<64 lowercase hex>`。

创建后续 Version：

    POST /api/projects/{project_id}/workflow-plans/{plan_id}/versions
    Idempotency-Key: <opaque-client-key>

Version 请求只提交 `preview_input`、`expected_preview_fingerprint` 和以下字段，不接受 `name`：

```json
{
  "expected_current_version_id": "00000000-0000-0000-0000-000000000000"
}
```

语义：

- 新建 Plan/v1：`201 Created`。
- 创建后续 Version：`201 Created`。
- 与当前 Version 语义相同：`200 OK`、`outcome=semantic_no_op`。
- 相同幂等请求重放原 HTTP 状态和资源响应快照，并把当前 attempt 标记为 `idempotent_replay=true`、`database_write=false`、`plan_changed=false`。
- Version number 由服务端在锁内生成，客户端不能指定。
- 服务端只信任可重算的 `preview_input`，不信任客户端提交的 `plan_payload`。

保存响应：

```json
{
  "database_write": true,
  "plan_changed": true,
  "outcome": "created",
  "idempotent_replay": false,
  "provider_call": false,
  "actor_run": false,
  "browser_run": false,
  "llm_call": false,
  "workflow_run_created": false,
  "execution_authorized": false,
  "plan": {},
  "version": {
    "version_number": 2,
    "editable_input": {},
    "preview": {
      "database_write": false
    }
  }
}
```

每个完整 Version 响应（Save、Plan detail 的 current Version、Version detail）必须包含 `editable_input: PlanningInput`。该字段由服务端从已持久化的 `fingerprint_payload.fingerprint_input` 重建，用于把当前或历史 Version 重新载入 Planner；Version 列表和 Compare 的 summary 不包含该字段。

`editable_input` 是规范化可编辑输入，不是原始草稿回放：服务端可生成稳定的 `scope_ref`、折叠重复 Scope，并将与 defaults 相同的 effective language、region、platform 还原为空的 Scope override。在 Planner Contract、Catalog、Policy、Mode Template、Query Compiler 和 Candidate Fixture 版本不变时，它必须满足重新 Preview 后得到原 `preview_fingerprint`；这些依赖版本升级时只保证输入语义不丢失，完整 Fingerprint 可以诚实变化并在保存时创建新 Version。Batch 输入不得携带 `schedule_intent`。响应不得暴露内部 `fingerprint_payload`，也不得要求新增 migration。

### 8.2 读接口

    GET /api/projects/{project_id}/workflow-plans
    GET /api/projects/{project_id}/workflow-plans/{plan_id}
    GET /api/projects/{project_id}/workflow-plans/{plan_id}/versions
    GET /api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}
    GET /api/projects/{project_id}/workflow-plans/{plan_id}/version-compare
    GET /api/projects/{project_id}/monitoring-scopes

Compare 使用与 `/versions/{version_id}` 不重叠的静态路径，避免 FastAPI 将 `compare` 解析为 UUID。参数：

    ?base_version_id=<id>&target_version_id=<id>

Compare 返回结构化差异：

- Plan 基础信息与 `planning_status`。
- Scope 新增、移除和顺序变化。
- QueryTerm 新增、移除和状态变化。
- policy、catalog、contract、template 与 query compiler 版本变化。
- warnings、blocking issues、route、budget、limits 和 workflow steps 变化。
- 不返回仅由 JSON 键顺序或无语义数组顺序产生的伪差异。

Plan 列表只返回当前版本摘要；Version 详情返回完整冻结 Preview 和服务端重建的 `editable_input`。三个列表接口统一使用 `limit`（默认 50，范围 1..100）和 `offset`（默认 0），响应包含 `items`、`total`、`limit`、`offset`：

- Plan：`updated_at DESC, id DESC`。
- Version：`version_number DESC`。
- MonitoringScope：`created_at DESC, id DESC`。

读取接口的顶层 operation boundary 固定 `database_write=false`、`plan_changed=false` 和全部执行/外部调用布尔值为 false。Project 归档后，当前 tenant 成员仍可读取 Plan、Version、history 和 compare；新建或保存 Version 继续返回 `project_not_active`。

### 8.3 不存在的 API

    PATCH /workflow-plans/*
    DELETE /workflow-plans/*
    POST /workflow-plans/*/activate
    POST /workflow-plans/*/run
    POST /workflow-plans/*/archive

## 9. 事务、幂等与并发

### 9.1 写入前门禁

以下步骤必须发生在业务数据写入前：

1. 校验身份和 Workspace 归属。
2. 规范化 Header/Body，计算 `idempotency_scope`、key hash 和 `request_hash`。
3. 查询已完成幂等记录；同 key、同请求直接返回不可变响应快照。
4. 新请求校验 Project 存在且可写。
5. 服务端重新生成 Preview。
6. 比较 `expected_preview_fingerprint`。

Fingerprint 不匹配必须返回 `409 preview_stale`，且不写入 Plan、Version、Scope、QueryTerm、关联或幂等记录。

### 9.2 事务边界

业务写入、当前指针和幂等结果使用同一事务。任一步失败必须全部回滚，不得留下：

- 无 Version 的 Plan。
- 无 Plan 的 Version。
- 未被 Version 使用的本次 Scope 半成品。
- 缺少 QueryTerm 或 Scope 关联的部分 Version。
- 指向错误 Plan 的 `current_version_id`。
- 没有对应结果的幂等记录。

### 9.3 并发控制

- 所有新请求统一先锁 Project 行并复查 active 状态，再锁既有 WorkflowPlan 行；锁顺序不得反转。
- 锁内再次校验 `expected_current_version_id`。
- 不一致返回 `409 version_conflict`，不自动合并。
- `version_number` 在锁内由当前状态生成。
- Scope 并发创建使用 PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING`；未返回行时读取既有对象并验证语义 payload，不能先触发普通唯一键异常使事务进入 aborted 状态。
- 获取 Project/Plan 锁后、创建业务行前必须再次查询幂等记录，覆盖两个请求同时通过第一次只读检查的竞态。
- Idempotency-Key 唯一约束是最终兜底；若最终插入仍冲突，必须回滚本请求完整事务，在新事务读取已提交记录，同 `request_hash` replay，不同 hash 返回 conflict。

## 10. 错误合同

| HTTP | code | 语义与副作用 |
|---|---|---|
| `401` | `authentication_required` | 未登录，零写入 |
| `404` | `Project not found` | 复用 Phase One 现有 detail；Project 不存在或跨 Workspace，零写入 |
| `404` | `workflow_plan_not_found` | Plan 不存在或跨 tenant，零写入 |
| `404` | `workflow_version_not_found` | Version 不存在、跨 Plan 或跨 tenant，零写入 |
| `409` | `project_not_active` | 复用 Phase One 现有 detail；Project 不可写，零业务写入 |
| `409` | `preview_stale` | 服务端 Fingerprint 不匹配，零写入 |
| `409` | `version_conflict` | 当前 Version 已推进，零业务写入 |
| `409` | `idempotency_conflict` | 相同 key 对应不同请求，零业务写入 |
| `409` | `workflow_plan_flow_mode_conflict` | 新 Preview mode 与 Plan 冻结 mode 不一致，零业务写入 |
| `422` | `validation_error` | Body、Header 或 Compare 参数无效，零写入 |
| `503` | `capability_catalog_load_failed` | 复用 Phase One Catalog 加载失败合同，零写入 |
| `503` | `workflow_planner_dependency_unavailable` | 复用 Phase One 依赖不可用合同，零写入 |
| `503` | `persistence_unavailable` | 数据库或事务不可用，不宣称成功 |
| `500` | `workflow_planner_invalid_step_graph` | 复用 Phase One topology 安全错误合同，零写入 |
| `500` | `workflow_planner_internal_error` | 未预期错误，脱敏日志，零写入 |

Phase One `WorkflowPlannerInputError` 继续返回 loc-aware 422 issues。成功响应以及 route 内映射的 404/409/normalizer 422/500/503 保留 `X-Request-ID`；FastAPI/Pydantic 在 handler 前生成的 schema 422 沿用现有合同，不承诺该 header。跨 Workspace 资源统一返回 404，不能通过错误差异枚举其他 tenant 对象。错误响应不包含原始 Idempotency-Key、数据库 SQL、内部路径、凭据或完整敏感输入。

## 11. Web 产品流程

### 11.1 Planner

- 保留现有四步 Planner 和双模式入口。
- Preview 成功后显示 `Save Preview`。
- `resolved`、`partially_resolved`、`held` 均可保存。
- `held` 保存入口明确说明不会解除阻断、批准或启动运行。
- 任一输入变化立即标记当前 Preview stale，并禁用保存。
- 必须重新 Preview 才能再次保存。
- 新建时要求 Plan 名称；保存 v1 后进入该 Plan 的版本上下文。
- 网络重试对同一次逻辑保存复用 Idempotency-Key；输入变化后生成新 key。

### 11.2 未保存变更

- 表单草稿只保存在当前页面内存。
- 存在 dirty 输入时，站内离开和浏览器刷新/关闭显示离开确认。
- 保存失败保留表单与 Preview。
- `preview_stale` 保留输入、清除可保存状态并要求重新 Preview。
- `version_conflict` 获取最新当前版本，要求重新 Preview，不静默合并。

### 11.3 Saved Plans 与历史

Saved Plans 列表展示：

- Plan 名称。
- 当前 `planning_status`。
- 当前版本号。
- Scope 和 QueryTerm 数量。
- 最近更新时间。
- 创建者。

Plan 详情默认展示当前 Version 的完整 Preview，并提供 `Edit in Planner`、Version History 和 Compare Versions。

历史版本只读，不提供一键覆盖或回滚。需要恢复旧配置时，使用该 Version 的 `editable_input` 载入 Planner，重新 Preview 后创建新 Version；乐观并发基线始终来自 Plan 最新 `current_version_id`，不能使用历史 source Version ID。

### 11.4 Compare

- 默认比较相邻版本。
- 允许选择任意 base 和 target。
- 展示结构化差异，不展示原始 JSON diff。
- Web 不重新计算差异，只消费后端 Compare contract。
- 页面不出现 Activate、Run、Schedule 或 provider 运行状态。

## 12. 安全与可观测性

### 12.1 安全

- 所有查询都以当前 Workspace 和 Project 为边界。
- Seed URL 只作为字符串进入 Phase One 纯规划，不执行 HTTP 请求。
- 写接口不接受 Secret、token、Cookie 或私钥字段。
- 原始 Idempotency-Key 只用于当前请求哈希，不写数据库、不写日志。
- `created_by_user_id` 用于审计，不作为绕过 tenant 校验的授权依据。
- 不允许客户端提交 Version ID、Version number、Scope ID 或可信 `plan_payload` 控制持久化关系。

### 12.2 结构化日志

成功写入日志至少记录：

- `request_id`
- `workspace_id`
- `project_id`
- `workflow_plan_id`
- `workflow_version_id`
- `version_number`
- `outcome`
- `preview_fingerprint`
- `planning_status`
- Scope 与 QueryTerm 数量
- `idempotent_replay`
- transaction duration

冲突与失败日志记录错误 code、请求摘要和对象 ID；不得记录原始 key、完整输入、凭据或数据库连接信息。

## 13. Alembic Migration 设计

### 13.1 Revision

计划新增：

    revision = 202606110027
    down_revision = 202606110026

实施前必须重新执行 `alembic heads`，确认 `202606110026` 仍是唯一 head；若 head 已变化，不得继续使用该 revision 编号或制造分叉。

### 13.2 Upgrade 顺序

1. 为 `projects(workspace_id, id)` 增加 supporting unique constraint。
2. 创建 `monitoring_scopes`。
3. 创建 `workflow_plans`，暂缓循环外键。
4. 创建 `workflow_versions`。
5. 创建 `workflow_version_scopes`。
6. 创建 `query_terms`。
7. 创建 `workflow_plan_save_requests`。
8. 添加 supporting unique、tenant 索引和复合外键。
9. 添加当前 Version 所有权约束与提交时最终状态检查。
10. 添加不可变触发器。

Migration 纯增量；除给 `projects` 增加无数据变化的 supporting unique 外，不改变旧表列或约束语义，不回填旧对象，不调用应用服务或外部系统。

### 13.3 Downgrade 与回滚

Downgrade 按严格逆序删除触发器、约束、索引、新增表和 `projects` supporting unique。它会销毁全部 Phase Two 数据，因此：

- 只在 disposable 本地 PostgreSQL 验证 downgrade。
- 不在共享或生产数据库无备份执行。
- 已有真实数据时优先 roll-forward 修复。
- 生产 destructive downgrade 需要备份、恢复步骤与独立用户授权。

### 13.4 生产部署阻断项

当前 health check 要求数据库 revision 与代码 bundled head 完全一致。旧、新应用实例与 migration 重叠时可能出现临时 503。生产上线前必须另行批准并选择：

- 维护窗口内协调 migration 与应用切换；或
- 先发布兼容多个 revision 的过渡版本，再执行 migration 和正式版本。

本文不选择生产策略，也不授权生产 migration 或 deploy。

## 14. 测试策略

### 14.1 Phase One 回归

- 相同 PlanningInput 继续产生确定性 Fingerprint。
- Preview endpoint 继续固定所有副作用布尔值为 false。
- Preview 前后现有业务表计数不变。
- canonical candidate-only Catalog 继续诚实返回 held。
- 不因 persistence 模块存在而调用 Provider、Actor、浏览器或 LLM。

### 14.2 模型与 Repository

- 所有唯一键、复合外键和 tenant 约束。
- Plan 当前 Version 所有权。
- Plan name/flow_mode 不可变，跨 mode 保存被拒绝。
- Scope 项目内复用和跨项目隔离。
- Version、QueryTerm、关联和幂等记录不可变。
- `matched_scope_id` 非空且必须属于同一 Version。
- `held` Preview 可以保存。
- 跨 Workspace 读取返回 not found。

### 14.3 版本、幂等与并发

- v1 创建与当前指针原子提交。
- 新语义创建 v2。
- 与当前 Fingerprint 相同返回 `semantic_no_op`。
- A→B→A 创建 v3。
- 同 key、同请求重放原结果。
- 幂等重放使用原响应快照且本次无 INSERT/UPDATE，返回 `database_write=false`、`plan_changed=false`。
- 同 key、不同请求返回 conflict。
- 两个并发写请求只能有一个推进当前 Version；另一个返回 `version_conflict`。
- 并发创建相同 Scope 最终只保留一个语义对象。

### 14.4 失败注入与错误映射

在 Scope、Version、Version–Scope、QueryTerm、当前指针和幂等结果各阶段注入失败，证明整笔事务回滚。覆盖 `401/404/409/422/503`、inactive Project、stale Preview、跨 tenant、数据库不可用和不可变触发器拒绝。

### 14.5 Web

- 输入变化使 Preview stale 并禁用保存。
- `resolved`、`partially_resolved`、`held` 保存文案和行为正确；Route `partial` 不被误映射为 Plan 状态。
- 新建 Plan、创建新 Version、semantic no-op 和 idempotent replay 状态正确。
- 离开 dirty 页面显示确认。
- 保存失败保留输入。
- 历史列表、Version 详情和 Compare 消费后端事实。
- 冲突要求重新 Preview，不静默覆盖。
- 不渲染 Activate、Run、Schedule 或 provider 执行状态。

### 14.6 PostgreSQL Migration

SQLite `create_all` 不能证明 PostgreSQL migration、复合约束或触发器正确。必须使用与当前 `docker-compose.yml` 一致的 disposable PostgreSQL 15 独立 volume 自动验证：

1. 空数据库 upgrade 到 head。
2. 带既有数据的 `202606110026` upgrade 到新 head。
3. `upgrade -> downgrade -> upgrade`。
4. downgrade 前明确确认环境可销毁。
5. 比较旧表 schema 与旧数据，证明 upgrade 未改动它们。
6. `alembic heads` 仍为单一 head，`alembic current` 与代码 head 一致。

CI 或等价本地 gate 必须新增 PostgreSQL migration job；现有只执行 `alembic heads` 的检查不足以证明 revision 可升级、可降级或触发器有效。

### 14.7 完整回归

按项目现有命令执行 targeted test、API full suite、Web unit、lint、typecheck、build 和 mock E2E。测试输出如被截断必须缩小范围或保存完整日志后再下结论。

## 15. 完成标准

只有同时满足以下条件才能声明 Phase Two persistence 本地完成：

1. 两个写接口和全部读接口符合本文合同。
2. 只有通过服务端重算和 Fingerprint 校验的 Preview 能够保存，Plan mode 与 name 规则不可绕过。
3. Scope 复用、Version–Scope 冻结和 QueryTerm 快照通过数据库集成测试。
4. 当前版本所有权、tenant 复合完整性、历史不可变、幂等和并发竞争均有 PostgreSQL 证据。
5. `preview_stale` 和事务失败无部分数据。
6. Version history 与 Compare Web 流程通过 unit 和 mock E2E。
7. Migration 在 disposable PostgreSQL 通过 upgrade/downgrade/upgrade。
8. Phase One Preview 零写入回归与全量测试通过。
9. 开发记录、API、架构和产品文档与实现一致。

完成声明必须保持证据分层：

    phase_2_persistence_locally_complete
    database_write=local_postgres_only
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    workflow_run_created=false
    live_send=false
    production unchanged

fixture、mock E2E 或 local PostgreSQL 结果不能表述为生产数据库、真实 Provider 或部署验收。

## 16. 授权门与下一步

本设计的规格审阅、实施计划审阅、本地实现和 disposable PostgreSQL 15 验证已获得用户授权并已进入实施。历史的“实施计划编写前不得改代码”门禁已完成，不能再作为当前状态陈述。

当前顺序：

1. 完成 Task 14 的文档/状态同步。
2. 运行 Task 15 的完整本地 exit gate，并只在全部命令获得新鲜证据后评估 `phase_2_persistence_locally_complete`。
3. 在用户单独授权前，保持 commit、push、PR、merge、deploy、共享/生产数据库、Provider、Activate、Run 与 WorkflowRun 未执行。

本设计没有遗留的产品或数据模型开放决策。生产 rollout 策略仍是后续 deploy 前的显式阻断项，不属于 Phase Two 本地实现范围。

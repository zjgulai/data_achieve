# Governed Task Platform C4 — Workbench Task Submission and Idempotency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `workbench_tasks` 七槽位任务单以 `Idempotency-Key` 幂等地创建，可以关联不可变 `workflow_versions`，在版本创建时固化逐步骤执行计划并校验 `collection_tasks`，并按市场幂等地提交为 `runs` 行；blocked 市场保留 run 与 gate/gap，但绝不把 `blocked` 写进 `runs.status`。

**Architecture:** C4 只做提交、幂等与计划步骤固化，不执行、不预算。`workbench_tasks` 保存七槽位、种子商品、目标价格带、任务单状态与 `idempotency_key_hash`；工作区级部分唯一索引保证同一幂等键只建一单，相同请求摘要重放返回已有任务，不同摘要返回 `idempotency_conflict`。`workflow_versions.workbench_task_id` 建立任务到计划版本的租户安全关联；版本创建时把 `execution_steps` 写入不可变 `plan_payload`，并为每个步骤创建或校验 `collection_tasks`。C4 提供 `create_initial_workflow_version_for_task` 接缝，复用既有 workflow planner 为任务单创建并批准首个版本，客户 `create_task` 与 `collect` 都调用该接缝，不建第二套计划事实。C4 提供 `services/run_creation.create_run_with_audit` 审计化 run 创建接缝：同一事务插入 run 并写 C2 `run.created`；C4 提交服务只调用该接缝，后续 C6 旧入口收敛复用同一接缝。`POST /api/runs` 在 workbench 模式下按市场创建一行 `status=queued` 的 run，用 `uq_runs_workspace_idempotency` 做幂等重放，用 `(workflow_version_id, market_code)` 部分唯一索引兜住不同幂等键的并发提交。blocked 市场的门禁写入 `authorizations.gate_status='blocked'`，结构化 gap 写入该行 `scope.gap`；run 本身仍为 `queued`。C5 在迁移 061 把 blocked G-Plan 绑定到 run；C6 执行前必须检查该门禁。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、PostgreSQL 生产 / SQLite 内存测试、pytest、ruff、mypy strict、GitNexus CLI。

## Global Constraints

- 契约优先级：`docs/design/【契约冻结】v1-表名-枚举-接口.md` > 已批准设计 `docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md` > 当前迁移与代码事实 > 其他计划。
- **C1 独占 registry。** C4 只消费 C1 登记的路径、schema、列与错误码，不修改契约文档或机器 registry。C1 必须登记 C4 的 `workbench.tasks.create`（`idempotent: true` 且 `Idempotency-Key` 头）、`workbench_tasks.idempotency_key_hash` 与工作区级部分唯一索引、`workbench_tasks.seed_products`、`workbench_tasks.target_price_band`、`workbench.tasks.update`、`workbench.tasks.gates`、`workflow_versions.plan_payload.execution_steps`、`idempotency_conflict`（绑定到 `workbench.tasks.create`）、全部错误码与复合外键；缺一项时 Task 0 停止，把缺口交回 C1。
- `workbench_tasks` 只存七槽位任务单，不记录执行状态。允许的 `status` 只有 `draft`、`submitted`、`cancelled`。
- `workbench_tasks` 同时保存任务包包型与市场角色：`package_type` 只有 `quick`、`standard`；`primary_market` 是主市场；`comparison_markets` 是对比市场数组；`acceptance_contact_id`、`max_cost_usd`、`max_pages`、`max_records`、`seed_products`、`target_price_band` 随任务单保存。`markets` JSON 是七槽位投影，服务层写入 `[primary_market] + comparison_markets`，请求不单独提交。
- `seed_products` 可空；非空时必须有 3–10 项公开链接或平台 ID（设计 §4.1）。`target_price_band` 可空；非空时是市场原币价格带，不换算、不新增档位阈值；已知金额键非负且 `min_amount <= max_amount`，未命名键原样保存。
- Quick 最多 1 个对比市场；Standard 最多 3 个对比市场。`primary_market` 不得出现在 `comparison_markets`，对比市场不得重复。不得新增其他产品阈值。
- `runs` 是唯一执行运行事实源。允许的 `status` 只有 `queued`、`running`、`completed`、`failed`、`cancelled`。禁止 `blocked`、`degraded`、`held`。
- `runs` 只新增 `market_code`；`market_role` 从 `workbench_tasks` 派生：等于 `primary_market` 时为 `primary`，否则为 `compare`。禁止新增 `runs.market_role` 或 `runs.package_type`。
- `acceptance_contact_id` 可空；空值回落到任务 `owner_id`。非空时必须是同工作区 `workspace_members` 中角色为 `owner` 或 `admin` 的成员；`member` 角色返回 422 `acceptance_contact_not_member`。复合外键保证成员存在，C2 `get_workspace_role()` 保证角色为 owner/admin。
- `max_cost_usd`、`max_pages`、`max_records` 可空；非空时不得为负。金额用 `Decimal`，不得用 float。
- `run_steps.status` 只有 `pending`、`running`、`success`、`empty`、`config_gated`、`failed`、`skipped`。
- `runs.outcome` 与 `run_steps.outcome` 只有 `success`、`empty`、`config_gated`、`failed`。禁止 `partial`。
- `run_steps` 与 `task_runs` 是 1─1 关系。C4 不创建 `run_steps`，也不创建 `task_runs`。
- 每个市场一行 `runs`。`runs.market_code` 保存 ISO 3166-1 alpha-2 大写市场码。
- 市场 blocked 只写 `authorizations.gate_status='blocked'` 与结构化 gap；不得写 `runs.status`。blocked 行必须带 `plan_version_id` 与 `scope.market_code`，供 C5 迁移 061 绑定到 run；C5 不得再为该 run 建 G-Cost pass。
- 幂等键必填。同一工作区、同一幂等键、同一参数返回第一次提交的 run 集合；同一键不同参数返回 409 `idempotency_conflict`。
- **任务单创建幂等键必填。** `POST /api/workbench/tasks` 必须带 `Idempotency-Key` 头；缺失或空值返回 422 `invalid_request`。`workbench_tasks.idempotency_key_hash` 保存 `sha256("workbench-task-create.v1:{key}")`；`uq_workbench_tasks_workspace_idempotency (workspace_id, idempotency_key_hash) WHERE idempotency_key_hash IS NOT NULL` 是唯一防线。同一工作区、同一键、同一请求摘要返回已有任务（200，`Idempotent-Replay: true`）；同一键不同摘要返回 409 `idempotency_conflict`。请求摘要由服务层对规范化请求字段计算 SHA-256，并从已持久化任务行重建同摘要；不新增第二个摘要列。
- **初始计划版本接缝。** C4 提供 `create_initial_workflow_version_for_task(session, *, workspace_id, project_id, created_by_user_id, workbench_task_id, idempotency_key)`，只调用既有 workflow planner（`build_workflow_plan_result`、`create_workflow_plan`、`transition_workflow_plan_status`）为任务单创建并批准首个版本；已有版本时复用，不再建第二个。客户 `create_task` 与 `collect` 都调用该接缝，C13 不生成计划。版本创建时写入 `workbench_task_id` 与 `execution_steps`；计划状态必须是 `approved` 且 `current_version_id` 指向该版本，`submit_workbench_task` 才接受。
- **审计化 run 创建接缝。** C4 新建 `apps/api/src/data_intelligence_hub/services/run_creation.py`，提供 `create_run_with_audit(...)`：在同一业务事务内调用 `repositories.runs.create_run` 并调用 C2 `services.audit_log.append_audit_event(action='run.created', resource_type='run', resource_id=str(run.id), actor_type='system', result='success')`。C4 提交服务只调用该接缝；后续 C6 旧入口收敛也复用该接缝。C4/C6 新增的 run 创建路径不得直接调用 `runs_repository.create_run`；旧 `POST /api/runs` 非 workbench 路径的既有直连由 C6 Task 10 用同一接缝收敛。`run.created` 只在新行插入时写，幂等重放不写。C4 不 import C6 `run_service`、`run_audit` 或任何 C6 模块，因此不依赖未来切片。
- 复用现有部分唯一索引 `uq_runs_workspace_idempotency`，不新建幂等记录表。旧索引 `uq_task_runs_task_idempotency` 与 `uq_runs_workspace_idempotency` 都必须保留。新增部分唯一索引 `uq_runs_workflow_version_market`：`(workflow_version_id, market_code) WHERE workflow_version_id IS NOT NULL AND market_code IS NOT NULL`。
- **执行步骤只在版本创建时生成。** `workflow_versions.plan_payload["execution_steps"]` 是不可变快照；批准、提交、重试都不改写。每项必须含 `step_index`、`task_id`、`endpoint_type`、`collector_type`、`depends_on`；`task_id` 必须指向同工作区同项目的 `collection_tasks` 行。C4 在版本创建事务内创建或校验这些行。
- 迁移只能有一个 head。C4 增加且只增加一个迁移：`202610220060`，`down_revision = "202610220059"`。
- 当前基线 HEAD 是 `f0560ca`，Alembic 当前 head 是 `202610210055`。C0/C1/C2 是前置；C4 从 `feat/gov-c3` 创建 `/Users/lute/Project/data_scrapy-gov-c4` 后，开工前 Alembic head 必须是 `202610220059`。此后所有 Run/Commit 命令的根目录是 `/Users/lute/Project/data_scrapy-gov-c4`，包括 `apps/api` 子路径；主工作树 `/Users/lute/Project/data_scrapy` 只用于 Task 0 Step 0 的 `git worktree prune`、前驱断言与 `cp` 源。
- 不做预算账本。`run_ledger_entries` 八列与六种 `entry_kind` 不得改变；C4 不写任何账本行。
- 不做多步骤执行、不创建 `run_steps`、不调用 collector、不调用 provider。
- 不做 `/workbench` 前端页面。浏览器最小验收交接给 C14；C4 只交 API、服务签名、测试与验收清单。
- **开关与回滚点。** `WORKBENCH_TASKS_ENABLED` 默认 `false`。关闭时 workbench 路由与 `POST /api/runs` 的 workbench 模式返回 503 `workbench_disabled`，非 workbench 的旧 `POST /api/runs` 行为不变。回滚先关开关，再回退代码；迁移 `202610220060` 的 downgrade 只在 `workbench_tasks`、`workflow_versions.workbench_task_id`、`runs.market_code` 无新数据时执行。
- 每次编辑函数、类或方法前必须跑 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。`risk: UNKNOWN` 按未解决处理，必须用文本搜索确认。HIGH/CRITICAL 必须在提交说明里报告，不得用 `riskSharedAxes` 豁免。
- 每次提交前必须跑 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不是干净检查；必须重跑。
- 测试驱动：先写失败测试，再写最小实现，再跑通过。每个任务结束提交一次；每个 commit 前重跑 detect-changes。
- 代码风格：ruff line-length 100，mypy strict。金额只用 `Decimal`，不得用 float。
- 生产 A/B 门禁：C4 不部署，也不执行任何生产写操作。生产 A/B 的备份、迁移、compose/env 变更、重启与功能开关切换只属于 PG0 发布批次；C14 只做只读 health/canary/preflight 与浏览器验收。C4 只保留交接清单。生产 B 使用 `configs/deploy/scrapy/docker-compose.yml`，与 A 共用；不修改 `configs/deploy/scrapy-new/**`。生产 A 不重建 edge。

## 切片、迁移、开关与回滚点

| 项 | C4 |
|---|---|
| 切片 | 任务单七槽位、创建幂等、版本关联、初始版本接缝、执行步骤固化、逐市场幂等提交 |
| 迁移 | 只新增 `202610220060_workbench_task_submission.py`，`down_revision=202610220059` |
| 开关 | `WORKBENCH_TASKS_ENABLED`，默认 `false`；只由 PG0 发布批次切换 |
| 回滚点 | 关开关 → 回退代码 → 迁移 downgrade（无新数据时）→ 恢复备份 |
| 外部依赖 | C1 registry、C2 `get_workspace_role`、C5 绑定 blocked G-Plan、C6 执行步骤解析、PG0 发布批次、C14 只读验收；taxonomy 由 C4 自持 |

## Contract Addendum C4（以 C1 契约为准）

C1 已冻结以下 C4 消费的机器契约。Task 0 必须逐项核对；缺一项就停止，不在 C4 里静默改契约。

| 对象 | C4 契约 |
|---|---|
| `workbench_tasks` | 表名、七槽位列、`package_type`（quick/standard）、`primary_market`、`comparison_markets`、`acceptance_contact_id`（owner/admin）、`max_cost_usd`/`max_pages`/`max_records`、`seed_products`、`target_price_band`、`idempotency_key_hash`、`status` 三值、租户唯一键 `(workspace_id, project_id, id)`、工作区级部分唯一索引 `uq_workbench_tasks_workspace_idempotency` |
| `workflow_versions.workbench_task_id` | 可空 UUID；复合外键指向 `workbench_tasks(workspace_id, project_id, id)`；`workflow_versions.plan_payload.execution_steps` 登记为 C4 生成的不可变步骤数组 |
| `runs.market_code` | 可空 `String(2)`；非空时必须等于大写两字母；新增部分唯一索引 `uq_runs_workflow_version_market (workflow_version_id, market_code) WHERE workflow_version_id IS NOT NULL AND market_code IS NOT NULL`。`runs` 不登记 `market_role` 与 `package_type`；角色由任务单派生。 |
| 市场角色 | `market_role_for(*, primary_market, comparison_markets, market_code)`：`market_code == primary_market` 返回 `primary`；`market_code in comparison_markets` 返回 `compare`；其他值返回 `task_markets_invalid`。角色只出现在响应投影，不写 `runs`。 |
| 提交端点 | 扩展现有 `POST /api/runs`；请求带 `workbench_task_id`、`workflow_version_id` 与 `Idempotency-Key` 头；响应 `run_ids[]`、`runs[]`、`gaps[]`、`idempotent_replay` |
| 任务单端点 | `POST /api/workbench/tasks`（`Idempotency-Key` 必填；201 新建、200 重放、409 `idempotency_conflict`、422 `invalid_request`）、`GET /api/workbench/tasks`、`GET /api/workbench/tasks/{task_id}`、`PATCH /api/workbench/tasks/{task_id}`、`GET /api/workbench/tasks/{task_id}/gates`；C1 registry id 分别为 `workbench.tasks.create`、`workbench.tasks.list`、`workbench.tasks.detail`、`workbench.tasks.update`、`workbench.tasks.gates` |
| 初始版本接缝 | `create_initial_workflow_version_for_task(session, *, workspace_id, project_id, created_by_user_id, workbench_task_id, idempotency_key) -> uuid.UUID`；只调用既有 planner 的 `build_workflow_plan_result`、`create_workflow_plan`、`transition_workflow_plan_status`。已有版本时复用；计划必须 `approved` 且 `current_version_id` 指向该版本。C13 `create_task` 与 `collect` 只调用此接缝。 |
| run 创建接缝 | C4 提供 `create_run_with_audit`：同一事务调用 `repositories.runs.create_run` 与 C2 `append_audit_event(action='run.created')`。C1 登记 `run.created` 的 owner 为 C4；C6 旧入口收敛只调用该接缝，不直接写 `run.created`。 |
| 幂等 | 复用 `uq_runs_workspace_idempotency`；每市场派生 `sha256("workbench-submit.v1:{key}:{market}")`。该前缀是 C4 内部派生常量，不要求成为 C1 路径。 |
| 市场门禁 | `authorizations` 行：`gate_id='G-Plan'`、`gate_status='blocked'`、`plan_version_id=workflow_version_id`、`scope.market_code`、`scope.gap` 保存结构化 gap。C4 不写 `run_id`（该列由 C5 迁移 061 增加）；C5 必须把该 blocked 行绑定到对应 run，且不得再建 G-Cost pass。 |
| gap 结构 | `market_code`、`domain='market'`、`reason_code='market_unsupported'`、`impact`、`customer_message`、`remediation`、`severity` |
| 错误码 | `workbench_disabled`、`invalid_request`、`market_unsupported`、`project_access_forbidden`、`task_not_found`、`task_locked`、`task_markets_invalid`、`package_type_invalid`、`comparison_markets_exceeded`、`acceptance_contact_not_member`、`budget_invalid`、`workflow_version_not_found`、`workflow_version_not_linked`、`plan_not_approved`、`plan_version_not_current`、`workflow_version_already_submitted`、`idempotency_conflict`、`idempotency_state_inconsistent`、`taxonomy_unavailable`、`execution_steps_missing`、`execution_step_unresolved`、`collection_task_invalid` |
| 不新增 | 不新增 gap 表、不新增幂等表、不新增 `runs.status` 枚举值、不新增 `run_steps` 记录、不新增 `runs.market_role`/`runs.package_type`、不修改 C1 registry 文件 |

## File Structure

| 文件 | 责任 |
|---|---|
| `apps/api/alembic/versions/202610220060_workbench_task_submission.py` | 唯一迁移：`workbench_tasks`（含 `seed_products`、`target_price_band`、`idempotency_key_hash` 与 `uq_workbench_tasks_workspace_idempotency`）、`workflow_versions.workbench_task_id`、`runs.market_code`、`uq_runs_workflow_version_market`；保留旧索引 |
| `apps/api/src/data_intelligence_hub/models/workbench.py` | `WorkbenchTask` ORM；七槽位列、`package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`、`seed_products`、`target_price_band`、`idempotency_key_hash`、预算列与状态 CHECK |
| `apps/api/src/data_intelligence_hub/models/workflow_plan.py` | `WorkflowVersion.workbench_task_id` 复合外键与索引 |
| `apps/api/src/data_intelligence_hub/models/run.py` | `Run.market_code` 列、CHECK 与索引 |
| `apps/api/src/data_intelligence_hub/models/__init__.py` | 导出 `WorkbenchTask` |
| `apps/api/src/data_intelligence_hub/core/markets.py` | 11 个正式市场常量；C4 与 settings 共用 |
| `apps/api/src/data_intelligence_hub/core/config.py` | `workbench_enabled_markets`、`workbench_taxonomy_path`（相对值由 taxonomy 服务按应用根解析） |
| `configs/deploy/scrapy/docker-compose.yml` | 把 `configs/taxonomy` 只读挂载到 API 容器 `/app/configs/taxonomy`；在 `api.environment` 声明 `WORKBENCH_*` 容器环境变量；A/B 共用同一权威 compose；不重建 edge |
| `apps/api/src/data_intelligence_hub/schemas/workbench.py` | 七槽位请求/响应、包型/主对比市场/验收联系人/预算字段、`seed_products`、`TargetPriceBand`/`target_price_band`、gap、提交响应、门禁响应 |
| `apps/api/src/data_intelligence_hub/services/workbench/__init__.py` | workbench 服务包 |
| `apps/api/src/data_intelligence_hub/services/workbench/errors.py` | 领域错误与 HTTP 映射码 |
| `apps/api/src/data_intelligence_hub/services/workbench/markets.py` | 市场启用判定与 `market_role` 派生 |
| `apps/api/src/data_intelligence_hub/services/workbench/taxonomy.py` | `resolve_workbench_taxonomy_path()` 按仓库/应用根解析路径（不依赖 cwd）并支持绝对路径环境变量；`load_maternal_category_ids()` 读取 taxonomy；缺文件 fail-closed |
| `apps/api/src/data_intelligence_hub/services/workbench/idempotency.py` | 创建幂等键规范化、`sha256("workbench-task-create.v1:{key}")`、请求/持久化行指纹 |
| `apps/api/src/data_intelligence_hub/services/workbench/tasks.py` | 创建、更新、读取任务单；七槽位、包型/主对比市场、种子商品、价格带、预算、验收联系人 owner/admin 校验；创建幂等重放/冲突；任务锁定 |
| `apps/api/src/data_intelligence_hub/services/workbench/initial_version.py` | `create_initial_workflow_version_for_task`：复用既有 planner 创建/批准首个版本；已有版本时只校验并复用 |
| `apps/api/src/data_intelligence_hub/services/workbench/submission.py` | 逐市场幂等提交；按 `primary_market`/`comparison_markets` 建 run；blocked gate/gap；事务 |
| `apps/api/src/data_intelligence_hub/services/run_creation.py` | 新建。C4 拥有的审计化 run 创建接缝：同事务调用仓储 `create_run` 与 C2 `append_audit_event('run.created')`；C4 提交与 C6 旧入口收敛的唯一 run 创建入口；不依赖 C6 |
| `apps/api/src/data_intelligence_hub/repositories/workbench_tasks.py` | 任务单、按幂等摘要查询、版本关联、任务 run 查询 |
| `apps/api/src/data_intelligence_hub/repositories/runs.py` | `market_code` 写入、按幂等摘要批量查询、按版本列 run |
| `apps/api/src/data_intelligence_hub/repositories/authorizations.py` | 按计划版本列门禁行 |
| `apps/api/src/data_intelligence_hub/repositories/workflow_plans.py` | 版本与计划联查 |
| `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py` | 计划/版本创建时写入 `workbench_task_id` |
| `apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py` | 计划/版本请求与响应增加 `workbench_task_id` |
| `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py` | `WorkflowPlanPreview` 增加 `execution_steps: list[ExecutionStepPreview]`，默认空列表；只允许 C4 在版本创建时写入 |
| `apps/api/src/data_intelligence_hub/services/workbench/execution_steps.py` | 从计划预览的 eligible route plan 生成步骤；解析 `collection_tasks`；失败 fail-closed |
| `apps/api/tests/unit/test_workbench_execution_steps.py` | 步骤生成、collection_tasks 创建/校验、不可变快照、错误码 |
| `apps/api/src/data_intelligence_hub/api/routes/workbench.py` | `/api/workbench/tasks` 创建（`Idempotency-Key`）、列表、详情、更新、门禁 |
| `apps/api/src/data_intelligence_hub/api/routes/runs.py` | 扩展 `POST /api/runs` 的 workbench 模式 |
| `apps/api/src/data_intelligence_hub/schemas/run.py` | `RunCreateRequest` 增加 workbench 字段；`RunResponse` 增加 `market_code` |
| `apps/api/src/data_intelligence_hub/main.py` | 挂载 workbench 路由 |
| `configs/taxonomy/maternal_v1.json` | C4 创建并拥有首期生产母婴二级品类闭集；运行时只读；与测试夹具逐字节一致 |
| `apps/api/tests/fixtures/maternal_v1.json` | C4 测试用冻结品类夹具；与生产 taxonomy 逐字节一致 |
| `apps/api/tests/unit/workbench_support.py` | 测试种子：用户、工作区、owner/admin/member、项目、任务单、计划版本 |
| `apps/api/tests/unit/test_workbench_task_models.py` | 表、列、创建幂等唯一索引、约束、旧索引、迁移单 head |
| `apps/api/tests/unit/test_workbench_schemas.py` | 七槽位与市场/语言/时间窗/种子商品/价格带校验；taxonomy 路径按仓库根解析且绝对覆盖优先 |
| `apps/api/tests/unit/test_workbench_task_repository.py` | 任务单仓储、幂等摘要查询、版本关联、任务 run 查询 |
| `apps/api/tests/unit/test_workbench_initial_version.py` | 初始计划版本接缝：复用、批准、单版本、错误码 |
| `apps/api/tests/unit/test_workbench_submission_service.py` | 幂等、冲突、blocked gate/gap、无账本/无步骤、`run.created` 审计 |
| `apps/api/tests/unit/test_run_creation.py` | 审计化 run 创建接缝：新 run 恰好一条 `run.created`；幂等重放零新增 |
| `apps/api/tests/integration/test_workbench_task_routes.py` | 任务单 API 全链路、创建幂等、验收联系人 owner/admin |
| `apps/api/tests/integration/test_workbench_submission_routes.py` | `POST /api/runs` 提交、重放、冲突、blocked 市场、租户隔离 |

## GitNexus Baseline（2026-10-22 实测）

计划编写时已在主工作树执行以下命令。实施时必须在 `/Users/lute/Project/data_scrapy-gov-c4` 内、编辑前重跑并报告同样的身份与风险。

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "Run" --direction upstream --repo .
node .gitnexus/run.cjs impact "WorkflowVersion" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_workflow_plan" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_workflow_version" --direction upstream --repo .
node .gitnexus/run.cjs impact "transition_workflow_plan_status" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_run" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

实测结果：

| 目标 | 风险 | 影响 | 必须报告 |
|---|---|---|---|
| `Run`（Class，`models/run.py`） | MEDIUM | 16 impacted，10 direct，0 processes | 只加可空列 `market_code`，不改现有状态迁移 |
| `WorkflowVersion`（Class，`models/workflow_plan.py`） | MEDIUM | 21 impacted，10 direct，0 processes | 只加可空关联列，不改版本快照校验 |
| `create_workflow_plan` | LOW | 1 direct：`create_workflow_plan_item` | 请求 schema 增加可空字段；初始版本接缝复用此服务 |
| `create_workflow_version` | LOW | 1 direct：`create_workflow_version_item` | 请求 schema 增加可空字段 |
| `transition_workflow_plan_status` | LOW | 1 direct：plan 状态路由 | 初始版本接缝只做 `previewed → approved`，不改转移表 |
| `create_run`（repositories/runs.py） | LOW | 5 impacted，2 direct | 增加可选参数 `market_code`，默认 `None` |
| `create_run`（api/routes/runs.py） | UNKNOWN | 0 resolved callers | 这是路由函数；用 `grep -rn "runs_router\|/api/runs"` 确认挂载后再改 |

`detect-changes --scope all` 当时输出 `未检测到变更。`。每个任务提交前重跑；若出现 `partial: true` 或 `truncated: true`，必须重跑。

---

### Task 0: 前置、契约与 GitNexus 预检

**Files:**
- Copy: `docs/superpowers/plans/2026-10-22-governed-task-platform-c4-task-submission-idempotency.md` 到新工作树（若不存在）。
- 不修改仓库文件。

**Interfaces:**
- Consumes: C0/C1/C2 的迁移链与契约条目。
- Produces: 独立工作树 `/Users/lute/Project/data_scrapy-gov-c4`（分支 `feat/gov-c4`，来自 `feat/gov-c3`）与已同步的 `apps/api/.venv`；C4 在 Task 2 创建 `configs/taxonomy/maternal_v1.json`。不通过就停止。

- [ ] **Step 0: 从 C3 分支创建独立 worktree**

Run（只在主工作树执行 `git worktree prune`、前驱断言与 `cp` 源；后续所有 Run/Commit 都在新工作树）：

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c3^{commit}
test ! -e /Users/lute/Project/data_scrapy-gov-c4 && echo "worktree_path_free"
git worktree add /Users/lute/Project/data_scrapy-gov-c4 -b feat/gov-c4 feat/gov-c3
cd /Users/lute/Project/data_scrapy-gov-c4
test "$(git branch --show-current)" = feat/gov-c4 && echo "branch=feat/gov-c4"
mkdir -p docs/superpowers/plans
test -f docs/superpowers/plans/2026-10-22-governed-task-platform-c4-task-submission-idempotency.md || cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c4-task-submission-idempotency.md docs/superpowers/plans/
git merge-base --is-ancestor feat/gov-c3 HEAD; echo "c3_ancestor=$?"
cd apps/api && uv sync
cd /Users/lute/Project/data_scrapy-gov-c4
```

Expected:

```text
worktree_path_free
branch=feat/gov-c4
c3_ancestor=0
```

`git rev-parse --verify feat/gov-c3^{commit}` 必须输出 C3 提交 SHA。`feat/gov-c3` 不存在、`/Users/lute/Project/data_scrapy-gov-c4` 已存在、分支名不是 `feat/gov-c4` 或 `c3_ancestor` 非 0 时停止。`feat/gov-c4` 已存在时停止，先审查旧分支，不得复用。`uv sync` 在 `apps/api` 建立 `.venv`。本计划的 Markdown 不在 `feat/gov-c3` 内，必须先从主工作树复制到新工作树，后续 Commit 才会包含它。主工作树 `/Users/lute/Project/data_scrapy` 只用于本 Step 的 `git worktree prune`、前驱断言与 `cp` 源。

- [ ] **Step 1: 确认 HEAD 与工作区**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git rev-parse --short HEAD
git status --short
git merge-base --is-ancestor f0560ca HEAD && echo "baseline-ancestor-ok"
git rev-parse HEAD | tee /tmp/c4-base-sha
```

Expected:
- `git status --short` 为空或只有本计划文件。
- 输出 `baseline-ancestor-ok`。
- HEAD 不是 `f0560ca`。若仍是 `f0560ca`，说明 C0/C1/C2 未落地，停止。

- [ ] **Step 2: 确认 Alembic 单 head 是 C2 head**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/alembic heads
```

Expected:

```text
202610220059 (head)
```

若输出多行或不是 `202610220059`，停止。不要为了让 C4 迁移接上而修改 C0/C1/C2 的 revision。

- [ ] **Step 3: 核对 C1 契约条目**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
rg -n "workbench_tasks|workflow_versions.workbench_task_id|runs.market_code|plan_payload|execution_steps|package_type|primary_market|comparison_markets|acceptance_contact_id|max_cost_usd|seed_products|target_price_band|idempotency_key_hash|uq_workbench_tasks_workspace_idempotency" \
  "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json
rg -n "package_type_invalid|comparison_markets_exceeded|acceptance_contact_not_member|budget_invalid" \
  configs/contracts/v1.1.0/registry.json
rg -n "workbench.tasks.create|workbench.tasks.update|workbench.tasks.gates|uq_runs_workflow_version_market|idempotency_conflict" \
  configs/contracts/v1.1.0/registry.json
rg -n "idempotency_conflict|taxonomy_unavailable|workflow_version_already_submitted|plan_not_approved|task_locked|workbench_disabled" \
  configs/contracts/v1.1.0/registry.json
rg -n "run\.created" \
  configs/contracts/v1.1.0/registry.json \
  apps/api/src/data_intelligence_hub/services/audit_log.py
```

Expected: 每条都有命中。C1 必须已登记 `workbench_tasks`（含 `package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`、`max_cost_usd/max_pages/max_records`、`seed_products`、`target_price_band`、`idempotency_key_hash` 与 `uq_workbench_tasks_workspace_idempotency`）、`workflow_versions.workbench_task_id` 复合外键、`runs.market_code`、`runs` 的部分唯一索引、`workflow_versions.plan_payload.execution_steps`、五个任务单/提交路径、`workbench.tasks.create` 的 `idempotent: true` 与 `Idempotency-Key` 语义、`idempotency_conflict` 绑定到该路径、全部错误码。`runs` 不得登记 `market_role` 或 `package_type`。缺一项时停止，把缺口交回 C1；C4 不改契约或 registry。`workbench-task-create.v1` 是 C4 内部派生常量，不要求出现在 registry。若 C1 已登记同义列名（例如 `workflow_versions.task_id`、`runs.market` 或 `workbench_tasks.request_hash`），以 C1 为准，停止并把本计划的代码名统一替换为 C1 名称；不得两套列名并存。若 C1 要求单独保存请求摘要列，C4 必须消费该列并停止使用行重建摘要；不得同时保留两套摘要。taxonomy 文件是 C4 的产物：只要求 registry 登记 `taxonomy_unavailable` 错误码，不要求已批准设计或 registry 出现 `configs/taxonomy/maternal_v1.json` 字面路径；不要用 rg 断言设计文档包含该路径。`run.created` 的 registry owner 必须是 C4；C2 `services.audit_log.AUDIT_ACTIONS` 必须包含 `run.created`，否则 C4 接缝写入会被 `audit_action_unregistered` 拒绝；缺失时停止并把缺口交回 C1/C2。

- [ ] **Step 4: 确认 production taxonomy 尚未被其他切片创建**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
test ! -e configs/taxonomy/maternal_v1.json && echo "taxonomy-owned-by-c4"
test ! -e apps/api/tests/fixtures/maternal_v1.json && echo "fixture-owned-by-c4"
```

Expected: 输出两行。C4 在 Task 2 同时创建生产 taxonomy 与测试夹具。若任一文件已存在，先比较内容与 C4 冻结 JSON；内容不同则停止，把 taxonomy 所有权冲突交回总索引处理。不得静默覆盖。

- [ ] **Step 5: 重跑 GitNexus 基线并记录风险**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "Run" --direction upstream --repo .
node .gitnexus/run.cjs impact "WorkflowVersion" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_workflow_plan" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_workflow_version" --direction upstream --repo .
node .gitnexus/run.cjs impact "transition_workflow_plan_status" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_run" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 与“GitNexus Baseline”表一致；`create_run` 仍是 ambiguous 时，用 `--target-uid` 分别查 repository 与 route 两个 UID。任何 `risk: UNKNOWN` 必须用文本搜索确认，不得当作 low。

- [ ] **Step 6: 记录预检结果**

在提交说明或任务执行记录里写：

```text
C4 preflight: HEAD=<sha> alembic_head=202610220059 workbench_tasks_enabled=false
GitNexus: Run=MEDIUM/16, WorkflowVersion=MEDIUM/21, create_workflow_plan=LOW/1,
create_workflow_version=LOW/1, transition_workflow_plan_status=LOW/1,
create_run(repo)=LOW/5, create_run(route)=UNKNOWN/0-confirmed-by-grep
C1 contract: workbench_tasks (package_type/primary_market/comparison_markets/
  acceptance_contact_id/budgets/seed_products/target_price_band/idempotency_key_hash)
  + uq_workbench_tasks_workspace_idempotency + workbench.tasks.create idempotent
  + Idempotency-Key + idempotency_conflict + workbench_task_id + market_code
  + execution_steps + workbench.tasks.update + workbench.tasks.gates
  + uq_runs_workflow_version_market + package/market errors present
```

无提交。

---

### Task 1: 迁移 060 与 ORM 模型

**Files:**
- Create: `apps/api/alembic/versions/202610220060_workbench_task_submission.py`
- Create: `apps/api/src/data_intelligence_hub/models/workbench.py`
- Modify: `apps/api/src/data_intelligence_hub/models/workflow_plan.py:135-224`
- Modify: `apps/api/src/data_intelligence_hub/models/run.py:81-145`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Test: `apps/api/tests/unit/test_workbench_task_models.py`

**Interfaces:**
- Consumes: `Base`、`UUIDPrimaryKeyMixin`、`TimestampMixin`、现有 `workflow_versions` 与 `runs` 表。
- Produces: `WorkbenchTask`、`WorkbenchTask.status`、`WorkflowVersion.workbench_task_id`、`Run.market_code`、迁移 revision `202610220060`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_workbench_task_models.py`:

```python
"""C4 workbench task 与 submission 的模型/迁移守卫。

覆盖八组规则：

1. 七槽位列与任务单状态精确。
2. `runs.status` 与 `workbench_tasks.status` 不混用。
3. `workflow_versions.workbench_task_id` 是租户安全复合外键。
4. `runs.market_code` 只接受空值或两个大写字母。
5. 旧幂等索引保留，C4 不新建幂等表。
6. 任务单创建幂等摘要按工作区唯一，且是部分唯一索引。
7. 迁移 060 是唯一 head，且接在 059 之后。
8. 迁移不建账本、不建 run_steps、不建 task_runs。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import cast

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610220060_workbench_task_submission.py"


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _check_sql(table: Table, name: str) -> str:
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == name:
            return str(constraint.sqltext).replace(" ", "")
    raise AssertionError(f"missing check constraint: {name}")


def _foreign_key_signatures(
    table: Table,
) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    signatures: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for constraint in table.constraints:
        if not isinstance(constraint, ForeignKeyConstraint):
            continue
        signatures.add(
            (
                tuple(element.parent.name for element in constraint.elements),
                tuple(element.target_fullname for element in constraint.elements),
            )
        )
    return signatures


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "workbench_task_submission_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workbench_task_has_the_seven_slots_and_metadata() -> None:
    columns = set(_table(WorkbenchTask).columns.keys())
    assert {
        "brand",
        "category",
        "competitors",
        "markets",
        "locale_by_market",
        "window_start",
        "window_end",
        "decision_question",
        "does_not_answer",
    } <= columns
    assert {
        "id",
        "workspace_id",
        "project_id",
        "created_by_user_id",
        "owner_id",
        "package_type",
        "primary_market",
        "comparison_markets",
        "acceptance_contact_id",
        "max_cost_usd",
        "max_pages",
        "max_records",
        "seed_products",
        "target_price_band",
        "idempotency_key_hash",
        "task_type",
        "task_type_confidence",
        "status",
        "created_at",
        "updated_at",
    } <= columns


def test_workbench_task_persists_package_type_and_market_roles() -> None:
    table = _table(WorkbenchTask)
    assert _check_sql(table, "package_type") == "package_typeIN('quick','standard')"
    assert _check_sql(table, "primary_market") == (
        "length(primary_market)=2ANDprimary_market=upper(primary_market)"
    )
    assert _check_sql(table, "budget_nonnegative") == (
        "(max_cost_usdISNULLORmax_cost_usd>=0)AND"
        "(max_pagesISNULLORmax_pages>=0)AND"
        "(max_recordsISNULLORmax_records>=0)"
    )
    signatures = _foreign_key_signatures(table)
    assert (
        ("workspace_id", "acceptance_contact_id"),
        ("workspace_members.workspace_id", "workspace_members.user_id"),
    ) in signatures
    assert table.c.acceptance_contact_id.nullable
    assert not table.c.package_type.nullable
    assert not table.c.primary_market.nullable
    assert not table.c.comparison_markets.nullable


def test_workbench_task_persists_seed_products_and_target_price_band() -> None:
    table = _table(WorkbenchTask)
    assert not table.c.seed_products.nullable
    assert table.c.target_price_band.nullable
    assert table.c.seed_products.type.__class__.__name__ == "JSON"
    assert table.c.target_price_band.type.__class__.__name__ == "JSON"


def test_task_create_idempotency_is_workspace_scoped_and_partial() -> None:
    index = next(
        item for item in _table(WorkbenchTask).indexes
        if item.name == "uq_workbench_tasks_workspace_idempotency"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "workspace_id",
        "idempotency_key_hash",
    ]
    assert _table(WorkbenchTask).c.idempotency_key_hash.nullable
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "uq_workbench_tasks_workspace_idempotency" in source
    assert "idempotency_key_hash IS NOT NULL" in source


def test_runs_does_not_persist_package_type_or_market_role() -> None:
    run_columns = set(_table(Run).columns.keys())
    assert "market_code" in run_columns
    assert "market_role" not in run_columns
    assert "package_type" not in run_columns


def test_workbench_task_status_is_not_execution_status() -> None:
    sql = _check_sql(_table(WorkbenchTask), "status")
    assert sql == "statusIN('draft','submitted','cancelled')"
    for forbidden in ("running", "queued", "completed", "failed", "blocked"):
        assert forbidden not in sql


def test_workflow_version_link_is_tenant_safe() -> None:
    signatures = _foreign_key_signatures(_table(WorkflowVersion))
    assert (
        ("workspace_id", "project_id", "workbench_task_id"),
        ("workbench_tasks.workspace_id", "workbench_tasks.project_id", "workbench_tasks.id"),
    ) in signatures
    assert _table(WorkflowVersion).c.workbench_task_id.nullable


def test_runs_market_code_is_optional_but_strict() -> None:
    assert _table(Run).c.market_code.nullable
    sql = _check_sql(_table(Run), "market_code")
    assert sql == (
        "market_codeISNULLOR("
        "length(market_code)=2ANDmarket_code=upper(market_code))"
    )


def test_old_idempotency_indexes_survive() -> None:
    run_indexes = {index.name for index in _table(Run).indexes}
    task_run_indexes = {index.name for index in _table(TaskRun).indexes}
    assert "uq_runs_workspace_idempotency" in run_indexes
    assert "uq_task_runs_task_idempotency" in task_run_indexes


def test_one_market_has_at_most_one_run_per_workflow_version() -> None:
    index = next(
        item for item in _table(Run).indexes
        if item.name == "uq_runs_workflow_version_market"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "workflow_version_id",
        "market_code",
    ]
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "uq_runs_workflow_version_market" in source
    assert "unique=True" in source
    assert "workflow_version_id IS NOT NULL AND market_code IS NOT NULL" in source


def test_migration_is_the_single_head_and_follows_059() -> None:
    module = _load_migration()
    assert module.revision == "202610220060"
    assert module.down_revision == "202610220059"

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["202610220060"]

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "This revision is source-only." in source
    assert 'create_table(\n        "workbench_tasks"' in source
    assert 'create_table(\n        "runs"' not in source
    assert 'create_table(\n        "run_steps"' not in source
    assert 'sa.Column("package_type", sa.String(length=10), nullable=False)' in source
    assert 'sa.Column("primary_market", sa.String(length=2), nullable=False)' in source
    assert 'sa.Column("comparison_markets", sa.JSON(), nullable=False)' in source
    assert 'sa.Column("seed_products", sa.JSON(), nullable=False)' in source
    assert 'sa.Column("target_price_band", sa.JSON(), nullable=True)' in source
    assert 'sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True)' in source
    assert 'create_index(\n        "uq_workbench_tasks_workspace_idempotency"' in source
    assert 'sa.Column("market_role"' not in source
    assert 'drop_index("uq_runs_workspace_idempotency"' not in source
    assert 'drop_index("uq_task_runs_task_idempotency"' not in source


def test_migration_does_not_add_execution_or_ledger_tables() -> None:
    module = _load_migration()
    import inspect as python_inspect

    source = python_inspect.getsource(module.upgrade)
    for forbidden in (
        "run_steps",
        "task_runs",
        "run_ledger_entries",
        "idempotency_records",
        "workbench_submission_requests",
    ):
        assert forbidden not in source
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_task_models.py -v
```

Expected: FAIL。至少出现 `ModuleNotFoundError: No module named 'data_intelligence_hub.models.workbench'` 与 `FileNotFoundError` 指向 `202610220060_workbench_task_submission.py`。

- [ ] **Step 3: 写迁移**

Create `apps/api/alembic/versions/202610220060_workbench_task_submission.py`:

```python
"""Create workbench task submission schema and reuse the existing run index.

Revision ID: 202610220060
Revises: 202610220059
Create Date: 2026-10-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- `workbench_tasks` 存七槽位任务单，不记录执行状态。
- `workbench_tasks` 同时存 `package_type`、`primary_market`、`comparison_markets`、
  `acceptance_contact_id` 与三项预算列；`markets` 是前两者的七槽位投影。
- `runs` 只加 `market_code`；`market_role` 从任务单派生，不加列。
- `workflow_versions.workbench_task_id` 用复合外键绑定同工作区同项目的任务单。
- `runs.market_code` 可空；非空时必须是两个大写字母。
- C4 复用 `uq_runs_workspace_idempotency`，不新建幂等记录表。
- 旧索引 `uq_task_runs_task_idempotency` 与 `uq_runs_workspace_idempotency` 保留。
- 本迁移不建 run_steps、task_runs、run_ledger_entries。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220060"
down_revision: str | None = "202610220059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workbench_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("brand", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("competitors", sa.JSON(), nullable=False),
        sa.Column("package_type", sa.String(length=10), nullable=False),
        sa.Column("primary_market", sa.String(length=2), nullable=False),
        sa.Column("comparison_markets", sa.JSON(), nullable=False),
        sa.Column("acceptance_contact_id", sa.Uuid(), nullable=True),
        sa.Column("max_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("max_pages", sa.Integer(), nullable=True),
        sa.Column("max_records", sa.Integer(), nullable=True),
        sa.Column("seed_products", sa.JSON(), nullable=False),
        sa.Column("target_price_band", sa.JSON(), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.Column("locale_by_market", sa.JSON(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("decision_question", sa.Text(), nullable=False),
        sa.Column("does_not_answer", sa.JSON(), nullable=False),
        sa.Column("task_type", sa.String(length=10), nullable=True),
        sa.Column("task_type_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workbench_tasks"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workbench_tasks_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workbench_tasks_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "owner_id"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            name="fk_workbench_tasks_owner_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workbench_tasks_created_by_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "acceptance_contact_id"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            name="fk_workbench_tasks_acceptance_contact_member",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'cancelled')",
            name="ck_workbench_tasks_status",
        ),
        sa.CheckConstraint(
            "window_end >= window_start",
            name="ck_workbench_tasks_window_order",
        ),
        sa.CheckConstraint(
            "package_type IN ('quick', 'standard')",
            name="ck_workbench_tasks_package_type",
        ),
        sa.CheckConstraint(
            "length(primary_market) = 2 AND primary_market = upper(primary_market)",
            name="ck_workbench_tasks_primary_market",
        ),
        sa.CheckConstraint(
            "(max_cost_usd IS NULL OR max_cost_usd >= 0) AND "
            "(max_pages IS NULL OR max_pages >= 0) AND "
            "(max_records IS NULL OR max_records >= 0)",
            name="ck_workbench_tasks_budget_nonnegative",
        ),
        sa.CheckConstraint(
            "task_type IS NULL OR task_type IN ('T1', 'T2', 'T3', 'T4', 'T5')",
            name="ck_workbench_tasks_task_type",
        ),
        sa.CheckConstraint(
            "task_type_confidence IS NULL OR "
            "(task_type_confidence >= 0 AND task_type_confidence <= 1)",
            name="ck_workbench_tasks_task_type_confidence",
        ),
    )
    op.create_index(
        "ix_workbench_tasks_workspace_project_status",
        "workbench_tasks",
        ["workspace_id", "project_id", "status"],
    )
    op.create_index(
        "ix_workbench_tasks_owner",
        "workbench_tasks",
        ["workspace_id", "owner_id"],
    )
    op.create_index(
        "uq_workbench_tasks_workspace_idempotency",
        "workbench_tasks",
        ["workspace_id", "idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("idempotency_key_hash IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key_hash IS NOT NULL"),
    )

    op.add_column(
        "workflow_versions",
        sa.Column("workbench_task_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_versions_workbench_task_tenant",
        "workflow_versions",
        "workbench_tasks",
        ["workspace_id", "project_id", "workbench_task_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_index(
        "ix_workflow_versions_workbench_task",
        "workflow_versions",
        ["workspace_id", "workbench_task_id"],
    )

    op.add_column(
        "runs",
        sa.Column("market_code", sa.String(length=2), nullable=True),
    )
    op.create_check_constraint(
        "ck_runs_market_code",
        "runs",
        "market_code IS NULL OR "
        "(length(market_code) = 2 AND market_code = upper(market_code))",
    )
    op.create_index(
        "uq_runs_workflow_version_market",
        "runs",
        ["workflow_version_id", "market_code"],
        unique=True,
        postgresql_where=sa.text(
            "workflow_version_id IS NOT NULL AND market_code IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "workflow_version_id IS NOT NULL AND market_code IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_runs_workflow_version_market", table_name="runs")
    op.drop_constraint("ck_runs_market_code", "runs", type_="check")
    op.drop_column("runs", "market_code")

    op.drop_index("ix_workflow_versions_workbench_task", table_name="workflow_versions")
    op.drop_constraint(
        "fk_workflow_versions_workbench_task_tenant",
        "workflow_versions",
        type_="foreignkey",
    )
    op.drop_column("workflow_versions", "workbench_task_id")

    op.drop_index("ix_workbench_tasks_owner", table_name="workbench_tasks")
    op.drop_index(
        "uq_workbench_tasks_workspace_idempotency",
        table_name="workbench_tasks",
    )
    op.drop_index(
        "ix_workbench_tasks_workspace_project_status",
        table_name="workbench_tasks",
    )
    op.drop_table("workbench_tasks")
```

- [ ] **Step 4: 写 `WorkbenchTask` 模型**

Create `apps/api/src/data_intelligence_hub/models/workbench.py`:

```python
"""七槽位任务单 ``workbench_tasks``。

契约冻结 v1 §1.0：``workbench_tasks`` 只存任务单，不记录执行状态。
执行状态在 ``runs``。任务单状态只有 ``draft``、``submitted``、``cancelled``。

七槽位映射：

1. brand
2. category
3. competitors
4. markets + locale_by_market
5. window_start + window_end
6. decision_question
7. does_not_answer

``package_type``、``primary_market``、``comparison_markets`` 是市场角色事实源；
``markets`` 是 ``[primary_market] + comparison_markets`` 的七槽位投影。
``seed_products`` 与 ``target_price_band`` 是设计 §4.1 的可选输入，随任务单保存。
``idempotency_key_hash`` 是创建幂等摘要；工作区级部分唯一索引保证同一键只建一单。
``owner_id`` 必须同时是工作区成员，由复合外键保证。
``acceptance_contact_id`` 可空；非空时必须也是同工作区 owner 或 admin。
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

WORKBENCH_TASK_STATUSES: tuple[str, ...] = ("draft", "submitted", "cancelled")
PACKAGE_TYPES: tuple[str, ...] = ("quick", "standard")
TASK_TYPES: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5")


class WorkbenchTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workbench_tasks"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workbench_tasks_tenant_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workbench_tasks_project_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "owner_id"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            name="fk_workbench_tasks_owner_member",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "acceptance_contact_id"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            name="fk_workbench_tasks_acceptance_contact_member",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "window_end >= window_start",
            name="window_order",
        ),
        CheckConstraint(
            "package_type IN ('quick', 'standard')",
            name="package_type",
        ),
        CheckConstraint(
            "length(primary_market) = 2 AND primary_market = upper(primary_market)",
            name="primary_market",
        ),
        CheckConstraint(
            "(max_cost_usd IS NULL OR max_cost_usd >= 0) AND "
            "(max_pages IS NULL OR max_pages >= 0) AND "
            "(max_records IS NULL OR max_records >= 0)",
            name="budget_nonnegative",
        ),
        CheckConstraint(
            "task_type IS NULL OR task_type IN ('T1', 'T2', 'T3', 'T4', 'T5')",
            name="task_type",
        ),
        CheckConstraint(
            "task_type_confidence IS NULL OR "
            "(task_type_confidence >= 0 AND task_type_confidence <= 1)",
            name="task_type_confidence",
        ),
        Index(
            "ix_workbench_tasks_workspace_project_status",
            "workspace_id",
            "project_id",
            "status",
        ),
        Index(
            "ix_workbench_tasks_owner",
            "workspace_id",
            "owner_id",
        ),
        Index(
            "uq_workbench_tasks_workspace_idempotency",
            "workspace_id",
            "idempotency_key_hash",
            unique=True,
            postgresql_where=text("idempotency_key_hash IS NOT NULL"),
            sqlite_where=text("idempotency_key_hash IS NOT NULL"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    brand: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    competitors: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    package_type: Mapped[str] = mapped_column(String(10), nullable=False)
    primary_market: Mapped[str] = mapped_column(String(2), nullable=False)
    comparison_markets: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    acceptance_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    max_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    max_pages: Mapped[int | None] = mapped_column(Integer)
    max_records: Mapped[int | None] = mapped_column(Integer)
    seed_products: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    target_price_band: Mapped[dict[str, object] | None] = mapped_column(JSON)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    markets: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    locale_by_market: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    decision_question: Mapped[str] = mapped_column(Text, nullable=False)
    does_not_answer: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(10))
    task_type_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)


__all__ = [
    "PACKAGE_TYPES",
    "TASK_TYPES",
    "WORKBENCH_TASK_STATUSES",
    "WorkbenchTask",
]
```

- [ ] **Step 5: 修改 `WorkflowVersion` 与 `Run`**

In `apps/api/src/data_intelligence_hub/models/workflow_plan.py`, add to `WorkflowVersion.__table_args__` after the existing tenant constraints:

```python
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workbench_task_id"],
            [
                "workbench_tasks.workspace_id",
                "workbench_tasks.project_id",
                "workbench_tasks.id",
            ],
            name="fk_workflow_versions_workbench_task_tenant",
        ),
        Index(
            "ix_workflow_versions_workbench_task",
            "workspace_id",
            "workbench_task_id",
        ),
```

Add `Index` and `text` to the `sqlalchemy` import list. Add the column before `created_at`:

```python
    workbench_task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
```

In `apps/api/src/data_intelligence_hub/models/run.py`, add to `Run.__table_args__`:

```python
        CheckConstraint(
            "market_code IS NULL OR "
            "(length(market_code) = 2 AND market_code = upper(market_code))",
            name="ck_runs_market_code",
        ),
        Index(
            "uq_runs_workflow_version_market",
            "workflow_version_id",
            "market_code",
            unique=True,
            postgresql_where=text(
                "workflow_version_id IS NOT NULL AND market_code IS NOT NULL"
            ),
            sqlite_where=text(
                "workflow_version_id IS NOT NULL AND market_code IS NOT NULL"
            ),
        ),
```

Add the column after `workflow_version_id`:

```python
    market_code: Mapped[str | None] = mapped_column(String(2))
```

- [ ] **Step 6: 导出模型**

In `apps/api/src/data_intelligence_hub/models/__init__.py`, add:

```python
from data_intelligence_hub.models.workbench import WorkbenchTask
```

and add `"WorkbenchTask",` to `__all__` in alphabetical position.

- [ ] **Step 7: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_task_models.py -v
```

Expected: 12 passed。

- [ ] **Step 8: 跑迁移单 head 与静态检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/alembic heads
.venv/bin/ruff check src/data_intelligence_hub/models/workbench.py src/data_intelligence_hub/models/run.py src/data_intelligence_hub/models/workflow_plan.py tests/unit/test_workbench_task_models.py
.venv/bin/mypy src/data_intelligence_hub/models/workbench.py
```

Expected:
- `202610220060 (head)`
- `All checks passed!`
- `Success: no issues found in 1 source file`

- [ ] **Step 9: GitNexus 变更检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 输出包含 `workbench.py`、`run.py`、`workflow_plan.py`、迁移与测试；`partial` 与 `truncated` 均不是 true。若 `partial: true`，重跑。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/alembic/versions/202610220060_workbench_task_submission.py \
  apps/api/src/data_intelligence_hub/models/workbench.py \
  apps/api/src/data_intelligence_hub/models/workflow_plan.py \
  apps/api/src/data_intelligence_hub/models/run.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/tests/unit/test_workbench_task_models.py
git commit -m "feat(workbench): add task submission schema (C4)"
```

---

### Task 2: 七槽位 schema、市场常量与 taxonomy 校验

**Files:**
- Create: `apps/api/src/data_intelligence_hub/core/markets.py`
- Create: `apps/api/src/data_intelligence_hub/schemas/workbench.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench/markets.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench/taxonomy.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench/errors.py`
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Create: `configs/taxonomy/maternal_v1.json`
- Modify: `configs/deploy/scrapy/docker-compose.yml`
- Create: `apps/api/tests/fixtures/maternal_v1.json`
- Test: `apps/api/tests/unit/test_workbench_schemas.py`

**Interfaces:**
- Consumes: `get_settings()`。
- Produces: `configs/taxonomy/maternal_v1.json`、API 容器只读 taxonomy 挂载与 `WORKBENCH_*` 环境变量、`FORMAL_MARKET_CODES`、`WorkbenchTaskCreateRequest`、`WorkbenchTaskUpdateRequest`、`WorkbenchTaskResponse`、`WorkbenchGapResponse`、`WorkbenchSubmissionResponse`、`resolve_workbench_taxonomy_path()`、`load_maternal_category_ids()`、`resolve_market_decisions()`。生产 taxonomy 与测试夹具必须逐字节一致。

- [ ] **Step 1: 写失败测试**

Create `configs/taxonomy/maternal_v1.json` and `apps/api/tests/fixtures/maternal_v1.json` with identical bytes:

```json
{
  "version": "maternal_v1",
  "categories": [
    {"id": "breast_pump", "name_zh": "吸乳器"},
    {"id": "stroller", "name_zh": "婴儿推车"},
    {"id": "sleep_bag", "name_zh": "睡袋"}
  ]
}
```

Create `apps/api/tests/unit/test_workbench_schemas.py`:

```python
"""七槽位 schema 与 taxonomy 读取的单元测试。"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.markets import FORMAL_MARKET_CODES
from data_intelligence_hub.schemas.workbench import (
    TargetPriceBand,
    WorkbenchTaskCreateRequest,
    WorkbenchTaskUpdateRequest,
)
from data_intelligence_hub.services.workbench.taxonomy import (
    TaxonomyUnavailableError,
    load_maternal_category_ids,
    resolve_workbench_taxonomy_path,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures/maternal_v1.json"
PRODUCTION_PATH = Path(__file__).resolve().parents[4] / "configs/taxonomy/maternal_v1.json"


def test_production_taxonomy_matches_frozen_fixture() -> None:
    assert PRODUCTION_PATH.read_bytes() == FIXTURE_PATH.read_bytes()


def test_taxonomy_path_resolves_from_repository_root_not_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WORKBENCH_TAXONOMY_PATH", raising=False)
    get_settings.cache_clear()
    try:
        assert resolve_workbench_taxonomy_path() == PRODUCTION_PATH
    finally:
        get_settings.cache_clear()


def test_taxonomy_path_absolute_override_wins(tmp_path: Path) -> None:
    override = tmp_path / "maternal_v1.json"
    assert resolve_workbench_taxonomy_path(str(override)) == override


def _payload(**overrides: object) -> dict[str, object]:
    today = date.today()
    payload: dict[str, object] = {
        "brand": " Momcozy ",
        "category": "breast_pump",
        "competitors": ["Medela"],
        "package_type": "standard",
        "primary_market": "us",
        "comparison_markets": ["de"],
        "locale_by_market": {"US": "en", "DE": "de"},
        "window": {
            "start": (today - timedelta(days=90)).isoformat(),
            "end": today.isoformat(),
        },
        "decision_question": "Fit 与支撑哪个是主要摩擦？",
        "does_not_answer": ["不推断销量与市场份额"],
        "max_cost_usd": "120.50",
        "max_pages": 10,
        "max_records": 500,
    }
    payload.update(overrides)
    return payload


def test_formal_markets_are_the_eleven_approved_markets() -> None:
    assert FORMAL_MARKET_CODES == (
        "US",
        "GB",
        "DE",
        "FR",
        "IT",
        "ES",
        "IE",
        "NL",
        "BE",
        "AT",
        "PL",
    )


def test_create_request_normalizes_seven_slots_and_package_fields() -> None:
    request = WorkbenchTaskCreateRequest.model_validate(_payload())
    assert request.brand == "Momcozy"
    assert request.package_type == "standard"
    assert request.primary_market == "US"
    assert request.comparison_markets == ["DE"]
    assert request.markets == ["US", "DE"]
    assert request.locale_by_market == {"US": "en", "DE": "de"}
    assert request.max_cost_usd == Decimal("120.50")
    assert request.max_pages == 10
    assert request.max_records == 500
    assert request.window.end == date.today()


def test_missing_slot_is_rejected() -> None:
    payload = _payload()
    payload.pop("decision_question")
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(payload)
    assert "required_slot_missing" in str(exc_info.value)


def test_non_formal_market_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(
                primary_market="JP",
                comparison_markets=[],
                locale_by_market={"JP": "ja"},
            )
        )
    assert "market_not_formal" in str(exc_info.value)


def test_locale_keys_must_match_markets() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(locale_by_market={"US": "en"})
        )
    assert "locale_market_mismatch" in str(exc_info.value)


def test_quick_allows_at_most_one_comparison_market() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(
                package_type="quick",
                comparison_markets=["DE", "FR"],
                locale_by_market={"US": "en", "DE": "de", "FR": "fr"},
            )
        )
    assert "comparison_markets_exceeded" in str(exc_info.value)


def test_standard_allows_at_most_three_comparison_markets() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(
                package_type="standard",
                comparison_markets=["DE", "FR", "IT", "ES"],
                locale_by_market={
                    "US": "en",
                    "DE": "de",
                    "FR": "fr",
                    "IT": "it",
                    "ES": "es",
                },
            )
        )
    assert "comparison_markets_exceeded" in str(exc_info.value)


def test_primary_market_cannot_be_a_comparison_market() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(comparison_markets=["US"])
        )
    assert "market_duplicate" in str(exc_info.value)


def test_negative_budget_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(_payload(max_cost_usd="-1"))
    assert "budget_invalid" in str(exc_info.value)


def test_future_window_is_rejected() -> None:
    today = date.today()
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(
                window={
                    "start": (today - timedelta(days=1)).isoformat(),
                    "end": (today + timedelta(days=1)).isoformat(),
                }
            )
        )
    assert "window_future" in str(exc_info.value)


def test_decision_question_must_be_a_question() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(decision_question="了解一下德国市场")
        )
    assert "decision_question_not_decidable" in str(exc_info.value)


def test_update_requires_market_fields_together() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskUpdateRequest.model_validate({"primary_market": "US"})
    assert "market_fields_incomplete" in str(exc_info.value)


def test_seed_products_require_three_to_ten_when_present() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkbenchTaskCreateRequest.model_validate(
            _payload(seed_products=["https://example.com/1", "ASIN-B0TEST"])
        )
    assert "seed_products_count_invalid" in str(exc_info.value)

    request = WorkbenchTaskCreateRequest.model_validate(
        _payload(
            seed_products=[
                "https://example.com/1",
                "https://example.com/2",
                "ASIN-B0TEST",
            ]
        )
    )
    assert request.seed_products == [
        "https://example.com/1",
        "https://example.com/2",
        "ASIN-B0TEST",
    ]


def test_seed_products_may_be_omitted_or_empty() -> None:
    assert WorkbenchTaskCreateRequest.model_validate(_payload()).seed_products == []
    assert (
        WorkbenchTaskCreateRequest.model_validate(
            _payload(seed_products=[])
        ).seed_products
        == []
    )


def test_target_price_band_uses_local_currency_and_ordered_bounds() -> None:
    band = TargetPriceBand(
        currency="USD",
        min_amount=Decimal("19.99"),
        max_amount=Decimal("49.99"),
    )
    assert band.min_amount == Decimal("19.99")

    with pytest.raises(ValidationError) as exc_info:
        TargetPriceBand(
            currency="USD",
            min_amount=Decimal("50"),
            max_amount=Decimal("20"),
        )
    assert "target_price_band_order_invalid" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        TargetPriceBand(currency="usd", min_amount=Decimal("10"))
    assert "target_price_band_currency_invalid" in str(exc_info.value)


def test_update_accepts_seed_products_and_target_price_band() -> None:
    request = WorkbenchTaskUpdateRequest.model_validate(
        {
            "seed_products": ["https://example.com/1", "https://example.com/2", "ID-3"],
            "target_price_band": {
                "currency": "EUR",
                "min_amount": "10",
                "max_amount": "30",
                "basis": "market_local_currency",
            },
        }
    )
    assert len(request.seed_products or []) == 3
    assert request.target_price_band is not None
    assert request.target_price_band.currency == "EUR"
    assert request.target_price_band.model_extra == {
        "basis": "market_local_currency"
    }


def test_taxonomy_reads_closed_category_set() -> None:
    assert load_maternal_category_ids(FIXTURE_PATH) == frozenset(
        {"breast_pump", "stroller", "sleep_bag"}
    )


def test_taxonomy_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(TaxonomyUnavailableError):
        load_maternal_category_ids(tmp_path / "missing.json")


def test_taxonomy_rejects_empty_set(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"version": "maternal_v1", "categories": []}), encoding="utf-8")
    with pytest.raises(TaxonomyUnavailableError):
        load_maternal_category_ids(path)
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_schemas.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `data_intelligence_hub.core.markets`。

- [ ] **Step 3: 写市场常量与 taxonomy 服务**

Create `apps/api/src/data_intelligence_hub/core/markets.py`:

```python
"""正式市场与启用市场常量。

来源：已批准设计 §2.4。core 与 US、GB、DE、FR、IT、ES 为 core；
IE、NL、BE、AT、PL 为 supported。首期正式市场共 11 个。
"""

from __future__ import annotations

FORMAL_MARKET_CODES: tuple[str, ...] = (
    "US",
    "GB",
    "DE",
    "FR",
    "IT",
    "ES",
    "IE",
    "NL",
    "BE",
    "AT",
    "PL",
)
CORE_MARKET_CODES: frozenset[str] = frozenset({"US", "GB", "DE", "FR", "IT", "ES"})
SUPPORTED_MARKET_CODES: frozenset[str] = frozenset(FORMAL_MARKET_CODES)
# 设计 §4.1/§4.2 的既有档位规则：Quick 最多 1 个对比市场，Standard 最多 3 个。
COMPARISON_MARKET_LIMITS: dict[str, int] = {"quick": 1, "standard": 3}

__all__ = [
    "COMPARISON_MARKET_LIMITS",
    "CORE_MARKET_CODES",
    "FORMAL_MARKET_CODES",
    "SUPPORTED_MARKET_CODES",
]
```

Create `apps/api/src/data_intelligence_hub/services/workbench/errors.py`:

```python
"""C4 workbench 领域错误。

路由只把 ``status_code`` 与 ``code`` 映射为 HTTP。
服务层不构造 HTTPException。
"""

from __future__ import annotations


class WorkbenchError(Exception):
    code = "workbench_error"
    status_code = 409

    def __init__(self, code: str | None = None) -> None:
        if code is not None:
            self.code = code
        super().__init__(self.code)


class WorkbenchValidationError(WorkbenchError):
    code = "workbench_validation_error"
    status_code = 422


class WorkbenchProjectNotFoundError(WorkbenchError):
    code = "project_not_found"
    status_code = 404


class WorkbenchProjectNotActiveError(WorkbenchError):
    code = "project_not_active"
    status_code = 409


class WorkbenchTaskNotFoundError(WorkbenchError):
    code = "task_not_found"
    status_code = 404


class WorkbenchTaskCancelledError(WorkbenchError):
    code = "task_cancelled"
    status_code = 409


class WorkbenchTaskLockedError(WorkbenchError):
    code = "task_locked"
    status_code = 409


class WorkbenchOwnerNotMemberError(WorkbenchValidationError):
    code = "owner_not_member"


class WorkbenchPackageTypeInvalidError(WorkbenchValidationError):
    code = "package_type_invalid"


class WorkbenchComparisonMarketsExceededError(WorkbenchValidationError):
    code = "comparison_markets_exceeded"


class WorkbenchAcceptanceContactNotMemberError(WorkbenchValidationError):
    code = "acceptance_contact_not_member"


class WorkbenchBudgetInvalidError(WorkbenchValidationError):
    code = "budget_invalid"


class WorkbenchCategoryUnknownError(WorkbenchValidationError):
    code = "category_unknown"


class WorkbenchVersionNotFoundError(WorkbenchError):
    code = "workflow_version_not_found"
    status_code = 404


class WorkflowVersionNotLinkedError(WorkbenchError):
    code = "workflow_version_not_linked"
    status_code = 409


class PlanNotApprovedError(WorkbenchError):
    code = "plan_not_approved"
    status_code = 409


class PlanVersionNotCurrentError(WorkbenchError):
    code = "plan_version_not_current"
    status_code = 409


class WorkflowVersionAlreadySubmittedError(WorkbenchError):
    code = "workflow_version_already_submitted"
    status_code = 409


class IdempotencyKeyConflictError(WorkbenchError):
    code = "idempotency_conflict"
    status_code = 409


class IdempotencyStateInconsistentError(WorkbenchError):
    code = "idempotency_state_inconsistent"
    status_code = 409
```

Create `apps/api/src/data_intelligence_hub/services/workbench/taxonomy.py`:

```python
"""读取母婴二级品类闭集。

``Settings.workbench_taxonomy_path`` 的相对值必须按应用根解析，不能依赖
进程 cwd：

- API 容器：应用根是 ``/app``，默认解析为
  ``/app/configs/taxonomy/maternal_v1.json``（compose 只读挂载点）。
- 本地仓库：应用根是仓库根，默认解析为
  ``<repo>/configs/taxonomy/maternal_v1.json``。

``WORKBENCH_TAXONOMY_PATH`` 可覆盖；覆盖值使用绝对路径。文件缺失、
JSON 损坏或空集合一律 fail-closed；不得猜品类。
"""

from __future__ import annotations

import json
from pathlib import Path

from data_intelligence_hub.core.config import get_settings


class TaxonomyUnavailableError(Exception):
    """taxonomy 缺失或不可解析。"""


def _application_roots() -> tuple[Path, ...]:
    """按模块文件位置推导应用根，不读 ``Path.cwd()``。

    - 容器：``/app/src/data_intelligence_hub/services/workbench/taxonomy.py``
      的 ``parents[4]`` 是 ``/app``。
    - 仓库：``<repo>/apps/api/src/.../taxonomy.py`` 的 ``parents[6]`` 是
      仓库根，优先使用；``parents[4]`` 是 ``apps/api``，只作后备。
    """
    module_path = Path(__file__).resolve()
    return tuple(
        module_path.parents[index]
        for index in (6, 4)
        if index < len(module_path.parents)
    )


def resolve_workbench_taxonomy_path(raw: str | None = None) -> Path:
    """解析 taxonomy 路径；不依赖进程 cwd。

    绝对路径（环境变量或显式参数）直接返回。相对路径依次按应用根解析，
    返回第一个存在的候选；都不存在时返回首个应用根候选，让读取阶段
    fail-closed。
    """
    configured = (
        raw if raw is not None else get_settings().workbench_taxonomy_path
    ).strip()
    candidate = Path(configured).expanduser()
    if candidate.is_absolute():
        return candidate
    roots = _application_roots()
    if not roots:
        raise TaxonomyUnavailableError("taxonomy_unavailable")
    for root in roots:
        resolved = (root / candidate).resolve()
        if resolved.is_file():
            return resolved
    return (roots[0] / candidate).resolve()


def load_maternal_category_ids(path: Path | None = None) -> frozenset[str]:
    source = path if path is not None else resolve_workbench_taxonomy_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaxonomyUnavailableError("taxonomy_unavailable") from exc
    categories = payload.get("categories") if isinstance(payload, dict) else None
    if not isinstance(categories, list):
        raise TaxonomyUnavailableError("taxonomy_unavailable")
    ids = {
        item["id"]
        for item in categories
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    }
    if not ids:
        raise TaxonomyUnavailableError("taxonomy_unavailable")
    return frozenset(ids)
```

Create `apps/api/src/data_intelligence_hub/services/workbench/markets.py`:

```python
"""市场启用判定。

正式市场来自设计 §2.4。启用集合来自 settings，默认 11 个全部启用。
未启用的正式市场是 blocked：保留 run 与 gap，不写 runs.status。
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from data_intelligence_hub.core.config import get_settings


@dataclass(frozen=True)
class MarketDecision:
    market_code: str
    enabled: bool


def resolve_market_decisions(
    markets: Sequence[str],
    *,
    enabled_markets: Collection[str] | None = None,
) -> tuple[MarketDecision, ...]:
    configured = (
        frozenset(enabled_markets)
        if enabled_markets is not None
        else frozenset(get_settings().workbench_enabled_markets)
    )
    return tuple(
        MarketDecision(market_code=market, enabled=market in configured)
        for market in markets
    )


def market_role_for(
    *,
    primary_market: str,
    comparison_markets: Sequence[str],
    market_code: str,
) -> str:
    """从任务单派生市场角色，不写 runs。"""
    if market_code == primary_market:
        return "primary"
    if market_code in comparison_markets:
        return "compare"
    raise ValueError("task_markets_invalid")


def task_market_codes(
    *,
    primary_market: str,
    comparison_markets: Sequence[str],
) -> tuple[str, ...]:
    return (primary_market, *comparison_markets)


__all__ = [
    "MarketDecision",
    "market_role_for",
    "resolve_market_decisions",
    "task_market_codes",
]
```

Create `apps/api/src/data_intelligence_hub/services/workbench/__init__.py`:

```python
"""C4 workbench 任务单与提交服务。"""
```

- [ ] **Step 4: 挂载生产 taxonomy 并声明容器环境变量**

In `configs/deploy/scrapy/docker-compose.yml`:

1. Add this read-only volume to the existing `api.volumes` list:

```yaml
      - ../../../configs/taxonomy:/app/configs/taxonomy:ro
```

2. Add these keys to the existing `api.environment` mapping. 只改 `.env.production` 不会进容器；必须同时写进 compose 的 environment 列表。

```yaml
      # C4 workbench 开关。默认关闭；只由 PG0 发布批次切换。
      WORKBENCH_TASKS_ENABLED: ${WORKBENCH_TASKS_ENABLED:-false}
      WORKBENCH_ENABLED_MARKETS: '${WORKBENCH_ENABLED_MARKETS:-["US","GB","DE","FR","IT","ES","IE","NL","BE","AT","PL"]}'
      # 必须是绝对路径。默认指向只读挂载点；相对值由 resolve_workbench_taxonomy_path() 按应用根解析。
      WORKBENCH_TAXONOMY_PATH: ${WORKBENCH_TAXONOMY_PATH:-/app/configs/taxonomy/maternal_v1.json}
```

Do not modify the `edge` service. Production A and B both use this compose file, so no second production-B compose change is allowed.

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
SCRAPY_POSTGRES_DB=check \
SCRAPY_POSTGRES_USER=check \
SCRAPY_POSTGRES_PASSWORD=check \
SCRAPY_JWT_SECRET=check \
docker compose -f configs/deploy/scrapy/docker-compose.yml config \
  | rg 'configs/taxonomy:ro|WORKBENCH_TAXONOMY_PATH|WORKBENCH_TASKS_ENABLED|WORKBENCH_ENABLED_MARKETS'
```

Expected:
- one API volume mount is rendered: host source resolves to repository `configs/taxonomy`; container target is `/app/configs/taxonomy`; mode is read-only.
- `WORKBENCH_TAXONOMY_PATH` renders as `/app/configs/taxonomy/maternal_v1.json` inside the API container.
- `WORKBENCH_TASKS_ENABLED` renders as `false`.
- `WORKBENCH_ENABLED_MARKETS` renders as the 11 formal markets.

- [ ] **Step 5: 修改 settings**

In `apps/api/src/data_intelligence_hub/core/config.py`:

Add imports:

```python
from data_intelligence_hub.core.markets import FORMAL_MARKET_CODES
```

Add fields after `cors_origins`:

```python
    # C4：workbench 总开关。默认关闭，C14 验收后逐市场开启。
    workbench_tasks_enabled: bool = False
    # C4：允许提交的正式市场。默认 11 个全部启用。
    workbench_enabled_markets: list[str] = list(FORMAL_MARKET_CODES)
    # C4：母婴二级品类闭集。相对值按应用根解析（容器 /app、仓库根），不依赖 cwd；
    # 显式覆盖用 WORKBENCH_TAXONOMY_PATH 绝对路径。缺失时创建任务单返回 503。
    workbench_taxonomy_path: str = "configs/taxonomy/maternal_v1.json"
```

Extend the existing before-validator tuple:

```python
    @field_validator(
        "cors_origins",
        "email_live_recipient_allowlist",
        "workbench_enabled_markets",
        mode="before",
    )
```

Add an after-validator:

```python
    @field_validator("workbench_enabled_markets", mode="after")
    @classmethod
    def validate_workbench_enabled_markets(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip().upper() for item in value if item.strip()})
        unknown = sorted(set(normalized) - set(FORMAL_MARKET_CODES))
        if unknown:
            raise ValueError(f"unknown_workbench_markets:{','.join(unknown)}")
        return normalized
```

- [ ] **Step 6: 写 `schemas/workbench.py`**

Create the full schema file:

```python
"""C4 workbench 任务单与提交合同。

七槽位来自 Playbook 1.1：
brand、category、competitors、markets+locale_by_market、window、
decision_question、does_not_answer。

本模块只做形状与静态规则校验。taxonomy 与市场启用状态由服务层校验。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from data_intelligence_hub.core.markets import (
    COMPARISON_MARKET_LIMITS,
    FORMAL_MARKET_CODES,
)
from data_intelligence_hub.schemas.run import RunResponse
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowVersionSummaryResponse,
)

MarketCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
LocaleCode = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"),
]
WorkbenchTaskStatus = Literal["draft", "submitted", "cancelled"]
PackageType = Literal["quick", "standard"]
TaskType = Literal["T1", "T2", "T3", "T4", "T5"]
GateStatus = Literal["pending", "pass", "fail", "blocked", "expired"]

FORMAL_MARKET_SET = frozenset(FORMAL_MARKET_CODES)


class WorkbenchContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class WorkbenchWindow(WorkbenchContract):
    start: date
    end: date

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.end < self.start:
            raise ValueError("window_order_invalid")
        if self.end > date.today():
            raise ValueError("window_future")
        if (self.end - self.start).days > 365:
            raise ValueError("window_too_long")
        return self


class TargetPriceBand(WorkbenchContract):
    """设计 §4.1：可选目标价格带，使用市场原币，不做汇率换算。

    C1 只登记 `target_price_band` 为 object；未命名的键原样保留，不静默丢弃。
    已知键做最小校验：币种三个大写字母，金额非负，min <= max。
    """

    model_config = ConfigDict(extra="allow", from_attributes=True)

    currency: str | None = None
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: object) -> object:
        if value is None:
            return None
        normalized = value.strip() if isinstance(value, str) else value
        if (
            not isinstance(normalized, str)
            or len(normalized) != 3
            or not normalized.isalpha()
            or normalized != normalized.upper()
        ):
            raise ValueError("target_price_band_currency_invalid")
        return normalized

    @model_validator(mode="after")
    def validate_band(self) -> Self:
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("target_price_band_order_invalid")
        return self


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _clean_list(value: object) -> object:
    if value is None:
        return []
    if not isinstance(value, list):
        return value
    return [str(item).strip() for item in value if str(item).strip()]


def _clean_markets(value: object) -> object:
    if not isinstance(value, list):
        return value
    return [str(item).strip().upper() for item in value]


def _clean_locales(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return {
        str(key).strip().upper(): str(item).strip().lower()
        for key, item in value.items()
    }


def _clean_market(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


def _markets_for(primary_market: str, comparison_markets: list[str]) -> list[str]:
    return [primary_market, *comparison_markets]


def _validate_common_slots(
    *,
    competitors: list[str] | None,
    decision_question: str | None,
    seed_products: list[str] | None = None,
) -> None:
    if competitors is not None and len(set(competitors)) != len(competitors):
        raise ValueError("competitor_duplicate")
    if decision_question is not None and not any(
        mark in decision_question for mark in ("?", "？")
    ):
        raise ValueError("decision_question_not_decidable")
    # 设计 §4.1：种子商品可选；使用时 3–10 个公开链接或平台 ID。
    if seed_products and not 3 <= len(seed_products) <= 10:
        raise ValueError("seed_products_count_invalid")


def _validate_market_selection(
    *,
    package_type: str,
    primary_market: str,
    comparison_markets: list[str],
    locale_by_market: dict[str, str] | None,
) -> None:
    if primary_market not in FORMAL_MARKET_SET:
        raise ValueError("market_not_formal")
    if len(set(comparison_markets)) != len(comparison_markets):
        raise ValueError("market_duplicate")
    if primary_market in comparison_markets:
        raise ValueError("market_duplicate")
    if any(market not in FORMAL_MARKET_SET for market in comparison_markets):
        raise ValueError("market_not_formal")
    if len(comparison_markets) > COMPARISON_MARKET_LIMITS[package_type]:
        raise ValueError("comparison_markets_exceeded")
    if locale_by_market is not None:
        expected = set(_markets_for(primary_market, comparison_markets))
        if set(locale_by_market) != expected:
            raise ValueError("locale_market_mismatch")


class WorkbenchTaskCreateRequest(WorkbenchContract):
    brand: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    competitors: list[str] = Field(default_factory=list, max_length=5)
    package_type: PackageType
    primary_market: MarketCode
    comparison_markets: list[MarketCode] = Field(default_factory=list)
    locale_by_market: dict[MarketCode, LocaleCode] = Field(min_length=1)
    window: WorkbenchWindow
    decision_question: str = Field(min_length=8, max_length=500)
    does_not_answer: list[str] = Field(default_factory=list, max_length=20)
    seed_products: list[str] = Field(default_factory=list)
    target_price_band: TargetPriceBand | None = None
    acceptance_contact_id: uuid.UUID | None = None
    max_cost_usd: Decimal | None = None
    max_pages: int | None = None
    max_records: int | None = None
    owner_id: uuid.UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("owner_id", "owner"),
    )
    task_type: TaskType | None = None
    task_type_confidence: float | None = Field(default=None, ge=0, le=1)

    @property
    def markets(self) -> list[str]:
        return _markets_for(self.primary_market, list(self.comparison_markets))

    @model_validator(mode="before")
    @classmethod
    def require_seven_slots(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        for field in (
            "brand",
            "category",
            "package_type",
            "primary_market",
            "locale_by_market",
            "window",
            "decision_question",
        ):
            if value.get(field) in (None, "", [], {}):
                raise ValueError("required_slot_missing")
        return value

    @field_validator("brand", "category", "decision_question", mode="before")
    @classmethod
    def strip_scalar(cls, value: object) -> object:
        return _strip(value)

    @field_validator("competitors", "does_not_answer", "seed_products", mode="before")
    @classmethod
    def clean_list(cls, value: object) -> object:
        return _clean_list(value)

    @field_validator("primary_market", mode="before")
    @classmethod
    def clean_primary_market(cls, value: object) -> object:
        return _clean_market(value)

    @field_validator("comparison_markets", mode="before")
    @classmethod
    def clean_comparison_markets(cls, value: object) -> object:
        return _clean_markets(value)

    @field_validator("locale_by_market", mode="before")
    @classmethod
    def clean_locales(cls, value: object) -> object:
        return _clean_locales(value)

    @field_validator("package_type", mode="before")
    @classmethod
    def clean_package_type(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in COMPARISON_MARKET_LIMITS:
                return normalized
        raise ValueError("package_type_invalid")

    @field_validator("max_cost_usd", "max_pages", "max_records", mode="after")
    @classmethod
    def reject_negative_budget(cls, value: object) -> object:
        if value is not None and value < 0:
            raise ValueError("budget_invalid")
        return value

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        _validate_common_slots(
            competitors=list(self.competitors),
            decision_question=self.decision_question,
            seed_products=list(self.seed_products),
        )
        _validate_market_selection(
            package_type=self.package_type,
            primary_market=self.primary_market,
            comparison_markets=list(self.comparison_markets),
            locale_by_market=dict(self.locale_by_market),
        )
        if self.task_type is None and self.task_type_confidence is not None:
            raise ValueError("task_type_confidence_without_type")
        return self


class WorkbenchTaskUpdateRequest(WorkbenchContract):
    brand: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    competitors: list[str] | None = Field(default=None, max_length=5)
    package_type: PackageType | None = None
    primary_market: MarketCode | None = None
    comparison_markets: list[MarketCode] | None = Field(default=None)
    locale_by_market: dict[MarketCode, LocaleCode] | None = Field(
        default=None,
        min_length=1,
    )
    window: WorkbenchWindow | None = None
    decision_question: str | None = Field(default=None, min_length=8, max_length=500)
    does_not_answer: list[str] | None = Field(default=None, max_length=20)
    seed_products: list[str] | None = None
    target_price_band: TargetPriceBand | None = None
    acceptance_contact_id: uuid.UUID | None = None
    max_cost_usd: Decimal | None = None
    max_pages: int | None = None
    max_records: int | None = None
    owner_id: uuid.UUID | None = None
    task_type: TaskType | None = None
    task_type_confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("brand", "category", "decision_question", mode="before")
    @classmethod
    def strip_scalar(cls, value: object) -> object:
        return _strip(value)

    @field_validator("competitors", "does_not_answer", "seed_products", mode="before")
    @classmethod
    def clean_list(cls, value: object) -> object:
        return value if value is None else _clean_list(value)

    @field_validator("primary_market", mode="before")
    @classmethod
    def clean_primary_market(cls, value: object) -> object:
        return value if value is None else _clean_market(value)

    @field_validator("comparison_markets", mode="before")
    @classmethod
    def clean_comparison_markets(cls, value: object) -> object:
        return value if value is None else _clean_markets(value)

    @field_validator("locale_by_market", mode="before")
    @classmethod
    def clean_locales(cls, value: object) -> object:
        return value if value is None else _clean_locales(value)

    @field_validator("package_type", mode="before")
    @classmethod
    def clean_package_type(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in COMPARISON_MARKET_LIMITS:
                return normalized
        raise ValueError("package_type_invalid")

    @field_validator("max_cost_usd", "max_pages", "max_records", mode="after")
    @classmethod
    def reject_negative_budget(cls, value: object) -> object:
        if value is not None and value < 0:
            raise ValueError("budget_invalid")
        return value

    @model_validator(mode="after")
    def validate_slots(self) -> Self:
        for field in (
            "brand",
            "category",
            "package_type",
            "primary_market",
            "comparison_markets",
            "locale_by_market",
            "window",
            "decision_question",
            "does_not_answer",
            "seed_products",
            "target_price_band",
            "owner_id",
            "acceptance_contact_id",
            "max_cost_usd",
            "max_pages",
            "max_records",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("field_required")
        market_fields = {
            "package_type",
            "primary_market",
            "comparison_markets",
            "locale_by_market",
        }
        provided_market_fields = market_fields & self.model_fields_set
        if provided_market_fields and provided_market_fields != market_fields:
            raise ValueError("market_fields_incomplete")
        if provided_market_fields == market_fields:
            assert self.package_type is not None
            assert self.primary_market is not None
            _validate_market_selection(
                package_type=self.package_type,
                primary_market=self.primary_market,
                comparison_markets=list(self.comparison_markets or []),
                locale_by_market=(
                    None if self.locale_by_market is None else dict(self.locale_by_market)
                ),
            )
        _validate_common_slots(
            competitors=None if self.competitors is None else list(self.competitors),
            decision_question=self.decision_question,
            seed_products=(
                None if self.seed_products is None else list(self.seed_products)
            ),
        )
        return self


class WorkbenchTaskResponse(WorkbenchContract):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    created_by_user_id: uuid.UUID
    owner_id: uuid.UUID
    brand: str
    category: str
    competitors: list[str]
    package_type: PackageType
    primary_market: MarketCode
    comparison_markets: list[MarketCode]
    markets: list[str]
    locale_by_market: dict[str, str]
    window_start: date
    window_end: date
    decision_question: str
    does_not_answer: list[str]
    seed_products: list[str]
    target_price_band: TargetPriceBand | None
    acceptance_contact_id: uuid.UUID | None
    max_cost_usd: Decimal | None
    max_pages: int | None
    max_records: int | None
    task_type: TaskType | None
    task_type_confidence: float | None
    status: WorkbenchTaskStatus
    created_at: datetime
    updated_at: datetime


class WorkbenchGapResponse(WorkbenchContract):
    market_code: MarketCode
    domain: Literal["market"] = "market"
    reason_code: Literal["market_unsupported"] = "market_unsupported"
    actual_value: str | None = None
    threshold_value: str | None = None
    impact: Literal["market_excluded"] = "market_excluded"
    customer_message: str
    remediation: str
    severity: Literal["blocking"] = "blocking"


class WorkbenchSubmissionResponse(WorkbenchContract):
    workbench_task_id: uuid.UUID
    workflow_version_id: uuid.UUID
    runs: list[RunResponse]
    run_ids: list[uuid.UUID]
    gaps: list[WorkbenchGapResponse]
    idempotent_replay: bool


class WorkbenchGateResponse(WorkbenchContract):
    authorization_id: uuid.UUID
    gate_id: str
    gate_status: GateStatus
    market_code: str | None = None
    reason_code: str | None = None
    gap: WorkbenchGapResponse | None = None


class WorkbenchTaskDetailResponse(WorkbenchContract):
    task: WorkbenchTaskResponse
    workflow_versions: list[WorkflowVersionSummaryResponse]
    runs: list[RunResponse]
    gates: list[WorkbenchGateResponse]


class WorkbenchTaskListResponse(WorkbenchContract):
    items: list[WorkbenchTaskResponse]


__all__ = [
    "COMPARISON_MARKET_LIMITS",
    "FORMAL_MARKET_SET",
    "GateStatus",
    "MarketCode",
    "PackageType",
    "TargetPriceBand",
    "TaskType",
    "WorkbenchContract",
    "WorkbenchGapResponse",
    "WorkbenchGateResponse",
    "WorkbenchSubmissionResponse",
    "WorkbenchTaskCreateRequest",
    "WorkbenchTaskDetailResponse",
    "WorkbenchTaskListResponse",
    "WorkbenchTaskResponse",
    "WorkbenchTaskStatus",
    "WorkbenchTaskUpdateRequest",
    "WorkbenchWindow",
]
```

- [ ] **Step 7: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_schemas.py -v
```

Expected: 22 passed。

- [ ] **Step 8: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/core/markets.py src/data_intelligence_hub/core/config.py src/data_intelligence_hub/schemas/workbench.py src/data_intelligence_hub/services/workbench tests/unit/test_workbench_schemas.py
.venv/bin/mypy src/data_intelligence_hub/schemas/workbench.py src/data_intelligence_hub/services/workbench
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add configs/taxonomy/maternal_v1.json \
  configs/deploy/scrapy/docker-compose.yml \
  apps/api/src/data_intelligence_hub/core/markets.py \
  apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/src/data_intelligence_hub/schemas/workbench.py \
  apps/api/src/data_intelligence_hub/services/workbench \
  apps/api/tests/fixtures/maternal_v1.json \
  apps/api/tests/unit/test_workbench_schemas.py
git commit -m "feat(workbench): validate seven task slots and market gates (C4)"
```

### Task 3: 任务单仓储、版本关联与 run 幂等查询

**Files:**
- Create: `apps/api/src/data_intelligence_hub/repositories/workbench_tasks.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/runs.py:128-183`
- Modify: `apps/api/src/data_intelligence_hub/repositories/workflow_plans.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/authorizations.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py:404-470,619-780,1160-1380`
- Modify: `apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py:64-78,108-160`
- Create: `apps/api/tests/unit/workbench_support.py`
- Test: `apps/api/tests/unit/test_workbench_task_repository.py`

**Interfaces:**
- Consumes: `WorkbenchTask`、`WorkflowVersion`、`Run`、`Authorization`。
- Produces:
  - `add_workbench_task(session, task) -> WorkbenchTask`
  - `get_workbench_task(session, *, workspace_id, task_id, project_id=None) -> WorkbenchTask | None`
  - `get_workbench_task_by_idempotency_hash(session, *, workspace_id, idempotency_key_hash) -> WorkbenchTask | None`
  - `list_workbench_tasks(session, *, workspace_id, project_id, status=None, limit=50, offset=0) -> list[WorkbenchTask]`
  - `update_workbench_task_fields(session, *, workspace_id, task_id, values) -> WorkbenchTask | None`
  - `get_workspace_member(session, *, workspace_id, user_id) -> WorkspaceMember | None`
  - `list_versions_for_task(session, *, workspace_id, task_id) -> list[WorkflowVersion]`
  - `has_runs_for_task(session, *, workspace_id, task_id) -> bool`
  - `list_runs_for_task(session, *, workspace_id, task_id) -> list[Run]`
  - `find_by_idempotency_hashes(session, *, workspace_id, hashes) -> list[Run]`
  - `list_runs_for_workflow_version(session, *, workspace_id, workflow_version_id) -> list[Run]`
  - `get_workflow_version_with_plan(session, *, workspace_id, project_id, workflow_version_id) -> tuple[WorkflowVersion, WorkflowPlan] | None`
  - `list_authorizations_for_versions(session, *, workspace_id, version_ids) -> list[Authorization]`

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/workbench_support.py`:

```python
"""C4 单元/集成测试共用的最小种子。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember


@dataclass(frozen=True)
class WorkbenchSeed:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    collection_task_id: uuid.UUID


async def seed_workbench_scope(
    session: AsyncSession,
    *,
    suffix: str = "c4",
    markets: tuple[str, ...] = ("US", "DE"),
    plan_status: str = "approved",
) -> WorkbenchSeed:
    today = date.today()
    user = User(
        email=f"{suffix}-{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
        name=f"{suffix} owner",
        status="active",
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(
        name=f"{suffix} workspace",
        slug=f"{suffix}-{uuid.uuid4().hex}",
        owner_id=user.id,
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = Project(
        workspace_id=workspace.id,
        name=f"{suffix} project",
        domain="mother_baby",
        owner_id=user.id,
        status="active",
    )
    session.add(project)
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name=f"{suffix} source",
        type="generic_web",
        url=None,
        config={},
        schedule_cron=None,
        enabled=True,
    )
    session.add(source)
    await session.flush()
    collection_task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type="generic_web",
        name=f"{suffix} collection task",
        status="enabled",
        config={"endpoint_type": "generic_web"},
    )
    session.add(collection_task)
    await session.flush()

    task = WorkbenchTask(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        owner_id=user.id,
        brand="Momcozy",
        category="breast_pump",
        competitors=["Medela"],
        package_type="standard",
        primary_market=markets[0],
        comparison_markets=list(markets[1:]),
        acceptance_contact_id=user.id,
        max_cost_usd=Decimal("120.500000"),
        max_pages=10,
        max_records=500,
        seed_products=[],
        target_price_band=None,
        idempotency_key_hash=None,
        markets=list(markets),
        locale_by_market={market: "en" for market in markets},
        window_start=today - timedelta(days=90),
        window_end=today,
        decision_question="Fit 与支撑哪个是主要摩擦？",
        does_not_answer=["不推断销量与市场份额"],
        task_type="T1",
        task_type_confidence=Decimal("0.900"),
        status="draft",
    )
    session.add(task)
    await session.flush()

    plan = WorkflowPlan(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        project_id=project.id,
        created_by_user_id=user.id,
        name=f"{suffix} plan",
        flow_mode="batch_research",
        status=plan_status,
        current_version_id=None,
    )
    session.add(plan)
    await session.flush()

    version = WorkflowVersion(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        project_id=project.id,
        workflow_plan_id=plan.id,
        workbench_task_id=task.id,
        created_by_user_id=user.id,
        version_number=1,
        planning_status="resolved",
        planner_contract_version="workflow_planner.v1",
        catalog_snapshot_id="catalog-v1",
        policy_version="policy.v1",
        mode_template_version="template.v1",
        query_versions={},
        fingerprint_payload={},
        normalized_input={},
        plan_payload={
            "execution_steps": [
                {
                    "step_index": 0,
                    "task_id": str(collection_task.id),
                    "endpoint_type": "generic_web",
                    "collector_type": "generic_web",
                    "depends_on": [],
                }
            ]
        },
        preview_fingerprint="sha256:" + "a" * 64,
        created_at=datetime.now(UTC),
    )
    session.add(version)
    await session.flush()
    plan.current_version_id = version.id
    await session.commit()

    return WorkbenchSeed(
        user_id=user.id,
        workspace_id=workspace.id,
        project_id=project.id,
        task_id=task.id,
        plan_id=plan.id,
        version_id=version.id,
        collection_task_id=collection_task.id,
    )


async def add_workspace_member(
    session: AsyncSession,
    seed: WorkbenchSeed,
    *,
    role: str = "member",
) -> uuid.UUID:
    """同工作区新增一个成员；用于验收联系人 owner/admin 规则。"""
    user = User(
        email=f"{role}-{uuid.uuid4().hex}@example.com",
        password_hash="test-hash",
        name=f"{role} member",
        status="active",
    )
    session.add(user)
    await session.flush()
    session.add(
        WorkspaceMember(
            workspace_id=seed.workspace_id,
            user_id=user.id,
            role=role,
        )
    )
    await session.commit()
    return user.id


async def add_linked_version(
    session: AsyncSession,
    seed: WorkbenchSeed,
    *,
    number: int = 2,
) -> uuid.UUID:
    version = WorkflowVersion(
        id=uuid.uuid4(),
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_plan_id=seed.plan_id,
        workbench_task_id=seed.task_id,
        created_by_user_id=seed.user_id,
        version_number=number,
        planning_status="resolved",
        planner_contract_version="workflow_planner.v1",
        catalog_snapshot_id="catalog-v1",
        policy_version="policy.v1",
        mode_template_version="template.v1",
        query_versions={},
        fingerprint_payload={},
        normalized_input={},
        plan_payload={
            "execution_steps": [
                {
                    "step_index": 0,
                    "task_id": str(seed.collection_task_id),
                    "endpoint_type": "generic_web",
                    "collector_type": "generic_web",
                    "depends_on": [],
                }
            ]
        },
        preview_fingerprint="sha256:" + f"{number:x}" * 64,
        created_at=datetime.now(UTC),
    )
    session.add(version)
    await session.commit()
    return version.id
```

Create `apps/api/tests/unit/test_workbench_task_repository.py`:

```python
"""任务单仓储与 workflow_versions 关联的单元测试。"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.repositories.runs import (
    create_run,
    find_by_idempotency_hashes,
    list_runs_for_workflow_version,
)
from data_intelligence_hub.repositories.workbench_tasks import (
    get_workspace_member,
    get_workbench_task,
    get_workbench_task_by_idempotency_hash,
    has_runs_for_task,
    list_runs_for_task,
    list_versions_for_task,
    list_workbench_tasks,
)
from data_intelligence_hub.repositories.workflow_plans import (
    get_workflow_version_with_plan,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanCreateRequest,
)
from data_intelligence_hub.services.workflow_planner.persistence import (
    _persist_version_graph,
)
from tests.unit.workbench_support import seed_workbench_scope


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


@pytest.mark.asyncio
async def test_task_reads_are_tenant_scoped(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="tenant-a")
    other = await seed_workbench_scope(session, suffix="tenant-b")

    own = await get_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        task_id=seed.task_id,
    )
    foreign = await get_workbench_task(
        session,
        workspace_id=other.workspace_id,
        project_id=seed.project_id,
        task_id=seed.task_id,
    )

    assert own is not None and own.id == seed.task_id
    assert foreign is None


@pytest.mark.asyncio
async def test_owner_membership_is_required(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="owner")
    member = await get_workspace_member(
        session,
        workspace_id=seed.workspace_id,
        user_id=seed.user_id,
    )
    missing = await get_workspace_member(
        session,
        workspace_id=seed.workspace_id,
        user_id=uuid.uuid4(),
    )
    assert member is not None
    assert missing is None


@pytest.mark.asyncio
async def test_linked_version_and_plan_are_read_together(
    session: AsyncSession,
) -> None:
    seed = await seed_workbench_scope(session, suffix="link")
    linked = await get_workflow_version_with_plan(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_version_id=seed.version_id,
    )
    versions = await list_versions_for_task(
        session,
        workspace_id=seed.workspace_id,
        task_id=seed.task_id,
    )

    assert linked is not None
    version, plan = linked
    assert version.workbench_task_id == seed.task_id
    assert plan.id == seed.plan_id
    assert [item.id for item in versions] == [seed.version_id]


@pytest.mark.asyncio
async def test_task_run_queries_follow_version_link(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="runs")
    assert (
        await has_runs_for_task(
            session, workspace_id=seed.workspace_id, task_id=seed.task_id
        )
        is False
    )

    run = await create_run(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_version_id=seed.version_id,
        market_code="US",
        idempotency_key_hash="a" * 64,
    )
    await session.commit()

    assert (
        await has_runs_for_task(
            session, workspace_id=seed.workspace_id, task_id=seed.task_id
        )
        is True
    )
    task_runs = await list_runs_for_task(
        session,
        workspace_id=seed.workspace_id,
        task_id=seed.task_id,
    )
    version_runs = await list_runs_for_workflow_version(
        session,
        workspace_id=seed.workspace_id,
        workflow_version_id=seed.version_id,
    )
    found = await find_by_idempotency_hashes(
        session,
        workspace_id=seed.workspace_id,
        hashes=("a" * 64, "b" * 64),
    )
    assert [item.id for item in task_runs] == [run.id]
    assert [item.id for item in version_runs] == [run.id]
    assert [item.id for item in found] == [run.id]
    assert run.market_code == "US"
    assert run.status == "queued"


@pytest.mark.asyncio
async def test_task_list_is_status_filtered(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="list")
    task = await session.get(WorkbenchTask, seed.task_id)
    assert task is not None
    task.status = "submitted"
    await session.commit()

    submitted = await list_workbench_tasks(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        status="submitted",
    )
    draft = await list_workbench_tasks(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        status="draft",
    )
    assert [item.id for item in submitted] == [seed.task_id]
    assert draft == []


@pytest.mark.asyncio
async def test_idempotency_lookup_is_workspace_scoped(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="idem")
    other = await seed_workbench_scope(session, suffix="idem-other")
    task = await session.get(WorkbenchTask, seed.task_id)
    assert task is not None
    task.idempotency_key_hash = "d" * 64
    await session.commit()

    own = await get_workbench_task_by_idempotency_hash(
        session,
        workspace_id=seed.workspace_id,
        idempotency_key_hash="d" * 64,
    )
    foreign = await get_workbench_task_by_idempotency_hash(
        session,
        workspace_id=other.workspace_id,
        idempotency_key_hash="d" * 64,
    )
    assert own is not None and own.id == seed.task_id
    assert foreign is None


def test_plan_create_request_accepts_workbench_task_id() -> None:
    task_id = uuid.uuid4()
    payload = WorkflowPlanCreateRequest.model_validate(
        {
            "name": "C4 plan",
            "preview_input": {
                "flow_mode": "batch_research",
                "scopes": [
                    {
                        "scope_ref": "brand:momcozy",
                        "scope_type": "brand",
                        "canonical_term": "Momcozy",
                        "platforms": ["tiktok"],
                    }
                ],
                "purpose": "market_research",
            },
            "expected_preview_fingerprint": "sha256:" + "a" * 64,
            "workbench_task_id": str(task_id),
        }
    )
    assert payload.workbench_task_id == task_id


def test_persist_version_graph_accepts_workbench_link() -> None:
    parameters = inspect.signature(_persist_version_graph).parameters
    assert "workbench_task_id" in parameters
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_task_repository.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `repositories.workbench_tasks`，或 `create_run` 不接受 `market_code`。

- [ ] **Step 3: 写任务单仓储**

Create `apps/api/src/data_intelligence_hub/repositories/workbench_tasks.py`:

```python
"""``workbench_tasks`` 与任务单关联查询。

仓储只做查询、插入与字段更新，并调用 ``flush``。
事务提交权留给服务层。所有读写必须带 ``workspace_id``。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.models.workspace import WorkspaceMember


async def add_workbench_task(
    session: AsyncSession,
    task: WorkbenchTask,
) -> WorkbenchTask:
    session.add(task)
    await session.flush()
    return task


async def get_workbench_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> WorkbenchTask | None:
    statement = select(WorkbenchTask).where(
        WorkbenchTask.workspace_id == workspace_id,
        WorkbenchTask.id == task_id,
    )
    if project_id is not None:
        statement = statement.where(WorkbenchTask.project_id == project_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_workbench_task_by_idempotency_hash(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    idempotency_key_hash: str,
) -> WorkbenchTask | None:
    result = await session.execute(
        select(WorkbenchTask).where(
            WorkbenchTask.workspace_id == workspace_id,
            WorkbenchTask.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def list_workbench_tasks(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkbenchTask]:
    statement: Select[tuple[WorkbenchTask]] = select(WorkbenchTask).where(
        WorkbenchTask.workspace_id == workspace_id,
        WorkbenchTask.project_id == project_id,
    )
    if status is not None:
        statement = statement.where(WorkbenchTask.status == status)
    statement = (
        statement.order_by(WorkbenchTask.created_at.desc(), WorkbenchTask.id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def update_workbench_task_fields(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    values: Mapping[str, Any],
) -> WorkbenchTask | None:
    task = await get_workbench_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    if task is None:
        return None
    for key, value in values.items():
        setattr(task, key, value)
    await session.flush()
    return task


async def get_workspace_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember | None:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_versions_for_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> list[WorkflowVersion]:
    result = await session.execute(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.workbench_task_id == task_id,
        )
        .order_by(WorkflowVersion.version_number, WorkflowVersion.id)
    )
    return list(result.scalars().all())


def _task_runs_statement(
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> Select[tuple[Run]]:
    return (
        select(Run)
        .join(WorkflowVersion, Run.workflow_version_id == WorkflowVersion.id)
        .where(
            Run.workspace_id == workspace_id,
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.workbench_task_id == task_id,
        )
    )


async def has_runs_for_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> bool:
    statement = (
        select(Run.id)
        .join(WorkflowVersion, Run.workflow_version_id == WorkflowVersion.id)
        .where(
            Run.workspace_id == workspace_id,
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.workbench_task_id == task_id,
        )
        .limit(1)
    )
    return await session.scalar(statement) is not None


async def list_runs_for_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> list[Run]:
    statement = _task_runs_statement(
        workspace_id=workspace_id,
        task_id=task_id,
    ).order_by(Run.market_code, Run.created_at, Run.id)
    result = await session.execute(statement)
    return list(result.scalars().all())


__all__ = [
    "add_workbench_task",
    "get_workbench_task",
    "get_workbench_task_by_idempotency_hash",
    "get_workspace_member",
    "has_runs_for_task",
    "list_runs_for_task",
    "list_versions_for_task",
    "list_workbench_tasks",
    "update_workbench_task_fields",
]
```

- [ ] **Step 4: 扩展 runs 仓储**

In `apps/api/src/data_intelligence_hub/repositories/runs.py`, add `market_code` to `create_run` signature and constructor:

```python
    market_code: str | None = None,
```

```python
        market_code=market_code,
```

Add these functions after `find_by_idempotency_key`:

```python
async def find_by_idempotency_hashes(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    hashes: tuple[str, ...],
) -> list[Run]:
    """按一组幂等摘要批量查询运行。空输入返回空列表。"""
    if not hashes:
        return []
    result = await session.execute(
        select(Run).where(
            Run.workspace_id == workspace_id,
            Run.idempotency_key_hash.in_(hashes),
        )
    )
    return list(result.scalars().all())


async def list_runs_for_workflow_version(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> list[Run]:
    """按计划版本列出运行。结果按市场码与创建时间排序。"""
    result = await session.execute(
        select(Run)
        .where(
            Run.workspace_id == workspace_id,
            Run.workflow_version_id == workflow_version_id,
        )
        .order_by(Run.market_code, Run.created_at, Run.id)
    )
    return list(result.scalars().all())
```

Add both names to `__all__`.

本计划新增的 C4 生产代码只允许 `services/run_creation.py` 直接调用 `create_run`；C4 提交服务与 C6 旧入口收敛都调用 Task 3C 的 `create_run_with_audit`。旧入口既有直连由 C6 Task 10 收敛。测试可以直接调用仓储，以验证唯一索引与查询行为。

- [ ] **Step 5: 扩展 workflow_plans 与 authorizations 仓储**

In `apps/api/src/data_intelligence_hub/repositories/workflow_plans.py`, add:

```python
async def get_workflow_version_with_plan(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> tuple[WorkflowVersion, WorkflowPlan] | None:
    """按租户读取一个计划版本及其计划。"""
    result = await session.execute(
        select(WorkflowVersion, WorkflowPlan)
        .join(
            WorkflowPlan,
            (WorkflowPlan.id == WorkflowVersion.workflow_plan_id)
            & (WorkflowPlan.workspace_id == WorkflowVersion.workspace_id)
            & (WorkflowPlan.project_id == WorkflowVersion.project_id),
        )
        .where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.id == workflow_version_id,
        )
    )
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]
```

In `apps/api/src/data_intelligence_hub/repositories/authorizations.py`, add:

```python
async def list_authorizations_for_versions(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    version_ids: list[uuid.UUID],
) -> list[Authorization]:
    """按计划版本列门禁行。空输入返回空列表。"""
    if not version_ids:
        return []
    result = await session.execute(
        select(Authorization)
        .where(
            Authorization.workspace_id == workspace_id,
            Authorization.plan_version_id.in_(version_ids),
            Authorization.gate_id == "G-Plan",
        )
        .order_by(Authorization.granted_at, Authorization.id)
    )
    return list(result.scalars().all())
```

Add to `__all__`.

- [ ] **Step 6: 计划与版本创建时写入 `workbench_task_id`**

In `apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py`:

- `WorkflowPlanCreateRequest` add:
```python
    workbench_task_id: UUID | None = None
```
- `WorkflowVersionCreateRequest` add:
```python
    workbench_task_id: UUID | None = None
```
- `WorkflowVersionSummaryResponse` add:
```python
    workbench_task_id: UUID | None = None
```

In `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`:

Add imports:
```python
from data_intelligence_hub.repositories.workbench_tasks import get_workbench_task
from data_intelligence_hub.services.workbench.errors import (
    WorkbenchTaskCancelledError,
    WorkbenchTaskNotFoundError,
)
```

Change `_persist_version_graph` signature:
```python
    workflow_template_revision_id: uuid.UUID | None = None,
    workbench_task_id: uuid.UUID | None = None,
) -> WorkflowVersion:
```

Set the column in the `WorkflowVersion(...)` constructor:
```python
        workbench_task_id=workbench_task_id,
```

In `_create_workflow_plan_attempt`, after `if project.status != "active": raise ProjectNotActiveError`, add:
```python
        if payload.workbench_task_id is not None:
            workbench_task = await get_workbench_task(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=payload.workbench_task_id,
            )
            if workbench_task is None:
                raise WorkbenchTaskNotFoundError()
            if workbench_task.status == "cancelled":
                raise WorkbenchTaskCancelledError()
```

Pass the link to the version graph:
```python
            workbench_task_id=payload.workbench_task_id,
```

In `_create_workflow_version_attempt`, after `current_version` is loaded and before `current_preview`:
```python
        if payload.workbench_task_id is not None:
            workbench_task = await get_workbench_task(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=payload.workbench_task_id,
            )
            if workbench_task is None:
                raise WorkbenchTaskNotFoundError()
            if workbench_task.status == "cancelled":
                raise WorkbenchTaskCancelledError()
```

Pass the inherited link:
```python
            workbench_task_id=(
                payload.workbench_task_id or current_version.workbench_task_id
            ),
```

In `_version_response`, add:
```python
        workbench_task_id=version.workbench_task_id,
```

- [ ] **Step 7: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_task_repository.py -v
```

Expected: 8 passed。

- [ ] **Step 8: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/repositories/workbench_tasks.py src/data_intelligence_hub/repositories/runs.py src/data_intelligence_hub/repositories/workflow_plans.py src/data_intelligence_hub/repositories/authorizations.py src/data_intelligence_hub/services/workflow_planner/persistence.py src/data_intelligence_hub/schemas/workflow_plan_persistence.py tests/unit/workbench_support.py tests/unit/test_workbench_task_repository.py
.venv/bin/mypy src/data_intelligence_hub/repositories/workbench_tasks.py src/data_intelligence_hub/services/workflow_planner/persistence.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/src/data_intelligence_hub/repositories/workbench_tasks.py \
  apps/api/src/data_intelligence_hub/repositories/runs.py \
  apps/api/src/data_intelligence_hub/repositories/workflow_plans.py \
  apps/api/src/data_intelligence_hub/repositories/authorizations.py \
  apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py \
  apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py \
  apps/api/tests/unit/workbench_support.py \
  apps/api/tests/unit/test_workbench_task_repository.py
git commit -m "feat(workbench): link workflow versions to tasks (C4)"
```

---

### Task 3A: 执行步骤固化与 `collection_tasks` 校验

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/workbench/execution_steps.py`
- Modify: `apps/api/src/data_intelligence_hub/schemas/workflow_planner.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- Modify: `apps/api/src/data_intelligence_hub/collectors/endpoint_catalog.py`
- Modify: `apps/api/tests/unit/workbench_support.py`
- Test: `apps/api/tests/unit/test_workbench_execution_steps.py`

**Interfaces:**
- Consumes: `WorkflowPlanPreview.route_plans`、`route_requirements`、`resolve_current_capability_catalog()`、`collector_type_for_endpoint()`、`WorkbenchTask`、`Source`、`CollectionTask`。
- Produces:
  - `ExecutionStepPreview(step_index: int, task_id: str, endpoint_type: str, collector_type: str, depends_on: list[int] = [], max_attempts: int | None = None)`
  - `build_execution_steps(session, *, workspace_id, project_id, workbench_task_id, preview, catalog=None) -> list[ExecutionStepPreview]`
  - `validate_execution_steps(session, *, workspace_id, project_id, version) -> list[ExecutionStepPreview]`
  - `ExecutionStepsMissingError`、`ExecutionStepUnresolvedError`、`CollectionTaskInvalidError`
  - `collector_type_for_endpoint(endpoint_type: str) -> str | None`
- 规则：只使用 `route_plans` 中 `route_eligible=True` 且 `primary_implementation` 非空的项。每个 eligible plan 产生一个 step，按列表顺序编号 `step_index=0..n-1`。`depends_on` 保持空列表，C6 按顺序执行。`max_attempts` 不写，使用 C6 的 `RetryPolicy` 默认值。解析不到实现或端点时 fail-closed，不猜端点。
- `CapabilityImplementation.supported_endpoints` 必须是 `endpoint_type` 键（与 `_ENDPOINT_TO_COLLECTOR` 同键空间）；不是时 `ExecutionStepUnresolvedError`，由 C1/C0 修 catalog，不在 C4 猜。
- 不可变：步骤只在此处写入 `WorkflowPlanPreview.execution_steps`；批准、提交、重试与查询都不得修改 `plan_payload`。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_workbench_execution_steps.py`:

```python
# 执行步骤固化与 collection_tasks 校验。

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.services.workbench.execution_steps import (
    ExecutionStepUnresolvedError,
    build_execution_steps,
    validate_execution_steps,
)
from tests.unit.workbench_support import seed_workbench_scope, with_sqlite_session


def _catalog(
    *,
    implementation_id: str = "tikhub.tiktok",
    endpoints: tuple[str, ...] = ("tikhub_tiktok_video_search",),
) -> SimpleNamespace:
    implementation = SimpleNamespace(
        implementation_id=implementation_id,
        supported_endpoints=list(endpoints),
    )
    return SimpleNamespace(implementations=[implementation])


def _preview(
    *,
    implementation_id: str = "tikhub.tiktok",
) -> SimpleNamespace:
    route_plan = SimpleNamespace(
        requirement_ref="req-1",
        route_eligible=True,
        primary_implementation=SimpleNamespace(implementation_id=implementation_id),
    )
    requirement = SimpleNamespace(
        requirement_ref="req-1",
        platform=SimpleNamespace(value="tiktok"),
        resource_type=SimpleNamespace(value="content"),
        operation=SimpleNamespace(value="search_discover"),
    )
    return SimpleNamespace(
        route_plans=[route_plan],
        route_requirements=[requirement],
    )


@pytest.mark.anyio
async def test_build_steps_creates_collection_tasks_and_stable_payload() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_workbench_scope(session, suffix="steps")
        steps = await build_execution_steps(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workbench_task_id=seed.task_id,
            preview=_preview(),
            catalog=_catalog(),
        )
        observed["steps"] = steps
        observed["sources"] = list((await session.execute(select(Source))).scalars())
        observed["tasks"] = list(
            (await session.execute(select(CollectionTask))).scalars()
        )

    await with_sqlite_session(scenario)

    steps = observed["steps"]
    assert [step.step_index for step in steps] == [0]
    assert steps[0].endpoint_type == "tikhub_tiktok_video_search"
    assert steps[0].collector_type == "tikhub_social"
    assert len(observed["sources"]) == 2
    assert len(observed["tasks"]) == 2
    created = next(
        item for item in observed["tasks"] if str(item.id) == steps[0].task_id
    )
    assert created.config["endpoint_type"] == "tikhub_tiktok_video_search"


@pytest.mark.anyio
async def test_validate_rejects_missing_collection_task() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await seed_workbench_scope(session, suffix="steps-deleted")
        task = await session.get(CollectionTask, seed.collection_task_id)
        assert task is not None
        await session.delete(task)
        await session.flush()
        with pytest.raises(Exception):
            await validate_execution_steps(
                session,
                workspace_id=seed.workspace_id,
                project_id=seed.project_id,
                version=await session.get(WorkflowVersion, seed.version_id),
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_unknown_implementation_fails_closed() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await seed_workbench_scope(session, suffix="steps-missing")
        with pytest.raises(ExecutionStepUnresolvedError):
            await build_execution_steps(
                session,
                workspace_id=seed.workspace_id,
                project_id=seed.project_id,
                workbench_task_id=seed.task_id,
                preview=_preview(implementation_id="missing"),
                catalog=_catalog(),
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_task_must_belong_to_workspace_and_project() -> None:
    async def scenario(session: AsyncSession) -> None:
        first = await seed_workbench_scope(session, suffix="steps-a")
        second = await seed_workbench_scope(session, suffix="steps-b")
        with pytest.raises(Exception):
            await build_execution_steps(
                session,
                workspace_id=first.workspace_id,
                project_id=first.project_id,
                workbench_task_id=second.task_id,
                preview=_preview(),
                catalog=_catalog(),
            )

    await with_sqlite_session(scenario)
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_execution_steps.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `services.workbench.execution_steps`。

- [ ] **Step 3: 写实现**

在 `collectors/endpoint_catalog.py` 末尾加公开查询：

```python
def collector_type_for_endpoint(endpoint_type: str) -> str | None:
    # 公开只读查询；键空间仍是 endpoint_type。
    return _ENDPOINT_TO_COLLECTOR.get(endpoint_type)
```

在 `schemas/workflow_planner.py` 的 `WorkflowStepPreview` 之后加：

```python
class ExecutionStepPreview(WorkflowPlannerContract):
    # C4 固化到 workflow_versions.plan_payload 的执行步骤。
    step_index: int = Field(ge=0)
    task_id: str
    endpoint_type: str
    collector_type: str
    depends_on: list[int] = Field(default_factory=list)
    max_attempts: int | None = Field(default=None, ge=1, le=5)
```

并在 `WorkflowPlanPreview` 的 `steps` 字段后加：

```python
    execution_steps: list[ExecutionStepPreview] = Field(default_factory=list)
```

Create `apps/api/src/data_intelligence_hub/services/workbench/execution_steps.py`:

```python
# 在不可变 workflow_versions 中固化执行步骤。

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.endpoint_catalog import collector_type_for_endpoint
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.schemas.workflow_planner import (
    ExecutionStepPreview,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.workbench.errors import WorkbenchError


class ExecutionStepError(WorkbenchError):
    code = "execution_step_invalid"
    status_code = 422


class ExecutionStepsMissingError(ExecutionStepError):
    code = "execution_steps_missing"


class ExecutionStepUnresolvedError(ExecutionStepError):
    code = "execution_step_unresolved"


class CollectionTaskInvalidError(ExecutionStepError):
    code = "collection_task_invalid"


class _Catalog(Protocol):
    implementations: list[Any]


def _resolve_endpoint(catalog: _Catalog, implementation_id: str) -> tuple[str, str]:
    implementation = next(
        (
            item
            for item in catalog.implementations
            if item.implementation_id == implementation_id
        ),
        None,
    )
    if implementation is None:
        raise ExecutionStepUnresolvedError(
            f"implementation_not_found:{implementation_id}"
        )
    for endpoint_type in implementation.supported_endpoints:
        collector_type = collector_type_for_endpoint(endpoint_type)
        if collector_type is not None:
            return endpoint_type, collector_type
    raise ExecutionStepUnresolvedError(
        f"endpoint_not_registered:{implementation_id}"
    )


def _requirement(preview: WorkflowPlanPreview, requirement_ref: str) -> Any:
    for item in preview.route_requirements:
        if item.requirement_ref == requirement_ref:
            return item
    raise ExecutionStepUnresolvedError(f"requirement_not_found:{requirement_ref}")


async def build_execution_steps(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workbench_task_id: uuid.UUID,
    preview: WorkflowPlanPreview,
    catalog: _Catalog | None = None,
) -> list[ExecutionStepPreview]:
    task = await session.scalar(
        select(WorkbenchTask).where(
            WorkbenchTask.id == workbench_task_id,
            WorkbenchTask.workspace_id == workspace_id,
            WorkbenchTask.project_id == project_id,
        )
    )
    if task is None:
        raise CollectionTaskInvalidError("workbench_task_not_found")
    if not task.markets:
        raise CollectionTaskInvalidError("workbench_task_markets_empty")
    if catalog is None:
        from data_intelligence_hub.services.capability_catalog import (
            resolve_current_capability_catalog,
        )

        catalog = await resolve_current_capability_catalog(session)

    steps: list[ExecutionStepPreview] = []
    for route_plan in preview.route_plans:
        if not route_plan.route_eligible or route_plan.primary_implementation is None:
            continue
        requirement = _requirement(preview, route_plan.requirement_ref)
        endpoint_type, collector_type = _resolve_endpoint(
            catalog,
            route_plan.primary_implementation.implementation_id,
        )
        name = f"{task.brand} {requirement.requirement_ref}"
        source = Source(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name[:200],
            type=collector_type,
            url=None,
            config={},
            schedule_cron=None,
            enabled=True,
        )
        session.add(source)
        await session.flush()
        collection_task = CollectionTask(
            workspace_id=workspace_id,
            project_id=project_id,
            source_id=source.id,
            collector_type=collector_type,
            name=name[:200],
            status="enabled",
            config={
                "endpoint_type": endpoint_type,
                "platform": requirement.platform.value,
                "resource_type": requirement.resource_type.value,
                "operation": requirement.operation.value,
                "market_codes": list(task.markets),
            },
        )
        session.add(collection_task)
        await session.flush()
        steps.append(
            ExecutionStepPreview(
                step_index=len(steps),
                task_id=str(collection_task.id),
                endpoint_type=endpoint_type,
                collector_type=collector_type,
                depends_on=[],
                max_attempts=None,
            )
        )
    if not steps:
        raise ExecutionStepsMissingError("no_eligible_route_plan")
    return steps


async def validate_execution_steps(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    version: WorkflowVersion,
) -> list[ExecutionStepPreview]:
    # 提交前重新校验不可变快照与 collection_tasks，防止任务被删除或跨租户。
    payload = version.plan_payload or {}
    raw = payload.get("execution_steps")
    if not isinstance(raw, list) or not raw:
        raise ExecutionStepsMissingError("execution_steps_missing")
    steps: list[ExecutionStepPreview] = []
    for item in raw:
        try:
            step = ExecutionStepPreview.model_validate(item)
            task_id = uuid.UUID(step.task_id)
        except (ValueError, TypeError) as exc:
            raise CollectionTaskInvalidError("execution_step_invalid") from exc
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise CollectionTaskInvalidError(f"collection_task_not_found:{task_id}")
        if task.workspace_id != workspace_id or task.project_id != project_id:
            raise CollectionTaskInvalidError(f"collection_task_tenant_mismatch:{task_id}")
        steps.append(step)
    return steps


__all__ = [
    "CollectionTaskInvalidError",
    "ExecutionStepError",
    "ExecutionStepUnresolvedError",
    "ExecutionStepsMissingError",
    "build_execution_steps",
    "validate_execution_steps",
]
```

在 `tests/unit/workbench_support.py` 加 `with_sqlite_session`：

```python
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base


async def with_sqlite_session(
    scenario: Callable[[AsyncSession], Awaitable[None]],
) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await scenario(session)
    finally:
        await engine.dispose()
```

- [ ] **Step 4: 接入版本创建**

在 `services/workflow_planner/persistence.py` 的 `_persist_version_graph` 签名加：

```python
    workbench_task_id: uuid.UUID | None = None,
```

在 `preview = build_result.preview` 之后加：

```python
    if workbench_task_id is not None:
        from data_intelligence_hub.services.workbench.execution_steps import (
            build_execution_steps,
        )

        execution_steps = await build_execution_steps(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workbench_task_id=workbench_task_id,
            preview=preview,
        )
        preview = preview.model_copy(
            update={"execution_steps": execution_steps}
        )
```

在两个调用点传 `workbench_task_id=payload.workbench_task_id`：`_create_workflow_plan_attempt` 与 `_create_workflow_version_attempt`。`_persist_version_graph` 的其它调用点（clone/refresh）没有 workbench task 时保持 `None`，`execution_steps` 为空列表；C6 只在 `runs.workflow_version_id` 存在且计划来自 workbench 时执行，空步骤会在 C6 报 `run_step_plan_missing`。

- [ ] **Step 5: 跑测试并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_execution_steps.py tests/unit/test_workbench_task_repository.py -v
.venv/bin/ruff check src/data_intelligence_hub/services/workbench/execution_steps.py   src/data_intelligence_hub/schemas/workflow_planner.py   src/data_intelligence_hub/services/workflow_planner/persistence.py   src/data_intelligence_hub/collectors/endpoint_catalog.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "create_workflow_version" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_workflow_plan" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/workbench/execution_steps.py   apps/api/src/data_intelligence_hub/schemas/workflow_planner.py   apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py   apps/api/src/data_intelligence_hub/collectors/endpoint_catalog.py   apps/api/tests/unit/workbench_support.py   apps/api/tests/unit/test_workbench_execution_steps.py
git commit -m "feat(workbench): freeze execution steps into workflow versions (C4)"
```

Expected: 全部通过；`detect-changes` 覆盖本任务文件且不含 `partial: true` / `truncated: true`。

---

### Task 3B: 初始计划版本接缝（客户 create_task → collect 可执行）

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/workbench/initial_version.py`
- Test: `apps/api/tests/unit/test_workbench_initial_version.py`

**Interfaces:**
- Consumes: `get_workbench_task`、`list_versions_for_task`、`get_workflow_version_with_plan`、`build_workflow_plan_result`、`create_workflow_plan`、`transition_workflow_plan_status`、`resolve_current_capability_catalog`、`WorkflowPlanCreateRequest`（Task 3 已增加 `workbench_task_id`）。
- Produces:
  - `build_initial_planning_input(task: WorkbenchTask) -> PlanningInput`
  - `create_initial_workflow_version_for_task(session, *, workspace_id, project_id, created_by_user_id, workbench_task_id, idempotency_key, request_id=None) -> uuid.UUID`
- 规则：已有任务版本时复用最后一条，不创建第二个版本；没有版本时用既有 planner 创建 `previewed` 计划与版本，再走既有 `transition_workflow_plan_status` 批准为 `approved`。计划必须 `current_version_id == version.id` 且状态 `approved`，否则 fail-closed。C4 不写第二套计划事实，C13 不生成计划。
- 这是一个 C4 接缝，`create_workbench_task` 本身仍只建任务单；客户 `create_task` 与 `collect` 在 C13 适配器里显式调用该接缝。这样浏览器/API 建单不会自动消耗计划生成配额，客户链则保证可执行。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_workbench_initial_version.py`:

```python
"""初始计划版本接缝。

只验证接缝调用既有 planner 服务、复用已有版本并批准首个版本。
计划生成、指纹与持久化仍归 workflow_planner；本测试不复制这些逻辑。
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from data_intelligence_hub.schemas.workflow_planner import (
    FlowMode,
    MonitoringScopeType,
)
from data_intelligence_hub.services.workbench import initial_version as module
from data_intelligence_hub.services.workbench.initial_version import (
    build_initial_planning_input,
    create_initial_workflow_version_for_task,
)
from data_intelligence_hub.services.workbench.errors import (
    PlanNotApprovedError,
    PlanVersionNotCurrentError,
)

TASK_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _task() -> SimpleNamespace:
    return SimpleNamespace(
        id=TASK_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        brand="Momcozy",
        category="breast_pump",
        competitors=["Medela"],
        markets=["US", "DE"],
        status="draft",
    )


def test_initial_planning_input_projects_task_slots() -> None:
    planning_input = build_initial_planning_input(_task())
    assert planning_input.flow_mode is FlowMode.BATCH_RESEARCH
    assert planning_input.default_regions == ["US", "DE"]
    assert [scope.scope_type for scope in planning_input.scopes] == [
        MonitoringScopeType.BRAND,
        MonitoringScopeType.CATEGORY,
        MonitoringScopeType.COMPETITOR,
    ]
    assert [scope.canonical_term for scope in planning_input.scopes] == [
        "Momcozy",
        "breast_pump",
        "Medela",
    ]
    assert len({scope.scope_ref for scope in planning_input.scopes}) == 3


@pytest.mark.asyncio
async def test_seam_creates_and_approves_first_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_task(session: object, **kwargs: object) -> object:
        del session
        assert kwargs["task_id"] == TASK_ID
        return _task()

    async def fake_versions(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return []

    async def fake_catalog(session: object) -> object:
        del session
        return SimpleNamespace(catalog_digest="catalog-v1", implementations=[])

    def fake_build(**kwargs: object) -> object:
        del kwargs
        return SimpleNamespace(
            preview=SimpleNamespace(
                planning_status="resolved",
                preview_fingerprint="sha256:" + "a" * 64,
            )
        )

    async def fake_create(session: object, **kwargs: object) -> object:
        del session
        calls.append(("create", dict(kwargs)))
        return SimpleNamespace(
            plan=SimpleNamespace(
                id=PLAN_ID,
                status="previewed",
                current_version_id=VERSION_ID,
            ),
            version=SimpleNamespace(id=VERSION_ID),
        )

    async def fake_transition(session: object, **kwargs: object) -> object:
        del session
        calls.append(("transition", dict(kwargs)))
        return SimpleNamespace(to_status="approved")

    monkeypatch.setattr(module, "get_workbench_task", fake_task)
    monkeypatch.setattr(module, "list_versions_for_task", fake_versions)
    monkeypatch.setattr(module, "resolve_current_capability_catalog", fake_catalog)
    monkeypatch.setattr(module, "build_workflow_plan_result", fake_build)
    monkeypatch.setattr(module, "create_workflow_plan", fake_create)
    monkeypatch.setattr(module, "transition_workflow_plan_status", fake_transition)

    version_id = await create_initial_workflow_version_for_task(
        object(),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        workbench_task_id=TASK_ID,
        idempotency_key="customer-task-key-0001",
    )

    assert version_id == VERSION_ID
    create_kwargs = calls[0][1]
    assert create_kwargs["payload"].workbench_task_id == TASK_ID
    assert create_kwargs["idempotency_key"].startswith(
        f"workbench-init:{TASK_ID}:"
    )
    transition_kwargs = calls[1][1]
    assert transition_kwargs["workflow_plan_id"] == PLAN_ID
    assert transition_kwargs["payload"].expected_status == "previewed"
    assert transition_kwargs["payload"].to_status == "approved"


@pytest.mark.asyncio
async def test_seam_reuses_existing_approved_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_task(session: object, **kwargs: object) -> object:
        del session, kwargs
        return _task()

    async def fake_versions(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return [SimpleNamespace(id=VERSION_ID)]

    async def fake_linked(session: object, **kwargs: object) -> object:
        del session, kwargs
        return (
            SimpleNamespace(
                id=VERSION_ID,
                workbench_task_id=TASK_ID,
            ),
            SimpleNamespace(
                id=PLAN_ID,
                status="approved",
                current_version_id=VERSION_ID,
            ),
        )

    async def fail_create(*args: object, **kwargs: object) -> object:
        raise AssertionError("existing version must not create a second plan")

    monkeypatch.setattr(module, "get_workbench_task", fake_task)
    monkeypatch.setattr(module, "list_versions_for_task", fake_versions)
    monkeypatch.setattr(module, "get_workflow_version_with_plan", fake_linked)
    monkeypatch.setattr(module, "create_workflow_plan", fail_create)

    version_id = await create_initial_workflow_version_for_task(
        object(),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        workbench_task_id=TASK_ID,
        idempotency_key="customer-task-key-0002",
    )
    assert version_id == VERSION_ID


@pytest.mark.asyncio
async def test_seam_rejects_stale_current_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_task(session: object, **kwargs: object) -> object:
        del session, kwargs
        return _task()

    async def fake_versions(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return [SimpleNamespace(id=VERSION_ID)]

    async def fake_linked(session: object, **kwargs: object) -> object:
        del session, kwargs
        return (
            SimpleNamespace(id=VERSION_ID, workbench_task_id=TASK_ID),
            SimpleNamespace(
                id=PLAN_ID,
                status="approved",
                current_version_id=uuid.uuid4(),
            ),
        )

    monkeypatch.setattr(module, "get_workbench_task", fake_task)
    monkeypatch.setattr(module, "list_versions_for_task", fake_versions)
    monkeypatch.setattr(module, "get_workflow_version_with_plan", fake_linked)

    with pytest.raises(PlanVersionNotCurrentError):
        await create_initial_workflow_version_for_task(
            object(),
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            created_by_user_id=USER_ID,
            workbench_task_id=TASK_ID,
            idempotency_key="customer-task-key-0003",
        )


@pytest.mark.asyncio
async def test_seam_rejects_unapproved_existing_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_task(session: object, **kwargs: object) -> object:
        del session, kwargs
        return _task()

    async def fake_versions(session: object, **kwargs: object) -> list[object]:
        del session, kwargs
        return [SimpleNamespace(id=VERSION_ID)]

    async def fake_linked(session: object, **kwargs: object) -> object:
        del session, kwargs
        return (
            SimpleNamespace(id=VERSION_ID, workbench_task_id=TASK_ID),
            SimpleNamespace(
                id=PLAN_ID,
                status="draft",
                current_version_id=VERSION_ID,
            ),
        )

    monkeypatch.setattr(module, "get_workbench_task", fake_task)
    monkeypatch.setattr(module, "list_versions_for_task", fake_versions)
    monkeypatch.setattr(module, "get_workflow_version_with_plan", fake_linked)

    with pytest.raises(PlanNotApprovedError):
        await create_initial_workflow_version_for_task(
            object(),
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            created_by_user_id=USER_ID,
            workbench_task_id=TASK_ID,
            idempotency_key="customer-task-key-0004",
        )
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_initial_version.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `services.workbench.initial_version`。

- [ ] **Step 3: 写实现**

Create `apps/api/src/data_intelligence_hub/services/workbench/initial_version.py`:

```python
"""任务单的初始计划版本接缝。

只调用既有 workflow planner 的公开函数。C4 不复制计划生成、指纹或持久化逻辑。
客户 create_task 与 collect 都通过此接缝取得同一个已批准版本。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.repositories.workbench_tasks import (
    get_workbench_task,
    list_versions_for_task,
)
from data_intelligence_hub.repositories.workflow_plans import (
    get_workflow_version_with_plan,
)
from data_intelligence_hub.schemas.capability_catalog import PlatformId
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanCreateRequest,
    WorkflowPlanTransitionRequest,
    normalize_idempotency_key,
)
from data_intelligence_hub.schemas.workflow_planner import (
    FlowMode,
    MonitoringScopeDraft,
    MonitoringScopeType,
    PlanningInput,
)
from data_intelligence_hub.services.capability_catalog import (
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.workbench.errors import (
    PlanNotApprovedError,
    PlanVersionNotCurrentError,
    WorkbenchTaskCancelledError,
    WorkbenchTaskNotFoundError,
    WorkbenchValidationError,
    WorkbenchVersionNotFoundError,
    WorkflowVersionNotLinkedError,
)
from data_intelligence_hub.services.workflow_planner.persistence import (
    create_workflow_plan,
    transition_workflow_plan_status,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)

_INITIAL_PLAN_PURPOSE = "market_research"
_INITIAL_PLAN_REASON = "customer_task_initial"


def build_initial_planning_input(task: WorkbenchTask) -> PlanningInput:
    """把七槽位任务单投影为既有 planner 的 PlanningInput。"""
    scopes = [
        MonitoringScopeDraft(
            scope_ref=f"brand:{task.id}",
            scope_type=MonitoringScopeType.BRAND,
            canonical_term=task.brand,
            regions=list(task.markets),
        ),
        MonitoringScopeDraft(
            scope_ref=f"category:{task.id}",
            scope_type=MonitoringScopeType.CATEGORY,
            canonical_term=task.category,
            regions=list(task.markets),
        ),
    ]
    scopes.extend(
        MonitoringScopeDraft(
            scope_ref=f"competitor:{task.id}:{index}",
            scope_type=MonitoringScopeType.COMPETITOR,
            canonical_term=competitor,
            regions=list(task.markets),
        )
        for index, competitor in enumerate(task.competitors)
    )
    return PlanningInput(
        flow_mode=FlowMode.BATCH_RESEARCH,
        scopes=scopes,
        default_languages=["en"],
        default_regions=list(task.markets),
        default_platforms=[PlatformId.TIKTOK],
        purpose=_INITIAL_PLAN_PURPOSE,
    )


def _planner_key(workbench_task_id: uuid.UUID, idempotency_key: str) -> str:
    try:
        normalized = normalize_idempotency_key(idempotency_key)
    except ValueError as exc:
        raise WorkbenchValidationError("invalid_request") from exc
    return normalize_idempotency_key(
        f"workbench-init:{workbench_task_id}:{normalized}"
    )


async def _approve_plan(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    request_id: str,
) -> None:
    await transition_workflow_plan_status(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        created_by_user_id=created_by_user_id,
        payload=WorkflowPlanTransitionRequest(
            expected_status="previewed",
            to_status="approved",
            reason=_INITIAL_PLAN_REASON,
        ),
        request_id=request_id,
    )


async def create_initial_workflow_version_for_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    workbench_task_id: uuid.UUID,
    idempotency_key: str,
    request_id: str | None = None,
) -> uuid.UUID:
    """创建或复用任务单的唯一初始计划版本，并保证计划已批准。"""
    request_id = request_id or uuid.uuid4().hex
    task = await get_workbench_task(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=workbench_task_id,
    )
    if task is None:
        raise WorkbenchTaskNotFoundError()
    if task.status == "cancelled":
        raise WorkbenchTaskCancelledError()

    versions = await list_versions_for_task(
        session,
        workspace_id=workspace_id,
        task_id=workbench_task_id,
    )
    if versions:
        version = versions[-1]
        linked = await get_workflow_version_with_plan(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_version_id=version.id,
        )
        if linked is None:
            raise WorkbenchVersionNotFoundError()
        existing_version, plan = linked
        if existing_version.workbench_task_id != task.id:
            raise WorkflowVersionNotLinkedError()
        if plan.current_version_id != existing_version.id:
            raise PlanVersionNotCurrentError()
        if plan.status == "previewed":
            await _approve_plan(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                plan_id=plan.id,
                created_by_user_id=created_by_user_id,
                request_id=request_id,
            )
        elif plan.status != "approved":
            raise PlanNotApprovedError()
        return existing_version.id

    planning_input = build_initial_planning_input(task)
    build_result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=planning_input,
        catalog=await resolve_current_capability_catalog(session),
        generated_at=datetime.now(UTC),
        request_id=request_id,
    )
    if build_result.preview.planning_status != "resolved":
        raise PlanNotApprovedError()
    response = await create_workflow_plan(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=created_by_user_id,
        payload=WorkflowPlanCreateRequest(
            name=f"{task.brand} {task.category}"[:200],
            preview_input=planning_input,
            expected_preview_fingerprint=build_result.preview.preview_fingerprint,
            workbench_task_id=task.id,
        ),
        idempotency_key=_planner_key(workbench_task_id, idempotency_key),
        request_id=request_id,
    )
    await _approve_plan(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=response.plan.id,
        created_by_user_id=created_by_user_id,
        request_id=request_id,
    )
    return response.version.id


__all__ = [
    "build_initial_planning_input",
    "create_initial_workflow_version_for_task",
]
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_initial_version.py -v
```

Expected: 5 passed。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/services/workbench/initial_version.py tests/unit/test_workbench_initial_version.py
.venv/bin/mypy src/data_intelligence_hub/services/workbench/initial_version.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "create_workflow_plan" --direction upstream --repo .
node .gitnexus/run.cjs impact "transition_workflow_plan_status" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件且不含 `partial: true` / `truncated: true`。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/src/data_intelligence_hub/services/workbench/initial_version.py \
  apps/api/tests/unit/test_workbench_initial_version.py
git commit -m "feat(workbench): add initial workflow version seam (C4)"
```

---

### Task 3C: 审计化 run 创建接缝（C4 拥有）

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_creation.py`
- Test: `apps/api/tests/unit/test_run_creation.py`

**Interfaces:**
- Consumes: `repositories.runs.create_run`、`repositories.runs.find_by_idempotency_key`、C2 `services.audit_log.append_audit_event`。
- Produces: `create_run_with_audit(session, *, workspace_id, project_id, trigger, task_id=None, workflow_version_id=None, status="queued", idempotency_key_hash=None, market_code=None) -> Run`。

- [ ] **Step 0: 逐符号 impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "create_run" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `create_run` 仍为 LOW/5 impacted、2 direct；新增接缝不改变仓储签名与现有调用方。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_run_creation.py`:

```python
"""审计化 run 创建接缝的单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.services.run_creation import create_run_with_audit
from tests.unit.workbench_support import seed_workbench_scope


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


@pytest.mark.asyncio
async def test_new_run_writes_exactly_one_run_created(
    session: AsyncSession,
) -> None:
    seed = await seed_workbench_scope(session, suffix="run-creation")
    run = await create_run_with_audit(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_version_id=seed.version_id,
        trigger="api",
        idempotency_key_hash="c" * 64,
        market_code="US",
    )
    await session.commit()

    assert run.status == "queued"
    assert run.market_code == "US"
    audit_actions = list(
        (
            await session.execute(
                select(AuditEvent.action).where(
                    AuditEvent.resource_id == str(run.id)
                )
            )
        ).scalars()
    )
    assert audit_actions == ["run.created"]
    event = await session.scalar(
        select(AuditEvent).where(AuditEvent.resource_id == str(run.id))
    )
    assert event is not None
    assert event.resource_type == "run"
    assert event.actor_type == "system"
    assert event.result == "success"
    assert event.details["market_code"] == "US"
    assert event.details["trigger"] == "api"


@pytest.mark.asyncio
async def test_idempotent_replay_does_not_add_run_created(
    session: AsyncSession,
) -> None:
    seed = await seed_workbench_scope(session, suffix="run-replay")
    first = await create_run_with_audit(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_version_id=seed.version_id,
        trigger="api",
        idempotency_key_hash="d" * 64,
        market_code="US",
    )
    await session.commit()
    second = await create_run_with_audit(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_version_id=seed.version_id,
        trigger="api",
        idempotency_key_hash="d" * 64,
        market_code="US",
    )
    await session.commit()

    assert second.id == first.id
    count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.action == "run.created",
            AuditEvent.resource_id == str(first.id),
        )
    )
    assert count == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_run_creation.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `services.run_creation`。

- [ ] **Step 3: 写审计化 run 创建接缝**

Create `apps/api/src/data_intelligence_hub/services/run_creation.py`:

```python
"""C4 拥有的审计化 run 创建接缝。

``create_run_with_audit`` 是创建 run 的唯一生产入口：同一事务内插入
``runs`` 行并追加 C2 的 ``run.created`` 审计事件。C4 提交服务与 C6 旧入口
收敛都调用本函数；C4 不依赖 C6 模块。
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run import Run, RunStatus
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.services.audit_log import append_audit_event


async def create_run_with_audit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    trigger: str,
    task_id: uuid.UUID | None = None,
    workflow_version_id: uuid.UUID | None = None,
    status: RunStatus | str = RunStatus.QUEUED,
    idempotency_key_hash: str | None = None,
    market_code: str | None = None,
) -> Run:
    """插入新 run 并写 ``run.created``；幂等重放不写审计。

    带幂等键时先查后插。已存在时返回原行且不追加审计；并发插入由
    ``create_run`` 的唯一索引与调用方的 IntegrityError 分支处理。
    本函数不提交事务，提交边界由调用方决定。
    """
    if idempotency_key_hash is not None:
        existing = await runs_repository.find_by_idempotency_key(
            session,
            workspace_id=workspace_id,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing is not None:
            return existing

    run = await runs_repository.create_run(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        workflow_version_id=workflow_version_id,
        status=status,
        trigger=trigger,
        idempotency_key_hash=idempotency_key_hash,
        market_code=market_code,
    )
    await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        actor_type="system",
        action="run.created",
        resource_type="run",
        resource_id=str(run.id),
        result="success",
        details={
            "run_id": str(run.id),
            "trigger": trigger,
            "market_code": market_code,
            "status": run.status,
        },
    )
    return run


__all__ = ["create_run_with_audit"]
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_run_creation.py -v
```

Expected: 2 passed。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/services/run_creation.py tests/unit/test_run_creation.py
.venv/bin/mypy src/data_intelligence_hub/services/run_creation.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件且不含 `partial: true` / `truncated: true`。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/src/data_intelligence_hub/services/run_creation.py \
  apps/api/tests/unit/test_run_creation.py
git commit -m "feat(workbench): add audited run creation seam (C4)"
```

**边界：** 本接缝是 C4 与后续 C6 旧入口收敛共用的唯一 run 创建入口。C4 的 `submit_workbench_task` 只调用 `create_run_with_audit`；C6 在 Task 10 收敛旧入口时复用同一函数。C4 不 import C6 的 `run_service`、`run_audit` 或任何 C6 模块，因此不依赖未来切片。

---

### Task 4: 逐市场幂等提交服务与 blocked gate/gap

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/workbench/submission.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/runs.py`（`create_run` 已在 Task 3 完成）
- Test: `apps/api/tests/unit/test_workbench_submission_service.py`

**Interfaces:**
- Consumes:
  - `WorkbenchTask` / `WorkflowVersion` / `Run`
  - `find_by_idempotency_hashes`、`list_runs_for_workflow_version`
  - `services.run_creation.create_run_with_audit`（C4 接缝；不直接调用仓储 `create_run`）
  - `get_workflow_version_with_plan`
  - `create_authorization`、`list_authorizations_for_versions`
- Produces:
  - `normalize_submission_key(value: str) -> str`
  - `market_idempotency_hash(key: str, market_code: str) -> str`
  - `WorkbenchSubmissionResult`
  - `submit_workbench_task(session, *, workspace_id, project_id, workbench_task_id, workflow_version_id, idempotency_key, enabled_markets=None) -> WorkbenchSubmissionResult`

- [ ] **Step 0: 逐符号 impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "create_authorization" --direction upstream --repo .
node .gitnexus/run.cjs impact "list_authorizations_for_versions" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_run" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_workflow_version" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 记录每个符号的调用方、processes 与 `risk`。`UNKNOWN` 必须文本搜索确认；HIGH/CRITICAL 先告警并写缓解。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_workbench_submission_service.py`:

```python
"""逐市场提交与幂等的服务级测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.services.workbench.errors import (
    IdempotencyKeyConflictError,
    WorkflowVersionAlreadySubmittedError,
)
from data_intelligence_hub.services.workbench.markets import (
    market_role_for,
    task_market_codes,
)
from data_intelligence_hub.services.workbench.submission import (
    market_idempotency_hash,
    normalize_submission_key,
    submit_workbench_task,
)
from tests.unit.workbench_support import add_linked_version, seed_workbench_scope

_KEY = "submission-key-0001"


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def test_idempotency_material_is_stable_and_market_scoped() -> None:
    assert normalize_submission_key("  " + _KEY + "  ") == _KEY
    assert market_idempotency_hash(_KEY, "US") == market_idempotency_hash(_KEY, "US")
    assert market_idempotency_hash(_KEY, "US") != market_idempotency_hash(_KEY, "DE")
    assert len(market_idempotency_hash(_KEY, "US")) == 64


def test_market_role_is_derived_from_task_not_persisted() -> None:
    assert task_market_codes(
        primary_market="US",
        comparison_markets=["DE", "FR"],
    ) == ("US", "DE", "FR")
    assert market_role_for(
        primary_market="US",
        comparison_markets=["DE", "FR"],
        market_code="US",
    ) == "primary"
    assert market_role_for(
        primary_market="US",
        comparison_markets=["DE", "FR"],
        market_code="DE",
    ) == "compare"
    with pytest.raises(ValueError, match="task_markets_invalid"):
        market_role_for(
            primary_market="US",
            comparison_markets=["DE"],
            market_code="GB",
        )


@pytest.mark.asyncio
async def test_submission_creates_one_queued_run_per_market(
    session: AsyncSession,
) -> None:
    seed = await seed_workbench_scope(session, suffix="submit", markets=("US", "DE"))
    result = await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US", "DE"),
    )

    assert result.idempotent_replay is False
    assert [run.market_code for run in result.runs] == ["US", "DE"]
    assert dict(result.market_roles) == {"US": "primary", "DE": "compare"}
    assert {run.status for run in result.runs} == {"queued"}
    assert {run.workflow_version_id for run in result.runs} == {seed.version_id}
    assert result.gaps == ()

    task = await session.get(WorkbenchTask, seed.task_id)
    assert task is not None and task.status == "submitted"
    run_created_count = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.action == "run.created")
    )
    assert run_created_count == 2


@pytest.mark.asyncio
async def test_replay_returns_the_same_run_ids(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="replay")
    first = await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US", "DE"),
    )
    second = await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=(),
    )

    assert second.idempotent_replay is True
    assert [run.id for run in second.runs] == [run.id for run in first.runs]
    assert second.gaps == first.gaps
    replayed_created = await session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.action == "run.created")
    )
    assert replayed_created == 2


@pytest.mark.asyncio
async def test_same_key_different_version_conflicts(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="conflict")
    await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US", "DE"),
    )

    second_version_id = await add_linked_version(session, seed)
    with pytest.raises(IdempotencyKeyConflictError):
        await submit_workbench_task(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workbench_task_id=seed.task_id,
            workflow_version_id=second_version_id,
            idempotency_key=_KEY,
            enabled_markets=("US", "DE"),
        )


@pytest.mark.asyncio
async def test_new_key_on_submitted_version_is_rejected(
    session: AsyncSession,
) -> None:
    seed = await seed_workbench_scope(session, suffix="duplicate")
    await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US", "DE"),
    )

    with pytest.raises(WorkflowVersionAlreadySubmittedError):
        await submit_workbench_task(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workbench_task_id=seed.task_id,
            workflow_version_id=seed.version_id,
            idempotency_key="submission-key-0002",
            enabled_markets=("US", "DE"),
        )


@pytest.mark.asyncio
async def test_database_rejects_two_runs_for_same_version_and_market(
    session: AsyncSession,
) -> None:
    """不同幂等键也不能为同一版本/市场写第二行 run。"""
    from sqlalchemy.exc import IntegrityError

    from data_intelligence_hub.repositories import runs as runs_repository

    seed = await seed_workbench_scope(session, suffix="unique-market")
    await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US", "DE"),
    )

    with pytest.raises(IntegrityError):
        # 仓储级测试直接调用；生产代码只允许 services/run_creation.py 调用。
        await runs_repository.create_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_version_id=seed.version_id,
            status="queued",
            trigger="api",
            idempotency_key_hash="b" * 64,
            market_code="US",
        )
        await session.flush()


@pytest.mark.asyncio
async def test_unique_conflict_after_lost_race_returns_version_submitted(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模拟两个不同幂等键同时通过预查的竞态。"""
    from sqlalchemy.exc import IntegrityError

    from data_intelligence_hub.repositories import runs as runs_repository

    seed = await seed_workbench_scope(session, suffix="race")
    calls = {"count": 0}

    async def first_call_is_empty(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return []
        # 第二个事务已经插入的 run；这里只需要非空。
        return [object()]

    monkeypatch.setattr(
        runs_repository,
        "list_runs_for_workflow_version",
        first_call_is_empty,
    )

    async def fail_with_integrity(*args, **kwargs):
        raise IntegrityError("uq_runs_workflow_version_market", {}, Exception())

    monkeypatch.setattr(runs_repository, "create_run", fail_with_integrity)

    with pytest.raises(WorkflowVersionAlreadySubmittedError):
        await submit_workbench_task(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workbench_task_id=seed.task_id,
            workflow_version_id=seed.version_id,
            idempotency_key=_KEY,
            enabled_markets=("US", "DE"),
        )


@pytest.mark.asyncio
async def test_blocked_market_keeps_run_and_writes_gate_and_gap(
    session: AsyncSession,
) -> None:
    seed = await seed_workbench_scope(session, suffix="blocked")
    result = await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US",),
    )

    assert [run.market_code for run in result.runs] == ["US", "DE"]
    assert {run.status for run in result.runs} == {"queued"}
    assert [gap.market_code for gap in result.gaps] == ["DE"]
    assert result.gaps[0].reason_code == "market_unsupported"

    gates = list(
        (
            await session.execute(
                select(Authorization).where(
                    Authorization.workspace_id == seed.workspace_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(gates) == 1
    assert gates[0].gate_status == "blocked"
    assert gates[0].scope["gap"]["reason_code"] == "market_unsupported"
    assert gates[0].scope["market_code"] == "DE"


@pytest.mark.asyncio
async def test_c4_writes_no_ledger_steps_or_task_runs(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(session, suffix="boundaries")
    await submit_workbench_task(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workbench_task_id=seed.task_id,
        workflow_version_id=seed.version_id,
        idempotency_key=_KEY,
        enabled_markets=("US", "DE"),
    )

    for model in (RunLedgerEntry, RunStep, TaskRun):
        count = await session.scalar(select(func.count()).select_from(model))
        assert count == 0
    run_count = await session.scalar(select(func.count()).select_from(Run))
    assert run_count == 2


@pytest.mark.asyncio
async def test_unapproved_plan_is_rejected(session: AsyncSession) -> None:
    seed = await seed_workbench_scope(
        session,
        suffix="unapproved",
        plan_status="previewed",
    )
    from data_intelligence_hub.services.workbench.errors import PlanNotApprovedError

    with pytest.raises(PlanNotApprovedError):
        await submit_workbench_task(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workbench_task_id=seed.task_id,
            workflow_version_id=seed.version_id,
            idempotency_key=_KEY,
            enabled_markets=("US", "DE"),
        )
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_submission_service.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `services.workbench.submission`。

- [ ] **Step 3: 写提交服务**

Create `apps/api/src/data_intelligence_hub/services/workbench/submission.py`:

```python
"""逐市场提交任务单。

规则：

1. 每个市场一行 ``runs``，初始 ``status=queued``。
2. 幂等键按市场派生摘要，复用 ``uq_runs_workspace_idempotency``。
3. 同一键不同参数返回 409；同一版本重复提交换新键也返回 409。
4. blocked 市场保留 run；门禁写 ``authorizations``，gap 写 ``scope.gap``。
5. 不写 ``runs.status=blocked``，不写 run_steps、task_runs、账本。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.run import Run, RunStatus
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.repositories import authorizations as authorization_repository
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.repositories import workbench_tasks as task_repository
from data_intelligence_hub.repositories import workflow_plans as plan_repository
from data_intelligence_hub.schemas.workbench import WorkbenchGapResponse
from data_intelligence_hub.services.run_creation import create_run_with_audit
from data_intelligence_hub.services.workbench.errors import (
    IdempotencyKeyConflictError,
    IdempotencyStateInconsistentError,
    PlanNotApprovedError,
    PlanVersionNotCurrentError,
    WorkbenchTaskCancelledError,
    WorkbenchTaskNotFoundError,
    WorkbenchValidationError,
    WorkbenchVersionNotFoundError,
    WorkflowVersionAlreadySubmittedError,
    WorkflowVersionNotLinkedError,
)
from data_intelligence_hub.services.workbench.markets import (
    market_role_for,
    resolve_market_decisions,
    task_market_codes,
)

_SUBMISSION_KEY_PREFIX = "workbench-submit.v1"


def normalize_submission_key(value: str) -> str:
    normalized = value.strip()
    if not 12 <= len(normalized) <= 200:
        raise WorkbenchValidationError("idempotency_key_invalid")
    return normalized


def market_idempotency_hash(key: str, market_code: str) -> str:
    material = f"{_SUBMISSION_KEY_PREFIX}:{key}:{market_code}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class WorkbenchSubmissionResult:
    workbench_task_id: uuid.UUID
    workflow_version_id: uuid.UUID
    runs: tuple[Run, ...]
    gaps: tuple[WorkbenchGapResponse, ...]
    idempotent_replay: bool
    market_roles: tuple[tuple[str, str], ...] = ()


def _market_gap(market_code: str) -> WorkbenchGapResponse:
    return WorkbenchGapResponse(
        market_code=market_code,
        customer_message=(
            f"Market {market_code} is not enabled for this delivery."
        ),
        remediation=(
            "Enable the market in the workspace configuration, or remove it "
            "from the task before submitting again."
        ),
    )


def _gate_expiry(task: WorkbenchTask) -> datetime:
    end = datetime.combine(task.window_end, time.max, tzinfo=UTC)
    now = datetime.now(UTC)
    return end if end > now else now + timedelta(days=30)


def _blocked_scope(
    *,
    task: WorkbenchTask,
    workflow_version_id: uuid.UUID,
    market_code: str,
    gap: WorkbenchGapResponse,
) -> dict[str, object]:
    return {
        "task_id": str(task.id),
        "workflow_version_id": str(workflow_version_id),
        "market_code": market_code,
        "template_id": task.task_type or "T1",
        "window": {
            "start": task.window_start.isoformat(),
            "end": task.window_end.isoformat(),
        },
        "gap": gap.model_dump(mode="json"),
    }


def _gaps_for_version(
    authorizations: list[Authorization],
) -> tuple[WorkbenchGapResponse, ...]:
    gaps: list[WorkbenchGapResponse] = []
    for authorization in authorizations:
        scope = authorization.scope
        if not isinstance(scope, dict):
            continue
        gap_payload = scope.get("gap")
        if isinstance(gap_payload, dict):
            gaps.append(WorkbenchGapResponse.model_validate(gap_payload))
    return tuple(gaps)


def _market_roles(
    task: WorkbenchTask,
    markets: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            market,
            market_role_for(
                primary_market=task.primary_market,
                comparison_markets=task.comparison_markets,
                market_code=market,
            ),
        )
        for market in markets
    )


def _replay(
    *,
    task: WorkbenchTask,
    workflow_version_id: uuid.UUID,
    markets: tuple[str, ...],
    existing: list[Run],
    gaps: tuple[WorkbenchGapResponse, ...],
) -> WorkbenchSubmissionResult:
    by_market = {
        run.market_code: run
        for run in existing
        if run.market_code is not None
    }
    if set(by_market) != set(markets):
        raise IdempotencyStateInconsistentError()
    for run in by_market.values():
        if (
            run.project_id != task.project_id
            or run.workflow_version_id != workflow_version_id
        ):
            raise IdempotencyKeyConflictError()
    ordered = tuple(by_market[market] for market in markets)
    return WorkbenchSubmissionResult(
        workbench_task_id=task.id,
        workflow_version_id=workflow_version_id,
        runs=ordered,
        gaps=gaps,
        idempotent_replay=True,
        market_roles=_market_roles(task, markets),
    )


async def _existing_gaps(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> tuple[WorkbenchGapResponse, ...]:
    authorizations = await authorization_repository.list_authorizations_for_versions(
        session,
        workspace_id=workspace_id,
        version_ids=[workflow_version_id],
    )
    return _gaps_for_version(authorizations)


async def submit_workbench_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workbench_task_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    idempotency_key: str,
    enabled_markets: Collection[str] | None = None,
) -> WorkbenchSubmissionResult:
    key = normalize_submission_key(idempotency_key)
    task = await task_repository.get_workbench_task(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=workbench_task_id,
    )
    if task is None:
        raise WorkbenchTaskNotFoundError()

    markets = task_market_codes(
        primary_market=task.primary_market,
        comparison_markets=task.comparison_markets,
    )
    if not markets or len(set(markets)) != len(markets):
        raise WorkbenchValidationError("task_markets_invalid")
    hashes = {market: market_idempotency_hash(key, market) for market in markets}

    existing = await runs_repository.find_by_idempotency_hashes(
        session,
        workspace_id=workspace_id,
        hashes=tuple(hashes.values()),
    )
    if existing:
        replay_linked = await plan_repository.get_workflow_version_with_plan(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_version_id=workflow_version_id,
        )
        if replay_linked is None:
            raise WorkbenchVersionNotFoundError()
        replay_version, _ = replay_linked
        if replay_version.workbench_task_id != task.id:
            raise WorkflowVersionNotLinkedError()
        gaps = await _existing_gaps(
            session,
            workspace_id=workspace_id,
            workflow_version_id=workflow_version_id,
        )
        return _replay(
            task=task,
            workflow_version_id=workflow_version_id,
            markets=markets,
            existing=existing,
            gaps=gaps,
        )

    if task.status == "cancelled":
        raise WorkbenchTaskCancelledError()

    linked = await plan_repository.get_workflow_version_with_plan(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_version_id=workflow_version_id,
    )
    if linked is None:
        raise WorkbenchVersionNotFoundError()
    version, plan = linked
    if version.workbench_task_id != task.id:
        raise WorkflowVersionNotLinkedError()
    if plan.status != "approved":
        raise PlanNotApprovedError()
    if plan.current_version_id != version.id:
        raise PlanVersionNotCurrentError()

    already = await runs_repository.list_runs_for_workflow_version(
        session,
        workspace_id=workspace_id,
        workflow_version_id=version.id,
    )
    if already:
        raise WorkflowVersionAlreadySubmittedError()

    from data_intelligence_hub.services.workbench.execution_steps import (
        validate_execution_steps,
    )

    await validate_execution_steps(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        version=version,
    )
    decisions = resolve_market_decisions(
        markets,
        enabled_markets=enabled_markets,
    )
    gaps = tuple(
        _market_gap(decision.market_code)
        for decision in decisions
        if not decision.enabled
    )

    try:
        created: list[Run] = []
        for decision in decisions:
            run = await create_run_with_audit(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_version_id=version.id,
                status=RunStatus.QUEUED,
                trigger="api",
                idempotency_key_hash=hashes[decision.market_code],
                market_code=decision.market_code,
            )
            created.append(run)
            if not decision.enabled:
                gap = _market_gap(decision.market_code)
                await authorization_repository.create_authorization(
                    session,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    plan_id=plan.id,
                    plan_version_id=version.id,
                    gate_id="G-Plan",
                    gate_status="blocked",
                    scope=_blocked_scope(
                        task=task,
                        workflow_version_id=version.id,
                        market_code=decision.market_code,
                        gap=gap,
                    ),
                    max_cost_usd=Decimal("0"),
                    approver=task.owner_id,
                    expires_at=_gate_expiry(task),
                    idempotency_key_hash=hashes[decision.market_code],
                )
        task.status = "submitted"
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raced = await runs_repository.find_by_idempotency_hashes(
            session,
            workspace_id=workspace_id,
            hashes=tuple(hashes.values()),
        )
        if raced:
            task = await task_repository.get_workbench_task(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=workbench_task_id,
            )
            if task is None:
                raise WorkbenchTaskNotFoundError()
            gaps = await _existing_gaps(
                session,
                workspace_id=workspace_id,
                workflow_version_id=workflow_version_id,
            )
            return _replay(
                task=task,
                workflow_version_id=workflow_version_id,
                markets=markets,
                existing=raced,
                gaps=gaps,
            )
        concurrent = await runs_repository.list_runs_for_workflow_version(
            session,
            workspace_id=workspace_id,
            workflow_version_id=workflow_version_id,
        )
        if concurrent:
            # 不同 Idempotency-Key 并发提交同一版本/市场时，
            # uq_runs_workflow_version_market 是唯一防线。
            raise WorkflowVersionAlreadySubmittedError()
        raise

    ordered = tuple(
        sorted(
            created,
            key=lambda run: markets.index(run.market_code or ""),
        )
    )
    return WorkbenchSubmissionResult(
        workbench_task_id=workbench_task_id,
        workflow_version_id=workflow_version_id,
        runs=ordered,
        gaps=gaps,
        idempotent_replay=False,
        market_roles=_market_roles(task, markets),
    )


__all__ = [
    "WorkbenchSubmissionResult",
    "market_idempotency_hash",
    "normalize_submission_key",
    "submit_workbench_task",
]
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_submission_service.py -v
```

Expected: 11 passed。

- [ ] **Step 5: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/services/workbench/submission.py tests/unit/test_workbench_submission_service.py
.venv/bin/mypy src/data_intelligence_hub/services/workbench/submission.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/src/data_intelligence_hub/services/workbench/submission.py \
  apps/api/tests/unit/test_workbench_submission_service.py
git commit -m "feat(workbench): submit one idempotent run per market (C4)"
```

### Task 5: `/api/workbench/tasks` 任务单路由

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/workbench/idempotency.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench/tasks.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/workbench.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py:50-70,180-225`
- Test: `apps/api/tests/unit/test_workbench_idempotency.py`
- Test: `apps/api/tests/integration/test_workbench_task_routes.py`

**Interfaces:**
- Consumes: `WorkbenchTaskCreateRequest`、`WorkbenchTaskUpdateRequest`、`WorkbenchTaskResponse`、`WorkbenchTaskDetailResponse`、`WorkbenchGateResponse`、`load_maternal_category_ids()`、C2 `get_workspace_role()`、`services.workbench.idempotency`。
- Produces:
  - `create_workbench_task(session, *, workspace_id, project_id, created_by_user_id, payload, idempotency_key) -> tuple[WorkbenchTask, bool]`（bool 为 `idempotent_replay`）
  - `update_workbench_task(session, *, workspace_id, task_id, payload) -> WorkbenchTask`
  - `get_workbench_task_detail(session, *, workspace_id, task_id) -> WorkbenchTaskDetailResponse`
  - `list_workbench_task_gates(session, *, workspace_id, task_id) -> list[WorkbenchGateResponse]`

- [ ] **Step 0: 逐符号 impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "create_workbench_task" --direction upstream --repo .
node .gitnexus/run.cjs impact "update_workbench_task" --direction upstream --repo .
node .gitnexus/run.cjs impact "list_workbench_task_gates" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 记录每个符号的调用方、processes 与 `risk`。`UNKNOWN` 必须文本搜索确认；HIGH/CRITICAL 先告警并写缓解。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/integration/test_workbench_task_routes.py`:

```python
"""``/api/workbench/tasks`` 的路由级集成测试。"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import date, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.workbench import WorkbenchTask
from tests.unit.workbench_support import (
    add_workspace_member,
    seed_workbench_scope,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures/maternal_v1.json"
HEADERS = {"Idempotency-Key": "task-create-key-0001"}


def _task_payload() -> dict[str, object]:
    today = date.today()
    return {
        "brand": "Momcozy",
        "category": "breast_pump",
        "competitors": ["Medela"],
        "package_type": "standard",
        "primary_market": "US",
        "comparison_markets": ["DE"],
        "locale_by_market": {"US": "en", "DE": "de"},
        "window": {
            "start": (today - timedelta(days=90)).isoformat(),
            "end": today.isoformat(),
        },
        "decision_question": "Fit 与支撑哪个是主要摩擦？",
        "does_not_answer": ["不推断销量与市场份额"],
        "seed_products": ["https://example.com/1", "https://example.com/2", "ID-3"],
        "target_price_band": {
            "currency": "USD",
            "min_amount": "10",
            "max_amount": "30",
        },
        "max_cost_usd": "120.50",
        "max_pages": 10,
        "max_records": 500,
        "task_type": "T1",
    }


@pytest_asyncio.fixture()
async def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    taxonomy = tmp_path / "maternal_v1.json"
    taxonomy.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("WORKBENCH_TAXONOMY_PATH", str(taxonomy))
    monkeypatch.setenv("WORKBENCH_TASKS_ENABLED", "true")
    get_settings.cache_clear()

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        value.headers.update(HEADERS)
        value.session_factory = factory  # type: ignore[attr-defined]
        yield value
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    await engine.dispose()


async def _seed(client: AsyncClient, *, suffix: str = "route"):
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        return await seed_workbench_scope(session, suffix=suffix)


def _auth(client: AsyncClient, user_id: uuid.UUID) -> None:
    client.cookies.set("access_token", create_access_token(user_id))


@pytest.mark.asyncio
async def test_workbench_switch_off_returns_503(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed(client, suffix="switch-off")
    _auth(client, seed.user_id)
    monkeypatch.setenv("WORKBENCH_TASKS_ENABLED", "false")
    get_settings.cache_clear()

    response = await client.get(
        f"/api/workbench/tasks?project_id={seed.project_id}"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "workbench_disabled"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_list_and_detail(client: AsyncClient) -> None:
    seed = await _seed(client)
    _auth(client, seed.user_id)

    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["package_type"] == "standard"
    assert body["primary_market"] == "US"
    assert body["comparison_markets"] == ["DE"]
    assert body["markets"] == ["US", "DE"]
    assert body["seed_products"] == [
        "https://example.com/1",
        "https://example.com/2",
        "ID-3",
    ]
    assert body["target_price_band"]["currency"] == "USD"
    assert float(body["target_price_band"]["min_amount"]) == 10.0
    assert float(body["target_price_band"]["max_amount"]) == 30.0
    assert float(body["max_cost_usd"]) == 120.5
    assert body["category"] == "breast_pump"
    task_id = body["id"]

    listing = await client.get(
        f"/api/workbench/tasks?project_id={seed.project_id}"
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [task_id]

    detail = await client.get(f"/api/workbench/tasks/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["task"]["id"] == task_id
    assert detail.json()["workflow_versions"] == []


@pytest.mark.asyncio
async def test_missing_slot_is_422_without_row(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="missing-slot")
    _auth(client, seed.user_id)
    payload = _task_payload()
    payload.pop("decision_question")

    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=payload,
    )
    assert response.status_code == 422
    assert "required_slot_missing" in response.text

    listing = await client.get(
        f"/api/workbench/tasks?project_id={seed.project_id}"
    )
    assert listing.json()["items"] == []


@pytest.mark.asyncio
async def test_unknown_category_and_non_formal_market_are_422(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, suffix="bad-slots")
    _auth(client, seed.user_id)

    unknown_category = _task_payload()
    unknown_category["category"] = "not_in_taxonomy"
    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=unknown_category,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "category_unknown"

    bad_market = _task_payload()
    bad_market["primary_market"] = "JP"
    bad_market["comparison_markets"] = []
    bad_market["locale_by_market"] = {"JP": "ja"}
    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=bad_market,
    )
    assert response.status_code == 422
    assert "market_not_formal" in response.text


@pytest.mark.asyncio
async def test_quick_and_standard_comparison_limits_are_422(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, suffix="limits")
    _auth(client, seed.user_id)

    quick = _task_payload()
    quick["package_type"] = "quick"
    quick["comparison_markets"] = ["DE", "FR"]
    quick["locale_by_market"] = {"US": "en", "DE": "de", "FR": "fr"}
    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=quick,
    )
    assert response.status_code == 422
    assert "comparison_markets_exceeded" in response.text

    standard = _task_payload()
    standard["package_type"] = "standard"
    standard["comparison_markets"] = ["DE", "FR", "IT", "ES"]
    standard["locale_by_market"] = {
        "US": "en",
        "DE": "de",
        "FR": "fr",
        "IT": "it",
        "ES": "es",
    }
    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=standard,
    )
    assert response.status_code == 422
    assert "comparison_markets_exceeded" in response.text


@pytest.mark.asyncio
async def test_create_replays_same_key_and_payload(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="replay")
    _auth(client, seed.user_id)
    headers = {"Idempotency-Key": "task-replay-key-0001"}

    first = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
        headers=headers,
    )
    second = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
        headers=headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.headers["Idempotent-Replay"] == "true"

    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(WorkbenchTask))
    assert count == 1


@pytest.mark.asyncio
async def test_create_same_key_changed_payload_is_conflict(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="idem-conflict")
    _auth(client, seed.user_id)
    headers = {"Idempotency-Key": "task-conflict-key-0001"}
    first = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
        headers=headers,
    )
    assert first.status_code == 201, first.text

    changed = _task_payload()
    changed["brand"] = "Momcozy Pro"
    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=changed,
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_create_requires_idempotency_key(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="idem-missing")
    _auth(client, seed.user_id)

    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
        headers={"Idempotency-Key": ""},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_request"


@pytest.mark.asyncio
async def test_same_key_in_another_workspace_creates_separate_task(
    client: AsyncClient,
) -> None:
    first_scope = await _seed(client, suffix="idem-ws-a")
    second_scope = await _seed(client, suffix="idem-ws-b")
    headers = {"Idempotency-Key": "task-shared-key-0001"}

    _auth(client, first_scope.user_id)
    first = await client.post(
        f"/api/workbench/tasks?project_id={first_scope.project_id}",
        json=_task_payload(),
        headers=headers,
    )
    assert first.status_code == 201, first.text

    _auth(client, second_scope.user_id)
    second = await client.post(
        f"/api/workbench/tasks?project_id={second_scope.project_id}",
        json=_task_payload(),
        headers=headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] != first.json()["id"]


@pytest.mark.asyncio
async def test_acceptance_contact_member_role_is_rejected(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, suffix="acceptance-member")
    _auth(client, seed.user_id)
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        member_id = await add_workspace_member(session, seed, role="member")
    payload = _task_payload()
    payload["acceptance_contact_id"] = str(member_id)

    response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "acceptance_contact_not_member"


@pytest.mark.asyncio
async def test_acceptance_contact_admin_or_owner_is_accepted(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, suffix="acceptance-admin")
    _auth(client, seed.user_id)
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        admin_id = await add_workspace_member(session, seed, role="admin")

    admin_payload = _task_payload()
    admin_payload["acceptance_contact_id"] = str(admin_id)
    admin_response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=admin_payload,
        headers={"Idempotency-Key": "task-admin-contact-0001"},
    )
    assert admin_response.status_code == 201, admin_response.text
    assert admin_response.json()["acceptance_contact_id"] == str(admin_id)

    owner_payload = _task_payload()
    owner_payload["acceptance_contact_id"] = str(seed.user_id)
    owner_response = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=owner_payload,
        headers={"Idempotency-Key": "task-owner-contact-0001"},
    )
    assert owner_response.status_code == 201, owner_response.text


@pytest.mark.asyncio
async def test_patch_acceptance_contact_member_role_is_422(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, suffix="acceptance-patch")
    _auth(client, seed.user_id)
    created = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
        headers={"Idempotency-Key": "task-member-patch-0001"},
    )
    task_id = created.json()["id"]
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        member_id = await add_workspace_member(session, seed, role="member")

    response = await client.patch(
        f"/api/workbench/tasks/{task_id}",
        json={"acceptance_contact_id": str(member_id)},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "acceptance_contact_not_member"


@pytest.mark.asyncio
async def test_patch_draft_and_lock_after_run(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="patch")
    _auth(client, seed.user_id)
    created = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
    )
    task_id = created.json()["id"]

    patched = await client.patch(
        f"/api/workbench/tasks/{task_id}",
        json={"brand": "Momcozy Pro"},
    )
    assert patched.status_code == 200
    assert patched.json()["brand"] == "Momcozy Pro"

    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        from data_intelligence_hub.repositories.runs import create_run

        await create_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_version_id=seed.version_id,
            market_code="US",
            idempotency_key_hash="c" * 64,
        )
        await session.commit()

    locked = await client.patch(
        f"/api/workbench/tasks/{seed.task_id}",
        json={"brand": "Blocked"},
    )
    assert locked.status_code == 409
    assert locked.json()["detail"] == "task_locked"


@pytest.mark.asyncio
async def test_patch_package_and_market_fields_are_saved(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="patch-markets")
    _auth(client, seed.user_id)
    created = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
    )
    task_id = created.json()["id"]

    response = await client.patch(
        f"/api/workbench/tasks/{task_id}",
        json={
            "package_type": "quick",
            "primary_market": "DE",
            "comparison_markets": ["FR"],
            "locale_by_market": {"DE": "de", "FR": "fr"},
            "max_pages": 5,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["package_type"] == "quick"
    assert body["primary_market"] == "DE"
    assert body["comparison_markets"] == ["FR"]
    assert body["markets"] == ["DE", "FR"]
    assert body["max_pages"] == 5


@pytest.mark.asyncio
async def test_patch_quick_with_two_comparisons_is_422(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="patch-limit")
    _auth(client, seed.user_id)
    created = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
    )
    task_id = created.json()["id"]

    response = await client.patch(
        f"/api/workbench/tasks/{task_id}",
        json={
            "package_type": "quick",
            "primary_market": "US",
            "comparison_markets": ["DE", "FR"],
            "locale_by_market": {"US": "en", "DE": "de", "FR": "fr"},
        },
    )
    assert response.status_code == 422
    assert "comparison_markets_exceeded" in response.text


@pytest.mark.asyncio
async def test_cross_workspace_and_missing_cookie(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="tenant")
    other = await _seed(client, suffix="other")

    no_cookie = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
    )
    assert no_cookie.status_code == 401

    _auth(client, seed.user_id)
    created = await client.post(
        f"/api/workbench/tasks?project_id={seed.project_id}",
        json=_task_payload(),
    )
    task_id = created.json()["id"]

    _auth(client, other.user_id)
    foreign = await client.get(f"/api/workbench/tasks/{task_id}")
    assert foreign.status_code == 404
```

- [ ] **Step 1A: 写幂等摘要单元测试**

Create `apps/api/tests/unit/test_workbench_idempotency.py`:

```python
"""任务单创建幂等摘要与请求指纹。"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.schemas.workbench import (
    TargetPriceBand,
    WorkbenchTaskCreateRequest,
    WorkbenchWindow,
)
from data_intelligence_hub.services.workbench.errors import (
    WorkbenchValidationError,
)
from data_intelligence_hub.services.workbench.idempotency import (
    canonical_target_price_band,
    hash_create_idempotency_key,
    normalize_create_idempotency_key,
    request_fingerprint,
    row_fingerprint,
)

WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
CONTACT_ID = uuid.uuid4()


def _payload(**overrides: object) -> WorkbenchTaskCreateRequest:
    payload: dict[str, object] = {
        "brand": "Momcozy",
        "category": "breast_pump",
        "competitors": ["Medela"],
        "package_type": "standard",
        "primary_market": "US",
        "comparison_markets": ["DE"],
        "locale_by_market": {"US": "en", "DE": "de"},
        "window": {
            "start": "2026-07-01",
            "end": "2026-09-30",
        },
        "decision_question": "Fit 与支撑哪个是主要摩擦？",
        "does_not_answer": ["不推断销量"],
        "seed_products": ["https://example.com/1", "https://example.com/2", "ID-3"],
        "target_price_band": {
            "currency": "USD",
            "min_amount": "10",
            "max_amount": "30",
        },
        "max_cost_usd": "120.50",
        "max_pages": 10,
        "max_records": 500,
        "task_type": "T1",
        "task_type_confidence": 0.9,
    }
    payload.update(overrides)
    return WorkbenchTaskCreateRequest.model_validate(payload)


def _row(payload: WorkbenchTaskCreateRequest) -> WorkbenchTask:
    return WorkbenchTask(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        owner_id=USER_ID,
        brand=payload.brand,
        category=payload.category,
        competitors=list(payload.competitors),
        package_type=payload.package_type,
        primary_market=payload.primary_market,
        comparison_markets=list(payload.comparison_markets),
        acceptance_contact_id=CONTACT_ID,
        max_cost_usd=Decimal("120.500000"),
        max_pages=10,
        max_records=500,
        seed_products=list(payload.seed_products),
        target_price_band=canonical_target_price_band(payload.target_price_band),
        idempotency_key_hash=hash_create_idempotency_key("create-key-0001"),
        markets=list(payload.markets),
        locale_by_market=dict(payload.locale_by_market),
        window_start=date(2026, 7, 1),
        window_end=date(2026, 9, 30),
        decision_question=payload.decision_question,
        does_not_answer=list(payload.does_not_answer),
        task_type=payload.task_type,
        task_type_confidence=Decimal("0.900"),
        status="draft",
    )


def test_create_key_is_normalized_and_hashed_stably() -> None:
    assert normalize_create_idempotency_key("  create-key-0001  ") == "create-key-0001"
    first = hash_create_idempotency_key("create-key-0001")
    second = hash_create_idempotency_key("create-key-0001")
    assert first == second
    assert len(first) == 64
    assert first != hash_create_idempotency_key("create-key-0002")
    with pytest.raises(WorkbenchValidationError):
        normalize_create_idempotency_key("   ")
    with pytest.raises(WorkbenchValidationError):
        normalize_create_idempotency_key("x" * 201)


def test_request_and_row_fingerprints_match_after_resolution() -> None:
    payload = _payload()
    request_digest = request_fingerprint(
        payload,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        owner_id=USER_ID,
        acceptance_contact_id=CONTACT_ID,
    )
    assert row_fingerprint(_row(payload)) == request_digest


def test_changed_payload_changes_fingerprint() -> None:
    payload = _payload()
    first = request_fingerprint(
        payload,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        owner_id=USER_ID,
        acceptance_contact_id=CONTACT_ID,
    )
    second = request_fingerprint(
        _payload(brand="Momcozy Pro"),
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        created_by_user_id=USER_ID,
        owner_id=USER_ID,
        acceptance_contact_id=CONTACT_ID,
    )
    assert first != second


def test_canonical_band_keeps_currency_and_decimal_text() -> None:
    band = TargetPriceBand(
        currency="EUR",
        min_amount=Decimal("10"),
        max_amount=Decimal("30"),
    )
    assert canonical_target_price_band(band) == {
        "currency": "EUR",
        "min_amount": "10.000000",
        "max_amount": "30.000000",
    }
    assert canonical_target_price_band(None) is None


def test_price_band_window_is_part_of_request_shape() -> None:
    payload = _payload(window=WorkbenchWindow(start=date(2026, 7, 1), end=date(2026, 9, 30)))
    assert payload.window.end == date(2026, 9, 30)
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_idempotency.py tests/integration/test_workbench_task_routes.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `services.workbench.idempotency`；路由未挂载时集成测试返回 404。

- [ ] **Step 3: 写幂等摘要**

Create `apps/api/src/data_intelligence_hub/services/workbench/idempotency.py`:

```python
"""任务单创建幂等摘要与请求指纹。

只使用规范化字段。`idempotency_key_hash` 用于工作区级唯一查找；
请求指纹从请求与已持久化行重建，二者必须逐位相同。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.schemas.workbench import (
    TargetPriceBand,
    WorkbenchTaskCreateRequest,
)
from data_intelligence_hub.services.workbench.errors import WorkbenchValidationError

_KEY_PREFIX = "workbench-task-create.v1"
_FINGERPRINT_VERSION = "workbench-task-create-fingerprint.v1"
_COST_QUANTUM = Decimal("0.000001")
_CONFIDENCE_QUANTUM = Decimal("0.001")


def normalize_create_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not 1 <= len(normalized) <= 200:
        raise WorkbenchValidationError("invalid_request")
    return normalized


def hash_create_idempotency_key(value: str) -> str:
    material = f"{_KEY_PREFIX}:{normalize_create_idempotency_key(value)}".encode(
        "utf-8"
    )
    return hashlib.sha256(material).hexdigest()


def _decimal_text(value: object, quantum: Decimal) -> str | None:
    if value is None:
        return None
    amount = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return format(amount, "f")


def canonical_target_price_band(
    value: TargetPriceBand | Mapping[str, object] | None,
) -> dict[str, object] | None:
    """规范化已知金额键，保留所有未命名的键。"""
    if value is None:
        return None
    if isinstance(value, TargetPriceBand):
        raw: Mapping[str, object] = value.model_dump(mode="json")
    else:
        raw = value
    canonical: dict[str, object] = {}
    for key, item in raw.items():
        if key in ("min_amount", "max_amount"):
            canonical[key] = _decimal_text(item, _COST_QUANTUM)
        elif key == "currency":
            canonical[key] = None if item is None else str(item)
        else:
            canonical[key] = item
    return canonical


def _fingerprint(values: Mapping[str, object]) -> str:
    canonical = json.dumps(
        {"version": _FINGERPRINT_VERSION, **values},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def request_fingerprint(
    payload: WorkbenchTaskCreateRequest,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    owner_id: uuid.UUID,
    acceptance_contact_id: uuid.UUID,
) -> str:
    return _fingerprint(
        {
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "created_by_user_id": str(created_by_user_id),
            "owner_id": str(owner_id),
            "acceptance_contact_id": str(acceptance_contact_id),
            "brand": payload.brand,
            "category": payload.category,
            "competitors": list(payload.competitors),
            "package_type": payload.package_type,
            "primary_market": payload.primary_market,
            "comparison_markets": list(payload.comparison_markets),
            "locale_by_market": dict(payload.locale_by_market),
            "window_start": payload.window.start.isoformat(),
            "window_end": payload.window.end.isoformat(),
            "decision_question": payload.decision_question,
            "does_not_answer": list(payload.does_not_answer),
            "seed_products": list(payload.seed_products),
            "target_price_band": canonical_target_price_band(
                payload.target_price_band
            ),
            "max_cost_usd": _decimal_text(payload.max_cost_usd, _COST_QUANTUM),
            "max_pages": payload.max_pages,
            "max_records": payload.max_records,
            "task_type": payload.task_type,
            "task_type_confidence": _decimal_text(
                payload.task_type_confidence,
                _CONFIDENCE_QUANTUM,
            ),
        }
    )


def row_fingerprint(task: WorkbenchTask) -> str:
    return _fingerprint(
        {
            "workspace_id": str(task.workspace_id),
            "project_id": str(task.project_id),
            "created_by_user_id": str(task.created_by_user_id),
            "owner_id": str(task.owner_id),
            "acceptance_contact_id": (
                None
                if task.acceptance_contact_id is None
                else str(task.acceptance_contact_id)
            ),
            "brand": task.brand,
            "category": task.category,
            "competitors": list(task.competitors),
            "package_type": task.package_type,
            "primary_market": task.primary_market,
            "comparison_markets": list(task.comparison_markets),
            "locale_by_market": dict(task.locale_by_market),
            "window_start": task.window_start.isoformat(),
            "window_end": task.window_end.isoformat(),
            "decision_question": task.decision_question,
            "does_not_answer": list(task.does_not_answer),
            "seed_products": list(task.seed_products),
            "target_price_band": canonical_target_price_band(
                task.target_price_band
            ),
            "max_cost_usd": _decimal_text(task.max_cost_usd, _COST_QUANTUM),
            "max_pages": task.max_pages,
            "max_records": task.max_records,
            "task_type": task.task_type,
            "task_type_confidence": _decimal_text(
                task.task_type_confidence,
                _CONFIDENCE_QUANTUM,
            ),
        }
    )


__all__ = [
    "canonical_target_price_band",
    "hash_create_idempotency_key",
    "normalize_create_idempotency_key",
    "request_fingerprint",
    "row_fingerprint",
]
```

- [ ] **Step 4: 写任务单服务**

Create `apps/api/src/data_intelligence_hub/services/workbench/tasks.py`:

```python
"""任务单创建、更新与读取。

七槽位的静态规则在 schema 层。本层补五件事：

1. 项目存在且 active。
2. owner 是工作区成员。
3. 验收联系人是 owner 或 admin。
4. category 在冻结 taxonomy 内。
5. 创建幂等：同一工作区同一键同一摘要重放已有任务，摘要变化返回冲突。
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.repositories.authorizations import (
    list_authorizations_for_versions,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workbench_tasks import (
    add_workbench_task,
    get_workbench_task,
    get_workbench_task_by_idempotency_hash,
    get_workspace_member,
    has_runs_for_task,
    list_runs_for_task,
    list_versions_for_task,
    update_workbench_task_fields,
)
from data_intelligence_hub.repositories.workspaces import get_workspace_role
from data_intelligence_hub.schemas.run import RunResponse
from data_intelligence_hub.schemas.workbench import (
    WorkbenchGateResponse,
    WorkbenchGapResponse,
    WorkbenchTaskCreateRequest,
    WorkbenchTaskDetailResponse,
    WorkbenchTaskResponse,
    WorkbenchTaskUpdateRequest,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowVersionSummaryResponse,
)
from data_intelligence_hub.services.workbench.errors import (
    IdempotencyKeyConflictError,
    WorkbenchAcceptanceContactNotMemberError,
    WorkbenchCategoryUnknownError,
    WorkbenchOwnerNotMemberError,
    WorkbenchProjectNotActiveError,
    WorkbenchProjectNotFoundError,
    WorkbenchTaskLockedError,
    WorkbenchTaskNotFoundError,
)
from data_intelligence_hub.services.workbench.idempotency import (
    canonical_target_price_band,
    hash_create_idempotency_key,
    request_fingerprint,
    row_fingerprint,
)
from data_intelligence_hub.services.workbench.taxonomy import (
    load_maternal_category_ids,
)


async def _require_active_project(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    project = await get_project(session, workspace_id, project_id)
    if project is None:
        raise WorkbenchProjectNotFoundError()
    if project.status != "active":
        raise WorkbenchProjectNotActiveError()


async def _require_owner_member(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> None:
    member = await get_workspace_member(
        session,
        workspace_id=workspace_id,
        user_id=owner_id,
    )
    if member is None:
        raise WorkbenchOwnerNotMemberError()


async def _require_acceptance_contact_privileged(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> None:
    # 设计 §4.1：验收联系人只能是 owner 或 admin，不能是普通 member。
    role = await get_workspace_role(session, workspace_id, contact_id)
    if role not in ("owner", "admin"):
        raise WorkbenchAcceptanceContactNotMemberError()


def _require_known_category(category: str) -> None:
    if category not in load_maternal_category_ids():
        raise WorkbenchCategoryUnknownError()


async def create_workbench_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    payload: WorkbenchTaskCreateRequest,
    idempotency_key: str,
) -> tuple[WorkbenchTask, bool]:
    """创建任务单；返回 ``(task, idempotent_replay)``。

    同一工作区同一键同一摘要返回已有行；摘要变化抛
    ``IdempotencyKeyConflictError``。唯一索引兜住并发竞态。
    """
    key_hash = hash_create_idempotency_key(idempotency_key)
    owner_id = payload.owner_id or created_by_user_id
    acceptance_contact_id = payload.acceptance_contact_id or owner_id
    requested_fingerprint = request_fingerprint(
        payload,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=created_by_user_id,
        owner_id=owner_id,
        acceptance_contact_id=acceptance_contact_id,
    )

    existing = await get_workbench_task_by_idempotency_hash(
        session,
        workspace_id=workspace_id,
        idempotency_key_hash=key_hash,
    )
    if existing is not None:
        if row_fingerprint(existing) != requested_fingerprint:
            raise IdempotencyKeyConflictError()
        return existing, True

    await _require_active_project(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    await _require_owner_member(
        session,
        workspace_id=workspace_id,
        owner_id=owner_id,
    )
    await _require_acceptance_contact_privileged(
        session,
        workspace_id=workspace_id,
        contact_id=acceptance_contact_id,
    )
    _require_known_category(payload.category)

    task = WorkbenchTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=created_by_user_id,
        owner_id=owner_id,
        brand=payload.brand,
        category=payload.category,
        competitors=list(payload.competitors),
        package_type=payload.package_type,
        primary_market=payload.primary_market,
        comparison_markets=list(payload.comparison_markets),
        acceptance_contact_id=acceptance_contact_id,
        max_cost_usd=payload.max_cost_usd,
        max_pages=payload.max_pages,
        max_records=payload.max_records,
        seed_products=list(payload.seed_products),
        target_price_band=canonical_target_price_band(payload.target_price_band),
        idempotency_key_hash=key_hash,
        markets=list(payload.markets),
        locale_by_market=dict(payload.locale_by_market),
        window_start=payload.window.start,
        window_end=payload.window.end,
        decision_question=payload.decision_question,
        does_not_answer=list(payload.does_not_answer),
        task_type=payload.task_type,
        task_type_confidence=(
            Decimal(str(payload.task_type_confidence))
            if payload.task_type_confidence is not None
            else None
        ),
        status="draft",
    )
    try:
        await add_workbench_task(session, task)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raced = await get_workbench_task_by_idempotency_hash(
            session,
            workspace_id=workspace_id,
            idempotency_key_hash=key_hash,
        )
        if raced is None:
            raise
        if row_fingerprint(raced) != requested_fingerprint:
            raise IdempotencyKeyConflictError()
        return raced, True
    await session.refresh(task)
    return task, False


def _update_values(payload: WorkbenchTaskUpdateRequest) -> dict[str, object]:
    values: dict[str, object] = {}
    scalar_fields = (
        "brand",
        "category",
        "competitors",
        "package_type",
        "primary_market",
        "comparison_markets",
        "locale_by_market",
        "decision_question",
        "does_not_answer",
        "seed_products",
        "target_price_band",
        "acceptance_contact_id",
        "max_cost_usd",
        "max_pages",
        "max_records",
        "owner_id",
        "task_type",
        "task_type_confidence",
    )
    for field in scalar_fields:
        if field not in payload.model_fields_set:
            continue
        value = getattr(payload, field)
        if field == "comparison_markets" and value is not None:
            value = list(value)
        if field == "locale_by_market" and value is not None:
            value = dict(value)
        if field == "seed_products" and value is not None:
            value = list(value)
        if field == "target_price_band":
            value = canonical_target_price_band(value)
        if field == "task_type_confidence" and value is not None:
            value = Decimal(str(value))
        if field == "max_cost_usd" and value is not None:
            value = Decimal(str(value))
        values[field] = value
    if {
        "package_type",
        "primary_market",
        "comparison_markets",
    } <= payload.model_fields_set:
        values["markets"] = [
            str(values["primary_market"]),
            *[str(item) for item in values["comparison_markets"] or []],
        ]
    if "window" in payload.model_fields_set and payload.window is not None:
        values["window_start"] = payload.window.start
        values["window_end"] = payload.window.end
    return values


async def update_workbench_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: WorkbenchTaskUpdateRequest,
) -> WorkbenchTask:
    task = await get_workbench_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    if task is None:
        raise WorkbenchTaskNotFoundError()
    if await has_runs_for_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    ):
        raise WorkbenchTaskLockedError()

    values = _update_values(payload)
    if values.get("category") is not None:
        _require_known_category(str(values["category"]))
    if values.get("owner_id") is not None:
        await _require_owner_member(
            session,
            workspace_id=workspace_id,
            owner_id=uuid.UUID(str(values["owner_id"])),
        )
    if values.get("acceptance_contact_id") is not None:
        await _require_acceptance_contact_privileged(
            session,
            workspace_id=workspace_id,
            contact_id=uuid.UUID(str(values["acceptance_contact_id"])),
        )

    updated = await update_workbench_task_fields(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
        values=values,
    )
    if updated is None:
        raise WorkbenchTaskNotFoundError()
    await session.commit()
    await session.refresh(updated)
    return updated


def _gate_response(authorization: Authorization) -> WorkbenchGateResponse:
    scope_dict = authorization.scope if isinstance(authorization.scope, dict) else {}
    gap_payload = scope_dict.get("gap")
    gap = (
        WorkbenchGapResponse.model_validate(gap_payload)
        if isinstance(gap_payload, dict)
        else None
    )
    return WorkbenchGateResponse(
        authorization_id=authorization.id,
        gate_id=authorization.gate_id,
        gate_status=authorization.gate_status,
        market_code=scope_dict.get("market_code"),
        reason_code=gap.reason_code if gap is not None else None,
        gap=gap,
    )


async def list_workbench_task_gates(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> list[WorkbenchGateResponse]:
    task = await get_workbench_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    if task is None:
        raise WorkbenchTaskNotFoundError()
    versions = await list_versions_for_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    authorizations = await list_authorizations_for_versions(
        session,
        workspace_id=workspace_id,
        version_ids=[version.id for version in versions],
    )
    return [_gate_response(item) for item in authorizations]


async def get_workbench_task_detail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> WorkbenchTaskDetailResponse:
    task = await get_workbench_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    if task is None:
        raise WorkbenchTaskNotFoundError()
    versions = await list_versions_for_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    runs = await list_runs_for_task(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    gates = await list_workbench_task_gates(
        session,
        workspace_id=workspace_id,
        task_id=task_id,
    )
    return WorkbenchTaskDetailResponse(
        task=WorkbenchTaskResponse.model_validate(task),
        workflow_versions=[
            WorkflowVersionSummaryResponse.model_validate(version)
            for version in versions
        ],
        runs=[RunResponse.model_validate(run) for run in runs],
        gates=gates,
    )


__all__ = [
    "create_workbench_task",
    "get_workbench_task_detail",
    "list_workbench_task_gates",
    "update_workbench_task",
]
```

- [ ] **Step 4: 写路由**

Create `apps/api/src/data_intelligence_hub/api/routes/workbench.py`:

```python
"""``/api/workbench/tasks`` 任务单端点。

所有端点按 ``context.workspace`` 隔离。跨工作区一律 404。
写端点使用 ``get_authenticated_context``，无 cookie 一律 401。
"""

from __future__ import annotations

import uuid
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from data_intelligence_hub.api.deps import (
    AuthContext,
    SessionDep,
    get_authenticated_context,
)
from data_intelligence_hub.schemas.workbench import (
    WorkbenchGateResponse,
    WorkbenchTaskCreateRequest,
    WorkbenchTaskDetailResponse,
    WorkbenchTaskListResponse,
    WorkbenchTaskResponse,
    WorkbenchTaskStatus,
    WorkbenchTaskUpdateRequest,
)
from data_intelligence_hub.services.workbench.errors import WorkbenchError
from data_intelligence_hub.services.workbench.tasks import (
    create_workbench_task,
    get_workbench_task_detail,
    list_workbench_task_gates,
    update_workbench_task,
)
from data_intelligence_hub.services.workbench.taxonomy import (
    TaxonomyUnavailableError,
)
from data_intelligence_hub.repositories.workbench_tasks import list_workbench_tasks

def require_workbench_enabled() -> None:
    # C4 总开关。默认 false；关闭时所有 workbench 路由 503。
    from data_intelligence_hub.core.config import get_settings

    if not get_settings().workbench_tasks_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workbench_disabled",
        )


router = APIRouter(
    tags=["workbench"],
    dependencies=[Depends(require_workbench_enabled)],
)


def _raise_workbench(exc: WorkbenchError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


@router.post(
    "/tasks",
    response_model=WorkbenchTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workbench_task_item(
    payload: WorkbenchTaskCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    project_id: Annotated[uuid.UUID, Query()],
    idempotency_header: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> WorkbenchTaskResponse:
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    if idempotency_header is None or not idempotency_header.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_request",
        )
    try:
        task, replayed = await create_workbench_task(
            session,
            workspace_id=context.workspace.id,
            project_id=project_id,
            created_by_user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_header,
        )
    except WorkbenchError as exc:
        _raise_workbench(exc)
    except TaxonomyUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="taxonomy_unavailable",
        ) from exc
    response.status_code = (
        status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    )
    response.headers["Idempotent-Replay"] = "true" if replayed else "false"
    return WorkbenchTaskResponse.model_validate(task)


@router.get("/tasks", response_model=WorkbenchTaskListResponse)
async def list_workbench_task_items(
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    project_id: Annotated[uuid.UUID, Query()],
    task_status: Annotated[WorkbenchTaskStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkbenchTaskListResponse:
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    items = await list_workbench_tasks(
        session,
        workspace_id=context.workspace.id,
        project_id=project_id,
        status=task_status,
        limit=limit,
        offset=offset,
    )
    return WorkbenchTaskListResponse(
        items=[WorkbenchTaskResponse.model_validate(item) for item in items]
    )


@router.get("/tasks/{task_id}", response_model=WorkbenchTaskDetailResponse)
async def get_workbench_task_item(
    task_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> WorkbenchTaskDetailResponse:
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    try:
        return await get_workbench_task_detail(
            session,
            workspace_id=context.workspace.id,
            task_id=task_id,
        )
    except WorkbenchError as exc:
        _raise_workbench(exc)


@router.patch("/tasks/{task_id}", response_model=WorkbenchTaskResponse)
async def update_workbench_task_item(
    task_id: uuid.UUID,
    payload: WorkbenchTaskUpdateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> WorkbenchTaskResponse:
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    try:
        task = await update_workbench_task(
            session,
            workspace_id=context.workspace.id,
            task_id=task_id,
            payload=payload,
        )
    except WorkbenchError as exc:
        _raise_workbench(exc)
    except TaxonomyUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="taxonomy_unavailable",
        ) from exc
    return WorkbenchTaskResponse.model_validate(task)


@router.get(
    "/tasks/{task_id}/gates",
    response_model=list[WorkbenchGateResponse],
)
async def list_workbench_task_gate_items(
    task_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> list[WorkbenchGateResponse]:
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    try:
        return await list_workbench_task_gates(
            session,
            workspace_id=context.workspace.id,
            task_id=task_id,
        )
    except WorkbenchError as exc:
        _raise_workbench(exc)


__all__ = ["router"]
```

- [ ] **Step 5: 挂载路由**

In `apps/api/src/data_intelligence_hub/main.py`, add the import near `runs_router`:

```python
from data_intelligence_hub.api.routes.workbench import router as workbench_router
```

Add the mount after the runs mount:

```python
    app.include_router(workbench_router, prefix="/api/workbench")
```

- [ ] **Step 6: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_workbench_idempotency.py tests/integration/test_workbench_task_routes.py -v
```

Expected: 21 passed（5 个幂等单元测试 + 16 个路由测试）。

- [ ] **Step 7: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/services/workbench/idempotency.py src/data_intelligence_hub/services/workbench/tasks.py src/data_intelligence_hub/api/routes/workbench.py src/data_intelligence_hub/main.py tests/unit/test_workbench_idempotency.py tests/integration/test_workbench_task_routes.py
.venv/bin/mypy src/data_intelligence_hub/services/workbench/idempotency.py src/data_intelligence_hub/services/workbench/tasks.py src/data_intelligence_hub/api/routes/workbench.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/src/data_intelligence_hub/services/workbench/idempotency.py \
  apps/api/src/data_intelligence_hub/services/workbench/tasks.py \
  apps/api/src/data_intelligence_hub/api/routes/workbench.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/tests/unit/test_workbench_idempotency.py \
  apps/api/tests/integration/test_workbench_task_routes.py
git commit -m "feat(api): add idempotent workbench task creation (C4)"
```

---

### Task 6: `POST /api/runs` 逐市场提交模式

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/run.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/runs.py`
- Test: `apps/api/tests/integration/test_workbench_submission_routes.py`

**Interfaces:**
- Consumes: `submit_workbench_task`、`WorkbenchSubmissionResponse`、`WorkbenchGapResponse`、`RunResponse`。
- Produces: `POST /api/runs` 的 workbench 模式；`RunCreateRequest.workbench_task_id`、`workflow_version_id`；`RunResponse.market_code`。

- [ ] **Step 0: 逐符号 impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs impact "create_run" --direction upstream --repo .
node .gitnexus/run.cjs impact "submit_workbench_task" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 记录每个符号的调用方、processes 与 `risk`。`UNKNOWN` 必须文本搜索确认；HIGH/CRITICAL 先告警并写缓解。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/integration/test_workbench_submission_routes.py`:

```python
"""``POST /api/runs`` workbench 模式的集成测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import date, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.task import TaskRun
from tests.unit.workbench_support import (
    WorkbenchSeed,
    add_linked_version,
    seed_workbench_scope,
)

_KEY = "route-submission-key-0001"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures/maternal_v1.json"


@pytest_asyncio.fixture()
async def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    taxonomy = tmp_path / "maternal_v1.json"
    taxonomy.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("WORKBENCH_TAXONOMY_PATH", str(taxonomy))
    monkeypatch.setenv("WORKBENCH_TASKS_ENABLED", "true")
    get_settings.cache_clear()

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        value.session_factory = factory  # type: ignore[attr-defined]
        yield value
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    await engine.dispose()


async def _seed(client: AsyncClient, *, suffix: str = "submit") -> WorkbenchSeed:
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        return await seed_workbench_scope(
            session,
            suffix=suffix,
            markets=("US", "DE"),
        )


def _auth(client: AsyncClient, user_id: uuid.UUID) -> None:
    client.cookies.set("access_token", create_access_token(user_id))


def _body(seed: WorkbenchSeed) -> dict[str, str]:
    return {
        "project_id": str(seed.project_id),
        "workbench_task_id": str(seed.task_id),
        "workflow_version_id": str(seed.version_id),
    }


@pytest.mark.asyncio
async def test_submission_creates_one_run_per_market(client: AsyncClient) -> None:
    seed = await _seed(client)
    _auth(client, seed.user_id)

    response = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["idempotent_replay"] is False
    assert len(body["run_ids"]) == 2
    assert [run["market_code"] for run in body["runs"]] == ["US", "DE"]
    assert {run["status"] for run in body["runs"]} == {"queued"}
    assert body["gaps"] == []


@pytest.mark.asyncio
async def test_replay_returns_same_ids_and_200(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="replay")
    _auth(client, seed.user_id)
    first = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    second = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert second.json()["run_ids"] == first.json()["run_ids"]


@pytest.mark.asyncio
async def test_same_key_different_version_conflicts(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="conflict")
    _auth(client, seed.user_id)
    await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )

    other = _body(seed)
    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        other["workflow_version_id"] = str(
            await add_linked_version(session, seed)
        )
    response = await client.post(
        "/api/runs",
        json=other,
        headers={"Idempotency-Key": _KEY},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_new_key_same_version_is_rejected(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="duplicate")
    _auth(client, seed.user_id)
    await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    response = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": "route-submission-key-0002"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "workflow_version_already_submitted"


@pytest.mark.asyncio
async def test_blocked_market_keeps_run_queued_and_exposes_gap(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKBENCH_ENABLED_MARKETS", "US")
    get_settings.cache_clear()
    seed = await _seed(client, suffix="blocked")
    _auth(client, seed.user_id)

    response = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert [run["status"] for run in body["runs"]] == ["queued", "queued"]
    assert [gap["market_code"] for gap in body["gaps"]] == ["DE"]

    detail = await client.get(f"/api/workbench/tasks/{seed.task_id}")
    assert detail.status_code == 200
    gates = detail.json()["gates"]
    assert len(gates) == 1
    assert gates[0]["gate_status"] == "blocked"
    assert gates[0]["gap"]["reason_code"] == "market_unsupported"

    for run in detail.json()["runs"]:
        assert run["status"] in {
            "queued",
            "running",
            "completed",
            "failed",
            "cancelled",
        }


@pytest.mark.asyncio
async def test_no_cookie_401_and_cross_workspace_404(client: AsyncClient) -> None:
    seed = await _seed(client, suffix="auth")
    other = await _seed(client, suffix="other")

    no_cookie = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    assert no_cookie.status_code == 401

    _auth(client, other.user_id)
    foreign = await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "task_not_found"


@pytest.mark.asyncio
async def test_submission_writes_no_steps_ledger_or_task_runs(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, suffix="boundaries")
    _auth(client, seed.user_id)
    await client.post(
        "/api/runs",
        json=_body(seed),
        headers={"Idempotency-Key": _KEY},
    )

    factory = client.session_factory  # type: ignore[attr-defined]
    async with factory() as session:
        for model in (RunLedgerEntry, RunStep, TaskRun):
            count = await session.scalar(select(func.count()).select_from(model))
            assert count == 0
        run_count = await session.scalar(select(func.count()).select_from(Run))
        assert run_count == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/integration/test_workbench_submission_routes.py -v
```

Expected: FAIL。`POST /api/runs` 返回 422 `run_binding_required` 或响应没有 `run_ids`。

- [ ] **Step 3: 扩展 run schema**

In `apps/api/src/data_intelligence_hub/schemas/run.py`:

Add `Self` and `model_validator` to the pydantic import:

```python
from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

Replace `RunCreateRequest` fields and add validator:

```python
class RunCreateRequest(BaseModel):
    """创建运行的请求体。

    两种模式：

    - 旧模式：``task_id`` + ``endpoint_type``，创建单个采集运行。
    - workbench 模式：``workbench_task_id`` + ``workflow_version_id``，
      按市场创建多个运行。``Idempotency-Key`` 头必填。
    """

    project_id: uuid.UUID
    task_id: uuid.UUID | None = Field(
        default=None,
        description="旧模式必填：单个采集任务 ID。",
    )
    workbench_task_id: uuid.UUID | None = None
    workflow_version_id: uuid.UUID | None = None
    endpoint_type: str | None = Field(default=None, min_length=1, max_length=80)
    trigger: Literal["manual", "schedule", "api"] = "api"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        workbench_mode = (
            self.workbench_task_id is not None or self.workflow_version_id is not None
        )
        if workbench_mode:
            if self.workbench_task_id is None or self.workflow_version_id is None:
                raise ValueError("run_binding_required")
            if self.task_id is not None or self.endpoint_type is not None:
                raise ValueError("run_binding_conflict")
            return self
        if self.task_id is None or self.endpoint_type is None:
            raise ValueError("run_binding_required")
        return self
```

Add to `RunResponse`:

```python
    market_code: str | None
```

- [ ] **Step 4: 扩展 runs 路由**

In `apps/api/src/data_intelligence_hub/api/routes/runs.py`:

Add imports:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from data_intelligence_hub.schemas.run import (
    RunCreateRequest,
    RunOutcomeResponse,
    RunResponse,
    RunStepResponse,
)
from data_intelligence_hub.schemas.workbench import WorkbenchSubmissionResponse
from data_intelligence_hub.services.workbench.errors import WorkbenchError
from data_intelligence_hub.services.workbench.submission import (
    submit_workbench_task,
)
```

Change the decorator:

```python
@router.post(
    "",
    response_model=RunResponse | WorkbenchSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
```

Change the function signature:

```python
async def create_run(
    body: RunCreateRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
    idempotency_header: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> RunResponse | WorkbenchSubmissionResponse:
```

At the top of the function, branch:

```python
    if body.workbench_task_id is not None:
        from data_intelligence_hub.core.config import get_settings

        if not get_settings().workbench_tasks_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="workbench_disabled",
            )
        assert body.workflow_version_id is not None
        key = idempotency_header or body.idempotency_key
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="idempotency_key_required",
            )
        try:
            result = await submit_workbench_task(
                session,
                workspace_id=context.workspace.id,
                project_id=body.project_id,
                workbench_task_id=body.workbench_task_id,
                workflow_version_id=body.workflow_version_id,
                idempotency_key=key,
            )
        except WorkbenchError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.code,
            ) from exc
        response.status_code = (
            status.HTTP_200_OK
            if result.idempotent_replay
            else status.HTTP_201_CREATED
        )
        return WorkbenchSubmissionResponse(
            workbench_task_id=result.workbench_task_id,
            workflow_version_id=result.workflow_version_id,
            runs=[RunResponse.model_validate(run) for run in result.runs],
            run_ids=[run.id for run in result.runs],
            gaps=list(result.gaps),
            idempotent_replay=result.idempotent_replay,
        )
```

For the legacy path, after the branch add:

```python
    assert body.task_id is not None
    task_id = body.task_id
```

Replace all `body.task_id` references below with `task_id`. The remaining legacy code is unchanged.

workbench 模式只调用 `submit_workbench_task`，因此 run 创建经 C4 `create_run_with_audit` 接缝并写 `run.created`。非 workbench 旧模式的代码保持原样；C6 Task 10 会用同一接缝收敛旧模式并补 `run.created`。C4 不在旧模式新增直接 `runs_repository.create_run` 调用。

- [ ] **Step 5: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/integration/test_workbench_submission_routes.py -v
```

Expected: 7 passed。

- [ ] **Step 6: 回归旧 runs 测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit/test_run_routes.py -v
```

Expected: 全部通过。旧模式响应仍是单个 `RunResponse`。

- [ ] **Step 7: 静态检查并提交**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub/schemas/run.py src/data_intelligence_hub/api/routes/runs.py tests/integration/test_workbench_submission_routes.py
.venv/bin/mypy src/data_intelligence_hub/schemas/run.py src/data_intelligence_hub/api/routes/runs.py
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: `All checks passed!`、`Success: no issues found`、detect-changes 覆盖本任务文件。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/src/data_intelligence_hub/schemas/run.py \
  apps/api/src/data_intelligence_hub/api/routes/runs.py \
  apps/api/tests/integration/test_workbench_submission_routes.py
git commit -m "feat(api): submit workbench runs per market (C4)"
```

### Task 7: C14 交接契约测试与浏览器最小验收清单

**Files:**
- Test: `apps/api/tests/integration/test_workbench_c14_handoff.py`

**Interfaces:**
- Consumes: FastAPI OpenAPI 文档、`WorkbenchSubmissionResponse`、`WorkbenchTaskCreateRequest`。
- Produces: C14 可直接依赖的 OpenAPI 契约断言；浏览器验收清单。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/integration/test_workbench_c14_handoff.py`:

```python
"""C14 交接契约。

C4 不实现 /workbench 页面。C14 只允许依赖这里断言过的字段。
"""

from __future__ import annotations

from data_intelligence_hub.main import app


def _schema(name: str) -> dict[str, object]:
    return app.openapi()["components"]["schemas"][name]


def test_c14_paths_are_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/workbench/tasks" in paths
    assert "post" in paths["/api/workbench/tasks"]
    assert "get" in paths["/api/workbench/tasks"]
    assert "/api/workbench/tasks/{task_id}" in paths
    assert "/api/workbench/tasks/{task_id}/gates" in paths
    assert "/api/runs" in paths


def test_c14_task_form_fields_are_stable() -> None:
    fields = set(_schema("WorkbenchTaskCreateRequest")["properties"])
    assert {
        "brand",
        "category",
        "competitors",
        "package_type",
        "primary_market",
        "comparison_markets",
        "locale_by_market",
        "window",
        "decision_question",
        "does_not_answer",
        "seed_products",
        "target_price_band",
        "acceptance_contact_id",
        "max_cost_usd",
        "max_pages",
        "max_records",
        "task_type",
    } <= fields


def test_c14_run_schema_does_not_persist_market_role_or_package_type() -> None:
    fields = set(_schema("RunResponse")["properties"])
    assert "market_code" in fields
    assert "market_role" not in fields
    assert "package_type" not in fields


def test_c14_submission_response_fields_are_stable() -> None:
    fields = set(_schema("WorkbenchSubmissionResponse")["properties"])
    assert {
        "workbench_task_id",
        "workflow_version_id",
        "runs",
        "run_ids",
        "gaps",
        "idempotent_replay",
    } == fields


def test_c14_run_create_request_has_workbench_binding() -> None:
    fields = set(_schema("RunCreateRequest")["properties"])
    assert {"workbench_task_id", "workflow_version_id", "idempotency_key"} <= fields


def test_c14_create_documents_idempotency_header() -> None:
    parameters = app.openapi()["paths"]["/api/workbench/tasks"]["post"]["parameters"]
    header = next(item for item in parameters if item["name"] == "Idempotency-Key")
    assert header["in"] == "header"


def test_c14_run_response_exposes_market_code() -> None:
    fields = set(_schema("RunResponse")["properties"])
    assert "market_code" in fields
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/integration/test_workbench_c14_handoff.py -v
```

Expected: FAIL，`KeyError: 'WorkbenchSubmissionResponse'` 或字段缺失。

- [ ] **Step 3: 跑测试确认通过**

前六个任务已实现全部字段。若测试仍失败，按失败字段回到对应任务修正，不要在测试里放宽断言。

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/integration/test_workbench_c14_handoff.py -v
```

Expected: 7 passed。

- [ ] **Step 4: 写 C14 浏览器最小验收清单**

C14 交付 `/workbench` 页面时必须执行以下验收。C4 不写前端代码，也不把浏览器验收当作 C4 的退出条件。C14 只读：不修改生产开关、不写 `.env.production`、不签发密钥。需要未启用市场的场景只在 staging 夹具中构造。

**C14 环境预期（只读）：**

- `WORKBENCH_TASKS_ENABLED=true` 由 PG0 发布批次在验收前设置；C14 只读取页面行为，不切换开关。
- `WORKBENCH_ENABLED_MARKETS` 由 PG0 配置；默认 11 个正式市场。C14 不修改该键。
- `WORKBENCH_TAXONOMY_PATH` 可以省略。省略时 API 容器按应用根解析为 `/app/configs/taxonomy/maternal_v1.json`；如果设置，值必须是绝对路径。C14 不得用 cwd 相对路径启动验收进程，也不得修改该键。
- C14 的只读脚本读取 taxonomy 时必须调用 `resolve_workbench_taxonomy_path()`（或直接读 `/app/configs/taxonomy/maternal_v1.json`），不得把 `settings.workbench_taxonomy_path` 当作 cwd 相对路径。
- API 容器必须有只读挂载 `configs/taxonomy:/app/configs/taxonomy:ro`。C14 只用 `docker compose config` 复核，不重建容器。
- C14 不执行迁移、不写数据库、不修改 compose 或 `.env.production`；生产写操作只属于 PG0 发布批次。

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 未登录访问 `/workbench` | 307 或跳转登录页；不出现任务数据 |
| 2 | 登录后打开 `/workbench` | 200；任务列表可见；无控制台错误 |
| 3 | 新建任务，填七个槽位，选择 Quick 或 Standard，并选择主市场与对比市场 | 提交按钮可用；Quick 只能选 1 个对比市场，Standard 最多 3 个；超出时按钮禁用或提交返回 `comparison_markets_exceeded`；验收联系人只能选 owner/admin |
| 4 | 提交创建 | 请求 `POST /api/workbench/tasks?project_id=...`；头 `Idempotency-Key` 存在；响应 201；任务状态 `draft` |
| 5 | 用同一幂等键和同一表单再次提交 | 响应 200；返回同一 `task_id`；页面不新增任务 |
| 6 | 同一幂等键修改任一槽位后提交 | 响应 409 `idempotency_conflict`；页面提示幂等键已用于其他内容 |
| 7 | 通过 workflow planner 生成并批准首个版本 | 计划状态 `approved`；`current_version_id` 指向该版本；`workflow_versions.workbench_task_id` 等于任务 ID |
| 8 | 提交计划版本 | 请求 `POST /api/runs`；头 `Idempotency-Key` 存在；响应 201 |
| 9 | 查看运行列表 | 每个市场一行；`market_code` 可见；状态显示 `queued` |
| 10 | 用同一幂等键再次提交 run | 响应 200；`run_ids` 与第一次完全相同；页面不新增 run |
| 11 | 在 staging 夹具中把一个市场设为未启用后提交 | blocked 市场显示 gap 文案；run 仍显示 `queued`；页面不得显示 `blocked` 作为 run 状态 |
| 12 | 修改已提交任务 | 响应 409 `task_locked`；页面提示任务已锁定 |
| 13 | 跨工作区打开任务 URL | 404；不泄露任务存在性 |

C14 禁止：

- 不得把 `blocked`、`degraded`、`held` 显示为 `runs.status`。
- 不得在前端自行拼接 provider、端点或市场降级链。
- 不得绕过 `POST /api/runs` 直接写 run。
- 不得把 `gaps[]` 当前端错误弹窗；它是交付结果的一部分。
- 不得修改生产功能开关、compose、`.env.production` 或任何生产数据；这些只属于 PG0 发布批次。

- [ ] **Step 5: 提交 C14 契约测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 只包含 `test_workbench_c14_handoff.py`。

Commit:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
git add apps/api/tests/integration/test_workbench_c14_handoff.py
git commit -m "test(workbench): freeze C14 handoff contract (C4)"
```

---

### Task 8: 全量验证与 C14 生产交接

**Files:**
- 无新增文件。

**Interfaces:**
- Consumes: 全部任务（含 Task 3A、Task 3C）的代码与测试。
- Produces: 可复核的测试、迁移、GitNexus 与发布门禁证据。

- [ ] **Step 1: 跑 C4 定向测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest \
  tests/unit/test_workbench_task_models.py \
  tests/unit/test_workbench_schemas.py \
  tests/unit/test_workbench_task_repository.py \
  tests/unit/test_workbench_idempotency.py \
  tests/unit/test_workbench_initial_version.py \
  tests/unit/test_run_creation.py \
  tests/unit/test_workbench_submission_service.py \
  tests/integration/test_workbench_task_routes.py \
  tests/integration/test_workbench_submission_routes.py \
  tests/integration/test_workbench_c14_handoff.py \
  -v
```

Expected: 全部 PASS，0 failed。

- [ ] **Step 2: 跑回归基线**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m pytest tests/integration -q
.venv/bin/python -m pytest tests/unit/test_run_routes.py tests/unit/test_run_models.py tests/unit/test_run_ledger.py tests/unit/test_task_run_idempotency.py -q
```

Expected: 每套 `0 failed`。不引用历史固定条数；只以本次输出为准。

- [ ] **Step 3: 跑静态检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/ruff check src/data_intelligence_hub tests/unit/workbench_support.py \
  tests/unit/test_workbench_task_models.py \
  tests/unit/test_workbench_schemas.py \
  tests/unit/test_workbench_task_repository.py \
  tests/unit/test_workbench_idempotency.py \
  tests/unit/test_workbench_initial_version.py \
  tests/unit/test_run_creation.py \
  tests/unit/test_workbench_submission_service.py \
  tests/integration/test_workbench_task_routes.py \
  tests/integration/test_workbench_submission_routes.py \
  tests/integration/test_workbench_c14_handoff.py
.venv/bin/mypy src/data_intelligence_hub/models/workbench.py \
  src/data_intelligence_hub/schemas/workbench.py \
  src/data_intelligence_hub/services/run_creation.py \
  src/data_intelligence_hub/services/workbench \
  src/data_intelligence_hub/repositories/workbench_tasks.py \
  src/data_intelligence_hub/api/routes/workbench.py
```

Expected: `All checks passed!`、`Success: no issues found`。

- [ ] **Step 4: 验证迁移单 head 与 060 内容**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4/apps/api
.venv/bin/alembic heads
grep -n "revision: str\|down_revision" alembic/versions/202610220060_workbench_task_submission.py
grep -n "uq_runs_workspace_idempotency\|uq_task_runs_task_idempotency" alembic/versions/202610220060_workbench_task_submission.py
```

Expected:

```text
202610220060 (head)
revision: str = "202610220060"
down_revision: str | None = "202610220059"
```

并且 060 中没有 `drop_index` 旧幂等索引。

- [ ] **Step 5: GitNexus 最终变更检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
node .gitnexus/run.cjs detect-changes --scope all --repo .
node .gitnexus/run.cjs impact "Run" --direction upstream --repo .
node .gitnexus/run.cjs impact "WorkflowVersion" --direction upstream --repo .
```

Expected:
- detect-changes 覆盖全部 C4 文件；`partial` 与 `truncated` 均不是 true。
- `Run` 与 `WorkflowVersion` 的风险不高于计划基线 MEDIUM；若升高到 HIGH/CRITICAL，必须在合并说明里列出新增调用方与原因。`UNKNOWN` 必须用文本搜索确认。

- [ ] **Step 6: 检查没有越界改动**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
C4_BASE=$(cat /tmp/c4-base-sha)
git diff --name-only "$C4_BASE"..HEAD
git diff --stat "$C4_BASE"..HEAD
```

Expected: 只包含 File Structure 列出的文件；不得出现：

```text
apps/web/**
apps/api/src/data_intelligence_hub/models/run_ledger.py
apps/api/src/data_intelligence_hub/services/run_ledger.py
apps/api/src/data_intelligence_hub/services/run_executor.py
apps/api/src/data_intelligence_hub/collectors/**
```

若出现以上路径，停止并回退该改动。C4 不碰预算账本、多步骤执行、collector 与前端。

再扫描 run 创建与审计落点：

```bash
cd /Users/lute/Project/data_scrapy-gov-c4
rg -n "runs_repository\.create_run\(" apps/api/src/data_intelligence_hub/services/workbench
rg -n 'action="run.created"' apps/api/src/data_intelligence_hub/services/workbench
rg -n "runs_repository\.create_run\(|append_audit_event\(" \
  apps/api/src/data_intelligence_hub/services/run_creation.py
```

Expected: 前两条零命中；第三条同时命中仓储调用与 `append_audit_event`。run 创建只在 C4 接缝；C4 提交服务不直接调用仓储，也不直接写 `run.created`。旧 `POST /api/runs` 非 workbench 路径仍保留既有直连，由 C6 Task 10 用同一接缝收敛。

- [ ] **Step 7: 生产 A/B 门禁（PG0 发布批次执行；C4/C14 不执行写操作）**

C4 合并后，发布必须与 C5/C6 同批，并且只由 PG0 发布批次执行。以下命令是交给 PG0 的交接清单；C4 与 C14 都不执行任何写操作（ssh 写命令、git fetch、alembic upgrade、docker compose up/run/restart、备份或 `.env.production` 修改），也不写生产记录文件。C14 只做只读 health/canary、`docker compose config`/`exec` 预检与浏览器验收。

**PG0 发布批次必须新增的 PostgreSQL 16 证据（C4/C14 不执行）：**

1. 空库迁移循环：在 PostgreSQL 15 空库执行 `alembic upgrade 202610220060`，再 `alembic downgrade 202610220059`，再 `alembic upgrade 202610220060`；三次退出码为 0，`alembic heads` 单行。
2. 双 key 并发 run：两个独立会话/连接同时用不同 `Idempotency-Key` 提交同一 `(workflow_version_id, market_code)`；只有一个成功，另一个收到 `workflow_version_already_submitted` 或 409，数据库只有一行 run。
3. 任务创建幂等：同一工作区同一 `Idempotency-Key` 与同一请求并发创建两次，只落一行 `workbench_tasks`；同键不同摘要返回 409 `idempotency_conflict`。
4. blocked 授权：C4 创建的 `G-Plan/blocked` 行在 C5 迁移后有 `run_id`，且该 run 没有 `G-Cost/pass`；PG0 用 SQL 断言。
5. 回滚：先关 `WORKBENCH_TASKS_ENABLED`，再回退镜像；060 downgrade 只在无新数据时执行。

**开关顺序与 C14 环境预期：** PG0 批次首次发布保持 `WORKBENCH_TASKS_ENABLED=false`，完成迁移、备份与健康检查后，在 `.env.production` 显式设为 `true` 并重启 api。`WORKBENCH_ENABLED_MARKETS` 可选，用 JSON 数组；默认 11 个正式市场。`WORKBENCH_TAXONOMY_PATH` 可以省略；省略时 API 容器按应用根解析为 `/app/configs/taxonomy/maternal_v1.json`。如果 PG0 显式设置该键，值必须是绝对路径；不得写相对路径，也不得依赖容器 cwd。compose 的 `api.environment` 必须已声明上述三个键，`api.volumes` 必须有 `../../../configs/taxonomy:/app/configs/taxonomy:ro`。C14 只在开关翻起后做只读验收，不切换开关，不修改 `.env.production`。C5 的 blocked G-Plan 绑定与 C6 的 blocked 检查必须先验收。

**C14 只读环境预检（不写文件、不重启）：**

```bash
cd /opt/data-achieve-scrapy/app
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml config \
  | rg 'WORKBENCH_TAXONOMY_PATH|WORKBENCH_TASKS_ENABLED|WORKBENCH_ENABLED_MARKETS|configs/taxonomy:ro'
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml exec -T api python -c \
  "from data_intelligence_hub.services.workbench.taxonomy import resolve_workbench_taxonomy_path; p = resolve_workbench_taxonomy_path(); print(p); raise SystemExit(0 if p.is_file() else 1)"
```

Expected: taxonomy path renders as `/app/configs/taxonomy/maternal_v1.json`; the Python command prints the same path and exits 0. If it exits non-zero, stop; PG0 must fix the mount or the absolute `WORKBENCH_TAXONOMY_PATH`. C14 不得改为相对路径或 cwd 方式绕过。

**共同前置（只读；合并后在主工作树执行，不属于 C4 实现命令）：**

```bash
cd /Users/lute/Project/data_scrapy
git status --short
git rev-parse --short HEAD
cd apps/api && .venv/bin/alembic heads
```

Expected: 工作区干净；HEAD 是合并提交；`alembic heads` 只有 `202610220060 (head)`。

**生产 A（`https://scrapy.luteos.com`）：**

```bash
ssh -i zhoujian_pachong.pem ubuntu@43.163.92.244
cd /opt/data-achieve-scrapy/app
git fetch origin main
git merge --ff-only FETCH_HEAD
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml run --rm --no-deps api \
  alembic upgrade head
```

Expected:
- 迁移前有数据库备份文件，路径记录在 PG0 发布记录里。
- `alembic upgrade head` 成功，schema head 为 `202610220060`。
- `curl -fsS https://scrapy.luteos.com/api/health` 返回 200。
- 不重建 edge。只用 `docker compose ... up -d --no-deps api console` 或 `restart edge`。
- 以上全部由 PG0 批次执行；C14 只读复核 health 与页面。

**生产 B（`https://scrapy.lute-tlz-dddd.top`）：**

```bash
ssh -i DDDD.pem ubuntu@101.34.52.232
cd /opt/data-achieve-scrapy/app
git fetch -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 \
  -c http.lowSpeedTime=20 origin deploy/tiktok-cdo-codex
git merge --ff-only FETCH_HEAD
docker compose --env-file /opt/data-achieve-scrapy/.env.production \
  -f configs/deploy/scrapy/docker-compose.yml run --rm --no-deps api \
  alembic upgrade head
```

Expected:
- B 的迁移链必须先到 `202610220059`，再升 `202610220060`。若 B 仍停在 `202607280044`，停止；先完成 B 的迁移补齐与备份授权。
- `curl -fsS https://scrapy.lute-tlz-dddd.top/api/health` 返回 200。
- A/B 健康检查都通过后，才允许把 C4 标记为已发布。

**回退：**

- 代码回退不回退已完成 run 的终态；重跑创建新 run。
- 数据库 downgrade 只在没有新 `workbench_tasks` / `runs.market_code` 数据时执行，并且必须先备份。
- 不得删除或改写 `run_ledger_entries`、`authorizations` 历史行。

- [ ] **Step 8: 记录最终证据**

在合并说明里写：

```text
C4 verification
- pytest C4: <count> passed, 0 failed
- pytest unit: <count> passed, 0 failed
- pytest integration: <count> passed, 0 failed
- ruff: All checks passed
- mypy: Success: no issues found
- alembic heads: 202610220060 (head)
- GitNexus detect-changes: partial=false truncated=false
- Run risk: <level>; WorkflowVersion risk: <level>
- task create: Idempotency-Key required; same digest replays, changed digest 409 idempotency_conflict
- task fields: seed_products (3-10 when present) and target_price_band persisted
- acceptance contact: owner/admin only; member role 422 acceptance_contact_not_member
- initial version seam: exactly one approved version per task; reused by customer create_task and collect
- runs: market_code only; market_role derived; no runs.market_role/package_type
- No run_steps / task_runs / run_ledger_entries written by C4
- run creation seam: submit_workbench_task only calls create_run_with_audit; one run.created per new run; idempotent replay adds zero
- taxonomy path: application-root resolution; container default /app/configs/taxonomy/maternal_v1.json; no cwd dependency
- C14 env: WORKBENCH_TASKS_ENABLED=true; WORKBENCH_TAXONOMY_PATH absolute or unset; read-only mount verified
- C14 handoff: /workbench acceptance checklist delivered; C14 read-only
- Production writes/releases: owned by PG0 release batch only
```

无提交；Task 7 已提交最后的测试文件。

---

## Self-Review

**1. Spec coverage**

| 设计要求 | 计划位置 |
|---|---|
| `workbench_tasks` 七槽位 | Task 1（表/模型）、Task 2（schema）、Task 5（API） |
| 包型与市场角色持久化 | Task 1（`package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`、预算列）、Task 2（schema 校验）、Task 5（保存与更新） |
| 种子商品与目标价格带 | Task 1（`seed_products`、`target_price_band` 列）、Task 2（3–10 项与价格带校验）、Task 5（保存/更新）、Task 7（C14 表单字段） |
| 任务创建幂等 | Task 1（`idempotency_key_hash` + 工作区部分唯一索引）、Task 2（请求不变）、Task 5（`Idempotency-Key`、摘要重放、409）、Task 7（浏览器重放/冲突步骤） |
| 验收联系人 owner/admin | Global Constraints、Task 5 服务/路由、Task 8 证据 |
| 初始计划版本接缝 | Task 3B（`create_initial_workflow_version_for_task`）、Task 7（C14 交接第 7 步）；C13 `create_task`/`collect` 调用 |
| `runs` 不持久化 `market_role`/`package_type` | Task 1（列断言）、Task 2（`PackageType` 只在任务单）、Task 4（`market_role_for()` 派生）、Task 7（OpenAPI 断言） |
| Quick 1 / Standard 3 对比市场 | Task 2（schema）、Task 5（API 422）、Task 7（C14 交接） |
| `workflow_versions` 关联 | Task 3（列、复合外键、创建时写入、仓储联查） |
| `execution_steps` 固化 | Task 3A（`ExecutionStepPreview`、`build_execution_steps`、`collection_tasks` 创建/校验、不可变快照） |
| 每个市场一个 run | Task 4（逐市场创建）、Task 6（API 响应 `run_ids[]`） |
| 审计化 run 创建接缝 | Task 3C（`create_run_with_audit`）、Task 4（提交服务只调用接缝并断言 `run.created`）、Task 8（直接仓储调用扫描） |
| 幂等 records 或复用现有索引 | 复用 `uq_runs_workspace_idempotency`；Task 4 派生 per-market 摘要；Task 1 测试旧索引保留；任务创建另用 `uq_workbench_tasks_workspace_idempotency` |
| 并发唯一保护 | Task 1 `uq_runs_workflow_version_market` 与 `uq_workbench_tasks_workspace_idempotency`；Task 4 IntegrityError 分支；Task 5 创建竞态分支；Task 8 PG0 PostgreSQL 双 key 证据 |
| 开关与回滚 | Global Constraints；Task 5 路由开关；Task 8 PG0 交接 |
| 市场 blocked gate/gap 不写 `runs.status` | Task 4（`authorizations.gate_status='blocked'` + `scope.gap`；run 仍 `queued`）；Task 6 集成测试 |
| 旧索引迁移 | Task 1 迁移测试；060 不 drop `uq_runs_workspace_idempotency` 与 `uq_task_runs_task_idempotency` |
| 一个迁移 060 | Task 1；`down_revision=202610220059`；单 head 测试 |
| 不做预算账本 | Global Constraints；Task 4/6 断言 `run_ledger_entries` 为 0 |
| 不做多步骤执行 | Global Constraints；C4 不创建 `run_steps` / `task_runs` |
| API 路由、服务签名、测试 | Task 5/6/7 的 Files/Interfaces/代码 |
| `/workbench` 浏览器最小验收交接 C14 | Task 7 清单与 OpenAPI 契约测试；C14 只读 |
| taxonomy 所有权与 cwd 无关路径 | Task 0（C4 自持，不要求设计文档字面路径）、Task 2（`resolve_workbench_taxonomy_path()`、生产文件、compose 挂载与环境变量）、Task 8（PG0/C14 只读复核） |
| C14 环境预期 | Task 7 Step 4、Task 8 Step 7（开关、taxonomy 绝对路径、只读挂载；C14 不改 env） |
| 生产 A/B 门禁 | Task 8 Step 7（PG0 发布批次执行写操作；C14 只读验收；C4 只交清单） |

**2. Placeholder scan**

- 已扫描全部占位词模式，未发现占位步骤。
- 每个代码步骤都有完整代码。
- 不引用其他任务代替本任务内容；重复的代码直接写出。
- 没有引用未定义的类型或函数：所有新符号都在前序任务或本任务 Files/Interfaces 里定义。

**3. Type consistency**

- `WorkbenchTask.package_type` 是 `str`，schema 是 `Literal["quick", "standard"]`；`primary_market` 与 `comparison_markets` 在模型、迁移、schema、服务中同名。
- `WorkbenchTask.markets` 是 `list[str]`，由 `[primary_market] + comparison_markets` 派生；schema 的 `markets` 是只读 property，不是输入字段。
- `runs` 只有 `market_code`；`market_role` 由 `market_role_for()` 派生，`WorkbenchSubmissionResult.market_roles` 是只读投影。
- `WorkbenchSubmissionResult.runs` 是 `tuple[Run, ...]`；路由转 `list[RunResponse]`。
- `market_idempotency_hash` 返回 64 位十六进制，匹配 `runs.idempotency_key_hash String(64)`。
- `WorkflowVersion.workbench_task_id` 在模型、迁移、schema、仓储、服务中同名。
- `Run.market_code` 在模型、迁移、schema、仓储、服务、测试中同名。
- `ExecutionStepPreview.task_id` 是 JSON 字符串；C6 的 `parse_execution_steps` 用 `uuid.UUID(value)` 解析；两处都要求合法 UUID。
- `seed_products` 在模型是 `list[str]`，schema 是 `list[str]`；空列表表示未提供，非空时 3–10 项。
- `target_price_band` 在模型是 `dict | None`，schema 是 `TargetPriceBand | None`；服务写入前统一走 `canonical_target_price_band()`，模型与指纹使用同一规范化字典。
- `idempotency_key_hash` 是 64 位十六进制，匹配 `String(64)`；`hash_create_idempotency_key()` 与 `uq_workbench_tasks_workspace_idempotency` 使用同一值。
- `create_workbench_task()` 返回 `tuple[WorkbenchTask, bool]`；路由把第二项映射为 200/201 与 `Idempotent-Replay` 头。
- `create_initial_workflow_version_for_task()` 返回 `uuid.UUID`（版本 ID）；C13 `WorkbenchTaskAdapter` 与 `WorkbenchCollectAdapter` 只消费该 ID，不读计划内部结构。
- `create_run_with_audit()` 返回 `Run`，不提交事务；`run.created` 的 `resource_id` 是 `str(run.id)`，`actor_type='system'`，`result='success'`。C4 提交服务与 C6 旧入口收敛都从 `services.run_creation` 导入该函数，不直接调用仓储 `create_run`。
- `resolve_workbench_taxonomy_path()` 返回绝对 `Path`：绝对环境变量或显式参数优先，相对值按应用根（容器 `/app`、仓库根）解析；`load_maternal_category_ids()` 收到显式 `Path` 时直接使用，不再读 cwd。
- 错误码在 `services/workbench/errors.py` 定义，路由只读 `exc.code` 与 `exc.status_code`；`idempotency_conflict` 与 C1 registry 同名。缺失 `Idempotency-Key` 复用已登记的 `invalid_request`，不新增错误码。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-22-governed-task-platform-c4-task-submission-idempotency.md`. Two execution options:

1. **Subagent-Driven（推荐）**：每个 Task 派一个 fresh subagent，任务之间做两阶段 review；适合 C4 这种跨迁移、模型、服务、路由的改动。
2. **Inline Execution**：在当前会话用 executing-plans 批量执行，在 Task 1、Task 3B、Task 3C、Task 4、Task 6、Task 8 设检查点。

执行前必须确认 C0/C1/C2 已落地、Alembic head 是 `202610220059`、C1 契约包含本计划 Contract Addendum 的全部条目。

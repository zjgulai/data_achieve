# 受治理任务平台 C6：Run 执行收敛实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `runs` 成为唯一执行真相：一个 run 可执行多个 step，每个 attempt 可审计，瞬态失败可重试，取消与租约可收敛，旧 quick / scheduler / task run-now 入口在受治理开关打开后改为创建受治理 run；MCP 行为不变，旧 MCP 到 C13。

**Architecture:** `RunExecutor` 读取 C4 固化的不可变执行步骤，按 `step_index` 顺序执行。每个逻辑 step 只有一行最终 `run_steps`，并只指向最终 attempt 的 `task_runs`；每次 attempt 另写一行 `run_step_attempts`，拥有自己的 `task_runs`。`run_steps` 只在 step 进入终态后写入，运行中的 attempt 由 attempt 表承载。重试只发生在瞬态错误。取消与租约围栏在每次 step 与每次 attempt 前检查。执行器只通过 C5 的 `RunBudget` 适配器预留/结算，不直接写账本。run 生命周期通过 C2 的 `audit_events` 统一审计：`run.created` 由 C4 `services/run_creation.create_run_with_audit` 接缝写；C6 写其余六类 `run.cancel_requested`、`run.cancelled`、`run.retry_scheduled`、`run.retry_exhausted`、`run.completed`、`run.failed`。所有 step 进入终态且 `runs.status='completed'` 后，执行器只追加一条 `run.completed` 审计事件；它不调用 C8、不计算数据集质量、不写质量表。C8 消费该事件。C8 依赖 C6；C6 不依赖 C8。取消是 C6 拥有的幂等操作：`cancel_run` 接收 `idempotency_key` 与 `reason_code`，同键同参重放，同键不同参返回 `idempotency_conflict`。旧入口只在 `RUN_EXECUTION_CONVERGENCE_ENABLED=true` 时收敛；MCP 的 `run_quick_collect` 保持旧路径到 C13。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2 async、Alembic、PostgreSQL 16、SQLite 单元测试、pytest-asyncio。

## Global Constraints

- **契约优先。** `docs/design/【契约冻结】v1-表名-枚举-接口.md` 是机器契约。本文与契约冲突时，以契约冻结为准。
- **隔离 worktree。** 执行分支是 `feat/gov-c6`，从 `feat/gov-c5` 创建，只在 `/Users/lute/Project/data_scrapy-gov-c6` 中创建和执行。主工作树 `/Users/lute/Project/data_scrapy` 只用于 Task 0 Step 0 的 `git worktree prune`、前驱断言与 `cp` 只读源；不得在主工作树切换分支、暂存、提交或运行测试。Task 0 Step 0 给出完整命令；后续所有 Run/Commit 命令的根目录是 `/Users/lute/Project/data_scrapy-gov-c6`，包括 `apps/api` 子路径。
- **前置计划。** C0、C1、C2 是任务文本列出的契约前置；master plan 还要求 C4、C5 先合入。C1 必须登记 `run_steps.attempt_no` 等扩展列、`run_step_attempts` 的精确列/约束/索引与 attempt 状态；C1 还必须登记本片段的取消幂等列与统一审计动作（见下两条）。C4 必须在版本创建时把执行步骤写入 `workflow_versions.plan_payload["execution_steps"]` 并创建/校验 `collection_tasks`（形状见 Task 3）；C4 还必须提供 `services/run_creation.create_run_with_audit` 作为 `run.created` 的唯一写入口；C5 提供 `RunBudget`、`start_tool_call` / `complete_tool_call`、预算服务与 `services/run_limits.py`。C6 开始时 Alembic head 必须是 `202610220063`。任一前置缺失时停止，不得另造并行结构。
- **基线。** 本文编写时 HEAD 是 `f0560ca`，Alembic head 是 `202610210055`。C0/C1/C2 合入后，C6 开始时 Alembic head 必须是 `202610220063`。C6 只新增一个迁移 `202610220064`；C6 结束时 head 是 `202610220064`，但这不是平台最终 head。master plan 的后续切片继续追加 `202610220065`–`202610220070`，平台最终 head 是 `202610220070`。生产 preflight 的期望 schema 由 `SCRAPY_EXPECTED_SCHEMA` 提供，PG0 发布批次按 master plan 的最终迁移 `202610220070` 设置；C6 与 C14 都不得把 `202610220064` 写死为生产期望值。
- **C1 取消幂等登记前置。** 本文件不修改 C1。C6 Task 1 开始前，C1 必须在 `runs` 注册表中登记 `cancel_idempotency_key_hash`（`string(64)`，可空，`status: extend`，`phase: C6`）、`cancel_reason_code`（`string(80)`，可空，`status: extend`，`phase: C6`）与部分唯一索引 `uq_runs_workspace_cancel_idempotency (workspace_id, cancel_idempotency_key_hash) WHERE cancel_idempotency_key_hash IS NOT NULL`；并在路径注册表登记 `runs.cancel`（`POST /api/runs/{run_id}/cancel`，`idempotent: true`，请求字段 `idempotency_key`、`reason_code`，错误码 `idempotency_conflict`）。C1 已登记的 `runs.idempotency_key_hash` 与 `uq_runs_workspace_idempotency` 是创建幂等，不得复用为取消幂等。缺失时停止；不得把取消幂等落到内存缓存、流程变量或第二张表。这两列与索引由 `202610220064` 落库，不新增第二个迁移。
- **C1 审计动作登记前置。** C1 现有 `audit_actions` 只登记了 `run.cancelled` 与 `run.completed`（owner 都是 C6）。C6 Task 1 开始前，C1 必须在 `audit_actions.actions` 登记 `run.created`（owner C4）与 `run.cancel_requested`、`run.retry_scheduled`、`run.retry_exhausted`、`run.failed`（owner 都是 C6）五个动作；`run.created` 只由 C4 接缝写，C6 不直接写；C2 的 `services.audit_log.AUDIT_ACTIONS` 必须与注册表逐字一致。缺失时停止，不得用 `task.retried` 代替，也不得自造未登记动作名。
- **执行真相。** `runs` 是运行状态唯一事实源。`run_steps` 是步骤执行唯一事实源。`task_runs` 是单次 collector 调用唯一事实源。其他表只能保存投影。
- **1─1 约束。** 一个逻辑 step 只有一行 `run_steps`，并只关联一条最终 `task_runs`。每次 attempt 新建一行 `run_step_attempts` 和一行独立 `task_runs`。`run_steps.attempt_no` 记录最终 attempt 号。绝不按 attempt 写 `run_steps`。
- **状态枚举。** `runs.status` 只用 `queued · running · completed · failed · cancelled`。`run_steps.status` 只用 `pending · running · success · empty · config_gated · failed · skipped`。两处 `outcome` 只用 `success · empty · config_gated · failed`。不得出现 `degraded`、`held`、`partial`。
- **账本。** `run_ledger_entries` 只有八列：`id`、`run_id`、`step_id`、`entry_kind`、`amount_usd`、`balance_after_usd`、`idempotency_key`、`created_at`。`entry_kind` 只有六个值：`estimate · reserve · accrued · settle · release · block`。`settle` 必须为正数，`release` 必须为负数。**C6 不直接调用 `record_entry`，不写 `accrued` / `settle` / `release`；唯一写入者是 C5 的 `budget_service`。** 生产路径必须注入 `OrmRunBudget`；无 budget 只允许测试替身，测试替身不得写数据库。
- **RunBudget 唯一权威。** `RunBudget` 只定义在 C5 的 `services/run_budget.py`。C6 不定义、不复制、不改名，只从该模块导入或原样 re-export；`run_execution_contracts.py`、`run_executor.py`、`run_step_runner.py` 与 `__all__` 都不得出现第二份 `RunBudget` Protocol。C6 只调用 `reserve` / `settle` / `mark_unknown` / `cancel`。
- **统一审计。** 唯一审计表是 C2 的 `audit_events`，唯一写入口是 `services.audit_log.append_audit_event`。C6 在 run 生命周期写六类动作：`run.cancel_requested`、`run.cancelled`、`run.retry_scheduled`、`run.retry_exhausted`、`run.completed`、`run.failed`。`run.created` 的 owner 是 C4；C6 只调用 C4 `services/run_creation.create_run_with_audit` 接缝，不直接写该动作。全部在同一业务事务内追加；`resource_type='run'`、`resource_id=str(run.id)`、`actor_type='system'`。`run.cancel_requested`、`run.cancelled`、`run.retry_scheduled`、`run.completed` 的 `result='success'`；`run.retry_exhausted` 与 `run.failed` 的 `result='failed'`。`details` 只放标识、状态、计数与原因码，不放密钥、原始幂等键或请求正文。不得新建第二张审计表，不得自造动作名。`run.created` 只在插入新 run 时由 C4 接缝发；幂等重放不发。
- **取消幂等（C6 拥有）。** 存储接缝是 `runs` 的取消幂等列：`cancel_idempotency_key_hash` 与 `cancel_reason_code`，加工作区级部分唯一索引 `uq_runs_workspace_cancel_idempotency`。`cancel_run` 同时接收 `idempotency_key` 与 `reason_code`；`cancel_idempotency_key_hash = sha256("run-cancel.v1:{key}")`。同一工作区、同一 run、同一键、同一 `reason_code` 重放第一次取消的结果（同一 `RunResponse`，响应头 `Idempotent-Replay: true`）；同一键不同 `reason_code` 返回 409 `idempotency_conflict`；同一 run 已被另一个键取消时按幂等取消返回原结果。并发取消只允许一个事务把 run 从 `queued · running` 原子改为 `cancelled`；只有胜出事务调用 C5 的 `OrmRunBudget.cancel`，因此预算预留只释放一次。落败事务读取已提交行，按同键重放或冲突返回，不写第二次审计。
- **质量链解耦。** C6 不 import `services.dataset_quality`、`services.market_quality` 或任何 C8 模块，不调用 `evaluate_and_persist_market_quality` / `ensure_market_quality`，不写 `market_assessments` / `data_gaps`。run 的全部 step 进入终态且 `runs.status='completed'` 后，C6 通过 C2 的 `services.audit_log.append_audit_event` 在同一事务追加一条 `action='run.completed'` 审计事件：`resource_type='run'`、`resource_id=str(run.id)`、`actor_type='system'`、`result='success'`。`details` 只含 `run_id`、`collection_task_id`、`workflow_version_id`、`market_code`、`run_status`、`outcome`、`records_count`、`finished_at`、`step_indexes`。`failed` 与 `cancelled` 不发 `run.completed`，分别发 `run.failed` 与 `run.cancelled`。质量评估接口 `evaluate_and_persist_market_quality(session, run_id, task_id, market_code, package_type)` 由 C8 计划定义；C8 的消费者从 `run.completed` 解析 `run_id` 并调用它。重复事件由 C8 的 `uq_market_assessments_task_market` 与 scorecard hash 幂等吸收；C6 不做质量幂等。
- **取消。** 取消只写 `runs.status=cancelled`、`finished_at`、`cancel_idempotency_key_hash`、`cancel_reason_code`，并清空 `lease_expires_at`。取消不删除 step、attempt、task_run 或账本。执行器不得把终态写回已取消的 run。取消幂等按上面“取消幂等”条目执行；重复取消不再调用 C5 的预算释放。
- **租约。** 领取、续期、释放都按 `worker_id` 围栏。执行器在每次 step 与每次 attempt 前检查租约。租约丢失时抛 `RunLeaseLostError`，worker 回滚未提交写入。
- **迁移单 head。** 每个迁移任务后运行 `uv run alembic heads`，输出必须只有一行。C6 的本地退出 head 是 `202610220064`。后续切片再追加 `202610220065`–`202610220070`；平台最终 head 是 master plan 的 `202610220070`，PG0 发布批次用它作为生产验收目标。C6 的 `uv run alembic heads` 断言只证明本切片没有被分叉，不证明生产最终 schema。
- **GitNexus 强制。** 编辑任何函数、类或方法前，先运行 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。报告调用方、流程和 `risk`。`risk` 为 HIGH 或 CRITICAL 时先告警并停下。`risk` 为 UNKNOWN 时不得当作安全，必须用文本搜索确认调用方。
- **提交前图分析。** 每个 commit 前运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。输出含 `partial: true` 或 `truncated: true` 时不算通过，必须重跑。最终交接再运行 `detect-changes --scope compare --base-ref main --repo .`。
- **TDD。** 每个代码任务先写失败测试，运行并确认失败，再写最小实现，运行并确认通过，最后提交。
- **旧入口保留响应。** `POST /api/quick-collect` 仍返回 201 与 `QuickCollectResponse`。`POST /api/quick-collect/async` 仍返回 202 与 `queued`。`POST /api/tasks/{task_id}/run` 仍返回 201 与 `TaskRunResponse`。只改内部执行路径。
- **MCP 行为不变。** C6 不修改 `mcp_runtime/**`，也不改变 `run_quick_collect` 对 MCP 的响应、错误与预算语义。API quick 路由只在 `RUN_EXECUTION_CONVERGENCE_ENABLED=true` 时走受治理 run；MCP 继续走旧路径，C13 再迁移。`run_quick_collect` 的 GitNexus 风险是 HIGH（30 impacted，3 processes）；编辑前必须报告并加 MCP 回归测试。
- **Attempt 契约。** `run_step_attempts` 只用 C1 的列名：`id`、`run_id`、`step_index`、`attempt_number`、`status`、`task_run_id`、`error_reason_code String(80)`、`error_message`、`started_at`、`finished_at`、`created_at`。约束名：`uq_run_step_attempts_run_step_attempt`、`uq_run_step_attempts_task_run_id`、`ck_run_step_attempts_attempt_number_positive`；索引 `ix_run_step_attempts_run_step (run_id, step_index)`。不得使用 `step_id`、`attempt_no`、`String(60)` 或 `ix_run_step_attempts_step_id`。
- **1─1 数据库约束。** `run_steps.task_run_id` 非空时必须唯一（部分唯一索引 `uq_run_steps_task_run_id`）；`run_step_attempts.task_run_id` 也唯一。两者共同保证一个 `task_runs` 只被一个逻辑 step 或一个 attempt 引用。
- **失败 attempt 成本。** 每个 attempt 都有自己的 `task_runs`。`RunBudget.settle` 必须汇总该 run 全部 attempt 的 `task_runs.total_cost_usd`，`run_steps` 只保存最终投影。不得只结算最终 step。
- **C5 run limits 消费。** C6 在每次 attempt 前调用 C5 `services.run_limits.resolve_run_limits(session, run_id=run.id)`，把 `RunLimits.max_pages` / `max_records` 原样传给 collector；`None` 表示不限制，`0` 表示零容忍。每次翻页前检查页数，每页入库后检查记录数，超限立即抛 C5 `RunLimitExceededError`（`max_pages_exceeded` / `max_records_exceeded`），停止请求下一页且不写剩余记录。C6 不复制限额解析逻辑、不新建限额表、不修改 `services/run_limits.py`；该消费不新增迁移，仍在 062 内完成。
- **Blocked gate。** 执行前检查 `authorizations` 是否存在 `gate_status='blocked'` 的 `G-Plan`；存在时 run 保持 `queued`，不领取、不执行、不写 `failed`。
- **开关与回滚点。** `RUN_EXECUTION_CONVERGENCE_ENABLED` 默认 `false`；`RUN_WORKER_ENABLED` 默认 `false`。C6 本切片不打开开关；PG0 发布批次在 C6 通过后打开 `RUN_WORKER_ENABLED`，在 C14 只读验收后打开 `RUN_EXECUTION_CONVERGENCE_ENABLED`，并由 PG0 重启 api。C14 只读验证 `/api/health`，不改 `.env.production`、不重启容器。回滚由 PG0 发布批次执行：先关两个开关并重启 api，再回退镜像；`202610220064` downgrade 只在 `run_step_attempts` 为空时执行。
- **生产 A/B 门禁。** 本切片不直接部署：C6 不改生产、不应用迁移、不重启容器、不切换开关。生产备份、迁移应用、A/B 发布、容器重启与开关切换只由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读健康检查、canary、preflight 与浏览器验收。PG0 发布批次必须先备份，再按 A、B 顺序应用迁移，并保持 A 的 edge 固定 IP 不被重建。生产 B 使用 `configs/deploy/scrapy/docker-compose.yml`，与 A 共用；不修改 `configs/deploy/scrapy-new/**`。全量完成后生产期望 head 是 `202610220070`，`scripts/preflight-production.sh` 通过 `SCRAPY_EXPECTED_SCHEMA` 读取该值；C6 的本地产物仍是 062。
- **不做。** 不做客户 MCP 八个工具。不做报告合同、报告渲染、交付包。不做 UI。不做价格簿、预算 reserve、退款。不做新 attempt HTTP 路由。
- **提交粒度。** 每个任务至少一个 commit。提交消息使用 `feat(run):`、`fix(run):`、`test(run):`、`docs(run):` 前缀。

## 切片、迁移、开关与回滚点

| 项 | C6 |
|---|---|
| 切片 | 多步骤 run、attempt、瞬态重试、取消幂等、租约、统一审计、旧 quick/scheduler/run-now 收敛 |
| 迁移 | 只新增 `202610220064_run_step_attempts.py`，`down_revision=202610220063`；建 `run_step_attempts`、扩 `run_steps` 列、加 `run_steps.task_run_id` 部分唯一索引、加 `runs` 取消幂等列与 `uq_runs_workspace_cancel_idempotency` |
| 开关 | `RUN_EXECUTION_CONVERGENCE_ENABLED` 默认 `false`；`RUN_WORKER_ENABLED` 默认 `false` |
| 回滚点 | 两个开关置 false → 回退代码 → 062 downgrade（attempt 表为空时）→ 恢复备份。取消幂等列随 062 回退；回退后旧代码不读这些列 |
| 部署 | 本切片不直接部署；迁移应用、A/B 发布与开关切换由 PG0 发布批次执行；C14 只做只读健康、canary、preflight 与浏览器验收。生产期望 schema 由 master/final `202610220070` 与 `SCRAPY_EXPECTED_SCHEMA` 决定，不是 C6 的 062 |
| 外部依赖 | C1 attempt 契约、C1 取消幂等列与审计动作登记、C4 `execution_steps` 与 `services/run_creation.create_run_with_audit`、C5 `RunBudget` / `run_limits`、PG0 发布批次与 C14 只读验收；下游 C8 消费 `run.completed`，C6 不回依赖 C8 |

## Non-Goals

- 不实现 `discover_capabilities`、`estimate_task`、`create_task`、`get_task`、`cancel_task`、`get_delivery_manifest`、`get_evidence`、`collect` 八个客户 MCP 工具。
- 不实现 `report_contract`、`report_artifacts`、`delivery_manifest.json`。
- 不修改 `run_ledger_entries` 的列数或枚举。
- 不新增 attempt 查询路由。C14 若需要浏览器逐 attempt 视图，先升级冻结契约并新增路径。
- 不验证 Postgres 并发。C6 在隔离 PostgreSQL 上执行；C14 只读复核结果。
- 不修改 C5 的 `services/run_budget.py` 或 `services/run_limits.py`；C6 只导入并消费，不复制 `RunBudget` 或限额解析。
- 不新增 `202610220064` 之外的迁移；取消幂等列与索引属于该迁移。
- 不把 C6 本地 head `202610220064` 当作生产最终 schema；最终 head 是 `202610220070`。
- 不把 fixture 的 `workflow_runs` 接入生产执行。
- 不计算市场质量、不写 `market_assessments` / `data_gaps`、不提供质量 backfill；这些属于 C8。
- 不新建第二张审计表，不自造未登记审计动作名。
- 不把取消幂等放进进程内缓存、流程变量或 `runs.idempotency_key_hash`（创建幂等列）。

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `apps/api/alembic/versions/202610220064_run_step_attempts.py` | Create | 唯一迁移。创建 `run_step_attempts`，扩展 `run_steps` 与 `runs` 的取消幂等列。 |
| `apps/api/src/data_intelligence_hub/models/run.py` | Modify | 扩展 `RunStep` 的 attempt、依赖与工具列；扩展 `Run` 的取消幂等列。 |
| `apps/api/src/data_intelligence_hub/models/run_attempt.py` | Create | `RunStepAttempt` 与状态枚举。 |
| `apps/api/src/data_intelligence_hub/models/__init__.py` | Modify | 导出新模型。 |
| `apps/api/src/data_intelligence_hub/services/run_execution_contracts.py` | Create | 执行器协议、数据类、异常、纯函数；含 `RunCompletedEventSink` 与 `RunAuditSink`；不定义 `RunBudget`（唯一权威定义在 C5 `services/run_budget.py`）。 |
| `apps/api/src/data_intelligence_hub/services/run_audit.py` | Create | run 生命周期六类 C6 审计动作的唯一写入口；`run.created` 由 C4 接缝写；只调用 C2 `append_audit_event`。 |
| `apps/api/src/data_intelligence_hub/services/run_cancel_service.py` | Create | 取消幂等：键哈希、原子领取、重放、冲突、只释放一次预算、两条取消审计。 |
| `apps/api/src/data_intelligence_hub/services/run_retry.py` | Create | 瞬态错误分类、重试次数与退避。 |
| `apps/api/src/data_intelligence_hub/services/run_step_plan.py` | Create | `RunStepSpec`、计划解析、ORM 步骤来源。 |
| `apps/api/src/data_intelligence_hub/services/run_step_runner.py` | Create | 单个 step 的 attempt 循环、重试、重试审计、账本。 |
| `apps/api/src/data_intelligence_hub/services/run_executor.py` | Modify | 多步骤编排、依赖、取消、聚合、等级、生命周期审计。 |
| `apps/api/src/data_intelligence_hub/services/run_executor_adapters.py` | Modify | 真实 ORM 仓储：run、step、attempt、ledger；`OrmRunAuditSink` 写 `audit_events`；`OrmRunLimitsResolver` 调用 C5 `resolve_run_limits`。 |
| `apps/api/src/data_intelligence_hub/services/run_collector_call.py` | Modify | 按 `RunStepSpec` 与 attempt 创建 `task_runs`，返回回执；透传 C5 `RunLimits` 并让 `RunLimitExceededError` 立即停止。 |
| `apps/api/src/data_intelligence_hub/services/run_service.py` | Create | 创建 run（调用 C4 `create_run_with_audit`；不直接写 `run.created`）、同步执行、scheduler 入队；re-export `cancel_task_runs`、`RunCancellationResult`、`CancellationError` 供 C13。 |
| `apps/api/src/data_intelligence_hub/services/quick_collect_service.py` | Modify | 同步 quick 走 run。 |
| `apps/api/src/data_intelligence_hub/services/task_service.py` | Modify | task run-now 走 run。 |
| `apps/api/src/data_intelligence_hub/scheduler/service.py` | Modify | 到期任务只入队。 |
| `apps/api/src/data_intelligence_hub/services/run_queue_worker.py` | Modify | handler 接收租约回调。 |
| `apps/api/src/data_intelligence_hub/services/run_worker_runtime.py` | Modify | 传入 checkpoint、租约回调与审计 sink。 |
| `apps/api/src/data_intelligence_hub/repositories/runs.py` | Modify | 取消原子领取、读取最终 `task_runs`。 |
| `apps/api/src/data_intelligence_hub/schemas/run.py` | Modify | `RunCancelRequest`：必填 `idempotency_key` 与 `reason_code`。 |
| `apps/api/src/data_intelligence_hub/api/routes/runs.py` | Modify | 取消请求体、重放响应头、冲突与不可取消映射；创建新 run 时调用 C4 `create_run_with_audit`，不直接写 `run.created`。 |
| `apps/api/src/data_intelligence_hub/core/config.py` | Modify | worker 与重试配置。 |
| `apps/api/src/data_intelligence_hub/main.py` | Modify | 传递 worker 配置。 |
| `apps/api/src/data_intelligence_hub/schemas/health.py` | Modify | 暴露 `run_worker_enabled` 与 `run_execution_convergence_enabled`。 |
| `apps/api/src/data_intelligence_hub/api/routes/health.py` | Modify | 写入 `run_worker_enabled` 与 `run_execution_convergence_enabled`。 |
| `configs/deploy/scrapy/docker-compose.yml` | Modify | 生产 A/B 共用的 worker、收敛与重试开关；默认 false。 |
| `apps/api/.env.example` | Modify | 本地配置示例。 |
| `apps/api/tests/unit/run_executor_fakes.py` | Create | 执行器测试替身，含 `FakeAuditSink`。 |
| `apps/api/tests/unit/test_run_step_attempt_migration.py` | Create | 迁移与模型测试（含取消幂等列）。 |
| `apps/api/tests/unit/test_run_retry.py` | Create | 重试策略测试。 |
| `apps/api/tests/unit/test_run_step_plan.py` | Create | 步骤计划测试。 |
| `apps/api/tests/unit/test_run_executor_multi_step.py` | Create | 多步骤编排测试。 |
| `apps/api/tests/unit/test_run_step_runner.py` | Create | attempt 与重试测试（含重试审计）。 |
| `apps/api/tests/unit/test_run_executor_orm.py` | Create | ORM 装配测试。 |
| `apps/api/tests/unit/test_run_cancel_idempotency.py` | Create | 取消同键重放、同键不同参数冲突、并发只释放一次预算。 |
| `apps/api/tests/unit/test_run_audit_events.py` | Create | 六类 C6 run 生命周期审计动作、载荷、失败/取消不发 `run.completed`；`run.created` 由 C4 接缝测试覆盖。 |
| `apps/api/tests/unit/test_run_limit_enforcement.py` | Create | `max_pages` / `max_records` 的 `None`、`0`、超限停止与不写剩余记录。 |
| `apps/api/tests/unit/test_legacy_run_entrypoints.py` | Create | 旧入口扫描守卫。 |
| `apps/api/tests/unit/test_run_worker_settings.py` | Create | 开关、配置、健康测试。 |
| `apps/api/tests/unit/test_run_completed_event.py` | Create | `run.completed` 事件载荷、一次性、失败/取消不发、无 C8 import。 |
| `apps/api/tests/unit/test_deploy_worker_facts.py` | Create | A/B compose 事实测试。 |

## 追溯矩阵

| 范围 | 任务 |
|---|---|
| 隔离 worktree 与本地命令根 | Task 0 |
| 多步骤 run | Task 3、Task 5、Task 5 测试 |
| 每 attempt 处理，保持 `run_steps` 1─1 `task_runs` | Task 1、Task 5、Task 6、Task 7 |
| 瞬态重试 | Task 2、Task 7 |
| 取消 | Task 8、Task 9 |
| 取消幂等（同键重放、同键不同参数冲突、并发只释放一次预算） | Task 1、Task 9、Task 16 |
| run 生命周期统一审计（C4 接缝写 created；C6 写 cancel requested / cancelled / retry scheduled / retry exhausted / completed / failed） | Task 1、Task 5、Task 6、Task 7、Task 9、Task 10、Task 16 |
| 消费 C5 run limits 与 `max_pages` / `max_records` | Task 5、Task 6、Task 16 |
| 租约 | Task 8 |
| 旧 quick / scheduler / task run-now 收敛 | Task 10、Task 11、Task 12、Task 13 |
| `run.completed` 质量链交接 | Task 5、Task 6、Task 16 |
| worker 开关 | Task 14 |
| A/B compose 正确事实 | Task 15 |
| 迁移 062 | Task 1 |
| 生产 A/B、Postgres、浏览器交接 | Task 16 |

---

### Task 0: 隔离 worktree 与本地命令根

**Files:**
- 不改代码。只创建执行工作树，复制本计划，并同步依赖。

**Interfaces:**
- Consumes: 前置分支 `feat/gov-c5`；主工作树中的本计划文件。
- Produces: 分支 `feat/gov-c6` 与 worktree `/Users/lute/Project/data_scrapy-gov-c6`；后续所有 Run/Commit 命令只在 worktree 执行。不通过就停止。

- [ ] **Step 0: 从 C5 分支创建独立 worktree**

Run（只在主工作树执行 `git worktree prune`、前驱断言与 `cp` 源；后续所有 Run/Commit 都在新工作树）:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c5^{commit}
test ! -e /Users/lute/Project/data_scrapy-gov-c6 && echo "worktree_path_free"
git branch --list feat/gov-c6
git worktree add /Users/lute/Project/data_scrapy-gov-c6 -b feat/gov-c6 feat/gov-c5
cd /Users/lute/Project/data_scrapy-gov-c6
test "$(git branch --show-current)" = feat/gov-c6 && echo "branch=feat/gov-c6"
git merge-base --is-ancestor feat/gov-c5 HEAD; echo "c5_ancestor=$?"
mkdir -p docs/superpowers/plans
test -f docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md || cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md docs/superpowers/plans/
cd apps/api && uv sync
cd /Users/lute/Project/data_scrapy-gov-c6
git status --porcelain
```

Expected:

```text
worktree_path_free
branch=feat/gov-c6
c5_ancestor=0
```

`git rev-parse --verify feat/gov-c5^{commit}` 必须输出 C5 提交 SHA。`feat/gov-c5` 不存在、`/Users/lute/Project/data_scrapy-gov-c6` 已存在、`feat/gov-c6` 已存在、分支名不是 `feat/gov-c6` 或 `c5_ancestor` 非 0 时停止。`uv sync` 在 `apps/api` 建立 `.venv`。`git status --porcelain` 只允许为空或一行 `?? docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md`；为空时说明前置分支已包含本计划，跳过下面的 `git add` / `git commit`。需要提交计划时运行：

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
git add docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md
git commit -m "docs(plan): add c6 run execution convergence plan"
```

主工作树 `/Users/lute/Project/data_scrapy` 只用于本 Step 的 `git worktree prune`、前驱断言与 `cp` 源；不得在主工作树执行 `git add`、`git commit`、切换分支或运行测试。

- [ ] **Step 1: 确认本地命令根**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
test "$(git rev-parse --show-toplevel)" = /Users/lute/Project/data_scrapy-gov-c6 && echo "root=ok"
test -f apps/api/src/data_intelligence_hub/services/run_creation.py && echo "c4_run_creation_seam=present"
test -f .gitnexus/run.cjs || bunx gitnexus@latest analyze
sed -n '/### Task 1/,$p' docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md | rg -n "cd /Users/lute/Project/data_scrapy($|/apps)" || echo "main_tree_commands_after_task0=none"
```

Expected: `root=ok`；`c4_run_creation_seam=present`；`main_tree_commands_after_task0=none`。缺少 C4 接缝时停止，不得在 C6 复制一份 run 创建实现。后续所有命令都从 `/Users/lute/Project/data_scrapy-gov-c6` 或其 `apps/api` 子目录执行，不得回到主工作树。

---

### Task 1: 迁移 062、`run_step_attempts` 模型与取消幂等列

**Files:**
- Create: `apps/api/alembic/versions/202610220064_run_step_attempts.py`
- Create: `apps/api/src/data_intelligence_hub/models/run_attempt.py`
- Modify: `apps/api/src/data_intelligence_hub/models/run.py`（`RunStep` 扩展列、`Run` 取消幂等列）
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Test: `apps/api/tests/unit/test_run_step_attempt_migration.py`

**Interfaces:**
- Consumes: C1 已登记 `run_steps.attempt_no`、`depends_on`、`tool_id`、`provider_run_id`、`idempotency_key_hash`、`evidence_grade`、`stage`；C1 新增登记 `runs.cancel_idempotency_key_hash`、`runs.cancel_reason_code` 与 `uq_runs_workspace_cancel_idempotency`。master plan 把 `run_step_attempts` 与 062 归 C6；attempt 状态复用 `run_steps.status` 的五值子集 `running · success · empty · config_gated · failed`。`run_steps.gap_id` 属于 C8 的 gap 表，C6 不添加。
- Produces: `RunStepAttempt`、`RunStepAttemptStatus`、`Run.cancel_idempotency_key_hash`、`Run.cancel_reason_code`。表列：`id`、`run_id`、`step_index`、`attempt_number`、`status`、`task_run_id`、`error_reason_code String(80)`、`error_message`、`started_at`、`finished_at`、`created_at`。`runs` 新增两列与部分唯一索引 `uq_runs_workspace_cancel_idempotency`。

- [ ] **Step 1: 运行前置门禁与影响分析**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
git log -1 --oneline
cd apps/api
uv run alembic heads
rg -n "run_steps.attempt_no|\"attempt_no\"" ../.. --glob '!**/.git/**' --glob '!**/.gitnexus/**'
rg -n "run_step_attempts" ../.. --glob '!**/.git/**' --glob '!**/.gitnexus/**'
rg -n "execution_steps" ../.. --glob '!**/.git/**' --glob '!**/.gitnexus/**'
rg -n "uq_run_steps_task_run_id" ../.. --glob '!**/.git/**' --glob '!**/.gitnexus/**'
rg -n "cancel_idempotency_key_hash|uq_runs_workspace_cancel_idempotency" ../.. --glob '!**/.git/**' --glob '!**/.gitnexus/**'
rg -n '"run\.(created|cancel_requested|cancelled|retry_scheduled|retry_exhausted|completed|failed)"' ../.. --glob '!**/.git/**' --glob '!**/.gitnexus/**'
cd /Users/lute/Project/data_scrapy-gov-c6
test -f .gitnexus/run.cjs || bunx gitnexus@latest analyze
node .gitnexus/run.cjs impact "RunStep" --direction upstream --repo .
```

Expected:
- HEAD 在 `f0560ca` 之后。
- `uv run alembic heads` 只有一行 `202610220063 (head)`。
- 第一条 `rg` 在 C1 契约中找到 `run_steps.attempt_no`。找不到时停止，先回 C1 登记。
- 第二条 `rg` 在 master plan 的迁移表找到 `202610220064` 的 `run_step_attempts`。找不到时停止。
- 第三条 `rg` 在 C4 计划找到 `execution_steps` 的写入约定。找不到时停止，先回 C4 补计划执行步骤。
- 第四条 `rg` 在 C1 registry 找到 `uq_run_steps_task_run_id`。找不到时停止，先回 C1 登记。
- 第五条 `rg` 在 C1 registry 找到 `cancel_idempotency_key_hash`、`cancel_reason_code` 与 `uq_runs_workspace_cancel_idempotency`。找不到时停止，先回 C1 按“C1 取消幂等登记前置”登记。
- 第六条 `rg` 在 C1 契约与 C2 计划找到七个审计动作名。`run.cancelled` 与 `run.completed` 必须已登记；另五个缺失时停止，先回 C1 按“C1 审计动作登记前置”登记。
- `impact` 输出调用方、流程与 `risk`。`risk` 为 HIGH/CRITICAL 时停止并报告。

- [ ] **Step 2: 写失败测试**

```python
"""迁移 062 与 attempt 模型的源测试。"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = API_ROOT / "alembic/versions/202610220064_run_step_attempts.py"


def test_migration_revision_chain() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "202610220064"' in text
    assert 'down_revision: str | None = "202610220063"' in text


def test_migration_creates_attempt_table() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'op.create_table(\n        "run_step_attempts"' in text
    for column in (
        "run_id",
        "step_index",
        "attempt_number",
        "status",
        "task_run_id",
        "error_reason_code",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
    ):
        assert f'"{column}"' in text
    assert "uq_run_step_attempts_run_step_attempt" in text
    assert "uq_run_step_attempts_task_run_id" in text
    assert "ck_run_step_attempts_attempt_number_positive" in text
    assert "ix_run_step_attempts_run_step" in text
    assert "String(length=80)" in text


def test_migration_extends_run_steps() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    for column in (
        "attempt_no",
        "depends_on",
        "tool_id",
        "provider_run_id",
        "idempotency_key_hash",
        "evidence_grade",
        "stage",
    ):
        assert f'"{column}"' in text


def test_migration_adds_run_cancel_idempotency() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    for column in ("cancel_idempotency_key_hash", "cancel_reason_code"):
        assert f'"{column}"' in text
    assert "uq_runs_workspace_cancel_idempotency" in text
    assert "sa.String(length=64)" in text
    assert "sa.String(length=80)" in text


def test_run_model_has_cancel_idempotency_columns() -> None:
    from data_intelligence_hub.models import Run

    table = Run.__table__
    assert table.columns["cancel_idempotency_key_hash"].type.length == 64
    assert table.columns["cancel_reason_code"].type.length == 80
    index = next(
        item
        for item in table.indexes
        if item.name == "uq_runs_workspace_cancel_idempotency"
    )
    assert [column.name for column in index.columns] == [
        "workspace_id",
        "cancel_idempotency_key_hash",
    ]
    assert index.unique is True


def test_model_columns_and_constraints() -> None:
    from data_intelligence_hub.models import RunStep, RunStepAttempt

    table = RunStepAttempt.__table__
    assert table.name == "run_step_attempts"
    assert set(table.columns.keys()) == {
        "id",
        "run_id",
        "step_index",
        "attempt_number",
        "status",
        "task_run_id",
        "error_reason_code",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
    }
    constraint_names = {item.name for item in table.constraints}
    assert "uq_run_step_attempts_run_step_attempt" in constraint_names
    assert "uq_run_step_attempts_task_run_id" in constraint_names
    assert "ck_run_step_attempts_attempt_number_positive" in constraint_names

    step_columns = set(RunStep.__table__.columns.keys())
    assert {
        "attempt_no",
        "depends_on",
        "tool_id",
        "provider_run_id",
        "idempotency_key_hash",
        "evidence_grade",
        "stage",
    } <= step_columns


def test_alembic_has_single_head_062() -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["202610220064"]
```

- [ ] **Step 3: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_step_attempt_migration.py -q
```

Expected: FAIL。迁移文件不存在，`RunStepAttempt` 无法导入。

- [ ] **Step 4: 写模型**

新建 `apps/api/src/data_intelligence_hub/models/run_attempt.py`：

```python
"""``run_step_attempts``：一次 step 的一次 collector 调用。"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class RunStepAttemptStatus(StrEnum):
    """``run_step_attempts.status`` 的五个取值。"""

    RUNNING = "running"
    SUCCESS = "success"
    EMPTY = "empty"
    CONFIG_GATED = "config_gated"
    FAILED = "failed"


_ATTEMPT_STATUS_CHECK = (
    "status IN ('running', 'success', 'empty', 'config_gated', 'failed')"
)


class RunStepAttempt(UUIDPrimaryKeyMixin, Base):
    # 一次 step attempt。
    # 一行对应一次 collector 调用。每次 attempt 新建一行。
    # run_steps 只关联最终 attempt 的 task_runs。

    __tablename__ = "run_step_attempts"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "step_index",
            "attempt_number",
            name="uq_run_step_attempts_run_step_attempt",
        ),
        UniqueConstraint(
            "task_run_id",
            name="uq_run_step_attempts_task_run_id",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_run_step_attempts_attempt_number_positive",
        ),
        CheckConstraint(_ATTEMPT_STATUS_CHECK, name="ck_run_step_attempts_status"),
        Index(
            "ix_run_step_attempts_run_step",
            "run_id",
            "step_index",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"),
        nullable=False,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    task_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_runs.id"))
    error_reason_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["RunStepAttempt", "RunStepAttemptStatus"]
```

在 `apps/api/src/data_intelligence_hub/models/run.py` 的 `RunStep` 类中加入 C1 登记的扩展列，并在文件头导入 `JSON`：

```python
    attempt_no: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
        nullable=False,
    )
    depends_on: Mapped[list[int] | None] = mapped_column(JSON)
    tool_id: Mapped[str | None] = mapped_column(String(200))
    provider_run_id: Mapped[str | None] = mapped_column(String(120))
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    stage: Mapped[str | None] = mapped_column(String(10))
```

在 `RunStep.__table_args__` 加：

```python
        Index(
            "uq_run_steps_task_run_id",
            "task_run_id",
            unique=True,
            postgresql_where=text("task_run_id IS NOT NULL"),
            sqlite_where=text("task_run_id IS NOT NULL"),
        ),
```

并在 `models/run.py` 导入 `Index` 与 `text`。该索引保证一个 `task_runs` 只被一个逻辑 step 引用。

在同一个文件给 `Run` 类加入 C1 登记的取消幂等列：

```python
    # 取消幂等。创建幂等用上面的 idempotency_key_hash，两者不得混用。
    cancel_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    cancel_reason_code: Mapped[str | None] = mapped_column(String(80))
```

在 `Run.__table_args__` 加：

```python
        # 同一工作区下，同一个取消幂等键只能落到一行 run。
        # 不同键对同一 run 的重复取消是幂等重放，不再命中唯一性。
        Index(
            "uq_runs_workspace_cancel_idempotency",
            "workspace_id",
            "cancel_idempotency_key_hash",
            unique=True,
            postgresql_where=text("cancel_idempotency_key_hash IS NOT NULL"),
            sqlite_where=text("cancel_idempotency_key_hash IS NOT NULL"),
        ),
```

在 `apps/api/src/data_intelligence_hub/models/__init__.py` 的 `models.run_attempt` 导入与 `__all__` 中加入 `RunStepAttempt`、`RunStepAttemptStatus`。不要把它们放进 `models/run.py`。

- [ ] **Step 5: 写迁移**

```python
"""Create run_step_attempts.

Revision ID: 202610220064
Revises: 202610220063
Create Date: 2026-10-22

说明：

- C1 v1.1 已登记本表与五值状态。
- 每次 attempt 一行，拥有自己的 task_runs。
- run_steps 只关联最终 attempt 的 task_runs，保持 1-1。
- C6 在 runs 上加取消幂等列与工作区级部分唯一索引；
  创建幂等列 idempotency_key_hash 不承载取消幂等。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220064"
down_revision: str | None = "202610220063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "run_steps",
        sa.Column(
            "attempt_no",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column("run_steps", sa.Column("depends_on", sa.JSON(), nullable=True))
    op.add_column("run_steps", sa.Column("tool_id", sa.String(length=200), nullable=True))
    op.add_column(
        "run_steps",
        sa.Column("provider_run_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "run_steps",
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "run_steps",
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
    )
    op.add_column("run_steps", sa.Column("stage", sa.String(length=10), nullable=True))

    # C6 取消幂等接缝。创建幂等列 idempotency_key_hash 已存在，不得复用。
    op.add_column(
        "runs",
        sa.Column("cancel_idempotency_key_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "runs",
        sa.Column("cancel_reason_code", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "uq_runs_workspace_cancel_idempotency",
        "runs",
        ["workspace_id", "cancel_idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("cancel_idempotency_key_hash IS NOT NULL"),
        sqlite_where=sa.text("cancel_idempotency_key_hash IS NOT NULL"),
    )

    op.create_table(
        "run_step_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("task_run_id", sa.Uuid(), nullable=True),
        sa.Column("error_reason_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_step_attempts"),
        sa.UniqueConstraint(
            "run_id",
            "step_index",
            "attempt_number",
            name="uq_run_step_attempts_run_step_attempt",
        ),
        sa.UniqueConstraint(
            "task_run_id",
            name="uq_run_step_attempts_task_run_id",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_run_step_attempts_attempt_number_positive",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'empty', 'config_gated', 'failed')",
            name="ck_run_step_attempts_status",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_step_attempts_run_id_runs",
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            ["task_runs.id"],
            name="fk_run_step_attempts_task_run_id_task_runs",
        ),
    )
    op.create_index(
        "ix_run_step_attempts_run_step",
        "run_step_attempts",
        ["run_id", "step_index"],
    )
    op.create_index(
        "uq_run_steps_task_run_id",
        "run_steps",
        ["task_run_id"],
        unique=True,
        postgresql_where=sa.text("task_run_id IS NOT NULL"),
        sqlite_where=sa.text("task_run_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_runs_workspace_cancel_idempotency",
        table_name="runs",
    )
    op.drop_column("runs", "cancel_reason_code")
    op.drop_column("runs", "cancel_idempotency_key_hash")
    op.drop_index("uq_run_steps_task_run_id", table_name="run_steps")
    op.drop_index("ix_run_step_attempts_run_step", table_name="run_step_attempts")
    op.drop_table("run_step_attempts")
    op.drop_column("run_steps", "stage")
    op.drop_column("run_steps", "evidence_grade")
    op.drop_column("run_steps", "idempotency_key_hash")
    op.drop_column("run_steps", "provider_run_id")
    op.drop_column("run_steps", "tool_id")
    op.drop_column("run_steps", "depends_on")
    op.drop_column("run_steps", "attempt_no")
```

- [ ] **Step 6: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_step_attempt_migration.py -q
uv run alembic heads
```

Expected: 7 passed。`alembic heads` 只有一行 `202610220064 (head)`。

- [ ] **Step 7: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/alembic/versions/202610220064_run_step_attempts.py \
  apps/api/src/data_intelligence_hub/models/run.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/tests/unit/test_run_step_attempt_migration.py
git commit -m "feat(run): add run_step_attempts schema"
```

Expected: `detect-changes` 不含 `partial: true` 或 `truncated: true`。

---

### Task 2: 重试策略纯函数

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_retry.py`
- Test: `apps/api/tests/unit/test_run_retry.py`

**Interfaces:**
- Produces: `RetryPolicy`、`StepRunRetry` 分类函数。`RetryPolicy.max_attempts`、`delay_for(failed_attempt_number)`、`is_transient_error(exc)`、`is_transient_result(result)`。
- C5 `RunLimitExceededError` 必须分类为非瞬态（不重试）；`is_transient_error` 显式返回 `False`，不得落入通用 `Exception` 瞬态分支。
- 后续任务：`RunStepRunner`（Task 7）消费。

- [ ] **Step 1: 写失败测试**

```python
"""重试策略测试。只测纯函数，不建库。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from data_intelligence_hub.collectors.outbound_policy import CollectionPolicyDenied
from data_intelligence_hub.services.run_retry import RetryPolicy


def test_timeout_is_transient() -> None:
    policy = RetryPolicy()
    assert policy.is_transient_error(TimeoutError("upstream timeout")) is True
    assert policy.reason_for_error(TimeoutError("upstream timeout")) == "timeout"


def test_policy_denied_is_not_transient() -> None:
    policy = RetryPolicy()
    exc = CollectionPolicyDenied("blocked", code="robots")
    assert policy.is_transient_error(exc) is False
    assert policy.reason_for_error(exc) == "policy_denied"


def test_429_and_5xx_results_are_transient() -> None:
    policy = RetryPolicy()
    assert policy.is_transient_result(SimpleNamespace(
        status="failed", outcome="failed", error_message="HTTP 429 rate limit"
    )) is True
    assert policy.is_transient_result(SimpleNamespace(
        status="failed", outcome="failed", error_message="HTTP 503 unavailable"
    )) is True


def test_unknown_failure_is_not_retried() -> None:
    policy = RetryPolicy()
    assert policy.is_transient_error(RuntimeError("bad payload")) is False
    assert policy.is_transient_result(SimpleNamespace(
        status="failed", outcome="failed", error_message="bad payload"
    )) is False


def test_delay_is_exponential_and_capped() -> None:
    policy = RetryPolicy(
        max_attempts=4,
        base_delay_seconds=2.0,
        max_delay_seconds=5.0,
    )
    assert [policy.delay_for(number) for number in (1, 2, 3, 4)] == [
        2.0,
        4.0,
        5.0,
        5.0,
    ]


def test_policy_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay_seconds=-1)
    with pytest.raises(ValueError):
        RetryPolicy(max_delay_seconds=0.5)
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_retry.py -q
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 写实现**

```python
"""瞬态失败分类与有界重试。

只重试可恢复的上游错误。认证、权限、配额、配置与策略错误不重试。
未知错误按非瞬态处理，避免无限重试和重复计费。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

_TRANSIENT_EXCEPTION_NAMES = (
    "timeout",
    "connection",
    "transport",
    "temporarilyunavailable",
)
_NON_TRANSIENT_NAME_TOKENS = (
    "policy",
    "config",
    "auth",
    "permission",
    "quota",
    "notrunnable",
    "notallowed",
    "invalid",
)
_TRANSIENT_TEXT_TOKENS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "temporarily unavailable",
    "rate limit",
    "too many requests",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
)


class FailureResult(Protocol):
    status: str
    outcome: str | None
    error_message: str | None


def _error_text(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    return f"{type(exc).__name__}: {exc}".lower()


def _matches(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """一次 step 的重试预算。

    ``max_attempts`` 是总 attempt 数，不是重试次数。
    """

    max_attempts: int = 3
    base_delay_seconds: float = 2.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError("max_attempts 必须在 1 到 5 之间")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds 不能为负数")
        if self.max_delay_seconds <= 0:
            raise ValueError("max_delay_seconds 必须大于 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds 不能小于 base_delay_seconds")

    def delay_for(self, failed_attempt_number: int) -> float:
        """第 N 次失败后的退避秒数。N 从 1 开始。"""
        if failed_attempt_number < 1:
            raise ValueError("failed_attempt_number 必须大于等于 1")
        raw = self.base_delay_seconds * (2 ** (failed_attempt_number - 1))
        return min(raw, self.max_delay_seconds)

    def is_transient_error(self, exc: BaseException | None) -> bool:
        text = _error_text(exc)
        if _matches(text, _NON_TRANSIENT_NAME_TOKENS):
            return False
        if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            return True
        return _matches(text, _TRANSIENT_EXCEPTION_NAMES + _TRANSIENT_TEXT_TOKENS)

    def reason_for_error(self, exc: BaseException | None) -> str:
        text = _error_text(exc)
        if "timeout" in text or "timed out" in text:
            return "timeout"
        if "429" in text or "rate limit" in text or "too many requests" in text:
            return "rate_limited"
        if any(code in text for code in ("500", "502", "503", "504")):
            return "upstream_5xx"
        if "connection" in text or "transport" in text:
            return "connection"
        if _matches(text, _NON_TRANSIENT_NAME_TOKENS):
            if "policy" in text:
                return "policy_denied"
            if "config" in text or "invalid" in text:
                return "config_error"
            return "non_transient"
        return "non_transient"

    def is_transient_result(self, result: FailureResult | None) -> bool:
        if result is None:
            return False
        if result.outcome != "failed" and result.status != "failed":
            return False
        text = (result.error_message or "").lower()
        return _matches(text, _TRANSIENT_TEXT_TOKENS)

    def reason_for_result(self, result: FailureResult | None) -> str:
        if result is None:
            return "non_transient"
        text = (result.error_message or "").lower()
        if "timeout" in text or "timed out" in text:
            return "timeout"
        if "429" in text or "rate limit" in text or "too many requests" in text:
            return "rate_limited"
        if any(code in text for code in ("500", "502", "503", "504")):
            return "upstream_5xx"
        if "connection" in text:
            return "connection"
        return "non_transient"


__all__ = ["RetryPolicy"]
```

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_retry.py -q
```

Expected: 6 passed。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_retry.py \
  apps/api/tests/unit/test_run_retry.py
git commit -m "feat(run): add bounded retry policy"
```

---

### Task 3: 计划步骤解析

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_step_plan.py`
- Test: `apps/api/tests/unit/test_run_step_plan.py`

**Interfaces:**
- Consumes: C4 写入 `workflow_versions.plan_payload["execution_steps"]`。每项形状：

```json
{
  "step_index": 0,
  "task_id": "uuid",
  "endpoint_type": "tikhub_tiktok_video_search",
  "collector_type": "tikhub_social",
  "depends_on": [],
  "max_attempts": 3
}
```

- Produces: `RunStepSpec`、`RunStepSource`、`DefaultRunStepSource`、`OrmRunStepSource`、`RunStepPlanError`、`RunStepPlanMissingError`、`RunStepPlanInvalidError`、`parse_execution_steps`、`validate_step_specs`。

- [ ] **Step 1: 写失败测试**

```python
"""执行步骤计划解析测试。不建库。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from data_intelligence_hub.services.run_step_plan import (
    DefaultRunStepSource,
    RunStepPlanInvalidError,
    RunStepPlanMissingError,
    RunStepSpec,
    parse_execution_steps,
    validate_step_specs,
)


def _raw(step_index: int = 0) -> dict[str, object]:
    return {
        "step_index": step_index,
        "task_id": str(uuid.uuid4()),
        "endpoint_type": "generic_web",
        "collector_type": "generic_web",
        "depends_on": [],
        "max_attempts": 2,
    }


def test_parse_execution_steps_returns_specs() -> None:
    raw = [_raw(0), {**_raw(1), "depends_on": [0]}]
    specs = parse_execution_steps(raw)
    assert [spec.step_index for spec in specs] == [0, 1]
    assert specs[1].depends_on == (0,)
    assert specs[0].max_attempts == 2


def test_missing_execution_steps_is_rejected() -> None:
    with pytest.raises(RunStepPlanMissingError):
        parse_execution_steps(None)
    with pytest.raises(RunStepPlanMissingError):
        parse_execution_steps([])


def test_non_contiguous_indices_are_rejected() -> None:
    with pytest.raises(RunStepPlanInvalidError):
        parse_execution_steps([_raw(1)])


def test_forward_dependency_is_rejected() -> None:
    with pytest.raises(RunStepPlanInvalidError):
        parse_execution_steps([{**_raw(0), "depends_on": [1]}, _raw(1)])


def test_duplicate_index_is_rejected() -> None:
    with pytest.raises(RunStepPlanInvalidError):
        parse_execution_steps([_raw(0), _raw(0)])


def test_invalid_max_attempts_is_rejected() -> None:
    with pytest.raises(RunStepPlanInvalidError):
        parse_execution_steps([{**_raw(0), "max_attempts": 6}])


def test_validate_step_specs_requires_collector() -> None:
    with pytest.raises(RunStepPlanInvalidError):
        validate_step_specs(
            [RunStepSpec(0, "generic_web", "", None)],
            require_collector=True,
        )


async def test_default_source_returns_single_step() -> None:
    run = SimpleNamespace(
        task_id=uuid.uuid4(),
        endpoint_type="generic_web",
        collector_type="generic_web",
    )
    specs = await DefaultRunStepSource()(run)
    assert specs == [RunStepSpec(0, "generic_web", "generic_web", run.task_id)]
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_step_plan.py -q
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 写实现**

```python
"""一次 run 的执行步骤。

步骤来源只有两个：

1. ``runs.workflow_version_id`` 指向的计划版本。C4 在
   ``plan_payload["execution_steps"]`` 写入不可变列表。
2. ``runs.task_id`` 指向的单次采集任务。旧 quick / task run-now 使用。

本模块只解析步骤，不执行采集。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.services.exceptions import (
    BudgetApprovalRequiredError,
    ServiceError,
)


class RunStepPlanError(ServiceError):
    message = "run_step_plan_invalid"


class RunStepPlanMissingError(RunStepPlanError):
    message = "run_step_plan_missing"


class RunStepPlanInvalidError(RunStepPlanError):
    message = "run_step_plan_invalid"


@dataclass(frozen=True, slots=True)
class RunStepSpec:
    step_index: int
    endpoint_type: str
    collector_type: str
    task_id: uuid.UUID | None
    depends_on: tuple[int, ...] = ()
    max_attempts: int | None = None


class RunRunContext(Protocol):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    workflow_version_id: uuid.UUID | None
    endpoint_type: str | None
    collector_type: str | None


class RunStepSource(Protocol):
    async def __call__(self, run: RunRunContext) -> list[RunStepSpec]: ...


def _as_task_id(value: Any) -> uuid.UUID:
    if not isinstance(value, str):
        raise RunStepPlanInvalidError("execution_steps.task_id 必须是字符串")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise RunStepPlanInvalidError("execution_steps.task_id 不是合法 UUID") from exc


def parse_execution_steps(raw: object) -> list[RunStepSpec]:
    """解析 C4 的 execution_steps。输入不合法时抛领域异常。"""
    if not isinstance(raw, list) or not raw:
        raise RunStepPlanMissingError("plan_payload.execution_steps 缺失或为空")
    specs: list[RunStepSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RunStepPlanInvalidError("execution_steps 每项必须是对象")
        step_index = item.get("step_index")
        if not isinstance(step_index, int) or isinstance(step_index, bool):
            raise RunStepPlanInvalidError("step_index 必须是整数")
        endpoint_type = item.get("endpoint_type")
        collector_type = item.get("collector_type")
        if not isinstance(endpoint_type, str) or not endpoint_type:
            raise RunStepPlanInvalidError("endpoint_type 必须是非空字符串")
        if not isinstance(collector_type, str) or not collector_type:
            raise RunStepPlanInvalidError("collector_type 必须是非空字符串")
        depends_raw = item.get("depends_on") or []
        if not isinstance(depends_raw, list) or any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in depends_raw
        ):
            raise RunStepPlanInvalidError("depends_on 必须是整数数组")
        max_attempts = item.get("max_attempts")
        if max_attempts is not None and (
            not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or max_attempts < 1
            or max_attempts > 5
        ):
            raise RunStepPlanInvalidError("max_attempts 必须在 1 到 5 之间")
        specs.append(
            RunStepSpec(
                step_index=step_index,
                endpoint_type=endpoint_type,
                collector_type=collector_type,
                task_id=_as_task_id(item.get("task_id")),
                depends_on=tuple(depends_raw),
                max_attempts=max_attempts,
            )
        )
    validate_step_specs(specs, require_collector=True)
    return specs


def validate_step_specs(
    specs: list[RunStepSpec],
    *,
    require_collector: bool,
) -> None:
    """校验序号连续、唯一、依赖只指向更早步骤。"""
    indices = sorted(spec.step_index for spec in specs)
    if indices != list(range(len(specs))):
        raise RunStepPlanInvalidError("step_index 必须从 0 连续递增")
    seen: set[int] = set()
    for spec in specs:
        if spec.step_index in seen:
            raise RunStepPlanInvalidError("step_index 不得重复")
        seen.add(spec.step_index)
        if require_collector and not spec.collector_type:
            raise RunStepPlanInvalidError("collector_type 不能为空")
        if spec.max_attempts is not None and not 1 <= spec.max_attempts <= 5:
            raise RunStepPlanInvalidError("max_attempts 必须在 1 到 5 之间")
        for dependency in spec.depends_on:
            if dependency >= spec.step_index or dependency < 0:
                raise RunStepPlanInvalidError("depends_on 只能指向更早的步骤")


class DefaultRunStepSource:
    """旧单步入口的步骤来源。"""

    async def __call__(self, run: RunRunContext) -> list[RunStepSpec]:
        return [
            RunStepSpec(
                step_index=0,
                endpoint_type=run.endpoint_type or "",
                collector_type=run.collector_type or "",
                task_id=run.task_id,
            )
        ]


class OrmRunStepSource:
    """从计划版本或采集任务解析步骤。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(self, run: RunRunContext) -> list[RunStepSpec]:
        if run.workflow_version_id is not None:
            version = await self._session.get(WorkflowVersion, run.workflow_version_id)
            if version is None:
                raise RunStepPlanMissingError("workflow_version_not_found")
            payload = version.plan_payload or {}
            specs = parse_execution_steps(payload.get("execution_steps"))
            await self._validate_tasks(run, specs)
            return specs
        if run.task_id is not None:
            task = await self._session.get(CollectionTask, run.task_id)
            if task is None:
                raise RunStepPlanMissingError("task_not_found")
            return [
                RunStepSpec(
                    step_index=0,
                    endpoint_type=_endpoint_type(task.config),
                    collector_type=task.collector_type,
                    task_id=task.id,
                )
            ]
        raise RunStepPlanMissingError("run_has_no_step_source")

    async def _validate_tasks(
        self,
        run: RunRunContext,
        specs: list[RunStepSpec],
    ) -> None:
        for spec in specs:
            if spec.task_id is None:
                raise RunStepPlanInvalidError("计划步骤必须提供 task_id")
            task = await self._session.get(CollectionTask, spec.task_id)
            if task is None:
                raise RunStepPlanInvalidError(f"task_not_found:{spec.task_id}")
            if task.workspace_id != run.workspace_id:
                raise RunStepPlanInvalidError(f"task_workspace_mismatch:{spec.task_id}")
            if task.project_id != run.project_id:
                raise RunStepPlanInvalidError(f"task_project_mismatch:{spec.task_id}")


def _endpoint_type(config: dict[str, Any] | None) -> str:
    value = (config or {}).get("endpoint_type")
    return value if isinstance(value, str) else ""


__all__ = [
    "DefaultRunStepSource",
    "OrmRunStepSource",
    "RunRunContext",
    "RunStepPlanError",
    "RunStepPlanInvalidError",
    "RunStepPlanMissingError",
    "RunStepSource",
    "RunStepSpec",
    "parse_execution_steps",
    "validate_step_specs",
]
```

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_step_plan.py -q
```

Expected: 8 passed。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_step_plan.py \
  apps/api/tests/unit/test_run_step_plan.py
git commit -m "feat(run): resolve execution step plans"
```

---

### Task 4: 执行契约模块抽取（行为不变）

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_execution_contracts.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_executor.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_executor_adapters.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_collector_call.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_worker_runtime.py`
- Test: `apps/api/tests/unit/test_run_executor.py`、`test_run_lease_fence.py`、`test_run_worker_runtime.py`（不新增断言，作为回归基线）

**Interfaces:**
- Produces: `RunRecord`、`CollectorCallResultView`、`CollectorCall`、`RunRepository`、`RunStepRepository`、`RunLedgerRepository`、`GradeRepository`、`UnitOfWork`、`RunStepWrite`、`RunLedgerWrite`、`RunNotFoundError`、`InvalidRunTransitionError`、`RunLeaseLostError`、状态常量与映射。
- 保持：`from data_intelligence_hub.services.run_executor import RunExecutor, RunRecord` 等旧导入仍可用。`run_executor.py` 重新导出迁移后的契约名；`RunBudget` 不在此列，只从 `services.run_budget` 导入或原样 re-export。

- [ ] **Step 1: 运行基线测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_executor.py tests/unit/test_run_lease_fence.py tests/unit/test_run_worker_runtime.py -q
```

Expected: 全部通过。记录通过数作为重构基线。

- [ ] **Step 2: 写共享契约模块**

```python
"""Run 执行器的共享契约。

本模块只放常量、协议、数据类与纯函数。
它不导入 ORM 模型，也不打开事务。
``RunBudget`` 不在此定义；唯一权威定义是 C5 的 ``services/run_budget.py``。
执行器、步骤 runner、ORM 适配器与测试都依赖这里。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from data_intelligence_hub.services.exceptions import ServiceError
from data_intelligence_hub.tool_catalog.evidence_grade import RunEvidenceGrade

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"

RUN_STATUSES: frozenset[str] = frozenset(
    {
        RUN_STATUS_QUEUED,
        RUN_STATUS_RUNNING,
        RUN_STATUS_COMPLETED,
        RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED,
    }
)

OUTCOME_SUCCESS = "success"
OUTCOME_EMPTY = "empty"
OUTCOME_CONFIG_GATED = "config_gated"
OUTCOME_FAILED = "failed"

RUN_OUTCOMES: frozenset[str] = frozenset(
    {OUTCOME_SUCCESS, OUTCOME_EMPTY, OUTCOME_CONFIG_GATED, OUTCOME_FAILED}
)

OUTCOME_BY_CALL_STATUS: dict[str, str] = {
    "success": OUTCOME_SUCCESS,
    "partial_success": OUTCOME_SUCCESS,
    "empty": OUTCOME_EMPTY,
    "config_gated": OUTCOME_CONFIG_GATED,
    "failed": OUTCOME_FAILED,
}

RUN_STATUS_BY_OUTCOME: dict[str, str] = {
    OUTCOME_SUCCESS: RUN_STATUS_COMPLETED,
    OUTCOME_EMPTY: RUN_STATUS_COMPLETED,
    OUTCOME_CONFIG_GATED: RUN_STATUS_COMPLETED,
    OUTCOME_FAILED: RUN_STATUS_FAILED,
}

STEP_STATUS_BY_OUTCOME: dict[str, str] = {
    OUTCOME_SUCCESS: "success",
    OUTCOME_EMPTY: "empty",
    OUTCOME_CONFIG_GATED: "config_gated",
    OUTCOME_FAILED: "failed",
}


class RunNotFoundError(ServiceError):
    message = "run_not_found"

    def __init__(self, run_id: uuid.UUID) -> None:
        super().__init__(self.message)
        self.run_id = run_id


class InvalidRunTransitionError(ServiceError):
    message = "invalid_run_transition"

    def __init__(self, run_id: uuid.UUID, status: str) -> None:
        super().__init__(f"{self.message}: {status}")
        self.run_id = run_id
        self.status = status


class RunLeaseLostError(ServiceError):
    message = "run_lease_lost"

    def __init__(
        self,
        run_id: uuid.UUID,
        expected_worker: str | None,
        actual_worker: str | None,
    ) -> None:
        super().__init__(
            f"{self.message}: expected={expected_worker!r} actual={actual_worker!r}"
        )
        self.run_id = run_id
        self.expected_worker = expected_worker
        self.actual_worker = actual_worker


class RunRecord(Protocol):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    workflow_version_id: uuid.UUID | None
    market_code: str | None
    status: str
    outcome: str | None
    evidence_grade: str | None
    error_message: str | None
    records_count: int
    total_cost_usd: Decimal | None
    execution_mode: str
    started_at: datetime | None
    finished_at: datetime | None
    template_id: str | None
    authorization_id: uuid.UUID | None
    window_days: int
    source_count: int
    collector_type: str | None
    endpoint_type: str | None


class CollectorCallResultView(Protocol):
    status: str
    outcome: str | None
    records_count: int
    entities_count: int
    error_message: str | None
    live_call: bool
    sample_n: int
    entity_count: int
    source_count: int
    window_days: int
    task_run_id: uuid.UUID | None
    collector_type: str | None
    endpoint_type: str | None
    unit: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_cost_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class RunStepWrite:
    id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    endpoint_type: str
    collector_type: str
    task_run_id: uuid.UUID | None
    status: str
    outcome: str | None
    records_count: int
    unit: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_cost_usd: Decimal | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime
    attempt_no: int = 1
    depends_on: tuple[int, ...] = ()
    tool_id: str | None = None
    provider_run_id: str | None = None
    idempotency_key_hash: str | None = None
    evidence_grade: str | None = None
    stage: str | None = None


@dataclass(frozen=True, slots=True)
class RunLedgerWrite:
    # 仅为旧测试兼容保留；C6 生产执行路径不构造、不写入。账本唯一写入者是 C5。
    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None
    entry_kind: str
    amount_usd: Decimal
    balance_after_usd: Decimal
    idempotency_key: str
    created_at: datetime


class RunRepository(Protocol):
    async def get(self, run_id: uuid.UUID) -> RunRecord | None: ...

    async def save(self, run: RunRecord) -> None: ...

    async def status(self, run_id: uuid.UUID) -> str | None: ...


class RunCompletedEventSink(Protocol):
    """run 终态后的唯一跨切片出口。

    只允许写 `run.completed` 审计事件；不得 import 或调用 C8 质量模块。
    """

    async def __call__(
        self,
        run: RunRecord,
        steps: tuple[RunStepWrite, ...],
    ) -> None: ...


class RunAuditSink(Protocol):
    """run 生命周期审计的唯一出口。

    只写 C2 的 `audit_events`。动作名必须在 C1 `audit-actions.v1` 登记。
    生产只注入一个实现；`run.completed` 可由 `record` 或 `__call__` 写。
    """

    async def record(
        self,
        action: str,
        run: RunRecord,
        *,
        steps: tuple[RunStepWrite, ...] = (),
        details: dict[str, object] | None = None,
        result: str = "success",
    ) -> None: ...


class RunStepRepository(Protocol):
    async def list(self, run_id: uuid.UUID) -> list[RunStepWrite]: ...

    async def add(self, step: RunStepWrite) -> None: ...

    async def update(self, step: RunStepWrite) -> None: ...


class RunLedgerRepository(Protocol):
    # 仅为旧测试兼容保留；生产 bundle 不再注入。
    async def add(self, entry: RunLedgerWrite) -> None: ...


class GradeRepository(Protocol):
    async def add(self, grade: RunEvidenceGrade) -> None: ...


class UnitOfWork(Protocol):
    async def flush(self) -> None: ...

    async def commit(self) -> None: ...


class CollectorCall(Protocol):
    async def __call__(self, run: RunRecord) -> CollectorCallResultView: ...


class GradeCalculator(Protocol):
    def __call__(
        self,
        *,
        run_id: uuid.UUID,
        live_call: bool,
        authorization_id: uuid.UUID | None,
        sample_n: int,
        required_n: int,
        window_days: int,
        required_window_days: int,
        source_count: int,
        required_source_count: int,
        entity_count: int,
        required_entity_count: int,
    ) -> RunEvidenceGrade: ...


# RunBudget 的唯一权威定义是 C5 的 services/run_budget.py。
# 本模块不定义、不复制该 Protocol；需要它的模块从 services.run_budget 导入或原样 re-export。


def resolve_outcome(call: CollectorCallResultView) -> str:
    """把一次调用结果收敛为契约四值。"""
    if call.outcome is not None:
        if call.outcome not in RUN_OUTCOMES:
            raise ValueError(f"unknown run outcome: {call.outcome}")
        return call.outcome
    try:
        return OUTCOME_BY_CALL_STATUS[call.status]
    except KeyError as exc:
        raise ValueError(f"unknown collector call status: {call.status}") from exc


__all__ = [
    "CollectorCall",
    "CollectorCallResultView",
    "GradeCalculator",
    "GradeRepository",
    "InvalidRunTransitionError",
    "OUTCOME_BY_CALL_STATUS",
    "OUTCOME_CONFIG_GATED",
    "OUTCOME_EMPTY",
    "OUTCOME_FAILED",
    "OUTCOME_SUCCESS",
    "RUN_OUTCOMES",
    "RUN_STATUSES",
    "RUN_STATUS_BY_OUTCOME",
    "RUN_STATUS_CANCELLED",
    "RUN_STATUS_COMPLETED",
    "RUN_STATUS_FAILED",
    "RUN_STATUS_QUEUED",
    "RUN_STATUS_RUNNING",
    "RunAuditSink",
    "RunCompletedEventSink",
    "RunLeaseLostError",
    "RunLedgerRepository",
    "RunLedgerWrite",
    "RunLimitsResolver",
    "RunNotFoundError",
    "RunRecord",
    "RunRepository",
    "RunStepRepository",
    "RunStepWrite",
    "STEP_STATUS_BY_OUTCOME",
    "UnitOfWork",
    "resolve_outcome",
    "unlimited_run_limits",
]
```

- [ ] **Step 3: 改 `run_executor.py` 只保留执行类**

删除 `run_executor.py` 中原有的状态常量、异常、Protocol、`RunStepWrite`、`RunLedgerWrite` 与 `_resolve_outcome`。`RunBudget` 的唯一权威定义是 C5 的 `services/run_budget.py`；其他模块只从那里导入或原样 re-export，本计划不重新定义。文件头改为：

```python
"""Run 执行器。契约定义在 ``run_execution_contracts``。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from data_intelligence_hub.services.run_execution_contracts import (
    OUTCOME_CONFIG_GATED,
    OUTCOME_EMPTY,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
    RUN_OUTCOMES,
    RUN_STATUS_BY_OUTCOME,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    RUN_STATUSES,
    STEP_STATUS_BY_OUTCOME,
    CollectorCall,
    CollectorCallResultView,
    GradeCalculator,
    GradeRepository,
    InvalidRunTransitionError,
    RunLeaseLostError,
    RunLedgerRepository,
    RunLedgerWrite,
    RunNotFoundError,
    RunRecord,
    RunRepository,
    RunStepRepository,
    RunStepWrite,
    UnitOfWork,
    resolve_outcome,
)
from data_intelligence_hub.tool_catalog.evidence_grade import (
    RunEvidenceGrade,
    compute_run_evidence_grade,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    TemplateEvidenceThreshold,
    threshold_for,
)
```

`RunExecutor` 类体保持现有单步逻辑不变。`_resolve_outcome` 调用改为 `resolve_outcome`。文件末尾的 `__all__` 同时导出迁移后的契约名，保证旧导入可用；`__all__` 不含 `RunBudget`，该类型只从 `services.run_budget` 导入或原样 re-export。

- [ ] **Step 4: 改适配器与 worker 的导入**

`run_executor_adapters.py`、`run_collector_call.py`、`run_worker_runtime.py` 改为从 `run_execution_contracts` 导入协议与数据类。`RunExecutor` 仍从 `run_executor` 导入。

- [ ] **Step 5: 运行基线测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_executor.py tests/unit/test_run_lease_fence.py tests/unit/test_run_worker_runtime.py -q
uv run ruff check src/data_intelligence_hub/services
```

Expected: 通过数与 Step 1 相同。ruff 无错误。

- [ ] **Step 6: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_execution_contracts.py \
  apps/api/src/data_intelligence_hub/services/run_executor.py \
  apps/api/src/data_intelligence_hub/services/run_executor_adapters.py \
  apps/api/src/data_intelligence_hub/services/run_collector_call.py \
  apps/api/src/data_intelligence_hub/services/run_worker_runtime.py
git commit -m "refactor(run): extract execution contracts"
```

---

### Task 5: 多步骤执行核心与 attempt 单次执行

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_step_runner.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_execution_contracts.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_executor.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_collector_call.py`
- Test: `apps/api/tests/unit/run_executor_fakes.py`
- Test: `apps/api/tests/unit/test_run_executor.py`
- Test: `apps/api/tests/unit/test_run_executor_multi_step.py`
- Test: `apps/api/tests/unit/test_run_collector_call_guard.py`
- Test: `apps/api/tests/unit/test_run_limit_enforcement.py`

**Interfaces:**
- Consumes: `RunStepSpec`、`RunStepSource`（Task 3）；C5 `services.run_limits.resolve_run_limits`、`RunLimits`、`RunLimitExceededError`。
- Produces:
  - `CollectorCallReceipt(result, task_run_id, error)`
  - `RunStepAttemptWrite`
  - `RunStepAttemptStatus`
  - `RunStepResult(step, cancelled)`
  - `RunLimitsResolver` / `unlimited_run_limits`：生产解析 C5 run limits，测试默认不限制
  - `RunStepRunner.run(run, spec, *, limits=None, is_cancelled=None) -> StepRunResult`
  - `RunExecutionResult(run, steps, last_task_run_id)`
  - `RunCompletedEventSink(run, steps)`：只发 `run.completed` 审计事件，不调用 C8
  - `RunAuditSink.record(action, run, *, steps=(), details=None, result=...)`：写六类 C6 run 生命周期审计事件；`run.created` 由 C4 接缝写
  - `RunExecutor.execute_detailed(run_id, *, lease_valid=None, checkpoint=None) -> RunExecutionResult`

- [ ] **Step 1: 写失败测试**

新建 `tests/unit/run_executor_fakes.py`：

```python
"""Run 执行器测试替身。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from data_intelligence_hub.services.collector_service import CollectionCallResult
from data_intelligence_hub.services.run_execution_contracts import (
    CollectorCallReceipt,
    RunLedgerWrite,
    RunRecord,
    RunStepAttemptWrite,
    RunStepWrite,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade, RunEvidenceGrade


@dataclass
class FakeRun:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    workspace_id: uuid.UUID = field(default_factory=uuid.uuid4)
    project_id: uuid.UUID = field(default_factory=uuid.uuid4)
    task_id: uuid.UUID | None = field(default_factory=uuid.uuid4)
    workflow_version_id: uuid.UUID | None = None
    market_code: str | None = "US"
    status: str = "queued"
    outcome: str | None = None
    evidence_grade: str | None = None
    error_message: str | None = None
    records_count: int = 0
    total_cost_usd: Decimal | None = None
    execution_mode: str = "live"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    template_id: str | None = "t1_voc"
    authorization_id: uuid.UUID | None = None
    window_days: int = 60
    source_count: int = 2
    collector_type: str | None = "tikhub_social"
    endpoint_type: str | None = "tikhub_tiktok_video_search"


class FakeRunRepository:
    def __init__(self, run: FakeRun | None) -> None:
        self.run = run
        self.status_history: list[str] = []
        self.cancelled = False

    async def get(self, run_id: uuid.UUID) -> FakeRun | None:
        if self.run is None or self.run.id != run_id:
            return None
        return self.run

    async def save(self, run: RunRecord) -> None:
        self.status_history.append(run.status)

    async def status(self, run_id: uuid.UUID) -> str | None:
        if self.run is None or self.run.id != run_id:
            return None
        return "cancelled" if self.cancelled else self.run.status


class FakeStepRepository:
    def __init__(self) -> None:
        self.steps: list[RunStepWrite] = []

    async def list(self, run_id: uuid.UUID) -> list[RunStepWrite]:
        return [step for step in self.steps if step.run_id == run_id]

    async def add(self, step: RunStepWrite) -> None:
        self.steps.append(step)

    async def update(self, step: RunStepWrite) -> None:
        for index, existing in enumerate(self.steps):
            if existing.id == step.id:
                self.steps[index] = step
                return
        raise AssertionError(f"step not found: {step.id}")


class FakeAttemptRepository:
    def __init__(self) -> None:
        self.attempts: list[RunStepAttemptWrite] = []

    async def add(self, attempt: RunStepAttemptWrite) -> None:
        self.attempts.append(attempt)

    async def finish(
        self,
        attempt_id: uuid.UUID,
        *,
        status: str,
        task_run_id: uuid.UUID | None,
        error_reason_code: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> None:
        original = next(item for item in self.attempts if item.id == attempt_id)
        index = self.attempts.index(original)
        self.attempts[index] = RunStepAttemptWrite(
            id=original.id,
            run_id=original.run_id,
            step_index=original.step_index,
            attempt_number=original.attempt_number,
            status=status,
            task_run_id=task_run_id,
            error_reason_code=error_reason_code,
            error_message=error_message,
            started_at=original.started_at,
            finished_at=finished_at,
            created_at=original.created_at,
        )


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.entries: list[RunLedgerWrite] = []

    async def add(self, entry: RunLedgerWrite) -> None:
        self.entries.append(entry)


class FakeGradeRepository:
    def __init__(self) -> None:
        self.grades: list[RunEvidenceGrade] = []

    async def add(self, grade: RunEvidenceGrade) -> None:
        self.grades.append(grade)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.flush_calls = 0
        self.commit_calls = 0

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeCollectorCall:
    def __init__(self, results: list[CollectionCallResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[uuid.UUID, int, int]] = []

    async def __call__(
        self,
        run: RunRecord,
        step: object,
        attempt_number: int,
        step_id: uuid.UUID | None = None,
        limits: object | None = None,
    ) -> CollectorCallReceipt:
        self.calls.append((run.id, getattr(step, "step_index"), attempt_number))
        result = self._results.pop(0)
        return CollectorCallReceipt(
            result=result,
            task_run_id=result.task_run_id,
            error=None,
        )


class FakeStepSource:
    def __init__(self, steps: list[object]) -> None:
        self.steps = steps

    async def __call__(self, run: RunRecord) -> list[object]:
        return list(self.steps)


class FakeGradeCalculator:
    def __init__(self, grade: EvidenceGrade) -> None:
        self.grade = grade
        self.received: dict[str, object] = {}

    def __call__(self, **kwargs: Any) -> RunEvidenceGrade:
        self.received.update(kwargs)
        return RunEvidenceGrade(**kwargs, grade=self.grade)


def success_result(**overrides: object) -> CollectionCallResult:
    values: dict[str, object] = {
        "status": "success",
        "records_count": 12,
        "entities_count": 5,
        "sample_n": 12,
        "window_days": 60,
        "source_count": 2,
        "collector_type": "tikhub_social",
        "endpoint_type": "tikhub_tiktok_video_search",
        "task_run_id": uuid.uuid4(),
    }
    values.update(overrides)
    return CollectionCallResult(**values)  # type: ignore[arg-type]
```

新建 `tests/unit/test_run_executor_multi_step.py`：

```python
"""多步骤 run 编排测试。"""

from __future__ import annotations

from decimal import Decimal

from data_intelligence_hub.services.run_execution_contracts import (
    RunStepWrite,
)
from data_intelligence_hub.services.run_executor import RunExecutor
from data_intelligence_hub.services.run_step_plan import RunStepSpec
from tests.unit.run_executor_fakes import (
    FakeAttemptRepository,
    FakeCollectorCall,
    FakeGradeRepository,
    FakeLedgerRepository,
    FakeRun,
    FakeRunRepository,
    FakeStepRepository,
    FakeStepSource,
    FakeUnitOfWork,
    success_result,
)


def _spec(index: int, *, depends_on: tuple[int, ...] = ()) -> RunStepSpec:
    return RunStepSpec(
        step_index=index,
        endpoint_type="generic_web",
        collector_type="generic_web",
        task_id=FakeRun().task_id,
        depends_on=depends_on,
    )


def _executor(
    run: FakeRun,
    *,
    specs: list[RunStepSpec],
    results: list,
) -> tuple[RunExecutor, FakeRunRepository, FakeStepRepository, FakeAttemptRepository, FakeUnitOfWork]:
    runs = FakeRunRepository(run)
    steps = FakeStepRepository()
    attempts = FakeAttemptRepository()
    uow = FakeUnitOfWork()
    executor = RunExecutor(
        runs=runs,
        steps=steps,
        unit_of_work=uow,
        collector_call=FakeCollectorCall(results),
        attempts=attempts,
        step_source=FakeStepSource(specs),
        grades=FakeGradeRepository(),
    )
    return executor, runs, steps, attempts, uow


async def test_two_steps_complete_and_aggregate() -> None:
    run = FakeRun()
    executor, runs, steps, attempts, uow = _executor(
        run,
        specs=[_spec(0), _spec(1)],
        results=[
            success_result(records_count=10, total_cost_usd=Decimal("0.5")),
            success_result(records_count=7, total_cost_usd=Decimal("0.25")),
        ],
    )

    result = await executor.execute_detailed(run.id)

    assert result.run.status == "completed"
    assert result.run.outcome == "success"
    assert result.run.records_count == 17
    assert result.run.total_cost_usd == Decimal("0.75")
    assert [step.step_index for step in result.steps] == [0, 1]
    assert [step.task_run_id for step in result.steps] != [None, None]
    assert len(steps.steps) == 2
    assert len(attempts.attempts) == 2
    assert all(item.status == "success" for item in attempts.attempts)
    assert runs.status_history == ["running", "completed"]
    assert uow.commit_calls == 0


async def test_failed_step_does_not_block_independent_step() -> None:
    run = FakeRun()
    executor, _, _, _, _ = _executor(
        run,
        specs=[_spec(0), _spec(1)],
        results=[
            success_result(status="failed", outcome="failed", error_message="bad"),
            success_result(records_count=3),
        ],
    )

    result = await executor.execute_detailed(run.id)

    assert result.run.status == "completed"
    assert result.run.outcome == "success"
    assert result.run.records_count == 3
    assert result.steps[0].status == "failed"
    assert result.steps[1].status == "success"


async def test_dependency_failure_skips_dependent_step() -> None:
    run = FakeRun()
    executor, _, _, _, _ = _executor(
        run,
        specs=[_spec(0), _spec(1, depends_on=(0,))],
        results=[success_result(status="failed", outcome="failed", error_message="bad")],
    )

    result = await executor.execute_detailed(run.id)

    assert result.run.status == "failed"
    assert result.run.outcome == "failed"
    assert [step.status for step in result.steps] == ["failed", "skipped"]
    assert result.steps[1].error_message == "dependency_not_met:0"


async def test_checkpoint_runs_after_each_step_and_finalize() -> None:
    run = FakeRun()
    executor, _, _, _, _ = _executor(
        run,
        specs=[_spec(0), _spec(1)],
        results=[success_result(), success_result()],
    )
    checkpoints: list[str] = []

    async def checkpoint() -> None:
        checkpoints.append("checkpoint")

    await executor.execute_detailed(run.id, checkpoint=checkpoint)

    assert len(checkpoints) == 3


async def test_existing_terminal_step_is_not_re_executed_on_resume() -> None:
    run = FakeRun(status="running")
    executor, _, steps, _, _ = _executor(
        run,
        specs=[_spec(0), _spec(1)],
        results=[success_result()],
    )
    steps.steps.append(
        RunStepWrite(
            id=uuid.uuid4(),
            run_id=run.id,
            step_index=0,
            endpoint_type="generic_web",
            collector_type="generic_web",
            task_run_id=uuid.uuid4(),
            status="success",
            outcome="success",
            records_count=5,
            unit=None,
            quantity=None,
            unit_price=None,
            total_cost_usd=None,
            error_message=None,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
    )

    result = await executor.execute_detailed(run.id)

    assert len(result.steps) == 2
    assert result.steps[0].records_count == 5
    assert result.run.records_count == 5 + 12
```

在文件顶部补 `import uuid` 与 `from datetime import UTC, datetime`。

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_executor_multi_step.py -q
```

Expected: FAIL。`RunExecutor` 没有 `execute_detailed`，没有 `step_source`/`attempts` 参数。

- [ ] **Step 3: 扩展共享契约**

Task 4 已定义 `RunCompletedEventSink` 与 `RunAuditSink`；本任务不重复定义这两个 Protocol，只新增 `RunStepSpec`、`RunStepAttemptStatus`、`RunStepAttemptWrite`、`CollectorCallReceipt`、`RunExecutionResult` 与 `RunStepAttemptRepository`。

在 `run_execution_contracts.py` 加入（同时在文件头加入 `from enum import StrEnum`）：

```python
@dataclass(frozen=True, slots=True)
class RunStepSpec:
    step_index: int
    endpoint_type: str
    collector_type: str
    task_id: uuid.UUID | None
    depends_on: tuple[int, ...] = ()
    max_attempts: int | None = None


class RunStepSource(Protocol):
    async def __call__(self, run: RunRecord) -> list[RunStepSpec]: ...


class RunStepAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    EMPTY = "empty"
    CONFIG_GATED = "config_gated"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RunStepAttemptWrite:
    id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    attempt_number: int
    status: str
    task_run_id: uuid.UUID | None
    error_reason_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CollectorCallReceipt:
    result: "CollectorCallResultView | None"
    task_run_id: uuid.UUID | None
    error: BaseException | None


@dataclass(frozen=True, slots=True)
class RunExecutionResult:
    run: RunRecord
    steps: tuple[RunStepWrite, ...]

    @property
    def last_task_run_id(self) -> uuid.UUID | None:
        for step in reversed(self.steps):
            if step.task_run_id is not None:
                return step.task_run_id
        return None


class RunLimitsResolver(Protocol):
    async def __call__(self, run: RunRecord) -> RunLimits: ...


async def unlimited_run_limits(run: RunRecord) -> RunLimits:
    """测试与旧入口默认值；生产必须注入 C5 的 resolve_run_limits。"""
    return RunLimits(max_pages=None, max_records=None)


class CollectorCall(Protocol):
    async def __call__(
        self,
        run: RunRecord,
        step: RunStepSpec,
        attempt_number: int,
        step_id: uuid.UUID,
        limits: RunLimits,
    ) -> CollectorCallReceipt: ...


class RunStepAttemptRepository(Protocol):
    async def add(self, attempt: RunStepAttemptWrite) -> None: ...

    async def finish(
        self,
        attempt_id: uuid.UUID,
        *,
        status: str,
        task_run_id: uuid.UUID | None,
        error_reason_code: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> None: ...
```

`RunStepSpec` 与 `RunStepSource` 从 `run_step_plan` 导入会形成循环。把这两个类移到本模块，`run_step_plan` 改为从本模块导入并重新导出 `RunStepSpec` 与 `RunStepSource`。同步更新两处 `__all__`。`RunBudget` 的唯一权威定义是 C5 的 `services/run_budget.py`；本模块不定义也不复制它，需要该类型的模块直接从 `services.run_budget` 导入或原样 re-export。`RunLimits` 从 C5 的 `services.run_limits` 导入；`StrEnum` 已从 `enum` 导入。

- [ ] **Step 4: 写 `run_step_runner.py`（单次 attempt）**

```python
"""单个 step 的执行单元。

每次 attempt 写一行 ``run_step_attempts`` 和一行账本。
最终写一行 ``run_steps``，只关联最终 attempt 的 ``task_runs``。
本模块只 flush，不 commit。
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Awaitable, Callable

from data_intelligence_hub.services.run_execution_contracts import (
    OUTCOME_FAILED,
    STEP_STATUS_BY_OUTCOME,
    CollectorCall,
    CollectorCallReceipt,
    RunLedgerRepository,
    RunLedgerWrite,
    RunAuditSink,
    RunLeaseLostError,
    RunRecord,
    RunStepAttemptRepository,
    RunStepAttemptStatus,
    RunStepAttemptWrite,
    RunStepSpec,
    RunStepWrite,
    resolve_outcome,
)
from data_intelligence_hub.services.run_limits import RunLimits
from data_intelligence_hub.services.run_retry import RetryPolicy

Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]
CancellationCheck = Callable[[], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class RunStepResult:
    step: RunStepWrite | None
    cancelled: bool = False


def _attempt_status(outcome: str) -> str:
    return {
        "success": RunStepAttemptStatus.SUCCESS.value,
        "empty": RunStepAttemptStatus.EMPTY.value,
        "config_gated": RunStepAttemptStatus.CONFIG_GATED.value,
        "failed": RunStepAttemptStatus.FAILED.value,
    }[outcome]


class RunStepRunner:
    def __init__(
        self,
        *,
        attempts: RunStepAttemptRepository,
        collector_call: CollectorCall,
        policy: RetryPolicy | None = None,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
        audit: RunAuditSink | None = None,
    ) -> None:
        self._attempts = attempts
        self._collector_call = collector_call
        self._policy = policy or RetryPolicy()
        self._sleep = sleep or asyncio.sleep
        self._clock = clock or (lambda: datetime.now(UTC))
        self._audit = audit

    async def run(
        self,
        run: RunRecord,
        spec: RunStepSpec,
        *,
        step_id: uuid.UUID,
        limits: RunLimits | None = None,
        lease_valid: Callable[[], bool] | None = None,
        is_cancelled: CancellationCheck | None = None,
    ) -> RunStepResult:
        lease_valid = lease_valid or _always_valid
        is_cancelled = is_cancelled or _never_cancelled
        limits = limits or RunLimits(max_pages=None, max_records=None)
        if await is_cancelled():
            return RunStepResult(step=None, cancelled=True)
        if not lease_valid():
            raise RunLeaseLostError(run.id, None, None)

        started_at = self._clock()
        attempt_id = uuid.uuid4()
        await self._attempts.add(
            RunStepAttemptWrite(
                id=attempt_id,
                run_id=run.id,
                step_index=spec.step_index,
                attempt_number=1,
                status=RunStepAttemptStatus.RUNNING.value,
                task_run_id=None,
                error_reason_code=None,
                error_message=None,
                started_at=started_at,
                finished_at=None,
                created_at=started_at,
            )
        )
        receipt = await self._collect(run, spec, 1, step_id=step_id, limits=limits)
        finished_at = self._clock()
        result = receipt.result
        if result is not None:
            outcome = resolve_outcome(result)
            attempt_status = _attempt_status(outcome)
            records_count = result.records_count
            error_message = result.error_message
            cost = result.total_cost_usd
            unit = result.unit
            quantity = result.quantity
            unit_price = result.unit_price
        else:
            outcome = OUTCOME_FAILED
            attempt_status = RunStepAttemptStatus.FAILED.value
            records_count = 0
            error_message = _error_text(receipt.error)
            cost = None
            unit = None
            quantity = None
            unit_price = None

        await self._attempts.finish(
            attempt_id,
            status=attempt_status,
            task_run_id=receipt.task_run_id,
            error_reason_code=None,
            error_message=error_message if outcome == OUTCOME_FAILED else None,
            finished_at=finished_at,
        )
        step = RunStepWrite(
            id=step_id,
            run_id=run.id,
            step_index=spec.step_index,
            endpoint_type=spec.endpoint_type or run.endpoint_type or "",
            collector_type=spec.collector_type or run.collector_type or "",
            task_run_id=receipt.task_run_id,
            status=STEP_STATUS_BY_OUTCOME[outcome],
            outcome=outcome,
            records_count=records_count,
            unit=unit,
            quantity=quantity,
            unit_price=unit_price,
            total_cost_usd=cost,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
            attempt_no=1,
            depends_on=spec.depends_on,
            tool_id=spec.endpoint_type or None,
        )
        return RunStepResult(step=step, cancelled=await is_cancelled())

    async def _collect(
        self,
        run: RunRecord,
        spec: RunStepSpec,
        attempt_number: int,
        *,
        step_id: uuid.UUID,
        limits: RunLimits,
    ) -> CollectorCallReceipt:
        try:
            return await self._collector_call(
                run,
                spec,
                attempt_number,
                step_id,
                limits,
            )
        except Exception as exc:
            return CollectorCallReceipt(result=None, task_run_id=None, error=exc)

def _error_text(exc: BaseException | None) -> str:
    if exc is None:
        return "collector_failed"
    return str(exc) or exc.__class__.__name__


async def _never_cancelled() -> bool:
    return False


def _always_valid() -> bool:
    return True


__all__ = ["RunStepResult", "RunStepRunner"]
```

- [ ] **Step 5: 重写 `RunExecutor.execute` 为多步骤**

在 `run_executor.py` 加入导入：

```python
import asyncio
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

from data_intelligence_hub.services.run_budget import RunBudget
from data_intelligence_hub.services.run_execution_contracts import (
    RunAuditSink,
    RunExecutionResult,
    RunLimitsResolver,
    RunStepAttemptRepository,
    RunStepSpec,
    RunStepWrite,
    unlimited_run_limits,
)
from data_intelligence_hub.services.run_retry import RetryPolicy
from data_intelligence_hub.services.run_step_plan import (
    DefaultRunStepSource,
    RunStepPlanError,
    RunStepSource,
    validate_step_specs,
)
from data_intelligence_hub.services.run_step_runner import RunStepRunner
```

把构造函数改为：

```python
    def __init__(
        self,
        *,
        runs: RunRepository,
        steps: RunStepRepository,
        unit_of_work: UnitOfWork,
        collector_call: CollectorCall,
        grade_calculator: GradeCalculator = compute_run_evidence_grade,
        grades: GradeRepository | None = None,
        attempts: RunStepAttemptRepository | None = None,
        step_source: RunStepSource | None = None,
        budget: RunBudget | None = None,
        limits: RunLimitsResolver | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        audit: RunAuditSink | None = None,
        completed_events: RunCompletedEventSink | None = None,
    ) -> None:
        self._runs = runs
        self._steps = steps
        self._unit_of_work = unit_of_work
        self._collector_call = collector_call
        self._grade_calculator = grade_calculator
        self._grades = grades
        self._attempts = attempts
        self._step_source = step_source or DefaultRunStepSource()
        self._budget = budget
        self._limits = limits or unlimited_run_limits
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep or asyncio.sleep
        self._audit = audit
        self._completed_events = completed_events
```

`RunRecord` 同时增加 `market_code: str | None`；`RunExecutor.__init__` 增加 `audit: RunAuditSink | None = None` 与 `completed_events: RunCompletedEventSink | None = None`。生产 bundle 只注入 `audit`；`completed_events` 保留为旧测试与旧调用方的兼容口。

把 `execute` 替换为下面的方法。删除旧 `_finish_failed` 与 `_build_ledger_entry`；C6 不写账本，结算由 C5 的 `RunBudget` 适配器完成。把旧单步 `_compute_grade(run, call)` 替换为下面的聚合版本。

```python
    async def execute(self, run_id: uuid.UUID) -> RunRecord:
        return (await self.execute_detailed(run_id)).run

    async def execute_detailed(
        self,
        run_id: uuid.UUID,
        *,
        lease_valid: Callable[[], bool] | None = None,
        checkpoint: Callable[[], Awaitable[None]] | None = None,
    ) -> RunExecutionResult:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if run.status == RUN_STATUS_CANCELLED:
            existing = await self._steps.list(run.id)
            return RunExecutionResult(run=run, steps=tuple(existing))
        if run.status not in (RUN_STATUS_QUEUED, RUN_STATUS_RUNNING):
            raise InvalidRunTransitionError(run_id, run.status)
        if self._attempts is None:
            raise RuntimeError("RunExecutor 需要 attempts 仓储")

        lease_valid = lease_valid or _always_valid
        checkpoint = checkpoint or _noop_checkpoint
        started_at = datetime.now(UTC)

        if self._budget is not None:
            try:
                await self._budget.reserve(run)
            except BudgetApprovalRequiredError as exc:
                if getattr(exc, "scope", None) == "blocked_gate":
                    # blocked 市场保持 queued；不得写成 failed。
                    run.status = RUN_STATUS_QUEUED
                    await self._runs.save(run)
                    return RunExecutionResult(run=run, steps=())
                await self._mark_failed(run, str(exc) or exc.__class__.__name__)
                await checkpoint()
                return RunExecutionResult(run=run, steps=())
            except Exception as exc:
                await self._mark_failed(run, str(exc) or exc.__class__.__name__)
                await checkpoint()
                return RunExecutionResult(run=run, steps=())

        run.status = RUN_STATUS_RUNNING
        if run.started_at is None:
            run.started_at = started_at
        await self._runs.save(run)
        await self._unit_of_work.flush()

        try:
            specs = await self._step_source(run)
            validate_step_specs(specs, require_collector=False)
        except RunStepPlanError as exc:
            if self._budget is not None:
                await self._budget.mark_unknown(run, reason="run_step_plan_invalid")
            await self._mark_failed(run, str(exc))
            await checkpoint()
            return RunExecutionResult(run=run, steps=())

        existing = {step.step_index: step for step in await self._steps.list(run.id)}
        runner = RunStepRunner(
            attempts=self._attempts,
            collector_call=self._collector_call,
            policy=self._retry_policy,
            sleep=self._sleep,
            audit=self._audit,
        )
        steps_by_index = dict(existing)
        limits = await self._limits(run)
        cancelled = False
        for spec in specs:
            if spec.step_index in steps_by_index:
                continue
            if cancelled or await self._is_cancelled(run.id):
                cancelled = True
                steps_by_index[spec.step_index] = self._skipped_step(
                    run.id,
                    spec,
                    "run_cancelled",
                )
                continue
            if not lease_valid():
                raise RunLeaseLostError(run.id, None, None)
            blocked_by = _dependency_blocked(spec, steps_by_index)
            if blocked_by is not None:
                steps_by_index[spec.step_index] = self._skipped_step(
                    run.id,
                    spec,
                    f"dependency_not_met:{blocked_by}",
                )
                continue
            step_id = uuid.uuid4()
            await self._steps.add(self._running_step(run.id, spec, step_id))
            result = await runner.run(
                run,
                spec,
                step_id=step_id,
                limits=limits,
                lease_valid=lease_valid,
                is_cancelled=lambda: self._is_cancelled(run.id),
            )
            if result.step is not None:
                await self._steps.update(result.step)
                steps_by_index[spec.step_index] = result.step
            else:
                skipped = self._skipped_step(
                    run.id,
                    spec,
                    "run_cancelled",
                    step_id=step_id,
                )
                await self._steps.update(skipped)
                steps_by_index[spec.step_index] = skipped
            if result.cancelled or await self._is_cancelled(run.id):
                cancelled = True
            elif not lease_valid():
                raise RunLeaseLostError(run.id, None, None)
            await checkpoint()

        ordered = [steps_by_index[index] for index in sorted(steps_by_index)]
        if cancelled or await self._is_cancelled(run.id):
            run.status = RUN_STATUS_CANCELLED
            return RunExecutionResult(run=run, steps=tuple(ordered))

        await self._finalize(run, ordered)
        await checkpoint()
        return RunExecutionResult(run=run, steps=tuple(ordered))
```

加入辅助方法：

```python
    async def _is_cancelled(self, run_id: uuid.UUID) -> bool:
        return await self._runs.status(run_id) == RUN_STATUS_CANCELLED

    async def _mark_failed(self, run: RunRecord, message: str) -> None:
        run.status = RUN_STATUS_FAILED
        run.outcome = OUTCOME_FAILED
        run.error_message = message
        run.records_count = 0
        run.evidence_grade = None
        run.finished_at = datetime.now(UTC)
        await self._runs.save(run)
        await self._unit_of_work.flush()
        await self._emit_audit(
            "run.failed",
            run,
            details={"error_message": message},
            result="failed",
        )

    async def _emit_audit(
        self,
        action: str,
        run: RunRecord,
        *,
        steps: tuple[RunStepWrite, ...] = (),
        details: dict[str, object] | None = None,
        result: str = "success",
    ) -> None:
        if self._audit is not None:
            await self._audit.record(
                action,
                run,
                steps=steps,
                details=details,
                result=result,
            )

    async def _finalize(
        self,
        run: RunRecord,
        steps: list[RunStepWrite],
    ) -> None:
        outcome = _aggregate_outcome(steps)
        run.status = RUN_STATUS_BY_OUTCOME[outcome]
        run.outcome = outcome
        run.records_count = sum(step.records_count for step in steps)
        # 最终 step 投影；C5 的 RunBudget.settle 用全部 attempt 的实际成本覆盖。
        run.total_cost_usd = sum(
            (step.total_cost_usd or Decimal("0") for step in steps),
            Decimal("0"),
        )
        run.error_message = _aggregate_error(steps)
        run.finished_at = datetime.now(UTC)
        if self._budget is not None:
            await self._settle_budget(run, steps)
        if outcome == OUTCOME_FAILED:
            run.evidence_grade = None
        else:
            grade = self._compute_grade(run, steps)
            await self._record_grade(grade)
            run.evidence_grade = grade.grade.value
        await self._runs.save(run)
        await self._unit_of_work.flush()
        if run.status == RUN_STATUS_COMPLETED:
            if self._audit is not None:
                # 统一审计：run.completed 也走 audit_events，只能一条。
                await self._audit.record(
                    "run.completed",
                    run,
                    steps=tuple(steps),
                )
            elif self._completed_events is not None:
                # 兼容旧测试与旧调用方；生产 bundle 不再注入该口。
                await self._completed_events(run, tuple(steps))
        else:
            await self._emit_audit(
                "run.failed",
                run,
                steps=tuple(steps),
                details={"error_message": run.error_message},
                result="failed",
            )

    async def _settle_budget(
        self,
        run: RunRecord,
        steps: list[RunStepWrite],
    ) -> None:
        """把整次 run 交给 C5 的 RunBudget。

        C6 不重复写账本，也不传金额。C5 的 settle_run_cost 汇总该 run
        全部 attempt 的 task_runs.total_cost_usd；失败 attempt 也计入。
        """
        final_step = steps[-1] if steps else None
        if final_step is None:
            await self._budget.mark_unknown(run, reason="no_steps")
            return
        # 即使 run 失败，也交给 C5 汇总全部 attempt 的成本；
        # 没有成本时 settle_run_cost 释放 quota 预留。
        await self._budget.settle(run, step_id=final_step.id)

    def _running_step(
        self,
        run_id: uuid.UUID,
        spec: RunStepSpec,
        step_id: uuid.UUID,
    ) -> RunStepWrite:
        now = datetime.now(UTC)
        return RunStepWrite(
            id=step_id,
            run_id=run_id,
            step_index=spec.step_index,
            endpoint_type=spec.endpoint_type,
            collector_type=spec.collector_type,
            task_run_id=None,
            status="running",
            outcome=None,
            records_count=0,
            unit=None,
            quantity=None,
            unit_price=None,
            total_cost_usd=None,
            error_message=None,
            started_at=now,
            finished_at=now,
            attempt_no=1,
            depends_on=spec.depends_on,
            tool_id=spec.endpoint_type or None,
        )

    def _skipped_step(
        self,
        run_id: uuid.UUID,
        spec: RunStepSpec,
        reason: str,
        *,
        step_id: uuid.UUID | None = None,
    ) -> RunStepWrite:
        now = datetime.now(UTC)
        return RunStepWrite(
            id=step_id or uuid.uuid4(),
            run_id=run_id,
            step_index=spec.step_index,
            endpoint_type=spec.endpoint_type,
            collector_type=spec.collector_type,
            task_run_id=None,
            status="skipped",
            outcome=None,
            records_count=0,
            unit=None,
            quantity=None,
            unit_price=None,
            total_cost_usd=None,
            error_message=reason,
            started_at=now,
            finished_at=now,
            attempt_no=1,
            depends_on=spec.depends_on,
            tool_id=spec.endpoint_type or None,
        )

    def _compute_grade(
        self,
        run: RunRecord,
        steps: list[RunStepWrite],
    ) -> RunEvidenceGrade:
        threshold = _threshold_for_run(run.template_id)
        # C6 不证明跨 step 的独立来源。source_count 固定为 1，
        # 避免把端点数量误算成独立来源并虚抬 L4。
        return self._grade_calculator(
            run_id=run.id,
            live_call=run.execution_mode != "fixture",
            authorization_id=run.authorization_id,
            sample_n=sum(step.records_count for step in steps),
            required_n=threshold.required_n,
            window_days=run.window_days,
            required_window_days=threshold.required_window_days,
            source_count=1 if any(step.records_count > 0 for step in steps) else 0,
            required_source_count=threshold.required_source_count,
            entity_count=0,
            required_entity_count=threshold.required_entity_count,
        )
```

加入模块级纯函数：

```python
def _aggregate_outcome(steps: list[RunStepWrite]) -> str:
    outcomes = [step.outcome for step in steps if step.outcome is not None]
    if OUTCOME_SUCCESS in outcomes:
        return OUTCOME_SUCCESS
    if OUTCOME_EMPTY in outcomes:
        return OUTCOME_EMPTY
    if OUTCOME_CONFIG_GATED in outcomes:
        return OUTCOME_CONFIG_GATED
    return OUTCOME_FAILED


def _aggregate_error(steps: list[RunStepWrite]) -> str | None:
    parts = [
        f"step {step.step_index}: {step.error_message}"
        for step in steps
        if step.outcome == OUTCOME_FAILED and step.error_message
    ]
    if not parts:
        return None
    return "; ".join(parts)[:4000]


def _dependency_blocked(
    spec: RunStepSpec,
    steps_by_index: dict[int, RunStepWrite],
) -> int | None:
    for dependency in spec.depends_on:
        step = steps_by_index.get(dependency)
        if step is None or step.outcome in (None, OUTCOME_FAILED):
            return dependency
    return None


def _always_valid() -> bool:
    return True


async def _noop_checkpoint() -> None:
    return None
```

- [ ] **Step 6: 发 `run.completed` 审计事件**

在 `tests/unit/test_run_completed_event.py` 写失败测试：

```python
"""C6 只发 run.completed 事件，不依赖 C8。"""

from __future__ import annotations

from pathlib import Path

import pytest

from data_intelligence_hub.services.run_executor import RunExecutor
from data_intelligence_hub.services.run_step_plan import RunStepSpec
from tests.unit.run_executor_fakes import (
    FakeAttemptRepository,
    FakeCollectorCall,
    FakeGradeRepository,
    FakeRun,
    FakeRunRepository,
    FakeStepRepository,
    FakeStepSource,
    FakeUnitOfWork,
    success_result,
)


def test_executor_does_not_import_c8_quality_modules() -> None:
    source = Path("src/data_intelligence_hub/services/run_executor.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "dataset_quality",
        "market_quality",
        "evaluate_and_persist_market_quality",
        "ensure_market_quality",
    ):
        assert forbidden not in source


def _executor(
    run: FakeRun,
    *,
    results: list,
    completed_events,
) -> RunExecutor:
    return RunExecutor(
        runs=FakeRunRepository(run),
        steps=FakeStepRepository(),
        unit_of_work=FakeUnitOfWork(),
        collector_call=FakeCollectorCall(results),
        attempts=FakeAttemptRepository(),
        step_source=FakeStepSource(
            [
                RunStepSpec(
                    step_index=0,
                    endpoint_type="generic_web",
                    collector_type="generic_web",
                    task_id=run.task_id,
                )
            ]
        ),
        grades=FakeGradeRepository(),
        completed_events=completed_events,
    )


@pytest.mark.anyio
async def test_completed_run_emits_one_event() -> None:
    run = FakeRun(market_code="US")
    events: list[tuple[object, tuple[int, ...]]] = []

    async def sink(record, steps) -> None:
        events.append((record.id, tuple(step.step_index for step in steps)))

    executor = _executor(
        run,
        results=[success_result(records_count=3)],
        completed_events=sink,
    )

    result = await executor.execute_detailed(run.id)

    assert result.run.status == "completed"
    assert events == [(run.id, (0,))]


@pytest.mark.anyio
async def test_failed_run_emits_no_completed_event() -> None:
    run = FakeRun(market_code="US")
    events: list[object] = []

    async def sink(record, steps) -> None:
        events.append(record.id)

    executor = _executor(
        run,
        results=[success_result(status="failed", outcome="failed", error_message="bad")],
        completed_events=sink,
    )

    result = await executor.execute_detailed(run.id)

    assert result.run.status == "failed"
    assert events == []


@pytest.mark.anyio
async def test_cancelled_run_emits_no_completed_event() -> None:
    run = FakeRun(market_code="US", status="cancelled")
    events: list[object] = []

    async def sink(record, steps) -> None:
        events.append(record.id)

    executor = _executor(
        run,
        results=[],
        completed_events=sink,
    )

    result = await executor.execute_detailed(run.id)

    assert result.run.status == "cancelled"
    assert events == []
```
Expected: 新测试 FAIL（执行器还没有 sink）。实现后，`RunCompletedEventSink` 在 `execute_detailed` 的 `_finalize` 内、`runs.save` 与 `flush` 之后调用一次；只有 `run.status == "completed"` 才调用。`failed` 与 `cancelled` 路径不调用。载荷只来自 `RunRecord` 与 `RunStepWrite`，不得查询 C8 表。

Run:
```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_completed_event.py -q
```
Expected: 通过；`events` 恰好一条；失败与取消用例为零条。生产 bundle 注入 `audit=OrmRunAuditSink(session)`，不再注入 `completed_events`；后者只保留给本测试的兼容路径。

- [ ] **Step 6A: 统一生命周期审计测试**

新建 `tests/unit/test_run_audit_events.py`：

```python
"""run 生命周期统一审计测试。

`run.created` 由 C4 `services/run_creation.create_run_with_audit` 接缝发出。
C6 的六类动作分别由 step runner、取消服务与执行器发出。
本文件验证执行器终态动作与一次性；其余动作在各自任务的测试中覆盖。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.services.run_executor import RunExecutor
from data_intelligence_hub.services.run_step_plan import RunStepSpec
from tests.unit.run_executor_fakes import (
    FakeAttemptRepository,
    FakeCollectorCall,
    FakeGradeRepository,
    FakeRun,
    FakeRunRepository,
    FakeStepRepository,
    FakeStepSource,
    FakeUnitOfWork,
    success_result,
)


class FakeAuditSink:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record(self, action, run, *, steps=(), details=None, result="success"):
        self.events.append(
            {
                "action": action,
                "result": result,
                "details": dict(details or {}),
                "step_indexes": [step.step_index for step in steps],
            }
        )


def _executor(run: FakeRun, *, results: list, audit: FakeAuditSink) -> RunExecutor:
    return RunExecutor(
        runs=FakeRunRepository(run),
        steps=FakeStepRepository(),
        unit_of_work=FakeUnitOfWork(),
        collector_call=FakeCollectorCall(results),
        attempts=FakeAttemptRepository(),
        step_source=FakeStepSource(
            [
                RunStepSpec(
                    step_index=0,
                    endpoint_type="generic_web",
                    collector_type="generic_web",
                    task_id=run.task_id,
                )
            ]
        ),
        grades=FakeGradeRepository(),
        audit=audit,
    )


@pytest.mark.anyio
async def test_completed_run_emits_exactly_one_run_completed() -> None:
    run = FakeRun(market_code="US")
    audit = FakeAuditSink()

    result = await _executor(
        run,
        results=[success_result(records_count=3)],
        audit=audit,
    ).execute_detailed(run.id)

    assert result.run.status == "completed"
    assert [event["action"] for event in audit.events] == ["run.completed"]
    assert audit.events[0]["step_indexes"] == [0]
    assert audit.events[0]["result"] == "success"


@pytest.mark.anyio
async def test_failed_run_emits_run_failed_not_completed() -> None:
    run = FakeRun(market_code="US")
    audit = FakeAuditSink()

    result = await _executor(
        run,
        results=[success_result(status="failed", outcome="failed", error_message="bad")],
        audit=audit,
    ).execute_detailed(run.id)

    assert result.run.status == "failed"
    assert [(event["action"], event["result"]) for event in audit.events] == [
        ("run.failed", "failed"),
    ]


@pytest.mark.anyio
async def test_cancelled_run_emits_no_terminal_audit() -> None:
    run = FakeRun(market_code="US", status="cancelled")
    audit = FakeAuditSink()

    result = await _executor(run, results=[], audit=audit).execute_detailed(run.id)

    assert result.run.status == "cancelled"
    assert audit.events == []
```

Expected: 三个用例通过。`run.created` 由 C4 接缝与 Task 10 验证，`run.retry_scheduled` / `run.retry_exhausted` 由 Task 7 验证，`run.cancel_requested` / `run.cancelled` 由 Task 9 验证。

- [ ] **Step 7: 改 `RunCollectorCall` 为回执式**

C5 已在 `RunCollectorCall` 中写入 `tool_calls`。保留 `start_tool_call` 与 `complete_tool_call`，把幂等键改为 `run:{run.id}:step:{step.step_index}:attempt:{attempt_number}:collector-call`；`tool_calls.step_id` 写逻辑 step 的 `run_steps.id`，不再写 `None`。

C5 run limits 消费：`RunExecutor` 在每次 attempt 前通过 `RunLimitsResolver` 调用 C5 `resolve_run_limits(session, run_id=run.id)`，把 `RunLimits` 作为 `limits` 参数传入 `CollectorCall`。`RunCollectorCall.__call__` 与 `execute_collector_call` 接收 `max_pages` / `max_records`：每次翻页前调用 `limits.check_pages(pages_done)`，每页入库后调用 `limits.check_records(records_done)`；`None` 原样透传，`0` 表示零容忍。`RunLimitExceededError` 不重试、不吞掉，记录为 attempt 失败并立即停止；不得继续请求下一页或写剩余记录。

把导入改为：

```python
from data_intelligence_hub.services.run_execution_contracts import (
    CollectorCallReceipt,
    RunRecord,
    RunStepSpec,
)
from data_intelligence_hub.services.run_limits import RunLimits
from data_intelligence_hub.services.tool_call_service import (
    complete_tool_call,
    start_tool_call,
)
```

替换 `__call__` 与 `_mark_failed`。在 `task_run` flush 后保留 C5 的 `start_tool_call`；成功与异常分支保留对应的 `complete_tool_call`。每个 run 只处理自己的 `run.market_code`；`CollectionTask.config` 是模板，不得把一个市场的查询结果复用到另一个市场。只把 `execute_collector_call` 的结果改成回执：

```python
    async def __call__(
        self,
        run: RunRecord,
        step: RunStepSpec,
        attempt_number: int,
        step_id: uuid.UUID,
        limits: RunLimits,
    ) -> CollectorCallReceipt:
        workspace_id = _required_uuid(run, "workspace_id")
        task_id = step.task_id or _required_uuid(run, "task_id")
        workspace = await self._session.get(Workspace, workspace_id)
        if workspace is None:
            return CollectorCallReceipt(
                result=None,
                task_run_id=None,
                error=RuntimeError(f"工作区不存在：{workspace_id}"),
            )
        task = await self._session.scalar(
            select(CollectionTask).where(
                CollectionTask.id == task_id,
                CollectionTask.workspace_id == workspace_id,
            )
        )
        if task is None:
            return CollectorCallReceipt(
                result=None,
                task_run_id=None,
                error=RuntimeError(f"采集任务不存在：{task_id}"),
            )

        task = await _lock_task_for_run_or_raise(self._session, workspace, task)
        self._previous_task_status[task.id] = task.status
        task.status = "running"
        started_at = self._clock()
        timeout_seconds = _collection_timeout_seconds(task.config)
        logs: list[dict[str, Any]] = [
            collector_log(
                "task_run_created",
                (
                    f"Collection requested by {self._trigger}; "
                    f"step={step.step_index} attempt={attempt_number}."
                ),
            ),
            collector_log(
                "collector_execution_started",
                f"Starting collector {task.collector_type}.",
            ),
            collector_log(
                "collector_timeout_configured",
                f"Collector run timeout set to {timeout_seconds:g}s.",
            ),
        ]
        task_run = TaskRun(
            task_id=task.id,
            workspace_id=workspace.id,
            status="running",
            started_at=started_at,
            finished_at=None,
            records_count=0,
            entities_count=0,
            error_message=None,
            error_traceback=None,
            logs=logs,
            created_at=started_at,
            project_id=task.project_id,
            run_id=run.id,
            step_index=step.step_index,
        )
        self._session.add(task_run)
        await self._session.flush()
        self._task_run_ids[(run.id, step.step_index, attempt_number)] = task_run.id
        endpoint_type = _endpoint_type(task.config) or task.collector_type
        tool_call = await start_tool_call(
            self._session,
            workspace_id=workspace.id,
            project_id=task.project_id,
            run_id=run.id,
            step_id=step_id,
            tool_id=endpoint_type,
            contract_version="run_collector.v1",
            idempotency_key=(
                f"run:{run.id}:step:{step.step_index}:"
                f"attempt:{attempt_number}:collector-call"
            ),
            request_payload={
                "task_id": str(task.id),
                "endpoint_type": endpoint_type,
                "trigger": self._trigger,
            },
            backend_ref_type="task_run",
            backend_ref_id=task_run.id,
            started_at=started_at,
        )

        try:
            async with self._session.begin_nested():
                result = await execute_collector_call(
                    session=self._session,
                    workspace=workspace,
                    task=task,
                    task_run=task_run,
                    trigger=self._trigger,
                    timeout_seconds=timeout_seconds,
                    max_pages=limits.max_pages,
                    max_records=limits.max_records,
                    logs=logs,
                )
        except Exception as exc:
            await self._mark_failed(task_run, task, exc, logs)
            await complete_tool_call(
                self._session,
                call_id=tool_call.id,
                outcome="failed",
                task_run_id=task_run.id,
                finished_at=self._clock(),
            )
            return CollectorCallReceipt(
                result=None,
                task_run_id=task_run.id,
                error=exc,
            )

        await self._mark_finished(task_run, task, result, logs)
        await complete_tool_call(
            self._session,
            call_id=tool_call.id,
            outcome=_tool_call_outcome(result.status),
            task_run_id=task_run.id,
            quantity=result.quantity,
            unit=result.unit,
            unit_price=result.unit_price,
            total_cost_usd=result.total_cost_usd,
            finished_at=self._clock(),
        )
        return CollectorCallReceipt(
            result=result,
            task_run_id=task_run.id,
            error=None,
        )


def _tool_call_outcome(status: str) -> str:
    if status in {"success", "partial_success"}:
        return "success"
    if status == "empty":
        return "empty"
    if status == "config_gated":
        return "config_gated"
    return "failed"
```

在 `_mark_failed` 末尾删除 `raise`。把 `_task_run_ids` 类型改为 `dict[tuple[uuid.UUID, int, int], uuid.UUID]`。`mirror_evidence_grade` 保留现有回退查询。

- [ ] **Step 8: 更新旧测试替身与断言**

- `test_run_executor.py` 改为从 `tests.unit.run_executor_fakes` 导入替身。`FakeCollectorCall` 改为按顺序返回 `CollectionCallReceipt`。
- `test_run_collector_call_guard.py` 改为：

```python
from data_intelligence_hub.services.run_limits import RunLimits
from data_intelligence_hub.services.run_step_plan import RunStepSpec

step = RunStepSpec(
    step_index=0,
    endpoint_type="tikhub_tiktok_search_web",
    collector_type="tikhub_social",
    task_id=task_id,
)
receipt = await RunCollectorCall(session)(
    run,
    step,
    1,
    uuid.uuid4(),
    RunLimits(max_pages=None, max_records=None),
)
assert isinstance(receipt.error, TaskNotRunnableError)
```

- `test_run_worker_runtime.py` 的 `FakeCollectorCall.__call__` 改为 `(run, step, attempt_number)`，返回 `CollectorCallReceipt`。

- [ ] **Step 9: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_executor.py tests/unit/test_run_executor_multi_step.py tests/unit/test_run_collector_call_guard.py tests/unit/test_run_worker_runtime.py -q
```

Expected: 全部通过。

- [ ] **Step 10: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs impact "RunExecutor" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_execution_contracts.py \
  apps/api/src/data_intelligence_hub/services/run_step_runner.py \
  apps/api/src/data_intelligence_hub/services/run_executor.py \
  apps/api/src/data_intelligence_hub/services/run_collector_call.py \
  apps/api/tests/unit/run_executor_fakes.py \
  apps/api/tests/unit/test_run_executor.py \
  apps/api/tests/unit/test_run_executor_multi_step.py \
  apps/api/tests/unit/test_run_collector_call_guard.py \
  apps/api/tests/unit/test_run_worker_runtime.py
git commit -m "feat(run): execute multi-step runs with per-attempt records"
```

---

### Task 6: ORM 适配器与生产装配

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/run_execution_contracts.py`
- Create: `apps/api/src/data_intelligence_hub/services/run_audit.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_executor_adapters.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_worker_runtime.py`
- Test: `apps/api/tests/unit/test_run_executor_orm.py`
- Test: `apps/api/tests/unit/test_run_worker_runtime.py`
- Test: `apps/api/tests/unit/test_run_audit_events.py`

**Interfaces:**
- Produces: `OrmRunStepAttemptRepository`、`OrmRunStepRepository.list`、`OrmRunRepository.status`、`OrmRunRecord.execution_mode`、`OrmRunRecord.total_cost_usd`、`OrmRunRecord.market_code`、`OrmRunAuditSink`（`OrmRunCompletedEventSink` 为兼容别名）、`OrmRunLimitsResolver`、`services.run_audit.audit_run_event`。
- `OrmRunLimitsResolver` 调用 C5 `resolve_run_limits(self._session, run_id=run.id)`，把 `RunLimits` 原样交给执行器；不得在 C6 重新解析 `workbench_tasks.max_pages` / `max_records`。
- `build_run_executor_bundle` 必须注入 `OrmRunStepSource`、`OrmRunStepAttemptRepository`、`OrmRunAuditSink` 与 `OrmRunLimitsResolver`。

- [ ] **Step 1: 写失败测试**

```python
"""ORM 装配测试。验证 run、step、attempt 与账本一起落库。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run, RunStep, RunStepAttempt
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.collector_service import CollectionCallResult
from data_intelligence_hub.services.run_execution_contracts import CollectorCallReceipt
from data_intelligence_hub.services.run_worker_runtime import build_run_executor_bundle


@pytest_asyncio.fixture()
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with factory() as session:
        user = User(email="orm@example.com", password_hash="x", name="Owner")
        session.add(user)
        await session.flush()
        workspace = Workspace(name="ORM", slug="orm-ws", owner_id=user.id)
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="ORM Project",
            domain="ecommerce",
            owner_id=user.id,
        )
        session.add(project)
        await session.flush()
        source = Source(
            workspace_id=workspace.id,
            project_id=project.id,
            name="ORM Source",
            type="manual_json",
            config={"endpoint_type": "manual_json"},
        )
        session.add(source)
        await session.flush()
        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=project.id,
            source_id=source.id,
            collector_type="manual_json",
            name="ORM Task",
            status="enabled",
            config={"endpoint_type": "manual_json"},
        )
        session.add(task)
        await session.flush()
        run = Run(
            workspace_id=workspace.id,
            project_id=project.id,
            task_id=task.id,
            status="queued",
            execution_mode="live",
            trigger="manual",
            records_count=0,
        )
        session.add(run)
        await session.commit()
        return workspace.id, project.id, run.id


async def test_bundle_writes_step_attempt_and_ledger(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    _, _, run_id = await _seed(factory)

    class FakeCall:
        async def __call__(self, run, step, attempt_number, step_id=None, limits=None):
            return CollectorCallReceipt(
                result=CollectionCallResult(
                    status="success",
                    records_count=3,
                    entities_count=1,
                    sample_n=3,
                    source_count=1,
                    window_days=7,
                    collector_type="manual_json",
                    endpoint_type="manual_json",
                    total_cost_usd=Decimal("0.5"),
                ),
                task_run_id=None,
                error=None,
            )

    async with factory() as session:
        bundle = build_run_executor_bundle(session, collector_call=FakeCall())
        result = await bundle.executor.execute_detailed(run_id, checkpoint=session.commit)
        await session.commit()
        assert result.run.status == "completed"
        step_count = await session.scalar(
            select(func.count()).select_from(RunStep).where(RunStep.run_id == run_id)
        )
        attempt_count = await session.scalar(
            select(func.count()).select_from(RunStepAttempt)
        )
        assert int(step_count or 0) == 1
        assert int(attempt_count or 0) == 1


async def test_bundle_uses_injected_budget_instead_of_local_ledger(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    _, _, run_id = await _seed(factory)
    observed: dict[str, object] = {"reserved": 0, "settled": 0, "ledger": 0}

    class FakeBudget:
        async def reserve(self, run) -> None:
            observed["reserved"] = int(observed["reserved"]) + 1

        async def settle(self, run, *, step_id=None) -> None:
            observed["settled"] = int(observed["settled"]) + 1

        async def mark_unknown(self, run, reason: str = "collector_exception") -> None:
            raise AssertionError(reason)

        async def cancel(self, run) -> None:
            raise AssertionError("cancel")

    class FakeCall:
        async def __call__(self, run, step, attempt_number, step_id=None, limits=None):
            return CollectorCallReceipt(
                result=CollectionCallResult(
                    status="success",
                    records_count=3,
                    entities_count=1,
                    sample_n=3,
                    source_count=1,
                    window_days=7,
                    collector_type="manual_json",
                    endpoint_type="manual_json",
                    total_cost_usd=Decimal("0.5"),
                ),
                task_run_id=None,
                error=None,
            )

    async with factory() as session:
        bundle = build_run_executor_bundle(
            session,
            collector_call=FakeCall(),
            budget=FakeBudget(),
        )
        await bundle.executor.execute_detailed(run_id, checkpoint=session.commit)
        await session.commit()
        observed["ledger"] = await session.scalar(
            select(func.count()).select_from(RunLedgerEntry)
        )

    assert observed == {"reserved": 1, "settled": 1, "ledger": 0}
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_executor_orm.py -q
```

Expected: FAIL。`build_run_executor_bundle` 没有注入 attempt 仓储与步骤来源，执行器报 “需要 attempts 仓储”。

- [ ] **Step 3: 实现 ORM 仓储**

把现有 `OrmRunStepRepository` 替换为下面的类。保留现有 `__init__` 与 `add`，新增 `list`。

```python
class OrmRunStepRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, run_id: uuid.UUID) -> list[RunStepWrite]:
        result = await self._session.execute(
            select(RunStep)
            .where(RunStep.run_id == run_id)
            .order_by(RunStep.step_index)
        )
        return [self._to_write(row) for row in result.scalars().all()]

    async def add(self, step: RunStepWrite) -> None:
        self._session.add(self._to_row(step))
        await self._session.flush()

    async def update(self, step: RunStepWrite) -> None:
        await self._session.execute(
            update(RunStep)
            .where(RunStep.id == step.id)
            .values(
                task_run_id=step.task_run_id,
                status=step.status,
                outcome=step.outcome,
                records_count=step.records_count,
                unit=step.unit,
                quantity=step.quantity,
                unit_price=step.unit_price,
                total_cost_usd=step.total_cost_usd,
                error_message=step.error_message,
                started_at=step.started_at,
                finished_at=step.finished_at,
                attempt_no=step.attempt_no,
                depends_on=list(step.depends_on),
                tool_id=step.tool_id,
                provider_run_id=step.provider_run_id,
                idempotency_key_hash=step.idempotency_key_hash,
                evidence_grade=step.evidence_grade,
                stage=step.stage,
            )
        )
        await self._session.flush()

    @staticmethod
    def _to_row(step: RunStepWrite) -> RunStep:
        return RunStep(
            id=step.id,
            run_id=step.run_id,
            step_index=step.step_index,
            endpoint_type=step.endpoint_type,
            collector_type=step.collector_type,
            task_run_id=step.task_run_id,
            status=step.status,
            outcome=step.outcome,
            records_count=step.records_count,
            unit=step.unit,
            quantity=step.quantity,
            unit_price=step.unit_price,
            total_cost_usd=step.total_cost_usd,
            error_message=step.error_message,
            started_at=step.started_at,
            finished_at=step.finished_at,
            attempt_no=step.attempt_no,
            depends_on=list(step.depends_on),
            tool_id=step.tool_id,
            provider_run_id=step.provider_run_id,
            idempotency_key_hash=step.idempotency_key_hash,
            evidence_grade=step.evidence_grade,
            stage=step.stage,
        )

    @staticmethod
    def _to_write(row: RunStep) -> RunStepWrite:
        return RunStepWrite(
            id=row.id,
            run_id=row.run_id,
            step_index=row.step_index,
            endpoint_type=row.endpoint_type,
            collector_type=row.collector_type,
            task_run_id=row.task_run_id,
            status=row.status,
            outcome=row.outcome,
            records_count=row.records_count,
            unit=row.unit,
            quantity=row.quantity,
            unit_price=row.unit_price,
            total_cost_usd=row.total_cost_usd,
            error_message=row.error_message,
            started_at=row.started_at or datetime.now(UTC),
            finished_at=row.finished_at or datetime.now(UTC),
            attempt_no=row.attempt_no or 1,
            depends_on=tuple(row.depends_on or ()),
            tool_id=row.tool_id,
            provider_run_id=row.provider_run_id,
            idempotency_key_hash=row.idempotency_key_hash,
            evidence_grade=row.evidence_grade,
            stage=row.stage,
        )


class OrmRunStepAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, attempt: RunStepAttemptWrite) -> None:
        self._session.add(
            RunStepAttempt(
                id=attempt.id,
                run_id=attempt.run_id,
                step_index=attempt.step_index,
                attempt_number=attempt.attempt_number,
                status=attempt.status,
                task_run_id=attempt.task_run_id,
                error_reason_code=attempt.error_reason_code,
                error_message=attempt.error_message,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
                created_at=attempt.created_at,
            )
        )
        await self._session.flush()

    async def finish(
        self,
        attempt_id: uuid.UUID,
        *,
        status: str,
        task_run_id: uuid.UUID | None,
        error_reason_code: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> None:
        result = await self._session.execute(
            update(RunStepAttempt)
            .where(
                RunStepAttempt.id == attempt_id,
                RunStepAttempt.status == "running",
            )
            .values(
                status=status,
                task_run_id=task_run_id,
                error_reason_code=error_reason_code,
                error_message=error_message,
                finished_at=finished_at,
            )
        )
        await self._session.flush()
        if int(getattr(result, "rowcount", 0)) == 0:
            raise ValueError(f"attempt 不是 running：{attempt_id}")
```

给 `OrmRunRepository` 加：

```python
    async def status(self, run_id: uuid.UUID) -> str | None:
        return await self._session.scalar(select(Run.status).where(Run.id == run_id))
```

给 `OrmRunRecord` 加属性：

```python
    @property
    def execution_mode(self) -> str:
        return self._row.execution_mode

    @property
    def total_cost_usd(self) -> Decimal | None:
        return self._row.total_cost_usd

    @total_cost_usd.setter
    def total_cost_usd(self, value: Decimal | None) -> None:
        self._row.total_cost_usd = value

    @property
    def market_code(self) -> str | None:
        return self._row.market_code
```

`save` 在写入前同步总价，并在 `values` 中包含它。终态仍按 `run_steps` 汇总，避免执行器漏写：

```python
        row.total_cost_usd = run.total_cost_usd
        values: dict[str, object] = {
            "status": row.status,
            "outcome": row.outcome,
            "evidence_grade": row.evidence_grade,
            "error_message": row.error_message,
            "records_count": row.records_count,
            "total_cost_usd": row.total_cost_usd,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
```

账本符号校验与 `record_entry` 归 C5；C6 不修改 `services/run_ledger.py`、`repositories/run_ledger.py` 或 `tests/unit/test_run_ledger.py`。C6 的测试只断言：注入 `FakeBudget` 后不写 `run_ledger_entries`，生产 bundle 注入 `OrmRunBudget`。

先在 `services/run_audit.py` 实现唯一写入口：

```python
"""run 生命周期统一审计。

唯一审计表是 C2 的 ``audit_events``；唯一写入口是 ``append_audit_event``。
本模块不 import C8 质量模块，也不写第二张审计表。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.services.audit_log import append_audit_event

# C6 只写六类动作；run.created 的 owner 是 C4，
# 由 C4 services.run_creation.create_run_with_audit 接缝写入。
RUN_AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "run.cancel_requested",
        "run.cancelled",
        "run.retry_scheduled",
        "run.retry_exhausted",
        "run.completed",
        "run.failed",
    }
)


async def audit_run_event(
    session: AsyncSession,
    *,
    action: str,
    run: Any,
    steps: tuple[Any, ...] = (),
    details: dict[str, object] | None = None,
    result: str = "success",
) -> None:
    """追加一条 run 审计事件。动作名必须已在 C1 registry 登记。"""
    if action not in RUN_AUDIT_ACTIONS:
        raise ValueError(f"unregistered run audit action: {action}")
    payload: dict[str, object] = {
        "run_id": str(run.id),
        "collection_task_id": str(run.task_id) if run.task_id else None,
        "workflow_version_id": (
            str(run.workflow_version_id)
            if run.workflow_version_id is not None
            else None
        ),
        "run_status": run.status,
        "outcome": run.outcome,
    }
    if action == "run.completed":
        payload.update(
            {
                "market_code": run.market_code,
                "records_count": run.records_count,
                "finished_at": (
                    run.finished_at.isoformat()
                    if run.finished_at is not None
                    else None
                ),
                "step_indexes": [step.step_index for step in steps],
            }
        )
    payload.update(details or {})
    await append_audit_event(
        session,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        actor_type="system",
        action=action,
        resource_type="run",
        resource_id=str(run.id),
        result=result,
        details=payload,
    )


__all__ = ["RUN_AUDIT_ACTIONS", "audit_run_event"]
```

在 `run_executor_adapters.py` 实现 sink：

```python
class OrmRunAuditSink:
    """把 run 生命周期写成 C2 的统一审计事件。

    生产只注入本类。``__call__`` 保留 `run.completed` 兼容口；
    ``record`` 承载六类 C6 动作；`run.created` 由 C4 接缝写。不计算质量，不 import C8。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(
        self,
        run: RunRecord,
        steps: tuple[RunStepWrite, ...],
    ) -> None:
        await self.record("run.completed", run, steps=steps)

    async def record(
        self,
        action: str,
        run: RunRecord,
        *,
        steps: tuple[RunStepWrite, ...] = (),
        details: dict[str, object] | None = None,
        result: str = "success",
    ) -> None:
        await audit_run_event(
            self._session,
            action=action,
            run=run,
            steps=steps,
            details=details,
            result=result,
        )


# 兼容旧计划与旧测试中的名字。
OrmRunCompletedEventSink = OrmRunAuditSink


class OrmRunLimitsResolver:
    """只调用 C5 的 resolve_run_limits，不在 C6 重新解析 workbench_tasks。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __call__(self, run: RunRecord) -> RunLimits:
        return await resolve_run_limits(self._session, run_id=run.id)
```

在 `run_executor_adapters.py` 导入：

```python
from data_intelligence_hub.services.run_audit import audit_run_event
from data_intelligence_hub.services.run_limits import RunLimits, resolve_run_limits
```

- [ ] **Step 4: 装配生产执行器**

在 `run_worker_runtime.py` 的 `build_run_executor_bundle` 中：

```python
from data_intelligence_hub.services.run_budget import OrmRunBudget, RunBudget
from data_intelligence_hub.services.run_executor_adapters import (
    OrmGradeRepository,
    OrmRunAuditSink,
    OrmRunLimitsResolver,
    OrmRunRepository,
    OrmRunStepAttemptRepository,
    OrmRunStepRepository,
    SessionUnitOfWork,
)
from data_intelligence_hub.services.run_step_plan import OrmRunStepSource
...
def build_run_executor_bundle(
    session: AsyncSession,
    *,
    collector_call: CollectorCall | None = None,
    grade_calculator: GradeCalculator | None = None,
    budget: RunBudget | None = None,
) -> RunExecutorBundle:
    ...
    executor = RunExecutor(
        runs=cast("RunRepository", runs),
        steps=OrmRunStepRepository(session),
        grades=OrmGradeRepository(session),
        unit_of_work=SessionUnitOfWork(session),
        collector_call=call,
        attempts=OrmRunStepAttemptRepository(session),
        step_source=OrmRunStepSource(session),
        budget=budget,
        limits=OrmRunLimitsResolver(session),
        audit=OrmRunAuditSink(session),
        **grade_options,
    )
```

`RunWorkerRuntime._handle` 调用时传入生产预算适配器：

```python
            bundle = build_run_executor_bundle(
                session,
                collector_call=call,
                grade_calculator=self._grade_calculator,
                budget=OrmRunBudget(session),
            )
```

`test_run_worker_runtime.py` 的 `_seed_context` 默认端点从 `mock_endpoint` 改为 `generic_web`，`_make_result()` 的 `endpoint_type` 也改为 `generic_web`。否则 C5 的 `OrmRunBudget` 会因价格簿缺少 `mock_endpoint` 抛 `tool_not_priced`。测试仍用注入的 collector 替身，不联网。

- [ ] **Step 5: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_executor_orm.py tests/unit/test_run_executor.py tests/unit/test_run_worker_runtime.py tests/unit/test_run_lease_fence.py tests/unit/test_run_audit_events.py -q
```

Expected: 全部通过。worker 成功路径现在同时写 `run_steps` 与 `run_step_attempts`。

- [ ] **Step 6: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_execution_contracts.py \
  apps/api/src/data_intelligence_hub/services/run_audit.py \
  apps/api/src/data_intelligence_hub/services/run_executor_adapters.py \
  apps/api/src/data_intelligence_hub/services/run_worker_runtime.py \
  apps/api/tests/unit/test_run_executor_orm.py \
  apps/api/tests/unit/test_run_worker_runtime.py \
  apps/api/tests/unit/test_run_audit_events.py
git commit -m "feat(run): wire ORM step and attempt repositories"
```

---

### Task 7: 瞬态重试与 attempt 循环

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/run_step_runner.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_executor.py`
- Test: `apps/api/tests/unit/test_run_step_runner.py`
- Test: `apps/api/tests/unit/test_run_executor_multi_step.py`
- Test: `apps/api/tests/unit/test_run_audit_events.py`

**Interfaces:**
- Consumes: `RetryPolicy`（Task 2）、`RunAuditSink`（Task 4）。
- Produces: `RunStepRunner.run(..., lease_valid=None, is_cancelled=None)`。每次 attempt 一行 attempt。最终 step 的成本是各 attempt 成本之和，记录数取最终 attempt。瞬态失败且还会重试时写 `run.retry_scheduled`；最后一次瞬态失败写 `run.retry_exhausted`；非瞬态失败不写重试事件。

- [ ] **Step 1: 写失败测试**

```python
"""Step runner 的 attempt 与重试测试。"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from data_intelligence_hub.services.collector_service import CollectionCallResult
from data_intelligence_hub.collectors.outbound_policy import CollectionPolicyDenied
from data_intelligence_hub.services.run_execution_contracts import (
    CollectorCallReceipt,
    RunLeaseLostError,
)
from data_intelligence_hub.services.run_retry import RetryPolicy
from data_intelligence_hub.services.run_step_plan import RunStepSpec
from data_intelligence_hub.services.run_step_runner import RunStepRunner
from tests.unit.run_executor_fakes import (
    FakeAttemptRepository,
    FakeLedgerRepository,
    FakeRun,
)


class SequencedCall:
    def __init__(self, steps: list[CollectorCallReceipt | BaseException]) -> None:
        self._steps = list(steps)
        self.calls: list[int] = []

    async def __call__(self, run, step, attempt_number, step_id=None, limits=None):
        self.calls.append(attempt_number)
        item = self._steps.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class FakeSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class FakeAuditSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object], str]] = []

    async def record(self, action, run, *, steps=(), details=None, result="success"):
        self.events.append((action, dict(details or {}), result))


def _success(records: int = 5, cost: str = "0.5", task_run_id=None) -> CollectorCallReceipt:
    return CollectorCallReceipt(
        result=CollectionCallResult(
            status="success",
            records_count=records,
            entities_count=1,
            sample_n=records,
            source_count=1,
            window_days=7,
            collector_type="generic_web",
            endpoint_type="generic_web",
            total_cost_usd=Decimal(cost),
            task_run_id=task_run_id or uuid.uuid4(),
        ),
        task_run_id=task_run_id or uuid.uuid4(),
        error=None,
    )


def _failed(message: str, task_run_id=None) -> CollectorCallReceipt:
    return CollectorCallReceipt(
        result=CollectionCallResult(
            status="failed",
            records_count=0,
            entities_count=0,
            error_message=message,
            collector_type="generic_web",
            endpoint_type="generic_web",
            task_run_id=task_run_id or uuid.uuid4(),
        ),
        task_run_id=task_run_id or uuid.uuid4(),
        error=None,
    )


def _spec() -> RunStepSpec:
    return RunStepSpec(0, "generic_web", "generic_web", uuid.uuid4())


def _runner(call: SequencedCall, sleep: FakeSleep | None = None):
    attempts = FakeAttemptRepository()
    runner = RunStepRunner(
        attempts=attempts,
        collector_call=call,
        sleep=sleep or FakeSleep(),
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=2.0, max_delay_seconds=30.0),
    )
    return runner, attempts


async def test_transient_failure_retries_then_succeeds() -> None:
    sleep = FakeSleep()
    runner, attempts = _runner(
        SequencedCall([TimeoutError("timeout"), _success()]),
        sleep,
    )

    result = await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4())

    assert result.step is not None
    assert result.step.status == "success"
    assert [item.status for item in attempts.attempts] == ["failed", "success"]
    assert [item.attempt_number for item in attempts.attempts] == [1, 2]
    assert sleep.delays == [1.0, 1.0]
    assert sum(sleep.delays) == 2.0


async def test_non_transient_failure_is_not_retried() -> None:
    call = SequencedCall([CollectionPolicyDenied("blocked", code="robots")])
    runner, attempts = _runner(call)

    result = await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4())

    assert result.step is not None
    assert result.step.status == "failed"
    assert call.calls == [1]
    assert len(attempts.attempts) == 1


async def test_retry_budget_exhaustion_marks_step_failed() -> None:
    call = SequencedCall([
        TimeoutError("timeout-1"),
        TimeoutError("timeout-2"),
        TimeoutError("timeout-3"),
    ])
    runner, attempts = _runner(call)

    result = await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4())

    assert result.step is not None
    assert result.step.status == "failed"
    assert call.calls == [1, 2, 3]
    assert len(attempts.attempts) == 3


async def test_transient_retry_emits_scheduled_then_exhausted() -> None:
    audit = FakeAuditSink()
    attempts = FakeAttemptRepository()
    runner = RunStepRunner(
        attempts=attempts,
        collector_call=SequencedCall([
            TimeoutError("timeout-1"),
            TimeoutError("timeout-2"),
        ]),
        policy=RetryPolicy(max_attempts=2, base_delay_seconds=1.0),
        sleep=FakeSleep(),
        audit=audit,
    )

    result = await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4())

    assert result.step is not None
    assert result.step.status == "failed"
    assert [event[0] for event in audit.events] == [
        "run.retry_scheduled",
        "run.retry_exhausted",
    ]
    scheduled = audit.events[0][1]
    assert scheduled["attempt_number"] == 1
    assert scheduled["next_attempt_number"] == 2
    assert scheduled["reason_code"] == "timeout"
    assert audit.events[1][2] == "failed"


async def test_non_transient_failure_emits_no_retry_audit() -> None:
    audit = FakeAuditSink()
    runner = RunStepRunner(
        attempts=FakeAttemptRepository(),
        collector_call=SequencedCall([CollectionPolicyDenied("blocked", code="robots")]),
        policy=RetryPolicy(max_attempts=3),
        sleep=FakeSleep(),
        audit=audit,
    )

    result = await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4())

    assert result.step is not None
    assert result.step.status == "failed"
    assert audit.events == []


async def test_cancellation_between_attempts_stops_retry() -> None:
    state = {"cancelled": False}

    async def is_cancelled() -> bool:
        return state["cancelled"]

    call = SequencedCall([TimeoutError("timeout"), _success()])
    runner, attempts = _runner(call)

    async def sleep_then_cancel(delay: float) -> None:
        state["cancelled"] = True

    runner._sleep = sleep_then_cancel  # type: ignore[attr-defined]
    result = await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4(), is_cancelled=is_cancelled)

    assert result.cancelled is True
    assert result.step is not None
    assert result.step.status == "failed"
    assert len(attempts.attempts) == 1


async def test_lease_loss_raises_before_next_attempt() -> None:
    call = SequencedCall([TimeoutError("timeout"), _success()])
    runner, _ = _runner(call)
    checks = {"count": 0}

    def lease_valid() -> bool:
        checks["count"] += 1
        return checks["count"] == 1

    with pytest.raises(RunLeaseLostError):
        await runner.run(FakeRun(), _spec(), step_id=uuid.uuid4(), lease_valid=lease_valid)
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_step_runner.py -q
```

Expected: FAIL。`RunStepRunner` 不接受 `policy`、`sleep`、`lease_valid`。

- [ ] **Step 3: 实现重试循环**

把 `RunStepRunner.__init__` 改为：

```python
    def __init__(
        self,
        *,
        attempts: RunStepAttemptRepository,
        collector_call: CollectorCall,
        policy: RetryPolicy | None = None,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
        audit: RunAuditSink | None = None,
    ) -> None:
        self._attempts = attempts
        self._collector_call = collector_call
        self._policy = policy or RetryPolicy()
        self._sleep = sleep or asyncio.sleep
        self._clock = clock or (lambda: datetime.now(UTC))
        self._audit = audit
```

把 `run` 替换为：

```python
    async def run(
        self,
        run: RunRecord,
        spec: RunStepSpec,
        *,
        step_id: uuid.UUID,
        limits: RunLimits | None = None,
        lease_valid: Callable[[], bool] | None = None,
        is_cancelled: CancellationCheck | None = None,
    ) -> RunStepResult:
        lease_valid = lease_valid or _always_valid
        is_cancelled = is_cancelled or _never_cancelled
        limits = limits or RunLimits(max_pages=None, max_records=None)

        max_attempts = spec.max_attempts or self._policy.max_attempts
        first_started_at: datetime | None = None
        step_cost = Decimal("0")
        attempt_number = 1

        while True:
            if await is_cancelled():
                return RunStepResult(
                    step=self._skipped(
                        run.id,
                        spec,
                        step_id,
                        attempt_number,
                        first_started_at,
                        "run_cancelled",
                    ),
                    cancelled=True,
                )
            if not lease_valid():
                raise RunLeaseLostError(run.id, None, None)

            started_at = self._clock()
            if first_started_at is None:
                first_started_at = started_at
            attempt_id = uuid.uuid4()
            await self._attempts.add(
                RunStepAttemptWrite(
                    id=attempt_id,
                    run_id=run.id,
                    step_index=spec.step_index,
                    attempt_number=attempt_number,
                    status=RunStepAttemptStatus.RUNNING.value,
                    task_run_id=None,
                    error_reason_code=None,
                    error_message=None,
                    started_at=started_at,
                    finished_at=None,
                    created_at=started_at,
                )
            )

            receipt = await self._collect(
                run,
                spec,
                attempt_number,
                step_id=step_id,
                limits=limits,
            )
            finished_at = self._clock()
            result = receipt.result
            if result is not None:
                outcome = resolve_outcome(result)
                attempt_status = _attempt_status(outcome)
                records_count = result.records_count
                error_message = result.error_message
                if result.total_cost_usd is not None:
                    step_cost += result.total_cost_usd
                transient = (
                    outcome == OUTCOME_FAILED
                    and self._policy.is_transient_result(result)
                )
                reason = (
                    self._policy.reason_for_result(result)
                    if outcome == OUTCOME_FAILED
                    else None
                )
                unit = result.unit
                quantity = result.quantity
                unit_price = result.unit_price
            else:
                outcome = OUTCOME_FAILED
                attempt_status = RunStepAttemptStatus.FAILED.value
                records_count = 0
                error_message = _error_text(receipt.error)
                transient = self._policy.is_transient_error(receipt.error)
                reason = self._policy.reason_for_error(receipt.error)
                unit = None
                quantity = None
                unit_price = None

            await self._attempts.finish(
                attempt_id,
                status=attempt_status,
                task_run_id=receipt.task_run_id,
                error_reason_code=reason,
                error_message=error_message if outcome == OUTCOME_FAILED else None,
                finished_at=finished_at,
            )

            if attempt_number < max_attempts and transient:
                if await is_cancelled():
                    return RunStepResult(
                        step=self._failed(
                            run,
                            spec,
                            step_id,
                            attempt_number,
                            outcome,
                            records_count,
                            step_cost,
                            receipt.task_run_id,
                            error_message,
                            unit,
                            quantity,
                            unit_price,
                            first_started_at or started_at,
                            finished_at,
                        ),
                        cancelled=True,
                    )
                delay = self._policy.delay_for(attempt_number)
                await self._emit_retry_audit(
                    "run.retry_scheduled",
                    run,
                    spec,
                    attempt_number,
                    next_attempt_number=attempt_number + 1,
                    delay_seconds=delay,
                    reason_code=reason,
                )
                if not await self._sleep_interruptibly(delay, is_cancelled):
                    return RunStepResult(
                        step=self._failed(
                            run,
                            spec,
                            step_id,
                            attempt_number,
                            outcome,
                            records_count,
                            step_cost,
                            receipt.task_run_id,
                            error_message,
                            unit,
                            quantity,
                            unit_price,
                            first_started_at or started_at,
                            self._clock(),
                        ),
                        cancelled=True,
                    )
                attempt_number += 1
                continue

            if transient:
                await self._emit_retry_audit(
                    "run.retry_exhausted",
                    run,
                    spec,
                    attempt_number,
                    reason_code=reason,
                )

            return RunStepResult(
                step=self._failed_or_success(
                    run,
                    spec,
                    step_id,
                    attempt_number,
                    outcome,
                    records_count,
                    step_cost,
                    receipt.task_run_id,
                    error_message,
                    unit,
                    quantity,
                    unit_price,
                    first_started_at or started_at,
                    finished_at,
                ),
                cancelled=await is_cancelled(),
            )
```

加入辅助方法：

```python
    async def _sleep_interruptibly(
        self,
        delay: float,
        is_cancelled: CancellationCheck,
    ) -> bool:
        remaining = delay
        while remaining > 0:
            if await is_cancelled():
                return False
            chunk = min(remaining, 1.0)
            await self._sleep(chunk)
            remaining -= chunk
        return True

    async def _emit_retry_audit(
        self,
        action: str,
        run: RunRecord,
        spec: RunStepSpec,
        attempt_number: int,
        *,
        next_attempt_number: int | None = None,
        delay_seconds: float | None = None,
        reason_code: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        details: dict[str, object] = {
            "step_index": spec.step_index,
            "attempt_number": attempt_number,
        }
        if next_attempt_number is not None:
            details["next_attempt_number"] = next_attempt_number
        if delay_seconds is not None:
            details["delay_seconds"] = delay_seconds
        if reason_code is not None:
            details["reason_code"] = reason_code
        await self._audit.record(
            action,
            run,
            details=details,
            result="failed" if action == "run.retry_exhausted" else "success",
        )

    def _failed_or_success(self, run, spec, step_id, attempt_number, outcome,
                           records_count, step_cost, task_run_id, error_message,
                           unit, quantity, unit_price, started_at,
                           finished_at) -> RunStepWrite:
        return RunStepWrite(
            id=step_id,
            run_id=run.id,
            step_index=spec.step_index,
            endpoint_type=spec.endpoint_type or run.endpoint_type or "",
            collector_type=spec.collector_type or run.collector_type or "",
            task_run_id=task_run_id,
            status=STEP_STATUS_BY_OUTCOME[outcome],
            outcome=outcome,
            records_count=records_count,
            unit=unit,
            quantity=quantity,
            unit_price=unit_price,
            total_cost_usd=step_cost,
            error_message=error_message if outcome == OUTCOME_FAILED else None,
            started_at=started_at,
            finished_at=finished_at,
            attempt_no=attempt_number,
            depends_on=spec.depends_on,
            tool_id=spec.endpoint_type or None,
        )

    def _failed(self, run, spec, step_id, attempt_number, outcome, records_count,
                step_cost, task_run_id, error_message, unit, quantity, unit_price,
                started_at, finished_at) -> RunStepWrite:
        return self._failed_or_success(
            run, spec, step_id, attempt_number, outcome, records_count, step_cost,
            task_run_id, error_message, unit, quantity, unit_price, started_at,
            finished_at,
        )

    def _skipped(self, run_id, spec, step_id, attempt_number, started_at, reason) -> RunStepWrite:
        now = self._clock()
        return RunStepWrite(
            id=step_id,
            run_id=run_id,
            step_index=spec.step_index,
            endpoint_type=spec.endpoint_type,
            collector_type=spec.collector_type,
            task_run_id=None,
            status="skipped",
            outcome=None,
            records_count=0,
            unit=None,
            quantity=None,
            unit_price=None,
            total_cost_usd=None,
            error_message=reason,
            started_at=started_at or now,
            finished_at=now,
            attempt_no=attempt_number,
            depends_on=spec.depends_on,
            tool_id=spec.endpoint_type or None,
        )
```

**C6 不写账本。** 删除 `_record_ledger`、`RunLedgerWrite` 导入与所有 `ledger.add` 调用。每个 attempt 的成本由 C6 调用 C5 的 `start_tool_call` / `complete_tool_call` 写入 `tool_calls` 与 `task_runs`；run 结束后由 `RunBudget.settle` 汇总该 run 全部 attempt 的 `task_runs.total_cost_usd` 并写一次 `settle`。无 budget 只允许测试替身，替身不得访问数据库。

`run_step_runner.py` 文件头加入 `import asyncio`，并从契约导入 `CollectorCallResultView` 与 `RunLeaseLostError`。确认默认回调已存在；若没有则加入：

```python
def _always_valid() -> bool:
    return True
```

- [ ] **Step 4: 让执行器传入租约与取消回调**

在 `RunExecutor.execute_detailed` 的 `runner.run(...)` 调用中加入：

```python
            result = await runner.run(
                run,
                spec,
                step_id=step_id,
                limits=limits,
                lease_valid=lease_valid,
                is_cancelled=lambda: self._is_cancelled(run.id),
            )
```

- [ ] **Step 5: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_step_runner.py tests/unit/test_run_executor_multi_step.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs impact "RunStepRunner" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_step_runner.py \
  apps/api/src/data_intelligence_hub/services/run_executor.py \
  apps/api/tests/unit/test_run_step_runner.py \
  apps/api/tests/unit/test_run_executor_multi_step.py \
  apps/api/tests/unit/test_run_audit_events.py
git commit -m "feat(run): retry transient step failures per attempt"
```

---

### Task 8: 租约围栏与 worker 回调

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/run_queue_worker.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_worker_runtime.py`
- Test: `apps/api/tests/unit/test_run_queue.py`
- Test: `apps/api/tests/unit/test_run_worker_runtime.py`
- Test: `apps/api/tests/unit/test_run_executor_multi_step.py`

**Interfaces:**
- Produces: `RunHandler = Callable[[ClaimedRun, Callable[[], bool]], Awaitable[None]]`。
- 执行器：`lease_valid` 为假时抛 `RunLeaseLostError`。worker 捕获后回滚，不释放别人的租约。
- `claim_next_run` 的 SELECT 必须排除存在 `gate_status='blocked'` 授权的 run；领取后执行器再检查一次。blocked run 保持 `queued`，不得被领取或写成 `failed`。

- [ ] **Step 1: 写失败测试**

在 `test_run_executor_multi_step.py` 加入（顶部补 `import pytest` 与 `from data_intelligence_hub.services.run_execution_contracts import RunLeaseLostError`）：

```python
async def test_lease_loss_before_second_step_raises() -> None:
    run = FakeRun()
    executor, runs, _, _, _ = _executor(
        run,
        specs=[_spec(0), _spec(1)],
        results=[success_result(), success_result()],
    )
    checks = {"count": 0}

    def lease_valid() -> bool:
        checks["count"] += 1
        return checks["count"] == 1

    with pytest.raises(RunLeaseLostError):
        await executor.execute_detailed(run.id, lease_valid=lease_valid)

    assert "completed" not in runs.status_history
```

在 `test_run_queue.py` 的 handler 改为：

```python
    async def handler(claimed, lease_valid) -> None:
        assert callable(lease_valid)
        assert lease_valid() is True
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_queue.py tests/unit/test_run_executor_multi_step.py -q
```

Expected: FAIL。handler 只接收一个参数。

- [ ] **Step 3: 改 worker 循环**

在 `run_queue_worker.py`：

```python
RunHandler = Callable[[ClaimedRun, Callable[[], bool]], Awaitable[None]]
...
        try:
            await handler(claimed, lambda: not heartbeat.lost)
```

在 `run_worker_runtime.py` 的 `_handle`：

```python
    async def _handle(self, claimed: ClaimedRun, lease_valid: Callable[[], bool]) -> None:
        async with self._session_factory() as session:
            call = (
                self._collector_call_factory(session)
                if self._collector_call_factory is not None
                else None
            )
            bundle = build_run_executor_bundle(
                session,
                collector_call=call,
                grade_calculator=self._grade_calculator,
            )
            try:
                result = await bundle.executor.execute_detailed(
                    claimed.run_id,
                    lease_valid=lease_valid,
                    checkpoint=session.commit,
                )
            except (
                RunNotFoundError,
                InvalidRunTransitionError,
                RunLeaseLostError,
            ) as exc:
                await session.rollback()
                logger.warning(
                    "run_worker_skip_run",
                    run_id=str(claimed.run_id),
                    reason=exc.__class__.__name__,
                )
                return

            mirror = getattr(bundle.collector_call, "mirror_evidence_grade", None)
            if callable(mirror):
                try:
                    await mirror(result.run.id, result.run.evidence_grade)
                except Exception:
                    logger.exception(
                        "run_worker_evidence_mirror_failed",
                        run_id=str(result.run.id),
                    )
            await session.commit()
```

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_queue.py tests/unit/test_run_worker_runtime.py tests/unit/test_run_executor_multi_step.py tests/unit/test_run_lease_fence.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_queue_worker.py \
  apps/api/src/data_intelligence_hub/services/run_worker_runtime.py \
  apps/api/tests/unit/test_run_queue.py \
  apps/api/tests/unit/test_run_worker_runtime.py \
  apps/api/tests/unit/test_run_executor_multi_step.py
git commit -m "feat(run): fence worker execution by lease"
```

---

### Task 9: 取消语义、取消幂等与路由

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_cancel_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_service.py`（re-export `cancel_task_runs`、`RunCancellationResult`、`CancellationError`）
- Modify: `apps/api/src/data_intelligence_hub/repositories/runs.py`
- Modify: `apps/api/src/data_intelligence_hub/schemas/run.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/runs.py`
- Test: `apps/api/tests/unit/test_run_routes.py`
- Test: `apps/api/tests/unit/test_run_cancel_idempotency.py`
- Test: `apps/api/tests/unit/test_run_executor_multi_step.py`
- Test: `apps/api/tests/unit/test_run_audit_events.py`

**Interfaces:**
- Consumes: C1 `runs.cancel_idempotency_key_hash`、`runs.cancel_reason_code`、`uq_runs_workspace_cancel_idempotency`；C5 `OrmRunBudget.cancel`；C2 `append_audit_event`。
- Produces:
  - `hash_cancel_idempotency_key(key: str) -> str` = `sha256("run-cancel.v1:{key}")`。
  - `CancelClaim(run, claimed)`（`repositories/runs.py`）。
  - `RunCancelResult(run, replayed)`、`cancel_run(session, *, workspace_id, run_id, idempotency_key, reason_code) -> RunCancelResult`。
  - `RunCancelConflictError`（409 `idempotency_conflict`）、`RunNotCancellableError`（409 `run_not_cancellable`）。
- 语义：同键同参重放原结果；同键不同参 `idempotency_conflict`；不同键对已取消 run 幂等重放；只有胜出事务调用 `OrmRunBudget.cancel`，预算预留只释放一次。
- `services.run_service.cancel_task_runs(session, *, workspace_id, project_id, task_id, idempotency_key, reason_code) -> RunCancellationResult`：C13 的任务级唯一入口。查询该任务全部 `queued · running` run，逐个复用 `run_cancel_service.cancel_run` 的原子接缝；汇总 `cancelled_run_ids`、`preserved_artifact_ids=()`、`cancelled_at`、`replayed`。`RunCancellationResult` 是 C13 兼容名，字段与 `RunCancelResult` 对齐并增加聚合字段。
- `CancellationError` 是 `RunCancelConflictError` 与 `RunNotCancellableError` 的基类；`CancellationError.code` 只用 `idempotency_conflict` 与 `state_conflict`。路由继续返回现有 detail `run_not_cancellable`，C13 适配器映射到 `state_conflict`。
- `cancel_run` 写入 `status=cancelled`、`finished_at`、`cancel_idempotency_key_hash`、`cancel_reason_code`，并清空 `lease_expires_at`。保留 `worker_id` 供围栏与审计。取消不删除 step、attempt、task_run 或账本。
- 执行器在取消后不再写 run 终态。已开始 step 保留实际结果。未开始 step 写 `skipped`。

- [ ] **Step 1: 写失败测试**

新建 `tests/unit/test_run_cancel_idempotency.py`：

```python
"""取消幂等测试。同键重放、同键不同参冲突、并发只释放一次预算。"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import pytest

from data_intelligence_hub.services import run_cancel_service
from data_intelligence_hub.services.run_cancel_service import (
    RunCancelConflictError,
    RunNotCancellableError,
    cancel_run,
    hash_cancel_idempotency_key,
)


@dataclass
class FakeRun:
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None = None
    workflow_version_id: uuid.UUID | None = None
    status: str = "queued"
    outcome: str | None = None
    finished_at: object | None = None
    cancel_idempotency_key_hash: str | None = None
    cancel_reason_code: str | None = None


def _run() -> FakeRun:
    return FakeRun(id=uuid.uuid4(), workspace_id=uuid.uuid4(), project_id=uuid.uuid4())


@pytest.mark.anyio
async def test_same_key_same_reason_replays_and_releases_once(monkeypatch) -> None:
    run = _run()
    key_hash = hash_cancel_idempotency_key("cancel-1")
    calls: list[str] = []

    async def claim_cancel(session, **kwargs):
        calls.append("claim")
        if len(calls) == 1:
            run.status = "cancelled"
            run.finished_at = "2026-10-22T00:00:00+00:00"
            run.cancel_idempotency_key_hash = key_hash
            run.cancel_reason_code = "user_request"
            return run_cancel_service.runs_repository.CancelClaim(run=run, claimed=True)
        return run_cancel_service.runs_repository.CancelClaim(run=run, claimed=False)

    async def fake_audit(session, **kwargs):
        calls.append(str(kwargs["action"]))

    class FakeBudget:
        def __init__(self, session) -> None:
            pass

        async def cancel(self, run) -> None:
            calls.append("budget_cancel")

    monkeypatch.setattr(run_cancel_service.runs_repository, "claim_cancel", claim_cancel)
    monkeypatch.setattr(run_cancel_service, "audit_run_event", fake_audit)
    monkeypatch.setattr(run_cancel_service, "OrmRunBudget", FakeBudget)

    first = await cancel_run(
        None,
        workspace_id=run.workspace_id,
        run_id=run.id,
        idempotency_key="cancel-1",
        reason_code="user_request",
    )
    second = await cancel_run(
        None,
        workspace_id=run.workspace_id,
        run_id=run.id,
        idempotency_key="cancel-1",
        reason_code="user_request",
    )

    assert first.replayed is False
    assert second.replayed is True
    assert second.run.finished_at == first.run.finished_at
    assert calls.count("budget_cancel") == 1
    assert calls.count("run.cancel_requested") == 1
    assert calls.count("run.cancelled") == 1


@pytest.mark.anyio
async def test_same_key_different_reason_conflicts(monkeypatch) -> None:
    run = _run()
    run.status = "cancelled"
    run.cancel_idempotency_key_hash = hash_cancel_idempotency_key("cancel-1")
    run.cancel_reason_code = "user_request"

    async def claim_cancel(session, **kwargs):
        return run_cancel_service.runs_repository.CancelClaim(run=run, claimed=False)

    monkeypatch.setattr(run_cancel_service.runs_repository, "claim_cancel", claim_cancel)

    with pytest.raises(RunCancelConflictError):
        await cancel_run(
            None,
            workspace_id=run.workspace_id,
            run_id=run.id,
            idempotency_key="cancel-1",
            reason_code="operator",
        )


@pytest.mark.anyio
async def test_concurrent_claims_release_budget_once(monkeypatch) -> None:
    run = _run()
    key_hash = hash_cancel_idempotency_key("cancel-1")
    claims = {"count": 0}
    calls: list[str] = []

    async def claim_cancel(session, **kwargs):
        claims["count"] += 1
        if claims["count"] == 1:
            await asyncio.sleep(0)
            run.status = "cancelled"
            run.cancel_idempotency_key_hash = key_hash
            run.cancel_reason_code = "user_request"
            return run_cancel_service.runs_repository.CancelClaim(run=run, claimed=True)
        return run_cancel_service.runs_repository.CancelClaim(run=run, claimed=False)

    async def fake_audit(session, **kwargs):
        calls.append(str(kwargs["action"]))

    class FakeBudget:
        def __init__(self, session) -> None:
            pass

        async def cancel(self, run) -> None:
            calls.append("budget_cancel")

    monkeypatch.setattr(run_cancel_service.runs_repository, "claim_cancel", claim_cancel)
    monkeypatch.setattr(run_cancel_service, "audit_run_event", fake_audit)
    monkeypatch.setattr(run_cancel_service, "OrmRunBudget", FakeBudget)

    results = await asyncio.gather(
        cancel_run(None, workspace_id=run.workspace_id, run_id=run.id,
                   idempotency_key="cancel-1", reason_code="user_request"),
        cancel_run(None, workspace_id=run.workspace_id, run_id=run.id,
                   idempotency_key="cancel-1", reason_code="user_request"),
    )

    assert sorted(result.replayed for result in results) == [False, True]
    assert calls.count("budget_cancel") == 1


@pytest.mark.anyio
async def test_terminal_non_cancelled_run_is_not_cancellable(monkeypatch) -> None:
    run = _run()
    run.status = "completed"

    async def claim_cancel(session, **kwargs):
        return run_cancel_service.runs_repository.CancelClaim(run=run, claimed=False)

    monkeypatch.setattr(run_cancel_service.runs_repository, "claim_cancel", claim_cancel)

    with pytest.raises(RunNotCancellableError):
        await cancel_run(
            None,
            workspace_id=run.workspace_id,
            run_id=run.id,
            idempotency_key="cancel-1",
            reason_code="user_request",
        )
```

现有 `test_run_routes.py` 的所有取消用例（含 `run_not_cancellable`）都必须带 JSON 请求体；`idempotency_key` 每次唯一，`reason_code` 用固定测试值。在新用例中加入：

```python
    response = await client.post(
        f"/api/runs/{run_id}/cancel",
        json={"idempotency_key": "cancel-1", "reason_code": "user_request"},
    )
    assert response.status_code == 200
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        stored = await session.get(Run, run_id)
        assert stored is not None
        assert stored.status == "cancelled"
        assert stored.lease_expires_at is None
        assert stored.finished_at is not None
        assert stored.cancel_idempotency_key_hash is not None
        assert stored.cancel_reason_code == "user_request"

    replay = await client.post(
        f"/api/runs/{run_id}/cancel",
        json={"idempotency_key": "cancel-1", "reason_code": "user_request"},
    )
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"

    conflict = await client.post(
        f"/api/runs/{run_id}/cancel",
        json={"idempotency_key": "cancel-1", "reason_code": "operator"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency_conflict"
```

在 `test_run_executor_multi_step.py` 加入：

```python
async def test_cancelled_run_skips_remaining_steps_without_overwriting_status() -> None:
    run = FakeRun()
    executor, runs, _, _, _ = _executor(
        run,
        specs=[_spec(0), _spec(1)],
        results=[success_result()],
    )
    runs.cancelled = False

    original_run_status = runs.status

    async def status(run_id):
        return "cancelled" if runs.cancelled else original_run_status(run_id)

    runs.status = status  # type: ignore[assignment]

    async def checkpoint() -> None:
        runs.cancelled = True

    result = await executor.execute_detailed(run.id, checkpoint=checkpoint)

    assert result.run.status == "cancelled"
    assert [step.status for step in result.steps] == ["success", "skipped"]
    assert result.steps[1].error_message == "run_cancelled"
    assert "completed" not in runs.status_history
```

在 `test_run_audit_events.py` 加入取消审计用例：第一次取消恰好一条 `run.cancel_requested` 与一条 `run.cancelled`；重放与冲突不新增审计。

在 `test_run_cancel_idempotency.py` 加入 `cancel_task_runs` 用例：任务下两条可取消 run 一次取消；同键同参重放 `replayed=True` 且不再释放预算；同键不同 reason 抛 `idempotency_conflict`；无活动 run 抛 `state_conflict`。

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_cancel_idempotency.py tests/unit/test_run_routes.py -q
```

Expected: FAIL。`run_cancel_service` 不存在；取消后 `lease_expires_at` 仍非空；同键重放没有 `Idempotent-Replay`。

- [ ] **Step 3: 实现取消原子领取**

在 `repositories/runs.py` 确认/加入以下导入与代码（已存在的导入不重复添加）：

```python
from dataclasses import dataclass

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError


@dataclass(frozen=True, slots=True)
class CancelClaim:
    run: Run | None
    claimed: bool
    conflict: bool = False


async def claim_cancel(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    idempotency_key_hash: str,
    reason_code: str,
) -> CancelClaim:
    """原子领取一次取消。

    只有把 run 从 queued/running 改为 cancelled、且取消键列为空的事务
    返回 claimed=True。落败事务返回当前行，由服务层判断重放或冲突。
    工作区级唯一索引拒绝跨 run 复用同一取消键时返回 conflict=True。
    """
    try:
        result = await session.execute(
            update(Run)
            .where(
                Run.id == run_id,
                Run.workspace_id == workspace_id,
                Run.status.in_(("queued", "running")),
                Run.cancel_idempotency_key_hash.is_(None),
            )
            .values(
                status=RunStatus.CANCELLED.value,
                finished_at=func.now(),
                lease_expires_at=None,
                cancel_idempotency_key_hash=idempotency_key_hash,
                cancel_reason_code=reason_code,
            )
        )
    except IntegrityError:
        # 同一工作区把同一取消键复用到另一 run：按参数冲突处理。
        await session.rollback()
        return CancelClaim(run=None, claimed=False, conflict=True)
    run = await session.get(Run, run_id, populate_existing=True)
    return CancelClaim(
        run=run,
        claimed=int(getattr(result, "rowcount", 0)) == 1,
    )
```

保留现有 `cancel_run` 仅供未迁移调用方；新路由与服务只调用 `claim_cancel`。不得清空 `worker_id`。

- [ ] **Step 4: 写取消幂等服务**

新建 `services/run_cancel_service.py`：

```python
"""取消幂等：原子领取、重放、冲突与预算释放。"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run import Run, RunStatus
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.services.exceptions import ServiceError
from data_intelligence_hub.services.run_audit import audit_run_event
from data_intelligence_hub.services.run_budget import OrmRunBudget
from data_intelligence_hub.services.run_execution_contracts import RunNotFoundError


class RunCancelConflictError(ServiceError):
    message = "idempotency_conflict"

    def __init__(self, run_id: uuid.UUID) -> None:
        super().__init__(self.message)
        self.run_id = run_id


class RunNotCancellableError(ServiceError):
    message = "run_not_cancellable"

    def __init__(self, run_id: uuid.UUID, status: str) -> None:
        super().__init__(f"{self.message}: {status}")
        self.run_id = run_id
        self.status = status


@dataclass(frozen=True, slots=True)
class RunCancelResult:
    run: Run
    replayed: bool


def hash_cancel_idempotency_key(key: str) -> str:
    return hashlib.sha256(f"run-cancel.v1:{key}".encode("utf-8")).hexdigest()


async def cancel_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    idempotency_key: str,
    reason_code: str,
) -> RunCancelResult:
    key = idempotency_key.strip()
    reason = reason_code.strip()
    if not key or len(key) > 200:
        raise ValueError("idempotency_key_required")
    if not reason or len(reason) > 80:
        raise ValueError("reason_code_invalid")

    key_hash = hash_cancel_idempotency_key(key)
    claim = await runs_repository.claim_cancel(
        session,
        workspace_id=workspace_id,
        run_id=run_id,
        idempotency_key_hash=key_hash,
        reason_code=reason,
    )
    if claim.conflict:
        raise RunCancelConflictError(run_id)
    if claim.run is None:
        raise RunNotFoundError(run_id)

    if claim.claimed:
        # 只有胜出事务释放预算；C5 的 cancel_reservation 自身也幂等。
        await OrmRunBudget(session).cancel(claim.run)
        details = {
            "cancel_idempotency_key_hash": key_hash,
            "reason_code": reason,
        }
        await audit_run_event(
            session,
            action="run.cancel_requested",
            run=claim.run,
            details=details,
        )
        await audit_run_event(
            session,
            action="run.cancelled",
            run=claim.run,
            details=details,
        )
        return RunCancelResult(run=claim.run, replayed=False)

    if claim.run.status != RunStatus.CANCELLED.value:
        raise RunNotCancellableError(run_id, claim.run.status)

    if (
        claim.run.cancel_idempotency_key_hash == key_hash
        and claim.run.cancel_reason_code != reason
    ):
        raise RunCancelConflictError(run_id)

    # 同一 run 已被另一个键取消：幂等重放第一次结果，不再释放预算。
    return RunCancelResult(run=claim.run, replayed=True)


__all__ = [
    "CancellationError",
    "RunCancelConflictError",
    "RunCancelResult",
    "RunCancellationResult",
    "RunNotCancellableError",
    "cancel_run",
    "cancel_task_runs",
    "hash_cancel_idempotency_key",
]
```

`RunNotFoundError` 从 `services.run_execution_contracts` 导入；不得从 `repositories` 暴露 HTTP 异常。

为 C13 增加兼容出口。把 `RunCancelConflictError` 与 `RunNotCancellableError` 的基类从 `ServiceError` 改为 `CancellationError`，并给每个类加 `code`：

```python
class CancellationError(ServiceError):
    code: str


class RunCancelConflictError(CancellationError):
    code = "idempotency_conflict"
    ...


class RunNotCancellableError(CancellationError):
    code = "state_conflict"
    ...
```

再增加聚合结果：

```python
@dataclass(frozen=True, slots=True)
class RunCancellationResult:
    cancelled_run_ids: tuple[uuid.UUID, ...]
    preserved_artifact_ids: tuple[str, ...]
    cancelled_at: datetime
    replayed: bool


async def cancel_task_runs(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    idempotency_key: str,
    reason_code: str,
) -> RunCancellationResult:
    runs = await runs_repository.list_cancellable_by_task(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
    )
    if not runs:
        raise RunNotCancellableError(task_id, "no_active_runs")
    results = [
        await cancel_run(
            session,
            workspace_id=workspace_id,
            run_id=run.id,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
        )
        for run in runs
    ]
    return RunCancellationResult(
        cancelled_run_ids=tuple(item.run.id for item in results),
        preserved_artifact_ids=(),
        cancelled_at=max(
            item.run.finished_at or datetime.now(UTC) for item in results
        ),
        replayed=all(item.replayed for item in results),
    )
```

`services/run_service.py` 从 `run_cancel_service` re-export `cancel_task_runs`、`RunCancellationResult`、`CancellationError`；C13 只导入这三个名字。`repositories/runs.py` 增加 `list_cancellable_by_task`，只读 `queued · running` run，不跨工作区或项目。

- [ ] **Step 5: 改请求 schema 与路由**

在 `schemas/run.py` 加入：

```python
from pydantic import BaseModel, Field, field_validator


class RunCancelRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    reason_code: str = Field(min_length=1, max_length=80)

    @field_validator("idempotency_key", "reason_code")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("invalid_request")
        return value
```

把 `api/routes/runs.py` 的 `cancel_run` 改为：

```python
from fastapi import Response

from data_intelligence_hub.schemas.run import RunCancelRequest
from data_intelligence_hub.services.run_cancel_service import (
    RunCancelConflictError,
    RunNotCancellableError,
    cancel_run as cancel_run_idempotent,
)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: uuid.UUID,
    body: RunCancelRequest,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> RunResponse:
    """取消一次运行。

    请求必须带 ``idempotency_key`` 与 ``reason_code``。
    同键同参返回第一次取消结果，响应头 ``Idempotent-Replay: true``。
    同键不同参返回 409 ``idempotency_conflict``。
    已完成的运行返回 409 ``run_not_cancellable``。
    """
    await _get_run_or_404(session, context, run_id)
    try:
        result = await cancel_run_idempotent(
            session,
            workspace_id=context.workspace.id,
            run_id=run_id,
            idempotency_key=body.idempotency_key,
            reason_code=body.reason_code,
        )
    except RunNotCancellableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run_not_cancellable",
        ) from exc
    except RunCancelConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency_conflict",
        ) from exc

    await session.commit()
    if result.replayed:
        response.headers["Idempotent-Replay"] = "true"
    return RunResponse.model_validate(result.run)
```

`RunCancelRequest` 的空白值由 Pydantic 返回 422。新增的注册错误码只有 `idempotency_conflict`（C1 已登记）；`run_not_cancellable` 是现有路由 detail，不是新增错误码。

- [ ] **Step 6: 加执行器状态围栏**

给 `OrmRunRepository.save` 的非终态写入加状态围栏，防止“读取后、写 running 前”被取消：

```python
        if row.status == "running":
            conditions.append(Run.status.in_(("queued", "running")))
        elif row.status in _TERMINAL_RUN_STATUSES:
            conditions.append(Run.status == "running")
```

取消路由写 `cancelled` 之后、提交之前调用 C5 的 `OrmRunBudget.cancel(run)`（已在服务内完成）；不写账本，不删除 step/attempt/task_run。

- [ ] **Step 7: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_routes.py tests/unit/test_run_cancel_idempotency.py tests/unit/test_run_executor_multi_step.py tests/unit/test_run_audit_events.py -q
```

Expected: 全部通过。同键重放不新增审计；并发取消只调用一次预算释放；`cancel_task_runs` 聚合同一任务的多条 run，并保持 C13 的 `idempotency_conflict` / `state_conflict` 语义。

- [ ] **Step 8: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs impact "RunExecutor" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_cancel_service.py   apps/api/src/data_intelligence_hub/repositories/runs.py   apps/api/src/data_intelligence_hub/schemas/run.py   apps/api/src/data_intelligence_hub/api/routes/runs.py   apps/api/tests/unit/test_run_routes.py   apps/api/tests/unit/test_run_cancel_idempotency.py   apps/api/tests/unit/test_run_executor_multi_step.py   apps/api/tests/unit/test_run_audit_events.py
git commit -m "fix(run): make cancellation idempotent and audited"
```

---

### Task 10: quick 同步入口收敛

**GitNexus 风险：HIGH。** `run_quick_collect` 实测 30 impacted、3 processes；MCP 的 `mcp_runtime/collect_service.py` 直接调用它。编辑前必须报告调用方，保留旧函数与 MCP 回归测试；不得用“未改 mcp_runtime 文件”代替行为边界。

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/quick_collect_service.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/runs.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/runs.py`
- Reuse（不修改）: C4 `apps/api/src/data_intelligence_hub/services/run_creation.py`
- Test: `apps/api/tests/integration/test_quick_collect_routes.py`
- Test: `apps/api/tests/integration/test_quick_collect_async.py`
- Test: `apps/api/tests/unit/test_run_audit_events.py`

**Interfaces:**
- Produces:
  - `create_run_for_task(session, *, workspace_id, project_id, task_id, trigger, idempotency_key_hash=None) -> Run`；只调用 C4 `create_run_with_audit`，不直接写 `run.created`。
  - `execute_run_inline(session, run_id) -> RunExecutionResult`
  - `get_last_task_run(session, run_id) -> TaskRun | None`
- 保持：quick 同步响应与异步响应不变。`run.created` 由 C4 接缝只在插入新 run 时写；幂等重放不写。

- [ ] **Step 1: 写失败测试**

在 `test_quick_collect_routes.py` 的成功用例末尾加入：

```python
    from data_intelligence_hub.models import AuditEvent, Run, RunStep, RunStepAttempt

    async with session_factory() as session:
        run = await session.scalar(
            select(Run).where(Run.task_id == uuid.UUID(body["task_id"]))
        )
        assert run is not None
        assert run.status == "completed"
        assert run.outcome == "success"
        steps = list(
            (
                await session.execute(
                    select(RunStep).where(RunStep.run_id == run.id)
                )
            ).scalars()
        )
        assert len(steps) == 1
        assert steps[0].task_run_id == uuid.UUID(body["task_run_id"])
        attempts = list(
            (
                await session.execute(select(RunStepAttempt))
            ).scalars()
        )
        assert len(attempts) == 1
        assert attempts[0].status == "success"
        assert attempts[0].run_id == run.id
        assert attempts[0].step_index == 0
        audit_actions = list(
            (
                await session.execute(
                    select(AuditEvent.action).where(
                        AuditEvent.resource_id == str(run.id)
                    )
                )
            ).scalars()
        )
        assert audit_actions == ["run.created", "run.completed"]
```

测试夹具必须设置 `RUN_EXECUTION_CONVERGENCE_ENABLED=true`；另加一个开关为 `false` 的用例，断言旧的 `run_quick_collect` 路径不创建 `runs` 行。

在文件顶部补 `from sqlalchemy import select` 与 `Run`、`RunStep`、`RunStepAttempt` 导入。

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/integration/test_quick_collect_routes.py::test_quick_collect_keeps_endpoint_type_in_task_config -q
```

Expected: FAIL。quick 同步路径没有创建 `runs` 行。

- [ ] **Step 3: 写 `run_service.py`**

```python
"""受治理 run 的创建与同步执行入口。

本模块只服务旧入口收敛。它不实现计划、预算或报告。
事务边界由本模块提交，因为同步入口需要在请求内完成一次完整运行。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.services.run_creation import create_run_with_audit
from data_intelligence_hub.services.run_execution_contracts import RunExecutionResult
from data_intelligence_hub.services.run_budget import OrmRunBudget
from data_intelligence_hub.services.run_worker_runtime import build_run_executor_bundle


def hash_idempotency_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def create_run_for_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    trigger: str,
    idempotency_key_hash: str | None = None,
) -> Run:
    """创建一行 queued run 并提交。

    并发重复提交同一幂等键时，唯一索引拒绝插入。回滚后重查并返回原行。
    """
    try:
        run = await create_run_with_audit(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task_id,
            status="queued",
            trigger=trigger,
            idempotency_key_hash=idempotency_key_hash,
        )
    except IntegrityError:
        # 只处理插入幂等冲突；C4 接缝的审计写入失败必须直接抛出。
        await session.rollback()
        if idempotency_key_hash is None:
            raise
        existing = await runs_repository.find_by_idempotency_key(
            session,
            workspace_id=workspace_id,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing is None:
            raise
        return existing

    await session.commit()
    return run


async def execute_run_inline(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> RunExecutionResult:
    """在请求进程内执行一次 run。

    每个 step 后提交。进程崩溃时已完成的 step 不会重复执行。
    """
    bundle = build_run_executor_bundle(
        session,
        budget=OrmRunBudget(session),
    )
    result = await bundle.executor.execute_detailed(
        run_id,
        checkpoint=session.commit,
    )
    await session.commit()
    return result


async def enqueue_scheduled_run(
    session: AsyncSession,
    *,
    task: CollectionTask,
    now: datetime,
) -> Run | None:
    """scheduler 为到期任务入队。同一时间槽只入队一次。"""
    slot = _scheduled_slot(task, now)
    key = f"schedule:{task.id}:{slot.isoformat()}"
    key_hash = hash_idempotency_key(key)
    active = await session.scalar(
        select(Run.id)
        .where(
            Run.task_id == task.id,
            Run.status.in_(("queued", "running")),
        )
        .limit(1)
    )
    if active is not None:
        return None
    existing = await runs_repository.find_by_idempotency_key(
        session,
        workspace_id=task.workspace_id,
        idempotency_key_hash=key_hash,
    )
    if existing is not None:
        return None
    try:
        run = await create_run_with_audit(
            session,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            status="queued",
            trigger="schedule",
            idempotency_key_hash=key_hash,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return None
    return run


def _scheduled_slot(task: CollectionTask, now: datetime) -> datetime:
    current = now.astimezone(UTC)
    if task.schedule_cron:
        return current.replace(second=0, microsecond=0)
    return current.replace(minute=0, second=0, microsecond=0)


__all__ = [
    "create_run_for_task",
    "enqueue_scheduled_run",
    "execute_run_inline",
    "hash_idempotency_key",
]
```

- [ ] **Step 4: 加 `get_last_task_run`**

在 `repositories/runs.py`：

```python
async def get_last_task_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
) -> TaskRun | None:
    """返回 run 最后一个有 task_run 的步骤记录。"""
    task_run_id = await session.scalar(
        select(RunStep.task_run_id)
        .where(
            RunStep.run_id == run_id,
            RunStep.task_run_id.is_not(None),
        )
        .order_by(RunStep.step_index.desc())
        .limit(1)
    )
    if task_run_id is None:
        return None
    return await session.get(TaskRun, task_run_id)
```

导入 `TaskRun`。加入 `__all__`。

- [ ] **Step 5: 改 quick 服务**

`quick_collect_service.py` 保留 `execute_collection_task` 导入与 `run_quick_collect`（MCP 继续使用）；新增 `run_quick_collect_governed` 所需导入：

```python
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.services.run_service import (
    create_run_for_task,
    execute_run_inline,
)
```

**保留 `run_quick_collect` 原实现不变。** MCP 的 `mcp_runtime/collect_service.py` 直接调用它；C6 不得改变 MCP 的响应、错误或预算语义。新增一个受开关控制的函数：

```python
async def run_quick_collect_governed(
    session: AsyncSession,
    body: QuickCollectRequest,
    *,
    workspace: Workspace | None = None,
) -> QuickCollectOutcome:
    """受治理的 quick-collect；只在 RUN_EXECUTION_CONVERGENCE_ENABLED=true 时使用。"""
    prepared = await _prepare_quick_collect(session, body, workspace)
    run = await create_run_for_task(
        session,
        workspace_id=prepared.workspace.id,
        project_id=body.project_id,
        task_id=prepared.task_id,
        trigger="api",
    )
    execution = await execute_run_inline(session, run.id)
    task_run = await runs_repository.get_last_task_run(session, run_id=run.id)
    if task_run is None:
        raise QuickCollectExecutionError(
            execution.run.error_message or "run_produced_no_task_run"
        )
    preview = await list_raw_records(
        session,
        workspace_id=prepared.workspace.id,
        task_run_id=task_run.id,
        limit=QUICK_COLLECT_RECORDS_PREVIEW_LIMIT,
    )
    return QuickCollectOutcome(
        run=task_run,
        task_id=prepared.task_id,
        source_id=prepared.source_id,
        records=tuple(build_record_preview(record) for record in preview),
    )
```

保留 `enqueue_quick_collect` 原实现。新增 `enqueue_quick_collect_governed`：

```python
    run = await create_run_for_task(
        session,
        workspace_id=prepared.workspace.id,
        project_id=body.project_id,
        task_id=prepared.task_id,
        trigger="api",
    )
    return QuickCollectQueuedOutcome(
        run_id=run.id,
        task_id=prepared.task_id,
        source_id=prepared.source_id,
    )
```

删除 `from data_intelligence_hub.services.run_queue import enqueue_run`。

- [ ] **Step 6: API 路由按开关选择，MCP 不动**

在 `api/routes/quick_collect.py` 的同步与异步处理处按 `get_settings().run_execution_convergence_enabled` 选择：

```python
    runner = (
        run_quick_collect_governed
        if get_settings().run_execution_convergence_enabled
        else run_quick_collect
    )
    outcome = await runner(session, body, workspace=workspace)
```

`api/routes/runs.py` 的 `create_run` 不得直接调用 `runs_repository.create_run`，也不得直接写 `run.created`。导入 C4 接缝：

```python
from data_intelligence_hub.services.run_creation import create_run_with_audit
```

把 `_insert()` 内的仓储调用替换为 C4 接缝：

```python
        run = await create_run_with_audit(
            session,
            workspace_id=workspace_id,
            project_id=body.project_id,
            task_id=body.task_id,
            status="queued",
            trigger=body.trigger,
            idempotency_key_hash=idempotency_key_hash,
        )
        await session.commit()
```

`_insert()` 只保留幂等预查与 `IntegrityError` 捕获；幂等重放路径与 `IntegrityError` 回滚路径不写审计。`try/except IntegrityError` 只包住接缝调用；`session.commit()` 放在 `try` 之后，审计写入失败必须直接抛出，不得被当作重复创建吞掉。删除不再使用的 `audit_run_event` 导入。变量名按 `api/routes/runs.py` 现有作用域调整，不得新增第二套幂等键派生。`mcp_runtime/collect_service.py` 不改，继续 import `run_quick_collect`。新增回归测试：

```python
# MCP 必须绑定旧入口；收敛开关不得改变 MCP 行为。
def test_mcp_uses_legacy_quick_collect() -> None:
    from data_intelligence_hub.mcp_runtime import collect_service
    from data_intelligence_hub.services import quick_collect_service

    assert (
        collect_service.run_quick_collect
        is quick_collect_service.run_quick_collect
    )


def test_mcp_does_not_import_governed_runner() -> None:
    from data_intelligence_hub.mcp_runtime import collect_service

    assert not hasattr(collect_service, "run_quick_collect_governed")
```

- [ ] **Step 7: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/integration/test_quick_collect_routes.py tests/integration/test_quick_collect_async.py tests/unit/test_mcp_quick_collect_compat.py tests/unit/test_run_audit_events.py -q
```

Expected: 全部通过。同步响应的 `status`、`records`、`usage`、`timing` 字段不变；MCP 路径不创建 `runs` 行。

- [ ] **Step 8: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs impact "run_quick_collect" --direction upstream --repo .
node .gitnexus/run.cjs impact "run_quick_collect_governed" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_service.py \
  apps/api/src/data_intelligence_hub/services/quick_collect_service.py \
  apps/api/src/data_intelligence_hub/repositories/runs.py \
  apps/api/src/data_intelligence_hub/api/routes/runs.py \
  apps/api/tests/integration/test_quick_collect_routes.py \
  apps/api/tests/integration/test_quick_collect_async.py \
  apps/api/tests/unit/test_run_audit_events.py
git commit -m "refactor(quick): execute quick collect through governed runs"
```

---

### Task 11: task run-now 收敛

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/task_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Test: `apps/api/tests/integration/test_sources_tasks.py`
- Test: `apps/api/tests/unit/test_task_runs_route.py`

**Interfaces:**
- `run_task_now` 返回的 `TaskRunResult.run` 仍是 `TaskRun`。
- 幂等重放先查 `runs.idempotency_key_hash`。历史 `task_runs.logs` 回退保留。

- [ ] **Step 1: 写失败测试**

在 `test_sources_tasks.py` 的 run-now 用例中加入：

```python
    async with session_factory() as session:
        runs = list(
            (
                await session.execute(
                    select(Run).where(Run.task_id == task_id)
                )
            ).scalars()
        )
        assert len(runs) == 1
        assert runs[0].trigger == "manual"
        steps = list(
            (
                await session.execute(
                    select(RunStep).where(RunStep.run_id == runs[0].id)
                )
            ).scalars()
        )
        assert len(steps) == 1
        assert steps[0].task_run_id == uuid.UUID(response.json()["id"])
        from data_intelligence_hub.models import AuditEvent

        audit_actions = list(
            (
                await session.execute(
                    select(AuditEvent.action).where(
                        AuditEvent.resource_id == str(runs[0].id)
                    )
                )
            ).scalars()
        )
        assert audit_actions.count("run.created") == 1
        assert audit_actions.count("run.completed") == 1

        # 同一幂等键重放不新增 run.created。
        replay = await client.post(
            f"/api/tasks/{task_id}/run",
            headers={"Idempotency-Key": "run-now-1"},
        )
        assert replay.status_code == 201
        async with session_factory() as session:
            replayed_actions = list(
                (
                    await session.execute(
                        select(AuditEvent.action).where(
                            AuditEvent.resource_id == str(runs[0].id)
                        )
                    )
                ).scalars()
            )
        assert replayed_actions.count("run.created") == 1
```

测试夹具必须设置 `RUN_EXECUTION_CONVERGENCE_ENABLED=true`。另加两条回归：开关为 `false` 时旧路径响应不变；`services/automation_service.py` 与 `agents/tiktok_cdo/data_sources.py` 的调用仍返回同一 `TaskRunResult` 形状。GitNexus 已确认 `run_task_now` 的 direct caller 包含 `services/automation_service.py:2424`。

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/integration/test_sources_tasks.py -q
```

Expected: FAIL。run-now 没有创建 `runs` 行。

- [ ] **Step 3: 改 task 服务（默认关闭时保留旧路径）**

`RUN_EXECUTION_CONVERGENCE_ENABLED=false` 时，`run_task_now` 继续走原 `execute_collection_task` 路径，响应与副作用不变。只有开关为 `true` 时，才执行下面的受治理路径。`services/automation_service.py:2424` 与 `agents/tiktok_cdo/data_sources.py` 是 `run_task_now` / `run_quick_collect` 的真实调用者；必须为它们加回归测试：开关关闭时旧响应不变，开关打开时仍返回同一 `TaskRunResult` 形状。

`task_service.py` 保留旧路径的 `execute_collection_task` 导入；受治理分支使用：

```python
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.services.exceptions import TaskRunExecutionError
from data_intelligence_hub.services.run_service import (
    create_run_for_task,
    execute_run_inline,
)
```

`run_task_now` 替换为：

```python
async def run_task_now(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> TaskRunResult:
    task = await get_task_or_raise(session, workspace, task_id)
    idempotency_key_hash = _manual_task_run_idempotency_key_hash(idempotency_key)

    if idempotency_key_hash is not None:
        existing_run = await runs_repository.find_by_idempotency_key(
            session,
            workspace_id=workspace.id,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_run is not None:
            existing_task_run = await runs_repository.get_last_task_run(
                session,
                run_id=existing_run.id,
            )
            if existing_task_run is None:
                raise TaskAlreadyRunningError
            return TaskRunResult(
                run=existing_task_run,
                idempotency_replayed=True,
                idempotency_key_hash=idempotency_key_hash,
            )
        legacy_run = await _find_manual_task_run_by_idempotency_key_hash(
            session,
            workspace_id=workspace.id,
            task_id=task.id,
            idempotency_key_hash=idempotency_key_hash,
        )
        if legacy_run is not None:
            return TaskRunResult(
                run=legacy_run,
                idempotency_replayed=True,
                idempotency_key_hash=idempotency_key_hash,
            )

    if task.status == "running":
        raise TaskAlreadyRunningError
    if task.status != "enabled":
        raise TaskNotRunnableError

    run = await create_run_for_task(
        session,
        workspace_id=workspace.id,
        project_id=task.project_id,
        task_id=task.id,
        trigger="manual",
        idempotency_key_hash=idempotency_key_hash,
    )
    if run.status != "queued":
        # 并发幂等重放命中已有行。返回它的最终 TaskRun。
        existing_task_run = await runs_repository.get_last_task_run(
            session,
            run_id=run.id,
        )
        if existing_task_run is None:
            raise TaskAlreadyRunningError
        return TaskRunResult(
            run=existing_task_run,
            idempotency_replayed=True,
            idempotency_key_hash=idempotency_key_hash,
        )
    execution = await execute_run_inline(session, run.id)
    task_run = await runs_repository.get_last_task_run(session, run_id=run.id)
    if task_run is None:
        raise TaskRunExecutionError(
            execution.run.error_message or "run_produced_no_task_run"
        )
    return TaskRunResult(
        run=task_run,
        idempotency_replayed=False,
        idempotency_key_hash=idempotency_key_hash,
    )
```

在 `services/exceptions.py` 加入：

```python
class TaskRunExecutionError(ServiceError):
    message = "task_run_execution_failed"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
```

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/integration/test_sources_tasks.py tests/unit/test_task_runs_route.py tests/unit/test_task_run_idempotency.py -q
```

Expected: 全部通过。历史 `task_runs.logs` 回退用例仍通过。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs impact "run_task_now" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/task_service.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/tests/integration/test_sources_tasks.py \
  apps/api/tests/unit/test_task_runs_route.py
git commit -m "refactor(tasks): execute task run-now through governed runs"
```

---

### Task 12: scheduler 入队收敛

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/scheduler/service.py`
- Test: `apps/api/tests/unit/test_scheduler.py`
- Test: `apps/api/tests/unit/test_scheduler_lease_renewal.py`

**Interfaces:**
- scheduler 只调用 `enqueue_scheduled_run`。不调用 `execute_collection_task`。
- 同一 task 同一时间槽只入队一次。cron 用分钟槽，freshness 用小时槽。

- [ ] **Step 1: 写失败测试**

在 `test_scheduler.py` 加入：

```python
@pytest.mark.asyncio
async def test_scheduler_tick_enqueues_due_task_without_executing() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(session, schedule_cron="* * * * *")
        await session.commit()
    scheduler = CollectionScheduler(session_factory, poll_interval_seconds=60)
    now = datetime.now(UTC)

    result = await scheduler.tick(now)

    assert result.started == 1
    async with session_factory() as session:
        runs = list((await session.execute(select(Run))).scalars())
        assert len(runs) == 1
        assert runs[0].status == "queued"
        assert runs[0].trigger == "schedule"
        task_runs = list((await session.execute(select(TaskRun))).scalars())
        assert task_runs == []


@pytest.mark.asyncio
async def test_scheduler_tick_does_not_duplicate_same_slot() -> None:
    session_factory = await _create_session_factory()
    async with session_factory() as session:
        await _create_collection_task(session, schedule_cron="* * * * *")
        await session.commit()
    scheduler = CollectionScheduler(session_factory, poll_interval_seconds=60)
    now = datetime.now(UTC)

    first = await scheduler.tick(now)
    second = await scheduler.tick(now)

    assert first.started == 1
    assert second.started == 0
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(Run))
        assert int(count or 0) == 1
```

在 `test_scheduler.py` 顶部补 `from sqlalchemy import func` 与 `from data_intelligence_hub.models import Run`。

删除以下测试，因为它们测的是 scheduler 直接执行：

- `test_scheduler_tick_merges_source_payload_with_task_metadata`
- `test_scheduler_tick_counts_task_lock_conflict_as_skipped`
- `test_scheduler_tick_fails_task_run_after_collector_timeout`

把 `test_scheduler_tick_runs_due_collection_task` 改名为 `test_scheduler_tick_enqueues_due_collection_task`，断言改为 `Run.status == "queued"` 与 `TaskRun` 为空。把 `test_scheduler_tick_runs_due_auto_freshness_task_without_cron` 的断言同样改为 queued run。`test_scheduler_tick_retries_failed_auto_freshness_task_after_delay` 仍保留：它断言失败后到期会再次入队。`test_scheduler_tick_skips_auto_freshness_task_after_retry_budget` 断言不新增 run。

在 `test_scheduler_lease_renewal.py` 中，把 patch 目标从 `execute_collection_task` 改为 `enqueue_scheduled_run`，让假的 enqueue 函数 `await asyncio.sleep(...)` 后返回一个 `Run`。断言不变：tick 期间租约续期，续期失败后停止认领。

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_scheduler.py tests/unit/test_scheduler_lease_renewal.py -q
```

Expected: FAIL。scheduler 仍直接执行，`TaskRun` 非空。

- [ ] **Step 3: 改 scheduler**

在 `scheduler/service.py` 删除：

```python
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.exceptions import TaskAlreadyRunningError
```

加入：

```python
from data_intelligence_hub.services.run_service import enqueue_scheduled_run
```

把任务循环中的 `execute_collection_task(...)` 替换为：

```python
                    try:
                        run = await enqueue_scheduled_run(
                            session,
                            task=task,
                            now=current_time,
                        )
                        if run is not None:
                            started += 1
                    except Exception:
                        task_errors += 1
                        logger.exception(
                            "collection_scheduler_enqueue_failed",
                            task_id=str(task.id),
                        )
                    finally:
                        self._running_task_ids.discard(task.id)
```

保留 `if task.id in self._running_task_ids` 去重。保留 quick_collect 跳过与 policy failure 跳过。

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_scheduler.py tests/unit/test_scheduler_lease_renewal.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs impact "CollectionScheduler" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/scheduler/service.py \
  apps/api/tests/unit/test_scheduler.py \
  apps/api/tests/unit/test_scheduler_lease_renewal.py
git commit -m "refactor(scheduler): enqueue governed runs"
```

---

### Task 13: 旧入口扫描守卫

**Files:**
- Create: `apps/api/tests/unit/test_legacy_run_entrypoints.py`

**Interfaces:**
- 生产代码中，`execute_collection_task` 只允许定义在 `collector_service.py`。不得从 quick、task、scheduler、MCP 入口直接调用。
- `run_quick_collect` 与 `run_task_now` 只允许在服务定义、MCP 适配器、agent 适配器与测试中出现。

- [ ] **Step 1: 写失败测试**

```python
"""旧执行入口扫描守卫。"""

from __future__ import annotations

import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
SRC = API_ROOT / "src/data_intelligence_hub"

FORBIDDEN_DIRECT_CALLERS = (
    SRC / "services/quick_collect_service.py",
    SRC / "services/task_service.py",
    SRC / "scheduler/service.py",
    SRC / "mcp_runtime/collect_service.py",
    SRC / "agents/tiktok_cdo/data_sources.py",
)


def test_no_direct_execute_collection_task_calls_in_legacy_entries() -> None:
    pattern = re.compile(r"\bexecute_collection_task\s*\(")
    offenders = [
        str(path.relative_to(API_ROOT))
        for path in FORBIDDEN_DIRECT_CALLERS
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_collector_service_keeps_definition_only() -> None:
    text = (SRC / "services/collector_service.py").read_text(encoding="utf-8")
    assert "async def execute_collection_task(" in text


def test_quick_and_task_services_use_governed_run_service() -> None:
    quick = (SRC / "services/quick_collect_service.py").read_text(encoding="utf-8")
    task = (SRC / "services/task_service.py").read_text(encoding="utf-8")
    assert "from data_intelligence_hub.services.run_service import" in quick
    assert "from data_intelligence_hub.services.run_service import" in task
    assert "execute_run_inline" in quick
    assert "execute_run_inline" in task
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_legacy_run_entrypoints.py -q
```

Expected: FAIL，最后一个测试失败。若前两个失败，说明 Task 10/11/12 未完成。

- [ ] **Step 3: 删除遗留导入**

检查并删除以下文件中未使用的 `execute_collection_task` 导入：

```bash
rg -n "execute_collection_task" apps/api/src/data_intelligence_hub
```

Expected after fix: 只有 `services/collector_service.py` 的定义与内部调用。

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_legacy_run_entrypoints.py -q
uv run ruff check src/data_intelligence_hub
```

Expected: 3 passed。ruff 无错误。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/tests/unit/test_legacy_run_entrypoints.py \
  apps/api/src/data_intelligence_hub
git commit -m "test(run): guard legacy execution entrypoints"
```

---

### Task 14: worker 开关、健康与配置

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`
- Modify: `apps/api/src/data_intelligence_hub/schemas/health.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/health.py`
- Test: `apps/api/tests/unit/test_run_worker_settings.py`
- Test: `apps/api/tests/unit/test_run_worker_runtime.py`

**Interfaces:**
- 新配置：`run_worker_enabled`（默认 false）、`run_execution_convergence_enabled`（默认 false）、`run_worker_poll_interval_seconds`、`run_worker_lease_seconds`、`run_worker_renew_interval_seconds`、`run_retry_max_attempts`、`run_retry_base_delay_seconds`、`run_retry_max_delay_seconds`。
- 健康响应新增 `run_worker_enabled`。

- [ ] **Step 1: 写失败测试**

```python
"""worker 开关、配置与健康字段测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from data_intelligence_hub.core.config import Settings
from data_intelligence_hub.schemas.health import HealthResponse


def test_worker_settings_defaults() -> None:
    settings = Settings()
    assert settings.run_worker_enabled is False
    assert settings.run_execution_convergence_enabled is False
    assert settings.run_worker_poll_interval_seconds == 5.0
    assert settings.run_worker_lease_seconds == 300.0
    assert settings.run_worker_renew_interval_seconds is None
    assert settings.run_retry_max_attempts == 3
    assert settings.run_retry_base_delay_seconds == 2.0
    assert settings.run_retry_max_delay_seconds == 30.0


def test_health_response_exposes_worker_switch() -> None:
    response = HealthResponse(
        service="api",
        environment="test",
        status="ok",
        database="connected",
        schema="current",
        schema_revision="202610220064",
        schema_head="202610220064",
        scheduler_enabled=False,
        run_worker_enabled=True,
        run_execution_convergence_enabled=False,
    )
    payload = json.loads(response.model_dump_json(by_alias=True))
    assert payload["run_worker_enabled"] is True
    assert payload["run_execution_convergence_enabled"] is False


async def test_health_route_reports_worker_switch(monkeypatch) -> None:
    from data_intelligence_hub.api.routes import health as health_module

    async def connected() -> str:
        return "connected"

    async def current():
        return SimpleNamespace(
            status="current",
            current_revision="202610220064",
            head_revision="202610220064",
        )

    monkeypatch.setattr(health_module, "check_database", connected)
    monkeypatch.setattr(health_module, "check_database_schema", current)
    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: Settings(run_worker_enabled=True),
    )

    response = await health_module.health()

    assert json.loads(response.body)["run_worker_enabled"] is True
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_worker_settings.py -q
```

Expected: FAIL。配置与健康字段不存在。

- [ ] **Step 3: 加配置**

在 `core/config.py` 的 worker 配置段加入：

```python
    # C6：默认关闭。C14 只读验收后由 PG0 发布批次显式打开。
    run_worker_enabled: bool = False
    run_execution_convergence_enabled: bool = False
    run_worker_poll_interval_seconds: float = Field(default=5.0, gt=0)
    run_worker_lease_seconds: float = Field(default=300.0, gt=0)
    run_worker_renew_interval_seconds: float | None = Field(default=None, gt=0)
    run_retry_max_attempts: int = Field(default=3, ge=1, le=5)
    run_retry_base_delay_seconds: float = Field(default=2.0, ge=0, le=60)
    run_retry_max_delay_seconds: float = Field(default=30.0, ge=0, le=300)
```

把重试配置传入 `RunWorkerRuntime`：

```python
            run_worker = RunWorkerRuntime(
                session_factory=async_session_factory,
                lease_seconds=settings.run_worker_lease_seconds,
                renew_interval_seconds=settings.run_worker_renew_interval_seconds,
                poll_interval_seconds=settings.run_worker_poll_interval_seconds,
            )
```

在 `schemas/health.py` 加入：

```python
    run_worker_enabled: bool
    run_execution_convergence_enabled: bool
```

在 `api/routes/health.py` 的 `HealthResponse(...)` 加入：

```python
        run_worker_enabled=settings.run_worker_enabled,
        run_execution_convergence_enabled=settings.run_execution_convergence_enabled,
```

- [ ] **Step 4: 运行测试并确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_worker_settings.py tests/unit/test_run_worker_runtime.py -q
```

Expected: 全部通过。lifespan 测试仍通过，`FakeRuntime` 接收新 kwargs 不报错。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/src/data_intelligence_hub/schemas/health.py \
  apps/api/src/data_intelligence_hub/api/routes/health.py \
  apps/api/tests/unit/test_run_worker_settings.py \
  apps/api/tests/unit/test_run_worker_runtime.py
git commit -m "feat(run): expose worker switches and retry settings"
```

---

### Task 15: 共用 compose 的开关事实（默认关闭）

**Files:**
- Modify: `configs/deploy/scrapy/docker-compose.yml`（生产 A 与 B 共用）
- Modify: `apps/api/.env.example`
- Test: `apps/api/tests/unit/test_deploy_worker_facts.py`

**Interfaces:**
- 生产 A/B 共用 `configs/deploy/scrapy/docker-compose.yml`；**不修改 `configs/deploy/scrapy-new/**`**。
- `RUN_WORKER_ENABLED` 默认 `false`。
- `RUN_EXECUTION_CONVERGENCE_ENABLED` 默认 `false`。
- `SCHEDULER_ENABLED` 默认 `false`。
- compose 声明 worker 轮询、租约与重试配置。
- 不改 edge、网络、volume、端口。本任务不部署；发布由总索引 §8.4 的 PG0 发布批次执行；C14 只做只读验收。

- [ ] **Step 1: 写失败测试**

```python
# 共用 compose 的 worker/收敛开关事实。

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "configs/deploy/scrapy/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "apps/api/.env.example"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_worker_and_convergence_are_off_by_default() -> None:
    text = _text(COMPOSE)
    assert "RUN_WORKER_ENABLED: ${SCRAPY_RUN_WORKER_ENABLED:-false}" in text
    assert (
        "RUN_EXECUTION_CONVERGENCE_ENABLED: "
        "${SCRAPY_RUN_EXECUTION_CONVERGENCE_ENABLED:-false}"
    ) in text
    assert "SCHEDULER_ENABLED: ${SCRAPY_SCHEDULER_ENABLED:-false}" in text


def test_compose_declares_worker_retry_settings() -> None:
    text = _text(COMPOSE)
    for key in (
        "RUN_WORKER_POLL_INTERVAL_SECONDS",
        "RUN_WORKER_LEASE_SECONDS",
        "RUN_RETRY_MAX_ATTEMPTS",
        "RUN_RETRY_BASE_DELAY_SECONDS",
        "RUN_RETRY_MAX_DELAY_SECONDS",
    ):
        assert key in text


def test_scrapy_new_is_not_used() -> None:
    assert "scrapy-new" not in _text(COMPOSE)


def test_env_example_has_switches() -> None:
    text = _text(ENV_EXAMPLE)
    for key in (
        "RUN_WORKER_ENABLED=false",
        "RUN_EXECUTION_CONVERGENCE_ENABLED=false",
        "RUN_RETRY_MAX_ATTEMPTS",
    ):
        assert key in text
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_deploy_worker_facts.py -q
```

Expected: FAIL。共享 compose 仍是旧默认值，且没有收敛开关。

- [ ] **Step 3: 改共享 compose**

把现有 `RUN_WORKER_ENABLED` 一行替换为：

```yaml
      # C6：默认关闭。C14 只读验收后由 PG0 发布批次显式打开。
      RUN_WORKER_ENABLED: ${SCRAPY_RUN_WORKER_ENABLED:-false}
      RUN_EXECUTION_CONVERGENCE_ENABLED: ${SCRAPY_RUN_EXECUTION_CONVERGENCE_ENABLED:-false}
      RUN_WORKER_POLL_INTERVAL_SECONDS: ${SCRAPY_RUN_WORKER_POLL_INTERVAL_SECONDS:-5}
      RUN_WORKER_LEASE_SECONDS: ${SCRAPY_RUN_WORKER_LEASE_SECONDS:-300}
      RUN_RETRY_MAX_ATTEMPTS: ${SCRAPY_RUN_RETRY_MAX_ATTEMPTS:-3}
      RUN_RETRY_BASE_DELAY_SECONDS: ${SCRAPY_RUN_RETRY_BASE_DELAY_SECONDS:-2}
      RUN_RETRY_MAX_DELAY_SECONDS: ${SCRAPY_RUN_RETRY_MAX_DELAY_SECONDS:-30}
```

确认 `SCHEDULER_ENABLED` 仍是 `${SCRAPY_SCHEDULER_ENABLED:-false}`。不要新增 `scrapy-new` 分支。

- [ ] **Step 4: 改 `.env.example`**

```dotenv
RUN_WORKER_ENABLED=false
RUN_EXECUTION_CONVERGENCE_ENABLED=false
RUN_WORKER_POLL_INTERVAL_SECONDS=5
RUN_WORKER_LEASE_SECONDS=300
RUN_RETRY_MAX_ATTEMPTS=3
RUN_RETRY_BASE_DELAY_SECONDS=2
RUN_RETRY_MAX_DELAY_SECONDS=30
```

- [ ] **Step 5: 校验 compose 与测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
docker compose -f configs/deploy/scrapy/docker-compose.yml config --quiet
cd apps/api
uv run pytest tests/unit/test_deploy_worker_facts.py -q
```

Expected: `docker compose config` 退出码 0；4 passed。若本机缺少生产必填变量，只运行测试，并在 C14 的 A/B 环境执行 `config --quiet`。

- [ ] **Step 6: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add configs/deploy/scrapy/docker-compose.yml \
  apps/api/.env.example \
  apps/api/tests/unit/test_deploy_worker_facts.py
git commit -m "ops(run): default worker and convergence switches to false"
```

Expected: `detect-changes` 不含 `partial: true` / `truncated: true`；没有 `configs/deploy/scrapy-new/**` 改动。

---

### Task 16: 全量验收与 PG0/C14 交接

**Files:**
- 不改代码。只运行验收命令，记录结果，交给 PG0 发布批次与 C14。
- 本任务不创建 commit。

**Interfaces:**
- Consumes: C6 Task 1–15 的提交；C5 `RunBudget`；C4 `execution_steps` 与 `services.run_creation.create_run_with_audit`（run.created 唯一写入口）；Task 14 的开关配置；Task 15 的共享 compose 事实。
- Produces: C6 本地验收结果；PG0 发布批次交接清单（迁移、备份、应用、开关切换、回滚）；C14 只读验收清单（健康、canary、preflight、浏览器 `/runs`）。
- 本任务只读：不修改代码、不写生产文件、不执行迁移、不改 `.env.production`、不重启容器、不切换开关。结束时 `git status --porcelain -uno` 必须为空。

- [ ] **Step 1: 运行 C6 相关测试**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest \
  tests/unit/test_run_step_attempt_migration.py \
  tests/unit/test_run_retry.py \
  tests/unit/test_run_step_plan.py \
  tests/unit/test_run_executor.py \
  tests/unit/test_run_executor_multi_step.py \
  tests/unit/test_run_step_runner.py \
  tests/unit/test_run_executor_orm.py \
  tests/unit/test_run_worker_runtime.py \
  tests/unit/test_run_queue.py \
  tests/unit/test_run_lease_fence.py \
  tests/unit/test_run_routes.py \
  tests/unit/test_run_cancel_idempotency.py \
  tests/unit/test_run_audit_events.py \
  tests/unit/test_run_limit_enforcement.py \
  tests/unit/test_legacy_run_entrypoints.py \
  tests/unit/test_run_worker_settings.py \
  tests/unit/test_run_completed_event.py \
  tests/unit/test_deploy_worker_facts.py \
  tests/integration/test_quick_collect_routes.py \
  tests/integration/test_quick_collect_async.py \
  tests/integration/test_sources_tasks.py \
  tests/unit/test_scheduler.py \
  tests/unit/test_scheduler_lease_renewal.py \
  -q
```

Expected: 0 failed。

- [ ] **Step 2: 运行全量后端测试与静态检查**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest -q
uv run ruff check src tests
uv run mypy src
uv run alembic heads
```

Expected:
- pytest 0 failed。
- ruff 无错误。
- mypy 无错误。
- `alembic heads` 只有一行 `202610220064 (head)`。这是 C6 的本地退出 head；平台最终 head 由 master plan 的后续切片推进到 `202610220070`，生产验收不以此处的 062 为准。

- [ ] **Step 3: 运行 GitNexus 全量比对**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
node .gitnexus/run.cjs detect-changes --scope all --repo .
node .gitnexus/run.cjs detect-changes --scope compare --base-ref main --repo .
```

Expected: 两次输出都不含 `partial: true` 或 `truncated: true`。若出现，重跑。零结果不代表无影响，必须结合测试与调用方报告判断。

- [ ] **Step 4: 确认旧入口扫描**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6
rg -n "execute_collection_task\s*\(" apps/api/src/data_intelligence_hub
rg -n "run_quick_collect\s*\(|run_task_now\s*\(" apps/api/src/data_intelligence_hub
```

Expected:
- 第一条只命中 `services/collector_service.py` 的函数定义。
- 第二条只命中服务定义、`mcp_runtime/collect_service.py`、`agents/tiktok_cdo/data_sources.py`。不得命中 scheduler、quick route、task route。

- [ ] **Step 4A: 审计与取消幂等验收**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_audit_events.py tests/unit/test_run_cancel_idempotency.py -q
rg -n "dataset_quality|market_quality|evaluate_and_persist_market_quality|ensure_market_quality" \
  src/data_intelligence_hub/services/run_executor.py \
  src/data_intelligence_hub/services/run_executor_adapters.py
rg -n "append_audit_event|audit_run_event" src/data_intelligence_hub/services/run_audit.py \
  src/data_intelligence_hub/services/run_executor.py \
  src/data_intelligence_hub/services/run_step_runner.py \
  src/data_intelligence_hub/services/run_cancel_service.py
rg -n 'action="run.created"' src/data_intelligence_hub
rg -n "runs_repository\.create_run\(" src/data_intelligence_hub
rg -n "from data_intelligence_hub.repositories.runs import create_run" src/data_intelligence_hub
```

`runs_repository.create_run` 的唯一允许调用方是 C4 接缝 `services/run_creation.py`。C6 的 `services/run_service.py` 与 `api/routes/runs.py` 必须调用 C4 `create_run_with_audit`；直接调用仓储或直接 import `create_run` 都使验收失败。`action="run.created"` 只允许出现在 C4 接缝 `services/run_creation.py`；C6 不写该动作，只消费 C4 接缝。

Expected:
- 测试通过：每个 completed run 恰好一条 `run.completed`；failed/cancelled 分别发 `run.failed` / `run.cancelled`；重试发 `run.retry_scheduled` 与 `run.retry_exhausted`；创建经 C4 接缝发 `run.created`；取消发 `run.cancel_requested` 与 `run.cancelled`。
- 同键同参取消重放原结果；同键不同参返回 `idempotency_conflict`；并发取消只释放一次预算；重放与冲突不新增审计行。
- `services.run_service` 可导入 `cancel_task_runs`、`RunCancellationResult`、`CancellationError`，供 C13 直接使用。
- `runs_repository.create_run` 与 `action="run.created"` 都只命中 C4 `services/run_creation.py`；C6 直接调用仓储或直接 import `create_run` 为零命中。
- `rg` 只命中注释或错误提示文本，不命中 import 或函数调用。C6 不依赖 C8。
- C8 的 `consume_completed_runs` 能用本切片测试库中的 `run.completed` 生成一条 `market_assessments`；重复消费为零新增。该验证由 C8 执行并在 C14 交接中引用。

- [ ] **Step 4B: C5 run limits 验收**

```bash
cd /Users/lute/Project/data_scrapy-gov-c6/apps/api
uv run pytest tests/unit/test_run_limit_enforcement.py -q
rg -n "max_pages|max_records" \
  src/data_intelligence_hub/services/run_executor.py \
  src/data_intelligence_hub/services/run_step_runner.py \
  src/data_intelligence_hub/services/run_collector_call.py
rg -n "resolve_run_limits|RunLimitsResolver" src/data_intelligence_hub
rg -n "class RunLimits|class RunBudget|RunBudget\(Protocol\)" src/data_intelligence_hub
```

Expected:
- 测试通过：`None` 不限制，`0` 零容忍；`max_pages_exceeded` 在下一页前停止，`max_records_exceeded` 在超限记录后停止；超限后不再调用 collector，不写剩余记录。
- C6 只在 `run_executor_adapters.py` 调用 C5 `resolve_run_limits`；`max_pages` / `max_records` 只作为 `RunLimits` 字段传递，没有第二份解析逻辑。
- `class RunLimits` 只在 C5 `services/run_limits.py` 命中；`class RunBudget` / `RunBudget(Protocol)` 只在 C5 `services/run_budget.py` 命中。C6 只导入或原样 re-export。

- [ ] **Step 5: 交接 PG0 发布批次与 C14**

把以下事实交给 PG0 发布批次与 C14。PG0 发布批次执行备份、迁移、应用、开关切换与回滚；C14 只做只读健康、canary、preflight 与浏览器验收，并记录证据。C14 不写数据库、不改 compose/env、不重启容器、不切换开关。

**1. 旧入口代码扫描**

```bash
cd /opt/data-achieve-scrapy/app
rg -n "execute_collection_task\s*\(" apps/api/src/data_intelligence_hub
rg -n "run_quick_collect\s*\(|run_task_now\s*\(" apps/api/src/data_intelligence_hub
```

验收：生产 commit 与本地 C6 commit 一致，扫描结果与 Step 4 相同。

**2. Postgres 并发验证**

SQLite 测试不证明 `FOR UPDATE SKIP LOCKED`、部分唯一索引和并发 attempt 编号。C6 在隔离的 PostgreSQL 16 上执行并发验证并提交报告；PG0 与 C14 只读复核：

- 两个 worker 同时 `claim_next_run`，只有一个领取成功。
- 两个 worker 同时写同一 `(run_id, step_index, attempt_number)`，唯一约束只允许一行。
- 两个 worker 同时写同一账本 `idempotency_key`，只落一行。
- `cancel_run` 与 worker 终态写入并发，最终状态是 `cancelled`，预算只释放一次。
- 两个并发取消请求使用同一 `idempotency_key`，只有一个事务领取成功，另一个重放；`quota_accounts.reserved_usd` 只减少一次。
- 两个并发取消请求使用同一键但不同 `reason_code`，恰好一个返回 409 `idempotency_conflict`，另一个成功。
- 租约过期后第二个 worker 接管，旧 worker 的续期与终态写入失败。

验收：并发测试 0 failed。不得用 SQLite 结果替代。C14 只读复核测试报告与结果，不执行写库并发测试。

**3. 生产 A/B 迁移（PG0 发布批次执行）**

生产 A：
- 主机 `ubuntu@43.163.92.244`。
- Compose `configs/deploy/scrapy/docker-compose.yml`。
- 环境文件 `/opt/data-achieve-scrapy/.env.production`。
- 先备份 `pg_dump`、`.env.production`、镜像 ID 与 `HEAD`。
- 运行：

```bash
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" run --rm --no-deps api alembic upgrade head
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api console
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge
```

- 不得重建 edge。不得运行不带服务名的 `docker compose up -d`。
- 验证 `/api/health` 的 `schema_revision` 与 `schema_head` 都是 master plan 的最终迁移 `202610220070`。C6 只保证自己的 062 迁移在链上；生产最终值取 master/final 链，不得写死 C6 的 062。
- `scripts/preflight-production.sh` 通过 `SCRAPY_EXPECTED_SCHEMA` 读取期望 schema。PG0 发布批次必须在发布前把该环境变量设为 master/final 的 `202610220070`，再只读运行脚本；C6 与 C14 都不修改脚本默认值，也不把 `202610220064` 写入 preflight。

生产 B：
- 主机 `ubuntu@101.34.52.232`。
- 域名 `https://scrapy.lute-tlz-dddd.top`。
- Compose `configs/deploy/scrapy/docker-compose.yml`（与 A 共用；不修改 `configs/deploy/scrapy-new/**`）。
- 先取得 B 的目标授权与备份，再应用同一迁移，再替换 `api console`。
- 验证 `/api/health` 的 schema 是 master/final 的 `202610220070`；`run_worker_enabled` 在 PG0 发布批次显式打开前必须是 `false`。

顺序：A 备份 → A 迁移 → A 代码 → B 备份 → B 迁移 → B 代码。任一环境迁移失败时停止，不回滚另一套。以上命令只由 PG0 发布批次执行；C14 在发布后只读检查 `/api/health`、canary 与公网响应。

**4. 共用 compose 事实**

- A/B 共用 `configs/deploy/scrapy/docker-compose.yml`。
- `RUN_WORKER_ENABLED` 默认 false；`RUN_EXECUTION_CONVERGENCE_ENABLED` 默认 false；`SCHEDULER_ENABLED` 默认 false。
- 两套都声明 worker 轮询、租约与三个重试配置。
- 总索引 §8.4 的 PG0 发布批次先以默认关闭状态发布并完成迁移；C14 完成只读健康检查后，由 PG0 发布批次在 `.env.production` 显式打开 `SCRAPY_RUN_WORKER_ENABLED=true` 与 `SCRAPY_RUN_EXECUTION_CONVERGENCE_ENABLED=true`，重启 api；C14 再只读复核 `/api/health` 的 `run_worker_enabled=true` 与 `run_execution_convergence_enabled=true`。
- 不得在 C14 只读验收前打开开关；不得修改 `configs/deploy/scrapy-new/**`。

**4A. 空库迁移循环**

- 这是 C6 切片级迁移循环，不是平台最终 head 验收：PostgreSQL 15 空库执行 `alembic upgrade 202610220064` → `alembic downgrade 202610220063` → `alembic upgrade 202610220064`；三次退出码 0。
- 循环后 `alembic heads` 只有一行 `202610220064`。
- 空库验证证明 `run_step_attempts`、`run_steps` 扩展列、`runs` 取消幂等列与 `uq_run_steps_task_run_id` / `uq_runs_workspace_cancel_idempotency` 可重复升降。
- PG0 发布批次在完整链（含 `202610220065`–`202610220070`）上再执行一次空库升级到 `202610220070`，作为生产目标版本的证据。

**5. 浏览器 `/runs` 查看（C14 只读）**

- 打开 A 与 B 的 `/runs`。C14 只观察 PG0 发布批次已准备的 run，不创建、不取消、不重试 run。
- 观察一条多步骤 run。确认步骤数、`step_index`、状态、`records_count`、`total_cost_usd` 与 `/api/runs/{run_id}/steps` 一致。
- 确认 `outcome` 只出现四值，`runs.status` 不出现 `degraded` 或 `held`。
- 取消 `queued` 与 `running` run 的行为由 PG0 发布批次在发布验收中执行；C14 只读复核取消后的状态、租约清空、`cancel_idempotency_key_hash` / `cancel_reason_code` 与未开始步骤的 `skipped`。
- attempt 逐条视图当前没有合同路由。C14 若要展示 attempts，先升级冻结契约并新增路径；不得用 `/steps` 冒充 attempts。

**6. 回滚（PG0 发布批次执行）**

- 由 PG0 发布批次先设 `SCRAPY_RUN_WORKER_ENABLED=false` 与 `SCRAPY_RUN_EXECUTION_CONVERGENCE_ENABLED=false`，重启 api，停止新领取并恢复旧 quick/run-now 路径。
- 代码回滚到上一镜像。
- `202610220064` 的 downgrade 只在 `run_step_attempts` 为空时执行。有 attempt 数据时保留表；旧代码不读该表，也不读 `runs` 取消幂等列。
- 不修改已发布报告、账本或已终态 run。C14 只读复核回滚后的健康与公网响应。

- [ ] **Step 6: 记录结果**

PG0 发布批次记录发布事实：commit、两套 schema（`202610220070`）、worker/convergence/scheduler 开关、迁移与备份路径、`SCRAPY_EXPECTED_SCHEMA` 值、回滚命令。C14 在只读验收记录中写明：健康与 canary 结果、Postgres 并发报告复核（含取消幂等）、空库迁移循环证据复核、浏览器 `/runs` 结果、旧入口扫描结果。C6 不写生产报告文件。

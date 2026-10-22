# C5 预算、账本与定价 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 `tool_prices` 为唯一价格事实源，建立进程级价格快照锁、严格缺价失败、按 run 多 gate 授权、原子预算预留、追加式成本账本、`quota_accounts`、`tool_calls` 与 quota 端点，并把 `remaining_budget` 写回 `task_runs`。

**Architecture:** `tool_prices` 表是唯一价格事实源，按 `tool_id`、币种与 `price_book_version` 保存单价与有效窗口。`tool_catalog/fixtures/price_book_v1.json` 只作种子输入，由 `scripts/seed_tool_prices.py` 写入 `tool_prices`，运行时不得读取。`services/pricing.py` 是价格簿唯一业务入口：启动时通过 `repositories/tool_prices.py` 从数据库读取当前有效快照并锁定，之后所有报价读同一份快照。`services/budget_service.py` 用 `authorizations.max_cost_usd` 控制单 run，`authorizations.max_cost_usd` 由 C4 `workbench_tasks.max_cost_usd` 经 `create_order_run_authorizations` 拆分得到；用 `quota_accounts` 控制项目额度，用 `run_ledger_entries` 的六种 `entry_kind` 记录估算、预留、结算、释放与阻断。**C5 是 `run_ledger_entries` 的唯一服务写入口**；C6 只通过 `RunBudget` 适配器调用 `reserve` / `settle` / `mark_unknown` / `cancel`，不得直接调用 `record_entry`。C5 还拥有 C1 登记的 `workbench_approval_actions` 与两个内联批准路径 `POST /api/workbench/tasks/{task_id}/approvals`、`POST /api/workbench/tasks/{task_id}/approvals/{approval_id}`；只有 owner/admin 可以决定，请求人不得自批，C5 不建独立收件箱，也不发明未登记路径。`services/run_limits.py` 从同一 `workbench_tasks` 读取 `max_pages` / `max_records`，`None` 表示不限制；C6 与 collector 必须在超限时立即停止。预算、额度与价格变更、批准/拒绝、阻断/释放全部调用 C2 `services.audit_log.append_audit_event` 写唯一 `audit_events`，动作名只使用 C1 `audit-actions.v1` 已登记的 `budget.price.changed`、`budget.limit.changed`、`budget.blocked`、`budget.released`。`runs` 与 `run_steps` 仍是唯一执行真相；`run_steps` 与 `task_runs` 保持 1─1。C5 只提供 pricing、budget、tool_call API、run limits、quota 端点与内联批准路径，执行器接线归 C6；C5 不改步骤模型、状态枚举与 MCP。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2 async、Alembic、PostgreSQL 16 / SQLite、pytest、`Decimal`。

## Global Constraints

- 隔离 worktree：`/Users/lute/Project/data_scrapy-gov-c5`。C5 从 `feat/gov-c4` 创建 `feat/gov-c5`。主工作树 `/Users/lute/Project/data_scrapy` 只用于创建 worktree 和复制本计划。C0 的起始提交 `f0560ca` 不是 C5 的开工 HEAD。执行 C5 前必须已合入 C0、C1、C2、C3、C4，且 `alembic heads` 只有 `202610220060`。
- **C1 独占 registry。** C5 只消费 C1 登记的 `tool_prices`、`quota_accounts`、`tool_calls`、`workbench_approval_actions`、`authorizations.run_id`、`run_ledger_entries` 与错误码；不修改契约文档或机器 registry。C1 必须在 `tables` 与 `phases[].objects` 正式登记 `tool_prices`，并移除旧的延期登记。C1 必须登记 `(run_id, gate_id)` 部分唯一约束 `uq_authorizations_run_gate`（`WHERE run_id IS NOT NULL`）、`tool_calls.step_id`、`workbench_approval_actions` 的 13 列/3 个 CHECK/2 个索引、quota 路径、批准路径与 `tool_not_priced` / `quota_exceeded` / `approval_required` / `quota_account_missing` / `approval_not_found` / `approval_self_approval_forbidden` / `approval_state_conflict`。
- **消费 C4 订单预算与执行限额。** `workbench_tasks.max_cost_usd` 是订单总预算；`max_pages` 与 `max_records` 是执行限额。C5 不新建订单预算表，不复制 C4 字段。`create_order_run_authorizations` 读取同一任务单的全部逐市场 run，把订单预算拆成 per-market `G-Cost` 授权：每行金额量化到 6 位小数，所有行（含 blocked G-Plan 市场）金额之和必须精确等于订单上限；主市场行取得十进制余数。`max_cost_usd` 为空时每行金额为 `0.000000`，不读取任何默认上限；enforce 模式必须阻断（`approval_required`），shadow 模式只记账并写 block。不得用 `default_run_authorization_max_cost_usd` 或任何硬编码值补足。
- **Run 限额。** `services/run_limits.py` 提供 `RunLimits` 与 `resolve_run_limits`。`max_pages` / `max_records` 来自 C4 `workbench_tasks`；`None` 表示不限制，`0` 表示零容忍。C6 与 collector 必须在每次翻页前检查页数、每页入库后检查记录数，超限立即抛 `RunLimitExceededError`（`max_pages_exceeded` / `max_records_exceeded`）并停止，不得继续请求下一页或把剩余记录写入。
- **内联批准只走 C1 路径。** owner/admin 对预算超支、加购与项目密钥变更使用 `workbench_approval_actions`，只暴露 C1 登记的 `POST /api/workbench/tasks/{task_id}/approvals` 与 `POST /api/workbench/tasks/{task_id}/approvals/{approval_id}`。请求人不得批准自己的动作（数据库 CHECK `ck_workbench_approval_actions_self_approval` + 服务层双重校验，`approval_self_approval_forbidden`）。C5 不建独立收件箱、不新增未登记路径、不改 C1 契约。
- **项目 ACL。** `GET /api/quota`、`GET /api/quota/projects/{project_id}`、授权读取与批准写入都必须调用 C2 `api.authz.require_project_access`；读 `manage=False`，写 `manage=True`。同工作区 member 跨项目返回 403 `project_access_forbidden`，跨工作区返回 404 `project_not_found`。不得按 `workspace_members.role` 自行放行。
- **统一 C2 审计。** 价格变更、额度/订单上限变更、批准/拒绝、预算阻断与释放只调用 `services.audit_log.append_audit_event` 写唯一 `audit_events` 表；动作名只用 C1 `audit-actions.v1` 的 `budget.price.changed`、`budget.limit.changed`、`budget.blocked`、`budget.released`。批准写 `budget.limit.changed` 且 `result="success"`，拒绝写同一动作且 `result="denied"`，`details.decision` 区分。额度变更只允许经 `set_project_quota_limit`，不得直接调用 `update_quota_limits` 绕过审计。不得自造 `budget.approval.*` 等未登记动作，不得建第二张审计表。
- **PG0 严格模式。** `BUDGET_ENFORCEMENT_ENABLED=true` 与 `STRICT_PRICE_ENABLED=true` 是 PG0 发布门槛。PG0 之前只允许 shadow（两者 `false`）；PG0 发布批次必须把两者置 `true` 后才可验收。生产备份、`alembic upgrade`、`seed_tool_prices`、compose/env 变更、重启与流量切换只属于总索引 §8.4 的 PG0 发布批次；C14 只做只读健康检查与浏览器验收，不执行任何写操作。
- **唯一价格事实源（正式表方案）。** 本计划采用正式 `tool_prices` 表；旧的延期/仅 fixture 方案作废。`tool_prices` 是唯一价格事实源；C5 建表、ORM、仓储、迁移与种子脚本。运行时只允许 `services/pricing.py` 经 `repositories/tool_prices.py` 从 `tool_prices` 读取价格。`apps/api/src/data_intelligence_hub/tool_catalog/fixtures/price_book_v1.json` 只允许被 `repositories/tool_prices.py` 的种子函数（由 `scripts/seed_tool_prices.py` 调用）和测试种子读取，用于向 `tool_prices` 写入种子，不得作为运行时价格源。禁止第二价格源：不得在运行时回退 fixture、不得硬编码第二份价格表、不得从其他配置读取价格。
- 迁移编号：C0 从 `202610210055` 合入 B5 的 `202610210056`、`202610210057`；C1 不新增迁移；C2 增加 `202610220058`；C3 增加 `202610220059`；C4 增加 `202610220060`；C5 只新增 `202610220061`，`down_revision=202610220060`。C5 不得再使用 `202610210056`/`202610210057` 作为自己的 revision。
- `run_ledger_entries` 只有八列：`id`、`run_id`、`step_id`、`entry_kind`、`amount_usd`、`balance_after_usd`、`idempotency_key`、`created_at`。不得增删列。
- `entry_kind` 只有六值：`estimate`、`reserve`、`accrued`、`settle`、`release`、`block`。不得改写为 `entry_type` 或 `phase`。
- `settle` 金额必须是正数。`release` 金额必须是负数。`estimate`、`reserve`、`accrued`、`block` 金额不得为负数。
- 实际成本只汇总 `settle` 与 `release`：`sum_cost = SUM(amount_usd) WHERE entry_kind IN ('settle','release')`。
- `remaining_budget = max_cost_usd - sum_cost`。结果可以为负。不得截断为零。
- **账本唯一写入者。** C5 的 `services/budget_service.py` 与 `RunBudget` 适配器是 `run_ledger_entries` 的唯一写入口。C6 不得直接调用 `record_entry`，不得在无 budget 时写 `accrued` / `settle`，不得用 `balance_after_usd=0` 写占位行。
- **多 gate。** `authorizations` 允许同一 run 有多行，部分唯一键是 `(run_id, gate_id)`（`WHERE run_id IS NOT NULL`），索引名固定为 `uq_authorizations_run_gate`，不是 `run_id` 单列唯一。budget 只读 `gate_id='G-Cost' AND gate_status='pass'` 的行。C4 写入的 `G-Plan/blocked` 行由迁移 061 绑定到 run；存在 blocked G-Plan 的 run 不得再建 G-Cost pass，C6 必须拒绝执行。
- `runs` 与 `run_steps` 是唯一执行真相。`run_steps` 与 `task_runs` 保持 1─1。C5 不修改 `run_steps` 表、步骤状态枚举、步骤序号规则与重试语义。
- C5 不修改 `run_executor.py`、`run_executor_adapters.py`、`run_worker_runtime.py`、`run_collector_call.py` 或 `mcp_runtime/**`。执行器与 collector 接线归 C6；C5 只提供 API 与适配器类。
- 价格未知时不得按零成本报价或执行。`pricing.quote` / `pricing.quote_usage` 恒为严格模式：缺条目、`unit_price` 为 `null`、订阅制端点都抛 `ToolNotPricedError`，错误码 `tool_not_priced`。`STRICT_PRICE_ENABLED` 默认 `false`；shadow 模式由路由记录 `tool_not_priced_shadow`，并回退到只按 `task_runs.total_cost_usd` 汇总的 legacy 路径（缺实际成本记 0，不另建价格解析）；enforce 模式返回 422。
- 价格锁。`pricing.refresh_price_book(session)` 是进程唯一价格快照入口：它从 `tool_prices` 读取当前有效行（`effective_to IS NULL`）并冻结，之后返回同一快照与同一 SHA-256 指纹。已锁定后再读取到不同快照必须抛 `PriceBookLockedError`（`price_book_locked`）。`main.py` 在 lifespan 启动时用 `async_session_factory` 调用它；未锁定时 `quote` 抛 `PriceBookNotLockedError`（`price_book_not_locked`）。测试用 `reset_price_book_for_tests()` 释放。
- **测试夹具。** 任何调用 `quote` / `quote_usage` 的测试必须先建 `tool_prices` 表并导入 fixture 种子，再调用 `refresh_price_book(session)`；测试结束调用 `reset_price_book_for_tests()`。`price_test_support.with_price_session` 与 `budget_test_support.with_sqlite_session` 已封装该流程。
- **种子门禁。** 迁移 061 只建 `tool_prices` 表。部署顺序是迁移后运行 `python -m data_intelligence_hub.scripts.seed_tool_prices`，再启动 API。`tool_prices` 为空时应用启动必须失败并提示运行种子，不得回退 fixture。种子脚本幂等，重复运行不产生重复行。`tool_prices.tool_id` 有外键指向 `tool_catalog.tool_id`；fixture 中每个 `tool_id` 必须已在 `tool_catalog`。缺失时种子失败并停止发布，不得跳过或伪造目录行。
- 每个 run 必须有一条 `G-Cost/pass` 授权；授权上限来自该行 `max_cost_usd`，该值由 C4 `workbench_tasks.max_cost_usd` 经 `create_order_run_authorizations` 拆分得到。缺少授权时按 `ensure_order_run_authorization` 懒创建：有订单时拆分；没有订单或订单上限为空时创建 `0.000000`，不发明默认上限。shadow 模式只记录 block，enforce 模式阻断。
- **quota 账户。** 迁移 061 为现有项目回填 `quota_accounts`，限额为 `0`（不发明业务阈值）。缺失账户时懒创建 `0` 限额账户。`BUDGET_ENFORCEMENT_ENABLED` 默认 `false`（shadow），只允许在 PG0 之前使用：计算、记账、投影照常，但不因额度/授权不足阻断 run；PG0 发布批次必须置 `true`，enforce 模式才抛 `quota_exceeded` / `approval_required` / `quota_account_missing`。`STRICT_PRICE_ENABLED` 同样只在 PG0 之前允许 `false`；PG0 必须置 `true`。
- 预算检查与项目额度预留必须在同一事务内原子完成。并发请求不得超卖项目额度。
- 所有金额使用 `Decimal` 与 `Numeric(12,6)`。禁止 `float`。禁止把金额转成字符串参与计算。
- 迁移必须单 head。每个代码任务结束前运行该任务的 impact 检查。每次提交前运行 `detect-changes --scope all`。`partial: true` 或 `truncated: true` 视为未完成。每个 commit 前重跑。
- **本切片不直接部署。** C5 只交付代码、迁移与测试，不执行 ssh、`git fetch`、`alembic upgrade`、`docker compose`，也不更新生产环境变量。生产 A/B 的备份、schema 060 预检、迁移 061、`tool_prices` 种子、compose/env 变更、重启、流量切换、两个严格开关置 `true` 与回滚演练全部归总索引 §8.4 的 PG0 发布批次执行；C14 只做只读健康检查与浏览器验收，不得执行迁移、种子、重启或开关写入。C5 只保留交接清单。生产 A 不得重建 edge。生产 B 使用 `configs/deploy/scrapy/docker-compose.yml`，与 A 共用，并必须取得目标授权；不修改 `configs/deploy/scrapy-new/**`。
- 本计划只写计划文档，不修改业务代码。执行者按任务逐项落地。

## 切片、迁移、开关与回滚点

| 项 | C5 |
|---|---|
| 切片 | `tool_prices` 唯一价格源与价格锁、quota 账户、tool_calls、按订单拆分 run 多 gate 授权、run limits、内联批准动作、账本、预算服务、quota 端点、C2 审计接入；不部署 |
| 迁移 | 只新增 `202610220061_budget_ledger_pricing.py`，`down_revision=202610220060`；建 `tool_prices`、`quota_accounts`、`tool_calls`、`workbench_approval_actions`，加 `authorizations.run_id` 与 `uq_authorizations_run_gate` 部分唯一索引（`WHERE run_id IS NOT NULL`），回填 quota 与授权。`tool_prices` 种子由独立脚本写入 |
| 开关 | PG0 之前只允许 `BUDGET_ENFORCEMENT_ENABLED=false`（shadow）与 `STRICT_PRICE_ENABLED=false`；PG0 发布批次必须把两者置 `true` |
| 回滚点 | PG0 批次先置两个开关 `false` → 回退代码 → 061 downgrade（`tool_prices`、`quota_accounts`、`tool_calls`、`workbench_approval_actions` 无新数据时）→ 恢复备份；重新升级后必须重跑 `seed_tool_prices` |
| 外部依赖 | C1 registry（含 `tool_prices`、`workbench_approval_actions`、批准路径与审计动作）、C2 `require_project_access` 与 `append_audit_event`、C4 任务单预算/限额与 blocked G-Plan、C6 执行器/collector 接线、PG0 发布批次、C14 只读验收 |

## Task 0: Prerequisites and Contract Gate（基线与契约门禁）

C5 依赖以下已交付接口。执行前逐项验证。任一项不满足时停止，不得用占位实现绕过。

```text
C0: 工作树 preflight、B5 合入、迁移 202610210056/202610210057、测试基线。
C1: 契约 v1.1 必须已正式登记 C5 的表、列、枚举、错误码；tool_prices 在 tables 与 phases[].objects 中，且无延期登记。
C2: owner/admin/member、项目 ACL、统一审计、迁移 202610220058。
C3: 项目密钥与凭据治理、迁移 202610220059。
C4: workbench_tasks（含 max_cost_usd/max_pages/max_records、primary_market/comparison_markets、status）、逐市场 run 提交、迁移 202610220060。
```

C5 消耗的现有接口：

```python
# apps/api/src/data_intelligence_hub/models/run.py
class Run: ...
class RunStep: ...

# apps/api/src/data_intelligence_hub/models/authorization.py
class Authorization: ...

# apps/api/src/data_intelligence_hub/models/task.py
class TaskRun: ...

# apps/api/src/data_intelligence_hub/models/workbench.py（C4）
class WorkbenchTask: ...  # max_cost_usd / max_pages / max_records / primary_market / status

# apps/api/src/data_intelligence_hub/models/workflow_plan.py
class WorkflowVersion: ...  # workbench_task_id

# apps/api/src/data_intelligence_hub/models/workbench_approval.py（C5）
class WorkbenchApprovalAction: ...

# apps/api/src/data_intelligence_hub/services/run_ledger.py
async def record_entry(...) -> RunLedgerEntry
async def sum_cost(session, run_id: uuid.UUID) -> Decimal
async def remaining_budget(session, *, run_id: uuid.UUID, max_cost_usd: Decimal) -> Decimal

# apps/api/src/data_intelligence_hub/repositories/authorizations.py
async def create_authorization(...) -> Authorization
async def get_authorization(...) -> Authorization | None

# apps/api/src/data_intelligence_hub/services/run_executor.py
class RunExecutor: ...
class RunRecord(Protocol): ...
class CollectorCallResultView(Protocol): ...

# apps/api/src/data_intelligence_hub/services/audit_log.py（C2）
async def append_audit_event(...) -> AuditEvent
AUDIT_ACTIONS: frozenset[str]

# apps/api/src/data_intelligence_hub/api/authz.py（C2）
async def require_project_access(...) -> ProjectAccess
async def require_workspace_role(...) -> str
```

C1 必须已在 `docs/design/【契约冻结】v1-表名-枚举-接口.md` 与 `configs/contracts/v1.1.0/registry.json` 登记以下对象。缺一项时先补契约，不得在 C5 静默新增。

| 对象 | 必须登记的内容 |
|---|---|
| `tool_prices` | C1 的 13 列：`id`、`tool_id`、`currency`、`price_book_version`、`unit_price`、`unit`、`quantity_basis`、`confidence`、`source`、`effective_from`、`effective_to`、`created_at`、`updated_at`；唯一约束 `uq_tool_prices_tool_currency_version` `(tool_id, currency, price_book_version)`；索引 `ix_tool_prices_tool_effective` `(tool_id, effective_from)`；`unit_price` 可空，空值表示未定价；fixture 只作种子 |
| `quota_accounts` | C1 的列：`id`、`workspace_id`、`project_id`、`period_start`、`period_end`、`currency`、`daily_limit_usd`、`monthly_limit_usd`、`used_usd`、`reserved_usd`、`remaining_usd`、`version`、`updated_at`；唯一约束 `uq_quota_accounts_project_period` |
| `tool_calls` | C1 的列：`id`、`workspace_id`、`project_id`、`run_id`、`step_id`、`tool_id`、`contract_version`、`idempotency_key_hash`、`request_hash`、`backend_ref_type`、`backend_ref_id`、`outcome`、`error_code`、`quantity`、`unit`、`unit_price`、`total_cost_usd`、`evidence_grade`、`started_at`、`finished_at` |
| `workbench_tasks`（消费） | C4 的 `max_cost_usd`（`numeric(12,6)` 可空、非负）、`max_pages` / `max_records`（integer 可空、非负）、`primary_market`、`comparison_markets`、`status`（`draft` / `submitted` / `cancelled`）；C5 只读，不建第二份订单预算表 |
| `workbench_approval_actions` | C1 的 13 列：`id`、`workspace_id`、`project_id`、`task_id`、`action_type`、`requester_user_id`、`approver_user_id`、`status`、`payload_json`、`idempotency_key_hash`、`created_at`、`expires_at`、`decided_at`；CHECK `ck_workbench_approval_actions_action_type`、`ck_workbench_approval_actions_status`、`ck_workbench_approval_actions_self_approval`；唯一索引 `uq_workbench_approval_actions_idempotency` `(workspace_id, idempotency_key_hash) WHERE idempotency_key_hash IS NOT NULL`；索引 `ix_workbench_approval_actions_task_status` `(task_id, status)` |
| `authorizations.run_id` | 可空 UUID；外键 `runs.id`；部分唯一索引 `(run_id, gate_id)`（`uq_authorizations_run_gate`，`WHERE run_id IS NOT NULL`），不是 `run_id` 单列唯一 |
| `run_ledger_entries` 金额符号约束 | `settle > 0`、`release < 0`、其余四类 `>= 0` |
| quota 端点 | `GET /api/quota`、`GET /api/quota/projects/{project_id}` |
| 批准路径 | `POST /api/workbench/tasks/{task_id}/approvals`、`POST /api/workbench/tasks/{task_id}/approvals/{approval_id}`；不新增收件箱或其他路径 |
| C2 审计动作 | `budget.price.changed`、`budget.limit.changed`、`budget.blocked`、`budget.released`；不得自造动作名 |
| 错误码 | `tool_not_priced`、`quota_exceeded`、`approval_required`、`quota_account_missing`、`idempotency_conflict`、`approval_not_found`、`approval_self_approval_forbidden`、`approval_state_conflict` |

C5 contract addendum 的精确机器登记片段：

```json
[
  {
    "name": "tool_prices",
    "module": "M08",
    "status": "new",
    "phase": "C5",
    "purpose": "工具单价快照；按 tool_id、币种与价格簿版本登记",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "tool_id", "type": "string(200)", "nullable": false, "status": "new", "phase": "C5", "references": "tool_catalog.tool_id"},
      {"name": "currency", "type": "string(3)", "nullable": false, "status": "new", "phase": "C5", "default": "USD"},
      {"name": "price_book_version", "type": "string(40)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "unit_price", "type": "numeric(12,6)", "nullable": true, "status": "new", "phase": "C5", "notes": "为空表示未定价"},
      {"name": "unit", "type": "string(30)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "quantity_basis", "type": "string(40)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "confidence", "type": "string(20)", "nullable": false, "status": "new", "phase": "C5", "enum": "tool_prices.confidence"},
      {"name": "source", "type": "text", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "effective_from", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "effective_to", "type": "datetime", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "updated_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"}
    ],
    "constraints": ["uq_tool_prices_tool_currency_version", "ck_tool_prices_unit_price_nonnegative", "ck_tool_prices_confidence", "ck_tool_prices_effective_window", "fk_tool_prices_tool_id_tool_catalog"],
    "indexes": [
      {"name": "uq_tool_prices_tool_currency_version", "columns": ["tool_id", "currency", "price_book_version"], "unique": true},
      {"name": "ix_tool_prices_tool_effective", "columns": ["tool_id", "effective_from"], "unique": false}
    ]
  },
  {
    "name": "authorizations",
    "status": "extend",
    "phase": "C5",
    "columns": [
      {"name": "run_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C5", "references": "runs.id"}
    ],
    "constraints": ["uq_authorizations_run_gate"],
    "indexes": [
      {"name": "uq_authorizations_run_gate", "columns": ["run_id", "gate_id"], "unique": true, "where": "run_id IS NOT NULL"}
    ]
  }
]
```

`tool_prices` 是唯一价格事实源。`price_book_v1.json` 只被种子脚本与测试读取；`pricing.py` 不导入 fixture，只读 `tool_prices`。`pricing.refresh_price_book(session)` 在进程启动时从数据库读一次并冻结；运行时不得绕过 `pricing.py` 直接查 `tool_prices`。缺价时 `pricing` 抛 `ToolNotPricedError`；`STRICT_PRICE_ENABLED` 只决定路由层是回退 legacy 汇总还是返回 422。

`duplicate_settlement` 是 C5 内部错误码，用于同一幂等键对应不同金额。HTTP 面统一映射为 `idempotency_conflict`。

- [ ] **Step 0: 创建隔离 worktree 并安装依赖**

Run only from the main working tree:

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify feat/gov-c4^{commit}
test -z "$(git branch --list feat/gov-c5)"
test ! -e /Users/lute/Project/data_scrapy-gov-c5
git worktree add /Users/lute/Project/data_scrapy-gov-c5 -b feat/gov-c5 feat/gov-c4
cp docs/superpowers/plans/2026-10-22-governed-task-platform-c5-budget-ledger-pricing.md   /Users/lute/Project/data_scrapy-gov-c5/docs/superpowers/plans/
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv sync --locked --dev
cd /Users/lute/Project/data_scrapy-gov-c5
git branch --show-current
git merge-base --is-ancestor feat/gov-c4 HEAD && echo C4_BRANCH_BASE_OK
git status --short
```

Expected: worktree creation succeeds; branch is `feat/gov-c5`; output includes `C4_BRANCH_BASE_OK`; `uv sync` exits 0; status contains only the copied C5 plan. If the branch or path already exists, stop and inspect it. Do not delete or reuse it blindly.

- [ ] **Step 1: Verify the branch and baseline**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git branch --show-current
git merge-base --is-ancestor feat/gov-c4 HEAD; echo "c4_ancestor=$?"
git status --short
cd apps/api && uv run alembic heads
```

Expected:

```text
feat/gov-c5
c4_ancestor=0
(empty git status)
202610220060 (head)
```

`f0560ca` 只是 C0 的起始提交，不是 C5 的开工 HEAD。C5 必须从 `feat/gov-c4` 创建。`c4_ancestor` 非 0、当前分支不是 `feat/gov-c5`、或 `alembic heads` 不是单行 `202610220060 (head)` 时停止。

- [ ] **Step 2: Verify the contract entries**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
rg -n "tool_prices|quota_accounts|tool_calls|workbench_approval_actions|authorizations.run_id|run_ledger_entries" \
  'docs/design/【契约冻结】v1-表名-枚举-接口.md'
rg -n "uq_authorizations_run_gate" configs/contracts/v1.1.0/registry.json
rg -n "uq_tool_prices_tool_currency_version" configs/contracts/v1.1.0/registry.json
rg -n "ix_tool_prices_tool_effective" configs/contracts/v1.1.0/registry.json
rg -n '"name": "tool_prices"' configs/contracts/v1.1.0/registry.json
rg -n '"name": "workbench_approval_actions"|ck_workbench_approval_actions_self_approval|workbench.tasks.approvals.create|workbench.tasks.approvals.decide' configs/contracts/v1.1.0/registry.json
rg -n "budget.price.changed|budget.limit.changed|budget.blocked|budget.released" configs/contracts/v1.1.0/registry.json
```

Expected: 输出包含 `tool_prices` 的正式表登记、`quota_accounts`、`tool_calls`、`workbench_approval_actions` 的 13 列与 3 个 CHECK、`authorizations` 的 C5 字段行、`uq_authorizations_run_gate`（部分唯一，`WHERE run_id IS NOT NULL`）、`uq_tool_prices_tool_currency_version`、`ix_tool_prices_tool_effective`、两个批准路径与四个 C5 审计动作。`tool_prices` 必须出现在正式表登记中，不得留在延期登记；若仍是延期登记，先回到 C1 改为正式表。`run_ledger_entries` 八列与六枚举不得被改写。`workbench_approval_actions` 的完整 JSON 以 C1 计划 Task 5 为准，C5 不复制第二份 registry。

- [ ] **Step 3: Verify no C5 schema exists yet**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
rg -n "class ToolPrice|class QuotaAccount|class ToolCall|class WorkbenchApprovalAction|create_table\(\s*\"tool_prices\"|create_table\(\s*\"quota_accounts\"|create_table\(\s*\"tool_calls\"|create_table\(\s*\"workbench_approval_actions\"" \
  apps/api/src apps/api/alembic/versions || true
```

Expected: 输出为空。C5 开始前不得已有 `tool_prices` / `quota_accounts` / `tool_calls` / `workbench_approval_actions` 的 ORM 或迁移；已有实现时先审查来源，不得重复建表。

- [ ] **Step 4: Record the impact baseline**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "get_usage_summary" --direction upstream --repo .
node .gitnexus/run.cjs impact "load_price_book" --direction upstream --repo .
node .gitnexus/run.cjs impact "RunExecutor" --direction upstream --repo .
node .gitnexus/run.cjs impact "record_entry" --direction upstream --repo .
```

Expected baseline:

```text
get_usage_summary: risk LOW, 1 direct caller: api/routes/usage.py:usage_summary
load_price_book: risk LOW, 3 impacted: _price_entries -> get_usage_summary -> usage_summary
RunExecutor: risk LOW, 4 impacted: run_collector_call, run_executor_adapters, run_worker_runtime, main
record_entry: risk UNKNOWN, 0 callers resolved; text search shows only tests/unit/test_run_ledger.py
```

`load_price_book` 在 C5 完成后只服务种子路径；Task 8 删除 `usage_service._price_entries` 的调用。`record_entry` 的 `UNKNOWN` 不等于低风险。文本搜索确认它当前没有生产调用者。保留现有签名兼容性，只增加符号校验。

## File Structure

新建文件：

| 文件 | 职责 |
|---|---|
| `apps/api/src/data_intelligence_hub/models/tool_price.py` | `tool_prices` ORM 模型。C1 的 13 列、有效窗口与 `(tool_id, currency, price_book_version)` 唯一键；`unit_price` 可空。 |
| `apps/api/src/data_intelligence_hub/repositories/tool_prices.py` | `tool_prices` 读取、幂等 upsert 与 fixture 种子导入。运行时只由 `pricing` 调用读取。 |
| `apps/api/src/data_intelligence_hub/scripts/__init__.py` | 可导入脚本包。 |
| `apps/api/src/data_intelligence_hub/scripts/seed_tool_prices.py` | 唯一 fixture 种子入口：把 `price_book_v1.json` 幂等写入 `tool_prices`。 |
| `apps/api/src/data_intelligence_hub/services/pricing.py` | 价格簿唯一业务入口。启动时从 `tool_prices` 读快照并锁定；严格缺价失败。输出 `PriceQuote`。 |
| `apps/api/src/data_intelligence_hub/models/quota_account.py` | `quota_accounts` ORM 模型。项目日额度、预留、已用、余额、版本。 |
| `apps/api/src/data_intelligence_hub/repositories/quota_accounts.py` | 额度账户读写与原子预留、结算、释放。 |
| `apps/api/src/data_intelligence_hub/models/tool_call.py` | `tool_calls` ORM 模型。调用意图与结果，不复制执行状态。 |
| `apps/api/src/data_intelligence_hub/repositories/tool_calls.py` | 调用记录读写与幂等。 |
| `apps/api/src/data_intelligence_hub/services/tool_call_service.py` | 开始与结束调用。 |
| `apps/api/src/data_intelligence_hub/services/run_authorizations.py` | 按订单拆分 per-market 多 gate 授权、零预算授权、历史回填、带项目 ACL 的授权读取。 |
| `apps/api/src/data_intelligence_hub/services/run_limits.py` | `RunLimits`、`resolve_run_limits`、页数与记录数检查；`None` 不限制，超限抛 `RunLimitExceededError`。 |
| `apps/api/src/data_intelligence_hub/models/workbench_approval.py` | `workbench_approval_actions` ORM；13 列、3 个 CHECK、2 个索引。 |
| `apps/api/src/data_intelligence_hub/repositories/workbench_approvals.py` | 内联批准动作的幂等创建、按任务/ID 读取、决定写入。 |
| `apps/api/src/data_intelligence_hub/services/workbench_approvals.py` | 创建与决定批准动作；requester 不得自批；批准/拒绝写 C2 审计。 |
| `apps/api/src/data_intelligence_hub/schemas/workbench_approval.py` | 创建/决定请求与响应 schema。 |
| `apps/api/src/data_intelligence_hub/api/routes/workbench_approvals.py` | 只暴露 C1 登记的两个批准路径，接入项目 ACL 与 workspace 角色。 |
| `apps/api/src/data_intelligence_hub/services/budget_service.py` | `estimate`、`reserve`、`settle`、`release`、`block`、`unknown`、`cancel`；写入 C2 审计。 |
| `apps/api/src/data_intelligence_hub/services/run_budget.py` | `RunBudget` Protocol 与 `OrmRunBudget` 适配器；只提供 API，不接线执行器。 |
| `apps/api/src/data_intelligence_hub/api/routes/quota.py` | `GET /api/quota`、`GET /api/quota/projects/{project_id}`；两个读端点都走 `require_project_access`。 |
| `apps/api/src/data_intelligence_hub/schemas/quota.py` | quota 响应 schema：limit、reserved、used、remaining、period。 |
| `apps/api/src/data_intelligence_hub/scripts/price_coverage_report.py` | 盘点生产 tool catalog `tool_id` 与 `tool_prices` 快照的差集；输出 JSON。 |
| `apps/api/alembic/versions/202610220061_budget_ledger_pricing.py` | 唯一迁移。建 `tool_prices`、`quota_accounts`、`tool_calls`、`workbench_approval_actions`，加 `authorizations.run_id` 与 `uq_authorizations_run_gate`，加金额符号约束，回填 quota 与零预算授权。不写入价格种子。 |
| `apps/api/tests/unit/price_test_support.py` | 价格测试的 SQLite 会话与 `tool_prices` 种子。 |
| `apps/api/tests/unit/budget_test_support.py` | 预算测试种子与内存 SQLite 会话；复用 `tool_prices` 种子。 |
| `apps/api/tests/unit/test_tool_prices.py` | `tool_prices` ORM、仓储、种子幂等与裁剪。 |
| `apps/api/tests/unit/test_pricing.py` | 价格入口、快照锁与严格缺价。 |
| `apps/api/tests/unit/test_quota_accounts.py` | 原子预留、结算、释放。 |
| `apps/api/tests/unit/test_tool_calls.py` | 调用记录幂等。 |
| `apps/api/tests/unit/test_run_authorizations.py` | 订单预算拆分、主市场余数、空上限零预算、幂等、blocked G-Plan、项目 ACL 负例。 |
| `apps/api/tests/unit/test_run_limits.py` | `None` 不限制、0 零容忍、页数/记录数超限停止、边界值。 |
| `apps/api/tests/unit/test_workbench_approvals.py` | 幂等创建、owner/admin 决定、requester 自批拒绝、状态冲突、跨项目 403/404、C2 审计。 |
| `apps/api/tests/unit/test_budget_service.py` | 估算、预留、结算、释放、阻断、未知结果、超额、重复结算、并发、C2 审计。 |
| `apps/api/tests/unit/test_budget_migration_source.py` | 迁移 061 源检查、四张表、`(run_id, gate_id)` 部分唯一键、quota 回填与单 head。 |
| `apps/api/tests/unit/test_run_budget.py` | `RunBudget` 适配器：一次 reserve、一次 settle、失败 attempt 成本汇总、unknown/cancel 释放 quota、按订单预算创建授权。 |
| `apps/api/tests/unit/test_quota_routes.py` | 两个 quota 端点、项目 ACL、shadow/enforce、422 `tool_not_priced`。 |
| `apps/api/tests/unit/test_price_coverage_report.py` | 价格覆盖差集报告。 |
| `apps/api/tests/integration/test_budget_ledger_pricing.py` | quota、ledger、task_runs.remaining_budget 对账；不经过执行器。 |

修改文件：

| 文件 | 修改 |
|---|---|
| `apps/api/src/data_intelligence_hub/models/authorization.py` | 加 `run_id` 与 `uq_authorizations_run_gate` 部分唯一索引。 |
| `apps/api/src/data_intelligence_hub/models/run_ledger.py` | 加金额符号 `CheckConstraint`；八列不变。 |
| `apps/api/src/data_intelligence_hub/models/__init__.py` | 导出 `ToolPrice`、`QuotaAccount`、`ToolCall`、`WorkbenchApprovalAction`。 |
| `apps/api/src/data_intelligence_hub/repositories/authorizations.py` | 支持 `run_id`，加 `list_authorizations_for_run`、`get_run_budget_authorization`、`has_blocked_gate`。 |
| `apps/api/src/data_intelligence_hub/repositories/quota_accounts.py` | 增加带版本的额度上限更新 `update_quota_limits`，供 owner/admin 操作路径调用。 |
| `apps/api/src/data_intelligence_hub/services/run_ledger.py` | 符号校验；`record_entry` 兼容旧签名。 |
| `apps/api/src/data_intelligence_hub/services/usage_service.py` | 删除本地价格解析与 fixture 读取，改用 `pricing.quote_usage`。 |
| `apps/api/src/data_intelligence_hub/services/exceptions.py` | 增加预算、授权与 `RunLimitExceededError`。 |
| `apps/api/src/data_intelligence_hub/core/config.py` | 只增加 `budget_enforcement_enabled`、`strict_price_enabled`、`default_quota_limit_usd`（默认 0）；不得增加默认 run 授权上限。 |
| `apps/api/src/data_intelligence_hub/main.py` | 挂载 quota 与 workbench approvals 路由；lifespan 启动时用 `async_session_factory` 调用 `pricing.refresh_price_book(session)`；空表时启动失败。 |
| `apps/api/src/data_intelligence_hub/api/routes/usage.py` | strict 模式把 `ToolNotPricedError` 映射 422 `tool_not_priced`。 |
| `configs/deploy/scrapy/docker-compose.yml` | 追加 `BUDGET_ENFORCEMENT_ENABLED` 与 `STRICT_PRICE_ENABLED` 默认关闭映射；生产值由 PG0 发布批次设置。 |
| `apps/api/.env.example` | 追加两个精确开关名的 `false` 示例。 |
| `apps/api/tests/unit/test_budget_deploy_facts.py` | compose 与 `.env.example` 键名门禁；禁止 `SCRAPY_` 前缀漂移。 |

不修改：

```text
apps/api/src/data_intelligence_hub/mcp_runtime/**
apps/api/src/data_intelligence_hub/models/run.py 的 run_steps 结构与枚举
apps/api/src/data_intelligence_hub/api/routes/runs.py 的步骤查询语义
apps/api/src/data_intelligence_hub/services/run_executor.py
apps/api/src/data_intelligence_hub/services/run_executor_adapters.py
apps/api/src/data_intelligence_hub/services/run_worker_runtime.py
apps/api/src/data_intelligence_hub/services/run_collector_call.py
```

---

### Task 1: `tool_prices` 唯一价格事实源、价格快照锁与严格缺价

**Files:**
- Create: `apps/api/src/data_intelligence_hub/models/tool_price.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/tool_prices.py`
- Create: `apps/api/src/data_intelligence_hub/scripts/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/scripts/seed_tool_prices.py`
- Create: `apps/api/src/data_intelligence_hub/services/pricing.py`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Create: `apps/api/tests/unit/price_test_support.py`
- Test: `apps/api/tests/unit/test_tool_prices.py`
- Test: `apps/api/tests/unit/test_pricing.py`

**Interfaces:**
- Consumes: `Base`、`UUIDPrimaryKeyMixin`；`tool_catalog.tool_id`；`tool_catalog.fixtures.load_price_book()` 仅用于种子。
- Produces:
  - `ToolPrice`（13 列，见 C1 契约）
  - `list_tool_prices(session, *, current_only=True, currency=None, price_book_version=None) -> list[ToolPrice]`
  - `get_tool_price(session, *, tool_id, currency="USD", price_book_version=None, current_only=True) -> ToolPrice | None`
  - `upsert_tool_price(...) -> ToolPrice`
  - `seed_tool_prices_from_entries(session, *, entries, price_book_version, currency="USD", effective_from=None, close_previous=True, close_missing=True, audit_workspace_id=None, actor_user_id=None) -> int`
  - `seed_tool_prices_from_fixture(session, *, effective_from=None, audit_workspace_id=None, actor_user_id=None) -> int`
  - `PriceQuote(tool_id, quantity_basis, unit, quantity, unit_price, total_cost_usd, price_book_schema_version, price_book_fingerprint)`
  - `async refresh_price_book(session) -> Mapping[str, object]`
  - `price_book_fingerprint() -> str`
  - `priced_endpoints() -> frozenset[str]`
  - `reset_price_book_for_tests() -> None`
  - `quote(tool_id: str, *, records_count: int = 0, units: Decimal | int | str | None = None) -> PriceQuote`
  - `quote_usage(tool_id: str, *, records_count: int) -> PriceQuote`
  - `ToolNotPricedError`，`message = "tool_not_priced"`
  - `PriceBookEntryInvalidError`，`message = "price_book_entry_invalid"`
  - `PriceBookLockedError`，`message = "price_book_locked"`
  - `PriceBookNotLockedError`，`message = "price_book_not_locked"`
  - `PriceBookEmptyError`，`message = "price_book_empty"`

- **价格变更审计。** 空表首次种子是基线，不写价格变更审计。已有价格行且规范化内容摘要发生变化时，种子函数必须在同一事务写一条 C2 `audit_events`：`action="budget.price.changed"`、`actor_type="system"`、`resource_type="tool_price"`、`resource_id=price_book_version`、`details` 含 `price_book_version` / `currency` / `entry_count` / `before_digest` / `after_digest`。调用方必须提供 `audit_workspace_id`；缺失时抛 `PriceChangeAuditRequiredError`，不得静默改价。`actor_user_id` 可选。内容无变化时幂等返回，不写审计。不得新建第二张价格审计表。

- [ ] **Step 1: Run impact for this task**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "load_price_book" --direction upstream --repo .
```

Expected: `risk: LOW`。受影响的是 `usage_service._price_entries`、`get_usage_summary`、`usage_summary`。本任务新增 `tool_prices` 与 `pricing.py`；`pricing` 不调用 `load_price_book`。`usage_service` 的 fixture 读取在 Task 8 删除；Task 1 不修改它。

- [ ] **Step 2: Write the failing `tool_prices` and pricing tests**

Create `apps/api/tests/unit/price_test_support.py`:

```python
"""价格测试的 SQLite 会话与 tool_prices 种子。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.repositories.tool_prices import (
    seed_tool_prices_from_fixture,
)
from data_intelligence_hub.services.pricing import (
    refresh_price_book,
    reset_price_book_for_tests,
)

Scenario = Callable[[AsyncSession], Awaitable[None]]


async def with_price_session(callback: Scenario) -> None:
    """建内存库、导入 tool_prices 种子、锁定快照，再运行场景。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    reset_price_book_for_tests()
    try:
        async with factory() as session:
            await seed_tool_prices_from_fixture(session)
            await session.commit()
            await refresh_price_book(session)
            try:
                await callback(session)
            finally:
                reset_price_book_for_tests()
    finally:
        await engine.dispose()
```

Create `apps/api/tests/unit/test_tool_prices.py`:

```python
"""tool_prices 的 C1 列、种子幂等与有效窗口。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.tool_price import ToolPrice
from data_intelligence_hub.repositories.tool_prices import (
    get_tool_price,
    seed_tool_prices_from_entries,
    seed_tool_prices_from_fixture,
)
from data_intelligence_hub.services.exceptions import PriceChangeAuditRequiredError
from tests.unit.price_test_support import with_price_session


@pytest.mark.anyio
async def test_seed_is_idempotent_and_matches_fixture() -> None:
    observed: dict[str, int] = {}

    async def scenario(session: AsyncSession) -> None:
        first = await seed_tool_prices_from_fixture(session)
        await session.commit()
        second = await seed_tool_prices_from_fixture(session)
        await session.commit()
        total = await session.scalar(
            select(func.count()).select_from(ToolPrice)
        )
        observed["first"] = first
        observed["second"] = second
        observed["total"] = int(total or 0)

    await with_price_session(scenario)

    assert observed["first"] == 227
    assert observed["second"] == 227
    assert observed["total"] == 227


@pytest.mark.anyio
async def test_seed_updates_existing_row_without_duplicating() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        row = await get_tool_price(session, tool_id="exa_search_lite")
        assert row is not None
        row.unit_price = Decimal("9.000000")
        await session.flush()
        count = await seed_tool_prices_from_fixture(session)
        await session.commit()
        refreshed = await get_tool_price(session, tool_id="exa_search_lite")
        total = await session.scalar(
            select(func.count()).select_from(ToolPrice)
        )
        observed["count"] = count
        observed["unit_price"] = refreshed.unit_price
        observed["total"] = int(total or 0)

    await with_price_session(scenario)

    assert observed["count"] == 227
    assert observed["unit_price"] == Decimal("0.004000")
    assert observed["total"] == 227


@pytest.mark.anyio
async def test_seed_closes_endpoints_missing_from_fixture() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        stale = ToolPrice(
            tool_id="stale_endpoint",
            currency="USD",
            price_book_version="price_book.v1",
            unit_price=Decimal("1.000000"),
            unit="query",
            quantity_basis="per_query",
            confidence="unknown",
            source="test",
            effective_from=datetime(2020, 1, 1, tzinfo=UTC),
        )
        session.add(stale)
        await session.flush()
        await seed_tool_prices_from_fixture(session)
        await session.commit()
        current = await get_tool_price(session, tool_id="stale_endpoint")
        historical = await get_tool_price(
            session,
            tool_id="stale_endpoint",
            current_only=False,
        )
        observed["current"] = current
        observed["effective_to"] = historical.effective_to

    await with_price_session(scenario)

    assert observed["current"] is None
    assert observed["effective_to"] is not None


@pytest.mark.anyio
async def test_new_version_closes_previous_current_rows() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        now = datetime.now(UTC)
        await seed_tool_prices_from_entries(
            session,
            entries={
                "exa_search_lite": {
                    "quantity_basis": "per_query",
                    "unit": "query",
                    "unit_price": 0.005,
                    "confidence": "high",
                    "source": "new-version",
                }
            },
            price_book_version="price_book.v2",
            effective_from=now + timedelta(seconds=1),
        )
        await session.commit()
        current = await get_tool_price(
            session,
            tool_id="exa_search_lite",
            price_book_version="price_book.v1",
        )
        latest = await get_tool_price(
            session,
            tool_id="exa_search_lite",
            price_book_version="price_book.v2",
        )
        observed["v1_current"] = current
        observed["v2_price"] = latest.unit_price

    await with_price_session(scenario)

    assert observed["v1_current"] is None
    assert observed["v2_price"] == Decimal("0.005000")


@pytest.mark.anyio
async def test_null_price_is_stored_as_unpriced() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        row = await get_tool_price(session, tool_id="apify_1688_advanced")
        observed["unit_price"] = row.unit_price if row is not None else "missing"

    await with_price_session(scenario)

    assert observed["unit_price"] is None


@pytest.mark.anyio
async def test_price_change_without_audit_workspace_is_rejected() -> None:
    async def scenario(session: AsyncSession) -> None:
        with pytest.raises(PriceChangeAuditRequiredError):
            await seed_tool_prices_from_entries(
                session,
                entries={
                    "exa_search_lite": {
                        "unit_price": "9.999999",
                        "unit": "request",
                        "quantity_basis": "per_call",
                        "confidence": "high",
                        "source": "test",
                    }
                },
                price_book_version="price_book.v1",
                close_missing=False,
            )

    await with_price_session(scenario)


def test_tool_prices_has_c1_columns_and_keys() -> None:
    assert set(ToolPrice.__table__.columns.keys()) == {
        "id",
        "tool_id",
        "currency",
        "price_book_version",
        "unit_price",
        "unit",
        "quantity_basis",
        "confidence",
        "source",
        "effective_from",
        "effective_to",
        "created_at",
        "updated_at",
    }
    constraints = {item.name for item in ToolPrice.__table__.constraints}
    assert "uq_tool_prices_tool_currency_version" in constraints
    indexes = {item.name for item in ToolPrice.__table__.indexes}
    assert "ix_tool_prices_tool_effective" in indexes
```

Create `apps/api/tests/unit/test_pricing.py`:

```python
"""价格簿唯一入口、数据库快照锁与严格缺价。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.repositories.tool_prices import get_tool_price
from data_intelligence_hub.services.pricing import (
    PriceBookEntryInvalidError,
    PriceBookLockedError,
    PriceBookNotLockedError,
    ToolNotPricedError,
    price_book_fingerprint,
    priced_endpoints,
    quote,
    quote_usage,
    refresh_price_book,
    reset_price_book_for_tests,
)
from tests.unit.price_test_support import with_price_session

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src/data_intelligence_hub"


@pytest.mark.anyio
async def test_per_query_quote_uses_one_unit() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        result = quote("exa_search_lite", records_count=99)
        observed["basis"] = result.quantity_basis
        observed["unit"] = result.unit
        observed["quantity"] = result.quantity
        observed["unit_price"] = result.unit_price
        observed["total"] = result.total_cost_usd
        observed["schema"] = result.price_book_schema_version

    await with_price_session(scenario)

    assert observed["basis"] == "per_query"
    assert observed["unit"] == "query"
    assert observed["quantity"] == Decimal("1")
    assert observed["unit_price"] == Decimal("0.004000")
    assert observed["total"] == Decimal("0.004000")
    assert observed["schema"] == "price_book.v1"


@pytest.mark.anyio
async def test_per_record_quote_multiplies_records() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        result = quote("tikhub_tiktok_video_search", records_count=12)
        observed["quantity"] = result.quantity
        observed["total"] = result.total_cost_usd

    await with_price_session(scenario)

    assert observed["quantity"] == Decimal("12")
    assert observed["total"] == Decimal("0.012000")


@pytest.mark.anyio
async def test_explicit_units_override_basis_quantity() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        result = quote("tikhub_tiktok_video_search", units=Decimal("3.5"))
        observed["quantity"] = result.quantity
        observed["total"] = result.total_cost_usd

    await with_price_session(scenario)

    assert observed["quantity"] == Decimal("3.5")
    assert observed["total"] == Decimal("0.003500")


@pytest.mark.anyio
async def test_missing_tool_raises_tool_not_priced() -> None:
    observed: dict[str, str] = {}

    async def scenario(session: AsyncSession) -> None:
        with pytest.raises(ToolNotPricedError) as caught:
            quote("endpoint_that_does_not_exist")
        observed["message"] = caught.value.message
        observed["text"] = str(caught.value)

    await with_price_session(scenario)

    assert observed["message"] == "tool_not_priced"
    assert "endpoint_that_does_not_exist" in observed["text"]


@pytest.mark.anyio
async def test_null_unit_price_raises_tool_not_priced() -> None:
    observed: dict[str, str] = {}

    async def scenario(session: AsyncSession) -> None:
        with pytest.raises(ToolNotPricedError) as caught:
            quote("apify_1688_advanced", records_count=1)
        observed["message"] = caught.value.message

    await with_price_session(scenario)

    assert observed["message"] == "tool_not_priced"


@pytest.mark.anyio
async def test_explicit_zero_price_is_valid() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        result = quote("ecommerce_product_page")
        observed["unit_price"] = result.unit_price
        observed["total"] = result.total_cost_usd

    await with_price_session(scenario)

    assert observed["unit_price"] == Decimal("0.000000")
    assert observed["total"] == Decimal("0.000000")


@pytest.mark.anyio
async def test_negative_units_are_rejected() -> None:
    async def scenario(session: AsyncSession) -> None:
        with pytest.raises(PriceBookEntryInvalidError):
            quote("tikhub_tiktok_video_search", units=Decimal("-1"))

    await with_price_session(scenario)


@pytest.mark.anyio
async def test_float_units_are_rejected() -> None:
    async def scenario(session: AsyncSession) -> None:
        with pytest.raises(TypeError):
            quote("tikhub_tiktok_video_search", units=0.1)  # type: ignore[arg-type]

    await with_price_session(scenario)


@pytest.mark.anyio
async def test_usage_helper_uses_the_same_entry_point() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        result = quote_usage("exa_search_lite", records_count=2)
        observed["total"] = result.total_cost_usd

    await with_price_session(scenario)

    assert observed["total"] == Decimal("0.004000")


@pytest.mark.anyio
async def test_price_book_locks_to_one_database_snapshot() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        first = price_book_fingerprint()
        row = await get_tool_price(session, tool_id="exa_search_lite")
        assert row is not None
        row.unit_price = Decimal("999.000000")
        await session.flush()
        with pytest.raises(PriceBookLockedError) as caught:
            await refresh_price_book(session)
        observed["message"] = caught.value.message
        observed["first"] = first
        observed["after"] = price_book_fingerprint()

    await with_price_session(scenario)

    assert observed["message"] == "price_book_locked"
    assert observed["first"] == observed["after"]


@pytest.mark.anyio
async def test_quotes_read_the_locked_snapshot() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        first = quote("exa_search_lite")
        second = quote("exa_search_lite")
        observed["first"] = first.price_book_fingerprint
        observed["second"] = second.price_book_fingerprint
        observed["current"] = price_book_fingerprint()

    await with_price_session(scenario)

    assert observed["first"] == observed["second"] == observed["current"]
    assert len(str(observed["first"])) == 64


@pytest.mark.anyio
async def test_quote_without_lock_raises_not_locked() -> None:
    observed: dict[str, str] = {}

    async def scenario(session: AsyncSession) -> None:
        reset_price_book_for_tests()
        with pytest.raises(PriceBookNotLockedError) as caught:
            quote("exa_search_lite")
        observed["message"] = caught.value.message
        await refresh_price_book(session)

    await with_price_session(scenario)

    assert observed["message"] == "price_book_not_locked"


@pytest.mark.anyio
async def test_priced_endpoints_excludes_null_prices() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        priced = priced_endpoints()
        observed["priced"] = "exa_search_lite" in priced
        observed["unpriced"] = "apify_1688_advanced" in priced

    await with_price_session(scenario)

    assert observed["priced"] is True
    assert observed["unpriced"] is False
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_tool_prices.py tests/unit/test_pricing.py -v
```

Expected: collection error，`ModuleNotFoundError: data_intelligence_hub.models.tool_price`。

- [ ] **Step 4: Implement the `ToolPrice` model**

Create `apps/api/src/data_intelligence_hub/models/tool_price.py`:

```python
"""价格事实表 ``tool_prices``。

C1 契约固定 13 列：按 ``tool_id``、币种与 ``price_book_version`` 登记。
``effective_from`` / ``effective_to`` 表达价格的有效窗口。
本表是唯一价格事实源；``price_book_v1.json`` 只用于种子导入。
``unit_price`` 为空表示该工具未定价，报价必须失败。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class ToolPrice(UUIDPrimaryKeyMixin, Base):
    """一个工具在一个价格簿版本下的单价与有效窗口。"""

    __tablename__ = "tool_prices"
    __table_args__ = (
        UniqueConstraint(
            "tool_id",
            "currency",
            "price_book_version",
            name="uq_tool_prices_tool_currency_version",
        ),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="unit_price_nonnegative",
        ),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown')",
            name="confidence",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="effective_window",
        ),
        Index(
            "ix_tool_prices_tool_effective",
            "tool_id",
            "effective_from",
        ),
    )

    tool_id: Mapped[str] = mapped_column(
        String(200),
        ForeignKey("tool_catalog.tool_id"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        server_default="USD",
        nullable=False,
    )
    price_book_version: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    unit: Mapped[str | None] = mapped_column(String(30))
    quantity_basis: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[str] = mapped_column(
        String(20),
        default="unknown",
        server_default="unknown",
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

Update `apps/api/src/data_intelligence_hub/models/__init__.py`:

```python
from data_intelligence_hub.models.tool_price import ToolPrice
```

并把 `"ToolPrice"` 加入 `__all__`。位置放在 `ToolCatalogEntry` 之后。

- [ ] **Step 5: Implement the repository and the seed script**

Create `apps/api/src/data_intelligence_hub/repositories/tool_prices.py`:

```python
"""``tool_prices`` 的读写与种子导入。

本模块不报价。运行时读取只由 ``services/pricing.py`` 调用。
``seed_tool_prices_from_fixture`` 是唯一读取 fixture 的种子入口。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.tool_price import ToolPrice
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.exceptions import PriceChangeAuditRequiredError

SIX_PLACES = Decimal("0.000001")
CONFIDENCE_VALUES = frozenset({"high", "medium", "low", "unknown"})


def _price(value: object, tool_id: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{tool_id}: unit_price 不得为 bool")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{tool_id}: unit_price 不是十进制数") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{tool_id}: unit_price 必须是非负有限数")
    return result.quantize(SIX_PLACES)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _confidence(value: object) -> str:
    candidate = "unknown" if value is None else str(value)
    return candidate if candidate in CONFIDENCE_VALUES else "unknown"


async def list_tool_prices(
    session: AsyncSession,
    *,
    current_only: bool = True,
    currency: str | None = None,
    price_book_version: str | None = None,
) -> list[ToolPrice]:
    statement = select(ToolPrice).order_by(ToolPrice.tool_id)
    if current_only:
        statement = statement.where(ToolPrice.effective_to.is_(None))
    if currency is not None:
        statement = statement.where(ToolPrice.currency == currency)
    if price_book_version is not None:
        statement = statement.where(
            ToolPrice.price_book_version == price_book_version
        )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_tool_price(
    session: AsyncSession,
    *,
    tool_id: str,
    currency: str = "USD",
    price_book_version: str | None = None,
    current_only: bool = True,
) -> ToolPrice | None:
    statement = select(ToolPrice).where(
        ToolPrice.tool_id == tool_id,
        ToolPrice.currency == currency,
    )
    if current_only:
        statement = statement.where(ToolPrice.effective_to.is_(None))
    if price_book_version is not None:
        statement = statement.where(
            ToolPrice.price_book_version == price_book_version
        )
    statement = statement.order_by(ToolPrice.effective_from.desc()).limit(1)
    return await session.scalar(statement)


async def upsert_tool_price(
    session: AsyncSession,
    *,
    tool_id: str,
    currency: str,
    price_book_version: str,
    unit_price: object,
    unit: object,
    quantity_basis: object,
    confidence: object,
    source: object,
    effective_from: datetime,
    effective_to: datetime | None = None,
) -> ToolPrice:
    existing = await get_tool_price(
        session,
        tool_id=tool_id,
        currency=currency,
        price_book_version=price_book_version,
        current_only=False,
    )
    values = {
        "unit_price": _price(unit_price, tool_id),
        "unit": _optional_text(unit),
        "quantity_basis": _optional_text(quantity_basis),
        "confidence": _confidence(confidence),
        "source": str(source),
        "effective_from": effective_from,
        "effective_to": effective_to,
    }
    if existing is None:
        existing = ToolPrice(
            tool_id=tool_id,
            currency=currency,
            price_book_version=price_book_version,
            **values,
        )
        session.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    await session.flush()
    return existing


def _entry_digest(
    entries: Mapping[str, Mapping[str, Any]],
    *,
    currency: str,
    price_book_version: str,
) -> str:
    rows = [
        {
            "tool_id": str(tool_id),
            "currency": currency,
            "price_book_version": price_book_version,
            "unit_price": None if payload.get("unit_price") is None else str(payload.get("unit_price")),
            "unit": payload.get("unit"),
            "quantity_basis": payload.get("quantity_basis"),
            "confidence": payload.get("confidence"),
            "source": payload.get("source"),
        }
        for tool_id, payload in sorted(entries.items())
    ]
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


async def _current_price_digest(
    session: AsyncSession,
    *,
    currency: str,
    price_book_version: str,
) -> str:
    rows = (
        await session.execute(
            select(ToolPrice).where(
                ToolPrice.currency == currency,
                ToolPrice.price_book_version == price_book_version,
                ToolPrice.effective_to.is_(None),
            )
        )
    ).scalars().all()
    payload = [
        {
            "tool_id": row.tool_id,
            "currency": row.currency,
            "price_book_version": row.price_book_version,
            "unit_price": None if row.unit_price is None else str(row.unit_price),
            "unit": row.unit,
            "quantity_basis": row.quantity_basis,
            "confidence": row.confidence,
            "source": row.source,
        }
        for row in sorted(rows, key=lambda item: item.tool_id)
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


async def seed_tool_prices_from_entries(
    session: AsyncSession,
    *,
    entries: Mapping[str, Mapping[str, Any]],
    price_book_version: str,
    currency: str = "USD",
    effective_from: datetime | None = None,
    close_previous: bool = True,
    close_missing: bool = True,
    audit_workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> int:
    """按 fixture 条目幂等写入，并维护有效窗口。返回写入行数。

    - 空表首次种子是基线，不写价格变更审计。
    - 已有价格且内容变化时必须提供 ``audit_workspace_id``，否则拒绝改价。
    - 内容无变化时幂等返回，不写审计、不重复行。
    """
    now = effective_from or datetime.now(UTC)
    before = await _current_price_digest(
        session,
        currency=currency,
        price_book_version=price_book_version,
    )
    expected = _entry_digest(
        entries,
        currency=currency,
        price_book_version=price_book_version,
    )
    existing_count = await session.scalar(
        select(func.count()).select_from(ToolPrice)
    )
    changed = bool(existing_count) and before != expected
    if changed and audit_workspace_id is None:
        raise PriceChangeAuditRequiredError(price_book_version)
    for tool_id, payload in entries.items():
        await upsert_tool_price(
            session,
            tool_id=str(tool_id),
            currency=currency,
            price_book_version=price_book_version,
            unit_price=payload.get("unit_price"),
            unit=payload.get("unit"),
            quantity_basis=payload.get("quantity_basis"),
            confidence=payload.get("confidence"),
            source=payload.get("source") or "price_book_v1.json",
            effective_from=now,
        )
    if close_previous:
        await session.execute(
            update(ToolPrice)
            .where(
                ToolPrice.currency == currency,
                ToolPrice.price_book_version != price_book_version,
                ToolPrice.effective_to.is_(None),
            )
            .values(effective_to=now)
        )
    if close_missing and entries:
        await session.execute(
            update(ToolPrice)
            .where(
                ToolPrice.currency == currency,
                ToolPrice.price_book_version == price_book_version,
                ToolPrice.tool_id.not_in(tuple(entries)),
                ToolPrice.effective_to.is_(None),
            )
            .values(effective_to=now)
        )
    await session.flush()
    if changed:
        assert audit_workspace_id is not None
        await append_audit_event(
            session,
            workspace_id=audit_workspace_id,
            actor_user_id=actor_user_id,
            actor_type="system",
            action="budget.price.changed",
            resource_type="tool_price",
            resource_id=price_book_version,
            result="success",
            details={
                "price_book_version": price_book_version,
                "currency": currency,
                "entry_count": len(entries),
                "before_digest": before,
                "after_digest": expected,
            },
            occurred_at=now,
        )
    return len(entries)


async def seed_tool_prices_from_fixture(
    session: AsyncSession,
    *,
    effective_from: datetime | None = None,
    audit_workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> int:
    """从随仓库发布的 fixture 导入种子。只允许种子路径调用。"""
    from data_intelligence_hub.tool_catalog.fixtures import load_price_book

    book = load_price_book()
    entries = book.get("entries")
    if not isinstance(entries, Mapping):
        raise ValueError("price_book_v1.json entries 必须是对象")
    schema_version = book.get("schema_version")
    if not isinstance(schema_version, str):
        raise ValueError("price_book_v1.json schema_version 必须是字符串")
    when = effective_from
    if when is None:
        updated_at = book.get("updated_at")
        if isinstance(updated_at, str):
            try:
                when = datetime.fromisoformat(updated_at)
            except ValueError:
                when = None
        if when is not None and when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
    return await seed_tool_prices_from_entries(
        session,
        entries=entries,
        price_book_version=schema_version,
        currency=str(book.get("currency", "USD")),
        effective_from=when,
        audit_workspace_id=audit_workspace_id,
        actor_user_id=actor_user_id,
    )


__all__ = [
    "CONFIDENCE_VALUES",
    "get_tool_price",
    "list_tool_prices",
    "seed_tool_prices_from_entries",
    "seed_tool_prices_from_fixture",
    "upsert_tool_price",
]
```

Create `apps/api/src/data_intelligence_hub/scripts/__init__.py`（空文件）。

Create `apps/api/src/data_intelligence_hub/scripts/seed_tool_prices.py`:

```python
"""把 price_book_v1.json 写入 tool_prices。

这是唯一允许读取 fixture 的运行时脚本；它只做种子，不参与报价。
重复运行幂等；新版本会关闭旧版本的有效窗口，fixture 中删除的工具会关闭当前窗口。
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.repositories.tool_prices import (
    seed_tool_prices_from_fixture,
)


async def seed(
    *,
    audit_workspace_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
) -> int:
    async with async_session_factory() as session:
        count = await seed_tool_prices_from_fixture(
            session,
            audit_workspace_id=audit_workspace_id,
            actor_user_id=actor_user_id,
        )
        await session.commit()
        return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-workspace-id", type=uuid.UUID, default=None)
    parser.add_argument("--actor-user-id", type=uuid.UUID, default=None)
    args = parser.parse_args()
    print(
        "seeded_tool_prices="
        f"{asyncio.run(seed(audit_workspace_id=args.audit_workspace_id, actor_user_id=args.actor_user_id))}"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Implement the pricing service**

Create `apps/api/src/data_intelligence_hub/services/pricing.py`:

```python
"""价格簿的唯一业务入口。

``tool_prices`` 是唯一价格事实源。启动时 ``refresh_price_book(session)``
从表中读取当前有效行并冻结；进程内所有报价读同一快照。
``price_book_v1.json`` 只由种子脚本写入 ``tool_prices``，本模块不读 fixture。

价格缺失或单价为空时抛出 ``ToolNotPricedError``，不得按零成本回退。
金额全程使用 ``Decimal``。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.tool_price import ToolPrice
from data_intelligence_hub.repositories.tool_prices import list_tool_prices
from data_intelligence_hub.services.exceptions import ServiceError

# 按记录数计价的 basis。其余已知 basis 按调用次数计价。
RECORD_BASES: frozenset[str] = frozenset(
    {
        "per_record",
        "per_review",
        "per_page",
        "per_dataset_item",
        "per_place_scraped",
        "per_profile",
    }
)

CALL_BASES: frozenset[str] = frozenset(
    {
        "per_request",
        "per_query",
        "per_event",
        "per_run",
        "per_search",
        "per_search_result_page",
    }
)

SIX_PLACES = Decimal("0.000001")

logger = logging.getLogger(__name__)


class ToolNotPricedError(ServiceError):
    """价格表没有可用单价。调用方不得执行或报价。"""

    message = "tool_not_priced"

    def __init__(self, tool_id: str, detail: str = "missing_price") -> None:
        super().__init__(f"{self.message}: {tool_id} ({detail})")
        self.tool_id = tool_id
        self.detail = detail


class PriceBookEntryInvalidError(ServiceError):
    """价格条目存在，但字段不合法。"""

    message = "price_book_entry_invalid"

    def __init__(self, tool_id: str, detail: str) -> None:
        super().__init__(f"{self.message}: {tool_id} ({detail})")
        self.tool_id = tool_id
        self.detail = detail


class PriceBookLockedError(ServiceError):
    """价格簿已经锁定为另一份快照。进程内不得换价。"""

    message = "price_book_locked"

    def __init__(self, detail: str) -> None:
        super().__init__(f"{self.message}: {detail}")
        self.detail = detail


class PriceBookNotLockedError(ServiceError):
    """价格快照尚未锁定。启动时必须先调用 refresh_price_book。"""

    message = "price_book_not_locked"


class PriceBookEmptyError(ServiceError):
    """当前有效价格为空。部署必须运行 seed_tool_prices。"""

    message = "price_book_empty"


_PRICE_LOCK = threading.Lock()
_LOCKED_BOOK: Mapping[str, object] | None = None
_LOCKED_FINGERPRINT: str | None = None


def _freeze(value: object) -> object:
    # 快照只读。字典转 mappingproxy，列表转 tuple。
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _fingerprint(book: Mapping[str, object]) -> str:
    payload = json.dumps(
        book,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot_from_rows(rows: Sequence[ToolPrice]) -> dict[str, object]:
    if not rows:
        raise PriceBookEmptyError("tool_prices is empty; run seed_tool_prices")
    versions = {row.price_book_version for row in rows}
    if len(versions) != 1:
        raise PriceBookEntryInvalidError("<book>", "mixed_price_book_version")
    currencies = {row.currency for row in rows}
    if len(currencies) != 1:
        raise PriceBookEntryInvalidError("<book>", "mixed_currency")
    entries: dict[str, dict[str, object]] = {}
    for row in rows:
        entries[row.tool_id] = {
            "quantity_basis": row.quantity_basis,
            "unit": row.unit,
            "unit_price": (
                None if row.unit_price is None else str(row.unit_price)
            ),
            "confidence": row.confidence,
            "source": row.source,
        }
    return {
        "schema_version": versions.pop(),
        "currency": currencies.pop(),
        "entries": entries,
    }


def _lock_snapshot(source: Mapping[str, object]) -> Mapping[str, object]:
    global _LOCKED_BOOK, _LOCKED_FINGERPRINT
    with _PRICE_LOCK:
        candidate = _fingerprint(source)
        if _LOCKED_BOOK is not None:
            if candidate != _LOCKED_FINGERPRINT:
                raise PriceBookLockedError(
                    "price_book_differs_from_locked_snapshot"
                )
            return _LOCKED_BOOK
        _LOCKED_BOOK = _freeze(source)  # type: ignore[assignment]
        _LOCKED_FINGERPRINT = candidate
        return _LOCKED_BOOK


async def refresh_price_book(session: AsyncSession) -> Mapping[str, object]:
    """从 tool_prices 读取当前有效快照并锁定。启动时调用一次。"""
    rows = await list_tool_prices(session)
    locked = _lock_snapshot(_snapshot_from_rows(rows))
    logger.info(
        "price_book_locked",
        extra={
            "fingerprint": _LOCKED_FINGERPRINT,
            "entries": len(rows),
        },
    )
    return locked


def _locked_book() -> Mapping[str, object]:
    if _LOCKED_BOOK is None:
        raise PriceBookNotLockedError("refresh_price_book_not_called")
    return _LOCKED_BOOK


def price_book_fingerprint() -> str:
    """返回锁定快照的 SHA-256 指纹。"""
    _locked_book()
    assert _LOCKED_FINGERPRINT is not None
    return _LOCKED_FINGERPRINT


def priced_endpoints() -> frozenset[str]:
    """返回有非空单价的 tool_id 集合。只用于价格覆盖报告。"""
    entries = _locked_book().get("entries")
    if not isinstance(entries, Mapping):
        raise PriceBookEntryInvalidError("<book>", "entries_not_object")
    return frozenset(
        str(name)
        for name, entry in entries.items()
        if isinstance(entry, Mapping) and entry.get("unit_price") is not None
    )


def reset_price_book_for_tests() -> None:
    """仅测试使用：释放价格锁。生产进程不得调用。"""
    global _LOCKED_BOOK, _LOCKED_FINGERPRINT
    with _PRICE_LOCK:
        _LOCKED_BOOK = None
        _LOCKED_FINGERPRINT = None


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """一次报价。数量与金额都已量化到六位小数。"""

    tool_id: str
    quantity_basis: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    total_cost_usd: Decimal
    price_book_schema_version: str
    price_book_fingerprint: str


def _money(value: object, *, tool_id: str, field: str) -> Decimal:
    if isinstance(value, bool):
        raise PriceBookEntryInvalidError(tool_id, f"{field}_is_bool")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PriceBookEntryInvalidError(
            tool_id,
            f"{field}_not_decimal",
        ) from exc
    if not result.is_finite():
        raise PriceBookEntryInvalidError(tool_id, f"{field}_not_finite")
    if result < 0:
        raise PriceBookEntryInvalidError(tool_id, f"{field}_negative")
    return result.quantize(SIX_PLACES)


def _quantity(value: Decimal | int | str, *, tool_id: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("quantity 必须用 Decimal、int 或 str，不得用 float")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PriceBookEntryInvalidError(
            tool_id,
            "quantity_not_decimal",
        ) from exc
    if not result.is_finite() or result < 0:
        raise PriceBookEntryInvalidError(tool_id, "quantity_invalid")
    return result


def _records_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("records_count 必须是 int")
    if value < 0:
        raise ValueError("records_count 不得为负")
    return value


def quote(
    tool_id: str,
    *,
    records_count: int = 0,
    units: Decimal | int | str | None = None,
) -> PriceQuote:
    """返回一次报价。

    ``units`` 显式给出时优先。否则按 ``quantity_basis`` 推导。
    价格缺失、单价为 null、订阅制工具都抛 ``ToolNotPricedError``。
    """
    if not tool_id:
        raise ToolNotPricedError(tool_id or "<empty>", "missing_tool_id")

    book = _locked_book()
    entries = book.get("entries")
    if not isinstance(entries, Mapping):
        raise PriceBookEntryInvalidError(tool_id, "entries_not_object")

    entry = entries.get(tool_id)
    if not isinstance(entry, Mapping):
        raise ToolNotPricedError(tool_id, "missing_entry")

    raw_price = entry.get("unit_price")
    if raw_price is None:
        raise ToolNotPricedError(tool_id, "null_unit_price")

    unit_price = _money(raw_price, tool_id=tool_id, field="unit_price")
    basis = entry.get("quantity_basis")
    unit = entry.get("unit")
    if not isinstance(basis, str) or not basis:
        raise PriceBookEntryInvalidError(tool_id, "missing_quantity_basis")
    if not isinstance(unit, str) or not unit:
        raise PriceBookEntryInvalidError(tool_id, "missing_unit")
    if basis == "subscription":
        raise ToolNotPricedError(tool_id, "subscription_not_per_call")

    if units is not None:
        quantity = _quantity(units, tool_id=tool_id)
    elif basis in RECORD_BASES:
        quantity = Decimal(_records_count(records_count))
    elif basis in CALL_BASES:
        quantity = Decimal("1")
    else:
        raise PriceBookEntryInvalidError(
            tool_id,
            f"unknown_quantity_basis:{basis}",
        )

    total = (quantity * unit_price).quantize(SIX_PLACES)
    schema_version = book.get("schema_version")
    if not isinstance(schema_version, str):
        raise PriceBookEntryInvalidError(tool_id, "missing_schema_version")

    return PriceQuote(
        tool_id=tool_id,
        quantity_basis=basis,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
        total_cost_usd=total,
        price_book_schema_version=schema_version,
        price_book_fingerprint=price_book_fingerprint(),
    )


def quote_usage(tool_id: str, *, records_count: int) -> PriceQuote:
    """按一次运行的实际记录数报价。"""
    return quote(tool_id, records_count=records_count)


__all__ = [
    "CALL_BASES",
    "RECORD_BASES",
    "PriceBookEmptyError",
    "PriceBookEntryInvalidError",
    "PriceBookLockedError",
    "PriceBookNotLockedError",
    "PriceQuote",
    "ToolNotPricedError",
    "price_book_fingerprint",
    "priced_endpoints",
    "quote",
    "quote_usage",
    "refresh_price_book",
    "reset_price_book_for_tests",
]
```

- [ ] **Step 7: Add the service error base if absent**

`services/exceptions.py` 已有 `ServiceError`。本步骤只确认以下导入可用：

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run python -c "from data_intelligence_hub.services.exceptions import ServiceError; print(ServiceError.__name__)"
```

Expected: `ServiceError`。

- [ ] **Step 8: Run the tests to verify they pass**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_tool_prices.py tests/unit/test_pricing.py -v
uv run ruff check src/data_intelligence_hub/models/tool_price.py \
  src/data_intelligence_hub/repositories/tool_prices.py \
  src/data_intelligence_hub/scripts/seed_tool_prices.py \
  src/data_intelligence_hub/services/pricing.py \
  tests/unit/price_test_support.py \
  tests/unit/test_tool_prices.py \
  tests/unit/test_pricing.py
```

Expected: 全部通过，ruff `All checks passed!`。`pricing.py` 不得导入 `tool_catalog.fixtures`，不得出现 `price_book_v1.json` 路径，也不得直接报价第二价格源。

- [ ] **Step 9: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/models/tool_price.py \
  apps/api/src/data_intelligence_hub/repositories/tool_prices.py \
  apps/api/src/data_intelligence_hub/scripts/__init__.py \
  apps/api/src/data_intelligence_hub/scripts/seed_tool_prices.py \
  apps/api/src/data_intelligence_hub/services/pricing.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/tests/unit/price_test_support.py \
  apps/api/tests/unit/test_tool_prices.py \
  apps/api/tests/unit/test_pricing.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(pricing): add tool_prices as the single price source"
```

Expected: `detect-changes` 覆盖本任务文件且 `partial` 与 `truncated` 均为 false。提交前必须重跑 detect-changes。

---

### Task 2: 额度账户与原子预留

**Files:**
- Create: `apps/api/src/data_intelligence_hub/models/quota_account.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/quota_accounts.py`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Create: `apps/api/tests/unit/budget_test_support.py`
- Test: `apps/api/tests/unit/test_quota_accounts.py`

**Interfaces:**
- Consumes: `Base`、`UUIDPrimaryKeyMixin`；`Project`、`Workspace`。
- Produces:
  - `QuotaAccount`
  - `get_quota_account(session, *, workspace_id, project_id, period_start) -> QuotaAccount | None`
  - `create_quota_account(session, *, workspace_id, project_id, period_start, daily_limit_usd, monthly_limit_usd=None, period_end=None, currency="USD") -> QuotaAccount`
  - `reserve_quota(session, *, account_id, amount_usd, at) -> QuotaAccount`
  - `settle_quota(session, *, account_id, reserved_amount_usd, actual_amount_usd, at) -> QuotaAccount`
  - `release_quota(session, *, account_id, reserved_amount_usd, at) -> QuotaAccount`
  - `update_quota_limits(session, *, account_id, daily_limit_usd, monthly_limit_usd, at) -> QuotaAccount`（乐观锁 `version`；只由 owner/admin 操作路径调用）
  - `QuotaAccountNotFoundError`、`QuotaExceededError`、`QuotaConcurrentUpdateError`

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "TaskRun" --direction upstream --repo .
node .gitnexus/run.cjs impact "Authorization" --direction upstream --repo .
```

Expected: 两个类均为模型锚点，`risk` 不高于 LOW；无 HIGH/CRITICAL。新表不改变现有调用图。

- [ ] **Step 2: Write the failing quota tests and support module**

Create `apps/api/tests/unit/budget_test_support.py`:

```python
"""C5 预算测试的种子数据与会话。"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.tool_prices import (
    seed_tool_prices_from_fixture,
)
from data_intelligence_hub.services.pricing import (
    refresh_price_book,
    reset_price_book_for_tests,
)

Scenario = Callable[[AsyncSession], Awaitable[None]]


async def with_sqlite_session(callback: Scenario) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    reset_price_book_for_tests()
    try:
        async with factory() as session:
            # tool_prices 是唯一价格源；测试也从 fixture 种子导入。
            await seed_tool_prices_from_fixture(session)
            await session.commit()
            await refresh_price_book(session)
            try:
                await callback(session)
            finally:
                reset_price_book_for_tests()
    finally:
        await engine.dispose()


class BudgetSeed:
    def __init__(
        self,
        *,
        user: User,
        workspace: Workspace,
        project: Project,
        run: Run,
        authorization: Authorization | None,
        task_run: TaskRun | None,
        step: RunStep | None,
    ) -> None:
        self.user = user
        self.workspace = workspace
        self.project = project
        self.run = run
        self.authorization = authorization
        self.task_run = task_run
        self.step = step


async def seed_budget_scope(
    session: AsyncSession,
    *,
    slug: str = "budget",
    max_cost_usd: Decimal = Decimal("2.000000"),
    with_task_run: bool = False,
    with_authorization: bool = True,
    endpoint_type: str = "exa_search_lite",
) -> BudgetSeed:
    now = datetime.now(UTC)
    user = User(
        email=f"{slug}-{uuid.uuid4().hex}@example.com",
        password_hash="x",
        name="Budget Owner",
    )
    session.add(user)
    await session.flush()
    workspace = Workspace(
        name=f"{slug} workspace",
        slug=f"{slug}-{uuid.uuid4().hex}",
        owner_id=user.id,
    )
    session.add(workspace)
    await session.flush()
    project = Project(
        workspace_id=workspace.id,
        name=f"{slug} project",
        domain="mother_baby",
        owner_id=user.id,
    )
    session.add(project)
    await session.flush()
    run = Run(
        workspace_id=workspace.id,
        project_id=project.id,
        status="queued",
        execution_mode="live",
        trigger="manual",
        records_count=0,
    )
    session.add(run)
    await session.flush()
    authorization = None
    if with_authorization:
        authorization = Authorization(
            workspace_id=workspace.id,
            project_id=project.id,
            run_id=run.id,
            gate_id="G-Cost",
            gate_status="pass",
            scope={"origin": "test", "run_id": str(run.id)},
            max_cost_usd=max_cost_usd,
            approver=user.id,
            granted_at=now,
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        session.add(authorization)
        await session.flush()

    task_run: TaskRun | None = None
    step: RunStep | None = None
    if with_task_run:
        source = Source(
            workspace_id=workspace.id,
            project_id=project.id,
            name=f"{slug} source",
            type="exa_search",
            url=None,
            config={},
            schedule_cron=None,
            enabled=True,
        )
        session.add(source)
        await session.flush()
        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=project.id,
            source_id=source.id,
            collector_type="exa_search",
            name=f"{slug} task",
            status="enabled",
            config={"endpoint_type": endpoint_type},
        )
        session.add(task)
        await session.flush()
        task_run = TaskRun(
            task_id=task.id,
            workspace_id=workspace.id,
            project_id=project.id,
            run_id=run.id,
            status="success",
            started_at=now,
            finished_at=now,
            records_count=1,
            entities_count=0,
            logs=[],
            created_at=now,
            endpoint_type=endpoint_type,
        )
        session.add(task_run)
        await session.flush()
        step = RunStep(
            run_id=run.id,
            step_index=0,
            endpoint_type=endpoint_type,
            collector_type="exa_search",
            task_run_id=task_run.id,
            status="success",
            outcome="success",
            records_count=1,
            started_at=now,
            finished_at=now,
        )
        session.add(step)
        await session.flush()

    return BudgetSeed(
        user=user,
        workspace=workspace,
        project=project,
        run=run,
        authorization=authorization,
        task_run=task_run,
        step=step,
    )


def today() -> date:
    return datetime.now(UTC).date()
```

Create `apps/api/tests/unit/test_quota_accounts.py`:

```python
"""quota_accounts 的原子预留、结算与释放。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.repositories.quota_accounts import (
    QuotaExceededError,
    create_quota_account,
    get_or_create_quota_account,
    get_quota_account,
    release_quota,
    reserve_quota,
    settle_quota,
)
from data_intelligence_hub.models.quota_account import QuotaAccount
from tests.unit.budget_test_support import seed_budget_scope, today, with_sqlite_session


async def _seed_account(session: AsyncSession, *, limit: str = "1.000000") -> tuple[QuotaAccount, object]:
    seed = await seed_budget_scope(session, slug="quota")
    account = await create_quota_account(
        session,
        workspace_id=seed.workspace.id,
        project_id=seed.project.id,
        period_start=today(),
        daily_limit_usd=Decimal(limit),
    )
    return account, seed


@pytest.mark.anyio
async def test_reserve_updates_reserved_and_remaining() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        account, _ = await _seed_account(session)
        updated = await reserve_quota(
            session,
            account_id=account.id,
            amount_usd=Decimal("0.600000"),
            at=datetime.now(UTC),
        )
        observed["reserved"] = updated.reserved_usd
        observed["remaining"] = updated.remaining_usd
        observed["version"] = Decimal(updated.version)

    await with_sqlite_session(scenario)

    assert observed["reserved"] == Decimal("0.600000")
    assert observed["remaining"] == Decimal("0.400000")
    assert observed["version"] == Decimal("2")


@pytest.mark.anyio
async def test_reserve_rejects_amount_above_remaining() -> None:
    async def scenario(session: AsyncSession) -> None:
        account, _ = await _seed_account(session, limit="0.500000")
        with pytest.raises(QuotaExceededError):
            await reserve_quota(
                session,
                account_id=account.id,
                amount_usd=Decimal("0.600000"),
                at=datetime.now(UTC),
            )
        current = await get_quota_account(
            session,
            workspace_id=account.workspace_id,
            project_id=account.project_id,
            period_start=account.period_start,
        )
        assert current is not None
        assert current.reserved_usd == Decimal("0.000000")

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_settle_converts_reservation_to_used() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        account, _ = await _seed_account(session)
        await reserve_quota(
            session,
            account_id=account.id,
            amount_usd=Decimal("0.600000"),
            at=datetime.now(UTC),
        )
        updated = await settle_quota(
            session,
            account_id=account.id,
            reserved_amount_usd=Decimal("0.600000"),
            actual_amount_usd=Decimal("0.400000"),
            at=datetime.now(UTC),
        )
        observed["reserved"] = updated.reserved_usd
        observed["used"] = updated.used_usd
        observed["remaining"] = updated.remaining_usd

    await with_sqlite_session(scenario)

    assert observed["reserved"] == Decimal("0.000000")
    assert observed["used"] == Decimal("0.400000")
    assert observed["remaining"] == Decimal("0.600000")


@pytest.mark.anyio
async def test_release_frees_reservation_without_touching_used() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        account, _ = await _seed_account(session)
        await reserve_quota(
            session,
            account_id=account.id,
            amount_usd=Decimal("0.600000"),
            at=datetime.now(UTC),
        )
        updated = await release_quota(
            session,
            account_id=account.id,
            reserved_amount_usd=Decimal("0.600000"),
            at=datetime.now(UTC),
        )
        observed["reserved"] = updated.reserved_usd
        observed["used"] = updated.used_usd
        observed["remaining"] = updated.remaining_usd

    await with_sqlite_session(scenario)

    assert observed["reserved"] == Decimal("0.000000")
    assert observed["used"] == Decimal("0.000000")
    assert observed["remaining"] == Decimal("1.000000")


@pytest.mark.anyio
async def test_lazy_account_uses_zero_limit_and_is_idempotent() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="quota-lazy")
        first = await get_or_create_quota_account(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            period_start=today(),
        )
        second = await get_or_create_quota_account(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            period_start=today(),
        )
        observed["first"] = first.id
        observed["second"] = second.id
        observed["limit"] = first.daily_limit_usd
        observed["remaining"] = first.remaining_usd

    await with_sqlite_session(scenario)

    assert observed["first"] == observed["second"]
    assert observed["limit"] == Decimal("0.000000")
    assert observed["remaining"] == Decimal("0.000000")


@pytest.mark.anyio
async def test_overage_settlement_can_make_remaining_negative() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        account, _ = await _seed_account(session, limit="0.500000")
        await reserve_quota(
            session,
            account_id=account.id,
            amount_usd=Decimal("0.500000"),
            at=datetime.now(UTC),
        )
        updated = await settle_quota(
            session,
            account_id=account.id,
            reserved_amount_usd=Decimal("0.500000"),
            actual_amount_usd=Decimal("0.800000"),
            at=datetime.now(UTC),
        )
        observed["remaining"] = updated.remaining_usd

    await with_sqlite_session(scenario)

    assert observed["remaining"] == Decimal("-0.300000")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_quota_accounts.py -v
```

Expected: `ModuleNotFoundError: data_intelligence_hub.models.quota_account`.

- [ ] **Step 4: Implement the quota model**

Create `apps/api/src/data_intelligence_hub/models/quota_account.py`:

```python
"""项目日额度账户 ``quota_accounts``。

一行代表一个工作区、一个项目、一个自然日的美元额度。
``remaining_usd = daily_limit_usd - used_usd - reserved_usd``。
余额可以为负。负值表示已超额，不得截断为零。

``version`` 用于乐观并发。预留、结算与释放都用条件更新。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class QuotaAccount(UUIDPrimaryKeyMixin, Base):
    """项目额度账户。"""

    __tablename__ = "quota_accounts"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "period_start",
            "period_end",
            name="uq_quota_accounts_project_period",
        ),
        CheckConstraint("daily_limit_usd >= 0", name="daily_limit_non_negative"),
        CheckConstraint("monthly_limit_usd >= 0", name="monthly_limit_non_negative"),
        CheckConstraint("reserved_usd >= 0", name="reserved_non_negative"),
        CheckConstraint("used_usd >= 0", name="used_non_negative"),
        Index(
            "ix_quota_accounts_project_period",
            "project_id",
            "period_start",
            "period_end",
            unique=True,
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        server_default="USD",
        nullable=False,
    )
    daily_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    monthly_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    reserved_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        default=Decimal("0"),
        server_default=text("0"),
        nullable=False,
    )
    used_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        default=Decimal("0"),
        server_default=text("0"),
        nullable=False,
    )
    remaining_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

Update `apps/api/src/data_intelligence_hub/models/__init__.py`:

```python
from data_intelligence_hub.models.quota_account import QuotaAccount
```

并把 `"QuotaAccount"` 加入 `__all__`。位置放在 `Project` 之后、`RawRecord` 之前。

- [ ] **Step 5: Implement the quota repository**

Create `apps/api/src/data_intelligence_hub/repositories/quota_accounts.py`:

```python
"""``quota_accounts`` 的读写与原子额度变更。

所有金额使用 ``Decimal``。float 与 bool 一律拒绝。
本模块只 flush，不 commit。

原子策略：
1. PostgreSQL 用 ``SELECT ... FOR UPDATE`` 锁行。
2. SQLite 不支持該语法时退化为带 ``version`` 的条件更新。
3. 条件更新失败说明并发冲突，重试三次。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.quota_account import QuotaAccount

SIX_PLACES = Decimal("0.000001")
MAX_RETRIES = 3


class QuotaAccountNotFoundError(RuntimeError):
    message = "quota_account_not_found"


class QuotaExceededError(RuntimeError):
    message = "quota_exceeded"

    def __init__(self, requested: Decimal, available: Decimal) -> None:
        super().__init__(f"{self.message}: requested={requested} available={available}")
        self.requested = requested
        self.available = available


class QuotaConcurrentUpdateError(RuntimeError):
    message = "quota_concurrent_update"


def _decimal(value: Decimal | int | str, field: str) -> Decimal:
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field} 必须用 Decimal，不得用 float")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        result = Decimal(value)
    else:
        raise TypeError(f"{field} 必须是 Decimal、int 或 str")
    if result < 0:
        raise ValueError(f"{field} 不得为负")
    return result.quantize(SIX_PLACES)


def _signed_decimal(value: Decimal | int | str, field: str) -> Decimal:
    """允许负数的金额。仅用于 release 修正。"""
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field} 必须用 Decimal，不得用 float")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        result = Decimal(value)
    else:
        raise TypeError(f"{field} 必须是 Decimal、int 或 str")
    if not result.is_finite():
        raise ValueError(f"{field} 必须是有限数")
    return result.quantize(SIX_PLACES)


async def get_quota_account(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    period_start: date,
) -> QuotaAccount | None:
    result = await session.execute(
        select(QuotaAccount).where(
            QuotaAccount.workspace_id == workspace_id,
            QuotaAccount.project_id == project_id,
            QuotaAccount.period_start == period_start,
            QuotaAccount.period_end == period_start,
        )
    )
    return result.scalar_one_or_none()


async def create_quota_account(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    period_start: date,
    daily_limit_usd: Decimal | int | str,
    monthly_limit_usd: Decimal | int | str | None = None,
    period_end: date | None = None,
    currency: str = "USD",
) -> QuotaAccount:
    limit = _decimal(daily_limit_usd, "daily_limit_usd")
    monthly = (
        limit
        if monthly_limit_usd is None
        else _decimal(monthly_limit_usd, "monthly_limit_usd")
    )
    account = QuotaAccount(
        workspace_id=workspace_id,
        project_id=project_id,
        period_start=period_start,
        period_end=period_end or period_start,
        currency=currency,
        daily_limit_usd=limit,
        monthly_limit_usd=monthly,
        reserved_usd=Decimal("0.000000"),
        used_usd=Decimal("0.000000"),
        remaining_usd=limit,
        version=1,
    )
    session.add(account)
    await session.flush()
    return account


async def get_or_create_quota_account(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    period_start: date,
    daily_limit_usd: Decimal | int | str | None = None,
    currency: str = "USD",
) -> QuotaAccount:
    # 懒创建。默认限额为 0，不发明业务阈值；enforce 前由 owner 设置。
    existing = await get_quota_account(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        period_start=period_start,
    )
    if existing is not None:
        return existing
    return await create_quota_account(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        period_start=period_start,
        daily_limit_usd=(
            Decimal("0.000000")
            if daily_limit_usd is None
            else daily_limit_usd
        ),
        currency=currency,
    )


async def _locked_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> QuotaAccount:
    statement = select(QuotaAccount).where(QuotaAccount.id == account_id)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        statement = statement.with_for_update()
    account = (await session.execute(statement)).scalar_one_or_none()
    if account is None:
        raise QuotaAccountNotFoundError(str(account_id))
    return account


async def reserve_quota(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    amount_usd: Decimal | int | str,
    at: datetime,
) -> QuotaAccount:
    amount = _decimal(amount_usd, "amount_usd")
    for _attempt in range(MAX_RETRIES):
        account = await _locked_account(session, account_id)
        available = account.daily_limit_usd - account.used_usd - account.reserved_usd
        if amount > available:
            raise QuotaExceededError(amount, available)
        new_reserved = account.reserved_usd + amount
        result = await session.execute(
            update(QuotaAccount)
            .where(
                QuotaAccount.id == account.id,
                QuotaAccount.version == account.version,
            )
            .values(
                reserved_usd=new_reserved,
                remaining_usd=account.daily_limit_usd - account.used_usd - new_reserved,
                version=account.version + 1,
                updated_at=at,
            )
        )
        if int(getattr(result, "rowcount", 0)) == 1:
            await session.flush()
            await session.refresh(account)
            return account
        await session.flush()
    raise QuotaConcurrentUpdateError(str(account_id))


async def settle_quota(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    reserved_amount_usd: Decimal | int | str,
    actual_amount_usd: Decimal | int | str,
    at: datetime,
) -> QuotaAccount:
    reserved = _decimal(reserved_amount_usd, "reserved_amount_usd")
    actual = _signed_decimal(actual_amount_usd, "actual_amount_usd")
    for _attempt in range(MAX_RETRIES):
        account = await _locked_account(session, account_id)
        new_reserved = max(account.reserved_usd - reserved, Decimal("0.000000"))
        new_used = account.used_usd + actual
        if new_used < 0:
            raise ValueError("actual_amount_usd 不得让 used_usd 变为负数")
        result = await session.execute(
            update(QuotaAccount)
            .where(
                QuotaAccount.id == account.id,
                QuotaAccount.version == account.version,
            )
            .values(
                reserved_usd=new_reserved,
                used_usd=new_used,
                remaining_usd=account.daily_limit_usd - new_used - new_reserved,
                version=account.version + 1,
                updated_at=at,
            )
        )
        if int(getattr(result, "rowcount", 0)) == 1:
            await session.flush()
            await session.refresh(account)
            return account
        await session.flush()
    raise QuotaConcurrentUpdateError(str(account_id))


async def release_quota(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    reserved_amount_usd: Decimal | int | str,
    at: datetime,
) -> QuotaAccount:
    reserved = _decimal(reserved_amount_usd, "reserved_amount_usd")
    for _attempt in range(MAX_RETRIES):
        account = await _locked_account(session, account_id)
        new_reserved = max(account.reserved_usd - reserved, Decimal("0.000000"))
        result = await session.execute(
            update(QuotaAccount)
            .where(
                QuotaAccount.id == account.id,
                QuotaAccount.version == account.version,
            )
            .values(
                reserved_usd=new_reserved,
                remaining_usd=account.daily_limit_usd - account.used_usd - new_reserved,
                version=account.version + 1,
                updated_at=at,
            )
        )
        if int(getattr(result, "rowcount", 0)) == 1:
            await session.flush()
            await session.refresh(account)
            return account
        await session.flush()
    raise QuotaConcurrentUpdateError(str(account_id))


async def update_quota_limits(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    daily_limit_usd: Decimal | int | str,
    monthly_limit_usd: Decimal | int | str,
    at: datetime,
) -> QuotaAccount:
    """按 ``version`` 乐观锁更新上限；不改变 used/reserved。"""
    daily = _decimal(daily_limit_usd, "daily_limit_usd")
    monthly = _decimal(monthly_limit_usd, "monthly_limit_usd")
    for _ in range(3):
        account = await _locked_account(session, account_id)
        remaining = daily - account.used_usd - account.reserved_usd
        result = await session.execute(
            update(QuotaAccount)
            .where(
                QuotaAccount.id == account.id,
                QuotaAccount.version == account.version,
            )
            .values(
                daily_limit_usd=daily,
                monthly_limit_usd=monthly,
                remaining_usd=remaining,
                version=account.version + 1,
                updated_at=at,
            )
        )
        if int(getattr(result, "rowcount", 0)) == 1:
            await session.flush()
            await session.refresh(account)
            return account
        await session.flush()
    raise QuotaConcurrentUpdateError(str(account_id))


__all__ = [
    "QuotaAccountNotFoundError",
    "QuotaConcurrentUpdateError",
    "QuotaExceededError",
    "create_quota_account",
    "get_or_create_quota_account",
    "get_quota_account",
    "release_quota",
    "reserve_quota",
    "settle_quota",
    "update_quota_limits",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_quota_accounts.py -v
uv run ruff check src/data_intelligence_hub/models/quota_account.py src/data_intelligence_hub/repositories/quota_accounts.py tests/unit/test_quota_accounts.py tests/unit/budget_test_support.py
```

Expected: 5 passed，ruff 通过。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/models/quota_account.py \
  apps/api/src/data_intelligence_hub/repositories/quota_accounts.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/tests/unit/budget_test_support.py \
  apps/api/tests/unit/test_quota_accounts.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(budget): add quota accounts with atomic reservations"
```

---

### Task 3: `tool_calls` 调用记录

**Files:**
- Create: `apps/api/src/data_intelligence_hub/models/tool_call.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/tool_calls.py`
- Create: `apps/api/src/data_intelligence_hub/services/tool_call_service.py`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Test: `apps/api/tests/unit/test_tool_calls.py`

**Interfaces:**
- Consumes: `Run`、`RunStep`、`TaskRun` 外键。
- Produces:
  - `ToolCall`
  - `ToolCallOutcome`
  - `record_tool_call(...) -> ToolCall`
  - `request_hash(payload) -> str`

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "RunStep" --direction upstream --repo .
```

Expected: 现有模型锚点，risk 不高于 LOW。新表只增加外键，不改变现有执行流。

- [ ] **Step 2: Write the failing tests**

Create `apps/api/tests/unit/test_tool_calls.py`:

```python
"""tool_calls 的幂等与结果写入。"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.repositories.tool_calls import (
    ToolCallIdempotencyConflictError,
    create_tool_call,
    get_tool_call,
)
from data_intelligence_hub.services.tool_call_service import record_tool_call
from tests.unit.budget_test_support import seed_budget_scope, with_sqlite_session


@pytest.mark.anyio
async def test_create_is_idempotent_for_same_request_hash() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="tool-call", with_task_run=True)
        first = await create_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=seed.step.id,
            tool_id="exa_search_lite",
            contract_version="1.0",
            idempotency_key_hash="a" * 64,
            request_hash="b" * 64,
            backend_ref_type="task_run",
            backend_ref_id=str(seed.task_run.id),
            outcome="success",
            started_at=datetime.now(UTC),
        )
        second = await create_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=seed.step.id,
            tool_id="exa_search_lite",
            contract_version="1.0",
            idempotency_key_hash="a" * 64,
            request_hash="b" * 64,
            backend_ref_type="task_run",
            backend_ref_id=str(seed.task_run.id),
            outcome="success",
            started_at=datetime.now(UTC),
        )
        observed["first"] = first.id
        observed["second"] = second.id

    await with_sqlite_session(scenario)

    assert observed["first"] == observed["second"]


@pytest.mark.anyio
async def test_same_key_with_different_request_hash_is_rejected() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="tool-conflict", with_task_run=True)
        await create_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=seed.step.id,
            tool_id="exa_search_lite",
            contract_version="1.0",
            idempotency_key_hash="c" * 64,
            request_hash="d" * 64,
            backend_ref_type="task_run",
            backend_ref_id=str(seed.task_run.id),
            outcome="success",
            started_at=datetime.now(UTC),
        )
        with pytest.raises(ToolCallIdempotencyConflictError):
            await create_tool_call(
                session,
                workspace_id=seed.workspace.id,
                project_id=seed.project.id,
                run_id=seed.run.id,
                step_id=seed.step.id,
                tool_id="exa_search_lite",
                contract_version="1.0",
                idempotency_key_hash="c" * 64,
                request_hash="e" * 64,
                backend_ref_type="task_run",
                backend_ref_id=str(seed.task_run.id),
                outcome="success",
                started_at=datetime.now(UTC),
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_record_tool_call_hashes_key_and_stores_outcome() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="tool-record", with_task_run=True)
        call = await record_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=seed.step.id,
            tool_id="exa_search_lite",
            contract_version="1.0",
            idempotency_key="run-1-step-0",
            request_payload={"endpoint_type": "exa_search_lite", "records": 1},
            backend_ref_type="task_run",
            backend_ref_id=str(seed.task_run.id),
            outcome="success",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        observed["hash"] = call.idempotency_key_hash
        observed["outcome"] = call.outcome
        observed["stored"] = await get_tool_call(
            session,
            workspace_id=seed.workspace.id,
            call_id=call.id,
        )

    await with_sqlite_session(scenario)

    assert observed["hash"] == hashlib.sha256(b"run-1-step-0").hexdigest()
    assert observed["outcome"] == "success"
    assert observed["stored"] is not None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_tool_calls.py -v
```

Expected: `ModuleNotFoundError: data_intelligence_hub.models.tool_call`.

- [ ] **Step 4: Implement the model**

Create `apps/api/src/data_intelligence_hub/models/tool_call.py`:

```python
"""工具调用意图 ``tool_calls``。

一行代表一次受治理的工具调用。它记录调用意图与结果。
采集类调用通过 ``backend_ref_type='task_run'`` 与 ``backend_ref_id``
关联 ``task_runs``。本表不复制 ``task_runs.status``。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class ToolCallOutcome(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    CONFIG_GATED = "config_gated"
    FAILED = "failed"


_OUTCOME_CHECK = "outcome IN ('success', 'empty', 'config_gated', 'failed')"


class ToolCall(UUIDPrimaryKeyMixin, Base):
    """一次工具调用。"""

    __tablename__ = "tool_calls"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "idempotency_key_hash",
            name="uq_tool_calls_workspace_idempotency",
        ),
        CheckConstraint(_OUTCOME_CHECK, name="outcome"),
        Index("ix_tool_calls_run_step", "run_id", "step_id"),
        Index("ix_tool_calls_tool_started", "tool_id", "started_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run_steps.id"))
    tool_id: Mapped[str] = mapped_column(String(200), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    backend_ref_type: Mapped[str | None] = mapped_column(String(40))
    backend_ref_id: Mapped[str | None] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    evidence_grade: Mapped[str | None] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Update `models/__init__.py`：

```python
from data_intelligence_hub.models.tool_call import ToolCall, ToolCallOutcome
```

并把 `"ToolCall"`、`"ToolCallOutcome"` 加入 `__all__`。

`tool_calls.tool_id` 是 `tool_catalog.tool_id` 的逻辑引用。C5 不建数据库外键：`tool_catalog` 是可重放快照，重建目录时会短暂清空；外键会让历史调用行阻塞目录重放。契约层仍登记 `references: tool_catalog.tool_id`。

- [ ] **Step 5: Implement the repository and service**

Create `apps/api/src/data_intelligence_hub/repositories/tool_calls.py`:

```python
"""``tool_calls`` 的读写与幂等。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.tool_call import ToolCall


class ToolCallIdempotencyConflictError(RuntimeError):
    message = "idempotency_conflict"


async def get_tool_call(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    call_id: uuid.UUID,
) -> ToolCall | None:
    result = await session.execute(
        select(ToolCall).where(
            ToolCall.id == call_id,
            ToolCall.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def get_by_idempotency_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    idempotency_key_hash: str,
) -> ToolCall | None:
    result = await session.execute(
        select(ToolCall).where(
            ToolCall.workspace_id == workspace_id,
            ToolCall.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def create_tool_call(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    step_id: uuid.UUID | None,
    tool_id: str,
    contract_version: str,
    idempotency_key_hash: str,
    request_hash: str,
    backend_ref_type: str | None,
    backend_ref_id: str | None,
    outcome: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    error_code: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    unit_price: Decimal | None = None,
    total_cost_usd: Decimal | None = None,
    evidence_grade: str | None = None,
) -> ToolCall:
    existing = await get_by_idempotency_key(
        session,
        workspace_id=workspace_id,
        idempotency_key_hash=idempotency_key_hash,
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ToolCallIdempotencyConflictError(idempotency_key_hash)
        return existing

    record = ToolCall(
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        step_id=step_id,
        tool_id=tool_id,
        contract_version=contract_version,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        backend_ref_type=backend_ref_type,
        backend_ref_id=backend_ref_id,
        outcome=outcome,
        error_code=error_code,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        total_cost_usd=total_cost_usd,
        evidence_grade=evidence_grade,
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(record)
    await session.flush()
    return record


__all__ = [
    "ToolCallIdempotencyConflictError",
    "create_tool_call",
    "get_by_idempotency_key",
    "get_tool_call",
]
```

Create `apps/api/src/data_intelligence_hub/services/tool_call_service.py`:

```python
"""工具调用回执。

幂等键只存摘要。请求摘要用于区分「同键不同请求」。
调用在结果确定后写入，因此 ``outcome`` 非空。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.models.tool_call import ToolCall, ToolCallOutcome
from data_intelligence_hub.repositories.tool_calls import (
    create_tool_call,
    update_tool_call,
)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return _hash_text(canonical)


async def record_tool_call(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    step_id: uuid.UUID | None,
    tool_id: str,
    contract_version: str,
    idempotency_key: str,
    request_payload: Mapping[str, Any],
    backend_ref_type: str | None,
    backend_ref_id: str | None,
    outcome: ToolCallOutcome | str,
    started_at: datetime,
    finished_at: datetime | None = None,
) -> ToolCall:
    return await create_tool_call(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        step_id=step_id,
        tool_id=tool_id,
        contract_version=contract_version,
        idempotency_key_hash=_hash_text(idempotency_key),
        request_hash=request_hash(request_payload),
        backend_ref_type=backend_ref_type,
        backend_ref_id=backend_ref_id,
        outcome=ToolCallOutcome(outcome).value,
        started_at=started_at,
        finished_at=finished_at,
    )


__all__ = [
    "record_tool_call",
    "request_hash",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_tool_calls.py -v
uv run ruff check src/data_intelligence_hub/models/tool_call.py \
  src/data_intelligence_hub/repositories/tool_calls.py \
  src/data_intelligence_hub/services/tool_call_service.py \
  tests/unit/test_tool_calls.py
```

Expected: 3 passed，ruff 通过。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/models/tool_call.py \
  apps/api/src/data_intelligence_hub/repositories/tool_calls.py \
  apps/api/src/data_intelligence_hub/services/tool_call_service.py \
  apps/api/src/data_intelligence_hub/models/__init__.py \
  apps/api/tests/unit/test_tool_calls.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(budget): add idempotent tool call records"
```

---

### Task 3A: `start_tool_call` / `complete_tool_call` API

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/repositories/tool_calls.py`
- Modify: `apps/api/src/data_intelligence_hub/services/tool_call_service.py`
- Test: `apps/api/tests/unit/test_tool_calls.py`

**Interfaces:**
- Consumes: `create_tool_call`、`get_by_idempotency_key`、`ToolCall`、`TaskRun`、`pricing.quote`。
- Produces:
  - `start_tool_call(session, *, workspace_id, project_id, run_id, step_id, tool_id, contract_version, idempotency_key, request_payload, backend_ref_type, backend_ref_id, started_at) -> ToolCall`
  - `complete_tool_call(session, *, call_id, outcome, error_code=None, task_run_id=None, quantity=None, unit=None, unit_price=None, total_cost_usd=None, finished_at=None) -> ToolCall`
- `start_tool_call` 先写一行占位记录：`outcome='failed'`、`error_code='in_progress'`、`finished_at=None`。进程崩溃时该行保留为 `failed/in_progress`，不伪装成功。
- `complete_tool_call` 覆盖占位结果，并把 `quantity`、`unit`、`unit_price`、`total_cost_usd` 同步到 `task_runs`（当 `task_run_id` 非空时）。C6 只传结果字段，不直接写账本。

- [ ] **Step 1: 写失败测试**

在 `apps/api/tests/unit/test_tool_calls.py` 追加：

```python
@pytest.mark.anyio
async def test_start_and_complete_tool_call_updates_task_run() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="tool-call-start",
            with_task_run=True,
        )
        call = await start_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=seed.step.id,
            tool_id="exa_search_lite",
            contract_version="run_collector.v1",
            idempotency_key="run:test:step:0:attempt:1:collector-call",
            request_payload={"task_id": str(seed.task_run.task_id)},
            backend_ref_type="task_run",
            backend_ref_id=str(seed.task_run.id),
            started_at=datetime.now(UTC),
        )
        assert call.outcome == "failed"
        assert call.error_code == "in_progress"
        completed = await complete_tool_call(
            session,
            call_id=call.id,
            outcome="success",
            task_run_id=seed.task_run.id,
            quantity=Decimal("2.000"),
            unit="record",
            unit_price=Decimal("0.002000"),
            total_cost_usd=Decimal("0.004000"),
            finished_at=datetime.now(UTC),
        )
        refreshed = await session.get(TaskRun, seed.task_run.id)
        observed["outcome"] = completed.outcome
        observed["total"] = refreshed.total_cost_usd
        observed["quantity"] = refreshed.quantity

    await with_sqlite_session(scenario)

    assert observed["outcome"] == "success"
    assert observed["total"] == Decimal("0.004000")
    assert observed["quantity"] == Decimal("2.000")


@pytest.mark.anyio
async def test_start_tool_call_is_idempotent_by_key() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="tool-call-idem")
        first = await start_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=None,
            tool_id="exa_search_lite",
            contract_version="run_collector.v1",
            idempotency_key="run:test:idem",
            request_payload={"task_id": "t"},
            backend_ref_type=None,
            backend_ref_id=None,
            started_at=datetime.now(UTC),
        )
        second = await start_tool_call(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            step_id=None,
            tool_id="exa_search_lite",
            contract_version="run_collector.v1",
            idempotency_key="run:test:idem",
            request_payload={"task_id": "t"},
            backend_ref_type=None,
            backend_ref_id=None,
            started_at=datetime.now(UTC),
        )
        assert first.id == second.id

    await with_sqlite_session(scenario)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_tool_calls.py -v
```

Expected: FAIL，`ImportError: cannot import name 'start_tool_call'`。

- [ ] **Step 3: 写实现**

在 `repositories/tool_calls.py` 加：

```python
async def update_tool_call(
    session: AsyncSession,
    *,
    call_id: uuid.UUID,
    values: Mapping[str, Any],
) -> ToolCall | None:
    await session.execute(
        update(ToolCall).where(ToolCall.id == call_id).values(**values)
    )
    await session.flush()
    return await session.get(ToolCall, call_id)
```

并在 `__all__` 加入 `update_tool_call`。文件头导入 `update` 与 `Mapping`。

在 `services/tool_call_service.py` 加：

```python
async def start_tool_call(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    step_id: uuid.UUID | None,
    tool_id: str,
    contract_version: str,
    idempotency_key: str,
    request_payload: Mapping[str, Any],
    backend_ref_type: str | None,
    backend_ref_id: str | None,
    started_at: datetime,
) -> ToolCall:
    # 占位行；complete_tool_call 覆盖。崩溃时保留 failed/in_progress。
    return await create_tool_call(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        step_id=step_id,
        tool_id=tool_id,
        contract_version=contract_version,
        idempotency_key_hash=_hash_text(idempotency_key),
        request_hash=request_hash(request_payload),
        backend_ref_type=backend_ref_type,
        backend_ref_id=backend_ref_id,
        outcome=ToolCallOutcome.FAILED.value,
        error_code="in_progress",
        started_at=started_at,
    )


async def complete_tool_call(
    session: AsyncSession,
    *,
    call_id: uuid.UUID,
    outcome: ToolCallOutcome | str,
    error_code: str | None = None,
    task_run_id: uuid.UUID | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    unit_price: Decimal | None = None,
    total_cost_usd: Decimal | None = None,
    finished_at: datetime | None = None,
) -> ToolCall:
    values: dict[str, Any] = {
        "outcome": ToolCallOutcome(outcome).value,
        "error_code": error_code,
        "finished_at": finished_at or datetime.now(UTC),
    }
    for key, value in (
        ("quantity", quantity),
        ("unit", unit),
        ("unit_price", unit_price),
        ("total_cost_usd", total_cost_usd),
    ):
        if value is not None:
            values[key] = value
    updated = await update_tool_call(session, call_id=call_id, values=values)
    if updated is None:
        raise ValueError(f"tool_call 不存在：{call_id}")
    if task_run_id is not None:
        await session.execute(
            update(TaskRun)
            .where(TaskRun.id == task_run_id)
            .values(
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                total_cost_usd=total_cost_usd,
                updated_at=datetime.now(UTC),
            )
        )
        await session.flush()
    return updated
```

`TaskRun` 需要 `updated_at` 列；如果没有，去掉该字段。C1 的 task_runs 有 `updated_at`（C5 extend）。OK。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_tool_calls.py -v
uv run ruff check src/data_intelligence_hub/repositories/tool_calls.py \
  src/data_intelligence_hub/services/tool_call_service.py tests/unit/test_tool_calls.py
```

Expected: 全部通过，ruff 通过。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "start_tool_call" --direction upstream --repo .
node .gitnexus/run.cjs impact "complete_tool_call" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/repositories/tool_calls.py \
  apps/api/src/data_intelligence_hub/services/tool_call_service.py \
  apps/api/tests/unit/test_tool_calls.py
git commit -m "feat(budget): add start and complete tool call API"
```

Expected: 全部通过；`detect-changes` 不含 `partial: true` / `truncated: true`。

---

### Task 4: 按订单拆分 run 授权与项目 ACL

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/models/authorization.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/authorizations.py`
- Create: `apps/api/src/data_intelligence_hub/services/run_authorizations.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Modify: `apps/api/src/data_intelligence_hub/core/config.py`
- Test: `apps/api/tests/unit/test_run_authorizations.py`

**Interfaces:**
- Consumes: C4 `WorkbenchTask.max_cost_usd` / `max_pages` / `max_records` / `primary_market` / `status`、`WorkflowVersion.workbench_task_id`、`Run`、`Workspace`、`Authorization`、C2 `require_project_access`。
- Produces:
  - `Authorization.run_id: uuid.UUID | None`
  - `list_authorizations_for_run(session, *, run_id, workspace_id=None) -> list[Authorization]`
  - `get_run_budget_authorization(session, *, run_id, workspace_id=None) -> Authorization | None`（只返回 `G-Cost/pass`）
  - `get_run_authorization_for_actor(session, *, context, run_id) -> Authorization | None`（先 `require_project_access(..., manage=False)`；同工作区跨项目 403，跨工作区 404）
  - `has_blocked_gate(session, *, run_id) -> bool`
  - `create_run_authorization(session, *, run_id, max_cost_usd, approver, expires_at, scope, gate_status="pass") -> Authorization`（`G-Cost`；只允许 `create_order_run_authorizations` 与零预算路径调用）
  - `create_order_run_authorizations(session, *, workbench_task_id, approver, expires_at, at=None) -> list[Authorization]`：读取订单全部逐市场 run，把 `workbench_tasks.max_cost_usd` 拆成 per-market `G-Cost` 行；金额量化到 6 位小数，所有行（含 blocked 市场）之和精确等于订单上限；主市场行取得十进制余数；`max_cost_usd` 为空时每行 `0.000000`，不读取任何默认值；blocked G-Plan 的 run 得到 `G-Cost/blocked`，其余得到 `G-Cost/pass`
  - `ensure_order_run_authorization(session, *, run_id, at=None) -> Authorization | None`（存在 blocked G-Plan 时返回该 run 的 blocked 行；有订单时调用拆分；无订单时创建 `0.000000` 的 `G-Cost/pass`，不发明默认上限）
  - `backfill_default_run_authorizations(session, *, at=None) -> int`（绑定 blocked G-Plan；只给无 blocked 的 run 建零预算 pass）

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "Authorization" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_authorization" --direction upstream --repo .
```

Expected: `risk` 不高于 LOW。`OrmRunRepository._resolve_authorization_id` 的接线归 C6；C5 只交付仓储查询函数，不修改 adapter。

- [ ] **Step 2: Write the failing tests**

Create `apps/api/tests/unit/test_run_authorizations.py`:

```python
"""按订单拆分 run 授权、零预算回填与项目 ACL。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project, ProjectMember
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.models.workspace import WorkspaceMember
from data_intelligence_hub.repositories.authorizations import (
    create_authorization,
    get_run_budget_authorization,
    list_authorizations_for_run,
)
from data_intelligence_hub.services.budget_service import reserve_run_budget
from data_intelligence_hub.services.run_authorizations import (
    backfill_default_run_authorizations,
    create_order_run_authorizations,
    create_run_authorization,
    ensure_order_run_authorization,
    get_run_authorization_for_actor,
)
from tests.unit.budget_test_support import seed_budget_scope, with_sqlite_session
from tests.unit.workbench_support import seed_workbench_scope


async def _seed_order(
    session: AsyncSession,
    *,
    markets: tuple[str, ...],
    primary_market: str,
    max_cost_usd: Decimal | None,
) -> tuple[WorkbenchTask, WorkflowVersion, list[Run]]:
    workbench = await seed_workbench_scope(session, suffix=f"c5-{uuid.uuid4().hex[:8]}")
    task = await session.get(WorkbenchTask, workbench.task_id)
    task.max_cost_usd = max_cost_usd
    task.max_pages = 10
    task.max_records = 500
    task.primary_market = primary_market
    task.comparison_markets = [market for market in markets if market != primary_market]
    task.markets = list(markets)
    task.status = "submitted"
    version = await session.get(WorkflowVersion, workbench.version_id)
    runs = [
        Run(
            workspace_id=workbench.workspace_id,
            project_id=workbench.project_id,
            workflow_version_id=version.id,
            market_code=market,
            status="queued",
            execution_mode="live",
            trigger="manual",
            records_count=0,
        )
        for market in markets
    ]
    session.add_all(runs)
    await session.flush()
    return task, version, runs


@pytest.mark.anyio
async def test_each_run_gets_its_own_authorization() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-run",
            max_cost_usd=Decimal("1.000000"),
        )
        second = Run(
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            status="queued",
            execution_mode="live",
            trigger="manual",
            records_count=0,
        )
        session.add(second)
        await session.flush()
        first_auth = await create_run_authorization(
            session,
            run_id=seed.run.id,
            max_cost_usd=Decimal("1.000000"),
            approver=seed.user.id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            scope={"template_id": "t1_voc"},
        )
        second_auth = await create_run_authorization(
            session,
            run_id=second.id,
            max_cost_usd=Decimal("2.000000"),
            approver=seed.user.id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            scope={"template_id": "t1_voc"},
        )
        observed["first"] = first_auth.max_cost_usd
        observed["second"] = second_auth.max_cost_usd
        observed["first_lookup"] = (
            await get_run_budget_authorization(session, run_id=seed.run.id)
        ).max_cost_usd
        observed["second_lookup"] = (
            await get_run_budget_authorization(session, run_id=second.id)
        ).max_cost_usd

    await with_sqlite_session(scenario)

    assert observed["first"] == Decimal("1.000000")
    assert observed["second"] == Decimal("2.000000")
    assert observed["first_lookup"] == Decimal("1.000000")
    assert observed["second_lookup"] == Decimal("2.000000")


@pytest.mark.anyio
async def test_default_authorization_uses_workspace_owner_and_marker() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-default",
            with_authorization=False,
        )
        authorization = await ensure_order_run_authorization(
            session,
            run_id=seed.run.id,
        )
        observed["approver"] = authorization.approver
        observed["max_cost"] = authorization.max_cost_usd
        observed["scope"] = authorization.scope
        observed["gate_status"] = authorization.gate_status

    await with_sqlite_session(scenario)

    assert observed["approver"] is not None
    assert observed["max_cost"] == Decimal("0.000000")
    assert observed["scope"]["origin"] == "c5_zero_budget_backfill"
    assert observed["gate_status"] == "pass"


@pytest.mark.anyio
async def test_default_authorization_is_idempotent() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-idempotent",
            with_authorization=False,
        )
        first = await ensure_order_run_authorization(session, run_id=seed.run.id)
        second = await ensure_order_run_authorization(session, run_id=seed.run.id)
        observed["first"] = first.id
        observed["second"] = second.id

    await with_sqlite_session(scenario)

    assert observed["first"] == observed["second"]


@pytest.mark.anyio
async def test_order_budget_splits_exactly_and_primary_gets_decimal_remainder() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-order-split",
            with_authorization=False,
        )
        task, version, runs = await _seed_order(
            session,
            markets=("US", "DE", "GB"),
            primary_market="US",
            max_cost_usd=Decimal("10.000000"),
        )
        authorizations = await create_order_run_authorizations(
            session,
            workbench_task_id=task.id,
            approver=seed.user.id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        by_market = {
            row.scope["market_code"]: row.max_cost_usd
            for row in authorizations
        }
        observed["sum"] = sum(by_market.values(), Decimal("0.000000"))
        observed["primary"] = by_market["US"]
        observed["compare"] = {by_market["DE"], by_market["GB"]}
        observed["run_ids"] = {run.id for run in runs}

    await with_sqlite_session(scenario)

    assert observed["sum"] == Decimal("10.000000")
    assert observed["primary"] == Decimal("3.333334")
    assert observed["compare"] == {Decimal("3.333333")}


@pytest.mark.anyio
async def test_null_order_cap_yields_zero_and_enforced_block() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-order-null",
            with_authorization=False,
        )
        task, _, runs = await _seed_order(
            session,
            markets=("US", "DE"),
            primary_market="US",
            max_cost_usd=None,
        )
        authorizations = await create_order_run_authorizations(
            session,
            workbench_task_id=task.id,
            approver=seed.user.id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        observed["amounts"] = {row.max_cost_usd for row in authorizations}
        observed["statuses"] = {row.gate_status for row in authorizations}
        with pytest.raises(Exception):
            await reserve_run_budget(
                session,
                run_id=runs[0].id,
                enforce=True,
            )

    await with_sqlite_session(scenario)

    assert observed["amounts"] == {Decimal("0.000000")}
    assert observed["statuses"] == {"pass"}


@pytest.mark.anyio
async def test_authorization_read_denies_same_workspace_cross_project_member() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-acl",
            with_authorization=False,
        )
        second_project = Project(
            workspace_id=seed.workspace.id,
            name="other project",
            domain="mother_baby",
            owner_id=seed.user.id,
        )
        session.add(second_project)
        await session.flush()
        member = User(
            email=f"member-{uuid.uuid4().hex}@example.com",
            password_hash="x",
            name="Member",
        )
        session.add(member)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=seed.workspace.id,
                user_id=member.id,
                role="member",
            )
        )
        session.add(
            ProjectMember(
                workspace_id=seed.workspace.id,
                project_id=seed.project.id,
                user_id=member.id,
            )
        )
        other_run = Run(
            workspace_id=seed.workspace.id,
            project_id=second_project.id,
            status="queued",
            execution_mode="live",
            trigger="manual",
            records_count=0,
        )
        session.add(other_run)
        await session.flush()
        context = SimpleNamespace(workspace=seed.workspace, user=member)
        with pytest.raises(Exception) as exc_info:
            await get_run_authorization_for_actor(
                session,
                context=context,
                run_id=other_run.id,
            )
        observed["code"] = getattr(exc_info.value, "code", None)

    await with_sqlite_session(scenario)

    assert observed["code"] == "project_access_forbidden"


@pytest.mark.anyio
async def test_backfill_covers_every_run_without_authorization() -> None:
    observed: dict[str, int] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-backfill",
            with_authorization=False,
        )
        second = Run(
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            status="completed",
            execution_mode="live",
            trigger="manual",
            records_count=0,
            total_cost_usd=Decimal("0.300000"),
        )
        session.add(second)
        await session.flush()
        count = await backfill_default_run_authorizations(session)
        observed["count"] = count
        observed["first"] = await get_run_budget_authorization(session, run_id=seed.run.id) is not None
        observed["second"] = await get_run_budget_authorization(session, run_id=second.id) is not None

    await with_sqlite_session(scenario)

    assert observed["count"] == 2
    assert observed["first"] is True
    assert observed["second"] is True


@pytest.mark.anyio
async def test_same_run_can_have_blocked_plan_and_cost_gate() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-multi",
            with_authorization=False,
        )
        now = datetime.now(UTC)
        blocked = await create_authorization(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            scope={"market_code": "DE"},
            max_cost_usd=Decimal("0"),
            approver=seed.user.id,
            expires_at=now + timedelta(days=30),
            gate_id="G-Plan",
            gate_status="blocked",
            run_id=seed.run.id,
        )
        cost = await create_authorization(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            scope={"markets": ["US"]},
            max_cost_usd=Decimal("1.000000"),
            approver=seed.user.id,
            expires_at=now + timedelta(days=30),
            gate_id="G-Cost",
            gate_status="pass",
            run_id=seed.run.id,
        )
        observed["ids"] = {blocked.id, cost.id}
        observed["count"] = len(
            await list_authorizations_for_run(session, run_id=seed.run.id)
        )

    await with_sqlite_session(scenario)

    assert len(observed["ids"]) == 2
    assert observed["count"] == 2


@pytest.mark.anyio
async def test_same_run_and_gate_cannot_repeat() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-unique",
            with_authorization=False,
        )
        now = datetime.now(UTC)
        await create_authorization(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            scope={"markets": ["US"]},
            max_cost_usd=Decimal("1.000000"),
            approver=seed.user.id,
            expires_at=now + timedelta(days=30),
            gate_id="G-Cost",
            run_id=seed.run.id,
        )
        with pytest.raises(IntegrityError):
            await create_authorization(
                session,
                workspace_id=seed.workspace.id,
                project_id=seed.project.id,
                scope={"markets": ["DE"]},
                max_cost_usd=Decimal("1.000000"),
                approver=seed.user.id,
                expires_at=now + timedelta(days=30),
                gate_id="G-Cost",
                run_id=seed.run.id,
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_backfill_binds_blocked_plan_and_does_not_create_pass() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="auth-blocked",
            with_authorization=False,
        )
        now = datetime.now(UTC)
        blocked = await create_authorization(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            plan_version_id=seed.run.workflow_version_id,
            scope={"market_code": seed.run.market_code},
            max_cost_usd=Decimal("0"),
            approver=seed.user.id,
            expires_at=now + timedelta(days=30),
            gate_id="G-Plan",
            gate_status="blocked",
        )
        count = await backfill_default_run_authorizations(session)
        gates = await list_authorizations_for_run(session, run_id=seed.run.id)
        observed["count"] = count
        observed["gates"] = {(gate.gate_id, gate.gate_status) for gate in gates}
        observed["blocked_id"] = blocked.id

    await with_sqlite_session(scenario)

    assert observed["count"] == 1
    assert observed["gates"] == {("G-Plan", "blocked")}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_authorizations.py -v
```

Expected: `ImportError: cannot import name 'create_run_authorization'` 或 `TypeError: create_authorization() got an unexpected keyword argument 'run_id'`。

- [ ] **Step 4: Extend the authorization model and repository**

在 `models/authorization.py` 的 `Authorization` 类中加：

```python
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
```

在 `__table_args__` 中加：

```python
        Index(
            "uq_authorizations_run_gate",
            "run_id",
            "gate_id",
            unique=True,
            postgresql_where=text("run_id IS NOT NULL"),
            sqlite_where=text("run_id IS NOT NULL"),
        ),
```

并在文件顶部导入 `text`。`max_cost_usd` 的 `CheckConstraint` 保持 `>= 0`。同一个 run 允许 `G-Plan/blocked` 与 `G-Cost/pass` 两行；同一 `(run_id, gate_id)` 只能一行。

在 `repositories/authorizations.py` 的 `create_authorization` 签名中加：

```python
    run_id: uuid.UUID | None = None,
```

并把 `run_id=run_id` 传给 `Authorization(...)`。

新增：

```python
async def list_authorizations_for_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> list[Authorization]:
    # 一个 run 可有多 gate；跨工作区返回空列表。
    statement = select(Authorization).where(Authorization.run_id == run_id)
    if workspace_id is not None:
        statement = statement.where(Authorization.workspace_id == workspace_id)
    result = await session.execute(statement.order_by(Authorization.gate_id))
    return list(result.scalars().all())


async def get_run_budget_authorization(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> Authorization | None:
    # 预算只认 G-Cost/pass；blocked G-Plan 不参与预算。
    for authorization in await list_authorizations_for_run(
        session,
        run_id=run_id,
        workspace_id=workspace_id,
    ):
        if (
            authorization.gate_id == "G-Cost"
            and authorization.gate_status == "pass"
            and authorization.revoked_at is None
        ):
            return authorization
    return None


async def has_blocked_gate(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
) -> bool:
    statement = select(Authorization.id).where(
        Authorization.run_id == run_id,
        Authorization.gate_status == "blocked",
    )
    return (await session.scalar(statement.limit(1))) is not None
```

把三个新函数加入 `__all__`。

- [ ] **Step 5: Add settings and the run authorization service**

在 `core/config.py` 的 `Settings` 中加：

```python
    # C5：不发明业务阈值。run 授权上限只来自 C4 订单预算；没有订单时为零。
    # 环境变量名与 compose 映射必须完全一致；不得使用 SCRAPY_ 前缀。
    budget_enforcement_enabled: bool = Field(
        default=False,
        validation_alias="BUDGET_ENFORCEMENT_ENABLED",
    )
    strict_price_enabled: bool = Field(
        default=False,
        validation_alias="STRICT_PRICE_ENABLED",
    )
    default_quota_limit_usd: Decimal = Field(
        default=Decimal("0.000000"),
        ge=Decimal("0"),
    )
```

不得增加 `default_run_authorization_max_cost_usd` 或任何等价的默认授权上限。在文件顶部导入 `Decimal`。

在 `services/exceptions.py` 中加：

```python
class AuthorizationConflictError(ServiceError):
    message = "authorization_conflict"


class PriceChangeAuditRequiredError(ServiceError):
    message = "price_change_audit_required"


class ApprovalInvalidError(ServiceError):
    message = "invalid_request"


class ApprovalNotFoundError(ServiceError):
    message = "approval_not_found"


class ApprovalSelfApprovalForbiddenError(ServiceError):
    message = "approval_self_approval_forbidden"


class ApprovalStateConflictError(ServiceError):
    message = "approval_state_conflict"


class RunLimitExceededError(ServiceError):
    message = "max_pages_exceeded"
```

Create `apps/api/src/data_intelligence_hub/services/run_authorizations.py`:

```python
"""按订单拆分 run 授权、零预算授权与回填。

一个 run 可以有多条 gate（例如 blocked G-Plan + pass G-Cost）。
预算只读 G-Cost/pass。订单上限只来自 C4 ``workbench_tasks.max_cost_usd``；
没有订单或订单上限为空时创建 0 预算授权，不读取任何默认上限。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.authorizations import (
    create_authorization,
    get_run_budget_authorization,
    has_blocked_gate,
    list_authorizations_for_run,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.exceptions import AuthorizationConflictError

DEFAULT_AUTHORIZATION_DAYS = 365
SIX_PLACES = Decimal("0.000001")


async def create_run_authorization(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    max_cost_usd: Decimal | int | str,
    approver: uuid.UUID,
    expires_at: datetime,
    scope: Mapping[str, Any] | None = None,
    gate_status: str = "pass",
) -> Authorization:
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"run 不存在：{run_id}")
    existing = await get_run_budget_authorization(session, run_id=run_id)
    requested = Decimal(str(max_cost_usd))
    if existing is not None:
        if existing.max_cost_usd != requested:
            raise AuthorizationConflictError(str(run_id))
        return existing
    payload = {"origin": "run_submission", "run_id": str(run_id)}
    if scope is not None:
        payload.update(dict(scope))
    return await create_authorization(
        session,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        scope=payload,
        max_cost_usd=requested,
        approver=approver,
        expires_at=expires_at,
        plan_version_id=run.workflow_version_id,
        gate_id="G-Cost",
        gate_status=gate_status,
        run_id=run_id,
    )


def _split_order_cap(
    cap: Decimal | None,
    *,
    markets: list[str],
    primary_market: str,
) -> dict[str, Decimal]:
    """把订单上限拆成逐市场金额；所有金额之和精确等于量化后的上限。

    ``cap`` 为空时返回全零，不读取任何默认值。主市场取得十进制余数；
    没有主市场行时余数给第一个市场。
    """
    if not markets:
        return {}
    normalized = (
        Decimal("0.000000")
        if cap is None
        else Decimal(str(cap)).quantize(SIX_PLACES)
    )
    if normalized < 0:
        raise ValueError("order cap 必须 >= 0")
    base = (normalized / len(markets)).quantize(SIX_PLACES, rounding=ROUND_FLOOR)
    remainder = normalized - base * len(markets)
    primary = primary_market if primary_market in markets else markets[0]
    return {
        market: base + remainder if market == primary else base
        for market in markets
    }


async def _order_runs(
    session: AsyncSession,
    *,
    workbench_task_id: uuid.UUID,
) -> list[Run]:
    statement = (
        select(Run)
        .join(
            WorkflowVersion,
            WorkflowVersion.id == Run.workflow_version_id,
        )
        .where(WorkflowVersion.workbench_task_id == workbench_task_id)
        .order_by(Run.market_code, Run.created_at, Run.id)
    )
    return list((await session.execute(statement)).scalars().all())


async def create_order_run_authorizations(
    session: AsyncSession,
    *,
    workbench_task_id: uuid.UUID,
    approver: uuid.UUID,
    expires_at: datetime,
    at: datetime | None = None,
) -> list[Authorization]:
    """按 C4 订单预算创建逐市场 G-Cost 授权。

    规则：
    - 所有 per-market 行（含 blocked G-Plan 市场）金额之和等于订单上限。
    - 主市场取得十进制余数。
    - ``max_cost_usd`` 为空时每行为 0；enforce 由预算服务阻断。
    - blocked G-Plan 的 run 得到 G-Cost/blocked，绝不升级为 pass。
    """
    task = await session.get(
        WorkbenchTask,
        workbench_task_id,
        with_for_update=True,
    )
    if task is None:
        raise ValueError(f"workbench task 不存在：{workbench_task_id}")
    if task.status != "submitted":
        raise AuthorizationConflictError("order_not_approved")
    runs = await _order_runs(session, workbench_task_id=workbench_task_id)
    if not runs:
        return []
    existing = {
        row.run_id: row
        for row in (
            await session.execute(
                select(Authorization).where(
                    Authorization.run_id.in_([run.id for run in runs]),
                    Authorization.gate_id == "G-Cost",
                )
            )
        ).scalars().all()
    }
    split = _split_order_cap(
        task.max_cost_usd,
        markets=[run.market_code or "" for run in runs],
        primary_market=task.primary_market,
    )
    if len(split) != len(runs):
        raise AuthorizationConflictError("duplicate_market_run")
    now = at or datetime.now(UTC)
    created: list[Authorization] = []
    new_count = 0
    for run in runs:
        market = run.market_code or ""
        if run.id in existing:
            expected_status = (
                "blocked"
                if await has_blocked_gate(session, run_id=run.id)
                else "pass"
            )
            if (
                existing[run.id].max_cost_usd != split[market]
                or existing[run.id].gate_status != expected_status
            ):
                raise AuthorizationConflictError("order_split_conflict")
            created.append(existing[run.id])
            continue
        new_count += 1
        gate_status = (
            "blocked"
            if await has_blocked_gate(session, run_id=run.id)
            else "pass"
        )
        authorization = await create_authorization(
            session,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            scope={
                "origin": "c4_order_split",
                "order_id": str(workbench_task_id),
                "market_code": market,
                "primary_market": task.primary_market,
                "order_cap_usd": str(
                    Decimal("0.000000")
                    if task.max_cost_usd is None
                    else Decimal(str(task.max_cost_usd)).quantize(SIX_PLACES)
                ),
            },
            max_cost_usd=split[market],
            approver=approver,
            expires_at=expires_at,
            plan_version_id=run.workflow_version_id,
            gate_id="G-Cost",
            gate_status=gate_status,
            run_id=run.id,
        )
        created.append(authorization)
    if new_count == 0:
        return created
    await append_audit_event(
        session,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        actor_type="system",
        action="budget.limit.changed",
        resource_type="workbench_task_budget",
        resource_id=str(workbench_task_id),
        result="success",
        details={
            "origin": "c4_order_split",
            "order_cap_usd": str(
                Decimal("0.000000")
                if task.max_cost_usd is None
                else Decimal(str(task.max_cost_usd)).quantize(SIX_PLACES)
            ),
            "split": {market: str(amount) for market, amount in split.items()},
            "run_count": len(runs),
            "null_cap": task.max_cost_usd is None,
        },
        occurred_at=now,
    )
    return created


async def ensure_order_run_authorization(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    at: datetime | None = None,
) -> Authorization | None:
    if await has_blocked_gate(session, run_id=run_id):
        # blocked run 不建 pass；返回同 run 的 G-Cost/blocked 行（若有）。
        rows = await list_authorizations_for_run(session, run_id=run_id)
        return next(
            (
                row
                for row in rows
                if row.gate_id == "G-Cost" and row.gate_status == "blocked"
            ),
            None,
        )
    existing = await get_run_budget_authorization(session, run_id=run_id)
    if existing is not None:
        return existing
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"run 不存在：{run_id}")
    # 有 C4 订单时由拆分函数一次性创建全部 per-market 行。
    if run.workflow_version_id is not None:
        task_id = await session.scalar(
            select(WorkflowVersion.workbench_task_id).where(
                WorkflowVersion.id == run.workflow_version_id
            )
        )
        if task_id is not None:
            await create_order_run_authorizations(
                session,
                workbench_task_id=task_id,
                approver=(await session.get(Workspace, run.workspace_id)).owner_id,
                expires_at=(at or datetime.now(UTC))
                + timedelta(days=DEFAULT_AUTHORIZATION_DAYS),
                at=at,
            )
            existing = await get_run_budget_authorization(
                session,
                run_id=run_id,
            )
            if existing is not None:
                return existing
    workspace = await session.get(Workspace, run.workspace_id)
    if workspace is None:
        raise ValueError(f"workspace 不存在：{run.workspace_id}")
    now = at or datetime.now(UTC)
    # 没有订单时只建 0 预算授权；不发明默认上限。
    return await create_run_authorization(
        session,
        run_id=run_id,
        max_cost_usd=Decimal("0.000000"),
        approver=workspace.owner_id,
        expires_at=now + timedelta(days=DEFAULT_AUTHORIZATION_DAYS),
        scope={"origin": "c5_zero_budget_backfill"},
    )


async def get_run_authorization_for_actor(
    session: AsyncSession,
    *,
    context,
    run_id: uuid.UUID,
) -> Authorization | None:
    """带项目 ACL 的授权读取；同工作区跨项目 403，跨工作区 404。"""
    from data_intelligence_hub.api.authz import require_project_access

    run = await session.get(Run, run_id)
    if run is None:
        return None
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=run.project_id,
        manage=False,
    )
    return await get_run_budget_authorization(
        session,
        run_id=run_id,
        workspace_id=run.workspace_id,
    )


async def backfill_default_run_authorizations(
    session: AsyncSession,
    *,
    at: datetime | None = None,
) -> int:
    """绑定 blocked G-Plan；只给没有 blocked 的 run 建默认 G-Cost。

    返回绑定或新建的行数。blocked G-Plan 绝不升级为 pass。
    """
    result = await session.execute(
        select(Run)
        .outerjoin(Authorization, Authorization.run_id == Run.id)
        .where(Authorization.id.is_(None))
        .order_by(Run.created_at, Run.id)
    )
    count = 0
    for run in result.scalars().all():
        bound = False
        if run.workflow_version_id is not None and run.market_code is not None:
            blocked_rows = (
                await session.execute(
                    select(Authorization).where(
                        Authorization.plan_version_id == run.workflow_version_id,
                        Authorization.gate_id == "G-Plan",
                        Authorization.gate_status == "blocked",
                        Authorization.run_id.is_(None),
                    )
                )
            ).scalars().all()
            for row in blocked_rows:
                scope = row.scope if isinstance(row.scope, dict) else {}
                if scope.get("market_code") == run.market_code:
                    row.run_id = run.id
                    bound = True
                    break
        if bound:
            count += 1
            continue
        created = await ensure_order_run_authorization(
            session,
            run_id=run.id,
            at=at,
        )
        if created is not None:
            count += 1
    return count


__all__ = [
    "DEFAULT_AUTHORIZATION_DAYS",
    "backfill_default_run_authorizations",
    "create_order_run_authorizations",
    "create_run_authorization",
    "ensure_order_run_authorization",
    "get_run_authorization_for_actor",
]
```

- [ ] **Step 6: 交 C6 接线（C5 不改执行器）

C5 不修改 `run_executor.py`、`run_executor_adapters.py`、`run_worker_runtime.py` 或 `run_collector_call.py`。C6 必须：

- 用 `get_run_budget_authorization` 按 run 取 `G-Cost/pass`，不再按模板匹配；任何对外授权读取路由必须调用 `get_run_authorization_for_actor`（内部 `require_project_access`），不得直接暴露仓储函数。
- 在执行前调用 `has_blocked_gate`；blocked run 保持 `queued`，不得执行，也不得写成 `failed`。
- 用 C5 的 `OrmRunBudget` 适配器注入预算；不得直接调用 `record_entry`。
- 在每个 attempt 调用 `start_tool_call` / `complete_tool_call`；`tool_calls.step_id` 写逻辑 step 的 `run_steps.id`，幂等键含 step/attempt。
- `RunBudget.settle` 汇总该 run 全部 attempt 的 `task_runs.total_cost_usd`；失败 attempt 的成本不得丢失。
- 在 attempt 前调用 `resolve_run_limits`，把 `max_pages` / `max_records` 传给 collector；`None` 原样透传，超限立即停止。

C5 只在本任务交付 `get_run_budget_authorization`、`get_run_authorization_for_actor`、`has_blocked_gate`、`list_authorizations_for_run` 与 `OrmRunBudget`（Task 9）。

- [ ] **Step 7: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_authorizations.py -v
uv run ruff check src/data_intelligence_hub/models/authorization.py \
  src/data_intelligence_hub/repositories/authorizations.py \
  src/data_intelligence_hub/services/run_authorizations.py \
  tests/unit/test_run_authorizations.py
```

Expected: 10 passed，ruff 通过。必须覆盖精确拆分、主市场余数、空上限零预算、enforce 阻断与跨项目 403。

- [ ] **Step 8: 提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/models/authorization.py \
  apps/api/src/data_intelligence_hub/repositories/authorizations.py \
  apps/api/src/data_intelligence_hub/services/run_authorizations.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/src/data_intelligence_hub/core/config.py \
  apps/api/tests/unit/test_run_authorizations.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(budget): bind authorizations to individual runs"
```

---

### Task 4A: owner/admin 内联批准动作（`workbench_approval_actions`）

**Files:**
- Create: `apps/api/src/data_intelligence_hub/models/workbench_approval.py`
- Create: `apps/api/src/data_intelligence_hub/repositories/workbench_approvals.py`
- Create: `apps/api/src/data_intelligence_hub/services/workbench_approvals.py`
- Create: `apps/api/src/data_intelligence_hub/schemas/workbench_approval.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/workbench_approvals.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`（挂载路由）
- Test: `apps/api/tests/unit/test_workbench_approvals.py`

**Interfaces:**
- Consumes: C1 `workbench_approval_actions` 13 列、`approval_not_found` / `approval_self_approval_forbidden` / `approval_state_conflict`、C2 `require_workspace_role` / `require_project_access` / `append_audit_event`。
- Produces:
  - `WorkbenchApprovalAction` 模型与 `WorkbenchApprovalStatus` / `WorkbenchApprovalActionType` 常量。
  - `create_approval_action(session, *, context, task_id, action_type, payload, idempotency_key, expires_at) -> WorkbenchApprovalAction`
  - `decide_approval_action(session, *, context, task_id, approval_id, decision, reason=None) -> WorkbenchApprovalAction`
  - 只暴露两个 C1 路径：
    - `POST /api/workbench/tasks/{task_id}/approvals`（必须带 `Idempotency-Key`）
    - `POST /api/workbench/tasks/{task_id}/approvals/{approval_id}`
- **不新增**收件箱、独立 inbox 页面、列表页或任何未登记路径。C14 只在任务工作台内联渲染这两个动作。
- 允许的 `action_type` 只有 C1 的三值：`budget_overage`、`package_addon`、`project_key_change`。允许的 `status` 只有 `pending`、`approved`、`rejected`、`expired`。
- **请求人不得自批。** `requester_user_id` 在创建时取当前用户；`approver_user_id` 创建时必须为空。决定时若 `requester_user_id == context.user.id`，返回 403 `approval_self_approval_forbidden`。数据库 CHECK `ck_workbench_approval_actions_self_approval` 是第二道防线。
- **项目 ACL。** 创建走 `require_project_access(..., manage=False)`；决定走 `require_workspace_role(..., ("owner", "admin"))` 且 `require_project_access(..., manage=True)`。同工作区 member 跨项目返回 403 `project_access_forbidden`，跨工作区返回 404 `project_not_found`。
- **审计。** 创建不写审计；批准写 `budget.limit.changed` + `result="success"`，拒绝写 `budget.limit.changed` + `result="denied"`，`details.decision` 为 `approved` / `rejected`。不得自造 `budget.approval.*`。
- **批准预算超支。** `budget_overage` 的 payload 必须含正数 `amount_usd` 与目标 `run_id`；批准时只增加该 run 的 `G-Cost/pass` 授权上限，不重拆订单其他市场，不改 C4 `workbench_tasks.max_cost_usd`。`package_addon` 与 `project_key_change` 只记录批准事实，由 C4/C6 消费，不在 C5 执行。

- [ ] **Step 1: Run impact**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "WorkbenchApprovalAction" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_approval_action" --direction upstream --repo .
```

Expected: 新符号没有调用者，`risk: UNKNOWN`。用文本搜索确认仓库中不存在同名实现；`UNKNOWN` 不是放行信号。

- [ ] **Step 2: Write the failing tests**

Create `apps/api/tests/unit/test_workbench_approvals.py`。至少覆盖：

```python
@pytest.mark.anyio
async def test_requester_cannot_approve_own_action() -> None:
    # owner 创建 budget_overage，再以同一用户决定 → 403 approval_self_approval_forbidden
    ...


@pytest.mark.anyio
async def test_admin_approves_and_c2_audit_is_appended() -> None:
    # owner 创建，admin 批准；审批行 approved，audit_events 有 budget.limit.changed/success
    ...


@pytest.mark.anyio
async def test_rejection_audits_denied() -> None:
    # owner 创建，admin 拒绝；audit_events 有 budget.limit.changed/denied
    ...


@pytest.mark.anyio
async def test_same_workspace_member_cross_project_is_forbidden() -> None:
    # member 只属于项目 A；对项目 B 的 task 创建/决定 → 403 project_access_forbidden
    ...


@pytest.mark.anyio
async def test_create_is_idempotent_and_state_conflict_is_rejected() -> None:
    # 同一 Idempotency-Key 返回同一行；已决定后再次决定 → approval_state_conflict
    ...
```

测试必须断言：只写 `audit_events`，不新建审计表；创建时 `approver_user_id IS NULL`；决定后 `approver_user_id` 是 owner/admin 且 `decided_at` 非空。

- [ ] **Step 3: Implement the model**

Create `apps/api/src/data_intelligence_hub/models/workbench_approval.py`：

```python
"""owner/admin 内联批准动作 ``workbench_approval_actions``。

C1 冻结 13 列、3 个 CHECK、2 个索引。本表只承载
``budget_overage`` / ``package_addon`` / ``project_key_change``。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

ACTION_TYPES = ("budget_overage", "package_addon", "project_key_change")
STATUSES = ("pending", "approved", "rejected", "expired")


class WorkbenchApprovalAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workbench_approval_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('budget_overage', 'package_addon', 'project_key_change')",
            name="action_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="status",
        ),
        CheckConstraint(
            "approver_user_id IS NULL OR approver_user_id <> requester_user_id",
            name="self_approval",
        ),
        Index(
            "uq_workbench_approval_actions_idempotency",
            "workspace_id",
            "idempotency_key_hash",
            unique=True,
            postgresql_where=text("idempotency_key_hash IS NOT NULL"),
            sqlite_where=text("idempotency_key_hash IS NOT NULL"),
        ),
        Index(
            "ix_workbench_approval_actions_task_status",
            "task_id",
            "status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workbench_tasks.id"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["ACTION_TYPES", "STATUSES", "WorkbenchApprovalAction"]
```

- [ ] **Step 4: Implement the repository**

Create `apps/api/src/data_intelligence_hub/repositories/workbench_approvals.py`：

```python
async def get_approval(session, *, approval_id, workspace_id) -> WorkbenchApprovalAction | None
async def get_by_idempotency_key(session, *, workspace_id, idempotency_key_hash) -> WorkbenchApprovalAction | None
async def create_approval(session, *, values: dict[str, object]) -> WorkbenchApprovalAction
async def mark_decided(session, *, approval, approver_user_id, status, decided_at) -> WorkbenchApprovalAction
```

所有查询都带 `workspace_id`，跨工作区返回 `None`，由路由映射 404 `approval_not_found`。

- [ ] **Step 5: Implement the service**

Create `apps/api/src/data_intelligence_hub/services/workbench_approvals.py`。核心规则：

```python
SIX_PLACES = Decimal("0.000001")


def _hash_idempotency_key(key: str) -> str:
    return hashlib.sha256(f"workbench-approval-create.v1:{key}".encode()).hexdigest()


def _validate_payload(action_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if action_type == "budget_overage":
        amount = Decimal(str(payload.get("amount_usd")))
        if amount <= 0:
            raise ApprovalInvalidError("amount_usd")
        return {"amount_usd": str(amount.quantize(SIX_PLACES)),
                "run_id": str(uuid.UUID(str(payload["run_id"])))}
    if action_type == "package_addon":
        return {"package_type": str(payload["package_type"]),
                "markets": [str(m) for m in payload.get("markets", [])]}
    if action_type == "project_key_change":
        return {"project_id": str(uuid.UUID(str(payload["project_id"]))),
                "reason": str(payload.get("reason", ""))[:500]}
    raise ApprovalInvalidError("action_type")


async def create_approval_action(session, *, context, task_id, action_type,
                                 payload, idempotency_key, expires_at):
    task = await _task_or_raise(session, workspace_id=context.workspace.id,
                                task_id=task_id)
    await require_project_access(session, workspace=context.workspace,
                                 user=context.user, project_id=task.project_id,
                                 manage=False)
    if task.status == "cancelled":
        raise ApprovalStateConflictError("task_cancelled")
    digest = _hash_idempotency_key(idempotency_key)
    existing = await get_by_idempotency_key(...)
    if existing is not None:
        return existing
    row = await create_approval(session, values={
        "workspace_id": context.workspace.id,
        "project_id": task.project_id,
        "task_id": task.id,
        "action_type": action_type,
        "requester_user_id": context.user.id,
        "approver_user_id": None,
        "status": "pending",
        "payload_json": _validate_payload(action_type, payload),
        "idempotency_key_hash": digest,
        "created_at": datetime.now(UTC),
        "expires_at": expires_at,
        "decided_at": None,
    })
    return row


async def decide_approval_action(session, *, context, task_id, approval_id,
                                 decision, reason=None):
    if decision not in ("approve", "reject"):
        raise ApprovalInvalidError("decision")
    approval = await get_approval(session, approval_id=approval_id,
                                  workspace_id=context.workspace.id)
    if approval is None or approval.task_id != task_id:
        raise ApprovalNotFoundError(str(approval_id))
    task = await _task_or_raise(...)
    await require_workspace_role(session, workspace_id=context.workspace.id,
                                 user_id=context.user.id,
                                 allowed=("owner", "admin"))
    await require_project_access(session, workspace=context.workspace,
                                 user=context.user, project_id=task.project_id,
                                 manage=True)
    if approval.requester_user_id == context.user.id:
        raise ApprovalSelfApprovalForbiddenError(str(approval_id))
    status = "approved" if decision == "approve" else "rejected"
    if approval.status in ("approved", "rejected"):
        if approval.status == status:
            return approval  # 幂等重放
        raise ApprovalStateConflictError(approval.status)
    if approval.expires_at <= datetime.now(UTC):
        raise ApprovalStateConflictError("expired")
    await mark_decided(session, approval=approval,
                       approver_user_id=context.user.id, status=status,
                       decided_at=datetime.now(UTC))
    if status == "approved" and approval.action_type == "budget_overage":
        run_id = uuid.UUID(approval.payload_json["run_id"])
        amount = Decimal(approval.payload_json["amount_usd"])
        authorization = await get_run_budget_authorization(session, run_id=run_id)
        if authorization is None:
            raise ApprovalStateConflictError("authorization_missing")
        authorization.max_cost_usd = (
            Decimal(str(authorization.max_cost_usd)) + amount
        ).quantize(SIX_PLACES)
    await append_audit_event(
        session,
        workspace_id=context.workspace.id,
        project_id=task.project_id,
        actor_user_id=context.user.id,
        actor_type="user",
        action="budget.limit.changed",
        resource_type="workbench_approval_action",
        resource_id=str(approval.id),
        result="success" if status == "approved" else "denied",
        details={
            "decision": status,
            "action_type": approval.action_type,
            "requester_user_id": str(approval.requester_user_id),
            "reason": reason or "",
        },
    )
    return approval
```

- [ ] **Step 6: Implement the routes**

Create `apps/api/src/data_intelligence_hub/api/routes/workbench_approvals.py`。只注册两个 C1 路径：

```python
@router.post("/workbench/tasks/{task_id}/approvals", status_code=201)
async def create_task_approval(
    task_id: uuid.UUID,
    payload: ApprovalCreateRequest,
    session: SessionDep,
    context=Depends(get_authenticated_context),
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    if not idempotency_key.strip():
        raise HTTPException(status_code=422, detail="invalid_request")
    row = await create_approval_action(...)
    return ApprovalResponse.model_validate(row)


@router.post("/workbench/tasks/{task_id}/approvals/{approval_id}")
async def decide_task_approval(
    task_id: uuid.UUID,
    approval_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    session: SessionDep,
    context=Depends(get_authenticated_context),
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    if not idempotency_key.strip():
        raise HTTPException(status_code=422, detail="invalid_request")
    row = await decide_approval_action(...)
    return ApprovalResponse.model_validate(row)
```

异常映射：`ApprovalNotFoundError` → 404 `approval_not_found`；`ApprovalSelfApprovalForbiddenError` → 403 `approval_self_approval_forbidden`；`ApprovalStateConflictError` → 409 `approval_state_conflict`；`ApprovalInvalidError` → 422 `invalid_request`；`APIError` 原样抛出（项目 ACL 的 403/404）。

- [ ] **Step 7: Run tests and commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_workbench_approvals.py -v
uv run ruff check src/data_intelligence_hub/models/workbench_approval.py \
  src/data_intelligence_hub/repositories/workbench_approvals.py \
  src/data_intelligence_hub/services/workbench_approvals.py \
  src/data_intelligence_hub/schemas/workbench_approval.py \
  src/data_intelligence_hub/api/routes/workbench_approvals.py \
  tests/unit/test_workbench_approvals.py
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/models/workbench_approval.py \
  apps/api/src/data_intelligence_hub/repositories/workbench_approvals.py \
  apps/api/src/data_intelligence_hub/services/workbench_approvals.py \
  apps/api/src/data_intelligence_hub/schemas/workbench_approval.py \
  apps/api/src/data_intelligence_hub/api/routes/workbench_approvals.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/tests/unit/test_workbench_approvals.py
git commit -m "feat(budget): add owner-admin inline approval actions"
```

Expected: 全部通过；`detect-changes` 不含 `partial: true` / `truncated: true`。路径清单必须与 C1 完全一致，多一个路径即失败。

---

### Task 5: 账本八列六枚举与符号约束

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/models/run_ledger.py`
- Modify: `apps/api/src/data_intelligence_hub/services/run_ledger.py`
- Modify: `apps/api/src/data_intelligence_hub/repositories/run_ledger.py`
- Test: `apps/api/tests/unit/test_run_ledger.py`

**Interfaces:**
- Consumes: `RunLedgerEntry`、`ENTRY_KINDS`。
- Produces:
  - `validate_entry_amount(entry_kind: str, amount_usd: Decimal) -> None`
  - `record_entry(...)` 保持旧签名，增加符号校验。
  - 模型 `CheckConstraint("amount_sign_by_kind")`。

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "record_entry" --direction upstream --repo .
node .gitnexus/run.cjs impact "RunLedgerEntry" --direction upstream --repo .
```

Expected: `record_entry` 为 `UNKNOWN`，0 个已解析调用者。文本搜索确认只有 `tests/unit/test_run_ledger.py`。保留签名，只增加校验。`RunLedgerEntry` 为 LOW。

- [ ] **Step 2: Add the failing tests**

在 `apps/api/tests/unit/test_run_ledger.py` 追加：

```python
@pytest.mark.anyio
async def test_settle_must_be_positive() -> None:
    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="sign-settle")
        with pytest.raises(ValueError):
            await record_entry(
                session,
                run_id=run.id,
                entry_kind="settle",
                amount_usd=Decimal("0"),
                balance_after_usd=Decimal("1"),
                idempotency_key="sign-settle-zero",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_release_must_be_negative() -> None:
    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="sign-release")
        with pytest.raises(ValueError):
            await record_entry(
                session,
                run_id=run.id,
                entry_kind="release",
                amount_usd=Decimal("0.1"),
                balance_after_usd=Decimal("1"),
                idempotency_key="sign-release-positive",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_non_cost_entries_must_not_be_negative() -> None:
    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="sign-block")
        for kind in ("estimate", "reserve", "accrued", "block"):
            with pytest.raises(ValueError):
                await record_entry(
                    session,
                    run_id=run.id,
                    entry_kind=kind,
                    amount_usd=Decimal("-0.1"),
                    balance_after_usd=Decimal("1"),
                    idempotency_key=f"sign-{kind}-negative",
                )

    await _with_session(scenario)


def test_ledger_has_exactly_eight_columns_and_six_kinds() -> None:
    from data_intelligence_hub.models.run_ledger import ENTRY_KINDS, RunLedgerEntry

    assert set(RunLedgerEntry.__table__.columns.keys()) == {
        "id",
        "run_id",
        "step_id",
        "entry_kind",
        "amount_usd",
        "balance_after_usd",
        "idempotency_key",
        "created_at",
    }
    assert ENTRY_KINDS == (
        "estimate",
        "reserve",
        "accrued",
        "settle",
        "release",
        "block",
    )
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_ledger.py -v
```

Expected: 符号校验测试失败；八列六枚举测试通过。

- [ ] **Step 4: Implement the sign validation**

先在 `models/run_ledger.py` 加唯一一份校验函数：

```python
def validate_entry_amount(entry_kind: str, amount_usd: Decimal) -> None:
    """按契约校验金额符号。"""
    if entry_kind == "settle" and amount_usd <= 0:
        raise ValueError("settle 金额必须为正数")
    if entry_kind == "release" and amount_usd >= 0:
        raise ValueError("release 金额必须为负数")
    if entry_kind in {"estimate", "reserve", "accrued", "block"} and amount_usd < 0:
        raise ValueError(f"{entry_kind} 金额不得为负数")
```

不要在 `services/run_ledger.py` 或 `repositories/run_ledger.py` 复制这份函数。两边都从模型导入。

在 `services/run_ledger.py` 的 `record_entry` 中，`entry_kind` 校验后调用：

```python
    amount = _as_decimal(amount_usd, "amount_usd")
    validate_entry_amount(entry_kind, amount)
```

并把 `amount_usd=amount` 传给 `add_entry`。

在 `repositories/run_ledger.py` 的 `add_entry` 中调用同一函数：

```python
    amount = _as_decimal(amount_usd, "amount_usd")
    validate_entry_amount(entry_kind, amount)
```

把 `amount_usd=amount` 传给模型。

在 `RunLedgerEntry.__table_args__` 加：

```python
        CheckConstraint(
            "(entry_kind = 'settle' AND amount_usd > 0) OR "
            "(entry_kind = 'release' AND amount_usd < 0) OR "
            "(entry_kind IN ('estimate', 'reserve', 'accrued', 'block') "
            "AND amount_usd >= 0)",
            name="amount_sign_by_kind",
        ),
```

`services/run_ledger.py` 改为：

```python
from data_intelligence_hub.models.run_ledger import (
    ENTRY_KINDS,
    RunLedgerEntry,
    validate_entry_amount,
)
```

`repositories/run_ledger.py` 改为：

```python
from data_intelligence_hub.models.run_ledger import (
    ENTRY_KINDS,
    RunLedgerEntry,
    validate_entry_amount,
)
```

并在 `add_entry` 中：

```python
    amount = _as_decimal(amount_usd, "amount_usd")
    validate_entry_amount(entry_kind, amount)
```

把 `amount_usd=amount` 传给模型。

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_ledger.py -v
uv run ruff check src/data_intelligence_hub/models/run_ledger.py \
  src/data_intelligence_hub/services/run_ledger.py \
  src/data_intelligence_hub/repositories/run_ledger.py \
  tests/unit/test_run_ledger.py
```

Expected: 全部通过。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/models/run_ledger.py \
  apps/api/src/data_intelligence_hub/services/run_ledger.py \
  apps/api/src/data_intelligence_hub/repositories/run_ledger.py \
  apps/api/tests/unit/test_run_ledger.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(budget): enforce ledger entry kinds and amount signs"
```

---

### Task 6: 预算服务与并发原子性

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/budget_service.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Test: `apps/api/tests/unit/test_budget_service.py`

**Interfaces:**
- Consumes:
  - `pricing.quote`、`pricing.quote_usage`
  - `repositories/quota_accounts.py`
  - `repositories/run_ledger.py`
  - `repositories/authorizations.get_run_budget_authorization`、`has_blocked_gate`
  - `repositories/runs`、`models/Run`、`models/RunStep`、`models/TaskRun`
- Produces:
  - `BudgetEstimate`
  - `BudgetReservation`
  - `BudgetSettlement`
  - `estimate_run_budget(...)`
  - `reserve_run_budget(...)`
  - `settle_run_cost(...)`
  - `release_settlement(...)`
  - `cancel_reservation(...)`
  - `mark_result_unknown(...)`
  - `block_run_budget(...)`
  - `run_remaining_budget(...)`

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "remaining_budget" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_usage_summary" --direction upstream --repo .
```

Expected:

```text
remaining_budget: UNKNOWN, 0 callers; text search finds only tests/unit/test_run_ledger.py
get_usage_summary: LOW, 1 direct caller
```

保留 `remaining_budget` 的现有签名。预算服务新增函数，不替换它。

- [ ] **Step 2: Add the failing budget tests**

Create `apps/api/tests/unit/test_budget_service.py`:

```python
"""预算服务的估算、预留、结算、释放、阻断与并发。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.audit_event import AuditEvent
from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.quota_account import QuotaAccount
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.run_ledger import RunLedgerEntry
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.repositories.quota_accounts import create_quota_account
from data_intelligence_hub.services.budget_service import (
    BudgetApprovalRequiredError,
    BudgetExceededError,
    DuplicateSettlementError,
    ReservationAlreadySettledError,
    block_run_budget,
    cancel_reservation,
    estimate_run_budget,
    mark_result_unknown,
    release_settlement,
    reserve_run_budget,
    run_remaining_budget,
    set_project_quota_limit,
    settle_run_cost,
)
from data_intelligence_hub.services.pricing import ToolNotPricedError
from tests.unit.budget_test_support import (
    BudgetSeed,
    seed_budget_scope,
    today,
    with_sqlite_session,
)


async def _seed_with_quota(
    session: AsyncSession,
    *,
    slug: str,
    max_cost: str = "2.000000",
    quota: str = "10.000000",
    with_task_run: bool = False,
) -> tuple[BudgetSeed, QuotaAccount]:
    seed = await seed_budget_scope(
        session,
        slug=slug,
        max_cost_usd=Decimal(max_cost),
        with_task_run=with_task_run,
    )
    account = await create_quota_account(
        session,
        workspace_id=seed.workspace.id,
        project_id=seed.project.id,
        period_start=today(),
        daily_limit_usd=Decimal(quota),
    )
    return seed, account


@pytest.mark.anyio
async def test_estimate_writes_estimate_without_changing_cost() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="estimate")
        estimate = await estimate_run_budget(
            session,
            run_id=seed.run.id,
            endpoint_type="exa_search_lite",
            records_count=1,
        )
        observed["amount"] = estimate.quote.total_cost_usd
        observed["remaining"] = await run_remaining_budget(session, run_id=seed.run.id)

    await with_sqlite_session(scenario)

    assert observed["amount"] == Decimal("0.004000")
    assert observed["remaining"] == Decimal("2.000000")


@pytest.mark.anyio
async def test_reserve_is_idempotent() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(session, slug="reserve-idem")
        first = await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        second = await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        observed["first"] = first.ledger_entry_id
        observed["second"] = second.ledger_entry_id
        refreshed = await session.get(QuotaAccount, account.id)
        assert refreshed is not None
        observed["reserved"] = refreshed.reserved_usd

    await with_sqlite_session(scenario)

    assert observed["first"] == observed["second"]
    assert observed["reserved"] == Decimal("0.500000")


@pytest.mark.anyio
async def test_reserve_rejects_amount_above_run_authorization() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="reserve-auth", max_cost="0.500000")
        with pytest.raises(BudgetApprovalRequiredError):
            await reserve_run_budget(
                session,
                run_id=seed.run.id,
                amount_usd=Decimal("0.600000"),
                enforce=True,
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_reserve_rejects_amount_above_project_quota() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="reserve-quota", quota="0.500000")
        with pytest.raises(BudgetExceededError):
            await reserve_run_budget(
                session,
                run_id=seed.run.id,
                amount_usd=Decimal("0.600000"),
                enforce=True,
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_unknown_price_blocks_and_raises() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="unpriced")
        with pytest.raises(ToolNotPricedError):
            await estimate_run_budget(
                session,
                run_id=seed.run.id,
                endpoint_type="apify_1688_advanced",
                records_count=1,
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_settle_writes_remaining_budget_to_task_runs() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(
            session,
            slug="settle-task-run",
            max_cost="2.000000",
            with_task_run=True,
        )
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        seed.task_run.total_cost_usd = Decimal("0.300000")
        await session.flush()
        settlement = await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
            task_run_id=seed.task_run.id,
            step_id=seed.step.id,
        )
        refreshed = await session.get(TaskRun, seed.task_run.id)
        assert refreshed is not None
        observed["remaining"] = refreshed.remaining_budget
        observed["total"] = refreshed.total_cost_usd
        observed["settlement_remaining"] = settlement.remaining_budget

    await with_sqlite_session(scenario)

    assert observed["remaining"] == Decimal("1.700000")
    assert observed["total"] == Decimal("0.300000")
    assert observed["settlement_remaining"] == Decimal("1.700000")


@pytest.mark.anyio
async def test_quota_ledger_and_run_total_reconcile() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(
            session,
            slug="reconcile",
            max_cost="2.000000",
            with_task_run=True,
        )
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
            task_run_id=seed.task_run.id,
            step_id=seed.step.id,
        )
        ledger_total = await session.scalar(
            select(func.sum(RunLedgerEntry.amount_usd)).where(
                RunLedgerEntry.run_id == seed.run.id,
                RunLedgerEntry.entry_kind.in_(("settle", "release")),
            )
        )
        refreshed = await session.get(QuotaAccount, account.id)
        run = await session.get(Run, seed.run.id)
        observed["ledger"] = ledger_total or Decimal("0")
        observed["used"] = refreshed.used_usd
        observed["run_total"] = run.total_cost_usd
        observed["reserved"] = refreshed.reserved_usd

    await with_sqlite_session(scenario)

    assert observed["ledger"] == Decimal("0.300000")
    assert observed["used"] == Decimal("0.300000")
    assert observed["run_total"] == Decimal("0.300000")
    assert observed["reserved"] == Decimal("0.000000")


@pytest.mark.anyio
async def test_duplicate_settle_is_idempotent() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(session, slug="settle-idem")
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        first = await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
            idempotency_key="settle-once",
        )
        second = await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
            idempotency_key="settle-once",
        )
        refreshed = await session.get(QuotaAccount, account.id)
        assert refreshed is not None
        observed["first"] = first.ledger_entry_id
        observed["second"] = second.ledger_entry_id
        observed["used"] = refreshed.used_usd
        observed["remaining"] = first.remaining_budget

    await with_sqlite_session(scenario)

    assert observed["first"] == observed["second"]
    assert observed["used"] == Decimal("0.300000")
    assert observed["remaining"] == Decimal("1.700000")


@pytest.mark.anyio
async def test_duplicate_settle_with_different_amount_raises() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="settle-conflict")
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
            idempotency_key="settle-conflict",
        )
        with pytest.raises(DuplicateSettlementError):
            await settle_run_cost(
                session,
                run_id=seed.run.id,
                amount_usd=Decimal("0.310000"),
                idempotency_key="settle-conflict",
            )

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_overage_keeps_negative_remaining() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(
            session,
            slug="overage",
            max_cost="0.500000",
            quota="10.000000",
        )
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        settlement = await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.800000"),
        )
        observed["remaining"] = settlement.remaining_budget
        observed["overage"] = settlement.overage_usd

    await with_sqlite_session(scenario)

    assert observed["remaining"] == Decimal("-0.300000")
    assert observed["overage"] == Decimal("0.300000")


@pytest.mark.anyio
async def test_unknown_result_keeps_reservation_and_writes_accrued() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(session, slug="unknown-result")
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        await mark_result_unknown(session, run_id=seed.run.id, reason_code="upstream_timeout")
        refreshed = await session.get(QuotaAccount, account.id)
        assert refreshed is not None
        observed["reserved"] = refreshed.reserved_usd
        observed["sum_cost"] = await run_remaining_budget(session, run_id=seed.run.id)

    await with_sqlite_session(scenario)

    assert observed["reserved"] == Decimal("0.500000")
    assert observed["sum_cost"] == Decimal("2.000000")


@pytest.mark.anyio
async def test_cancel_reservation_frees_quota_without_release_row() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(session, slug="cancel")
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        released = await cancel_reservation(session, run_id=seed.run.id)
        refreshed = await session.get(QuotaAccount, account.id)
        assert refreshed is not None
        observed["released"] = released
        observed["reserved"] = refreshed.reserved_usd
        observed["remaining"] = await run_remaining_budget(session, run_id=seed.run.id)

    await with_sqlite_session(scenario)

    assert observed["released"] == Decimal("0.500000")
    assert observed["reserved"] == Decimal("0.000000")
    assert observed["remaining"] == Decimal("2.000000")


@pytest.mark.anyio
async def test_cancel_after_settle_is_rejected() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="cancel-settled")
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
        )
        with pytest.raises(ReservationAlreadySettledError):
            await cancel_reservation(session, run_id=seed.run.id)

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_release_settlement_writes_negative_and_reduces_used() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(session, slug="release")
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        settlement = await release_settlement(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("-0.200000"),
            idempotency_key="release-1",
        )
        refreshed = await session.get(QuotaAccount, account.id)
        assert refreshed is not None
        observed["remaining"] = settlement.remaining_budget
        observed["used"] = refreshed.used_usd

    await with_sqlite_session(scenario)

    assert observed["remaining"] == Decimal("1.700000")
    assert observed["used"] == Decimal("0.300000")


@pytest.mark.anyio
async def test_block_writes_zero_amount_without_changing_quota() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, account = await _seed_with_quota(session, slug="block")
        entry = await block_run_budget(
            session,
            run_id=seed.run.id,
            reason_code="approval_required",
        )
        refreshed = await session.get(QuotaAccount, account.id)
        assert refreshed is not None
        observed["amount"] = entry.amount_usd
        observed["reserved"] = refreshed.reserved_usd

    await with_sqlite_session(scenario)

    assert observed["amount"] == Decimal("0.000000")
    assert observed["reserved"] == Decimal("0.000000")


@pytest.mark.anyio
async def test_set_project_quota_limit_writes_c2_audit() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="quota-audit")
        account = await set_project_quota_limit(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            daily_limit_usd=Decimal("10.000000"),
            actor_user_id=seed.user.id,
        )
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.workspace_id == seed.workspace.id,
                AuditEvent.action == "budget.limit.changed",
            )
        )
        observed["daily"] = account.daily_limit_usd
        observed["action"] = event.action
        observed["result"] = event.result

    await with_sqlite_session(scenario)

    assert observed["daily"] == Decimal("10.000000")
    assert observed["action"] == "budget.limit.changed"
    assert observed["result"] == "success"


@pytest.mark.anyio
async def test_concurrent_reservations_never_exceed_project_quota(tmp_path) -> None:
    database = tmp_path / "budget-concurrency.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        first = await seed_budget_scope(
            session,
            slug="concurrent-a",
            max_cost_usd=Decimal("10.000000"),
        )
        second_run = Run(
            workspace_id=first.workspace.id,
            project_id=first.project.id,
            status="queued",
            execution_mode="live",
            trigger="manual",
            records_count=0,
        )
        session.add(second_run)
        await session.flush()
        session.add(
            Authorization(
                workspace_id=first.workspace.id,
                project_id=first.project.id,
                run_id=second_run.id,
                gate_id="G-Cost",
                gate_status="pass",
                scope={"origin": "test", "run_id": str(second_run.id)},
                max_cost_usd=Decimal("10.000000"),
                approver=first.user.id,
                granted_at=datetime.now(UTC),
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await create_quota_account(
            session,
            workspace_id=first.workspace.id,
            project_id=first.project.id,
            period_start=today(),
            daily_limit_usd=Decimal("1.000000"),
        )
        await session.commit()
        first_run_id = first.run.id
        second_run_id = second_run.id

    async def attempt(run_id: uuid.UUID) -> bool:
        async with factory() as session:
            async with session.begin():
                try:
                    await reserve_run_budget(
                        session,
                        run_id=run_id,
                        amount_usd=Decimal("0.600000"),
                        enforce=True,
                    )
                except (BudgetExceededError, BudgetApprovalRequiredError):
                    return False
                return True

    results = await asyncio.gather(attempt(first_run_id), attempt(second_run_id))
    await engine.dispose()

    assert results.count(True) == 1


@pytest.mark.anyio
async def test_run_remaining_budget_uses_only_settle_and_release() -> None:
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        seed, _ = await _seed_with_quota(session, slug="remaining")
        await estimate_run_budget(
            session,
            run_id=seed.run.id,
            endpoint_type="exa_search_lite",
            records_count=1,
        )
        await reserve_run_budget(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.500000"),
        )
        observed["before"] = await run_remaining_budget(session, run_id=seed.run.id)
        await settle_run_cost(
            session,
            run_id=seed.run.id,
            amount_usd=Decimal("0.300000"),
        )
        observed["after"] = await run_remaining_budget(session, run_id=seed.run.id)

    await with_sqlite_session(scenario)

    assert observed["before"] == Decimal("2.000000")
    assert observed["after"] == Decimal("1.700000")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_budget_service.py -v
```

Expected: `ModuleNotFoundError: data_intelligence_hub.services.budget_service`。

- [ ] **Step 4: Add the budget exceptions**

在 `services/exceptions.py` 中加：

```python
class BudgetApprovalRequiredError(ServiceError):
    message = "approval_required"

    def __init__(self, scope: str) -> None:
        super().__init__(f"{self.message}: {scope}")
        self.scope = scope


class BudgetExceededError(ServiceError):
    message = "quota_exceeded"

    def __init__(self, scope: str) -> None:
        super().__init__(f"{self.message}: {scope}")
        self.scope = scope


class DuplicateSettlementError(ServiceError):
    message = "duplicate_settlement"

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(f"{self.message}: {idempotency_key}")
        self.idempotency_key = idempotency_key


class ReservationAlreadySettledError(ServiceError):
    message = "reservation_already_settled"


class ReservationNotFoundError(ServiceError):
    message = "reservation_not_found"
```

- [ ] **Step 5: Implement `budget_service.py`**

Create `apps/api/src/data_intelligence_hub/services/budget_service.py`。核心代码如下。执行者必须完整落盘，不得省略分支。

```python
"""预算估算、预留、结算、释放与阻断。

规则：
- 单 run 上限来自 ``authorizations.max_cost_usd``。
- 项目日额度来自 ``quota_accounts``。
- 账本只追加。``settle`` 正数，``release`` 负数。
- ``reserve``、``estimate``、``accrued``、``block`` 不计入实际成本。
- 一个 run 最多一条 ``reserve``。幂等键固定为 ``run:{id}:reserve``。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_ledger import RunLedgerEntry, validate_entry_amount
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.repositories.authorizations import (
    get_run_budget_authorization,
    has_blocked_gate,
)
from data_intelligence_hub.repositories.quota_accounts import (
    QuotaExceededError,
    get_or_create_quota_account,
    get_quota_account,
    release_quota,
    reserve_quota,
    settle_quota,
)
from data_intelligence_hub.repositories.run_ledger import (
    add_entry,
    get_by_idempotency_key,
)
from data_intelligence_hub.services.audit_log import append_audit_event
from data_intelligence_hub.services.exceptions import (
    BudgetApprovalRequiredError,
    BudgetExceededError,
    DuplicateSettlementError,
    ReservationAlreadySettledError,
    ReservationNotFoundError,
)
from data_intelligence_hub.services.pricing import (
    PriceQuote,
    ToolNotPricedError,
    quote,
)
from data_intelligence_hub.services.run_ledger import sum_cost

SIX_PLACES = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class BudgetEstimate:
    run_id: uuid.UUID
    quote: PriceQuote
    remaining_budget: Decimal
    ledger_entry_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class BudgetReservation:
    run_id: uuid.UUID
    authorization_id: uuid.UUID
    quota_account_id: uuid.UUID
    amount_usd: Decimal
    ledger_entry_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class BudgetSettlement:
    run_id: uuid.UUID
    amount_usd: Decimal
    cumulative_cost_usd: Decimal
    remaining_budget: Decimal
    overage_usd: Decimal
    task_run_id: uuid.UUID | None
    ledger_entry_id: uuid.UUID | None


def _money(value: Decimal | int | str, field: str) -> Decimal:
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field} 必须用 Decimal，不得用 float")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        result = Decimal(value)
    else:
        raise TypeError(f"{field} 必须是 Decimal、int 或 str")
    if not result.is_finite():
        raise ValueError(f"{field} 必须是有限数")
    return result.quantize(SIX_PLACES)


def _day_start(at: datetime) -> object:
    return at.astimezone(UTC).date()


async def _audit_budget_event(
    session: AsyncSession,
    *,
    run: Run,
    action: str,
    result: str = "success",
    details: Mapping[str, object] | None = None,
    at: datetime | None = None,
) -> None:
    """只写 C2 唯一审计表；动作名必须已由 C1 登记。"""
    await append_audit_event(
        session,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        actor_type="system",
        action=action,
        resource_type="run_budget",
        resource_id=str(run.id),
        result=result,
        details=dict(details or {}),
        occurred_at=at,
    )


async def _run_or_raise(session: AsyncSession, run_id: uuid.UUID) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError(f"run 不存在：{run_id}")
    return run


async def _authorization_or_raise(
    session: AsyncSession,
    *,
    run: Run,
) -> Authorization:
    authorization = await get_run_budget_authorization(
        session,
        run_id=run.id,
        workspace_id=run.workspace_id,
    )
    if authorization is None:
        raise BudgetApprovalRequiredError("authorization_missing")
    if authorization.revoked_at is not None:
        raise BudgetApprovalRequiredError("authorization_revoked")
    if authorization.gate_status != "pass":
        raise BudgetApprovalRequiredError("authorization_not_passed")
    if authorization.expires_at <= datetime.now(UTC):
        raise BudgetApprovalRequiredError("authorization_expired")
    return authorization


async def _quota_account_or_raise(
    session: AsyncSession,
    *,
    run: Run,
    at: datetime,
):
    # 懒创建 0 限额账户；enforce 前由 owner 设置限额。
    return await get_or_create_quota_account(
        session,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        period_start=_day_start(at),
    )


async def run_remaining_budget(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    authorization: Authorization | None = None,
) -> Decimal:
    run = await _run_or_raise(session, run_id)
    auth = authorization or await _authorization_or_raise(session, run=run)
    return auth.max_cost_usd - await sum_cost(session, run_id=run_id)


async def block_run_budget(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    reason_code: str,
    amount_usd: Decimal | int | str = Decimal("0"),
    at: datetime | None = None,
) -> RunLedgerEntry:
    run = await _run_or_raise(session, run_id)
    now = at or datetime.now(UTC)
    amount = _money(amount_usd, "amount_usd")
    validate_entry_amount("block", amount)
    key = f"run:{run.id}:block:{reason_code}"
    existing = await get_by_idempotency_key(session, idempotency_key=key)
    if existing is not None:
        return existing
    try:
        remaining = await run_remaining_budget(session, run_id=run.id)
    except BudgetApprovalRequiredError:
        remaining = Decimal("0.000000")
    entry = await add_entry(
        session,
        run_id=run.id,
        entry_kind="block",
        amount_usd=amount,
        balance_after_usd=remaining,
        idempotency_key=key,
    )
    await _audit_budget_event(
        session,
        run=run,
        action="budget.blocked",
        details={"reason_code": reason_code, "amount_usd": str(amount)},
        at=now,
    )
    return entry


async def estimate_run_budget(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    endpoint_type: str,
    records_count: int,
    at: datetime | None = None,
) -> BudgetEstimate:
    run = await _run_or_raise(session, run_id)
    try:
        price = quote(endpoint_type, records_count=records_count)
    except ToolNotPricedError:
        await block_run_budget(
            session,
            run_id=run.id,
            reason_code="tool_not_priced",
            at=at,
        )
        raise
    remaining = await run_remaining_budget(session, run_id=run.id)
    key = f"run:{run.id}:estimate:{endpoint_type}:{price.quantity}"
    existing = await get_by_idempotency_key(session, idempotency_key=key)
    if existing is None:
        existing = await add_entry(
            session,
            run_id=run.id,
            entry_kind="estimate",
            amount_usd=price.total_cost_usd,
            balance_after_usd=remaining,
            idempotency_key=key,
        )
    return BudgetEstimate(
        run_id=run.id,
        quote=price,
        remaining_budget=remaining,
        ledger_entry_id=existing.id,
    )


async def reserve_run_budget(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    amount_usd: Decimal | int | str | None = None,
    enforce: bool | None = None,
    at: datetime | None = None,
) -> BudgetReservation:
    run = await _run_or_raise(session, run_id)
    enforce = (
        get_settings().budget_enforcement_enabled
        if enforce is None
        else enforce
    )
    now = at or datetime.now(UTC)
    authorization = await _authorization_or_raise(session, run=run)
    # 一次 run 预留整条授权的上限；调用方可显式传更小金额。
    amount = _money(
        authorization.max_cost_usd if amount_usd is None else amount_usd,
        "amount_usd",
    )
    if enforce and amount <= 0:
        # enforce 下没有正数授权不得执行；shadow 只记录 block。
        marker = await block_run_budget(
            session,
            run_id=run.id,
            reason_code="run_authorization_missing_or_zero",
            at=now,
        )
        raise BudgetApprovalRequiredError("run_authorization_missing_or_zero")
    validate_entry_amount("reserve", amount)
    key = f"run:{run.id}:reserve"
    existing = await get_by_idempotency_key(session, idempotency_key=key)
    if existing is not None:
        if existing.amount_usd != amount:
            raise DuplicateSettlementError(key)
        authorization = await _authorization_or_raise(session, run=run)
        account = await _quota_account_or_raise(session, run=run, at=now)
        return BudgetReservation(
            run_id=run.id,
            authorization_id=authorization.id,
            quota_account_id=account.id,
            amount_usd=amount,
            ledger_entry_id=existing.id,
        )

    remaining = authorization.max_cost_usd - await sum_cost(session, run_id=run.id)
    if amount > remaining:
        marker = await block_run_budget(
            session,
            run_id=run.id,
            reason_code="run_authorization_exceeded",
            at=now,
        )
        if enforce:
            raise BudgetApprovalRequiredError("run_authorization_exceeded")
        return BudgetReservation(
            run_id=run.id,
            authorization_id=authorization.id,
            quota_account_id=None,
            amount_usd=Decimal("0.000000"),
            ledger_entry_id=marker.id,
        )

    account = await _quota_account_or_raise(session, run=run, at=now)
    try:
        await reserve_quota(
            session,
            account_id=account.id,
            amount_usd=amount,
            at=now,
        )
    except QuotaExceededError as exc:
        marker = await block_run_budget(
            session,
            run_id=run.id,
            reason_code="project_daily_quota_exceeded",
            at=now,
        )
        if enforce:
            raise BudgetExceededError("project_daily_quota_exceeded") from exc
        return BudgetReservation(
            run_id=run.id,
            authorization_id=authorization.id,
            quota_account_id=account.id,
            amount_usd=Decimal("0.000000"),
            ledger_entry_id=marker.id,
        )

    entry = await add_entry(
        session,
        run_id=run.id,
        entry_kind="reserve",
        amount_usd=amount,
        balance_after_usd=remaining,
        idempotency_key=key,
    )
    return BudgetReservation(
        run_id=run.id,
        authorization_id=authorization.id,
        quota_account_id=account.id,
        amount_usd=amount,
        ledger_entry_id=entry.id,
    )


async def _task_run_id_for_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    task_run_id: uuid.UUID | None,
    step_id: uuid.UUID | None,
) -> uuid.UUID | None:
    if task_run_id is not None:
        return task_run_id
    if step_id is not None:
        value = await session.scalar(
            select(RunStep.task_run_id).where(RunStep.id == step_id)
        )
        if value is not None:
            return value
    return await session.scalar(
        select(RunStep.task_run_id)
        .where(RunStep.run_id == run_id, RunStep.task_run_id.is_not(None))
        .order_by(RunStep.step_index.desc())
        .limit(1)
    )


async def _write_all_task_run_remaining(
    session: AsyncSession,
    *,
    run: Run,
    remaining: Decimal,
    at: datetime,
) -> None:
    # remaining_budget 是 run 级投影；写到该 run 的全部 attempt 的 task_runs。
    await session.execute(
        update(TaskRun)
        .where(
            TaskRun.run_id == run.id,
            TaskRun.workspace_id == run.workspace_id,
        )
        .values(remaining_budget=remaining, updated_at=at)
    )
    await session.flush()


async def _write_task_run_budget(
    session: AsyncSession,
    *,
    run: Run,
    task_run_id: uuid.UUID | None,
    remaining: Decimal,
    task_run_total: Decimal | None,
    price: PriceQuote | None,
    at: datetime,
) -> None:
    if task_run_id is None:
        return
    values: dict[str, object] = {
        "remaining_budget": remaining,
        "updated_at": at,
    }
    if task_run_total is not None:
        values["total_cost_usd"] = task_run_total
    if price is not None:
        values.update(
            {
                "unit": price.unit,
                "quantity": price.quantity,
                "unit_price": price.unit_price,
            }
        )
    await session.execute(
        update(TaskRun)
        .where(
            TaskRun.id == task_run_id,
            TaskRun.workspace_id == run.workspace_id,
        )
        .values(**values)
    )
    await session.flush()


async def _run_attempt_cost(session: AsyncSession, *, run_id: uuid.UUID) -> Decimal:
    # 汇总该 run 全部 attempt 的 task_runs；失败的 attempt 也计入。
    total = await session.scalar(
        select(func.sum(TaskRun.total_cost_usd)).where(TaskRun.run_id == run_id)
    )
    return _money(total or Decimal("0.000000"), "amount_usd")


async def settle_run_cost(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    amount_usd: Decimal | int | str | None = None,
    idempotency_key: str | None = None,
    task_run_id: uuid.UUID | None = None,
    step_id: uuid.UUID | None = None,
    price: PriceQuote | None = None,
    at: datetime | None = None,
) -> BudgetSettlement:
    run = await _run_or_raise(session, run_id)
    now = at or datetime.now(UTC)
    # 不传金额时由 C5 自己汇总所有 attempt，C6 不得只传最终 step。
    amount = _money(
        (
            await _run_attempt_cost(session, run_id=run.id)
            if amount_usd is None
            else amount_usd
        ),
        "amount_usd",
    )
    if amount == 0:
        authorization = await _authorization_or_raise(session, run=run)
        cumulative = await sum_cost(session, run_id=run.id)
        remaining = authorization.max_cost_usd - cumulative
        resolved = await _task_run_id_for_run(
            session,
            run_id=run.id,
            task_run_id=task_run_id,
            step_id=step_id,
        )
        reserve = await get_by_idempotency_key(
            session,
            idempotency_key=f"run:{run.id}:reserve",
        )
        if reserve is not None:
            account = await _quota_account_or_raise(session, run=run, at=now)
            await settle_quota(
                session,
                account_id=account.id,
                reserved_amount_usd=reserve.amount_usd,
                actual_amount_usd=Decimal("0.000000"),
                at=now,
            )
        await _write_all_task_run_remaining(
            session,
            run=run,
            remaining=remaining,
            at=now,
        )
        return BudgetSettlement(
            run_id=run.id,
            amount_usd=Decimal("0.000000"),
            cumulative_cost_usd=cumulative,
            remaining_budget=remaining,
            overage_usd=max(-remaining, Decimal("0.000000")),
            task_run_id=resolved,
            ledger_entry_id=None,
        )
    validate_entry_amount("settle", amount)
    key = idempotency_key or f"run:{run.id}:settle"

    existing = await get_by_idempotency_key(session, idempotency_key=key)
    if existing is not None:
        if existing.entry_kind != "settle" or existing.amount_usd != amount:
            raise DuplicateSettlementError(key)
        authorization = await _authorization_or_raise(session, run=run)
        cumulative = await sum_cost(session, run_id=run.id)
        remaining = authorization.max_cost_usd - cumulative
        resolved_task_run_id = await _task_run_id_for_run(
            session,
            run_id=run.id,
            task_run_id=task_run_id,
            step_id=step_id,
        )
        return BudgetSettlement(
            run_id=run.id,
            amount_usd=amount,
            cumulative_cost_usd=cumulative,
            remaining_budget=remaining,
            overage_usd=max(-remaining, Decimal("0.000000")),
            task_run_id=resolved_task_run_id,
            ledger_entry_id=existing.id,
        )

    authorization = await _authorization_or_raise(session, run=run)
    current = await sum_cost(session, run_id=run.id)
    cumulative = current + amount
    remaining = authorization.max_cost_usd - cumulative

    reserve = await get_by_idempotency_key(
        session,
        idempotency_key=f"run:{run.id}:reserve",
    )
    reserved_amount = reserve.amount_usd if reserve is not None else Decimal("0.000000")
    account = await _quota_account_or_raise(session, run=run, at=now)
    await settle_quota(
        session,
        account_id=account.id,
        reserved_amount_usd=reserved_amount,
        actual_amount_usd=amount,
        at=now,
    )

    entry = await add_entry(
        session,
        run_id=run.id,
        step_id=step_id,
        entry_kind="settle",
        amount_usd=amount,
        balance_after_usd=remaining,
        idempotency_key=key,
    )
    await session.execute(
        update(Run)
        .where(Run.id == run.id)
        .values(total_cost_usd=cumulative)
    )
    # 同一 session 的 ORM 对象同步，避免调用方随后 save 覆盖。
    run.total_cost_usd = cumulative
    resolved_task_run_id = await _task_run_id_for_run(
        session,
        run_id=run.id,
        task_run_id=task_run_id,
        step_id=step_id,
    )
    await _write_all_task_run_remaining(
        session,
        run=run,
        remaining=remaining,
        at=now,
    )
    return BudgetSettlement(
        run_id=run.id,
        amount_usd=amount,
        cumulative_cost_usd=cumulative,
        remaining_budget=remaining,
        overage_usd=max(-remaining, Decimal("0.000000")),
        task_run_id=resolved_task_run_id,
        ledger_entry_id=entry.id,
    )


async def release_settlement(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    amount_usd: Decimal | int | str,
    idempotency_key: str,
    task_run_id: uuid.UUID | None = None,
    step_id: uuid.UUID | None = None,
    at: datetime | None = None,
) -> BudgetSettlement:
    run = await _run_or_raise(session, run_id)
    now = at or datetime.now(UTC)
    amount = _money(amount_usd, "amount_usd")
    validate_entry_amount("release", amount)

    existing = await get_by_idempotency_key(session, idempotency_key=idempotency_key)
    if existing is not None:
        if existing.entry_kind != "release" or existing.amount_usd != amount:
            raise DuplicateSettlementError(idempotency_key)
        authorization = await _authorization_or_raise(session, run=run)
        cumulative = await sum_cost(session, run_id=run.id)
        remaining = authorization.max_cost_usd - cumulative
        return BudgetSettlement(
            run_id=run.id,
            amount_usd=amount,
            cumulative_cost_usd=cumulative,
            remaining_budget=remaining,
            overage_usd=max(-remaining, Decimal("0.000000")),
            task_run_id=task_run_id,
            ledger_entry_id=existing.id,
        )

    authorization = await _authorization_or_raise(session, run=run)
    current = await sum_cost(session, run_id=run.id)
    cumulative = current + amount
    if cumulative < 0:
        raise ValueError("release 不得让实际成本变为负数")
    remaining = authorization.max_cost_usd - cumulative
    account = await _quota_account_or_raise(session, run=run, at=now)
    await settle_quota(
        session,
        account_id=account.id,
        reserved_amount_usd=Decimal("0.000000"),
        actual_amount_usd=amount,
        at=now,
    )
    entry = await add_entry(
        session,
        run_id=run.id,
        step_id=step_id,
        entry_kind="release",
        amount_usd=amount,
        balance_after_usd=remaining,
        idempotency_key=idempotency_key,
    )
    await _audit_budget_event(
        session,
        run=run,
        action="budget.released",
        details={
            "amount_usd": str(amount),
            "idempotency_key": idempotency_key,
            "source": "release_settlement",
        },
        at=now,
    )
    await session.execute(
        update(Run).where(Run.id == run.id).values(total_cost_usd=cumulative)
    )
    run.total_cost_usd = cumulative
    resolved_task_run_id = await _task_run_id_for_run(
        session,
        run_id=run.id,
        task_run_id=task_run_id,
        step_id=step_id,
    )
    task_run_total: Decimal | None = None
    if resolved_task_run_id is not None:
        current_task_total = await session.scalar(
            select(TaskRun.total_cost_usd).where(
                TaskRun.id == resolved_task_run_id,
                TaskRun.workspace_id == run.workspace_id,
            )
        )
        task_run_total = max(
            (current_task_total or Decimal("0.000000")) + amount,
            Decimal("0.000000"),
        )
    await _write_task_run_budget(
        session,
        run=run,
        task_run_id=resolved_task_run_id,
        remaining=remaining,
        task_run_total=task_run_total,
        price=None,
        at=now,
    )
    return BudgetSettlement(
        run_id=run.id,
        amount_usd=amount,
        cumulative_cost_usd=cumulative,
        remaining_budget=remaining,
        overage_usd=max(-remaining, Decimal("0.000000")),
        task_run_id=resolved_task_run_id,
        ledger_entry_id=entry.id,
    )


async def cancel_reservation(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    at: datetime | None = None,
) -> Decimal:
    run = await _run_or_raise(session, run_id)
    now = at or datetime.now(UTC)
    reserve = await get_by_idempotency_key(
        session,
        idempotency_key=f"run:{run.id}:reserve",
    )
    if reserve is None:
        # 没有预留时取消是幂等 no-op。
        return Decimal("0.000000")
    settled = await session.scalar(
        select(RunLedgerEntry.id)
        .where(
            RunLedgerEntry.run_id == run.id,
            RunLedgerEntry.entry_kind.in_(("settle", "accrued")),
        )
        .limit(1)
    )
    if settled is not None:
        raise ReservationAlreadySettledError(str(run.id))
    marker_key = f"run:{run.id}:block:reservation_cancelled"
    marker = await get_by_idempotency_key(session, idempotency_key=marker_key)
    if marker is not None:
        return Decimal("0.000000")
    account = await _quota_account_or_raise(session, run=run, at=now)
    await release_quota(
        session,
        account_id=account.id,
        reserved_amount_usd=reserve.amount_usd,
        at=now,
    )
    await block_run_budget(
        session,
        run_id=run.id,
        reason_code="reservation_cancelled",
        at=now,
    )
    await _audit_budget_event(
        session,
        run=run,
        action="budget.released",
        details={
            "amount_usd": str(reserve.amount_usd),
            "source": "cancel_reservation",
        },
        at=now,
    )
    return reserve.amount_usd


async def mark_result_unknown(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    reason_code: str = "upstream_unknown",
    at: datetime | None = None,
) -> RunLedgerEntry:
    run = await _run_or_raise(session, run_id)
    now = at or datetime.now(UTC)
    reserve = await get_by_idempotency_key(
        session,
        idempotency_key=f"run:{run.id}:reserve",
    )
    if reserve is None:
        # 没有预留时只写审计 block，不阻塞。
        return await block_run_budget(
            session,
            run_id=run.id,
            reason_code=f"unknown_without_reserve:{reason_code}",
            at=now,
        )
    key = f"run:{run.id}:accrued:unknown:{reason_code}"
    existing = await get_by_idempotency_key(session, idempotency_key=key)
    if existing is not None:
        return existing
    # 未知结果：释放 quota 预留，不让 reserved_usd 永久占用。
    account = await _quota_account_or_raise(session, run=run, at=now)
    await settle_quota(
        session,
        account_id=account.id,
        reserved_amount_usd=reserve.amount_usd,
        actual_amount_usd=Decimal("0.000000"),
        at=now,
    )
    await block_run_budget(
        session,
        run_id=run.id,
        reason_code=f"unknown:{reason_code}",
        at=now,
    )
    remaining = await run_remaining_budget(session, run_id=run.id)
    # accrued 只做审计，不计入 sum_cost。
    return await add_entry(
        session,
        run_id=run.id,
        entry_kind="accrued",
        amount_usd=reserve.amount_usd,
        balance_after_usd=remaining,
        idempotency_key=key,
    )


async def set_project_quota_limit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    daily_limit_usd: Decimal | int | str,
    monthly_limit_usd: Decimal | int | str | None = None,
    actor_user_id: uuid.UUID,
    request_id: str | None = None,
    at: datetime | None = None,
):
    """owner/admin 操作路径设置项目额度；没有 HTTP 路由时也写统一审计。"""
    from data_intelligence_hub.repositories.quota_accounts import (
        update_quota_limits,
    )

    now = at or datetime.now(UTC)
    daily = _money(daily_limit_usd, "daily_limit_usd")
    monthly = _money(
        daily if monthly_limit_usd is None else monthly_limit_usd,
        "monthly_limit_usd",
    )
    account = await get_or_create_quota_account(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        period_start=_day_start(now),
    )
    previous_daily = account.daily_limit_usd
    previous_monthly = account.monthly_limit_usd
    account = await update_quota_limits(
        session,
        account_id=account.id,
        daily_limit_usd=daily,
        monthly_limit_usd=monthly,
        at=now,
    )
    await append_audit_event(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        actor_type="user",
        action="budget.limit.changed",
        resource_type="quota_account",
        resource_id=str(account.id),
        request_id=request_id,
        result="success",
        details={
            "previous_daily_limit_usd": str(previous_daily),
            "previous_monthly_limit_usd": str(previous_monthly),
            "daily_limit_usd": str(daily),
            "monthly_limit_usd": str(monthly),
        },
        occurred_at=now,
    )
    return account


__all__ = [
    "BudgetApprovalRequiredError",
    "BudgetEstimate",
    "BudgetExceededError",
    "BudgetReservation",
    "BudgetSettlement",
    "DuplicateSettlementError",
    "ReservationAlreadySettledError",
    "block_run_budget",
    "cancel_reservation",
    "estimate_run_budget",
    "mark_result_unknown",
    "release_settlement",
    "reserve_run_budget",
    "run_remaining_budget",
    "set_project_quota_limit",
    "settle_run_cost",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_budget_service.py -v
uv run ruff check src/data_intelligence_hub/services/budget_service.py tests/unit/test_budget_service.py
```

Expected: 17 passed，ruff 通过。并发测试必须只允许一个 `True`，额度变更必须写 `budget.limit.changed`。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/services/budget_service.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/tests/unit/test_budget_service.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(budget): add atomic estimate reserve settle release block"
```

---

### Task 7: 唯一迁移 061

**Files:**
- Create: `apps/api/alembic/versions/202610220061_budget_ledger_pricing.py`
- Test: `apps/api/tests/unit/test_budget_migration_source.py`

**Interfaces:**
- Consumes: C4 的迁移 `202610220060`。
- Produces: 表 `tool_prices`（C1 的 13 列、5 个约束、2 个索引）、`quota_accounts`、`tool_calls`、`workbench_approval_actions`（C1 的 13 列、3 个 CHECK、2 个索引）；列 `authorizations.run_id`；部分唯一索引 `uq_authorizations_run_gate`（`WHERE run_id IS NOT NULL`）；约束 `ck_run_ledger_entries_amount_sign_by_kind`；存量 quota 账户与 run 授权回填（blocked G-Plan 绑定，不创建 pass 行；其余 run 建 `0.000000` 零预算行）。迁移只建空的 `tool_prices`，价格种子由 `scripts/seed_tool_prices.py` 写入。

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "RunLedgerEntry" --direction upstream --repo .
node .gitnexus/run.cjs impact "Authorization" --direction upstream --repo .
```

Expected: `risk` 不高于 LOW。迁移只加表、列与约束，不改现有列名。

- [ ] **Step 2: Write the failing migration tests**

Create `apps/api/tests/unit/test_budget_migration_source.py`:

```python
"""迁移 061 的源检查与单 head 守卫。"""

from __future__ import annotations

import importlib.util
import inspect
import subprocess
from pathlib import Path
from types import ModuleType

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    API_ROOT / "alembic/versions/202610220061_budget_ledger_pricing.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "budget_ledger_pricing",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_follows_c4_revision() -> None:
    module = _load_migration()
    assert module.revision == "202610220061"
    assert module.down_revision == "202610220060"


def test_migration_creates_tool_prices_table() -> None:
    module = _load_migration()
    upgrade = inspect.getsource(module.upgrade)
    downgrade = inspect.getsource(module.downgrade)
    source = inspect.getsource(module)

    assert 'create_table(\n        "tool_prices"' in upgrade
    for column in (
        "tool_id",
        "currency",
        "price_book_version",
        "unit_price",
        "unit",
        "quantity_basis",
        "confidence",
        "source",
        "effective_from",
        "effective_to",
    ):
        assert f'"{column}"' in upgrade
    for constraint in (
        "uq_tool_prices_tool_currency_version",
        "ck_tool_prices_unit_price_nonnegative",
        "ck_tool_prices_confidence",
        "ck_tool_prices_effective_window",
        "fk_tool_prices_tool_id_tool_catalog",
    ):
        assert constraint in source
    assert "ix_tool_prices_tool_effective" in upgrade
    assert 'drop_table("tool_prices")' in downgrade


def test_migration_does_not_seed_tool_prices() -> None:
    # 迁移只建表；fixture 读取与种子导入属于 scripts/seed_tool_prices.py。
    module = _load_migration()
    source = inspect.getsource(module)
    assert "price_book_v1.json" not in source
    assert "load_price_book" not in source
    assert "seed_tool_prices_from_entries" not in source


def test_migration_creates_quota_tool_calls_and_approval_tables() -> None:
    module = _load_migration()
    upgrade = inspect.getsource(module.upgrade)
    downgrade = inspect.getsource(module.downgrade)

    assert 'create_table(\n        "quota_accounts"' in upgrade
    assert 'create_table(\n        "tool_calls"' in upgrade
    assert 'create_table(\n        "workbench_approval_actions"' in upgrade
    assert 'drop_table("workbench_approval_actions")' in downgrade
    assert 'drop_table("tool_calls")' in downgrade
    assert 'drop_table("quota_accounts")' in downgrade


def test_migration_registers_inline_approval_constraints() -> None:
    module = _load_migration()
    source = inspect.getsource(module)
    for name in (
        "ck_workbench_approval_actions_action_type",
        "ck_workbench_approval_actions_status",
        "ck_workbench_approval_actions_self_approval",
        "uq_workbench_approval_actions_idempotency",
        "ix_workbench_approval_actions_task_status",
    ):
        assert name in source
    assert "approver_user_id IS NULL OR approver_user_id <> requester_user_id" in source


def test_migration_adds_run_id_to_authorizations() -> None:
    module = _load_migration()
    upgrade = inspect.getsource(module.upgrade)
    assert '"run_id"' in upgrade
    assert "fk_authorizations_run_id_runs" in upgrade
    assert "uq_authorizations_run_gate" in upgrade
    assert "run_id IS NOT NULL" in upgrade


def test_migration_does_not_change_ledger_columns() -> None:
    module = _load_migration()
    upgrade = inspect.getsource(module.upgrade)
    assert 'add_column("run_ledger_entries"' not in upgrade
    assert "entry_type" not in upgrade
    assert "amount_sign_by_kind" in upgrade


def test_migration_backfills_run_authorizations() -> None:
    module = _load_migration()
    upgrade = inspect.getsource(module.upgrade)
    source = inspect.getsource(module._backfill_authorizations)
    assert "_backfill_authorizations" in upgrade
    assert "c5_legacy_zero_cap" in source
    assert "blocked_by_key" in source
    assert "G-Cost" in source
    assert "Decimal(\"1.000000\")" not in source
    assert "total_cost_usd" not in source
    assert 'Decimal("0.000000")' in source


def test_migration_backfills_quota_accounts_with_zero_limit() -> None:
    module = _load_migration()
    upgrade = inspect.getsource(module.upgrade)
    source = inspect.getsource(module._backfill_quota_accounts)
    assert "_backfill_quota_accounts" in upgrade
    assert '"0.000000"' in source
    assert "uq_quota_accounts_project_period" in upgrade


def test_migration_leaves_a_single_head() -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=API_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("202610220061")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_budget_migration_source.py -v
```

Expected: `FileNotFoundError` 或 `ModuleNotFoundError`，因为迁移文件不存在。

- [ ] **Step 4: Implement the migration**

Create `apps/api/alembic/versions/202610220061_budget_ledger_pricing.py`:

```python
"""Create tool_prices, quota_accounts, tool_calls, workbench_approval_actions and per-run authorization binding.

Revision ID: 202610220061
Revises: 202610220060
Create Date: 2026-10-22

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

规则：
- ``tool_prices`` 按 C1 契约建 13 列：tool_id、currency、price_book_version、
  unit_price、unit、quantity_basis、confidence、source、effective_from、
  effective_to、created_at、updated_at、id。
- ``tool_prices`` 是唯一价格事实源；本迁移只建空表，不读取 fixture、不写入价格。
- 价格种子由 ``python -m data_intelligence_hub.scripts.seed_tool_prices`` 执行。
- ``workbench_approval_actions`` 按 C1 建 13 列、3 个 CHECK、2 个索引；
  只承载 budget_overage、package_addon、project_key_change。
- ``run_ledger_entries`` 只加金额符号约束，不加列。
- ``(run_id, gate_id)`` 在 ``run_id`` 非空时部分唯一；索引名是 ``uq_authorizations_run_gate``。
- 存量 run 回填零预算授权。回填行带 ``scope.origin='c5_legacy_zero_cap'``。
- downgrade 删除所有 run 绑定授权，再删列与四张新表。
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision: str = "202610220061"
down_revision: str | None = "202610220060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def _backfill_quota_accounts(bind: sa.Connection) -> None:
    # 为每个现有项目建今日 0 限额账户；不发明业务额度。
    projects = sa.table(
        "projects",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("status", sa.String()),
    )
    quota_accounts = sa.table(
        "quota_accounts",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("period_start", sa.Date()),
        sa.column("period_end", sa.Date()),
        sa.column("currency", sa.String()),
        sa.column("daily_limit_usd", sa.Numeric(12, 6)),
        sa.column("monthly_limit_usd", sa.Numeric(12, 6)),
        sa.column("used_usd", sa.Numeric(12, 6)),
        sa.column("reserved_usd", sa.Numeric(12, 6)),
        sa.column("remaining_usd", sa.Numeric(12, 6)),
        sa.column("version", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    today = datetime.now(UTC).date()
    rows = bind.execute(
        sa.select(projects.c.id, projects.c.workspace_id).where(
            projects.c.status == "active"
        )
    ).all()
    for row in rows:
        exists = bind.execute(
            sa.select(quota_accounts.c.id).where(
                quota_accounts.c.project_id == row.id,
                quota_accounts.c.period_start == today,
            )
        ).first()
        if exists is not None:
            continue
        bind.execute(
            quota_accounts.insert().values(
                id=uuid.uuid4(),
                workspace_id=row.workspace_id,
                project_id=row.id,
                period_start=today,
                period_end=today,
                currency="USD",
                daily_limit_usd=Decimal("0.000000"),
                monthly_limit_usd=Decimal("0.000000"),
                used_usd=Decimal("0.000000"),
                reserved_usd=Decimal("0.000000"),
                remaining_usd=Decimal("0.000000"),
                version=1,
                updated_at=datetime.now(UTC),
            )
        )


def _backfill_authorizations(bind: sa.Connection) -> None:
    runs = sa.table(
        "runs",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("workflow_version_id", sa.Uuid()),
        sa.column("market_code", sa.String()),
    )
    workspaces = sa.table(
        "workspaces",
        sa.column("id", sa.Uuid()),
        sa.column("owner_id", sa.Uuid()),
    )
    authorizations = sa.table(
        "authorizations",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("plan_id", sa.Uuid()),
        sa.column("plan_version_id", sa.Uuid()),
        sa.column("gate_id", sa.String()),
        sa.column("gate_status", sa.String()),
        sa.column("scope", sa.JSON()),
        sa.column("allowed_risk_levels", sa.JSON()),
        sa.column("max_cost_usd", sa.Numeric(12, 6)),
        sa.column("approver", sa.Uuid()),
        sa.column("granted_at", sa.DateTime(timezone=True)),
        sa.column("expires_at", sa.DateTime(timezone=True)),
        sa.column("revoked_at", sa.DateTime(timezone=True)),
        sa.column("idempotency_key_hash", sa.String()),
        sa.column("run_id", sa.Uuid()),
    )

    blocked_rows = bind.execute(
        sa.select(authorizations)
        .where(
            authorizations.c.gate_id == "G-Plan",
            authorizations.c.gate_status == "blocked",
            authorizations.c.run_id.is_(None),
        )
    ).mappings().all()
    blocked_by_key: dict[tuple[object, object], object] = {}
    for item in blocked_rows:
        scope = item["scope"] if isinstance(item["scope"], dict) else {}
        blocked_by_key[(item["plan_version_id"], scope.get("market_code"))] = item["id"]

    rows = bind.execute(
        sa.select(
            runs.c.id,
            runs.c.workspace_id,
            runs.c.project_id,
            runs.c.status,
            runs.c.created_at,
            runs.c.workflow_version_id,
            runs.c.market_code,
            workspaces.c.owner_id,
        )
        .select_from(runs.join(workspaces, runs.c.workspace_id == workspaces.c.id))
        .where(
            ~sa.exists(
                sa.select(1)
                .select_from(authorizations)
                .where(authorizations.c.run_id == runs.c.id)
            )
        )
    ).all()

    for row in rows:
        created_at = row.created_at or datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        blocked_id = blocked_by_key.get(
            (row.workflow_version_id, row.market_code)
        )
        if blocked_id is not None:
            # C4 的 blocked G-Plan 绑定到 run；不建 G-Cost pass。
            bind.execute(
                authorizations.update()
                .where(authorizations.c.id == blocked_id)
                .values(run_id=row.id)
            )
            continue
        # 存量 run 没有 C4 订单上限：回填 0，不发明默认预算。
        max_cost = Decimal("0.000000")
        bind.execute(
            authorizations.insert().values(
                id=uuid.uuid4(),
                workspace_id=row.workspace_id,
                project_id=row.project_id,
                plan_id=None,
                plan_version_id=None,
                gate_id="G-Cost",
                gate_status="pass",
                scope={
                    "origin": "c5_legacy_zero_cap",
                    "run_id": str(row.id),
                    "status": row.status,
                },
                allowed_risk_levels=None,
                max_cost_usd=max_cost,
                approver=row.owner_id,
                granted_at=created_at,
                expires_at=created_at + timedelta(days=365),
                revoked_at=None,
                idempotency_key_hash=None,
                run_id=row.id,
            )
        )


def upgrade() -> None:
    op.create_table(
        "tool_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.String(length=200), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("price_book_version", sa.String(length=40), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("quantity_basis", sa.String(length=40), nullable=True),
        sa.Column(
            "confidence",
            sa.String(length=20),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_tool_prices"),
        sa.UniqueConstraint(
            "tool_id",
            "currency",
            "price_book_version",
            name="uq_tool_prices_tool_currency_version",
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_tool_prices_unit_price_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown')",
            name="ck_tool_prices_confidence",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_tool_prices_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"],
            ["tool_catalog.tool_id"],
            name="fk_tool_prices_tool_id_tool_catalog",
        ),
    )
    op.create_index(
        "ix_tool_prices_tool_effective",
        "tool_prices",
        ["tool_id", "effective_from"],
        unique=False,
    )

    op.create_table(
        "quota_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("daily_limit_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("monthly_limit_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "used_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "reserved_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("remaining_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quota_accounts"),
        sa.UniqueConstraint(
            "project_id",
            "period_start",
            "period_end",
            name="uq_quota_accounts_project_period",
        ),
        sa.CheckConstraint(
            "daily_limit_usd >= 0",
            name="ck_quota_accounts_daily_limit_non_negative",
        ),
        sa.CheckConstraint(
            "monthly_limit_usd >= 0",
            name="ck_quota_accounts_monthly_limit_non_negative",
        ),
        sa.CheckConstraint(
            "reserved_usd >= 0",
            name="ck_quota_accounts_reserved_non_negative",
        ),
        sa.CheckConstraint(
            "used_usd >= 0",
            name="ck_quota_accounts_used_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_quota_accounts_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_quota_accounts_project_id_projects",
        ),
    )
    op.create_index(
        "ix_quota_accounts_project_period",
        "quota_accounts",
        ["project_id", "period_start", "period_end"],
        unique=True,
    )

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("tool_id", sa.String(length=200), nullable=False),
        sa.Column("contract_version", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("backend_ref_type", sa.String(length=40), nullable=True),
        sa.Column("backend_ref_id", sa.String(length=120), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_tool_calls"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key_hash",
            name="uq_tool_calls_workspace_idempotency",
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'empty', 'config_gated', 'failed')",
            name="ck_tool_calls_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_tool_calls_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_tool_calls_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_tool_calls_run_id_runs",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["run_steps.id"],
            name="fk_tool_calls_step_id_run_steps",
        ),
    )
    op.create_index(
        "ix_tool_calls_run_step",
        "tool_calls",
        ["run_id", "step_id"],
    )
    op.create_index(
        "ix_tool_calls_tool_started",
        "tool_calls",
        ["tool_id", "started_at"],
    )

    op.create_table(
        "workbench_approval_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("approver_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_workbench_approval_actions"),
        sa.CheckConstraint(
            "action_type IN ('budget_overage', 'package_addon', 'project_key_change')",
            name="ck_workbench_approval_actions_action_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="ck_workbench_approval_actions_status",
        ),
        sa.CheckConstraint(
            "approver_user_id IS NULL OR approver_user_id <> requester_user_id",
            name="ck_workbench_approval_actions_self_approval",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workbench_approval_actions_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_workbench_approval_actions_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["workbench_tasks.id"],
            name="fk_workbench_approval_actions_task_id_workbench_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"],
            ["users.id"],
            name="fk_workbench_approval_actions_requester_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["approver_user_id"],
            ["users.id"],
            name="fk_workbench_approval_actions_approver_user_id_users",
        ),
    )
    op.create_index(
        "uq_workbench_approval_actions_idempotency",
        "workbench_approval_actions",
        ["workspace_id", "idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("idempotency_key_hash IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key_hash IS NOT NULL"),
    )
    op.create_index(
        "ix_workbench_approval_actions_task_status",
        "workbench_approval_actions",
        ["task_id", "status"],
        unique=False,
    )

    with op.batch_alter_table("authorizations") as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_authorizations_run_id_runs",
            "runs",
            ["run_id"],
            ["id"],
        )
    op.create_index(
        "uq_authorizations_run_gate",
        "authorizations",
        ["run_id", "gate_id"],
        unique=True,
        postgresql_where=sa.text("run_id IS NOT NULL"),
        sqlite_where=sa.text("run_id IS NOT NULL"),
    )

    with op.batch_alter_table("run_ledger_entries") as batch_op:
        batch_op.create_check_constraint(
            "amount_sign_by_kind",
            "(entry_kind = 'settle' AND amount_usd > 0) OR "
            "(entry_kind = 'release' AND amount_usd < 0) OR "
            "(entry_kind IN ('estimate', 'reserve', 'accrued', 'block') "
            "AND amount_usd >= 0)",
        )

    _backfill_quota_accounts(op.get_bind())
    _backfill_authorizations(op.get_bind())


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM authorizations WHERE run_id IS NOT NULL"))
    with op.batch_alter_table("run_ledger_entries") as batch_op:
        batch_op.drop_constraint(
            "ck_run_ledger_entries_amount_sign_by_kind",
            type_="check",
        )
    op.drop_index("uq_authorizations_run_gate", table_name="authorizations")
    with op.batch_alter_table("authorizations") as batch_op:
        batch_op.drop_constraint(
            "fk_authorizations_run_id_runs",
            type_="foreignkey",
        )
        batch_op.drop_column("run_id")
    op.drop_index("ix_tool_calls_tool_started", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_step", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index(
        "ix_workbench_approval_actions_task_status",
        table_name="workbench_approval_actions",
    )
    op.drop_index(
        "uq_workbench_approval_actions_idempotency",
        table_name="workbench_approval_actions",
    )
    op.drop_table("workbench_approval_actions")
    op.drop_index("ix_quota_accounts_project_period", table_name="quota_accounts")
    op.drop_table("quota_accounts")
    op.drop_index("ix_tool_prices_tool_effective", table_name="tool_prices")
    op.drop_table("tool_prices")
```

注意：`CheckConstraint` 在模型里的 name 是 `amount_sign_by_kind`。Alembic 命名约定会生成 `ck_run_ledger_entries_amount_sign_by_kind`。downgrade 必须使用完整名。`tool_prices` 不读取 fixture；downgrade 直接删表，价格可由重新升级后的种子脚本恢复。

- [ ] **Step 5: Run the migration tests**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_budget_migration_source.py -v
uv run alembic heads
```

Expected:

```text
10 passed
202610220061 (head)
```

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/alembic/versions/202610220061_budget_ledger_pricing.py \
  apps/api/tests/unit/test_budget_migration_source.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(budget): add migration 061 with tool prices and run authorization"
```

Expected: `detect-changes` 覆盖迁移与测试且 `partial` 与 `truncated` 均为 false。提交前必须重跑 detect-changes。

---

### Task 8: `usage_service` 统一价格入口（`tool_prices` 快照）

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/usage_service.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/usage.py`
- Modify: `apps/api/tests/unit/test_usage_service.py`
- Modify: `apps/api/tests/unit/test_pricing.py`

**Interfaces:**
- Consumes: `pricing.quote_usage`（读取已锁定的 `tool_prices` 快照）。
- Produces: `get_usage_summary` 不再读取 fixture，统一经 `pricing`；缺价格时抛 `ToolNotPricedError`。保留 `get_usage_summary_legacy` 作为 shadow 回退：它只汇总 `task_runs.total_cost_usd`，缺实际成本记 0，不读 fixture、不查 `tool_prices`、不做估算。`STRICT_PRICE_ENABLED=true` 时路由返回 422 `tool_not_priced`。

- [ ] **Step 1: Run impact**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "get_usage_summary" --direction upstream --repo .
node .gitnexus/run.cjs impact "usage_summary" --direction upstream --repo .
```

Expected: `get_usage_summary` LOW，1 个直接调用者。`usage_summary` LOW。

- [ ] **Step 2: Add the failing tests**

在 `apps/api/tests/unit/test_usage_service.py` 追加：

```python
@pytest.mark.asyncio
async def test_usage_summary_raises_for_unpriced_endpoint(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from data_intelligence_hub.models.task import TaskRun
    from data_intelligence_hub.services.pricing import ToolNotPricedError

    async with session_factory() as session:
        session.add(
            TaskRun(
                task_id=_ids()["task"],
                workspace_id=_ids()["workspace"],
                status="success",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                records_count=1,
                entities_count=0,
                logs=[],
                created_at=datetime.now(UTC),
                endpoint_type="apify_1688_advanced",
                provider="apify",
                total_cost_usd=None,
            )
        )
        await session.commit()
        with pytest.raises(ToolNotPricedError):
            await get_usage_summary(
                session,
                workspace_id=_ids()["workspace"],
                days=30,
            )


@pytest.mark.asyncio
async def test_usage_summary_uses_actual_cost_without_price(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from data_intelligence_hub.models.task import TaskRun

    async with session_factory() as session:
        session.add(
            TaskRun(
                task_id=_ids()["task"],
                workspace_id=_ids()["workspace"],
                status="success",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                records_count=1,
                entities_count=0,
                logs=[],
                created_at=datetime.now(UTC),
                endpoint_type="endpoint_without_price",
                provider="unknown",
                total_cost_usd=Decimal("0.75"),
            )
        )
        await session.commit()
        summary = await get_usage_summary(
            session,
            workspace_id=_ids()["workspace"],
            days=30,
        )

    assert summary["totals"]["cost_usd"] == "1.258000"
```

同时更新 `test_usage_service.py` 的 `session_factory` fixture：建表后调用 `seed_tool_prices_from_fixture(session)` 与 `refresh_price_book(session)`，测试结束调用 `reset_price_book_for_tests()`。`quote_usage` 只读已锁定的 `tool_prices` 快照，未锁定时会抛 `PriceBookNotLockedError`。

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_usage_service.py -v
```

Expected: 新测试失败。现有 fixture 价格回退不会从 `tool_prices` 报价。

- [ ] **Step 4: Replace the local price logic**

在 `services/usage_service.py`：

1. 删除 `from data_intelligence_hub.tool_catalog.fixtures import load_price_book`。
2. 删除 `_RECORD_BASES`、`_price_entries` 与旧的 `_estimate_cost`。
3. 加：

```python
from data_intelligence_hub.services.pricing import ToolNotPricedError, quote_usage


def _estimate_cost(
    tool_id: str | None,
    records_count: int,
    actual_cost: Decimal | None,
) -> Decimal:
    if actual_cost is not None:
        return actual_cost
    if not tool_id:
        raise ToolNotPricedError("<missing>", "missing_tool_id")
    return quote_usage(tool_id, records_count=records_count).total_cost_usd
```

4. 先把现有 `get_usage_summary` 实现重命名为 `get_usage_summary_legacy`，再让新的 `get_usage_summary` 使用 `pricing`；删除新函数里的 `entries = _price_entries()`。
5. legacy 路径也必须与价格源解耦：循环里用 `cost = actual_cost if actual_cost is not None else Decimal("0")`，不调用 `_estimate_cost`，不查 `tool_prices`，不读 fixture。
6. 新 `get_usage_summary` 的循环改为：

```python
        cost = _estimate_cost(endpoint_type, int(records_count or 0), actual_cost)
```

在 `api/routes/usage.py`：

```python
import logging

from fastapi import APIRouter, HTTPException, Query, status

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.services.pricing import ToolNotPricedError

logger = logging.getLogger(__name__)
```

并在 `usage_summary` 中包住服务调用：

```python
    try:
        return await get_usage_summary(
            session,
            workspace_id=context.workspace.id,
            days=days,
            project_id=project_id,
        )
    except ToolNotPricedError as exc:
        if get_settings().strict_price_enabled:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.message,
            ) from exc
        logger.warning("tool_not_priced_shadow", extra={"tool_id": exc.tool_id})
        return await get_usage_summary_legacy(
            session,
            workspace_id=context.workspace.id,
            days=days,
            project_id=project_id,
        )
```

- [ ] **Step 5: Run the tests**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_usage_service.py -v
uv run ruff check src/data_intelligence_hub/services/usage_service.py \
  src/data_intelligence_hub/api/routes/usage.py \
  tests/unit/test_usage_service.py
```

Expected: 全部通过。原有三种汇总断言保持不变。

- [ ] **Step 6: Add and run the price-source guards**

在 `apps/api/tests/unit/test_pricing.py` 末尾追加：

```python
def test_no_runtime_fixture_price_reads() -> None:
    # fixture 只允许种子路径读取；pricing/usage 等运行时代码不得读取。
    allowed = {
        SOURCE_ROOT / "tool_catalog/fixtures.py",
        SOURCE_ROOT / "repositories/tool_prices.py",
        SOURCE_ROOT / "scripts/seed_tool_prices.py",
    }
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if path in allowed:
            continue
        if "load_price_book" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(SOURCE_ROOT)))

    assert offenders == []


def test_only_pricing_reads_tool_prices() -> None:
    # tool_prices 的唯一运行时读者是 pricing；种子与模型定义除外。
    allowed = {
        SOURCE_ROOT / "models/tool_price.py",
        SOURCE_ROOT / "models/__init__.py",
        SOURCE_ROOT / "repositories/tool_prices.py",
        SOURCE_ROOT / "services/pricing.py",
        SOURCE_ROOT / "scripts/seed_tool_prices.py",
    }
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if "ToolPrice" in text or "tool_prices" in text:
            offenders.append(str(path.relative_to(SOURCE_ROOT)))

    assert offenders == []
```

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest \
  tests/unit/test_pricing.py::test_no_runtime_fixture_price_reads \
  tests/unit/test_pricing.py::test_only_pricing_reads_tool_prices \
  -v
```

Expected: 2 passed。`usage_service.py` 已删除 `load_price_book` 导入；运行时代码只通过 `pricing` 读取锁定快照。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git add apps/api/src/data_intelligence_hub/services/usage_service.py \
  apps/api/src/data_intelligence_hub/api/routes/usage.py \
  apps/api/tests/unit/test_usage_service.py \
  apps/api/tests/unit/test_pricing.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "refactor(usage): route all cost estimates through tool prices"
```

Expected: `detect-changes` 覆盖本任务文件且 `partial` 与 `truncated` 均为 false。提交前必须重跑 detect-changes。

---

### Task 8A: quota 端点与价格覆盖预检

**Files:**
- Create: `apps/api/src/data_intelligence_hub/schemas/quota.py`
- Create: `apps/api/src/data_intelligence_hub/api/routes/quota.py`
- Create: `apps/api/src/data_intelligence_hub/scripts/price_coverage_report.py`
- Modify: `apps/api/src/data_intelligence_hub/main.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/usage.py`
- Test: `apps/api/tests/unit/test_quota_routes.py`
- Test: `apps/api/tests/unit/test_price_coverage_report.py`

**Interfaces:**
- Produces:
  - `GET /api/quota`：当前工作区今日额度汇总。
  - `GET /api/quota/projects/{project_id}`：单项目额度；项目不在工作区时 404。
  - `QuotaSummaryResponse`、`QuotaProjectResponse`。
  - `price_coverage_report.build_report(session, *, endpoints=None) -> dict[str, object]`。
- 两个端点都先调用 C2 `require_project_access(..., manage=False)`，再走 `get_or_create_quota_account`；缺失账户返回 0 限额，不报 500。`GET /api/quota` 对同工作区未授权项目静默跳过，不得泄露其额度；`GET /api/quota/projects/{project_id}` 跨工作区 404 `project_not_found`，同工作区未授权 403 `project_access_forbidden`。
- `STRICT_PRICE_ENABLED=false` 时，`usage.py` 捕获 `ToolNotPricedError` 并回退 `get_usage_summary_legacy`（只按实际成本汇总），同时记录 `tool_not_priced_shadow`；`true` 时返回 422 `tool_not_priced`。
- `price_coverage_report.py` 先用 `pricing.refresh_price_book(session)` 从 `tool_prices` 锁定快照，再对比 tool catalog 的 `tool_id` 集合与 `pricing.priced_endpoints()`（快照里有非空单价的工具），输出 `priced`、`unpriced`、`missing_count`。报告不读 fixture、不猜价格、不写库。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_quota_routes.py`:

```python
# quota 端点：额度、reserved、used、remaining。

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.routes.quota import (
    get_project_quota,
    get_workspace_quota,
)
from data_intelligence_hub.models.project import Project, ProjectMember
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import WorkspaceMember
from tests.unit.budget_test_support import seed_budget_scope, with_sqlite_session


@pytest.mark.anyio
async def test_quota_endpoints_return_zero_for_new_project() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="quota-route")
        context = SimpleNamespace(workspace=seed.workspace, user=seed.user)
        summary = await get_workspace_quota(session, context=context)
        project = await get_project_quota(
            seed.project.id,
            session,
            context=context,
        )
        observed["daily"] = summary.daily_limit_usd
        observed["reserved"] = summary.reserved_usd
        observed["used"] = summary.used_usd
        observed["project_id"] = project.project_id

    await with_sqlite_session(scenario)

    assert observed["daily"] == Decimal("0.000000")
    assert observed["reserved"] == Decimal("0.000000")
    assert observed["used"] == Decimal("0.000000")


@pytest.mark.anyio
async def test_project_quota_denies_same_workspace_cross_project_member() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="quota-acl")
        second = Project(
            workspace_id=seed.workspace.id,
            name="other",
            domain="mother_baby",
            owner_id=seed.user.id,
        )
        session.add(second)
        await session.flush()
        member = User(
            email="quota-member@example.com",
            password_hash="x",
            name="Member",
        )
        session.add(member)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=seed.workspace.id,
                user_id=member.id,
                role="member",
            )
        )
        session.add(
            ProjectMember(
                workspace_id=seed.workspace.id,
                project_id=seed.project.id,
                user_id=member.id,
            )
        )
        context = SimpleNamespace(workspace=seed.workspace, user=member)
        with pytest.raises(Exception) as exc_info:
            await get_project_quota(second.id, session, context=context)
        observed["code"] = getattr(exc_info.value, "code", None)

    await with_sqlite_session(scenario)

    assert observed["code"] == "project_access_forbidden"
```

Create `apps/api/tests/unit/test_price_coverage_report.py`:

```python
# 价格覆盖差集报告。读取 tool_prices 快照，不读 fixture。

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.scripts.price_coverage_report import build_report
from tests.unit.price_test_support import with_price_session


@pytest.mark.anyio
async def test_report_lists_unpriced_endpoints() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        report = await build_report(
            session,
            endpoints={"exa_search_lite", "missing_tool"},
        )
        observed["missing_count"] = report["missing_count"]
        observed["unpriced"] = report["unpriced"]
        observed["priced"] = report["priced"]

    await with_price_session(scenario)

    assert observed["missing_count"] == 1
    assert observed["unpriced"] == ["missing_tool"]
    assert observed["priced"] == ["exa_search_lite"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_quota_routes.py tests/unit/test_price_coverage_report.py -v
```

Expected: FAIL，路由或模块不存在。

- [ ] **Step 3: 写 schema 与路由**

Create `apps/api/src/data_intelligence_hub/schemas/quota.py`:

```python
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class QuotaProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    period_start: date
    period_end: date
    currency: str
    daily_limit_usd: Decimal
    monthly_limit_usd: Decimal
    reserved_usd: Decimal
    used_usd: Decimal
    remaining_usd: Decimal


class QuotaSummaryResponse(BaseModel):
    period_start: date
    period_end: date
    currency: str
    daily_limit_usd: Decimal
    reserved_usd: Decimal
    used_usd: Decimal
    remaining_usd: Decimal
    projects: list[QuotaProjectResponse]
```

Create `apps/api/src/data_intelligence_hub/api/routes/quota.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.authz import require_project_access
from data_intelligence_hub.api.deps import SessionDep, get_authenticated_context
from data_intelligence_hub.core.errors import APIError
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.repositories.quota_accounts import (
    get_or_create_quota_account,
)
from data_intelligence_hub.schemas.quota import (
    QuotaProjectResponse,
    QuotaSummaryResponse,
)

router = APIRouter(tags=["quota"])


@router.get("/quota", response_model=QuotaSummaryResponse)
async def get_workspace_quota(
    session: SessionDep,
    context=Depends(get_authenticated_context),
) -> QuotaSummaryResponse:
    today = datetime.now(UTC).date()
    projects = (
        await session.execute(
            select(Project).where(Project.workspace_id == context.workspace.id)
        )
    ).scalars().all()
    items = []
    for project in projects:
        try:
            await require_project_access(
                session,
                workspace=context.workspace,
                user=context.user,
                project_id=project.id,
                manage=False,
            )
        except APIError as exc:
            if exc.code == "project_access_forbidden":
                continue
            raise
        account = await get_or_create_quota_account(
            session,
            workspace_id=context.workspace.id,
            project_id=project.id,
            period_start=today,
        )
        items.append(QuotaProjectResponse.model_validate(account, from_attributes=True))
    return QuotaSummaryResponse(
        period_start=today,
        period_end=today,
        currency="USD",
        daily_limit_usd=sum((item.daily_limit_usd for item in items), Decimal("0")),
        reserved_usd=sum((item.reserved_usd for item in items), Decimal("0")),
        used_usd=sum((item.used_usd for item in items), Decimal("0")),
        remaining_usd=sum((item.remaining_usd for item in items), Decimal("0")),
        projects=items,
    )


@router.get("/quota/projects/{project_id}", response_model=QuotaProjectResponse)
async def get_project_quota(
    project_id: uuid.UUID,
    session: SessionDep,
    context=Depends(get_authenticated_context),
) -> QuotaProjectResponse:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == context.workspace.id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    await require_project_access(
        session,
        workspace=context.workspace,
        user=context.user,
        project_id=project.id,
        manage=False,
    )
    account = await get_or_create_quota_account(
        session,
        workspace_id=context.workspace.id,
        project_id=project.id,
        period_start=datetime.now(UTC).date(),
    )
    return QuotaProjectResponse.model_validate(account, from_attributes=True)
```

`QuotaProjectResponse` 的 `project_id` 与 `QuotaAccount.project_id` 同名；`period_*`、`currency`、金额字段同名，`from_attributes` 可直接校验。

在 `main.py` 挂载 `quota_router`，并在 lifespan 启动阶段用数据库会话调用：

```python
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.services import pricing

async with async_session_factory() as session:
    await pricing.refresh_price_book(session)
```

该步骤只读 `tool_prices` 并锁定快照，不读 fixture。`tool_prices` 为空时 `PriceBookEmptyError` 让启动失败，提示先运行 `seed_tool_prices`。测试在 fixture 里 `reset_price_book_for_tests()` 后重新 `refresh_price_book(session)`。

- [ ] **Step 4: strict price 与覆盖报告**

在 `api/routes/usage.py` 的 `get_usage_summary` 调用处加：

```python
    try:
        summary = await get_usage_summary(session, ...)
    except ToolNotPricedError as exc:
        if get_settings().strict_price_enabled:
            raise HTTPException(status_code=422, detail="tool_not_priced") from exc
        logger.warning("tool_not_priced_shadow", extra={"endpoint": str(exc)})
        summary = await get_usage_summary_legacy(session, ...)
```

Create `apps/api/src/data_intelligence_hub/scripts/price_coverage_report.py`:

```python
from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.platform_packages.service import (
    get_platform_package_catalog,
)
from data_intelligence_hub.services.pricing import (
    priced_endpoints,
    refresh_price_book,
)
from data_intelligence_hub.tool_catalog.projection import build_tool_catalog


async def _catalog_tool_ids() -> set[str]:
    catalog = build_tool_catalog(await get_platform_package_catalog())
    return {tool.tool_id for tool in catalog.tools}


async def build_report(
    session: AsyncSession,
    *,
    endpoints: Iterable[str] | None = None,
) -> dict[str, object]:
    await refresh_price_book(session)
    if endpoints is None:
        catalog = await _catalog_tool_ids()
    else:
        catalog = set(endpoints)
    priced = set(priced_endpoints())
    unpriced = sorted(catalog - priced)
    return {
        "priced": sorted(catalog & priced),
        "unpriced": unpriced,
        "missing_count": len(unpriced),
    }


def main() -> None:
    import asyncio

    async def run() -> None:
        async with async_session_factory() as session:
            print(
                json.dumps(
                    await build_report(session),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
```

`build_tool_catalog` 与 `get_platform_package_catalog` 是仓库现有公开入口；报告只对比端点集合与 `tool_prices` 快照，不猜价格、不读 fixture。

**价格来源。** 运行时唯一价格源是 `tool_prices`。`price_book_v1.json` 只由 `seed_tool_prices.py` 写入该表，总索引 §8.4 的 PG0 发布批次在迁移后、API 启动前执行。`price_coverage_report.py` 的 `unpriced` 清单是 enforce 前的唯一门禁：未定价端点保持失败，不得补猜价格。价格变更走 fixture 的代码评审、重新种子与版本发布，不走生产手工 SQL。

- [ ] **Step 5: 跑测试并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_quota_routes.py tests/unit/test_price_coverage_report.py -v
uv run ruff check src/data_intelligence_hub/api/routes/quota.py \
  src/data_intelligence_hub/schemas/quota.py \
  src/data_intelligence_hub/scripts/price_coverage_report.py
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "get_usage_summary" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/schemas/quota.py \
  apps/api/src/data_intelligence_hub/api/routes/quota.py \
  apps/api/src/data_intelligence_hub/scripts/price_coverage_report.py \
  apps/api/src/data_intelligence_hub/main.py \
  apps/api/src/data_intelligence_hub/api/routes/usage.py \
  apps/api/tests/unit/test_quota_routes.py \
  apps/api/tests/unit/test_price_coverage_report.py
git commit -m "feat(budget): expose quota endpoints and tool price coverage"
```

Expected: 全部通过；`detect-changes` 不含 `partial: true` / `truncated: true`。提交前必须重跑 detect-changes。

C14 `/settings` 浏览器验收：额度页必须显示 daily limit、reserved、used、remaining；未定价端点必须显示 422 `tool_not_priced`，不得显示 0 成本。

---

### Task 9: `RunBudget` 适配器（不接线执行器）

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_budget.py`
- Test: `apps/api/tests/unit/test_run_budget.py`

**Interfaces:**
- Consumes: `budget_service`、`run_authorizations`、`get_run_budget_authorization`、`has_blocked_gate`。
- Produces:
  - `RunBudget` Protocol：`reserve(run)`、`settle(run, *, step_id=None)`、`mark_unknown(run, reason)`、`cancel(run)`。
  - `OrmRunBudget(session)`：生产适配器。
- **C5 不修改** `run_executor.py`、`run_executor_adapters.py`、`run_worker_runtime.py`、`run_collector_call.py`。C6 负责注入 `OrmRunBudget` 与调用 `start_tool_call` / `complete_tool_call`。
- `RunBudget.settle` 不接收金额或 call 对象；C5 的 `settle_run_cost` 自己汇总该 run 全部 attempt 的 `task_runs.total_cost_usd`。C6 不得只传最终 step 的成本。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_run_budget.py`:

```python
# RunBudget 适配器：一次 reserve、一次 settle、失败 attempt 成本汇总。

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.quota_account import QuotaAccount
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.repositories.quota_accounts import create_quota_account
from data_intelligence_hub.services.run_budget import OrmRunBudget
from tests.unit.budget_test_support import seed_budget_scope, today, with_sqlite_session


@pytest.mark.anyio
async def test_reserve_uses_authorization_limit_and_settle_sums_attempts() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(
            session,
            slug="run-budget",
            max_cost_usd=Decimal("2.000000"),
            with_task_run=True,
        )
        await create_quota_account(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            period_start=today(),
            daily_limit_usd=Decimal("10.000000"),
        )
        failed_attempt = TaskRun(
            task_id=seed.task_run.task_id,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            run_id=seed.run.id,
            status="failed",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            records_count=0,
            entities_count=0,
            logs=[],
            created_at=datetime.now(UTC),
            total_cost_usd=Decimal("0.500000"),
            endpoint_type="exa_search_lite",
        )
        session.add(failed_attempt)
        await session.flush()
        seed.task_run.total_cost_usd = Decimal("0.250000")
        await session.flush()

        budget = OrmRunBudget(session)
        await budget.reserve(seed.run)
        await budget.settle(seed.run, step_id=seed.step.id)

        account = await session.scalar(
            select(QuotaAccount).where(QuotaAccount.project_id == seed.project.id)
        )
        refreshed = await session.get(TaskRun, seed.task_run.id)
        observed["reserved"] = account.reserved_usd
        observed["used"] = account.used_usd
        observed["remaining"] = refreshed.remaining_budget
        observed["total"] = refreshed.total_cost_usd

    await with_sqlite_session(scenario)

    assert observed["reserved"] == Decimal("0.000000")
    assert observed["used"] == Decimal("0.750000")
    assert observed["remaining"] == Decimal("1.250000")
    assert observed["total"] == Decimal("0.250000")


@pytest.mark.anyio
async def test_blocked_gate_is_refused() -> None:
    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="run-budget-blocked")
        from data_intelligence_hub.models.authorization import Authorization

        session.add(
            Authorization(
                workspace_id=seed.workspace.id,
                project_id=seed.project.id,
                run_id=seed.run.id,
                gate_id="G-Plan",
                gate_status="blocked",
                scope={"market_code": "DE"},
                max_cost_usd=Decimal("0"),
                approver=seed.user.id,
                granted_at=datetime.now(UTC),
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await session.flush()
        with pytest.raises(Exception):
            await OrmRunBudget(session).reserve(seed.run)

    await with_sqlite_session(scenario)


@pytest.mark.anyio
async def test_unknown_and_cancel_release_quota() -> None:
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await seed_budget_scope(session, slug="run-budget-unknown")
        await create_quota_account(
            session,
            workspace_id=seed.workspace.id,
            project_id=seed.project.id,
            period_start=today(),
            daily_limit_usd=Decimal("10.000000"),
        )
        budget = OrmRunBudget(session)
        await budget.reserve(seed.run)
        await budget.mark_unknown(seed.run, reason="timeout")
        account = await session.scalar(
            select(QuotaAccount).where(QuotaAccount.project_id == seed.project.id)
        )
        observed["reserved"] = account.reserved_usd
        observed["used"] = account.used_usd

    await with_sqlite_session(scenario)

    assert observed["reserved"] == Decimal("0.000000")
    assert observed["used"] == Decimal("0.000000")
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_budget.py -v
```

Expected: FAIL，`ModuleNotFoundError` 指向 `services.run_budget`。

- [ ] **Step 3: 写实现**

Create `apps/api/src/data_intelligence_hub/services/run_budget.py`:

```python
# C5 提供给 C6 的预算适配器。C5 不接线执行器。

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.repositories.authorizations import has_blocked_gate
from data_intelligence_hub.services import budget_service
from data_intelligence_hub.services.exceptions import BudgetApprovalRequiredError
from data_intelligence_hub.services.run_authorizations import (
    ensure_order_run_authorization,
)


class RunRecord(Protocol):
    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    workflow_version_id: uuid.UUID | None
    market_code: str | None


class RunBudget(Protocol):
    async def reserve(self, run: RunRecord) -> None: ...
    async def settle(
        self,
        run: RunRecord,
        *,
        step_id: uuid.UUID | None = None,
    ) -> None: ...
    async def mark_unknown(
        self,
        run: RunRecord,
        reason: str = "collector_exception",
    ) -> None: ...
    async def cancel(self, run: RunRecord) -> None: ...


class OrmRunBudget:
    # 生产适配器。所有账本写入都经过 budget_service。
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(self, run: RunRecord) -> None:
        if await has_blocked_gate(self._session, run_id=run.id):
            raise BudgetApprovalRequiredError("blocked_gate")
        await ensure_order_run_authorization(self._session, run_id=run.id)
        await budget_service.reserve_run_budget(self._session, run_id=run.id)

    async def settle(
        self,
        run: RunRecord,
        *,
        step_id: uuid.UUID | None = None,
    ) -> None:
        await budget_service.settle_run_cost(
            self._session,
            run_id=run.id,
            step_id=step_id,
        )

    async def mark_unknown(
        self,
        run: RunRecord,
        reason: str = "collector_exception",
    ) -> None:
        await budget_service.mark_result_unknown(
            self._session,
            run_id=run.id,
            reason_code=reason,
        )

    async def cancel(self, run: RunRecord) -> None:
        await budget_service.cancel_reservation(self._session, run_id=run.id)


__all__ = ["OrmRunBudget", "RunBudget", "RunRecord"]
```

- [ ] **Step 4: 跑测试确认通过**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_budget.py -v
uv run ruff check src/data_intelligence_hub/services/run_budget.py tests/unit/test_run_budget.py
```

Expected: 3 passed，ruff 通过。

- [ ] **Step 5: 图分析与提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "RunBudget" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_budget.py   apps/api/tests/unit/test_run_budget.py
git commit -m "feat(budget): provide the run budget adapter for C6"
```

Expected: `detect-changes` 覆盖本任务文件且不含 `partial: true` / `truncated: true`。

---

### Task 9A: `services/run_limits.py` 与 C6/collector 限额交接

**Files:**
- Create: `apps/api/src/data_intelligence_hub/services/run_limits.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`
- Test: `apps/api/tests/unit/test_run_limits.py`

**Interfaces:**
- Consumes: C4 `WorkbenchTask.max_pages` / `max_records`、`WorkflowVersion.workbench_task_id`、`Run.workflow_version_id`。
- Produces:
  - `RunLimits(max_pages: int | None, max_records: int | None)`，`None` 表示不限制。
  - `limits_from_task(task) -> RunLimits`
  - `resolve_run_limits(session, *, run_id) -> RunLimits`
  - `RunLimits.check_pages(pages_done: int) -> None`
  - `RunLimits.check_records(records_done: int) -> None`
  - `RunLimits.next_page_allowed(pages_done: int) -> bool`
  - `RunLimitExceededError.message` 只能是 `max_pages_exceeded` 或 `max_records_exceeded`。
- `0` 是合法限额，表示零容忍：`max_pages=0` 不允许第 1 页，`max_records=0` 不允许任何记录。不得把 `None` 当成 `0`，也不得把 `0` 当成 `None`。
- C5 不修改 `run_executor.py`、`run_executor_adapters.py`、`run_worker_runtime.py`、`run_collector_call.py`、`collector_service.py`；C6 按下述交接接线。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_run_limits.py`：

```python
"""RunLimits：None 不限制、0 零容忍、超限立即停止。"""

from __future__ import annotations

import pytest

from data_intelligence_hub.services.exceptions import RunLimitExceededError
from data_intelligence_hub.services.run_limits import RunLimits, limits_from_task


def test_none_means_unlimited() -> None:
    limits = RunLimits(max_pages=None, max_records=None)
    limits.check_pages(10_000)
    limits.check_records(10_000_000)
    assert limits.next_page_allowed(10_000) is True


def test_zero_means_zero_tolerance() -> None:
    limits = RunLimits(max_pages=0, max_records=0)
    assert limits.next_page_allowed(0) is False
    with pytest.raises(RunLimitExceededError) as pages:
        limits.check_pages(1)
    with pytest.raises(RunLimitExceededError) as records:
        limits.check_records(1)
    assert pages.value.message == "max_pages_exceeded"
    assert records.value.message == "max_records_exceeded"


def test_boundary_is_allowed_and_one_over_is_rejected() -> None:
    limits = RunLimits(max_pages=2, max_records=10)
    limits.check_pages(2)
    limits.check_records(10)
    assert limits.next_page_allowed(2) is False
    with pytest.raises(RunLimitExceededError):
        limits.check_pages(3)
    with pytest.raises(RunLimitExceededError):
        limits.check_records(11)


def test_limits_from_task_preserves_null_and_zero() -> None:
    from types import SimpleNamespace

    unlimited = limits_from_task(None)
    assert unlimited.max_pages is None
    assert unlimited.max_records is None
    task = SimpleNamespace(max_pages=0, max_records=20)
    limits = limits_from_task(task)
    assert limits.max_pages == 0
    assert limits.max_records == 20


def test_negative_limits_are_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        RunLimits(max_pages=-1, max_records=None)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_limits.py -v
```

Expected: `ModuleNotFoundError` 指向 `services.run_limits`。

- [ ] **Step 3: 写实现**

Create `apps/api/src/data_intelligence_hub/services/run_limits.py`：

```python
"""C4 任务单的页数与记录数限额。

``None`` 表示不限制；``0`` 表示零容忍。超限立即抛
``RunLimitExceededError``，调用方必须停止翻页与入库。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.workbench import WorkbenchTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.services.exceptions import RunLimitExceededError


@dataclass(frozen=True, slots=True)
class RunLimits:
    max_pages: int | None = None
    max_records: int | None = None

    def __post_init__(self) -> None:
        if self.max_pages is not None and self.max_pages < 0:
            raise ValueError("max_pages 必须 >= 0")
        if self.max_records is not None and self.max_records < 0:
            raise ValueError("max_records 必须 >= 0")

    def check_pages(self, pages_done: int) -> None:
        if self.max_pages is not None and pages_done > self.max_pages:
            raise RunLimitExceededError("max_pages_exceeded")

    def check_records(self, records_done: int) -> None:
        if self.max_records is not None and records_done > self.max_records:
            raise RunLimitExceededError("max_records_exceeded")

    def next_page_allowed(self, pages_done: int) -> bool:
        return self.max_pages is None or pages_done < self.max_pages


def limits_from_task(task: WorkbenchTask | None) -> RunLimits:
    if task is None:
        return RunLimits()
    return RunLimits(
        max_pages=task.max_pages,
        max_records=task.max_records,
    )


async def resolve_run_limits(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
) -> RunLimits:
    task = await session.scalar(
        select(WorkbenchTask)
        .join(
            WorkflowVersion,
            WorkflowVersion.workbench_task_id == WorkbenchTask.id,
        )
        .join(Run, Run.workflow_version_id == WorkflowVersion.id)
        .where(Run.id == run_id)
    )
    return limits_from_task(task)


__all__ = [
    "RunLimits",
    "limits_from_task",
    "resolve_run_limits",
]
```

在 `services/exceptions.py` 中复用 Task 4 已加入的 `RunLimitExceededError`；若实现顺序调整，则补以下定义：

- [ ] **Step 4: C6/collector 交接（C5 不改执行器）**

C6 必须按以下顺序接线：

1. 在 attempt 开始前调用 `limits = await resolve_run_limits(session, run_id=run.id)`。
2. 把 `limits` 或 `limits.max_pages` / `limits.max_records` 传给 `RunCollectorCall` 与 `execute_collector_call`；`None` 原样传 `None`，不得替换为 `0` 或任意默认值。
3. collector 每次请求下一页前调用 `limits.next_page_allowed(pages_done)`；为 `False` 时停止翻页，不得再发请求。
4. 每页入库后调用 `limits.check_records(total_records)`；超限时立即抛 `RunLimitExceededError`，把 attempt 标记失败（错误码取 `max_pages_exceeded` / `max_records_exceeded`），不得继续写剩余记录。
5. `max_pages` 与 `max_records` 只来自 C4 `workbench_tasks`；C5 不提供默认值，C6 不得自行放宽。

- [ ] **Step 5: 跑测试并提交**

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_run_limits.py -v
uv run ruff check src/data_intelligence_hub/services/run_limits.py \
  src/data_intelligence_hub/services/exceptions.py \
  tests/unit/test_run_limits.py
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "RunLimits" --direction upstream --repo .
node .gitnexus/run.cjs detect-changes --scope all --repo .
git add apps/api/src/data_intelligence_hub/services/run_limits.py \
  apps/api/src/data_intelligence_hub/services/exceptions.py \
  apps/api/tests/unit/test_run_limits.py
git commit -m "feat(budget): add C4 run limits for pages and records"
```

Expected: 全部通过；`detect-changes` 不含 `partial: true` / `truncated: true`。

---

### Task 10: 全量验证、GitNexus 与 C14 交接

**Files:**
- No code files. Test output is captured in the task execution log, not written as a report file.

**Interfaces:**
- Consumes: C5 全部任务。
- Produces: 可复核的测试输出、GitNexus 变更报告、A/B 迁移与 `tool_prices` 种子门禁记录。

- [ ] **Step 1: Run the full unit suite**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit -q
```

Expected: `0 failed`。若出现新失败，先修到全绿。不得用“基线失败”解释新失败。

- [ ] **Step 2: Run the integration suite**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/integration -q
```

Expected: `0 failed`。

- [ ] **Step 3: Run the focused C5 suite with verbose output**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest \
  tests/unit/test_tool_prices.py \
  tests/unit/test_pricing.py \
  tests/unit/test_quota_accounts.py \
  tests/unit/test_tool_calls.py \
  tests/unit/test_run_authorizations.py \
  tests/unit/test_run_ledger.py \
  tests/unit/test_budget_service.py \
  tests/unit/test_budget_migration_source.py \
  tests/unit/test_run_budget.py \
  tests/unit/test_run_limits.py \
  tests/unit/test_workbench_approvals.py \
  tests/unit/test_quota_routes.py \
  tests/unit/test_price_coverage_report.py \
  tests/unit/test_usage_service.py \
  tests/unit/test_run_executor.py \
  tests/integration/test_budget_ledger_pricing.py \
  -v
```

Expected: 全部 PASS。保存完整输出到执行报告。

- [ ] **Step 4: Run lint and type checks**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run ruff check src tests
uv run mypy src/data_intelligence_hub/models/tool_price.py \
  src/data_intelligence_hub/repositories/tool_prices.py \
  src/data_intelligence_hub/scripts/seed_tool_prices.py \
  src/data_intelligence_hub/scripts/price_coverage_report.py \
  src/data_intelligence_hub/services/pricing.py \
  src/data_intelligence_hub/services/budget_service.py \
  src/data_intelligence_hub/services/run_authorizations.py \
  src/data_intelligence_hub/services/run_limits.py \
  src/data_intelligence_hub/services/workbench_approvals.py \
  src/data_intelligence_hub/services/tool_call_service.py \
  src/data_intelligence_hub/repositories/quota_accounts.py \
  src/data_intelligence_hub/repositories/tool_calls.py \
  src/data_intelligence_hub/repositories/workbench_approvals.py
```

Expected: ruff `All checks passed!`。mypy `Success: no issues found`。

- [ ] **Step 5: Verify the single Alembic head**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run alembic heads
```

Expected:

```text
202610220061 (head)
```

`alembic branches` 必须为空：

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run alembic branches
```

Expected: 空输出。

- [ ] **Step 6: Run GitNexus impact on every modified symbol**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs impact "ToolPrice" --direction upstream --repo .
node .gitnexus/run.cjs impact "refresh_price_book" --direction upstream --repo .
node .gitnexus/run.cjs impact "quote" --direction upstream --repo .
node .gitnexus/run.cjs impact "reserve_run_budget" --direction upstream --repo .
node .gitnexus/run.cjs impact "settle_run_cost" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_order_run_authorizations" --direction upstream --repo .
node .gitnexus/run.cjs impact "ensure_order_run_authorization" --direction upstream --repo .
node .gitnexus/run.cjs impact "RunLimits" --direction upstream --repo .
node .gitnexus/run.cjs impact "WorkbenchApprovalAction" --direction upstream --repo .
node .gitnexus/run.cjs impact "create_approval_action" --direction upstream --repo .
node .gitnexus/run.cjs impact "decide_approval_action" --direction upstream --repo .
node .gitnexus/run.cjs impact "record_tool_call" --direction upstream --repo .
node .gitnexus/run.cjs impact "get_usage_summary" --direction upstream --repo .
node .gitnexus/run.cjs impact "RunExecutor" --direction upstream --repo .
```

Expected: 所有结果为 LOW 或 UNKNOWN。UNKNOWN 必须用文本搜索确认调用者。不得出现 HIGH/CRITICAL。出现 HIGH/CRITICAL 时停止并写出回滚方案。

- [ ] **Step 7: Run GitNexus change analysis**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 输出包含 `models/tool_price.py`、`models/workbench_approval.py`、`repositories/tool_prices.py`、`repositories/workbench_approvals.py`、`scripts/seed_tool_prices.py`、`services/pricing.py`、`services/budget_service.py`、`services/run_authorizations.py`、`services/run_limits.py`、`services/workbench_approvals.py`、`repositories/quota_accounts.py`、`repositories/tool_calls.py`、`alembic/versions/202610220061_budget_ledger_pricing.py`。`partial` 与 `truncated` 必须为 false。任一为 true 时重跑；重跑仍为 true 时停止提交。

- [ ] **Step 8: 交 PG0 发布批次执行生产门禁，C14 只读验收（C5 不部署）

以下生产备份、迁移、种子、compose/env 变更、重启与开关切换全部由总索引 §8.4 的 PG0 发布批次执行并留存证据；C5 不执行 ssh、git fetch、alembic upgrade 或 docker compose 命令，C14 只做只读健康检查与浏览器验收，不得执行任何写操作，也不写生产记录文件。

**1. PostgreSQL 16 并发与对账证据（PG0 发布批次执行）**

- 两个会话同时 `reserve_run_budget` 同一项目，只有一个成功，`quota_accounts.reserved_usd` 不超卖。
- 两个会话用同一账本 `idempotency_key` 写 `settle`，只落一行。
- 一个 run 的两个 attempt（一失败一成功）结算后，`quota_accounts.used_usd` 等于两条 `task_runs.total_cost_usd` 之和；`run_ledger_entries` 的 `settle` 合计等于同一金额。
- `mark_result_unknown` 与 `cancel_reservation` 后，`reserved_usd` 归零。
- 空库迁移循环：PostgreSQL 16 空库 `upgrade 202610220061` → `downgrade 202610220060` → `upgrade 202610220061`，三次退出码 0，`alembic heads` 单行。
- 空表启动门禁：升级后、种子前启动 API 必须失败并报 `price_book_empty`；运行种子后启动成功。

**2. 生产 A（PG0 发布批次执行）**

- 主机 `ubuntu@43.163.92.244`。
- Modify: `configs/deploy/scrapy/docker-compose.yml`（只追加 C5 默认关闭的静态环境变量映射；PG0 发布批次设置生产值）
- Test: `apps/api/tests/unit/test_budget_deploy_facts.py`
- 环境文件 `/opt/data-achieve-scrapy/.env.production`。
- 先备份 `pg_dump`、`.env.production`、镜像 ID 与 `HEAD`。
- 迁移前确认 schema head 是 `202610220060`；不是时停止。
- `alembic upgrade head` 后运行 `python -m data_intelligence_hub.scripts.seed_tool_prices`，再启动 API。
- 种子后核对：`SELECT count(*) FROM tool_prices WHERE effective_to IS NULL;` 必须等于 `price_book_v1.json` 的 entries 数（当前 227）；`SELECT DISTINCT price_book_version FROM tool_prices WHERE effective_to IS NULL;` 只能有一行 `price_book.v1`。
- 启动日志必须包含 `price_book_locked`，指纹非空，`entries` 等于当前有效 `tool_prices` 行数（当前 227）。
- 健康检查 `schema_revision=schema_head=202610220061`。
- 不重建 edge；只允许 `up -d --no-deps api console` 或 `restart edge`。

**3. 生产 B（PG0 发布批次执行）**

- 主机 `ubuntu@101.34.52.232`。
- Compose `configs/deploy/scrapy/docker-compose.yml`（静态映射由 C5 代码提交；A/B 共用；不修改 `configs/deploy/scrapy-new/**`）。
- 分支 `deploy/tiktok-cdo-codex`；拉取失败时按仓库运维手册重试，不得改写 `.env.production`。
- 必须取得 B 的目标授权与备份；迁移前确认 schema head 是 `202610220060`。
- 迁移后运行同一 `seed_tool_prices`，核对 227 行与单一 `price_book_version`，再启动 API。
- 健康检查 `schema_revision=schema_head=202610220061`。

**4. 浏览器 `/settings` 与任务工作台内联批准验收（只读）**

- 打开 A 与 B 的 `/settings`。
- 额度卡片显示 daily limit、reserved、used、remaining 四个值。
- 新建一个项目后，额度为 0，页面显示 0 而不是 500。
- 调用未定价端点时必须返回 422 `tool_not_priced`。PG0 前 shadow 演练可以显示 `tool_not_priced_shadow` 提示，但不得显示 0 成本；PG0 验收时 `STRICT_PRICE_ENABLED=true`，不得再出现 shadow 回退。
- 打开任务工作台：owner/admin 能看到 `workbench_approval_actions` 的内联批准/拒绝按钮；requester 只能看到自己的 pending 动作，不能批准；不得存在独立收件箱页面或未登记路径。
- 用 member 会话直接调用 decide 路径必须返回 403 `approval_self_approval_forbidden` 或 `project_management_forbidden`；跨项目返回 403 `project_access_forbidden`，跨工作区返回 404 `project_not_found`。

**5. 开关顺序（PG0 必须严格模式）**

- PG0 之前只允许 shadow 演练：`BUDGET_ENFORCEMENT_ENABLED=false` 且 `STRICT_PRICE_ENABLED=false`。shadow 只用于迁移前演练，不得作为 PG0 交付状态。
- PG0 发布批次在迁移后先运行 `seed_tool_prices`，确认 `tool_prices` 有 227 行且版本单一，再由 owner 显式设置项目额度。
- PG0 发布批次必须把 `BUDGET_ENFORCEMENT_ENABLED=true` 与 `STRICT_PRICE_ENABLED=true` 同时写入目标环境，并重启 API；任一开关为 `false` 时 PG0 验收失败，不得进入付费试点。
- compose 映射与 `Settings` 的 `validation_alias` 必须使用同一组精确变量名，不加 `SCRAPY_` 前缀：

```yaml
BUDGET_ENFORCEMENT_ENABLED: ${BUDGET_ENFORCEMENT_ENABLED:-false}
STRICT_PRICE_ENABLED: ${STRICT_PRICE_ENABLED:-false}
```

`.env.production` 也写这两个名字；不得改成 `SCRAPY_` 前缀或任何其他前缀，否则 Settings 读不到开关。
- `true/true` 后运行 `price_coverage_report.py`，确认 `unpriced` 清单与 `missing_count`。价格来源是 `tool_prices`；fixture 只用于种子，不参与运行时报价。未定价端点必须 422，不得补猜价格。
- 任一开关回退即回到 PG0 前状态，按回滚步骤执行；不得只在单台生产保留严格模式。

**6. 回滚**

- 先设 `BUDGET_ENFORCEMENT_ENABLED=false` 与 `STRICT_PRICE_ENABLED=false`，再回退镜像。
- `202610220061` 的 downgrade 只在 `tool_prices`、`quota_accounts`、`tool_calls`、`workbench_approval_actions` 无新业务数据时执行；有数据时保留表。
- downgrade 会删除 `tool_prices`；重新升级后必须重跑 `seed_tool_prices` 恢复价格，不得手工写价格 SQL。
- 不删除或改写 `run_ledger_entries` 历史行。


- [ ] **Step 8A: 提交静态 compose 映射与门禁测试**

Create `apps/api/tests/unit/test_budget_deploy_facts.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_budget_switches_are_mapped_into_shared_compose() -> None:
    text = (ROOT / "configs/deploy/scrapy/docker-compose.yml").read_text(encoding="utf-8")
    assert "BUDGET_ENFORCEMENT_ENABLED: ${BUDGET_ENFORCEMENT_ENABLED:-false}" in text
    assert "STRICT_PRICE_ENABLED: ${STRICT_PRICE_ENABLED:-false}" in text
    assert "configs/deploy/scrapy-new" not in text


def test_budget_switch_examples_use_exact_names() -> None:
    text = (ROOT / "apps/api/.env.example").read_text(encoding="utf-8")
    assert "BUDGET_ENFORCEMENT_ENABLED=false" in text
    assert "STRICT_PRICE_ENABLED=false" in text
    assert "SCRAPY_BUDGET_ENFORCEMENT_ENABLED" not in text
    assert "SCRAPY_STRICT_PRICE_ENABLED" not in text
```

Add to `configs/deploy/scrapy/docker-compose.yml` under `api.environment`:

```yaml
      BUDGET_ENFORCEMENT_ENABLED: ${BUDGET_ENFORCEMENT_ENABLED:-false}
      STRICT_PRICE_ENABLED: ${STRICT_PRICE_ENABLED:-false}
```

Append the same exact names with `false` values to `apps/api/.env.example`.

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5/apps/api
uv run pytest tests/unit/test_budget_deploy_facts.py -v
cd /Users/lute/Project/data_scrapy-gov-c5
git add configs/deploy/scrapy/docker-compose.yml apps/api/.env.example \
  apps/api/tests/unit/test_budget_deploy_facts.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "ops(budget): map strict budget switches"
```

Expected: `2 passed`; compose mappings default to false; `partial` and `truncated` are false. This commit does not set production values or restart services; PG0 release batch does that.

- [ ] **Step 9: Final check**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c5
git status --short
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 工作树只包含计划文件；`detect-changes` 无 `partial` 与 `truncated`。C5 完成。

## Self-Review

**Spec coverage:**

- `tool_prices` 作为唯一价格事实源：建表、ORM、仓储、迁移与种子脚本在 Task 1、Task 7；运行时读取只在 Task 1 的 `pricing`。
- fixture 只作种子：Task 1 的 `seed_tool_prices_from_fixture`、Task 8 的源码守卫、Task 8A 的覆盖报告措辞。
- 无第二价格源：Task 1（禁止运行时读 fixture）、Task 8（`test_no_runtime_fixture_price_reads`）、Task 8A（报告只读 `tool_prices` 快照）。
- 进程级价格锁、严格缺价失败与 shadow/enforce：Task 1、Task 8、Task 8A。
- `quota_accounts`、回填与懒创建：Task 2、Task 7。
- `tool_calls`、`start_tool_call` / `complete_tool_call`：Task 3、Task 3A、Task 7。
- `estimate` / `reserve` / `settle` / `release` / `block`：Task 6。
- 冻结八列六枚举：Task 5、Task 7。
- 唯一账本写入者：Global Constraints；Task 6；Task 9 的 `OrmRunBudget` 只调用 `budget_service`。
- `remaining_budget` 写 `task_runs`：Task 6、Task 9。
- 多 gate `authorizations` 与 `uq_authorizations_run_gate`：Task 4、Task 7；blocked G-Plan 不建 pass。
- C4 订单预算拆分：`create_order_run_authorizations` 在 Task 4；逐市场金额之和精确等于 `workbench_tasks.max_cost_usd`；主市场取得十进制余数；空上限为 0 并在 enforce 下阻断；不读取默认上限。
- C4 执行限额：Task 9A 的 `RunLimits` / `resolve_run_limits`；`None` 不限制、`0` 零容忍；C6/collector 超限立即停止。
- 内联批准动作：Task 4A 的 `workbench_approval_actions` 与两个 C1 路径；requester 不得自批；无未登记路径。
- 项目 ACL：Task 4A、Task 8A 与 Task 4 的 `get_run_authorization_for_actor`；同工作区 cross-project 403，跨工作区 404。
- 统一 C2 审计：Task 1（`budget.price.changed`）、Task 4/4A（`budget.limit.changed`）、Task 6（`budget.blocked` / `budget.released` / `budget.limit.changed`）；只写 `audit_events`。
- PG0 严格模式：Task 10 要求 `BUDGET_ENFORCEMENT_ENABLED=true` 与 `STRICT_PRICE_ENABLED=true`；shadow 只允许 PG0 前演练；生产写操作归 PG0 发布批次，C14 只读。
- quota 端点：Task 8A。
- `usage_service` 统一：Task 8。
- 一个迁移 061：Task 7。
- 不改运行步骤、执行器与 MCP：Global Constraints；Task 9 不修改执行器文件。
- 并发原子预算：Task 2、Task 6、Task 10（PG0 发布批次的 PostgreSQL 证据）。
- 重复结算：Task 6。
- 未知结果 / overage / 取消释放 quota：Task 6、Task 9。
- 生产 A/B 门禁、`tool_prices` 种子与部署：Task 10（PG0 发布批次执行；C14 只读验收；C5 不部署）。

**占位符扫描:** 计划中没有未完成标记、延后实现、跨任务省略或“按上文补测试”的步骤。所有代码步骤给出实际代码。唯一的环境变量是生产数据库 URL，由执行环境提供。

**Type consistency:** `ToolPrice`、`PriceQuote`、`BudgetEstimate`、`BudgetReservation`、`BudgetSettlement`、`QuotaAccount`、`ToolCall`、`RunBudget` 的字段与函数签名在各任务中一致。`ToolPrice` 严格使用 C1 的 13 列与 `(tool_id, currency, price_book_version)` 唯一键，`PriceQuote.tool_id` 与 `ToolPrice.tool_id` 同名。`PriceQuote.price_book_fingerprint` 来自 `pricing.price_book_fingerprint()`，与 `refresh_price_book(session)` 锁定的当前有效 `tool_prices` 快照一一对应。`ToolNotPricedError.message` 固定为 `tool_not_priced`；价格锁冲突固定为 `price_book_locked`；未锁定固定为 `price_book_not_locked`；空表固定为 `price_book_empty`。`settle` 正数、`release` 负数在模型、仓储、服务与测试中一致。`authorizations` 的唯一键是部分唯一索引 `(run_id, gate_id)`（`WHERE run_id IS NOT NULL`，`uq_authorizations_run_gate`），不是 `run_id` 单列唯一；`get_run_budget_authorization` 只返回 `G-Cost/pass`；`has_blocked_gate` 只看 `gate_status='blocked'`。`RunBudget.settle` 不接收金额，由 `settle_run_cost` 汇总该 run 全部 attempt 的 `task_runs.total_cost_usd`。全计划只有一个价格事实源 `tool_prices`；`price_book_v1.json` 只被种子脚本读取，运行时没有 fixture 回退，也没有第二价格表。`create_order_run_authorizations` 的逐市场金额使用 `Decimal` 与 6 位小数，所有行之和等于订单上限；主市场余数只加一次。`RunLimits.max_pages` / `max_records` 的 `None` 与 `0` 语义在服务、测试与 C6 交接中一致。`workbench_approval_actions` 的 13 列、3 个 CHECK、2 个索引与 C1 逐字一致；C5 不新增批准路径。`run_ledger_entries` 仍是八列六枚举，`settle > 0`、`release < 0`，C5 仍是唯一账本写入者与 `RunBudget` 权威来源。

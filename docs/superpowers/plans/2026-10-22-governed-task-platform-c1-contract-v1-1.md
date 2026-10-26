# 受治理任务平台 C1 契约 v1.1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 C2-C14 需要的全部表、列、枚举、接口路径、客户 MCP 八工具、错误码、canonical profile 和报告/交付 schema 登记到冻结契约 v1.1，并建立可执行的机器 registry 与 checker。

**Architecture:** 冻结契约 Markdown 是唯一权威。契约附录内嵌一个 `contract-registry` JSON 块。`scripts/contract_registry.py` 从 Markdown 提取该块，校验结构，生成 `configs/contracts/v1.1.0/registry.json`。checker 比对生成物与 Markdown，检查跨文档一致性。C1 不写迁移；唯一运行时改动是统一 B5 报告合同 schema、Pydantic 模型与 canonical 常量。

**Tech Stack:** Markdown、JSON Schema draft 2020-12、Python 3.12、pytest、ruff、GitNexus CLI。

## Global Constraints

- 只改契约、PRD、Playbook、机器 registry、checker、tests，以及报告合同的三个既有 B5 契约文件：`apps/api/schemas/report_contract.schema.json`、`apps/api/src/data_intelligence_hub/schemas/report_contract.py`、`apps/api/tests/unit/test_report_contract.py`。禁止改其他 `apps/api/src/**`、`apps/api/alembic/**`、`apps/web/**`。
- 冻结契约 Markdown 是唯一权威。`configs/contracts/v1.1.0/registry.json` 是生成物。禁止手改生成物。契约附录 A 是 Markdown 内的机器投影；附录 A 与正文冲突时以正文为准，生成物与 Markdown 冲突时以 Markdown 为准。
- 报告合同 schema 只有一份：`apps/api/schemas/report_contract.schema.json`。C1 更新这一份并把 `schema_version` 升到 `1.1.0`；不得创建 `configs/contracts/v1.1.0/report_contract.schema.json`，不得保留第二份报告合同 schema。
- 唯一 canonical 常量，全部从 `apps/api/src/data_intelligence_hub/schemas/report_contract.py` 导出：`CANONICAL_PROFILE_ID = "dih-canonical-json-v1"`、`CANONICAL_PROFILE = CANONICAL_PROFILE_ID`、`SCHEMA_VERSION = "1.1.0"`。C7、C9、C10 只 import 这三个名字；不得另写常量、第二套 canonicalizer 或第二个 profile ID。C8 复用 `schemas/report_contract.canonical_json_bytes`，不得在 `contracts/canonical_json.py` 另写 RFC 8785 实现。
- 消费者对齐：C7/C9/C10 的常量测试必须断言上述单一组值。C9 计划中 `CANONICAL_PROFILE in {"RFC8785", "DIH-CJ-1.0"}` 的二选一断言是早期草案；执行 C9 时以本计划的 `dih-canonical-json-v1` + `1.1.0` 为准，不得新增第二套常量或第二份 canonicalizer。
- `tool_prices` 是正式 C5 表：登记完整列、约束、索引，并进入 `phases[].objects`；由 C5 在其迁移中建表。价格初始值来自 `tool_catalog/fixtures/price_book_v1.json`。`mcp_customer_request_leases` 仍标 `deferred`：不建表、不登记为 `tables`、不进入 `phases[].objects`；客户 MCP 租约不持久化，C13 不得要求 C1 代建迁移。
- MFA 延期：C1 不登记 `mfa_required`，不定义 `require_recent_mfa`。C12 计划中的 MFA 依赖与 MFA 错误码从 PG0 删除，相关功能开关保持关闭；MFA 作为 PG0 后事项单独提案。
- 新表、新列、新枚举值、新接口路径、新 MCP 工具、新错误码必须先登记契约，再进入 C2-C14 实现。
- **ReportContract 只有一个 1.1 形状。** B5 嵌套组保持原字段名与必填集合：`identity` 必填 `task_id`、`brand`、`category`、`markets`、`window`；`coverage` 必须是 `{"cells": [...]}`；`coverage.cells[]` 必填 `source_tool_id`、`market`、`window`、`record_count`、`frame_member_count`、`status`。1.1 只新增顶层键，不改这三个嵌套组的名字或必填项。顶层 `task_id` 是唯一权威业务键；`identity.task_id` 是 B5 兼容镜像，必须等于顶层。C9 assembler 同时写两处；C9/C10 只读顶层 `task_id`，不得读 `identity.task_id`。
- **报告生命周期不可变。** 草稿合同必须携带合法的 `review`、`acceptance`、`delivery` 占位组（nil UUID 与 64 位零哈希，状态 `draft` / `pending`）。审核通过后创建新的取代版本，只填写 `review` 组；交付发布后创建再下一个取代版本，只填写 `acceptance` 与 `delivery` 组。`status='published'` 的合同、HTML、SOP 与哈希不得原地修改；只允许同一事务内 `status` 转 `superseded` 并写 `superseded_at`。C9 负责 `create_reviewed_contract_version` 与 `create_delivery_contract_version`，C10 调用后者，不得自行改合同 JSON。
- **内部审核人不是客户工作区角色。** C1 登记 `report_reviewer_assignments` 表与内部审核路径。审核主体只有 `assignment_scope IN ('report_read','report_review')` 的受限读范围；审核事件 `reviewer_role` 固定写 `internal_reviewer`。客户 `owner`、`admin` 不得自审，`member` 不获得审核角色；不得新增客户侧 `reviewer` 角色。C9 的 `record_review` 与 C10 的 `validate_review_signoff` 都只认 active assignment。指派必须有非空 `expires_at`；读与审核路径在 `expires_at <= now` 时返回 403 `reviewer_assignment_expired`。
- **owner/admin 批准动作内联在任务工作台。** 预算超支、加购与项目密钥变更使用 `workbench_approval_actions` 表，绑定 `task_id`，由 owner/admin 在任务工作台内联批准或拒绝。请求人不得自批（数据库 CHECK 与服务层双重校验）。不建独立收件箱页面或独立 inbox 路径；C14 只消费这些内联动作。
- **C9/C10/C11 公开错误码先登记。** 至少登记 `report_quality_not_ready`、`delivery_not_publishable`、`delivery_input_invalid`、`publish_forbidden`、`idempotency_key_required`、`dataset_export_internal_isolated_source`，以及 C9 路由实际返回的 `report_contract_not_published`、`report_contract_hash_mismatch`、`report_contract_invalid`、`report_artifact_not_draft`、`report_artifact_incomplete`、`report_artifact_integrity_failed`、`report_review_required`、`report_publish_gate_blocked`、`report_revision_target_invalid`、`reviewer_assignment_required`、`reviewer_self_review_forbidden`、`reviewer_assignment_invalid`、`reviewer_assignment_expired`、`report_forbidden_language`。C9/C10/C11 不得返回未登记的错误码。
- **审计动作注册表只有一个。** 契约正文 `### 2.10 审计动作注册表` 与附录 A 的 `audit_actions` 对象是唯一权威，版本 `audit-actions.v1`。每个动作只有一个写入 owner；`services.audit_log.AUDIT_ACTIONS` 必须与注册表逐字一致。未登记动作抛 `audit_action_unregistered`（500），形状非法抛 `audit_action_invalid`。下游切片只调用 `append_audit_event`，不得自造动作名，不得建第二张审计表；`run.created` 只能经 C4 `services/run_creation.create_run_with_audit` 接缝写入，C6 旧入口收敛调用该接缝。`audit_events` 仍是唯一审计表；内部审阅者不是客户角色。
- **C6/C8/C9/C10 修复前置先登记。** C6 取消幂等只使用 `runs.cancel_idempotency_key_hash`、`runs.cancel_reason_code` 与 `uq_runs_workspace_cancel_idempotency`，全部落在迁移 `202610220064`；C8 模板能力白名单只存在代码注册表 `TaskTemplate.capability_allowlist`，不建表；C9 Quick 2 小时方向稿复用报告合同 1.1 与 `report_artifacts` 生命周期，不新增客户工具、不重复计费、证据上限 L3、不出现 `confirmed`、不启动验收；C10 验收只追加 `report_audit_events`，幂等键哈希与 payload 摘要只写 `metadata_json`，manifest 与交付文件不可变，相关列只落在迁移 `202610220068`；C9/C10 PII 发布失败只复用 C11 的 `export_policy.v1` 与 `scan_export_policy()`/`scan_export_value()`。C1 不新增迁移，不新增取消表、验收表、模板能力表或第二套 PII 规则。
- **唯一禁用语言画像。** C1 只登记一个 `forbidden_language_profile`：`profile_id` 固定 `dih-descriptive-language-v1`，`profile_version` 固定 `1.0.0`，`source` 只写已批准设计 §5.7。画像只禁止因果表述（导致、驱动、提升、降低、造成、证明及精确英文对应词）与销量、市场份额、转化率、营收预测；允许描述性相关、共同出现和描述性差异。C9 发布前必须消费该画像；C10 可以复用同一画像，但 C1、C9、C10 都不得定义第二份术语表或第二个画像。命中时 C9 返回 `report_forbidden_language`；C10 返回 `delivery_input_invalid` 并附同一 `profile_id`。不得为画像增加任何阈值、计数或评分规则。
- **页面路由只有一份事实源。** 契约 §5 的 11 条页面路由（10 条启用、1 条禁用）与 4 条一级导航是唯一事实源。附录 A 的 `page_routes` 与 `primary_nav` 是 §5 的机器投影；C14 的 `contract-routes.test.ts` 必须解析 §5 的两个 `text` 代码块并与 `CONTRACT_ROUTES` 逐条比较，`PRIMARY_NAVIGATION` 测试必须解析 §5 的一级导航表并与 4 条导航逐条比较。C14 不得在代码或测试里维护第二份路由或导航清单。页面路由不是 API 路径：不得写入 `paths`，不得以 `/api/` 开头。动态段名固定为 `/capabilities/[toolId]`、`/reports/[artifactId]`、`/workbench/[taskId]`，公开分享固定为 `/reports/public/[id]` 且禁用；不得用 `[id]` 代替前三个段名。
- 任务包包型与市场角色持久化：`workbench_tasks.package_type` 只有 `quick`、`standard`；`primary_market` 与 `comparison_markets` 是市场角色事实源。`runs` 只登记 `market_code`；不得登记 `runs.market_role` 或 `runs.package_type`，角色由任务单派生（主市场为 `primary`，对比市场为 `compare`）。Quick 最多 1 个对比市场，Standard 最多 3 个；不得新增其他产品阈值。
- **C4 任务单创建契约必须完整登记。** `workbench_tasks` 还必须有 `seed_products`（JSON，非空，默认空数组）、`target_price_band`（JSON，可空）与 `idempotency_key_hash`（`string(64)`，可空），以及工作区级部分唯一索引 `uq_workbench_tasks_workspace_idempotency (workspace_id, idempotency_key_hash) WHERE idempotency_key_hash IS NOT NULL`。`seed_products` 非空时必须有 3–10 项公开链接或平台 ID。`target_price_band` 使用市场原币，至少一个边界，`min_amount <= max_amount`，金额非负，币种三个大写字母。`acceptance_contact_id` 可空；空值回落到任务 `owner_id`，非空必须是同工作区 `owner` 或 `admin`，`member` 返回 422 `acceptance_contact_not_member`。
- **任务单创建幂等语义必须先登记。** `workbench.tasks.create` 必须登记 `idempotent: true`、`Idempotency-Key` 请求头与 `idempotency_conflict` 错误码。头缺失或空值返回 422 `invalid_request`；`idempotency_key_hash = sha256("workbench-task-create.v1:{key}")`；同一工作区、同一键、同一请求摘要返回已有任务（200，响应头 `Idempotent-Replay: true`）；同一键不同摘要返回 409 `idempotency_conflict`。请求摘要由服务层对规范化请求字段计算，并从已持久化任务行重建；不新增第二个摘要列。
- **初始计划版本接缝先登记。** `workflow_versions.workbench_task_id` 用复合外键指向 `workbench_tasks(workspace_id, project_id, id)`；`workflow_versions.plan_payload["execution_steps"]` 是 C4 版本创建时生成的不可变步骤快照。C4 的 `create_initial_workflow_version_for_task(session, *, workspace_id, project_id, created_by_user_id, workbench_task_id, idempotency_key)` 只调用既有 workflow planner 创建并批准首个版本；已有版本时复用。C1 只登记该接缝，不实现 planner。
- **C4 新增对象只落在迁移 `202610220062`。** `workbench_tasks` 的上述列与索引、`workflow_versions.workbench_task_id`、`runs.market_code` 与 `uq_runs_workflow_version_market` 全部由 C4 的唯一迁移 `202610220062_workbench_task_submission.py` 创建（`down_revision = "202610220061"`）。C1 不新增迁移，不新增第二份摘要表，不新增第二个 C4 迁移号。
- `run_ledger_entries` 只有八列：`id`、`run_id`、`step_id`、`entry_kind`、`amount_usd`、`balance_after_usd`、`idempotency_key`、`created_at`。不得增删列。
- `entry_kind` 只有六值：`estimate`、`reserve`、`accrued`、`settle`、`release`、`block`。
- `settle` 必须是正数实际成本。`release` 必须是负数修正。`estimate`、`reserve`、`accrued`、`block` 不计入实际成本。
- `remaining_budget = max_cost_usd - SUM(amount_usd WHERE entry_kind IN ('settle','release'))`。允许为负，不得截断为零。
- 客户 MCP 只有八个工具：`discover_capabilities`、`estimate_task`、`create_task`、`get_task`、`cancel_task`、`get_delivery_manifest`、`get_evidence`、`collect`。
- 客户 MCP 路径是 `/mcp/customer`。客户 REST 只读面在首期延期。内部端点级工具不得出现在客户 `tools/list`、客户文档和客户 SDK。
- 客户任务包、客户 MCP、客户交付链禁止接收客户 Cookie。`tiktok.creator_cookie` 只能留在内部控制台范围。
- 金额列使用 `numeric(12,6)`。禁止 float。时间使用 RFC 3339 UTC，后缀 `Z`。
- 文档正文写中文。机器标识、字段名、枚举值写英文 snake_case。
- 每个 task 先写失败测试。运行测试并确认失败。写最小实现。运行测试并确认通过。再 commit。
- 每个 task 可独立评审。每个 task 结束时测试全绿，registry 可生成。
- 提交前必须运行 `python scripts/contract_registry.py check --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --registry configs/contracts/v1.1.0/registry.json`。
- 提交前必须运行 `node .gitnexus/run.cjs detect-changes --scope all --repo .`。`partial: true` 或 `truncated: true` 不算通过，必须重跑。
- 改既有符号前必须运行 `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .`。本计划只新增脚本、测试和文档；不编辑既有运行时代码符号。
- 每个步骤给出实际内容；占位符扫描必须通过。
- 当前基线：C0 标签 `pg0-baseline-v1`，Alembic 单头 `202610210057`。Task 1 Step 0 是唯一开工入口：从主工作树 `/Users/lute/Project/data_scrapy` 运行 `git worktree prune`，再运行 `git worktree add /Users/lute/Project/data_scrapy-gov-c1 -b feat/gov-c1 pg0-baseline-v1`，然后在 `/Users/lute/Project/data_scrapy-gov-c1` 内执行 `cd apps/api && uv sync`。此后所有 Run/Commit 命令的根目录是 `/Users/lute/Project/data_scrapy-gov-c1`，包括 `apps/api` 子路径；不得在 `feat/tool-catalog-catalog`、`main`、`f0560ca` 或主工作树 `/Users/lute/Project/data_scrapy` 上直接执行（仅允许 `cp` 读取主工作树中的本计划）。
- 开工断言：`git rev-parse --verify pg0-baseline-v1^{commit}` 成功；`cd apps/api && uv run alembic heads` 只有 `202610210057 (head)`；`git merge-base --is-ancestor feat/b5-workbench HEAD` 退出码 0。任一不成立就停止，先完成 C0。
- C0 已合入 B5。C1 只登记对象，不重新合并 B5，不新建或修改迁移。
- C1 不创建任何数据库迁移。C13 的速率与并发租约由 C13 按现有配置实现，不新增表。若 C13 确需持久化租约，必须先修订 C13 计划并单独申请迁移，不得让 C1 代建。
- 回滚点：契约版本与 `registry.json` 是单一回滚点。回滚时恢复到 C0 标签的契约与 B5 schema，并重新生成 registry；不得手改生成物。C1 不处理生产数据回滚。
- 本切片不直接部署：C1 只交付契约、机器 registry 与 checker。生产 A/B 的备份、迁移、compose/env 修改、重启与开关切换只由 PG0 发布批次执行；控制台实现属于 C14，由 PG0 批次部署；C14 只做只读健康、canary 前置与浏览器验收。C1 不包含浏览器操作、截图或逐页验收。

## C2-C14 工作包边界（非权威）

> **非权威：** 本表是早期分工草案，已被 master plan §1 与 §5 取代。冲突时以 master plan 为准。保留本表只为说明对象归属，不用于迁移号、依赖或完成判据。

本计划使用以下 13 个工作包。每个对象的 `phase` 字段必须取这里的 ID。C1 只登记对象，不实现行为。

| ID | 工作包 | 范围 | C1 必须登记的对象 |
|---|---|---|---|
| C2 | 身份、项目 ACL 与统一审计 | 工作区角色、项目成员、追加式审计、请求 ID | `project_members`、`audit_events`、`workspace_members.role`、审计路径、身份错误码、审计动作注册表 |
| C3 | 项目密钥与项目级凭据 | 密钥状态、轮换、能力白名单、项目级凭据、Cookie 元数据 | `project_api_keys` 扩展、`platform_credential_bundles` 扩展、密钥与凭据路径 |
| C4 | 任务单提交、计划关联与幂等 | 七槽位任务单、包型与主/对比市场、种子商品、目标价格带、创建幂等、初始计划版本接缝、逐市场 run 幂等 | `workbench_tasks`（含 `package_type`、`primary_market`、`comparison_markets`、`seed_products`、`target_price_band`、`idempotency_key_hash`、`uq_workbench_tasks_workspace_idempotency`）、`workflow_versions.workbench_task_id`、`workflow_versions.plan_payload.execution_steps`、`runs.market_code`、任务单路径与 `Idempotency-Key` 语义 |
| C5 | 预算、账本与定价 | 单价、额度账户、调用记录、按 run 授权、账本符号 | `tool_prices`、`quota_accounts`、`tool_calls`、`authorizations.run_id`、金额符号约束 |
| C6 | Run 执行收敛、尝试与取消 | 逻辑 step、attempt、重试、取消、租约 | `run_steps` 扩展列、`run_step_attempts`、attempt 状态枚举、执行路径 |
| C7 | 证据、Claim 与独立来源 | Claim 治理字段、审核、风险、独立来源、证据扩展 | `claims` 扩展、`claim_evidence` 扩展、`evidences` 扩展、Claim 枚举 |
| C8 | 数据集质量、缺口与首期模板 | 数据集哈希、逐市场质量、结构化 gap、首期模板 | `dataset_versions` 扩展、`data_gaps`、`market_assessments`、质量枚举 |
| C9 | 不可变报告合同与产物发布 | 报告生命周期、审核签字、发布、取代 | `report_artifacts` 扩展、`report_audit_events` 扩展、报告发布路径 |
| C10 | 交付 Manifest、bundle、验收与分享 | manifest、sidecar、公开投影、验收快照、篡改检测 | `report_artifacts` 交付列、`report_audit_events` 交付事件、交付路径 |
| C11 | 工作区伪名化、导出遮蔽与保留 | 伪名盐、法律保留、保留清理、保留墓碑、TTL | `workspace_pseudonym_salts`、`legal_holds`、`retention_cleanup_runs`、`retention_tombstones` |
| C12 | 删除请求、墓碑、删除证明与 DSR | 删除状态机、重放、证明、DSR、隐私审计 | `deletion_requests`、`deletion_tombstones`、`deletion_subprocessor_receipts`、`deletion_proofs`、`deletion_replay_runs`、`deletion_replay_items`、`dsr_cases`、`privacy_audit_events` |
| C13 | 客户 MCP `/mcp/customer` 八工具 | 客户入口、八工具、能力白名单、速率并发租约 | `/mcp/customer`、八个工具；不登记租约表 |
| C14 | 控制台 11 路由、CI 与验收门禁 | 页面路由、CI、Playwright、PG0 验收 | 契约 §5 的 11 条页面路由（`page_routes`，10 启用、1 禁用）与 4 条一级导航（`primary_nav`）；不新增数据库表 |

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `docs/design/【契约冻结】v1-表名-枚举-接口.md` | Modify | 唯一权威。版本升到 v1.1。写入 C2-C14 对象账本、枚举、路径、MCP、错误码、审计动作注册表、canonical profile、附录 A 机器登记块。 |
| `docs/product/【PRD】母婴出海数据洞察Agent工作台.md` | Modify | 同步客户 MCP 八工具、报告合同新顶层键、任务包输入、账本符号、验收判据。版本升到 v1.1。 |
| `docs/product/【Playbook】母婴出海洞察交付.md` | Modify | 同步市场质量状态、数据域状态、gap、刷新可比性、失败码、账本符号。版本升到 v1.1。 |
| `configs/contracts/v1.1.0/registry.schema.json` | Create | registry 的 JSON Schema。定义所有必填键、枚举和模式，含 `page_routes` 与 `primary_nav`。 |
| `configs/contracts/v1.1.0/registry.json` | Create | 从契约 Markdown 生成的机器 registry。禁止手改。 |
| `apps/api/schemas/report_contract.schema.json` | Modify | B5 唯一的报告合同 schema；升级到 `1.1.0` 并补齐 v1.1 组。禁止新建第二份。 |
| `apps/api/src/data_intelligence_hub/schemas/report_contract.py` | Modify | 只改常量与 `ReportContract` 的 v1.1 字段：`CANONICAL_PROFILE_ID`、`CANONICAL_PROFILE`、`SCHEMA_VERSION = "1.1.0"`。 |
| `apps/api/tests/unit/test_report_contract.py` | Modify | 同步 1.1.0 常量、必填组与既有 golden fixture。 |
| `apps/api/tests/fixtures/golden_reports/*.contract.json` | Modify | 三份 golden 合同补 29 个必填键与 `schema_version = "1.1.0"`。 |
| `configs/contracts/v1.1.0/delivery_manifest.schema.json` | Create | 交付 manifest 的 JSON Schema。 |
| `configs/contracts/v1.1.0/customer_mcp.schema.json` | Create | 客户 MCP 八工具的输入与输出 schema。 |
| `scripts/contract_registry.py` | Create | 提取、校验、生成、比对 registry；检查文档完整性。 |
| `apps/api/tests/unit/test_contract_registry.py` | Create | registry、schema、checker、负向 fixture 的单元测试。 |
| `apps/api/tests/fixtures/contract_registry/negative/*` | Create | 负向 fixture。每个 fixture 只破坏一个规则。 |

**权威方向：**

```text
docs/design/【契约冻结】v1-表名-枚举-接口.md  (authority)
        │  extract_registry_block()
        ▼
configs/contracts/v1.1.0/registry.json        (generated)
        │  check()
        ▼
scripts/contract_registry.py + pytest         (enforcement)
```

`registry.json` 不反向覆盖 Markdown。checker 发现差异时失败，不自动修 Markdown。

---

### Task 1: Registry Schema 与提取器

**Files:**
- Create: `configs/contracts/v1.1.0/registry.schema.json`
- Create: `scripts/contract_registry.py`
- Create: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Produces: `extract_registry_block(markdown: str) -> dict[str, Any]`
- Produces: `validate_registry(registry: dict[str, Any], schema: dict[str, Any]) -> list[str]`
- Produces: 版本化审计动作注册表 `audit_actions`（`audit-actions.v1`）的 schema 与语义校验
- Produces: `canonical_dump(value: dict[str, Any]) -> str`
- Produces: CLI `build`、`check`、`check-docs`
- Consumes: 无

- [ ] **Step 0: 从 C0 标签创建独立 worktree**

Run（只在主工作树执行 `git worktree prune`、前驱断言与 `cp` 源；后续所有 Run/Commit 都在新工作树）：

```bash
cd /Users/lute/Project/data_scrapy
git worktree prune
git rev-parse --verify pg0-baseline-v1^{commit}
test ! -e /Users/lute/Project/data_scrapy-gov-c1 && echo "worktree_path_free"
git worktree add /Users/lute/Project/data_scrapy-gov-c1 -b feat/gov-c1 pg0-baseline-v1
cd /Users/lute/Project/data_scrapy-gov-c1
test "$(git branch --show-current)" = feat/gov-c1 && echo "branch=feat/gov-c1"
mkdir -p docs/superpowers/plans
test -f docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md || cp /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md docs/superpowers/plans/
git merge-base --is-ancestor feat/b5-workbench HEAD; echo "b5_ancestor=$?"
cd apps/api && uv sync
uv run alembic heads
cd /Users/lute/Project/data_scrapy-gov-c1
test -f configs/contracts/v1.1.0/registry.json && echo "C1_REGISTRY_PRESENT" || echo "C1_REGISTRY_ABSENT"
```

Expected:

```text
worktree_path_free
branch=feat/gov-c1
b5_ancestor=0
202610210057 (head)
C1_REGISTRY_ABSENT
```

`C1_REGISTRY_ABSENT` 是正常状态：registry 由本计划创建。标签不存在、工作树路径已存在、分支名不是 `feat/gov-c1`、`b5_ancestor` 非 0 或 Alembic head 不是 `202610210057` 时停止，先完成 C0。`feat/gov-c1` 已存在时停止，先审查旧分支，不得复用。`uv sync` 在 `apps/api` 建立 `.venv`。本计划的 Markdown 不在 `pg0-baseline-v1` 标签内，必须先从主工作树复制到新工作树，后续 Commit 才会包含它。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_contract_registry.py`:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = PROJECT_ROOT / "scripts/contract_registry.py"

BEGIN = "<!-- contract-registry:begin -->"
END = "<!-- contract-registry:end -->"


def load_module():
    spec = importlib.util.spec_from_file_location("contract_registry", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_registry() -> dict:
    return {
        "registry_version": "contract-registry.v1",
        "contract_version": "v1.1",
        "status": "frozen",
        "source_document": "contract.md",
        "source_section": "附录 A",
        "generated_at": "2026-10-22",
        "canonical_profile": {
            "profile_id": "dih-canonical-json-v1",
            "encoding": "UTF-8",
            "json_rules": "RFC 8785",
            "digest_algorithm": "sha256",
            "digest_encoding": "lowercase-hex",
            "excluded_top_level_keys": ["generated_at", "artifact"],
            "timestamp_format": "RFC3339-UTC-Z",
            "number_rules": "finite-only",
            "unicode_rules": "preserve scalar values",
        },
        "audit_actions": {
            "version": "audit-actions.v1",
            "actions": [
                {
                    "name": "project.created",
                    "owner": "C2",
                    "status": "new",
                    "phase": "C2",
                }
            ],
        },
        "phases": [
            {
                "id": f"C{index}",
                "name": f"Phase {index}",
                "scope": "scope",
                "objects": [],
            }
            for index in range(2, 15)
        ],
        "tables": [
            {
                "name": "runs",
                "module": "M10",
                "status": "existing",
                "phase": "C2",
                "purpose": "run",
                "primary_key": ["id"],
                "columns": [
                    {
                        "name": "id",
                        "type": "uuid",
                        "nullable": False,
                        "status": "existing",
                        "phase": "C2",
                    }
                ],
            }
        ],
        "enums": [
            {
                "name": "runs.status",
                "values": ["queued"],
                "status": "frozen",
                "phase": "C2",
                "source": "contract",
            }
        ],
        "paths": [
            {
                "id": "runs.list",
                "method": "GET",
                "path": "/api/runs",
                "audience": "session",
                "status": "existing",
                "phase": "C2",
                "auth": "session",
                "idempotent": False,
                "error_codes": [],
            }
        ],
        "page_routes": [
            {"id": "home", "path": "/", "area": "public", "enabled": True, "kind": "static", "phase": "C14"},
            {"id": "capabilities", "path": "/capabilities", "area": "public", "enabled": True, "kind": "static", "phase": "C14"},
            {"id": "capabilities.detail", "path": "/capabilities/[toolId]", "area": "public", "enabled": True, "kind": "dynamic", "dynamic_segment": "toolId", "phase": "C14"},
            {"id": "reports.public.detail", "path": "/reports/public/[id]", "area": "public", "enabled": False, "kind": "dynamic", "dynamic_segment": "id", "phase": "C14"},
            {"id": "docs", "path": "/docs", "area": "public", "enabled": True, "kind": "static", "phase": "C14"},
            {"id": "workbench", "path": "/workbench", "area": "authorized", "enabled": True, "kind": "static", "phase": "C14"},
            {"id": "workbench.detail", "path": "/workbench/[taskId]", "area": "authorized", "enabled": True, "kind": "dynamic", "dynamic_segment": "taskId", "phase": "C14"},
            {"id": "reports", "path": "/reports", "area": "authorized", "enabled": True, "kind": "static", "phase": "C14"},
            {"id": "reports.detail", "path": "/reports/[artifactId]", "area": "authorized", "enabled": True, "kind": "dynamic", "dynamic_segment": "artifactId", "phase": "C14"},
            {"id": "connectors", "path": "/connectors", "area": "authorized", "enabled": True, "kind": "static", "phase": "C14"},
            {"id": "settings", "path": "/settings", "area": "authorized", "enabled": True, "kind": "static", "phase": "C14"}
        ],
        "primary_nav": [
            {"id": "workbench", "label": "工作台", "path": "/workbench", "order": 1, "phase": "C14"},
            {"id": "reports", "label": "报告", "path": "/reports", "order": 2, "phase": "C14"},
            {"id": "connectors", "label": "连接器", "path": "/connectors", "order": 3, "phase": "C14"},
            {"id": "settings", "label": "设置", "path": "/settings", "order": 4, "phase": "C14"}
        ],
        "mcp": {
            "endpoint": "/mcp/customer",
            "transport": "streamable-http",
            "tools_version": "customer-mcp.v1",
            "schema_file": "customer_mcp.schema.json",
            "tools": [
                {
                    "name": f"tool_{index}",
                    "status": "new",
                    "phase": "C10",
                    "audience": "customer",
                    "read_only": True,
                    "input_ref": f"customer_mcp.schema.json#/$defs/Tool{index}Input",
                    "output_ref": f"customer_mcp.schema.json#/$defs/Tool{index}Output",
                    "error_codes": [],
                }
                for index in range(8)
            ],
            "forbidden_tools": ["collect_endpoint"],
        },
        "error_codes": [
            {
                "code": "tool_not_allowed",
                "kind": "error",
                "http_status": 403,
                "retryable": False,
                "phase": "C10",
                "meaning": "tool not allowed",
            }
        ],
        "schemas": [
            {
                "id": "registry",
                "path": "configs/contracts/v1.1.0/registry.schema.json",
                "kind": "registry",
                "profile": "dih-canonical-json-v1",
                "digest_algorithm": "sha256",
            },
            {
                "id": "registry_copy",
                "path": "configs/contracts/v1.1.0/registry.schema.json",
                "kind": "registry",
                "profile": "dih-canonical-json-v1",
                "digest_algorithm": "sha256",
            },
        ],
        "documents": [
            {
                "path": "docs/design/contract.md",
                "role": "authority",
                "version": "v1.1",
                "must_contain": ["runs"],
            },
            {
                "path": "docs/product/prd.md",
                "role": "derived",
                "version": "v1.1",
                "must_contain": ["runs"],
            },
            {
                "path": "docs/product/playbook.md",
                "role": "derived",
                "version": "v1.1",
                "must_contain": ["runs"],
            },
        ],
        "deferred": [],
    }


def test_extract_registry_block_returns_object() -> None:
    module = load_module()
    payload = minimal_registry()
    markdown = f"# Contract\n\n{BEGIN}\n```json\n{json.dumps(payload, ensure_ascii=False)}\n```\n{END}\n"
    assert module.extract_registry_block(markdown) == payload


def test_extract_registry_block_rejects_missing_markers() -> None:
    module = load_module()
    try:
        module.extract_registry_block("# Contract\n")
    except module.RegistryError as exc:
        assert str(exc) == "registry_block_missing"
    else:
        raise AssertionError("expected RegistryError")


def test_extract_registry_block_rejects_duplicate_markers() -> None:
    module = load_module()
    markdown = f"{BEGIN}\n```json\n{{}}\n```\n{END}\n{BEGIN}\n```json\n{{}}\n```\n{END}\n"
    try:
        module.extract_registry_block(markdown)
    except module.RegistryError as exc:
        assert str(exc) == "registry_block_duplicate"
    else:
        raise AssertionError("expected RegistryError")


def test_validate_registry_accepts_minimal_object() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert module.validate_registry(minimal_registry(), schema) == []


def test_validate_registry_rejects_wrong_mcp_tool_count() -> None:
    module = load_module()
    schema = json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(
            encoding="utf-8"
        )
    )
    payload = minimal_registry()
    payload["mcp"]["tools"] = payload["mcp"]["tools"][:7]
    errors = module.validate_registry(payload, schema)
    assert any("mcp" in error and "tools" in error for error in errors)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。`scripts/contract_registry.py` 不存在。`registry.schema.json` 不存在。

- [ ] **Step 3: 写 registry schema**

Create `configs/contracts/v1.1.0/registry.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dih.local/contracts/v1.1.0/registry.schema.json",
  "title": "DIH Contract Registry v1.1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "registry_version",
    "contract_version",
    "status",
    "source_document",
    "source_section",
    "generated_at",
    "canonical_profile",
    "audit_actions",
    "phases",
    "tables",
    "enums",
    "paths",
    "page_routes",
    "primary_nav",
    "mcp",
    "error_codes",
    "schemas",
    "documents",
    "deferred"
  ],
  "properties": {
    "registry_version": {"const": "contract-registry.v1"},
    "contract_version": {"const": "v1.1"},
    "status": {"enum": ["draft", "frozen"]},
    "source_document": {"type": "string", "minLength": 1},
    "source_section": {"type": "string", "minLength": 1},
    "generated_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "canonical_profile": {"$ref": "#/$defs/canonical_profile"},
    "capability_profiles": {
      "type": "array",
      "minItems": 1,
      "items": {"$ref": "#/$defs/capability_profile"}
    },
    "audit_actions": {"$ref": "#/$defs/audit_actions"},
    "phases": {
      "type": "array",
      "minItems": 13,
      "maxItems": 13,
      "items": {"$ref": "#/$defs/phase"}
    },
    "tables": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/table"}},
    "enums": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/enum"}},
    "paths": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/path"}},
    "page_routes": {
      "type": "array",
      "minItems": 11,
      "maxItems": 11,
      "items": {"$ref": "#/$defs/page_route"}
    },
    "primary_nav": {
      "type": "array",
      "minItems": 4,
      "maxItems": 4,
      "items": {"$ref": "#/$defs/primary_nav_item"}
    },
    "mcp": {"$ref": "#/$defs/mcp"},
    "error_codes": {
      "type": "array",
      "minItems": 1,
      "items": {"$ref": "#/$defs/error_code"}
    },
    "schemas": {
      "type": "array",
      "minItems": 2,
      "items": {"$ref": "#/$defs/schema_ref"}
    },
    "documents": {
      "type": "array",
      "minItems": 3,
      "items": {"$ref": "#/$defs/document"}
    },
    "deferred": {
      "type": "array",
      "items": {"$ref": "#/$defs/deferred_object"}
    }
  },
  "$defs": {
    "canonical_profile": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "profile_id",
        "encoding",
        "json_rules",
        "digest_algorithm",
        "digest_encoding",
        "excluded_top_level_keys",
        "timestamp_format",
        "number_rules",
        "unicode_rules",
        "forbidden_language"
      ],
      "properties": {
        "profile_id": {"const": "dih-canonical-json-v1"},
        "encoding": {"const": "UTF-8"},
        "json_rules": {"const": "RFC 8785"},
        "digest_algorithm": {"const": "sha256"},
        "digest_encoding": {"const": "lowercase-hex"},
        "excluded_top_level_keys": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "timestamp_format": {"const": "RFC3339-UTC-Z"},
        "number_rules": {"type": "string", "minLength": 1},
        "unicode_rules": {"type": "string", "minLength": 1},
        "null_policy": {"type": "string", "minLength": 1},
        "line_endings": {"type": "string", "minLength": 1},
        "trailing_newline": {"type": "string", "minLength": 1},
        "known_deviations": {
          "type": "array",
          "items": {"type": "string", "minLength": 1}
        },
        "forbidden_language": {"$ref": "#/$defs/forbidden_language_profile"},
        "pii_scan": {"$ref": "#/$defs/pii_scan_profile"}
      }
    },
    "capability_profile": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "profile_id",
        "profile_version",
        "registry_source",
        "schema_path",
        "entrypoint",
        "digest_function",
        "digest_profile",
        "digest_algorithm",
        "digest_includes",
        "empty_allowlist_policy",
        "unknown_template",
        "storage",
        "excluded_capability_ids"
      ],
      "properties": {
        "profile_id": {"const": "dih-template-capability-v1"},
        "profile_version": {"const": "1.0.0"},
        "registry_source": {"const": "apps/api/src/data_intelligence_hub/services/workbench_templates.py"},
        "schema_path": {"const": "configs/contracts/v1.1.0/template_capability_profile.schema.json"},
        "entrypoint": {"const": "template_capability_ids"},
        "digest_function": {"const": "template_registry_digest"},
        "digest_profile": {"const": "dih-canonical-json-v1"},
        "digest_algorithm": {"const": "sha256"},
        "digest_includes": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "empty_allowlist_policy": {"const": "deny_all"},
        "unknown_template": {"const": "KeyError"},
        "storage": {"const": "code_registry_not_table"},
        "excluded_capability_ids": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        }
      }
    },
    "pii_scan_profile": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "profile_id",
        "owner",
        "module",
        "scanner",
        "value_scanner",
        "finding_type",
        "finding_codes",
        "c9_error",
        "c10_error",
        "shared_by",
        "no_second_ruleset"
      ],
      "properties": {
        "profile_id": {"const": "export_policy.v1"},
        "owner": {"const": "C11"},
        "module": {"const": "apps/api/src/data_intelligence_hub/services/export_policy.py"},
        "scanner": {"const": "scan_export_policy"},
        "value_scanner": {"const": "scan_export_value"},
        "finding_type": {"const": "PiiHit"},
        "finding_codes": {
          "type": "array",
          "minItems": 4,
          "maxItems": 4,
          "uniqueItems": true,
          "items": {"enum": ["contact", "profile_link", "avatar", "tracking"]}
        },
        "c9_error": {"const": "report_publish_gate_blocked"},
        "c10_error": {"const": "delivery_pii_detected"},
        "shared_by": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "uniqueItems": true,
          "items": {"enum": ["C9", "C10"]}
        },
        "no_second_ruleset": {"const": true}
      }
    },
    "forbidden_language_profile": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "profile_id",
        "profile_version",
        "source",
        "causal_terms_zh",
        "causal_terms_en",
        "prediction_terms_zh",
        "prediction_terms_en",
        "prediction_objects_zh",
        "prediction_objects_en",
        "allowed_relations_zh",
        "allowed_relations_en"
      ],
      "properties": {
        "profile_id": {"const": "dih-descriptive-language-v1"},
        "profile_version": {"const": "1.0.0"},
        "source": {"const": "docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md#5.7"},
        "causal_terms_zh": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "causal_terms_en": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "prediction_terms_zh": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "prediction_terms_en": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "prediction_objects_zh": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "prediction_objects_en": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "allowed_relations_zh": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "allowed_relations_en": {
          "type": "array",
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        }
      }
    },
    "audit_actions": {
      "type": "object",
      "additionalProperties": false,
      "required": ["version", "actions"],
      "properties": {
        "version": {"const": "audit-actions.v1"},
        "actions": {
          "type": "array",
          "minItems": 1,
          "items": {"$ref": "#/$defs/audit_action"}
        }
      }
    },
    "audit_action": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "owner", "status", "phase"],
      "properties": {
        "name": {
          "type": "string",
          "minLength": 3,
          "maxLength": 80,
          "pattern": "^[a-z][a-z0-9_]*(?:\\.[a-z0-9_]+)+$"
        },
        "owner": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "status": {"enum": ["new", "existing", "extended", "frozen"]},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"}
      }
    },
    "phase": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "name", "scope", "objects"],
      "properties": {
        "id": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "name": {"type": "string", "minLength": 1},
        "scope": {"type": "string", "minLength": 1},
        "objects": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^(table|enum|path|mcp_tool|error|schema|page_route|primary_nav):"
          }
        }
      }
    },
    "table": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "module", "status", "phase", "purpose", "primary_key", "columns"],
      "properties": {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "module": {"type": "string", "pattern": "^M(?:0[1-9]|1[0-2])$"},
        "status": {"enum": ["existing", "extend", "new"]},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "purpose": {"type": "string", "minLength": 1},
        "primary_key": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "columns": {
          "type": "array",
          "minItems": 1,
          "items": {"$ref": "#/$defs/column"}
        },
        "constraints": {
          "type": "array",
          "items": {"type": "string", "minLength": 1}
        },
        "indexes": {
          "type": "array",
          "items": {"$ref": "#/$defs/index"}
        }
      }
    },
    "column": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "type", "nullable", "status", "phase"],
      "properties": {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "type": {
          "type": "string",
          "pattern": "^(uuid|text|integer|boolean|datetime|date|json|string\\([0-9]+\\)|numeric\\([0-9]+,[0-9]+\\))$"
        },
        "nullable": {"type": "boolean"},
        "status": {"enum": ["existing", "extend", "new"]},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "references": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*(?:\\.[a-z][a-z0-9_]*)?$"
        },
        "enum": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"},
        "default": {},
        "notes": {"type": "string"}
      }
    },
    "index": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "columns", "unique"],
      "properties": {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "columns": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string", "minLength": 1}
        },
        "unique": {"type": "boolean"},
        "where": {"type": "string", "minLength": 1}
      }
    },
    "enum": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "values", "status", "phase", "source"],
      "properties": {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"},
        "values": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {"type": "string", "minLength": 1}
        },
        "status": {"enum": ["frozen", "extended", "new"]},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "banned_values": {
          "type": "array",
          "items": {"type": "string", "minLength": 1}
        },
        "source": {"type": "string", "minLength": 1},
        "rule": {"type": "string", "minLength": 1}
      }
    },
    "path": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "method", "path", "audience", "status", "phase", "auth", "idempotent", "error_codes"],
      "properties": {
        "id": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"},
        "method": {"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
        "path": {"type": "string", "pattern": "^/"},
        "audience": {"enum": ["public", "session", "customer_key", "internal"]},
        "status": {"enum": ["existing", "new"]},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "auth": {"enum": ["none", "session", "bearer", "internal"]},
        "idempotent": {"type": "boolean"},
        "idempotency": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "header",
            "required",
            "replay_status",
            "replay_header",
            "conflict_error"
          ],
          "properties": {
            "header": {"const": "Idempotency-Key"},
            "required": {"const": true},
            "replay_status": {"const": 200},
            "replay_header": {"const": "Idempotent-Replay"},
            "conflict_error": {
              "type": "string",
              "pattern": "^[a-z][a-z0-9_]*$"
            }
          }
        },
        "error_codes": {
          "type": "array",
          "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}
        }
      }
    },
    "page_route": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "path", "area", "enabled", "kind", "phase"],
      "properties": {
        "id": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"},
        "path": {"type": "string", "pattern": "^/"},
        "area": {"enum": ["public", "authorized"]},
        "enabled": {"type": "boolean"},
        "kind": {"enum": ["static", "dynamic"]},
        "dynamic_segment": {"enum": ["toolId", "artifactId", "taskId", "id"]},
        "phase": {"const": "C14"}
      }
    },
    "primary_nav_item": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "label", "path", "order", "phase"],
      "properties": {
        "id": {"enum": ["workbench", "reports", "connectors", "settings"]},
        "label": {"type": "string", "minLength": 1},
        "path": {"type": "string", "pattern": "^/"},
        "order": {"type": "integer", "minimum": 1, "maximum": 4},
        "phase": {"const": "C14"}
      }
    },
    "mcp": {
      "type": "object",
      "additionalProperties": false,
      "required": ["endpoint", "transport", "tools_version", "schema_file", "tools", "forbidden_tools"],
      "properties": {
        "endpoint": {"const": "/mcp/customer"},
        "transport": {"const": "streamable-http"},
        "tools_version": {"const": "customer-mcp.v1"},
        "schema_file": {"type": "string", "minLength": 1},
        "tools": {
          "type": "array",
          "minItems": 8,
          "maxItems": 8,
          "items": {"$ref": "#/$defs/mcp_tool"}
        },
        "forbidden_tools": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string", "minLength": 1}
        }
      }
    },
    "mcp_tool": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "status", "phase", "audience", "read_only", "input_ref", "output_ref", "error_codes"],
      "properties": {
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "status": {"enum": ["new", "existing"]},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "audience": {"const": "customer"},
        "read_only": {"type": "boolean"},
        "input_ref": {
          "type": "string",
          "pattern": "^customer_mcp\\.schema\\.json#/\\$defs/"
        },
        "output_ref": {
          "type": "string",
          "pattern": "^customer_mcp\\.schema\\.json#/\\$defs/"
        },
        "error_codes": {
          "type": "array",
          "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}
        }
      }
    },
    "error_code": {
      "type": "object",
      "additionalProperties": false,
      "required": ["code", "kind", "http_status", "retryable", "phase", "meaning"],
      "properties": {
        "code": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "kind": {"enum": ["error", "result_code"]},
        "http_status": {"type": "integer", "minimum": 200, "maximum": 599},
        "retryable": {"type": "boolean"},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "meaning": {"type": "string", "minLength": 1},
        "banned_context": {"type": "string", "minLength": 1}
      }
    },
    "schema_ref": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "path", "kind", "profile", "digest_algorithm"],
      "properties": {
        "id": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"},
        "path": {"type": "string", "pattern": "^(configs/contracts/v1\\.1\\.0/|apps/api/schemas/)"},
        "kind": {"enum": ["registry", "report_contract", "delivery_manifest", "customer_mcp", "template_capability_profile"]},
        "profile": {"const": "dih-canonical-json-v1"},
        "digest_algorithm": {"const": "sha256"}
      }
    },
    "document": {
      "type": "object",
      "additionalProperties": false,
      "required": ["path", "role", "version", "must_contain"],
      "properties": {
        "path": {"type": "string", "minLength": 1},
        "role": {"enum": ["authority", "derived", "supporting"]},
        "version": {"type": "string", "minLength": 1},
        "must_contain": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string", "minLength": 1}
        }
      }
    },
    "deferred_object": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "name", "phase", "owner", "reason"],
      "properties": {
        "kind": {"enum": ["table", "column", "enum", "path", "mcp_tool", "error", "schema"]},
        "name": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"},
        "phase": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "owner": {"type": "string", "pattern": "^C(?:[2-9]|1[0-4])$"},
        "reason": {"type": "string", "minLength": 1}
      }
    }
  }
}
```

- [ ] **Step 4: 写提取器与最小校验器**

Create `scripts/contract_registry.py`:

```python
#!/usr/bin/env python3
"""Extract, validate, generate, and compare the DIH contract registry.

The Markdown contract is authoritative. The registry JSON block lives inside
the contract. This script never writes the Markdown.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BEGIN = "<!-- contract-registry:begin -->"
END = "<!-- contract-registry:end -->"
FENCE_OPEN = "```json"
FENCE_CLOSE = "```"


class RegistryError(ValueError):
    """A deterministic registry error. The message is the error code."""


def extract_registry_block(markdown: str) -> dict[str, Any]:
    if markdown.count(BEGIN) == 0 or markdown.count(END) == 0:
        raise RegistryError("registry_block_missing")
    if markdown.count(BEGIN) != 1 or markdown.count(END) != 1:
        raise RegistryError("registry_block_duplicate")
    start = markdown.find(BEGIN)
    end = markdown.find(END)
    if end <= start:
        raise RegistryError("registry_block_order")
    body = markdown[start + len(BEGIN):end].strip()
    if not body.startswith(FENCE_OPEN) or not body.endswith(FENCE_CLOSE):
        raise RegistryError("registry_block_fence_invalid")
    payload = body[len(FENCE_OPEN):-len(FENCE_CLOSE)].strip()
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RegistryError(
            f"registry_block_json_invalid:{exc.lineno}:{exc.colno}"
        ) from exc
    if not isinstance(value, dict):
        raise RegistryError("registry_block_not_object")
    return value


def canonical_dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise RegistryError(f"unsupported_ref:{ref}")
    name = ref.removeprefix(prefix)
    definitions = root.get("$defs")
    if not isinstance(definitions, dict) or name not in definitions:
        raise RegistryError(f"missing_def:{name}")
    target = definitions[name]
    if not isinstance(target, dict):
        raise RegistryError(f"def_not_object:{name}")
    return target


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _validate_value(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str,
) -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        return _validate_value(value, _resolve_ref(str(schema["$ref"]), root), root, path)
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}:const")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}:enum")
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(value, str(expected_type)):
        errors.append(f"{path}:type")
        return errors
    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{path}:minLength")
        pattern = schema.get("pattern")
        # JSON Schema ``pattern`` is an unanchored regular expression: it
        # matches when the pattern occurs anywhere in the string. Use
        # ``re.search`` and let schemas anchor with ``^`` / ``$`` themselves.
        if pattern is not None and re.search(str(pattern), value) is None:
            errors.append(f"{path}:pattern")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{path}:minItems")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{path}:maxItems")
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}:uniqueItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_value(item, item_schema, root, f"{path}[{index}]")
                )
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    errors.append(f"{path}:required:{key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            for key in value:
                if key not in properties:
                    errors.append(f"{path}:additional:{key}")
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(
                        _validate_value(value[key], child_schema, root, f"{path}.{key}")
                    )
    return errors


def validate_registry(
    registry: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    errors = _validate_value(registry, schema, schema, "$")
    errors.extend(check_semantics(registry))
    return errors


def check_semantics(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phases = [str(item.get("id")) for item in registry.get("phases", [])]
    expected_phases = [f"C{index}" for index in range(2, 15)]
    if phases != expected_phases:
        errors.append("phase_sequence_invalid")

    tables = registry.get("tables", [])
    table_names = [str(item.get("name")) for item in tables]
    if len(table_names) != len(set(table_names)):
        errors.append("duplicate_table")
    for table in tables:
        columns = [str(item.get("name")) for item in table.get("columns", [])]
        if len(columns) != len(set(columns)):
            errors.append(f"duplicate_column:{table.get('name')}")

    enums = registry.get("enums", [])
    enum_names = [str(item.get("name")) for item in enums]
    if len(enum_names) != len(set(enum_names)):
        errors.append("duplicate_enum")
    for item in enums:
        values = [str(value) for value in item.get("values", [])]
        banned = {str(value) for value in item.get("banned_values", [])}
        if banned.intersection(values):
            errors.append(f"banned_enum_value:{item.get('name')}")

    paths = registry.get("paths", [])
    path_keys = [(str(item.get("method")), str(item.get("path"))) for item in paths]
    if len(path_keys) != len(set(path_keys)):
        errors.append("duplicate_path")
    path_ids = [str(item.get("id")) for item in paths]
    if len(path_ids) != len(set(path_ids)):
        errors.append("duplicate_path_id")
    for item in paths:
        idempotency = item.get("idempotency")
        if not isinstance(idempotency, dict):
            continue
        if item.get("idempotent") is not True:
            errors.append(f"idempotency_path_not_idempotent:{item.get('id')}")
        path_codes = {str(code) for code in item.get("error_codes", [])}
        if str(idempotency.get("conflict_error")) not in path_codes:
            errors.append(f"idempotency_conflict_unbound:{item.get('id')}")

    page_routes = registry.get("page_routes", [])
    page_paths = [str(item.get("path")) for item in page_routes]
    if len(page_paths) != 11:
        errors.append("page_route_count")
    if len(page_paths) != len(set(page_paths)):
        errors.append("duplicate_page_route")
    if any(path.startswith("/api/") for path in page_paths):
        errors.append("page_route_is_api_path")
    enabled_routes = [item for item in page_routes if item.get("enabled") is True]
    disabled_routes = [item for item in page_routes if item.get("enabled") is False]
    if len(enabled_routes) != 10:
        errors.append("page_route_enabled_count")
    if [str(item.get("path")) for item in disabled_routes] != [
        "/reports/public/[id]"
    ]:
        errors.append("page_route_disabled_set")
    for item in page_routes:
        kind = item.get("kind")
        segment = item.get("dynamic_segment")
        if kind == "dynamic":
            if not isinstance(segment, str) or f"[{segment}]" not in str(
                item.get("path")
            ):
                errors.append(f"page_route_dynamic_segment:{item.get('id')}")
        elif kind == "static" and "dynamic_segment" in item:
            errors.append(f"page_route_static_has_segment:{item.get('id')}")

    primary_nav = registry.get("primary_nav", [])
    nav_paths = [str(item.get("path")) for item in primary_nav]
    nav_ids = [str(item.get("id")) for item in primary_nav]
    if len(nav_paths) != 4:
        errors.append("primary_nav_count")
    if nav_ids != ["workbench", "reports", "connectors", "settings"]:
        errors.append("primary_nav_ids")
    if nav_paths != ["/workbench", "/reports", "/connectors", "/settings"]:
        errors.append("primary_nav_paths")
    if [item.get("order") for item in primary_nav] != [1, 2, 3, 4]:
        errors.append("primary_nav_order")
    if not set(nav_paths).issubset(
        {str(item.get("path")) for item in enabled_routes}
    ):
        errors.append("primary_nav_not_page_route")

    audit_actions = registry.get("audit_actions", {}).get("actions", [])
    action_names = [str(item.get("name")) for item in audit_actions]
    if len(action_names) != len(set(action_names)):
        errors.append("duplicate_audit_action")
    for action_name in action_names:
        if len(action_name) > 80:
            errors.append(f"audit_action_too_long:{action_name}")

    deferred_names = {str(item.get("name")) for item in registry.get("deferred", [])}
    if deferred_names.intersection(table_names):
        errors.append("deferred_object_registered")

    tools = registry.get("mcp", {}).get("tools", [])
    tool_names = [str(item.get("name")) for item in tools]
    if len(tool_names) != 8:
        errors.append("mcp_tool_count")
    if len(tool_names) != len(set(tool_names)):
        errors.append("duplicate_mcp_tool")

    errors.extend(check_schema_refs_exist(registry))
    return errors


def check_schema_refs_exist(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = Path(__file__).resolve().parents[1]
    for item in registry.get("schemas", []):
        path = root / str(item.get("path"))
        if not path.exists():
            errors.append(f"schema_file_missing:{item.get('path')}")
    for tool in registry.get("mcp", {}).get("tools", []):
        for key in ("input_ref", "output_ref"):
            ref = str(tool.get(key, ""))
            if "#/$defs/" not in ref:
                errors.append(f"mcp_ref_invalid:{tool.get('name')}:{key}")
    return errors


def build(doc: Path, schema_path: Path, out: Path) -> int:
    registry = extract_registry_block(doc.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_registry(registry, schema)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    out.write_text(canonical_dump(registry), encoding="utf-8")
    print(f"registry built: {out}")
    return 0


def check(doc: Path, schema_path: Path, registry_path: Path) -> int:
    registry = extract_registry_block(doc.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_registry(registry, schema)
    if registry_path.read_text(encoding="utf-8") != canonical_dump(registry):
        errors.append("registry_out_of_date")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"registry check OK: {registry_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--doc", type=Path, required=True)
    build_parser.add_argument("--schema", type=Path, required=True)
    build_parser.add_argument("--out", type=Path, required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--doc", type=Path, required=True)
    check_parser.add_argument("--schema", type=Path, required=True)
    check_parser.add_argument("--registry", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.doc, args.schema, args.out)
    if args.command == "check":
        return check(args.doc, args.schema, args.registry)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `5 passed`。测试读取 `configs/contracts/v1.1.0/registry.schema.json`。该文件已存在。

- [ ] **Step 6: 运行 ruff**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/ruff check ../scripts/contract_registry.py tests/unit/test_contract_registry.py`

Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add configs/contracts/v1.1.0/registry.schema.json scripts/contract_registry.py apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(contract): add registry schema and extractor"
```

Commit only after `detect-changes` returns without `partial: true` or `truncated: true`.

---

### Task 2: C4/C5/C6 执行、预算与 attempt 表

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Create: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `extract_registry_block`、`validate_registry`、CLI `build`、CLI `check`。
- Produces: 契约附录 A 的 `contract-registry` 块。
- Produces: `workbench_tasks`（含 `package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`、`max_cost_usd`、`max_pages`、`max_records`、`seed_products`、`target_price_band`、`idempotency_key_hash` 与 `uq_workbench_tasks_workspace_idempotency`）、`workflow_versions.workbench_task_id`、`workflow_versions.plan_payload.execution_steps`、`runs.market_code`、`authorizations.run_id`、`run_steps` 扩展列、`run_step_attempts`、`tool_prices`、`quota_accounts`、`tool_calls`。
- Produces: C4 这些对象的唯一归属迁移是 `202610220062`（`down_revision = "202610220061"`）。C1 只登记，不新增迁移；不得把 `seed_products`、`target_price_band`、`idempotency_key_hash` 或 `uq_workbench_tasks_workspace_idempotency` 拆到第二个迁移。
- Produces: 13 个 phase 条目。
- Produces: `tool_prices` 的完整列、约束与索引；`deferred` 数组登记 `mcp_customer_request_leases`、`report_shares` 与两个公开分享路径。
- Produces: registry 骨架中的 seed enum、seed path、8 个 MCP 工具占位条目、seed error、2 个 schema ref、3 个 document。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
CONTRACT_PATH = (
    PROJECT_ROOT / "docs/design/【契约冻结】v1-表名-枚举-接口.md"
)
SCHEMA_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json"
REGISTRY_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"


def load_contract_registry() -> dict:
    module = load_module()
    return module.extract_registry_block(CONTRACT_PATH.read_text(encoding="utf-8"))


def _table(registry: dict, name: str) -> dict:
    return next(item for item in registry["tables"] if item["name"] == name)


def test_registry_contains_execution_and_budget_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {
        "workbench_tasks",
        "workflow_versions",
        "runs",
        "run_steps",
        "authorizations",
        "task_runs",
        "run_step_attempts",
        "tool_prices",
        "quota_accounts",
        "tool_calls",
    } <= names


def test_tool_prices_matches_c5_pricing_contract() -> None:
    registry = load_contract_registry()
    table = _table(registry, "tool_prices")
    assert {column["name"] for column in table["columns"]} == {
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
    assert {
        "uq_tool_prices_tool_currency_version",
        "ck_tool_prices_unit_price_nonnegative",
        "ck_tool_prices_confidence",
        "ck_tool_prices_effective_window",
        "fk_tool_prices_tool_id_tool_catalog",
    } <= set(table["constraints"])
    indexes = {index["name"]: index for index in table["indexes"]}
    assert indexes["uq_tool_prices_tool_currency_version"]["columns"] == [
        "tool_id",
        "currency",
        "price_book_version",
    ]
    assert indexes["uq_tool_prices_tool_currency_version"]["unique"] is True
    assert indexes["ix_tool_prices_tool_effective"]["columns"] == [
        "tool_id",
        "effective_from",
    ]


def test_deferred_customer_lease_is_not_registered_as_table() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    deferred = {(item["kind"], item["name"]) for item in registry["deferred"]}
    assert ("table", "mcp_customer_request_leases") in deferred
    assert ("table", "report_shares") in deferred
    assert "mcp_customer_request_leases" not in names
    assert "report_shares" not in names
    assert ("table", "tool_prices") not in deferred


def test_workbench_tasks_matches_c4_seven_slots() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "workbench_tasks")["columns"]}
    assert {
        "workspace_id",
        "project_id",
        "created_by_user_id",
        "owner_id",
        "brand",
        "category",
        "competitors",
        "markets",
        "locale_by_market",
        "window_start",
        "window_end",
        "decision_question",
        "does_not_answer",
        "task_type",
        "task_type_confidence",
        "status",
    } <= columns


def test_workbench_tasks_persist_package_type_and_market_roles() -> None:
    registry = load_contract_registry()
    table = _table(registry, "workbench_tasks")
    columns = {column["name"]: column for column in table["columns"]}
    assert {
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
    } <= set(columns)
    assert columns["package_type"]["enum"] == "workbench_tasks.package_type"
    assert columns["primary_market"]["enum"] == "market_code"
    assert columns["comparison_markets"]["type"] == "json"
    assert columns["seed_products"]["type"] == "json"
    assert columns["seed_products"]["nullable"] is False
    assert columns["target_price_band"]["type"] == "json"
    assert columns["target_price_band"]["nullable"] is True
    assert columns["idempotency_key_hash"]["type"] == "string(64)"
    assert columns["idempotency_key_hash"]["nullable"] is True
    assert "owner" in columns["acceptance_contact_id"]["notes"]
    assert "admin" in columns["acceptance_contact_id"]["notes"]
    assert {
        "ck_workbench_tasks_package_type",
        "ck_workbench_tasks_primary_market",
        "ck_workbench_tasks_budget_nonnegative",
        "fk_workbench_tasks_acceptance_contact_member",
    } <= set(table["constraints"])
    indexes = {index["name"]: index for index in table["indexes"]}
    assert indexes["uq_workbench_tasks_workspace_idempotency"] == {
        "name": "uq_workbench_tasks_workspace_idempotency",
        "columns": ["workspace_id", "idempotency_key_hash"],
        "unique": True,
        "where": "idempotency_key_hash IS NOT NULL",
    }
    versions = {
        column["name"]: column
        for column in _table(registry, "workflow_versions")["columns"]
    }
    assert "plan_payload" in versions
    assert "execution_steps" in versions["plan_payload"]["notes"]
    assert "不可变" in versions["plan_payload"]["notes"]
    assert versions["workbench_task_id"]["nullable"] is True
    version_table = _table(registry, "workflow_versions")
    assert "fk_workflow_versions_workbench_task_tenant" in version_table["constraints"]


def test_runs_uses_market_code_and_authorization_binds_run_id() -> None:
    registry = load_contract_registry()
    run_columns = {column["name"] for column in _table(registry, "runs")["columns"]}
    authorization = _table(registry, "authorizations")
    authorization_columns = {column["name"] for column in authorization["columns"]}
    assert "market_code" in run_columns
    assert "market_role" not in run_columns
    assert "package_type" not in run_columns
    assert "run_id" in authorization_columns
    assert "gate_id" in authorization_columns
    assert "uq_authorizations_run_gate" in authorization["constraints"]
    assert {
        "name": "uq_authorizations_run_gate",
        "columns": ["run_id", "gate_id"],
        "unique": True,
        "where": "run_id IS NOT NULL",
    } in authorization["indexes"]


def test_run_step_attempts_matches_c6_columns() -> None:
    registry = load_contract_registry()
    attempt = _table(registry, "run_step_attempts")
    assert {column["name"] for column in attempt["columns"]} == {
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
    assert {
        "uq_run_step_attempts_run_step_attempt",
        "uq_run_step_attempts_task_run_id",
        "ck_run_step_attempts_attempt_number_positive",
        "ck_run_step_attempts_status",
        "fk_run_step_attempts_run_id_runs",
        "fk_run_step_attempts_task_run_id_task_runs",
    } <= set(attempt["constraints"])
    assert {
        "name": "ix_run_step_attempts_run_step",
        "columns": ["run_id", "step_index"],
        "unique": False,
    } in attempt["indexes"]


def test_run_steps_has_c6_extension_columns() -> None:
    registry = load_contract_registry()
    table = _table(registry, "run_steps")
    columns = {column["name"]: column for column in table["columns"]}
    assert {
        "attempt_no",
        "depends_on",
        "tool_id",
        "provider_run_id",
        "idempotency_key_hash",
        "evidence_grade",
        "stage",
    } <= set(columns)
    assert columns["attempt_no"]["nullable"] is False
    assert columns["attempt_no"]["default"] == 1
    assert {
        "name": "uq_run_steps_task_run_id",
        "columns": ["task_run_id"],
        "unique": True,
        "where": "task_run_id IS NOT NULL",
    } in table["indexes"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。`registry_block_missing`。契约文件还没有 `contract-registry` 块。

- [ ] **Step 3: 在契约文件加入版本头与附录骨架**

Modify `docs/design/【契约冻结】v1-表名-枚举-接口.md`:

1. 在 front matter 中加入 `version: v1.1`。
2. 把 `> 版本：v1.0 · 2026-10-20` 改为 `> 版本：v1.1 · 2026-10-22`。
3. 在文件末尾追加以下内容。`tables` 先为空数组，下一步填入完整数组。`page_routes` 与 `primary_nav` 从骨架起就是契约 §5 的完整投影；后续任务不得整体替换或删减这两个数组。

````markdown
## 附录 A 机器登记块

本块是 Markdown 正文的机器投影。正文与本节冲突时，以正文为准；生成物与 Markdown 冲突时，以 Markdown 为准。
本块由 `scripts/contract_registry.py build` 生成 `configs/contracts/v1.1.0/registry.json`。
禁止手改生成物。

<!-- contract-registry:begin -->
```json
{
  "registry_version": "contract-registry.v1",
  "contract_version": "v1.1",
  "status": "frozen",
  "source_document": "docs/design/【契约冻结】v1-表名-枚举-接口.md",
  "source_section": "附录 A 机器登记块",
  "generated_at": "2026-10-22",
  "canonical_profile": {
    "profile_id": "dih-canonical-json-v1",
    "encoding": "UTF-8",
    "json_rules": "RFC 8785",
    "digest_algorithm": "sha256",
    "digest_encoding": "lowercase-hex",
    "excluded_top_level_keys": ["generated_at", "artifact"],
    "timestamp_format": "RFC3339-UTC-Z",
    "number_rules": "finite-only; integers exact; no negative zero",
    "unicode_rules": "preserve scalar values; no Unicode normalization",
    "null_policy": "required nulls are emitted; optional absent keys are omitted",
    "line_endings": "LF",
    "trailing_newline": "file-only; excluded from digest",
    "known_deviations": ["1e-07 formatting", "-0.0", "code-point key ordering"],
    "forbidden_language": {
      "profile_id": "dih-descriptive-language-v1",
      "profile_version": "1.0.0",
      "source": "docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md#5.7",
      "causal_terms_zh": ["导致", "驱动", "提升", "降低", "造成", "证明"],
      "causal_terms_en": ["cause", "causes", "caused", "drive", "drives", "driven", "improve", "improves", "increase", "increases", "decrease", "decreases", "reduce", "reduces", "lead to", "leads to", "prove", "proves"],
      "prediction_terms_zh": ["预测", "预计", "将会"],
      "prediction_terms_en": ["predict", "predicts", "forecast", "forecasts", "projection", "projections"],
      "prediction_objects_zh": ["销量", "市场份额", "转化率", "营收"],
      "prediction_objects_en": ["sales", "market share", "conversion rate", "revenue"],
      "allowed_relations_zh": ["共同出现", "相关", "描述性差异"],
      "allowed_relations_en": ["co-occurrence", "correlation", "descriptive difference"]
    },
    "pii_scan": {
      "profile_id": "export_policy.v1",
      "owner": "C11",
      "module": "apps/api/src/data_intelligence_hub/services/export_policy.py",
      "scanner": "scan_export_policy",
      "value_scanner": "scan_export_value",
      "finding_type": "PiiHit",
      "finding_codes": ["contact", "profile_link", "avatar", "tracking"],
      "c9_error": "report_publish_gate_blocked",
      "c10_error": "delivery_pii_detected",
      "shared_by": ["C9", "C10"],
      "no_second_ruleset": true
    }
  },
  "capability_profiles": [
    {
      "profile_id": "dih-template-capability-v1",
      "profile_version": "1.0.0",
      "registry_source": "apps/api/src/data_intelligence_hub/services/workbench_templates.py",
      "schema_path": "configs/contracts/v1.1.0/template_capability_profile.schema.json",
      "entrypoint": "template_capability_ids",
      "digest_function": "template_registry_digest",
      "digest_profile": "dih-canonical-json-v1",
      "digest_algorithm": "sha256",
      "digest_includes": ["template_id", "version", "markets", "package_tiers", "capability_allowlist", "thresholds"],
      "empty_allowlist_policy": "deny_all",
      "unknown_template": "KeyError",
      "storage": "code_registry_not_table",
      "excluded_capability_ids": ["tikhub_tiktok_video_products", "tikhub_tiktok_creator_showcase"]
    }
  ],
  "audit_actions": {
    "version": "audit-actions.v1",
    "actions": [
      {"name": "auth.login.succeeded", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "auth.login.failed", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "auth.logout.succeeded", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "workspace.member.added", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "workspace.member.role_changed", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "workspace.member.removed", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.created", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.updated", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.archived", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.member.added", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.member.removed", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.access.denied", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project.management.denied", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "reviewer.access.granted", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "reviewer.access.denied", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "config.switch.changed", "owner": "C2", "status": "new", "phase": "C2"},
      {"name": "project_api_key.issued", "owner": "C3", "status": "new", "phase": "C3"},
      {"name": "project_api_key.rotated", "owner": "C3", "status": "new", "phase": "C3"},
      {"name": "project_api_key.revoked", "owner": "C3", "status": "new", "phase": "C3"},
      {"name": "platform_credential.updated", "owner": "C3", "status": "new", "phase": "C3"},
      {"name": "platform_credential.removed", "owner": "C3", "status": "new", "phase": "C3"},
      {"name": "task.created", "owner": "C4", "status": "new", "phase": "C4"},
      {"name": "task.cancelled", "owner": "C4", "status": "new", "phase": "C4"},
      {"name": "budget.price.changed", "owner": "C5", "status": "new", "phase": "C5"},
      {"name": "budget.limit.changed", "owner": "C5", "status": "new", "phase": "C5"},
      {"name": "budget.blocked", "owner": "C5", "status": "new", "phase": "C5"},
      {"name": "budget.released", "owner": "C5", "status": "new", "phase": "C5"},
      {"name": "task.retried", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "run.created", "owner": "C4", "status": "new", "phase": "C4"},
      {"name": "run.cancel_requested", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "run.cancelled", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "run.retry_scheduled", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "run.retry_exhausted", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "run.completed", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "run.failed", "owner": "C6", "status": "new", "phase": "C6"},
      {"name": "claim.review.submitted", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "claim.review.approved", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "claim.review.rejected", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "claim.review.overridden", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "claim.blocked", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "claim.unblocked", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "claim.revised", "owner": "C7", "status": "new", "phase": "C7"},
      {"name": "dataset.quality.evaluated", "owner": "C8", "status": "new", "phase": "C8"},
      {"name": "quality.assessment.computed", "owner": "C8", "status": "new", "phase": "C8"},
      {"name": "quality.gap.resolved", "owner": "C8", "status": "new", "phase": "C8"},
      {"name": "quality.template.changed", "owner": "C8", "status": "new", "phase": "C8"},
      {"name": "report.review.approved", "owner": "C9", "status": "new", "phase": "C9"},
      {"name": "report.review.rejected", "owner": "C9", "status": "new", "phase": "C9"},
      {"name": "report.published", "owner": "C9", "status": "new", "phase": "C9"},
      {"name": "report.superseded", "owner": "C9", "status": "new", "phase": "C9"},
      {"name": "reviewer.assignment.created", "owner": "C9", "status": "new", "phase": "C9"},
      {"name": "reviewer.assignment.revoked", "owner": "C9", "status": "new", "phase": "C9"},
      {"name": "delivery.published", "owner": "C10", "status": "new", "phase": "C10"},
      {"name": "delivery.downloaded", "owner": "C10", "status": "new", "phase": "C10"},
      {"name": "delivery.projection.viewed", "owner": "C10", "status": "new", "phase": "C10"},
      {"name": "delivery.tamper_detected", "owner": "C10", "status": "new", "phase": "C10"},
      {"name": "delivery.superseded", "owner": "C10", "status": "new", "phase": "C10"},
      {"name": "privacy.projection.applied", "owner": "C11", "status": "new", "phase": "C11"},
      {"name": "dataset.export.created", "owner": "C11", "status": "new", "phase": "C11"},
      {"name": "retention.cleanup.executed", "owner": "C11", "status": "new", "phase": "C11"},
      {"name": "legal_hold.created", "owner": "C11", "status": "new", "phase": "C11"},
      {"name": "legal_hold.released", "owner": "C11", "status": "new", "phase": "C11"},
      {"name": "privacy.deletion.requested", "owner": "C12", "status": "new", "phase": "C12"},
      {"name": "privacy.deletion.executed", "owner": "C12", "status": "new", "phase": "C12"},
      {"name": "privacy.dsr.received", "owner": "C12", "status": "new", "phase": "C12"},
      {"name": "mcp.tool_call.started", "owner": "C13", "status": "new", "phase": "C13"},
      {"name": "mcp.tool_call.finished", "owner": "C13", "status": "new", "phase": "C13"},
      {"name": "mcp.tool_call.denied", "owner": "C13", "status": "new", "phase": "C13"}
    ]
  },
  "phases": [
    {"id": "C2", "name": "身份、项目 ACL 与统一审计", "scope": "工作区角色、项目成员、追加式审计、请求 ID", "objects": []},
    {"id": "C3", "name": "项目密钥与项目级凭据", "scope": "密钥状态、轮换、能力白名单、项目级凭据、Cookie 元数据", "objects": []},
    {"id": "C4", "name": "任务单提交、计划关联与幂等", "scope": "七槽位任务单、计划版本关联、逐市场 run 幂等", "objects": []},
    {"id": "C5", "name": "预算、账本与定价", "scope": "单价、额度账户、调用记录、按 run 授权、账本符号", "objects": []},
    {"id": "C6", "name": "Run 执行收敛、尝试与取消", "scope": "逻辑 step、attempt、重试、取消、租约", "objects": []},
    {"id": "C7", "name": "证据、Claim 与独立来源", "scope": "Claim 治理字段、审核、风险、独立来源、证据扩展", "objects": []},
    {"id": "C8", "name": "数据集质量、缺口与首期模板", "scope": "数据集哈希、逐市场质量、结构化 gap、首期模板", "objects": []},
    {"id": "C9", "name": "不可变报告合同与产物发布", "scope": "报告生命周期、审核签字、发布、取代", "objects": []},
    {"id": "C10", "name": "交付 Manifest、bundle、验收与分享", "scope": "manifest、sidecar、公开投影、验收快照、篡改检测", "objects": []},
    {"id": "C11", "name": "工作区伪名化、导出遮蔽与保留", "scope": "伪名盐、法律保留、保留清理、保留墓碑、TTL", "objects": []},
    {"id": "C12", "name": "删除请求、墓碑、删除证明与 DSR", "scope": "删除状态机、重放、证明、DSR、隐私审计", "objects": []},
    {"id": "C13", "name": "客户 MCP /mcp/customer 八工具", "scope": "客户入口、八工具、能力白名单、速率并发租约", "objects": []},
    {"id": "C14", "name": "控制台 11 路由、CI 与验收门禁", "scope": "页面路由、CI、Playwright、PG0 验收", "objects": []}
  ],
  "tables": [],
  "enums": [
    {"name": "runs.status", "values": ["queued", "running", "completed", "failed", "cancelled"], "status": "frozen", "phase": "C6", "banned_values": ["held", "degraded", "partial"], "source": "契约 v1 §2.1"}
  ],
  "paths": [
    {"id": "tools.list", "method": "GET", "path": "/api/tools", "audience": "session", "status": "existing", "phase": "C2", "auth": "session", "idempotent": false, "error_codes": ["authentication_required"]}
  ],
  "page_routes": [
    {"id": "home", "path": "/", "area": "public", "enabled": true, "kind": "static", "phase": "C14"},
    {"id": "capabilities", "path": "/capabilities", "area": "public", "enabled": true, "kind": "static", "phase": "C14"},
    {"id": "capabilities.detail", "path": "/capabilities/[toolId]", "area": "public", "enabled": true, "kind": "dynamic", "dynamic_segment": "toolId", "phase": "C14"},
    {"id": "reports.public.detail", "path": "/reports/public/[id]", "area": "public", "enabled": false, "kind": "dynamic", "dynamic_segment": "id", "phase": "C14"},
    {"id": "docs", "path": "/docs", "area": "public", "enabled": true, "kind": "static", "phase": "C14"},
    {"id": "workbench", "path": "/workbench", "area": "authorized", "enabled": true, "kind": "static", "phase": "C14"},
    {"id": "workbench.detail", "path": "/workbench/[taskId]", "area": "authorized", "enabled": true, "kind": "dynamic", "dynamic_segment": "taskId", "phase": "C14"},
    {"id": "reports", "path": "/reports", "area": "authorized", "enabled": true, "kind": "static", "phase": "C14"},
    {"id": "reports.detail", "path": "/reports/[artifactId]", "area": "authorized", "enabled": true, "kind": "dynamic", "dynamic_segment": "artifactId", "phase": "C14"},
    {"id": "connectors", "path": "/connectors", "area": "authorized", "enabled": true, "kind": "static", "phase": "C14"},
    {"id": "settings", "path": "/settings", "area": "authorized", "enabled": true, "kind": "static", "phase": "C14"}
  ],
  "primary_nav": [
    {"id": "workbench", "label": "工作台", "path": "/workbench", "order": 1, "phase": "C14"},
    {"id": "reports", "label": "报告", "path": "/reports", "order": 2, "phase": "C14"},
    {"id": "connectors", "label": "连接器", "path": "/connectors", "order": 3, "phase": "C14"},
    {"id": "settings", "label": "设置", "path": "/settings", "order": 4, "phase": "C14"}
  ],
  "mcp": {
    "endpoint": "/mcp/customer",
    "transport": "streamable-http",
    "tools_version": "customer-mcp.v1",
    "schema_file": "configs/contracts/v1.1.0/customer_mcp.schema.json",
    "tools": [
      {"name": "discover_capabilities", "status": "new", "phase": "C13", "audience": "customer", "read_only": true, "input_ref": "customer_mcp.schema.json#/$defs/DiscoverCapabilitiesInput", "output_ref": "customer_mcp.schema.json#/$defs/DiscoverCapabilitiesOutput", "error_codes": ["authentication_required", "tool_not_allowed", "quota_exceeded", "rate_limited"]},
      {"name": "estimate_task", "status": "new", "phase": "C13", "audience": "customer", "read_only": true, "input_ref": "customer_mcp.schema.json#/$defs/EstimateTaskInput", "output_ref": "customer_mcp.schema.json#/$defs/EstimateTaskOutput", "error_codes": ["authentication_required", "tool_not_allowed", "quota_exceeded", "rate_limited", "market_unsupported", "tool_not_priced", "package_type_invalid", "comparison_markets_exceeded", "budget_invalid"]},
      {"name": "create_task", "status": "new", "phase": "C13", "audience": "customer", "read_only": false, "input_ref": "customer_mcp.schema.json#/$defs/CreateTaskInput", "output_ref": "customer_mcp.schema.json#/$defs/CreateTaskOutput", "error_codes": ["authentication_required", "invalid_request", "tool_not_allowed", "quota_exceeded", "rate_limited", "approval_required", "market_unsupported", "idempotency_conflict", "package_type_invalid", "comparison_markets_exceeded", "acceptance_contact_not_member", "budget_invalid"]},
      {"name": "get_task", "status": "new", "phase": "C13", "audience": "customer", "read_only": true, "input_ref": "customer_mcp.schema.json#/$defs/GetTaskInput", "output_ref": "customer_mcp.schema.json#/$defs/GetTaskOutput", "error_codes": ["authentication_required", "tool_not_allowed", "quota_exceeded", "rate_limited", "task_not_found"]},
      {"name": "cancel_task", "status": "new", "phase": "C13", "audience": "customer", "read_only": false, "input_ref": "customer_mcp.schema.json#/$defs/CancelTaskInput", "output_ref": "customer_mcp.schema.json#/$defs/CancelTaskOutput", "error_codes": ["authentication_required", "invalid_request", "tool_not_allowed", "quota_exceeded", "rate_limited", "task_not_found", "state_conflict", "idempotency_conflict"]},
      {"name": "get_delivery_manifest", "status": "new", "phase": "C13", "audience": "customer", "read_only": true, "input_ref": "customer_mcp.schema.json#/$defs/GetDeliveryManifestInput", "output_ref": "customer_mcp.schema.json#/$defs/GetDeliveryManifestOutput", "error_codes": ["authentication_required", "tool_not_allowed", "quota_exceeded", "rate_limited", "task_not_found", "manifest_not_found"]},
      {"name": "get_evidence", "status": "new", "phase": "C13", "audience": "customer", "read_only": true, "input_ref": "customer_mcp.schema.json#/$defs/GetEvidenceInput", "output_ref": "customer_mcp.schema.json#/$defs/GetEvidenceOutput", "error_codes": ["authentication_required", "tool_not_allowed", "quota_exceeded", "rate_limited", "claim_not_found", "evidence_not_found"]},
      {"name": "collect", "status": "new", "phase": "C13", "audience": "customer", "read_only": false, "input_ref": "customer_mcp.schema.json#/$defs/CollectInput", "output_ref": "customer_mcp.schema.json#/$defs/CollectOutput", "error_codes": ["authentication_required", "tool_not_allowed", "quota_exceeded", "rate_limited", "approval_required", "tool_not_executable", "tool_not_priced", "market_unsupported", "capability_not_allowed", "cookie_not_accepted", "package_type_invalid", "comparison_markets_exceeded"]}
    ],
    "forbidden_tools": ["collect_endpoint", "tiktok_creator_cookie", "raw_provider_call", "admin_query"]
  },
  "error_codes": [
    {"code": "tool_not_allowed", "kind": "error", "http_status": 403, "retryable": false, "phase": "C13", "meaning": "工具不在项目密钥白名单内"}
  ],
  "schemas": [
    {"id": "registry", "path": "configs/contracts/v1.1.0/registry.schema.json", "kind": "registry", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"},
    {"id": "registry_copy", "path": "configs/contracts/v1.1.0/registry.schema.json", "kind": "registry", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"},
    {"id": "template_capability_profile", "path": "configs/contracts/v1.1.0/template_capability_profile.schema.json", "kind": "template_capability_profile", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"}
  ],
  "documents": [
    {"path": "docs/design/【契约冻结】v1-表名-枚举-接口.md", "role": "authority", "version": "v1.1", "must_contain": ["附录 A 机器登记块"]},
    {"path": "docs/product/【PRD】母婴出海数据洞察Agent工作台.md", "role": "derived", "version": "v1.1", "must_contain": ["discover_capabilities"]},
    {"path": "docs/product/【Playbook】母婴出海洞察交付.md", "role": "derived", "version": "v1.1", "must_contain": ["comparable_with_caveats"]}
  ],
  "deferred": [
    {"kind": "table", "name": "mcp_customer_request_leases", "phase": "C13", "owner": "C13", "reason": "C13 不新增迁移与表；租约按现有配置实现"},
    {"kind": "table", "name": "report_shares", "phase": "C10", "owner": "C10", "reason": "首期延期；C10 只提供项目内鉴权下载"},
    {"kind": "path", "name": "reports.share", "phase": "C10", "owner": "C10", "reason": "公开分享延期；不得登记 POST /api/reports/{report_id}/share"},
    {"kind": "path", "name": "reports.public.access", "phase": "C10", "owner": "C10", "reason": "公开分享延期；不得登记 GET /api/reports/public/{token}"}
  ]
}
```
<!-- contract-registry:end -->
````

- [ ] **Step 4: 把以下对象填入 `tables` 数组**

```json
[
  {
    "name": "tool_catalog",
    "module": "M02",
    "status": "existing",
    "phase": "C2",
    "purpose": "内部工具目录与工具合同",
    "primary_key": ["tool_id"],
    "columns": [
      {"name": "tool_id", "type": "string(200)", "nullable": false, "status": "existing", "phase": "C2"}
    ]
  },
  {
    "name": "workbench_tasks",
    "module": "M10",
    "status": "new",
    "phase": "C4",
    "purpose": "七槽位任务单与包型/市场角色；保存种子商品、目标价格带与创建幂等摘要；不记录执行状态",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C4", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C4", "references": "projects.id"},
      {"name": "created_by_user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C4", "references": "users.id"},
      {"name": "owner_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C4", "references": "users.id"},
      {"name": "brand", "type": "string(200)", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "category", "type": "string(80)", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "competitors", "type": "json", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "package_type", "type": "string(10)", "nullable": false, "status": "new", "phase": "C4", "enum": "workbench_tasks.package_type"},
      {"name": "primary_market", "type": "string(2)", "nullable": false, "status": "new", "phase": "C4", "enum": "market_code", "notes": "市场角色事实源；等于该市场 run 的 primary"},
      {"name": "comparison_markets", "type": "json", "nullable": false, "status": "new", "phase": "C4", "notes": "市场角色事实源；元素为正式市场码，最多数量由 package_type 决定"},
      {"name": "markets", "type": "json", "nullable": false, "status": "new", "phase": "C4", "notes": "七槽位投影；服务层写入 [primary_market] + comparison_markets，不单独接收"},
      {"name": "locale_by_market", "type": "json", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "window_start", "type": "date", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "window_end", "type": "date", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "decision_question", "type": "text", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "does_not_answer", "type": "json", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "acceptance_contact_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C4", "references": "workspace_members.user_id", "notes": "复合外键指向 workspace_members(workspace_id, user_id)；空值表示任务 owner；非空必须是同工作区 owner 或 admin，member 返回 acceptance_contact_not_member"},
      {"name": "max_cost_usd", "type": "numeric(12,6)", "nullable": true, "status": "new", "phase": "C4"},
      {"name": "max_pages", "type": "integer", "nullable": true, "status": "new", "phase": "C4"},
      {"name": "max_records", "type": "integer", "nullable": true, "status": "new", "phase": "C4"},
      {"name": "seed_products", "type": "json", "nullable": false, "status": "new", "phase": "C4", "notes": "默认空数组；非空时必须有 3–10 项公开链接或平台 ID"},
      {"name": "target_price_band", "type": "json", "nullable": true, "status": "new", "phase": "C4", "notes": "市场原币价格带；至少一个边界，min_amount <= max_amount，金额非负，币种三个大写字母"},
      {"name": "idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "new", "phase": "C4", "notes": "创建幂等摘要 sha256(\"workbench-task-create.v1:{key}\")；工作区级部分唯一索引保证同一键只建一单"},
      {"name": "task_type", "type": "string(10)", "nullable": true, "status": "new", "phase": "C4", "enum": "workbench_tasks.task_type"},
      {"name": "task_type_confidence", "type": "numeric(4,3)", "nullable": true, "status": "new", "phase": "C4"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C4", "enum": "workbench_tasks.status"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C4"},
      {"name": "updated_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C4"}
    ],
    "constraints": [
      "uq_workbench_tasks_tenant_id",
      "fk_workbench_tasks_project_tenant",
      "fk_workbench_tasks_owner_member",
      "fk_workbench_tasks_created_by_user_id_users",
      "fk_workbench_tasks_acceptance_contact_member",
      "ck_workbench_tasks_status",
      "ck_workbench_tasks_window_order",
      "ck_workbench_tasks_task_type",
      "ck_workbench_tasks_task_type_confidence",
      "ck_workbench_tasks_package_type",
      "ck_workbench_tasks_primary_market",
      "ck_workbench_tasks_budget_nonnegative"
    ],
    "indexes": [
      {"name": "uq_workbench_tasks_workspace_idempotency", "columns": ["workspace_id", "idempotency_key_hash"], "unique": true, "where": "idempotency_key_hash IS NOT NULL"},
      {"name": "ix_workbench_tasks_workspace_project_status", "columns": ["workspace_id", "project_id", "status"], "unique": false},
      {"name": "ix_workbench_tasks_owner", "columns": ["workspace_id", "owner_id"], "unique": false}
    ]
  },
  {
    "name": "workflow_versions",
    "module": "M10",
    "status": "extend",
    "phase": "C4",
    "purpose": "不可变计划版本；关联任务单",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C4"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C4"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C4"},
      {"name": "plan_payload", "type": "json", "nullable": false, "status": "existing", "phase": "C4", "notes": "execution_steps 是 C4 版本创建时写入的不可变步骤快照；批准、提交、重试都不改写"},
      {"name": "workbench_task_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C4", "references": "workbench_tasks.id", "notes": "复合外键指向 workbench_tasks(workspace_id, project_id, id)；版本创建时把 execution_steps 写入 plan_payload，批准、提交、重试都不改写"}
    ],
    "constraints": ["fk_workflow_versions_workbench_task_tenant"],
    "indexes": [
      {"name": "ix_workflow_versions_workbench_task", "columns": ["workspace_id", "workbench_task_id"], "unique": false}
    ]
  },
  {
    "name": "runs",
    "module": "M10",
    "status": "extend",
    "phase": "C4",
    "purpose": "一次执行运行；逐市场提交；market_role 由 workbench_tasks 派生，不落列",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C4"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C4"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C4"},
      {"name": "workflow_version_id", "type": "uuid", "nullable": true, "status": "existing", "phase": "C4"},
      {"name": "idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "existing", "phase": "C4"},
      {"name": "cancel_idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C6", "notes": "取消幂等摘要 sha256(\"run-cancel.v1:{idempotency_key}\")；只在迁移 202610220064 创建；不得复用创建幂等列 idempotency_key_hash"},
      {"name": "cancel_reason_code", "type": "string(80)", "nullable": true, "status": "extend", "phase": "C6", "notes": "取消原因码；与 cancel_idempotency_key_hash 同事务写入；只在迁移 202610220064 创建"},
      {"name": "market_code", "type": "string(2)", "nullable": true, "status": "extend", "phase": "C4", "enum": "market_code", "notes": "非空时必须是两个大写字母；逐市场一行 run。market_role 不落列：等于任务 primary_market 时为 primary，否则为 compare"}
    ],
    "constraints": ["ck_runs_market_code"],
    "indexes": [
      {"name": "uq_runs_workspace_idempotency", "columns": ["workspace_id", "idempotency_key_hash"], "unique": true, "where": "idempotency_key_hash IS NOT NULL"},
      {"name": "uq_runs_workspace_cancel_idempotency", "columns": ["workspace_id", "cancel_idempotency_key_hash"], "unique": true, "where": "cancel_idempotency_key_hash IS NOT NULL"},
      {"name": "uq_runs_workflow_version_market", "columns": ["workflow_version_id", "market_code"], "unique": true, "where": "workflow_version_id IS NOT NULL AND market_code IS NOT NULL"}
    ]
  },
  {
    "name": "authorizations",
    "module": "M08",
    "status": "extend",
    "phase": "C5",
    "purpose": "人工授权与按 run 预算绑定",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C5"},
      {"name": "run_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C5", "references": "runs.id"},
      {"name": "gate_id", "type": "string(40)", "nullable": false, "status": "existing", "phase": "C5", "enum": "gate_id"}
    ],
    "constraints": ["uq_authorizations_run_gate"],
    "indexes": [
      {"name": "uq_authorizations_run_gate", "columns": ["run_id", "gate_id"], "unique": true, "where": "run_id IS NOT NULL"}
    ]
  },
  {
    "name": "run_ledger_entries",
    "module": "M08",
    "status": "extend",
    "phase": "C5",
    "purpose": "追加式运行成本账本；八列冻结",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C5"},
      {"name": "run_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C5", "references": "runs.id"},
      {"name": "step_id", "type": "uuid", "nullable": true, "status": "existing", "phase": "C5", "references": "run_steps.id"},
      {"name": "entry_kind", "type": "string(30)", "nullable": false, "status": "existing", "phase": "C5", "enum": "entry_kind"},
      {"name": "amount_usd", "type": "numeric(12,6)", "nullable": false, "status": "existing", "phase": "C5"},
      {"name": "balance_after_usd", "type": "numeric(12,6)", "nullable": false, "status": "existing", "phase": "C5"},
      {"name": "idempotency_key", "type": "string(160)", "nullable": false, "status": "existing", "phase": "C5"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "existing", "phase": "C5"}
    ],
    "constraints": ["ck_run_ledger_entries_amount_sign_by_kind"]
  },
  {
    "name": "task_runs",
    "module": "M04",
    "status": "extend",
    "phase": "C5",
    "purpose": "一次采集执行的记录；写回剩余额度",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C5"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C5", "references": "projects.id"},
      {"name": "run_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C5", "references": "runs.id"},
      {"name": "step_index", "type": "integer", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "unit", "type": "string(20)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "quantity", "type": "numeric(12,3)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "unit_price", "type": "numeric(12,6)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "total_cost_usd", "type": "numeric(12,6)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "remaining_budget", "type": "numeric(12,6)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "provider", "type": "string(40)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "provider_run_id", "type": "string(120)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "endpoint_type", "type": "string(80)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "evidence_grade", "type": "string(30)", "nullable": true, "status": "extend", "phase": "C7", "enum": "evidence_grade"},
      {"name": "schema_version", "type": "string(20)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C5"},
      {"name": "updated_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C5"}
    ]
  },
  {
    "name": "run_steps",
    "module": "M10",
    "status": "extend",
    "phase": "C6",
    "purpose": "逻辑执行步骤；attempt 号与依赖只保留最终值",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C6"},
      {"name": "task_run_id", "type": "uuid", "nullable": true, "status": "existing", "phase": "C6", "references": "task_runs.id"},
      {"name": "attempt_no", "type": "integer", "nullable": false, "status": "extend", "phase": "C6", "default": 1, "notes": "最终 attempt 号；非空，默认 1"},
      {"name": "depends_on", "type": "json", "nullable": true, "status": "extend", "phase": "C6"},
      {"name": "tool_id", "type": "string(200)", "nullable": true, "status": "extend", "phase": "C6"},
      {"name": "provider_run_id", "type": "string(120)", "nullable": true, "status": "extend", "phase": "C6"},
      {"name": "idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C6"},
      {"name": "evidence_grade", "type": "string(30)", "nullable": true, "status": "extend", "phase": "C6", "enum": "evidence_grade"},
      {"name": "stage", "type": "string(10)", "nullable": true, "status": "extend", "phase": "C6"}
    ],
    "constraints": ["ck_run_steps_attempt_no_positive"],
    "indexes": [
      {"name": "uq_run_steps_task_run_id", "columns": ["task_run_id"], "unique": true, "where": "task_run_id IS NOT NULL"}
    ]
  },
  {
    "name": "run_step_attempts",
    "module": "M10",
    "status": "new",
    "phase": "C6",
    "purpose": "每次 step attempt 一行；逻辑 step 仍只有一行 run_steps",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C6"},
      {"name": "run_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C6", "references": "runs.id"},
      {"name": "step_index", "type": "integer", "nullable": false, "status": "new", "phase": "C6"},
      {"name": "attempt_number", "type": "integer", "nullable": false, "status": "new", "phase": "C6"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C6", "enum": "run_step_attempts.status"},
      {"name": "task_run_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C6", "references": "task_runs.id"},
      {"name": "error_reason_code", "type": "string(80)", "nullable": true, "status": "new", "phase": "C6"},
      {"name": "error_message", "type": "text", "nullable": true, "status": "new", "phase": "C6"},
      {"name": "started_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C6"},
      {"name": "finished_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C6"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C6"}
    ],
    "constraints": [
      "uq_run_step_attempts_run_step_attempt",
      "uq_run_step_attempts_task_run_id",
      "ck_run_step_attempts_attempt_number_positive",
      "ck_run_step_attempts_status",
      "fk_run_step_attempts_run_id_runs",
      "fk_run_step_attempts_task_run_id_task_runs"
    ],
    "indexes": [
      {"name": "ix_run_step_attempts_run_step", "columns": ["run_id", "step_index"], "unique": false}
    ]
  },
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
    "name": "quota_accounts",
    "module": "M08",
    "status": "new",
    "phase": "C5",
    "purpose": "项目额度账户；预算检查与预留的锁点",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5", "references": "projects.id"},
      {"name": "period_start", "type": "date", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "period_end", "type": "date", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "currency", "type": "string(3)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "daily_limit_usd", "type": "numeric(12,6)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "monthly_limit_usd", "type": "numeric(12,6)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "used_usd", "type": "numeric(12,6)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "reserved_usd", "type": "numeric(12,6)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "remaining_usd", "type": "numeric(12,6)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "version", "type": "integer", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "updated_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"}
    ],
    "constraints": ["uq_quota_accounts_project_period"]
  },
  {
    "name": "tool_calls",
    "module": "M08",
    "status": "new",
    "phase": "C5",
    "purpose": "单次工具调用回执；成本与幂等",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5", "references": "projects.id"},
      {"name": "run_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C5", "references": "runs.id"},
      {"name": "step_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C5", "references": "run_steps.id"},
      {"name": "tool_id", "type": "string(200)", "nullable": false, "status": "new", "phase": "C5", "references": "tool_catalog.tool_id"},
      {"name": "contract_version", "type": "string(50)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "idempotency_key_hash", "type": "string(64)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "request_hash", "type": "string(64)", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "backend_ref_type", "type": "string(40)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "backend_ref_id", "type": "string(120)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "outcome", "type": "string(20)", "nullable": false, "status": "new", "phase": "C5", "enum": "runs.outcome"},
      {"name": "error_code", "type": "string(80)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "quantity", "type": "numeric(12,3)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "unit", "type": "string(20)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "unit_price", "type": "numeric(12,6)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "total_cost_usd", "type": "numeric(12,6)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "evidence_grade", "type": "string(30)", "nullable": true, "status": "new", "phase": "C7", "enum": "evidence_grade"},
      {"name": "started_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "finished_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C5"}
    ],
    "constraints": ["uq_tool_calls_workspace_idempotency"],
    "indexes": [
      {"name": "ix_tool_calls_run_step", "columns": ["run_id", "step_id"], "unique": false},
      {"name": "ix_tool_calls_tool_started", "columns": ["tool_id", "started_at"], "unique": false}
    ]
  }
]
```

- [ ] **Step 5: 生成 registry**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py build \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --out configs/contracts/v1.1.0/registry.json
```

Expected: `registry built: configs/contracts/v1.1.0/registry.json`。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `13 passed`。

- [ ] **Step 7: 运行 checker**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: `registry check OK`。

- [ ] **Step 8: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register C4-C6 execution budget and attempt objects"
```

---

### Task 3: C2/C3 身份、审计、密钥与凭据表

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `registry.json` 中已有的 `tables` 数组。
- Produces: `project_members`、`audit_events` 新表。
- Produces: `workspace_members.role`、`project_api_keys` 扩展、`platform_credential_bundles` 扩展。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_registry_contains_identity_audit_key_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {
        "workspace_members",
        "project_members",
        "audit_events",
        "project_api_keys",
        "platform_credential_bundles",
    } <= names


def test_audit_events_has_sequence_and_hash_chain() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "audit_events")["columns"]}
    assert {"sequence_number", "prev_hash", "event_hash", "actor_type", "result"} <= columns


def test_project_api_keys_matches_c3_rotation_columns() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "project_api_keys")["columns"]}
    assert {
        "tool_allowlist",
        "capability_allowlist",
        "daily_budget_usd",
        "status",
        "rotation_group_id",
        "superseded_by_key_id",
        "last_rotated_at",
        "expires_at",
    } <= columns


def test_c3_constraints_are_registered() -> None:
    registry = load_contract_registry()
    project_key_constraints = set(_table(registry, "project_api_keys").get("constraints", []))
    credential_constraints = set(
        _table(registry, "platform_credential_bundles").get("constraints", [])
    )
    assert "fk_project_api_keys_workspace_project_projects" in project_key_constraints
    assert "uq_project_api_keys_active_project" in project_key_constraints
    assert {
        "uq_platform_credential_bundles_workspace_provider",
        "uq_platform_credential_bundles_project_provider",
        "fk_platform_credential_bundles_workspace_project_projects",
    } <= credential_constraints


def test_platform_credentials_has_project_scope() -> None:
    registry = load_contract_registry()
    columns = {
        column["name"]
        for column in _table(registry, "platform_credential_bundles")["columns"]
    }
    assert {"project_id", "creator_cookie_metadata"} <= columns
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。缺 `project_members`。

- [ ] **Step 3: 把以下对象追加到 `tables` 数组**

```json
[
  {
    "name": "workspace_members",
    "module": "M01",
    "status": "extend",
    "phase": "C2",
    "purpose": "工作区成员与唯一授权角色",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C2"},
      {"name": "role", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C2", "enum": "workspace_members.role"}
    ],
    "constraints": ["ck_workspace_members_role"]
  },
  {
    "name": "project_members",
    "module": "M01",
    "status": "new",
    "phase": "C2",
    "purpose": "项目成员 ACL；只表达 member 的项目可见性",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2", "references": "projects.id"},
      {"name": "user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2", "references": "users.id"},
      {"name": "created_by_user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2", "references": "users.id"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C2"}
    ],
    "constraints": ["uq_project_members_workspace_project_user", "fk_project_members_project_tenant"],
    "indexes": [
      {"name": "ix_project_members_workspace_user", "columns": ["workspace_id", "user_id"], "unique": false}
    ]
  },
  {
    "name": "audit_events",
    "module": "M08",
    "status": "new",
    "phase": "C2",
    "purpose": "追加式统一审计事件；按工作区哈希链",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C2", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C2", "references": "projects.id"},
      {"name": "sequence_number", "type": "integer", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "actor_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C2", "references": "users.id"},
      {"name": "actor_type", "type": "string(20)", "nullable": false, "status": "new", "phase": "C2", "enum": "audit_events.actor_type"},
      {"name": "action", "type": "string(80)", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "resource_type", "type": "string(40)", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "resource_id", "type": "string(120)", "nullable": true, "status": "new", "phase": "C2"},
      {"name": "request_id", "type": "string(64)", "nullable": true, "status": "new", "phase": "C2"},
      {"name": "result", "type": "string(20)", "nullable": false, "status": "new", "phase": "C2", "enum": "audit_events.result"},
      {"name": "details", "type": "json", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "prev_hash", "type": "string(64)", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "event_hash", "type": "string(64)", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "occurred_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C2"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C2"}
    ],
    "constraints": ["uq_audit_events_workspace_sequence", "uq_audit_events_workspace_hash", "fk_audit_events_project_tenant"],
    "indexes": [
      {"name": "ix_audit_events_workspace_occurred", "columns": ["workspace_id", "occurred_at"], "unique": false},
      {"name": "ix_audit_events_workspace_action", "columns": ["workspace_id", "action"], "unique": false}
    ]
  },
  {
    "name": "project_api_keys",
    "module": "M09",
    "status": "extend",
    "phase": "C3",
    "purpose": "项目级客户 MCP 密钥",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C3"},
      {"name": "tool_allowlist", "type": "json", "nullable": false, "status": "existing", "phase": "C3", "notes": "现有 MCP 工具名白名单；C13 的 enforcement 事实源"},
      {"name": "capability_allowlist", "type": "json", "nullable": false, "status": "extend", "phase": "C3", "notes": "稳定 tool_catalog.tool_id 数组；C3 存储、展示、审计并通过 ProjectApiKeyIdentity/allows_capability 暴露；C13 执行客户 MCP enforcement"},
      {"name": "daily_budget_usd", "type": "numeric(12,6)", "nullable": true, "status": "extend", "phase": "C3"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C3", "enum": "project_api_keys.status"},
      {"name": "rotation_group_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C3"},
      {"name": "superseded_by_key_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C3", "references": "project_api_keys.id"},
      {"name": "last_rotated_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C3"},
      {"name": "expires_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C3"}
    ],
    "constraints": ["fk_project_api_keys_workspace_project_projects", "uq_project_api_keys_active_project"]
  },
  {
    "name": "platform_credential_bundles",
    "module": "M03",
    "status": "extend",
    "phase": "C3",
    "purpose": "项目级凭据与 creator cookie 元数据",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C3"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C3", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C3", "references": "projects.id"},
      {"name": "provider_id", "type": "string(120)", "nullable": false, "status": "existing", "phase": "C3"},
      {"name": "creator_cookie_metadata", "type": "json", "nullable": true, "status": "extend", "phase": "C3"}
    ],
    "constraints": ["uq_platform_credential_bundles_workspace_provider", "uq_platform_credential_bundles_project_provider", "fk_platform_credential_bundles_workspace_project_projects"],
    "indexes": [
      {"name": "uq_platform_credential_bundles_workspace_provider", "columns": ["workspace_id", "provider_id"], "unique": true},
      {"name": "uq_platform_credential_bundles_project_provider", "columns": ["workspace_id", "project_id", "provider_id"], "unique": true}
    ]
  }
]
```

- [ ] **Step 4: 重新生成 registry**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json`

Expected: `registry built`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `18 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register C2-C3 identity audit keys and credentials"
```

---

### Task 4: C7/C8 Claim、证据、缺口与数据集质量表

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `tables` 数组与 `phases` 数组。
- Produces: `claims` 扩展、`claim_evidence` 扩展、`evidences` 扩展。
- Produces: `data_gaps`、`market_assessments` 新表、`dataset_versions` 扩展。
- Produces: 契约正文的 C8 实现决定。C8 是 `market_assessments` 与 `data_gaps` 的唯一创建者，并在迁移 `066` 创建这两张已登记的表；C5 的迁移 `063` 不创建它们。任务包模板只存在于代码注册表，C8 不建 `task_templates` 表，C1 不登记该表。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_registry_contains_claim_quality_dataset_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {
        "claims",
        "claim_evidence",
        "evidences",
        "data_gaps",
        "market_assessments",
        "dataset_versions",
    } <= names
    assert "task_templates" not in names


def test_claims_has_review_and_risk_columns() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "claims")["columns"]}
    assert {
        "text_en",
        "scope_window_start",
        "scope_window_end",
        "risk_flags",
        "review_status",
        "reviewed_by",
        "reviewed_payload_sha256",
        "second_reviewed_by",
        "content_version",
        "independent_source_count",
        "blocked_reason",
        "review_history",
    } <= columns


def test_claim_tables_register_c7_constraint_guards() -> None:
    registry = load_contract_registry()
    claims = set(_table(registry, "claims")["constraints"])
    assert {
        "ck_claims_evidence_grade_min",
        "ck_claims_state_grade_ceiling",
        "ck_claims_review_status",
        "ck_claims_review_coherence",
        "ck_claims_confirmed_review",
        "ck_claims_content_version",
        "ck_claims_reviewed_version",
        "ck_claims_independent_count",
        "ck_claims_scope_window",
        "ck_claims_scope_days",
        "ck_claims_scope_sample",
        "ck_claims_blocked_reason",
        "ck_claims_blocked_state",
        "ck_claims_second_review_pair",
        "ck_claims_reviewer_differ",
        "ck_claims_state",
        "ck_claims_evidence_grade",
        "ck_claims_confidence_range",
        "fk_claims_workspace_id_workspaces",
        "fk_claims_project_id_projects",
        "fk_claims_run_id_runs",
        "fk_claims_owner_users",
        "fk_claims_reviewed_by_users",
        "fk_claims_second_reviewed_by_users",
    } <= claims
    assert {
        "ck_claim_evidence_role",
        "ck_claim_evidence_evidence_grade",
        "ck_claim_evidence_source_cluster_basis",
        "ck_claim_evidence_independent_cluster",
        "fk_claim_evidence_claim_id_claims",
        "fk_claim_evidence_evidence_id_evidences",
    } <= set(_table(registry, "claim_evidence")["constraints"])
    assert {
        "ck_evidences_evidence_grade",
        "ck_evidences_source_cluster_basis",
        "ck_evidences_source_cluster_coherence",
        "ck_evidences_workspace_project_pair",
        "fk_evidences_intelligence_id_intelligence_items",
        "fk_evidences_signal_id_signals",
        "fk_evidences_entity_id_entities",
        "fk_evidences_raw_record_id_raw_records",
        "fk_evidences_workspace_id_workspaces",
        "fk_evidences_project_id_projects",
    } <= set(_table(registry, "evidences")["constraints"])


def test_data_gaps_and_market_assessments_match_c8() -> None:
    registry = load_contract_registry()
    gap_columns = {column["name"] for column in _table(registry, "data_gaps")["columns"]}
    assessment_columns = {
        column["name"] for column in _table(registry, "market_assessments")["columns"]
    }
    assert {"market", "data_domain", "reason_code", "severity", "step_id", "resolved_at"} <= gap_columns
    assert {
        "task_id",
        "market",
        "market_role",
        "quality_status",
        "conclusion_standard",
        "conclusion_quick",
        "evidence_grade",
        "core_domain_coverage",
        "gap_ids",
    } <= assessment_columns


def test_dataset_versions_has_quality_and_hash_columns() -> None:
    registry = load_contract_registry()
    columns = {column["name"] for column in _table(registry, "dataset_versions")["columns"]}
    assert {"task_id", "market", "schema_hash", "content_sha256", "license_class", "quality_status"} <= columns
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。缺 `claims`。

- [ ] **Step 3: 把以下对象追加到 `tables` 数组**

```json
[
  {
    "name": "claims",
    "module": "M05",
    "status": "extend",
    "phase": "C7",
    "purpose": "可复核结论；审核、风险与独立来源",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C7"},
      {"name": "text_en", "type": "text", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "scope_window_start", "type": "date", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "scope_window_end", "type": "date", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "risk_flags", "type": "json", "nullable": false, "status": "extend", "phase": "C7"},
      {"name": "review_status", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C7", "enum": "claim_review_status"},
      {"name": "reviewed_by", "type": "uuid", "nullable": true, "status": "extend", "phase": "C7", "references": "users.id"},
      {"name": "reviewed_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "reviewed_content_version", "type": "integer", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "reviewed_payload_sha256", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "reviewed_profile", "type": "string(40)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "second_reviewed_by", "type": "uuid", "nullable": true, "status": "extend", "phase": "C7", "references": "users.id"},
      {"name": "second_reviewed_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "review_note", "type": "text", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "content_version", "type": "integer", "nullable": false, "status": "extend", "phase": "C7"},
      {"name": "independent_source_count", "type": "integer", "nullable": false, "status": "extend", "phase": "C7"},
      {"name": "blocked_reason", "type": "string(40)", "nullable": true, "status": "extend", "phase": "C7", "enum": "claims.blocked_reason"},
      {"name": "review_history", "type": "json", "nullable": false, "status": "extend", "phase": "C7"}
    ],
    "constraints": [
      "ck_claims_state",
      "ck_claims_evidence_grade",
      "ck_claims_confidence_range",
      "ck_claims_evidence_grade_min",
      "ck_claims_state_grade_ceiling",
      "ck_claims_review_status",
      "ck_claims_review_coherence",
      "ck_claims_confirmed_review",
      "ck_claims_content_version",
      "ck_claims_reviewed_version",
      "ck_claims_independent_count",
      "ck_claims_scope_window",
      "ck_claims_scope_days",
      "ck_claims_scope_sample",
      "ck_claims_blocked_reason",
      "ck_claims_blocked_state",
      "ck_claims_second_review_pair",
      "ck_claims_reviewer_differ",
      "fk_claims_workspace_id_workspaces",
      "fk_claims_project_id_projects",
      "fk_claims_run_id_runs",
      "fk_claims_owner_users",
      "fk_claims_reviewed_by_users",
      "fk_claims_second_reviewed_by_users"
    ]
  },
  {
    "name": "claim_evidence",
    "module": "M05",
    "status": "extend",
    "phase": "C7",
    "purpose": "Claim 与 Evidence 多对多；独立来源快照",
    "primary_key": ["claim_id", "evidence_id"],
    "columns": [
      {"name": "claim_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C7", "references": "claims.id"},
      {"name": "evidence_id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C7", "references": "evidences.id"},
      {"name": "role", "type": "string(20)", "nullable": false, "status": "existing", "phase": "C7", "enum": "claim_evidence.role"},
      {"name": "evidence_grade", "type": "string(30)", "nullable": true, "status": "extend", "phase": "C7", "enum": "evidence_grade"},
      {"name": "source_cluster_key", "type": "string(200)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "source_cluster_basis", "type": "string(20)", "nullable": true, "status": "extend", "phase": "C7", "enum": "source_cluster_basis"},
      {"name": "independent", "type": "boolean", "nullable": false, "status": "extend", "phase": "C7"}
    ],
    "constraints": [
      "ck_claim_evidence_role",
      "ck_claim_evidence_evidence_grade",
      "ck_claim_evidence_source_cluster_basis",
      "ck_claim_evidence_independent_cluster",
      "fk_claim_evidence_claim_id_claims",
      "fk_claim_evidence_evidence_id_evidences"
    ]
  },
  {
    "name": "evidences",
    "module": "M05",
    "status": "extend",
    "phase": "C7",
    "purpose": "证据记录；intelligence_id 改为可空",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C7"},
      {"name": "workspace_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C7", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C7", "references": "projects.id"},
      {"name": "evidence_grade", "type": "string(30)", "nullable": true, "status": "extend", "phase": "C7", "enum": "evidence_grade"},
      {"name": "market", "type": "string(10)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "locale", "type": "string(16)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "source_tool_id", "type": "string(200)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "provider_id", "type": "string(40)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "captured_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "source_cluster_key", "type": "string(200)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "source_cluster_basis", "type": "string(20)", "nullable": true, "status": "extend", "phase": "C7"},
      {"name": "intelligence_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C7", "references": "intelligence_items.id"}
    ],
    "constraints": [
      "ck_evidences_evidence_grade",
      "ck_evidences_source_cluster_basis",
      "ck_evidences_source_cluster_coherence",
      "ck_evidences_workspace_project_pair",
      "fk_evidences_intelligence_id_intelligence_items",
      "fk_evidences_signal_id_signals",
      "fk_evidences_entity_id_entities",
      "fk_evidences_raw_record_id_raw_records",
      "fk_evidences_workspace_id_workspaces",
      "fk_evidences_project_id_projects"
    ]
  },
  {
    "name": "data_gaps",
    "module": "M05",
    "status": "new",
    "phase": "C8",
    "purpose": "结构化数据缺口；逐市场逐数据域",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8", "references": "projects.id"},
      {"name": "task_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8", "references": "workbench_tasks.id"},
      {"name": "run_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C8", "references": "runs.id"},
      {"name": "step_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C8", "references": "run_steps.id"},
      {"name": "market", "type": "string(2)", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "data_domain", "type": "string(30)", "nullable": false, "status": "new", "phase": "C8", "enum": "data_domains"},
      {"name": "reason_code", "type": "string(80)", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "actual_value", "type": "json", "nullable": true, "status": "new", "phase": "C8"},
      {"name": "threshold_value", "type": "json", "nullable": true, "status": "new", "phase": "C8"},
      {"name": "impact", "type": "text", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "customer_text_zh", "type": "text", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "customer_text_en", "type": "text", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "remediation", "type": "text", "nullable": true, "status": "new", "phase": "C8"},
      {"name": "severity", "type": "string(20)", "nullable": false, "status": "new", "phase": "C8", "enum": "data_gaps.severity"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C8", "enum": "data_gaps.status"},
      {"name": "resolved_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C8"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C8"}
    ],
    "indexes": [
      {"name": "ix_data_gaps_task_market_domain", "columns": ["task_id", "market", "data_domain"], "unique": false}
    ]
  },
  {
    "name": "market_assessments",
    "module": "M05",
    "status": "new",
    "phase": "C8",
    "purpose": "逐市场质量评估与结论门禁",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8", "references": "projects.id"},
      {"name": "task_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C8", "references": "workbench_tasks.id"},
      {"name": "market", "type": "string(2)", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "market_role", "type": "string(10)", "nullable": false, "status": "new", "phase": "C8", "enum": "market_assessments.market_role"},
      {"name": "quality_status", "type": "string(30)", "nullable": false, "status": "new", "phase": "C8", "enum": "market_quality_status"},
      {"name": "conclusion_standard", "type": "string(30)", "nullable": true, "status": "new", "phase": "C8", "enum": "market_assessments.conclusion_standard"},
      {"name": "conclusion_quick", "type": "string(30)", "nullable": true, "status": "new", "phase": "C8", "enum": "market_assessments.conclusion_quick"},
      {"name": "evidence_grade", "type": "string(30)", "nullable": true, "status": "new", "phase": "C8", "enum": "evidence_grade"},
      {"name": "core_domain_coverage", "type": "json", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "sample_counts", "type": "json", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "thresholds", "type": "json", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "gap_ids", "type": "json", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "details_json", "type": "json", "nullable": false, "status": "new", "phase": "C8"},
      {"name": "computed_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C8"}
    ],
    "constraints": ["uq_market_assessments_task_market"]
  },
  {
    "name": "dataset_versions",
    "module": "M12",
    "status": "extend",
    "phase": "C8",
    "purpose": "交付数据集版本；绑定任务包与质量",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C8"},
      {"name": "task_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C8", "references": "workbench_tasks.id"},
      {"name": "market", "type": "string(2)", "nullable": true, "status": "extend", "phase": "C8"},
      {"name": "schema_hash", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C8"},
      {"name": "content_sha256", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C8"},
      {"name": "license_class", "type": "string(30)", "nullable": true, "status": "extend", "phase": "C8"},
      {"name": "quality_status", "type": "string(30)", "nullable": true, "status": "extend", "phase": "C8", "enum": "market_quality_status"}
    ]
  }
]
```

- [ ] **Step 3A: 在契约正文写入 C8 实现决定**

在契约 §1 的表清单后插入以下小节。C8 的 `test_c8_contract_gate.py` 逐项断言这些原文；缺任一项，C8 不得创建迁移 066。

````markdown
### C8 实现决定：数据集质量与任务包模板

- 任务包模板的事实源是代码注册表 `apps/api/src/data_intelligence_hub/services/workbench_templates.py`。C8 不创建 `task_templates` 表。
- C8 不创建第二套 claims、claim_evidence、report_artifacts 或 report_contract。
- C8 是 `market_assessments` 与 `data_gaps` 的唯一创建者。C5 的迁移 063 不创建这两张表；C8 在迁移 066 创建已登记的 `market_assessments` 与 `data_gaps`。
````

- [ ] **Step 4: 重新生成 registry**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json`

Expected: `registry built`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `23 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register C7-C8 claims quality and dataset objects"
```

---

### Task 5: C9/C10 报告生命周期与交付列

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `tables` 数组。
- Produces: `report_artifacts` 扩展（C9 发布列与 C10 交付列，含 `delivered_at`、`delivered_by`、`supersedes_delivery_id`）、`report_audit_events` 扩展（含 `artifact_id` 与审核 metadata 键 `reviewer_role`）。
- Produces: `report_reviewer_assignments`（含非空 `expires_at`）与内部审阅者指派/撤销路径。
- Produces: 报告发布与交付路径；`ck_report_artifacts_status`、`uq_report_artifacts_current_published`、`ck_report_artifacts_delivery_status`、`ck_report_artifacts_delivery_fields`。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_registry_contains_report_lifecycle_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {"report_artifacts", "report_audit_events"} <= names


def test_report_artifacts_has_publication_and_delivery_columns() -> None:
    registry = load_contract_registry()
    table = _table(registry, "report_artifacts")
    columns = {column["name"] for column in table["columns"]}
    assert {
        "status",
        "created_by",
        "published_at",
        "published_by",
        "supersedes_id",
        "superseded_at",
        "delivery_status",
        "delivery_class",
        "manifest_json",
        "manifest_sha256",
        "manifest_sidecar_sha256",
        "public_contract_json",
        "acceptance_snapshot_json",
        "acceptance_deadline",
        "delivered_at",
        "delivered_by",
        "supersedes_delivery_id",
        "quick_draft_of_artifact_id",
        "publish_idempotency_key_hash",
    } <= columns
    assert {
        "ck_report_artifacts_status",
        "uq_report_artifacts_current_published",
        "ck_report_artifacts_delivery_status",
        "ck_report_artifacts_delivery_class",
        "ck_report_artifacts_delivery_fields",
        "uq_report_artifacts_publish_idempotency",
    } <= set(table["constraints"])
    index_predicates = {
        index["name"]: index.get("where") for index in table["indexes"]
    }
    assert index_predicates["uq_report_artifacts_current_published"] == (
        "status = 'published'"
    )
    assert index_predicates["uq_report_artifacts_publish_idempotency"] == (
        "publish_idempotency_key_hash IS NOT NULL"
    )


def test_report_audit_events_has_artifact_id() -> None:
    registry = load_contract_registry()
    table = _table(registry, "report_audit_events")
    columns = {column["name"] for column in table["columns"]}
    assert {"artifact_id", "report_id", "metadata_json"} <= columns
    metadata = next(
        column for column in table["columns"] if column["name"] == "metadata_json"
    )
    assert "reviewer_role" in metadata["notes"]
    assert "reviewed_claim_digest" in metadata["notes"]
    assert "reviewer_assignment_id" in metadata["notes"]


def test_internal_reviewer_assignment_is_registered() -> None:
    registry = load_contract_registry()
    table = _table(registry, "report_reviewer_assignments")
    columns = {column["name"] for column in table["columns"]}
    assert {
        "id",
        "workspace_id",
        "project_id",
        "report_id",
        "artifact_id",
        "reviewer_user_id",
        "assignment_scope",
        "status",
        "assigned_by",
        "assigned_at",
        "expires_at",
        "revoked_at",
    } <= columns
    expires_at = next(
        column for column in table["columns"] if column["name"] == "expires_at"
    )
    assert expires_at["nullable"] is False
    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert enums["report_reviewer_assignments.assignment_scope"] == [
        "report_read",
        "report_review",
    ]
    assert enums["report_reviewer_assignments.status"] == ["active", "revoked"]
    assert "reviewer" not in enums["workspace_members.role"]


def test_owner_admin_inline_approval_actions_are_registered() -> None:
    registry = load_contract_registry()
    table = _table(registry, "workbench_approval_actions")
    columns = {column["name"] for column in table["columns"]}
    assert {
        "id",
        "workspace_id",
        "project_id",
        "task_id",
        "action_type",
        "requester_user_id",
        "approver_user_id",
        "status",
        "payload_json",
        "idempotency_key_hash",
        "created_at",
        "expires_at",
        "decided_at",
    } <= columns
    assert "ck_workbench_approval_actions_self_approval" in table["constraints"]
    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert enums["workbench_approval_actions.action_type"] == [
        "budget_overage",
        "package_addon",
        "project_key_change",
    ]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。缺 `report_artifacts`。

- [ ] **Step 3: 把以下对象追加到 `tables` 数组**

```json
[
  {
    "name": "report_artifacts",
    "module": "M07",
    "status": "extend",
    "phase": "C9",
    "purpose": "不可变报告合同、发布生命周期与交付封存",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C9"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C9", "enum": "report_artifacts.status"},
      {"name": "created_by", "type": "uuid", "nullable": true, "status": "extend", "phase": "C9", "references": "users.id"},
      {"name": "published_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C9"},
      {"name": "published_by", "type": "uuid", "nullable": true, "status": "extend", "phase": "C9", "references": "users.id"},
      {"name": "supersedes_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C9", "references": "report_artifacts.id"},
      {"name": "superseded_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C9"},
      {"name": "delivery_status", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C10", "enum": "report_artifacts.delivery_status", "default": "pending"},
      {"name": "delivery_class", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C10", "enum": "report_artifacts.delivery_class", "default": "formal", "notes": "formal 为 24 小时正式交付；quick_draft 为 Quick 2 小时方向稿。只在迁移 202610220068 创建"},
      {"name": "manifest_json", "type": "json", "nullable": true, "status": "extend", "phase": "C10"},
      {"name": "manifest_sha256", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C10"},
      {"name": "manifest_sidecar_sha256", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C10"},
      {"name": "public_contract_json", "type": "json", "nullable": true, "status": "extend", "phase": "C10"},
      {"name": "acceptance_snapshot_json", "type": "json", "nullable": true, "status": "extend", "phase": "C10"},
      {"name": "acceptance_deadline", "type": "datetime", "nullable": true, "status": "extend", "phase": "C10", "notes": "第 5 个工作日 23:59:59 UTC；formal delivered 必须非空；quick_draft 必须为空。只在迁移 202610220068 创建"},
      {"name": "delivered_at", "type": "datetime", "nullable": true, "status": "extend", "phase": "C10"},
      {"name": "delivered_by", "type": "uuid", "nullable": true, "status": "extend", "phase": "C10", "references": "users.id"},
      {"name": "supersedes_delivery_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C10", "references": "report_artifacts.id"},
      {"name": "quick_draft_of_artifact_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C10", "references": "report_artifacts.id", "notes": "quick_draft delivered 必须非空，指向正式交付产物。只在迁移 202610220068 创建"},
      {"name": "publish_idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C10"}
    ],
    "constraints": ["uq_report_artifacts_publish_idempotency", "ck_report_artifacts_status", "uq_report_artifacts_current_published", "ck_report_artifacts_delivery_status", "ck_report_artifacts_delivery_class", "ck_report_artifacts_delivery_fields"],
    "indexes": [
      {"name": "ix_report_artifacts_report_status", "columns": ["report_id", "status"], "unique": false},
      {"name": "uq_report_artifacts_current_published", "columns": ["report_id"], "unique": true, "where": "status = 'published'"},
      {"name": "uq_report_artifacts_publish_idempotency", "columns": ["workspace_id", "publish_idempotency_key_hash"], "unique": true, "where": "publish_idempotency_key_hash IS NOT NULL"},
      {"name": "ix_report_artifacts_delivery_status", "columns": ["delivery_status"], "unique": false}
    ]
  },
  {
    "name": "report_audit_events",
    "module": "M07",
    "status": "extend",
    "phase": "C9",
    "purpose": "报告审核、发布、交付与验收事件；只追加",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "existing", "phase": "C9"},
      {"name": "artifact_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C9", "references": "report_artifacts.id"},
      {"name": "report_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C9", "references": "reports.id"},
      {"name": "event_type", "type": "string(40)", "nullable": false, "status": "extend", "phase": "C9", "enum": "report_audit_events.event_type"},
      {"name": "metadata_json", "type": "text", "nullable": true, "status": "existing", "phase": "C9", "notes": "审核事件必须带 reviewer_role=internal_reviewer、reviewer_assignment_id、review_scope、contract_sha256 与 reviewed_contract_sha256、reviewed_data_sha256、reviewed_report_html_sha256、reviewed_sop_html_sha256、reviewed_claim_digest"}
    ],
    "constraints": ["ck_report_audit_events_target"]
  },
  {
    "name": "report_reviewer_assignments",
    "module": "M07",
    "status": "new",
    "phase": "C9",
    "purpose": "内部审核人主体与受限读/审核范围；不是客户工作区角色",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C9"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C9", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C9", "references": "projects.id"},
      {"name": "report_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C9", "references": "reports.id"},
      {"name": "artifact_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C9", "references": "report_artifacts.id"},
      {"name": "reviewer_user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C9", "references": "users.id"},
      {"name": "assignment_scope", "type": "string(30)", "nullable": false, "status": "new", "phase": "C9", "enum": "report_reviewer_assignments.assignment_scope", "default": "report_review"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C9", "enum": "report_reviewer_assignments.status", "default": "active"},
      {"name": "assigned_by", "type": "uuid", "nullable": false, "status": "new", "phase": "C9", "references": "users.id"},
      {"name": "assigned_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C9"},
      {"name": "expires_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C9", "notes": "到期后读与审核路径返回 403 reviewer_assignment_expired；不得为空"},
      {"name": "revoked_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C9"}
    ],
    "constraints": ["ck_report_reviewer_assignments_scope", "ck_report_reviewer_assignments_status"],
    "indexes": [
      {"name": "uq_report_reviewer_assignments_active", "columns": ["report_id", "reviewer_user_id"], "unique": true, "where": "status = 'active'"},
      {"name": "ix_report_reviewer_assignments_reviewer_status", "columns": ["reviewer_user_id", "status"], "unique": false}
    ]
  },
  {
    "name": "workbench_approval_actions",
    "module": "M10",
    "status": "new",
    "phase": "C5",
    "purpose": "owner/admin 对预算超支、加购与项目密钥变更的内联批准动作；无独立收件箱",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C5", "references": "projects.id"},
      {"name": "task_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C5", "references": "workbench_tasks.id"},
      {"name": "action_type", "type": "string(30)", "nullable": false, "status": "new", "phase": "C5", "enum": "workbench_approval_actions.action_type"},
      {"name": "requester_user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C5", "references": "users.id"},
      {"name": "approver_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C5", "references": "users.id"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C5", "enum": "workbench_approval_actions.status", "default": "pending"},
      {"name": "payload_json", "type": "json", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "new", "phase": "C5"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "expires_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C5"},
      {"name": "decided_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C5"}
    ],
    "constraints": [
      "ck_workbench_approval_actions_action_type",
      "ck_workbench_approval_actions_status",
      "ck_workbench_approval_actions_self_approval"
    ],
    "indexes": [
      {"name": "uq_workbench_approval_actions_idempotency", "columns": ["workspace_id", "idempotency_key_hash"], "unique": true, "where": "idempotency_key_hash IS NOT NULL"},
      {"name": "ix_workbench_approval_actions_task_status", "columns": ["task_id", "status"], "unique": false}
    ]
  }
]
```

- [ ] **Step 4: 重新生成 registry**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json`

Expected: `registry built`。

Verify the generated golden registry:

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python -c 'import json; r=json.load(open("configs/contracts/v1.1.0/registry.json")); t=next(x for x in r["tables"] if x["name"]=="report_reviewer_assignments"); c=next(x for x in t["columns"] if x["name"]=="expires_at"); assert c["nullable"] is False'`

Expected: exit code 0，无输出。`report_reviewer_assignments.expires_at` 在生成物中必须是非空列。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `26 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register C9-C10 report lifecycle and delivery columns"
```

---

### Task 6: C11/C12/C13 保留、删除、DSR 与客户租约表

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `tables` 数组。
- Produces: `workspace_pseudonym_salts`、`legal_holds`、`retention_cleanup_runs`、`retention_tombstones`。这四张 C11 表的列、约束与索引与 C11 计划的迁移 `069` 完全同名，不得出现 `target_type`、`target_id`、`authority` 或 `uq_legal_holds_active_target`。
- Produces: `deletion_requests`、`deletion_tombstones`、`deletion_subprocessor_receipts`、`deletion_proofs`、`deletion_replay_runs`、`deletion_replay_items`、`dsr_cases`、`privacy_audit_events`。
- Produces: `deferred` 中的 `mcp_customer_request_leases` 条目；不登记租约表。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_registry_contains_privacy_tables() -> None:
    registry = load_contract_registry()
    names = {table["name"] for table in registry["tables"]}
    assert {
        "workspace_pseudonym_salts",
        "legal_holds",
        "retention_cleanup_runs",
        "retention_tombstones",
        "deletion_requests",
        "deletion_tombstones",
        "deletion_subprocessor_receipts",
        "deletion_proofs",
        "deletion_replay_runs",
        "deletion_replay_items",
        "dsr_cases",
        "privacy_audit_events",
    } <= names
    assert "mcp_customer_request_leases" not in names


def test_c11_privacy_tables_match_c11_plan() -> None:
    registry = load_contract_registry()
    salt = _table(registry, "workspace_pseudonym_salts")
    hold = _table(registry, "legal_holds")
    cleanup = _table(registry, "retention_cleanup_runs")
    assert {column["name"] for column in salt["columns"]} == {
        "id",
        "workspace_id",
        "salt_version",
        "salt_b64",
        "created_at",
    }
    assert {
        "uq_workspace_pseudonym_salts_workspace_id",
        "ck_workspace_pseudonym_salts_salt_version",
        "fk_workspace_pseudonym_salts_workspace_id_workspaces",
    } <= set(salt["constraints"])
    assert {column["name"] for column in hold["columns"]} == {
        "id",
        "workspace_id",
        "project_id",
        "data_class",
        "status",
        "reason",
        "requested_by_user_id",
        "requested_at",
        "released_by_user_id",
        "released_at",
        "release_reason",
        "created_at",
    }
    assert {
        "ck_legal_holds_status",
        "ck_legal_holds_data_class",
        "ck_legal_holds_release_fields",
    } <= set(hold["constraints"])
    assert {index["name"] for index in hold["indexes"]} == {
        "ix_legal_holds_workspace_status",
        "ix_legal_holds_scope",
    }
    assert {column["name"] for column in cleanup["columns"]} == {
        "id",
        "mode",
        "status",
        "policy_version",
        "requested_by_user_id",
        "started_at",
        "finished_at",
        "cutoffs",
        "counts",
        "samples",
        "blocked",
        "error_message",
        "created_at",
    }
    assert {
        "ck_retention_cleanup_runs_mode",
        "ck_retention_cleanup_runs_status",
    } <= set(cleanup["constraints"])
    assert {index["name"] for index in cleanup["indexes"]} == {
        "ix_retention_cleanup_runs_created_at",
    }
    request = _table(registry, "deletion_requests")
    assert {"created_at", "updated_at"} <= {
        column["name"] for column in request["columns"]
    }
    assert {
        "ck_deletion_requests_target_type",
        "ck_deletion_requests_requested_by_role",
        "ck_deletion_requests_status",
        "ck_deletion_requests_target_scope",
        "fk_deletion_requests_workspace_id_workspaces",
        "fk_deletion_requests_project_id_projects",
        "fk_deletion_requests_requested_by_user_id_users",
        "fk_deletion_requests_approved_by_user_id_users",
        "fk_deletion_requests_confirmed_by_user_id_users",
    } <= set(request["constraints"])
    assert {
        "name": "uq_deletion_requests_active_target",
        "columns": ["workspace_id", "target_type", "target_id"],
        "unique": True,
        "where": "status IN ('pending_owner_approval', 'pending_confirmation', 'ready', 'blocked_legal_hold', 'executing')",
    } in request["indexes"]
    assert {
        "fk_deletion_tombstones_deletion_request_id_deletion_requests",
        "fk_deletion_tombstones_workspace_id_workspaces",
        "fk_deletion_tombstones_project_id_projects",
    } <= set(_table(registry, "deletion_tombstones")["constraints"])
    receipt = _table(registry, "deletion_subprocessor_receipts")
    assert {"created_at", "updated_at"} <= {
        column["name"] for column in receipt["columns"]
    }
    assert {
        "uq_deletion_subprocessor_receipts_request_name",
        "ck_deletion_subprocessor_receipts_status",
        "fk_deletion_subprocessor_receipts_deletion_request_id_deletion_requests",
        "fk_deletion_subprocessor_receipts_workspace_id_workspaces",
    } <= set(receipt["constraints"])
    assert {
        "uq_deletion_proofs_request",
        "uq_deletion_proofs_number",
        "fk_deletion_proofs_deletion_request_id_deletion_requests",
        "fk_deletion_proofs_workspace_id_workspaces",
    } <= set(_table(registry, "deletion_proofs")["constraints"])
    assert {
        "ck_deletion_replay_runs_status",
        "fk_deletion_replay_runs_workspace_id_workspaces",
    } <= set(_table(registry, "deletion_replay_runs")["constraints"])
    assert {
        "uq_deletion_replay_items_run_target",
        "ck_deletion_replay_items_status",
        "fk_deletion_replay_items_run_id_deletion_replay_runs",
    } <= set(_table(registry, "deletion_replay_items")["constraints"])
    dsr = _table(registry, "dsr_cases")
    assert {"created_at", "updated_at"} <= {
        column["name"] for column in dsr["columns"]
    }
    assert {
        "uq_dsr_cases_number",
        "ck_dsr_cases_request_type",
        "ck_dsr_cases_status",
        "ck_dsr_cases_responsibility",
        "fk_dsr_cases_workspace_id_workspaces",
        "fk_dsr_cases_project_id_projects",
        "fk_dsr_cases_deletion_request_id_deletion_requests",
    } <= set(dsr["constraints"])
    assert {
        "uq_privacy_audit_events_stream_sequence",
        "uq_privacy_audit_events_stream_digest",
        "ck_privacy_audit_events_sequence",
        "ck_privacy_audit_events_predecessor",
        "ck_privacy_audit_events_actor_kind",
        "fk_privacy_audit_events_workspace_id_workspaces",
        "fk_privacy_audit_events_actor_user_id_users",
        "fk_privacy_audit_events_predecessor",
    } <= set(_table(registry, "privacy_audit_events")["constraints"])


def test_customer_lease_is_deferred() -> None:
    registry = load_contract_registry()
    deferred = {(item["kind"], item["name"]) for item in registry["deferred"]}
    assert ("table", "mcp_customer_request_leases") in deferred
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。缺 `workspace_pseudonym_salts`。

- [ ] **Step 3: 把以下对象追加到 `tables` 数组**

```json
[
  {
    "name": "workspace_pseudonym_salts",
    "module": "M05",
    "status": "new",
    "phase": "C11",
    "purpose": "工作区级伪名盐；一工作区一行",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11", "references": "workspaces.id"},
      {"name": "salt_version", "type": "string(20)", "nullable": false, "status": "new", "phase": "C11", "enum": "workspace_pseudonym_salts.salt_version", "default": "v1"},
      {"name": "salt_b64", "type": "text", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"}
    ],
    "constraints": ["uq_workspace_pseudonym_salts_workspace_id", "ck_workspace_pseudonym_salts_salt_version", "fk_workspace_pseudonym_salts_workspace_id_workspaces"]
  },
  {
    "name": "legal_holds",
    "module": "M08",
    "status": "new",
    "phase": "C11",
    "purpose": "法律保留；按工作区、项目与数据类阻止清理",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C11", "references": "projects.id"},
      {"name": "data_class", "type": "string(40)", "nullable": true, "status": "new", "phase": "C11", "enum": "data_class"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C11", "enum": "legal_holds.status", "default": "active"},
      {"name": "reason", "type": "text", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "requested_by_user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11", "references": "users.id"},
      {"name": "requested_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "released_by_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C11", "references": "users.id"},
      {"name": "released_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C11"},
      {"name": "release_reason", "type": "text", "nullable": true, "status": "new", "phase": "C11"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"}
    ],
    "constraints": ["ck_legal_holds_status", "ck_legal_holds_data_class", "ck_legal_holds_release_fields", "fk_legal_holds_workspace_id_workspaces", "fk_legal_holds_project_id_projects", "fk_legal_holds_requested_by_user_id_users", "fk_legal_holds_released_by_user_id_users"],
    "indexes": [
      {"name": "ix_legal_holds_workspace_status", "columns": ["workspace_id", "status"], "unique": false},
      {"name": "ix_legal_holds_scope", "columns": ["workspace_id", "project_id", "data_class"], "unique": false}
    ]
  },
  {
    "name": "retention_cleanup_runs",
    "module": "M08",
    "status": "new",
    "phase": "C11",
    "purpose": "保留清理运行；只记录 execute",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "mode", "type": "string(20)", "nullable": false, "status": "new", "phase": "C11", "enum": "retention_cleanup_runs.mode"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C11", "enum": "retention_cleanup_runs.status"},
      {"name": "policy_version", "type": "string(40)", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "requested_by_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C11", "references": "users.id"},
      {"name": "started_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "finished_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "cutoffs", "type": "json", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "counts", "type": "json", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "samples", "type": "json", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "blocked", "type": "json", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "error_message", "type": "text", "nullable": true, "status": "new", "phase": "C11"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"}
    ],
    "constraints": ["ck_retention_cleanup_runs_mode", "ck_retention_cleanup_runs_status", "fk_retention_cleanup_runs_requested_by_user_id_users"],
    "indexes": [
      {"name": "ix_retention_cleanup_runs_created_at", "columns": ["created_at"], "unique": false}
    ]
  },
  {
    "name": "retention_tombstones",
    "module": "M08",
    "status": "new",
    "phase": "C11",
    "purpose": "保留清理墓碑；逐被删除主体",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C11", "references": "projects.id"},
      {"name": "data_class", "type": "string(40)", "nullable": false, "status": "new", "phase": "C11", "enum": "data_class"},
      {"name": "subject_type", "type": "string(80)", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "subject_id", "type": "string(120)", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "cleanup_run_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C11", "references": "retention_cleanup_runs.id"},
      {"name": "deleted_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C11"},
      {"name": "reason", "type": "string(40)", "nullable": false, "status": "new", "phase": "C11", "enum": "retention_tombstones.reason", "default": "retention_ttl"},
      {"name": "metadata_json", "type": "json", "nullable": false, "status": "new", "phase": "C11"}
    ],
    "constraints": ["uq_retention_tombstones_subject", "ck_retention_tombstones_data_class", "ck_retention_tombstones_reason", "fk_retention_tombstones_workspace_id_workspaces", "fk_retention_tombstones_project_id_projects", "fk_retention_tombstones_cleanup_run_id_retention_cleanup_runs"],
    "indexes": [
      {"name": "ix_retention_tombstones_workspace_class", "columns": ["workspace_id", "data_class"], "unique": false},
      {"name": "ix_retention_tombstones_cleanup_run", "columns": ["cleanup_run_id"], "unique": false}
    ]
  },
  {
    "name": "deletion_requests",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "删除请求与二次确认状态机",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "projects.id"},
      {"name": "target_type", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12", "enum": "deletion_requests.target_type"},
      {"name": "target_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "target_name_snapshot", "type": "string(200)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "requested_by_user_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "users.id"},
      {"name": "requested_by_role", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12", "enum": "deletion_requests.requested_by_role"},
      {"name": "status", "type": "string(30)", "nullable": false, "status": "new", "phase": "C12", "enum": "deletion_requests.status"},
      {"name": "reason", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "confirmation_token_hash", "type": "string(64)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "confirmation_expires_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "approved_by_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "users.id"},
      {"name": "approved_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "confirmed_by_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "users.id"},
      {"name": "confirmed_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "decided_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "rejection_reason", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "execution_started_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "completed_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "failed_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "failure_code", "type": "string(80)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "failure_detail", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "tombstone_digest", "type": "string(71)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "updated_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": [
      "ck_deletion_requests_target_type",
      "ck_deletion_requests_requested_by_role",
      "ck_deletion_requests_status",
      "ck_deletion_requests_target_scope",
      "fk_deletion_requests_workspace_id_workspaces",
      "fk_deletion_requests_project_id_projects",
      "fk_deletion_requests_requested_by_user_id_users",
      "fk_deletion_requests_approved_by_user_id_users",
      "fk_deletion_requests_confirmed_by_user_id_users"
    ],
    "indexes": [
      {"name": "uq_deletion_requests_active_target", "columns": ["workspace_id", "target_type", "target_id"], "unique": true, "where": "status IN ('pending_owner_approval', 'pending_confirmation', 'ready', 'blocked_legal_hold', 'executing')"}
    ]
  },
  {
    "name": "deletion_tombstones",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "删除墓碑；逐对象类",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "deletion_request_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "deletion_requests.id"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "projects.id"},
      {"name": "target_type", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "target_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "object_class", "type": "string(60)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "row_count", "type": "integer", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "content_digest", "type": "string(71)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "deleted_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": [
      "uq_deletion_tombstones_request_class_target",
      "fk_deletion_tombstones_deletion_request_id_deletion_requests",
      "fk_deletion_tombstones_workspace_id_workspaces",
      "fk_deletion_tombstones_project_id_projects"
    ]
  },
  {
    "name": "deletion_subprocessor_receipts",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "子处理者删除回执",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "deletion_request_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "deletion_requests.id"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "subprocessor_name", "type": "string(120)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "status", "type": "string(30)", "nullable": false, "status": "new", "phase": "C12", "enum": "deletion_subprocessor_receipts.status"},
      {"name": "request_reference", "type": "string(200)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "receipt_reference", "type": "string(200)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "requested_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "received_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "evidence_note", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "recorded_by_operator", "type": "string(200)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "updated_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": [
      "uq_deletion_subprocessor_receipts_request_name",
      "ck_deletion_subprocessor_receipts_status",
      "fk_deletion_subprocessor_receipts_deletion_request_id_deletion_requests",
      "fk_deletion_subprocessor_receipts_workspace_id_workspaces"
    ]
  },
  {
    "name": "deletion_proofs",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "删除证明；一请求一证明",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "deletion_request_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "deletion_requests.id"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "proof_number", "type": "string(40)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "payload", "type": "json", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "proof_digest", "type": "string(71)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "audit_head_digest", "type": "string(71)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "issued_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": [
      "uq_deletion_proofs_request",
      "uq_deletion_proofs_number",
      "fk_deletion_proofs_deletion_request_id_deletion_requests",
      "fk_deletion_proofs_workspace_id_workspaces"
    ]
  },
  {
    "name": "deletion_replay_runs",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "备份删除重放批次",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "workspace_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "manifest_digest", "type": "string(71)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "source_backup_ref", "type": "string(200)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12", "enum": "deletion_replay_runs.status"},
      {"name": "matched_count", "type": "integer", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "replayed_count", "type": "integer", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "failed_count", "type": "integer", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "operator_label", "type": "string(200)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "error_code", "type": "string(80)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "started_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "finished_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": ["ck_deletion_replay_runs_status", "fk_deletion_replay_runs_workspace_id_workspaces"]
  },
  {
    "name": "deletion_replay_items",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "备份删除重放条目",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "run_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "deletion_replay_runs.id"},
      {"name": "target_type", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "target_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "status", "type": "string(30)", "nullable": false, "status": "new", "phase": "C12", "enum": "deletion_replay_items.status"},
      {"name": "detail", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": [
      "uq_deletion_replay_items_run_target",
      "ck_deletion_replay_items_status",
      "fk_deletion_replay_items_run_id_deletion_replay_runs"
    ]
  },
  {
    "name": "dsr_cases",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "人工 DSR 案件",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "project_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "projects.id"},
      {"name": "case_number", "type": "string(40)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "request_type", "type": "string(30)", "nullable": false, "status": "new", "phase": "C12", "enum": "dsr_cases.request_type"},
      {"name": "status", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12", "enum": "dsr_cases.status"},
      {"name": "responsibility", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12", "enum": "dsr_cases.responsibility"},
      {"name": "requester_ref", "type": "string(200)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "verification_method", "type": "string(80)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "verified_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "verification_note", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "received_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "due_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "closed_at", "type": "datetime", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "deletion_request_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "deletion_requests.id"},
      {"name": "summary", "type": "text", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "created_by_operator", "type": "string(200)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "created_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "updated_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"}
    ],
    "constraints": [
      "uq_dsr_cases_number",
      "ck_dsr_cases_request_type",
      "ck_dsr_cases_status",
      "ck_dsr_cases_responsibility",
      "fk_dsr_cases_workspace_id_workspaces",
      "fk_dsr_cases_project_id_projects",
      "fk_dsr_cases_deletion_request_id_deletion_requests"
    ]
  },
  {
    "name": "privacy_audit_events",
    "module": "M08",
    "status": "new",
    "phase": "C12",
    "purpose": "隐私审计事件；按 stream 哈希链",
    "primary_key": ["id"],
    "columns": [
      {"name": "id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "workspace_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12", "references": "workspaces.id"},
      {"name": "stream_type", "type": "string(30)", "nullable": false, "status": "new", "phase": "C12", "enum": "privacy_audit_events.stream_type"},
      {"name": "stream_id", "type": "uuid", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "sequence_number", "type": "integer", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "previous_event_digest", "type": "string(71)", "nullable": true, "status": "new", "phase": "C12"},
      {"name": "event_digest", "type": "string(71)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "event_type", "type": "string(100)", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "actor_user_id", "type": "uuid", "nullable": true, "status": "new", "phase": "C12", "references": "users.id"},
      {"name": "actor_kind", "type": "string(20)", "nullable": false, "status": "new", "phase": "C12", "enum": "privacy_audit_events.actor_kind"},
      {"name": "payload", "type": "json", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "occurred_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12"},
      {"name": "recorded_at", "type": "datetime", "nullable": false, "status": "new", "phase": "C12", "notes": "创建时间；只追加表，无 updated_at"}
    ],
    "constraints": [
      "uq_privacy_audit_events_stream_sequence",
      "uq_privacy_audit_events_stream_digest",
      "ck_privacy_audit_events_sequence",
      "ck_privacy_audit_events_predecessor",
      "ck_privacy_audit_events_actor_kind",
      "fk_privacy_audit_events_workspace_id_workspaces",
      "fk_privacy_audit_events_actor_user_id_users",
      "fk_privacy_audit_events_predecessor"
    ]
  }
]
```

- [ ] **Step 4: 重新生成 registry**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json`

Expected: `registry built`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `29 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register C11-C12 privacy and deletion tables"
```

### Task 7: 枚举与状态机

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: 每个 column 的 `enum` 字段。
- Produces: `enums` 全量数组。所有 `column.enum` 必须能解析。
- Produces: `settle` 正数、`release` 负数的机器规则。
- Produces: C2-C13 的审核、质量、隐私、定价置信度与客户 MCP 枚举。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_every_column_enum_reference_resolves() -> None:
    registry = load_contract_registry()
    enum_names = {item["name"] for item in registry["enums"]}
    missing = {
        column["enum"]
        for table in registry["tables"]
        for column in table["columns"]
        if "enum" in column and column["enum"] not in enum_names
    }
    assert missing == set()


def test_entry_kind_values_and_sign_rule() -> None:
    registry = load_contract_registry()
    item = next(enum for enum in registry["enums"] if enum["name"] == "entry_kind")
    assert item["values"] == [
        "estimate",
        "reserve",
        "accrued",
        "settle",
        "release",
        "block",
    ]
    assert item["rule"] == "settle must be positive; release must be negative"


def test_run_status_bans_held_degraded_partial() -> None:
    registry = load_contract_registry()
    item = next(enum for enum in registry["enums"] if enum["name"] == "runs.status")
    assert item["values"] == ["queued", "running", "completed", "failed", "cancelled"]
    assert set(item["banned_values"]) == {"held", "degraded", "partial"}


def test_market_code_has_eleven_formal_markets() -> None:
    registry = load_contract_registry()
    item = next(enum for enum in registry["enums"] if enum["name"] == "market_code")
    assert item["values"] == [
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
    ]


def test_claim_review_and_report_status_values() -> None:
    registry = load_contract_registry()
    review = next(
        enum for enum in registry["enums"] if enum["name"] == "claim_review_status"
    )
    report = next(
        enum for enum in registry["enums"] if enum["name"] == "report_artifacts.status"
    )
    delivery = next(
        enum
        for enum in registry["enums"]
        if enum["name"] == "report_artifacts.delivery_status"
    )
    assert review["values"] == ["draft", "pending", "approved", "rejected", "stale"]
    assert report["values"] == ["draft", "published", "superseded"]
    assert delivery["values"] == ["pending", "delivered", "superseded"]
    assert delivery["values"] != report["values"]


def test_internal_reviewer_and_inline_approval_enums() -> None:
    registry = load_contract_registry()
    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert enums["report_reviewer_assignments.assignment_scope"] == [
        "report_read",
        "report_review",
    ]
    assert enums["report_reviewer_assignments.status"] == ["active", "revoked"]
    assert enums["workbench_approval_actions.action_type"] == [
        "budget_overage",
        "package_addon",
        "project_key_change",
    ]
    assert enums["workbench_approval_actions.status"] == [
        "pending",
        "approved",
        "rejected",
        "expired",
    ]
    assert enums["workspace_members.role"] == ["owner", "admin", "member"]


def test_deletion_status_has_nine_values() -> None:
    registry = load_contract_registry()
    item = next(
        enum for enum in registry["enums"] if enum["name"] == "deletion_requests.status"
    )
    assert item["values"] == [
        "pending_owner_approval",
        "pending_confirmation",
        "ready",
        "blocked_legal_hold",
        "executing",
        "completed",
        "failed",
        "rejected",
        "cancelled",
    ]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。`enums` 只有 seed `runs.status`。`missing` 不为空。

- [ ] **Step 3: 用以下数组替换附录 A 的 `enums` 数组**

```json
[
  {"name": "runs.status", "values": ["queued", "running", "completed", "failed", "cancelled"], "status": "frozen", "phase": "C6", "banned_values": ["held", "degraded", "partial"], "source": "契约 v1 §2.1"},
  {"name": "runs.outcome", "values": ["success", "empty", "config_gated", "failed"], "status": "frozen", "phase": "C6", "banned_values": ["partial"], "source": "契约 v1 §2.3"},
  {"name": "run_steps.status", "values": ["pending", "running", "success", "empty", "config_gated", "failed", "skipped"], "status": "frozen", "phase": "C6", "source": "契约 v1 §2.2"},
  {"name": "health_status", "values": ["healthy", "stable", "degraded", "outage", "unknown"], "status": "frozen", "phase": "C2", "source": "契约 v1 §2.4"},
  {"name": "evidence_grade", "values": ["L0_unverified", "L1_contract", "L2_fixture_local", "L3_live_single", "L4_authorized_live"], "status": "frozen", "phase": "C7", "source": "契约 v1 §2.5"},
  {"name": "claims.state", "values": ["confirmed", "directional", "hypothesis", "evidence_gap", "blocked"], "status": "frozen", "phase": "C7", "source": "契约 v1 §2.6"},
  {"name": "gate_status", "values": ["pending", "pass", "fail", "blocked", "expired"], "status": "frozen", "phase": "C4", "source": "契约 v1 §2.7"},
  {"name": "gate_id", "values": ["G-Plan", "G-Cost", "G-Evidence", "G-Claim", "G-Publish"], "status": "frozen", "phase": "C4", "source": "契约 v1 §2.8"},
  {"name": "entry_kind", "values": ["estimate", "reserve", "accrued", "settle", "release", "block"], "status": "frozen", "phase": "C5", "source": "契约 v1 §2.7.1", "rule": "settle must be positive; release must be negative"},
  {"name": "tool_prices.confidence", "values": ["high", "medium", "low", "unknown"], "status": "new", "phase": "C5", "source": "C5 定价（price_book_v1.json 字段）"},
  {"name": "market_code", "values": ["US", "GB", "DE", "FR", "IT", "ES", "IE", "NL", "BE", "AT", "PL"], "status": "new", "phase": "C4", "source": "设计 §2.4"},
  {"name": "workspace_members.role", "values": ["owner", "admin", "member"], "status": "extended", "phase": "C2", "source": "设计 §7.1"},
  {"name": "audit_events.actor_type", "values": ["user", "system", "project_key"], "status": "new", "phase": "C2", "source": "C2 契约 §2.9"},
  {"name": "audit_events.result", "values": ["success", "denied", "failed"], "status": "new", "phase": "C2", "source": "C2 契约 §2.9"},
  {"name": "project_api_keys.status", "values": ["active", "rotating", "revoked", "expired"], "status": "new", "phase": "C3", "source": "设计 §7.2"},
  {"name": "workbench_tasks.status", "values": ["draft", "submitted", "cancelled"], "status": "new", "phase": "C4", "source": "C4 契约"},
  {"name": "workbench_tasks.package_type", "values": ["quick", "standard"], "status": "new", "phase": "C4", "source": "设计 §4.2"},
  {"name": "workbench_tasks.task_type", "values": ["T1", "T2", "T3", "T4", "T5"], "status": "new", "phase": "C4", "source": "PRD §8"},
  {"name": "run_step_attempts.status", "values": ["running", "success", "empty", "config_gated", "failed"], "status": "new", "phase": "C6", "source": "C6 契约"},
  {"name": "claim_review_status", "values": ["draft", "pending", "approved", "rejected", "stale"], "status": "new", "phase": "C7", "source": "C7 契约 §2.6.1"},
  {"name": "claim_risk_flags", "values": ["medical", "health", "safety", "legal", "recall", "children", "causal_language", "single_source", "price_comparison"], "status": "new", "phase": "C7", "source": "C7 契约 §2.6.2"},
  {"name": "claims.blocked_reason", "values": ["rights", "permission", "configuration", "gate", "upstream"], "status": "new", "phase": "C7", "source": "C7 契约 §2.6.3"},
  {"name": "claim_evidence.role", "values": ["support", "counter", "context", "gap"], "status": "frozen", "phase": "C7", "source": "契约 v1 §1.1"},
  {"name": "source_cluster_basis", "values": ["explicit", "content_hash", "platform_item", "url", "unresolved"], "status": "new", "phase": "C7", "source": "C7 契约"},
  {"name": "data_domains", "values": ["products", "reviews", "creator_content", "ads", "trends"], "status": "new", "phase": "C8", "source": "设计 §3.3"},
  {"name": "domain_status", "values": ["pass", "partial", "missing", "blocked"], "status": "new", "phase": "C8", "source": "设计 §5.2"},
  {"name": "market_quality_status", "values": ["qualified", "qualified_with_gap", "not_qualified"], "status": "new", "phase": "C8", "source": "设计 §5.2"},
  {"name": "data_gaps.severity", "values": ["info", "warning", "blocking", "critical"], "status": "new", "phase": "C8", "source": "设计 §5.2"},
  {"name": "data_gaps.status", "values": ["open", "mitigated", "accepted", "closed"], "status": "new", "phase": "C8", "source": "设计 §5.2"},
  {"name": "market_assessments.market_role", "values": ["primary", "compare"], "status": "new", "phase": "C8", "source": "设计 §2.4"},
  {"name": "market_assessments.conclusion_standard", "values": ["enter", "conditional_enter", "do_not_enter", "insufficient_evidence"], "status": "new", "phase": "C8", "source": "设计 §5.2"},
  {"name": "market_assessments.conclusion_quick", "values": ["worth_validating", "deprioritize", "key_risk", "evidence_gap", "recommend_standard_scope"], "status": "new", "phase": "C8", "source": "设计 §5.2"},
  {"name": "report_artifacts.status", "values": ["draft", "published", "superseded"], "status": "new", "phase": "C9", "source": "C9 契约 §2.7.2"},
  {"name": "report_artifacts.delivery_status", "values": ["pending", "delivered", "superseded"], "status": "new", "phase": "C10", "source": "C10 契约 §2.9"},
  {"name": "report_audit_events.event_type", "values": ["report_draft_created", "report_review_approved", "report_review_rejected", "report_published", "report_superseded", "gate_evaluated", "delivery_published", "delivery_downloaded", "delivery_tamper_detected", "delivery_pii_detected", "acceptance_snapshot_appended", "delivery_superseded", "acceptance_accepted", "acceptance_disputed", "acceptance_deemed_accepted"], "status": "extended", "phase": "C9", "source": "C9 契约 §2.7.3 与 C10 契约 §2.10/§2.16"},
  {"name": "report_artifacts.delivery_class", "values": ["formal", "quick_draft"], "status": "new", "phase": "C10", "source": "C10 契约 §2.9"},
  {"name": "report_reviewer_assignments.assignment_scope", "values": ["report_read", "report_review"], "status": "new", "phase": "C9", "source": "C1 §3.10 内部审核人受限范围"},
  {"name": "report_reviewer_assignments.status", "values": ["active", "revoked"], "status": "new", "phase": "C9", "source": "C1 §3.10 内部审核人指派状态"},
  {"name": "workbench_approval_actions.action_type", "values": ["budget_overage", "package_addon", "project_key_change"], "status": "new", "phase": "C5", "source": "C1 §3.11 内联批准动作"},
  {"name": "workbench_approval_actions.status", "values": ["pending", "approved", "rejected", "expired"], "status": "new", "phase": "C5", "source": "C1 §3.11 内联批准状态"},
  {"name": "workspace_pseudonym_salts.salt_version", "values": ["v1"], "status": "new", "phase": "C11", "source": "C11 契约 §2.9"},
  {"name": "legal_holds.status", "values": ["active", "released"], "status": "new", "phase": "C11", "source": "C11 契约 §2.9"},
  {"name": "data_class", "values": ["raw_response", "normalized_dataset", "report_delivery", "run_log", "security_access_audit", "backup"], "status": "new", "phase": "C11", "source": "C11 契约 §2.9"},
  {"name": "retention_cleanup_runs.mode", "values": ["dry_run", "execute"], "status": "new", "phase": "C11", "source": "C11 契约 §2.9"},
  {"name": "retention_cleanup_runs.status", "values": ["completed", "blocked", "failed"], "status": "new", "phase": "C11", "source": "C11 契约 §2.9"},
  {"name": "retention_tombstones.reason", "values": ["retention_ttl"], "status": "new", "phase": "C11", "source": "C11 契约 §2.9"},
  {"name": "deletion_requests.target_type", "values": ["project", "workspace"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "deletion_requests.requested_by_role", "values": ["owner", "admin"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "deletion_requests.status", "values": ["pending_owner_approval", "pending_confirmation", "ready", "blocked_legal_hold", "executing", "completed", "failed", "rejected", "cancelled"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "deletion_subprocessor_receipts.status", "values": ["pending", "requested", "acknowledged", "not_applicable"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "dsr_cases.request_type", "values": ["access", "rectification", "restriction", "deletion"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "dsr_cases.status", "values": ["received", "verifying", "in_progress", "completed", "rejected", "closed"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "dsr_cases.responsibility", "values": ["controller", "processor", "undetermined"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "deletion_replay_runs.status", "values": ["pending", "running", "completed", "failed"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "deletion_replay_items.status", "values": ["replayed", "skipped_absent", "failed"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "privacy_audit_events.stream_type", "values": ["deletion_request", "legal_hold", "dsr_case", "deletion_replay"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"},
  {"name": "privacy_audit_events.actor_kind", "values": ["user", "operator", "system"], "status": "new", "phase": "C12", "source": "C12 契约 §2.9"}
]
```

- [ ] **Step 4: 重新生成 registry**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json`

Expected: `registry built`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `35 passed`。

- [ ] **Step 6: 运行 checker**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py check --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --registry configs/contracts/v1.1.0/registry.json`

Expected: `registry check OK`。

- [ ] **Step 7: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): freeze C2-C13 enums and state machines"
```

### Task 8: C2-C13 接口路径、客户 MCP 八工具与错误码

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `paths`、`mcp`、`error_codes` 数组。
- Produces: 客户 MCP 路径 `/mcp/customer` 与八个工具名。
- Produces: C2、C3、C4、C6、C7、C9、C10、C12、C13 的路径与错误码。
- Produces: 每个 path 的 `error_codes` 必须存在于 `error_codes`。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_customer_mcp_has_exactly_eight_named_tools() -> None:
    registry = load_contract_registry()
    assert registry["mcp"]["endpoint"] == "/mcp/customer"
    names = [tool["name"] for tool in registry["mcp"]["tools"]]
    assert names == [
        "discover_capabilities",
        "estimate_task",
        "create_task",
        "get_task",
        "cancel_task",
        "get_delivery_manifest",
        "get_evidence",
        "collect",
    ]


def test_customer_mcp_forbids_endpoint_level_tools() -> None:
    registry = load_contract_registry()
    forbidden = set(registry["mcp"]["forbidden_tools"])
    assert {"collect_endpoint", "raw_provider_call", "tiktok_creator_cookie"} <= forbidden


def test_customer_mcp_path_is_registered() -> None:
    registry = load_contract_registry()
    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("POST", "/mcp/customer") in paths
    assert ("GET", "/mcp/customer") in paths


def test_c2_c3_c4_paths_are_registered() -> None:
    registry = load_contract_registry()
    paths = {item["path"] for item in registry["paths"]}
    assert {
        "/api/projects/{project_id}/members",
        "/api/projects/{project_id}/members/{user_id}",
        "/api/workspaces/current/members/{user_id}",
        "/api/audit-events",
        "/api/audit-events/verify",
        "/api/projects/{project_id}/keys",
        "/api/projects/{project_id}/keys/{key_id}/rotate",
        "/api/workbench/tasks",
        "/api/runs",
    } <= paths
    audit_actions = registry["audit_actions"]
    assert audit_actions["version"] == "audit-actions.v1"
    actions = {item["name"] for item in audit_actions["actions"]}
    assert {
        "auth.login.succeeded",
        "auth.login.failed",
        "auth.logout.succeeded",
        "task.created",
        "task.cancelled",
        "task.retried",
        "budget.price.changed",
        "budget.limit.changed",
        "budget.blocked",
        "claim.review.submitted",
        "claim.review.approved",
        "claim.review.rejected",
        "claim.review.overridden",
        "claim.blocked",
        "claim.unblocked",
        "config.switch.changed",
        "delivery.published",
        "delivery.projection.viewed",
        "privacy.projection.applied",
        "reviewer.access.granted",
        "reviewer.access.denied",
        "reviewer.assignment.created",
        "reviewer.assignment.revoked",
    } <= actions
    assert len(actions) == len(audit_actions["actions"])


def test_report_and_privacy_paths_are_registered() -> None:
    registry = load_contract_registry()
    paths = {item["path"] for item in registry["paths"]}
    assert {
        "/api/reports/{report_id}/contract",
        "/api/reports/{report_id}/publish",
        "/api/reports/{artifact_id}/delivery",
        "/api/privacy/deletion-requests",
        "/api/privacy/dsr-cases",
        "/api/privacy/audit-events",
    } <= paths


def test_report_lifecycle_paths_and_internal_reviewer_are_registered() -> None:
    registry = load_contract_registry()
    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("POST", "/api/reports/drafts") in paths
    assert ("POST", "/api/reports/{report_id}/reviewers") in paths
    assert ("DELETE", "/api/reports/{report_id}/reviewers/{user_id}") in paths
    reviews = next(
        item for item in registry["paths"] if item["id"] == "reports.reviews.create"
    )
    assert reviews["audience"] == "internal"
    assert reviews["auth"] == "internal"
    assert {
        "reviewer_assignment_required",
        "reviewer_assignment_expired",
        "reviewer_self_review_forbidden",
        "reviewer_assignment_invalid",
        "state_conflict",
    } <= set(reviews["error_codes"])
    by_id = {item["id"]: item for item in registry["paths"]}
    for path_id in (
        "reports.contract",
        "reports.artifact",
        "reports.sop",
        "reports.revisions",
    ):
        assert {
            "reviewer_assignment_required",
            "reviewer_assignment_expired",
        } <= set(by_id[path_id]["error_codes"])
    for path_id in ("reports.reviewers.assign", "reports.reviewers.revoke"):
        assert "reviewer_assignment_expired" in by_id[path_id]["error_codes"]


def test_inline_approval_paths_are_registered() -> None:
    registry = load_contract_registry()
    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("POST", "/api/workbench/tasks/{task_id}/approvals") in paths
    assert (
        "POST",
        "/api/workbench/tasks/{task_id}/approvals/{approval_id}",
    ) in paths
    decide = next(
        item
        for item in registry["paths"]
        if item["id"] == "workbench.tasks.approvals.decide"
    )
    assert "approval_self_approval_forbidden" in decide["error_codes"]


def test_report_lifecycle_error_codes_are_registered() -> None:
    registry = load_contract_registry()
    codes = {item["code"] for item in registry["error_codes"]}
    assert {
        "report_quality_not_ready",
        "delivery_not_publishable",
        "delivery_input_invalid",
        "publish_forbidden",
        "idempotency_key_required",
        "dataset_export_internal_isolated_source",
        "report_contract_not_published",
        "report_contract_hash_mismatch",
        "report_contract_invalid",
        "report_artifact_not_draft",
        "report_artifact_incomplete",
        "report_artifact_integrity_failed",
        "report_review_required",
        "report_publish_gate_blocked",
        "report_revision_target_invalid",
        "reviewer_assignment_required",
        "reviewer_self_review_forbidden",
        "reviewer_assignment_invalid",
        "reviewer_assignment_expired",
        "audit_action_unregistered",
        "report_forbidden_language",
    } <= codes
    publish = next(
        item for item in registry["paths"] if item["id"] == "delivery.publish"
    )
    assert {
        "publish_forbidden",
        "delivery_not_publishable",
        "delivery_input_invalid",
        "idempotency_key_required",
        "gate_failed",
    } <= set(publish["error_codes"])
    export = next(
        item for item in registry["paths"] if item["id"] == "datasets.export.create"
    )
    assert "dataset_export_internal_isolated_source" in export["error_codes"]


def test_report_shares_is_deferred() -> None:
    registry = load_contract_registry()
    deferred = {(item["kind"], item["name"]) for item in registry["deferred"]}
    tables = {table["name"] for table in registry["tables"]}
    assert ("table", "report_shares") in deferred
    assert ("path", "reports.share") in deferred
    assert ("path", "reports.public.access") in deferred
    assert "report_shares" not in tables
    paths = {item["path"] for item in registry["paths"]}
    assert "/api/reports/{report_id}/share" not in paths
    assert "/api/reports/public/{token}" not in paths


def test_design_failure_codes_are_registered() -> None:
    registry = load_contract_registry()
    codes = {item["code"] for item in registry["error_codes"]}
    assert {
        "tool_not_allowed",
        "quota_exceeded",
        "approval_required",
        "tool_not_executable",
        "tool_not_priced",
        "market_unsupported",
        "cookie_not_accepted",
        "project_access_forbidden",
        "workspace_owner_required",
        "workspace_role_invalid",
        "workspace_last_owner_required",
        "task_locked",
        "workflow_version_already_submitted",
        "taxonomy_unavailable",
        "idempotency_conflict",
        "quota_account_missing",
        "package_type_invalid",
        "comparison_markets_exceeded",
        "acceptance_contact_not_member",
        "budget_invalid",
    } <= codes
    assert "mfa_required" not in codes


def test_c4_c5_c6_paths_are_registered() -> None:
    registry = load_contract_registry()
    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("PATCH", "/api/workbench/tasks/{task_id}") in paths
    assert ("GET", "/api/workbench/tasks/{task_id}/gates") in paths
    assert ("GET", "/api/quota") in paths
    assert ("GET", "/api/quota/projects/{project_id}") in paths
    create = next(
        item for item in registry["paths"] if item["id"] == "workbench.tasks.create"
    )
    assert create["idempotent"] is True
    assert create["idempotency"] == {
        "header": "Idempotency-Key",
        "required": True,
        "replay_status": 200,
        "replay_header": "Idempotent-Replay",
        "conflict_error": "idempotency_conflict",
    }
    assert "idempotency_conflict" in create["error_codes"]
    assert "invalid_request" in create["error_codes"]


def test_delivery_publish_path_does_not_shadow_report_publish() -> None:
    registry = load_contract_registry()
    paths = {(item["method"], item["path"]) for item in registry["paths"]}
    assert ("POST", "/api/reports/{report_id}/publish") in paths
    assert ("POST", "/api/reports/{artifact_id}/delivery/publish") in paths
    assert ("POST", "/api/reports/{artifact_id}/publish") not in paths


def test_every_path_error_code_exists() -> None:
    registry = load_contract_registry()
    codes = {item["code"] for item in registry["error_codes"]}
    missing = {
        code
        for path in registry["paths"]
        for code in path["error_codes"]
        if code not in codes
    }
    assert missing == set()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。`paths` 只有 seed `/api/tools`。

- [ ] **Step 3: 用以下数组替换附录 A 的 `paths` 数组**

```json
[
  {"id": "projects.members.list", "method": "GET", "path": "/api/projects/{project_id}/members", "audience": "session", "status": "new", "phase": "C2", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "project_access_forbidden", "project_not_found"]},
  {"id": "projects.members.grant", "method": "POST", "path": "/api/projects/{project_id}/members", "audience": "session", "status": "new", "phase": "C2", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_management_forbidden", "project_member_exists", "project_not_found"]},
  {"id": "projects.members.revoke", "method": "DELETE", "path": "/api/projects/{project_id}/members/{user_id}", "audience": "session", "status": "new", "phase": "C2", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_management_forbidden", "project_member_not_found", "project_not_found"]},
  {"id": "workspaces.members.role", "method": "PATCH", "path": "/api/workspaces/current/members/{user_id}", "audience": "session", "status": "new", "phase": "C2", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "workspace_last_owner_required", "workspace_owner_immovable", "workspace_role_forbidden"]},
  {"id": "audit.events.list", "method": "GET", "path": "/api/audit-events", "audience": "session", "status": "new", "phase": "C2", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "workspace_role_forbidden"]},
  {"id": "audit.events.verify", "method": "GET", "path": "/api/audit-events/verify", "audience": "session", "status": "new", "phase": "C2", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "workspace_role_forbidden"]},
  {"id": "project_keys.create", "method": "POST", "path": "/api/projects/{project_id}/keys", "audience": "session", "status": "new", "phase": "C3", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_not_found", "project_key_management_forbidden", "project_api_key_active_exists", "invalid_request"]},
  {"id": "project_keys.list", "method": "GET", "path": "/api/projects/{project_id}/keys", "audience": "session", "status": "new", "phase": "C3", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "project_not_found", "project_key_management_forbidden"]},
  {"id": "project_keys.rotate", "method": "POST", "path": "/api/projects/{project_id}/keys/{key_id}/rotate", "audience": "session", "status": "new", "phase": "C3", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_not_found", "project_key_management_forbidden", "project_api_key_not_found", "state_conflict", "invalid_request"]},
  {"id": "project_keys.revoke", "method": "DELETE", "path": "/api/projects/{project_id}/keys/{key_id}", "audience": "session", "status": "new", "phase": "C3", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_not_found", "project_key_management_forbidden", "project_api_key_not_found"]},
  {"id": "credentials.list", "method": "GET", "path": "/api/settings/platform-credentials", "audience": "session", "status": "existing", "phase": "C3", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "project_not_found", "project_access_forbidden", "connector_not_found"]},
  {"id": "credentials.update", "method": "PUT", "path": "/api/settings/platform-credentials/{platform}", "audience": "session", "status": "existing", "phase": "C3", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "workspace_role_forbidden", "project_not_found", "project_access_forbidden", "project_management_forbidden", "connector_not_found", "credential_invalid", "vault_write_disabled"]},
  {"id": "credentials.delete", "method": "DELETE", "path": "/api/settings/platform-credentials/{platform}", "audience": "session", "status": "existing", "phase": "C3", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "workspace_role_forbidden", "project_not_found", "project_access_forbidden", "project_management_forbidden", "connector_not_found", "vault_write_disabled"]},
  {"id": "workbench.tasks.create", "method": "POST", "path": "/api/workbench/tasks", "audience": "session", "status": "new", "phase": "C4", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "invalid_request", "market_unsupported", "workbench_disabled", "package_type_invalid", "comparison_markets_exceeded", "acceptance_contact_not_member", "budget_invalid", "idempotency_conflict"]},
  {"id": "workbench.tasks.list", "method": "GET", "path": "/api/workbench/tasks", "audience": "session", "status": "new", "phase": "C4", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "project_access_forbidden", "workbench_disabled"]},
  {"id": "workbench.tasks.detail", "method": "GET", "path": "/api/workbench/tasks/{task_id}", "audience": "session", "status": "new", "phase": "C4", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "task_not_found", "workbench_disabled"]},
  {"id": "runs.create", "method": "POST", "path": "/api/runs", "audience": "session", "status": "existing", "phase": "C4", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "approval_required", "idempotency_conflict", "market_unsupported", "workbench_disabled", "task_markets_invalid", "workflow_version_not_found", "workflow_version_not_linked", "plan_not_approved", "plan_version_not_current", "idempotency_state_inconsistent", "execution_steps_missing", "execution_step_unresolved", "collection_task_invalid"]},
  {"id": "runs.cancel", "method": "POST", "path": "/api/runs/{run_id}/cancel", "audience": "session", "status": "existing", "phase": "C6", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "run_not_found", "state_conflict", "invalid_request", "idempotency_conflict"]},
  {"id": "workbench.tasks.update", "method": "PATCH", "path": "/api/workbench/tasks/{task_id}", "audience": "session", "status": "new", "phase": "C4", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "invalid_request", "task_locked", "task_not_found", "workflow_version_already_submitted", "workbench_disabled", "task_markets_invalid", "package_type_invalid", "comparison_markets_exceeded", "acceptance_contact_not_member", "budget_invalid"]},
  {"id": "workbench.tasks.gates", "method": "GET", "path": "/api/workbench/tasks/{task_id}/gates", "audience": "session", "status": "new", "phase": "C4", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "task_not_found", "workbench_disabled"]},
  {"id": "workbench.tasks.approvals.create", "method": "POST", "path": "/api/workbench/tasks/{task_id}/approvals", "audience": "session", "status": "new", "phase": "C5", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "task_not_found", "workspace_role_forbidden", "approval_state_conflict", "invalid_request"]},
  {"id": "workbench.tasks.approvals.decide", "method": "POST", "path": "/api/workbench/tasks/{task_id}/approvals/{approval_id}", "audience": "session", "status": "new", "phase": "C5", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "workspace_role_forbidden", "approval_not_found", "approval_self_approval_forbidden", "approval_state_conflict"]},
  {"id": "quota.summary", "method": "GET", "path": "/api/quota", "audience": "session", "status": "new", "phase": "C5", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "quota_account_missing"]},
  {"id": "quota.project", "method": "GET", "path": "/api/quota/projects/{project_id}", "audience": "session", "status": "new", "phase": "C5", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "project_not_found", "quota_account_missing"]},
  {"id": "claims.list", "method": "GET", "path": "/api/claims", "audience": "session", "status": "existing", "phase": "C7", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "permission_denied"]},
  {"id": "claims.detail", "method": "GET", "path": "/api/claims/{claim_id}", "audience": "session", "status": "existing", "phase": "C7", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "claim_not_found"]},
  {"id": "reports.contract", "method": "GET", "path": "/api/reports/{report_id}/contract", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "report_artifact_not_found", "reviewer_assignment_required", "reviewer_assignment_expired"]},
  {"id": "reports.artifact", "method": "GET", "path": "/api/reports/{report_id}/artifact", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "report_artifact_not_found", "reviewer_assignment_required", "reviewer_assignment_expired"]},
  {"id": "reports.sop", "method": "GET", "path": "/api/reports/{report_id}/sop", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "report_not_published", "reviewer_assignment_required", "reviewer_assignment_expired"]},
  {"id": "reports.revisions", "method": "GET", "path": "/api/reports/{report_id}/revisions", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "report_artifact_not_found", "reviewer_assignment_required", "reviewer_assignment_expired"]},
  {"id": "reports.drafts.create", "method": "POST", "path": "/api/reports/drafts", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_access_forbidden", "report_quality_not_ready", "report_contract_invalid", "state_conflict"]},
  {"id": "reports.reviewers.assign", "method": "POST", "path": "/api/reports/{report_id}/reviewers", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "report_artifact_not_found", "reviewer_assignment_invalid", "reviewer_assignment_expired", "state_conflict"]},
  {"id": "reports.reviewers.revoke", "method": "DELETE", "path": "/api/reports/{report_id}/reviewers/{user_id}", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "reviewer_assignment_invalid", "reviewer_assignment_expired"]},
  {"id": "reports.reviews.create", "method": "POST", "path": "/api/reports/{report_id}/reviews", "audience": "internal", "status": "new", "phase": "C9", "auth": "internal", "idempotent": false, "error_codes": ["authentication_required", "report_review_required", "reviewer_assignment_required", "reviewer_self_review_forbidden", "reviewer_assignment_invalid", "reviewer_assignment_expired", "state_conflict"]},
  {"id": "reports.publish", "method": "POST", "path": "/api/reports/{report_id}/publish", "audience": "session", "status": "new", "phase": "C9", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "report_publish_forbidden", "report_review_required", "report_publish_gate_blocked", "report_forbidden_language", "state_conflict"]},
  {"id": "delivery.publish", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/publish", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "publish_forbidden", "reviewer_assignment_required", "reviewer_self_review_forbidden", "reviewer_assignment_expired", "delivery_not_found", "delivery_not_publishable", "delivery_input_invalid", "delivery_pii_detected", "idempotency_key_required", "idempotency_conflict", "gate_failed", "delivery_integrity_error"]},
  {"id": "delivery.manifest", "method": "GET", "path": "/api/reports/{artifact_id}/delivery/manifest", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "delivery_not_found", "delivery_not_published", "delivery_integrity_error"]},
  {"id": "delivery.download", "method": "GET", "path": "/api/reports/{artifact_id}/delivery", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "delivery_integrity_error", "delivery_pii_detected", "delivery_not_found", "delivery_not_published"]},
  {"id": "delivery.quick_draft.create", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/quick-draft", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "quick_draft_not_allowed", "quick_draft_claim_invalid", "delivery_pii_detected", "delivery_input_invalid", "idempotency_key_required", "idempotency_conflict", "gate_failed", "delivery_integrity_error"]},
  {"id": "delivery.quick_draft.read", "method": "GET", "path": "/api/reports/{artifact_id}/delivery/quick-draft", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "delivery_not_found", "delivery_not_published"]},
  {"id": "delivery.quick_draft.task_read", "method": "GET", "path": "/api/tasks/{task_id}/delivery/quick-draft", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "task_not_found", "delivery_not_found"]},
  {"id": "delivery.acceptance.accept", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/acceptance/accept", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable", "acceptance_window_open", "acceptance_already_closed", "idempotency_key_required", "idempotency_conflict"]},
  {"id": "delivery.acceptance.dispute", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/acceptance/dispute", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable", "acceptance_window_open", "acceptance_already_closed", "acceptance_reference_invalid", "idempotency_key_required", "idempotency_conflict"]},
  {"id": "delivery.acceptance.deemed_accept", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/acceptance/deemed-accepted", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable", "acceptance_window_open", "acceptance_already_closed", "idempotency_key_required", "idempotency_conflict"]},
  {"id": "delivery.acceptance.read", "method": "GET", "path": "/api/reports/{artifact_id}/delivery/acceptance", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable"]},
  {"id": "datasets.export.create", "method": "POST", "path": "/api/automation/product-dataset-exports", "audience": "session", "status": "existing", "phase": "C11", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "project_access_forbidden", "dataset_export_internal_isolated_source"]},
  {"id": "privacy.deletion.create", "method": "POST", "path": "/api/privacy/deletion-requests", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_state_conflict"]},
  {"id": "privacy.deletion.list", "method": "GET", "path": "/api/privacy/deletion-requests", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required"]},
  {"id": "privacy.deletion.detail", "method": "GET", "path": "/api/privacy/deletion-requests/{request_id}", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "deletion_request_not_found"]},
  {"id": "privacy.deletion.approve", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/approve", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.confirm", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/confirm", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.execute", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/execute", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "legal_hold_active", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.proof", "method": "GET", "path": "/api/privacy/deletion-requests/{request_id}/proof", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "deletion_proof_not_ready", "deletion_request_not_found"]},
  {"id": "privacy.deletion.resend", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/resend-confirmation", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.cancel", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/cancel", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.retry", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/retry", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.reevaluate", "method": "POST", "path": "/api/privacy/deletion-requests/{request_id}/reevaluate", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "deletion_request_not_found", "deletion_state_conflict"]},
  {"id": "privacy.deletion.receipts", "method": "GET", "path": "/api/privacy/deletion-requests/{request_id}/subprocessor-receipts", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "deletion_request_not_found"]},
  {"id": "privacy.legal_holds.list", "method": "GET", "path": "/api/privacy/legal-holds", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required"]},
  {"id": "privacy.dsr.list", "method": "GET", "path": "/api/privacy/dsr-cases", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required"]},
  {"id": "privacy.dsr.detail", "method": "GET", "path": "/api/privacy/dsr-cases/{case_id}", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "dsr_case_not_found"]},
  {"id": "privacy.audit.list", "method": "GET", "path": "/api/privacy/audit-events", "audience": "session", "status": "new", "phase": "C12", "auth": "session", "idempotent": false, "error_codes": ["authentication_required"]},
  {"id": "mcp.customer.post", "method": "POST", "path": "/mcp/customer", "audience": "customer_key", "status": "new", "phase": "C13", "auth": "bearer", "idempotent": false, "error_codes": ["authentication_required", "project_key_invalid", "project_key_revoked", "tool_not_allowed", "quota_exceeded", "rate_limited"]},
  {"id": "mcp.customer.get", "method": "GET", "path": "/mcp/customer", "audience": "customer_key", "status": "new", "phase": "C13", "auth": "bearer", "idempotent": false, "error_codes": ["authentication_required", "project_key_invalid", "project_key_revoked"]}
]
```

- [ ] **Step 4: 用以下数组替换附录 A 的 `error_codes` 数组**

```json
[
  {"code": "authentication_required", "kind": "error", "http_status": 401, "retryable": false, "phase": "C2", "meaning": "缺少有效会话或密钥"},
  {"code": "project_key_invalid", "kind": "error", "http_status": 401, "retryable": false, "phase": "C13", "meaning": "项目密钥不存在或格式错误"},
  {"code": "project_key_revoked", "kind": "error", "http_status": 401, "retryable": false, "phase": "C13", "meaning": "项目密钥已撤销或过期"},
  {"code": "permission_denied", "kind": "error", "http_status": 403, "retryable": false, "phase": "C2", "meaning": "角色不足或跨项目访问"},
  {"code": "workspace_role_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C2", "meaning": "工作区角色不允许该动作"},
  {"code": "workspace_owner_required", "kind": "error", "http_status": 403, "retryable": false, "phase": "C2", "meaning": "该动作只允许工作区 owner"},
  {"code": "workspace_role_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C2", "meaning": "角色值不在 owner/admin/member 中"},
  {"code": "workspace_membership_required", "kind": "error", "http_status": 403, "retryable": false, "phase": "C2", "meaning": "不是工作区成员"},
  {"code": "workspace_member_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C2", "meaning": "工作区成员不存在"},
  {"code": "workspace_member_exists", "kind": "error", "http_status": 409, "retryable": false, "phase": "C2", "meaning": "工作区成员已存在"},
  {"code": "workspace_last_owner_required", "kind": "error", "http_status": 409, "retryable": false, "phase": "C2", "meaning": "工作区必须保留至少一名 owner"},
  {"code": "workspace_owner_immovable", "kind": "error", "http_status": 409, "retryable": false, "phase": "C2", "meaning": "owner_id 用户不得降级或移除"},
  {"code": "project_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C2", "meaning": "项目不存在"},
  {"code": "project_access_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C2", "meaning": "无权访问该项目"},
  {"code": "project_management_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C2", "meaning": "无权管理该项目"},
  {"code": "project_member_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C2", "meaning": "项目成员不存在"},
  {"code": "project_member_exists", "kind": "error", "http_status": 409, "retryable": false, "phase": "C2", "meaning": "项目成员已存在"},
  {"code": "request_validation_failed", "kind": "error", "http_status": 422, "retryable": false, "phase": "C2", "meaning": "请求字段校验失败"},
  {"code": "internal_error", "kind": "error", "http_status": 500, "retryable": false, "phase": "C2", "meaning": "未分类内部错误"},
  {"code": "audit_action_unregistered", "kind": "error", "http_status": 500, "retryable": false, "phase": "C2", "meaning": "审计动作不在 audit-actions.v1 注册表；append_audit_event 拒绝写入"},
  {"code": "project_key_management_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C3", "meaning": "无权管理项目密钥"},
  {"code": "project_api_key_active_exists", "kind": "error", "http_status": 409, "retryable": false, "phase": "C3", "meaning": "项目已有有效密钥"},
  {"code": "project_api_key_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C3", "meaning": "项目密钥不存在"},
  {"code": "connector_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C3", "meaning": "连接器或凭据不存在"},
  {"code": "credential_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C3", "meaning": "凭据格式或内容无效"},
  {"code": "vault_write_disabled", "kind": "error", "http_status": 503, "retryable": false, "phase": "C3", "meaning": "凭据写入被开关关闭"},
  {"code": "tool_not_allowed", "kind": "error", "http_status": 403, "retryable": false, "phase": "C13", "meaning": "工具不在项目密钥白名单内"},
  {"code": "capability_not_allowed", "kind": "error", "http_status": 403, "retryable": false, "phase": "C13", "meaning": "能力不在 project_api_keys.capability_allowlist 或不在 TaskTemplate.capability_allowlist 内；不披露具体失败的白名单"},
  {"code": "cookie_not_accepted", "kind": "error", "http_status": 403, "retryable": false, "phase": "C13", "meaning": "客户链不接受 Cookie"},
  {"code": "quota_exceeded", "kind": "error", "http_status": 429, "retryable": false, "phase": "C5", "meaning": "日额度或项目额度耗尽"},
  {"code": "rate_limited", "kind": "error", "http_status": 429, "retryable": true, "phase": "C13", "meaning": "速率或并发超限"},
  {"code": "approval_required", "kind": "error", "http_status": 409, "retryable": false, "phase": "C5", "meaning": "超出预授权，需要 owner 或 admin 批准"},
  {"code": "tool_not_executable", "kind": "error", "http_status": 422, "retryable": false, "phase": "C13", "meaning": "工具不可执行"},
  {"code": "tool_not_priced", "kind": "error", "http_status": 422, "retryable": false, "phase": "C5", "meaning": "工具没有价格，不报价不执行"},
  {"code": "market_unsupported", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "市场不在正式支持目录"},
  {"code": "invalid_request", "kind": "error", "http_status": 400, "retryable": false, "phase": "C4", "meaning": "参数不合法"},
  {"code": "idempotency_conflict", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "同一幂等键对应不同参数"},
  {"code": "state_conflict", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "当前状态不允许该动作"},
  {"code": "task_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C4", "meaning": "任务不存在或无权访问"},
  {"code": "run_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C6", "meaning": "run 不存在或无权访问"},
  {"code": "task_locked", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "任务已提交，不能再改七槽位"},
  {"code": "workflow_version_already_submitted", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "该计划版本已提交过任务"},
  {"code": "taxonomy_unavailable", "kind": "error", "http_status": 503, "retryable": true, "phase": "C4", "meaning": "品类目录缺失或不可读"},
  {"code": "workbench_disabled", "kind": "error", "http_status": 503, "retryable": false, "phase": "C4", "meaning": "工作台任务开关关闭"},
  {"code": "task_markets_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "市场列表为空、重复或含未支持市场"},
  {"code": "package_type_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "包型不是 quick 或 standard"},
  {"code": "comparison_markets_exceeded", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "对比市场数量超过档位上限：Quick 最多 1 个，Standard 最多 3 个"},
  {"code": "acceptance_contact_not_member", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "验收联系人不是当前工作区 owner 或 admin（member 或无成员关系）"},
  {"code": "budget_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "max_cost_usd、max_pages 或 max_records 为负或格式不合法"},
  {"code": "workflow_version_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C4", "meaning": "计划版本不存在或无权访问"},
  {"code": "workflow_version_not_linked", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "计划版本未关联任务单"},
  {"code": "plan_not_approved", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "计划版本尚未批准"},
  {"code": "plan_version_not_current", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "计划版本不是当前版本"},
  {"code": "idempotency_state_inconsistent", "kind": "error", "http_status": 409, "retryable": false, "phase": "C4", "meaning": "幂等键命中但关联状态不一致"},
  {"code": "execution_steps_missing", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "计划缺少 execution_steps 快照"},
  {"code": "execution_step_unresolved", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "execution_steps 中的 task_id 无法解析"},
  {"code": "collection_task_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C4", "meaning": "collection_tasks 行缺失、跨项目或不合法"},
  {"code": "quota_account_missing", "kind": "error", "http_status": 409, "retryable": false, "phase": "C5", "meaning": "项目没有额度账户"},
  {"code": "approval_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C5", "meaning": "内联批准动作不存在或无权访问"},
  {"code": "approval_self_approval_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C5", "meaning": "请求人不得批准自己的预算超支、加购或密钥变更"},
  {"code": "approval_state_conflict", "kind": "error", "http_status": 409, "retryable": false, "phase": "C5", "meaning": "批准动作已决定或已过期"},
  {"code": "claim_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C7", "meaning": "Claim 不存在或无权访问"},
  {"code": "claim_blocked_reason_required", "kind": "error", "http_status": 422, "retryable": false, "phase": "C7", "meaning": "blocked 状态必须给出原因"},
  {"code": "claim_scope_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C7", "meaning": "Claim scope 不合法"},
  {"code": "claim_grade_below_minimum", "kind": "error", "http_status": 422, "retryable": false, "phase": "C7", "meaning": "证据等级低于 Claim 最低要求"},
  {"code": "claim_grade_exceeds_evidence", "kind": "error", "http_status": 422, "retryable": false, "phase": "C7", "meaning": "Claim 状态超过证据等级上限"},
  {"code": "claim_confirmation_requires_review", "kind": "error", "http_status": 422, "retryable": false, "phase": "C7", "meaning": "confirmed 必须通过审核"},
  {"code": "report_quality_not_ready", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "C8 市场质量尚未就绪，不能创建报告草稿"},
  {"code": "report_contract_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C9", "meaning": "报告合同结构或语义校验失败"},
  {"code": "report_contract_not_published", "kind": "error", "http_status": 404, "retryable": false, "phase": "C9", "meaning": "报告合同尚未发布"},
  {"code": "report_contract_hash_mismatch", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "调用方合同哈希与记录不一致"},
  {"code": "report_artifact_not_draft", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "报告产物不是草稿"},
  {"code": "report_artifact_incomplete", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "报告产物缺少 HTML 或 SOP"},
  {"code": "report_artifact_integrity_failed", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "报告产物哈希复核失败"},
  {"code": "report_publish_gate_blocked", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "G-Publish 门禁不是 pass"},
  {"code": "report_revision_target_invalid", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "取代目标不是同报告的可发布版本"},
  {"code": "reviewer_assignment_required", "kind": "error", "http_status": 403, "retryable": false, "phase": "C9", "meaning": "内部审核人没有 active assignment"},
  {"code": "reviewer_assignment_expired", "kind": "error", "http_status": 403, "retryable": false, "phase": "C9", "meaning": "内部审核人的 active assignment 已到 expires_at"},
  {"code": "reviewer_self_review_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C9", "meaning": "客户 owner/admin 不得自审，创建人不得自审"},
  {"code": "reviewer_assignment_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C9", "meaning": "审核人指派范围、主体或状态不合法"},
  {"code": "report_artifact_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C9", "meaning": "报告产物不存在"},
  {"code": "report_review_required", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "发布前缺少审核签字"},
  {"code": "report_publish_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C9", "meaning": "无权发布该报告"},
  {"code": "report_forbidden_language", "kind": "error", "http_status": 422, "retryable": false, "phase": "C9", "meaning": "报告文本命中唯一 forbidden-language profile 的因果或预测表述"},
  {"code": "report_not_published", "kind": "error", "http_status": 409, "retryable": false, "phase": "C9", "meaning": "报告尚未发布"},
  {"code": "delivery_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C10", "meaning": "交付物不存在"},
  {"code": "delivery_not_published", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "交付物尚未发布"},
  {"code": "delivery_integrity_error", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "manifest 或文件哈希不一致"},
  {"code": "gate_failed", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "G-Claim 或 G-Publish 未通过"},
  {"code": "publish_forbidden", "kind": "error", "http_status": 403, "retryable": false, "phase": "C10", "meaning": "只有工作区 owner/admin 可以发布交付包"},
  {"code": "delivery_not_publishable", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "C9 产物未发布或交付状态不允许发布"},
  {"code": "delivery_input_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "数据集版本、幂等键或交付输入不合法"},
  {"code": "idempotency_key_required", "kind": "error", "http_status": 400, "retryable": false, "phase": "C10", "meaning": "交付发布、Quick 2 小时方向稿或验收动作缺少 Idempotency-Key 请求头"},
  {"code": "delivery_pii_detected", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "PII 扫描命中，交付发布或下载被阻断；只记录 kind 与 field_path，不记录原始值"},
  {"code": "quick_draft_not_allowed", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "任务包型不是 quick，不能创建 Quick 2 小时方向稿"},
  {"code": "quick_draft_claim_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "Quick 稿 Claim 出现 confirmed、Standard 四态或高于 L3 的证据"},
  {"code": "acceptance_window_open", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "验收窗口仍开放，不能写 deemed_accepted"},
  {"code": "acceptance_already_closed", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "已有终态验收事件，不能再次验收"},
  {"code": "acceptance_reference_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "争议引用未命中 manifest 文件、Claim、证据或条目"},
  {"code": "acceptance_not_applicable", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "Quick 2 小时方向稿不启动验收"},
  {"code": "dataset_export_internal_isolated_source", "kind": "error", "http_status": 409, "retryable": false, "phase": "C11", "meaning": "数据集含内部隔离来源，禁止客户导出"},
  {"code": "manifest_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C13", "meaning": "交付 manifest 不存在"},
  {"code": "evidence_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C13", "meaning": "证据不存在"},
  {"code": "deletion_request_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C12", "meaning": "删除请求不存在"},
  {"code": "legal_hold_active", "kind": "error", "http_status": 409, "retryable": false, "phase": "C12", "meaning": "法律保留阻止删除"},
  {"code": "deletion_state_conflict", "kind": "error", "http_status": 409, "retryable": false, "phase": "C12", "meaning": "删除状态不允许该动作"},
  {"code": "deletion_proof_not_ready", "kind": "error", "http_status": 409, "retryable": false, "phase": "C12", "meaning": "删除证明尚未生成"},
  {"code": "dsr_case_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C12", "meaning": "DSR 案件不存在"}
]
```

- [ ] **Step 5: 把 `mcp.tools` 中的工具名与错误码与下表核对**

八个工具名必须按以下顺序。`read_only` 与 `error_codes` 必须一致。

| 顺序 | 工具 | `read_only` | 主要错误码 |
|---|---|---:|---|
| 1 | `discover_capabilities` | true | `authentication_required`、`tool_not_allowed`、`quota_exceeded`、`rate_limited` |
| 2 | `estimate_task` | true | `authentication_required`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`market_unsupported`、`tool_not_priced`、`package_type_invalid`、`comparison_markets_exceeded`、`budget_invalid` |
| 3 | `create_task` | false | `authentication_required`、`invalid_request`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`approval_required`、`market_unsupported`、`idempotency_conflict`、`package_type_invalid`、`comparison_markets_exceeded`、`acceptance_contact_not_member`、`budget_invalid` |
| 4 | `get_task` | true | `authentication_required`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`task_not_found` |
| 5 | `cancel_task` | false | `authentication_required`、`invalid_request`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`task_not_found`、`state_conflict`、`idempotency_conflict` |
| 6 | `get_delivery_manifest` | true | `authentication_required`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`task_not_found`、`manifest_not_found` |
| 7 | `get_evidence` | true | `authentication_required`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`claim_not_found`、`evidence_not_found` |
| 8 | `collect` | false | `authentication_required`、`tool_not_allowed`、`quota_exceeded`、`rate_limited`、`approval_required`、`tool_not_executable`、`tool_not_priced`、`market_unsupported`、`capability_not_allowed`、`cookie_not_accepted`、`package_type_invalid`、`comparison_markets_exceeded` |

- [ ] **Step 6: 重新生成 registry**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json`

Expected: `registry built`。

- [ ] **Step 7: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `44 passed`。

- [ ] **Step 8: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.json apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register C2-C13 paths customer MCP and error codes"
```

### Task 9: Canonical Profile、统一报告合同 schema 与交付/MCP schema

**Files:**
- Modify: `apps/api/schemas/report_contract.schema.json`
- Modify: `apps/api/src/data_intelligence_hub/schemas/report_contract.py`
- Modify: `apps/api/tests/unit/test_report_contract.py`
- Create: `configs/contracts/v1.1.0/delivery_manifest.schema.json`
- Create: `configs/contracts/v1.1.0/forbidden_language.profile.json`
- Create: `configs/contracts/v1.1.0/customer_mcp.schema.json`
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: registry 的 `canonical_profile`、`schemas`、`mcp.tools`。
- Produces: `apps/api/schemas/report_contract.schema.json` 顶层 29 个必填键；这是唯一报告合同 schema。
- Produces: `CANONICAL_PROFILE_ID`、`CANONICAL_PROFILE`、`SCHEMA_VERSION = "1.1.0"`。
- Produces: `delivery_manifest.schema.json` 的 `files[]` 与 sidecar 哈希。
- Produces: `customer_mcp.schema.json` 的 17 个 `$defs`（16 个工具输入输出 def 加 `TargetPriceBand`）。
- Produces: checker 对所有 `$ref` 的解析。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def _load_schema(name: str) -> dict:
    return json.loads(
        (PROJECT_ROOT / "configs/contracts/v1.1.0" / name).read_text(encoding="utf-8")
    )


def _load_report_schema() -> dict:
    return json.loads(
        (PROJECT_ROOT / "apps/api/schemas/report_contract.schema.json").read_text(
            encoding="utf-8"
        )
    )


def test_report_contract_has_all_required_top_level_groups() -> None:
    schema = _load_report_schema()
    assert set(schema["required"]) == {
        "schema_version",
        "contract_id",
        "task_id",
        "order_id",
        "template_id",
        "template_version",
        "report_version",
        "generated_at",
        "identity",
        "decision",
        "gates",
        "coverage",
        "markets",
        "metrics",
        "claims",
        "evidences",
        "sku_candidates",
        "datasets",
        "scorecard",
        "rights",
        "currency",
        "language",
        "run_ledger",
        "limits",
        "unknowns",
        "review",
        "acceptance",
        "delivery",
        "artifact",
    }


def test_report_contract_preserves_b5_nested_shape() -> None:
    schema = _load_report_schema()
    identity = schema["$defs"]["identity"]
    assert set(identity["required"]) == {
        "task_id",
        "brand",
        "category",
        "markets",
        "window",
    }
    assert "category_id" not in identity["properties"]
    coverage = schema["$defs"]["coverage"]
    assert set(coverage["required"]) == {"cells"}
    cell = coverage["properties"]["cells"]["items"]
    assert set(cell["required"]) == {
        "source_tool_id",
        "market",
        "window",
        "record_count",
        "frame_member_count",
        "status",
    }
    assert schema["$defs"]["coverage_status"]["enum"] == [
        "success",
        "empty",
        "failed",
    ]
    assert schema["properties"]["task_id"] == {"$ref": "#/$defs/uuid"}


def test_report_contract_defs_resolve() -> None:
    schema = _load_report_schema()
    module = load_module()
    errors = module.check_json_schema_refs(schema)
    assert errors == []


def test_canonical_constants_are_single_sourced() -> None:
    import importlib

    module = importlib.import_module(
        "data_intelligence_hub.schemas.report_contract"
    )
    assert module.CANONICAL_PROFILE_ID == "dih-canonical-json-v1"
    assert module.CANONICAL_PROFILE == module.CANONICAL_PROFILE_ID
    assert module.SCHEMA_VERSION == "1.1.0"


def test_delivery_manifest_required_fields() -> None:
    schema = _load_schema("delivery_manifest.schema.json")
    assert {
        "schema_version",
        "manifest_id",
        "task_id",
        "report_artifact_id",
        "report_version",
        "created_at",
        "files",
        "bundle_sha256",
        "sidecar_sha256",
        "access_scope",
        "retention_class",
    } <= set(schema["required"])


def test_delivery_manifest_exact_keys_and_file_entries() -> None:
    schema = _load_schema("delivery_manifest.schema.json")
    assert set(schema["properties"]) == {
        "schema_version",
        "manifest_id",
        "task_id",
        "report_artifact_id",
        "report_version",
        "created_at",
        "files",
        "bundle_sha256",
        "sidecar_sha256",
        "access_scope",
        "retention_class",
    }
    assert schema["additionalProperties"] is False
    assert schema["properties"]["files"]["minItems"] == 10
    file_entry = schema["$defs"]["file_entry"]
    assert set(file_entry["required"]) == {
        "path",
        "sha256",
        "size_bytes",
        "media_type",
    }
    assert set(file_entry["properties"]) == {
        "path",
        "sha256",
        "size_bytes",
        "media_type",
    }


def test_customer_mcp_schema_has_seventeen_defs() -> None:
    schema = _load_schema("customer_mcp.schema.json")
    expected = {
        "DiscoverCapabilitiesInput",
        "DiscoverCapabilitiesOutput",
        "EstimateTaskInput",
        "EstimateTaskOutput",
        "CreateTaskInput",
        "CreateTaskOutput",
        "GetTaskInput",
        "GetTaskOutput",
        "CancelTaskInput",
        "CancelTaskOutput",
        "GetDeliveryManifestInput",
        "GetDeliveryManifestOutput",
        "GetEvidenceInput",
        "GetEvidenceOutput",
        "CollectInput",
        "CollectOutput",
        "TargetPriceBand",
    }
    assert expected <= set(schema["$defs"])
    assert len(schema["$defs"]) == 17


def test_canonical_profile_excludes_generated_at_and_artifact() -> None:
    registry = load_contract_registry()
    profile = registry["canonical_profile"]
    assert profile["profile_id"] == "dih-canonical-json-v1"
    assert profile["json_rules"] == "RFC 8785"
    assert profile["excluded_top_level_keys"] == ["generated_at", "artifact"]
    assert profile["digest_algorithm"] == "sha256"


def test_forbidden_language_profile_is_versioned_and_single_sourced() -> None:
    profile = _load_schema("forbidden_language.profile.json")
    assert profile["profile_id"] == "dih-descriptive-language-v1"
    assert profile["profile_version"] == "1.0.0"
    assert profile["causal_terms_zh"] == [
        "导致",
        "驱动",
        "提升",
        "降低",
        "造成",
        "证明",
    ]
    assert profile["prediction_objects_zh"] == ["销量", "市场份额", "转化率", "营收"]
    registry = load_contract_registry()
    registered = registry["canonical_profile"]["forbidden_language"]
    assert registered["profile_id"] == profile["profile_id"]
    assert registered["profile_version"] == profile["profile_version"]
    assert registered["causal_terms_zh"] == profile["causal_terms_zh"]
    module = importlib.import_module(
        "data_intelligence_hub.schemas.report_contract"
    )
    assert module.FORBIDDEN_LANGUAGE_PROFILE_ID == profile["profile_id"]
    assert module.FORBIDDEN_LANGUAGE_PROFILE_VERSION == profile["profile_version"]
    assert module.FORBIDDEN_LANGUAGE_PROFILE == profile


def test_forbidden_language_scanner_rejects_causal_and_prediction_only() -> None:
    module = importlib.import_module(
        "data_intelligence_hub.schemas.report_contract"
    )
    assert module.scan_forbidden_language(
        {"decision": {"answer": "评论量与销量共同出现，属于描述性差异。"}}
    ) == []
    causal = module.scan_forbidden_language(
        {"decision": {"answer": "评论提升销量。"}}
    )
    assert [hit.term for hit in causal] == ["提升"]
    assert [hit.rule for hit in causal] == ["causal"]
    prediction = module.scan_forbidden_language(
        {"decision": {"answer_en": "We predict US sales will grow."}}
    )
    assert [hit.term for hit in prediction] == ["predict"]
    assert [hit.rule for hit in prediction] == ["prediction"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。三份 schema 文件不存在。`check_json_schema_refs` 未定义。

- [ ] **Step 3: 在 `scripts/contract_registry.py` 加入 schema 引用检查**

在 `check_schema_refs_exist` 之前加入：

```python
def _collect_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                refs.append(child)
            else:
                refs.extend(_collect_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_collect_refs(child))
    return refs


def check_json_schema_refs(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    definitions = schema.get("$defs", {})
    if not isinstance(definitions, dict):
        return ["schema_defs_not_object"]
    for ref in _collect_refs(schema):
        if ref.startswith("#/$defs/"):
            name = ref.removeprefix("#/$defs/")
            if name not in definitions:
                errors.append(f"missing_schema_def:{name}")
        elif ref.startswith("#"):
            continue
        else:
            errors.append(f"external_ref_not_allowed:{ref}")
    return errors


def validate_json_document(value: Any, schema: dict[str, Any]) -> list[str]:
    """Validate one JSON document against a local draft 2020-12 schema.

    C9/C10 use this to prove their generated contracts and delivery manifest
    match the frozen schemas without adding a third-party dependency.
    """
    return _validate_value(value, schema, schema, "$")
```

- [ ] **Step 3A: 冻结唯一的 forbidden-language profile**

Create `configs/contracts/v1.1.0/forbidden_language.profile.json`。词表只来自已批准设计 §5.7；C9 与 C10 都 import 同一个扫描器，不得复制本文件或 `FORBIDDEN_LANGUAGE_PROFILE`。

```json
{
  "profile_id": "dih-descriptive-language-v1",
  "profile_version": "1.0.0",
  "source": "docs/superpowers/specs/2026-10-21-tikhub-governed-task-platform-design.md#5.7",
  "causal_terms_zh": ["导致", "驱动", "提升", "降低", "造成", "证明"],
  "causal_terms_en": ["cause", "causes", "caused", "drive", "drives", "driven", "improve", "improves", "increase", "increases", "decrease", "decreases", "reduce", "reduces", "lead to", "leads to", "prove", "proves"],
  "prediction_terms_zh": ["预测", "预计", "将会"],
  "prediction_terms_en": ["predict", "predicts", "forecast", "forecasts", "projection", "projections"],
  "prediction_objects_zh": ["销量", "市场份额", "转化率", "营收"],
  "prediction_objects_en": ["sales", "market share", "conversion rate", "revenue"],
  "allowed_relations_zh": ["共同出现", "相关", "描述性差异"],
  "allowed_relations_en": ["co-occurrence", "correlation", "descriptive difference"]
}
```

在 `apps/api/src/data_intelligence_hub/schemas/report_contract.py` 增加单一入口：

```python
FORBIDDEN_LANGUAGE_PROFILE_ID: Final = "dih-descriptive-language-v1"
FORBIDDEN_LANGUAGE_PROFILE_VERSION: Final = "1.0.0"
FORBIDDEN_LANGUAGE_PROFILE_PATH: Final = (
    "configs/contracts/v1.1.0/forbidden_language.profile.json"
)


@dataclass(frozen=True, slots=True)
class ForbiddenLanguageHit:
    field_path: str
    term: str
    rule: Literal["causal", "prediction"]


def _load_forbidden_language_profile() -> dict[str, Any]:
    path = PROJECT_ROOT / FORBIDDEN_LANGUAGE_PROFILE_PATH
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile["profile_id"] != FORBIDDEN_LANGUAGE_PROFILE_ID:
        raise RuntimeError("forbidden_language_profile_id_mismatch")
    if profile["profile_version"] != FORBIDDEN_LANGUAGE_PROFILE_VERSION:
        raise RuntimeError("forbidden_language_profile_version_mismatch")
    return profile


FORBIDDEN_LANGUAGE_PROFILE: Final = MappingProxyType(
    _load_forbidden_language_profile()
)


def scan_forbidden_language(contract: Mapping[str, Any]) -> list[ForbiddenLanguageHit]:
    """扫描决策答案与 Claim 文本。C9/C10 唯一共享实现。"""
    profile = FORBIDDEN_LANGUAGE_PROFILE
    hits: list[ForbiddenLanguageHit] = []
    for field_path, text in _iter_contract_text(contract):
        lowered = text.lower()
        for term in profile["causal_terms_zh"]:
            if term in text:
                hits.append(ForbiddenLanguageHit(field_path, term, "causal"))
        for term in profile["causal_terms_en"]:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                hits.append(ForbiddenLanguageHit(field_path, term, "causal"))
        if any(term in text for term in profile["prediction_terms_zh"]) and any(
            obj in text for obj in profile["prediction_objects_zh"]
        ):
            term = next(term for term in profile["prediction_terms_zh"] if term in text)
            hits.append(ForbiddenLanguageHit(field_path, term, "prediction"))
        if any(
            re.search(rf"\b{re.escape(term)}\b", lowered)
            for term in profile["prediction_terms_en"]
        ) and any(
            re.search(rf"\b{re.escape(obj)}\b", lowered)
            for obj in profile["prediction_objects_en"]
        ):
            term = next(
                term
                for term in profile["prediction_terms_en"]
                if re.search(rf"\b{re.escape(term)}\b", lowered)
            )
            hits.append(ForbiddenLanguageHit(field_path, term, "prediction"))
    return hits


def _iter_contract_text(contract: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    decision = contract.get("decision") or {}
    value = decision.get("answer")
    if isinstance(value, str) and value.strip():
        yield "decision.answer", value
    for key in ("protect", "resolve", "prove"):
        for index, item in enumerate(decision.get(key) or []):
            if isinstance(item, str) and item.strip():
                yield f"decision.{key}[{index}]", item
    for index, claim in enumerate(contract.get("claims") or []):
        for key in ("text", "text_en", "counterevidence_text"):
            value = claim.get(key)
            if isinstance(value, str) and value.strip():
                yield f"claims[{index}].{key}", value
```

`report_contract.py` 需要 `re`、`json`、`Path`、`MappingProxyType` 与 `Iterator`；`MappingProxyType` 与 `Iterator` 从 `types`、`collections.abc` 导入。`PROJECT_ROOT` 使用模块现有常量；若不存在，用 `Path(__file__).resolve().parents[4]` 定义一次。扫描器不评分、不计数、不设阈值；命中即由 C9 抛 `report_forbidden_language`，C10 抛 `delivery_input_invalid` 并附同一 `profile_id`。

- [ ] **Step 4: 升级唯一的 B5 报告合同 schema**

Modify `apps/api/schemas/report_contract.schema.json`。保留 B5 的 `$id` 与 14 个既有必填组，把 `schema_version` 的 `const` 改为 `"1.1.0"`，把 `required` 扩展为下列 29 个键，并补齐 `$defs`：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://data-intelligence-hub.local/schemas/report_contract.schema.json",
  "title": "DIH report_contract v1.1.0",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "contract_id",
    "task_id",
    "order_id",
    "template_id",
    "template_version",
    "report_version",
    "generated_at",
    "identity",
    "decision",
    "gates",
    "coverage",
    "markets",
    "metrics",
    "claims",
    "evidences",
    "sku_candidates",
    "datasets",
    "scorecard",
    "rights",
    "currency",
    "language",
    "run_ledger",
    "limits",
    "unknowns",
    "review",
    "acceptance",
    "delivery",
    "artifact"
  ],
  "properties": {
    "schema_version": {"const": "1.1.0"},
    "contract_id": {"$ref": "#/$defs/uuid"},
    "task_id": {"$ref": "#/$defs/uuid"},
    "order_id": {"$ref": "#/$defs/uuid"},
    "template_id": {"type": "string", "minLength": 1},
    "template_version": {"type": "string", "minLength": 1},
    "report_version": {"type": "integer", "minimum": 1},
    "supersedes_id": {"oneOf": [{"$ref": "#/$defs/uuid"}, {"type": "null"}]},
    "generated_at": {"$ref": "#/$defs/timestamp"},
    "identity": {"$ref": "#/$defs/identity"},
    "decision": {"$ref": "#/$defs/decision"},
    "gates": {"type": "array", "items": {"$ref": "#/$defs/gate"}},
    "coverage": {"$ref": "#/$defs/coverage"},
    "markets": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/market_assessment"}},
    "metrics": {"type": "array", "items": {"$ref": "#/$defs/metric"}},
    "claims": {"type": "array", "items": {"$ref": "#/$defs/claim"}},
    "evidences": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
    "sku_candidates": {"type": "array", "items": {"$ref": "#/$defs/sku_candidate"}},
    "datasets": {"type": "array", "items": {"$ref": "#/$defs/dataset"}},
    "scorecard": {"$ref": "#/$defs/scorecard"},
    "rights": {"$ref": "#/$defs/rights"},
    "currency": {"$ref": "#/$defs/currency"},
    "language": {"$ref": "#/$defs/language"},
    "run_ledger": {"type": "array", "items": {"$ref": "#/$defs/ledger_entry"}},
    "limits": {"type": "array", "items": {"type": "string"}},
    "unknowns": {"type": "array", "items": {"type": "string"}},
    "review": {"$ref": "#/$defs/review"},
    "acceptance": {"$ref": "#/$defs/acceptance"},
    "delivery": {"$ref": "#/$defs/delivery"},
    "artifact": {"$ref": "#/$defs/artifact"}
  },
  "$defs": {
    "uuid": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "timestamp": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},
    "date": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "market": {"type": "string", "enum": ["US", "GB", "DE", "FR", "IT", "ES", "IE", "NL", "BE", "AT", "PL"]},
    "data_domain": {"type": "string", "enum": ["products", "reviews", "creator_content", "ads", "trends"]},
    "domain_status": {"type": "string", "enum": ["pass", "partial", "missing", "blocked"]},
    "coverage_status": {"type": "string", "enum": ["success", "empty", "failed"]},
    "market_quality": {"type": "string", "enum": ["qualified", "qualified_with_gap", "not_qualified"]},
    "claim_status": {"type": "string", "enum": ["confirmed", "directional", "hypothesis", "evidence_gap", "blocked"]},
    "evidence_grade": {"type": "string", "enum": ["L0_unverified", "L1_contract", "L2_fixture_local", "L3_live_single", "L4_authorized_live"]},
    "gate_status": {"type": "string", "enum": ["pending", "pass", "fail", "blocked", "expired"]},
    "role": {"type": "string", "enum": ["support", "counter", "context", "gap"]},
    "count_type": {"type": "string", "enum": ["raw_object", "occurrence", "canonical_record", "frame_member", "annotation", "metric_row"]},
    "gap": {
      "type": "object",
      "additionalProperties": false,
      "required": ["gap_id", "market", "data_domain", "reason_code", "impact", "customer_text_zh", "severity"],
      "properties": {
        "gap_id": {"$ref": "#/$defs/uuid"},
        "market": {"$ref": "#/$defs/market"},
        "data_domain": {"$ref": "#/$defs/data_domain"},
        "reason_code": {"type": "string"},
        "actual_value": {},
        "threshold_value": {},
        "impact": {"type": "string"},
        "customer_text_zh": {"type": "string"},
        "customer_text_en": {"type": "string"},
        "remediation": {"type": "string"},
        "severity": {"type": "string", "enum": ["info", "warning", "blocking", "critical"]}
      }
    },
    "gate": {
      "type": "object",
      "additionalProperties": false,
      "required": ["gate_id", "status"],
      "properties": {
        "gate_id": {"type": "string", "enum": ["G-Plan", "G-Cost", "G-Evidence", "G-Claim", "G-Publish"]},
        "status": {"$ref": "#/$defs/gate_status"},
        "owner": {"oneOf": [{"$ref": "#/$defs/uuid"}, {"type": "null"}]},
        "decided_at": {"oneOf": [{"$ref": "#/$defs/timestamp"}, {"type": "null"}]},
        "note": {"type": "string"}
      }
    },
    "identity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id", "brand", "category", "markets", "window"],
      "properties": {
        "task_id": {"$ref": "#/$defs/uuid"},
        "brand": {"type": "string"},
        "category": {"type": "string"},
        "competitors": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
        "markets": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/market"}},
        "window": {
          "type": "object",
          "additionalProperties": false,
          "required": ["start", "end", "days"],
          "properties": {
            "start": {"$ref": "#/$defs/date"},
            "end": {"$ref": "#/$defs/date"},
            "days": {"type": "integer", "minimum": 1}
          }
        },
        "product": {"type": "string"},
        "model": {"type": "string"},
        "variant_id": {"type": "string"},
        "sku": {"type": "string"},
        "asin": {"type": "string"},
        "parent_asin": {"type": "string"},
        "bundle": {"type": "string"},
        "offer": {"type": "string"},
        "mapping_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "family_children": {"type": "array", "items": {"type": "object"}}
      }
    },
    "decision": {
      "type": "object",
      "additionalProperties": false,
      "required": ["decision_question", "answer", "protect", "resolve", "prove"],
      "properties": {
        "decision_question": {"type": "string"},
        "answer": {"type": "string"},
        "protect": {"type": "array", "items": {"type": "string"}},
        "resolve": {"type": "array", "items": {"type": "string"}},
        "prove": {"type": "array", "items": {"type": "string"}}
      }
    },
    "coverage": {
      "type": "object",
      "additionalProperties": false,
      "required": ["cells"],
      "properties": {
        "cells": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["source_tool_id", "market", "window", "record_count", "frame_member_count", "status"],
            "properties": {
              "source_tool_id": {"type": "string"},
              "market": {"$ref": "#/$defs/market"},
              "window": {
                "type": "object",
                "additionalProperties": false,
                "required": ["start", "end", "days"],
                "properties": {
                  "start": {"$ref": "#/$defs/date"},
                  "end": {"$ref": "#/$defs/date"},
                  "days": {"type": "integer", "minimum": 1}
                }
              },
              "record_count": {"type": "integer", "minimum": 0},
              "frame_member_count": {"type": "integer", "minimum": 0},
              "status": {"$ref": "#/$defs/coverage_status"}
            }
          }
        }
      }
    },
    "market_assessment": {
      "type": "object",
      "additionalProperties": false,
      "required": ["market", "market_role", "quality_status", "evidence_grade", "domains", "sample_counts", "thresholds", "gaps"],
      "properties": {
        "market": {"$ref": "#/$defs/market"},
        "market_role": {"type": "string", "enum": ["primary", "compare"]},
        "quality_status": {"$ref": "#/$defs/market_quality"},
        "conclusion_standard": {"type": "string", "enum": ["enter", "conditional_enter", "do_not_enter", "insufficient_evidence"]},
        "conclusion_quick": {"type": "string", "enum": ["worth_validating", "deprioritize", "key_risk", "evidence_gap", "recommend_standard_scope"]},
        "evidence_grade": {"$ref": "#/$defs/evidence_grade"},
        "domains": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["data_domain", "status"],
            "properties": {
              "data_domain": {"$ref": "#/$defs/data_domain"},
              "status": {"$ref": "#/$defs/domain_status"},
              "record_count": {"type": "integer", "minimum": 0},
              "threshold": {"type": "integer", "minimum": 0}
            }
          }
        },
        "sample_counts": {"type": "object"},
        "thresholds": {"type": "object"},
        "gaps": {"type": "array", "items": {"$ref": "#/$defs/gap"}}
      }
    },
    "metric": {
      "type": "object",
      "additionalProperties": false,
      "required": ["metric_id", "label", "numerator", "denominator", "count_type", "frame", "as_of"],
      "properties": {
        "metric_id": {"type": "string"},
        "label": {"type": "string"},
        "numerator": {"type": "number"},
        "denominator": {"type": "number"},
        "count_type": {"$ref": "#/$defs/count_type"},
        "frame": {"type": "string"},
        "as_of": {"$ref": "#/$defs/date"},
        "note": {"type": "string"}
      }
    },
    "claim": {
      "type": "object",
      "additionalProperties": false,
      "required": ["claim_id", "text", "claim_status", "evidence_grade", "scope", "counterevidence_text", "owner", "evidence_ids"],
      "properties": {
        "claim_id": {"$ref": "#/$defs/uuid"},
        "text": {"type": "string"},
        "text_en": {"type": "string"},
        "claim_status": {"$ref": "#/$defs/claim_status"},
        "evidence_grade": {"$ref": "#/$defs/evidence_grade"},
        "scope": {
          "type": "object",
          "additionalProperties": false,
          "required": ["market", "window", "sample_n"],
          "properties": {
            "market": {"$ref": "#/$defs/market"},
            "window": {
              "type": "object",
              "additionalProperties": false,
              "required": ["start", "end", "days"],
              "properties": {
                "start": {"$ref": "#/$defs/date"},
                "end": {"$ref": "#/$defs/date"},
                "days": {"type": "integer", "minimum": 1}
              }
            },
            "sample_n": {"type": "integer", "minimum": 0}
          }
        },
        "owner": {"$ref": "#/$defs/uuid"},
        "review_status": {"type": "string", "enum": ["draft", "pending", "approved", "rejected", "stale"]},
        "blocked_reason": {"type": "string", "enum": ["rights", "permission", "configuration", "gate", "upstream"]},
        "sample_n": {"type": "integer", "minimum": 0},
        "independent_source_count": {"type": "integer", "minimum": 0},
        "counterevidence_text": {"type": "string", "minLength": 1},
        "risk_flags": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["medical", "health", "safety", "legal", "recall", "children", "causal_language", "single_source", "price_comparison"]
          }
        },
        "evidence_ids": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/uuid"}}
      }
    },
    "evidence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["evidence_id", "claim_id", "role", "source_tool_id", "captured_at", "market", "evidence_grade"],
      "properties": {
        "evidence_id": {"$ref": "#/$defs/uuid"},
        "claim_id": {"$ref": "#/$defs/uuid"},
        "role": {"$ref": "#/$defs/role"},
        "raw_record_id": {"oneOf": [{"$ref": "#/$defs/uuid"}, {"type": "null"}]},
        "source_tool_id": {"type": "string"},
        "url": {"type": "string"},
        "excerpt": {"type": "string"},
        "captured_at": {"$ref": "#/$defs/timestamp"},
        "market": {"$ref": "#/$defs/market"},
        "locale": {"type": "string"},
        "evidence_grade": {"$ref": "#/$defs/evidence_grade"}
      }
    },
    "sku_candidate": {
      "type": "object",
      "additionalProperties": false,
      "required": ["market", "rank", "price_band_local", "price_band_usd", "evidence_grade", "risks", "next_validation"],
      "properties": {
        "market": {"$ref": "#/$defs/market"},
        "rank": {"type": "integer", "minimum": 1},
        "price_band_local": {"type": "object"},
        "price_band_usd": {"type": "object"},
        "attributes": {"type": "object"},
        "demand_evidence_ids": {"type": "array", "items": {"$ref": "#/$defs/uuid"}},
        "competition_evidence_ids": {"type": "array", "items": {"$ref": "#/$defs/uuid"}},
        "evidence_grade": {"$ref": "#/$defs/evidence_grade"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_validation": {"type": "string"}
      }
    },
    "dataset": {
      "type": "object",
      "additionalProperties": false,
      "required": ["dataset_version_id", "market", "row_count", "content_sha256", "schema_hash"],
      "properties": {
        "dataset_version_id": {"$ref": "#/$defs/uuid"},
        "market": {"$ref": "#/$defs/market"},
        "row_count": {"type": "integer", "minimum": 0},
        "content_sha256": {"$ref": "#/$defs/sha256"},
        "schema_hash": {"$ref": "#/$defs/sha256"},
        "quality_status": {"$ref": "#/$defs/market_quality"}
      }
    },
    "scorecard": {
      "type": "object",
      "additionalProperties": false,
      "required": ["markets", "minimum_evidence_grade", "claims"],
      "properties": {
        "markets": {"type": "array", "items": {"$ref": "#/$defs/market_assessment"}},
        "minimum_evidence_grade": {"$ref": "#/$defs/evidence_grade"},
        "claims": {
          "type": "object",
          "additionalProperties": false,
          "required": ["total", "by_status", "by_grade", "independent_source_count"],
          "properties": {
            "total": {"type": "integer", "minimum": 0},
            "by_status": {"type": "object"},
            "by_grade": {"type": "object"},
            "independent_source_count": {"type": "integer", "minimum": 0}
          }
        }
      }
    },
    "rights": {
      "type": "object",
      "additionalProperties": false,
      "required": ["sources"],
      "properties": {
        "sources": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["source_tool_id", "rights_status"],
            "properties": {
              "source_tool_id": {"type": "string"},
              "rights_status": {"type": "string", "enum": ["cleared", "restricted", "unknown", "blocked"]}
            }
          }
        }
      }
    },
    "currency": {
      "type": "object",
      "additionalProperties": false,
      "required": ["base_currency", "quote_currency", "rate", "rate_date", "source"],
      "properties": {
        "base_currency": {"type": "string"},
        "quote_currency": {"type": "string"},
        "rate": {"type": "number", "exclusiveMinimum": 0},
        "rate_date": {"$ref": "#/$defs/date"},
        "source": {"type": "string"}
      }
    },
    "language": {
      "type": "object",
      "additionalProperties": false,
      "required": ["primary_language", "executive_summary_language", "translation_method"],
      "properties": {
        "primary_language": {"type": "string"},
        "executive_summary_language": {"type": "string"},
        "translation_method": {"type": "string"}
      }
    },
    "ledger_entry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["run_id", "tool_id", "endpoint_type", "unit", "quantity", "unit_price", "total_cost_usd", "evidence_grade", "started_at", "finished_at", "outcome"],
      "properties": {
        "run_id": {"$ref": "#/$defs/uuid"},
        "tool_id": {"type": "string"},
        "endpoint_type": {"type": "string"},
        "unit": {"type": "string"},
        "quantity": {"type": "number"},
        "unit_price": {"type": "number"},
        "total_cost_usd": {"type": "number"},
        "authorization_id": {"oneOf": [{"$ref": "#/$defs/uuid"}, {"type": "null"}]},
        "evidence_grade": {"$ref": "#/$defs/evidence_grade"},
        "started_at": {"$ref": "#/$defs/timestamp"},
        "finished_at": {"$ref": "#/$defs/timestamp"},
        "outcome": {"type": "string", "enum": ["success", "empty", "config_gated", "failed"]}
      }
    },
    "review": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "reviewer_id", "reviewer_assignment_id", "reviewer_role", "review_scope", "reviewed_at", "review_version", "contract_sha256"],
      "properties": {
        "status": {"type": "string", "enum": ["draft", "pending", "approved", "rejected", "stale"]},
        "reviewer_id": {"$ref": "#/$defs/uuid"},
        "reviewer_assignment_id": {"$ref": "#/$defs/uuid"},
        "reviewer_role": {"type": "string", "enum": ["internal_reviewer"]},
        "review_scope": {"type": "array", "items": {"type": "string"}},
        "reviewed_at": {"$ref": "#/$defs/timestamp"},
        "review_version": {"type": "integer", "minimum": 1},
        "contract_sha256": {"$ref": "#/$defs/sha256"}
      }
    },
    "acceptance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "window_start", "window_end"],
      "properties": {
        "status": {"type": "string", "enum": ["pending", "accepted", "auto_accepted", "objection", "rework", "closed"]},
        "window_start": {"$ref": "#/$defs/date"},
        "window_end": {"$ref": "#/$defs/date"}
      }
    },
    "delivery": {
      "type": "object",
      "additionalProperties": false,
      "required": ["manifest_id", "report_artifact_id", "report_version", "access_scope", "retention_class"],
      "properties": {
        "manifest_id": {"$ref": "#/$defs/uuid"},
        "report_artifact_id": {"$ref": "#/$defs/uuid"},
        "report_version": {"type": "integer", "minimum": 1},
        "access_scope": {"type": "array", "items": {"type": "string"}},
        "retention_class": {"type": "string", "enum": ["standard_24m", "extended", "legal_hold"]}
      }
    },
    "artifact": {
      "type": "object",
      "additionalProperties": false,
      "required": ["report_html_sha256", "sop_html_sha256", "contract_sha256"],
      "properties": {
        "report_html_sha256": {"$ref": "#/$defs/sha256"},
        "sop_html_sha256": {"$ref": "#/$defs/sha256"},
        "contract_sha256": {"$ref": "#/$defs/sha256"}
      }
    }
  }
}
```

- [ ] **Step 4A: 更新 Pydantic 模型与 canonical 常量**

Modify `apps/api/src/data_intelligence_hub/schemas/report_contract.py`。只改常量和 `ReportContract` 模型，不改哈希函数、校验器或渲染器。

1. 把 `SCHEMA_VERSION: Final = "1.0.0"` 改为：

```python
SCHEMA_VERSION: Final = "1.1.0"
CANONICAL_PROFILE_ID: Final = "dih-canonical-json-v1"
CANONICAL_PROFILE: Final = CANONICAL_PROFILE_ID
```

2. 把 `ReportContract.schema_version` 改为 `Literal["1.1.0"]`，并按 schema 的 29 个顶层键补齐字段。字段顺序与 schema 一致：

```python
class ReportContract(ContractModel):
    schema_version: Literal["1.1.0"]
    contract_id: UUID
    task_id: UUID
    order_id: UUID
    template_id: str
    template_version: str
    report_version: int = Field(ge=1)
    supersedes_id: UUID | None = None
    generated_at: datetime
    identity: Identity
    decision: Decision
    gates: list[Gate]
    coverage: CoverageBlock
    markets: list[MarketAssessment]
    metrics: list[Metric]
    claims: list[Claim]
    evidences: list[Evidence]
    sku_candidates: list[SkuCandidate]
    datasets: list[DatasetVersion]
    scorecard: Scorecard
    rights: Rights
    currency: Currency
    language: LanguageContract
    run_ledger: list[RunLedgerRow]
    limits: list[str]
    unknowns: list[str]
    review: Review
    acceptance: Acceptance
    delivery: Delivery
    artifact: Artifact
```

3. 在同一模块补齐 `MarketAssessment`、`SkuCandidate`、`DatasetVersion`、`Scorecard`、`Rights`、`Currency`、`LanguageContract`、`Review`、`Acceptance`、`Delivery` 十个 `ContractModel`，字段与 Step 4 schema 的 `$defs` 逐字段对应。不得改变既有 `Identity`、`CoverageCell`、`CoverageBlock`、`Claim`、`Evidence`、`Gate`、`Metric`、`Artifact` 的字段名或必填集合。`Identity.task_id` 与顶层 `task_id` 都必填，两者必须相等；`Review` 必须含 `reviewer_assignment_id` 与 `reviewer_role: Literal["internal_reviewer"]`；`Delivery` 必须含 `report_artifact_id` 与 `report_version`；`Scorecard` 必须含 `claims` 汇总组。新增 C7 治理字段只允许作为 `Claim` 的可选字段，不得把 B5 报告变成不可解析。`Claim` 的 `text_en`、`review_status`、`blocked_reason`、`independent_source_count`、`risk_flags` 均为可选；`claims.review_status` 等数据库强制项由 C7 的 `load_publishable_claim_rows()` 校验。

4. 更新 `apps/api/tests/unit/test_report_contract.py`：

- golden fixture 的 `schema_version` 改为 `"1.1.0"`，并按 29 个必填键补全字段。
- `EXPECTED_REQUIRED_FIELDS` 改为 Step 4 的 29 个键。
- `test_handwritten_schema_required_matches_pydantic` 与 `test_handwritten_nested_required_sets_match_pydantic` 保持通过。

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1/apps/api
.venv/bin/python -m pytest tests/unit/test_report_contract.py -q
```

Expected: 全部 passed。既有断言数量不得减少；新增字段只增加断言。

- [ ] **Step 5: 写交付 manifest schema**

Create `configs/contracts/v1.1.0/delivery_manifest.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dih.local/contracts/v1.1.0/delivery_manifest.schema.json",
  "title": "DIH Delivery Manifest v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "manifest_id",
    "task_id",
    "report_artifact_id",
    "report_version",
    "created_at",
    "files",
    "bundle_sha256",
    "sidecar_sha256",
    "access_scope",
    "retention_class"
  ],
  "properties": {
    "schema_version": {"const": "delivery-manifest.v1"},
    "manifest_id": {"$ref": "#/$defs/uuid"},
    "task_id": {"$ref": "#/$defs/uuid"},
    "report_artifact_id": {"$ref": "#/$defs/uuid"},
    "report_version": {"type": "integer", "minimum": 1},
    "created_at": {"$ref": "#/$defs/timestamp"},
    "files": {
      "type": "array",
      "minItems": 10,
      "items": {"$ref": "#/$defs/file_entry"}
    },
    "bundle_sha256": {"$ref": "#/$defs/sha256"},
    "sidecar_sha256": {"$ref": "#/$defs/sha256"},
    "access_scope": {"type": "array", "minItems": 1, "items": {"type": "string"}},
    "retention_class": {"type": "string", "enum": ["standard_24m", "extended", "legal_hold"]}
  },
  "$defs": {
    "uuid": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "timestamp": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},
    "file_entry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["path", "sha256", "size_bytes", "media_type"],
      "properties": {
        "path": {"type": "string", "minLength": 1},
        "sha256": {"$ref": "#/$defs/sha256"},
        "size_bytes": {"type": "integer", "minimum": 0},
        "media_type": {"type": "string", "minLength": 1}
      }
    }
  }
}
```

- [ ] **Step 6: 写客户 MCP schema**

Create `configs/contracts/v1.1.0/customer_mcp.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dih.local/contracts/v1.1.0/customer_mcp.schema.json",
  "title": "DIH Customer MCP v1",
  "$defs": {
    "DiscoverCapabilitiesInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["query"],
      "properties": {
        "query": {"type": "string", "minLength": 1},
        "markets": {"type": "array", "items": {"type": "string"}},
        "data_domains": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50}
      }
    },
    "DiscoverCapabilitiesOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["catalog_digest", "items"],
      "properties": {
        "catalog_digest": {"type": "string"},
        "items": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["capability_id", "display_name", "data_domain", "why_this"],
            "properties": {
              "capability_id": {"type": "string"},
              "display_name": {"type": "string"},
              "data_domain": {"type": "string"},
              "markets": {"type": "array", "items": {"type": "string"}},
              "why_this": {"type": "string"},
              "cost_estimate_usd": {"type": "number"}
            }
          }
        }
      }
    },
    "EstimateTaskInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["template_id", "package_type", "primary_market", "category_id", "window_start", "window_end", "budget"],
      "properties": {
        "template_id": {"type": "string"},
        "package_type": {"type": "string", "enum": ["quick", "standard"]},
        "primary_market": {"type": "string", "pattern": "^[A-Z]{2}$"},
        "compare_markets": {"type": "array", "items": {"type": "string", "pattern": "^[A-Z]{2}$"}, "maxItems": 3},
        "category_id": {"type": "string"},
        "window_start": {"type": "string"},
        "window_end": {"type": "string"},
        "budget": {"$ref": "#/$defs/BudgetInput"}
      },
      "allOf": [
        {"if": {"properties": {"package_type": {"const": "quick"}}}, "then": {"properties": {"compare_markets": {"maxItems": 1}}}},
        {"if": {"properties": {"package_type": {"const": "standard"}}}, "then": {"properties": {"compare_markets": {"maxItems": 3}}}}
      ]
    },
    "EstimateTaskOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["estimate_id", "max_cost_usd", "currency", "price_book_version", "expires_at"],
      "properties": {
        "estimate_id": {"type": "string"},
        "max_cost_usd": {"type": "number"},
        "currency": {"type": "string"},
        "price_book_version": {"type": "string"},
        "expires_at": {"type": "string"},
        "breakdown": {"type": "array", "items": {"type": "object"}}
      }
    },
    "CreateTaskInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["idempotency_key", "template_id", "package_type", "primary_market", "category_id", "brand", "window_start", "window_end", "decision_question", "budget", "acceptance_contact_id"],
      "properties": {
        "idempotency_key": {"type": "string", "minLength": 1},
        "template_id": {"type": "string"},
        "package_type": {"type": "string", "enum": ["quick", "standard"]},
        "primary_market": {"type": "string", "pattern": "^[A-Z]{2}$"},
        "compare_markets": {"type": "array", "items": {"type": "string", "pattern": "^[A-Z]{2}$"}, "maxItems": 3},
        "category_id": {"type": "string"},
        "brand": {"type": "string"},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "window_start": {"type": "string"},
        "window_end": {"type": "string"},
        "decision_question": {"type": "string"},
        "does_not_answer": {"type": "array", "items": {"type": "string"}},
        "seed_products": {
          "type": "array",
          "items": {"type": "string", "minLength": 1},
          "anyOf": [
            {"maxItems": 0},
            {"minItems": 3, "maxItems": 10}
          ]
        },
        "target_price_band": {
          "oneOf": [
            {"type": "null"},
            {"$ref": "#/$defs/TargetPriceBand"}
          ]
        },
        "budget": {"$ref": "#/$defs/BudgetInput"},
        "acceptance_contact_id": {"type": "string"}
      },
      "allOf": [
        {"if": {"properties": {"package_type": {"const": "quick"}}}, "then": {"properties": {"compare_markets": {"maxItems": 1}}}},
        {"if": {"properties": {"package_type": {"const": "standard"}}}, "then": {"properties": {"compare_markets": {"maxItems": 3}}}}
      ]
    },
    "TargetPriceBand": {
      "type": "object",
      "additionalProperties": false,
      "required": ["currency"],
      "properties": {
        "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "min_amount": {
          "oneOf": [
            {"type": "string", "pattern": "^(0|[1-9][0-9]*)(\\.[0-9]{1,6})?$"},
            {"type": "number", "minimum": 0},
            {"type": "null"}
          ]
        },
        "max_amount": {
          "oneOf": [
            {"type": "string", "pattern": "^(0|[1-9][0-9]*)(\\.[0-9]{1,6})?$"},
            {"type": "number", "minimum": 0},
            {"type": "null"}
          ]
        }
      },
      "anyOf": [
        {"required": ["min_amount"]},
        {"required": ["max_amount"]}
      ],
      "not": {
        "properties": {
          "min_amount": {"type": "null"},
          "max_amount": {"type": "null"}
        },
        "required": ["min_amount", "max_amount"]
      },
      "description": "市场原币价格带；不换算。服务层校验 min_amount <= max_amount；金额非负；币种三个大写字母。"
    },
    "CreateTaskOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id", "status", "plan_version_id", "run_ids", "created_at"],
      "properties": {
        "task_id": {"type": "string"},
        "status": {"type": "string"},
        "plan_version_id": {"type": "string"},
        "run_ids": {"type": "array", "items": {"type": "string"}},
        "quote_id": {"type": "string"},
        "created_at": {"type": "string"}
      }
    },
    "GetTaskInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id"],
      "properties": {"task_id": {"type": "string"}}
    },
    "GetTaskOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id", "status", "package_type", "markets", "updated_at"],
      "properties": {
        "task_id": {"type": "string"},
        "status": {"type": "string"},
        "package_type": {"type": "string", "enum": ["quick", "standard"]},
        "markets": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["market_code", "market_role"],
            "properties": {
              "market_code": {"type": "string", "pattern": "^[A-Z]{2}$"},
              "market_role": {"type": "string", "enum": ["primary", "compare"]},
              "quality_status": {"type": ["string", "null"]},
              "data_gaps": {"type": "array", "items": {"type": "object"}}
            }
          }
        },
        "delivery_manifest_id": {"type": "string"},
        "updated_at": {"type": "string"}
      }
    },
    "CancelTaskInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id", "idempotency_key", "reason_code"],
      "properties": {
        "task_id": {"type": "string", "minLength": 1},
        "idempotency_key": {"type": "string", "minLength": 1, "description": "必填；同键同 reason_code 重放，同键不同 reason_code 返回 idempotency_conflict"},
        "reason_code": {"type": "string", "minLength": 1, "description": "必填取消原因码；不得为空"}
      }
    },
    "CancelTaskOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id", "status", "cancelled_runs", "preserved_artifacts", "cancelled_at"],
      "properties": {
        "task_id": {"type": "string"},
        "status": {"type": "string"},
        "cancelled_runs": {"type": "array", "items": {"type": "string"}},
        "preserved_artifacts": {"type": "array", "items": {"type": "string"}},
        "cancelled_at": {"type": "string"}
      }
    },
    "GetDeliveryManifestInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["task_id"],
      "properties": {
        "task_id": {"type": "string"},
        "manifest_version": {"type": "integer", "minimum": 1}
      }
    },
    "GetDeliveryManifestOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["manifest_id", "task_id", "report_artifact_id", "manifest_sha256", "files", "access_scope", "retention_class", "published_at"],
      "properties": {
        "manifest_id": {"type": "string"},
        "task_id": {"type": "string"},
        "report_artifact_id": {"type": "string"},
        "manifest_sha256": {"type": "string"},
        "files": {"type": "array", "items": {"type": "object"}},
        "access_scope": {"type": "array", "items": {"type": "string"}},
        "retention_class": {"type": "string"},
        "published_at": {"type": "string"}
      }
    },
    "GetEvidenceInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["claim_id"],
      "properties": {"claim_id": {"type": "string"}}
    },
    "GetEvidenceOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["claim_id", "claim_status", "evidence_grade", "items"],
      "properties": {
        "claim_id": {"type": "string"},
        "claim_status": {"type": "string"},
        "evidence_grade": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object"}}
      }
    },
    "CollectInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["capability_id", "params", "idempotency_key", "budget"],
      "properties": {
        "capability_id": {"type": "string"},
        "params": {"type": "object"},
        "idempotency_key": {"type": "string"},
        "budget": {"$ref": "#/$defs/BudgetInput"}
      }
    },
    "CollectOutput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["run_id", "task_id", "status", "accepted_at"],
      "properties": {
        "run_id": {"type": "string"},
        "task_id": {"type": "string"},
        "status": {"type": "string"},
        "accepted_at": {"type": "string"}
      }
    },
    "BudgetInput": {
      "type": "object",
      "additionalProperties": false,
      "required": ["max_cost_usd"],
      "properties": {
        "max_cost_usd": {"type": "number", "minimum": 0},
        "max_pages": {"type": "integer", "minimum": 0},
        "max_records": {"type": "integer", "minimum": 0}
      }
    }
  }
}
```

`CreateTaskInput` 到 C4 `WorkbenchTaskCreateRequest` 的映射固定如下，C13 不得另起字段名：

| `CreateTaskInput` | C4 目标 | 规则 |
|---|---|---|
| `idempotency_key` | `Idempotency-Key` 请求头 → `workbench_tasks.idempotency_key_hash` | 必填；空白拒绝；服务层写 `sha256("workbench-task-create.v1:{key}")` |
| `compare_markets` | `workbench_tasks.comparison_markets` | 改名；Quick 最多 1 个，Standard 最多 3 个；不得含 `primary_market`，不得重复 |
| `category_id` / `window_start` / `window_end` | `workbench_tasks.category` / `window_start` / `window_end` | `category_id` 写入 `category`；C4 请求把起止日期包装为 `window={start,end}` |
| `budget.max_cost_usd` / `budget.max_pages` / `budget.max_records` | `workbench_tasks.max_cost_usd` / `max_pages` / `max_records` | 展开；非空不得为负；金额用 `Decimal` |
| `seed_products` | `workbench_tasks.seed_products` | 原样保存；可省略或空数组；非空 3–10 项公开链接或平台 ID |
| `target_price_band` | `workbench_tasks.target_price_band` | 原样规范化保存；可空；市场原币；至少一个边界；`min_amount <= max_amount` |
| `acceptance_contact_id` | `workbench_tasks.acceptance_contact_id` | 非空必须是同工作区 owner/admin；空值回落任务 `owner_id`；`member` 返回 422 `acceptance_contact_not_member` |
| `package_type` / `primary_market` | `workbench_tasks.package_type` / `primary_market` | 原样保存；`markets` 由服务层写 `[primary_market] + comparison_markets` |

`create_task` 的精确请求示例：

```json
{
  "idempotency_key": "customer-task-0001",
  "template_id": "t1_voc",
  "package_type": "standard",
  "primary_market": "US",
  "compare_markets": ["DE"],
  "category_id": "breast_pump",
  "brand": "Momcozy",
  "competitors": ["Medela"],
  "window_start": "2026-07-01",
  "window_end": "2026-09-30",
  "decision_question": "Fit 与支撑哪个是主要摩擦？",
  "does_not_answer": ["不推断销量"],
  "seed_products": ["https://example.com/1", "https://example.com/2", "ID-3"],
  "target_price_band": {"currency": "USD", "min_amount": "10", "max_amount": "30"},
  "budget": {"max_cost_usd": 120.5, "max_pages": 10, "max_records": 500},
  "acceptance_contact_id": "6f0c1a5e-7d1f-4f4e-9a4e-2b0f7c9d1e21"
}
```

- [ ] **Step 7: 把附录 A 的 `schemas` 数组替换为四份 schema ref**

用以下数组替换附录 A 的 `schemas` 数组：

```json
[
  {"id": "registry", "path": "configs/contracts/v1.1.0/registry.schema.json", "kind": "registry", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"},
  {"id": "report_contract", "path": "apps/api/schemas/report_contract.schema.json", "kind": "report_contract", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"},
  {"id": "delivery_manifest", "path": "configs/contracts/v1.1.0/delivery_manifest.schema.json", "kind": "delivery_manifest", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"},
  {"id": "customer_mcp", "path": "configs/contracts/v1.1.0/customer_mcp.schema.json", "kind": "customer_mcp", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"}
]
```

- [ ] **Step 8: 重新生成 registry 并运行测试**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py build \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --out configs/contracts/v1.1.0/registry.json
cd apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q
```

Expected: `registry built`；`50 passed`。

- [ ] **Step 9: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add configs/contracts/v1.1.0 scripts/contract_registry.py "docs/design/【契约冻结】v1-表名-枚举-接口.md" apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(contract): add report delivery and customer MCP schemas"
```

---

### Task 10: 负向 Fixture 与 Checker 语义测试

**Files:**
- Create: `apps/api/tests/fixtures/contract_registry/negative/duplicate_table.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/duplicate_column.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/banned_enum_value.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/mcp_tool_count.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/missing_phase.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/unregistered_path.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/page_route_count.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/idempotency_contract_mismatch.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/registry_drift.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `check_semantics`、CLI `check`。
- Produces: 每个负向 fixture 只触发一个错误码。
- Produces: `registry_out_of_date` 的回归测试。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
import copy

NEGATIVE_DIR = (
    PROJECT_ROOT / "apps/api/tests/fixtures/contract_registry/negative"
)


def _mutate(registry: dict, mutation: str) -> dict:
    value = copy.deepcopy(registry)
    if mutation == "duplicate_table":
        value["tables"].append(copy.deepcopy(value["tables"][0]))
    elif mutation == "duplicate_column":
        value["tables"][0]["columns"].append(
            copy.deepcopy(value["tables"][0]["columns"][0])
        )
    elif mutation == "banned_enum_value":
        value["enums"][0]["banned_values"] = [value["enums"][0]["values"][0]]
    elif mutation == "mcp_tool_count":
        value["mcp"]["tools"] = value["mcp"]["tools"][:7]
    elif mutation == "missing_phase":
        value["phases"] = value["phases"][:-1]
    elif mutation == "unregistered_path":
        value["paths"].append(copy.deepcopy(value["paths"][0]))
    elif mutation == "page_route_count":
        value["page_routes"] = value["page_routes"][:-1]
    elif mutation == "idempotency_contract_mismatch":
        path = value["paths"][0]
        path["idempotent"] = True
        path["idempotency"] = {
            "header": "Idempotency-Key",
            "required": True,
            "replay_status": 200,
            "replay_header": "Idempotent-Replay",
            "conflict_error": "idempotency_conflict",
        }
    else:
        raise AssertionError(f"unknown mutation: {mutation}")
    return value


def test_negative_fixtures_are_rejected_with_specific_codes() -> None:
    module = load_module()
    schema = _load_schema("registry.schema.json")
    expected = {
        "duplicate_table": "duplicate_table",
        "duplicate_column": "duplicate_column:runs",
        "banned_enum_value": "banned_enum_value:runs.status",
        "mcp_tool_count": "mcp_tool_count",
        "missing_phase": "phase_sequence_invalid",
        "unregistered_path": "duplicate_path",
        "page_route_count": "page_route_count",
        "idempotency_contract_mismatch": "idempotency_conflict_unbound:runs.list",
    }
    for fixture_path in sorted(NEGATIVE_DIR.glob("*.json")):
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        mutation = fixture["mutation"]
        if mutation == "registry_drift":
            continue
        errors = module.validate_registry(_mutate(minimal_registry(), mutation), schema)
        assert expected[mutation] in errors, (fixture_path.name, errors)


def test_check_detects_registry_drift(tmp_path: Path) -> None:
    module = load_module()
    registry = minimal_registry()
    doc = tmp_path / "contract.md"
    doc.write_text(
        f"{BEGIN}\n```json\n{json.dumps(registry, ensure_ascii=False)}\n```\n{END}\n",
        encoding="utf-8",
    )
    schema = tmp_path / "registry.schema.json"
    schema.write_text(
        (PROJECT_ROOT / "configs/contracts/v1.1.0/registry.schema.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    generated = tmp_path / "registry.json"
    assert module.build(doc, schema, generated) == 0
    generated.write_text(generated.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert module.check(doc, schema, generated) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。fixture 目录不存在。

- [ ] **Step 3: 写负向 fixture**

Create `apps/api/tests/fixtures/contract_registry/negative/duplicate_table.json`:

```json
{"mutation": "duplicate_table"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/duplicate_column.json`:

```json
{"mutation": "duplicate_column"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/banned_enum_value.json`:

```json
{"mutation": "banned_enum_value"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/mcp_tool_count.json`:

```json
{"mutation": "mcp_tool_count"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/missing_phase.json`:

```json
{"mutation": "missing_phase"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/unregistered_path.json`:

```json
{"mutation": "unregistered_path"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/page_route_count.json`:

```json
{"mutation": "page_route_count"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/idempotency_contract_mismatch.json`:

```json
{"mutation": "idempotency_contract_mismatch"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/registry_drift.json`:

```json
{"mutation": "registry_drift"}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `52 passed`。

- [ ] **Step 5: 运行 checker 负向命令**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
cp configs/contracts/v1.1.0/registry.json /tmp/registry-drift.json
printf ' ' >> /tmp/registry-drift.json
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry /tmp/registry-drift.json
```

Expected: exit code 1，输出包含 `registry_out_of_date`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add apps/api/tests/fixtures/contract_registry apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "test(contract): add negative registry fixtures"
```

---

### Task 11: 契约正文 v1.1 与对象账本

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: 附录 A 的完整机器 registry。
- Produces: 正文表格、阶段账本、权威规则、错误码表、MCP 八工具表。
- Produces: 文档版本 `v1.1` 与变更记录。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_contract_body_contains_every_table_name() -> None:
    registry = load_contract_registry()
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    missing = [
        table["name"] for table in registry["tables"] if table["name"] not in text
    ]
    assert missing == []


def test_contract_body_contains_customer_mcp_table() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for name in [
        "discover_capabilities",
        "estimate_task",
        "create_task",
        "get_task",
        "cancel_task",
        "get_delivery_manifest",
        "get_evidence",
        "collect",
    ]:
        assert name in text


def test_contract_body_contains_c2_to_c14_ledger() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for index in range(2, 15):
        assert f"| C{index} |" in text


def test_contract_body_contains_canonical_profile_rules() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for fragment in [
        "RFC 8785",
        "dih-canonical-json-v1",
        "contract_sha256",
        "excluded_top_level_keys",
    ]:
        assert fragment in text


def test_contract_body_contains_c2_c3_ownership_tokens() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for fragment in [
        "唯一授权事实源",
        "错误信封",
        "project_id IS NULL",
        "project_id IS NOT NULL",
        "tool_allowlist",
        "workspace_role_invalid",
        "report_review_approved",
        "Idempotency-Key",
        "Idempotent-Replay",
        "seed_products",
        "target_price_band",
        "idempotency_key_hash",
        "create_initial_workflow_version_for_task",
        "execution_steps",
        "审计动作注册表",
        "audit-actions.v1",
        "audit_action_unregistered",
        "reviewer_assignment_expired",
    ]:
        assert fragment in text
    registry = load_contract_registry()
    for action in registry["audit_actions"]["actions"]:
        assert action["name"] in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。正文还没有 C2-C14 账本和完整对象表。

- [ ] **Step 3: 在契约 §0 增加版本与权威规则**

在 `## 0. 为什么要有这份文件` 之前插入以下章节。把原标题改为 `## 0.1 为什么要有这份文件`。

````markdown
## 0.0 版本、权威与生成关系

| 项 | 值 |
|---|---|
| 契约版本 | `v1.1` |
| 冻结日期 | 2026-10-22 |
| 状态 | 生效 |
| 权威文档 | 本文件 |
| 机器生成物 | `configs/contracts/v1.1.0/registry.json` |
| 机器 schema | `configs/contracts/v1.1.0/registry.schema.json` |
| 生成命令 | `python scripts/contract_registry.py build` |
| 校验命令 | `python scripts/contract_registry.py check` |

规则：

1. 本文件正文与附录 A 冲突时，以正文为准；附录 A 是正文的机器投影。
2. `registry.json` 只能由 `scripts/contract_registry.py build` 生成。禁止手改。
3. 新增表、列、枚举、路径、MCP 工具或错误码时，先改正文与附录 A，再重新生成。
4. checker 失败时不得提交。不得用生成物反向覆盖 Markdown。
5. C1 只登记对象。C2-C14 才实现行为和迁移。

### 0.0.1 迁移号

| 切片 | 迁移号 | down_revision |
|---|---|---|
| C2 | `202610220060` | `202610220059` |
| C3 | `202610220061` | `202610220060` |
| C4 | `202610220062` | `202610220061` |
| C5 | `202610220063` | `202610220062` |
| C6 | `202610220064` | `202610220063` |
| C7 | `202610220065` | `202610220064` |
| C8 | `202610220066` | `202610220065` |
| C9 | `202610220067` | `202610220066` |
| C10 | `202610220068` | `202610220067` |
| C11 | `202610220069` | `202610220068` |
| C12 | `202610220070` | `202610220069` |

> **2026-10-26 重排。** 058 与 059 已被 S0 报告链占用（`claims`、`report_artifacts`，
> 见 2026-10-25-n1-change-requests.md）。上表整体顺延两号，起点是当前真实
> head `202610220059`。C2–C12 与 C14 的分片文档已同步改号，全系列一号一名。
> C0 文档里的 `202610210052`/`053`/`056`/`057` 是历史记录，不是活跃分配。

迁移号是全局串行资源。同一波次只允许一个切片持有下一号迁移。

C1 不新增迁移。C4 新增的 `workbench_tasks` 列与索引、`workflow_versions.workbench_task_id`、`runs.market_code` 与 `uq_runs_workflow_version_market` 全部落在唯一迁移 `202610220062`，不得拆到第二个 C4 迁移。`workflow_versions.plan_payload` 是既有列，C4 只在该列写入 `execution_steps` 不可变快照，不新增列。
````

- [ ] **Step 4: 在 §6 后增加 C2-C14 对象账本**

插入以下章节：

````markdown
## 6A. C2-C14 对象账本

| ID | 工作包 | 拥有对象 | 退出条件 |
|---|---|---|---|
| C2 | 身份、项目 ACL 与统一审计 | `project_members`、`audit_events`、`workspace_members.role` | 角色、项目 ACL、审计哈希链通过 |
| C3 | 项目密钥与项目级凭据 | `project_api_keys` 扩展、`platform_credential_bundles` 扩展 | 密钥轮换、凭据作用域、`/connectors` 验收通过 |
| C4 | 任务单提交、计划关联与幂等 | `workbench_tasks`（含 `package_type`、`primary_market`、`comparison_markets`、`seed_products`、`target_price_band`、`idempotency_key_hash`）、`workflow_versions.workbench_task_id`、`workflow_versions.plan_payload.execution_steps`、`runs.market_code`（`market_role` 由任务单派生，不落列） | 七槽位、包型与市场角色、种子商品、目标价格带、创建幂等、初始计划版本、逐市场幂等提交通过 |
| C5 | 预算、账本与定价 | `tool_prices`、`quota_accounts`、`tool_calls`、`authorizations.run_id`、账本符号约束；价格初始值来自 `price_book_v1.json` | 价格登记、预算预留、账本与额度通过 |
| C6 | Run 执行收敛、尝试与取消 | `run_steps` 扩展列、`run_step_attempts`、attempt 状态 | 多 step、attempt、取消、租约与旧入口收敛通过 |
| C7 | 证据、Claim 与独立来源 | `claims` 扩展、`claim_evidence` 扩展、`evidences` 扩展 | Claim 字段、独立来源、证据上限、审核字段通过 |
| C8 | 数据集质量、缺口与首期模板 | `dataset_versions` 扩展、`data_gaps`、`market_assessments` | 数据集哈希、逐市场质量、缺口、首期模板通过 |
| C9 | 不可变报告合同与产物发布 | `report_artifacts` 扩展、`report_audit_events` 扩展 | 报告生命周期、审核签字、不可变与取代通过 |
| C10 | 交付 Manifest、bundle、验收与分享 | `report_artifacts` 交付列、`report_audit_events` 交付事件 | manifest、sidecar、公开投影、验收快照、篡改拒下载通过 |
| C11 | 工作区伪名化、导出遮蔽与保留 | `workspace_pseudonym_salts`、`legal_holds`、`retention_cleanup_runs`、`retention_tombstones` | 伪名、保留、法律保留、清理记录通过 |
| C12 | 删除请求、墓碑、删除证明与 DSR | `deletion_requests`、`deletion_tombstones`、`deletion_subprocessor_receipts`、`deletion_proofs`、`deletion_replay_runs`、`deletion_replay_items`、`dsr_cases`、`privacy_audit_events` | 删除状态机、墓碑、证明、恢复重放、DSR 通过 |
| C13 | 客户 MCP `/mcp/customer` 八工具 | `/mcp/customer`、八个工具；不建租约表 | 客户 `tools/list` 只返回八工具 |
| C14 | 控制台 11 路由、CI 与验收门禁 | 页面路由、CI、Playwright、PG0 验收 | 11 路由、4 一级导航、全量测试与浏览器验收通过 |

对象详情以正文与附录 A 为准。正文不重复列全部列名。
````

- [ ] **Step 5: 填写附录 A 的 `phases[].objects`**

用以下数组替换附录 A 的 `phases` 数组。`objects` 只放对象名，不重复写列。

```json
[
  {"id": "C2", "name": "身份、项目 ACL 与统一审计", "scope": "工作区角色、项目成员、追加式审计、请求 ID", "objects": ["table:project_members", "table:audit_events", "table:workspace_members", "enum:workspace_members.role", "enum:audit_events.actor_type", "enum:audit_events.result", "path:projects.members.list", "path:projects.members.grant", "path:projects.members.revoke", "path:workspaces.members.role", "path:audit.events.list", "path:audit.events.verify", "error:project_access_forbidden", "error:workspace_last_owner_required", "error:workspace_owner_required", "error:workspace_role_invalid", "error:audit_action_unregistered"]},
  {"id": "C3", "name": "项目密钥与项目级凭据", "scope": "密钥状态、轮换、能力白名单、项目级凭据、Cookie 元数据", "objects": ["table:project_api_keys", "table:platform_credential_bundles", "enum:project_api_keys.status", "path:project_keys.create", "path:project_keys.list", "path:project_keys.rotate", "path:project_keys.revoke", "path:credentials.list", "path:credentials.update", "path:credentials.delete", "error:project_api_key_active_exists", "error:project_api_key_not_found", "error:credential_invalid"]},
  {"id": "C4", "name": "任务单提交、计划关联与幂等", "scope": "七槽位任务单、包型与主/对比市场、种子商品、目标价格带、创建幂等、初始计划版本接缝、逐市场 run 幂等", "objects": ["table:workbench_tasks", "table:workflow_versions", "table:runs", "enum:workbench_tasks.status", "enum:workbench_tasks.package_type", "enum:workbench_tasks.task_type", "enum:market_code", "path:workbench.tasks.create", "path:workbench.tasks.list", "path:workbench.tasks.detail", "path:workbench.tasks.update", "path:workbench.tasks.gates", "path:runs.create", "error:idempotency_conflict", "error:invalid_request", "error:market_unsupported", "error:task_locked", "error:workflow_version_already_submitted", "error:taxonomy_unavailable", "error:package_type_invalid", "error:comparison_markets_exceeded", "error:acceptance_contact_not_member", "error:budget_invalid"]},
  {"id": "C5", "name": "预算、账本与定价", "scope": "单价、额度账户、调用记录、按 run 授权、账本符号、内联批准动作", "objects": ["table:tool_prices", "table:quota_accounts", "table:tool_calls", "table:workbench_approval_actions", "table:authorizations", "table:run_ledger_entries", "table:task_runs", "enum:tool_prices.confidence", "enum:entry_kind", "enum:workbench_approval_actions.action_type", "enum:workbench_approval_actions.status", "path:quota.summary", "path:quota.project", "path:workbench.tasks.approvals.create", "path:workbench.tasks.approvals.decide", "error:quota_exceeded", "error:tool_not_priced", "error:approval_required", "error:quota_account_missing", "error:approval_not_found", "error:approval_self_approval_forbidden", "error:approval_state_conflict"]},
  {"id": "C6", "name": "Run 执行收敛、尝试与取消", "scope": "逻辑 step、attempt、重试、取消、租约", "objects": ["table:run_steps", "table:run_step_attempts", "enum:run_step_attempts.status", "enum:runs.status", "enum:runs.outcome", "enum:run_steps.status", "path:runs.cancel", "error:run_not_found", "error:idempotency_conflict"]},
  {"id": "C7", "name": "证据、Claim 与独立来源", "scope": "Claim 治理字段、审核、风险、独立来源、证据扩展", "objects": ["table:claims", "table:claim_evidence", "table:evidences", "enum:evidence_grade", "enum:claim_review_status", "enum:claim_risk_flags", "enum:claims.blocked_reason", "enum:claim_evidence.role", "enum:source_cluster_basis", "path:claims.list", "path:claims.detail", "error:claim_not_found"]},
  {"id": "C8", "name": "数据集质量、缺口与首期模板", "scope": "数据集哈希、逐市场质量、结构化 gap、首期模板", "objects": ["table:data_gaps", "table:market_assessments", "table:dataset_versions", "enum:data_domains", "enum:domain_status", "enum:market_quality_status", "enum:data_gaps.severity", "enum:data_gaps.status", "schema:template_capability_profile", "error:capability_not_allowed"]},
  {"id": "C9", "name": "不可变报告合同与产物发布", "scope": "报告生命周期、审核签字、内部审核人、发布、取代", "objects": ["table:report_artifacts", "table:report_audit_events", "table:report_reviewer_assignments", "enum:report_artifacts.status", "enum:report_audit_events.event_type", "enum:report_reviewer_assignments.assignment_scope", "enum:report_reviewer_assignments.status", "schema:report_contract", "path:reports.drafts.create", "path:reports.reviewers.assign", "path:reports.reviewers.revoke", "path:reports.contract", "path:reports.artifact", "path:reports.sop", "path:reports.revisions", "path:reports.reviews.create", "path:reports.publish", "error:report_quality_not_ready", "error:report_contract_invalid", "error:report_contract_not_published", "error:report_contract_hash_mismatch", "error:report_artifact_not_draft", "error:report_artifact_incomplete", "error:report_artifact_integrity_failed", "error:report_review_required", "error:report_publish_gate_blocked", "error:report_revision_target_invalid", "error:report_publish_forbidden", "error:report_forbidden_language", "error:reviewer_assignment_required", "error:reviewer_self_review_forbidden", "error:reviewer_assignment_invalid", "error:reviewer_assignment_expired"]},
  {"id": "C10", "name": "交付 Manifest、bundle、验收与分享", "scope": "manifest、sidecar、公开投影、验收快照、篡改检测、Quick 方向稿、验收事件、延期分享", "objects": ["table:report_artifacts", "table:report_audit_events", "enum:report_artifacts.delivery_status", "enum:report_artifacts.delivery_class", "schema:delivery_manifest", "path:delivery.publish", "path:delivery.manifest", "path:delivery.download", "path:delivery.quick_draft.create", "path:delivery.quick_draft.read", "path:delivery.quick_draft.task_read", "path:delivery.acceptance.accept", "path:delivery.acceptance.dispute", "path:delivery.acceptance.deemed_accept", "path:delivery.acceptance.read", "error:delivery_integrity_error", "error:gate_failed", "error:publish_forbidden", "error:delivery_not_publishable", "error:delivery_input_invalid", "error:delivery_pii_detected", "error:idempotency_key_required", "error:quick_draft_not_allowed", "error:quick_draft_claim_invalid", "error:acceptance_window_open", "error:acceptance_already_closed", "error:acceptance_reference_invalid", "error:acceptance_not_applicable"]},
  {"id": "C11", "name": "工作区伪名化、导出遮蔽与保留", "scope": "伪名盐、法律保留、导出遮蔽、保留清理、保留墓碑、TTL", "objects": ["table:workspace_pseudonym_salts", "table:legal_holds", "table:retention_cleanup_runs", "table:retention_tombstones", "enum:workspace_pseudonym_salts.salt_version", "enum:legal_holds.status", "enum:data_class", "enum:retention_cleanup_runs.mode", "enum:retention_cleanup_runs.status", "enum:retention_tombstones.reason", "path:datasets.export.create", "error:dataset_export_internal_isolated_source"]},
  {"id": "C12", "name": "删除请求、墓碑、删除证明与 DSR", "scope": "删除状态机、重放、证明、DSR、隐私审计", "objects": ["table:deletion_requests", "table:deletion_tombstones", "table:deletion_subprocessor_receipts", "table:deletion_proofs", "table:deletion_replay_runs", "table:deletion_replay_items", "table:dsr_cases", "table:privacy_audit_events", "enum:deletion_requests.target_type", "enum:deletion_requests.requested_by_role", "enum:deletion_requests.status", "enum:deletion_subprocessor_receipts.status", "enum:dsr_cases.request_type", "enum:dsr_cases.status", "enum:dsr_cases.responsibility", "enum:deletion_replay_runs.status", "enum:deletion_replay_items.status", "enum:privacy_audit_events.stream_type", "enum:privacy_audit_events.actor_kind", "path:privacy.deletion.create", "path:privacy.deletion.list", "path:privacy.deletion.detail", "path:privacy.deletion.approve", "path:privacy.deletion.confirm", "path:privacy.deletion.execute", "path:privacy.deletion.proof", "path:privacy.legal_holds.list", "path:privacy.dsr.list", "path:privacy.dsr.detail", "path:privacy.audit.list", "error:legal_hold_active"]},
  {"id": "C13", "name": "客户 MCP /mcp/customer 八工具", "scope": "客户入口、八工具、能力白名单、速率并发租约", "objects": ["mcp_tool:discover_capabilities", "mcp_tool:estimate_task", "mcp_tool:create_task", "mcp_tool:get_task", "mcp_tool:cancel_task", "mcp_tool:get_delivery_manifest", "mcp_tool:get_evidence", "mcp_tool:collect", "schema:customer_mcp", "path:mcp.customer.post", "path:mcp.customer.get", "error:tool_not_allowed", "error:capability_not_allowed", "error:cookie_not_accepted", "error:rate_limited", "error:idempotency_conflict", "error:invalid_request", "error:state_conflict"]},
  {"id": "C14", "name": "控制台 11 路由、CI 与验收门禁", "scope": "页面路由、CI、Playwright、PG0 验收", "objects": ["schema:registry", "page_route:/", "page_route:/capabilities", "page_route:/capabilities/[toolId]", "page_route:/reports/public/[id]", "page_route:/docs", "page_route:/workbench", "page_route:/workbench/[taskId]", "page_route:/reports", "page_route:/reports/[artifactId]", "page_route:/connectors", "page_route:/settings", "primary_nav:workbench", "primary_nav:reports", "primary_nav:connectors", "primary_nav:settings"]}
]
```

- [ ] **Step 5A: 写入 C2/C3 身份、ACL、密钥与凭据正文**

在契约 §1 新增以下小节。C2 与 C3 只读本文件，不得再改契约。

````markdown
### 1.4 身份事实源

`workspace_members.role` 是唯一授权事实源。取值只有 `owner`、`admin`、`member`。

`workspaces.owner_id` 不是授权事实源。它只表示创建者与账单联系人。每个工作区的 `owner_id` 用户必须有一条 `workspace_members.role='owner'` 行。该用户不得被降级或移除，直到所有旧检查迁移完毕。

`project_members` 只表达 `member` 可查看某项目。owner/admin 不依赖该表即可访问工作区全部项目。`project_members` 不设项目级角色列。

每个工作区至少有一名 owner。最后一个 owner 不能被降级或移除。

功能开关 `WORKSPACE_RBAC_ENFORCED` 控制项目 ACL 是否生效。关闭时保留旧的项目可见性；打开时执行本节的 403/404 规则。审计写入没有关闭开关。

`audit_events.prev_hash` 指向同工作区上一事件的 `event_hash`，字段含义是“上一事件哈希”。首条事件的 `prev_hash` 是 64 个 `0`。`event_hash` 是 SHA-256 小写十六进制。

### 1.5 C2 新表列

`project_members`：

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `id` | uuid | 否 | 主键 |
| `workspace_id` | uuid | 否 | 工作区 |
| `project_id` | uuid | 否 | 项目 |
| `user_id` | uuid | 否 | 被授权的工作区成员 |
| `created_by_user_id` | uuid | 否 | 授权人 |
| `created_at` | datetime | 否 | 授权时间 |

唯一键 `(workspace_id, project_id, user_id)`。复合外键 `(workspace_id, project_id)` 指向 `projects(workspace_id, id)`。

`audit_events`：

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `id` | uuid | 否 | 主键 |
| `workspace_id` | uuid | 否 | 工作区 |
| `project_id` | uuid | 是 | 项目 |
| `sequence_number` | integer | 否 | 工作区内从 1 递增 |
| `actor_user_id` | uuid | 是 | 用户主体；系统事件为空 |
| `actor_type` | string(20) | 否 | `user` / `system` / `project_key` |
| `action` | string(80) | 否 | 动作名 |
| `resource_type` | string(40) | 否 | 资源类型 |
| `resource_id` | string(120) | 是 | 资源 ID |
| `request_id` | string(64) | 是 | 请求 ID |
| `result` | string(20) | 否 | `success` / `denied` / `failed` |
| `details` | json | 否 | 最小化细节；不得含密钥、Cookie、盐、原始 PII |
| `prev_hash` | string(64) | 否 | 上一事件哈希 |
| `event_hash` | string(64) | 否 | 当前事件 SHA-256 |
| `occurred_at` | datetime | 否 | 业务发生时间 |
| `created_at` | datetime | 否 | 数据库写入时间 |

唯一键 `(workspace_id, sequence_number)` 与 `(workspace_id, event_hash)`。

### 1.6 C3 凭据作用域与部分唯一索引

`platform_credential_bundles.project_id` 为空表示工作区级，非空表示项目级。

Postgres 的普通唯一约束不会把两个 `NULL` 视为相等。因此不得使用 `UNIQUE (workspace_id, provider_id, project_id)`。必须使用两个部分唯一索引：

```text
uq_platform_credential_bundles_workspace_provider
  UNIQUE (workspace_id, provider_id) WHERE project_id IS NULL
uq_platform_credential_bundles_project_provider
  UNIQUE (workspace_id, project_id, provider_id) WHERE project_id IS NOT NULL
```

`platform_credential_scope` 只有三值：`project`、`workspace`、`none`。

`project_api_keys(workspace_id, project_id)` 与 `platform_credential_bundles(workspace_id, project_id)` 都必须有复合外键，指向 `projects(workspace_id, id)`。该外键阻止跨工作区绑定。

`project_api_keys.tool_allowlist` 是现有 MCP 工具名白名单，也是 C13 的工具 enforcement 事实源。`project_api_keys.capability_allowlist` 是 `tool_catalog.tool_id` 数组；空数组表示没有授权任何 capability。C3 负责存储、展示、审计，并通过 `ProjectApiKeyIdentity.capability_allowlist` 与 `allows_capability()` 暴露；C13 负责客户 MCP capability enforcement。

### 2.9 身份与审计枚举

`workspace_members.role`：`owner · admin · member`。
`audit_events.actor_type`：`user · system · project_key`。
`audit_events.result`：`success · denied · failed`。

### 2.10 审计动作注册表

审计动作只有一个版本化注册表：`audit-actions.v1`。注册表同时存在于本节与附录 A 的 `audit_actions` 对象，两者必须逐字一致。所有动作只写入唯一的 `audit_events` 表；不得建第二张审计表。`services.audit_log.AUDIT_ACTIONS` 必须与注册表动作名逐字一致。

规则：

1. 每个动作只有一个写入 owner；owner 切片负责在实现中调用 `append_audit_event`。`run.created` 的 owner 是 C4，唯一写入入口是 C4 `services/run_creation.create_run_with_audit`；C6 旧入口收敛只调用该接缝，不直接写 `run.created`。
2. 下游切片不得自造动作名。未登记动作抛 `audit_action_unregistered`（HTTP 500）；动作名形状非法抛 `audit_action_invalid`。
3. 动作名只允许小写字母、数字、下划线与点，至少两段，最长 80 字符。
4. 已登记的名称不得改名。新增动作必须先改本节与附录 A，再升级注册表版本；不得只改代码。
5. `reviewer.*` 动作只由 C2 与 C9 写入。内部审阅者不是客户工作区角色；`workspace_members.role` 仍然只有 `owner`、`admin`、`member`，不得出现 `reviewer`。
6. `audit_events.action` 是 `string(80)`，数据库不建 Enum；本注册表是服务层与文档层的唯一校验源。

| 动作 | owner | 用途 |
|---|---|---|
| `auth.login.succeeded` | C2 | 登录成功 |
| `auth.login.failed` | C2 | 登录失败 |
| `auth.logout.succeeded` | C2 | 登出成功 |
| `workspace.member.added` | C2 | 工作区成员新增 |
| `workspace.member.role_changed` | C2 | 工作区成员角色变更 |
| `workspace.member.removed` | C2 | 工作区成员移除 |
| `project.created` | C2 | 项目创建 |
| `project.updated` | C2 | 项目更新 |
| `project.archived` | C2 | 项目归档 |
| `project.member.added` | C2 | 项目成员授予 |
| `project.member.removed` | C2 | 项目成员撤销 |
| `project.access.denied` | C2 | 项目读权限拒绝 |
| `project.management.denied` | C2 | 项目管理权限拒绝 |
| `reviewer.access.granted` | C2 | 内部审阅者受限读/审核放行 |
| `reviewer.access.denied` | C2 | 内部审阅者受限读/审核拒绝 |
| `config.switch.changed` | C2 | 功能开关变更 |
| `project_api_key.issued` | C3 | 项目密钥签发 |
| `project_api_key.rotated` | C3 | 项目密钥轮换 |
| `project_api_key.revoked` | C3 | 项目密钥撤销 |
| `platform_credential.updated` | C3 | 平台凭据写入或更新 |
| `platform_credential.removed` | C3 | 平台凭据删除 |
| `task.created` | C4 | 任务单创建 |
| `task.cancelled` | C4 | 任务单取消 |
| `budget.price.changed` | C5 | 单价变更 |
| `budget.limit.changed` | C5 | 预算上限或额度变更 |
| `budget.blocked` | C5 | 预算阻断 |
| `budget.released` | C5 | 预算释放 |
| `task.retried` | C6 | 任务重试 |
| `run.created` | C4 | 运行创建；由 C4 `services/run_creation.create_run_with_audit` 接缝写，只在插入新 run 时写，幂等重放不写；C6 旧入口收敛调用该接缝，不直接写 |
| `run.cancel_requested` | C6 | 运行取消请求 |
| `run.cancelled` | C6 | 运行取消 |
| `run.retry_scheduled` | C6 | 运行重试已排期 |
| `run.retry_exhausted` | C6 | 运行重试耗尽 |
| `run.completed` | C6 | 运行完成 |
| `run.failed` | C6 | 运行失败 |
| `claim.review.submitted` | C7 | Claim 提交审核 |
| `claim.review.approved` | C7 | Claim 审核通过 |
| `claim.review.rejected` | C7 | Claim 审核拒绝 |
| `claim.review.overridden` | C7 | Claim 审核覆盖 |
| `claim.blocked` | C7 | Claim 阻断 |
| `claim.unblocked` | C7 | Claim 解除阻断 |
| `claim.revised` | C7 | Claim 修订 |
| `dataset.quality.evaluated` | C8 | 数据集质量评估 |
| `quality.assessment.computed` | C8 | 市场质量评分计算 |
| `quality.gap.resolved` | C8 | 数据缺口解除 |
| `quality.template.changed` | C8 | 质量模板或阈值变更 |
| `report.review.approved` | C9 | 报告审核通过 |
| `report.review.rejected` | C9 | 报告审核拒绝 |
| `report.published` | C9 | 报告发布 |
| `report.superseded` | C9 | 报告取代 |
| `reviewer.assignment.created` | C9 | 内部审阅者指派 |
| `reviewer.assignment.revoked` | C9 | 内部审阅者撤销 |
| `delivery.published` | C10 | 交付包发布 |
| `delivery.downloaded` | C10 | 交付包下载 |
| `delivery.projection.viewed` | C10 | 公开投影查看 |
| `delivery.tamper_detected` | C10 | 交付篡改检测 |
| `delivery.superseded` | C10 | 交付取代 |
| `privacy.projection.applied` | C11 | 导出遮蔽或伪名化应用 |
| `dataset.export.created` | C11 | 数据集导出创建 |
| `retention.cleanup.executed` | C11 | 保留清理执行 |
| `legal_hold.created` | C11 | 法律保留建立 |
| `legal_hold.released` | C11 | 法律保留解除 |
| `privacy.deletion.requested` | C12 | 删除请求创建 |
| `privacy.deletion.executed` | C12 | 删除执行 |
| `privacy.dsr.received` | C12 | DSR 案件接收 |
| `mcp.tool_call.started` | C13 | 客户 MCP 调用开始 |
| `mcp.tool_call.finished` | C13 | 客户 MCP 调用完成 |
| `mcp.tool_call.denied` | C13 | 客户 MCP 调用拒绝 |
````

- [ ] **Step 6: 在 §3 增加客户 MCP 与客户 REST**

插入以下内容：

````markdown
### 3.4 客户 MCP

客户 MCP 路径是 `/mcp/customer`。内部 MCP 路径 `/mcp` 保持不变。协议是 streamable HTTP。
客户 `tools/list` 只返回以下八个工具。顺序固定。

| # | 工具 | 只读 | 用途 |
|---|---|---:|---|
| 1 | `discover_capabilities` | 是 | 按自然语言、市场、数据域发现模板白名单能力 |
| 2 | `estimate_task` | 是 | 返回任务包报价、价格簿版本和有效期 |
| 3 | `create_task` | 否 | 幂等创建任务包订单 |
| 4 | `get_task` | 是 | 读取任务、市场、run 和 gap 状态 |
| 5 | `cancel_task` | 否 | 取消允许取消的任务 |
| 6 | `get_delivery_manifest` | 是 | 读取交付 manifest 与文件哈希 |
| 7 | `get_evidence` | 是 | 读取 Claim 绑定证据 |
| 8 | `collect` | 否 | 用 `capability_id` 创建受治理 run |

禁止出现在客户工具列表的名称：

```text
collect_endpoint · raw_provider_call · tiktok_creator_cookie · admin_query
```

请求检查顺序：

```text
Bearer 鉴权 → 密钥状态 → 工作区与项目绑定 → 工具白名单 → 能力白名单
→ Cookie 隔离 → 日额度 → 速率与并发 → 预算 → 执行与审计
```

### 3.5 客户 REST

客户 REST 只读面在首期延期。C13 只交付 `/mcp/customer` 八工具。
`/api/workbench/*`、`/api/runs/*`、`/api/tools/*` 是会话或内部面，不是客户开发者合同。
客户 REST 恢复时必须先升级契约并登记路径。

### 3.6 身份、密钥与隐私路径

`workspace_members.role` 是唯一授权事实源。`workspaces.owner_id` 不是授权事实源。
`project_members` 只表达 member 的项目可见性。`audit_events` 只追加。
`audit_events.prev_hash` 指向同工作区上一事件的 `event_hash`，字段含义是“上一事件哈希”。
功能开关 `WORKSPACE_RBAC_ENFORCED` 控制项目 ACL 是否生效。审计写入没有关闭开关。
MFA 延期。C12 的删除、DSR 与隐私审计路径不使用 `require_recent_mfa`，也不返回 `mfa_required`。权限只由 C2 的工作区角色与项目 ACL 判定。

C2、C3、C12 的路径以正文与附录 A 为准。正文至少列出前缀：

```text
/api/projects/{project_id}/members · /api/audit-events
/api/projects/{project_id}/keys · /api/settings/platform-credentials
/api/privacy/deletion-requests · /api/privacy/legal-holds
/api/privacy/dsr-cases · /api/privacy/audit-events
```

### 3.7 报告发布与交付路径

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/reports/{report_id}/contract` | 读取当前已发布合同 JSON |
| GET | `/api/reports/{report_id}/artifact` | 读取当前产物元数据 |
| GET | `/api/reports/{report_id}/sop` | 读取已发布 SOP HTML |
| GET | `/api/reports/{report_id}/revisions` | 读取修订链 |
| POST | `/api/reports/{report_id}/reviews` | 写入人工审核事件 |
| POST | `/api/reports/{report_id}/publish` | 发布草稿并取代旧版本 |
| POST | `/api/reports/{artifact_id}/delivery/publish` | 发布交付包 |
| GET | `/api/reports/{artifact_id}/delivery` | 下载交付 bundle |
| GET | `/api/reports/{artifact_id}/delivery/manifest` | 读取交付 manifest |

交付端点原文：

```text
POST /api/reports/{artifact_id}/delivery/publish
GET /api/reports/{artifact_id}/delivery
GET /api/reports/{artifact_id}/delivery/manifest
```

报告产物状态：`draft · published · superseded`。
产物发布约束：`ck_report_artifacts_status`（三值状态）与 `uq_report_artifacts_current_published`（每个 `report_id` 最多一行 `published`；部分唯一索引，条件 `status = 'published'`）。

交付状态 `delivery_status`：`pending · delivered · superseded`。它与 C9 的 `report_artifacts.status` 是两套枚举，不得复用同名状态机。
交付列：`delivery_status`（默认 `pending`）、`manifest_json`、`manifest_sha256`、`manifest_sidecar_sha256`、`public_contract_json`、`acceptance_snapshot_json`、`delivered_at`、`delivered_by`、`supersedes_delivery_id`、`publish_idempotency_key_hash`。
交付约束：`ck_report_artifacts_delivery_status`（`pending · delivered · superseded` 三值）与 `ck_report_artifacts_delivery_fields`（`pending` 时封存列为空；`delivered` 或 `superseded` 时 manifest、sidecar、公开投影、验收快照、`delivered_at`、`delivered_by` 全部非空）。
`POST /api/reports/{artifact_id}/publish` 不得存在；该路径形状会遮蔽 C9 的 `POST /api/reports/{report_id}/publish`。

`POST /api/reports/drafts` 是 C9 唯一草稿入口。请求只带 `task_id`、`run_id`、`template_id` 与决策问题；服务从 C8 的 `market_assessments`、`data_gaps`、`dataset_versions` 装配 1.1 合同。草稿的 `review`、`acceptance`、`delivery` 三组必须是合法占位：`review.reviewer_id` 与 `review.reviewer_assignment_id` 使用 nil UUID，`review.reviewer_role='internal_reviewer'`，`review.status='draft'`，`review.contract_sha256='0'*64`；`acceptance.status='pending'`，窗口用合同生成日与五个工作日；`delivery.manifest_id` 与 `delivery.report_artifact_id` 使用 nil UUID，`access_scope=['workspace_project']`，`retention_class='standard_24m'`；`artifact` 三个哈希使用 `'0'*64`。占位值不得写入审核事件或交付事件。

审核通过不得原地改草稿。C9 的 `create_reviewed_contract_version` 创建 `report_version + 1` 的新产物，`supersedes_id` 指向草稿，只填 `review` 组，草稿转 `superseded`。交付发布不得原地改已发布合同。C10 在 G-Claim/G-Publish 通过后调用 C9 的 `create_delivery_contract_version`，创建再下一个 `report_version` 的产物，`supersedes_id` 指向已发布的审核版本，只填 `acceptance` 与 `delivery` 组；该产物由 C9 在同一事务内发布，旧版本转 `superseded`。继承审核只允许在 `review.contract_sha256` 命中祖先审核事件且实质组 `content_contract_sha256` 完全一致时成立；任何实质组变化必须重新审核。

`content_contract_sha256` 的输入是合同去掉 `generated_at`、`artifact`、`review`、`acceptance`、`delivery`、`report_version`、`supersedes_id` 后的顶层键，按 `dih-canonical-json-v1` 规范化后取 SHA-256。`create_delivery_contract_version` 与 `publish_artifact` 都用这个函数，不得复制第二套。

### 3.10 内部审核人指派

`report_reviewer_assignments` 是审核主体的唯一事实源。`assignment_scope` 只有 `report_read` 与 `report_review`；`report_read` 只允许读指定 `report_id` 的合同、产物、SOP 与修订链，`report_review` 额外允许写 `report_review_approved` / `report_review_rejected` 事件并创建审核版本。`status` 只有 `active` 与 `revoked`；同一 `(report_id, reviewer_user_id)` 最多一条 `active` 行。`expires_at` 是必填的 `datetime`，不得为空；到期时间按 UTC 判定。

内部审核人不是客户工作区角色。`workspace_members.role` 仍然只有 `owner`、`admin`、`member`，不得新增 `reviewer`。指派服务必须拒绝：`reviewer_user_id` 是目标工作区 `owner` 或 `admin`（客户自审）、是报告创建人、是任一 Claim 的 `owner`、或已有非 revoked 指派。C9 的 `record_review` 要求 `assignment_scope='report_review'`、`status='active'`、`assigned_at <= now`、`expires_at > now`；C10 的 `validate_review_signoff` 重新读同一行。读路径要求 `assignment_scope IN ('report_read','report_review')`、`status='active'`、`assigned_at <= now`、`expires_at > now`；无 active 行返回 403 `reviewer_assignment_required`，`expires_at <= now` 返回 403 `reviewer_assignment_expired`。审核事件 `reviewer_role` 固定 `internal_reviewer`，`reviewer_assignment_id` 必须指向该行。

`POST /api/reports/{report_id}/reviewers` 与 `DELETE /api/reports/{report_id}/reviewers/{user_id}` 是内部路径，`audience=internal`、`auth=internal`，不出现在客户文档、客户 SDK 或客户 MCP。`GET /api/reports/{report_id}/contract|artifact|sop|revisions` 在内部审核上下文下只返回被指派报告；跨报告读返回 404。

### 3.11 owner/admin 内联批准动作

`workbench_approval_actions` 只承载三类动作：`budget_overage`（预算超支）、`package_addon`（加购）、`project_key_change`（项目密钥变更）。动作绑定 `task_id`，`payload_json` 保存动作参数，`idempotency_key_hash` 保存幂等键哈希。`status` 只有 `pending`、`approved`、`rejected`、`expired`。`approver_user_id` 为空或等于 `requester_user_id` 时数据库 CHECK `ck_workbench_approval_actions_self_approval` 失败；服务层在读取后再次拒绝。

内联动作只出现在任务工作台的预算、加购与密钥面板，不建独立收件箱路由或页面。`POST /api/workbench/tasks/{task_id}/approvals` 创建 pending 动作；`POST /api/workbench/tasks/{task_id}/approvals/{approval_id}` 由 owner/admin 批准或拒绝，`requester_user_id` 不得调用 decide。C14 在任务工作台内联渲染这两个动作并只做只读验收；PG0 发布批次部署控制台。

报告审计事件类型：

```text
report_draft_created · report_review_approved · report_review_rejected ·
report_published · report_superseded · gate_evaluated ·
delivery_published · delivery_downloaded · delivery_tamper_detected ·
acceptance_snapshot_appended · delivery_superseded
```

审核事件只有一个名字：`report_review_approved`。C10 读取该事件，不得另写 `review_signed`。审核 metadata 必须包含 `contract_sha256`、`review_scope`、`reviewer_role` 与 `reviewed_contract_sha256`、`reviewed_data_sha256`、`reviewed_report_html_sha256`、`reviewed_sop_html_sha256`、`reviewed_claim_digest`。

`report_audit_events` 增加 `artifact_id uuid null`。`report_id` 改为可空。
审核签字 metadata 必须包含：`reviewer_role`、`reviewed_contract_sha256`、`reviewed_data_sha256`、`reviewed_report_html_sha256`、`reviewed_sop_html_sha256`、`reviewed_claim_digest`。

`report_shares` 与匿名公开分享标记【延期】。首期只提供项目内鉴权下载。

### 3.12 任务单创建、幂等与初始计划版本

`workbench_tasks` 是七槽位任务单的唯一事实源，不记录执行状态。除七槽位外，它保存 `package_type`（只有 `quick`、`standard`）、`primary_market`、`comparison_markets`、`acceptance_contact_id`、`max_cost_usd`、`max_pages`、`max_records`、`seed_products`、`target_price_band` 与 `idempotency_key_hash`。`status` 只有 `draft`、`submitted`、`cancelled`。`markets` 是 `[primary_market] + comparison_markets` 的七槽位投影，请求不单独提交。

`seed_products` 是 JSON 数组，非空，默认空数组。非空时必须有 3–10 项公开链接或平台 ID。`target_price_band` 是 JSON 对象，可空；非空时使用市场原币，不换算、不新增档位阈值，至少有一个边界，`min_amount <= max_amount`，金额非负，币种为三个大写字母。`target_price_band` 的精确形状：

```json
{
  "currency": "USD",
  "min_amount": "10.000000",
  "max_amount": "30.000000"
}
```

`acceptance_contact_id` 可空；空值回落到任务 `owner_id`。非空时必须是同工作区 `workspace_members` 中角色为 `owner` 或 `admin` 的成员；`member` 角色返回 422 `acceptance_contact_not_member`。复合外键 `fk_workbench_tasks_acceptance_contact_member` 保证成员存在，角色由 C2 `get_workspace_role()` 判定。

`uq_workbench_tasks_workspace_idempotency` 是创建工作区级幂等的唯一防线：

```text
(workspace_id, idempotency_key_hash) UNIQUE
WHERE idempotency_key_hash IS NOT NULL
```

`POST /api/workbench/tasks` 必须带 `Idempotency-Key` 请求头；缺失或空值返回 422 `invalid_request`。`idempotency_key_hash` 保存 `sha256("workbench-task-create.v1:{key}")`。同一工作区、同一键、同一请求摘要返回已有任务（200，响应头 `Idempotent-Replay: true`）；同一键不同摘要返回 409 `idempotency_conflict`。请求摘要由服务层对规范化请求字段计算 SHA-256，并从已持久化任务行重建同摘要；不新增第二个摘要列。任务单创建请求的精确示例：

```json
{
  "brand": "Momcozy",
  "category": "breast_pump",
  "competitors": ["Medela"],
  "package_type": "standard",
  "primary_market": "US",
  "comparison_markets": ["DE"],
  "locale_by_market": {"US": "en", "DE": "de"},
  "window": {"start": "2026-07-01", "end": "2026-09-30"},
  "decision_question": "Fit 与支撑哪个是主要摩擦？",
  "does_not_answer": ["不推断销量"],
  "seed_products": ["https://example.com/1", "https://example.com/2", "ID-3"],
  "target_price_band": {"currency": "USD", "min_amount": "10", "max_amount": "30"},
  "acceptance_contact_id": "6f0c1a5e-7d1f-4f4e-9a4e-2b0f7c9d1e21",
  "max_cost_usd": "120.50",
  "max_pages": 10,
  "max_records": 500
}
```

同一键不同摘要的错误体：

```json
{
  "detail": "idempotency_conflict",
  "error": {
    "code": "idempotency_conflict",
    "message": "Idempotency key was reused with different parameters",
    "request_id": "0123456789abcdef0123456789abcdef",
    "details": {}
  }
}
```

`workflow_versions.workbench_task_id` 是可空 UUID，用复合外键 `fk_workflow_versions_workbench_task_tenant` 指向 `workbench_tasks(workspace_id, project_id, id)`。`workflow_versions.plan_payload["execution_steps"]` 是 C4 在版本创建时写入的不可变步骤数组；每项必须含 `step_index`、`task_id`、`endpoint_type`、`collector_type`、`depends_on`，`task_id` 指向同工作区同项目的 `collection_tasks`。批准、提交、重试都不改写该数组。

`create_initial_workflow_version_for_task(session, *, workspace_id, project_id, created_by_user_id, workbench_task_id, idempotency_key) -> uuid.UUID` 是 C4 唯一的初始计划版本接缝。它只调用既有 workflow planner 的 `build_workflow_plan_result`、`create_workflow_plan`、`transition_workflow_plan_status`；已有版本时复用，不建第二个版本。计划必须是 `approved` 且 `current_version_id` 指向该版本，`submit_workbench_task` 才接受。客户 `create_task` 与 `collect` 都只调用该接缝，C13 不生成计划。

C4 的这些列、约束与索引全部由唯一迁移 `202610220062_workbench_task_submission.py` 创建，`down_revision = "202610220061"`。C1 只登记，不新增迁移号。

### 3.8 Claim 治理枚举

`claims.review_status`：`draft · pending · approved · rejected · stale`。
`claims.risk_flags`：`medical · health · safety · legal · recall · children · causal_language · single_source · price_comparison`。
`claims.blocked_reason`：`rights · permission · configuration · gate · upstream`。
`claim_evidence.role`：`support · counter · context · gap`。

`claims` 扩展列：`text_en`、`scope_window_start`、`scope_window_end`、`risk_flags`、`review_status`、`reviewed_by`、`reviewed_at`、`reviewed_content_version`、`reviewed_payload_sha256`、`reviewed_profile`、`second_reviewed_by`、`second_reviewed_at`、`review_note`、`content_version`、`independent_source_count`、`blocked_reason`、`review_history`。
`claim_evidence` 扩展列：`evidence_grade`、`source_cluster_key`、`source_cluster_basis`、`independent`。
`evidences` 扩展列：`workspace_id`、`project_id`、`evidence_grade`、`market`、`locale`、`source_tool_id`、`provider_id`、`captured_at`、`source_cluster_key`、`source_cluster_basis`。
````

- [ ] **Step 7: 在 §4 增加 canonical profile 与错误码**

插入以下内容：

````markdown
### 4.4 Canonical Profile

| 项 | 值 |
|---|---|
| `profile_id` | `dih-canonical-json-v1` |
| JSON 规则 | RFC 8785 |
| 已知偏离 | `1e-07` 格式、`-0.0`、码点排序；实现保持 `dih-canonical-json-v1`，不得静默切换 |
| 编码 | UTF-8 |
| 摘要 | SHA-256，小写十六进制，64 字符 |
| 时间 | RFC 3339 UTC，后缀 `Z` |
| 数字 | 有限值；禁止 NaN、Infinity、负零 |
| 换行 | LF |
| 摘要排除 | `excluded_top_level_keys` 为 `generated_at` 与 `artifact` 组 |
| 末尾换行 | 文件可有；摘要输入不含 |
| 唯一禁用语言画像 | `dih-descriptive-language-v1`，`profile_version=1.0.0`，单一来源 `configs/contracts/v1.1.0/forbidden_language.profile.json` |

`dih-descriptive-language-v1` 只来自已批准设计 §5.7。它禁止因果表述（导致、驱动、提升、降低、造成、证明及精确英文对应词）和销量、市场份额、转化率、营收预测；允许共同出现、相关和描述性差异。C1 导出 `FORBIDDEN_LANGUAGE_PROFILE` 与 `scan_forbidden_language()`；C9 发布前调用，C10 渲染交付文件前调用。C1、C9、C10 不得定义第二份词表或第二个画像。命中统一错码：C9 用 `report_forbidden_language`，C10 用 `delivery_input_invalid`。

`report_contract.artifact.contract_sha256` 的计算步骤：

```text
1. 复制 report_contract。
2. 删除顶层 generated_at 与 artifact 键。
3. 用 RFC 8785 规范化。
4. 对 UTF-8 字节计算 SHA-256。
5. 输出 64 位小写十六进制。
```

### 4.5 错误码

错误码以正文与附录 A 的 `error_codes` 数组为准。
客户 MCP 错误体使用 `{"detail": "<snake_case_code>"}`。
HTTP 状态必须与登记值一致。
`empty_records` 是结果码，不是错误。
`approval_required` 表示进入待批准状态，不是普通失败。
`quota_exceeded` 与 `rate_limited` 都是 429，但恢复方式不同。
`report_quality_not_ready`、`report_contract_invalid`、`report_contract_not_published`、`report_contract_hash_mismatch`、`report_artifact_not_draft`、`report_artifact_incomplete`、`report_artifact_integrity_failed`、`report_publish_gate_blocked`、`report_revision_target_invalid`、`report_forbidden_language` 属于 C9。`publish_forbidden`、`delivery_not_publishable`、`delivery_input_invalid`、`idempotency_key_required` 属于 C10。`dataset_export_internal_isolated_source` 属于 C11。`reviewer_assignment_required`、`reviewer_self_review_forbidden`、`reviewer_assignment_invalid`、`reviewer_assignment_expired` 只用于内部审核路径。`approval_not_found`、`approval_self_approval_forbidden`、`approval_state_conflict` 只用于内联批准动作。

`audit_action_unregistered` 是 C2 审计写入的拒绝码：动作不在 `audit-actions.v1` 注册表时，`append_audit_event` 抛出并阻止写入；HTTP 映射为 500。`audit_action_invalid` 是动作名形状非法的同级拒绝码。两者都不改变 `audit_events` 是唯一审计表。

### 4.6 错误信封

所有 HTTP 错误响应保留既有 `detail`，并附加 `error` 对象。字段固定为 `error.code`、`error.message`、`error.request_id`、`error.details`。请求 ID 来自 `X-Request-ID`，缺失时生成 32 位小写十六进制，并在响应头回显。

```json
{
  "detail": "project_access_forbidden",
  "error": {
    "code": "project_access_forbidden",
    "message": "Project access is forbidden",
    "request_id": "0123456789abcdef0123456789abcdef",
    "details": {}
  }
}
```

错误码以正文与附录 A 的 `error_codes` 数组为准。C2 登记 `workspace_owner_required`、`workspace_role_invalid`、`workspace_role_forbidden`、`workspace_last_owner_required`、`workspace_owner_immovable`、`project_not_found`、`project_access_forbidden`、`project_management_forbidden`、`project_member_not_found`、`project_member_exists`、`request_validation_failed`、`internal_error`。

### 4.7 公开合同投影

公开合同使用独立 profile：`dih-public-report-contract-v1`。
`schema_version` 是 `1.0.0-public`。
公开投影保留顶层 `task_id`、`report_version` 与 `delivery.report_artifact_id`；不得从 `identity.task_id` 取值。
禁止键：`provider`、`provider_id`、`endpoint_type`、`source_tool_id`、`unit_price`、`authorization_id`、`actor_id`、`approver`、`owner`、`run_ledger`。
`evidence` 使用 `source_ref`。run 信息只出现在 `run_receipt.json`。

### 4.8 保留 TTL

| 数据类 | TTL |
|---|---:|
| 原始响应 | 30 天 |
| 标准化数据集 | 12 个月（365 天） |
| 正式报告和交付包 | 24 个月（730 天） |
| 运行日志 | 180 天 |
| 安全与访问审计 | 24 个月（730 天） |
| 备份 | 30 天 |

`retention_ttl` 是保留清理的唯一原因码。保留期只能通过合同与法务流程变更。

C11 表：`workspace_pseudonym_salts`、`legal_holds`、`retention_cleanup_runs`、`retention_tombstones`。
C12 表：`deletion_requests`、`deletion_tombstones`、`deletion_subprocessor_receipts`、`deletion_proofs`、`deletion_replay_runs`、`deletion_replay_items`、`dsr_cases`、`privacy_audit_events`。
C13 不建租约表。`mcp_customer_request_leases` 在附录 A 的 `deferred` 中登记，PG0 不持久化客户 MCP 租约。
````

- [ ] **Step 8: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `57 passed`。

- [ ] **Step 9: 运行 checker**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py check --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --registry configs/contracts/v1.1.0/registry.json`

Expected: `registry check OK`。

- [ ] **Step 10: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): write v1.1 body and phase ledger"
```

---

### Task 11A: 页面路由 §5 与一级导航唯一清单

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: 附录 A 的 `page_routes` 与 `primary_nav`。
- Produces: 契约 §5 的 11 条页面路由（10 条启用、1 条禁用）与 4 条一级导航。
- Produces: C14 `contract-routes.test.ts` 逐条比较的唯一解析源；C14 解析两个 `text` 代码块得页面路由、解析一级导航表得 4 条导航，不维护第二份清单。

- [ ] **Step 1: 写失败测试**

在 `apps/api/tests/unit/test_contract_registry.py` 顶部加入 `import re`，并在文件末尾追加：

```python
SECTION_5_PATTERN = re.compile(
    r"^## 5\. 页面路由\n([\s\S]*?)^## 6\.", re.MULTILINE
)
TEXT_BLOCK_PATTERN = re.compile(r"```text\n([\s\S]*?)```")


def contract_page_route_paths() -> list[str]:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    section = SECTION_5_PATTERN.search(text)
    assert section is not None, "contract_page_routes_missing"
    values = [
        value.strip()
        for block in TEXT_BLOCK_PATTERN.findall(section.group(1))
        for value in re.split(r"[·\n]+", block)
    ]
    return [value for value in values if value.startswith("/")]


def test_contract_page_routes_match_registry() -> None:
    registry = load_contract_registry()
    assert contract_page_route_paths() == [
        route["path"] for route in registry["page_routes"]
    ]


def test_page_routes_are_exact_eleven_with_one_disabled() -> None:
    routes = load_contract_registry()["page_routes"]
    assert [route["path"] for route in routes] == [
        "/",
        "/capabilities",
        "/capabilities/[toolId]",
        "/reports/public/[id]",
        "/docs",
        "/workbench",
        "/workbench/[taskId]",
        "/reports",
        "/reports/[artifactId]",
        "/connectors",
        "/settings",
    ]
    assert len({route["path"] for route in routes}) == 11
    assert sum(1 for route in routes if route["enabled"]) == 10
    disabled = [route for route in routes if not route["enabled"]]
    assert [route["path"] for route in disabled] == ["/reports/public/[id]"]
    segments = {
        route["path"]: route.get("dynamic_segment")
        for route in routes
        if route["kind"] == "dynamic"
    }
    assert segments == {
        "/capabilities/[toolId]": "toolId",
        "/reports/public/[id]": "id",
        "/workbench/[taskId]": "taskId",
        "/reports/[artifactId]": "artifactId",
    }


def contract_primary_nav_rows() -> list[tuple[str, str]]:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    section = SECTION_5_PATTERN.search(text)
    assert section is not None, "contract_page_routes_missing"
    rows = re.findall(
        r"^\| [1-4] \| ([^|]+?) \| `([^`]+)` \|$", section.group(1), re.MULTILINE
    )
    return [(label.strip(), path) for label, path in rows]


def test_primary_navigation_is_exact_four_and_subset_of_enabled_page_routes() -> None:
    registry = load_contract_registry()
    nav = registry["primary_nav"]
    expected = [
        ("工作台", "/workbench"),
        ("报告", "/reports"),
        ("连接器", "/connectors"),
        ("设置", "/settings"),
    ]
    assert [(item["label"], item["path"]) for item in nav] == expected
    assert contract_primary_nav_rows() == expected
    enabled_routes = {
        route["path"] for route in registry["page_routes"] if route["enabled"]
    }
    assert {item["path"] for item in nav} <= enabled_routes


def test_page_routes_are_not_api_paths() -> None:
    registry = load_contract_registry()
    page_paths = {route["path"] for route in registry["page_routes"]}
    api_paths = {item["path"] for item in registry["paths"]}
    assert page_paths.isdisjoint(api_paths)
    assert all(route["path"].startswith("/api/") is False for route in registry["page_routes"])
    assert all(item["path"].startswith("/api/") is False for item in registry["primary_nav"])
    assert all(item["path"].startswith(("/api/", "/mcp/")) for item in registry["paths"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。`test_contract_page_routes_match_registry` 失败：§5 仍写 `/capabilities/[id]` 与 `/reports/[id]`，解析出的 11 条路径与 `page_routes` 不一致。

- [ ] **Step 3: 重写契约 §5 页面路由**

用以下内容替换 `## 5. 页面路由` 到 `## 6. 模块标识` 之间的全部内容：

````markdown
## 5. 页面路由

页面路由共 11 条：10 条启用、1 条禁用。页面路由不是 API 路径，不得写入 §3 的接口路径表或机器 registry 的 `paths` 数组。附录 A 的 `page_routes` 与 `primary_nav` 是本节机器投影。

公开区 5 条：

```text
/ · /capabilities · /capabilities/[toolId] · /reports/public/[id] · /docs
```

授权区 6 条：

```text
/workbench · /workbench/[taskId] · /reports · /reports/[artifactId] · /connectors · /settings
```

| # | 页面路由 | 区 | 本期状态 | 动态段 |
|---:|---|---|---|---|
| 1 | `/` | 公开 | 启用 | 无 |
| 2 | `/capabilities` | 公开 | 启用 | 无 |
| 3 | `/capabilities/[toolId]` | 公开 | 启用 | `toolId` |
| 4 | `/reports/public/[id]` | 公开 | 禁用 | `id` |
| 5 | `/docs` | 公开 | 启用 | 无 |
| 6 | `/workbench` | 授权 | 启用 | 无 |
| 7 | `/workbench/[taskId]` | 授权 | 启用 | `taskId` |
| 8 | `/reports` | 授权 | 启用 | 无 |
| 9 | `/reports/[artifactId]` | 授权 | 启用 | `artifactId` |
| 10 | `/connectors` | 授权 | 启用 | 无 |
| 11 | `/settings` | 授权 | 启用 | 无 |

动态段名固定为 `toolId`、`artifactId`、`taskId`，公开分享固定为 `id`。B5 已落地的 `[toolId]`、`[artifactId]` 页面只用于实现核对，不改变本节路径。不得写 `/capabilities/[id]` 或 `/reports/[id]`。`/reports/public/[id]` 保持禁用，不创建页面。

一级导航只有 4 条：

| 顺序 | 一级导航 | 路径 |
|---:|---|---|
| 1 | 工作台 | `/workbench` |
| 2 | 报告 | `/reports` |
| 3 | 连接器 | `/connectors` |
| 4 | 设置 | `/settings` |

`/runs`、`/assets`、`/projects`、`/tasks`、`/dashboard` 不得进入一级导航。它们是工作台或报告的下钻。C14 的 `contract-routes.test.ts` 只解析本节的两个 `text` 代码块，并与 `CONTRACT_ROUTES` 逐条比较；`PRIMARY_NAVIGATION` 测试只解析本节的一级导航表，并与 4 条导航逐条比较。C14 不得复制 `page_routes` 或 `primary_nav` 数组，也不得维护第二份路由或导航清单。
````

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `61 passed`。

- [ ] **Step 5: 运行 checker**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1 && apps/api/.venv/bin/python scripts/contract_registry.py check --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --registry configs/contracts/v1.1.0/registry.json`

Expected: `registry check OK`。

- [ ] **Step 6: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): freeze 11 page routes and four primary nav entries"
```

---

### Task 12: PRD v1.1 同步

**Files:**
- Modify: `docs/product/【PRD】母婴出海数据洞察Agent工作台.md`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: registry 的 `mcp.tools`、`error_codes`、`report_contract` 顶层键。
- Produces: PRD 与契约 v1.1 一致的客户 MCP、报告合同、账本符号和验收判据。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
PRD_PATH = (
    PROJECT_ROOT / "docs/product/【PRD】母婴出海数据洞察Agent工作台.md"
)


def test_prd_contains_eight_customer_tools() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")
    for name in [
        "discover_capabilities",
        "estimate_task",
        "create_task",
        "get_task",
        "cancel_task",
        "get_delivery_manifest",
        "get_evidence",
        "collect",
    ]:
        assert name in text


def test_prd_documents_create_task_input_contract() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")
    for fragment in [
        "seed_products",
        "target_price_band",
        "Idempotency-Key",
        "acceptance_contact_id",
        "comparison_markets",
        "idempotency_conflict",
    ]:
        assert fragment in text


def test_prd_contains_new_report_contract_groups() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")
    for key in [
        "sku_candidates",
        "scorecard",
        "rights",
        "currency",
        "language",
        "review",
        "acceptance",
        "delivery",
    ]:
        assert key in text


def test_prd_states_ledger_sign_rules() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")
    assert "settle" in text
    assert "release" in text
    assert "正数" in text
    assert "负数" in text


def test_prd_has_v11_version() -> None:
    text = PRD_PATH.read_text(encoding="utf-8")
    assert "版本：v1.1" in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。PRD 仍是 v1.0，仍是旧 18 工具清单。

- [ ] **Step 3: 更新 PRD 版本头**

把：

```markdown
> 版本：v1.0 · 2026-10-20
```

改为：

```markdown
> 版本：v1.1 · 2026-10-22
> 契约依据：[契约冻结 v1.1](../design/【契约冻结】v1-表名-枚举-接口.md)
```

- [ ] **Step 4: 更新 PRD §5.4.1 的 claim 字段**

把 claim 字段块替换为：

```text
claim
  id · task_id · market · window_start · window_end
  text · text_en
  claim_status · evidence_grade · scope{market, window{start,end,days}, sample_n}
  independent_source_count · owner_user_id · counterevidence_text · risk_flags
  review_status · reviewed_by_user_id · reviewed_at · blocked_reason

claim_evidence        （多对多）
  claim_id · evidence_id · role

evidence
  id · workspace_id · project_id · raw_record_id · url · excerpt
  source_tool_id · market · locale · evidence_grade · captured_at
  content_sha256 · source_cluster_key · rights_status · redaction_state
```

在 `role` 表后加入：

```markdown
每条 claim 必须填写 `text`。正式双语报告还必须填写 `text_en`。
`independent_source_count` 按原始记录簇计数，不按端点计数。
`risk_flags` 是 JSON 数组。允许值：`medical`、`health`、`safety`、`legal`、`recall`、`children`、`causal_language`、`single_source`、`price_comparison`。
`review_status` 允许值：`draft`、`pending`、`approved`、`rejected`、`stale`。
```

- [ ] **Step 5: 更新 PRD §5.5.1 的报告合同顶层键**

把 JSON 顶层示例替换为：

```json
{
  "schema_version": "1.1.0",
  "contract_id": "uuid",
  "task_id": "uuid",
  "order_id": "uuid",
  "template_id": "t1_voc",
  "template_version": "1.0.0",
  "report_version": 1,
  "generated_at": "ISO-8601 UTC",
  "identity": {},
  "decision": {},
  "gates": [],
  "coverage": {},
  "markets": [],
  "metrics": [],
  "claims": [],
  "evidences": [],
  "sku_candidates": [],
  "datasets": [],
  "scorecard": {},
  "rights": {},
  "currency": {},
  "language": {},
  "run_ledger": [],
  "limits": [],
  "unknowns": [],
  "review": {},
  "acceptance": {},
  "delivery": {},
  "artifact": {}
}
```

在合同字段表后加入：

```markdown
`markets[]` 每个元素必须包含 `market`、`market_role`、`quality_status`、`evidence_grade`、`domains`、`gaps`。
`sku_candidates[]` 只允许 Standard 输出。少于 3 个候选时不得输出 `enter`。
`datasets[]` 每个元素必须包含 `dataset_version_id`、`market`、`row_count`、`content_sha256`、`schema_hash`。
`review` 必须包含审核人、审核范围、审核时间、审核版本和合同哈希。
`acceptance` 必须包含验收状态、窗口起止和验收快照。
`delivery` 必须包含 `manifest_id`、访问范围和保留类别。
```

- [ ] **Step 6: 更新 PRD §5.6 的账本符号**

在 §5.6.2 的规则列表后加入：

```markdown
`run_ledger_entries.entry_kind` 只有六值：`estimate`、`reserve`、`accrued`、`settle`、`release`、`block`。

- `settle` 必须是正数实际成本。
- `release` 必须是负数修正。
- `estimate`、`reserve`、`accrued`、`block` 不计入实际成本。
- 实际成本公式：`SUM(amount_usd) WHERE entry_kind IN ('settle','release')`。
- 剩余额度公式：`max_cost_usd - 实际成本`。允许为负，不得截断为零。
```

- [ ] **Step 7: 更新 PRD §5.7 的客户 MCP**

把 §5.7 的“现有 MCP 有 13 个工具”到“工具 | 状态 | 说明”整表替换为：

```markdown
客户 MCP 只有八个稳定工具。路径是 `/mcp/customer`。
内部端点级工具继续存在，但不得出现在客户 `tools/list`、客户文档和客户 SDK。

| 工具 | 只读 | 用途 |
|---|---:|---|
| `discover_capabilities` | 是 | 按自然语言、市场、数据域发现模板白名单能力 |
| `estimate_task` | 是 | 返回任务包报价、价格簿版本和有效期 |
| `create_task` | 否 | 幂等创建任务包订单 |
| `get_task` | 是 | 读取任务、市场、run 和 gap 状态 |
| `cancel_task` | 否 | 取消允许取消的任务 |
| `get_delivery_manifest` | 是 | 读取交付 manifest 与文件哈希 |
| `get_evidence` | 是 | 读取 Claim 绑定证据 |
| `collect` | 否 | 用 `capability_id` 创建受治理 run |

客户 `collect` 只接受模板白名单内的 `capability_id`。
客户 `collect` 不接受 `endpoint_type`、Cookie、Seller Center 登录态、provider 名称或原始端点。

`create_task` 输入与 C4 `WorkbenchTaskCreateRequest` 的映射固定如下：

- `idempotency_key` 对应 `Idempotency-Key` 请求头；头必填，空白返回 422 `invalid_request`。同一工作区、同一键、同一请求摘要返回已有任务；同一键不同摘要返回 409 `idempotency_conflict`。
- `compare_markets` 映射到 `workbench_tasks.comparison_markets`；Quick 最多 1 个，Standard 最多 3 个；不得包含 `primary_market`，不得重复。
- `budget.max_cost_usd`、`budget.max_pages`、`budget.max_records` 分别映射到同名列；非空不得为负。
- `seed_products` 可省略或为空数组；非空时必须有 3–10 项公开链接或平台 ID。
- `target_price_band` 可空；非空时使用市场原币，至少一个边界，`min_amount <= max_amount`，金额非负，币种三个大写字母。
- `acceptance_contact_id` 必须是同工作区 `owner` 或 `admin`；空值回落到任务 `owner_id`；`member` 返回 422 `acceptance_contact_not_member`。
```

把验收判据替换为：

```markdown
- 客户 `tools/list` 只返回八个工具。工具数量快照固定为 8。
- 一个外部 Agent 只读客户 MCP 文档，能完成 discover → estimate → create → get → delivery。
- 白名单外工具返回 403 `tool_not_allowed`。
- 白名单外能力返回 403 `capability_not_allowed`。
- 客户链出现 `creator_cookie` 的次数为 0。
- 超额度返回 429 `quota_exceeded`。
- 不同项目不能互读任务、Claim、证据和交付。
```

- [ ] **Step 8: 在 PRD §12 增加 C1 契约验收**

在 §12 末尾加入：

```markdown
### 12.5 契约 v1.1

| # | 判据 | 命令或位置 |
|---|---|---|
| C1-1 | 契约附录 A 可提取为 registry | `python scripts/contract_registry.py build` |
| C1-2 | 生成物与 Markdown 一致 | `python scripts/contract_registry.py check` |
| C1-3 | 客户 MCP 工具数固定为 8 | `apps/api/tests/unit/test_contract_registry.py::test_customer_mcp_has_exactly_eight_named_tools` |
| C1-4 | 每个 column 的 enum 引用可解析 | `apps/api/tests/unit/test_contract_registry.py::test_every_column_enum_reference_resolves` |
| C1-5 | 正文、PRD、Playbook 无废弃名 | `python scripts/contract_registry.py check-docs` |
```

- [ ] **Step 9: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `66 passed`。

- [ ] **Step 10: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/product/【PRD】母婴出海数据洞察Agent工作台.md" apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(prd): sync customer MCP and report contract v1.1"
```

---

### Task 13: Playbook v1.1 同步

**Files:**
- Modify: `docs/product/【Playbook】母婴出海洞察交付.md`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: registry 的 `data_domains`、`domain_status`、`market_quality_status`、`data_gaps.severity`、`entry_kind`。
- Produces: Playbook 的市场质量、缺口、刷新可比性和账本符号说明。

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
PLAYBOOK_PATH = (
    PROJECT_ROOT / "docs/product/【Playbook】母婴出海洞察交付.md"
)


def test_playbook_has_v11_version() -> None:
    text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    assert "版本：v1.1" in text


def test_playbook_contains_market_quality_states() -> None:
    text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    for value in ["qualified", "qualified_with_gap", "not_qualified"]:
        assert value in text


def test_playbook_contains_domain_statuses_and_gap_fields() -> None:
    text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    for value in ["pass", "partial", "missing", "blocked"]:
        assert value in text
    for field in ["reason_code", "customer_text_zh", "remediation", "severity"]:
        assert field in text


def test_playbook_contains_refresh_comparability_states() -> None:
    text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    for value in [
        "comparable",
        "comparable_with_caveats",
        "not_comparable",
        "failed",
    ]:
        assert value in text


def test_playbook_states_ledger_sign_rules() -> None:
    text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    assert "settle" in text
    assert "release" in text
    assert "正数" in text
    assert "负数" in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。Playbook 仍是 v1.0，没有市场质量三态和可比性四态。

- [ ] **Step 3: 更新 Playbook 版本头**

把：

```markdown
> 版本：v1.0 · 2026-10-20
```

改为：

```markdown
> 版本：v1.1 · 2026-10-22
> 契约依据：[契约冻结 v1.1](../design/【契约冻结】v1-表名-枚举-接口.md)
```

- [ ] **Step 4: 在 Playbook §1.4 增加数据域状态与 gap 字段**

在“健康度与运行结果分开记录”段后加入：

```markdown
数据域状态只有四值：

| 状态 | 含义 |
|---|---|
| `pass` | 达到门槛 |
| `partial` | 有数据，但低于门槛 |
| `missing` | 没有合格记录 |
| `blocked` | 市场、权限、配置、条款或上游阻断 |

`missing` 不得写成数值 0。
`blocked` 不得写成空结果。
真实空结果不得解释为“市场没有需求”。

每个 gap 必须写以下字段：

| 字段 | 说明 |
|---|---|
| `market` | 市场 |
| `data_domain` | 数据域 |
| `reason_code` | 原因码 |
| `actual_value` | 实际值 |
| `threshold_value` | 门槛值 |
| `impact` | 对结论的影响 |
| `customer_text_zh` | 客户可见中文说明 |
| `customer_text_en` | 客户可见英文说明 |
| `remediation` | 补救方式 |
| `severity` | `info`、`warning`、`blocking`、`critical` |
```

- [ ] **Step 5: 在 Playbook §1.5 增加 L4 许可边界**

在证据等级表后加入：

```markdown
`L4_authorized_live` 只表示内部执行批准和数据门槛达标。
它不表示 TikTok、TikHub 或其他平台授权。
它不表示法律许可、隐私合规认证或转售权。
没有上游书面商业许可时，不向客户交付上游派生结果。
取得书面许可不会自动提升证据等级。
```

- [ ] **Step 6: 在 Playbook §1 增加市场质量与刷新可比性**

插入以下章节：

````markdown
### 1.7 市场质量状态与结论

市场质量状态只有三值：

| 状态 | 条件 | Standard 允许结论 | Quick 允许标签 |
|---|---|---|---|
| `qualified` | 核心门槛全部通过，无关键缺口 | `enter`、`conditional_enter`、`do_not_enter` | `worth_validating`、`deprioritize`、`key_risk`、`recommend_standard_scope` |
| `qualified_with_gap` | 核心门槛通过，但增强域或关键辅助证据有缺口 | `conditional_enter`、`insufficient_evidence` | `recommend_standard_scope`、`key_risk`、`evidence_gap` |
| `not_qualified` | 任一核心门槛失败 | 只允许 `insufficient_evidence` | 只允许 `evidence_gap` |

Standard 四态：`enter`、`conditional_enter`、`do_not_enter`、`insufficient_evidence`。
Quick 标签：`worth_validating`、`deprioritize`、`key_risk`、`evidence_gap`、`recommend_standard_scope`。
Quick 不使用四态。所有 Quick 标签必须标记为方向性。

### 1.8 刷新可比性

刷新可比状态只有四值：

| 状态 | 含义 |
|---|---|
| `comparable` | 模板、市场角色、时间窗、指标、计数、编码、汇率、盐值和来源组合兼容 |
| `comparable_with_caveats` | 存在已披露的等价替换或小差异 |
| `not_comparable` | 关键口径变化，不能计算跨期变化 |
| `failed` | 刷新失败，保留旧版本并标 `stale` |

来源变化不得平滑成连续趋势。必要时建立新基线。

### 1.9 成本账本符号

`run_ledger_entries.entry_kind` 只有六值：`estimate`、`reserve`、`accrued`、`settle`、`release`、`block`。

- `settle` 必须是正数实际成本。
- `release` 必须是负数修正。
- `estimate`、`reserve`、`accrued`、`block` 不计入实际成本。
- 实际成本 = `SUM(amount_usd) WHERE entry_kind IN ('settle','release')`。
- 剩余额度 = `max_cost_usd - 实际成本`。允许为负，不得截断为零。
````

- [ ] **Step 7: 更新 Playbook §8 失败处理**

在失败处理表后加入：

```markdown
补充失败码：

| 失败码 | 含义 | 运行结果 | 报告写法 |
|---|---|---|---|
| `tool_not_executable` | 工具不可执行 | 不分派 | 披露工具状态与替代来源 |
| `tool_not_priced` | 工具没有价格 | 不报价、不执行 | 披露价格簿缺口 |
| `market_unsupported` | 市场不在正式支持目录 | 写 blocked gate 和 gap | 不承诺该市场交付 |
| `insufficient_evidence` | 证据不足 | 有效交付结果 | 输出证据不足，不自动重跑 |
| `cookie_not_accepted` | 客户链收到 Cookie | 拒绝执行 | 披露客户链禁止 Cookie |
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `71 passed`。

- [ ] **Step 9: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/product/【Playbook】母婴出海洞察交付.md" apps/api/tests/unit/test_contract_registry.py
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(playbook): sync quality gaps and comparability v1.1"
```

---

### Task 14: 文档完整性 Checker

**Files:**
- Modify: `scripts/contract_registry.py`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Test: `apps/api/tests/unit/test_contract_registry.py`

**Interfaces:**
- Consumes: `contract_registry.extract_registry_block`、`check_json_schema_refs`。
- Produces: `check_documents(contract: Path, prd: Path, playbook: Path, registry: dict[str, Any]) -> list[str]`
- Produces: `check_relative_links(document: Path, text: str) -> list[str]`
- Produces: CLI `check-docs --contract --prd --playbook --registry`

- [ ] **Step 1: 写失败测试**

Append to `apps/api/tests/unit/test_contract_registry.py`:

```python
def test_docs_checker_accepts_real_documents() -> None:
    module = load_module()
    registry = load_contract_registry()
    assert module.check_documents(CONTRACT_PATH, PRD_PATH, PLAYBOOK_PATH, registry) == []


def test_docs_checker_detects_missing_mcp_tool(tmp_path: Path) -> None:
    module = load_module()
    registry = load_contract_registry()
    prd = tmp_path / "prd.md"
    text = PRD_PATH.read_text(encoding="utf-8").replace("collect", "gather")
    prd.write_text(text, encoding="utf-8")
    errors = module.check_documents(CONTRACT_PATH, prd, PLAYBOOK_PATH, registry)
    assert "prd_missing_mcp_tool:collect" in errors


def test_docs_checker_detects_banned_name(tmp_path: Path) -> None:
    module = load_module()
    registry = load_contract_registry()
    prd = tmp_path / "prd.md"
    prd.write_text(
        PRD_PATH.read_text(encoding="utf-8") + "\nautomation_runs\n",
        encoding="utf-8",
    )
    errors = module.check_documents(CONTRACT_PATH, prd, PLAYBOOK_PATH, registry)
    assert "banned_name:prd:automation_runs" in errors


def test_docs_checker_detects_missing_idempotency_header(tmp_path: Path) -> None:
    module = load_module()
    registry = load_contract_registry()
    contract = tmp_path / "contract.md"
    contract.write_text(
        CONTRACT_PATH.read_text(encoding="utf-8").replace(
            "Idempotency-Key", "IdempotencyKey"
        ),
        encoding="utf-8",
    )
    errors = module.check_documents(contract, PRD_PATH, PLAYBOOK_PATH, registry)
    assert "contract_missing_idempotency_header:workbench.tasks.create" in errors


def test_relative_link_checker_detects_missing_target(tmp_path: Path) -> None:
    module = load_module()
    doc = tmp_path / "doc.md"
    text = "[missing](./missing.md)\n"
    doc.write_text(text, encoding="utf-8")
    errors = module.check_relative_links(doc, text)
    assert errors == ["broken_link:doc.md:./missing.md"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: FAIL。`check_documents` 与 `check_relative_links` 未定义。

- [ ] **Step 3: 在 `scripts/contract_registry.py` 加入文档检查**

在 `canonical_dump` 后加入：

```python
BANNED_NAMES = (
    "automation_runs",
    "automation_steps",
    "automation_cost_ledger",
    "automation_authorizations",
    "automation_gate_evaluations",
    "task_orders",
    "task_plans",
    "task_gates",
    "task_order_runs",
    "tool_catalog_revisions",
    "cost_ledger_entries",
    "tool_catalog_snapshots",
    "evidence_grade_cap",
    "remaining_budget_usd",
)

LINK_PATTERN = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")

REQUIRED_PLAYBOOK_FRAGMENTS = (
    "success",
    "empty",
    "config_gated",
    "failed",
    "L0_unverified",
    "L1_contract",
    "L2_fixture_local",
    "L3_live_single",
    "L4_authorized_live",
    "confirmed",
    "directional",
    "hypothesis",
    "evidence_gap",
    "blocked",
    "qualified",
    "qualified_with_gap",
    "not_qualified",
    "pass",
    "partial",
    "missing",
    "comparable",
    "comparable_with_caveats",
    "not_comparable",
    "settle",
    "release",
)


def check_relative_links(document: Path, text: str) -> list[str]:
    errors: list[str] = []
    for match in LINK_PATTERN.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith("#"):
            continue
        if "://" in target or target.startswith("mailto:"):
            continue
        resolved = (document.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"broken_link:{document.name}:{target}")
    return errors


def check_documents(
    contract: Path,
    prd: Path,
    playbook: Path,
    registry: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    contract_text = contract.read_text(encoding="utf-8")
    prd_text = prd.read_text(encoding="utf-8")
    playbook_text = playbook.read_text(encoding="utf-8")

    for table in registry.get("tables", []):
        name = str(table["name"])
        if name not in contract_text:
            errors.append(f"contract_missing_table:{name}")
    for enum in registry.get("enums", []):
        name = str(enum["name"])
        if name not in contract_text:
            errors.append(f"contract_missing_enum:{name}")
        for value in enum.get("values", []):
            if str(value) not in contract_text:
                errors.append(f"contract_missing_enum_value:{name}:{value}")
    for path in registry.get("paths", []):
        if str(path["path"]) not in contract_text:
            errors.append(f"contract_missing_path:{path['path']}")
        idempotency = path.get("idempotency")
        if isinstance(idempotency, dict):
            header = str(idempotency.get("header", ""))
            if header and header not in contract_text:
                errors.append(f"contract_missing_idempotency_header:{path['id']}")
            conflict = str(idempotency.get("conflict_error", ""))
            if conflict and conflict not in contract_text:
                errors.append(f"contract_missing_idempotency_conflict:{path['id']}")
    for tool in registry.get("mcp", {}).get("tools", []):
        name = str(tool["name"])
        if name not in contract_text:
            errors.append(f"contract_missing_mcp_tool:{name}")
        if name not in prd_text:
            errors.append(f"prd_missing_mcp_tool:{name}")
    for error in registry.get("error_codes", []):
        code = str(error["code"])
        if code not in contract_text:
            errors.append(f"contract_missing_error_code:{code}")
    for action in registry.get("audit_actions", {}).get("actions", []):
        name = str(action["name"])
        if name not in contract_text:
            errors.append(f"contract_missing_audit_action:{name}")

    for key in [
        "sku_candidates",
        "scorecard",
        "rights",
        "currency",
        "language",
        "review",
        "acceptance",
        "delivery",
    ]:
        if key not in prd_text:
            errors.append(f"prd_missing_report_group:{key}")

    for fragment in REQUIRED_PLAYBOOK_FRAGMENTS:
        if fragment not in playbook_text:
            errors.append(f"playbook_missing_fragment:{fragment}")

    for label, text in (
        ("contract", contract_text),
        ("prd", prd_text),
        ("playbook", playbook_text),
    ):
        for line in text.splitlines():
            if any(marker in line for marker in ("废弃", "不得", "禁止", "不建", "不写")):
                continue
            for banned in BANNED_NAMES:
                if banned in line:
                    errors.append(f"banned_name:{label}:{banned}")

    errors.extend(check_relative_links(contract, contract_text))
    errors.extend(check_relative_links(prd, prd_text))
    errors.extend(check_relative_links(playbook, playbook_text))
    return errors
```

- [ ] **Step 4: 加入 CLI `check-docs`**

在 `main` 的 `check_parser` 后加入：

```python
    docs_parser = subparsers.add_parser("check-docs")
    docs_parser.add_argument("--contract", type=Path, required=True)
    docs_parser.add_argument("--prd", type=Path, required=True)
    docs_parser.add_argument("--playbook", type=Path, required=True)
    docs_parser.add_argument("--registry", type=Path, required=True)
```

在 `main` 的分支中加入：

```python
    if args.command == "check-docs":
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        errors = check_documents(args.contract, args.prd, args.playbook, registry)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("document check OK")
        return 0
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py -q`

Expected: `76 passed`。

- [ ] **Step 6: 运行完整文档检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py check-docs \
  --contract "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --prd "docs/product/【PRD】母婴出海数据洞察Agent工作台.md" \
  --playbook "docs/product/【Playbook】母婴出海洞察交付.md" \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: `document check OK`。若失败，按错误码补齐对应文档，不删除检查项。

- [ ] **Step 7: 运行 ruff**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/ruff check ../scripts/contract_registry.py tests/unit/test_contract_registry.py`

Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add scripts/contract_registry.py apps/api/tests/unit/test_contract_registry.py configs/contracts/v1.1.0/registry.json
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "feat(contract): add document completeness checker"
```

---

### Task 14A: 修复前置登记（C6 取消幂等、C8 模板能力、C9 Quick 稿、C10 验收、PII 发布）

**Files:**
- Modify: `docs/design/【契约冻结】v1-表名-枚举-接口.md`
- Modify: `configs/contracts/v1.1.0/registry.schema.json`
- Modify: `configs/contracts/v1.1.0/registry.json`
- Create: `configs/contracts/v1.1.0/template_capability_profile.schema.json`
- Modify: `scripts/contract_registry.py`
- Create: `apps/api/tests/unit/test_contract_repair_prerequisites.py`
- Create: `apps/api/tests/fixtures/contract_registry/golden/repair_prerequisites.json`
- Create: `apps/api/tests/fixtures/contract_registry/golden/cancel_replay.json`
- Create: `apps/api/tests/fixtures/contract_registry/golden/quick_draft_artifact.json`
- Create: `apps/api/tests/fixtures/contract_registry/golden/acceptance_events.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/repair_quick_draft_confirmed.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/repair_quick_draft_acceptance.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/repair_acceptance_early_deemed.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/repair_cancel_reason_conflict.json`
- Create: `apps/api/tests/fixtures/contract_registry/negative/repair_pii_second_profile.json`

**Interfaces:**
- Consumes: Task 1–14、Task 11A 与 Task 14A 之前的 registry、schema 与 checker；C6 最新取消幂等前置；C8 最新模板能力白名单前置；C9 最新 Quick 2 小时方向稿前置；C10 最新 §0.4 合同登记门禁与验收决策；C11 最新导出策略前置。
- Produces: `check_repair_prerequisites(registry) -> list[str]`。
- Produces: `check_cancel_request(value, stored) -> list[str]`。
- Produces: `check_quick_draft_artifact(artifact, contract) -> list[str]`。
- Produces: `check_acceptance_event_sequence(events, *, deadline, now) -> list[str]`。
- Produces: CLI `check-repairs --registry <path>`。
- Produces: 契约正文 §2.13-§2.17 与附录 A 的修复前置对象。
- Boundary: C1 不新增迁移。C6 取消幂等列只在 `202610220064`；C9 报告生命周期只在 `202610220067`；C10 交付类别与验收字段只在 `202610220068`。不得新增取消表、验收表、模板能力表或第二套 PII 规则。

- [ ] **Step 0: 复核最新下游计划的前置原文**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
rg -n "cancel_idempotency_key_hash|uq_runs_workspace_cancel_idempotency|cancel_task_runs" /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c6-run-execution-convergence.md /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c13-customer-mcp.md
rg -n "template_capability_ids|template_registry_digest|capability_not_allowed" /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c8-dataset-quality-template.md /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c13-customer-mcp.md
rg -n "Quick 2 小时方向稿|acceptance_accepted|acceptance_disputed|acceptance_deemed_accepted|delivery_pii_detected|quick_draft_not_allowed" /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c9-report-contract-artifacts.md /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c10-delivery-manifest-publish.md
rg -n "EXPORT_POLICY_VERSION|scan_export_policy|scan_export_value|export_policy.v1" /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c10-delivery-manifest-publish.md /Users/lute/Project/data_scrapy/docs/superpowers/plans/2026-10-22-governed-task-platform-c11-pseudonymization-retention.md
```

Expected: 每条都有命中。若 C6 仍要求 `cancel_idempotency_key_hash` 之外的列名，或 C8/C13 对字段名不一致，停止本任务，先统一字段名为 `TaskTemplate.capability_allowlist`、读取入口为 `template_capability_ids(template_id)`。不得在 C1 登记两个同义字段，也不得在 C13 写第二套取消实现。

- [ ] **Step 1: 写失败测试**

Create `apps/api/tests/unit/test_contract_repair_prerequisites.py`:

```python
"""C1：C6/C8/C9/C10 修复前置登记守卫。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = PROJECT_ROOT / "configs/contracts/v1.1.0/registry.json"
SCRIPT_PATH = PROJECT_ROOT / "scripts/contract_registry.py"
GOLDEN_DIR = PROJECT_ROOT / "apps/api/tests/fixtures/contract_registry/golden"
NEGATIVE_DIR = PROJECT_ROOT / "apps/api/tests/fixtures/contract_registry/negative"


def load_module():
    spec = importlib.util.spec_from_file_location("contract_registry_repair", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def table(registry: dict, name: str) -> dict:
    return next(item for item in registry["tables"] if item["name"] == name)


def path(registry: dict, path_id: str) -> dict:
    return next(item for item in registry["paths"] if item["id"] == path_id)


def error(registry: dict, code: str) -> dict:
    return next(item for item in registry["error_codes"] if item["code"] == code)


def golden(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def test_runs_cancel_idempotency_is_registered() -> None:
    registry = load_registry()
    runs = table(registry, "runs")
    columns = {column["name"]: column for column in runs["columns"]}
    assert columns["cancel_idempotency_key_hash"]["type"] == "string(64)"
    assert columns["cancel_idempotency_key_hash"]["nullable"] is True
    assert columns["cancel_idempotency_key_hash"]["phase"] == "C6"
    assert columns["cancel_reason_code"]["type"] == "string(80)"
    assert columns["cancel_reason_code"]["nullable"] is True
    assert columns["cancel_reason_code"]["phase"] == "C6"
    indexes = {index["name"]: index for index in runs["indexes"]}
    assert indexes["uq_runs_workspace_cancel_idempotency"] == {
        "name": "uq_runs_workspace_cancel_idempotency",
        "columns": ["workspace_id", "cancel_idempotency_key_hash"],
        "unique": True,
        "where": "cancel_idempotency_key_hash IS NOT NULL",
    }
    assert indexes["uq_runs_workspace_idempotency"]["columns"] == [
        "workspace_id",
        "idempotency_key_hash",
    ]
    cancel = path(registry, "runs.cancel")
    assert (cancel["method"], cancel["path"]) == ("POST", "/api/runs/{run_id}/cancel")
    assert cancel["idempotent"] is True
    assert {"run_not_found", "state_conflict", "invalid_request", "idempotency_conflict"} <= set(
        cancel["error_codes"]
    )


def test_run_lifecycle_audit_actions_are_registered() -> None:
    actions = {item["name"]: item for item in load_registry()["audit_actions"]["actions"]}
    for name in (
        "run.cancel_requested",
        "run.retry_scheduled",
        "run.retry_exhausted",
        "run.failed",
    ):
        assert name in actions
        assert actions[name]["owner"] == "C6"
    assert "run.created" in actions
    assert actions["run.created"]["owner"] == "C4"
    assert "run.cancelled" in actions
    assert "run.completed" in actions


def test_template_capability_profile_is_code_registry_not_table() -> None:
    registry = load_registry()
    profiles = registry["capability_profiles"]
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile["profile_id"] == "dih-template-capability-v1"
    assert profile["entrypoint"] == "template_capability_ids"
    assert profile["digest_function"] == "template_registry_digest"
    assert profile["digest_profile"] == "dih-canonical-json-v1"
    assert profile["empty_allowlist_policy"] == "deny_all"
    assert profile["unknown_template"] == "KeyError"
    assert profile["storage"] == "code_registry_not_table"
    assert {"tikhub_tiktok_video_products", "tikhub_tiktok_creator_showcase"} <= set(
        profile["excluded_capability_ids"]
    )
    assert profile["schema_path"] == (
        "configs/contracts/v1.1.0/template_capability_profile.schema.json"
    )
    table_names = {item["name"] for item in registry["tables"]}
    assert table_names.isdisjoint(
        {"task_templates", "template_capability_profiles", "template_capability_allowlist"}
    )
    capability = error(registry, "capability_not_allowed")
    assert capability["http_status"] == 403
    assert "capability_allowlist" in capability["meaning"]
    assert "TaskTemplate.capability_allowlist" in capability["meaning"]
    schema = next(
        item for item in registry["schemas"] if item["id"] == "template_capability_profile"
    )
    assert schema["kind"] == "template_capability_profile"


def test_quick_draft_representation_is_registered() -> None:
    registry = load_registry()
    artifacts = table(registry, "report_artifacts")
    columns = {column["name"]: column for column in artifacts["columns"]}
    assert columns["delivery_class"]["enum"] == "report_artifacts.delivery_class"
    assert columns["delivery_class"]["default"] == "formal"
    assert columns["acceptance_deadline"]["nullable"] is True
    assert columns["quick_draft_of_artifact_id"]["nullable"] is True
    assert columns["quick_draft_of_artifact_id"]["references"] == "report_artifacts.id"
    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert enums["report_artifacts.delivery_class"] == ["formal", "quick_draft"]
    assert {"ck_report_artifacts_delivery_class", "ck_report_artifacts_delivery_fields"} <= set(
        artifacts["constraints"]
    )
    module = load_module()
    fixture = golden("quick_draft_artifact.json")
    assert module.check_quick_draft_artifact(fixture["artifact"], fixture["contract"]) == []


def test_acceptance_events_paths_and_status_mapping_are_registered() -> None:
    registry = load_registry()
    enums = {item["name"]: item["values"] for item in registry["enums"]}
    event_values = enums["report_audit_events.event_type"]
    for event_type in (
        "acceptance_accepted",
        "acceptance_disputed",
        "acceptance_deemed_accepted",
        "delivery_pii_detected",
    ):
        assert event_type in event_values
    expected_paths = {
        "delivery.acceptance.accept": "/api/reports/{artifact_id}/delivery/acceptance/accept",
        "delivery.acceptance.dispute": "/api/reports/{artifact_id}/delivery/acceptance/dispute",
        "delivery.acceptance.deemed_accept": "/api/reports/{artifact_id}/delivery/acceptance/deemed-accepted",
        "delivery.acceptance.read": "/api/reports/{artifact_id}/delivery/acceptance",
    }
    for path_id, expected_path in expected_paths.items():
        item = path(registry, path_id)
        assert item["path"] == expected_path
        if item["method"] == "POST":
            assert item["idempotent"] is True
            assert item["idempotency"]["header"] == "Idempotency-Key"
            assert item["idempotency"]["required"] is True
            assert item["idempotency"]["conflict_error"] == "idempotency_conflict"
    statuses = {
        "acceptance_window_open": 409,
        "acceptance_already_closed": 409,
        "acceptance_reference_invalid": 422,
        "acceptance_not_applicable": 409,
    }
    for code, expected_status in statuses.items():
        assert error(registry, code)["http_status"] == expected_status
    module = load_module()
    fixture = golden("acceptance_events.json")
    assert module.check_acceptance_event_sequence(
        fixture["accepted"], deadline=fixture["deadline"], now=fixture["now_before"]
    ) == []
    assert module.check_acceptance_event_sequence(
        fixture["deemed"], deadline=fixture["deadline"], now=fixture["now_after"]
    ) == []


def test_pii_publication_failure_reuses_single_c11_profile() -> None:
    registry = load_registry()
    pii = registry["canonical_profile"]["pii_scan"]
    assert pii["profile_id"] == "export_policy.v1"
    assert pii["module"] == (
        "apps/api/src/data_intelligence_hub/services/export_policy.py"
    )
    assert pii["scanner"] == "scan_export_policy"
    assert pii["finding_type"] == "PiiHit"
    assert pii["value_scanner"] == "scan_export_value"
    assert pii["finding_codes"] == [
        "contact",
        "profile_link",
        "avatar",
        "tracking",
    ]
    assert pii["c9_error"] == "report_publish_gate_blocked"
    assert pii["c10_error"] == "delivery_pii_detected"
    assert pii["shared_by"] == ["C9", "C10"]
    assert pii["no_second_ruleset"] is True
    assert "pii_profiles" not in registry
    assert error(registry, "delivery_pii_detected")["http_status"] == 409
    assert "report_publish_gate_blocked" in path(registry, "reports.publish")["error_codes"]
    assert "delivery_pii_detected" in path(registry, "delivery.publish")["error_codes"]
    assert "delivery_pii_detected" in path(registry, "delivery.download")["error_codes"]
    action_names = {item["name"] for item in registry["audit_actions"]["actions"]}
    assert all(not name.startswith("delivery.pii.") for name in action_names)


def test_cancel_replay_and_conflict_golden() -> None:
    module = load_module()
    fixture = golden("cancel_replay.json")
    assert module.check_cancel_request(
        fixture["new_request"], fixture["stored_after_first"]
    ) == []
    assert module.check_cancel_request(
        fixture["replay_request"], fixture["stored_after_first"]
    ) == []
    assert module.check_cancel_request(
        fixture["conflict_request"], fixture["stored_after_first"]
    ) == ["idempotency_conflict"]


def test_repair_negative_fixtures_are_rejected() -> None:
    module = load_module()
    quick = golden("quick_draft_artifact.json")
    acceptance = golden("acceptance_events.json")
    cancel = golden("cancel_replay.json")
    checked: set[str] = set()
    for fixture_path in sorted(NEGATIVE_DIR.glob("repair_*.json")):
        mutation = json.loads(fixture_path.read_text(encoding="utf-8"))["mutation"]
        checked.add(mutation)
        if mutation == "repair_quick_draft_confirmed":
            bad = json.loads(json.dumps(quick))
            bad["contract"]["claims"][0]["status"] = "confirmed"
            errors = module.check_quick_draft_artifact(
                bad["artifact"], bad["contract"]
            )
            assert "quick_draft_confirmed_forbidden" in errors, mutation
        elif mutation == "repair_quick_draft_acceptance":
            bad = json.loads(json.dumps(quick))
            bad["artifact"]["acceptance_events"] = [
                {"event_type": "acceptance_accepted"}
            ]
            errors = module.check_quick_draft_artifact(
                bad["artifact"], bad["contract"]
            )
            assert "quick_draft_acceptance_forbidden" in errors, mutation
        elif mutation == "repair_acceptance_early_deemed":
            bad_events = json.loads(json.dumps(acceptance["deemed"]))
            bad_events[0]["recorded_at"] = acceptance["now_before"]
            errors = module.check_acceptance_event_sequence(
                bad_events,
                deadline=acceptance["deadline"],
                now=acceptance["now_before"],
            )
            assert "acceptance_deemed_accepted_before_deadline" in errors, mutation
        elif mutation == "repair_cancel_reason_conflict":
            errors = module.check_cancel_request(
                cancel["conflict_request"], cancel["stored_after_first"]
            )
            assert "idempotency_conflict" in errors, mutation
        elif mutation == "repair_pii_second_profile":
            registry = load_registry()
            registry["pii_profiles"] = [{"profile_id": "export_policy.v2"}]
            assert "pii_scan_profile_duplicated" in (
                module.check_repair_prerequisites(registry)
            ), mutation
        else:
            raise AssertionError(f"unknown repair mutation: {mutation}")
    assert checked == {
        "repair_quick_draft_confirmed",
        "repair_quick_draft_acceptance",
        "repair_acceptance_early_deemed",
        "repair_cancel_reason_conflict",
        "repair_pii_second_profile",
    }


def test_golden_repair_prerequisites_match_registry() -> None:
    registry = load_registry()
    fixture = golden("repair_prerequisites.json")
    runs = table(registry, "runs")
    assert set(fixture["runs_columns"]) <= {
        column["name"] for column in runs["columns"]
    }
    artifacts = table(registry, "report_artifacts")
    assert set(fixture["report_artifacts_columns"]) <= {
        column["name"] for column in artifacts["columns"]
    }
    enums = {item["name"]: item["values"] for item in registry["enums"]}
    assert set(fixture["acceptance_event_types"]) <= set(
        enums["report_audit_events.event_type"]
    )
    assert set(fixture["run_audit_actions"]) <= {
        item["name"] for item in registry["audit_actions"]["actions"]
    }
    assert fixture["capability_profile_id"] == registry["capability_profiles"][0][
        "profile_id"
    ]
    assert fixture["pii_scan_profile_id"] == registry["canonical_profile"]["pii_scan"][
        "profile_id"
    ]


def test_page_route_registration_is_preserved() -> None:
    registry = load_registry()
    assert [item["path"] for item in registry["page_routes"]] == [
        "/",
        "/capabilities",
        "/capabilities/[toolId]",
        "/reports/public/[id]",
        "/docs",
        "/workbench",
        "/workbench/[taskId]",
        "/reports",
        "/reports/[artifactId]",
        "/connectors",
        "/settings",
    ]
    assert sum(1 for item in registry["page_routes"] if item["enabled"]) == 10
    assert [item["path"] for item in registry["primary_nav"]] == [
        "/workbench",
        "/reports",
        "/connectors",
        "/settings",
    ]
    assert {item["path"] for item in registry["page_routes"]}.isdisjoint(
        {item["path"] for item in registry["paths"]}
    )
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_repair_prerequisites.py -q
```

Expected: FAIL。`capability_profiles`、取消列、验收事件或 checker 函数缺失。

- [ ] **Step 3: 写模板能力画像 schema**

Create `configs/contracts/v1.1.0/template_capability_profile.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dih.local/contracts/v1.1.0/template_capability_profile.schema.json",
  "title": "Template capability profile",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "template_id",
    "profile_version",
    "allowed_capability_ids",
    "digest_scope",
    "digest_algorithm",
    "digest_profile",
    "empty_policy",
    "unknown_template"
  ],
  "properties": {
    "template_id": {"const": "tiktok_shop_maternal_newborn"},
    "profile_version": {"const": "1.0.0"},
    "allowed_capability_ids": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {"type": "string", "pattern": "^[a-z][a-z0-9_.]*$"}
    },
    "digest_scope": {"const": "template_registry_digest"},
    "digest_algorithm": {"const": "sha256"},
    "digest_profile": {"const": "dih-canonical-json-v1"},
    "empty_policy": {"const": "deny_all"},
    "unknown_template": {"const": "KeyError"}
  }
}
```

- [ ] **Step 4: 在契约正文写入 §2.13-§2.17**

在 `### 2.12` 之后插入以下内容。不得改写 §2.9-§2.12 的既有编号。

````markdown
### 2.13 取消幂等与 run 生命周期审计

`runs` 新增两列，只在 C6 的迁移 `202610220064` 创建：

- `cancel_idempotency_key_hash string(64) null`
- `cancel_reason_code string(80) null`

部分唯一索引：`uq_runs_workspace_cancel_idempotency (workspace_id, cancel_idempotency_key_hash) WHERE cancel_idempotency_key_hash IS NOT NULL`。

取消键派生：`sha256("run-cancel.v1:{idempotency_key}")`。创建幂等列 `runs.idempotency_key_hash` 与索引 `uq_runs_workspace_idempotency` 不得复用为取消幂等。

`POST /api/runs/{run_id}/cancel` 请求体必须含 `idempotency_key` 与 `reason_code`，二者非空。

- 缺少或空白：422 `invalid_request`。
- 同一工作区、同一 run、同一键、同一 `reason_code`：200 重放第一次结果，响应头 `Idempotent-Replay: true`；不重复写审计，不重复释放预算。
- 同一键、不同 `reason_code`：409 `idempotency_conflict`。
- 同一 run 已被另一个键取消：200 重放原结果。
- run 不存在：404 `run_not_found`。
- run 已进入非取消终态：409 `state_conflict`。

并发只允许一个事务把 `queued`/`running` 改为 `cancelled`。只有胜出事务调用 C5 `OrmRunBudget.cancel`。

客户 MCP `cancel_task`：

- `CancelTaskInput` 必填 `task_id`、`idempotency_key`、`reason_code`；空白值由 MCP schema 的 `minLength` 拒绝，服务层兜底返回 `invalid_request`。C13 的允许错误码列表必须包含 `invalid_request`。
- C13 必须调用 C6 `services.run_service.cancel_task_runs(session, *, workspace_id, project_id, task_id, idempotency_key, reason_code) -> RunCancellationResult`。该函数是任务级取消唯一入口。
- 每个 run 派生键 `f"{idempotency_key}:{run_id}"`，再按 `run-cancel.v1` 规则哈希。
- 同键同 `reason_code`：重放，`RunCancellationResult.replayed=True`。
- 同键不同 `reason_code` 或不同 `task_id`：409 `idempotency_conflict`。
- 已终态且无同键记录：409 `state_conflict`。
- 不得 `del` 参数，不得在 C13 循环 `cancel_run`，不得写第二张取消表。

run 生命周期审计动作只允许：`run.created`、`run.cancel_requested`、`run.cancelled`、`run.retry_scheduled`、`run.retry_exhausted`、`run.completed`、`run.failed`。`run.created` 的 owner 是 C4，只能由 C4 `services/run_creation.create_run_with_audit` 接缝写；其余六个动作的 owner 是 C6。C6 旧入口收敛调用 C4 接缝，不直接写 `run.created`。`run.created` 只在插入新 run 时写；幂等重放不写。

### 2.14 模板能力画像

模板能力画像不是表。唯一事实源是代码注册表 `apps/api/src/data_intelligence_hub/services/workbench_templates.py`。禁止创建 `task_templates`、`template_capability_profiles` 或任何能力白名单表。

`TaskTemplate.capability_allowlist` 是 `tuple[str, ...]`，元素是 `tool_catalog` 的稳定 `tool_id`，按字典序去重。首期模板 `tiktok_shop_maternal_newborn` 使用显式冻结列表，不按目录谓词动态展开。`creator_cookie` 门控能力 `tikhub_tiktok_video_products`、`tikhub_tiktok_creator_showcase` 不得进入。

`template_capability_ids(template_id)` 是唯一读取入口：未知模板抛 `KeyError`；空白名单返回空元组，调用方必须拒绝全部能力（fail-closed）。

`template_registry_digest()` 使用 `dih-canonical-json-v1` 与 SHA-256，覆盖 `template_id`、`version`、`markets`、`package_tiers`、`TaskTemplate.capability_allowlist` 与全部阈值。白名单变化必须改变摘要，并写 `quality.template.changed` 审计。

`capability_not_allowed`（403）表示能力不在 `project_api_keys.capability_allowlist` 或不在 `TaskTemplate.capability_allowlist` 内。先查密钥白名单，再查模板白名单；两处都在 Cookie 与额度检查之前。不得返回具体哪一处失败。C13 只调用 `template_capability_ids(template_id)`，不直接读字段名，也不新增第二个同义字段。

C1 登记 schema 文件 `configs/contracts/v1.1.0/template_capability_profile.schema.json`。它是结构约束，不是数据副本。

### 2.15 Quick 2 小时方向稿

Quick 首次草稿是 2 小时方向稿。它使用既有 `report_artifacts` 与 ReportContract 1.1，不新增顶层键、客户 MCP 工具、订单、run、workflow_version、授权或账本行。

`report_artifacts.delivery_class='quick_draft'`，`status='draft'`，`report_version=1`。合同 `review.status='draft'`；`acceptance` 使用合法占位组；`delivery` 使用合法 nil 占位组。

证据等级上限 `L3_live_single`。`sku_candidates` 必须为空。`markets[].conclusion_standard` 必须缺省。不得出现 `confirmed`。只允许 Quick 方向标签：`worth_validating`、`deprioritize`、`key_risk`、`evidence_gap`、`recommend_standard_scope`。Standard 任务调用 Quick 端点返回 422 `quick_draft_not_allowed`；Quick 稿出现 `confirmed`、Standard 四态或高于 L3 的证据时返回 422 `quick_draft_claim_invalid`。

不启动验收：`report_artifacts.acceptance_deadline` 为 `NULL`；不写任何 `acceptance_*` 事件；验收端点返回 409 `acceptance_not_applicable`。

Quick 稿端点固定为：`POST /api/reports/{artifact_id}/delivery/quick-draft`、`GET /api/reports/{artifact_id}/delivery/quick-draft`、`GET /api/tasks/{task_id}/delivery/quick-draft`。三个端点都只做项目内鉴权读取或发布，不做公开分享。

不重复计费：发布前后 `runs`、`run_ledger_entries`、`dataset_versions` 行数不变。

24 小时正式版由 C9 `create_reviewed_contract_version` 创建 `report_version=2`，沿用同一 `report_id`、`task_id`、`order_id` 与 L3 上限；不新建 run、订单、授权或账本。Quick 稿不得公开分享。

### 2.16 交付类别、验收事件与状态映射

`report_artifacts.delivery_status`：`pending · delivered · superseded`。
`report_artifacts.delivery_class`：`formal · quick_draft`。
C9 `report_artifacts.status`：`draft · published · superseded`。三套值集分开，不得复用同名状态机。

`report_audit_events.event_type` 追加：`delivery_pii_detected`、`acceptance_accepted`、`acceptance_disputed`、`acceptance_deemed_accepted`。

验收状态映射：`acceptance_accepted -> accepted`；`acceptance_disputed -> objection`；`acceptance_deemed_accepted -> auto_accepted`。只使用 C1 `$defs/acceptance.status` 的既有值。

验收事件只追加，不更新、不删除；不得写第二张验收表。`manifest`、bundle、交付文件、`report_artifacts.acceptance_snapshot_json` 在验收前后不得变化。验收幂等键哈希与 `payload_sha256` 只写入 `report_audit_events.metadata_json`；不新增列、不新增表。

幂等派生固定为：`acceptance_idempotency_key_hash = sha256("delivery-acceptance.v1:{idempotency_key}")`；`payload_sha256 = sha256(canonical_json_bytes(payload))`，canonical profile 使用 `dih-canonical-json-v1`。`payload` 只含 `event_type`、`artifact_id`、`references` 与可选的验收备注；不得把原始 `Idempotency-Key` 写入事件。

`POST /api/reports/{artifact_id}/delivery/acceptance/{accept|dispute|deemed-accepted}` 都必须带 `Idempotency-Key`。

验收端点固定为：`POST /api/reports/{artifact_id}/delivery/acceptance/accept`、`POST /api/reports/{artifact_id}/delivery/acceptance/dispute`、`POST /api/reports/{artifact_id}/delivery/acceptance/deemed-accepted`、`GET /api/reports/{artifact_id}/delivery/acceptance`。

- `accept`/`dispute` 只在 `delivery_class='formal'`、`delivery_status='delivered'`、`now <= acceptance_deadline` 且无终态验收事件时允许。
- `deemed-accepted` 只在 `now > acceptance_deadline` 且无终态验收事件时允许。
- 同一 artifact、同一 key、同一 `event_type`、同一 `payload_sha256`：200 重放，不写第二条事件。
- 同 key 不同 `event_type` 或不同 `payload_sha256`：409 `idempotency_conflict`。
- 已有终态验收事件后，不同动作：409 `acceptance_already_closed`。
- `deemed-accepted` 在窗口内：409 `acceptance_window_open`。
- Quick 稿：409 `acceptance_not_applicable`。
- `dispute.references` 至少 1 项；`path` 必须命中 manifest 文件；未知 path、claim、evidence 或 item：422 `acceptance_reference_invalid`。
- 缺少 `Idempotency-Key`：400 `idempotency_key_required`。

### 2.17 PII 发布扫描画像

唯一扫描画像：`export_policy.v1`。唯一实现：C11 `apps/api/src/data_intelligence_hub/services/export_policy.py`。

C11 导出 `EXPORT_POLICY_VERSION = "export_policy.v1"`、`PiiHit(kind, field_path, start, end)`、`scan_export_policy(text, field_path="$") -> tuple[PiiHit, ...]`、`scan_export_value(value, field_path="$") -> tuple[PiiHit, ...]`。两个扫描函数都是只读纯函数，不写库、不读时钟、不联网。它们复用 C11 既有 `CONTACT_PATTERN`、`URL_PATTERN`、`PROFILE_HOSTS`、`HANDLE_FIELD_PATTERN`、`AVATAR_FIELD_PATTERN`。禁止第二套正则或第二份词表。

C9 与 C10 都只调用 C11 的 `scan_export_policy` / `scan_export_value`，只使用 `PiiHit`，不定义第二种命中类型。C9 审计键写 `export_policy_version='export_policy.v1'`；C10 审计键写 `pii_scan_profile='export_policy.v1'`。C9/C10 不得各自实现扫描器，不得复制正则，不得让两处命中集合分叉。C10 的扫描范围固定：manifest、公开合同与 Claim bundle 用 `scan_export_value`；两页 HTML、CSV、JSON、Markdown 文本用 `scan_export_policy`。

统一命中码只有四个：`contact`、`profile_link`、`avatar`、`tracking`。`PiiHit.kind` 只使用这四个值；不得增加第五个值。

C9 `publish_artifact` 命中时：合同保持 `draft`，写 `gate_evaluated`（`gate_id='G-Publish'`、`gate_status='blocked'`、`reason='pii_detected'`、`export_policy_version='export_policy.v1'`），抛既有 `report_publish_gate_blocked`。不新增 C9 错误码。

C10 发布与下载命中时：409 `delivery_pii_detected`。不写 bundle，不置 `delivered_*` 字段。发布写 `gate_evaluated` 与 `delivery.published`（`result=denied`）；下载复核写 `delivery_pii_detected` 领域事件并投影 `delivery.tamper_detected`。审计只记录 `kind`、`field_path` 与 `pii_scan_profile`，不记录原始值。

C9/C10 不得新增 PII 扫描实现、第二套正则、第二个扫描画像或 `delivery.pii.*` 审计动作。
````

- [ ] **Step 5: 用以下片段修订 registry schema**

在 Task 1 生成的 `configs/contracts/v1.1.0/registry.schema.json` 中：

1. 顶层 `properties` 增加 `capability_profiles`：

```json
{
  "capability_profiles": {
    "type": "array",
    "minItems": 1,
    "items": {"$ref": "#/$defs/capability_profile"}
  }
}
```

2. `canonical_profile.properties` 增加 `pii_scan`：

```json
{
  "pii_scan": {"$ref": "#/$defs/pii_scan_profile"}
}
```

3. `$defs` 增加 `capability_profile` 与 `pii_scan_profile`，并保留 `additionalProperties: false`：

```json
{
  "capability_profile": {
    "type": "object",
    "additionalProperties": false,
    "required": ["profile_id", "profile_version", "registry_source", "schema_path", "entrypoint", "digest_function", "digest_profile", "digest_algorithm", "digest_includes", "empty_allowlist_policy", "unknown_template", "storage", "excluded_capability_ids"],
    "properties": {
      "profile_id": {"const": "dih-template-capability-v1"},
      "profile_version": {"const": "1.0.0"},
      "registry_source": {"const": "apps/api/src/data_intelligence_hub/services/workbench_templates.py"},
      "schema_path": {"const": "configs/contracts/v1.1.0/template_capability_profile.schema.json"},
      "entrypoint": {"const": "template_capability_ids"},
      "digest_function": {"const": "template_registry_digest"},
      "digest_profile": {"const": "dih-canonical-json-v1"},
      "digest_algorithm": {"const": "sha256"},
      "digest_includes": {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
      "empty_allowlist_policy": {"const": "deny_all"},
      "unknown_template": {"const": "KeyError"},
      "storage": {"const": "code_registry_not_table"},
      "excluded_capability_ids": {"type": "array", "uniqueItems": true, "items": {"type": "string", "minLength": 1}}
    }
  },
  "pii_scan_profile": {
    "type": "object",
    "additionalProperties": false,
    "required": ["profile_id", "owner", "module", "scanner", "value_scanner", "finding_type", "finding_codes", "c9_error", "c10_error", "shared_by", "no_second_ruleset"],
    "properties": {
      "profile_id": {"const": "export_policy.v1"},
      "owner": {"const": "C11"},
      "module": {"const": "apps/api/src/data_intelligence_hub/services/export_policy.py"},
      "scanner": {"const": "scan_export_policy"},
      "value_scanner": {"const": "scan_export_value"},
      "finding_type": {"const": "PiiHit"},
      "finding_codes": {"type": "array", "minItems": 4, "maxItems": 4, "uniqueItems": true, "items": {"enum": ["contact", "profile_link", "avatar", "tracking"]}},
      "c9_error": {"const": "report_publish_gate_blocked"},
      "c10_error": {"const": "delivery_pii_detected"},
      "shared_by": {"type": "array", "minItems": 2, "maxItems": 2, "uniqueItems": true, "items": {"enum": ["C9", "C10"]}},
      "no_second_ruleset": {"const": true}
    }
  }
}
```

4. `$defs.schema_ref.properties.kind.enum` 追加 `template_capability_profile`。

5. `$defs.phase.properties.objects.items.pattern` 改为 `^(table|enum|path|mcp_tool|error|schema|page_route|primary_nav):`，以保留 C14 既有的 `page_route:` 与 `primary_nav:` 前缀。

- [ ] **Step 6: 把以下对象合并进附录 A 的对应数组**

`runs` 表对象增加两列与一个索引：

```json
[
  {"name": "cancel_idempotency_key_hash", "type": "string(64)", "nullable": true, "status": "extend", "phase": "C6", "notes": "sha256(\"run-cancel.v1:{idempotency_key}\")；只在迁移 202610220064 创建；不得复用创建幂等列"},
  {"name": "cancel_reason_code", "type": "string(80)", "nullable": true, "status": "extend", "phase": "C6", "notes": "取消原因码；只在迁移 202610220064 创建"}
]
```

```json
{"name": "uq_runs_workspace_cancel_idempotency", "columns": ["workspace_id", "cancel_idempotency_key_hash"], "unique": true, "where": "cancel_idempotency_key_hash IS NOT NULL"}
```

`report_artifacts` 表对象增加三列与一个约束：

```json
[
  {"name": "delivery_class", "type": "string(20)", "nullable": false, "status": "extend", "phase": "C10", "enum": "report_artifacts.delivery_class", "default": "formal"},
  {"name": "acceptance_deadline", "type": "datetime", "nullable": true, "status": "extend", "phase": "C10"},
  {"name": "quick_draft_of_artifact_id", "type": "uuid", "nullable": true, "status": "extend", "phase": "C10", "references": "report_artifacts.id"}
]
```

```json
"ck_report_artifacts_delivery_class"
```

`ck_report_artifacts_delivery_fields` 增加以下判定：

```text
delivery_class = 'formal' AND delivery_status = 'delivered'
  => acceptance_snapshot_json IS NOT NULL
     AND acceptance_deadline IS NOT NULL
     AND quick_draft_of_artifact_id IS NULL
delivery_class = 'quick_draft' AND delivery_status = 'delivered'
  => acceptance_snapshot_json IS NULL
     AND acceptance_deadline IS NULL
     AND quick_draft_of_artifact_id IS NOT NULL
```

`enums` 数组增加：

```json
{"name": "report_artifacts.delivery_class", "values": ["formal", "quick_draft"], "status": "new", "phase": "C10", "source": "C10 契约 §2.9"}
```

`report_audit_events.event_type` 的 `values` 追加 `delivery_pii_detected`、`acceptance_accepted`、`acceptance_disputed`、`acceptance_deemed_accepted`。

`audit_actions.actions` 追加：

```json
[
  {"name": "run.created", "owner": "C4", "status": "new", "phase": "C4"},
  {"name": "run.cancel_requested", "owner": "C6", "status": "new", "phase": "C6"},
  {"name": "run.retry_scheduled", "owner": "C6", "status": "new", "phase": "C6"},
  {"name": "run.retry_exhausted", "owner": "C6", "status": "new", "phase": "C6"},
  {"name": "run.failed", "owner": "C6", "status": "new", "phase": "C6"}
]
```

`paths` 数组追加：

```json
[
{"id": "runs.cancel", "method": "POST", "path": "/api/runs/{run_id}/cancel", "audience": "session", "status": "existing", "phase": "C6", "auth": "session", "idempotent": true, "error_codes": ["authentication_required", "run_not_found", "state_conflict", "invalid_request", "idempotency_conflict"]},
{"id": "delivery.quick_draft.create", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/quick-draft", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "quick_draft_not_allowed", "quick_draft_claim_invalid", "delivery_pii_detected", "delivery_input_invalid", "idempotency_key_required", "idempotency_conflict", "gate_failed", "delivery_integrity_error"]},
{"id": "delivery.quick_draft.read", "method": "GET", "path": "/api/reports/{artifact_id}/delivery/quick-draft", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "delivery_not_found", "delivery_not_published"]},
{"id": "delivery.quick_draft.task_read", "method": "GET", "path": "/api/tasks/{task_id}/delivery/quick-draft", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "task_not_found", "delivery_not_found"]},
{"id": "delivery.acceptance.accept", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/acceptance/accept", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable", "acceptance_window_open", "acceptance_already_closed", "idempotency_key_required", "idempotency_conflict"]},
{"id": "delivery.acceptance.dispute", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/acceptance/dispute", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable", "acceptance_window_open", "acceptance_already_closed", "acceptance_reference_invalid", "idempotency_key_required", "idempotency_conflict"]},
{"id": "delivery.acceptance.deemed_accept", "method": "POST", "path": "/api/reports/{artifact_id}/delivery/acceptance/deemed-accepted", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": true, "idempotency": {"header": "Idempotency-Key", "required": true, "replay_status": 200, "replay_header": "Idempotent-Replay", "conflict_error": "idempotency_conflict"}, "error_codes": ["authentication_required", "publish_forbidden", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable", "acceptance_window_open", "acceptance_already_closed", "idempotency_key_required", "idempotency_conflict"]},
{"id": "delivery.acceptance.read", "method": "GET", "path": "/api/reports/{artifact_id}/delivery/acceptance", "audience": "session", "status": "new", "phase": "C10", "auth": "session", "idempotent": false, "error_codes": ["authentication_required", "delivery_not_found", "delivery_not_published", "acceptance_not_applicable"]}
]
```

`error_codes` 数组追加：

```json
[
{"code": "run_not_found", "kind": "error", "http_status": 404, "retryable": false, "phase": "C6", "meaning": "run 不存在或无权访问"},
{"code": "delivery_pii_detected", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "PII 扫描命中，交付发布或下载被阻断；只记录 kind 与 field_path，不记录原始值"},
{"code": "quick_draft_not_allowed", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "任务包型不是 quick，不能创建 Quick 2 小时方向稿"},
{"code": "quick_draft_claim_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "Quick 稿 Claim 出现 confirmed、Standard 四态或高于 L3 的证据"},
{"code": "acceptance_window_open", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "验收窗口仍开放，不能写 deemed_accepted"},
{"code": "acceptance_already_closed", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "已有终态验收事件，不能再次验收"},
{"code": "acceptance_reference_invalid", "kind": "error", "http_status": 422, "retryable": false, "phase": "C10", "meaning": "争议引用未命中 manifest 文件、Claim、证据或条目"},
{"code": "acceptance_not_applicable", "kind": "error", "http_status": 409, "retryable": false, "phase": "C10", "meaning": "Quick 2 小时方向稿不启动验收"}
]
```

同时更新 `idempotency_key_required` 的 `meaning` 为“交付发布、Quick 2 小时方向稿或验收动作缺少 Idempotency-Key 请求头”，更新 `capability_not_allowed` 的 `meaning` 为“能力不在 project_api_keys.capability_allowlist 或不在 TaskTemplate.capability_allowlist 内；不披露具体失败的白名单”。

`schemas` 数组追加：

```json
{"id": "template_capability_profile", "path": "configs/contracts/v1.1.0/template_capability_profile.schema.json", "kind": "template_capability_profile", "profile": "dih-canonical-json-v1", "digest_algorithm": "sha256"}
```

顶层增加 `capability_profiles`，并在 `canonical_profile` 增加 `pii_scan`：

```json
{
  "capability_profiles": [
    {
      "profile_id": "dih-template-capability-v1",
      "profile_version": "1.0.0",
      "registry_source": "apps/api/src/data_intelligence_hub/services/workbench_templates.py",
      "schema_path": "configs/contracts/v1.1.0/template_capability_profile.schema.json",
      "entrypoint": "template_capability_ids",
      "digest_function": "template_registry_digest",
      "digest_profile": "dih-canonical-json-v1",
      "digest_algorithm": "sha256",
      "digest_includes": ["template_id", "version", "markets", "package_tiers", "capability_allowlist", "thresholds"],
      "empty_allowlist_policy": "deny_all",
      "unknown_template": "KeyError",
      "storage": "code_registry_not_table",
      "excluded_capability_ids": ["tikhub_tiktok_video_products", "tikhub_tiktok_creator_showcase"]
    }
  ]
}
```

```json
{
  "pii_scan": {
    "profile_id": "export_policy.v1",
    "owner": "C11",
    "module": "apps/api/src/data_intelligence_hub/services/export_policy.py",
    "scanner": "scan_export_policy",
    "value_scanner": "scan_export_value",
    "finding_type": "PiiHit",
    "finding_codes": ["contact", "profile_link", "avatar", "tracking"],
    "c9_error": "report_publish_gate_blocked",
    "c10_error": "delivery_pii_detected",
    "shared_by": ["C9", "C10"],
    "no_second_ruleset": true
  }
}
```

- [ ] **Step 7: 在 `scripts/contract_registry.py` 加入修复 checker**

在脚本导入区加入 `import hashlib` 与 `from datetime import datetime`。在 `check_semantics` 后加入：

```python
QUICK_DIRECTION_LABELS = {
    "worth_validating",
    "deprioritize",
    "key_risk",
    "evidence_gap",
    "recommend_standard_scope",
}
ACCEPTANCE_EVENT_TYPES = {
    "acceptance_accepted",
    "acceptance_disputed",
    "acceptance_deemed_accepted",
}
EVIDENCE_RANK = {
    "L0_unverified": 0,
    "L1_contract": 1,
    "L2_fixture_local": 2,
    "L3_live_single": 3,
    "L4_authorized_live": 4,
}


def _cancel_hash(idempotency_key: str) -> str:
    return hashlib.sha256(
        f"run-cancel.v1:{idempotency_key}".encode("utf-8")
    ).hexdigest()


def check_cancel_request(value: dict[str, Any], stored: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    key = str(value.get("idempotency_key") or "")
    reason = str(value.get("reason_code") or "")
    if not key:
        errors.append("cancel_idempotency_key_missing")
    if not reason:
        errors.append("cancel_reason_code_missing")
    if errors or stored is None:
        return errors
    expected = _cancel_hash(key)
    stored_hash = str(stored.get("cancel_idempotency_key_hash") or "")
    stored_reason = str(stored.get("cancel_reason_code") or "")
    status = str(stored.get("status") or "")
    if stored_hash == expected:
        if stored_reason != reason:
            errors.append("idempotency_conflict")
        return errors
    if status == "cancelled":
        return errors
    if status in {"completed", "failed"}:
        errors.append("cancel_state_conflict")
    return errors


def check_quick_draft_artifact(
    artifact: dict[str, Any], contract: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if artifact.get("status") != "draft":
        errors.append("quick_draft_status_invalid")
    if artifact.get("delivery_class") != "quick_draft":
        errors.append("quick_draft_delivery_class_invalid")
    if artifact.get("report_version") != 1:
        errors.append("quick_draft_report_version_invalid")
    if artifact.get("acceptance_deadline") is not None:
        errors.append("quick_draft_acceptance_deadline_not_null")
    if artifact.get("acceptance_events"):
        errors.append("quick_draft_acceptance_forbidden")
    if contract.get("review", {}).get("status") != "draft":
        errors.append("quick_draft_review_not_draft")
    if contract.get("sku_candidates"):
        errors.append("quick_draft_sku_candidates_not_empty")
    for claim in contract.get("claims", []):
        if claim.get("status") == "confirmed":
            errors.append("quick_draft_confirmed_forbidden")
        grade = str(claim.get("evidence_grade") or "")
        if EVIDENCE_RANK.get(grade, 99) > EVIDENCE_RANK["L3_live_single"]:
            errors.append("quick_draft_evidence_grade_exceeds_l3")
    for market in contract.get("markets", []):
        if market.get("conclusion_standard") is not None:
            errors.append("quick_draft_conclusion_standard_present")
        label = market.get("conclusion_quick")
        if label is not None and label not in QUICK_DIRECTION_LABELS:
            errors.append(f"quick_draft_label_invalid:{label}")
    return errors


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_acceptance_event_sequence(
    events: list[dict[str, Any]], *, deadline: str, now: str
) -> list[str]:
    errors: list[str] = []
    deadline_at = _parse_timestamp(deadline)
    now_at = _parse_timestamp(now)
    terminal_count = 0
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        event_type = str(event.get("event_type") or "")
        if event_type not in ACCEPTANCE_EVENT_TYPES:
            errors.append(f"acceptance_event_type_invalid:{event_type}")
            continue
        key_hash = str(event.get("idempotency_key_hash") or "")
        payload_sha256 = str(event.get("payload_sha256") or "")
        if not key_hash:
            errors.append("acceptance_event_idempotency_key_missing")
        if not payload_sha256:
            errors.append("acceptance_event_payload_digest_missing")
        identity = (event_type, key_hash, payload_sha256)
        if identity in seen:
            errors.append(f"acceptance_event_duplicate:{event_type}")
            continue
        seen.add(identity)
        recorded_at = _parse_timestamp(str(event["recorded_at"]))
        if recorded_at > now_at:
            errors.append("acceptance_event_in_future")
        if event_type == "acceptance_deemed_accepted":
            if recorded_at <= deadline_at:
                errors.append("acceptance_deemed_accepted_before_deadline")
        else:
            if recorded_at > deadline_at:
                errors.append("acceptance_window_closed")
            if event_type == "acceptance_disputed" and not event.get("references"):
                errors.append("acceptance_reference_invalid")
        terminal_count += 1
    if terminal_count > 1:
        errors.append("acceptance_already_closed")
    if terminal_count == 0:
        errors.append("acceptance_terminal_event_missing")
    return errors


def check_repair_prerequisites(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tables = {str(item["name"]): item for item in registry.get("tables", [])}
    runs = tables.get("runs", {})
    run_columns = {str(item["name"]): item for item in runs.get("columns", [])}
    for name, expected_type in (
        ("cancel_idempotency_key_hash", "string(64)"),
        ("cancel_reason_code", "string(80)"),
    ):
        column = run_columns.get(name)
        if column is None:
            errors.append(f"missing_cancel_column:{name}")
        elif column.get("type") != expected_type or column.get("phase") != "C6":
            errors.append(f"invalid_cancel_column:{name}")
    cancel_indexes = [
        item
        for item in runs.get("indexes", [])
        if item.get("name") == "uq_runs_workspace_cancel_idempotency"
    ]
    if not cancel_indexes:
        errors.append("missing_cancel_index:uq_runs_workspace_cancel_idempotency")
    else:
        index = cancel_indexes[0]
        if index.get("columns") != ["workspace_id", "cancel_idempotency_key_hash"]:
            errors.append("invalid_cancel_index:uq_runs_workspace_cancel_idempotency")
        if index.get("where") != "cancel_idempotency_key_hash IS NOT NULL":
            errors.append("invalid_cancel_index_predicate:uq_runs_workspace_cancel_idempotency")
    create_indexes = {
        item.get("name"): item for item in runs.get("indexes", [])
    }
    create_index = create_indexes.get("uq_runs_workspace_idempotency", {})
    if create_index.get("columns") == ["workspace_id", "cancel_idempotency_key_hash"]:
        errors.append("cancel_idempotency_reuses_create_index")
    actions = {
        str(item["name"]) for item in registry.get("audit_actions", {}).get("actions", [])
    }
    for name in (
        "run.created",
        "run.cancel_requested",
        "run.retry_scheduled",
        "run.retry_exhausted",
        "run.failed",
    ):
        if name not in actions:
            errors.append(f"missing_run_audit_action:{name}")
    profiles = registry.get("capability_profiles", [])
    if len(profiles) != 1 or profiles[0].get("profile_id") != "dih-template-capability-v1":
        errors.append("missing_template_capability_profile")
    forbidden_tables = {
        "task_templates",
        "template_capability_profiles",
        "template_capability_allowlist",
    }
    if forbidden_tables & set(tables):
        errors.append("template_capability_profile_table_forbidden")
    artifacts = tables.get("report_artifacts", {})
    artifact_columns = {
        str(item["name"]): item for item in artifacts.get("columns", [])
    }
    for name in (
        "delivery_class",
        "acceptance_deadline",
        "quick_draft_of_artifact_id",
    ):
        if name not in artifact_columns:
            errors.append(f"missing_delivery_column:{name}")
    if "ck_report_artifacts_delivery_class" not in set(
        artifacts.get("constraints", [])
    ):
        errors.append("missing_delivery_constraint:ck_report_artifacts_delivery_class")
    enums = {
        str(item["name"]): list(item.get("values", []))
        for item in registry.get("enums", [])
    }
    for event_type in (
        "delivery_pii_detected",
        "acceptance_accepted",
        "acceptance_disputed",
        "acceptance_deemed_accepted",
    ):
        if event_type not in enums.get("report_audit_events.event_type", []):
            errors.append(f"missing_acceptance_event:{event_type}")
    paths = {str(item["id"]): item for item in registry.get("paths", [])}
    for path_id in (
        "delivery.acceptance.accept",
        "delivery.acceptance.dispute",
        "delivery.acceptance.deemed_accept",
    ):
        item = paths.get(path_id)
        if item is None:
            errors.append(f"missing_acceptance_path:{path_id}")
            continue
        idempotency = item.get("idempotency", {})
        if item.get("idempotent") is not True:
            errors.append(f"acceptance_path_not_idempotent:{path_id}")
        if idempotency.get("conflict_error") != "idempotency_conflict":
            errors.append(f"acceptance_path_conflict_unbound:{path_id}")
    codes = {
        str(item["code"]) for item in registry.get("error_codes", [])
    }
    for code in (
        "run_not_found",
        "delivery_pii_detected",
        "quick_draft_not_allowed",
        "quick_draft_claim_invalid",
        "acceptance_window_open",
        "acceptance_already_closed",
        "acceptance_reference_invalid",
        "acceptance_not_applicable",
    ):
        if code not in codes:
            errors.append(f"missing_error:{code}")
    pii = registry.get("canonical_profile", {}).get("pii_scan")
    if not isinstance(pii, dict):
        errors.append("missing_pii_scan_profile")
    else:
        if pii.get("profile_id") != "export_policy.v1":
            errors.append("invalid_pii_scan_profile")
        if pii.get("scanner") != "scan_export_policy":
            errors.append("invalid_pii_scan_scanner")
        if pii.get("value_scanner") != "scan_export_value":
            errors.append("invalid_pii_value_scanner")
        if pii.get("finding_codes") != [
            "contact",
            "profile_link",
            "avatar",
            "tracking",
        ]:
            errors.append("invalid_pii_finding_codes")
    if "pii_profiles" in registry:
        errors.append("pii_scan_profile_duplicated")
    return errors
```

在 `check` 的 `errors = validate_registry(registry, schema)` 后加一行；`build` 不加，避免 Task 10 的最小 registry 测试被修复检查拦截：

```python
    errors.extend(check_repair_prerequisites(registry))
```

在 `main` 增加 CLI：

```python
    repairs_parser = subparsers.add_parser("check-repairs")
    repairs_parser.add_argument("--registry", type=Path, required=True)
```

在 `main` 分支加入：

```python
    if args.command == "check-repairs":
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        errors = check_repair_prerequisites(registry)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("repair prerequisites OK")
        return 0
```

- [ ] **Step 8: 写 golden 与 negative fixture**

Create `apps/api/tests/fixtures/contract_registry/golden/repair_prerequisites.json`:

```json
{
  "runs_columns": ["cancel_idempotency_key_hash", "cancel_reason_code"],
  "runs_index": {
    "name": "uq_runs_workspace_cancel_idempotency",
    "columns": ["workspace_id", "cancel_idempotency_key_hash"],
    "unique": true,
    "where": "cancel_idempotency_key_hash IS NOT NULL"
  },
  "report_artifacts_columns": [
    "delivery_class",
    "acceptance_deadline",
    "quick_draft_of_artifact_id"
  ],
  "acceptance_event_types": [
    "acceptance_accepted",
    "acceptance_disputed",
    "acceptance_deemed_accepted"
  ],
  "run_audit_actions": [
    "run.created",
    "run.cancel_requested",
    "run.retry_scheduled",
    "run.retry_exhausted",
    "run.failed"
  ],
  "capability_profile_id": "dih-template-capability-v1",
  "pii_scan_profile_id": "export_policy.v1"
}
```

Create `apps/api/tests/fixtures/contract_registry/golden/cancel_replay.json`:

```json
{
  "new_request": {
    "run_id": "11111111-1111-1111-1111-111111111111",
    "idempotency_key": "cancel-1",
    "reason_code": "user_request"
  },
  "stored_after_first": {
    "status": "cancelled",
    "cancel_idempotency_key_hash": "edff473ca1b30feba66785a84e903703a112f6ee97b80e52f01e841ca9101783",
    "cancel_reason_code": "user_request"
  },
  "replay_request": {
    "run_id": "11111111-1111-1111-1111-111111111111",
    "idempotency_key": "cancel-1",
    "reason_code": "user_request"
  },
  "conflict_request": {
    "run_id": "11111111-1111-1111-1111-111111111111",
    "idempotency_key": "cancel-1",
    "reason_code": "budget_stop"
  }
}
```

Create `apps/api/tests/fixtures/contract_registry/golden/quick_draft_artifact.json`:

```json
{
  "artifact": {
    "status": "draft",
    "report_version": 1,
    "delivery_class": "quick_draft",
    "acceptance_deadline": null,
    "acceptance_events": []
  },
  "contract": {
    "schema_version": "1.1.0",
    "report_version": 1,
    "review": {"status": "draft"},
    "acceptance": {
      "status": "pending",
      "window_start": "2026-10-22",
      "window_end": "2026-10-29"
    },
    "delivery": {
      "manifest_id": "00000000-0000-0000-0000-000000000000",
      "report_artifact_id": "00000000-0000-0000-0000-000000000000",
      "report_version": 1,
      "access_scope": ["workspace_project"],
      "retention_class": "standard_24m"
    },
    "claims": [
      {
        "claim_id": "claim-1",
        "status": "directional",
        "evidence_grade": "L3_live_single"
      }
    ],
    "sku_candidates": [],
    "markets": [
      {
        "market": "US",
        "conclusion_standard": null,
        "conclusion_quick": "worth_validating"
      }
    ]
  }
}
```

Create `apps/api/tests/fixtures/contract_registry/golden/acceptance_events.json`:

```json
{
  "deadline": "2026-10-29T23:59:59Z",
  "now_before": "2026-10-24T00:00:00Z",
  "now_after": "2026-10-30T00:00:00Z",
  "accepted": [
    {
      "event_type": "acceptance_accepted",
      "idempotency_key_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "payload_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "recorded_at": "2026-10-24T00:00:00Z",
      "references": []
    }
  ],
  "disputed": [
    {
      "event_type": "acceptance_disputed",
      "idempotency_key_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "payload_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "recorded_at": "2026-10-24T00:00:00Z",
      "references": [
        {"path": "report.zh.html", "description": "结论与证据不一致"}
      ]
    }
  ],
  "deemed": [
    {
      "event_type": "acceptance_deemed_accepted",
      "idempotency_key_hash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      "payload_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      "recorded_at": "2026-10-30T00:00:00Z",
      "references": []
    }
  ]
}
```

Create `apps/api/tests/fixtures/contract_registry/negative/repair_quick_draft_confirmed.json`:

```json
{"mutation": "repair_quick_draft_confirmed"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/repair_quick_draft_acceptance.json`:

```json
{"mutation": "repair_quick_draft_acceptance"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/repair_acceptance_early_deemed.json`:

```json
{"mutation": "repair_acceptance_early_deemed"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/repair_cancel_reason_conflict.json`:

```json
{"mutation": "repair_cancel_reason_conflict"}
```

Create `apps/api/tests/fixtures/contract_registry/negative/repair_pii_second_profile.json`:

```json
{"mutation": "repair_pii_second_profile"}
```

- [ ] **Step 9: 重新生成 registry 并运行 checker**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py build --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --out configs/contracts/v1.1.0/registry.json
apps/api/.venv/bin/python scripts/contract_registry.py check --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" --schema configs/contracts/v1.1.0/registry.schema.json --registry configs/contracts/v1.1.0/registry.json
apps/api/.venv/bin/python scripts/contract_registry.py check-repairs --registry configs/contracts/v1.1.0/registry.json
```

Expected: `registry built`、`registry check OK`、`repair prerequisites OK`。

- [ ] **Step 10: 运行测试与 ruff**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_repair_prerequisites.py -q
cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py tests/unit/test_contract_repair_prerequisites.py -q
cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/ruff check ../scripts/contract_registry.py tests/unit/test_contract_repair_prerequisites.py
```

Expected: 全部 passed；`All checks passed!`。

- [ ] **Step 11: 页面路由保留断言**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python - <<'PY'
import json
from pathlib import Path
registry = json.loads(Path("configs/contracts/v1.1.0/registry.json").read_text(encoding="utf-8"))
assert len(registry["page_routes"]) == 11
assert sum(1 for item in registry["page_routes"] if item["enabled"]) == 10
assert [item["path"] for item in registry["primary_nav"]] == ["/workbench", "/reports", "/connectors", "/settings"]
assert {item["path"] for item in registry["page_routes"]}.isdisjoint({item["path"] for item in registry["paths"]})
print("page routes preserved")
PY
```

Expected: `page routes preserved`。

- [ ] **Step 12: Commit**

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" configs/contracts/v1.1.0/registry.schema.json configs/contracts/v1.1.0/registry.json configs/contracts/v1.1.0/template_capability_profile.schema.json scripts/contract_registry.py apps/api/tests/unit/test_contract_repair_prerequisites.py apps/api/tests/fixtures/contract_registry
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): register repair prerequisites for c6 c8 c9 c10"
```

---

### Task 15: 最终验证与评审包

**Files:**
- Verify: 全部 C1 文件
- Modify: 无（除非验证发现缺陷）

**Interfaces:**
- Consumes: 所有前序任务的产物。
- Produces: 可复核的验证记录与最终 commit。

- [ ] **Step 1: 运行完整单元测试**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit/test_contract_registry.py tests/unit/test_contract_repair_prerequisites.py -q`

Expected: 全部 passed。`test_contract_registry.py` 仍为 `76 passed`；`test_contract_repair_prerequisites.py` 的 10 个测试全部通过。若人数不同，以实际输出为准，但 0 failed。

- [ ] **Step 2: 运行全量 unit 测试**

Run: `cd /Users/lute/Project/data_scrapy-gov-c1/apps/api && .venv/bin/python -m pytest tests/unit -q`

Expected: 0 failed。记录 passed 数量。不得引用旧基线数字。

- [ ] **Step 3: 运行 registry build 与 check**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py build \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --out configs/contracts/v1.1.0/registry.json
apps/api/.venv/bin/python scripts/contract_registry.py check \
  --doc "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --schema configs/contracts/v1.1.0/registry.schema.json \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: `registry built` 与 `registry check OK`。`git diff --exit-code configs/contracts/v1.1.0/registry.json` 必须无输出。

- [ ] **Step 4: 运行文档检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/contract_registry.py check-docs \
  --contract "docs/design/【契约冻结】v1-表名-枚举-接口.md" \
  --prd "docs/product/【PRD】母婴出海数据洞察Agent工作台.md" \
  --playbook "docs/product/【Playbook】母婴出海洞察交付.md" \
  --registry configs/contracts/v1.1.0/registry.json
```

Expected: `document check OK`。

- [ ] **Step 5: 运行格式与文件完整性检查**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1/apps/api
.venv/bin/ruff check ../scripts/contract_registry.py tests/unit/test_contract_registry.py
cd /Users/lute/Project/data_scrapy-gov-c1
apps/api/.venv/bin/python scripts/check_file_integrity.py
```

Expected: `All checks passed!` 与 `file integrity OK`。

- [ ] **Step 6: 运行 GitNexus 变更分析**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
node .gitnexus/run.cjs detect-changes --scope all --repo .
```

Expected: 输出不含 `partial: true` 与 `truncated: true`。记录受影响文件与符号。

- [ ] **Step 7: 检查工作树与提交范围**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git status --short
git diff --stat pg0-baseline-v1..HEAD
```

Expected: 只包含本计划列出的文件。`apps/api/src/**` 只允许 `apps/api/src/data_intelligence_hub/schemas/report_contract.py`；不得包含 `apps/api/alembic/**`、`apps/web/**` 或其他 `apps/api/src/**`。

- [ ] **Step 8: 生成评审包摘要**

Run:

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git log --oneline -15
git diff --stat pg0-baseline-v1..HEAD
```

把以下内容写入评审说明，不写入仓库文件：

```text
C1 交付：
- 契约 v1.1 正文与附录 A 机器登记块
- registry.schema.json、registry.json
- apps/api/schemas/report_contract.schema.json（唯一报告合同 schema，1.1.0）、delivery_manifest.schema.json、customer_mcp.schema.json
- contract_registry.py（build/check/check-docs）
- 76 个契约测试
- PRD v1.1 与 Playbook v1.1

未交付：
- C2-C14 运行时代码
- 数据库迁移
- 生产发布
```

- [ ] **Step 9: 最终 commit**

只有在 `git status --short` 非空时执行。提交范围为 C1 文件。

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
git add "docs/design/【契约冻结】v1-表名-枚举-接口.md" "docs/product/【PRD】母婴出海数据洞察Agent工作台.md" "docs/product/【Playbook】母婴出海洞察交付.md" configs/contracts/v1.1.0 apps/api/schemas/report_contract.schema.json apps/api/src/data_intelligence_hub/schemas/report_contract.py apps/api/tests/unit/test_report_contract.py apps/api/tests/unit/test_contract_registry.py apps/api/tests/fixtures/contract_registry apps/api/tests/fixtures/golden_reports docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
node .gitnexus/run.cjs detect-changes --scope all --repo .
git commit -m "docs(contract): finalize v1.1 registry and review evidence"
```

---

## Self-Review

### 规格覆盖

| 设计章节 | 覆盖任务 | 证据 |
|---|---|---|
| §0.5 冲突优先级 | Task 11 | 契约 §0.0 权威规则 |
| §3.2 唯一事实源 | Task 2、Task 3、Task 4、Task 5、Task 6 | 表、列、owner phase |
| §3.3 订单展开 | Task 2 | `workbench_tasks`、`runs.market_code`、`run_step_attempts` |
| §3.5 失败语义 | Task 8 | 错误码表与 MCP 工具错误码 |
| §4.1 输入合同 | Task 2、Task 9、Task 11、Task 12 | `workbench_tasks` 七槽位字段与 `package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`、`max_cost_usd/max_pages/max_records`、`seed_products`、`target_price_band`、`idempotency_key_hash` 与 `uq_workbench_tasks_workspace_idempotency` |
| §4.2 Quick/Standard | Task 2、Task 7、Task 12、Task 13 | `package_type`、Quick 最多 1 个对比市场、Standard 最多 3 个、市场质量与标签 |
| §5.1-5.7 质量与 Claim | Task 4、Task 7、Task 13 | gap、market_assessments、claims |
| §6.1 不可变报告合同 | Task 5、Task 9 | `report_artifacts`、`apps/api/schemas/report_contract.schema.json` |
| §6.2 交付包 | Task 5、Task 9 | `report_artifacts` 交付列、manifest schema |
| §6.3 人工审核 | Task 5 | `report_audit_events` 扩展 |
| §6.4 验收与补救 | Task 5、Task 7 | `report_artifacts.acceptance_snapshot_json`、`report_audit_events` |
| §6.5 刷新与可比性 | 延期 | 首期不登记刷新对象；新增前先升级契约 |
| §7.1 客户角色 | Task 3、Task 7 | `workspace_members.role` |
| §7.2 项目密钥 | Task 3、Task 8 | `project_api_keys`、密钥路径 |
| §7.3 客户 MCP | Task 8、Task 9、Task 12 | 八工具、`/mcp/customer`、`customer_mcp.schema.json` |
| §7.4 Cookie 隔离 | Task 8 | `cookie_not_accepted`、forbidden tools |
| §7.5 冻结账本契约 | Task 2、Task 7、Task 12、Task 13 | 八列、六值、settle/release 符号 |
| §7.6 隐私与保留 | Task 6 | `workspace_pseudonym_salts`、`legal_holds`、`retention_*`、`deletion_*`、`dsr_cases` |
| §7.8 审计 | Task 3、Task 6 | `audit_events`、`privacy_audit_events` |
| §8.2 PG0 | Task 14 | 控制台、CI 与验收门禁 |
| §8.2 控制台路由 | Task 11A、C14 | §5 的 11 条页面路由（10 启用、1 禁用）、4 条一级导航、`page_routes` 与 `primary_nav` 机器投影 |
| §10 风险与非承诺 | Task 11 | 契约正文限制与 gap |
| §11 实施规划输入 | 本计划 | C2-C14 账本 |

### Placeholder 扫描

计划的占位符扫描必须通过。
每个代码步骤给出实际代码或实际 JSON。
每个测试步骤给出实际断言。
每个 commit 步骤给出实际命令。

### 类型一致性

- 表名、列名、枚举名在 Task 2-7 与 Task 11-13 使用同一拼写。
- `claim_evidence.role` 与 `claim_status` 分离。
- `runs.outcome` 与 `run_steps.outcome` 使用同一四值。
- `health_status` 的 `degraded` 不进入 `runs.status`。
- `settle` 正数、`release` 负数在 Task 7、Task 12、Task 13 三处一致。
- `customer_mcp.schema.json` 的 17 个 `$defs`（含 `TargetPriceBand`）与八个工具的 `input_ref`/`output_ref` 一致。
- `report_contract.schema.json` 的 29 个必填键与 PRD §5.5.1 一致。
- 唯一报告合同 schema 是 `apps/api/schemas/report_contract.schema.json`；`configs/contracts/v1.1.0/` 下不得出现第二份报告合同 schema。
- canonical 常量只有一组：`CANONICAL_PROFILE_ID = "dih-canonical-json-v1"`、`CANONICAL_PROFILE = CANONICAL_PROFILE_ID`、`SCHEMA_VERSION = "1.1.0"`。C7、C9、C10 只 import，不重复定义。
- `tool_prices` 是正式 C5 表，完整列、约束与索引登记在 `tables`，并进入 `phases[].objects`；`mcp_customer_request_leases` 只在 `deferred` 中，不出现在 `tables` 或 `phases[].objects`。
- `report_artifacts.delivery_status` 与 `report_artifacts.status` 是两套枚举：前者 `pending/delivered/superseded`，后者 `draft/published/superseded`。
- 审计动作只有一份注册表 `audit_actions`（`audit-actions.v1`），`audit_events` 是唯一审计表；`report_reviewer_assignments.expires_at` 非空与 `reviewer_assignment_expired` 在 Task 5、Task 8、Task 11 三处一致；不得新增客户 `reviewer` 角色。
- `authorizations` 的唯一键是 `(run_id, gate_id)` 部分唯一索引 `uq_authorizations_run_gate`，不是 `run_id` 单列唯一。
- C11 的 `workspace_pseudonym_salts`、`legal_holds`、`retention_cleanup_runs`、`retention_tombstones` 与迁移 069 使用同一组列名、约束名与索引名；`uq_legal_holds_active_target`、`target_type`、`target_id`、`authority` 不得出现。
- MFA 不在 PG0：无 `mfa_required`、无 `require_recent_mfa`。
- `workbench_tasks.seed_products`、`target_price_band`、`idempotency_key_hash` 与 `uq_workbench_tasks_workspace_idempotency` 只登记一次，列名与 C4 迁移 `202610220062` 一致；不新增 `request_hash` 第二摘要列，不新增第二个 C4 迁移。
- `workbench.tasks.create` 的 `idempotency` 对象必须同时满足 `idempotent: true` 且 `conflict_error` 在路径 `error_codes` 中；checker 拒绝任一不满足。
- 页面路由只有契约 §5 一份：附录 A 的 `page_routes` 与 `primary_nav` 是机器投影，`paths` 只存 API 路径；`[toolId]`、`[artifactId]`、`[taskId]`、`[id]` 段名在 §5、`page_routes` 与 C14 `CONTRACT_ROUTES` 三处一致。C14 不维护第二份清单。
- `CreateTaskInput` 的 `compare_markets` 只映射到 `comparison_markets`；`seed_products` 与 `target_price_band` 原样映射；`budget.*` 展开为同名列；不得出现第二套字段名。

---

## 审查摘要（2026-10-22 修订）

| 审查项 | 级别 | 处理 | 落点 |
|---|---|---:|---|
| 没有分支/worktree 起点 | P0 | 从 `pg0-baseline-v1` 创建 `feat/gov-c1`；断言 tag、Alembic 057、B5 祖先。 | Global、Task 1 Step 0 |
| 最终 diff 基线错误 | P0 | `f0560ca..HEAD` 改为 `pg0-baseline-v1..HEAD`。 | Task 15 Step 7/8 |
| `tool_prices` 定价表登记 | P0 | `tool_prices` 从 `deferred` 改为正式 C5 表：登记 13 列、5 个约束、2 个索引与 `phases[].objects`。 | Task 2、Task 7、Task 11 |
| `mcp_customer_request_leases` 幽灵表 | P0 | 删除表、测试与 phase 对象；登记到 `deferred`，C13 不建表。 | Task 6、Task 11 |
| 报告 schema 分叉 B5 | P0 | 删除 `configs/contracts/v1.1.0/report_contract.schema.json`；只升级 `apps/api/schemas/report_contract.schema.json`。 | File Structure、Task 9 |
| 缺 canonical 常量 | P0 | 在 B5 `schemas/report_contract.py` 导出三个常量；`SCHEMA_VERSION=1.1.0`。 | Global、Task 9 Step 4A |
| 凭据路径重复 | P0 | 删除 `platform_credentials.list/write`；登记 `credentials.list/update/delete` 三条规范路径。 | Task 8 |
| C1/C2 契约章节冲突 | P0 | 错误信封并入 C1 §4.6；C2 只读；补 `workspace_owner_required`、`workspace_role_invalid`。 | Task 8、Task 11 |
| MFA 无实现者 | P0 | PG0 延期 MFA；删除错误码、路径错误与 `require_recent_mfa` 文本。 | Global、Task 8、Task 11 |
| 早期边界表非权威 | P1 | 标注“非权威”，以 master plan 为准；移除幽灵表。 | C2-C14 工作包边界 |
| 最终提交信息不匹配 | P2 | 改为 `docs(contract): finalize v1.1 registry and review evidence`。 | Task 15 Step 9 |
| 契约计数随表登记重算 | P2 | 测试总数改为 69；表、枚举、路径随登记项更新。 | 各 Task 与 Self-Review |
| C4 PATCH/gates、C5 quota、C6 run_steps 未登记 | P0 | 增加 4 条路径、`run_steps` 扩展列、C6 attempt 精确列与错误码。 | Task 2、Task 8、Task 11 |
| C8 质量列未登记 | P0 | 增加 `data_gaps.step_id/resolved_at` 与 `market_assessments.market_role/conclusion_*/evidence_grade`。 | Task 4 |
| C10 发布路径遮蔽 C9 | P0 | 交付发布改为 `/api/reports/{artifact_id}/delivery/publish`；只保留 `report_review_approved`。 | Task 8、Task 11 |
| PRD/Playbook 枚举冲突 | P0 | PRD 改用 C7 的 claim 枚举与 `source_cluster_key`；Playbook 市场质量与账本符号同步。 | Task 12、Task 13 |
| C10 交付字段未登记 | P0 | `report_artifacts` 增加 `delivered_at`、`delivered_by`、`supersedes_delivery_id`；交付列与默认值写入 registry。 | Task 5 Step 1/3、§3.7 |
| 交付状态枚举错复用 C9 | P0 | `report_artifacts.delivery_status` 改为 `pending/delivered/superseded`；`ck_report_artifacts_delivery_status` 与 `ck_report_artifacts_delivery_fields` 登记到 registry 与正文。 | Task 5 Step 1/3、Task 7、§3.7 |
| C9 发布约束未登记 | P0 | 登记 `ck_report_artifacts_status`、`uq_report_artifacts_current_published`（部分唯一，`status = 'published'`）与发布幂等部分唯一索引。 | Task 5 Step 1/3、§3.7 |
| 审核 metadata 缺 `reviewer_role` | P0 | `report_audit_events.metadata_json` 的 notes 登记 `reviewer_role` 与 `reviewed_*` 五个摘要键；正文同步。 | Task 5 Step 1/3、§3.7 |
| C8 表所有权不清 | P0 | 增加“C8 实现决定”：C8 是 `market_assessments` 与 `data_gaps` 的唯一创建者，在迁移 `066` 创建；不建 `task_templates` 表。 | Task 4 Interfaces、Step 3A、§6A |
| C11 三表约束与计划冲突 | P0 | `workspace_pseudonym_salts`、`legal_holds`、`retention_cleanup_runs` 按 C11 迁移 069 对齐列、约束与索引；删除 `uq_legal_holds_active_target` 与 `target_type/target_id/authority`。 | Task 6 Step 1/3 |
| `authorizations` 唯一键错误 | P0 | 改为 `(run_id, gate_id)` 部分唯一 `uq_authorizations_run_gate`，条件 `run_id IS NOT NULL`；index schema 增加可选 `where`。 | Task 1 schema、Task 2 Step 1/3 |
| 幽灵表复发风险 | P0 | `mcp_customer_request_leases` 保持只在 `deferred`，不出现在 `tables`/`phases[].objects`；`tool_prices` 只以正式 C5 表出现；C8 不建 `task_templates`。 | Global、Task 2、Task 4、Task 6、Task 11 |
| C9/C10 新字段未覆盖 registry 测试与正文 | P0 | 扩展 Task 5 交付列/约束断言与 Task 7 枚举断言；§3.7 同步交付列、交付约束与审核 metadata。 | Task 5、Task 7、§3.7 |
| 包型与市场角色持久化缺失 | P0 | `workbench_tasks` 登记 `package_type`、`primary_market`、`comparison_markets`、`acceptance_contact_id`（owner/admin）、`max_cost_usd/max_pages/max_records`、`seed_products`、`target_price_band`、`idempotency_key_hash` 与 `uq_workbench_tasks_workspace_idempotency`；`runs` 只保留 `market_code`，不登记 `market_role`/`package_type`；Quick 最多 1 个对比市场，Standard 最多 3 个。 | Task 2、Task 7、Task 8、Task 11 |
| C4 创建幂等与初始版本接缝未登记 | P0 | 登记 `workbench.tasks.create` 的 `Idempotency-Key` 必填、`Idempotent-Replay`、409 `idempotency_conflict` 与 `idempotency_key_hash` 部分唯一索引；登记 `workflow_versions.workbench_task_id` 复合外键、`plan_payload.execution_steps` 不可变快照与 `create_initial_workflow_version_for_task` 接缝；全部对象归入迁移 `202610220062`，C1 不新增迁移。 | Task 2、Task 8、Task 9、Task 11、Task 12 |
| C4 种子商品/价格带/验收联系人规则缺失 | P0 | `seed_products` 3–10 项、`target_price_band` 原币边界规则、`acceptance_contact_id` owner/admin 与空值回落 owner 写入 registry notes、正文、`CreateTaskInput` 与 PRD；`acceptance_contact_not_member` 含义改为非 owner/admin。 | Task 2、Task 8、Task 9、Task 11、Task 12 |
| 发布与浏览器边界未声明 | P0 | Global Constraints 写明本切片不直接部署、A/B 发布由 PG0 发布批次执行、C14 只做只读验收、浏览器交接无。 | Global Constraints |
| C2 消费者契约缺口 | P0 | 登记 `report_reviewer_assignments.expires_at`（非空）、`reviewer_assignment_expired`（403）、审阅者读/审核路径错误码、版本化审计动作注册表 `audit-actions.v1`（68 动作）与 `audit_action_unregistered`（500）；不新增第二张审计表，不新增客户 `reviewer` 角色。 | Global、Task 1、Task 5、Task 8、Task 11、Task 14 |
| C6/C8/C9/C10 修复前置未登记 | P0 | 登记 `runs.cancel_idempotency_key_hash`、`runs.cancel_reason_code` 与 `uq_runs_workspace_cancel_idempotency`（迁移 064）；登记 `runs.cancel`、`RunCancellationResult` 接缝与 `invalid_request`/`idempotency_conflict`/`state_conflict`；登记 `TaskTemplate.capability_allowlist`、`template_capability_ids()` 与 `template_registry_digest()` 代码画像；登记 `report_artifacts.delivery_class`、`acceptance_deadline`、`quick_draft_of_artifact_id`（迁移 068）；登记验收三种事件、四条路径与 `metadata_json` 幂等语义；登记唯一 `export_policy.v1` 扫描画像与 `delivery_pii_detected`；C1 不新增迁移。 | Global、Task 1、Task 2、Task 5、Task 8、Task 14A |

验证命令（在 `/Users/lute/Project/data_scrapy-gov-c1` 执行，确认字段已登记）：

```bash
cd /Users/lute/Project/data_scrapy-gov-c1
rg -n "delivered_at|delivered_by|supersedes_delivery_id|ck_report_artifacts_delivery_status|ck_report_artifacts_delivery_fields" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "ck_report_artifacts_status|uq_report_artifacts_current_published|reviewer_role|pending.*delivered.*superseded" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "uq_authorizations_run_gate|uq_workspace_pseudonym_salts_workspace_id|ck_legal_holds_release_fields|ck_retention_cleanup_runs_status" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "task_templates|唯一创建者|迁移 066" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n '"name": "tool_prices"|uq_tool_prices_tool_currency_version|ix_tool_prices_tool_effective|table:tool_prices' docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "requested_by_user_id|requested_at|released_by_user_id|released_at|release_reason|finished_at" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "seed_products|target_price_band|idempotency_key_hash|uq_workbench_tasks_workspace_idempotency" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "Idempotency-Key|Idempotent-Replay|idempotency_conflict|conflict_error" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "create_initial_workflow_version_for_task|workbench_task_id|plan_payload|execution_steps" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "202610220062|202610220061" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "reviewer_assignment_expired|audit-actions\\.v1|audit_action_unregistered|审计动作注册表" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n '"name": "report_reviewer_assignments"|"name": "expires_at"|"audit_actions"' docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "cancel_idempotency_key_hash|cancel_reason_code|uq_runs_workspace_cancel_idempotency|runs.cancel" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "template_capability_ids|template_registry_digest|dih-template-capability-v1|capability_not_allowed" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "delivery_class|acceptance_deadline|quick_draft_of_artifact_id|acceptance_accepted|acceptance_disputed|acceptance_deemed_accepted|acceptance_not_applicable" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "export_policy.v1|scan_export_policy|delivery_pii_detected|report_publish_gate_blocked" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
rg -n "page_routes|primary_nav|page_route:|primary_nav:" docs/superpowers/plans/2026-10-22-governed-task-platform-c1-contract-v1-1.md
```


自检结论：占位符扫描已通过。所有 commit 前置 `detect-changes`；C1 不建迁移。

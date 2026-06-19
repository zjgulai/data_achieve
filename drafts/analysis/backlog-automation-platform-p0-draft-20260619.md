---
title: 自动化数据采集工作台 P0 Backlog
doc_type: backlog
module: automation
topic: automation-platform-p0
status: draft
created: 2026-06-19
updated: 2026-06-19
owner: self
source: human+ai
---

# 自动化数据采集工作台 P0 Backlog

## 1. 目标

P0 的目标是把当前 `/automation` 从“可运行流程”升级为“可运营资产系统”。

完成 P0 后，用户应能：

1. 分析一个授权 URL。
2. 保存站点分析历史。
3. 从历史分析创建采集计划。
4. 保存并版本化字段选择、采集策略和清洗规则。
5. 基于计划运行采集、保存 Dataset、导出文件。
6. 对长期任务做漂移监控、告警和重复动作保护。

## 2. P0-1：ExtractionPlan 持久化

### 问题

当前 SiteAnalysis、FieldCandidate 和 ExtractionPlan 主要存在于 API response、Source config 和前端状态中。刷新页面后，用户无法把一次分析作为长期资产复用。

### 建议实现

后端：

1. 新增 `site_analyses` 模型。
2. 新增 `field_candidates` 模型，或先作为 `site_analyses.analysis_payload` 的 JSONB 子结构保存。
3. 新增 `extraction_plans` 模型。
4. 新增 migration。
5. 新增 repository：`apps/api/src/data_intelligence_hub/repositories/automation_plans.py`。
6. 扩展 service：`apps/api/src/data_intelligence_hub/services/automation_service.py`。
7. 扩展 schema：`apps/api/src/data_intelligence_hub/schemas/automation.py`。
8. 扩展 route：`apps/api/src/data_intelligence_hub/api/routes/automation.py`。

前端：

1. `/automation` 增加“历史分析”列表。
2. 支持从历史分析恢复字段候选和 source draft。
3. 支持复制为新计划。

测试：

1. API 集成测试：分析 URL -> 保存历史 -> 查询历史 -> 创建计划。
2. Web E2E：刷新页面后仍可看到历史分析并继续创建计划。

验收：

1. `site_analysis_created=true`。
2. `extraction_plan_created=true`。
3. 页面刷新后历史分析仍存在。
4. 不启动真实采集时必须标记 `run_started=false`。

## 3. P0-2：CleaningPlan 持久化和 dry-run

### 问题

当前清洗规则主要体现在 DatasetVersion 的 `cleaning_script` 字段中，还不是可复用、可审计、可 dry-run 的资产。

### 建议实现

后端：

1. 新增 `cleaning_plans` 模型。
2. 支持字段类型、主键、默认值、格式化、去重规则。
3. 新增 dry-run API，对样本 rows 输出 before/after。
4. DatasetVersion 增加 CleaningPlan 追踪字段，或先在 `export_preview`/audit_events 中保留 plan id 与版本。

前端：

1. `/automation` 或 `/datasets` 增加清洗规则编辑区。
2. 展示 dry-run 前后对比。
3. 保存 Dataset 前要求用户确认清洗规则。

测试：

1. 单元测试：类型转换、默认值、去重主键、异常值处理。
2. API 测试：dry-run 不写入 DatasetVersion。
3. E2E：编辑规则 -> dry-run -> 确认 -> 保存 DatasetVersion。

验收：

1. dry-run 不产生生产写入。
2. CleaningPlan 版本可回溯。
3. DatasetVersion 能明确追踪清洗规则来源。
4. AI 只能生成草案，不能自动确认正式规则。

## 4. P0-3：Platform Package 模板化

### 问题

当前 `ecommerce_product_page` 和 `ecommerce_product_discovery` 已经可用，但“平台包”还没有正式抽象。继续增加 Amazon、社媒或 GitHub/API-first 时会复制临时逻辑。

### 建议实现

后端：

1. 新增 PlatformPackage contract。
2. 定义平台包字段：`id`、`name`、`category`、`supported_targets`、`collector_types`、`field_schema`、`strategy_matrix`、`risk_boundaries`、`sop_links`。
3. Shopify-style 独立站作为第一个平台包。
4. GitHub/API-first 作为第二个平台包候选。

前端：

1. 新增或扩展平台包入口。
2. 平台包页面展示适用场景、字段 schema、推荐策略、风险边界和启动采集入口。

测试：

1. 平台包 contract 单元测试。
2. 页面 E2E：打开平台包 -> 选择策略 -> 进入 automation。

验收：

1. 每个平台包必须指向可执行采集路径或明确标记为 SOP/import-only。
2. 高风险平台不得默认启动自动抓取。
3. 每个平台包必须有 fixture 或可审计样例。

## 5. P0-4：调度、告警和重复动作保护

### 问题

当前自动采集链路已有调度审批、漂移检查和告警链路，但重复点击、重复规则、重复运行和失败状态解释还需要硬化。

### 建议实现

后端：

1. AlertRule 创建增加幂等键。
2. Drift Alert Event 创建增加重复事件保护。
3. TaskRun 增加运行锁或短窗口重复运行保护。
4. 标准化失败原因：`blocked`、`validation_failed`、`collector_failed`、`timeout`、`rate_limited`。

前端：

1. 写入按钮提交中禁用。
2. 重复请求返回已存在资源时展示“已存在，可继续使用”。
3. Task 失败时展示下一步建议。

测试：

1. API 测试：重复创建同一漂移告警规则不会产生多条规则。
2. E2E：连续点击创建按钮只产生一个结果。
3. 集成测试：并发或短窗口重复运行不会产生互相覆盖的状态。

验收：

1. 重复点击不会产生重复任务、重复规则或重复事件。
2. 失败状态可解释。
3. 所有写入接口保留 `authorized` / `confirm_*` 边界。

## 6. 执行顺序

推荐顺序：

1. P0-1 ExtractionPlan 持久化。
2. P0-2 CleaningPlan dry-run。
3. P0-4 重复动作保护。
4. P0-3 Platform Package 模板化。

理由：

1. 先把计划和清洗规则资产化，才能支撑平台包扩展。
2. 重复动作保护需要基于新增 plan id、rule id 和状态机一起设计。
3. 平台包模板化最后做，可以把前面形成的 plan/cleaning 能力纳入统一 contract。

## 7. 验收证据要求

每一项 P0 完成时必须分层报告：

1. `docs-only`：文档、backlog 或 contract 更新。
2. `local unit`：本地单元测试。
3. `local integration`：API 集成测试。
4. `local web e2e`：浏览器或 Playwright E2E。
5. `production read-only`：生产只读 smoke。
6. `authorized production e2e`：授权生产写入测试。
7. `cleanup dry-run / execute / dry-run-zero`：真实 E2E 数据清理闭环。

本文件本身只是 backlog，不代表任何运行时代码已完成。

## 8. 执行记录

### 2026-06-19 P0-1 本地实现记录

事实：

1. 已新增 `site_analyses` 与 `extraction_plans` 持久化模型、repository、schema、route、migration。
2. `/api/automation/site-analysis` 在传入 `project_id` 时会保存站点分析历史并创建默认 `ExtractionPlan v1`。
3. 已新增历史列表、历史详情与从历史分析创建新版 extraction plan 的 API。
4. `/automation` 已接入项目归档选择、历史分析列表和采集计划保存状态展示。
5. E2E fixture cleanup 已覆盖 `site_analyses` 与 `extraction_plans`。

本地验收：

1. `uv run pytest tests/integration/test_sources_tasks.py::test_automation_site_analysis_persists_history_and_extraction_plan tests/unit/test_automation_service.py tests/unit/test_e2e_cleanup.py -q` 通过。
2. `pnpm --dir apps/web exec tsc --noEmit` 通过。
3. `bash scripts/verify-mvp.sh` 通过：API 90 passed，Web Playwright 32 passed / 8 skipped。

边界：

1. `production unchanged`：本记录不代表生产环境已部署或生产数据库已执行 migration。
2. 生产 read-only smoke、授权生产写入 E2E、生产 E2E fixture cleanup 尚未执行。
3. P0-2 CleaningPlan 持久化和 dry-run 仍是下一轮未完成任务。

### 2026-06-19 P0-2 本地实现记录

事实：

1. 已新增 `cleaning_plans` 持久化模型、repository、schema、route、migration。
2. 已新增 `/api/automation/cleaning-plan-dry-run`，可对 TaskRun 聚合样本执行清洗规则 dry-run。
3. 已新增 `/api/automation/cleaning-plans` 创建与列表接口。
4. `DatasetVersion` 已新增可选 `cleaning_plan_id`，保存 DatasetVersion 时可追踪 CleaningPlan。
5. `/automation` 已接入默认清洗规则、dry-run、保存 CleaningPlan、保存 Dataset 时使用 CleaningPlan 的前端操作链路。
6. E2E fixture cleanup 已覆盖 `cleaning_plans`。

本地验收：

1. RED：`uv run pytest tests/integration/test_sources_tasks.py::test_automation_product_batch_run_returns_field_completeness -q` 先失败于 `/api/automation/cleaning-plan-dry-run` 返回 404。
2. GREEN：同一测试后续通过，并验证 dry-run 不创建 DatasetVersion、CleaningPlan 保存、DatasetVersion 追踪 `cleaning_plan_id`。
3. `uv run pytest tests/integration/test_sources_tasks.py tests/unit/test_e2e_cleanup.py -q` 通过：15 passed。
4. `pnpm --dir apps/web exec tsc --noEmit`、`pnpm lint:web`、`pnpm test:web` 通过。
5. `bash scripts/verify-mvp.sh` 通过：API 90 passed，Alembic head `202606110020`，Web Playwright 32 passed / 8 skipped。
6. PostgreSQL migration 已通过显式连接验证：`DATABASE_URL=postgresql+psycopg://data_intel:dev_password@localhost:55432/data_intel uv run alembic upgrade head` 跑到 `202606110020`。

边界：

1. `production unchanged`：本记录不代表生产环境已部署或生产数据库已执行 migration。
2. `bash scripts/verify-mvp.sh --with-db` 首次被本机 `5432` 端口占用阻断；改用 `POSTGRES_PORT=55432` 后 full script 的 Alembic 阶段仍需显式 `DATABASE_URL`，因此最终 DB migration 证据来自单独的 Alembic 命令。
3. 生产 read-only smoke、授权生产写入 E2E、生产 E2E fixture cleanup 尚未执行。
4. P0-4 重复动作保护仍是下一轮未完成任务。

### 2026-06-19 P0-4 本地实现记录

事实：

1. `DatasetDriftEvent` 保存已增加幂等 fingerprint；相同 dataset、version、task_ids、thresholds、summary、items、note 的重复请求会复用已有 DriftEvent。
2. 重复保存 DriftEvent 时不会创建新 DriftEvent，会在原事件 `audit_events` 中追加 `product_drift_event_reused`，并保持 `run_started=false`、`alert_created=false`。
3. `create_product_drift_alert_rule` 已按 project、signal_type、condition、channel、enabled 复用既有 Drift AlertRule；重复创建同一策略不会产生第二条 AlertRule。
4. TaskRun 失败日志已增加标准化 `failure_reason`，当前覆盖 `validation_failed`、`collector_failed`、`timeout`、`rate_limited`，同时保留原有 `error_message`。
5. 既有 Drift AlertEvent、Signal、Notification 去重测试继续保留，重复桥接/通知不会重复写入。

本地验收：

1. RED：`uv run pytest tests/integration/test_sources_tasks.py::test_automation_product_batch_run_returns_field_completeness -q` 先失败于重复 DriftEvent 返回了新的 UUID。
2. GREEN：同一测试后续通过，并验证重复 DriftEvent 复用原 ID、重复 AlertRule 复用原 ID、AlertRule 列表仍只有 1 条。
3. `uv run pytest tests/integration/test_sources_tasks.py::test_automation_product_batch_run_returns_field_completeness tests/integration/test_sources_tasks.py::test_collector_exception_persists_failed_task_run -q` 通过：2 passed。
4. `uv run ruff check src tests/integration/test_sources_tasks.py` 通过。
5. `uv run mypy src` 通过。
6. `bash scripts/verify-mvp.sh` 通过：API 90 passed，Alembic head `202606110020`，Web Playwright 32 passed / 8 skipped。

边界：

1. `production unchanged`：本记录不代表生产环境已部署或生产数据库已执行 migration。
2. 本轮未改前端按钮提交中禁用状态；当前验收重点是后端重复写入保护和失败原因分类。
3. 生产 read-only smoke、授权生产写入 E2E、生产 E2E fixture cleanup 尚未执行。
4. 下一轮建议进入 P0-3 Platform Package 模板化，或先做生产部署前的 migration/production read-only smoke 计划。

### 2026-06-19 P0-3 本地实现记录

事实：

1. 已新增 PlatformPackage contract schema，覆盖 `id`、`name`、`category`、`supported_targets`、`collector_types`、`field_schema`、`strategy_matrix`、`risk_boundaries`、`sop_links`、`sample_fixture`、`execution_boundary`。
2. 已新增 `/api/automation/platform-packages` 和 `/api/automation/platform-packages/{package_id}`。
3. 首批平台包包含 `shopify-independent-ecommerce` 和 `github-api-first`。
4. `shopify-independent-ecommerce` 标记为 `executable`，指向 `ecommerce_product_discovery` 与 `ecommerce_product_page`。
5. `github-api-first` 标记为 `sop_import_only`，指向 `github_topic` 与 `github_repo`，不允许从 Automation 默认启动。
6. `/automation` 已新增“平台包矩阵”，展示字段 contract、collector、策略、风险边界和 SOP links；可执行平台包支持一键应用到当前采集入口。
7. Mock API 已同步平台包数据，保证本地 E2E 和真实 API contract 不分叉。

本地验收：

1. RED：`uv run pytest tests/integration/test_sources_tasks.py::test_automation_platform_packages_expose_collection_contract -q` 先失败于 `/api/automation/platform-packages` 返回 404。
2. GREEN：同一测试后续通过，验证两个平台包 contract、执行边界、风险边界、fixture 和详情 404。
3. RED：`pnpm --dir apps/web exec playwright test tests/e2e/main-flows.spec.ts -g "renders automation platform packages"` 先失败于页面缺少“平台包矩阵”。
4. GREEN：同一 E2E 后续通过：desktop/mobile 2 passed。
5. 回归修复：完整 E2E 首次发现平台包字段展示与 Dataset 字段按钮重名，已将平台包字段 chip 改为非按钮文本。
6. `pnpm --dir apps/web exec playwright test tests/e2e/main-flows.spec.ts -g "runs automation workbench|renders automation platform packages"` 通过：4 passed。
7. `bash scripts/verify-mvp.sh` 通过：API 91 passed，Alembic head `202606110020`，Web Playwright 34 passed / 8 skipped。

边界：

1. `production unchanged`：本记录不代表生产环境已部署或生产数据库已执行 migration。
2. 平台包目前是静态 contract registry；尚未支持用户自定义平台包持久化。
3. GitHub/API-first 仍是 SOP/import-only，不代表已经进入 Automation 一键运行链路。
4. 生产 read-only smoke、授权生产写入 E2E、生产 E2E fixture cleanup 尚未执行。

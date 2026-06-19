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

状态说明：第 2 至第 7 节保留原始 P0 计划语义，用于追溯为什么做这些任务；当前完成状态和验收事实以第 8 节执行记录为准。

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

### 2026-06-19 Phase B.1 GitHub 工具数据集本地实现记录

事实：

1. 已新增 `/api/automation/github-tool-dataset-preview`，可从 `github_topic` / `github_repo` 运行记录生成工具情报 Dataset 预览。
2. 已新增 `/api/automation/github-tool-dataset-save`，保存 `dataset_type=github_tool_radar` 的 DatasetVersion。
3. GitHub topic collector 已补齐 `open_issues_count`、`language`、`topics`、`pushed_at` 等工具情报字段。
4. `/automation` 的 GitHub Topic Radar 结果区已新增工具数据集字段筛选、预览和保存交互。
5. CSV/JSON/JSONL 导出复用现有 Dataset Export API；本轮 API 集成测试已覆盖 CSV 导出和下载。

本地验收：

1. RED：`uv run pytest tests/integration/test_sources_tasks.py::test_github_topic_radar_saves_tool_dataset_and_export -q` 先失败于 `/api/automation/github-tool-dataset-preview` 返回 404。
2. GREEN：同一测试后续通过，并验证 GitHub topic fixture -> 工具 Dataset 预览 -> 保存 `github_tool_radar` DatasetVersion -> CSV 导出下载。
3. `uv run pytest tests/integration/test_sources_tasks.py::test_github_topic_radar_saves_tool_dataset_and_export tests/integration/test_sources_tasks.py::test_automation_platform_packages_expose_collection_contract -q` 通过：2 passed。
4. `uv run ruff check src tests/integration/test_sources_tasks.py` 通过。
5. `uv run mypy src` 通过。
6. `pnpm --dir apps/web exec tsc --noEmit` 通过。
7. `pnpm --dir apps/web exec playwright test tests/e2e/main-flows.spec.ts -g "renders automation platform packages"` 通过：desktop/mobile 2 passed。

边界：

1. `production unchanged`：本记录不代表生产环境已部署。
2. 本轮完成 GitHub 工具 Dataset 预览、保存和导出 API 验证；工具漂移检查、策略推荐回流和工具雷达报告仍是 Phase B 下一切片。
3. 导出 endpoint 仍复用历史 `product-dataset-exports` 命名；底层按 Dataset/Version 权限工作，后续可补无破坏 alias。

### 2026-06-19 Phase B.2 GitHub 工具漂移与雷达报告本地实现记录

事实：

1. 已新增 `/api/automation/github-tool-drift-check`，对 `github_tool_radar` 数据集做同源 GitHub task 的只读漂移检查。
2. 已新增 `/api/automation/github-tool-drift-events`，保存 `event_type=github_tool_radar_drift` 的 DatasetDriftEvent，并复用 fingerprint 避免重复快照。
3. 已新增 `/api/automation/github-tool-report`，基于已保存 DatasetVersion 汇总仓库数、stars、语言、topics、高价值仓库和培训建议。
4. 已新增 `/api/automation/github-tool-report-assets`，在 `confirm_create=true` 时保存 `report_type=github_tool_radar` 的 Report 中心资产。
4. `/automation` GitHub Topic Radar 结果区在保存工具数据集后，可生成雷达报告、检查工具漂移、保存漂移快照。

本地验收：

1. RED：`uv run pytest tests/integration/test_sources_tasks.py::test_github_topic_radar_saves_tool_dataset_and_export -q` 先失败于 `/api/automation/github-tool-drift-check` 返回 404。
2. GREEN：同一测试后续通过，并验证 GitHub 工具 Dataset -> 二次运行 -> 漂移检查 -> 保存 `github_tool_radar_drift` -> 生成工具雷达报告。
3. `uv run pytest tests/integration/test_sources_tasks.py::test_github_topic_radar_saves_tool_dataset_and_export tests/integration/test_sources_tasks.py::test_automation_product_batch_run_returns_field_completeness -q` 通过：2 passed。
4. `uv run ruff check src tests/integration/test_sources_tasks.py` 通过。
5. `uv run mypy src` 通过。
6. `pnpm --dir apps/web exec tsc --noEmit` 通过。
7. `pnpm lint:web` 通过。
8. `pnpm --dir apps/web exec playwright test tests/e2e/main-flows.spec.ts -g "renders automation platform packages"` 通过：desktop/mobile 2 passed。

边界：

1. `production unchanged`：本记录不代表生产环境已部署。
2. GitHub 工具漂移和报告均为只读评估；不会启动采集、创建告警或发送通知。
3. `github-tool-report-assets` 只写 Report 资产和 report audit event；不会启动采集、创建站内通知或发送邮件。

### 2026-06-19 Phase B.3 GitHub 工具雷达报告中心资产本地实现记录

目标：把 GitHub 工具雷达从只读 response 推进为可在 Report 中心查看的持久化资产，同时保持发送、通知、采集运行全部 fail-closed。

实现：

1. 新增 `AutomationGitHubToolReportAssetCreateRequest` / `AutomationGitHubToolReportAssetResponse`。
2. 新增 `/api/automation/github-tool-report-assets`，要求 `authorized=true` 和 `confirm_create=true`。
3. 新增 `create_github_tool_report_asset`，复用只读报告汇总后创建 `reports.report_type=github_tool_radar`，并写入 `github_tool_report_asset_created` audit event。
4. 前端 `/automation` 在 GitHub Topic Radar 结果中新增“保存到报告中心”按钮，保存后展示 `/reports/{reportId}` 入口。
5. `github_tool_radar` 被纳入前端培训报告类型判断，Report 中心训练视角可识别该类报告。

验收证据：

1. RED：目标 integration test 先失败在 `/api/automation/github-tool-report-assets` 返回 `404`。
2. GREEN：同一测试后续通过，验证 report asset 创建、Report API 读回、报告列表包含 `github_tool_radar`。
3. 前端目标 Playwright 覆盖桌面和移动，从 Topic Radar 到保存报告中心，断言“已保存到报告中心”和“打开报告”入口出现。

边界：

1. 本轮为本地实现与本地验收，生产未部署。
2. Report 资产保存不会启动采集、创建通知或发送邮件。

### 2026-06-19 工具雷达 Report 资产部署与生产验收记录

事实：

1. 该轮生产部署 commit：`20c4bd252bbf85cac0a7d68acaa199e087e6fa05`。
2. 生产运行目录：`/opt/data-achieve-scrapy/app`，该轮部署完成时 HEAD 为 `20c4bd2`。
3. `/api/automation/platform-packages` 在生产返回 3 个平台包：`shopify-independent-ecommerce`、`github-api-first`、`public-page-structure-preflight`。
4. `github-api-first` 已升级为 `executable`，可从 `/automation` 创建 GitHub topic Source、启用 Task，并执行一次公开 GitHub API 采集。
5. `public-page-structure-preflight` 已作为 `executable` 平台包上线，可从 `/automation` 调用公开网页结构预检；授权通过后可继续创建 `generic_web` 采集源。
6. GitHub 工具雷达 Dataset 已可进入导出、漂移检查和只读报告链路，并可保存为 `report_type=github_tool_radar` 的 Report 中心资产。

生产验收：

1. 生产 API smoke 通过。
2. 生产真实 API E2E 通过：Playwright `34 passed / 8 skipped`。
3. 生产健康检查返回 `status=ok`、`database=connected`、`schema_revision=202606110020`、`schema_head=202606110020`。
4. `/automation`、`/toolkit`、`/tasks`、`/datasets`、`/reports`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities` 页面 HTTP 检查均返回 200。
5. E2E fixture cleanup 与 demo-noise cleanup 已执行，后续 dry-run 计数为 0。
6. 2026-06-19 只读复核：`https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`。

边界：

1. 本记录覆盖下方 `db6189f` 历史基线中的 GitHub/API-first SOP-only 边界，也覆盖上一轮 `dda2786` 平台包部署记录；当前事实以本记录为准。
2. GitHub/API-first 当前可执行范围是 Topic Radar 的 Source/Task/Run、Dataset、导出、漂移、只读报告和 Report 资产链路；通知、邮件、自动采集调度仍保持 fail-closed。
3. 公开网页结构预检当前是授权 gate 和结构诊断，不实现登录绕过、反检测或风控规避。
4. 远程 GitHub fetch 曾遇到传输失败，本次部署先保存远程 dirty worktree 的 status、patch 与 stash，再通过 git bundle fast-forward 到 `20c4bd2`；该经验已写入自进化候选池。

### 2026-06-19 Phase C-1 结构预检采集路径建议部署记录

事实：

1. 最新生产部署 commit：`d9b2a5e35274963c1804d200824d5767d2f4ae3d`。
2. `/api/toolkit/preflight` 新增 `collection_strategy`，包含 `recommended_path`、`label`、`fit`、`confidence`、`field_stability`、`reasons`、`next_steps`、`cleaning_notes`。
3. `/automation` 的结构预检结果新增“采集路径建议”面板，展示推荐路径、适配度、字段稳定性、判断依据、下一步和清洗建议。
4. `/toolkit` 的授权 URL 预检报告同步展示同一策略字段。

验收证据：

1. 本地 `bash scripts/verify-mvp.sh` 通过：API `94 passed`，Web unit `1 passed`，Playwright `34 passed / 8 skipped`。
2. 生产 `https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`。
3. 生产 `/dashboard`、`/automation`、`/toolkit`、`/datasets`、`/reports`、`/tasks`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities` 页面 HTTP 检查均返回 200。
4. 生产只读 preflight smoke 返回 `recommended_path=generic_web`、`fit=high`、`field_stability=medium`、`run_started=false`。
5. 生产真实 API E2E 通过：Playwright `34 passed / 8 skipped`。
6. E2E fixture cleanup 已执行，清理后 dry-run 全部计数为 0。

边界：

1. 本轮新增的是结构诊断和策略建议，不执行登录绕过、反检测或风控规避。
2. 生产只读 preflight smoke 使用登录态调用授权公开 URL 预检，不创建 Source、Task、Run、Dataset 或 Report。
3. 真实 API E2E 产生的一次性测试数据已通过 cleanup 脚本清理。

### 2026-06-19 P0 生产部署与真实浏览器验收记录（历史基线：db6189f）

事实：

1. P0-1 `ExtractionPlan` 持久化、P0-2 清洗计划持久化和试跑、P0-3 Platform Package 模板化、P0-4 重复动作基础保护已合入并部署到生产。
2. 生产部署 commit：`db6189faea4cf4b400d711162f43bdf928d5e938`。
3. 生产站点：`https://scrapy.lute-tlz-dddd.top`。
4. 真实 Chrome + browser-harness 已验证 `/automation` 主链路：应用平台包、商品发现、fan-out 预览、创建采集源/任务、批量运行、数据集预览、清洗规则试跑。
5. UI 文案已完成核心链路去调试化：面向用户页面不再把 `dry-run`、`CleaningPlan`、`DatasetVersion`、`Source/Task` 作为核心操作文案。

生产验收：

1. `bash scripts/verify-mvp.sh`：API `91 passed`，Web build 通过，Playwright `34 passed / 8 skipped`。
2. 生产 API smoke 通过。
3. 生产真实 API E2E：`14 passed / 7 skipped`。
4. 真实浏览器 E2E 通过，截图证据：`/tmp/data-scrapy-prod-db6189f-automation-cleaning-trial.png`。
5. E2E fixture cleanup 已执行，后续清理试跑计数为 0。
6. 本轮只读复核：`GET https://scrapy.lute-tlz-dddd.top/api/health` 返回 `status=ok`、`database=connected`、`schema_revision=202606110020`、`schema_head=202606110020`。

边界：

1. 本节覆盖下方各“本地实现记录”中的 `production unchanged` 历史边界；那些边界只描述当时提交前状态。
2. 平台包仍处于首批静态 contract registry 阶段，尚未支持用户自定义平台包持久化。
3. GitHub/API-first 当时仍是 SOP/import-only 平台包；该历史边界已被上方 `20c4bd2` 生产记录覆盖。
4. 采集任务运行锁、重试预算、超时策略和更完整的前端提交中状态仍是后续可靠性增强项。

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
3. P0-2 清洗计划持久化和试跑在后续记录中已完成；本条仅保留 P0-1 当时边界。

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
4. P0-4 重复动作基础保护在后续记录中已完成；本条仅保留 P0-2 当时边界。

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
4. P0-3 Platform Package 模板化和生产部署验收在后续记录中已完成；本条仅保留 P0-4 当时边界。

### 2026-06-19 P0-3 本地实现记录

事实：

1. 已新增 PlatformPackage contract schema，覆盖 `id`、`name`、`category`、`supported_targets`、`collector_types`、`field_schema`、`strategy_matrix`、`risk_boundaries`、`sop_links`、`sample_fixture`、`execution_boundary`。
2. 已新增 `/api/automation/platform-packages` 和 `/api/automation/platform-packages/{package_id}`。
3. 首批平台包包含 `shopify-independent-ecommerce` 和 `github-api-first`。
4. `shopify-independent-ecommerce` 标记为 `executable`，指向 `ecommerce_product_discovery` 与 `ecommerce_product_page`。
5. `github-api-first` 当时标记为 `sop_import_only`，指向 `github_topic` 与 `github_repo`，不允许从 Automation 默认启动；后续 commit 已将其升级为 `executable`。
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
3. GitHub/API-first 当时仍是 SOP/import-only，不代表已经进入 Automation 一键运行链路；当前事实以上方 `20c4bd2` 生产记录为准。
4. 生产 read-only smoke、授权生产写入 E2E、生产 E2E fixture cleanup 尚未执行。

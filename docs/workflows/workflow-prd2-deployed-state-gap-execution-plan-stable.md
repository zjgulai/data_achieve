---
title: PRD2 Deployed State Gap Audit And Execution Plan
doc_type: workflow
module: automation
topic: prd2-deployed-state-gap
status: stable
created: 2026-06-21
updated: 2026-06-21
owner: self
source: human+ai
---

# PRD2 Deployed State Gap Audit And Execution Plan

## 0. Evidence Boundary

本文件盘点的是 2026-06-21 M3 GitHub API-first 深化发布后的“线上当前状态 vs PRD2/本地工作树目标”。本轮执行了 production deploy、authenticated read-only smoke 和 gateway/cross-domain read-only regression；没有执行生产写入、provider call、邮件发送、通知发送、调度变更或外部平台读取。

| Evidence | Current fact | Boundary |
|---|---|---|
| Production health | `GET https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`schema_revision=202606110023`、`schema_head=202606110023`、`scheduler_enabled=true` | L3 production read-only smoke；证明 production release 已对齐到 PRD2 R0 schema |
| Production pages | `/dashboard`、`/intelligence`、`/reports`、`/tasks`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities`、`/automation`、`/datasets` 均返回 `200 text/html` | L3 production read-only smoke；不证明页面内写入链路可用 |
| Production auth boundary | 未认证访问 `/api/automation/platform-packages` 和 `/api/sources` 返回 `401 application/json` | L3 production read-only smoke；符合业务接口需要登录态的 API 合同 |
| Authenticated read-only API smoke | 既有 demo 账号读取 session、dashboard、tasks、reports、alert events、notifications 均通过 | L3 production read-only；没有创建或修改业务数据 |
| GitHub API-first package | Authenticated read-only `GET /api/automation/platform-packages/github-api-first` 确认 `field_schema.required` 包含 `license_spdx_id`、`default_branch`、`latest_release_tag`、`latest_release_published_at`、`pushed_at` | L3 production read-only；只证明平台包字段合同已发布，不证明生产 GitHub 采集写入 |
| Local PRD2 docs | PRD2 源头文档为 `docs/product/product-prd-data-intelligence-hub-stable.md`；执行计划为 `docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md` | L1 repo evidence |
| Release commit | `main@e9ccb814899231d49be2f130ed0a9ee9599c93fc` 已发布到 `/opt/data-achieve-scrapy/app` | L3 production deployment evidence；不含生产写入 E2E |
| Schema delta | `202606110021_browser_diagnostic_runs.py`、`202606110022_browser_diagnostic_jobs.py`、`202606110023_browser_diagnostic_job_runs.py` 已在生产 migration 中执行 | Browser diagnostic 资产表已上线；真实浏览器执行仍需单独授权 |
| Browser local smoke | `workflow-browser-evidence-artifact-retention-stable.md` 记录 `tmp/browser-harness-readonly-smoke-20260621.json` 为 `blocked_local_daemon`、`browser_started=false`、`collection_resources_written=false` | L2 local validation；不是生产可用性证明 |
| Cross-domain regression | `video.lute-tlz-dddd.top=200`、`mkt.lute-tlz-dddd.top=200`、`voc.lute-tlz-dddd.top=302`，跟随 redirect 后到登录页返回 200；`scrapy.lute-tlz-dddd.top/api/health=200` | L3 read-only gateway regression；`voc` 直接访问是 302，不应写成直接 200 |

## 1. Executive Snapshot

### Facts

1. 当前线上服务是可访问的：API health 正常，数据库已连接，核心页面均能返回 HTML。
2. 当前线上 API 未认证访问会返回 401，这和 API contract 中“登录、注册以外业务接口都要求当前用户和 workspace”的设计一致；既有 demo 账号 authenticated read-only smoke 已通过。
3. PRD2 的产品中心已经从通用情报平台收敛为“平台化采集工作台”，主链路是授权确认、能力探测、结构/浏览器诊断、字段候选、采集/清洗计划、Dataset、Export、Drift、Report、Alert、Evidence。
4. 本地和生产 HEAD `e9ccb81` 已包含 PRD2/M1/M2/M3 的多项实现：平台包、CapabilityProbe、BrowserDiagnosticRun/Job/JobRun、browser local runner、GitHub Tool Radar 深化字段、独立站 dataset/export/drift/report 等。
5. 生产 Alembic head 已到 `202606110023`，PRD2 R0 release/schema gap 已闭合；M3 GitHub API-first 字段合同已上线；剩余 gap 转为剩余字段深度、显式 provenance 和 authorized production write E2E 证据。

### Inferences

1. 线上产品已经完成 PRD2 R0 release/schema 对齐和 M3 首轮 GitHub API-first 字段深化发布，但这仍然只是 production release + read-only smoke，不等于生产写入 E2E 已完成。
2. BrowserDiagnosticRun/Job/JobRun 资产化链路已随 schema `202606110023` 上线；真实浏览器执行器、文件保留和外部平台读取仍需单独授权。
3. GitHub API-first 仍是下一阶段最适合继续加深的平台样板，因为首轮 M3 已上线但 README metadata、issue activity、commit freshness、显式 field provenance 和生产写入验收仍未闭合。
4. Public Web/RSS/Docs、Video transcript import、Public community trend 适合做 P1 新平台包；Marketplace、RPA/no-code、Social 平台应先做 API/import/SOP，不应默认做页面自动采集。

### Unknowns

1. 本轮使用登录态执行了生产 read-only API smoke，但没有在 `/automation` 页面内执行交互式写入流程，所以不能确认生产 Dataset write-through、Report asset 创建和 cleanup 链路。
2. 本轮没有生产写入授权，所以没有执行 Source/Task/TaskRun/Dataset/Report/Alert 的 L4 验收。
3. 本轮没有重新运行生产 GitHub topic/repo 采集，所以 M3 的生产证据只覆盖字段合同发布，不覆盖真实 GitHub 采集写入结果。
4. 线上运行环境是否安装 `agent-reach` 或 `browser-harness` 未验证；即便安装，也只能先进入 doctor/read-only probe 边界。

## 2. PRD2 Gap Matrix

| Area | PRD2 target | Current deployed evidence | Local/repo evidence | Gap | Priority |
|---|---|---|---|---|---|
| Product shell | `/automation` 作为平台化采集工作台主入口，`/datasets` 作为数据资产池 | `/automation=200`、`/datasets=200` | Web app 有 automation/datasets routes 和 E2E 覆盖 | 生产页面内交互未登录验证；根路径 `307` 只说明有跳转 | P0 release evidence |
| Auth/workspace boundary | 业务接口绑定登录态、workspace、current user | 未认证业务 API 返回 401；authenticated read-only smoke 通过 | API contract 明确 cookie auth；routes 使用 `get_auth_context` | 缺少 authorized production write E2E 和 cleanup evidence | P0 evidence |
| Stable collectors | `github_repo`、`github_topic`、`generic_web`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page` | 本轮未重新运行生产采集 | API docs、collector tests、Automation service 可见 | 稳定 collector 需要在 release 后做授权生产 smoke 和 cleanup register | P0 release |
| PlatformPackage | 3 个可解释、可验收平台包：independent site、GitHub API-first、public page preflight | 未认证平台包接口返回 401；authenticated read-only 已确认 `github-api-first` M3 字段合同 | `list_platform_packages()` 返回 3 个 package；E2E 覆盖应用平台包 | 平台包仍是静态 catalog；缺 version、owner、acceptance registry | P0/P1 |
| CapabilityProbe | Agent Reach 风格 no-read/no-write doctor，区分 backend candidates 和 forbidden actions | 生产未登录未验证 | `list_capability_probes()`、`_probe_agent_reach_channel()`、TS types/UI 可见 | 线上未证明；缺 probe run history、probe evidence asset、operator remediation UI | P0 |
| Agent Reach fusion | 作为能力路由和 doctor，不直接读平台内容 | 线上未知 | 本地逻辑只允许 `agent-reach doctor --json`，缺失时返回 `missing_tool` | 未安装/线上运行态未知；尚未沉淀 channel-level evidence | P0/P1 |
| BrowserDiagnostic assets | BrowserDiagnosticRun/Job/JobRun 只读证据资产，selector/network/promotion/redaction 可审计 | 线上 schema head 已是 `202606110023` | migrations `021/022/023`、routes、service、UI、E2E 已随 `80f0566` 发布并保留在 `e9ccb81` | 资产表已上线；real browser local smoke 仍受 daemon 阻断；无生产 runner 授权 | M2-3 |
| Browser artifact retention | metadata-only 当前阶段，截图/trace/HAR 需单独批准 | 生产未验证 | retention workflow 已定义 `files_written=false` 等不变量 | 缺自动 TTL/cleanup job；未实现 approved artifact retention mode | P1 |
| GitHub Tool Radar | API-first 样板，能进入 Dataset/Export/Drift/Report | authenticated read-only 平台包字段合同已确认；本轮未生产写入 | E2E 覆盖 Topic Radar -> dataset -> report -> drift；M3 已补 license、default branch、latest release、pushed_at 等字段和 report summary | README metadata、issue activity、commit freshness、显式 schema version/provenance、生产写入 E2E 仍未闭合 | P0/M3 |
| Independent site | Shopify-style 商品发现、fan-out、dataset、drift、export | 本轮未生产写入 | 平台包和 service 覆盖 title/price/currency/availability/sku/canonical_url | 缺 pagination/sitemap/canonical 去重增强；缺 variant/image/brand/category；授权测试站 E2E 未执行 | P0/M4 |
| Public Web/RSS/Docs | 公开网页、RSS/Atom、docs 更新监控平台包 | 只有 page availability，不是采集链路 | `public-page-structure-preflight` 已有，generic_web 可作为基础 | RSS/Docs 还不是一等平台包；缺 feed parser、doc diff、dataset schema、drift/report | P1/M5 |
| Video transcript import | YouTube/B 站公开视频 metadata/transcript import，不下载媒体 | 无 | PRD2 已定义边界 | 缺 import schema、source provenance、copyright/subtitle fields、UI flow | P1/M6 |
| Public community trend | 聚合主题趋势，不做人级画像 | 无 | PRD2 已定义边界 | 缺 V2EX 等公开社区 package、aggregate schema、redaction/privacy guard | P1/P2 |
| Marketplace | Amazon/marketplace 走官方 API、授权导出或人工导入优先 | 无 | PRD2 已定义边界 | 缺 import template、API credential boundary、sample dataset、cleanup/audit | P2 |
| RPA/no-code | Browse AI/Octoparse/影刀/Power Automate/UiPath 作为 workflow/import 连接器 | 无 | PRD2 已定义边界 | 缺 ExternalToolSnapshot 或 manual_json import review flow | P2 |
| Social SOP/import-only | Twitter/X、小红书、Instagram、LinkedIn 默认 SOP/import-only | 无 | PRD2 已定义边界 | 缺 SOP templates、field templates、UI 禁用自动采集按钮的 package states | P3 |
| Report/Alert/Notification | Report/Alert/Notification 绑定 Evidence 和授权发送边界 | 未生产写入 | routes/service/test 覆盖 report、drift alert、站内通知、邮件发送路径 | 需要把保存 Report、站内通知、邮件发送、调度变更分成独立 authorization gate | P1 governance |

## 3. Deployed State vs Local Worktree Gap

当前最重要的 gap 已从“本地最新 PRD2/M2 能力和线上部署证据没有对齐”，转为“生产发布已完成，但 authenticated read-only 和 authorized write E2E 还没有补齐”。

| Gap | Why it matters | Required action |
|---|---|---|
| Production schema head aligned to `202606110023` | BrowserDiagnosticRun/Job/JobRun 表已上线，但仍需要生产 auth/read-only 和写入 E2E 证据分层 | 先做 authenticated production read-only smoke；写入链路另走 L4 授权和 cleanup register |
| Worktree dirty and mixed scope | 当前已有多个修改和未跟踪文件，不能直接把“本地看起来有”说成“可发布” | 做 scoped diff audit，拆分 release PR 或明确本轮发布包 |
| Production API needs auth | 只读未认证 smoke 只能证明服务边界，不证明内部流程 | 需要授权的真实账号或专用测试账号执行 production read-only/authenticated smoke |
| No L4 run this turn | Source/Task/Dataset/Report/Alert 生产写入都未执行 | 需要显式授权后按 cleanup register 执行小样本 E2E |
| Browser local daemon blocked | M2-3 real browser smoke 仍未形成 `browser_started=true` 证据 | 先修本机 daemon/connection，再只对 `https://example.com/` 或明确授权测试页重跑 |

## 4. Execution Plan

### Track R0 - Release Boundary And Evidence Alignment

目标：在 release/schema 已对齐后，继续把生产证据分成 L3 authenticated read-only 和 L4 authorized write E2E，避免把只读发布验收夸大成全链路生产写入验收。

| ID | To do | Files/commands | Acceptance evidence | Boundary |
|---|---|---|---|---|
| R0-1 | 建立 release scope 清单 | `git status --short`、`git diff --stat`、PRD/API/workflow docs | 列出本次要发布的 code/doc/migration 文件，排除无关 dirty files | docs/code audit only |
| R0-2 | 本地门禁 | `pnpm lint:web`、`pnpm test:web`、`bash scripts/verify-mvp.sh` | 本地 lint/unit/build/E2E/MVP smoke 通过或列出阻断项 | local validation |
| R0-3 | DB migration rehearsal | `bash scripts/verify-mvp.sh --with-db` 或 `uv run alembic upgrade head` | 本地 DB 可从 `020` 升到 `023`，downgrade/recovery notes 清楚 | local DB only |
| R0-4 | 部署前 schema gate | 检查 `apps/api/alembic/versions` 和 health contract | 准备发布版本的 `schema_head=202606110023` 可解释 | no production write |
| R0-5 | 发布后只读 smoke | `/api/health`、`/automation`、`/datasets`、未认证 401 检查 | done：生产 health 显示 `schema_revision/schema_head=202606110023`，页面可达，API 边界不变 | L3 production read-only |
| R0-6 | 授权生产 E2E | 专用测试 workspace，最小 Source/Task/Dataset/Report run | 所有新增资产有 id、owner、created_at、cleanup dry-run/execute 记录 | L4 only after explicit approval |

R0-5 已完成；M3/M4 仍不能宣称生产写入完成，除非 R0-6 获得单独授权并留下 cleanup evidence。

### Track M3 - GitHub API-first Deepening

目标：把 GitHub 做成第一个 PRD2 “API-first 平台包样板”，形成可复用的采集、数据集、漂移和报告标准。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M3-1 | 扩展 GitHub collector 原始字段 | collector/service/tests | 支持 latest release、README metadata、license、default branch、open issue activity、commit freshness |
| M3-2 | Dataset schema version/provenance | dataset service、API schema、docs | `github_tool_radar` DatasetVersion 写入 `schema_version`、field source、collector version |
| M3-3 | Report 增强 | `automation_service.py`、report UI、tests | 报告包含维护风险、安装方式、适用采集场景、不适用边界 |
| M3-4 | Drift 规则增强 | drift service/tests | stars/forks/issues/release freshness/field missingness 能分层输出 drift status |
| M3-5 | E2E 和 cleanup | web E2E + API integration + authorized production runbook | 本地通过；生产写入只在授权后执行，并可清理 |

Acceptance commands:

```bash
pnpm lint:web
pnpm test:web
bash scripts/verify-mvp.sh
bash scripts/verify-mvp.sh --with-db
```

当前 M3 状态：

1. `M3-1` 部分完成：license、default branch、latest release、pushed_at 已部署；README metadata、issue activity、commit freshness 仍待补。
2. `M3-2` 部分完成：collector/API/report 已带字段来源和缺失摘要；DatasetVersion 显式 `schema_version` 与 per-field provenance 仍待补。
3. `M3-3` 部分完成：report 已显示 license/release/default branch/pushed_at summary；维护风险、安装方式、适用/不适用边界仍待增强。
4. `M3-4` 未完成：当前只继承既有 completeness/drift 基础能力，尚未按 stars/forks/issues/release freshness/field missingness 分层输出。
5. `M3-5` 已完成本地门禁和 production read-only smoke；production write E2E 仍为 pending authorization。

### Track M4 - Independent Site / Shopify-style Deepening

目标：把独立站从 demo 闭环提升为可运营的商品数据采集模板。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M4-1 | Discovery 增强 | ecommerce collectors、automation service | 支持 collection/listing/sitemap/pagination/canonical 去重和 skip reasons |
| M4-2 | 商品字段增强 | collector/schema/tests/UI | 增加 variant、image、brand、category、price range、availability detail |
| M4-3 | Dataset/drift 样例 | dataset/drift tests、docs | 新增/下架、价格变化、字段缺失能进入 DatasetDriftEvent |
| M4-4 | 授权测试站 E2E | API script、Playwright | 从 URL 到 Dataset/export/drift 全链路可跑，并有 cleanup record |

Boundary: 只处理授权公开页面；不处理登录墙、验证码、购物车态、反检测或 marketplace 页面。

### Track M5 - Public Web/RSS/Docs Package

目标：新增第一个低风险公开内容监控平台包。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M5-1 | 定义 `public-web-rss-docs` package | API contract、platform package catalog、TS types/UI | package 显示 URL/RSS/Docs 三种 entrypoint，含 risk boundary |
| M5-2 | RSS/Atom parser | collector + tests | 支持 title/link/published/updated/author/tags/content summary/hash |
| M5-3 | Docs diff dataset | dataset service + drift service | 能比较 previous/current content hash、heading diff、link changes |
| M5-4 | Report template | report service/UI | 生成“公开页面/文档更新摘要”并绑定 evidence |

Boundary: 公开源、低频、保留 final URL/source timestamp/content hash；不覆盖原始事实。

### Track M6 - Video And Public Community Import

目标：先做 metadata/transcript 和聚合趋势导入，不下载媒体、不做人级画像。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M6-1 | Video transcript import schema | API docs、schemas、manual/import service | 保存 video url、platform、title、channel label、published_at、transcript source、license/copyright note |
| M6-2 | Video dataset/report | dataset/report service/UI | transcript rows 可进入 DatasetVersion 和 report summary |
| M6-3 | V2EX/public community aggregate | collector/import service/tests | 只保留 topic/title/link/time/reply_count/aggregate score，不保存个人画像 |
| M6-4 | Privacy gate | UI + tests | 高风险字段被拒绝或进入 manual review |

Boundary: 公开视频 metadata/transcript import；不下载媒体文件；社区只做聚合。

### Track M7 - Marketplace/RPA/Social Boundary Packages

目标：把高风险但业务价值高的平台做成授权导入/API/SOP，而不是默认自动采集。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M7-1 | Marketplace authorized import | import template、API docs、UI | Amazon/SP-API 或后台 CSV 导入 demo，字段模板可审计 |
| M7-2 | ExternalToolSnapshot | model/schema/service/UI | Browse AI/Octoparse/影刀/Power Automate/UiPath 输出先进入 snapshot review，再人工确认入 Dataset |
| M7-3 | SOP-only social packages | platform catalog、toolkit docs/UI | Twitter/X、小红书、Instagram、LinkedIn 显示 `sop_only`，不出现自动采集按钮 |
| M7-4 | Compliance checklist | docs + UI gates | cookie export、login bypass、anti-detect、bulk scroll scraping 均在 forbidden actions |

Boundary: API/import/SOP first；不复用主账号 cookie；不绕过登录态、验证码或平台限制。

### Track G1 - Governance And Evidence Quality

目标：把不同证据层的 closeout 固化，避免 mock/local/prod 被混写。

| ID | To do | Acceptance |
|---|---|---|
| G1-1 | Release closeout template | 每次收口列出 changed files、local gates、L3 smoke、L4 writes、cleanup assets |
| G1-2 | Production cleanup register | 每次授权生产写入都有 ids、resource type、cleanup dry-run、cleanup result |
| G1-3 | Notification/provider gate | Report save、站内通知、邮件发送、provider call、scheduler mutation 分开授权 |
| G1-4 | Evidence wording lint | 文档和 UI 不把 doctor/probe/read-only 说成采集成功 |

## 5. Platform Priority

| Priority | Platform/capability | Why next | Work mode |
|---|---|---|---|
| Done | Release boundary, migration to `023`, M3 read-only deployment | production HEAD `e9ccb81`，schema `202606110023`，L3 read-only smoke 和 GitHub API-first 字段合同检查完成 | release/evidence |
| P0 | GitHub API-first remaining M3 | 官方 API、低风险、已有 collector/Dataset/Report path；首轮字段深化已上线，剩余 README/issue/freshness/provenance/drift | API collector |
| P0 | Independent site / Shopify-style | 已有业务闭环，能产生电商 dataset/drift | public page collector |
| P1 | Public Web/RSS/Docs | 低风险、高复用，适合训练/竞品/文档更新 | URL/feed/docs collector |
| P1 | Video transcript import | 内容趋势价值高，但应 import metadata/transcript | import |
| P1/P2 | Public community trend | 可做聚合趋势，不做人级画像 | aggregate import/collector |
| P2 | Marketplace | 商业价值高，平台政策和账号边界复杂 | API/import first |
| P2 | RPA/no-code | 适合接业务后台导出结果，不应内置主账号自动化 | ExternalToolSnapshot |
| P3 | Twitter/X、小红书、Instagram、LinkedIn | 登录态、个人数据和平台限制风险高 | SOP/import-only |

## 6. Immediate Next To Do

按当前证据，R0 release/schema 对齐和 M3 首轮 production read-only 发布已完成。下一轮不应重复 release boundary，应进入剩余 M3 深挖或授权生产写入验收。

1. 补齐 M3 剩余项：README metadata、issue activity、commit freshness、DatasetVersion `schema_version`、per-field provenance 和 drift 分层规则。
2. 如需证明写入链路，再单独授权 L4 production E2E：明确测试 workspace、允许写入的 Source/Task/Dataset/Report 范围、cleanup register 和 cleanup dry-run/execute。
3. 并行准备 M4 Independent Site 和 M5 Public Web/RSS/Docs，但保持平台政策、授权和导入优先边界。

## 7. Definition Of Done

一个平台采集工作包只有同时满足以下条件，才可以被写成“已打通”：

1. PRD/API contract/schema/UI copy 同步。
2. Collector 或 import path 有本地测试。
3. DatasetVersion 记录 schema version、field provenance、source task/snapshot ids。
4. Export、Drift、Report 至少有一个可复现验收样例。
5. forbidden actions 和授权边界在 UI/API 中可见。
6. 本地门禁通过。
7. 生产只读 smoke 通过。
8. 若涉及生产写入，必须有显式授权、资源清单和 cleanup 记录。

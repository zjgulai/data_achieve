---
title: PRD2 Deployed State Gap Audit And Execution Plan
doc_type: workflow
module: automation
topic: prd2-deployed-state-gap
status: stable
created: 2026-06-21
updated: 2026-06-24
owner: self
source: human+ai
---

# PRD2 Deployed State Gap Audit And Execution Plan

## 0. Evidence Boundary

本文件盘点的是 2026-06-21 M3 GitHub API-first 深化发布后的“线上当前状态 vs PRD2/本地工作树目标”。2026-06-22 增补 M4 源码分支状态：PR #6 已把 M4-1/M4-2 合并到 `main@67f611e`；PR #7 已把 M4-3 合并到 `main@8cd3e8f` 且 main CI 通过。2026-06-23 已完成一次小范围 M3 GitHub API-first 生产 package gate：`topic=web-scraping`、`max_repositories=3`、允许 Source/Task write、一次 GitHub API TaskRun、Dataset save、report asset、drift snapshot，并按 `cleanup_after_evidence` 清理。同日已完成 M5 Public Web/RSS/Docs production package smoke：允许一次公开 RSS TaskRun、`public_content_update` DatasetVersion save、read-only drift/report preview，并按 exact-ID 与 generic E2E cleanup 清理；随后已完成 M5 Public Content Report asset gate，允许创建一个 `public_content` Report asset 并清理；之后已完成 M5 Public Content Dataset export gate，允许创建一个 CSV DatasetExportJob、写出一个受控导出文件、下载校验并清理 scoped fixtures 与导出文件；随后已完成 M5 Public Content retained lifecycle gate，保留一组 production canary 资产并验证重登录后的 Dataset/Report/Export 可见性与 export artifact 存在。2026-06-24 先本地补齐 public-content drift event 专用持久化路径，随后部署 production SHA `68c27e0f9c62d542149eedc5b18439938103b4bb` 并完成一个 scoped production drift-event gate：创建 `public_content_drift` DatasetDriftEvent、重复提交复用同一 ID，并在取证后清理为零；retained canary inventory 的 `dataset_drift_events=0` 历史事实不代表 retained canary 已更新。本文的生产写入证据只覆盖这些授权包，不覆盖 provider call、邮件发送、调度变更、生产浏览器运行或浏览器 artifact 写入。

| Evidence | Current fact | Boundary |
|---|---|---|
| Production health | `GET https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`schema_revision=202606110023`、`schema_head=202606110023`、`scheduler_enabled=true` | L3 production read-only smoke；证明 production release 已对齐到 PRD2 R0 schema |
| Production deploy identity | 2026-06-24 M5 Public Content drift-event production gate 后，remote `HEAD` 和 `.deploy-sha` 均为 `68c27e0f9c62d542149eedc5b18439938103b4bb` | L3 deployment evidence；该 SHA 是当前生产代码点 |
| Production pages | `/dashboard`、`/automation`、`/datasets`、`/tasks`、`/sources`、`/raw-records`、`/reports`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/entities`、`/toolkit` 均返回 `200` | L3 production read-only smoke；不证明页面内写入链路可用 |
| Production auth boundary | 未认证访问 `/api/automation/platform-packages` 和 `/api/sources` 返回 `401 application/json` | L3 production read-only smoke；符合业务接口需要登录态的 API 合同 |
| Authenticated read-only API smoke | 既有 demo 账号读取 session、dashboard、tasks、reports、alert events、notifications 均通过 | L3 production read-only；没有创建或修改业务数据 |
| GitHub API-first package | 真实生产 API Playwright gate `PLAYWRIGHT_REAL_API=true ... --grep "renders automation platform packages"` 返回 `2 passed`；scope 为 `topic=web-scraping`、`max_repositories=3` | L4 authorized live；证明小范围 GitHub package write-through、Dataset save、report asset、drift snapshot 和 cleanup 链路，不证明大规模或定时采集 |
| GitHub cleanup register | cleanup dry-run 发现 scoped E2E residue：`users=8`、`workspaces=8`、`workspace_members=16`、`notifications=8`、`dataset_versions=2`、`dataset_drift_events=2`、`report_audit_events=2`；execute 后 recount 全为 0 | L4 cleanup evidence；保留证据，不保留测试资产 |
| Public content package | 公开 RSS `https://hnrss.org/frontpage` 生产 TaskRun `success`，采集 5 条 feed entries，保存 `public_content_update` DatasetVersion `row_count=5`，read-only drift/report preview 通过，后续 gate 创建 `public_content` Report asset，在 export gate 创建 CSV DatasetExportJob、写入 4900-byte export artifact 且下载校验通过，在 retained gate 保留一组 canary Dataset/Report/Export asset，并在 2026-06-24 drift-event gate 创建/复用一个 `public_content_drift` DatasetDriftEvent | L4 authorized live；证明小范围 public_feed write-through、Dataset save、read-only drift/report preview、Report asset、Dataset export、DatasetDriftEvent persistence、cleanup-after-evidence 和 retained-no-cleanup 两种生命周期；不证明 recurring monitoring、multi-day TTL 或 scheduler |
| Public content retention register | retained lifecycle gate 保留 `retained-public-content-20260623123816-90w0q7@example.com` 资产链：Source `c86b280c`、Task `b8a4cb3f`、TaskRun `1f684c04`、Dataset `ee4a4a7a`、Version `6e2cbc17`、Report `38a0f8ce`、ExportJob `3f43b866`；read-only DB/volume inventory 返回 `export_artifact_files=1`、`violations=[]`、`cleanup_executed=false` | L4 retained evidence；保留测试资产，未来清理必须按 exact IDs，不走 generic E2E cleanup |
| Public content drift event production gate | 2026-06-24 部署 SHA `68c27e0f9c62d542149eedc5b18439938103b4bb` 后，新建 scoped public RSS fixture，保存 `public_content_drift` DatasetDriftEvent `6acbd871-e0f8-4580-a7c7-b3d2459962f1`，重复提交复用同一 ID，exact-ID cleanup 和 generic cleanup dry-run 全 0 | L4 authorized live；证明生产 save/list/reuse 与 cleanup-after-evidence；不证明 retained canary 已更新或 scheduler recurring drift 已启用 |
| Public content cleanup register | base smoke、Report asset gate 和 Dataset export gate 的 exact-ID cleanup 均执行；Dataset export gate 成功 run 的 pre-cleanup 命中 `users=1`、`sources=1`、`collection_tasks=1`、`task_runs=1`、`raw_records=1`、`entities=1`、`entity_snapshots=1`、`datasets=1`、`dataset_versions=1`、`dataset_export_jobs=1`、`export_artifact_files=1`；execute 后 exact-ID 与 generic E2E recount 全为 0；retained gate 仅跑 generic dry-run 且全 0 | L4 cleanup evidence；cleanup-after-evidence gate 不保留测试资产；retained gate 明确保留 canary |
| Local PRD2 docs | PRD2 源头文档为 `docs/product/product-prd-data-intelligence-hub-stable.md`；执行计划为 `docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md` | L1 repo evidence |
| Release commit | `68c27e0f9c62d542149eedc5b18439938103b4bb` 已发布到 `/opt/data-achieve-scrapy/app` | L4 M5 public content drift-event production gate 对应生产部署；后续本地测试/文档提交不代表生产已同步 |
| Source main state | 生产服务器 `main...origin/main [ahead 14]`，当前 deployed commit 为本地 gate 分支经 bundle fast-forward 后的 `68c27e0f9c62d542149eedc5b18439938103b4bb` | L1/L3 source and deployment evidence；origin/main 是否同步到该 SHA 仍需单独推送/PR 证据 |
| Production deploy access | 2026-06-23 生产部署、preflight、Docker build、Alembic upgrade、gateway retry 和 health/page smoke 已完成 | 当前发布入口已可用；未来每次 deploy 仍需单独记录 preflight/build/health evidence |
| Schema delta | `202606110021_browser_diagnostic_runs.py`、`202606110022_browser_diagnostic_jobs.py`、`202606110023_browser_diagnostic_job_runs.py` 已在生产 migration 中执行 | Browser diagnostic 资产表已上线；真实浏览器执行仍需单独授权 |
| Browser local smoke | `workflow-browser-evidence-artifact-retention-stable.md` 记录 `tmp/browser-harness-readonly-smoke-20260621.json` 为 `blocked_local_daemon`、`browser_started=false`、`collection_resources_written=false` | L2 local validation；不是生产可用性证明 |
| Cross-domain regression | `video.lute-tlz-dddd.top=200`、`mkt.lute-tlz-dddd.top=200`、`voc.lute-tlz-dddd.top=302`，跟随 redirect 后到登录页返回 200；`scrapy.lute-tlz-dddd.top/api/health=200` | L3 read-only gateway regression；`voc` 直接访问是 302，不应写成直接 200 |

## 1. Executive Snapshot

### Facts

1. 当前线上服务是可访问的：API health 正常，数据库已连接，核心页面均能返回 HTML。
2. 当前线上 API 未认证访问会返回 401，这和 API contract 中“登录、注册以外业务接口都要求当前用户和 workspace”的设计一致；既有 demo 账号 authenticated read-only smoke 已通过。
3. PRD2 的产品中心已经从通用情报平台收敛为“平台化采集工作台”，主链路是授权确认、能力探测、结构/浏览器诊断、字段候选、采集/清洗计划、Dataset、Export、Drift、Report、Alert、Evidence。
4. 生产 HEAD `68c27e0f9c62d542149eedc5b18439938103b4bb` 已包含 PRD2/M1/M2/M3/M5 的多项实现：平台包、CapabilityProbe、BrowserDiagnosticRun/Job/JobRun、browser local runner、GitHub Tool Radar 深化字段、schema/provenance、report risk sections、drift signal groups、独立站 dataset/export/drift/report、`public_feed`、`public_content_update.v1` Dataset/drift/report preview、`public_content` Report asset 持久化，以及 `public_content_drift` DatasetDriftEvent save/list/reuse。
5. 生产 Alembic head 已到 `202606110023`，PRD2 R0 release/schema gap 已闭合；M3 GitHub API-first 小范围生产 package gate 已完成并清理；M5 public content 小范围生产 package smoke、Report asset gate、Dataset export gate 已完成并清理；M5 retained lifecycle gate 已保留一组 canary Dataset/Report/Export asset；public-content drift event 专用持久化已完成生产 scoped gate 并清理。剩余 gap 转为更大 scope rate-limit、多日 TTL/自动清理、scheduler/provider/email、docs diff 等独立 gate。

### Inferences

1. 线上产品已经完成 PRD2 R0 release/schema 对齐，并完成一次小范围 M3 GitHub API-first L4 package gate、一次 M5 public content L4 package smoke、一次 M5 Report asset gate、一次 M5 Dataset export gate 与一次 M5 retained lifecycle gate；这不等于大规模 recurring collection、scheduler、多日 TTL 或自动清理生命周期也已完成。
2. BrowserDiagnosticRun/Job/JobRun 资产化链路已随 schema `202606110023` 上线；真实浏览器执行器、文件保留和外部平台读取仍需单独授权。
3. GitHub API-first 与 Public Web/RSS/Docs 已经形成两个可复用样板：前者证明 API-first tool radar 的 Dataset/report/drift asset 链路，后者证明低风险公开 feed 的 Dataset/read-only drift/report preview 链路。
4. Public Web/RSS/Docs、Video transcript import、Public community trend 适合做 P1 新平台包；Marketplace、RPA/no-code、Social 平台应先做 API/import/SOP，不应默认做页面自动采集。

### Unknowns

1. GitHub API rate-limit、失败重试和数据完整性在大于 `max_repositories=3` 的 topic scope 下仍未验证。
2. retained lifecycle gate 只验证了即时保留、重登录后可见、DB/volume 中 canary asset 存在；没有验证多日保留、TTL、自动清理、定时刷新后的生命周期；retained canary 本身仍未被本轮 drift-event gate 更新。
3. 生产 GitHub package gate 覆盖 Source/Task write、一次 GitHub API TaskRun、Dataset save、report asset、drift snapshot；不覆盖 provider enrichment、邮件发送、scheduler mutation、dataset export 或浏览器运行。
4. 线上运行环境是否安装 `agent-reach` 或 `browser-harness` 未验证；即便安装，也只能先进入 doctor/read-only probe 边界。

## 2. PRD2 Gap Matrix

| Area | PRD2 target | Current deployed evidence | Local/repo evidence | Gap | Priority |
|---|---|---|---|---|---|
| Product shell | `/automation` 作为平台化采集工作台主入口，`/datasets` 作为数据资产池 | `/automation=200`、`/datasets=200` | Web app 有 automation/datasets routes 和 E2E 覆盖 | 生产页面内交互未登录验证；根路径 `307` 只说明有跳转 | P0 release evidence |
| Auth/workspace boundary | 业务接口绑定登录态、workspace、current user | 未认证业务 API 返回 401；authenticated read-only smoke 通过；M3/M5 多个 scoped authorized production write gates 均带 cleanup evidence | API contract 明确 cookie auth；routes 使用 `get_auth_context` | 其它平台和 side-effect gates 仍需逐项授权与 cleanup/retention evidence | P0 evidence |
| Stable collectors | `github_repo`、`github_topic`、`generic_web`、`public_feed`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page` | M3 GitHub 和 M5 `public_feed` 已各完成一次小范围授权生产 gate/smoke | API docs、collector tests、Automation service 可见；`public_feed` 已生产验证 `https://hnrss.org/frontpage` | 独立站、generic_web、manual_json 等其它 collector 的生产写入 gate 仍需单独执行 | P0 release |
| PlatformPackage | 3 个可解释、可验收平台包：independent site、GitHub API-first、public page preflight | 未认证平台包接口返回 401；authenticated read-only 已确认 `github-api-first` M3 字段合同 | `list_platform_packages()` 返回 3 个 package；E2E 覆盖应用平台包 | 平台包仍是静态 catalog；缺 version、owner、acceptance registry | P0/P1 |
| CapabilityProbe | Agent Reach 风格 no-read/no-write doctor，区分 backend candidates 和 forbidden actions | 生产未登录未验证 | `list_capability_probes()`、`_probe_agent_reach_channel()`、TS types/UI 可见 | 线上未证明；缺 probe run history、probe evidence asset、operator remediation UI | P0 |
| Agent Reach fusion | 作为能力路由和 doctor，不直接读平台内容 | 线上未知 | 本地逻辑只允许 `agent-reach doctor --json`，缺失时返回 `missing_tool` | 未安装/线上运行态未知；尚未沉淀 channel-level evidence | P0/P1 |
| BrowserDiagnostic assets | BrowserDiagnosticRun/Job/JobRun 只读证据资产，selector/network/promotion/redaction 可审计 | 线上 schema head 已是 `202606110023` | migrations `021/022/023`、routes、service、UI、E2E 已保留在当前生产基线 | 资产表已上线；生产 runner、artifact 写入和外部平台读取仍需单独授权 | M2-3 |
| Browser artifact retention | metadata-only 当前阶段，截图/trace/HAR 需单独批准 | 生产未验证 | retention workflow 已定义 `files_written=false` 等不变量 | 缺自动 TTL/cleanup job；未实现 approved artifact retention mode | P1 |
| GitHub Tool Radar | API-first 样板，能进入 Dataset/Export/Drift/Report | 2026-06-23 小范围 L4 gate 已跑通 Topic Radar -> GitHub API TaskRun -> Dataset save -> report asset -> drift snapshot -> cleanup | E2E 覆盖 Topic Radar -> dataset -> report -> drift；M3 已补 license、default branch、latest release、README metadata、pushed_at、schema/provenance、report risk sections 和 drift signal groups | 大 scope rate-limit、retained dataset、scheduler、export、provider/email 仍未闭合 | Done/M3 |
| Independent site | Shopify-style 商品发现、fan-out、dataset、drift、export | 本轮未执行 M4 授权测试站写入 E2E | `origin/main=e97810a` 基线已随当前 `68c27e0f9c62d542149eedc5b18439938103b4bb` 生产代码点保留 | M4-4 授权测试站 E2E 未完成；需要测试站 URL、cleanup register 和 export/retention 边界 | P0/M4 |
| Public Web/RSS/Docs | 公开网页、RSS/Atom、docs 更新监控平台包 | M5 production smoke 已跑通 `public_feed` RSS TaskRun、`public_content_update` DatasetVersion、read-only drift/report preview；Report asset、Dataset export、retained lifecycle canary 和 scoped `public_content_drift` event gate 均已完成 | M5 local scaffold、Dataset/drift/report slice、Report asset/API/Web client/export contract、public-content drift event persistence 和测试已完成 | docs diff、recurring monitoring、scheduler、多日 TTL/自动清理仍未闭合；retained canary 未被 drift-event gate 更新 | Done/M5 |
| Video transcript import | YouTube/B 站公开视频 metadata/transcript import，不下载媒体 | 无 | PRD2 已定义边界 | 缺 import schema、source provenance、copyright/subtitle fields、UI flow | P1/M6 |
| Public community trend | 聚合主题趋势，不做人级画像 | 无 | PRD2 已定义边界 | 缺 V2EX 等公开社区 package、aggregate schema、redaction/privacy guard | P1/P2 |
| Marketplace | Amazon/marketplace 走官方 API、授权导出或人工导入优先 | 无 | PRD2 已定义边界 | 缺 import template、API credential boundary、sample dataset、cleanup/audit | P2 |
| RPA/no-code | Browse AI/Octoparse/影刀/Power Automate/UiPath 作为 workflow/import 连接器 | 无 | PRD2 已定义边界 | 缺 ExternalToolSnapshot 或 manual_json import review flow | P2 |
| Social SOP/import-only | Twitter/X、小红书、Instagram、LinkedIn 默认 SOP/import-only | 无 | PRD2 已定义边界 | 缺 SOP templates、field templates、UI 禁用自动采集按钮的 package states | P3 |
| Report/Alert/Notification | Report/Alert/Notification 绑定 Evidence 和授权发送边界 | GitHub `github_tool_radar` report asset 和 M5 `public_content` Report asset 已各完成一次小范围生产 gate；站内通知/邮件发送/调度触发仍需单独 gate | routes/service/test 覆盖 report、drift alert、站内通知、邮件发送路径 | 需要继续把站内通知、邮件发送、调度变更分成独立 authorization gate | P1 governance |

## 3. Deployed State vs Local Worktree Gap

当前最重要的 gap 已从“本地最新 PRD2/M2 能力和线上部署证据没有对齐”，转为“GitHub 小范围 L4 package gate 已完成，但更大 scope、长期保留、调度、导出、provider/email 和下一平台包仍需分 gate 推进”。

| Gap | Why it matters | Required action |
|---|---|---|
| Production schema head aligned to `202606110023` | BrowserDiagnosticRun/Job/JobRun 表已上线，但仍需要生产 auth/read-only 和写入 E2E 证据分层 | 先做 authenticated production read-only smoke；写入链路另走 L4 授权和 cleanup register |
| Worktree dirty and mixed scope | 当前已有多个修改和未跟踪文件，不能直接把“本地看起来有”说成“可发布” | 做 scoped diff audit，拆分 release PR 或明确本轮发布包 |
| Production API needs auth | 只读未认证 smoke 只能证明服务边界，不证明内部流程 | 需要授权的真实账号或专用测试账号执行 production read-only/authenticated smoke |
| Remaining L4 breadth | GitHub 小范围 L4 已完成；其他平台、导出、邮件、provider、scheduler 仍未执行 | 继续按 single-step authorization envelope 执行，每次保留 cleanup 或 retention evidence |
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
| R0-6 | 授权生产 E2E | 专用测试 workspace，最小 Source/Task/Dataset/Report run | done for M3 GitHub scope：真实 API E2E `2 passed`，cleanup recount 全 0 | L4 only after explicit approval；其他平台和 side effects 另行授权 |

R0-5 已完成；R0-6 已在 M3 GitHub 小范围 scope 下完成；M5 public content production smoke 和 Report asset gate 已完成。M4、dataset export、provider/email、scheduler 和生产浏览器运行仍不能宣称生产写入完成，除非各自获得单独授权并留下 cleanup 或 retention evidence。

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

1. `M3-1` 已完成：GitHub collector/normalizer 已补 latest release、README metadata、license、default branch、issue/activity/freshness 相关字段，并通过 GitHub targeted tests。
2. `M3-2` 已完成：`github_tool_radar.v2` 暴露 schema version、field source、collector versions、endpoint origins 和 lineage provenance。
3. `M3-3` 已完成：report 已包含 maintenance risk、install/source entries、recommended use cases 和 unsuitable boundaries。
4. `M3-4` 已完成：drift 输出 `signal_groups`，覆盖字段缺失、repository coverage、popularity regressions、issue activity、release freshness 和 commit freshness。
5. `M3-5` 已完成本地门禁、production runbook 和小范围 L4 production package gate；后续只剩更大 scope、retention/export/scheduler/provider/email 等独立 gate。

### Track M4 - Independent Site / Shopify-style Deepening

目标：把独立站从 demo 闭环提升为可运营的商品数据采集模板。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M4-1 | Discovery 增强 | ecommerce collectors、automation service | done_main_67f611e：支持 collection/listing/sitemap/pagination/canonical 去重和 skip reasons |
| M4-2 | 商品字段增强 | collector/schema/tests/UI | done_main_67f611e：增加 variant、image、brand、category、price range、availability detail |
| M4-3 | Dataset/drift 样例 | dataset/drift tests、docs | done_main_and_deployed_in_current_baseline：新增/下架、价格变化可进入 DatasetDriftEvent；随 `origin/main=e97810a` 基线保留在当前 `68c27e0f9c62d542149eedc5b18439938103b4bb` 生产代码点 |
| M4-4 | 授权测试站 E2E | API script、Playwright | 从 URL 到 Dataset/export/drift 全链路可跑，并有 cleanup record |

Boundary: 只处理授权公开页面；不处理登录墙、验证码、购物车态、反检测或 marketplace 页面。

### Track M5 - Public Web/RSS/Docs Package

目标：新增第一个低风险公开内容监控平台包。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M5-1 | 定义 `public-web-rss-docs` package | API contract、platform package catalog、TS types/UI | done_local_20260623：package 显示 URL/RSS/Docs targets，含 risk boundary |
| M5-2 | RSS/Atom parser | collector + tests | done_local_20260623：`public_feed` 支持 title/link/published/updated/author/tags/content summary/hash |
| M5-3 | Public content dataset/drift | dataset service + drift service | done_production_smoke_20260623：`public_feed` entries 可保存为 `public_content_update.v1` DatasetVersion，并用 `link` + `content_hash` 做 read-only drift check |
| M5-4 | Report preview template | report service | done_production_smoke_20260623：`public-content-report` 可生成公开内容更新只读摘要、风险段和建议；preview 不创建 Report asset |
| M5-5 | Report asset persistence | report service + tests + production smoke | done_report_asset_gate_20260623：`public-content-report-assets` 可创建 `public_content` Report asset，内容保留 `public_content_update.v1` schema，并完成 exact-ID cleanup |
| M5-6 | Dataset export gate | existing export service + production smoke | done_export_gate_20260623：`product-dataset-exports` 可从 `public_content_update` DatasetVersion 创建 CSV DatasetExportJob、写入受控 export artifact、下载校验，并完成 exact-ID cleanup 与 artifact deletion |
| M5-7 | Retained lifecycle canary | existing source/task/dataset/report/export list APIs | done_retained_gate_20260623：retained user/source/task/run/dataset/version/report/export artifact 保留；重登录后 list/detail/download 校验通过；generic E2E cleanup dry-run 不命中 retained canary |
| M5-8 | Drift event production gate | public-content drift-event endpoints + production smoke | done_drift_event_gate_20260624：production SHA `68c27e0f9c62d542149eedc5b18439938103b4bb`；`public_content_drift` DatasetDriftEvent 创建/复用通过；exact-ID cleanup 和 generic cleanup dry-run 全 0 |

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
| Done | Release boundary, migration to `023`, M3 GitHub package gate, M5 public content smoke, M5 Report asset gate, M5 Dataset export gate, M5 retained lifecycle gate, M5 public-content drift event production gate | production HEAD `68c27e0f`，schema `202606110023`，小范围 L4 GitHub package gate、M5 public content smoke、M5 Report asset gate、M5 Dataset export gate、M5 retained canary、public-content drift event save/reuse 和 cleanup/retention evidence 完成 | release/evidence |
| P0 | GitHub API-first scale/retention gates | 官方 API、低风险、已有 collector/Dataset/Report path；下一步只扩 scope、retention、export 或 scheduler，不重复证明小范围链路 | API collector |
| P0 | Independent site / Shopify-style | 已有业务闭环，能产生电商 dataset/drift | public page collector |
| P1 | Public Web/RSS/Docs next gates | M5 base production smoke、Report asset gate、Dataset export gate、retained lifecycle gate 和 production drift-event gate 已完成；下一步只剩 docs diff、scheduler、多日 TTL/cleanup policy 等独立 gate | URL/feed/docs collector |
| P1 | Video transcript import | 内容趋势价值高，但应 import metadata/transcript | import |
| P1/P2 | Public community trend | 可做聚合趋势，不做人级画像 | aggregate import/collector |
| P2 | Marketplace | 商业价值高，平台政策和账号边界复杂 | API/import first |
| P2 | RPA/no-code | 适合接业务后台导出结果，不应内置主账号自动化 | ExternalToolSnapshot |
| P3 | Twitter/X、小红书、Instagram、LinkedIn | 登录态、个人数据和平台限制风险高 | SOP/import-only |

## 6. Immediate Next To Do

按当前证据，R0 release/schema 对齐和 M3 GitHub 小范围 L4 package gate 已完成；M4-1 到 M4-3 已进入 `main@8cd3e8f` 并通过 main CI，但 M4 生产写入验收仍未按测试站 URL、cleanup register 和 retention/export 边界执行。

1. M5 public content production package smoke、Report asset gate、Dataset export gate、retained lifecycle gate 和 production drift-event gate 已完成；下一步可选择一个独立授权 gate：scheduler approval、docs diff 或多日 TTL/cleanup policy 之一。
2. 如继续 M4-4，需要明确测试站 URL、允许写入资源、cleanup register、是否允许 export file，以及 cleanup dry-run/execute。
3. M5 已完成小范围生产写入、Report asset 创建、Dataset export 创建/下载/删除、retained canary 保留、public-content drift event 创建/复用和清理边界验证；仍不做 provider call、email、scheduler 或 browser run，除非另起授权 gate。

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

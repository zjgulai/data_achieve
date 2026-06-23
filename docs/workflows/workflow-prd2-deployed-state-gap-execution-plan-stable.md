---
title: PRD2 Deployed State Gap Audit And Execution Plan
doc_type: workflow
module: automation
topic: prd2-deployed-state-gap
status: stable
created: 2026-06-21
updated: 2026-06-23
owner: self
source: human+ai
---

# PRD2 Deployed State Gap Audit And Execution Plan

## 0. Evidence Boundary

本文件最初盘点 2026-06-21 只读核验下的“线上当前状态 vs PRD2/本地工作树目标”。2026-06-22 已完成后续 P1/P2/P3/P4 边界遗留执行：P1 重新核验 live 状态和 dry-run inventory，P2 执行授权 demo cleanup，P3 执行授权 scoped production write E2E 并完成 fixture cleanup recount，P4 完成本地 dedicated-CDP browser-harness spike。P5 provider/email/scheduler gate 计划已完成，2026-06-23 P5 read-only inventory 和 B1 one-test-email 已完成。随后已完成 M3 GitHub API-first M3-1/M3-2/M3-3/M3-4/M3-5 local slices，但仍未执行 provider call、product/report/subscription email send、调度变更、dataset export、生产 GitHub 采集或生产 browser-harness run。

| Evidence | Current fact | Boundary |
|---|---|---|
| Production deployment closeout | 上一轮 closeout 记录生产已部署到 `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`；P1/P2/P3 live recheck 均确认 remote `HEAD` 与 `.deploy-sha` 仍为同一 SHA | L3/L4 operation evidence from prior closeout plus P1/P2/P3 read-only rechecks；本次未重新部署 |
| Production health closeout | 上一轮 closeout 记录 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`schema_revision=202606110023`、`schema_head=202606110023`、`scheduler_enabled=true`；P1/P2/P3 recheck 仍一致 | L3 production read-only smoke |
| Production pages | P1/P2/P3 均记录 `/api/health`、`/dashboard`、`/automation`、`/datasets`、`/tasks`、`/sources`、`/alerts`、`/notifications`、`/projects`、`/signals`、`/raw-records`、`/entities`、`/toolkit` 返回 `200` | L3 production read-only smoke；不证明 full-suite 页面内写入链路 |
| Authenticated API smoke | 上一轮 closeout 记录 health、login、session、dashboard、tasks、reports、alert-events、notifications 通过 | L3 authenticated smoke；不等于 production write E2E |
| P3 scoped production write E2E | `analysis-boundary-p3-production-write-e2e-draft-20260622.md` 记录 targeted real API Playwright `16 passed (49.9s)`，并完成 E2E fixture cleanup dry-run/execute/recount，全零收口 | L4 authorized live for scoped write E2E；不等于 full real suite、email/provider/scheduler/export/browser-harness 验收 |
| Local PRD2 docs | PRD2 源头文档为 `docs/product/product-prd-data-intelligence-hub-stable.md`；执行计划为 `docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md` | L1 repo evidence |
| Browser local smoke | P4 记录 dedicated-CDP isolated headless Chrome + browser-harness 对 `https://example.com/` 的本地只读 smoke 成功；缺 CDP 的 product route 会 blocked | L1 local runtime / L2 fixture validation；不是生产可用性证明 |
| P5 gate plan | `analysis-boundary-p5-provider-email-scheduler-gate-plan-draft-20260622.md` 拆分 provider、email、scheduler、dataset export 的 read-only inventory 与 live side-effect 授权模板 | L1 planning evidence；不等于 live call/send/mutation/export 验收 |
| P5 read-only inventory | `analysis-boundary-p5-read-only-inventory-draft-20260623.md` 记录 provider=`mock`、email channel ready、scheduler latest tick completed due=0/started=0、dataset export root exists and existing jobs counted | L3 production read-only；不等于 live call/send/mutation/export 验收 |
| P5 B1 one-test-email | `analysis-boundary-p5-b1-email-test-send-draft-20260623.md` 记录对 `zhoujianaaa123@gmail.com` 的 1 次授权 test email，`delivered=true` | L4 authorized live email test；不等于 product/report/subscription email 验收 |
| M3 GitHub local package | 本地代码和测试扩展 `github_repo` / `github_topic` / normalization / `github_tool_radar` dataset/report/drift 字段；web mock E2E 覆盖 `github_tool_radar.v2` schema/provenance、report risk sections、drift `signal_groups`；新增生产 gate runbook | L1/L2 local evidence；不等于生产 GitHub collection、Dataset export 或 report delivery |

## 1. Executive Snapshot

### Facts

1. 上一轮 release closeout 记录生产已部署到 SHA `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`，并保留部署前快照 `lhsnap-erfd1c6c / pre-data-scrapy-deploy-20260622`。
2. 上一轮 release closeout 记录生产 health 为 `schema_revision=202606110023`、`schema_head=202606110023`、`schema=current`。
3. PRD2 的产品中心已经从通用情报平台收敛为“平台化采集工作台”，主链路是授权确认、能力探测、结构/浏览器诊断、字段候选、采集/清洗计划、Dataset、Export、Drift、Report、Alert、Evidence。
4. 上一轮 release closeout 记录 public page smoke 和 authenticated API smoke 已通过。
5. P2 已执行授权 demo cleanup，P3 已执行 scoped production write E2E 并清理一次性 fixtures，P4 已完成 local-only dedicated-CDP browser-harness spike，P5 gate 计划、read-only inventory 和 B1 one-test-email 已完成；demo seed、provider call、product/report/subscription email send、scheduler mutation、dataset export、生产 browser-harness run 仍未执行。
6. M3 GitHub API-first 已完成本地字段增强、Dataset schema/provenance、report risk sections、drift signal groups 和 web mock E2E/runbook cleanup package：repo collector best-effort latest release / README metadata，topic summary license/default branch/status，normalization `commit_freshness_days`，Dataset schema `github_tool_radar.v2`，report 维护风险/适用场景/不适用边界，drift `signal_groups`。

### Inferences

1. R0 发布边界已经从“本地能力待上线”转为“已发布，且 P1/P2/P3/P4 已完成基础生产边界收口，P5 gate 计划、read-only inventory 和 B1 one-test-email 已完成，M3 GitHub local slices 已完成”；下一步应按生产 GitHub gate runbook 打开一个明确授权的 GitHub package gate，或选择下一个 P5 L4 live gate，而不是把本地 browser smoke 升级为生产浏览器执行。
2. `schema_head=202606110023` 的 closeout 记录支持 PRD2 R0 runtime 已随上一轮发布进入生产；P3 进一步证明 scoped production write E2E 可通过并可清理，但仍不证明 full real suite、provider call、email send、scheduler mutation、dataset export 或生产 browser-harness run 已完成。
3. GitHub API-first 和独立站/Shopify-style 是下一阶段最适合继续加深的平台样板，因为它们已经有 collector、Dataset、Export、Drift、Report 的本地产品路径；其中 GitHub 已完成 local package hardening，下一步只差明确授权的生产 gate。
4. Public Web/RSS/Docs、Video transcript import、Public community trend 适合做 P1 新平台包；Marketplace、RPA/no-code、Social 平台应先做 API/import/SOP，不应默认做页面自动采集。

### Unknowns

1. Full real Playwright suite 仍未作为生产 L4 通过，因为其中包含 report send、subscription execution、GitHub Topic Radar、dataset export、schedule approval 和 browser-harness probe controls，需要拆成单独 gate。
2. Product/report/subscription email send、provider call、scheduler mutation、dataset export 和生产 browser-harness run 仍未执行；P5 B1 只证明一封授权 test email 投递成功。
3. 线上运行环境是否安装 `agent-reach` 或 `browser-harness` 未验证；即便安装，也只能先进入 doctor/read-only probe 边界。

## 2. PRD2 Gap Matrix

| Area | PRD2 target | Current deployed evidence | Local/repo evidence | Gap | Priority |
|---|---|---|---|---|---|
| Product shell | `/automation` 作为平台化采集工作台主入口，`/datasets` 作为数据资产池 | P1/P2/P3 记录核心页面 200；P3 targeted E2E 覆盖部分页面内写入链路 | Web app 有 automation/datasets routes 和 E2E 覆盖 | 页面可达不证明 full-suite 写入；dataset export/schedule approval 仍拆出 P3 | P3 complete / P4 |
| Auth/workspace boundary | 业务接口绑定登录态、workspace、current user | P3 scoped write E2E 使用一次性 `e2e-*@example.com` users/workspaces，通过并清理 | API contract 明确 cookie auth；routes 使用 `get_auth_context` | full real suite 和 external side effects 仍需单独授权 | P3 complete / P5 |
| Stable collectors | `github_repo`、`github_topic`、`generic_web`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page` | P3 targeted suite 覆盖 manual_json Source/Task/TaskRun 写入和可见性；GitHub Topic Radar、dataset export、schedule approval 未纳入 P3 | API docs、collector tests、Automation service 可见 | GitHub API-first 和 independent-site 深化仍需后续平台包验收 | M3/M4 |
| PlatformPackage | 3 个可解释、可验收平台包：independent site、GitHub API-first、public page preflight | 上一轮 authenticated smoke 未单独列出平台包内容验收 | `list_platform_packages()` 返回 3 个 package；E2E 覆盖应用平台包 | 平台包仍是静态 catalog；缺 version、owner、acceptance registry | P1/P3 |
| CapabilityProbe | Agent Reach 风格 no-read/no-write doctor，区分 backend candidates 和 forbidden actions | 生产未单独验证 probe history | `list_capability_probes()`、`_probe_agent_reach_channel()`、TS types/UI 可见 | 缺 probe run history、probe evidence asset、operator remediation UI | P1 |
| Agent Reach fusion | 作为能力路由和 doctor，不直接读平台内容 | 线上未知 | 本地逻辑只允许 `agent-reach doctor --json`，缺失时返回 `missing_tool` | 未安装/线上运行态未知；尚未沉淀 channel-level evidence | P0/P1 |
| BrowserDiagnostic assets | BrowserDiagnosticRun/Job/JobRun 只读证据资产，selector/network/promotion/redaction 可审计 | 上一轮 closeout 记录 production schema 已到 `202606110023` | 本地 migrations `021/022/023`、routes、service、UI、E2E、P4 dedicated-CDP guard 可见 | schema 已部署的记录不等于生产 browser-harness run；selector/network 扩展和生产 gate 仍分开 | P4 complete / P5 |
| Browser artifact retention | metadata-only 当前阶段，截图/trace/HAR 需单独批准 | 生产未验证 | retention workflow 已定义 `files_written=false` 等不变量 | 缺自动 TTL/cleanup job；未实现 approved artifact retention mode | P1 |
| GitHub Tool Radar | API-first 样板，能进入 Dataset/Export/Drift/Report | P3 未覆盖 GitHub Topic Radar，因为它属于外部 API/provider-like 平台验收边界；M3-1/M3-2/M3-3/M3-4/M3-5 local slices 已通过 API/web tests | 本地覆盖 Topic Radar -> dataset -> report -> drift；dataset 字段、schema/provenance、report risk sections、drift signal groups 和 web E2E 已扩展；生产 gate runbook 已新增 | 授权生产 GitHub run 仍未完成 | P0/M3 |
| Independent site | Shopify-style 商品发现、fan-out、dataset、drift、export | P3 未覆盖 URL 到 Dataset/export/drift 全链路，因为 schedule approval/export 被拆出 P3 | 平台包和 service 覆盖 title/price/currency/availability/sku/canonical_url | 缺 pagination/sitemap/canonical 去重增强；缺 variant/image/brand/category；授权测试站 E2E 未执行 | P0/M4 |
| Public Web/RSS/Docs | 公开网页、RSS/Atom、docs 更新监控平台包 | 只有 page availability，不是采集链路 | `public-page-structure-preflight` 已有，generic_web 可作为基础 | RSS/Docs 还不是一等平台包；缺 feed parser、doc diff、dataset schema、drift/report | P1/M5 |
| Video transcript import | YouTube/B 站公开视频 metadata/transcript import，不下载媒体 | 无 | PRD2 已定义边界 | 缺 import schema、source provenance、copyright/subtitle fields、UI flow | P1/M6 |
| Public community trend | 聚合主题趋势，不做人级画像 | 无 | PRD2 已定义边界 | 缺 V2EX 等公开社区 package、aggregate schema、redaction/privacy guard | P1/P2 |
| Marketplace | Amazon/marketplace 走官方 API、授权导出或人工导入优先 | 无 | PRD2 已定义边界 | 缺 import template、API credential boundary、sample dataset、cleanup/audit | P2 |
| RPA/no-code | Browse AI/Octoparse/影刀/Power Automate/UiPath 作为 workflow/import 连接器 | 无 | PRD2 已定义边界 | 缺 ExternalToolSnapshot 或 manual_json import review flow | P2 |
| Social SOP/import-only | Twitter/X、小红书、Instagram、LinkedIn 默认 SOP/import-only | 无 | PRD2 已定义边界 | 缺 SOP templates、field templates、UI 禁用自动采集按钮的 package states | P3 |
| Report/Alert/Notification | Report/Alert/Notification 绑定 Evidence 和授权发送边界 | P3 覆盖 AlertRule/AlertEvent 和短暂 in-app Notification 创建/cleanup；未执行 Report send 或 external email send | routes/service/test 覆盖 report、drift alert、站内通知、邮件发送路径 | Report send、邮件发送、调度变更仍需独立 authorization gate | P5 governance |

## 3. Deployed State vs Local Worktree Gap

当前最重要的 gap 已从“本地最新 PRD2/M2 能力和线上部署证据没有对齐”，转为“发布 closeout 已记录，但剩余 side-effect gate 不能被 public/auth smoke 覆盖”。

| Gap | Why it matters | Required action |
|---|---|---|
| Fresh live state not rechecked in this docs-only pass | 已由 P1/P2/P3 前后置检查补齐 | P1/P2/P3 均记录 live SHA、health、schema、compose、public page smoke |
| Authenticated smoke vs production write E2E | login/session/read-style smoke 不证明 Source/Task/Dataset/Report/Alert 写入链路可清理 | P3 已完成 scoped L4 production write E2E，使用一次性账号/workspace 和 cleanup register；full suite 仍另行 gate |
| Demo state unknown after deploy | 已由 P1 dry-run 和 P2 execute/recount 补齐 | P2 demo cleanup execute 后 recount 全零；demo seed 未执行且当前无证据要求补种 |
| External side effects remain ungated | provider call、email send、scheduler mutation 的风险和回滚不同 | P5 已分别建立授权 envelope 并完成 read-only inventory；下一步选择一个 L4 live gate |
| Real browser runtime remains separate | schema 和 job/run 资产不代表生产 browser-harness 已启动 | P4 已做 local-only dedicated-CDP adapter guard；生产 run 仍需单独 gate |

## 4. Execution Plan

### Track R0 - Release Boundary And Evidence Alignment

目标：先把“当前线上状态”和“准备上线的本地能力”对齐，避免继续在未发布代码上制定生产结论。

| ID | To do | Files/commands | Acceptance evidence | Boundary |
|---|---|---|---|---|
| R0-1 | 建立 release scope 清单 | `git status --short`、`git diff --stat`、PRD/API/workflow docs | 列出本次要发布的 code/doc/migration 文件，排除无关 dirty files | docs/code audit only |
| R0-2 | 本地门禁 | `pnpm lint:web`、`pnpm test:web`、`bash scripts/verify-mvp.sh` | 本地 lint/unit/build/E2E/MVP smoke 通过或列出阻断项 | local validation |
| R0-3 | DB migration rehearsal | `bash scripts/verify-mvp.sh --with-db` 或 `uv run alembic upgrade head` | 本地 DB 可从 `020` 升到 `023`，downgrade/recovery notes 清楚 | local DB only |
| R0-4 | 部署前 schema gate | 检查 `apps/api/alembic/versions` 和 health contract | 准备发布版本的 `schema_head=202606110023` 可解释 | no production write |
| R0-5 | 发布后只读 smoke | 上一轮 closeout 记录 `/api/health`、核心页面、authenticated API smoke | 生产 health 显示 `schema_revision/schema_head=202606110023`，页面可达，API smoke 通过 | L3 production read-only / authenticated smoke |
| R0-6 | 授权生产 E2E | 专用测试 workspace，最小 cleanup-covered write path | P3 targeted real API E2E `16 passed`；cleanup dry-run/execute/recount 全零 | done scoped L4; full suite remains separate |

Do not claim full real suite, provider execution, email delivery, scheduler mutation, dataset export, or production browser-harness run until the corresponding L4 gate is completed.

### Track M3 - GitHub API-first Deepening

目标：把 GitHub 做成第一个 PRD2 “API-first 平台包样板”，形成可复用的采集、数据集、漂移和报告标准。

| ID | To do | Suggested files | Acceptance |
|---|---|---|---|
| M3-1 | 扩展 GitHub collector 原始字段 | collector/service/tests | Status: local complete 2026-06-23。支持 best-effort latest release、README metadata、license、default branch、open issue activity、commit freshness |
| M3-2 | Dataset schema version/provenance | dataset service、API schema、docs | Status: local complete 2026-06-23。`github_tool_radar` DatasetVersion export preview 写入 `schema_version=github_tool_radar.v2`、field source、collector version、endpoint origin、lineage/provenance |
| M3-3 | Report 增强 | `automation_service.py`、report UI、tests | Status: local complete 2026-06-23。报告已透出维护风险、安装/溯源入口、适用采集场景、不适用边界和 schema version |
| M3-4 | Drift 规则增强 | drift service/tests | Status: local complete 2026-06-23。stars/forks/issues/release freshness/field missingness/repository coverage/commit freshness 能分层输出 `signal_groups` |
| M3-5 | E2E 和 cleanup | web E2E + API integration + authorized production runbook | Status: local complete 2026-06-23。Web mock E2E 覆盖 schema/provenance、report risk sections、drift signal groups；新增 `workflow-github-api-first-production-gate-stable.md`；生产写入只在授权后执行，并可清理或按策略保留 |

Acceptance commands:

```bash
pnpm lint:web
pnpm test:web
bash scripts/verify-mvp.sh
bash scripts/verify-mvp.sh --with-db
```

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
| P0 | Release boundary and migration to `023` | 上一轮 closeout 已记录完成；当前只保留为历史 P0 | release/evidence |
| P0/P1 | Post-deploy boundary inventory | 部署后仍要盘点 demo、E2E fixture、email channel 和 live state | read-only/dry-run |
| P0 | GitHub API-first | 官方 API、低风险、已有 collector/Dataset/Report path | API collector |
| P0 | Independent site / Shopify-style | 已有业务闭环，能产生电商 dataset/drift | public page collector |
| P1 | Public Web/RSS/Docs | 低风险、高复用，适合训练/竞品/文档更新 | URL/feed/docs collector |
| P1 | Video transcript import | 内容趋势价值高，但应 import metadata/transcript | import |
| P1/P2 | Public community trend | 可做聚合趋势，不做人级画像 | aggregate import/collector |
| P2 | Marketplace | 商业价值高，平台政策和账号边界复杂 | API/import first |
| P2 | RPA/no-code | 适合接业务后台导出结果，不应内置主账号自动化 | ExternalToolSnapshot |
| P3 | Twitter/X、小红书、Instagram、LinkedIn | 登录态、个人数据和平台限制风险高 | SOP/import-only |

## 6. Immediate Next To Do

按当前证据，P1/P2/P3/P4 已完成，P5 provider/email/scheduler gate 单项计划、read-only inventory 和 B1 one-test-email 已完成；M3 GitHub API-first M3-1/M3-2/M3-3/M3-4/M3-5 local slices 已完成。下一轮建议按 `workflow-github-api-first-production-gate-stable.md` 打开一个明确授权的 production GitHub package gate；也可以选择一个仍未完成的 P5 L4 live gate。不应把本地 browser smoke 写成生产 real browser run，也不应把一封 test email 写成 product/report/subscription email 验收。

1. B1 one-test-email 已完成：recipient `zhoujianaaa123@gmail.com`，max_sends=1，`delivered=true`。
2. M3-5 已完成：GitHub package local E2E/runbook、cleanup/retention policy 和生产授权前置条件已补齐。
3. M3 production gate 前置：需要 exact GitHub topic/repo、是否允许 live GitHub API collection、是否允许 Dataset save/report asset/export，以及每个 side effect 的清理或保留策略；默认不允许 provider/email/scheduler/browser/export。
4. GitHub dataset export 仍属于 D live gate，需要 exact dataset/version IDs、format、retention/cleanup policy 和 checksum evidence。
5. Provider A2 仍 blocked until configured：生产当前 `llm_provider=mock`，无 model/key。
6. Scheduler C1 需要 exact dataset/version/task set、cron、previous state capture 和 rollback。
7. Dataset export、生产 browser run、截图/trace/HAR 文件写入仍分别保留独立授权。
8. P4 的下一技术延伸是 dedicated-CDP selector DOM evaluation 与 network metadata summary，但不直接进入生产执行。

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

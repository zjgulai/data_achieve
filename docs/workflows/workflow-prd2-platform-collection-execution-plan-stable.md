---
title: PRD2 平台采集执行计划和 To do
doc_type: workflow
module: automation
topic: prd2-platform-collection
status: stable
created: 2026-06-21
updated: 2026-07-02
owner: self
source: human+ai
---

# PRD2 平台采集执行计划和 To do

## 0. 证据边界

本计划只定义下一阶段执行方案，不代表已完成实现、部署或生产写入。

当前已复核事实：

1. `docs/product/product-prd-data-intelligence-hub-stable.md` 已调整为 PRD 2.0 当前源头版本。
2. 生产只读 health 在 2026-07-02 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`schema_revision=202606110026`、`schema_head=202606110026`、`scheduler_enabled=true`。
3. 2026-07-02 active app working tree `/opt/data-achieve-scrapy/app` 的 `HEAD` 与 `/opt/data-achieve-scrapy/app/.deploy-sha` 均为 `b81a4be2a47f387d381293db7c4b2932128f6708`，API/Web compose working directory 仍沿用 `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`。
4. 本地 `codex/release-3b-on-428` 与 `origin/codex/release-3b-on-428` 已推进到 docs-only follow-up commit `d96c0b32193e4b4ff4302b7b3b11a770b0b8c6fd`；生产仍运行 release commit `b81a4be2a47f387d381293db7c4b2932128f6708`；`main` 与 `origin/main` 仍为 `42851929d59d82708c9380d36347ca721979297d`；Loop 36 已创建 draft PR #10，最终 branch-head 检查观测为 no checks reported，后续 merge 仍是单独 source-control gate。
5. 后续历史记录显示 M3 GitHub API-first 已完成一次小范围 production package gate 并清理；下一步是更大 scope、retention/export/scheduler gate。
6. 后续历史记录显示 M5 Public Web/RSS/Docs 已完成 RSS/docs/page Dataset、drift、report、export、scheduler tick、retained canary refresh、cleanup dry-run 与 default 168h TTL final observation；剩余 cleanup execute、provider/email/browser runtime。
7. M4 独立站 collector 和 Dataset/drift 样例已进入当前生产代码基线；2026-06-29 已补本地 deterministic fixture E2E gate，但真实授权测试站 L4 仍未执行。
8. 本轮状态同步不执行生产写入、provider call、email send、cleanup execute、scheduler mutation、production browser run 或 browser artifact write。
9. 2026-06-29 本地运行安全第一切片已完成并通过 `scripts/verify-mvp.sh`：API ruff/mypy/pytest、Alembic head、Web lint/unit/build、Playwright E2E 均通过；这仍只属于 local validation，不等于生产运行安全门禁。
10. 2026-06-29/30 Batch 1b/1c 已补 auto freshness retry budget 本地合同：`max_retry_attempts`、`retry_attempts_used`、`retry_budget_exhausted`；手动 Task run、Dataset export create、Report send、drift alert notification/email send、Report asset create、subscription run/retry、email-channel test、email provider-live gate preflight、email provider live-send readiness 和 email provider live-send gate default-deny 已补 `Idempotency-Key` replay/只读 readiness 本地合同。L4 provider 生产发送 runbook 已补，生产 side-effect 日志仍待后续授权。

## 1. 执行总原则

1. 先加深已打通平台，再新增高风险平台。
2. 先能力探测和只读证据，再创建采集资源。
3. 先官方 API、授权导出、人工导入，再考虑浏览器诊断。
4. Agent Reach 先内化为 `CapabilityProbe` 思路，不直接扩成多个生产 collector。
5. browser-harness 先内化为 `BrowserEvidenceRunner`，输出 selector/network/page evidence，不直接创建 Dataset。
6. 每个切片必须区分 `docs-only`、`local validation`、`production read-only smoke`、`authorized production E2E`。
7. 任何生产写入、邮件发送、provider call、登录态复用、cookie 导出、调度变更，都必须另行获得显式授权。

## 2. 优先级总览

| 优先级 | 工作包 | 目标结果 | 默认边界 |
|---|---|---|---|
| P0 | `run-safety-baseline` | 已补 task run lock、collector timeout、scheduler running-task skip、前端 submitting guard、auto freshness retry budget、手动 Task run、Dataset export create、Report send、drift alert notification/email send、Report asset create、subscription run/retry、email-channel test、provider-live preflight、live-send readiness 和 live-send default-deny `Idempotency-Key` replay；L4 provider 生产发送 runbook 已补 | local validation 已通过；不触发生产写入 |
| P0 | `shopify-independent-ecommerce-e2e` | 授权测试站点从 discovery/fan-out/batch 到 DatasetVersion/export/drift 的闭环；本地 fixture gate 已覆盖 platform package、export download、drift event 和 export history；WebScraper.io 公开测试站 local API E2E 已验证静态 microdata 商品页 | 当前证据是 L2 + public test-site read；真实生产/客户站只处理授权公开页面，需要另起 cleanup/retention register |
| P0 | `platform-package-governance` | 本地 API/UI 合同已补平台包 version、owner、lifecycle status、acceptance registry、evidence grade、authorization required、cleanup policy 和禁止动作；后续补持久化/自定义层 | 不把 sop_only/import_only 平台显示为自动采集；不把 scoped L4 写成全平台规模化完成 |
| P1 | `github-api-first-scale` | 扩展 GitHub API-first 大 scope、retention、export、scheduler | 官方 API 为事实源；生产写入 E2E 单独授权 |
| P1 | `browser-evidence-governance` | BrowserDiagnostic evidence asset 与人工 promotion gate | 不创建 Source/Task/Dataset，不写截图/trace/HAR 文件，除非 retention 已批准 |
| P1 | `public-web-rss-docs-followup` | 推进 cleanup execute 决策、provider/email gate、post-cleanup recount | 公开源；side effect 单独授权 |
| P1 | `video-public-transcript-import` | YouTube/B 站公开视频 metadata/transcript 导入 | 不下载媒体资产，不采私人内容 |
| P1/P2 | `public-community-trend` | V2EX/公开社区聚合趋势 | 聚合层，不做人级画像 |
| P2 | `marketplace-authorized-import` | Amazon/marketplace API 或授权导入 demo | API/import 优先，不默认页面抓取 |
| P2 | `rpa-no-code-import-connectors` | RPA/no-code 作为 workflow/import 连接器 | 不复用主账号 cookie 做无人值守采集 |
| P3 | `social-sop-import-only` | Twitter/X、小红书、Instagram、LinkedIn SOP 和导入模板 | 不做自动抓取、不导出 cookie、不做反检测 |

## 3. Milestone 顺序

### Milestone 0：文档与门禁同步

目标：确保 PRD、执行计划、API contract、架构文档不会继续漂移。

To do：

| ID | 任务 | 产出 | 验收 |
|---|---|---|---|
| M0-1 | 更新 PRD 2.0 当前控制面 | `docs/product/product-prd-data-intelligence-hub-stable.md` | 文件有 frontmatter，清楚写出事实/推断/边界 |
| M0-2 | 建立本执行计划 | 本文件 | 每个工作包都有目标、边界、验收 |
| M0-3 | 下一轮实现前同步 API/架构 | `docs/api/...`、`docs/architecture/...` | 新合同先入 docs，再进入代码 |
| M0-4 | PlatformPackage governance 本地合同 | API schema/service、Automation UI、integration test | `version/owner/lifecycle_status/evidence_grade/authorization_required/acceptance_registry/cleanup_policy/forbidden_actions` 均可通过 API/UI 看到；production unchanged |

当前状态：M0-1、M0-2 已在 docs-only 阶段完成；M0-3/M0-4 已在 Batch 3 本地合同切片执行，仍未部署生产。

### Milestone 1：CapabilityProbe 合同层

目标：把 Agent Reach 的“渠道候选 + doctor + 修复建议”内化为本项目的平台能力探测资产，不直接读取平台内容。

To do：

| ID | 任务 | 建议文件 | 完成条件 |
|---|---|---|---|
| M1-1 | 定义 `capability_probe.v1` schema | `docs/api/api-contract-data-intelligence-hub-stable.md`、`apps/api/src/data_intelligence_hub/schemas/automation.py` | 字段包含 `platform_id`、`backend_candidates`、`doctor_status`、`credential_mode`、`execution_boundary`、`allowed_outputs`、`forbidden_actions` |
| M1-2 | 定义 `agent_reach_channel_probe.v1` contract | API docs + schema | 支持 `installed=false`、`blocked_missing_tool`、`requires_login`、`requires_proxy`、`active_backend` |
| M1-3 | 后端 no-read probe service | `automation_service.py`、`automation.py` | 未安装 `agent-reach` 时返回 blocked，不报成功；安装时仅允许 doctor/probe，不调用 read/search |
| M1-4 | 前端显示能力探测卡 | `automation-workbench.tsx`、`types/automation.ts`、`lib/api/automation.ts` | UI 明确显示“能力探测不等于采集成功” |
| M1-5 | 测试覆盖 | API integration + web unit/E2E | fake installed / missing / blocked 三类状态可复现 |

禁止动作：

1. 不在生产 API worker 中自动安装 Agent Reach。
2. 不自动读取 Twitter/X、小红书、Reddit 等登录态平台。
3. 不把 doctor green 写成 Source/Task/TaskRun/Dataset。

### Milestone 2：browser-harness 只读证据扩展

目标：把当前 `ephemeral_browser_harness_probe` 从 page info 扩展到 selector 求值和 network metadata，用于判断“是否应该采集”，而不是直接采集。

To do：

| ID | 任务 | 建议文件 | 完成条件 |
|---|---|---|---|
| M2-1 | 扩展 `BrowserDiagnosticJobRun` result contract | API docs、schema、model/migration 如需字段 | result 包含 `selector_evaluations`、`network_metadata_summary`、`promotion_gate`、`redaction_summary` |
| M2-2 | fake CLI 覆盖 selector/network 成功与异常路径 | API tests | fixture 能覆盖 selector missing、network blocked、timeout_case、redaction_case |
| M2-3 | real CLI 本机只读 smoke | `tmp/` 证据脚本 | 只对 `https://example.com/` 或明确授权测试页执行；输出不含 cookie/header/body |
| M2-4 | artifact retention 方案 | workflow 或 architecture doc | 截图/trace/HAR 文件写入目录、TTL、清理命令、redaction 和生产持久化策略明确前，保持 `files_written=false` |
| M2-5 | UI 结果面板升级 | `automation-workbench.tsx` | 明确区分 snapshot replay、real browser probe、blocked/failed 状态 |

禁止动作：

1. 不复用用户主 Chrome profile。
2. 不导出 cookie，不保存敏感 headers/body。
3. 不对验证码、登录墙或反爬页面做绕过。
4. 不从 BrowserDiagnosticJobRun 直接创建 Source/Task/Dataset。

### Milestone 3：GitHub API-first 深化

目标：把 GitHub Tool Radar 做成第一个完整 API-first 平台样板。

To do：

| ID | 任务 | 当前状态 | 建议文件 | 完成条件 / 下一步 |
|---|---|---|---|---|
| M3-1 | 扩展 GitHub 字段 schema | done_main_71b52be | collector/service/schema/tests | README 摘要、issue activity、commit freshness 已随 PR #5 合并 |
| M3-2 | Dataset schema 版本化 | done_main_71b52be | dataset service + API docs | `github_tool_radar` schema version、collector schema versions、per-field source 已随 PR #5 合并 |
| M3-3 | Report 增强 | done_main_71b52be | report response + frontend | README、issue activity、freshness summary 已随 PR #5 合并 |
| M3-4 | Drift 规则增强 | done_main_71b52be | drift service/tests | stars/forks/issues/release freshness/field missingness 分层输出已随 PR #5 合并 |
| M3-5 | 生产授权 E2E 和 cleanup | done_scoped_l4_small | `tmp/` 证据脚本 | 已完成一次 `topic=web-scraping`、`max_repositories=3` 小范围 package gate 并清理；大 scope rate-limit、retention/export/scheduler 仍需单独授权 |

默认事实源：

1. GitHub 官方 API 是正式事实源。
2. Agent Reach/gh CLI 只做能力路由、补充检索或本地诊断。
3. browser-harness 只用于 UI/README 页面结构补充，不作为主采集路径。

### Milestone 4：独立站/Shopify-style 深化

目标：把当前独立站平台包从 demo 闭环提升为可训练、可复用、可漂移监控的业务模板。

To do：

| ID | 任务 | 建议文件 | 完成条件 |
|---|---|---|---|
| M4-1 | collection/listing/sitemap 发现增强 | collector + automation service | 已随 PR #6 合并到 `main@67f611e`，实现 canonical、pagination、sitemap URL、去重和 skipped reasons |
| M4-2 | 商品字段增强 | collector/schema/tests | 已随 PR #6 合并到 `main@67f611e`，增加 variant、price range、availability detail、category，并保留 SKU、image、brand、currency、availability |
| M4-3 | Dataset 和 drift 样例 | tests + docs | 已随 PR #7 合并到 `main@8cd3e8f`，覆盖新增/下架、价格变化进入 `product-drift-check` 和 `product-drift-events`；生产部署被 SSH 连接阻断 |
| M4-4a | 本地 deterministic fixture E2E | API integration test | `test_shopify_independent_ecommerce_package_runs_local_authorized_e2e_gate` 覆盖 platform package、discovery、fan-out、batch、DatasetVersion、manual_refresh_only approval、Dataset export/download、drift check/event、dataset/export history；边界为 L2 local validation |
| M4-4b | 真实授权测试站 E2E | local API script + cleanup/retention register | done_local_external_20260629：WebScraper.io 公开测试站 `https://webscraper.io/test-sites/e-commerce/static`，`max_products=2`，same-origin candidates only；本地临时 API DB 跑通 discovery/fan-out/batch/DatasetVersion/manual_refresh_only approval/export download/drift check/drift event，Dataset `row_count=2`、完整度 `100%`、CSV export `966 bytes`、drift event `status=ok`；export 保留在 `apps/api/tmp/m4-independent-site-e2e-20260629-exports/` 供人工复核；不是 production write |

禁止动作：

1. 不处理登录墙、验证码或需要绕过风控的页面。
2. 不把 marketplace 页面抓取混入独立站包。

### Milestone 5：P1 低风险新增平台包

目标：优先新增公开、低风险、能形成结构化 Dataset 的平台包。

To do：

| ID | 工作包 | 首版范围 | 完成条件 |
|---|---|---|---|
| M5-1 | `public-web-rss-docs` | URL、RSS/Atom、公开 docs 更新监控 | Source draft、Dataset preview、drift、report summary |
| M5-2 | `video-public-transcript-import` | YouTube/B 站公开视频 metadata/transcript import | 不下载媒体文件；保留字幕来源、URL、发布时间、授权边界 |
| M5-3 | `public-community-trend` | V2EX 或其他公开社区聚合 | 只采主题、链接、时间、回复数、聚合热度，不做人级画像 |

升级门槛：

1. 有公开来源或官方 API。
2. 可定义稳定 schema。
3. 可进入 Dataset/Export/Drift。
4. 不需要登录态、cookie、验证码或反检测。

### Milestone 6：P2/P3 边界型平台

目标：把高商业价值但高风险的平台先做成授权导入、API-first 或 SOP，而不是默认自动抓取。

To do：

| ID | 工作包 | 首版范围 | 完成条件 |
|---|---|---|---|
| M6-1 | `marketplace-authorized-import` | Amazon/SP-API、后台导出 CSV、字段模板 | 至少一个 import/API-first demo；UI 标注 API/import 优先 |
| M6-2 | `reddit-aggregate-import` | 聚合趋势导入或人工授权 read-only | 不采个人画像；登录态风险写入边界 |
| M6-3 | `rpa-no-code-import-connectors` | Browse AI、Octoparse、影刀、Power Automate、UiPath 等工作流结果导入 | 外部工具结果以 `ExternalToolSnapshot` 或 `manual_json` 导入，经人工确认 |
| M6-4 | `social-sop-import-only` | Twitter/X、小红书、Instagram、LinkedIn 字段模板和 SOP | 默认 `sop_only`，不出现自动采集按钮 |

禁止动作：

1. 不提供 cookie 导出指导作为产品默认流程。
2. 不做登录绕过、反检测、滚动批采或个人数据画像。
3. 不把 Agent Reach 支持某平台读内容写成 Data Intelligence Hub 已打通该平台。

## 4. 验收门禁

### 本地门禁

优先使用 `.codex/commands.md` 中的命令：

```bash
pnpm lint:web
pnpm test:web
bash scripts/verify-mvp.sh
```

涉及数据库、migration、Dataset、TaskRun、Report、Alert 的切片，再运行：

```bash
bash scripts/verify-mvp.sh --with-db
```

### 生产门禁

| 证据层 | 允许结论 | 不允许结论 |
|---|---|---|
| production read-only smoke | 服务存在、只读接口返回、schema 可见 | 写入链路已通过 |
| authorized production E2E | 指定链路在授权范围内完成写入和清理 | 其他平台已全部打通 |
| cleanup dry-run/execute | 测试产物可清点、可清理 | 生产无风险 |

### 每个工作包的 closeout 必填

1. 修改文件列表。
2. 本地测试命令和结果。
3. 是否做了生产只读 smoke。
4. 是否做了授权生产写入 E2E。
5. 是否触发 provider call、邮件、通知、调度或外部平台读取。
6. 新增或未清理的数据资产清单。
7. 不确定项和下一步。

## 5. 当前 To do 清单

| 优先级 | ID | To do | 状态 | 下一步 |
|---|---|---|---|---|
| P0 | M1-1 | 定义 `capability_probe.v1` API/schema | done | 已同步 API contract、Pydantic schema 和 TS types |
| P0 | M1-2 | 定义 `agent_reach_channel_probe.v1` | done | 已覆盖 missing/blocked/available 三类状态 |
| P0 | M1-3 | 实现 no-read Agent Reach probe | done | 未安装时返回 blocked，不自动安装；安装时只调用 `doctor --json` |
| P0 | M1-4 | 前端能力探测卡 | done | 已放在 `/automation` 平台包矩阵前；只展示边界，不触发采集 |
| P0 | M1-5 | CapabilityProbe 测试覆盖 | done | 已覆盖 missing 和 fake installed doctor-only 路径 |
| P0 | M2-1 | 扩展 `BrowserDiagnosticJobRun` result contract | done | 已新增 `selector_evaluations`、`network_metadata_summary`、`promotion_gate`、`redaction_summary`；无需 migration |
| P0 | M2-2 | fake CLI selector/network 测试 | done | 已覆盖 snapshot replay、fake browser-harness success、selector missing、binary unavailable、timeout_case、redaction_case |
| P0 | M2-3 | 本机 real CLI 授权公开页只读 smoke | blocked_local_daemon | 已对 `https://example.com/` 生成 `tmp/browser-harness-readonly-smoke-20260621.json`；本机 daemon 未响应，`browser_started=false` |
| P0 | M2-4 | artifact retention 方案 | done | 已新增 `docs/workflows/workflow-browser-evidence-artifact-retention-stable.md`；当前阶段保持 `files_written=false` |
| P0 | M2-5 | UI 结果面板升级 | done | 已展示 selector 求值、network metadata、promotion gate 和 redaction 边界 |
| P1 | M2-6 | Production metadata-only no-run gate | local_done | 已新增 `/browser-diagnostic-jobs/{job_id}/production-metadata-run-gate`、前端“生产只读预检”和 targeted 验收脚本；证据等级 `L2-fixture-or-dry-run`，`production_read_only_observed=false`、`run_started=false`、`browser_started=false`、`files_written=false`、`collection_resources_written=false` |
| P0 | M3-1 | GitHub deep fields | done_main_71b52be | README、issue activity、commit freshness 已合并 |
| P0 | M3-2 | GitHub Dataset schema version | done_main_71b52be | schema version、collector schema versions、per-field source 已合并 |
| P0 | M3-3 | GitHub Tool Radar report 增强 | done_main_71b52be | 报告 summary 字段已合并 |
| P0 | M3-4 | GitHub drift 规则增强 | done_main_71b52be | stars/forks/issues/release freshness/field missingness 分层输出已合并 |
| P0 | M3-5 | GitHub production write E2E | done_scoped_l4_small | 已完成一次 `topic=web-scraping`、`max_repositories=3` 小范围 package gate 并清理；下一步是大 scope rate-limit、retention/export/scheduler |
| P0 | M4-1 | 独立站 discovery 深化 | done_main_67f611e | collection/listing/sitemap/canonical 去重、pagination、skipped reasons |
| P0 | M4-2 | 独立站商品字段增强 | done_main_67f611e | variant、price range、availability detail、category、SKU、image、currency、availability |
| P0 | M4-3 | Dataset/drift 样例 | done_current_code_baseline | 新增/下架、价格变化进入 drift check/events；当前生产 release 已更新到 `b81a4be`，`main/origin/main` 仍停在 `42851929` |
| P0 | M4-4a | 授权测试站点本地 fixture E2E | local_done | 已新增 API integration gate：platform package -> discovery -> fan-out -> batch -> DatasetVersion -> export/download -> drift event -> history；未触发生产写入 |
| P0 | M4-4b | 真实授权测试站点 E2E | local_external_done | 已用 WebScraper.io 公开测试站完成 local API E2E；证据等级为 `L2 local validation + public test-site read`，未触发生产写入、provider call、email send、production browser run 或 cleanup execute |
| P0 | RUN-1 | 运行安全第一切片 | local_done | 已通过本地 `verify-mvp`；task lock、timeout、前端 submitting guard 已完成本地验证 |
| P0 | RUN-2 | 运行安全第二切片 | local_done_partial | auto freshness retry budget 已通过 `verify-mvp`；手动 Task run、Dataset export create、Report send、drift alert notification/email send、Report asset create、subscription run/retry、email-channel test、provider-live preflight、live-send readiness 和 live-send default-deny `Idempotency-Key` replay 已补本地合同；剩余 L4 provider 生产发送证据和调度触发生产门禁 |
| P1 | M5-1 | Public Web/RSS/Docs 平台包 | done_scoped_l4 | 已完成小范围 RSS/docs/page Dataset、drift、report、export、scheduler tick、retained refresh、cleanup dry-run 和 default 168h TTL final observation；剩余 cleanup execute、provider/email |
| P1 | EVID-1 | CapabilityProbe/BrowserDiagnostic evidence reference | local_done_partial | CapabilityProbe、BrowserDiagnosticRun/Job/JobRun 已补 `evidence_asset_reference.v1` 响应级引用；BrowserDiagnosticJobRun 已补 Source/Task 候选 preview gate、no-write execution dry-run、显式授权 Source+Task 写 gate；BrowserDiagnosticJob 已补 production metadata-only no-run gate；仍待持久化 EvidenceAsset 表、L3 production read-only browser observation、单独授权 TaskRun/Dataset promotion |
| P1 | M5-2 | Video transcript import | todo | metadata/transcript 导入，不下载媒体 |
| P1 | M5-3 | Public community trend | todo | 优先 V2EX 聚合趋势 |
| P2 | M6-1 | Marketplace authorized import | todo | Amazon API/export/import 模板优先 |
| P2 | M6-2 | Reddit aggregate import | todo | 先 SOP/import-only |
| P2 | M6-3 | RPA/no-code import connectors | todo | 外部工具结果人工确认导入 |
| P3 | M6-4 | Social SOP/import-only | todo | Twitter/X、小红书、Instagram、LinkedIn 不做默认自动采集 |

## 6. 下一轮推荐执行顺序

1. `Batch 0` 状态归一：PRD2、架构、gap plan 和本执行计划同步到 2026-06-29 当前事实。
2. `Batch 1a` 运行安全底座第一切片：task run lock、collector timeout、scheduler running-task skip、前端 submitting state 已完成本地验证。
3. `Batch 1b/1c` 运行安全剩余项：retry budget policy 已完成本地验证；手动 Task run、Dataset export create、Report send、drift alert notification/email send、Report asset create、subscription run/retry、email-channel test、provider-live preflight、live-send readiness 和 live-send default-deny 的 `Idempotency-Key` replay/只读 readiness 已完成本地合同；L4 provider 生产发送证据仍待后续授权。
4. `Batch 2` M4-4 独立站授权 E2E：M4-4a 本地 fixture gate 已完成；M4-4b 已完成 WebScraper.io 公开测试站 local API E2E。若继续升级，只能另起 production/customer-site gate，明确真实站 URL、允许写入资源、export retention、cleanup dry-run/execute 和是否允许 scheduler/provider/email。
5. `Batch 3` PlatformPackage governance：补 version、owner、acceptance registry、evidence grade、禁止动作和 lifecycle status。
6. `Batch 4` 已验证平台扩大：GitHub 大 scope gate、Public Web/RSS cleanup execute 决策、email/scheduler/provider 独立 gate。
7. `Batch 5` 导入型平台：ExternalToolSnapshot、Video transcript import、Public community aggregate、Marketplace import、Social SOP/import-only。

## 7. Side-effect Idempotency Evidence Matrix

| Scope | Current enforcement | Evidence | Remaining |
|---|---|---|---|
| Task run duplicate/concurrent execution | Backend task row lock rejects `running`; scheduler maps lock conflict to `skipped_running`; frontend primary submit has in-flight guard; manual `POST /api/tasks/{task_id}/run` supports optional `Idempotency-Key` replay by workspace/task/key hash | `tests/unit/test_scheduler.py` covers running-task skip; `/api/tasks/{task_id}/run` returns 409 for running/non-enabled task; `tests/integration/test_sources_tasks.py` covers same-key replay returning original run with `idempotency_replayed=true` and no raw key stored | Operator UI explaining duplicate run vs duplicate raw rows; extend the same contract to non-task side-effect endpoints |
| Raw record storage after repeated successful run | `content_hash` dedupe skips duplicate raw records | `tests/integration/test_sources_tasks.py` duplicate manual_json run expects `raw_record_deduplicated` | Operator UI explaining duplicate run vs duplicate raw rows |
| BrowserDiagnosticJob creation | Same analysis/plan/diagnostic input reuses existing job | Integration test duplicate job returns original `id` | Extend reuse evidence to all browser diagnostic write endpoints |
| Public content schedule approval duplicate task ids | Duplicate task ids are blocked with `duplicate_task_id`; `run_started=false` | Integration test schedule approval duplicate task path | General idempotency key for repeated HTTP request replay |
| Dataset export side effect | `POST /api/automation/product-dataset-exports` supports optional `Idempotency-Key` replay by workspace/dataset/version/export_format/key hash; repeated same-key request returns the original `DatasetExportJob` and download URL | `tests/integration/test_sources_tasks.py` covers same-key export replay with `idempotency_replayed=true`, one export history row and no raw key stored | Operator UI can surface replay/duplicate export meaning; production deployment gate still separate |
| Report send side effect | `POST /api/reports/{report_id}/send` requires `authorized=true` + `confirm_send=true` and supports optional `Idempotency-Key` replay by workspace/report/channels/key hash; repeated same-key request returns original delivered/skipped channels and does not create duplicate in-app notification | `tests/integration/test_reports_alerts_notifications.py` covers missing confirmation rejection, same-key replay, no raw key stored and one notification | Production deployment/write gate still separate |
| Drift alert notification/email side effects | `POST /api/automation/product-drift-alert-notifications` and `/product-drift-alert-emails` support optional `Idempotency-Key`; notification replay returns existing notification, email replay reads AlertEvent delivery audit and skips SMTP/provider call | `tests/integration/test_sources_tasks.py` covers same-key notification and email replay with hash evidence; email replay asserts provider skip boundary wording | Operator UI can surface replay state; production provider send stays behind L4 runbook |
| Report asset / subscription side effects | `github-tool-report-assets`、`public-content-report-assets`、report subscription run/retry support optional `Idempotency-Key` replay; subscription run/retry also require explicit `authorized` + `confirm_*` body | `tests/integration/test_sources_tasks.py` covers report asset same-key replay and no raw key stored; `tests/integration/test_reports_alerts_notifications.py` covers subscription run/retry replay and no duplicate Report/notification/email attempt | Production deployment/write gate remains separate; production provider send stays behind L4 runbook |
| Email channel / provider send side effects | `email-channel/test`、`provider-live-gate`、`live-send-readiness`、`live-send` 分层：test 支持 replay，preflight 只写 gate run，readiness 只读返回配置/allowlist/channel 清单，live-send 强制 `gate_run_id`、`approval_id` 和 `Idempotency-Key`；默认配置 deny 并返回 `provider_call_attempted=false` | `tests/integration/test_reports_alerts_notifications.py` covers readiness inventory、missing confirmation/key rejection、same-key replay、default-deny 和 fake sender replay without duplicate provider call | Production provider send stays behind L4 runbook and SMTP/provider evidence |

所有 batch 必须继续区分 `docs-only`、`local validation`、`production read-only smoke`、`authorized production E2E`、`provider call`、`email send`、`production browser run` 和 `cleanup execute`。

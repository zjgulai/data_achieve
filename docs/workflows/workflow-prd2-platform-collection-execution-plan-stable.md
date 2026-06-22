---
title: PRD2 平台采集执行计划和 To do
doc_type: workflow
module: automation
topic: prd2-platform-collection
status: stable
created: 2026-06-21
updated: 2026-06-22
owner: self
source: human+ai
---

# PRD2 平台采集执行计划和 To do

## 0. 证据边界

本计划只定义下一阶段执行方案，不代表已完成实现、部署或生产写入。

当前已复核事实：

1. `docs/product/product-prd-data-intelligence-hub-stable.md` 已调整为 PRD 2.0 当前源头版本。
2. 生产只读 health 在 2026-06-21 返回 `production`、`ok`、`database=connected`、`schema=current`、`scheduler_enabled=true`。
3. 本机 `browser-harness` 可执行，`browser-harness --doctor` 显示 Chrome running、daemon alive，但 active browser connections 为 0。
4. 本机当前未找到 `agent-reach` 命令。
5. 本轮没有做业务代码修改，没有创建 Source/Task/TaskRun/Dataset/Report/Notification，没有 provider call，没有生产写入。
6. 2026-06-22 已复核 `origin/main=71b52be`，PR #5 已合并 M3 GitHub provenance/drift 深化；API/Web Quality Gate 为 success，`Web Real API E2E (manual)` 在 workflow 中为 skipped。
7. `codex/m4-independent-site-depth` 已通过 PR #6 合并到 `main@67f611e`，覆盖 M4-1/M4-2 独立站 discovery 和商品字段增强；不代表生产写入 E2E 或授权测试站 E2E 已完成。
8. 当前 `codex/m4-dataset-drift-samples` 分支补齐 M4-3 Dataset/drift 样例；新增/下架/价格变化已有本地 API 集成测试覆盖，且 `scripts/verify-mvp.sh` 已通过；仍需完成 PR、合并、部署和生产只读验收。

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
| P0 | `capability-probe-contract` | 新增平台能力体检合同和 UI/文档入口 | no-read/no-write，doctor 不等于采集成功 |
| P0 | `browser-evidence-selector-network` | 扩展浏览器只读证据到 selector 求值和 network metadata | 不创建 Source/Task/Dataset，不写截图/trace/HAR 文件，除非 retention 已批准 |
| P0 | `github-api-first-deepening` | 深化 GitHub Tool Radar 字段、Dataset 和 Report | 官方 API 为事实源 |
| P0 | `independent-site-depth` | 深化独立站 collection/sitemap/product 字段和漂移 | 只处理授权公开站点 |
| P1 | `public-web-rss-docs` | 新增公开网页/RSS/文档更新平台包 | 公开源，只读或人工确认写入 |
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

当前状态：M0-1、M0-2 已在本轮 docs-only 完成；M0-3 等下一轮实现前执行。

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
| M3-5 | 生产授权 E2E 和 cleanup | local_and_l3_readonly_done | `tmp/` 证据脚本 | 本地门禁和 production read-only smoke 已完成；生产写入需单独授权，创建的 Source/Task/Dataset/Report 必须可 dry-run 清点并清理 |

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
| M4-3 | Dataset 和 drift 样例 | tests + docs | 当前分支本地已覆盖新增/下架、价格变化进入 `product-drift-check` 和 `product-drift-events`；`scripts/verify-mvp.sh` 已通过，PR、合并和部署仍待完成 |
| M4-4 | 授权测试站 E2E | Playwright/API script | 能从 URL 到 Dataset/export/drift 完整跑通并清理 |

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
| P0 | M3-1 | GitHub deep fields | done_main_71b52be | README、issue activity、commit freshness 已合并 |
| P0 | M3-2 | GitHub Dataset schema version | done_main_71b52be | schema version、collector schema versions、per-field source 已合并 |
| P0 | M3-3 | GitHub Tool Radar report 增强 | done_main_71b52be | 报告 summary 字段已合并 |
| P0 | M3-4 | GitHub drift 规则增强 | done_main_71b52be | stars/forks/issues/release freshness/field missingness 分层输出已合并 |
| P0 | M3-5 | GitHub production write E2E | pending_authorization | 明确测试 workspace、写入范围、cleanup register 后才能执行 |
| P0 | M4-1 | 独立站 discovery 深化 | done_main_67f611e | collection/listing/sitemap/canonical 去重、pagination、skipped reasons |
| P0 | M4-2 | 独立站商品字段增强 | done_main_67f611e | variant、price range、availability detail、category、SKU、image、currency、availability |
| P0 | M4-3 | Dataset/drift 样例 | local_verified_pending_pr | 新增/下架、价格变化进入 drift check/events；`scripts/verify-mvp.sh` 已通过，PR、部署待完成 |
| P1 | M5-1 | Public Web/RSS/Docs 平台包 | todo | 先做公开 feed/docs fixture |
| P1 | M5-2 | Video transcript import | todo | metadata/transcript 导入，不下载媒体 |
| P1 | M5-3 | Public community trend | todo | 优先 V2EX 聚合趋势 |
| P2 | M6-1 | Marketplace authorized import | todo | Amazon API/export/import 模板优先 |
| P2 | M6-2 | Reddit aggregate import | todo | 先 SOP/import-only |
| P2 | M6-3 | RPA/no-code import connectors | todo | 外部工具结果人工确认导入 |
| P3 | M6-4 | Social SOP/import-only | todo | Twitter/X、小红书、Instagram、LinkedIn 不做默认自动采集 |

## 6. 下一轮推荐执行顺序

1. `M1-1` 到 `M1-5` 已完成，能力探测合同已立住。
2. `M2-1`、`M2-2`、`M2-4`、`M2-5` 已完成；`M2-3` 留作本机 daemon 修复后的重试项。
3. `M2-3` 重试前需要先让 `browser-harness --doctor` 达到 `daemon alive` 和 active browser connection 可用；仍只允许 `https://example.com/` 或明确授权测试页。
4. 当前 browser evidence runner 继续保持 `files_written=false`，不保存截图/trace/HAR 新文件。
5. M3-1 到 M3-4 已随 PR #5 合并；M3-5 仍需单独生产写入授权，并在执行前确定测试 workspace、允许写入资源、cleanup register 和 dry-run/execute 命令。
6. 当前下一步是为 `M4-3` 创建 PR、合并、部署和生产只读验收；之后进入 `M4-4` 授权测试站 E2E，或并行准备 `M5-1` Public Web/RSS。
7. P2/P3 只在 P0/P1 证据链稳定后进入，且默认以 API/import/SOP 为主。

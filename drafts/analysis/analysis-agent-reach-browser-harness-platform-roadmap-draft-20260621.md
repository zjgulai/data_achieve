---
title: Agent Reach 与 Browser Harness 融合后的平台采集优先级草案
doc_type: analysis
module: automation
topic: agent-reach-browser-harness-platform-roadmap
status: draft
created: 2026-06-21
updated: 2026-06-21
owner: self
source: human+ai
---

# Agent Reach 与 Browser Harness 融合后的平台采集优先级草案

## 0. 证据边界

本草案基于 2026-06-21 的只读核对：

1. 已读取本仓库 `.codex/context-pack.md`、README、PRD、架构、API contract、workflow、roadmap、collector、automation service、browser diagnostic model、集成测试和训练源配置。
2. 已浏览当前 GitHub 上的 `Panniantong/Agent-Reach`、`browser-use/browser-harness` README、skill/install 说明。
3. 本机环境只读核对：`browser-harness` 存在于 `/Users/pray/.local/bin/browser-harness`；`browser-harness --doctor` 显示 Chrome running、daemon alive，但 active browser connections 为 0，且未设置 `BROWSER_USE_API_KEY`。`agent-reach` 当前不在 PATH。
4. 生产只读健康检查：`curl -fsS https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`scheduler_enabled=true`。
5. 本轮没有登录生产、没有运行真实平台采集、没有创建 Source/Task/TaskRun/Dataset/Report/Notification，没有 provider call，也没有安装 Agent Reach。

证据等级说明：

| 等级 | 本文用法 |
|---|---|
| `L0-unverified` | 只有推断或外部项目声称，未在本项目实现或验收。 |
| `L1-public-or-runtime` | 当前公开仓库、公开文档、本地命令或生产只读 health 可见。 |
| `L2-fixture-or-dry-run` | 本地测试、fixture、dry-run、fake CLI 或 no-run 合同通过。 |
| `L3-production-read-only` | 生产只读观测，不产生写入。 |
| `L4-authorized-live` | 明确授权且有真实写入/运行日志。本轮没有新增 L4。 |

## 1. 当前项目产品形态

当前项目已经不是普通爬虫脚手架，而是一个“可追溯的数据采集工作台”：

```text
目标 URL / API / 导入样本
-> 授权与合规确认
-> 结构解析 / 字段候选
-> 采集计划 / 清洗计划
-> Source / Task / TaskRun / RawRecord
-> EntitySnapshot / Signal / Intelligence / Evidence
-> Dataset / Drift / Export / Report / Alert / Notification
```

稳定底座：

1. 后端：FastAPI + SQLAlchemy + PostgreSQL。
2. 前端：Next.js / React。
3. 稳定 collector：`github_repo`、`github_topic`、`generic_web`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page`。
4. Automation 平台包：`shopify-independent-ecommerce`、`github-api-first`、`public-page-structure-preflight`。
5. Browser diagnostic 本地增量：`BrowserDiagnosticRun`、`BrowserDiagnosticJob`、`BrowserDiagnosticJobRun`、`browser_executor_adapter_contract.v1`、`diagnostic_snapshot_replay`、`ephemeral_browser_harness_probe`。
6. Training source 线：`configs/training-content-sources.json` 里有 72 个来源，类型分布为 GitHub topic 10、GitHub repo 27、公开文档 17、平台方法卡 18。

核心判断：项目的护城河不是“多抓几个页面”，而是把每次采集变成可复盘资产。新增外部能力必须落到 `PlatformPackage -> Plan -> Run/Evidence -> Dataset` 的链路里，否则只会变成一次性脚本。

## 2. 三者核心能力对照

| 维度 | Data Intelligence Hub | Agent Reach | browser-harness |
|---|---|---|---|
| 本质 | 数据资产与证据链工作台 | 多平台读/搜能力路由器、installer、doctor | 真实浏览器 CDP 控制薄层 |
| 最强能力 | Source/Task/RawRecord/Dataset/Report 可追溯闭环 | 为 Agent 选择和体检上游工具，覆盖网页、GitHub、YouTube、B 站、Reddit、小红书、Twitter/X、RSS 等 | 连接用户 Chrome 或 remote browser，读取页面、截图、DOM、network、点击和恢复 |
| 不擅长 | 快速跟踪所有平台接入方式变化 | 长期数据资产、字段版本、清洗、漂移、审计 | 平台合规判断、长期数据模型、字段治理 |
| 适合内化成 | 主产品与证据系统 | `CapabilityRouter` / `ChannelProbe` / 平台方法卡来源 | `BrowserEvidenceRunner` / selector/network/screenshot 证据生成器 |
| 风险 | 把 demo/fixture 说成真实平台已打通 | 把“能读”误说成“可合规持续采集” | 把“能控制浏览器”误说成“可绕过登录/反爬” |

外部仓库事实：

1. Agent Reach 当前定位是能力层，不是 wrapper；它通过 channels 按平台路由到上游 CLI/API，并以 `doctor` 检测当前后端。
2. Agent Reach 的渠道合同包含 `can_handle(url)`、`read(url)`、`search(query)`、`check()`，这和本项目缺失的“平台包后端候选列表 + 可用性体检”高度互补。
3. browser-harness 明确是 CDP 直连浏览器，日常使用走 `browser-harness <<'PY'`，默认连接用户正在运行的 Chrome；它强调截图优先、坐标点击、raw CDP、helper 可编辑和 remote browser。
4. browser-harness 的能力适合生成证据，不适合直接跳过本项目的授权、字段、清洗和 Dataset 层。

## 3. 反直觉洞察

### 3.1 Agent Reach 不应该先变成 13 个 collector

直觉做法是把 Agent Reach 支持的平台全部做成本项目 collector。这个方向维护成本最高，也最容易过度承诺。

更稳的内化方式是先做 `capability_probe` 和 `external_tool_snapshot`：

1. `agent-reach doctor --json` 只进入能力可用性资产，不进入业务事实。
2. `agent-reach read/search` 的输出先进入 `manual_json` 或新增 `external_tool_result`，作为人工审核后的导入样本。
3. 只有低风险、schema 稳定、授权清晰的平台，才升级为正式 collector 或平台包。

### 3.2 browser-harness 最大价值是证明“不要采集”

当前项目已经有静态 preflight。browser-harness 的下一步不应是“自动点页面批量抓”，而是补三个只读证据：

1. 真实 selector 求值：字段是否可见、缺失率、稳定性。
2. network metadata 摘要：是否有同源 API 候选，是否可走官方/API-first 路径。
3. screenshot/trace/HAR retention 策略：证据能否保存、脱敏、过期清理。

这些证据常常会把页面导向 `official_api_or_file`、`manual_review` 或 `blocked_review`，这比盲目升级浏览器自动化更有产品价值。

### 3.3 社媒平台先做方法卡，反而更接近产品目标

Agent Reach 能让 Agent 读 Twitter/X、小红书、Reddit 等内容，但本项目的产品目标是可持续、可交付、可审计的数据工作台。社媒登录态、cookie、个人级内容和平台 ToS 风险很高。

因此社媒平台优先级不应按“工具能不能读”排序，而应按“是否能形成合规聚合数据集”排序。YouTube metadata/transcript、B 站公开视频搜索、V2EX 公开接口可更靠前；Twitter/X、小红书、Instagram、LinkedIn 先保持 SOP/import-only。

### 3.4 GitHub 是最应该继续深挖的 Agent 平台

GitHub 已经有官方 API、公开 metadata、topic/repo 模型和本项目已实现的 Dataset/Export/Drift/Report 闭环。和 browser agent 相比，GitHub 更适合做第一个“能力内化样板”：

1. Agent Reach 的 GitHub channel 可作为路由和补充检索。
2. 本项目继续用官方 API 作为事实来源。
3. browser-harness 只用于 UI E2E 或 README/页面结构补充，不作为主采集路径。

## 4. 已打通平台盘点

这里的“已打通”按证据层写，不做泛化。

| 平台/能力 | 当前路径 | 本轮证据等级 | 可说的事实 | 不能说的事实 |
|---|---|---:|---|---|
| GitHub topic/repo | `github_topic`、`github_repo`、GitHub API-first 平台包 | `L1` repo 当前实现；生产 health 为 `L3`；历史生产 E2E 由仓库文档记录 | 代码和 API contract 已支持 topic/repo collector，Topic Radar 可进入 Dataset/Export/Drift/Report 设计链路 | 本轮没有重新跑生产 GitHub 采集，不能说今天重新验收了 Topic Radar 全链路 |
| 独立站 / Shopify-style 商品页和集合页 | `ecommerce_product_discovery`、`ecommerce_product_page` | `L1/L2` | 代码支持公开 listing/sitemap/product page 解析，平台包为 executable，测试覆盖 fixture/集成路径 | 不能说 Amazon/Temu/Shopee/Lazada 页面抓取已打通，也不能说所有 Shopify 站点都稳定 |
| 公开网页静态采集 | `generic_web`、`public-page-structure-preflight` | `L1` repo；health `L3` | 支持公开 URL 预检、robots/sitemap/DOM 摘要、策略建议，预检后可转 `generic_web` | 预检不等于创建 Source/Task；本轮未登录生产验证 preflight endpoint |
| Browser diagnostic | `BrowserDiagnosticRun/Job/JobRun`、`ephemeral_browser_harness_probe` | `L1/L2` | 本地代码有只读诊断资产、job、合同、snapshot replay、fake CLI 测试和本机 harness spike 记录 | 不是生产执行器；不复用登录态；不写 Source/Task/TaskRun/Dataset |
| Training/Toolkit 知识采集 | `curated_training` 72 sources | `L1` repo config | 已覆盖 GitHub topic/repo、官方文档、平台方法卡、RPA/no-code/OSINT/browser risk 分类 | 这是培训内容线，不等于这些业务平台已进入正式数据采集 |
| RPA/no-code 方法 | `manual_json` 方法卡、`generic_web` 官网/文档 | `L1` | Browse AI、Octoparse、影刀 RPA、Power Automate、UiPath、Apify 等已作为训练源/方法卡存在 | 不能说已自动采集这些 SaaS 或内部后台 |
| 社媒/marketplace 边界 | 方法卡 | `L1` | Amazon、Reddit、YouTube、TikTok、竞品官网等已有方法卡或 roadmap 边界 | 不能说高风险平台的登录态抓取已打通 |

## 5. Agent Reach 能力可用于哪些平台

| Agent Reach 渠道 | 建议进入本项目的方式 | 优先级 | 边界 |
|---|---|---:|---|
| Web/Jina Reader | `external_tool_result` 或 `generic_web` 补充摘要 | P1 | 只处理公开 URL；保留 final URL、时间、来源、摘要；不要覆盖 RawRecord HTML 事实 |
| RSS/feedparser | 新增 `rss_feed` 或先用 `external_tool_result` | P1 | 适合公开更新监控，低风险高收益 |
| GitHub/gh CLI | 作为 GitHub API-first 的辅助 router/doctor | P0 | 正式事实仍优先官方 API；token 权限和 rate limit 入 audit |
| YouTube/yt-dlp | `video_metadata_transcript_import` 平台包 | P1 | 优先公开视频 metadata/transcript；注意版权和字幕来源；不下载无授权媒体资产 |
| B 站/bili-cli | `video_public_search_import` 方法包 | P1/P2 | 适合公开视频搜索和摘要；保持公开、低频、聚合 |
| V2EX | `public_community_trend` 小平台包 | P1/P2 | 公开 API/页面优先；不采个人画像 |
| Reddit | `social_aggregate_import`，先 SOP/import-only | P2 | Agent Reach 文档也指出需要登录态；不做匿名绕过，不做个人级内容采集 |
| Twitter/X | SOP/import-only | P3 | cookie 风险高；只做人工授权、聚合趋势、短期调研证据 |
| 小红书 | SOP/import-only | P3 | 登录态和内容政策风险高；先做字段模板与人工导入 |
| LinkedIn/Instagram | SOP/import-only | P3 | 招聘/社媒个人数据风险高，默认不做自动采集 |
| 雪球/小宇宙 | 候选 watchlist | P3 | 需要按金融/音频内容边界单独评估 |

## 6. browser-harness 能力可用于哪些平台

| 平台类型 | 可用能力 | 不可越界 |
|---|---|---|
| 独立站 / Shopify-style | selector 求值、JS 渲染字段确认、截图、同源 API 候选、分页证据 | 不自动绕过验证码/登录墙，不直接批量创建 Dataset |
| 公开网页/竞品官网 | DOM、文本、截图、network metadata、变更证据 | 不采私网、账号页、表单提交或个人数据 |
| RPA/no-code/内部后台 | 只作为人工授权流程诊断、字段定位和任务说明资产 | 不复用主账号 cookie 做无人值守采集，不导出 cookie |
| Marketplace | 用于公开页面结构评估和“是否应转 API/export/import”判断 | 不默认做页面抓取，不做反检测 |
| 社媒平台 | 只用于可见公开页的人工验收或方法卡截图证据 | 不做登录态抓取、滚动批量采集、cookie 导出 |

## 7. 能力内化方案

### 7.1 新增能力层，而不是新增一堆爬虫

建议新增抽象：

```text
PlatformPackage
-> CapabilityProbe
-> BackendCandidate
-> ExecutionBoundary
-> EvidenceContract
-> Import/Collector Promotion Gate
```

最小字段：

1. `platform_id`：如 `github`、`web`、`youtube`、`bilibili`、`reddit`。
2. `backend_candidates`：如 `official_api`、`agent_reach_channel`、`generic_web`、`browser_harness_probe`、`manual_import`。
3. `doctor_status`：可用、缺配置、被阻断、需人工授权。
4. `credential_mode`：none、token、cookie、browser_profile、manual_export。
5. `execution_boundary`：executable、read_only_probe、import_only、sop_only、blocked。
6. `allowed_outputs`：RawRecord、ExternalToolSnapshot、BrowserDiagnosticJobRun、DatasetVersion。
7. `forbidden_actions`：submit form、login bypass、cookie export、notification send、scheduler mutation。

### 7.2 先把 Agent Reach 内化为 `CapabilityProbe`

第一切片不要安装生产依赖，也不要把 Agent Reach 绑进 API worker。先做：

1. 在 `/toolkit` 或 `/automation` 增加 Agent Reach 方法卡，说明本机未安装时的状态。
2. 定义 `agent_reach_channel_probe.v1` JSON contract，字段包括 platform、active_backend、requires_login、proxy_required、doctor_status、risk_level、next_action。
3. 本地 CLI 只跑 `doctor --json` 的 dry-run/probe，不读取平台内容。
4. 将 probe 结果保存为 `CapabilityProbe` 草案或 `manual_json` 资产。
5. 待证据稳定后，再对 Web/RSS/GitHub/YouTube/B 站/V2EX 做 read/search snapshot adapter。

### 7.3 把 browser-harness 从 page_info 扩到有界证据

在现有 Phase 18A 后，下一步应扩展：

1. `selector_evaluation`: 对 `selector_scope` 做真实 DOM 求值，输出 match_count、sample_text、missing_reason。
2. `network_metadata`: 输出 same-origin API candidate、resource counts、method/status/content-type，默认不保存 headers/body。
3. `artifact_retention`: 明确 screenshot/trace/HAR summary 的写入目录、TTL、清理命令和 redaction。
4. `promotion_gate`: 只有在 selector 稳定、授权明确、字段缺失率可接受后，才允许人工创建 Source/Task。

### 7.4 逐步新增正式平台包

新增平台包顺序不应按“外部工具支持数量”排序，而应按本项目闭环成本排序：

1. `github-api-first-deepening`: repo/release/README/license/issue activity。
2. `public-web-rss-docs`: Web/RSS/官方文档更新监控。
3. `video-public-transcript`: YouTube/B 站公开视频 metadata/transcript 导入。
4. `public-community-trend`: V2EX/Reddit 等社区聚合趋势，Reddit 先 import-only。
5. `marketplace-authorized-import`: Amazon/SP-API 或后台导出模板。
6. `social-import-only`: 小红书/Twitter/X/Instagram/LinkedIn 字段模板、SOP 和人工导入。

## 8. 下一阶段优先级

### P0：继续加深已有可执行平台

1. GitHub API-first 深化。
   - 增加 release、README 摘要、license、default branch、issue activity、commit freshness 字段。
   - 把 Agent Reach/gh CLI 只作为 router 和补充检索，不取代官方 API。
   - 验收：本地 integration、web E2E、生产只读 smoke、授权生产 E2E 和 cleanup。

2. browser-harness 有界证据。
   - 实现 selector 求值和 network metadata summary。
   - 保持 `files_written=false`，直到 retention 策略通过。
   - 验收：fake CLI + 本机 real CLI 分层；生产只读前必须标注 browser-control gate。

3. 独立站 collection/sitemap 深化。
   - 提升 product discovery、去重、canonical、variant、image、price/currency/availability 字段。
   - 验收：授权测试站点或 fixture 完成 fan-out、batch run、Dataset、export、drift。

### P1：低风险新平台包

1. Public Web/RSS/Docs 平台包。
   - 内化 Agent Reach 的 Web/Jina、RSS/feedparser 思路。
   - 产出公开文档更新 Dataset，服务培训内容和竞品官网监控。

2. YouTube/B 站公开视频包。
   - 先做 metadata/transcript import，不做下载媒体资产。
   - 适合市场/培训/内容趋势采集。

3. V2EX/公开社区趋势包。
   - 只采聚合层主题、回复数、时间和链接。
   - 不做人级画像。

### P2：高价值但需授权来源的平台

1. Amazon/Marketplace import/API-first。
   - 优先 SP-API、Brand Analytics、Seller/Vendor authorized export、CSV import。
   - browser-harness 只做公开页结构评估，不做默认采集。

2. Reddit 聚合趋势。
   - Agent Reach 可做能力探测，但因登录态/403 风险，先 import-only 或人工授权 read-only。
   - 不采个人级评论画像。

3. 国内业务/RPA 场景。
   - 影刀 RPA、Octoparse、Browse AI、Power Automate、UiPath 先作为 workflow/import 连接器，不嵌入无人值守浏览器。

### P3：SOP-only 或暂缓

1. Twitter/X、小红书、Instagram、LinkedIn。
2. 任何需要 cookie、扫码、主账号、验证码、反检测、登录绕过的平台。
3. 任何平台政策不清或涉及个人敏感数据的采集任务。

## 9. 执行切片

### Slice 1：能力路由合同

交付：

1. 新增 `CapabilityProbe` 草案 schema 或先写到 `drafts/analysis`。
2. 新增 Agent Reach 平台方法卡，明确 `doctor`、active backend、cookie/proxy、blocked 状态。
3. 不安装、不调用真实平台读取。

验收：

1. 单元测试覆盖 schema。
2. 文档明确 `doctor` 不等于采集成功。

### Slice 2：browser-harness selector/network 证据

交付：

1. 扩展 `BrowserDiagnosticJobRun` result contract。
2. fake CLI 覆盖 selector/network 成功和失败。
3. 本机 real CLI 仅对 `https://example.com/` 或授权公开测试页验证。

验收：

1. `collection_resources_written=false`。
2. `files_written=false`，除非 retention 策略已完成并单独确认。
3. 所有失败保留 `blocked_*` 或 `failed_*`，不伪装成功。

### Slice 3：GitHub deep fields

交付：

1. 增加 release/license/README/issue activity 字段。
2. Dataset schema 与 report summary 更新。
3. 工具雷达报告显示维护风险、安装方式、适用采集场景和不适用边界。

验收：

1. API integration。
2. Web E2E。
3. 生产只读 + 授权 E2E + cleanup。

### Slice 4：Public Web/RSS 平台包

交付：

1. `public-web-rss-docs` 平台包。
2. URL/RSS source draft。
3. Dataset preview 和 drift。

验收：

1. 公开 RSS feed 和公开 docs 页面各一条 fixture。
2. 生产只读预检，不自动创建调度。

### Slice 5：Video public transcript import

交付：

1. YouTube/B 站公开视频 metadata/transcript import 方法卡。
2. Agent Reach 可用性 probe。
3. 手动导入模板。

验收：

1. 不下载媒体文件。
2. 不采私人账号或未授权内容。

## 10. 结论

三者可以融合，但融合点不是“把 Agent Reach 和 browser-harness 都塞进采集器”。更稳的架构是：

```text
Agent Reach = 平台能力路由和健康检查
browser-harness = 浏览器只读证据生成器
Data Intelligence Hub = 事实、字段、清洗、Dataset、报告、告警和审计闭环
```

下一阶段应优先加深 GitHub、独立站、公开网页/RSS 和 browser-harness 证据层；marketplace/social 先走 API/import/SOP。这样能扩大平台覆盖，同时不破坏当前项目最重要的边界：证据可追溯、授权显式、写入可审计。

## 11. 参考来源

外部：

1. Agent Reach README: `https://github.com/Panniantong/Agent-Reach`
2. Agent Reach `llms.txt`: `https://github.com/Panniantong/Agent-Reach/blob/main/llms.txt`
3. Agent Reach skill: `https://github.com/Panniantong/Agent-Reach/blob/main/agent_reach/skill/SKILL.md`
4. Agent Reach `CLAUDE.md`: `https://github.com/Panniantong/Agent-Reach/blob/main/CLAUDE.md`
5. browser-harness README: `https://github.com/browser-use/browser-harness`
6. browser-harness skill: `https://github.com/browser-use/browser-harness/blob/main/SKILL.md`
7. browser-harness install: `https://github.com/browser-use/browser-harness/blob/main/install.md`

本地：

1. `.codex/context-pack.md`
2. `docs/architecture/architecture-data-intelligence-hub-stable.md`
3. `docs/product/product-prd-data-intelligence-hub-stable.md`
4. `docs/api/api-contract-data-intelligence-hub-stable.md`
5. `docs/workflows/workflow-browser-structure-diagnostic-stable.md`
6. `drafts/analysis/analysis-prd-next-roadmap-draft-20260619.md`
7. `configs/training-content-sources.json`
8. `apps/api/src/data_intelligence_hub/services/automation_service.py`
9. `apps/api/src/data_intelligence_hub/services/collector_catalog.py`
10. `apps/api/tests/integration/test_sources_tasks.py`

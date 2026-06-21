---
title: Data Intelligence Hub PRD 2.0 平台化采集工作台
doc_type: prd
module: product
topic: data-intelligence-hub
status: stable
created: 2026-06-11
updated: 2026-06-21
owner: self
source: human+ai
---

# Data Intelligence Hub PRD 2.0 — 平台化采集工作台

> **当前状态**：PRD 2.0 当前源头版本 · **版本日期**：2026-06-21
>
> 本版本将早期“跨平台数据采集情报平台”收敛为“平台化数据采集工作台”。旧 PRD 的数据闭环、证据链、Collector、Report、Alert 等详细规格仍作为历史详细规格保留；本文件顶部的 PRD 2.0 控制面用于指导下一阶段平台采集实现、优先级和验收边界。

## PRD 2.0 当前控制面

### 事实基线

| 事项 | 当前事实 | 证据边界 |
|---|---|---|
| 主产品形态 | `/automation` 已是自动化采集工作台入口，串联授权 URL/API/导入样本、结构解析、字段候选、采集计划、清洗计划、Dataset、导出、漂移、报告和告警 | 来自本仓库架构/API 文档和既有实现；本轮没有做业务代码修改 |
| 稳定 Collector | `github_repo`、`github_topic`、`generic_web`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page` | 代码和 API contract 可见 |
| 已上线平台包 | `shopify-independent-ecommerce`、`github-api-first`、`public-page-structure-preflight` | 历史生产 E2E 记录显示 commit `d9b2a5e` 完成一轮验收；本轮只做生产 health 只读复核 |
| GitHub Tool Radar | GitHub topic/repo 运行记录可进入 `github_tool_radar` Dataset、导出、漂移、只读报告和 Report 资产 | 历史验收已记录；本轮未重新跑生产 GitHub 采集 |
| Browser diagnostic | 本地已有 `BrowserDiagnosticRun`、`BrowserDiagnosticJob`、`BrowserDiagnosticJobRun`、`browser_executor_adapter_contract.v1`、`diagnostic_snapshot_replay` 和受控 `ephemeral_browser_harness_probe` 第一切片 | 当前仍是本地/受控诊断链路，不等于生产浏览器执行器已上线 |
| 生产 health | 2026-06-21 只读请求 `https://scrapy.lute-tlz-dddd.top/api/health` 返回 `environment=production`、`status=ok`、`database=connected`、`schema=current`、`scheduler_enabled=true` | 只证明服务健康，不证明本轮重新验收采集全链路 |
| 外部能力环境 | 本机 `browser-harness` 存在，`browser-harness --doctor` 显示 Chrome running、daemon alive，但 active browser connections 为 0；`agent-reach` 当前不在 PATH | 本地运行态事实，不代表生产可用 |

### 本轮修订目的

1. 把 PRD 的中心从“多域情报平台”调整为“平台化采集工作台”。
2. 把 Agent Reach 内化为平台能力路由和健康检查思路，而不是一次性扩成多个生产 collector。
3. 把 browser-harness 内化为浏览器只读证据生成器，而不是默认无人值守抓取器。
4. 明确哪些平台已打通、哪些只能做 API/import/SOP，避免把方法卡、工具可读性或本地 spike 误写成生产采集能力。
5. 将下一阶段执行计划落到独立 workflow 文档：[PRD2 平台采集执行计划](../workflows/workflow-prd2-platform-collection-execution-plan-stable.md)。

## PRD 2.0 产品规格摘要

### 产品定位

Data Intelligence Hub 是一个以授权、证据和可复用数据资产为中心的平台化采集工作台。它帮助运营、数据、增长、市场和技术人员判断目标平台适合 API、静态解析、浏览器诊断、RPA、第三方工具还是人工导入，并把可执行路径沉淀为可追溯的 Dataset、Report、Alert 和审计证据。

### 主链路

```text
目标平台 / URL / API / 导入样本
-> 授权与合规确认
-> 平台能力探测
-> 结构解析 / 浏览器只读诊断
-> 字段候选与字段稳定性评分
-> 采集计划 / 清洗计划
-> Source / Task / TaskRun / RawRecord
-> DatasetVersion / Export / Drift
-> Report / Alert / Notification / Evidence
```

### 核心产品对象

| 对象 | PRD 2.0 角色 | 下一阶段变化 |
|---|---|---|
| `PlatformPackage` | 平台级采集路径合同 | 从静态平台包扩展为可版本化、可解释、可验收的策略对象 |
| `CapabilityProbe` | 平台能力和后端候选体检资产 | 新增 Agent Reach 风格的 doctor/result contract，先作为草案资产 |
| `BrowserDiagnosticRun/Job/JobRun` | 浏览器只读证据资产 | 扩展 selector 求值、network metadata、artifact retention 和 promotion gate |
| `ExternalToolSnapshot` | 外部工具读/搜结果导入资产 | 用于 Web/RSS/GitHub/Video 等低风险渠道的人工审核导入 |
| `DatasetVersion` | 结构化交付资产 | 继续作为采集结果进入导出、漂移、报告的中心 |
| `Evidence` | 事实链路绑定 | 所有报告、告警和推荐必须可回溯到采集或诊断证据 |

## 能力融合与平台优先级

### 三者融合方式

| 系统 | 应内化的能力 | 不应承担的职责 |
|---|---|---|
| Data Intelligence Hub | 授权、字段、采集、清洗、Dataset、报告、告警、审计闭环 | 跟踪所有平台工具变化、直接绕过平台风控 |
| Agent Reach | 平台后端候选、安装/诊断/doctor、read/search 可用性路由 | 长期数据资产、字段版本、生产写入、合规判断 |
| browser-harness | 真实浏览器只读证据：page info、selector、network metadata、screenshot/trace/HAR 摘要 | 登录绕过、cookie 导出、无人值守社媒抓取、直接创建 Dataset |

### 平台采集优先级

| 优先级 | 平台/能力 | 原因 | 执行边界 |
|---|---|---|---|
| P0 | GitHub API-first 深化 | 已有官方 API、topic/repo collector、Dataset/Report 闭环，是最稳的平台内化样板 | 官方 API 为事实源；Agent Reach/gh CLI 只做 router/doctor 或补充检索 |
| P0 | browser-harness 有界证据 | 当前浏览器诊断已经资产化，下一步最需要补 selector 和 network 证据 | 默认 `collection_resources_written=false`；截图/trace/HAR 文件写入必须先完成 retention 方案 |
| P0 | 独立站/Shopify-style 深化 | 已有 `ecommerce_product_discovery` 和 `ecommerce_product_page`，可形成业务数据集 | 只处理授权公开页面；不处理登录墙、验证码或反检测 |
| P1 | Public Web/RSS/Docs | 低风险、高复用，适合培训内容、竞品官网和文档更新监控 | 公开 URL/feed；保留来源、时间、final URL 和摘要，不覆盖原始事实 |
| P1 | YouTube/B 站公开视频 metadata/transcript import | 适合内容趋势和培训资料，但不应下载媒体资产 | 先做 metadata/transcript import；版权和字幕来源进入审计字段 |
| P1/P2 | V2EX/公开社区趋势 | 公开社区聚合可做趋势数据，不做人级画像 | 聚合主题、链接、时间、回复数；不采个人画像 |
| P2 | Amazon/Marketplace | 商业价值高，但页面抓取风险高 | 官方 API、授权导出或人工导入优先；browser-harness 只做公开结构评估 |
| P2 | Reddit 聚合趋势 | Agent Reach 可探测，但登录态/403 风险明显 | 先 SOP/import-only 或明确授权 read-only；不采个人级画像 |
| P2 | RPA/no-code/内部后台 | 能服务真实业务流程，但授权、账号和留痕要求高 | 先 workflow/import 连接器；不复用主账号 cookie 做无人值守采集 |
| P3 | Twitter/X、小红书、Instagram、LinkedIn | 登录态、个人数据、平台政策和风控风险高 | SOP/import-only；不做 cookie 导出、登录绕过、滚动批采或反检测 |

## 证据与验收边界

| 证据等级 | 含义 | 当前可用场景 |
|---|---|---|
| `L0-unverified` | 只有推断或外部项目声称 | 新平台假设、未安装工具 |
| `L1-repo-or-runtime` | 本地代码、公开仓库、公开文档或本机命令可见 | PRD/架构/API contract、本机 `browser-harness --doctor` |
| `L2-local-test-or-dry-run` | 本地测试、fixture、fake CLI、dry-run 或 no-run 合同通过 | BrowserDiagnosticJob/JobRun 本地切片 |
| `L3-production-read-only` | 生产只读观测，无写入 | `/api/health`、只读 endpoint smoke |
| `L4-authorized-live` | 明确授权且有真实写入/运行日志，并完成 cleanup | Source/Task/Dataset/Report 等生产 E2E |

本 PRD2.0 的强制边界：

1. `doctor` 或 `probe` 不等于采集成功。
2. browser-harness 能打开页面不等于允许持续采集。
3. 方法卡、训练源、外部工具输出不等于正式平台已打通。
4. `Report` 资产保存不等于通知或邮件已发送。
5. `production health ok` 不等于本轮平台链路重新验收。
6. 任何 provider call、生产写入、邮件发送、登录态复用、cookie 导出、调度变更都必须有显式授权和可清理审计记录。

---

## 目录

- [PRD 2.0 当前控制面](#prd-20-当前控制面)
- [PRD 2.0 产品规格摘要](#prd-20-产品规格摘要)
- [能力融合与平台优先级](#能力融合与平台优先级)
- [证据与验收边界](#证据与验收边界)
- [历史详细规格：调研决策汇总](#1-调研决策汇总)
- [历史详细规格：产品定义](#2-产品定义)
- [历史详细规格：核心用户故事](#3-核心用户故事)
- [历史详细规格：信息架构与导航](#4-信息架构与导航)
- [历史详细规格：核心对象与状态机](#5-核心对象与状态机)
- [历史详细规格：开发计划与验收标准](#18-开发计划)

---

## 1. 调研决策汇总

经过四轮逐层调研，以下关键决策已确认并写入本 PRD：

| 维度 | 决策 | 理由 |
|---|---|---|
| 目标用户 | 全场景覆盖（跨境 / 技术 / 社媒 / 竞品） | 四域业务场景均需覆盖 |
| PRD 2.0 策略 | 平台包深挖 + 能力探测 + 证据资产 | 先把低风险平台做成可复用闭环，再扩到 API/import/SOP 平台 |
| 后端技术栈 | Python 3.12 + FastAPI | 数据处理采集生态成熟，自动 OpenAPI |
| 数据库 | PostgreSQL（JSONB 支持半结构化数据） | 功能完整，JSONB 列完美匹配采集数据 |
| 任务调度 | APScheduler（进程内，无外部依赖） | 小规模日采集量 <1 万条，Celery/Redis 过重 |
| 前端技术栈 | React / Next.js（独立前端项目） | 灵活性最高，与后端通过 OpenAPI 契约协作 |
| LLM 策略 | 外部 API 调用 + 可插拔 Provider Adapter | 先支持 OpenAI/Claude API，后续可扩展 |
| 部署环境 | 公有云（AWS / 阿里云） | 使用云原生基础设施 |
| 数据规模 | 小型（<20 数据源，日采集 <1 万条） | 单机 PostgreSQL + 进程内调度可满足 |
| 用户认证 | 邮箱 + 密码登录 | MVP 最简方案 |
| 通知渠道 | 站内通知 + 邮件（SMTP） | 日报和预警的基础触达方式 |
| 稳定 Collector | GitHub Repo / GitHub Topic / 通用网页 / 手动 JSON / 独立站商品发现 / 独立站商品页 | 当前实现和 API contract 可见 |
| 核心关注模块 | 授权与合规确认 + 平台包 + 能力探测 + 浏览器证据 + Dataset + 导出 + 漂移 + 报告/告警 | 可追溯数据资产闭环优先 |

---

## 2. 产品定义

### 2.1 产品名称

**Data Intelligence Hub** — 平台化数据采集工作台

### 2.2 一句话定位

一个以授权、证据和可复用 Dataset 为核心的平台化数据采集工作台，帮助用户判断目标平台应该走 API、静态解析、浏览器诊断、RPA、第三方工具还是人工导入，并把可执行路径沉淀为可审计的数据资产。

### 2.3 产品目标

构建面向跨境电商、开源生态、公开网页、内容平台、社区趋势和授权 marketplace 数据的采集工作台。平台通过**授权确认 → 能力探测 → 结构诊断 → 采集计划 → 清洗计划 → Dataset → 漂移/导出/报告/告警**的闭环，帮助用户把一次性采集任务变成可重复、可验收、可交付的数据流程。

### 2.4 产品边界

本平台**不是**单纯爬虫系统，**不是**通用 BI 工具，**不是**反检测或登录绕过工具，而是以"授权路径 + 结构化数据资产 + 证据链"为中心的数据采集与分析系统。

**PRD 2.0 能力矩阵：**

| 能力 | 当前状态 | 说明 |
|---|---|---|
| 用户登录 / Workspace / Project | 已有 | 邮箱密码、单 workspace 和项目管理仍是 MVP 边界 |
| Source / Task / TaskRun | 已有 | 采集源、采集任务和运行记录是正式写入链路 |
| 稳定 Collector | 已有 | `github_repo`、`github_topic`、`generic_web`、`manual_json`、`ecommerce_product_discovery`、`ecommerce_product_page` |
| Platform Package | 已有第一版 | `shopify-independent-ecommerce`、`github-api-first`、`public-page-structure-preflight`；下一步做能力探测和版本化 |
| SiteAnalysis / ExtractionPlan | 已有 | 公开 URL 分析、字段候选、采集计划和浏览器诊断导入 |
| Browser diagnostic | 本地增强中 | 只读诊断资产、job、contract、snapshot replay、受控 `ephemeral_browser_harness_probe`；不是生产无人值守采集 |
| CleaningPlan | 已有 | 清洗规则草案、试跑和 DatasetVersion 追踪 |
| Dataset / DatasetVersion | 已有 | 结构化交付资产，可从商品采集和 GitHub Tool Radar 进入 |
| Dataset Export | 已有 | CSV/JSON/JSONL 导出，必须记录审计和 checksum |
| Drift / Alert / Notification | 已有基础 | 漂移、告警规则、站内通知和邮件仍需按授权分层 |
| Report Asset | 已有基础 | 工具雷达报告可保存为 Report 资产；保存不等于通知或邮件发送 |
| CapabilityProbe | 待实现 | Agent Reach 风格的能力体检和后端候选路由，先做 no-read/no-write probe |
| ExternalToolSnapshot | 待实现 | 外部工具 read/search 输出的人工审核导入资产 |
| Marketplace API/import | 待实现 | Amazon 等优先 API、授权导出或人工导入 |
| Social SOP/import-only | 待实现 | Twitter/X、小红书、Instagram、LinkedIn 等默认不做自动页面抓取 |
| 企业多租户 / 计费 | 暂缓 | 非下一阶段平台采集优先级 |

### 2.5 核心设计原则

**原则一：先把低风险平台做成可验收闭环，不追求平台数量。**

**原则二：全链路可追溯。** Report / Alert / Dataset → TaskRun / RawRecord / BrowserDiagnosticJobRun / ExternalToolSnapshot，每一步都可反向溯源。

**原则三：AI 和外部工具不直接决定事实。** LLM、Agent Reach、browser-harness 或其他工具只能生成候选、诊断或摘要；正式事实必须进入采集、导入、Dataset 和证据链。

**原则四：先 API/import，后浏览器；先只读证据，后采集写入。** 对 marketplace/social/登录态平台默认走官方 API、授权导出、人工导入或 SOP。

**原则五：证据等级写清楚。** `docs-only`、`local dry-run`、`production read-only`、`authorized production E2E` 必须分层表述。

**原则六：前后端通过 OpenAPI 契约并行开发。** 前端支持 mock data 模式，但 mock green 不能替代真实 API 或生产验收。

---

## 3. 核心用户故事

### 故事一：跨境运营人员

> 我负责监控几个竞品的 Amazon 店铺和独立站。我希望创建一个"竞品监控"项目，添加竞品独立站 URL 和 GitHub 仓库作为数据源，设置每天早上 8 点自动采集。我在 Dashboard 看到今天有一条"竞品官网大幅改版"的情报，点击进入详情，通过审计抽屉对比了新旧页面的 HTML 快照，确认竞品新增了一个产品线。我把这条情报标记为"跟进中"。

### 故事二：技术情报分析人员

> 我关注 AI 数据采集工具圈的开源动态。我创建了一个"AI Scrapy Tools"项目，通过 GitHub Topic `web-scraping` 发现项目，对其中 5 个 repo 建立持续监控。系统检测到其中一个 repo 24 小时内 Star 增长了 300+，自动生成了一条"趋势"情报。我查看证据——Star 增长曲线图和 GitHub API 返回的原始 JSON——确认了这个趋势信号，生成日报发送给团队。

### 故事三：团队负责人

> 每天早上 9 点，我在站内通知中心和邮箱收到系统自动生成的日报。日报包含：今日关键情报摘要、数据采集健康度、高风险预警。我浏览核心发现后，对一条"竞品大幅降价"的高风险情报点进去查看证据链，决定是否需要动作。

### 故事四：工程维护人员

> 某个采集任务连续失败 3 次，系统生成了 `data_quality_anomaly` 信号。我在 Dashboard 看到任务健康度下降，进入 Task 详情看到错误日志，发现是目标网站加了 Cloudflare 防护。我调整了数据源配置，重新启用任务。

### 故事五：平台采集负责人

> 我拿到一个新的平台采集需求，先在 `/automation` 输入目标 URL、API 或导入样本。系统告诉我该平台当前推荐路径是官方 API、静态解析、浏览器只读诊断、RPA、第三方工具还是人工导入，并展示能力探测结果、字段稳定性、风险边界和下一步 To do。我只在证据和授权充分时创建 Source/Task 或保存 Dataset；高风险平台只生成 SOP 或导入模板。

---

## 4. 信息架构与导航

### 4.1 导航模型（整合两版 PRD）

整合后采用 **业务域导航 + 工程入口** 的双层结构。左侧边栏分为两个区块：

**区块 A：业务域（Scope Navigation）**

这是 `ai_prd_end.md` 中以业务视角导航的核心设计，让用户按工作场景进入：

| 导航项 | 聚焦领域 | 默认视图 |
|---|---|---|
| 📡 开源雷达 | GitHub·技术趋势 | Trending 榜单、Star 增速、Release 流 |
| 🛒 电商风向 | 跨境平台·商品 | 价格变动、排名走势、上新日历 |
| 📱 社媒脉搏 | 社媒·热点 | 热搜词云、达人动态、爆款摘要 |
| 🎯 竞品守望 | 独立站·竞品 | 官网变化、落地页快照、策略变动 |

每个业务域页面内部包含该域专属的项目列表、情报流和实体视图。

**区块 B：全局中心（General）**

| 导航项 | 功能 |
|---|---|
| 📊 全局仪表盘 | 跨域情报汇总、任务健康度、数据质量 |
| 📰 情报中心 | 全局情报列表、筛选、排序、状态管理 |
| 📋 报告中心 | 日报生成与历史 |
| 🔔 预警中心 | 规则配置 + 预警事件记录 |

**区块 C：工程中心（Engine）**

| 导航项 | 功能 |
|---|---|
| ⚙️ 采集任务 | 任务列表、运行记录、日志 |
| 🔗 数据源 | 数据源管理、测试采集 |
| 💾 原始数据 | RawRecord 列表与详情 |
| 🗂️ 实体库 | 所有标准化实体的统一视图 |

### 4.2 审计抽屉（Audit Drawer）

来自 `ai_prd_end.md` 的核心交互设计。在**情报详情页**点击任何一条 AI 生成的结论文字，右侧弹出抽屉视图：

- **证据段落**：高亮显示关联 RawRecord 中的相关文本
- **视觉快照**：该时间戳下的 HTML 渲染快照或截图（S3 URL）
- **时序变化**：该实体过去 N 次采集的指标曲线（如 Star 数增长）
- **对比模式**：Old Snapshot vs New Snapshot 左右并排

---

## 5. 核心对象与状态机

### 5.1 核心对象一览

| 对象 | 说明 | 数据来源 |
|---|---|---|
| User | 用户 | 注册产生 |
| Workspace | 工作空间（MVP 单 workspace） | 注册时默认创建 |
| Project | 监控项目，按业务域分类 | 用户创建 |
| Source | 数据源，绑定到 Project | 用户配置 |
| Collector | 采集器类型定义（系统级） | 系统预置 |
| CollectionTask | 采集任务，绑定 Source | 启用 Source 时自动创建 |
| TaskRun | 单次任务运行记录 | 每次执行产生 |
| RawRecord | 原始数据记录（含截图 URL） | 采集产生 |
| Entity | 标准化实体（去重） | 标准化产生 |
| EntitySnapshot | 实体在某个时间点的快照 | 每次采集产生 |
| Signal | 变化信号（确定性检测） | Signal Engine 产生 |
| Intelligence | 情报（聚合信号 + LLM 摘要） | Intelligence Engine 产生 |
| Evidence | 证据（情报与原始数据的桥梁） | 情报生成时创建 |
| Report | 日报 | 用户手动或定时生成 |
| AlertRule | 预警规则 | 用户配置 |
| AlertEvent | 预警事件 | 规则命中时产生 |
| Notification | 站内通知 | 报告/预警送达时创建 |

### 5.2 CollectionTask 状态机

```
draft → enabled → running → success / partial_success / failed
failed → retrying → running
success / partial_success → enabled（等待下次调度）
enabled → paused → enabled
enabled → disabled → [*]
```

### 5.3 Intelligence 状态机

```
new → reviewed → following / dismissed
following → converted / dismissed
dismissed → reviewed（可重新审视）
converted → [*]
```

### 5.4 AlertEvent 状态机

```
triggered → sent / muted
sent → acknowledged / resolved
acknowledged → resolved
```

---

## 6. 技术架构

### 6.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React/Next.js)              │
│  业务域页面 · 情报中心 · 仪表盘 · 报告 · 预警 · 审计抽屉  │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API (OpenAPI Contract)
┌─────────────────────▼───────────────────────────────────┐
│                  Backend (Python 3.12 + FastAPI)         │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Auth     │ │ Source   │ │ Task     │ │ Dashboard │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │Collector │ │ Signal   │ │Intellig. │ │ Report    │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ Alert    │ │ LLM      │ │ Notify   │               │
│  │ Service  │ │ Service  │ │ Service  │               │
│  └──────────┘ └──────────┘ └──────────┘               │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         APScheduler (进程内定时调度)               │  │
│  │  采集任务调度 · 信号检测触发 · 日报定时生成        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              PostgreSQL (含 JSONB 列)                    │
│  users · projects · sources · raw_records · entities    │
│  entity_snapshots · signals · intelligence_items · ...  │
└─────────────────────────────────────────────────────────┘
```

### 6.2 技术选型

| 层 | 技术 | 说明 |
|---|---|---|
| 后端框架 | FastAPI (Python 3.12) | 异步支持、自动 OpenAPI、类型安全 |
| ORM | SQLAlchemy 2.x | 成熟的 Python ORM |
| 迁移 | Alembic | SQLAlchemy 官方迁移工具 |
| 数据库 | PostgreSQL 15+ | JSONB 支持半结构化采集数据 |
| 调度 | APScheduler | 进程内定时任务（无外部依赖，契合小规模） |
| LLM | OpenAI / Anthropic API + 可插拔 Adapter | 先支持主流 API，后扩展本地模型 |
| 邮件 | SMTP（aiosmtplib） | 日报推送和预警 |
| 对象存储 | S3-compatible（MinIO 或 AWS S3） | 存储 HTML 快照截图 |
| 测试 | pytest + httpx | 单元测试 + API 测试 |
| 文档 | OpenAPI (自动生成) | FastAPI 原生支持 |

### 6.3 前端技术栈

| 层 | 技术 |
|---|---|
| 框架 | React 18+ / Next.js App Router |
| 语言 | TypeScript |
| UI | Tailwind CSS + shadcn/ui |
| 状态管理 | TanStack Query（服务端状态）+ React Context（客户端状态） |
| 表单 | React Hook Form + Zod |
| 表格 | TanStack Table |
| 图表 | Recharts |
| API Client | OpenAPI 生成的 TypeScript client（或 fetch wrapper） |
| 认证 | JWT（HttpOnly Cookie） |

### 6.4 后端目录结构

```
apps/api/
  main.py                          # FastAPI 入口
  core/
    config.py                      # 环境变量集中管理
    security.py                    # JWT + 密码哈希
    database.py                    # SQLAlchemy session
    errors.py                      # 统一错误处理
  api/
    deps.py                        # 依赖注入（current_user, current_workspace）
    routes/
      auth.py                      # 登录/登出/me
      dashboard.py                 # 仪表盘数据聚合
      projects.py                  # 项目 CRUD
      sources.py                   # 数据源 CRUD + 测试
      tasks.py                     # 任务管理 + 运行
      task_runs.py                 # 运行记录 + 日志
      raw_records.py               # 原始数据查看
      entities.py                  # 实体 + 快照 + 信号
      intelligence.py              # 情报 CRUD + 证据 + 反馈
      reports.py                   # 日报生成 + 历史
      alerts.py                    # 规则 + 事件
      notifications.py             # 站内通知
      collectors.py                # Collector 元信息
  models/                          # SQLAlchemy ORM 模型
    user.py · project.py · source.py · task.py
    raw_record.py · entity.py · signal.py
    intelligence.py · report.py · alert.py · notification.py
  schemas/                         # Pydantic 请求/响应 schema
    auth.py · project.py · source.py · task.py
    entity.py · signal.py · intelligence.py
    report.py · alert.py · dashboard.py
  services/                        # 业务逻辑层
    auth_service.py
    project_service.py
    source_service.py
    task_service.py
    collector_service.py           # Collector 调度
    normalization_service.py       # Raw → Entity 标准化
    signal_service.py              # 信号检测
    intelligence_service.py        # 情报生成
    report_service.py              # 日报生成
    alert_service.py               # 预警匹配
    llm_service.py                 # LLM Adapter
    evidence_service.py            # 证据链构建
    notification_service.py        # 站内通知 + 邮件
  collectors/                      # Collector 插件
    base.py                        # BaseCollector 抽象类
    github_repo.py
    github_topic.py
    generic_web.py
    manual_json.py
  scheduler/                       # APScheduler 配置
    scheduler.py                   # 调度器初始化
    jobs.py                        # 定时任务定义
  repositories/                    # 数据访问层
    base.py
    project_repo.py
    source_repo.py
    task_repo.py
    intelligence_repo.py
  tests/
    unit/
    integration/
alembic/
requirements.txt
pyproject.toml
```

### 6.5 前端目录结构

```
apps/web/
  app/
    login/page.tsx
    dashboard/page.tsx
    projects/
      page.tsx
      [projectId]/page.tsx
    sources/
      page.tsx
      new/page.tsx
      [sourceId]/page.tsx
    tasks/
      page.tsx
      [taskId]/page.tsx
    intelligence/
      page.tsx
      [itemId]/page.tsx
    entities/[entityId]/page.tsx
    reports/
      page.tsx
      [reportId]/page.tsx
    alerts/page.tsx
    notifications/page.tsx
  components/
    layout/
      Sidebar.tsx                   # 双层业务/全局/工程导航
      TopBar.tsx
    dashboard/                      # 仪表盘组件
    projects/
    sources/
    tasks/
    intelligence/
      IntelligenceCard.tsx
      IntelligenceDetail.tsx
      AuditDrawer.tsx               # 审计抽屉（核心交互）
      EvidenceTimeline.tsx
      ScoreBreakdown.tsx
    reports/
    alerts/
    entities/
    notifications/
    common/                         # 通用组件
      DateRangeFilter.tsx
      ProjectFilter.tsx
      StatusBadge.tsx
      EmptyState.tsx
      ErrorState.tsx
      LoadingSkeleton.tsx
  lib/
    api/                            # API client
    auth/                           # Auth context + hooks
    formatters/                     # 日期/数字格式化
    validators/                     # Zod schemas
  hooks/                            # 自定义 hooks
  types/
    api.ts                          # 从 OpenAPI 生成的类型
```

---

## 7. 数据库设计

### 7.1 users

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | — |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 登录邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 哈希 |
| name | VARCHAR(100) | NOT NULL | 显示名称 |
| status | VARCHAR(20) | DEFAULT 'active' | active / disabled |
| created_at | TIMESTAMPTZ | NOT NULL | — |
| updated_at | TIMESTAMPTZ | NOT NULL | — |

### 7.2 workspaces（MVP 单 workspace，表结构预留扩展）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | — |
| name | VARCHAR(200) | NOT NULL | 工作空间名 |
| slug | VARCHAR(100) | UNIQUE, NOT NULL | URL 标识 |
| owner_id | UUID | FK → users.id | 创建者 |
| created_at | TIMESTAMPTZ | NOT NULL | — |

### 7.3 projects

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | — |
| workspace_id | UUID | FK → workspaces.id | — |
| name | VARCHAR(200) | NOT NULL | 项目名称 |
| description | TEXT | — | — |
| domain | VARCHAR(30) | NOT NULL | osint / ecommerce / social / competitor / mixed |
| status | VARCHAR(20) | DEFAULT 'active' | active / archived |
| owner_id | UUID | FK → users.id | 负责人 |
| created_at | TIMESTAMPTZ | NOT NULL | — |
| updated_at | TIMESTAMPTZ | NOT NULL | — |

### 7.4 sources

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | — |
| workspace_id | UUID | FK → workspaces.id | — |
| project_id | UUID | FK → projects.id | — |
| name | VARCHAR(200) | NOT NULL | — |
| type | VARCHAR(30) | NOT NULL | github_repo / github_topic / generic_web / manual_json |
| url | TEXT | — | 网页/仓库 URL |
| config | JSONB | NOT NULL | 类型化配置 |
| schedule_cron | VARCHAR(50) | — | APScheduler cron 表达式 |
| enabled | BOOLEAN | DEFAULT false | — |
| created_at | TIMESTAMPTZ | NOT NULL | — |
| updated_at | TIMESTAMPTZ | NOT NULL | — |

**索引**：`(workspace_id, project_id)`, `(type, enabled)`

### 7.5 collectors（系统预置表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| type | VARCHAR(50) | github_repo / github_topic / generic_web / manual_json |
| name | VARCHAR(100) | 显示名 |
| description | TEXT | — |
| config_schema | JSONB | 前端动态表单的 JSON Schema |
| enabled | BOOLEAN | — |

### 7.6 collection_tasks

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | — |
| workspace_id | UUID | FK | — |
| project_id | UUID | FK | — |
| source_id | UUID | FK → sources.id | — |
| collector_type | VARCHAR(50) | NOT NULL | — |
| name | VARCHAR(200) | NOT NULL | — |
| schedule_cron | VARCHAR(50) | — | 继承自 Source |
| status | VARCHAR(20) | DEFAULT 'draft' | draft / enabled / running / paused / disabled |
| config | JSONB | — | 任务级配置覆盖 |
| success_count | INTEGER | DEFAULT 0 | — |
| failure_count | INTEGER | DEFAULT 0 | — |
| last_run_at | TIMESTAMPTZ | — | — |
| created_at | TIMESTAMPTZ | NOT NULL | — |
| updated_at | TIMESTAMPTZ | NOT NULL | — |

### 7.7 task_runs

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| task_id | UUID | FK → collection_tasks.id |
| workspace_id | UUID | FK |
| status | VARCHAR(20) | running / success / partial_success / failed |
| started_at | TIMESTAMPTZ | — |
| finished_at | TIMESTAMPTZ | — |
| records_count | INTEGER | 采集的原始记录数 |
| entities_count | INTEGER | 标准化的实体数 |
| error_message | TEXT | — |
| error_traceback | TEXT | — |
| logs | JSONB | 步骤级日志 `[{step, message, timestamp}]` |
| created_at | TIMESTAMPTZ | — |

**索引**：`(task_id, created_at DESC)`

### 7.8 raw_records

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| workspace_id | UUID | FK |
| project_id | UUID | FK |
| source_id | UUID | FK |
| task_run_id | UUID | FK → task_runs.id |
| record_type | VARCHAR(20) | html / json / markdown / text / screenshot |
| source_url | TEXT | 来源 URL |
| content | JSONB | 原始内容或结构化内容 |
| content_hash | VARCHAR(64) | SHA-256 去重哈希 |
| screenshot_url | TEXT | S3 截图路径（网页采集时） |
| collected_at | TIMESTAMPTZ | 采集时间戳 |
| created_at | TIMESTAMPTZ | — |

**索引**：`(content_hash)`, `(source_id, collected_at DESC)`, `(task_run_id)`

### 7.9 entities

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| workspace_id | UUID | FK |
| project_id | UUID | FK |
| entity_type | VARCHAR(30) | github_repo / web_page / product / social_post / shop / brand |
| external_id | VARCHAR(500) | 外部唯一标识（如 GitHub repo ID） |
| canonical_url | TEXT | 标准 URL |
| name | VARCHAR(500) | — |
| domain | VARCHAR(30) | 所属业务域 |
| latest_snapshot_id | UUID | FK → entity_snapshots.id |
| first_seen_at | TIMESTAMPTZ | — |
| last_seen_at | TIMESTAMPTZ | — |
| created_at | TIMESTAMPTZ | — |
| updated_at | TIMESTAMPTZ | — |

**索引**：`(external_id, entity_type)` 用于 upsert 去重，`(workspace_id, domain)`

### 7.10 entity_snapshots

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| entity_id | UUID | FK → entities.id |
| raw_record_id | UUID | FK → raw_records.id |
| snapshot_data | JSONB | 快照的结构化数据 |
| metrics | JSONB | `{stars, forks, price, rank, ...}` |
| captured_at | TIMESTAMPTZ | 快照时间 |
| created_at | TIMESTAMPTZ | — |

**索引**：`(entity_id, captured_at DESC)` 用于趋势图查询

### 7.11 signals

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| workspace_id | UUID | FK |
| project_id | UUID | FK |
| entity_id | UUID | FK → entities.id |
| signal_type | VARCHAR(30) | star_growth / page_changed / price_drop / review_growth / rank_up / data_quality_anomaly |
| previous_snapshot_id | UUID | FK → entity_snapshots.id |
| current_snapshot_id | UUID | FK → entity_snapshots.id |
| current_value | NUMERIC(18,4) | 当前值 |
| previous_value | NUMERIC(18,4) | 前值 |
| delta | NUMERIC(18,4) | 变化量 |
| delta_ratio | NUMERIC(10,6) | 变化比例 |
| confidence | NUMERIC(5,2) | 信号置信度 0-100 |
| severity | VARCHAR(10) | low / medium / high / critical |
| metadata | JSONB | 扩展数据 |
| detected_at | TIMESTAMPTZ | — |

**索引**：`(entity_id, detected_at DESC)`, `(project_id, signal_type, detected_at DESC)`

### 7.12 intelligence_items

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| workspace_id | UUID | FK |
| project_id | UUID | FK |
| title | VARCHAR(500) | 情报标题（规则或 LLM 生成） |
| summary | TEXT | LLM 生成摘要 |
| intelligence_type | VARCHAR(20) | opportunity / risk / trend / competitor / anomaly |
| status | VARCHAR(20) | new / reviewed / following / dismissed / converted |
| impact_score | NUMERIC(5,2) | 影响分 0-100 |
| confidence_score | NUMERIC(5,2) | 置信度 0-100 |
| novelty_score | NUMERIC(5,2) | 新鲜度 0-100 |
| urgency_score | NUMERIC(5,2) | 紧急度 0-100 |
| final_score | NUMERIC(5,2) | 加权总分 0-100 |
| generated_by | VARCHAR(10) | rule / llm / hybrid |
| domain | VARCHAR(30) | 所属业务域 |
| created_at | TIMESTAMPTZ | — |
| updated_at | TIMESTAMPTZ | — |

**索引**：`(project_id, created_at DESC)`, `(workspace_id, domain, created_at DESC)`, `(final_score DESC)`

### 7.13 evidences

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| intelligence_id | UUID | FK → intelligence_items.id |
| signal_id | UUID | FK → signals.id（可选） |
| entity_id | UUID | FK → entities.id（可选） |
| raw_record_id | UUID | FK → raw_records.id（可选） |
| evidence_type | VARCHAR(20) | signal / snapshot / raw_record / url |
| title | VARCHAR(500) | 证据标题 |
| url | TEXT | 来源 URL |
| excerpt | TEXT | 摘要片段（来自 RawRecord） |
| highlighted_text | TEXT | 审计抽屉中高亮的原文 |
| created_at | TIMESTAMPTZ | — |

**索引**：`(intelligence_id)`

### 7.14 reports

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| workspace_id | UUID | FK |
| project_id | UUID | FK（NULL = 全局报表） |
| report_type | VARCHAR(20) | daily |
| title | VARCHAR(300) | — |
| content | TEXT | Markdown 内容 |
| status | VARCHAR(20) | draft / generated / sent |
| period_start | TIMESTAMPTZ | — |
| period_end | TIMESTAMPTZ | — |
| created_at | TIMESTAMPTZ | — |

### 7.15 alert_rules

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| workspace_id | UUID | FK |
| project_id | UUID | FK（NULL = 全局规则） |
| name | VARCHAR(200) | — |
| signal_type | VARCHAR(30) | 监听的信号类型 |
| condition | JSONB | `{field: "severity", op: "eq", value: "critical"}` |
| channel | VARCHAR(20) | email / in_app / both |
| enabled | BOOLEAN | — |
| created_at | TIMESTAMPTZ | — |

### 7.16 alert_events

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| rule_id | UUID | FK → alert_rules.id |
| signal_id | UUID | FK → signals.id |
| status | VARCHAR(20) | triggered / sent / acknowledged / resolved |
| payload | JSONB | 通知内容快照 |
| triggered_at | TIMESTAMPTZ | — |
| sent_at | TIMESTAMPTZ | — |

### 7.17 notifications（站内通知）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| title | VARCHAR(300) | — |
| body | TEXT | — |
| notification_type | VARCHAR(30) | report_ready / alert / task_failed |
| reference_type | VARCHAR(30) | report / alert_event / task_run |
| reference_id | UUID | 关联对象 ID |
| is_read | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | — |

---

## 8. Collector 采集引擎

### 8.1 统一抽象接口

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class CollectorResult:
    raw_records: list[dict[str, Any]]   # 原始记录列表
    logs: list[dict[str, Any]]          # 步骤日志
    errors: list[str] = field(default_factory=list)

class BaseCollector(ABC):
    collector_type: str

    @abstractmethod
    async def validate_config(self, config: dict[str, Any]) -> bool:
        """验证配置是否合法"""
        ...

    @abstractmethod
    async def test(self, config: dict[str, Any]) -> CollectorResult:
        """测试采集（返回少量数据验证连通性）"""
        ...

    @abstractmethod
    async def collect(self, config: dict[str, Any]) -> CollectorResult:
        """执行完整采集"""
        ...

    @abstractmethod
    async def normalize(
        self, raw_record: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """将 RawRecord 标准化为 Entity + Snapshot 数据"""
        ...
```

### 8.2 MVP 四个 Collector

#### GitHubRepoCollector

- **输入**：`{owner: "org_or_user", repo: "repo_name"}`
- **采集方式**：GitHub REST API（无需 token 可访问公开仓库基础信息）
- **采集字段**：`full_name`, `description`, `stargazers_count`, `forks_count`, `open_issues_count`, `language`, `topics`, `pushed_at`, `latest_release` (tag_name, published_at, body)
- **输出 Entity**：`github_repo`
- **关键指标**：`stars`, `forks`, `latest_release_tag`, `pushed_at`

#### GitHubTopicCollector

- **输入**：`{topic: "web-scraping", max_results: 30}`
- **采集方式**：GitHub Search API（按 topic 搜索仓库，按 stars 排序）
- **采集字段**：top N 仓库的基础信息（同上）
- **输出 Entity**：`github_repo[]`（仓库列表）
- **用途**：发现新项目，可对其中感兴趣的 repo 再创建 GitHubRepoCollector 持续监控

#### GenericWebCollector

- **输入**：`{url: "https://...", extract_mode: "full_html" | "main_content"}`
- **采集方式**：httpx + BeautifulSoup / readability-lxml
- **采集字段**：`title`, `text_content`, `html_content`, `meta_tags`
- **输出 Entity**：`web_page`
- **附加**：如配置了 S3，截图保存到 `screenshot_url`
- **限制**：单页面，不递归爬取；遵守 robots.txt

#### ManualJsonCollector

- **输入**：用户上传的 JSON 数据 + `{entity_type: "product" | "github_repo" | ...}`
- **采集方式**：直接解析 JSON
- **输出 Entity**：任意 entity_type
- **用途**：第三方数据导入、CSV 转 JSON 导入、手动补充数据

### 8.3 Collector 开发规则

1. 每个 Collector 必须实现 `validate_config`、`test`、`collect`、`normalize` 四个方法
2. `collect()` 必须生成至少一条 RawRecord
3. `normalize()` 必须生成至少一个 Entity + EntitySnapshot
4. Collector 内**禁止**直接生成 Intelligence——只负责采集和标准化
5. 所有 HTTP 请求必须设置合理的 timeout 和 User-Agent
6. 网络错误必须捕获并以结构化日志记录，不抛未处理异常

---

## 9. Signal 信号检测引擎

### 9.1 设计原则

信号检测**不依赖 AI**，全部通过确定性代码逻辑对比 EntitySnapshot 的 metrics 产生。每个 Signal 必须记录 `previous_snapshot_id` 和 `current_snapshot_id`，支持前端对比视图。

### 9.2 MVP 信号类型

#### star_growth（Star 增长信号）

```python
# 触发条件（任一满足即触发）
stars_growth_24h > 100  # 24h 内绝对增长超过 100
# 或
growth_rate_24h > 2.0   # 24h 内增长率超过 200%

# 严重度
if growth_rate > 5.0 or stars_growth > 500: severity = "critical"
elif growth_rate > 2.0 or stars_growth > 200: severity = "high"
elif growth_rate > 1.0 or stars_growth > 50: severity = "medium"
else: severity = "low"
```

#### page_changed（页面变化信号）

```python
# 触发条件
content_hash 变化  # 与前一次快照的 hash 不同

# 更进一步：计算变化幅度
# 对 html_content 计算归一化的 Levenshtein 距离
change_ratio = levenshtein(old_html, new_html) / max(len(old_html), len(new_html))

if change_ratio > 0.3: severity = "high"       # 大幅改版
elif change_ratio > 0.1: severity = "medium"   # 中等变化
elif change_ratio > 0.01: severity = "low"     # 细微变化
else: severity = "low"  # 仅 hash 变化，内容几乎相同
```

#### price_drop（价格下降信号）

```python
# 触发条件
delta_ratio < -0.05  # 价格下降超过 5%

# 严重度
if delta_ratio < -0.3: severity = "critical"   # 降价超 30%
elif delta_ratio < -0.15: severity = "high"    # 降价超 15%
elif delta_ratio < -0.05: severity = "medium"  # 降价超 5%
```

#### data_quality_anomaly（数据质量异常信号）

```python
# 触发条件（在 task_run 完成后评估）
recent_failure_rate > 0.3  # 最近 10 次运行失败率超过 30%
# 或
consecutive_failures >= 3   # 连续失败 3 次

if consecutive_failures >= 5: severity = "critical"
elif consecutive_failures >= 3: severity = "high"
elif recent_failure_rate > 0.5: severity = "medium"
else: severity = "low"
```

### 9.3 信号检测时序

信号检测发生在每次 TaskRun 成功完成后：

```
TaskRun success
    → CollectorService 返回 raw_records
    → NormalizationService 生成 entities + snapshots
    → SignalService.detect(entity_id)  # 对比最近两次 snapshot
        → 满足触发条件 → 创建 Signal
        → 不满足 → 跳过
    → 如有新 Signal → 触发 IntelligenceService
```

---

## 10. Intelligence 情报引擎

### 10.1 评分公式

全部通过确定性规则计算，不受 AI 随机性影响：

```
FinalScore = ImpactScore × 0.35 + ConfidenceScore × 0.25
           + NoveltyScore × 0.20 + UrgencyScore × 0.20
```

所有分维度范围：**0-100**。

| 维度 | 权重 | 计算依据 |
|---|---|---|
| ImpactScore | 35% | delta_ratio 绝对值映射、平台权重（GitHub > 通用网页）、实体热门度 |
| ConfidenceScore | 25% | evidence 数量（≥3 条 = 满分）、数据源可信度、字段完整率 |
| NoveltyScore | 20% | 该实体是否首次产生此类信号、过去 30 天是否有同类信号 |
| UrgencyScore | 20% | severity 映射（critical=100, high=70, medium=40, low=10）、信号新鲜度 |

### 10.2 情报生成规则

| Intelligence Type | 触发条件 | 说明 |
|---|---|---|
| trend | 同一 Project 下多个 star_growth / topic 实体增长 | 技术趋势信号 |
| competitor | page_changed / 竞品实体产生新 signal | 竞品动态 |
| opportunity | 多个正向信号聚合（stars↑ + release + 页面更新） | 市场机会 |
| risk | 高危 severity 信号 | 风险预警 |
| anomaly | data_quality_anomaly 或指标突变 | 系统/数据异常 |

### 10.3 情报生成流程

```
1. SignalService 检测到新 Signal
2. IntelligenceService 查询该 Project 下最近 N 个 Signal
3. 按 Intelligence Type 聚合规则，判断是否生成新 Intelligence
4. 收集关联 Entity、Signal、RawRecord 作为 evidence
5. 计算四个分维度评分 → 加权得 FinalScore
6. 调用 LLM Service 生成 title 和 summary（附带 evidence 列表）
7. 保存 IntelligenceItem + Evidences（每条 evidence 绑定 signal/entity/raw_record）
8. 匹配 AlertRule → 满足规则则创建 AlertEvent
```

### 10.4 证据链构建规则

- 每条 Intelligence 至少有 **1 条** Evidence
- Evidence 类型包括：
  - `signal`：直接关联的 Signal（含 previous/current snapshot 引用）
  - `snapshot`：EntitySnapshot（含 metrics 数据）
  - `raw_record`：RawRecord（含原文和截图 URL）
  - `url`：来源 URL（如 GitHub 链接）
- 审计抽屉通过 Evidence 的 `highlighted_text` 字段定位原文

---

## 11. Report 日报系统

### 11.1 日报结构

```markdown
# {项目名} 日报 — {日期}

## 📊 监控概览
- 采集任务成功率：{percent}%
- 新增信号数：{count}
- 新增情报数：{count}
- 活跃预警：{count}

## 🔥 核心发现（按业务域分组）
### {Domain 1}
1. **{Intelligence Title}** — Score: {final_score}
   {summary}
   证据数：{evidence_count}

### {Domain 2}
...

## ⚠️ 预警区
- {alert_event 1}
- {alert_event 2}

## 📈 数据质量
| 数据源 | 采集状态 | 成功率 | 记录数 | 延迟 |
|--------|----------|--------|--------|------|
| ...    | ...      | ...    | ...    | ...  |
```

### 11.2 日报生成流程

```
1. 用户手动触发 或 APScheduler 定时触发
2. ReportService 查询当日数据：
   - Intelligence（created_at IN today）
   - Signal（detected_at IN today）
   - TaskRun（started_at IN today）
   - AlertEvent（triggered_at IN today）
3. 构建结构化数据上下文
4. LLM 基于结构化数据生成日报 Markdown
5. 保存 Report（status: generated）
6. 发送（邮件 + 站内通知）→ status: sent
```

### 11.3 配置项

| 配置 | 默认值 | 说明 |
|---|---|---|
| 日报范围 | 全局（所有 Project） | 可指定 project_id |
| 生成时间 | 每天 08:00 | APScheduler cron |
| 发送方式 | 站内通知 + 邮件 | 可在 AlertRule 中覆盖 |

---

## 12. Alert 预警系统

### 12.1 预警规则配置

```json
{
  "name": "高危信号即时通知",
  "project_id": null,
  "signal_type": "*",
  "condition": {
    "field": "severity",
    "op": "in",
    "value": ["critical", "high"]
  },
  "channel": "both",
  "enabled": true
}
```

### 12.2 预警触发流程

```
Signal 创建
  → AlertService.match_rules(signal)
    → 遍历该 workspace 下所有 enabled 的 AlertRule
    → condition 匹配 → 创建 AlertEvent (status: triggered)
    → channel = email → 发送邮件 → status: sent
    → channel = in_app → 创建 Notification → status: sent
```

---

## 13. API 合约

### 13.1 Auth

| Method | Path | 说明 |
|---|---|---|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录（返回 JWT Cookie） |
| POST | /api/auth/logout | 登出 |
| GET | /api/auth/me | 获取当前用户 |

### 13.2 Dashboard

| Method | Path | 说明 |
|---|---|---|
| GET | /api/dashboard/overview?project_id=&from=&to= | 仪表盘汇总数据 |

Response:
```json
{
  "intelligence_count": 24,
  "by_type": {"opportunity": 8, "risk": 3, "trend": 9, "competitor": 2, "anomaly": 2},
  "task_success_rate": 0.93,
  "field_completeness": 0.87,
  "top_intelligence": [{...}],
  "domain_breakdown": {
    "osint": {"intelligence_count": 10, "signal_count": 15},
    "competitor": {"intelligence_count": 6, "signal_count": 8}
  }
}
```

### 13.3 Projects

| Method | Path | 说明 |
|---|---|---|
| GET | /api/projects | 列表（支持 domain 筛选） |
| POST | /api/projects | 创建 |
| GET | /api/projects/{id} | 详情 |
| PATCH | /api/projects/{id} | 更新 |
| DELETE | /api/projects/{id} | 删除（软删除→归档） |

### 13.4 Sources

| Method | Path | 说明 |
|---|---|---|
| GET | /api/sources?project_id=&type= | 列表 |
| POST | /api/sources | 创建 |
| GET | /api/sources/{id} | 详情 |
| PATCH | /api/sources/{id} | 更新 |
| POST | /api/sources/{id}/test | 测试采集 |
| POST | /api/sources/{id}/enable | 启用（自动创建 Task + APScheduler job） |
| POST | /api/sources/{id}/disable | 停用（移除 APScheduler job） |

### 13.5 Tasks

| Method | Path | 说明 |
|---|---|---|
| GET | /api/tasks?project_id=&status= | 列表 |
| GET | /api/tasks/{id} | 详情 |
| POST | /api/tasks/{id}/run | 手动运行 |
| POST | /api/tasks/{id}/pause | 暂停 |
| POST | /api/tasks/{id}/resume | 恢复 |
| GET | /api/tasks/{id}/runs | 运行历史 |

### 13.6 Task Runs

| Method | Path | 说明 |
|---|---|---|
| GET | /api/task-runs/{id} | 运行详情 |
| GET | /api/task-runs/{id}/logs | 运行日志 |

### 13.7 Raw Records

| Method | Path | 说明 |
|---|---|---|
| GET | /api/raw-records?source_id=&task_run_id= | 列表 |
| GET | /api/raw-records/{id} | 详情（含完整 content） |

### 13.8 Entities

| Method | Path | 说明 |
|---|---|---|
| GET | /api/entities?entity_type=&domain=&project_id= | 列表 |
| GET | /api/entities/{id} | 详情 |
| GET | /api/entities/{id}/snapshots | 快照历史（用于趋势图） |
| GET | /api/entities/{id}/signals | 关联信号 |

### 13.9 Intelligence

| Method | Path | 说明 |
|---|---|---|
| GET | /api/intelligence?project_id=&type=&status=&domain=&sort= | 列表 |
| GET | /api/intelligence/{id} | 详情 |
| PATCH | /api/intelligence/{id}/status | 更新状态 |
| GET | /api/intelligence/{id}/evidences | 证据列表 |
| POST | /api/intelligence/{id}/feedback | 提交反馈 {useful / not_useful / false_positive} |

### 13.10 Reports

| Method | Path | 说明 |
|---|---|---|
| GET | /api/reports?project_id= | 列表 |
| POST | /api/reports/generate | 手动生成日报 |
| GET | /api/reports/{id} | 详情（含 Markdown 内容） |
| POST | /api/reports/{id}/send | 发送（邮件 + 站内通知） |

### 13.11 Alerts

| Method | Path | 说明 |
|---|---|---|
| GET | /api/alert-rules | 列表 |
| POST | /api/alert-rules | 创建 |
| PATCH | /api/alert-rules/{id} | 更新 |
| DELETE | /api/alert-rules/{id} | 删除 |
| GET | /api/alert-events?rule_id=&status= | 事件列表 |

### 13.12 Notifications

| Method | Path | 说明 |
|---|---|---|
| GET | /api/notifications?is_read= | 列表 |
| PATCH | /api/notifications/{id}/read | 标记已读 |
| POST | /api/notifications/read-all | 全部已读 |

---

## 14. 前端页面规格

### 14.1 页面一：登录/注册

**路径**：`/login`

- 邮箱 + 密码登录
- 新用户注册（自动创建默认 Workspace）
- 登录失败显示错误提示
- 刷新页面后保持登录态（JWT HttpOnly Cookie）

### 14.2 页面二：全局仪表盘

**路径**：`/dashboard`

组件：

| 组件 | 功能 |
|---|---|
| DomainFilter | 按业务域筛选 |
| DateRangeFilter | 时间范围 |
| IntelligenceSummaryCards | 情报总量 / 机会 / 风险 / 趋势 / 异常 |
| DomainBreakdown | 各域情报和信号数量 |
| TopIntelligenceList | 按 finalScore 排序的 Top 10 |
| TaskHealthPanel | 采集成功率、失败任务数、最近失败 |
| DataQualityPanel | 字段完整率 |
| LatestReportCard | 最新日报入口 |

### 14.3 页面三：业务域视图（4 个域各自独立页）

每个域的页面结构一致，只是默认筛选器和展示重点不同：

- `/domain/osint` — 开源雷达：GitHub Trending 榜单、Star 增速、Release 流
- `/domain/ecommerce` — 电商风向：价格变动、排名走势
- `/domain/social` — 社媒脉搏（MVP 仅展示手动导入的数据）
- `/domain/competitor` — 竞品守望：官网变化、页面快照对比

每个域页面包含：
- 该域下的 Project 列表卡片
- 该域下的最新 Intelligence
- 该域下的 Entity 趋势

### 14.4 页面四：项目列表

**路径**：`/projects`

- 卡片 + 表格混合视图
- 支持按 domain 分类筛选
- 支持搜索、按状态（active / archived）筛选
- 创建项目弹窗（name, description, domain, owner）

### 14.5 页面五：数据源管理

**路径**：`/sources`

- 数据源列表（名称、类型、关联项目、状态、最近采集时间）
- 新增数据源：根据 collector type 动态渲染配置表单
- 测试采集按钮 → 显示测试结果
- 启用/停用开关

Source 类型与表单字段映射：

| Type | 必填字段 |
|---|---|
| github_repo | owner (string), repo (string) |
| github_topic | topic (string), max_results (int, default 30) |
| generic_web | url (string) |
| manual_json | entity_type (select), json_data (textarea/file upload) |

### 14.6 页面六：任务管理

**路径**：`/tasks`

- 任务列表（任务名、数据源、状态、调度、成功率、最近运行时间）
- Run Now 按钮 → 创建 TaskRun
- Pause / Resume
- 点击进入任务详情 → 运行历史列表 → 点击 run_id → 运行日志

### 14.7 页面七：情报列表

**路径**：`/intelligence`

筛选条件：domain / project / type / status / score 区间 / 日期范围

情报卡片展示：标题 / 摘要 / 类型标签 / severity 标签 / finalScore / 证据数 / 创建时间 / 状态

支持按 finalScore 排序、状态快速修改（下拉菜单）

### 14.8 页面八：情报详情（含审计抽屉）

**路径**：`/intelligence/{id}`

页面模块：

| 模块 | 内容 |
|---|---|
| Header | 标题、类型标签、状态、finalScore |
| Score Breakdown | 四个维度雷达图或条形图 |
| AI Summary | LLM 生成的摘要（底部标注"基于 X 条证据生成"） |
| Related Entities | 关联实体卡片（点击进入实体详情） |
| Signals | 关联信号列表（含 delta 和严重度） |
| Evidence Timeline | 按时间线的证据列表 |
| Feedback | 有用 / 无用 / 误报 按钮 |

**审计抽屉**：点击摘要中的任意关键结论文字，右侧弹出 Drawer：

- 左栏：AI 生成的摘要，关键数字/结论可点击高亮
- 右栏：对应 Evidence 的原文片段、截图、对比视图
- 对比模式：Old Snapshot vs New Snapshot 指标并排展示

### 14.9 页面九：实体详情

**路径**：`/entities/{id}`

- 实体基本信息（name, type, canonical_url, first_seen, last_seen）
- 指标趋势图（基于 snapshots 的 metrics 绘制折线图）
- 关联 Signal 时间线
- 关联 Intelligence

### 14.10 页面十：报告中心

**路径**：`/reports`

- 报告列表（标题、类型、周期、状态、生成时间）
- 生成日报按钮 → 选择 project（或全局）→ 生成
- 报告详情：完整 Markdown 渲染
- 发送按钮 → 邮件 + 站内通知

### 14.11 页面十一：预警配置

**路径**：`/alerts`

- 规则列表（名称、信号类型、条件、渠道、状态）
- 创建/编辑规则弹窗
- 预警事件列表（规则、信号、状态、触发时间）

### 14.12 页面十二：站内通知

**路径**：`/notifications`

- 通知列表（标题、类型、时间、已读/未读）
- 点击跳转到关联对象（情报/日报/任务运行）
- 全部已读按钮

---

## 15. 后端服务流程

### 15.1 采集任务执行流程

```
User/APScheduler 触发
  → TaskService.create_task_run(task_id)
  → TaskRun status = "running"
  → CollectorService.execute(source, collector_type, config)
    → Collector.collect(config)
    → 保存 RawRecords
    → Collector.normalize(raw_record)
    → NormalizationService.upsert_entity()
    → NormalizationService.create_snapshot()
  → TaskRun status = "success" | "partial_success" | "failed"
  → SignalService.detect_for_entity(entity_id)
    → 如有新 Signal → IntelligenceService.generate()
  → AlertService.match_rules(new_signals)
  → 返回 TaskRun 结果
```

### 15.2 定时调度（APScheduler）

```python
# scheduler/jobs.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()

def sync_tasks_from_db():
    """从数据库加载所有 enabled 的 collection_task，注册/更新 cron job"""
    tasks = get_enabled_tasks()
    for task in tasks:
        job_id = f"collect_{task.id}"
        if scheduler.get_job(job_id):
            scheduler.reschedule_job(job_id, trigger=CronTrigger.from_crontab(task.schedule_cron))
        else:
            scheduler.add_job(
                run_collection_task,
                CronTrigger.from_crontab(task.schedule_cron),
                id=job_id,
                args=[task.id],
                replace_existing=True,
            )

# 日报定时生成
scheduler.add_job(
    generate_daily_reports,
    CronTrigger(hour=8, minute=0),  # 每天 8:00
    id="daily_report",
)

# 每 5 分钟同步一次任务调度表
scheduler.add_job(sync_tasks_from_db, "interval", minutes=5, id="sync_tasks")

scheduler.start()
```

---

## 16. LLM 使用边界

### 16.1 允许 LLM 做的事

| 场景 | 输入 | 输出 |
|---|---|---|
| Intelligence summary | 结构化信号 + 实体 + 证据 | title, summary, reasoning |
| Daily report content | 当日情报列表 + 采集数据 | Markdown 报告正文 |
| Entity description | Entity snapshots 数据 | 实体自然语言描述 |
| Evidence explanation | Evidence excerpt | 证据为何支持结论的解释 |

### 16.2 严格禁止 LLM 做的事

| 禁止项 | 原因 |
|---|---|
| 伪造/编造数据 | 所有数据必须来自 RawRecord |
| 生成不存在的 URL | 防止幻觉链接 |
| 修改 score | Score 由确定性公式计算 |
| 决定采集任务成功/失败 | 由系统状态判断 |
| 越权访问数据 | 权限在 Service 层控制 |

### 16.3 LLM 可插拔 Adapter 模式

```python
from abc import ABC, abstractmethod

class BaseLLMAdapter(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        ...

class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        ...

class AnthropicAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        ...

# llm_service.py
class LLMService:
    def __init__(self, adapter: BaseLLMAdapter):
        self.adapter = adapter

    async def summarize_intelligence(self, context: dict) -> dict:
        """根据情报上下文生成 title + summary"""
        ...
```

### 16.4 LLM Prompt 模板（Anti-Hallucination）

```
你是一个商业情报分析师。输入包含：
- 信号列表：[{signal_type, delta_ratio, severity, ...}]
- 实体快照：[{entity_type, name, metrics, ...}]
- 证据片段：[{title, url, excerpt, ...}]

请输出 JSON 格式：
{
  "title": "简洁的情报标题（中文，<30字）",
  "summary": "2-3 句话的业务洞察（中文）",
  "reasoning": "分析推理过程"
}

严格要求：
1. 每条结论必须能从证据片段中找到支撑
2. 如果数据不足以得出结论，回答"信息不足"
3. 禁止编造任何数字、URL、人名或公司名
4. 所有指标必须来自输入数据，不得推测
```

---

## 17. 部署方案

### 17.1 推荐方案：单机 Docker Compose

小规模数据量下，单机部署完全满足需求：

```yaml
# docker-compose.yml
services:
  api:
    build: ./apps/api
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/data_intel
      - JWT_SECRET=${JWT_SECRET}
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - LLM_API_KEY=${LLM_API_KEY}
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - S3_ENDPOINT=${S3_ENDPOINT}
      - S3_ACCESS_KEY=${S3_ACCESS_KEY}
      - S3_SECRET_KEY=${S3_SECRET_KEY}
    depends_on: [db]

  web:
    build: ./apps/web
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on: [api]

  db:
    image: postgres:15
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=data_intel
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=${DB_PASSWORD}

volumes:
  pgdata:
```

### 17.2 环境变量清单

| 变量 | 说明 | 必填 |
|---|---|---|
| DATABASE_URL | PostgreSQL 连接串 | ✅ |
| JWT_SECRET | JWT 签名密钥 | ✅ |
| LLM_PROVIDER | openai / anthropic | ✅ |
| LLM_API_KEY | LLM API Key | ✅ |
| LLM_MODEL | 模型名（默认 gpt-4o-mini） | — |
| SMTP_HOST | 邮件服务器 | ✅ |
| SMTP_PORT | 邮件端口 | ✅ |
| SMTP_USER | 邮箱账号 | ✅ |
| SMTP_PASSWORD | 邮箱密码 | ✅ |
| SMTP_FROM | 发件人地址 | ✅ |
| S3_ENDPOINT | S3 或 MinIO endpoint | — |
| S3_ACCESS_KEY | Access Key | — |
| S3_SECRET_KEY | Secret Key | — |
| S3_BUCKET | Bucket 名 | — |
| LOG_LEVEL | 日志级别（默认 INFO） | — |

### 17.3 成本估算（月度，小型规模）

| 资源 | 预估费用 |
|---|---|
| 云主机（2C4G） | $20-40 |
| PostgreSQL 云数据库 | $15-30（或使用自建，含在主机内） |
| S3 / MinIO（截图存储） | $2-5 |
| LLM API（GPT-4o-mini，约 10 万 token/月） | $0.5-2 |
| SMTP 邮件服务 | $0-5 |
| **合计** | **约 $40-80/月** |

---

## 18. 开发计划

### 18.1 总览

总周期：**10 周**（10 个 Sprint，每周 1 Sprint）

| Sprint | 周期 | 主题 | 核心交付 |
|---|---|---|---|
| 0 | 2 天 | 工程初始化 | 前后端骨架 + DB + Auth |
| 1 | 1 周 | 用户与项目 | 登录/注册 + Project CRUD |
| 2 | 1 周 | 数据源与任务 | Source CRUD + Task 手动运行 |
| 3 | 1 周 | Collector 引擎 | 四个 Collector + RawRecord |
| 4 | 1 周 | 实体与快照 | Entity upsert + Snapshot |
| 5 | 1 周 | Signal 检测 | 确定性信号检测引擎 |
| 6 | 1 周 | Intelligence 引擎 | 证据绑定情报 + 审计抽屉 |
| 7 | 1 周 | Dashboard | 仪表盘 + 业务域视图 |
| 8 | 1 周 | Report + Alert | 日报生成 + 预警通知 |
| 9 | 1 周 | 稳定与交付 | 测试、性能、部署、seed data |

### 18.2 Sprint 详情

#### Sprint 0：工程初始化（2 天）

**后端**：
- FastAPI 项目骨架、目录结构
- SQLAlchemy + Alembic 配置
- PostgreSQL 连接
- JWT Auth 基础结构（登录/注册/me）
- pytest 配置
- OpenAPI 文档可访问

**前端**：
- Next.js 项目初始化
- Tailwind CSS + shadcn/ui
- TanStack Query 配置
- 基础 Layout（Sidebar 双层导航）
- API client 封装

**验收**：`/health` 返回 200，`/api/docs` 可访问，前端登录页可渲染

#### Sprint 1：用户与项目（1 周）

**后端**：users / workspaces / projects 表 + models + schemas + services + routes

**前端**：登录页、Dashboard 空状态、Project 列表 + 创建/编辑、domain 筛选

#### Sprint 2：数据源与任务（1 周）

**后端**：sources / collectors / collection_tasks / task_runs 表 + CRUD + Source test + Task run + APScheduler 集成

**前端**：Source 列表 + 创建（动态表单）+ 测试结果展示 + Task 列表 + 手动 Run Now

#### Sprint 3：Collector 引擎（1 周）

**后端**：BaseCollector + 四个 MVP Collector + raw_records 表 + collector_service + normalization_service 初版

**前端**：RawRecord 列表 + 详情 + TaskRun 日志页

#### Sprint 4：实体与快照（1 周）

**后端**：entities / entity_snapshots 表 + Entity upsert（external_id 去重）+ Snapshot 创建 + Entity API + Snapshots API

**前端**：Entity 列表 + 详情 + Snapshot 时间线 + 趋势图

#### Sprint 5：Signal 检测（1 周）

**后端**：signals 表 + star_growth / page_changed / data_quality_anomaly 检测 + signal_service + signals API

**前端**：Signal 列表 + Entity 详情中展示 signals

#### Sprint 6：Intelligence 引擎（1 周）

**后端**：intelligence_items / evidences 表 + intelligence_service + evidence_service + 规则聚合 + LLM adapter + mock LLM

**前端**：Intelligence 列表 + 详情 + Evidence Timeline + **审计抽屉** + 状态修改 + Feedback

#### Sprint 7：Dashboard（1 周）

**后端**：dashboard overview API + task health API + top intelligence API + domain breakdown

**前端**：Dashboard 总览 + 四个业务域页面 + 情报卡片 + 任务健康度 + 数据质量

#### Sprint 8：Report + Alert（1 周）

**后端**：reports / alert_rules / alert_events / notifications 表 + report generator + alert matcher + email sender + notification service

**前端**：Reports 列表 + 生成/查看 + Alerts 配置 + 事件列表 + 通知中心

#### Sprint 9：稳定与交付（1 周）

- 统一错误处理（前端 + 后端）
- API 参数校验
- 前端 loading / empty / error 三态
- 后端单元测试（核心 service）
- 端到端 happy path 测试
- Seed data + Demo workspace
- 部署文档 + docker-compose
- 性能：Dashboard 首屏 ≤3s，API P95 ≤800ms

---

## 19. 验收标准

### 19.1 功能验收

| 模块 | 验收标准 |
|---|---|
| Auth | 邮箱注册、登录、登出、获取当前用户 |
| Project | 创建、编辑、归档、domain 筛选 |
| Source | 创建（4 种类型）、测试采集、启停 |
| Task | 手动运行、查看状态、查看运行日志 |
| Collector | GitHub Repo / Topic / 通用网页 / 手动 JSON 四个 Collector 可正常工作 |
| RawRecord | 每次采集保存原始记录（含 content_hash） |
| Entity | 原始记录转为实体，同 external_id 不重复创建 |
| Snapshot | 每次采集为新/旧实体创建快照 |
| Signal | star_growth、page_changed、data_quality_anomaly 按规则正确触发 |
| Intelligence | Signal 聚合生成情报，每条至少 1 Evidence |
| Evidence | 可溯源到 Signal → Snapshot → RawRecord |
| Dashboard | 展示情报汇总、任务健康度、数据质量、分域拆解 |
| 业务域视图 | 四个域页面各自展示对应域的 Project 和 Intelligence |
| 审计抽屉 | 情报详情中可点击结论查看证据原文和对比视图 |
| Report | 手动生成日报，显示情报和数据质量 |
| Alert | 规则命中后生成 AlertEvent，触发通知 |
| 通知 | 站内通知列表 + 已读/未读 + 邮件发送 |

### 19.2 数据质量验收

| 指标 | MVP 目标 |
|---|---|
| 采集任务成功率 | ≥ 90% |
| RawRecord 保存率 | 100%（采集成功时） |
| Entity 去重准确率 | ≥ 95% |
| Intelligence 证据链覆盖率 | 100% |
| Dashboard 首屏加载 | ≤ 3 秒 |
| API P95 响应时间 | ≤ 800ms |
| 日报生成成功率 | ≥ 95% |

### 19.3 工程验收

| 项目 | 标准 |
|---|---|
| 后端测试 | 核心 service 有单元测试 |
| API 文档 | OpenAPI（/docs）可访问且完整 |
| DB migration | Alembic upgrade/downgrade 可重复执行 |
| 前端类型 | TypeScript 无 `any` 滥用 |
| 错误处理 | API 返回统一 `{error: {code, message}}` 格式 |
| 权限 | Workspace 数据隔离 |
| 日志 | TaskRun 保存结构化步骤日志 |
| 配置 | 所有环境变量在 config.py 集中管理 |

---

## 20. 风险控制

### 20.1 数据采集风险

- MVP 不做社媒页面直接抓取——社媒数据通过手动导入或 API 接入
- 网页采集设置合理并发、遵守 robots.txt、设置 User-Agent
- 每个 Collector 独立错误处理，一个 Collector 失败不影响其他

### 20.2 LLM 幻觉风险

- LLM 只生成摘要文本——所有事实数据来自系统
- 每条 Prompt 包含"禁止编造"指令
- Intelligence 必须绑定至少 1 条 Evidence
- 评分不使用 AI，全部确定性公式

### 20.3 架构过度设计风险

- MVP 不引入 Kafka / 复杂多租户 / 插件市场 / 复杂 BI
- 单 PostgreSQL + 进程内 APScheduler 完成闭环
- 规模增长后可按需引入 Redis + Celery，接口层无需改变

### 20.4 前后端阻塞风险

- 前端支持 mock API 模式独立开发
- 后端先输出 OpenAPI 文档
- 双方通过 API 契约并行开发

### 20.5 合规风险

- 网页采集仅限公开可访问页面
- 不绕过付费墙、登录墙
- 首次使用前建议确认目标网站的 ToS

---

## 21. 附录：源 PRD 差异整合说明

本 PRD 由两份源文档整合而来，以下是关键差异的取舍说明：

| 差异点 | ai_prd.md | ai_prd_end.md | 整合决策 |
|---|---|---|---|
| 导航模型 | 传统功能导航（项目/数据源/任务...） | 业务域导航（开源/电商/社媒/竞品）+ 工程中心 | **合并**：双层导航——业务域 + 全局中心 + 工程中心 |
| Collector 列表 | 6 个 MVP Collector（含 Firecrawl, Apify） | 3 个（GitHub, Web, Ecommerce） | **裁剪**：MVP 做 4 个——GitHub Repo / Topic / 通用网页 / 手动 JSON。Firecrawl 和 Apify 后置到 P1 |
| 信号类型 | 6 种（含 price_drop, review_growth, rank_up） | 3 种（PriceDrop, StarSurge, HtmlDiff） | **采用 ai_prd.md** 的信号枚举更完整，但 MVP 只实现有数据源支撑的类型 |
| 调度框架 | Celery + Redis + Celery Beat | Celery Beat | **采用 APScheduler**：调研确认小规模无需 Redis，进程内调度更简洁 |
| 审计抽屉 | 无 | 核心交互 | **保留**：这是 ai_prd_end.md 的灵魂设计 |
| 开发周期 | 10 个 Sprint × 1 周 + Sprint 0（2 天） | 5 周（W1-W5） | **采用 ai_prd.md** 的 10 Sprint 计划，更细粒度的开发任务拆分 |
| 数据库 | 15 张表 | SQL Schema 片段（4 张核心表） | **采用 ai_prd.md** 的完整表设计，补充 notifications 表 |
| LLM 使用 | 明确允许/禁止场景 + Prompt 模板 | Anti-Hallucination 策略 | **合并**：保留两边精华 |
| 评分公式 | FinalScore 四维度加权 | Impact / Confidence / Novelty 三维度 | **采用 ai_prd.md** 的四维度加权（补充了 Urgency） |
| 截图存储 | 未明确 | 明确要求 screenshot_url（S3） | **保留**：网页采集保存截图 |

---

> **版本历史**：v2.0 — 2026-06-11 初始整合版本，基于 ai_prd.md v1 和 ai_prd_end.md v1 以及四轮全维度调研决策。
>
> *本文档为产品 PRD，面向人类开发者与 AI 开发工具（Codex/Cursor/Copilot）双读者，所有模块均包含明确的数据模型、API 合同和验收标准，支持直接按 Sprint 顺序生成前后端代码。*

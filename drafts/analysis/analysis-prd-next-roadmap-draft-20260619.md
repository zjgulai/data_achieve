---
title: 自动化数据采集工作台下一阶段路线草案
doc_type: analysis
module: product
topic: prd-next-roadmap
status: draft
created: 2026-06-19
updated: 2026-06-19
owner: self
source: human+ai
---

# 自动化数据采集工作台下一阶段路线草案

## 1. 结论

当前项目应从“跨平台数据采集情报平台”继续重构为“自动化数据采集工作台”。工具情报、培训 SOP 和采集工具雷达不是主产品入口，而是辅助层：它们负责根据目标网站、字段、合规边界和维护成本推荐采集策略。

下一阶段的主链路是：

```text
目标平台/URL/API/导入数据
-> 授权与合规确认
-> 网站结构解析
-> 字段候选与字段筛选
-> 采集计划生成
-> 清洗规则或脚本生成
-> 结构化保存为 Dataset
-> 调度运行与漂移监控
-> 报告、告警、通知与导出
```

状态修正：采集计划、清洗计划、首批平台包和重复动作基础保护已经完成一轮生产部署与验收。下一阶段优先级应从“补齐骨架”切换为“扩大真实平台采集深度”，尤其是 GitHub/API-first 工具情报包、浏览器结构解析预检、独立站 collection/sitemap 深化，以及 marketplace/social 的授权导入或 API 路线。

## 2. 事实基线

以下为 2026-06-19 本地代码、文档和生产验收记录得到的事实。

### 2.1 已完成或基本完成

1. 核心情报链路已经建立：`RawRecord -> EntitySnapshot -> Signal -> Intelligence -> Evidence -> Report / Alert`。
2. API 已挂载 `/api/automation` 自动采集路由。
3. 已存在 `ecommerce_product_page` 和 `ecommerce_product_discovery` collector。
4. `/automation` 工作台已覆盖站点分析、商品发现、fan-out、批量运行、Dataset 预览、保存、调度审批、漂移检查等流程。
5. `/datasets` 资产台已覆盖 Dataset、DatasetVersion、漂移历史和导出入口。
6. 数据模型已存在 `datasets`、`dataset_versions`、`dataset_drift_events`、`dataset_export_jobs`。
7. Dataset 导出已经不是空白项：后端已有 `product-dataset-exports` 创建接口、导出历史接口和下载接口，前端已有 CSV/JSON/JSONL 导出交互。
8. 集成测试已覆盖 Dataset 导出确认、导出文件写入、导出历史、下载和 CSV 内容验证。
9. `SiteAnalysis` 与 `ExtractionPlan` 已升级为可保存、可查询、可复制版本的正式资产。
10. 清洗计划已升级为可保存、可试跑、可追踪到数据集版本的正式草案资产。
11. 首批 Platform Package 已覆盖 `shopify-independent-ecommerce` 与 `github-api-first`；前者可执行，后者仍是 SOP/import-only。
12. P0 生产部署 commit 为 `db6189faea4cf4b400d711162f43bdf928d5e938`，真实 Chrome + browser-harness 已验证 `/automation` 主链路。

### 2.2 文档与实现不一致

1. 稳定 PRD 仍以 GitHub Repo、GitHub Topic、Generic Web、Manual JSON 为 MVP Collector 叙述主轴，需要继续向自动化采集工作台叙事迁移。
2. 架构和 API 文档已开始同步 Automation、Dataset Export、Platform Package、采集计划、清洗计划和生产验收事实；后续需要防止再次漂移。
3. Phase 1 草案中的“Dataset 记录级导出未完成”已经过期，当前实现中已存在导出模型、服务、路由和前端入口。
4. 仍需把 GitHub/API-first、marketplace、social 等平台包从 SOP/导入说明推进到可验收的采集闭环或明确的授权导入闭环。

## 3. 产品定位重述

系统的目标用户不是只看工具清单的人，而是需要完成真实采集任务的运营、数据、增长、市场和技术人员。

产品应解决的具体问题：

1. 不知道某个平台能不能采集。
2. 不知道该用 API、静态解析、浏览器自动化、RPA、第三方工具还是人工导入。
3. 不知道页面里哪些字段稳定、哪些字段脆弱。
4. 不知道采集后的数据如何清洗成可复用结构。
5. 不知道采集任务是否仍然稳定、字段是否漂移、数据是否缺失。
6. 不知道如何把采集结果交付给培训、分析、报告或下游系统。

## 4. P0 状态与剩余缺口

P0 的目标是让自动化采集工作台从“页面骨架”变成可验收闭环。当前状态是：核心 P0 已完成第一轮实现、部署和验收，但仍有可运营化增强项。

### 4.1 采集计划资产

当前状态：

1. `site_analyses` 与 `extraction_plans` 已落库。
2. 分析 URL 后可以保存历史分析，并创建默认采集计划版本。
3. 前端 `/automation` 已接入项目归档选择、历史分析列表和采集计划保存状态。

剩余缺口：

1. 字段候选的稳定性评分仍需要更多真实平台样本校准。
2. 采集计划复制后的差异对比还不够强。
3. 平台包与采集计划之间的版本依赖需要更明确。

### 4.2 清洗计划资产

当前状态：

1. `cleaning_plans` 已落库。
2. 清洗规则可先对样本行试跑，再保存为可复用草案。
3. 数据集版本可追踪 `cleaning_plan_id`。
4. 前端已接入默认规则、试跑、保存清洗计划和绑定保存数据集。

剩余缺口：

1. 清洗规则编辑器还停留在基础规则层，需要增强字段类型、主键、默认值、格式化和去重体验。
2. before/after 对比可读性仍可提升。
3. AI 清洗脚本只能作为草案，后续必须继续保持试跑和人工确认边界。

### 4.3 平台包模板

当前状态：

1. 已定义 PlatformPackage contract。
2. 首批平台包包含 `shopify-independent-ecommerce` 和 `github-api-first`。
3. Shopify/独立站包可执行，并能进入当前 Automation 主链路。
4. GitHub/API-first 包目前是 SOP/import-only，用于工具情报场景的下一轮深化。

剩余缺口：

1. 平台包还不是用户可自定义、可版本化的持久化资产。
2. GitHub/API-first 需要从 SOP/import-only 推进到可运行采集链路。
3. marketplace 和 social 平台必须先定义官方 API、授权导出或人工导入路径，不默认做登录态抓取。

### 4.4 调度、告警与重复动作保护

当前状态：

1. 漂移快照已增加 fingerprint 复用。
2. 漂移告警规则已按项目、条件、渠道和启用状态复用既有规则。
3. 采集失败日志已增加标准化 `failure_reason`。

剩余缺口：

1. 前端提交中禁用状态和重复点击反馈仍需统一。
2. 采集任务运行锁、重试预算和超时策略仍需继续增强。
3. 失败状态需要在 UI 中输出更明确的下一步建议。

## 5. P1 Gap

P1 是 P0 稳定后推进的平台能力。

### 5.1 Shopify / 独立站平台包深化

范围：

1. 商品详情页。
2. collection/listing 页面。
3. sitemap 批量发现。
4. JSON-LD、Open Graph、meta、HTML 文本多来源字段提取。
5. 价格、货币、库存、SKU、图片、品牌、描述、变体字段。

验收：

1. 授权测试站点能完成发现、fan-out、批量运行、Dataset 保存、导出。
2. 字段缺失、价格变化、商品新增/下架能触发漂移检查。

### 5.2 GitHub / API-first 平台包

范围：

1. GitHub repo、topic、release、stars、issues、README。
2. 工具情报监控作为第一个 API-first 平台包。
3. 将工具雷达里的 Browser AI、RPA、crawler、agent 项目转成可追踪实体。

验收：

1. 可监控指定 topic 或 repo 列表。
2. 可生成工具情报 Dataset。
3. 可把工具推荐结果回流到采集策略推荐层。

### 5.3 Marketplace 平台包边界

Amazon、Temu、Shopee、Lazada 等平台先走边界优先策略：

1. 官方 API 或授权导出优先。
2. 人工导入作为可用路径。
3. 页面抓取默认不作为第一实现。
4. 字段模型先行：ASIN/SKU、价格、排名、评论数、评分、库存、类目。

验收：

1. 至少完成一个 marketplace import/API-first demo。
2. UI 明确标识合规边界和采集限制。

### 5.4 社媒平台包边界

YouTube、Reddit 等优先官方 API 或公开数据；TikTok、Instagram、X、小红书等先做 SOP、字段模型和导入路径。

验收：

1. 不实现绕过登录、反检测或风控规避。
2. 可展示字段 schema、采集路径选择和人工导入模板。

## 6. P2 Gap

P2 是平台稳定后的增强能力。

1. AI 清洗脚本 Copilot：生成 Python/JS 清洗草案，必须 sandbox dry-run。
2. 对象存储抽象：当前导出文件可先保留本地 volume，后续扩展 COS/S3。
3. 采集质量评分：完整率、字段稳定性、漂移率、失败率、维护成本。
4. 多 workspace / 多租户隔离。
5. 更完整的报告模板：平台日报、竞品周报、工具雷达周报。

## 7. 推荐执行顺序

### Phase A：状态同步和术语治理

目标：消除 PRD、架构、API Contract 和实现状态的偏差，并把页面文案从内部技术名词切回业务动作。

任务：

1. 更新稳定架构文档，加入 P0 生产验收状态。
2. 更新 API Contract，区分技术合同名和用户页面文案。
3. 更新 Phase 1 草案和 P0 backlog，把已完成能力从待办中移除。
4. 盘点 UI 中仍残留的 `AlertRule`、`TaskRun`、`DriftEvent`、`Signal/AlertEvent` 等内部名词，形成下一轮页面文案清理项。

验收：

1. 文档不再把已完成事项列为未完成。
2. 每个 P0 项都能映射到后端、前端、测试和生产验收。

### Phase B：GitHub/API-first 可执行平台包

目标：把工具情报监控从 SOP/import-only 推进为可运行采集链路，服务“当下采集工具、agent、skill、crawler、RPA 项目”情报库。

任务：

1. 将 `github-api-first` 平台包升级为 executable。
2. 定义 repo、topic、release、README、issue activity 等字段 schema。
3. 建立工具实体标准：名称、安装方式、适用平台、采集方式、维护活跃度、风险边界、SOP 链接。
4. 接入 Dataset 保存、导出、漂移检查和报告。

验收：

1. 可输入 GitHub topic 或 repo 列表生成工具情报数据集。
2. 数据集能进入导出、漂移和报告链路。
3. 页面能说明每个工具适用场景和不适用场景。

### Phase C：浏览器结构解析预检

目标：把 browser-harness 的真实浏览器能力用于只读结构诊断，帮助判断目标站点适合 API、静态解析、浏览器自动化、RPA 还是人工导入。

任务：

1. 设计只读页面能力探测：渲染方式、关键字段来源、分页方式、登录态需求、反爬风险信号。
2. 将探测结果写入站点分析或采集计划建议。
3. UI 展示“推荐采集路径”和“不建议自动采集原因”。
4. 明确不实现登录绕过、反检测或风控规避。

验收：

1. 对授权公开页面能输出结构诊断和策略建议。
2. 对风险页面只输出边界说明，不进入默认自动采集。

### Phase D：独立站电商平台包深化

目标：把当前 Shopify/独立站包从 demo 闭环提升为可培训、可复用的采集模板。

任务：

1. 强化 collection、listing、sitemap 的发现质量。
2. 扩展字段：变体、SKU、库存、图片、品牌、价格历史、类目。
3. 增加字段缺失、价格变化、新增/下架的漂移示例。
4. 补齐培训 SOP：从 URL 到 Dataset 导出全流程。

验收：

1. 授权测试站点能完成发现、fan-out、批量运行、数据集保存和导出。
2. 至少一条漂移样例可用于培训演示。

### Phase E：marketplace 与 social 的边界型平台包

目标：先把高风险平台做成合规边界、字段模型和授权导入路径，避免误导用户以为可以默认页面抓取。

任务：

1. Amazon、Temu、Shopee、Lazada：优先官方 API、授权导出和人工导入模板。
2. YouTube、Reddit：优先官方 API 或公开数据。
3. TikTok、Instagram、X、小红书：先做 SOP、字段模型和导入模板。
4. UI 明确标识“可自动采集 / API 优先 / 仅导入 / 暂不支持”的策略等级。

验收：

1. 至少完成一个 marketplace import/API-first demo。
2. 至少完成一个 social API/import demo。
3. 高风险平台不会默认进入自动采集执行链路。

## 8. 验收策略

每个 Phase 都按以下证据层级验收：

1. 本地单元测试。
2. API 集成测试。
3. 前端交互测试。
4. 本地 E2E。
5. 生产 smoke。
6. 生产真实浏览器 E2E。
7. E2E 数据清理 dry-run。
8. E2E 数据清理 execute。
9. 清理后 dry-run 为零残留。

必须明确区分：

1. `docs-only`：只更新文档，不代表生产变化。
2. `local smoke`：本地服务通过，不代表生产可用。
3. `production read-only`：只读生产验证，不代表有生产写入。
4. `authorized production E2E`：经过授权的生产写入测试，必须清理。

## 9. 下一步执行建议

当前轮次执行 Phase A 的文档和状态同步。

Phase A 完成后的下一轮建议：

1. 先清理 `/automation`、`/datasets`、漂移和告警相关页面中剩余的内部技术名词。
2. 再进入 Phase B：GitHub/API-first 可执行平台包。
3. 之后进入 Phase C：browser-harness 支撑的浏览器结构解析预检。
4. 每一轮都按“实现一轮、测试一轮、验收一轮、生产边界说明一轮”闭环。

## 10. 不确定项

以下事项需要在进入对应 Phase 前再核验：

1. Dataset Export 在生产容器中的文件持久化目录和备份策略。
2. GitHub/API-first 是否优先从 topic 监控、repo 列表导入，还是 release/README 解析开始。
3. browser-harness 结构解析预检是否仅做本地/生产 E2E 工具，还是进入后端服务能力。
4. marketplace 和 social 平台采集的授权边界和数据来源。
5. 是否在 P2 前提前引入 COS/S3，还是继续使用本地 volume。

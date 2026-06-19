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

优先级判断：先补齐“采集计划和清洗计划的一等模型化”，再扩展平台包。原因是如果 ExtractionPlan 和 CleaningPlan 不能保存、复用、版本化，后续每增加一个平台都会堆成一次性流程，无法稳定运营。

## 2. 事实基线

以下为 2026-06-19 本地代码和文档检查得到的事实。

### 2.1 已完成或基本完成

1. 核心情报链路已经建立：`RawRecord -> EntitySnapshot -> Signal -> Intelligence -> Evidence -> Report / Alert`。
2. API 已挂载 `/api/automation` 自动采集路由。
3. 已存在 `ecommerce_product_page` 和 `ecommerce_product_discovery` collector。
4. `/automation` 工作台已覆盖站点分析、商品发现、fan-out、批量运行、Dataset 预览、保存、调度审批、漂移检查等流程。
5. `/datasets` 资产台已覆盖 Dataset、DatasetVersion、漂移历史和导出入口。
6. 数据模型已存在 `datasets`、`dataset_versions`、`dataset_drift_events`、`dataset_export_jobs`。
7. Dataset 导出已经不是空白项：后端已有 `product-dataset-exports` 创建接口、导出历史接口和下载接口，前端已有 CSV/JSON/JSONL 导出交互。
8. 集成测试已覆盖 Dataset 导出确认、导出文件写入、导出历史、下载和 CSV 内容验证。

### 2.2 文档与实现不一致

1. 稳定 PRD 仍以 GitHub Repo、GitHub Topic、Generic Web、Manual JSON 为 MVP Collector 叙述主轴，未完整反映自动采集工作台和电商平台包进展。
2. 架构文档仍偏“数据情报平台”视角，缺少 Automation、Dataset Export、Platform Package、ExtractionPlan、CleaningPlan 的最新架构位置。
3. API Contract 未完整同步当前 `/api/automation`、Dataset、导出、漂移和告警链路。
4. Phase 1 草案中的“Dataset 记录级导出未完成”已经过期，当前实现中已存在导出模型、服务、路由和前端入口。

## 3. 产品定位重述

系统的目标用户不是只看工具清单的人，而是需要完成真实采集任务的运营、数据、增长、市场和技术人员。

产品应解决的具体问题：

1. 不知道某个平台能不能采集。
2. 不知道该用 API、静态解析、浏览器自动化、RPA、第三方工具还是人工导入。
3. 不知道页面里哪些字段稳定、哪些字段脆弱。
4. 不知道采集后的数据如何清洗成可复用结构。
5. 不知道采集任务是否仍然稳定、字段是否漂移、数据是否缺失。
6. 不知道如何把采集结果交付给培训、分析、报告或下游系统。

## 4. P0 Gap

P0 是下一阶段必须先闭环的缺口。

### 4.1 ExtractionPlan 未一等模型化

当前自动化流程可以生成采集建议，但计划主要仍以 API response、Source config 和前端状态承载。

需要补齐：

1. `site_analyses`：保存 URL、平台画像、页面类型、授权确认、分析结果、风险边界。
2. `field_candidates`：保存字段候选、来源选择器、置信度、样例值、稳定性评分。
3. `extraction_plans`：保存字段选择、采集策略、collector 类型、执行参数、计划状态。
4. 计划版本：每次字段或策略调整都应能回溯。

验收标准：

1. 用户分析 URL 后，刷新页面仍能看到历史分析。
2. 用户可以从历史分析创建或复制采集计划。
3. 同一个 URL 可以有多个计划版本。
4. 计划能明确输出将使用的 collector、字段、频率和边界说明。

### 4.2 CleaningPlan 未一等模型化

当前 DatasetVersion 已保存 `selected_fields` 和 `cleaning_script`，但清洗规则还没有成为可复用资产。

需要补齐：

1. `cleaning_plans`：字段标准化、类型转换、默认值、去重主键、异常值规则。
2. dry-run：清洗规则必须先在样本行上预览。
3. 版本管理：清洗规则变更要能追踪。
4. 应用范围：可绑定 ExtractionPlan、Dataset 或平台包。

验收标准：

1. 用户可编辑字段类型、主键和基础清洗规则。
2. dry-run 能展示清洗前后对比。
3. 清洗规则确认后才允许保存为正式 DatasetVersion。
4. AI 只能生成草案，不允许直接写入正式规则。

### 4.3 平台包模板不完整

当前 Shopify-style 商品页和发现流程已经打通，但平台包还没有产品化成可复制模板。

需要补齐：

1. 平台包元数据：平台类型、可采集对象、字段 schema、推荐策略、风险等级。
2. 平台包 SOP：安装、授权、采集步骤、失败处理、导出方式。
3. 平台包验收 fixture：每个平台必须有稳定 fixture 和真实授权样例。
4. 平台包策略推荐：API 优先、静态解析、浏览器自动化、RPA、第三方工具、人工导入。

验收标准：

1. 平台包页面能说明适用场景和不适用场景。
2. 每个平台包至少包含一个从输入到 Dataset 导出的可演示闭环。
3. 风险平台不能默认进入自动采集，只能进入 SOP、导入或授权 API 路线。

### 4.4 调度与重复动作保护需要硬化

需要补齐：

1. 重复点击保护。
2. AlertRule 去重。
3. 任务锁和重复运行保护。
4. 运行预算、超时、重试次数和失败原因标准化。
5. 采集任务与导出任务的状态可解释。

验收标准：

1. 前端重复点击不会创建重复规则或重复任务。
2. 同一 dataset、同一阈值规则不会重复创建。
3. 任务失败后能在 UI 看到原因和下一步建议。
4. E2E 覆盖重复点击、失败重试和刷新恢复。

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

### Phase A：文档和状态同步

目标：消除 PRD、架构、API Contract 和实现状态的偏差。

任务：

1. 更新稳定架构文档，加入 Automation、Dataset Export、Platform Package。
2. 更新 API Contract，补齐 `/api/automation` 当前路由。
3. 更新 Phase 1 草案，把已完成的 Dataset Export 标为完成。
4. 生成 P0/P1/P2 backlog 对应实现文件和验收证据。

验收：

1. 文档不再把已完成事项列为未完成。
2. 每个 P0 项都能映射到后端、前端、测试和生产验收。

### Phase B：ExtractionPlan 持久化

目标：让采集计划成为可回看的资产。

任务：

1. 新增模型、schema、repository、migration。
2. 新增分析历史列表和详情接口。
3. 前端 `/automation` 增加历史分析和复制计划入口。
4. E2E 覆盖分析、保存、刷新恢复、复制计划。

验收：

1. 页面刷新不丢失 site analysis。
2. 用户能从历史分析创建采集任务。

### Phase C：CleaningPlan 持久化和 dry-run

目标：让清洗规则从 DatasetVersion 的附属字段升级为可复用资产。

任务：

1. 新增 CleaningPlan 模型。
2. 支持字段类型、主键、默认值、格式化、去重规则。
3. 新增 dry-run API 和前端对比视图。
4. Dataset 保存时绑定 CleaningPlan 版本。

验收：

1. 清洗规则可保存、复制、版本化。
2. DatasetVersion 能明确追踪来自哪个 CleaningPlan。

### Phase D：平台包模板化

目标：把 Shopify-style 成果沉淀成可复制的平台包系统。

任务：

1. 定义 PlatformPackage contract。
2. 将 Shopify/独立站包迁移到模板。
3. 平台包页面展示字段、策略、SOP、风险边界和演示入口。
4. 添加 GitHub/API-first 平台包。

验收：

1. 平台包不是静态介绍页，而是能启动实际采集流程。
2. 每个平台包都有 SOP 和 E2E fixture。

### Phase E：调度和告警可靠性

目标：让长期运行稳定。

任务：

1. 任务锁和重复运行保护。
2. AlertRule 幂等创建。
3. 重复点击保护。
4. 失败状态和 UI 修复建议。

验收：

1. 重复点击不会产生重复任务、重复规则或重复事件。
2. 失败任务有可解释状态和下一步动作。

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

立即执行 Phase A。

具体顺序：

1. 更新 `docs/architecture/architecture-data-intelligence-hub-stable.md`。
2. 更新 `docs/api/api-contract-data-intelligence-hub-stable.md`。
3. 更新 `drafts/analysis/analysis-automation-platform-phase1-refactor-draft-20260617.md` 的过期 gap。
4. 建立 P0 backlog 文件，绑定代码路径和验收方式。
5. 运行文档级检查和相关 API 测试，确认没有把已完成能力误列为未完成。

Phase A 完成后进入 Phase B：ExtractionPlan 持久化。

## 10. 不确定项

以下事项需要在进入对应 Phase 前再核验：

1. 生产环境当前部署 SHA 是否已包含 Dataset Export 运行时代码。
2. Dataset Export 在生产容器中的文件持久化目录和备份策略。
3. 下一个非 Shopify 平台包的业务优先级。
4. 社媒平台采集的授权边界和数据来源。
5. 是否在 P2 前提前引入 COS/S3，还是继续使用本地 volume。

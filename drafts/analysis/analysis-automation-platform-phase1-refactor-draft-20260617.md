---
title: 自动化数据采集平台 Phase 1 重构草案
doc_type: analysis
module: automation
topic: data-collection-automation-platform-phase1
status: draft
created: 2026-06-17
updated: 2026-06-19
owner: self
source: human+ai
---

# 自动化数据采集平台 Phase 1 重构草案

## 1. 产品定位修正

当前项目要从“培训型数据采集情报工作台”切换为“自动化数据采集工作台”。

核心目标不是展示工具，而是帮助用户完成真实采集任务：

```text
识别网站结构
-> 筛选目标字段
-> 选择采集工具和执行策略
-> 生成清洗规则
-> 结构化保存数据
-> 定时运行和质量监控
```

采集工具监控保留，但降级为辅助能力。它的作用是根据目标网站结构、渲染方式、字段类型、合规风险和维护成本，推荐合适的采集策略，而不是作为主产品入口。

## 2. Phase 1 平台包

Phase 1 选择“独立站 / Shopify-style 商品页”作为第一平台包。

原因：

1. 页面结构比社媒平台稳定。
2. 常见商品字段清晰：标题、价格、货币、图片、SKU、库存状态、品牌、描述。
3. 可以从公开 HTML、JSON-LD、Open Graph 和商品 meta 中提取字段。
4. 合规风险低于登录态社媒和 marketplace 高频抓取。
5. 能完整验证“URL 输入 -> 结构解析 -> 字段候选 -> 工具推荐 -> 清洗规则 -> 结构化入库”闭环。

## 3. 新对象模型

Phase 1 先以 API response 和 Source config 承载新对象，不立即做数据库大迁移。

| 对象 | Phase 1 形态 | 后续形态 |
|---|---|---|
| PlatformProfile | API response | 独立表 |
| SiteAnalysis | API response | 独立表，记录分析历史 |
| FieldCandidate | API response | FieldSchema 表 |
| ExtractionPlan | API response + Source config | ExtractionPlan 表 |
| CleaningPlan | API response + Source config | CleaningPipeline 表 |
| Dataset | 已实现 `datasets` / `dataset_versions` / `dataset_export_jobs` | 后续拆 DatasetRecord，并补对象存储抽象 |
| QualityIssue | 已通过 `dataset_drift_events` 承载漂移快照 | 后续拆 QualityIssue / Incident |

## 4. Phase 1 后端能力

新增 `ecommerce_product_page` collector：

1. 接受公开商品页 URL。
2. 复用现有公开 URL 安全校验，阻断内网和 localhost。
3. 解析 JSON-LD Product、Open Graph 和商品 meta。
4. 输出 `record_type=ecommerce_product_page`。
5. 内容包含 `extracted_fields`、`field_schema`、`platform_profile`、`cleaning_plan`、`html_title`、`text_sample`。
6. Normalization 将其转为 `product` entity，price 等数值进入 metrics。

新增 `/api/automation/site-analysis`：

1. 用户必须确认授权。
2. 返回平台画像。
3. 返回页面结构。
4. 返回字段候选。
5. 返回工具推荐。
6. 返回清洗规则草案。
7. 返回可用于创建 Source 的 collector config。

## 5. Phase 1 前端能力

新增 `/automation` 页面：

1. 输入 URL。
2. 勾选授权确认。
3. 点击分析。
4. 查看平台识别、页面类型、字段候选、推荐工具、清洗规则。
5. 明确显示是否可进入自动采集。

该页面是新产品主入口，不属于 `/toolkit`。

## 6. 验收标准

1. 商品页 fixture 能识别为 ecommerce product page。
2. 至少能提取标题、价格、货币、图片或描述中的多个字段。
3. 推荐工具能区分静态解析和浏览器采集。
4. collector 运行后能写入 RawRecord。
5. normalization 能生成 `product` entity snapshot。
6. 前端页面能完整展示分析结果。
7. 不引入登录态、反检测、绕过风控能力。

## 7. 下一平台候选

Phase 1 通过后，下一平台按以下顺序推进：

1. Shopify collection/listing page。
2. 独立站 sitemap + 商品详情批量发现。
3. Amazon marketplace，先做合规边界和人工导入，不直接自动抓取。
4. YouTube / Reddit，优先官方 API 或公开结构。
5. 小红书 / TikTok / Instagram / X，单独做登录态和平台政策决策。

## 8. 2026-06-18 至 2026-06-19 执行结果

Phase 1 已从草案推进到生产可验收闭环：

1. 新增 `ecommerce_product_page` 和 `ecommerce_product_discovery` collectors。
2. 新增 `/automation` 工作台，覆盖站点解析、商品发现、fan-out 创建、小批量运行、Dataset 预览、保存、调度审批、漂移检查。
3. 新增 `/datasets` 资产台，展示 DatasetVersion、字段与清洗规则、漂移历史和漂移告警策略。
4. 新增数据集、数据集版本、漂移事件、导出任务、站点分析、采集计划和清洗计划相关表，生产 schema 已升级到 `202606110020`。
5. 告警链路已覆盖站内通知和邮件告警；生产 E2E 使用一次性账号验证后已清理。
6. cleanup 工具已补齐新数据集表，避免真实 E2E fixture 残留。
7. 首批 Platform Package 已覆盖 Shopify/独立站和 GitHub/API-first；前者可执行，后者仍是 SOP/import-only。
8. P0 生产部署 commit 为 `db6189faea4cf4b400d711162f43bdf928d5e938`，真实 Chrome + browser-harness 已验证 `/automation` 主链路。

仍未完成：

1. 真实平台包还没有扩展到 Amazon、Temu、Shopee、Lazada、YouTube、Reddit 等 marketplace/social 平台的 API 或授权导入闭环。
2. GitHub/API-first 仍是 SOP/import-only，不代表已经进入 Automation 一键采集链路。
3. 平台包还不是用户可自定义、可版本化的持久化资产。
4. Dataset 导出已具备文件写出、下载和审计记录，但生产持久化目录、备份策略和 COS/S3 对象存储抽象仍未闭环。
5. 采集任务运行锁、重试预算、超时策略和前端提交中状态仍需继续增强。

## 9. 2026-06-19 P0 收口记录

本地仓库检查和生产验收记录确认，Phase 1 的 P0 骨架已完成：

1. Dataset Export 已实现：后端有 `DatasetExportJob` 模型，接口支持 `csv`、`json`、`jsonl`，前端 `/datasets` 已提供生成和下载入口。
2. 采集计划已实现：`SiteAnalysis` 与 `ExtractionPlan` 可保存、查询和复制版本。
3. 清洗计划已实现：规则可试跑、保存，并可被数据集版本追踪。
4. Platform Package 初版已实现：Shopify/独立站可执行，GitHub/API-first 作为下一轮 executable 候选。
5. 重复动作基础保护已实现：漂移快照和漂移告警规则具备复用逻辑，采集失败日志具备标准化原因。

下一阶段不再继续补 P0 骨架，调整为：

1. 清理 UI 中剩余内部技术名词，让培训和业务用户能直接理解。
2. 将 GitHub/API-first 平台包升级为可执行采集链路。
3. 引入 browser-harness 支撑的只读结构解析预检。
4. 深化独立站电商包，并为 marketplace/social 建立 API/import-first 边界包。

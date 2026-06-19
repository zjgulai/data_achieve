---
title: Data Intelligence Hub API 合同
doc_type: api
module: api
topic: data-intelligence-hub
status: stable
created: 2026-06-14
updated: 2026-06-19
owner: self
source: human+ai
---

# Data Intelligence Hub API 合同

## 基础规则

Base URL：

| 环境 | URL |
|---|---|
| 本地 API | `http://localhost:8000` |
| 生产 API | `https://scrapy.lute-tlz-dddd.top` |

通用规则：

1. 所有业务接口以 `/api` 开头。
2. 认证使用 HttpOnly cookie `access_token`。
3. 登录、注册以外的业务接口都要求当前用户和当前 workspace。
4. 早期资源列表接口多返回 JSON array；Automation 与 Dataset 类接口返回带 `items`、`total` 和状态标记的 response object。
5. 创建接口成功通常返回 `200` 或 `201`，以实际 route 声明为准。
6. 未认证返回 `401`，无权限或跨 workspace 资源不可见。
7. 生产环境 cookie 必须启用 secure。
8. 本文件是技术合同，endpoint、schema 和 response model 名称保留英文；面向用户页面应使用“采集任务、数据集版本、清洗计划、试跑”等中文业务文案。

## Auth

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/auth/register` | `email`、`password`、`name` | `AuthSessionResponse` | 创建用户、workspace、owner membership，并设置 cookie |
| `POST` | `/api/auth/login` | `email`、`password` | `AuthSessionResponse` | 设置 cookie |
| `POST` | `/api/auth/logout` | 无 | `204` | 清除 cookie |
| `GET` | `/api/auth/me` | 无 | `AuthSessionResponse` | 返回当前用户与 workspace |

## Health

| 方法 | 路径 | 响应 | 说明 |
|---|---|---|---|
| `GET` | `/api/health` | `service`、`environment`、`status`、`database`、`scheduler_enabled` | 生产健康检查入口 |

## Project

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/projects` | query: `domain`、`status` | `ProjectResponse[]` |
| `POST` | `/api/projects` | `name`、`description?`、`domain` | `ProjectResponse` |
| `GET` | `/api/projects/{project_id}` | 无 | `ProjectResponse` |
| `PATCH` | `/api/projects/{project_id}` | `name?`、`description?`、`domain?`、`status?` | `ProjectResponse` |
| `DELETE` | `/api/projects/{project_id}` | 无 | `ProjectResponse` |

允许的 `domain`：

```text
osint, ecommerce, social, competitor, mixed
```

## Collector And Source

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/collectors` | 无 | `CollectorResponse[]` |
| `GET` | `/api/sources` | query: `project_id`、`type`、`enabled` | `SourceResponse[]` |
| `POST` | `/api/sources` | `project_id`、`name`、`type`、`url?`、`config`、`schedule_cron?` | `SourceResponse` |
| `GET` | `/api/sources/{source_id}` | 无 | `SourceResponse` |
| `PATCH` | `/api/sources/{source_id}` | source 可编辑字段 | `SourceResponse` |
| `POST` | `/api/sources/{source_id}/test` | 无 | `SourceTestResponse` |
| `POST` | `/api/sources/{source_id}/enable` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/sources/{source_id}/disable` | 无 | `SourceResponse` |

稳定 collector：

| type | 必填 config | 用途 |
|---|---|---|
| `github_repo` | `owner`、`repo` | GitHub 仓库指标 |
| `github_topic` | `topic` | GitHub topic 趋势 |
| `generic_web` | `url` | 公开网页快照 |
| `manual_json` | `entity_type`、`json_data` | 人工或外部工具导入结构化样本 |
| `ecommerce_product_discovery` | `url` | 从公开独立站 listing、collection 或 sitemap 发现商品 URL |
| `ecommerce_product_page` | `url` | 从公开独立站商品页解析商品字段 |

## Automation

所有 Automation 接口都要求登录态。写入、运行、导出、发送通知类动作必须在请求体中显式传入 `authorized=true`；部分动作还要求 `confirm_create=true` 或 `confirm_send=true`。

### Site Analysis And Product Discovery

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/site-analysis` | `url`、`authorized`、`target=ecommerce_product`、`fields?` | `AutomationSiteAnalysisResponse` | 分析公开商品页，返回平台画像、页面结构、字段候选、工具推荐、清洗草案和 source draft |
| `POST` | `/api/automation/product-discovery` | `url`、`authorized`、`max_products?` | `AutomationProductDiscoveryResponse` | 从 listing、collection 或 sitemap 页面发现商品候选 URL |
| `POST` | `/api/automation/product-fanout-preview` | `parent_url`、`authorized`、`candidates`、`fields?`、`max_sources?` | `AutomationProductFanoutPreviewResponse` | 预览候选商品 URL 是否可转成商品页 source |
| `POST` | `/api/automation/product-fanout-create` | `project_id`、`parent_url`、`authorized`、`candidates`、`fields?`、`max_sources?`、`enable_tasks?` | `AutomationProductFanoutCreateResponse` | 创建或复用商品页采集源，可同时启用采集任务 |

关键边界：

1. 这些接口不支持登录态抓取、风控绕过或反检测能力。
2. `product-fanout-preview` 只预览，不创建采集源或采集任务。
3. `product-fanout-create` 会写入采集源/任务，必须用于授权页面或测试 fixture。

### Batch Run And Dataset

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-batch-run` | `authorized`、`task_ids`、`max_tasks?` | `AutomationProductBatchRunResponse` | 对已审阅商品页采集任务执行小批量采集 |
| `POST` | `/api/automation/product-dataset-preview` | `authorized`、`task_run_ids`、`fields?`、`max_rows?` | `AutomationProductDatasetPreviewResponse` | 从采集运行结果聚合数据集预览和清洗草案 |
| `POST` | `/api/automation/cleaning-plan-dry-run` | `authorized`、`task_run_ids`、`fields?`、`rules`、`max_rows?` | `AutomationCleaningPlanDryRunResponse` | 对样本行执行清洗规则试跑，不保存数据集版本 |
| `POST` | `/api/automation/cleaning-plans` | 试跑请求 + `name` | `AutomationCleaningPlanCreateResponse` | 保存可复用清洗计划草案 |
| `GET` | `/api/automation/cleaning-plans` | query: `project_id?`、`limit?` | `AutomationCleaningPlanListResponse` | 列出清洗计划资产 |
| `POST` | `/api/automation/product-dataset-save` | `authorized`、`task_run_ids`、`fields?`、`max_rows?`、`name`、`description?`、`cleaning_plan_id?` | `AutomationProductDatasetSaveResponse` | 保存数据集版本，可追踪清洗计划 |
| `GET` | `/api/automation/product-datasets` | query: `project_id?`、`limit?` | `AutomationProductDatasetListResponse` | 列出商品数据集资产 |
| `GET` | `/api/automation/product-datasets/{dataset_id}/versions` | query: `limit?` | `AutomationProductDatasetVersionListResponse` | 列出数据集版本 |

数据集不变量：

1. 数据集版本必须保留 `source_task_run_ids`、`selected_fields`、`cleaning_script`、`rows`、`export_preview` 和 completeness 指标。
2. 清洗计划是独立草案资产，保存规则、脚本文案、试跑预览和版本号。
3. `cleaning-plan-dry-run` 必须返回 `dataset_version_created=false`、`cleaning_plan_created=false`、`run_started=false`。
4. 数据集版本可选追踪 `cleaning_plan_id`；不传该字段时保持原始预览保存行为。

### Dataset Export

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-dataset-exports` | `authorized`、`confirm_create`、`dataset_id`、`dataset_version_id`、`export_format` | `AutomationProductDatasetExportJobResponse` | 生成受控导出文件，格式支持 `csv`、`json`、`jsonl` |
| `GET` | `/api/automation/product-datasets/{dataset_id}/exports` | query: `dataset_version_id?`、`limit?` | `AutomationProductDatasetExportListResponse` | 查看导出历史 |
| `GET` | `/api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download` | 无 | 文件响应 | 下载导出文件 |

导出不变量：

1. 未传 `confirm_create=true` 时必须拒绝导出。
2. ExportJob 必须记录 `filename`、`content_type`、`artifact_size_bytes`、`row_count`、`checksum_sha256`、`audit_events`。
3. 下载接口必须限制 artifact 位于 `Settings.dataset_export_dir` 内，避免路径穿越。

### Schedule, Drift And Dataset Alerts

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-schedule-approve` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、调度策略字段 | `AutomationProductScheduleApproveResponse` | 审批数据集关联采集任务的后续刷新策略 |
| `POST` | `/api/automation/product-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、阈值字段 | `AutomationProductDriftCheckResponse` | 检查数据集版本与最新运行结果的字段漂移 |
| `POST` | `/api/automation/product-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 保存漂移快照 |
| `GET` | `/api/automation/product-drift-events` | query: `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出漂移事件 |
| `POST` | `/api/automation/product-drift-alert-preview` | `authorized`、`dataset_id`、`dataset_version_id?`、`min_status?`、`channel?` | `AutomationProductDriftAlertPreviewResponse` | 预览漂移告警规则 |
| `POST` | `/api/automation/product-drift-alert-rules` | preview request + `confirm_create` | `AutomationProductDriftAlertRuleCreateResponse` | 创建漂移告警规则 |
| `POST` | `/api/automation/product-drift-alert-events` | `authorized`、`confirm_create`、`dataset_id`、`dataset_version_id`、`drift_event_id` | `AutomationProductDriftAlertEventCreateResponse` | 从漂移事件创建 Signal 和 AlertEvent |
| `POST` | `/api/automation/product-drift-alert-notifications` | `authorized`、`confirm_send`、`dataset_id`、`dataset_version_id`、`drift_event_id`、`alert_event_ids` | `AutomationProductDriftAlertNotificationSendResponse` | 发送站内通知 |
| `POST` | `/api/automation/product-drift-alert-emails` | notification request + `recipient_email?` | `AutomationProductDriftAlertEmailSendResponse` | 发送邮件告警 |

当前已硬化：

1. 漂移快照保存具备 fingerprint 复用，重复提交不会创建重复漂移事件。
2. 漂移告警规则按项目、条件、渠道和启用状态复用既有规则。
3. 采集运行失败日志已记录标准化 `failure_reason`。

仍需扩展：

1. 前端提交中状态和更完整的重复点击交互反馈。
2. 采集任务运行锁、重试预算和超时策略。

## Task And Run

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/tasks` | query: `project_id`、`status`、`collector_type` | `CollectionTaskResponse[]` |
| `GET` | `/api/tasks/{task_id}` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/tasks/{task_id}/run` | 无 | `TaskRunResponse` |
| `POST` | `/api/tasks/{task_id}/pause` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/tasks/{task_id}/resume` | 无 | `CollectionTaskResponse` |
| `GET` | `/api/tasks/{task_id}/runs` | 无 | `TaskRunResponse[]` |

运行语义：

1. `run` 会创建 TaskRun，并把采集、归一化、信号、情报链路串起。
2. 失败 run 必须记录 `error_message` 和 logs。
3. pause/resume 只改变 task 状态，不删除历史 run。

## Raw Record, Entity, Signal

| 方法 | 路径 | 响应 |
|---|---|---|
| `GET` | `/api/raw-records` | `RawRecordResponse[]` |
| `GET` | `/api/raw-records/{raw_record_id}` | `RawRecordResponse` |
| `GET` | `/api/entities` | `EntityResponse[]` |
| `GET` | `/api/entities/{entity_id}` | `EntityResponse` |
| `GET` | `/api/entities/{entity_id}/snapshots` | `EntitySnapshotResponse[]` |
| `GET` | `/api/entities/{entity_id}/signals` | `SignalResponse[]` |
| `GET` | `/api/signals` | `SignalResponse[]` |
| `GET` | `/api/signals/{signal_id}` | `SignalResponse` |
| `GET` | `/api/signals/{signal_id}/snapshot-compare` | `SignalSnapshotCompareResponse` |

不变量：

1. RawRecord 是原始事实。
2. EntitySnapshot 是状态快照。
3. Signal 是快照差异或异常，不是最终分析文本。

## Intelligence And Evidence

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/intelligence` | query: `project_id`、`type`、`status`、`domain`、`sort` | `IntelligenceResponse[]` |
| `GET` | `/api/intelligence/{intelligence_id}` | 无 | `IntelligenceResponse` |
| `PATCH` | `/api/intelligence/{intelligence_id}/status` | `status` | `IntelligenceResponse` |
| `GET` | `/api/intelligence/{intelligence_id}/evidences` | 无 | `EvidenceResponse[]` |
| `POST` | `/api/intelligence/{intelligence_id}/feedback` | `feedback_type`、`comment?` | `IntelligenceFeedbackResponse` |

证据要求：

1. 情报详情页必须能回溯 Evidence。
2. Evidence 应带出 Signal、Entity、RawRecord、TaskRun、Source 上下文。
3. LLM 或 mock LLM 输出只允许生成 `title` 和 `summary`。

## Report

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/reports` | query: `project_id`、`report_type` | `ReportResponse[]` |
| `POST` | `/api/reports/generate` | `project_id?`、`report_type`、`period_hours?` | `ReportResponse` |
| `GET` | `/api/reports/subscriptions` | 无 | `ReportSubscriptionResponse[]` |
| `POST` | `/api/reports/subscriptions` | 订阅配置 | `ReportSubscriptionResponse` |
| `POST` | `/api/reports/subscriptions/{subscription_id}/run` | 无 | `ReportSubscriptionResponse` |
| `GET` | `/api/reports/subscriptions/{subscription_id}/runs` | 无 | `ReportSubscriptionRunResponse[]` |
| `GET` | `/api/reports/{report_id}/evidence-references` | 无 | `ReportEvidenceReferenceResponse[]` |
| `GET` | `/api/reports/{report_id}/download.md` | 无 | Markdown 文件 |
| `GET` | `/api/reports/{report_id}/audit-events` | 无 | `ReportAuditEventResponse[]` |
| `POST` | `/api/reports/{report_id}/audit-events` | 审计事件 | `ReportAuditEventResponse` |
| `GET` | `/api/reports/{report_id}` | 无 | `ReportResponse` |
| `POST` | `/api/reports/{report_id}/send` | 无 | `ReportResponse` |

## Alert And Notification

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/alert-rules` | query: `enabled` | `AlertRuleResponse[]` |
| `POST` | `/api/alert-rules` | 规则配置 | `AlertRuleResponse` |
| `PATCH` | `/api/alert-rules/{rule_id}` | 规则可编辑字段 | `AlertRuleResponse` |
| `DELETE` | `/api/alert-rules/{rule_id}` | 无 | `AlertRuleResponse` |
| `GET` | `/api/alert-events` | query: `rule_id`、`status` | `AlertEventResponse[]` |
| `PATCH` | `/api/alert-events/{event_id}` | `status` | `AlertEventResponse` |
| `GET` | `/api/notifications` | query: `unread_only`、`type` | `NotificationResponse[]` |
| `GET` | `/api/notifications/email-channel` | 无 | `EmailChannelStatusResponse` |
| `POST` | `/api/notifications/email-channel/test` | 无 | `EmailChannelTestResponse` |
| `PATCH` | `/api/notifications/{notification_id}/read` | 无 | `NotificationResponse` |
| `POST` | `/api/notifications/read-all` | 无 | `NotificationReadAllResponse` |
| `POST` | `/api/notifications/read-bulk` | `notification_ids` | `NotificationReadAllResponse` |

通知规则：

1. report send 会进入通知链路。
2. alert match 会生成 alert event，并按 rule channel 生成站内通知。
3. email channel 必须通过环境变量配置，未配置时接口返回禁用状态。

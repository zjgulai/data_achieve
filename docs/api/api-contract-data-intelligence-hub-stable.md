---
title: Data Intelligence Hub API 合同
doc_type: api
module: api
topic: data-intelligence-hub
status: stable
created: 2026-06-14
updated: 2026-06-14
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
4. 列表接口当前返回 JSON array。
5. 创建接口成功通常返回 `201`。
6. 未认证返回 `401`，无权限或跨 workspace 资源不可见。
7. 生产环境 cookie 必须启用 secure。

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

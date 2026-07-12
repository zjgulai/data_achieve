---
title: Data Intelligence Hub API 合同
doc_type: api
module: api
topic: data-intelligence-hub
status: stable
created: 2026-06-14
updated: 2026-06-23
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
| `public_feed` | `url` | 公开 RSS/Atom feed 更新条目 |
| `manual_json` | `entity_type`、`json_data` | 人工或外部工具导入结构化样本 |
| `ecommerce_product_discovery` | `url` | 从公开独立站 listing、collection 或 sitemap 发现商品 URL |
| `ecommerce_product_page` | `url` | 从公开独立站商品页解析商品字段；优先 JSON-LD/Product，兼容静态 schema.org microdata `itemprop` 字段 |

`ecommerce_product_page` 默认字段合同：

| 字段 | 说明 |
|---|---|
| `title`、`price`、`currency`、`availability`、`sku`、`brand`、`description`、`image_url`、`canonical_url` | 基础商品字段 |
| `price_min`、`price_max` | 从多 offer / variant price 中计算价格区间 |
| `availability_detail` | 保留 offer / variant 级库存状态摘要 |
| `variant` | 商品变体名称或变体维度摘要 |
| `category` | 商品分类或分类层级 |

字段来源优先级：JSON-LD Product / Offer 仍是最高优先级；当真实静态测试站没有 JSON-LD 时，`ecommerce_product_page` 可从 schema.org microdata 的 `itemprop=name/price/priceCurrency/description/image` 中提取基础字段；站点级 `og:image` 不覆盖商品级 microdata image。

## Automation

所有 Automation 接口都要求登录态。写入、运行、导出、发送通知类动作必须在请求体中显式传入 `authorized=true`；部分动作还要求 `confirm_create=true` 或 `confirm_send=true`。

### Platform Package Contract

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `GET` | `/api/automation/platform-packages` | 无 | `AutomationPlatformPackageListResponse` | 返回当前平台包矩阵 |
| `GET` | `/api/automation/platform-packages/{package_id}` | path: `package_id` | `AutomationPlatformPackageResponse` | 返回单个平台包合同，未知 id 返回 `404` |

`AutomationPlatformPackageResponse` 除字段 contract、SOP 和策略矩阵外，还必须返回治理字段：

```text
version
owner
lifecycle_status
evidence_grade
authorization_required
acceptance_registry[]
cleanup_policy
forbidden_actions[]
```

当前平台包：

| id | version | execution boundary | evidence grade | default entrypoint | 说明 |
|---|---|---|---|---|---|
| `shopify-independent-ecommerce` | `2026.06.m4` | `executable` | `L2-fixture-or-dry-run` | `product-discovery` | 独立站/Shopify-style 商品采集，从集合页或商品页进入 Automation 主链路；本地 fixture 和公开测试站 local API E2E 已登记，production/customer-site gate 待授权 |
| `github-api-first` | `2026.06.m3` | `executable` | `L4-authorized-live` | `source-create` | GitHub topic 工具情报采集，使用官方 API 创建 Source、启用 Task 并运行一次；L4 仅代表已授权的小范围 package gate |
| `public-page-structure-preflight` | `2026.06.preflight` | `executable` | `L2-fixture-or-dry-run` | `preflight` | 授权公开网页结构预检，先输出 gate 和结构诊断，再决定是否创建 `generic_web` Source |
| `public-web-rss-docs` | `2026.06.m5` | `executable` | `L4-authorized-live` | `source-create` | 公开 RSS/Atom feed 与 docs/page hash 更新监控；L4 仅代表已完成的 scoped public-content gates 和 retained canary |

平台包不变量：

1. `execution_boundary=executable` 只表示可以从界面启动其声明的低风险路径，不代表绕过授权、rate limit 或平台政策。
2. GitHub/API-first 当前可执行路径是 `github_topic` Topic Radar；单仓库 `github_repo` 仍建议通过 Sources 创建重点仓库监控。
3. `public-page-structure-preflight` 使用 Toolkit preflight，不是 Source collector；只有用户确认后才可继续创建 `generic_web` Source。
4. `public-web-rss-docs` 本地链路已覆盖 RSS/Atom 与 docs/page snapshot 的 Dataset preview/save、content-hash drift、drift event save/list、report preview 和 Report asset；生产调度、provider/email、生产浏览器运行和新增生产写入仍需后续授权 gate。
5. `acceptance_registry[]` 是验收登记，不会自动升级平台状态；`L4-authorized-live` 仍必须按登记项的 scoped 范围理解。

### Capability Probe Contract

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `GET` | `/api/automation/capability-probes` | query: `platform_id?` | `AutomationCapabilityProbeListResponse` | 返回平台能力体检矩阵；只运行允许的本地 doctor/probe，不读取平台内容、不创建采集资源 |

`AutomationCapabilityProbeResponse` 最小字段：

```text
schema_version=capability_probe.v1
platform_id
platform_label
doctor_status
credential_mode
execution_boundary
risk_level
backend_candidates[]
agent_reach?
allowed_outputs[]
forbidden_actions[]
next_actions[]
run_started=false
collection_resources_written=false
evidence_asset
```

`AutomationCapabilityProbeListResponse.evidence_assets[]` 聚合每个 probe 的 `evidence_asset`。`evidence_asset.schema_version=evidence_asset_reference.v1`，`evidence_boundary=no_read_no_search_no_write`，只表示本次 doctor/catalog 结果可被报告或 Evidence 引用；它不表示平台读取、采集运行或写入已发生。

`AutomationAgentReachChannelProbeResponse` 最小字段：

```text
schema_version=agent_reach_channel_probe.v1
installed
command_path
doctor_status
active_backend
requires_login
requires_proxy
blocked_reason
platforms[]
read_invoked=false
search_invoked=false
raw_summary
```

能力探测不变量：

1. `agent-reach` 缺失时返回 `doctor_status=missing_tool`，不能伪装为平台可采集。
2. `agent-reach` 存在时只允许调用 `agent-reach doctor --json`；不得调用 read/search，不得自动安装工具。
3. `browser-harness` 能力只作为 read-only probe 候选，不得直接创建 Source/Task/TaskRun/Dataset。
4. `execution_boundary=sop_only` 或 `import_only` 的平台不得在 UI 中出现默认自动采集按钮。
5. 所有 response 必须保持 `run_started=false`、`collection_resources_written=false`，直到进入单独授权的采集写入链路。
6. CapabilityProbe evidence reference 必须保持 `credentials_captured=false`、`cookies_captured=false`、`headers_captured=false`、`bodies_captured=false`，且 `read_invoked=false`、`search_invoked=false`。

### Browser Diagnostic Evidence Contract

浏览器诊断 gate 与本地诊断运行都属于证据资产链路，不代表正式采集任务。

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/browser-diagnostic-jobs/{job_id}/production-metadata-run-gate` | `authorized`、`confirm_review`、`confirm_production_readonly`、`confirm_metadata_only`、`confirm_no_file_write`、`confirm_no_collection_write`、`target_environment=production`、`max_metadata_events?` | `AutomationBrowserProductionMetadataRunGateResponse` | 只生成生产 metadata-only 手工只读运行预检；`evidence_grade=L2-fixture-or-dry-run`，`run_started=false`、`browser_started=false`、`files_written=false`、`collection_resources_written=false`、`provider_called=false` |
| `POST` | `/api/automation/browser-diagnostic-jobs/{job_id}/local-run` | `authorized`、`confirm_execute`、`run_mode`、`confirm_real_browser_probe?`、`browser_harness_cdp_url?` | `AutomationBrowserLocalRunnerResultResponse` | 只读回放或本机 dedicated-CDP 临时 tab 探测；不创建 Source/Task/TaskRun/Dataset |
| `POST` | `/api/automation/browser-diagnostic-job-runs/{job_run_id}/promotion-preview` | `authorized`、`confirm_review`、`target_source_type`、`enable_task_preview?` | `AutomationBrowserPromotionPreviewResponse` | 只根据本地 run 生成 Source/Task 候选包和阻断原因；不创建 Source/Task/TaskRun/Dataset |
| `POST` | `/api/automation/browser-diagnostic-job-runs/{job_run_id}/promotion-execution-dry-run` | `authorized`、`confirm_review`、`confirm_no_write`、`target_source_type`、`source_name?`、`schedule_cron?` | `AutomationBrowserPromotionExecutionDryRunResponse` | 复用正式 collector config 校验生成执行前预检计划；强制 no-write，不创建 Source/Task/TaskRun/Dataset |
| `POST` | `/api/automation/browser-diagnostic-job-runs/{job_run_id}/promotion-execution` | `authorized`、`confirm_review`、`confirm_write`、`confirm_create_collection_resources`、`confirm_no_task_run`、`target_source_type`、`source_name?`、`schedule_cron?`、`confirm_schedule?`、`idempotency_key` | `AutomationBrowserPromotionExecutionResponse` | 显式授权后创建 Source+Task；强制不启动 TaskRun，不创建 Dataset；同一 idempotency key replay，同 URL/type 不同 key 阻断 |
| `GET` | `/api/automation/browser-diagnostic-job-runs` | query: `project_id?`、`diagnostic_job_id?` | `AutomationBrowserLocalRunnerResultListResponse` | 返回本地诊断运行历史和只读副作用汇总 |

`AutomationBrowserLocalRunnerResultResponse` 在兼容旧字段的基础上新增 M2 证据字段：

```text
selector_results[]
selector_evaluations[]
network_observation_summary
network_metadata_summary
promotion_gate
redaction_summary
evidence_asset
files_written=false
collection_resources_written=false
```

M2 字段约束：

1. `selector_evaluations[]` 是 `selector_results[]` 的规范化视图，包含 `field`、`selector_hint`、`match_count`、`sample_text`、`missing_reason` 和 `browser_started`。
2. `network_metadata_summary` 只允许保留 metadata：`capture_headers=false`、`capture_body=false`、`redacted=true`；URL 必须移除 query 和 fragment。
3. `promotion_gate.can_create_collection_resources=false`，并包含 `m2_read_only_contract_no_direct_promotion`；只有独立的 `promotion-execution` 写 gate 可在显式授权和 idempotency key 下接管 Source+Task 创建。
4. `redaction_summary` 必须显式声明 `cookies_captured=false`、`headers_captured=false`、`bodies_captured=false`、`query_parameters_retained=false`。
5. `run_mode=ephemeral_browser_harness_probe` 只有在提供 dedicated `browser_harness_cdp_url` 时才可进入 browser-harness；缺少该字段必须返回 `blocked_ephemeral_probe` / `browser_harness_isolated_cdp_required`，不得默认连接用户主 Chrome。
6. `run_mode=ephemeral_browser_harness_probe` 可以使 `browser_started=true`，但仍保持 `files_written=false` 和 `collection_resources_written=false`。
7. `AutomationBrowserDiagnosticRunResponse`、`AutomationBrowserDiagnosticJobResponse`、`AutomationBrowserLocalRunnerResultResponse` 及对应 list response 必须携带 `evidence_asset` / `evidence_assets[]`；这些引用只保存 metadata、ID、脱敏 URL 和边界声明，不内嵌 screenshot、trace、HAR、headers、body 或 cookie。
8. `promotion-preview` 必须保持 `can_promote=false`、`source_created=false`、`task_created=false`、`task_run_started=false`、`collection_resources_written=false`；`source_draft` 和 `task_draft` 只供人工复核，不能作为自动写入证据。
9. `promotion-execution-dry-run` 必须要求 `confirm_no_write=true`，并保持 `dry_run=true`、`write_allowed=false`、`can_execute=false`、`source_created=false`、`task_created=false`、`task_run_started=false`、`collection_resources_written=false`；即使 collector config 校验通过，也不能升级为正式执行证据。
10. `promotion-execution` 必须要求 `confirm_write=true`、`confirm_create_collection_resources=true`、`confirm_no_task_run=true` 和 `idempotency_key`；成功时只允许 `source_created=true`、`task_created=true`、`task_run_started=false`，并在 `BrowserDiagnosticJobRun.audit_events` 记录 `browser_promotion_execution_resources_created`、`idempotency_scope=browser_promotion_execution` 和 `idempotency_key_hash`。
11. `promotion-execution` 的重复提交规则：同一 `idempotency_key` 返回 `idempotency_replayed=true` 且不再写入；不同 key 命中同一 `target_source_type + url` 必须返回 `browser_promotion_target_source_already_exists`；缺少必填 selector、collector config invalid 或证据边界异常时必须返回 400。
12. `production-metadata-run-gate` 是 no-run L2 预检；必须保持 `production_read_only_observed=false`、`run_started=false`、`browser_started=false`、`execution_started=false`、`files_written=false`、`collection_resources_written=false`、`provider_called=false`、`source_created=false`、`task_created=false`、`task_run_started=false`、`dataset_created=false`，直到另起授权 L3/L4 gate。
13. Artifact retention 规则以 `docs/workflows/workflow-browser-evidence-artifact-retention-stable.md` 为准；PRD2 M2 当前阶段只允许 metadata 和 `tmp/` 本地验证 JSON。

### GitHub/API-first Topic Radar Flow

GitHub Topic Radar 当前复用既有 Source/Task/Run API，不新增专用写入接口：

| 步骤 | 接口 | 关键字段 | 说明 |
|---|---|---|---|
| 创建 Source | `POST /api/sources` | `type=github_topic`、`config.topic`、`config.max_results` | 创建公开 topic 采集源 |
| 启用 Task | `POST /api/sources/{source_id}/enable` | 无 | 创建或复用采集任务 |
| 执行采集 | `POST /api/tasks/{task_id}/run` | 无 | 调用 GitHub Search API，写入 TaskRun、RawRecord、Entity/Snapshot/Signal |

GitHub 工具数据集化：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/github-tool-dataset-preview` | `authorized`、`task_run_ids`、`fields?`、`max_rows?` | `AutomationProductDatasetPreviewResponse` | 从 GitHub topic/repo 运行记录生成工具情报数据集预览，不保存 DatasetVersion |
| `POST` | `/api/automation/github-tool-dataset-save` | preview request + `name`、`description?` | `AutomationProductDatasetSaveResponse` | 保存 `dataset_type=github_tool_radar` 的 DatasetVersion |

GitHub 工具数据集字段：

```text
repo_full_name, owner_login, owner_type, description, stars, forks, open_issues, watchers,
language, topics, license_spdx_id, default_branch, latest_release_tag,
latest_release_published_at, archived, fork, html_url, homepage, created_at, updated_at, pushed_at
```

字段来源边界：

1. `github_topic` 优先来自 GitHub Search API，可稳定获得仓库基础元数据、license、默认分支、公开 topic 和 freshness 字段；`latest_release_*` 对 topic 结果可能为空。
2. `github_repo` 额外读取 GitHub REST `releases/latest`；公开仓库无 release 时保留 `latest_release=null`，不阻断基础仓库采集。
3. 以上 endpoint 仍为 API-first/read-only 数据集化能力；预览不保存 DatasetVersion，报告生成不启动采集、不创建通知、不发送邮件。

GitHub 工具数据集导出复用 Dataset Export：

1. `POST /api/automation/product-dataset-exports`
2. `GET /api/automation/product-datasets/{dataset_id}/exports`
3. `GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download`

这些导出 endpoint 名称仍保留 `product` 历史命名，但底层按 Dataset/Version 权限和 `dataset_type` 工作；后续可再做无破坏的 alias。

### Public Web/RSS/Docs Content Dataset Flow

公开内容更新当前复用 Source/Task/Run API：

| 步骤 | 接口 | 关键字段 | 说明 |
|---|---|---|---|
| 创建 Source | `POST /api/sources` | `type=public_feed` 或 `type=generic_web`、`url`、`config.url`、`config.feed_type?`、`config.max_items?`、`config.extract_mode?` | 创建公开 RSS/Atom 或公开 docs/page 采集源 |
| 启用 Task | `POST /api/sources/{source_id}/enable` | 无 | 创建或复用 `public_feed` / `generic_web` 采集任务 |
| 执行采集 | `POST /api/tasks/{task_id}/run` | 无 | 写入 TaskRun、RawRecord、Entity/Snapshot；不写 Dataset |

公开内容数据集化：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/public-content-dataset-preview` | `authorized`、`task_run_ids`、`fields?`、`max_rows?` | `AutomationProductDatasetPreviewResponse` | 从 `public_feed` entries 或 `generic_web` docs/page snapshot 生成公开内容数据集预览，不保存 DatasetVersion |
| `POST` | `/api/automation/public-content-dataset-save` | preview request + `name`、`description?` | `AutomationProductDatasetSaveResponse` | 保存 `dataset_type=public_content_update`、`schema_version=public_content_update.v1` 的 DatasetVersion |
| `POST` | `/api/automation/public-content-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、`completeness_drop_threshold_percent?`、`freshness_grace_hours?` | `AutomationProductDriftCheckResponse` | 只读比较最新 `public_feed` / `generic_web` TaskRun；用 `link` 做主键、`content_hash` 做内容漂移信号 |
| `POST` | `/api/automation/public-content-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 从只读 drift check 保存或复用 `event_type=public_content_drift` 的 DatasetDriftEvent |
| `GET` | `/api/automation/public-content-drift-events` | `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出公开内容 DatasetDriftEvent；不启动采集、不创建告警 |
| `POST` | `/api/automation/public-content-report` | `authorized`、`dataset_id`、`dataset_version_id`、`top_limit?` | `AutomationPublicContentReportResponse` | 从已保存 DatasetVersion 生成公开内容更新报告预览，不创建 Report 资产 |
| `POST` | `/api/automation/public-content-report-assets` | report request + `confirm_create`; optional header: `Idempotency-Key` | `AutomationPublicContentReportAssetResponse` | 在明确确认后创建 `report_type=public_content` Report 资产；同 key 重放返回原 Report，不发送通知、不写导出文件 |

公开内容数据集字段：

```text
title, link, published_at, updated_at, author, tags, summary,
content_hash, feed_url, feed_title, feed_type, site_url,
source_type, content_kind, text_length
```

公开内容边界：

1. 只支持已授权公开 RSS/Atom feed 或公开文档更新源；不覆盖登录态、私信、付费墙、验证码或账号后台页面。
2. `public-content-drift-check` 不启动采集、不创建 `DatasetDriftEvent`、不创建告警、不发送通知。
3. `public-content-drift-events` 只保存/复用 drift 快照，不启动采集、不创建告警、不发送通知。
4. `public-content-report` 只返回只读预览；`public-content-report-assets` 只在 `confirm_create=true` 后创建或重放 Report 资产，不写导出文件、不发送邮件；`Idempotency-Key` hash 绑定 `workspace_id`、`dataset_id`、`dataset_version_id` 与 `top_limit`，原始 key 不写入审计事件。
5. Dataset export、生产 Source/Task/TaskRun、scheduler、provider/email 和生产浏览器运行仍需独立授权。

### Public Page Structure Preflight

公开网页结构预检当前挂在 Toolkit API 下：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/toolkit/preflight` | `url`、`authorized` | `ToolkitPreflightReportResponse` | 对公开 URL 做授权 gate、robots、sitemap、DOM 摘要和工具建议 |

预检通过后，如需进入持续采集，前端再复用：

1. `POST /api/sources` 创建 `generic_web` Source。
2. `POST /api/sources/{source_id}/enable` 启用 Task。
3. `POST /api/tasks/{task_id}/run` 执行一次公开网页采集。

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

`AutomationProductDiscoveryResponse` 关键字段：

| 字段 | 说明 |
|---|---|
| `product_candidates[].canonical_url` | canonical 去重后的商品 URL；`url` 当前也使用 canonical URL 作为 fan-out 输入 |
| `page_structure.pagination_url_count` | listing/collection 中识别到的分页 URL 数 |
| `page_structure.duplicate_url_count` | 被 canonical 去重折叠的候选 URL 数 |
| `page_structure.skipped_url_count` | 被跳过的 URL 数，包含非商品链接和重复 canonical URL |
| `discovery_plan.pagination_urls` | 分页 URL 样本，供人工确认后继续扩展 |
| `discovery_plan.dedupe_summary` | 输入 URL 数、规范候选数、重复数、跳过数和 `skipped_reasons` 汇总 |

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
| `POST` | `/api/automation/product-dataset-exports` | body: `authorized`、`confirm_create`、`dataset_id`、`dataset_version_id`、`export_format`; optional header: `Idempotency-Key` | `AutomationProductDatasetExportJobResponse` | 生成受控导出文件，格式支持 `csv`、`json`、`jsonl`；同 key 重放返回原 job |
| `GET` | `/api/automation/product-datasets/{dataset_id}/exports` | query: `dataset_version_id?`、`limit?` | `AutomationProductDatasetExportListResponse` | 查看导出历史 |
| `GET` | `/api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download` | 无 | 文件响应 | 下载导出文件 |

导出不变量：

1. 未传 `confirm_create=true` 时必须拒绝导出。
2. ExportJob 必须记录 `filename`、`content_type`、`artifact_size_bytes`、`row_count`、`checksum_sha256`、`audit_events`。
3. 下载接口必须限制 artifact 位于 `Settings.dataset_export_dir` 内，避免路径穿越。
4. `Idempotency-Key` hash 绑定 `workspace_id`、`dataset_id`、`dataset_version_id` 和 `export_format`；首次写入返回 `idempotency_replayed=false`，重复请求返回 `idempotency_replayed=true` 和同一个 `download_url`。

GitHub 工具漂移和报告：

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/github-tool-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、阈值字段 | `AutomationProductDriftCheckResponse` | 对 `github_tool_radar` 数据集做同源 GitHub task 只读漂移检查 |
| `POST` | `/api/automation/github-tool-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 保存 `event_type=github_tool_radar_drift` 的漂移快照 |
| `GET` | `/api/automation/github-tool-drift-events` | query: `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出 GitHub 工具数据集漂移事件 |
| `POST` | `/api/automation/github-tool-report` | `authorized`、`dataset_id`、`dataset_version_id`、`min_stars?`、`top_limit?` | `AutomationGitHubToolReportResponse` | 基于已保存版本生成只读工具雷达报告 |
| `POST` | `/api/automation/github-tool-report-assets` | report request + `confirm_create=true`; optional header: `Idempotency-Key` | `AutomationGitHubToolReportAssetResponse` | 将工具雷达报告保存为 `report_type=github_tool_radar` 的 Report 中心资产，成功返回 `201`；同 key 重放返回原 Report |

`AutomationGitHubToolReportResponse.summary` 包含 `repository_count`、`total_stars`、`high_value_repositories`、`languages`、`top_topics`、`report_created=false`、`run_started=false`。

`AutomationGitHubToolReportAssetResponse` 继承只读报告 response，并额外返回 `report`、`notification_created=false`、`idempotency_replayed`、`idempotency_scope` 与 `idempotency_key_hash`；`summary.report_created=true` 仅表示已写入或命中既有 Report 资产，不表示发送或创建通知。

边界：

1. GitHub 工具漂移检查只允许与 DatasetVersion `source_task_run_ids` 同源的 `github_topic` / `github_repo` task 进入比较。
2. GitHub 工具漂移和只读报告接口均不启动采集、不创建告警、不发送通知。
3. `github-tool-report-assets` 只创建 Report 中心资产和审计事件；不会启动采集、创建站内通知或发送邮件。
4. `github-tool-report-assets` 的 `Idempotency-Key` hash 绑定 `workspace_id`、`dataset_id`、`dataset_version_id`、`min_stars` 与 `top_limit`；重复请求返回原 Report，原始 key 不写入审计事件。

### Schedule, Drift And Dataset Alerts

| 方法 | 路径 | 请求 | 响应 | 说明 |
|---|---|---|---|---|
| `POST` | `/api/automation/product-schedule-approve` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、调度策略字段 | `AutomationProductScheduleApproveResponse` | 审批数据集关联采集任务的后续刷新策略 |
| `POST` | `/api/automation/product-drift-check` | `authorized`、`dataset_id`、`dataset_version_id`、`task_ids`、阈值字段 | `AutomationProductDriftCheckResponse` | 检查数据集版本与最新运行结果的字段、目录 presence 和价格漂移 |
| `POST` | `/api/automation/product-drift-events` | drift check request + `note?` | `AutomationProductDriftEventResponse` | 保存漂移快照 |
| `GET` | `/api/automation/product-drift-events` | query: `dataset_id?`、`dataset_version_id?`、`limit?` | `AutomationProductDriftEventListResponse` | 列出漂移事件 |
| `POST` | `/api/automation/product-drift-alert-preview` | `authorized`、`dataset_id`、`dataset_version_id?`、`min_status?`、`channel?` | `AutomationProductDriftAlertPreviewResponse` | 预览漂移告警规则 |
| `POST` | `/api/automation/product-drift-alert-rules` | preview request + `confirm_create` | `AutomationProductDriftAlertRuleCreateResponse` | 创建漂移告警规则 |
| `POST` | `/api/automation/product-drift-alert-events` | `authorized`、`confirm_create`、`dataset_id`、`dataset_version_id`、`drift_event_id` | `AutomationProductDriftAlertEventCreateResponse` | 从漂移事件创建 Signal 和 AlertEvent |
| `POST` | `/api/automation/product-drift-alert-notifications` | body: `authorized`、`confirm_send`、`dataset_id`、`dataset_version_id`、`drift_event_id`、`alert_event_ids`; optional header: `Idempotency-Key` | `AutomationProductDriftAlertNotificationSendResponse` | 发送站内通知；同 key 重放返回既有通知 |
| `POST` | `/api/automation/product-drift-alert-emails` | notification request + `recipient_email?`; optional header: `Idempotency-Key` | `AutomationProductDriftAlertEmailSendResponse` | 发送邮件告警；同 key 重放返回既有发送结果且不再次调用 SMTP/provider |

当前已硬化：

1. 漂移快照保存具备 fingerprint 复用，重复提交不会创建重复漂移事件。
2. 漂移告警规则按项目、条件、渠道和启用状态复用既有规则。
3. 采集运行失败日志已记录标准化 `failure_reason`。
4. 商品漂移 item 返回 `row_change`、`added_row_count`、`removed_row_count`、`price_change_percent`；summary 返回 `added_rows`、`removed_rows`、`price_changed_tasks`。
5. `drift_layers` 除 `completeness`、`field_missingness`、`task_freshness` 外，可返回 `catalog_presence` 和 `price_change`；`product_removed` 会使任务状态进入 `critical`。

当前已补：

1. 前端主提交按钮有 submitting / in-flight guard。
2. 采集任务执行有 task row lock、collector `run_timeout_seconds`、scheduler running-task skip。
3. auto freshness 失败重试有 `max_retry_attempts` / `retry_attempts_used` 预算字段；预算耗尽后 `next_run_at=null`，`freshness_status=retry_exhausted`。
4. 手动 Task run 支持 `Idempotency-Key` 首个本地合同：同一 workspace/task/key hash 的重复请求返回原 `TaskRun`，不再启动 collector；原始 key 不写入日志，只保留 `idempotency_key_hash` 证据。
5. Dataset export create 支持 `Idempotency-Key` 本地合同：同一 workspace/dataset/version/export_format/key hash 的重复请求返回原 `DatasetExportJob`，不再重写导出文件；原始 key 不写入 `audit_events`。
6. Report send 支持 `authorized` + `confirm_send` + optional `Idempotency-Key` 本地合同：同一 workspace/report/channels/key hash 的重复请求返回原发送结果，不再创建重复站内通知；原始 key 不写入审计事件。
7. Drift alert notification/email send 支持 optional `Idempotency-Key` 本地合同：站内通知重放返回既有 notification；邮件重放读取 AlertEvent delivery audit，跳过 `send_email_notification` / SMTP/provider 调用；原始 key 不写入 payload。
8. Report asset create 支持 optional `Idempotency-Key` 本地合同：`github-tool-report-assets` 与 `public-content-report-assets` 重放返回原 Report 资产，不重复创建 Report、通知、邮件或导出文件；原始 key 不写入审计事件。
9. Report subscription run/retry 必须显式 `authorized=true` 与 `confirm_run=true` / `confirm_retry=true`，并支持 optional `Idempotency-Key` replay：重复请求返回原 `ReportSubscriptionRun`，不重复生成 Report、不重复创建站内通知或触发 email provider 尝试；原始 key 不写入审计事件。
10. Email channel test 必须显式 `authorized=true` 与 `confirm_send=true`，并支持 optional `Idempotency-Key` replay：重复请求返回原 `EmailChannelTestRun`，不重复调用 SMTP/provider；原始 key 不写入 payload 或测试记录。
11. Email provider-live gate preflight 必须显式 `authorized=true` 与 `confirm_prepare=true`，并支持 optional `Idempotency-Key` replay：重复请求返回原 `EmailProviderLiveGateRun`，始终返回 `provider_call_allowed=false`、`email_send_allowed=false`、`production_write_allowed=false` 和 `provider_call_attempted=false`，不触发 SMTP/provider。
12. Email provider live-send readiness 提供只读清单：返回 `send_enabled`、allowlist 是否配置、allowlist 计数、channel 状态、必填授权字段和 `provider_call_attempted=false`，不触发 SMTP/provider，也不创建 run。
13. Email provider live-send gate 必须显式 `authorized=true`、`confirm_send=true`、`gate_run_id`、`approval_id` 和 `Idempotency-Key`；默认 `EMAIL_LIVE_SEND_ENABLED=false` 且 allowlist 为空时只创建 `EmailProviderLiveSendRun` deny 审计记录，返回 `provider_call_attempted=false`，原始 key 不写入 payload 或 run 记录。

仍需扩展：

1. provider 真实生产发送和调度触发的审批记录、生产只读清单、side-effect 日志；L4 邮件发送 runbook 已有本地文档，生产执行证据仍待授权。
2. Retry budget 的生产门禁和更完整的 operator UI。

## Task And Run

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| `GET` | `/api/tasks` | query: `project_id`、`status`、`collector_type` | `CollectionTaskResponse[]` |
| `GET` | `/api/tasks/{task_id}` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/tasks/{task_id}/run` | optional header: `Idempotency-Key` | `TaskRunResponse` |
| `POST` | `/api/tasks/{task_id}/pause` | 无 | `CollectionTaskResponse` |
| `POST` | `/api/tasks/{task_id}/resume` | 无 | `CollectionTaskResponse` |
| `GET` | `/api/tasks/{task_id}/runs` | 无 | `TaskRunResponse[]` |

运行语义：

1. `run` 会创建 TaskRun，并把采集、归一化、信号、情报链路串起。
2. 失败 run 必须记录 `error_message` 和 logs。
3. pause/resume 只改变 task 状态，不删除历史 run。
4. `CollectionTaskResponse` 暴露 `retry_delay_minutes`、`max_retry_attempts`、`retry_attempts_used`、`retry_budget_exhausted`；这些字段来自 `CollectionTask.config`，当前属于本地运行安全合同，不等于生产调度门禁已完成。
5. `POST /api/tasks/{task_id}/run` 带相同 `Idempotency-Key` 重放时返回 `200` 和原 `TaskRun`，`idempotency_replayed=true`；首次执行仍返回 `201`，并在 `TaskRun.logs` 中记录 `idempotency_key_recorded`、`scope=task_manual_run`、`raw_key_stored=false` 和 hash。

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
| `POST` | `/api/reports/subscriptions/{subscription_id}/run` | body: `authorized`、`confirm_run`; optional header: `Idempotency-Key` | `ReportSubscriptionResponse` |
| `GET` | `/api/reports/subscriptions/{subscription_id}/runs` | 无 | `ReportSubscriptionRunResponse[]` |
| `POST` | `/api/reports/subscriptions/{subscription_id}/runs/{run_id}/retry` | body: `authorized`、`confirm_retry`; optional header: `Idempotency-Key` | `ReportSubscriptionResponse` |
| `GET` | `/api/reports/{report_id}/evidence-references` | 无 | `ReportEvidenceReferenceResponse[]` |
| `GET` | `/api/reports/{report_id}/download.md` | 无 | Markdown 文件 |
| `GET` | `/api/reports/{report_id}/audit-events` | 无 | `ReportAuditEventResponse[]` |
| `POST` | `/api/reports/{report_id}/audit-events` | 审计事件 | `ReportAuditEventResponse` |
| `GET` | `/api/reports/{report_id}` | 无 | `ReportResponse` |
| `POST` | `/api/reports/{report_id}/send` | body: `authorized`、`confirm_send`、`channels?`; optional header: `Idempotency-Key` | `ReportResponse` |

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
| `POST` | `/api/notifications/email-channel/test` | body: `authorized`、`confirm_send`; optional header: `Idempotency-Key` | `EmailChannelTestResponse` |
| `POST` | `/api/notifications/email-channel/provider-live-gate` | body: `authorized`、`confirm_prepare`、`operation`、`recipient_email?`、`max_provider_calls?`; optional header: `Idempotency-Key` | `EmailProviderLiveGateResponse` |
| `GET` | `/api/notifications/email-channel/live-send-readiness` | 无 | `EmailProviderLiveSendReadinessResponse` |
| `POST` | `/api/notifications/email-channel/live-send` | body: `authorized`、`confirm_send`、`gate_run_id`、`approval_id`、`operation`、`recipient_email?`; required header: `Idempotency-Key` | `EmailProviderLiveSendResponse` |
| `PATCH` | `/api/notifications/{notification_id}/read` | 无 | `NotificationResponse` |
| `POST` | `/api/notifications/read-all` | 无 | `NotificationReadAllResponse` |
| `POST` | `/api/notifications/read-bulk` | `notification_ids` | `NotificationReadAllResponse` |

通知规则：

1. report send 必须显式 `authorized=true`、`confirm_send=true`；带同一 `Idempotency-Key` 重放时返回 `idempotency_replayed=true` 和原 `delivered_channels` / `skipped_channels`，不会重复创建站内通知。
2. report subscription run/retry 必须显式授权与确认；带同一 `Idempotency-Key` 重放时返回同一个 `latest_run`，不会重复生成 Report、创建站内通知或触发 email provider 尝试。
3. email channel test 必须显式授权与确认；带同一 `Idempotency-Key` 重放时返回同一个测试记录，`idempotency_replayed=true`，不会重复调用 SMTP/provider。未配置 SMTP 时 `provider_call_attempted=false`。
4. email provider-live gate preflight 必须显式授权与确认；带同一 `Idempotency-Key` 重放时返回同一个 gate run，`provider_call_allowed=false`、`email_send_allowed=false`、`production_write_allowed=false`、`provider_call_attempted=false`，只形成本地预授权审计包，不发送邮件。
5. email provider live-send readiness 是只读 inventory endpoint；`status=blocked` 表示仍缺配置或 allowlist，`status=ready_pending_l4_authorization` 只表示具备进入人工审批的前置条件，不表示已允许发送。
6. email provider live-send gate 必须引用同 workspace/user 的 gate run，并显式提供 `approval_id` 与 `Idempotency-Key`；默认配置下返回 `blocked`，记录 `send_enabled=false`、`recipient_allowlisted=false`、`provider_call_attempted=false`。只有配置显式开启、recipient 命中 exact allowlist、gate ready、SMTP ready 且审批存在时才允许 sender 分支；测试仅用 fake sender 覆盖该分支。
7. alert match 会生成 alert event，并按 rule channel 生成站内通知。
8. Drift alert notification/email send 支持 `Idempotency-Key` replay；邮件 replay 不再次调用 SMTP/provider。
9. email channel 必须通过环境变量配置，未配置时接口返回禁用状态。

## Capability Read API

All routes require the existing authenticated session and are read-only.

| Method | Route | Filters / result |
|---|---|---|
| GET | `/api/capabilities/matrix` | `capability_matrix.v1`; 7 platforms, 6 channels, 42 explicit cells |
| GET | `/api/capabilities/assertions` | `platform`, `access_channel`, `resource_type`, `operation`, `support_status`; valid zero result is `[]` |
| GET | `/api/capabilities/implementations` | `platform`, `access_channel`; valid zero result is `[]` |
| GET | `/api/capabilities/implementations/{implementation_id}` | Implementation + owned Assertions + referenced Evidence |

Invalid enum query values return `422`. A missing Implementation returns `404` with `capability_implementation_not_found`. Catalog load/parse/validation failure returns `500` with `capability_catalog_load_failed`; there is no static-data fallback.

Every Matrix response carries `provider_call=false` and `production_write_allowed=false`. Evidence retains `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production_write_attempted=false`.

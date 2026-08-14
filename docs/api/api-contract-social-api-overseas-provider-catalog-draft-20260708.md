---
title: 海外媒体 API 私有化第一批（YouTube+Reddit+X+Instagram/Threads+TikTok+LinkedIn）深度盘点与落地计划
doc_type: analysis
topic: overseas-social-media
status: draft
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
private_deploy_boundary: self_hosted_collectors
created: 2026-07-08
updated: 2026-07-10
owner: self
source: codex
---

# 海外媒体 API 深度盘点与第一批落地计划

## 0. 边界与前提

### 事实

- 第一批只覆盖 `YouTube / Reddit / X / Instagram+Threads / TikTok / LinkedIn`。
- 本轮目标是 `docs-only + fixture-first + readiness/gate-only`，默认 `provider_call=false`，不走 TikHub hosted endpoint。
- 运行时新增接口:
  - `GET /api/automation/social-provider-catalog`
  - `POST /api/automation/social-provider-readiness`
  - `POST /api/automation/social-provider-gate`
  - `POST /api/automation/social-provider-live-approval-template`
  - `POST /api/automation/social-provider-dependency-gate`
  - `POST /api/automation/social-provider-adapter-plan`
  - `POST /api/automation/social-provider-source-template`
  - `POST /api/automation/social-raw-preview`
  - `POST /api/automation/social-normalization-preview`
  - `POST /api/automation/social-dataset-preview`
  - `POST /api/automation/social-task-run-approval-template`
  - `POST /api/automation/social-execution-dry-run`
- `social-provider-catalog` 支持 `data-domain` 与 `resource-group` 两套筛选，方便与 `ProviderRegistry` 的 resource_group 映射打通。
- `social-raw-preview` 只生成 `social_raw.v1` fixture records，不创建 Source/Task/RawRecord，不读取 credential，不执行 live comparison。
- `social-provider-adapter-plan` 只检查 catalog SDK selection、`data_intelligence_hub.social_api.*` 本地 adapter module 映射与可选依赖 import spec，不 import SDK live client、不读取 credential、不发生 provider call。
- `social-provider-source-template` 只生成 `manual_json` SourceCreate 候选 payload，不调用 `/api/sources`，不创建 Source/Task，不写 DB。
- V2 运行时 catalog 已迁移到 `apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json`。
- `GET /api/automation/social-provider-catalog` 由兼容投影返回 `external_provider_catalog.v1`，不会直接读取 `social_provider_catalog_overseas.json` 运行时文件。
- 历史 `social_provider_catalog_overseas.json` 的 `V1` 兼容数据仅保留在 `apps/api/tests/fixtures/external_provider_catalog_v1.json`，用于回归测试。

### V2.0 Catalog 迁移

- 运行时单一事实源：`services/fixtures/capability_catalog_overseas_v2.json`。
- 规范合同：`capability_catalog.v1`。
- 现有 `GET /api/automation/social-provider-catalog` 继续返回 `external_provider_catalog.v1`，由 V2 Catalog 投影生成。
- 历史 V1 Fixture 只保留在 `tests/fixtures/external_provider_catalog_v1.json`，用于兼容回归。
- GOAL-V2-01 不新增数据库表、API route、Provider Client 或 Credential 读取。

### 推断

- 海外采集最稳路径应是“官方/授权 API + 官方授权导出 + 公开 page/ feed + manual_json兜底”。
- 先验上，YouTube 与 Reddit 为第一批最优 P0：文档边界清晰、配额/用量可预算、可先做最小 `search/list/search-comments` 体系。
- LinkedIn 与 TikTok Research 的授权窗口、版本迁移和用途限制是本批最大的节奏风险，不适合并发实现 live。
- 本轮 SDK 复用采用 catalog contract 先行：只记录 `sdk_selection` 和 `live_adapter_strategy`，直到对应平台 L4 gate 通过才安装/启用 live adapter 依赖。
- 代码层已提供 optional extras：`social-youtube`、`social-reddit`、`social-overseas-live`；dependency gate 只返回安装计划，不执行安装。

### 不确定

- 预算/计费（单位成本、最低阶层、免费配额）会随平台政策更新，需每次 `catalog_sync` 与上线前复核。
- 目前不保证任何平台的 `用户数据再分发`、`AI 训练再利用` 或 `关系图谱扩展抓取` 在不同法域保持不变。

---

## 1. 海外 6 平台 Deep Dive（Docs-Contract）

以下是第一批的 API 对标与事实边界。每个平台均按 `official docs -> ready-made credential -> policy gate -> fixture dry-run` 顺序执行。

### 1.1 YouTube（P0）

#### 事实

- 官方主线：YouTube Data API v3（官方文档路径与资源均可公开查证）。
- 采集目标：视频/频道/评论/检索。
- 文档中的配额逻辑具备可预算性（method unit 成本）：
  - `search.list`、`videos.insert` 属于低频配额窗口；
  - 其他常用资源通常使用 `default daily quota`。
- 支持场景：`videos.list`、`channels.list`、`commentThreads.list`、`search.list`。
- 风险边界：版权、评论原文使用范围、配额异常回退。

#### 对应平台适配项

| 维度 | 结论 |
|---|---|
| 鉴权 | API Key / OAuth2 server-side |
| 资源分组 | `content_search`、`video_detail`、`channel_profile`、`comment_threads`、`live_feed` |
| 第一优先 endpoint | `search.list` -> `videos.list` -> `channels.list` -> `commentThreads.list` |
| 预算字段 | `requests_per_minute/hour/day`（按 method cost 聚合） |
| 默认阻断 | 私信、登录态抓取、未授权媒体下载、用户画像扩图 |
| 适配优先级 | P0 第一位 |

### 1.2 Reddit（P0）

#### 事实

- 官方主线：OAuth Data API；默认速率/头部字段可观测。
- 官方条款对用途与再用有约束，尤其是 AI 训练与商业化需确认协议。
- 公开可落地：`hot/new`、`search`、`comments`、`subreddit` 相关对象链路。
- 采集前置应先在 README/文档中统一 `User-Agent`、OAuth scope、速率窗口。

#### 对应平台适配项

| 维度 | 结论 |
|---|---|
| 鉴权 | OAuth bearer + app credentials |
| 资源分组 | `post_search`、`subreddit_snapshot`、`comment_snapshot`、`user_profile_public` |
| 第一优先 endpoint | `hot/new` 列表 -> `search` -> `comments.new` -> `user.profile` |
| 预算字段 | `requests_per_minute`、`requests_per_day` |
| 默认阻断 | `no_ai_training`（除非 owner 审批）、私信、login-state、captcha 绕过 |
| 适配优先级 | P0 第二位 |

### 1.3 X / Twitter（P1）

#### 事实

- 官方主线：X API v2，按产品权限/账单分层，不同 endpoint 成本与速率独立。
- 可优先用 `recent search` 与 `post/user lookup` 做低风险启动，避免 full archive 一起开。
- 交易型账单模式与限速窗口较易触发预算风险，必须 runbook 约束。

#### 对应平台适配项

| 维度 | 结论 |
|---|---|
| 鉴权 | OAuth2 bearer + paid key |
| 资源分组 | `post_search`、`post_lookup`、`user_profile`、`realtime_trends` |
| 第一优先 endpoint | `tweets/search/recent` -> `tweets` -> `users/me` |
| 预算字段 | `requests_per_minute/day`（按付费额度与 endpoint profile 叠加） |
| 默认阻断 | 私信、关系图扩张抓取、未支付权限范围外调用 |
| 适配优先级 | P1 |

### 1.4 Instagram + Threads（P2）

#### 事实

- 两者均围绕 Meta 体系，商业/创作者账号与授权范围是关键门槛。
- `mentions / comments / insights` 通常要求页面级或应用级权限，scope 错配会造成大量 403/审核失败。
- 公共内容可作为对照，但不以此覆盖官方授权路径。

#### 对应平台适配项

| 维度 | 结论 |
|---|---|
| 鉴权 | Meta app token + page/business token + scope |
| 资源分组 | `media_feed`、`user_pages`、`mentions`、`comments`、`insights` |
| 第一优先 endpoint | `media` -> `mentions` -> `comments` -> `insights` |
| 预算字段 | `requests_per_hour/day`（平台内计费与权限分层） |
| 默认阻断 | consumer account deep scrape、dm、未授权 comment dump |
| 适配优先级 | P2，同时跑（Instagram 与 Threads） |

### 1.5 TikTok Research（P3，预审窗口）

#### 事实

- 该通道明显为“研究场景”化路径，资格、地区、用途审批窗口比单纯 API 配额更关键。
- 文档可给出日请求与上下文上限线，日常应按 `test-stage` 控制体量。
- 未经过合法用途确认前不宜放开 high-volume 抓取。

#### 对应平台适配项

| 维度 | 结论 |
|---|---|
| 鉴权 | OAuth2 / VCE 资格链路 |
| 资源分组 | `video_snapshot`、`video_comment`、`search`、`creator_profile` |
| 第一优先 endpoint | `video.search` -> `video.list` -> `comment.list` |
| 预算字段 | `requests_per_day`（研究端口） |
| 默认阻断 | 非研究用途、私信、未备案 AI 训练 |
| 适配优先级 | P3（与 Live 授权解耦） |

### 1.6 LinkedIn（P3，社区/商业能力对齐）

#### 事实

- 官方能力路径以 MDP/MCM 为主，版本停用与 tier 升级节奏较快。
- 更适合先打通 readiness 文档（申请窗口、角色、组织与数据权限），随后再进入授权执行。
- 可落地字段以组织与内容页为主（`ugcPosts`、`organizations`、`socialActions`）。

#### 对应平台适配项

| 维度 | 结论 |
|---|---|
| 鉴权 | OAuth2 + app tier 审批 |
| 资源分组 | `company_updates`、`post_feed`、`ugc_posts`、`organization_pages` |
| 第一优先 endpoint | `organizations` -> `ugcPosts` -> `socialActions` |
| 预算字段 | `requests_per_minute/day`（需按 app tier 叠加） |
| 默认阻断 | 粉丝/联系人图谱扩展、未获批准的数据重分发 |
| 适配优先级 | P3（readiness -> live） |

---

## 2. 可落地稳定性评分与阻断矩阵

### 2.1 稳定性评分规则

- `5`: 官方文档稳定、鉴权链路清晰、配额/速率可直接预算（YouTube、Reddit）
- `4`: 官方 API 可用但成本和用途审核复杂（X）
- `3`: 官方能力明确但权限/资格流程重（Instagram/Threads/TikTok/LinkedIn）
- `2`: 当前以 readiness 和导入并行推进，未进入 live 运行

### 2.2 本批平台评分与风控

| 平台 | 稳定性 | 风险等级 | 第一批结论 |
|---|---:|---|---|
| YouTube | 5 | 中 | 立即推进：fixtures -> readiness -> quota gate -> 试运行 |
| Reddit | 5 | 中高 | 同步推进：先 read-only 清单、再 small-volume 试运行 |
| X | 4 | 高 | 成本先行，强制 budget gate |
| Instagram/Threads | 3 | 中高 | 先只做自有/商业资产范围 |
| TikTok | 3 | 高 | 仅 research test-only，等待资格 |
| LinkedIn | 3 | 高 | readiness 文档先行，未默认 live |

---

## 2.3 开源 SDK 选型（只登记，不发起调用）

| 平台 | 选型 | 状态 | 复用原因 | 本轮边界 |
|---|---|---|---|---|
| YouTube | `google-api-python-client` | selected | Google 官方 discovery-based Python client，覆盖 YouTube Data API v3 | catalog 记录，不执行 API |
| Reddit | `asyncpraw` | selected | PRAW 官方异步分支，适配 FastAPI async runtime，内置 Reddit API 规则处理 | catalog 记录，不创建 Reddit client |
| X | `tweepy[async]` | candidate | X 官方 tools page 列出的流行 Python v2 库 | 需付费 tier 与 `max_cost_usd` gate |
| Instagram | `facebook-business` | candidate | Meta Business SDK，覆盖部分 Instagram/Business API 能力 | 仅 business/professional scope |
| Threads | `httpx` | selected | 复用现有 HTTP client 依赖，走官方 Graph REST 合同 | 只读授权资产，未执行 live |
| TikTok | `TikTokResearchApi` | manual_review | TikTok 官方 Research API wrapper，但资格/地域/用途先决 | 默认 test-only |
| LinkedIn | `linkedin-api-client` | manual_review | LinkedIn 官方 Rest.li client beta | 只进入 readiness，不默认 live |

明确不采用：非官方登录态 LinkedIn/TikTok/Instagram scraper、captcha/anti-detect/browser-cookie 方案、无需官方权限即可读私有数据的 wrapper。

### Optional dependency extras

| Extra | Package | 用途 | 默认状态 |
|---|---|---|---|
| `social-youtube` | `google-api-python-client>=2.198.0` | YouTube Data API v3 官方 client | 未安装、未启用 |
| `social-reddit` | `asyncpraw>=8.0.2` | Reddit OAuth Data API async wrapper | 未安装、未启用 |
| `social-overseas-live` | 上述二者 | Phase 2 live adapter bundle | 未安装、未启用 |

---

## 3. 第一批执行树（2-3 周）

### Phase 0（D1-D2）：边界冻结

- 固定文档版本与证据：官方文档版本、条款条目、额度截图/文档节选。
- 产出:
  - `catalog_overseas`（静态 baseline + 稳定性评分 + 禁止动作）
  - `social-provider-readiness/gate` 合约
  - 第一次 Policy Gate 评审清单（默认 `allow_ai_training=false`）

### Phase 1（D3-D6）：fixture-first 工程

- 完成 provider_catalog 只读接口与 schema 校验。
- 完成 readiness/gate 单元与路由测试：
  - 未授权不允许 provider call
  - 超预算阻断
  - policy 违规阻断
- 输出:
  - `social_provider.*` 代码 + 测试闭环
  - `run_scope=fixture_gate_only` 的审计合同
  - `POST /api/automation/social-raw-preview` 只读 fixture preview

### Phase 2（D7-D12）：YouTube + Reddit PoC

- 按平台独立执行：
  1. catalog 验证
  2. dry-run readiness
  3. policy-gate
  4. tiny live checklist（10 分钟只读演练）
- 验收指标:
  - `provider_call_allowed=True` 时仍要求 `provider_call_attempted=False`（第一轮）
  - `forbidden_actions` 全部命中缺省
  - `provider_call` 与 `production_write` 保持 false
  - live adapter 依赖只在 L4 gate 通过后安装/启用

### Phase 3（D13+）：X 与 Meta 组合

- X：先上 `search/posts/user lookup`，并加入 `max_cost_usd` 强约束
- Instagram/Threads：仅 `professional/business` 资源，未确认 endpoint 进入 `manual_json/manual_import`
- `tasks/source` 侧只允许生产侧创建预置 payload，仍不执行历史回填

### 预留（Batch-2）

- TikTok: research qualification 通过后再放量。
- LinkedIn: 应用申请、tier 审核、组织角色评审通过后再执行。

---

## 4. 风控与政策默认值（生产未启动）

- 默认禁止：私信、登录态抓取、验证码绕过、图谱扩展、未授权下载。
- 默认 `author_policy=hashed|dropped`；仅在 owner 授权时允许 `retained_with_approval`。
- 任何 `social_voc_item` 或分析结论必须带 `raw_record_id/evidence_ref` 回溯，不得空游离生成。
- `policy_disable` 必须在 readiness 阶段返回，不进 live 逻辑。

---

## 4.1 API 合同补充：`social-raw-preview`

### Request

```json
{
  "platform": "youtube",
  "provider_id": "youtube.v3",
  "endpoint": "videos.list",
  "fixture_limit": 3,
  "include_live_comparison": false,
  "authorized": false,
  "approval_id": null
}
```

### Response 不变量

- `schema_version=social_raw_preview.v1`
- `fixture_only=true`
- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `production_write_allowed=false`
- `live_comparison_available=false`
- `records[*].schema_version=social_raw.v1`

`include_live_comparison=true` 或 `authorized=true` 只会返回 `live_comparison_requires_separate_l4_authorization`，不会触发 live provider call。

## 4.2 API 合同补充：`social-provider-live-approval-template`

用途：生成 L4 approval packet 模板，不代表已授权，不安装依赖，不发起 provider call。

Request:

```json
{
  "platform": "youtube",
  "provider_id": "youtube.v3",
  "endpoints": ["videos.list"],
  "intended_use": "small scoped read-only YouTube validation",
  "max_requests": 10,
  "max_items": 50,
  "max_cost_usd": 0,
  "retention_hours": 24,
  "allow_ai_training": false,
  "credential_reference": "env:YOUTUBE_API_KEY",
  "delete_policy": "delete_or_retain_by_policy_gate"
}
```

Response 不变量：

- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `dependency_install_allowed=false`
- `production_write_allowed=false`
- `approval_packet.authorized=false`
- `approval_packet.provider_call=false`
- `approval_packet.production_write=false`

## 4.3 API 合同补充：`social-provider-dependency-gate`

用途：判断本地可选依赖是否可进入安装计划；本接口不执行安装、不读取 credential、不启用 live adapter。

Request:

```json
{
  "platform": "reddit",
  "provider_id": "reddit.praw",
  "authorized": true,
  "approval_id": "approval-local-deps",
  "confirm_dependency_review": true,
  "confirm_no_provider_call": true,
  "confirm_no_credential_read": true,
  "install_scope": "local_dev_optional_dependency",
  "dry_run": true
}
```

Response 不变量：

- `dependency_install_executed=false`
- `live_adapter_enabled=false`
- `credential_read_attempted=false`
- `provider_call_attempted=false`
- `production_write_allowed=false`
- `installation_plan.executes_install=false`
- `installation_plan.enables_live_adapter=false`

## 4.4 API 合同补充：`social-provider-adapter-plan`

用途：生成 YouTube/Reddit fixture adapter 执行计划，验证已选成熟 SDK、`data_intelligence_hub.social_api.*` 本地 adapter module 名称和本地 optional dependency 是否存在。本接口不安装依赖、不 import live SDK client、不读取 `env` 或 secret manager、不创建 live client。

本轮已存在的 fixture adapter module：

- `data_intelligence_hub.social_api.youtube.google_api_client`
- `data_intelligence_hub.social_api.reddit.asyncpraw`

Request:

```json
{
  "platform": "youtube",
  "provider_id": "youtube.v3",
  "endpoints": ["videos.list"],
  "mode": "fixture_replay",
  "authorized": false,
  "approval_id": null,
  "credential_reference": null,
  "max_requests": 10,
  "fixture_limit": 2
}
```

Response 不变量：

- `schema_version=social_provider_adapter_plan.v1`
- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `live_client_created=false`
- `production_write_allowed=false`
- `fixture_replay_supported=true`
- `planned_operations[*].request_mode=fixture_replay`
- `planned_operations[*].provider_call=false`

`mode=live_dry_run`、`authorized=true`、`approval_id` 或 `credential_reference` 只会进入 blocker，例如：

- `live_adapter_requires_separate_l4_authorization`
- `authorized_ignored_for_fixture_adapter_plan`
- `approval_id_ignored_for_fixture_adapter_plan`
- `credential_reference_ignored_for_fixture_adapter_plan`

## 4.5 API 合同补充：`social-provider-source-template`

用途：生成海外 provider source 创建候选 payload，作为 owner 审核和后续 L4 source-create gate 的输入。本接口复用现有 `manual_json` 作为稳定导入兜底，不新增 live `social_api` collector，不调用 `/api/sources`。

Request:

```json
{
  "platform": "reddit",
  "provider_id": "reddit.praw",
  "endpoints": ["search"],
  "source_name": "Reddit search fixture source",
  "project_id": null,
  "authorized": false,
  "approval_id": null,
  "credential_reference": null,
  "fixture_limit": 3
}
```

Response 不变量：

- `schema_version=social_provider_source_template.v1`
- `source_type=manual_json`
- `template_strategy=manual_json_authorized_import`
- `fixture_only=true`
- `source_create_allowed=false`
- `source_created=false`
- `task_created=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `production_write_allowed=false`
- `source_create_payload.type=manual_json`
- `source_create_payload.config.entity_type=social_provider_fixture`
- `source_create_payload.config.json_data.provider_call=false`

`authorized=true`、`approval_id` 或 `credential_reference` 只会进入 blocker，例如：

- `authorized_ignored_for_source_template_preview`
- `approval_id_ignored_for_source_template_preview`
- `credential_reference_ignored_for_source_template_preview`

## 4.6 API 合同补充：`social-normalization-preview`

用途：把 `social-raw-preview` 的本地 fixture raw records 转成标准化草稿对象，供 owner 审核 `social_post.v1`、`social_comment.v1`、`social_voc_item.v1` 的字段形态。本接口只做内存预览，不写 RawRecord、EntitySnapshot、Dataset 或报告。

Request:

```json
{
  "platform": "reddit",
  "provider_id": "reddit.praw",
  "endpoint": "comments.new",
  "fixture_limit": 1,
  "include_voc": true,
  "include_live_comparison": false,
  "authorized": false,
  "approval_id": null,
  "author_policy": "hashed"
}
```

Response 不变量：

- `schema_version=social_normalization_preview.v1`
- `fixture_only=true`
- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `production_write_allowed=false`
- `normalization_write_allowed=false`
- `dataset_write_allowed=false`
- `raw_records[*].schema_version=social_raw.v1`
- `normalized_items[*].raw_record_id` 必须回指 raw record
- `normalized_items[*].evidence_ref` 必须回指 fixture evidence
- `social_voc_item.v1.payload.llm_call_attempted=false`

`authorized=true`、`approval_id`、live comparison 或明文作者保留只会进入 blocker，例如：

- `authorized_ignored_for_normalization_preview`
- `approval_id_ignored_for_normalization_preview`
- `live_comparison_requires_separate_l4_authorization`
- `author_retention_requires_separate_l4_authorization`

## 4.7 API 合同补充：`social-dataset-preview`

用途：把 `social-normalization-preview` 中的 `social_voc_item.v1` 草稿项投影成 `social_voc_dataset.v1` 预览 rows，供 owner 审核字段、证据引用和后续 DatasetVersion 保存授权范围。本接口只返回内存预览，不保存 Dataset、DatasetVersion，也不创建 DatasetExportJob 或文件。

Request:

```json
{
  "platform": "reddit",
  "provider_id": "reddit.praw",
  "endpoint": "comments.new",
  "fixture_limit": 2,
  "dataset_name": "Reddit comments VOC fixture",
  "max_rows": 100,
  "include_live_comparison": false,
  "authorized": false,
  "approval_id": null,
  "author_policy": "hashed",
  "save_requested": false,
  "export_requested": false
}
```

Response 不变量：

- `schema_version=social_dataset_preview.v1`
- `dataset_type=social_voc_fixture_preview`
- `dataset_schema_version=social_voc_dataset.v1`
- `fixture_only=true`
- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `production_write_allowed=false`
- `dataset_write_allowed=false`
- `dataset_created=false`
- `dataset_version_created=false`
- `export_created=false`
- `rows[*].source_schema_version=social_voc_item.v1`
- `rows[*].raw_record_id` 和 `rows[*].evidence_ref` 必须回指源 fixture evidence
- `rows[*].payload.llm_call_attempted=false`

`authorized=true`、`approval_id`、live comparison、保存、导出或明文作者保留只会进入 blocker，例如：

- `authorized_ignored_for_dataset_preview`
- `approval_id_ignored_for_dataset_preview`
- `live_comparison_requires_separate_l4_authorization`
- `dataset_save_requires_separate_l4_authorization`
- `dataset_export_requires_separate_l4_authorization`
- `author_retention_requires_separate_l4_authorization`

## 4.8 API 合同补充：`social-task-run-approval-template`

用途：为后续真正创建 Source、Task、TaskRun、DatasetVersion 或 DatasetExportJob 的 L4 执行申请生成审批包。本接口只返回 `social_task_run_l4_approval_packet.v1` 草稿，不创建资源、不启动采集、不读取 credential、不调用 provider。

Request:

```json
{
  "platform": "reddit",
  "provider_id": "reddit.praw",
  "endpoints": ["comments.new"],
  "intended_use": "small scoped Reddit comments VOC fixture run",
  "source_name": "Reddit comments fixture source",
  "task_name": "Reddit comments fixture task",
  "dataset_name": "Reddit comments VOC fixture",
  "credential_reference": "secret:reddit-oauth-readonly",
  "authorized": false,
  "approval_id": null,
  "max_requests": 5,
  "max_items": 20,
  "max_rows": 20,
  "max_cost_usd": 0,
  "retention_hours": 24,
  "allow_ai_training": false,
  "dataset_save_requested": false,
  "export_requested": false,
  "cleanup_policy": "cleanup_after_evidence"
}
```

Response 不变量：

- `schema_version=social_task_run_approval_template.v1`
- `approval_packet.schema_version=social_task_run_l4_approval_packet.v1`
- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `source_create_allowed=false`
- `task_create_allowed=false`
- `task_run_allowed=false`
- `dataset_write_allowed=false`
- `export_allowed=false`
- `production_write_allowed=false`
- `approval_packet.provider_call=false`
- `approval_packet.source_create=false`
- `approval_packet.task_create=false`
- `approval_packet.task_run=false`
- `approval_packet.dataset_save=false`
- `approval_packet.export_create=false`

`authorized=true`、AI 训练、Dataset save 或 export 请求只会被记录为未来申请意图，不会执行，例如：

- `authorized_recorded_but_not_executed`
- `allow_ai_training_must_be_false`
- `dataset_save_requires_separate_l4_authorization`
- `dataset_export_requires_separate_l4_authorization`
- `credential_reference_required_before_task_run`

## 4.9 API 合同补充：`social-execution-dry-run`

用途：把 readiness、raw preview、normalization preview、dataset preview、source template 与 task run approval template 串成一个可审阅的 fixture-only 执行预案。本接口不调用 provider、不读取 credential、不创建 Source/Task/TaskRun/RawRecord/Dataset/Export，也不授予 live 权限。

Request:

```json
{
  "platform": "reddit",
  "provider_id": "reddit.praw",
  "endpoint": "comments.new",
  "fixture_limit": 2,
  "dataset_name": "Reddit comments VOC fixture",
  "source_name": "Reddit comments fixture source",
  "task_name": "Reddit comments fixture task",
  "intended_use": "small scoped Reddit comments fixture dry-run",
  "credential_reference": "secret:reddit-oauth-readonly",
  "credentials_ready": false,
  "authorized": false,
  "approval_id": null,
  "include_live_comparison": false,
  "dataset_save_requested": false,
  "export_requested": false,
  "allow_ai_training": false,
  "max_requests": 5,
  "max_items": 20,
  "max_rows": 20,
  "max_cost_usd": 0,
  "retention_hours": 24,
  "author_policy": "hashed",
  "cleanup_policy": "cleanup_after_evidence"
}
```

Response 不变量：

- `schema_version=social_execution_dry_run.v1`
- `fixture_only=true`
- `execution_plan[*].provider_call=false`
- `execution_plan[*].credential_read=false`
- `execution_plan[*].production_write=false`
- `provider_call_allowed=false`
- `provider_call_attempted=false`
- `credential_read_attempted=false`
- `source_create_allowed=false`
- `task_create_allowed=false`
- `task_run_allowed=false`
- `dataset_write_allowed=false`
- `export_allowed=false`
- `production_write_allowed=false`
- `readiness`、`raw_preview`、`normalization_preview`、`dataset_preview`、`source_template`、`task_run_approval_template` 保留各自原合同与 blocker。

`authorized=true`、`approval_id`、live comparison、Dataset save、export、AI training 或明文作者保留只会进入 blocker，例如：

- `authorized_ignored_for_execution_dry_run`
- `approval_id_ignored_for_execution_dry_run`
- `live_comparison_requires_separate_l4_authorization`
- `dataset_save_requires_separate_l4_authorization`
- `dataset_export_requires_separate_l4_authorization`
- `allow_ai_training_must_be_false`
- `author_retention_requires_separate_l4_authorization`

---

## 5. 验收清单（本批）与失败态

### 官方文档待复核清单（上线前必须更新）

- YouTube Data API v3 文档页（quota 与 method cost）
  [https://developers.google.com/youtube/v3/docs](https://developers.google.com/youtube/v3/docs)
- Reddit OAuth Data API 文档（rate limit header 与 terms）
  [https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)
- X API v2 开发者文档（tier、quota、endpoints）
  [https://docs.x.com/x-api/introduction](https://docs.x.com/x-api/introduction)
- Meta Graph API / Threads API 文档（scopes、page/business 约束）
  [https://developers.facebook.com/docs/instagram-api](https://developers.facebook.com/docs/instagram-api)
- TikTok Research API 文档（VCE 与日请求/上下文上限）
  [https://developers.tiktok.com/doc/research-api-get-started](https://developers.tiktok.com/doc/research-api-get-started)
- LinkedIn Marketing/Community 文档（应用版本、组织权限、社区条款）
  [https://developer.linkedin.com/product-catalog](https://developer.linkedin.com/product-catalog)

### 本批可交付

- `social_provider` 路由与 catalog contract 可正常返回（含六大平台）。
- 约束级别测试通过：未认证、超预算、policy 禁止、未知平台都可复现阻断原因。
- adapter plan 可返回 YouTube/Reddit fixture operation，并保持 `credential_read_attempted=false` 与 `live_client_created=false`。
- source template 可返回 no-write `manual_json` SourceCreate 候选 payload，并保持 `source_created=false` 与 `task_created=false`。
- normalization preview 可返回 no-write `social_post.v1` / `social_comment.v1` / `social_voc_item.v1` 草稿项，并保持 `normalization_write_allowed=false` 与 `dataset_write_allowed=false`。
- dataset preview 可返回 no-write `social_voc_dataset.v1` 预览 rows，并保持 `dataset_created=false`、`dataset_version_created=false` 与 `export_created=false`。
- task run approval template 可返回 no-write L4 execution packet，并保持 `source_create_allowed=false`、`task_run_allowed=false`、`dataset_write_allowed=false` 与 `provider_call_attempted=false`。
- execution dry-run 可返回跨阶段 no-write 执行预案，并保持 `provider_call_attempted=false`、`credential_read_attempted=false`、`task_run_allowed=false`、`dataset_write_allowed=false` 与 `production_write_allowed=false`。
- 计划书输出可直接挂载到运行手册，不触发对外 provider call。

### 当前不在本批的失败态

- 任何平台 live 大规模抓取（YouTube/Reddit 除外的规模化）、历史回填、付费/关系图谱能力开启。
- TikTok/LinkedIn `authorized` 生产分流仍默认 `fixture-only`。

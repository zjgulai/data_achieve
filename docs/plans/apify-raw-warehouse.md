# Apify 本地 RAW 数据仓库建设方案

状态：待批准　｜　盘点时间：2026-10-28　｜　盘点方式：Apify API 只读实测 + 本机磁盘扫描

## 0 先读这三条

1. **数据正在过期。** 账号 `dataRetentionDays=31`。最早可见 dataset 创建于 2026-10-09，约 2026-11-09 起逐日删除。2026-09-27 之前的原始数据已经不可恢复。距首批删除还有 12 天。
2. **本机没有 Apify 原始层。** 本地有大量数据，但都是派生表或规范化副本：SI-Agent 的 `dw_video_wide`（31,316 视频）是宽表，`fact_video_comment`（46,633）是清洗后的评论，不是 Apify 原始 payload。Echo-Agent 的 DATA-MODEL 明确写「原始 payload 不落盘」。所以要建 raw 层，必须从 Apify 云端重新拉。
3. **只需要 API token，不需要登录。** 详见 §7。

## 1 现状盘点

### 1.1 Apify 云端（yueguz 账号）

| 项 | 值 |
|---|---|
| dataset 总数 | 2,349（持续增长，20 分钟内 +2） |
| item 总数 | 约 91,970 |
| 命名 dataset | 1 个（其余 2,348 个为 unnamed，受 31 天保留期约束） |
| `actId` 与 `actRunId` 均为 null | 538 个（22.9%），17,195 条 item（18.9%） |
| 最大 actor | `clockworks/tiktok-scraper`，1,301 个 dataset |
| ≤20 条的 dataset | 2,162 个（长尾极碎） |
| 10,000 条以上的 dataset | 2 个（reddit 23,241、trustpilot 20,010） |
| 保留期 | 31 天，起算点官方未文档化，按 `createdAt + 31d` 估算 |

### 1.2 本机已有数据（不能当 raw 用）

| 位置 | 内容 | 可否进 raw |
|---|---|---|
| `SI-Agent/data/warehouse/si.duckdb` | 31,316 视频、46,633 评论、101,815 tag 快照 | 否。派生宽表，无原始 payload |
| `pr-agent/data/processed/pr_intel/apify_cache` + prod 副本 | X 推文 4,592 条 / 953 unique，81 文件 | 可，标 `origin=local_cache` |
| `pr-agent-prod/artifacts/ig-probe-20260928` | IG 240 条，25 字段 | 可，标 `origin=local_probe` |
| `pr-agent-prod/artifacts/tiktok-recency-probe-20260919` | TikTok 330 条 / 266 unique | 可，同上 |
| `pr-agent-prod/artifacts/yt-sort-ab-20260919` | YouTube 240 条 / 135 unique | 可，同上 |
| `PMO/.../04_采集快照/20260816` | 372 条 provider=apify（两仓库完全重复） | 可，需先按 sha256 去重 |
| `Desktop/amazon_reviews_*.xlsx` | 193,870 行 | 否。无 Apify 元数据，单列 `local_unverified` |
| `Desktop/品类+品牌+产品名称.csv` | 58,605 行 | 否。同上 |
| `meltwater/`、`Echo-Agent/output/`、`VOC-Agent/` | 数百万行 | 否。非 Apify，不可逐条归因 |

`pr-agent` 与 `pr-agent-prod` 的探针目录是完全重复的副本，只取一份。

### 1.3 仓库基础设施

- 采集器唯一实现：`apps/api/src/data_intelligence_hub/collectors/apify_actor.py:431`，手写 httpx，只传 `limit`，上限 1000，**不传 offset**，`APIFY_TIMEOUT=30s`。直接复用会截断 reddit 大集。
- endpoint 目录：`endpoint_catalog.py:465` 的 `_APIFY_ENDPOINT_DEFAULTS`，96 个 endpoint_type → 85 个 actor（48 个 owner）。
- 现有 `raw_records` 表（Postgres）只有 `content` JSON，无 `dataset_id`/`run_id`，不能承担原始层。且当前 Docker daemon 不可达，本地无 SQL dump。
- 无 duckdb/parquet/pyarrow 依赖。系统 Python 3.14 有 duckdb 1.4.5；app venv 3.12 没有。
- 磁盘：可用 161 GiB。

## 2 结论

采用 **文件湖 + DuckDB 清单**。不引入 Postgres、不引入 Docker、不引入 pyarrow/polars。

理由：

1. 原始层要的是不可变、可重放、可字节校验。JSONL 原样落盘满足这条，写进 jsonb 不满足。
2. 当前 Postgres 不可达；为了存 92 MB 级的数据起 Docker 不值得。
3. DuckDB 直接从目录 glob 就能查，不需要 ETL 中转。

清单定位为**缓存**：能从 raw + YAML 完整重建。这一条是硬要求，验收时跑一次重建。

## 3 目录与命名

```
根：/Users/lute/data/apify-lake          # 仓库外，避免污染 git

raw/platform=<p>/data_type=<t>/dt=<YYYY-MM-DD>/actor=<owner>__<name>/dataset=<dataset_id>/rev=<NN>/
    part-00000.jsonl.zst                 # 一页一个 part，每条记录后补 \n
    meta.json                            # 列级字段指纹、行数、content_sha256、file_sha256、request_id
    input.redacted.json                  # 白名单键，或仅 sha256
    run.json  dataset.json               # API 元数据快照
    _SUCCESS                             # 行数与哈希校验通过后才写

raw_recovered/origin=<si-agent|local_cache|local_probe|local_unverified>/...   # 独立命名空间
curated/platform=<p>/data_type=<t>/dt=<dt>/actor=<owner>__<name>/mapper=<v>/part-<dataset_id>.parquet
_manifest/{catalog.duckdb, platform_map.yaml, data_type_map.yaml, mapper/}
_manifest/snapshots/catalog-<ts>.duckdb   # 供分析与 rsync 用的只读快照
_staging/  _quarantine/  _logs/
```

硬规则：

- **路径里保留 dataset_id 原始大小写。** 只对 platform 与 actor 做 slug。按原文小写化会让路径与清单对不上，APFS 大小写不敏感还可能撞目录。
- **不加 `run=` 段。** dataset_id 已唯一，run 段只是让目录数翻倍。
- dt 取 run `startedAt` 的 UTC 日期；无 run 时取 `dataset.createdAt`。dt 明确定义为「采集日（UTC）」。
- 混合类型 dataset（Reddit 同时含 post/comment/community/user）raw 记 `data_type=mixed`，curated 按 item 拆分。
- 重抓改 `rev=02`，不写 `<id>.r2`（`.` 会污染 hive 分区值）。
- `batch_id` 不进 raw 路径。

### 3.1 平台与数据类型字典

以 `endpoint_catalog.py` 的 96 个 endpoint_type 为唯一事实来源，用 `scripts/generate_platform_packages.py` 导出 `platform_map.yaml`，钉 `catalog_digest`。**不使用 `_infer_platform` 与 `_infer_record_type`。**

原因：96 个端点中 31 个的推断平台与实际不符；`_infer_record_type` 会把 9 个 product 判成 social_post。

data_type 收敛 13 值：`post / comment / product / review / account / ad / search_result / news / job / trend / ai_answer / web_page / feed`。

### 3.2 归因（最容易出错的一步）

`actor_id` 不能作为归因主键。实测 `clockworks/tiktok-scraper` 同时服务 `apify_tiktok_scraper`(post) 与 `apify_tiktok_media_profile_scraper`(account)；`apify/google-search-scraper` 服务 4 个 endpoint。

归因顺序：

1. 有 `actRunId` → 读 run 的 INPUT，与 endpoint 的 `base_input` 键集比对。
2. 有 `actId` 无 run → 查 `task_runs.logs` 里的 dataset_id 反查 `collection_task.config.endpoint_type`。
3. 两者都无（538 个）→ 按首条 item 的字段签名归类（`cid`+`videoWebUrl` → tiktok/comment；`profiles` → account 等）。
4. 失败 → `platform_unverified`，进人工队列。**禁止退回 actor 默认值。**

每条记 `endpoint_type_source`（run_input / task_log / field_signature / manual）与 `confidence`。

## 4 清单表

DuckDB 单文件，单写者，分析端只读快照。

| 表 | 关键列 |
|---|---|
| `datasets` | dataset_id, revision, account_key, run_id, act_id, actor, platform, platform_raw, data_type, content_type_raw, dt, named, created_at, modified_at, item_count_head, local_item_count, schema_hash, revision_count, expires_at（仅 unnamed，标 estimated）, status, root_path, origin, endpoint_type_source, confidence, license, terms_url |
| `runs` | run_id, act_id, status, started_at, finished_at, default_dataset_id, usage_total_usd（仅 finalized）, input_sha256, build_id, build_number, actor_name_snapshot |
| `files` | file_id, dataset_id, revision, part_index, path, row_count, bytes, content_sha256, file_sha256, schema_hash, request_id |
| `schemas` | schema_hash, act_id, endpoint_type, input_sha256, field_names, field_types, field_count, first_seen_at, last_seen_at |
| `batches` | sweep_id, batch_id, mode, started_at, heartbeat_at, finished_at, datasets_total, datasets_done, items_total, bytes_total, status, tool_version, config_sha256 |
| `checkpoints` | sweep_id, dataset_id, stage, state, part_index, offset, bytes, updated_at |
| `exceptions` | sweep_id, dataset_id, stage, error_class, http_status, request_id, message, attempts, staging_path, next_action, last_at |
| `accounts` | account_key, token_sha12, data_retention_days, last_verified_at |

视图：`v_ingest_gap`（远端有本地无）、`v_retention_risk`、`v_field_drift`、`v_content_dupes`、`v_quality_gate`。

`expires_at` 只用 `createdAt + dataRetentionDays` 估算并标 `estimated`；命名 dataset 置 NULL。API 没有 `expiresAt` 字段，也没有 `expired` 状态——到期后 dataset 直接从列表消失。

## 5 摄取流程

**阶段 0（几小时内，优先做）**：枚举 + 全量下载 + 清单。不做 parquet、不做归因、不做去重。

1. 预检：`GET /users/me` 认账号，`GET /users/me/limits` 读当前 `dataRetentionDays` 与 `maxMonthlyUsageUsd`。
2. 枚举：`GET /datasets?unnamed=1&limit=1000`，用 `(createdAt, id)` keyset 游标，**不用 offset**。列表默认升序，删除会前移元素，offset 会跳过数据。
3. 同时 `GET /actor-runs`，按 `actRunId` 关联。只对 `finishedAt != null` 的 run 落最终成本；RUNNING 标 provisional。
4. 抓取：`GET /datasets/{id}/items?format=jsonl&clean=0&limit=5000`。一页一个 part。**每条记录后补 `\n`**——实测 API 返回的 jsonl 末尾无换行，直接拼接会产生 `}{`。
5. 段内原子写：`.tmp` → fsync → rename → 校验行数与哈希 → 写 `_SUCCESS`。
6. 提交：先追加 ledger 并 fsync，再单事务写 DuckDB。

幂等点在「每个 dataset 的 revision」：`batch_id` 必须纳入 `item_count_head` 与 `modified_at`。dataset 是 append-only，同参重跑必须处理新增 item，**不能 no-op**。

重试：429 从 500ms 指数退避；5xx 重试 5 次；401 立即停并报账号。

### 5.1 抓取期间的三个坑

- `HEAD /items` 的 `X-Apify-Pagination-Total` 在写入后 5 秒内可能偏小。**以 GET 翻到空页为准**；或连续两次 HEAD（间隔 ≥5s）值不变才提交。
- 只对终态 run（SUCCEEDED/FAILED/TIMED-OUT/ABORTED）标 complete。RUNNING 的 dataset 记 partial。
- 重写 revision 前先删旧 `_SUCCESS` 并 fsync 目录，否则崩溃后留下「完整」的半份数据。

## 6 去重与 schema 漂移

raw 层不去重、不删行。唯一键是 `(dataset_id, revision, part_index)`。业务键只放 curated。

`_content_hash = sha256(platform|data_type|canonical_json)`，**不含采集时间**，只作查询辅助。

curated 按 data_type 注册：

- `entity` 类型（account、product 基础信息）：键用稳定平台 ID（不用 username），保留最新。
- `snapshot` 类型（post 指标、review 计数、商品价格）：键加 `dt`，保留多行，查询层取 latest。

`schema_hash` 采样 name + type + nullability，不只哈希字段名。同一 actor 不同 INPUT 会产生多套合法字段集（实测 `clockworks/tiktok-scraper` 的 8 个 dataset 有 6 种字段集），所以漂移键是 `(actor_id, endpoint_type, input_sha256)`，不是 `actor_id`。

Parquet 用显式 `columns=` schema，不依赖 `union_by_name` 自动推断——同名不同类型会退化成 JSON 列。mapper 升级时原子重建分区并删除旧版本，不并存两版。

## 7 凭证

**只需 API token。不需要登录、Cookie、OAuth 或 apify-client。**

请求头：`Authorization: Bearer <token>`。token 在 Apify Console → Settings → Integrations → API tokens。

要点：

- 现有 `APIFY_API_TOKEN`（`apps/api/.env:50`，账号 `yueguz`）已可用于只读回填。复用，不要再建第二份凭证文件。
- 若新建专用 token，必须是**账号级 Read**（datasets + actor-runs）。资源级只读 token 只能访问指定 dataset，全量枚举会返回空。
- `complex_homage` 账号的 key 当前 paused，需另给；不给则该账号数据不在覆盖范围内。
- 凭证只读一处来源，变量名支持 `APIFY_API_TOKEN` / `APIFY_API_KEY`。库内只存 token sha256 前 12 位。
- `PUT /users/me/limits` 是**写操作**，须用交互式全权 token，且请求体要同时带 `dataRetentionDays` 和 `maxMonthlyUsageUsd`（整体替换语义，单独传可能把消费上限重置）。数字 180 不在现行文档里，先在 Console 确认可选项。

## 8 验收

按阶段分开验，不要混。

阶段 0：

```bash
# 1 条数对账：远端 total 等于本地行数之和
duckdb _manifest/catalog.duckdb -c "SELECT count(*) FROM datasets WHERE status='complete' AND local_item_count<>item_count_head"
# 2 每片行数（不用 wc -l，jsonl 末尾无换行）
for f in $(find raw -name 'part-*.jsonl.zst'); do echo "$f $(zstd -dc $f | grep -c '^')"; done
# 3 content_sha256 复算
# 4 清单可重建：删掉 catalog.duckdb，从 raw + YAML 重建，比对行数
```

清单条数与 `GET /datasets` 返回的 total 比对时记 `as_of`，不要写死 2,349。

阶段 2 才验：缺口视图为空或仅剩已过期；漂移视图只报真事件。

## 9 分期

| 阶段 | 内容 | 时长 |
|---|---|---|
| 0 | 枚举 + 全量下载 + 清单 + 第二份副本 | 半天 |
| 1 | 归因 + curated parquet + 数据字典，先做有下游的 3-5 个类型 | 1-2 天 |
| 2 | 每日增量（launchd）+ 健康检查 + 月检脚本修复 | 2-3 天 |
| 3 | 媒体资产、C11 PII 接缝、压缩与 compaction | 按需 |

阶段 0 的产出必须在 2026-11-09 前完成。

## 10 本轮不做

- 不改 `ApifyActorCollector`，不回写 `raw_records`，不动 catalog 与 endpoint_catalog。工具是只读导出器，不进业务路由。
- 不做 S3/MinIO、服务化、调度框架。
- 不建 canonical 业务表，不动 21 张 TikTok 表。
- 不下载视频与图片（只存 URL + media manifest，CDN 会过期）。
- 不做行级 PII 脱敏（但 raw 层限 700，且打 PII 标签）。
- 不并入 Desktop Amazon、Echo-Agent Reddit、Meltwater。另设 `local_unverified` 层。
- 不自动 `PUT` 命名或延长保留期。

## 11 待你决定的四件事

1. 是否批准 `PUT /users/me/limits` 延长保留期（能多救多少取决于 Console 实际选项）。
2. 是否提供 `complex_homage` 账号 token。
3. 湖根目录定在 `/Users/lute/data/apify-lake` 还是别处（需第二块盘做副本）。
4. 阶段 1 先做哪 3-5 个 data_type（建议 tiktok/post、tiktok/comment、x/post，这三个有明确下游）。

## 附 C11/C12 冲突（不解决会返工）

- C11 冻结「原始响应 30 天」，本方案 raw 长期保留。需先声明湖是否属于 C11 的「原始响应」。属于则按 30 天清理，长期保留改存脱敏层；不属于则走正式例外审批。
- C12 删除清单未覆盖 lake 路径。需把 lake 登记进删除执行器，并按 `platform+item_id` 建源端删除台账。
- 每个 actor 的 Store 许可与平台 ToS 未随 dataset 记录。`datasets` 表已留 `license`/`terms_url` 列，首次 ingest 时快照。

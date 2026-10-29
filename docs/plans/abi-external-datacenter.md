# ABI 外部数据中心 · 建设方案

状态：待批准　｜　盘点：2026-10-28　｜　实测方式：Apify API 只读 + 本机扫描 + 临时 PG 集群跑 DDL

本方案取代 `docs/plans/apify-raw-warehouse.md`（那份是文件湖 + DuckDB，不引入 Postgres）。本轮按你的要求改为 Postgres + Docker + 看板。

---

## 0 三条先读

1. **实测规模 8,383 个 dataset、247,263 条 item。** 不是我上一轮说的 2,349，那只是 `yueguz` 一个账号。

   | 账号 | token | dataset | item | 最早 createdAt |
   |---|---|---|---|---|
   | `complex_homage` | t1–t4（同一账号） | 6,029 | 155,286 | 2026-09-25 |
   | `yueguz` | t5 | 2,354 | 91,977 | 2026-10-09 |

2. **5 个 token 只有 2 个账号。** `dataRetentionDays=31`。`complex_homage` 最早的数据今天已 33 天，实测仍可读——删除是惰性的，但随时可能清理。回填必须按 `createdAt` **从老到新**做，这是唯一正确顺序。

3. **token 暂存在 `~/.config/apify-lake/tokens.txt`（600）**，按你的要求落完数据后再由你替换。方案要求从文件读取、支持热替换，不硬编码。

---

## 1 结论

采用「**raw 窄表 + typed 视图**」为主干，嫁接三处：raw/current 双层、独立 job 容器、显式 PII 口径。

三条理由：

1. **148 个 actor、23 种字段集。** 逐 actor 建宽表要持续 DDL；窄表加视图只加注册行。
2. **不新建栈。** 复用现有 Postgres 16、compose、console、edge，只加一个 ingest 容器。
3. **raw 只追加、可重放；视图可重建。** 归因或映射写错了不丢数据。

---

## 2 架构

```
Apify API（2 账号 / 5 token，限流按账号）
   │ HTTPS
   ▼
abi-ingest（新容器，复用 api 镜像，command 改 worker）
   scheduler 02:15 CST 投 T-1 │ items 16 并发 │ 账号级令牌桶
   │ 幂等写
   ▼
Postgres 16（现有 db）
   meta  账号 / token 密文 / 作业 / 水位 / 审计
   raw   apify_item（月分区，只追加）+ 11 张本地表 + 2 张装载支撑表
   abi   目录 / item_current / 上传 / 导出 / 字段策略
   │ abi.v_* 视图（security_barrier）
   ▼
/api/abi → console /abi
```

数据流向：Apify → ingest worker → `raw.*` → `abi.item_current`（去重后最新值）→ `abi.v_*` 视图 → 看板。

---

## 3 Postgres 模型

新增 `meta` / `raw` / `abi` 三个 schema。`public` 与现有 59 条迁移不动。

四条迁移接 head `202610220059`：`202610280060`（meta）、`061`（raw + 分区）、`062`（abi + 上传导出）、`063`（视图与函数）。

**前置改动**：`apps/api/alembic/env.py` 必须加 `include_schemas=True` 与 `version_table_schema='public'`，否则 autogenerate 看不见三个新 schema，多 schema 迁移必然与模型漂移。

### 3.1 meta（11 张）

| 表 | 用途 |
|---|---|
| `apify_account` | 账号（2 行）：label、user_id、plan、retention_days、max_rps |
| `apify_token` | token 密文、sha256 指纹、last4、状态 |
| `apify_token_daily` | 按账号记账（不是按 token） |
| `actor_registry` | actor_id → 平台/类型/端点映射 |
| `actor_schema_version` | actor 字段集版本，漂移检测 |
| `ingest_job` | 作业队列，含幂等键、租约、attempts |
| `ingest_run` | 一次 sweep 的汇总 |
| `schedule_state` | 每账号目标日期水位 |
| `partition_registry` | 分区登记，驱动自动建分区 |
| `worker_heartbeat` | worker 存活 |
| `audit_log` | 审计（月分区） |

### 3.2 raw（14 + 2 张）

- `apify_dataset`、`apify_run`、`apify_item`（月分区）
- 11 张本地表（见 §7）
- `load_file`、`load_error`（装载支撑，见 §7.4）

### 3.3 abi（12 张）

`catalog_dataset`、`dataset_column`、`field_policy`、`item_current`、`record`、`upload_batch`、`upload_row`、`upload_error`、`export_job`、`saved_query`、`dataset_daily_stat`、`access_grant`、`export_policy`。

**命名注意**：用 `abi.catalog_dataset` 不叫 `abi.dataset`。仓库已有 `datasets` / `dataset_versions` / `dataset_export_jobs`（`models/dataset.py`、`routes/automation.py`），同名不同义会让 ORM、迁移、搜索全部混淆。

### 3.4 关键 DDL（已按复核修正）

```sql
CREATE SCHEMA meta; CREATE SCHEMA raw; CREATE SCHEMA abi;

CREATE TABLE meta.apify_account (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  label text UNIQUE NOT NULL,
  apify_user_id text UNIQUE NOT NULL,
  plan text,
  data_retention_days int NOT NULL DEFAULT 31,
  max_concurrency smallint NOT NULL DEFAULT 8,
  max_rps numeric(6,2) NOT NULL DEFAULT 8.0,
  enabled bool NOT NULL DEFAULT true);

CREATE TABLE meta.apify_token (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id uuid NOT NULL REFERENCES meta.apify_account(id) ON DELETE CASCADE,
  label text NOT NULL,
  token_fingerprint bytea NOT NULL UNIQUE,     -- sha256(raw token)，32 字节
  token_last4 char(4) NOT NULL,
  encrypted_payload text NOT NULL,              -- Fernet，独立 key
  key_version text NOT NULL DEFAULT 'abi.fernet.v1',
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','invalid','retired')),
  last_error_code int, last_used_at timestamptz,
  UNIQUE (account_id, label));
```

```sql
-- 分区键 = dataset 的 createdAt 月份，不可变
-- 这样同一 dataset 在任何日期重抓都落同一分区，PK 天然去重
CREATE TABLE raw.apify_item (
  collected_month date NOT NULL,          -- date_trunc('month', dataset.created_at)
  dataset_id text NOT NULL,
  item_index int NOT NULL CHECK (item_index >= 0),
  account_id uuid NOT NULL,
  platform text NOT NULL DEFAULT 'other',
  object_type text NOT NULL DEFAULT 'unknown',
  item jsonb NOT NULL,
  content_hash bytea NOT NULL,            -- sha256(canonical json)
  pii_class text NOT NULL DEFAULT 'unknown'
    CHECK (pii_class IN ('unknown','none','quasi','direct','secret')),
  fetched_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  fetch_batch_id uuid NOT NULL,
  PRIMARY KEY (collected_month, dataset_id, item_index)
) PARTITION BY RANGE (collected_month);

-- 按 dataset 取数的主路径。dataset_id 不是 PK 前导列，必须单独建
CREATE INDEX ON raw.apify_item (dataset_id, item_index);
CREATE INDEX ON raw.apify_item (platform, collected_month);
-- 不建 GIN jsonb_path_ops：查询层用 ->> 做等值/范围，该 opclass 只服务 @> @? @@，
-- 实测写了 2.6 倍成本却用不上。若将来需要，只在 abi.item_current 上按需建。
```

四条硬规则，都是复核用实测否掉的坑：

| 规则 | 不这么做的后果（实测） |
|---|---|
| `collected_month` = `date_trunc('month', dataset.createdAt)`，**不是入仓日** | 原方案 §3 写「入仓日」、§5 写「target_date」，跨天重跑同一 item 在两个分区各留一行，`DO NOTHING` 拦不住，验收只查当月看不见 |
| 分区补齐从 `min(target_date)` 到 `+3 月` | 原 `ensure_partitions(3)` 只建未来，首日回填 2026-09 直接报 `no partition of relation found`，整批回滚 |
| `fetched_at` 用 `clock_timestamp()` | `now()` 是事务开始时间，一个事务写 1,000 行只有 1 个时间戳 |
| 主键用 `bigint IDENTITY` 或 uuidv7，不用 uuid v4 | 随机索引 + WAL 膨胀，回填时放大数倍 |

### 3.5 item 形状与编码

`item` 可能是数组、字符串或 null，`jsonb NOT NULL` 拦不住。入库前必须：

1. `jsonb_typeof(item) = 'object'` 才收，否则进 `load_error`。
2. **剔除 `\u0000`**。PostgreSQL `jsonb` 拒绝 NUL 字节，Apify 文本常带，一条坏 item 会让整批 COPY 失败。
3. 统一 UTF-8、NFC 规范化；非法字节进隔离表。

### 3.6 视图

16 个 `abi.v_*`：tiktok_video、youtube_video、instagram_post、x_post、reddit_post、web_page、unclassified、amazon_review、product_catalog、pmo_record、apify_tweet、probe_instagram_post、probe_tiktok_video、probe_youtube_video、si_tiktok_comment、si_tiktok_hashtag_snapshot。

每个视图：

- 暴露 `row_key` 与 `collected_month`（后者供 API 强制范围裁剪）。
- 标 `security_barrier`，join `abi.catalog_dataset` 做授权过滤。
- 内部 `::bigint` / `::numeric` 转换一律走 `safe_cast`，坏值返回 NULL 并记 `abi.cast_error`，不让整页 500。

---

## 4 Docker

**只加一个服务** `abi-ingest`，镜像复用 `data_achieve_scrapy_api`，command 改 worker。

| 项 | 值 |
|---|---|
| 资源 | `mem_limit 3g`、`cpus 2.0`、`pids_limit 512` |
| 日志 | json-file `50m` × 5 |
| 端口 | 无 `ports:`，只 `expose`（与现状一致：全 compose 只有 expose） |
| 卷 | 复用 `scrapy_postgres_data`、`scrapy_export_data` |
| 环境 | **只有** `DATABASE_URL` + `ABI_FERNET_KEY`。不继承 api 的 `JWT_SECRET` / `PLATFORM_CREDENTIAL_MASTER_KEY` / LARK / LLM keys |

**导出拆独立容器** `abi-export`，`mem_limit 1g`。理由：02:14 一个大导出会把 ingest OOM，T-1 窗口直接丢。

db 加 `shm_size: 1gb`。

启动顺序：

```
db healthy
 → run --rm abi-migrate alembic upgrade head     # 专用 one-off service
 → up abi-ingest
 → up abi-export
 → up api console
 → restart edge
```

`abi-ingest` 启动时读 `alembic_version`，不等于 head 就退出，靠 `restart: unless-stopped` 等迁移。

**上传体积限制只放在上传的精确 location**：

```nginx
location = /api/abi/uploads/content {
  client_max_body_size 210m;
  proxy_request_buffering off;      # 缺这条会把整个 body 缓冲到容器可写层
  proxy_read_timeout 300s;
}
```

`client_max_body_size` 写在 server 级 = 任何人向任意 `/api/*`（含未认证路径）POST 210MB，打满 edge 磁盘。edge 与主机 nginx 两层都要改，只改一层不够。

---

## 5 T-1 调度

### 5.1 触发

`abi-ingest` 内 asyncio loop，每分钟判时。

**时区必须显式**。容器默认 UTC，`TZ` 没设会让整条链偏 8 小时：

- Postgres：`timezone = 'UTC'`
- `abi-ingest`：`TZ=Asia/Shanghai`
- **所有 SQL 不出现 `current_date`**，日期一律由应用算好后作为参数传入

目标日期只在 `meta.schedule_state` 一处计算：

```
target_date = (now() AT TIME ZONE 'Asia/Shanghai')::date - 1
条件：COALESCE(last_target_date, '1970-01-01') < target_date
```

`COALESCE` 不能省。`NULL < x` 结果是 NULL 不是 true，新环境没有种子行时调度永不触发。

### 5.2 幂等

| 键 | 用法 |
|---|---|
| `scan:{account}:{target_date}` | 清单扫描 |
| `items:{dataset_id}:{observed_item_count}:{modified_at}` | 逐 dataset 拉取。**必须带 revision** |
| `export:{job_id}` | 导出 |

原方案用 `items:{dataset_id}:{date}`，会挡住 09:15 sweep：某 dataset 02:20 成功，05:00 actor 又追加 5,000 条，09:15 sweep 入队同键被唯一键挡掉，追加数据当天不入仓。加 `observed_item_count` 与 `modified_at` 解决。

写 raw 用 `ON CONFLICT DO NOTHING`（稳态），提供 `--repair` 显式 `DO UPDATE`。**不要默认 `DO UPDATE`**：PG 文档明确 `ON CONFLICT DO UPDATE` 执行时会锁所有行，`WHERE` 只决定是否更新，租约过期后重叠 worker 会把等待放大到分钟级。

### 5.3 失败与重试

| 错误 | 处置 |
|---|---|
| 401 | token 进 `invalid`，换下一把 |
| 403 | **不进 invalid**，记 `last_error_code`，跳过该 dataset |
| 404 | 终态 `expired`，不重试，写 gap 并告警 |
| 429 | 读 `X-RateLimit-Reset`；缺失则指数退避 + 抖动。**不换 token** |
| 5xx | 重试 5 次 |

原方案写「401/403 都标 invalid」是错的：访问已删除的 dataset 返回 403，会把健康 token retire。

**429 换 token 是无效切换。** Apify 限流按账号，不按 token。t1→t2→t3→t4 会连续 429，四把全进 cooldown，到期同时复活再打一轮。正确做法：单账号级令牌桶，429 不改变 token 状态。

attempts 上限 6，退避 1m/5m/15m/60m/6h。租约 10 分钟，每 60 秒续租。job 加 `lease_version`，每次写都带 `WHERE lease_version = :mine`，失配中止——否则租约过期后两个 worker 同时写，旧 payload 可能覆盖新值。

### 5.4 漏跑补偿

**差 N 天就入队 N 个按日期的 scan。** 清单扫描每天只有 10 个请求，成本极低。

原方案「差 ≤7 天只补昨天」会丢掉中间日期：周五 02:15 到周一 10:00 停机，只补周日，周五周六永不执行，那两天新增的 dataset 写进周一的 `collected_month`，看板日环比失真。

### 5.5 单飞与并发

- 每账号一个 scan 单飞（部分唯一索引）。上一个 target 未终态时新 target 排队。
- claim 查询按账号剩余并发过滤（`FOR UPDATE SKIP LOCKED` + 每账号计数）。先全局 claim 再阻塞在 `Semaphore(8)` 会让 16 并发名存实亡。
- 限流桶按账号单例，不按 worker。按 worker 建 = 8 worker × 8 rps = 64 rps/账号。

### 5.6 耗时

| 阶段 | 请求数 | 估算 |
|---|---|---|
| 清单枚举 | 10（complex 7 页 + yueguz 3 页） | 秒级 |
| 首日 item 全量 | ~8,633 | 16 rps 理论 9 分钟，计入 429 与长尾 **30–45 分钟** |
| 日常增量 | ~420（只拉 `itemCount`/`modifiedAt` 变化的） | 2 分钟内 |

**不要复用现有 `_fetch_dataset_items`**（`collectors/apify_actor.py:259`）：它 `clean=1`、`limit<=1000`、**不传 offset**、`APIFY_TIMEOUT=30s`。两个 10,000 条的 dataset 只会入前 1,000 条。新写分页客户端，显式 `offset + limit`，连接超时与读超时分开，单页设字节上限。

### 5.7 三条护栏

1. 本次列举数 < `max(100, 已知 active 的 50%)` → job 失败，不标 missing。
2. 无 `actRunId` 的 dataset（1,459 个）用 `modifiedAt` + `itemCount` 连续两次（间隔 ≥5s）稳定才拉；不稳定落 `not_before`，不靠固定 sleep。
3. 健康检查加 `last_success_target_date` 与 `oldest_queued_age`。只查 DB 连通和 schema head 看不出「16 个 worker 都在 6h 退避里睡觉」。

---

## 6 账号与 token

### 6.1 建模

扫描、限流、保留期**按账号**；token 只做认证与故障切换。

| 账号 | user_id | token |
|---|---|---|
| `complex_homage` | `ofO5drbJf0BsFH2YO` | t1–t4 |
| `yueguz` | `fgLOe61icpb5nmMm5` | t5 |

**`yueguz` 与生产共用配额。** `configs/deploy/scrapy/docker-compose.yml:90` 已注入 `APIFY_API_TOKEN`，属 `yueguz`。T-1 的 t5 也是 `yueguz`，02:15 与生产采集撞同一额度。两条链路必须接同一个账号级限流器，或给入仓单独账号。

### 6.2 存放

| 位置 | 内容 |
|---|---|
| `~/.config/apify-lake/tokens.txt` | 明文，600，**只挂给 `abi-ingest`**，不挂 api/console |
| `meta.apify_token.encrypted_payload` | Fernet 密文 |
| `meta.apify_token.token_fingerprint` | `sha256(raw)`，32 字节 binary |

三条硬要求：

1. **明文文件绝不挂进 api 容器。** api 是唯一直接解析 200MB 用户上传的容器（非 root `app` 运行）。上传解析链出一次任意文件读，就从「读上传文件」升级为「Apify 账号接管」。seed 用只挂 secret 的 one-off service，或从 stdin 读。
2. **ABI 用自己的 Fernet key**（`ABI_FERNET_KEY`），不复用 `PLATFORM_CREDENTIAL_MASTER_KEY`。后者今天在 compose 的 `environment` 里，还同时解 workspace 的 TikTok cookie / X token。共享一把 key = 泄露即全解、轮换即同时打断凭证库。密文加 AAD（`account_id || label`）。
3. `retire` 时把 `encrypted_payload` 置 NULL，只留 fingerprint / last4。

### 6.3 token 范围

每个账号留 **1 把 scoped read-only**（datasets + actor-runs 读，禁写）。Apify 默认 token 是全权的，泄露后能跑 actor 花钱、改账号资源。

**资源级 scoped token 不能用于全量枚举**——只能访问指定 dataset，`GET /v2/datasets` 会返回空。

### 6.4 轮换

新 token 写入文件 → `abi_seed_tokens`（逐把 `GET /users/me`，`user_id` 与 `meta.apify_account.apify_user_id` 不匹配就整个失败）→ 观察 24h → 旧行 `retired` → 控制台删除。

**这 5 个 token 已在本轮对话明文出现，视为已泄露。** 你说落完数据再替换，那就在替换时一并：控制台吊销重建、改密码、踢会话、查近期 token 创建与消费记录——不只换 token，还要确认期间没有被跑过 actor。

---

## 7 本地数据原始表模板

全部在 `raw` schema。与 Apify raw 的区分：

- `origin` 列不同
- 本地表无 `dataset_id`
- `abi.catalog_dataset.source_kind` 分 `apify_platform` / `local_table` / `upload`

### 7.1 公共列（11 张表都带，不再重复）

```sql
load_batch_id    uuid        NOT NULL
origin           text        NOT NULL   -- si_duckdb | pr_agent_apify_cache | probe_ig
                                        -- | probe_tiktok | probe_yt | pmo_snapshot
                                        -- | desktop_xlsx | desktop_csv
src_file         text        NOT NULL   -- 相对路径或 "si.duckdb#dw_video_wide"，不存 /Users/lute
src_row_ordinal  integer     NOT NULL   -- 文件/查询结果内 0 基序号
src_pk           text                   -- 源系统主键原值
content_hash     bytea       NOT NULL   -- sha256(规范化源行)
loaded_at        timestamptz NOT NULL DEFAULT clock_timestamp()
```

PII 等级：`unknown` / `none` / `quasi` / `direct` / `secret`。`secret` 指 URL query 里的 token / signature / refresh_token——入库前只保留 `scheme://host/path`。

### 7.2 11 张表

| 表 | 来源 | 行数 | 主键 |
|---|---|---|---|
| `si_tiktok_video` | `si.duckdb#dw_video_wide` | 31,316 | `video_id` |
| `si_tiktok_comment` | `#fact_video_comment` | 46,633 | `(platform, video_id, comment_id)` |
| `si_tiktok_hashtag_snapshot` | `#fact_tag_video_snapshot` | 102,153 | `(snapshot_date, hashtag_id, video_id)` |
| `si_metric_snapshot` | `#fact_metric_snapshot` | 4,856 | `(snapshot_date, platform_code, object_type, object_id, source_actor)` |
| `apify_tweet` | pr-agent `apify_cache` | 4,592 | `(origin, src_file, src_row_ordinal)` |
| `probe_instagram_post` | `ig-probe-20260928` | 240 | `(origin, src_file, src_row_ordinal)` + `UNIQUE(short_code)` |
| `probe_tiktok_video` | `tiktok-recency-probe-20260919` | 330 | `(origin, src_file, src_row_ordinal)` |
| `probe_youtube_video` | `yt-sort-ab-20260919` | 240 | `(origin, src_file, src_row_ordinal)` |
| `pmo_collection_record` | `04_采集快照/20260816` | 394 | `record_id` + `UNIQUE(content_hash)` |
| `amazon_review` | `Desktop/amazon_reviews_*.xlsx` | 193,870 | `review_key` |
| `product_catalog` | `Desktop/品类+品牌+产品名称*.csv` | 58,605 | 代理键 + `UNIQUE NULLS NOT DISTINCT` |

### 7.3 逐表列定义

**`raw.si_tiktok_video`**（31,316 行）

```sql
video_id              text PRIMARY KEY
hashtag               text
snapshot_date         date          -- 实测 31,316 行全 NULL，不可当时间维度
rank_in_tag           integer
author_unique_id      text          -- PII direct
author_nickname       text          -- PII direct
author_id             text          -- PII quasi
descr                 text          -- PII quasi
published_at          timestamp
is_ad                 boolean
music_id              text
music_title           text
music_author          text          -- PII quasi
play_count            bigint
digg_count            bigint
comment_count         bigint
share_count           bigint
collect_count         bigint
snap_days             integer
peak_play             bigint
first_seen            date
last_seen             date
play_gain_total       bigint
play_gain_daily_avg   double precision
parse_level           text
recommendation        text
analysis_status       text
evidence_state        text
analysis_version      text
summary_original      text          -- PII quasi
target_audience       text
hook_visual           text
hook_audio            text
hook_formula          text
n_mechanisms          integer
n_timeline_segments   integer
n_transcript_segments integer
brand_borrow_n        integer
brand_replace_n       integer
analysis_created_at   timestamp
has_deepread          boolean
deepread_model        text
deepread_at           timestamp
theme_tags            text
mechanism_tags        text
life_stage            text
one_liner             text          -- PII quasi
media_playable        boolean
media_size_bytes      bigint
comment_rows          integer
comment_top_digg      bigint
built_at              timestamp
```

> `dw_video_wide` 是**派生表**，含 LLM 分析列（`summary_original`、`hook_*`、`deepread_*`）。原始事实在 `fact_tag_video_snapshot`。本表只做保真复制，分析列应另放 derived 层。

**`raw.si_tiktok_comment`**（46,633 行 / 1,473 视频 / 670 行空正文）

```sql
platform              text NOT NULL DEFAULT 'tiktok'
video_id              text NOT NULL
comment_id            text NOT NULL
parent_id             text
text                  text          -- PII quasi
digg_count            bigint
reply_count           bigint
author_handle         text          -- PII direct
author_id             text          -- PII quasi
author_avatar         text          -- PII secret（query 含 refresh_token）
liked_by_author       boolean
pinned_by_author      boolean
platform_created_at   timestamptz
fetched_at            timestamptz
source_tier           text
run_id                text
sample_rank           integer
PRIMARY KEY (platform, video_id, comment_id)
```

> 评论只覆盖 1,473 / 31,316 个视频 = **4.7%**。看板必须显示覆盖率，不能把评论数当全量。

**`raw.si_tiktok_hashtag_snapshot`**（102,153 行，2026-09-15 至 10-28，实测无重复）

```sql
snapshot_date          date NOT NULL
captured_at            timestamptz
hashtag_id             text NOT NULL
hashtag                text
source_actor           text
rank_in_tag            integer
video_id               text NOT NULL
author_id              text          -- PII quasi
author_unique_id       text          -- PII direct
author_nickname        text          -- PII direct
author_avatar_url      text          -- PII secret
play_count             bigint
digg_count             bigint
comment_count          bigint
share_count            bigint
collect_count          bigint
published_at           timestamptz
is_ad                  boolean
descr                  text          -- PII quasi
run_id                 text
cover_url              text          -- PII secret
music_id               text
music_title            text
music_author           text          -- PII quasi
music_duration_sec     integer
music_is_original      boolean
music_is_commerce      boolean
hashtags               text[]
PRIMARY KEY (snapshot_date, hashtag_id, video_id)
```

**`raw.si_metric_snapshot`**（4,856 行，无 PII）

```sql
snapshot_date   date NOT NULL
captured_at     timestamptz
platform_code   text NOT NULL
object_type     text NOT NULL
object_id       text NOT NULL
view_count      bigint
like_count      bigint
comment_count   bigint
share_count     bigint
collect_count   bigint
source_actor    text NOT NULL
run_id          text
PRIMARY KEY (snapshot_date, platform_code, object_type, object_id, source_actor)
```

**`raw.apify_tweet`**（4,592 条 / 953 unique / 24 种字段集 / 另有 76 条 `{"noResults":true}` 哨兵）

```sql
snapshot_date          date NOT NULL          -- 从文件名日期取
tweet_id               text NOT NULL
conversation_id        text
author_id              text                   -- PII quasi
author_user_name       text                   -- PII direct
author_name            text                   -- PII direct
author_followers       bigint
author_verified        boolean
author_description     text                   -- PII quasi（可能含邮箱）
author_location        text                   -- PII quasi
created_at             timestamptz
full_text              text                   -- PII quasi
lang                   text
like_count             integer
reply_count            integer
retweet_count          integer
quote_count            integer
bookmark_count         integer
view_count             bigint
is_reply               boolean
is_quote               boolean
is_retweet             boolean
is_pinned              boolean
possibly_sensitive     boolean
in_reply_to_id         text
in_reply_to_user_id    text
in_reply_to_username   text
quoted_id              text
hashtags               text[]
urls                   jsonb
media                  jsonb
is_no_results          boolean NOT NULL DEFAULT false
raw                    jsonb NOT NULL       -- PII direct（含 author.* 全量）
PRIMARY KEY (origin, src_file, src_row_ordinal)
```

索引：`(tweet_id, snapshot_date)`。`text` 与 `full_text` 实测重复，只留 `full_text`。

**`raw.probe_instagram_post`**（240 行，`short_code` 全唯一）

```sql
probe_date          date NOT NULL
short_code          text NOT NULL
post_id             text NOT NULL
post_type           text
url                 text
input_url           text
caption             text                   -- PII quasi
owner_id            text                   -- PII quasi
owner_username      text                   -- PII direct
owner_full_name     text                   -- PII direct
posted_at           timestamptz
likes_count         integer
comments_count      integer
video_view_count    integer
video_duration      double precision
dimensions_width    integer
dimensions_height   integer
display_url         text                   -- PII secret
video_url           text                   -- PII secret
images              jsonb                  -- PII secret（CDN 签名）
child_posts         jsonb
latest_comments     jsonb                  -- PII direct
first_comment       text                   -- PII quasi
hashtags            text[]
mentions            text[]
tagged_users        jsonb                  -- PII direct
location_id         text
location_name       text                   -- PII quasi
music_info          jsonb
paid_partnership    boolean
product_type        text
is_pinned           boolean
raw                 jsonb NOT NULL         -- PII direct
PRIMARY KEY (origin, src_file, src_row_ordinal)
```

**`raw.probe_tiktok_video`**（330 行 / 266 unique / A-B-C 三臂）

```sql
probe_date                date NOT NULL
arm                       text NOT NULL       -- A | B | C
video_id                  text NOT NULL
text                      text                -- PII quasi
create_time               bigint              -- 原始 Unix 秒
create_time_iso           timestamptz
web_video_url             text
search_query              text
author_id                 text                -- PII quasi
author_name               text                -- PII direct
author_nickname           text                -- PII direct
author_signature          text                -- PII direct（PII 最集中，可含邮箱/电话）
author_fans               bigint
author_following          bigint
author_heart              bigint
author_verified           boolean
author_avatar_url         text                -- PII secret
author_bio_link           text                -- PII quasi
author_profile_url        text
author_private            boolean
music_id                  text
music_name                text
music_author              text                -- PII quasi
music_original            boolean
music_play_url            text                -- PII secret
music_cover_url           text                -- PII secret
video_height              integer
video_width               integer
video_duration            integer
video_definition          text
video_format              text
video_cover_url           text                -- PII secret
video_cover_original_url  text                -- PII secret
transcription_link        text
play_count                bigint
digg_count                bigint
comment_count             bigint
share_count               bigint
collect_count             bigint
repost_count              bigint
is_ad                     boolean
is_sponsored              boolean
is_pinned                 boolean
is_slideshow              boolean
is_story                  boolean
is_muted                  boolean
location_created          text                -- PII quasi
hashtags                  jsonb
mentions                  jsonb
detailed_mentions         jsonb
effect_stickers           jsonb
media_urls                jsonb
slideshow_image_links     jsonb
has_tiktok_shop_product   boolean
comments_dataset_url      text
raw                       jsonb NOT NULL      -- PII direct
PRIMARY KEY (origin, src_file, src_row_ordinal)
```

> 该批数据已带 `{{EMAIL_...}}`、`{{SECRET_...}}` 占位符。**保留占位符，不要回填原文。**

**`raw.probe_youtube_video`**（240 行 / 135 unique / A-B 两组）

```sql
probe_date              date NOT NULL
arm                     text NOT NULL       -- A | B
video_id                text NOT NULL
title                   text                -- PII quasi
description             text                -- PII quasi
url                     text
from_yt_url             text
channel_id              text                -- PII quasi
channel_name            text                -- PII direct
channel_username        text                -- PII direct
channel_url             text
number_of_subscribers   bigint
published_at            timestamptz         -- 源字段 date
duration                text                -- 源为 "00:14:38"
view_count              bigint
likes                   bigint
comments_count          bigint
comments_turned_off     boolean
is_members_only         boolean
is_paid_content         boolean
is_monetized            boolean
hashtags                text[]
description_links       jsonb
thumbnail_url           text
order_index             integer             -- 源字段 order
input                   text
video_type              text                -- 源字段 type
translated_title        text                -- PII quasi
translated_text         text                -- PII quasi
ai_video_summary        text
ai_video_description    text
collaborators           jsonb
subtitles               jsonb
transcription_url       text
location                text                -- PII quasi
raw                     jsonb NOT NULL      -- PII direct
PRIMARY KEY (origin, src_file, src_row_ordinal)
```

**`raw.pmo_collection_record`**（394 行，5 种 `schema_version`）

```sql
record_id        uuid PRIMARY KEY
project_id       uuid
workspace_id     uuid
source_id        uuid
task_run_id      uuid
record_type      text
source_url       text
screenshot_url   text          -- PII secret
collected_at     timestamptz
created_at       timestamptz
snapshot_date    date NOT NULL -- 2026-08-16
schema_version   text NOT NULL
provider         text          -- apify | generic_web | public_feed
platform         text
actor_id         text
content_text     text          -- PII quasi
content          jsonb NOT NULL -- PII direct（IG profile 含 username/fullName/biography）
```

`schema_version` 分布：`apify_social_post.v1` 260、`apify_twitter_post.v1` 101、`generic_web.v1` 20、`apify_instagram_profile.v1` 11、`public_feed.v1` 2。

`content` 是 **JSON 对象**，不是 Python dict repr（上一版方案写错了）。`raw_L0056.json` 已损坏（unterminated string at char 3539），装载时写 `load_error` 并继续，不中止整批。

**`raw.amazon_review`**（193,870 行 / 1,206 ASIN / 116 行空正文）

```sql
review_key         bytea PRIMARY KEY   -- md5(asin|作者|日期|标题|正文)
file_date          date NOT NULL       -- 2026-08-14
asin               text NOT NULL
rating             smallint CHECK (rating BETWEEN 1 AND 5)
title              text                -- PII quasi
body               text                -- PII quasi（可含健康/家庭信息）
author             text                -- PII direct
review_date        date
verified_purchase  boolean
helpful_votes      integer
total_votes        integer
source_description text                -- PII quasi
```

入库前统一解码 HTML 实体（`&#39;` → `'`、`&nbsp;` → 空格）、去 NBSP、去 BOM、全角转半角。

无原生评论 id。`review_key` 实测覆盖全部 193,870 行无重复；仅三元组有 103 条重复。

**`raw.product_catalog`**（58,605 行，无 PII）

```sql
product_key    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
file_date      date NOT NULL          -- 2026-08-14
category       text                   -- 空 3,036 行
brand          text                   -- 空 1 行
product_name   text                   -- 空 17,128 行（29.2%）
UNIQUE NULLS NOT DISTINCT (category, brand, product_name)
```

`NULLS NOT DISTINCT` 不能省，否则 17,128 个 NULL 商品名去重不掉。

### 7.4 两张装载支撑表

```sql
-- 解决"源文件删除后不可重放"
CREATE TABLE raw.load_file (
  file_id        uuid PRIMARY KEY,
  origin         text NOT NULL,
  source_path    text NOT NULL,      -- PII quasi，尽量存相对路径
  storage_path   text NOT NULL,      -- 归档后的实际路径
  sha256         bytea NOT NULL UNIQUE,
  size_bytes     bigint NOT NULL,
  mtime          timestamptz,
  rows_total     integer,
  rows_loaded    integer,
  rows_rejected  integer,
  status         text NOT NULL,      -- pending | loaded | partial | failed
  loaded_at      timestamptz);

-- 拒收行。只存定位信息，不存原始 PII
CREATE TABLE raw.load_error (
  load_batch_id    uuid NOT NULL,
  origin           text NOT NULL,
  src_file         text NOT NULL,
  src_row_ordinal  integer NOT NULL,
  column_name      text,
  rule_id          text,
  message          text);
```

`raw.load_error` **不存原始值**。用户上传含卡号的文件被拒时，卡号不能落在错误表里。错误报告可下载 CSV，只含 `(行号, 列, 规则)`。

### 7.5 跨源实体

同一条 TikTok 视频在 SI duckdb（`video_id`）、Apify（`id`）、探针（`id`）里编号不同，16 个视图无法 join。需要 `abi.platform_object` 规范 ID 表，本地表与 `item_current` 共用 `row_key`。

快照与最新值不能混用：`fact_*_snapshot` 是日快照，`item_current` 是最新值。视图加 `snapshot_kind` 列与 `as_of` 参数。

时区统一：DuckDB `TIMESTAMP` 无时区，IG/YT 是 ISO UTC，TikTok 同时有 `createTime` 与 `createTimeISO`。入仓统一 `timestamptz` 并记录原始假设。

---

## 8 ABI 看板

console 新增 `/abi`：总览、目录、查询、上传、导出、管理。API 为 `/api/abi`。

### 8.1 授权（原方案的最大缺陷）

原方案用 `get_authenticated_context`（`api/deps.py:92`），它只证明「已登录 + 有 workspace」，**不做 grant 判断**。结果：任一登录用户可枚举/查询全量 dataset。

修正：

1. ABI 所有表加 `workspace_id`，与现有 `raw_records`、`datasets` 一致。
2. 所有端点过 `require_dataset_role(min_role)`，按 `workspace_id + grant` 双条件取数。无显式 grant 一律 deny。
3. 视图标 `security_barrier` 并 join `abi.catalog_dataset`；查询 builder 强制注入不可移除的 `dataset_id = :granted_id`。
4. 用户移出 workspace 时 `access_grant` 级联回收。

### 8.2 查询

`POST /api/abi/datasets/{slug}/query`

- 列与过滤列**只从服务端物理列 allowlist 取**，统一 `quote_ident`。`abi.dataset_column` 是数据，用户上传的 CSV 表头会流进它——只靠它做白名单等于把列名当可信输入。
- op 白名单。
- keyset cursor，HMAC 签名，绑定 `{dataset_id, user_id, columns_hash, filters_hash, order, last_key, exp}`。不用 offset。
- 只读事务 + `statement_timeout 15s` + `idle_in_transaction_session_timeout 60s`。
- 分页用 `REPEATABLE READ` 单事务，避免翻页期间 02:15 ingest 提交导致重复/漏行。
- `total_estimate` 读 `dataset_daily_stat`，不跑 count。
- `secret` 列永不返回；`unknown` 列默认拒绝。

限流：每用户并发 1，ABI 全局查询池 ≤4，`work_mem` 上限。不做的话一个 viewer 循环发 15s 重查询就能打满共享库，主产品采集一起变慢。

### 8.3 上传

`POST /uploads` → `PUT content` → `POST commit`（三步）

- batch token 绑定 `(user, dataset, expected_sha256, expected_rows, expires)`，一次性。
- commit 必须复核 sha256、行数、清单。
- 流式写 `/app/exports/abi/_uploads/{batch_id}/`，边写边算 sha256，上限 200MB / 50 万行。
- 先校验后写：表头对齐、类型、必填、主键重复、PII 扫描。命中信用卡或私钥直接拒行。
- 模式 `append` / `upsert` / `replace`。**`replace` 写新版本并切指针，保留旧版本与 restore**，且要求 publisher 权限。不可逆清空是真实事故场景。
- 大文件按 10k 行/事务分批 + `COPY`，不要整批一个事务（50 万行单事务在共享 OLTP 库上产生长事务、WAL 尖峰、锁等待）。

### 8.4 导出

`POST /exports` 建异步 job，`abi-export` 容器写文件，7 天过期，过期 410。

- 格式 csv / xlsx / jsonl。xlsx 用 `xlsxwriter` 的 `constant_memory`，openpyxl 全量加载 50 万行会 OOM。
- 默认 `mask_pii`。
- 关遮罩：publisher 权限 + reason ≥10 字 + **申请人 ≠ 审批人**。单人自批只是自证，不是控制。
- 超过 N 行即使 masked 也要审批。`author_id` + 时间 + 部分 handle 足以重识别。
- CSV 注入处理五种前缀 `= + - @ \t \r`，不只四种。文档写明数据变形方式。
- 下载按 `(job_id, workspace_id, created_by or grant)` 取 job，校验 `expires_at`；`Path.resolve().relative_to(abi_export_root)` 不通过就 404。仓库现有正面样本：`services/automation_service.py:5176-5208`。
- 审计写创建/审批/下载三条，`detail` 存 HMAC 后的 `filters_hash`，不存值。裸 sha256 对邮箱、handle 这类低熵值可被字典反查。
- `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`。

**ABI 导出目录在现有 retention 根之外。** 现有清理（`maintenance/public_content_retention.py:443-470`）只扫 `/app/exports/datasets`，且会把越界路径记成 violation。ABI 需要独立 retention worker，按 `expires_at` unlink，复用 `relative_to(root)` 约束。

### 8.5 PII 策略

原方案 `pii_class DEFAULT 'none'` 是 **fail-open**：分类器漏判时默认不遮罩。

修正：

1. 默认改 `unknown`。导出与视图默认拒绝 `unknown`。
2. ingest 时按字段名/正则 deny-by-default 分类。Apify 的 PII 在 `item jsonb` 里是字段级，不是列级。
3. 遮罩在 **API 序列化层**执行，不在前端。前端做等于 curl 直接拿明文。
4. `abi.field_policy(dataset_id, field_path, pii_class, mask_rule)` 统一覆盖 Apify / 本地 / 上传三类来源。11 张本地表才是最大的 PII 面（`amazon_review` 19 万行含评论者姓名，`si_tiktok_comment` 4.6 万行含 handle 与正文）。
5. `pii_class` 由系统分类器写，人和 API 都不得降级。
6. dataset 注册与 `field_policy` 只允许 admin/publisher；`source_table` 只从服务端 allowlist 取。否则 editor 建个 dataset 成为 owner=admin，再把字段标成 `none` 就能导出全量 PII。

### 8.6 数据库角色

当前 `DATABASE_URL` 用 `SCRAPY_POSTGRES_USER`，官方镜像把它建成**超级用户**。任一 SQL 注入就不只是读 ABI 表，而是全库 + `meta.apify_token` 密文 + `COPY ... FROM PROGRAM` + DROP 分区。

拆三个 role：

| role | 权限 |
|---|---|
| `abi_migrator` | DDL |
| `abi_ingest` | `meta`/`raw` 写 |
| `abi_api` | 只 SELECT 视图 + 写 upload/export 表 |

`REVOKE ALL ON meta.apify_token FROM abi_api`。

生产还应关掉 `/docs`、`/redoc`、`/openapi.json`（`main.py:156-161` 目前无条件启用）。

---

## 9 执行路径

### 9.1 首日回填

```bash
colima start                       # 本机 Docker daemon 当前不可达

docker compose -f configs/deploy/scrapy/docker-compose.yml \
  run --rm abi-migrate alembic upgrade head

# 分区按最早 target 补齐，不是只建未来 3 个月
docker compose ... run --rm abi-ingest \
  python -m data_intelligence_hub.abi.ensure_partitions --from 2026-09-01 --to +3mo

# seed token（逐把 GET /users/me 校验 user_id）
docker compose ... run --rm abi-seed \
  python -m data_intelligence_hub.maintenance.abi_seed_tokens \
  --from-file /run/secrets/abi_apify_tokens

# 本地数据入库
docker compose ... run --rm abi-seed \
  python -m data_intelligence_hub.maintenance.abi_load_local \
  --source si_duckdb --execute

# Apify 回填：按 createdAt 从老到新（complex_homage 最早 09-25，优先）
docker compose ... run --rm abi-ingest \
  python -m data_intelligence_hub.abi.backfill \
  --account all --order created_at_asc --execute
```

### 9.2 日常

```
02:05  建分区（未来 3 个月滚动）
02:15  scan:{account}:{yesterday} → items:{dataset_id}:{count}:{modified_at}
09:15  sweep 补凌晨后新增
```

---

## 10 验收

```sql
-- 1 分区数（预建 2026-09 至未来 3 月，不是固定 12）
SELECT count(*) FROM pg_inherits WHERE inhparent = 'raw.apify_item'::regclass;

-- 2 清单与实测对账（用回填当天 as_of，不写死 8383）
SELECT count(*) FROM raw.apify_dataset;

-- 3 item 总数（不写死 247263）
SELECT count(*) FROM raw.apify_item;

-- 4 同一 dataset 每个 index 只有一行
SELECT count(*) FROM (
  SELECT dataset_id, item_index FROM raw.apify_item
  GROUP BY 1,2 HAVING count(*) > 1) t;          -- 必须为 0

-- 5 重跑不增（按目标日期范围，不是 date_trunc 等值）
SELECT count(*) FROM raw.apify_item
 WHERE collected_month >= :target_month_start
   AND collected_month <  :target_month_end
   AND fetch_batch_id = :first_batch;            -- 与首跑一致

-- 6 保留期风险
SELECT count(*) FROM raw.apify_dataset
 WHERE status='active' AND retention_deadline < CURRENT_DATE + 3;

-- 7 本地表行数
SELECT 'amazon_review', count(*) FROM raw.amazon_review
UNION ALL SELECT 'product_catalog', count(*) FROM raw.product_catalog
UNION ALL SELECT 'si_tiktok_comment', count(*) FROM raw.si_tiktok_comment;
```

> 原方案第 5 条用 `collected_month = date_trunc('month', current_date)`，这是 date 列与「月初那一天」的等值比较，不是月范围。实测 52,003 行的表该语句返回 **0**——永远「通过」。必须改成范围。

```bash
curl -s localhost:8000/api/health | jq -r .schema_revision   # = head
python -m data_intelligence_hub.abi.healthcheck; echo $?      # 0
```

健康检查必须包含 `last_success_target_date` 与 `oldest_queued_age`，不能只看连通性。

---

## 11 风险

| 风险 | 处置 |
|---|---|
| 31 天保留期，09-25 的数据随时被删 | 回填当天完成，按 `createdAt` 升序 |
| `unnamed=1` 漏掉命名 dataset（yueguz 1 个） | 不带 `unnamed` 过滤，或用 `named` 列标记 |
| offset 分页在删除时会跳 dataset | `(createdAt, id)` keyset 游标，结束前用 total 对账 |
| 1,459 个 dataset 无 `actId`/`actRunId` | 按字段形状分类，落 `other` 并在 UI 标注 |
| 5 个 token 已泄露 | 落完数据后立即轮换 + 查审计 |
| Docker daemon 不可达 | `colima start` |
| 本地 PG15、生产 PG16 | 迁移两边都跑 |
| 无定时备份，raw 不可再生 | 每日 pg_dump，加密，存另一台机器 |
| 单库共享 I/O | 查询只读事务 + 15s 超时 + 并发上限 |

## 12 本轮不做

- 不做文件湖 / DuckDB 查询层（上一版方案作废）。
- 不做任意 SQL 端点；`saved_query` 只存结构化 `{column, op, value}`。
- 不做 parquet 导出（需 pyarrow）。
- 不引入 S3 / MinIO，先用本地卷。
- 不重跑 actor 补数，只读已有 dataset。
- 不复用 `raw_records`（工作流溯源表，`content` 是 json，无 `dataset_id`）。
- 不在 `apps/web` 建页面（edge 不路由到它）。
- 不下载视频与图片，只存 URL + media manifest。
- 不做实时流，只做 T-1。

## 13 待你决定

1. **`yueguz` 与生产共用配额。** T-1 的 t5 和生产采集撞同一账号。是给入仓单独一个账号，还是共用并接统一限流器？
2. **回填窗口。** 是否现在就跑首日回填（需要 `colima start`）？`complex_homage` 最早数据已 33 天。
3. **ABI 的 workspace 归属。** 现有业务表都带 `workspace_id`，ABI 数据挂哪个 workspace？
4. **看板先做哪个模块。** 建议先做查询（只读、风险最低），上传和导出后置。

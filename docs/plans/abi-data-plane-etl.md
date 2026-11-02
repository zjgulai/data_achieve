# ABI 数据面 ETL 方案（2026-11-02 拍板）

- 状态：已拍板，待实施
- 决策：本地快照 ETL 进应用库（生产 PG16 的 `abi` schema）；分析型临时查询可读外部仓
- 依据：[NB-2026-11-02-next-batch](../tickets/NB-2026-11-02-next-batch.md) §0.1；[ABI 外部数据中心](./abi-external-datacenter.md)
- 不在范围：实时同步、双写、把外部仓当生产读库

## 1. 为什么要做

当前是两套库：

| 库 | 位置 | 内容 | 谁在用 |
|---|---|---|---|
| 本地快照 | PG18.6，`meta`/`raw`/`public` | SOP 记录 23 表、726,499 行；报告用到 5 表、186,352 行 | 分析脚本、爆款报告 |
| 应用 ABI | 生产 PG16，`meta`/`raw`/`abi` | 48 表/766 字段（应用侧） | `/abi` 看板、查询、上传、导出 |

结果：看板看不到真实数据；报告基于本地快照；两边口径无法对账。ETL 把快照的可信子集搬进应用库，让看板、查询、导出、报告共用一套数据。

## 2. 第一切片

只搬报告用到的 5 张表：

| 源表 | 行数（manifest） | 目标 dataset slug | 主键/去重 |
|---|---:|---|---|
| `raw.si_tiktok_video` | 31,366 | `si_tiktok_video` | `video_id` |
| `raw.si_tiktok_comment` | 47,073 | `si_tiktok_comment` | `comment_id` |
| `raw.si_tiktok_hashtag_snapshot` | 102,153 | `si_tiktok_hashtag_snapshot` | `(hashtag, snapshot_date)` |
| `raw.si_metric_snapshot` | 4,856 | `si_metric_snapshot` | `(video_id, snapshot_at)` |
| `raw.si_author_video_snapshot` | 904 | `si_author_video_snapshot` | `(author_id, video_id)` |

合计 186,352 行。第二切片再搬其余表。

## 3. 步骤

### 3.1 盘点与映射

1. 读源库 `information_schema.columns`，导出每表列名、类型、可空、样例。
2. 对照 `docs/plans/abi-schema-manifest.md`，确定目标 `data_type`：
   - `jsonb` 列标 `json`；数组标 `array`；时间标 `timestamptz`。
   - 计数列标 `bigint`；金额列标 `numeric`。
3. 生成 `configs/abi/etl-map-<date>.json`：源表、目标 slug、列映射、主键、PII 初判。

### 3.2 建 dataset 与 PII 策略

1. 用 `POST /api/abi/datasets` 建 dataset；`columns` 只传 `AbiColumnCreate` 允许的字段。
2. **先设 PII 策略再加载**：`pii_class` 默认 `unknown`，未分类列在未遮罩导出时会被拒绝。
3. 初判规则：
   - `author_id`、`username`、`avatar_url` → `quasi` 或 `direct`。
   - 文本正文、评论正文 → `unknown`，人工确认后再降级。
   - 计数、时间、标签 → `none`。
4. 策略变更走 `replace_abi_policy`，需要 admin + 理由。

### 3.3 导出

1. 从 PG18.6 只读导出，按主键排序，分块 10,000 行。
2. 清洗：
   - 去掉 `\u0000`（Postgres text 不接受 NUL）。
   - `jsonb` 列先 `jsonb_typeof` 检查；`item` 非 object 的整行隔离到 `etl_reject`。
   - 时间统一 UTC；不用 `current_date`。
3. 输出 JSONL（保留类型）与 CSV（人工核对）各一份，写 SHA-256 与行数。
4. 落 `tmp/abi-etl/<date>/`，不提交原始数据。

### 3.4 加载

优先走上传闭环，复用现有代码：

```text
create_abi_upload -> write_abi_upload_content -> commit_abi_upload
```

- `mode=upsert`，按主键去重。
- 每批记录 `expected_rows`、`expected_sha256`。
- 失败批次保留 `failed`，可重试；不整批回滚已成功批次。

第二选择：直接 `COPY` 到 `raw.apify_item` + typed 视图，仅当上传闭环吞吐不够。走这条要先写 ADR。

### 3.5 验收

| 检查 | 通过条件 |
|---|---|
| 行数 | 5 张表逐表与源一致；总 186,352 |
| 校验 | 每批 SHA-256 一致；抽样 100 行逐列比对 |
| 幂等 | 同一批重跑两次，行数不变 |
| PII | `unknown` 列未遮罩导出被拒绝；`direct` 列导出为 `***` |
| 查询 | `/abi` 看板显示 5 个 dataset 与真实行数 |
| 导出 | 一次 CSV 导出成功，行数与筛选条件一致 |
| 报告 | 爆款报告可从 ABI 查询结果重算，数字与当前报告一致 |

### 3.6 回滚

- 源库不动；目标 dataset 用版本号管理。
- 失败时把新 dataset 标 `is_current=false`，保留旧版本；不删数据。
- 上传批次失败可重试；已成功批次不回滚，除非行数或校验不符。

## 4. 风险

| 风险 | 处理 |
|---|---|
| NUL 字节 | 导出前剔除；整行隔离并计数 |
| `jsonb` 非 object | `jsonb_typeof='object'` 检查；否则进 reject |
| 时区漂移 | 应用算好时间传入；SQL 不用 `current_date` |
| PII 误判 | 默认 `unknown`；先 fail-closed，再人工降级 |
| 大表耗时 | 分块 + 断点续传；先 5 表，再其余 |
| 应用库膨胀 | 先算行数与索引大小；必要时按月分区 |
| 双库口径 | 验收时写清「源库快照日期 + 目标库加载时间」 |

## 5. 时间与负责人

| 步骤 | 预计 | owner |
|---|---|---|
| 盘点与映射 | 0.5 天 | Pray |
| 建 dataset 与策略 | 0.5 天 | Pray |
| 导出与清洗 | 1 天 | Pray |
| 加载与重试 | 0.5 天 | Pray |
| 验收与报告重算 | 0.5 天 | Pray |

合计 3 天。第一切片通过后再评估其余 18 张表。

## 6. 2026-11-02 实施记录（第一切片）

源数据不在本地 `abi_migtest` 容器（已不存在），而在 `~/data/apify-lake/local/si_duckdb/` 的 5 个 `.jsonl.zst` 抽取，行数与计划一致：31,366 / 47,073 / 102,153 / 4,856 / 904。

实际工作区不是 `data_scrapy`，而是生产 A 的 `zhoujianaaa123`（owner `zhoujianaaa123@gmail.com`）。`data-achieve-demo` 是演示库，`abi-e2e-*` 是测试库，都不要装生产数据。

装载器 `scripts/abi_etl_load.py` 复用 ABI 上传闭环。实施中修掉四个真实缺陷：

1. **JSONL 少计一行。** 上传服务按「表头 + 数据行」计数并固定减 1；JSONL 没有表头，`expected_rows` 永远差 1，提交报 `abi_upload_expected_rows_mismatch`。改用 CSV（表头 + 数据行）。
2. **默认主键是第一列。** 快照表第一列 `snapshot_date` 重复，99 行里 97 行被判 `primary_key_duplicate`。`commit_abi_upload` 增加 `primary_key_columns`；第一切片用复合键：
   - `si_tiktok_video`：`video_id`
   - `si_tiktok_comment`：`comment_id`
   - `si_tiktok_hashtag_snapshot`：`(snapshot_date, hashtag, video_id)`
   - `si_metric_snapshot`：`(snapshot_date, object_type, object_id, captured_at)`
   - `si_author_video_snapshot`：`(snapshot_date, account_handle, video_id)`
   已在源数据逐表验证唯一。
3. **旧主键索引不会自动消失。** 第一次用默认主键建表后，再传复合主键，旧的 `(__abi_version, snapshot_date)` 唯一索引仍在，插入仍失败。第一切片删除旧的单列唯一索引后重建复合索引。产品侧后续应在 `_ensure_upload_table` 里对主键变更做显式迁移。
4. **asyncpg 参数上限。** `MAX_BIND_PARAMETERS` 原为 60,000，但 asyncpg 上限是 32,767；4,856 行 × 12 列的语句在 commit 阶段报 `the number of query arguments cannot exceed 32767`。改为 30,000，并按列宽切分语句。
5. **信用卡扫描误伤公开 ID。** `author_id`、`video_id`、`hashtag_id` 是 16-19 位裸数字，偶尔通过 Luhn；`author_nickname` 的 `user<13位>` 与头像 URL 也会命中。186,352 行扫描原有 194 次误伤。修复：正则边界排除字母前缀；`*_id`/`*_uid`/`*_handle`/`*_avatar`/`*_url` 列跳过卡扫描；正文列仍扫描。修复后全量扫描 0 命中。

冒烟结果：`si_metric_snapshot` 99 行、0 拒绝、`committed`。

**2026-11-02 全量结果（生产 A，workspace `zhoujianaaa123`）：**

| dataset | 行数 | 拒绝 |
|---|---:|---:|
| `si_tiktok_video` | 31,366 | 0 |
| `si_tiktok_comment` | 47,073 | 0 |
| `si_tiktok_hashtag_snapshot` | 102,153 | 0 |
| `si_metric_snapshot` | 4,856 | 0 |
| `si_author_video_snapshot` | 904 | 0 |
| **合计** | **186,352** | **0** |

验收：`abi.catalog_dataset.row_count` 与 5 张物理表的当前版本计数逐表一致；PII 策略已写入（`author_id`/`author_unique_id` 等 `quasi+hash`，昵称/头像 `direct+redact`，正文与计数 `none`）。读路径实测：`run_query_page` 返回 3 行，`author_id` 为 32 位哈希，`author_nickname` 为 `***`，`descr` 保持明文。B 代码已升级到 `144d7f2`。2026-11-02 已在 B 创建同名 workspace，复制 A 的 owner 与成员关系，并用同一脚本装载同一批数据：5 表 / 186,352 行 / 0 拒绝。`abi.catalog_dataset.row_count` 与物理表当前版本逐表一致；当前版本内容哈希与 A 全部一致（`si_metric_snapshot` 的版本号 A=4、B=2，数据相同；A 的旧版本行仍留在物理表）。B 读路径实测：`author_id` 为 32 位哈希，`author_nickname` 为 `***`，`descr` 保持明文。5 个 dataset 各有 1 条 owner admin grant。

相关修复已提交：`4b303a6`（PII 误伤）、`321b23b`（asyncpg 参数上限）、`de14840`（复合主键 + CSV）。ETL 脚本：`scripts/abi_etl_load.py`。

### 6.1 导出终态验收（2026-11-02）

A/B 各做两条导出，均通过：

| 路径 | 结果 |
|---|---|
| 未遮罩 `si_metric_snapshot`（`object_id`, `view_count`） | 创建 → `awaiting_approval` → 审批 → `queued` → worker `succeeded`；4,856 行 / 103,721 字节 |
| 遮罩 `si_tiktok_video`（`video_id`, `author_id`, `author_nickname`） | 同步 `succeeded`；31,366 行 / 1,787,894 字节 |

- 未遮罩 job：A `7f54b8f9…`、B `245361ce…`。遮罩 job：A `c223cd86…`、B `1864aaca…`。
- 未遮罩产物 SHA-256 `f04ae81e…`；遮罩产物 SHA-256 `27922fdb…`；A/B 字节一致。
- 遮罩检查：`author_id` 32 位十六进制哈希，`author_nickname` 为 `***`，`video_id` 保留。
- worker 心跳：A/B `abi-export` 均 < 180 秒；B 当次 note 为 `export claimed=1 ok=1 failed=0 skipped=0`。
- 测试用 publisher grant 已在 A/B 撤销；导出 job 与产物保留作审计证据，按 TTL 过期。

## 7. 2026-11-02 T-1 扫描试点

- 目标日期：2026-11-01（北京时间）；账号 `complex_homage`（token 文件 t1）。
- 结果：**131 个 dataset / 4,163 条 item**。
- `raw.apify_dataset`：131 行，`item_count_head=item_count_local=4,163`。
- `raw.apify_item`：4,163 行；分区 `2026-10` 2,609 行、`2026-11` 1,554 行。
- 命令：`python -m data_intelligence_hub.abi.ingest --scan-once --target-date 2026-11-01`；token 通过 stdin 传入，不落盘。
- 自动队列：`drain_scan_queue` 已实现并用 2 个 `scan` job 验证；complex_homage 与 yueguz 均 `succeeded`，心跳 `scan claimed=2 ok=2 failed=0 skipped=0`，`schedule_state` 两账号 `last_target_date=2026-11-01`。
- per-account token：A 已种子化 5 条（`complex_homage` 4、`yueguz` 1），Fernet 加密，`ABI_FERNET_KEY` 已配置。
- actor 归因：`meta.actor_registry` 已种子化 9 个 actor，131 个 dataset 全部回填；分布 tiktok/post 40、youtube/post 32、x/post 24、instagram/post 16、tiktok/hashtag 16、reddit/post 3；`endpoint_source='unknown'` 为 0。脚本 `scripts/seed_abi_actor_registry.py`。
- 多日补扫：`backfill_dates` 按 `schedule_state.last_target_date` 补齐缺失日期，最多 7 天；`enqueue_scan_job` 过滤已成功账号；`schedule_state` 用 `GREATEST` 防止乱序回填把水位改小。实测 yueguz 缺口 2 天：`scan backfill days=2 enqueued=1`，补扫 2026-10-31 成功。
- B 对等：B 已种子化 5 个 token、启动 `abi-ingest`，T-1 raw 装载 131 dataset / 4,163 item（head=local），actor 归因 9/131 与 A 一致；B 应用层已用同一 workspace 装载 5 个 ABI dataset，行数与内容哈希和 A 一致。

## 8. 报告输入切换到 ABI：评估结论

**结论：不是简单 SQL 替换，先不切。**

- ABI raw 表有 `si_tiktok_video`、`si_tiktok_comment`、`si_tiktok_hashtag_snapshot`、`si_metric_snapshot`、`si_author_video_snapshot`，包含 caption、评论、播放/互动计数。
- 爆款报告依赖 `deepread288.tsv` 的 `theme_tags` 与 `mechanism_tags`。这两个字段不在 ABI raw 表里，也不在 `insight_pipeline/tiktok_viral/` 的脚本里；该目录只消费已打标的 TSV。README §“换数据”明确要求保持 9 列与列序。
- 因此要切换，必须先补一条 deepread 打标链：
  1. 固定 prompt、模型、版本与输入字段（caption + 评论 + 指标）。
  2. 先对 20 条做试点，与现有 288 条的标签比对，记录一致率与分歧。
  3. 一致率达标后，把标签写入新的 ABI 数据集或派生表，保留 `assigned_by`、`model_version`、`prompt_hash`。
  4. 重做 `theme-clusters.json`/`mech-clusters.json` 的映射（人工/模型判断，不是规则脚本）。
  5. 保持 `deepread288.tsv` 的 9 列契约，或显式升级契约并同步渲染器。

在完成 1-3 之前，报告继续读现有 `deepread288.tsv`；ABI 只作为原始数据底座，不冒充洞察输入。

### 8.1 20 条试点结果（2026-11-02）

试点报告见 [abi-tag-pilot-2026-11-02.md](./abi-tag-pilot-2026-11-02.md)。结论：

- A（caption）与 B（caption+评论）的 top-1 family 准确率都是 25.0%（5/20）。
- family 平均 Jaccard：A 0.361，B 0.409；motif 平均 Jaccard：A 0.549，B 0.498。
- 评论不改变 top-1，20 条首选族完全一致。
- 首选族只覆盖 F3-F7。F1/F2/F8/F9/F10 需要画面、音频或叙事证据，纯文本无法判断。

因此第 2 条的“补 deepread 打标链”暂停。先补多模态输入、100 条以上样本和双人标注，再评估。报告输入继续用 `deepread288.tsv`。

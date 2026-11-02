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
# ABI 数据仓库 · 表结构清单

权威来源：真实 PostgreSQL 16 库的 information_schema（不是从代码推断）。

总计 **48 张表、766 个字段**。

分区子表（apify_item_2026xx、audit_log_202610）与父表字段完全相同，单独列出但不重复展开。


## meta schema（12 张表，119 字段）


### meta.actor_registry — actor→平台/类型映射

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `actor_id` | text | NO |  |
| 3 | `actor_name` | text | NO |  |
| 4 | `platform` | text | NO |  |
| 5 | `object_type` | text | NO |  |
| 6 | `endpoint_type` | text | YES |  |
| 7 | `source` | text | NO |  |
| 8 | `confidence` | text | NO |  |
| 9 | `license` | text | YES |  |
| 10 | `terms_url` | text | YES |  |
| 11 | `deprecated` | boolean | NO | false |
| 12 | `created_at` | timestamp with time zone | NO | now() |

### meta.actor_schema_version — actor 字段集版本（漂移检测）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `actor_id` | text | NO |  |
| 3 | `endpoint_type` | text | YES |  |
| 4 | `input_sha256` | bytea | YES |  |
| 5 | `schema_hash` | bytea | NO |  |
| 6 | `field_names` | array | NO |  |
| 7 | `field_types` | json | NO |  |
| 8 | `field_count` | integer | NO |  |
| 9 | `first_seen_at` | timestamp with time zone | NO |  |
| 10 | `last_seen_at` | timestamp with time zone | NO |  |
| 11 | `sample_dataset_id` | text | YES |  |

### meta.apify_account — Apify 账号（2 行）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `label` | text | NO |  |
| 3 | `apify_user_id` | text | NO |  |
| 4 | `plan` | text | YES |  |
| 5 | `data_retention_days` | integer | NO | 31 |
| 6 | `max_concurrency` | smallint | NO | 8 |
| 7 | `max_rps` | numeric | NO | 8.0 |
| 8 | `enabled` | boolean | NO | true |
| 9 | `created_at` | timestamp with time zone | NO | now() |
| 10 | `updated_at` | timestamp with time zone | NO | now() |

### meta.apify_token — token 密文与指纹

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `account_id` | uuid | NO |  |
| 3 | `label` | text | NO |  |
| 4 | `token_fingerprint` | bytea | NO |  |
| 5 | `token_last4` | varchar | NO |  |
| 6 | `encrypted_payload` | text | NO |  |
| 7 | `key_version` | text | NO | 'abi.fernet.v1'::text |
| 8 | `status` | text | NO | 'active'::text |
| 9 | `last_error_code` | integer | YES |  |
| 10 | `last_used_at` | timestamp with time zone | YES |  |
| 11 | `created_at` | timestamp with time zone | NO | now() |
| 12 | `updated_at` | timestamp with time zone | NO | now() |

### meta.apify_token_daily — 按账号的日用量

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `account_id` | uuid | NO |  |
| 3 | `usage_date` | date | NO |  |
| 4 | `requests` | integer | NO | 0 |
| 5 | `rate_limited` | integer | NO | 0 |
| 6 | `items_fetched` | bigint | NO | 0 |

### meta.audit_log — 审计（月分区父表）

主键：occurred_month, id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `occurred_month` ★ | date | NO |  |
| 2 | `id` ★ | uuid | NO | gen_random_uuid() |
| 3 | `occurred_at` | timestamp with time zone | NO | clock_timestamp() |
| 4 | `actor` | text | NO |  |
| 5 | `action` | text | NO |  |
| 6 | `object_type` | text | NO |  |
| 7 | `object_id` | text | YES |  |
| 8 | `workspace_id` | uuid | YES |  |
| 9 | `detail` | jsonb | YES |  |

### meta.audit_log_202610

主键：occurred_month, id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `occurred_month` ★ | date | NO |  |
| 2 | `id` ★ | uuid | NO | gen_random_uuid() |
| 3 | `occurred_at` | timestamp with time zone | NO | clock_timestamp() |
| 4 | `actor` | text | NO |  |
| 5 | `action` | text | NO |  |
| 6 | `object_type` | text | NO |  |
| 7 | `object_id` | text | YES |  |
| 8 | `workspace_id` | uuid | YES |  |
| 9 | `detail` | jsonb | YES |  |

### meta.ingest_job — 作业队列（幂等键+租约）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `idempotency_key` | text | NO |  |
| 3 | `job_type` | text | NO |  |
| 4 | `account_id` | uuid | YES |  |
| 5 | `target_date` | date | YES |  |
| 6 | `dataset_id` | text | YES |  |
| 7 | `state` | text | NO | 'queued'::text |
| 8 | `attempts` | integer | NO | 0 |
| 9 | `max_attempts` | integer | NO | 6 |
| 10 | `not_before` | timestamp with time zone | YES |  |
| 11 | `lease_owner` | text | YES |  |
| 12 | `lease_expires_at` | timestamp with time zone | YES |  |
| 13 | `lease_version` | bigint | NO | 0 |
| 14 | `last_error_code` | integer | YES |  |
| 15 | `last_error` | text | YES |  |
| 16 | `created_at` | timestamp with time zone | NO | now() |
| 17 | `started_at` | timestamp with time zone | YES |  |
| 18 | `finished_at` | timestamp with time zone | YES |  |

### meta.ingest_run — 一次扫描的汇总

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `sweep_id` | uuid | NO |  |
| 3 | `mode` | text | NO |  |
| 4 | `account_id` | uuid | YES |  |
| 5 | `started_at` | timestamp with time zone | NO |  |
| 6 | `heartbeat_at` | timestamp with time zone | YES |  |
| 7 | `finished_at` | timestamp with time zone | YES |  |
| 8 | `datasets_total` | integer | NO | 0 |
| 9 | `datasets_done` | integer | NO | 0 |
| 10 | `items_total` | bigint | NO | 0 |
| 11 | `bytes_total` | bigint | NO | 0 |
| 12 | `status` | text | NO | 'running'::text |
| 13 | `tool_version` | text | YES |  |
| 14 | `config_sha256` | bytea | YES |  |

### meta.partition_registry — 分区登记

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `parent_table` | text | NO |  |
| 3 | `partition_name` | text | NO |  |
| 4 | `range_start` | date | NO |  |
| 5 | `range_end` | date | NO |  |
| 6 | `created_at` | timestamp with time zone | NO | now() |
| 7 | `detached_at` | timestamp with time zone | YES |  |

### meta.schedule_state — 每账号目标日期水位

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `account_id` | uuid | NO |  |
| 3 | `last_target_date` | date | YES |  |
| 4 | `last_success_at` | timestamp with time zone | YES |  |
| 5 | `last_sweep_at` | timestamp with time zone | YES |  |
| 6 | `updated_at` | timestamp with time zone | NO | now() |

### meta.worker_heartbeat — worker 存活

主键：worker_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `worker_id` ★ | text | NO |  |
| 2 | `role` | text | NO |  |
| 3 | `beat_at` | timestamp with time zone | NO |  |
| 4 | `current_job_id` | uuid | YES |  |
| 5 | `note` | text | YES |  |

## raw schema（24 张表，524 字段）


### raw.amazon_review

主键：review_key

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `review_key` ★ | bytea | NO |  |
| 2 | `file_date` | date | NO |  |
| 3 | `asin` | text | NO |  |
| 4 | `rating` | smallint | YES |  |
| 5 | `title` | text | YES |  |
| 6 | `body` | text | YES |  |
| 7 | `author` | text | YES |  |
| 8 | `review_date` | date | YES |  |
| 9 | `verified_purchase` | boolean | YES |  |
| 10 | `helpful_votes` | integer | YES |  |
| 11 | `total_votes` | integer | YES |  |
| 12 | `source_description` | text | YES |  |
| 13 | `origin` | text | NO |  |
| 14 | `load_batch_id` | uuid | NO |  |
| 15 | `src_file` | text | NO |  |
| 16 | `src_row_ordinal` | integer | NO |  |
| 17 | `content_hash` | bytea | NO |  |
| 18 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.apify_dataset — dataset 清单（8446 行）

主键：dataset_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `dataset_id` ★ | text | NO |  |
| 2 | `account_id` | uuid | NO |  |
| 3 | `run_id` | text | YES |  |
| 4 | `act_id` | text | YES |  |
| 5 | `actor_name` | text | YES |  |
| 6 | `platform` | text | NO | 'other'::text |
| 7 | `object_type` | text | NO | 'unknown'::text |
| 8 | `endpoint_type` | text | YES |  |
| 9 | `endpoint_source` | text | NO | 'unknown'::text |
| 10 | `confidence` | text | NO | 'unknown'::text |
| 11 | `dataset_name` | text | YES |  |
| 12 | `named` | boolean | NO | false |
| 13 | `created_at` | timestamp with time zone | YES |  |
| 14 | `modified_at` | timestamp with time zone | YES |  |
| 15 | `accessed_at` | timestamp with time zone | YES |  |
| 16 | `retention_deadline` | date | YES |  |
| 17 | `retention_estimated` | boolean | NO | true |
| 18 | `item_count_head` | bigint | NO | 0 |
| 19 | `item_count_local` | bigint | NO | 0 |
| 20 | `schema_hash` | bytea | YES |  |
| 21 | `revision` | integer | NO | 1 |
| 22 | `status` | text | NO | 'active'::text |
| 23 | `last_synced_at` | timestamp with time zone | YES |  |
| 24 | `last_synced_batch` | uuid | YES |  |
| 25 | `storage_path` | text | YES |  |
| 26 | `workspace_id` | uuid | YES |  |
| 27 | `created_row_at` | timestamp with time zone | NO | now() |
| 28 | `updated_at` | timestamp with time zone | NO | now() |

### raw.apify_item — Apify 原始条目（月分区父表）

主键：collected_month, dataset_id, item_index

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `collected_month` ★ | date | NO |  |
| 2 | `dataset_id` ★ | text | NO |  |
| 3 | `item_index` ★ | integer | NO |  |
| 4 | `account_id` | uuid | NO |  |
| 5 | `platform` | text | NO | 'other'::text |
| 6 | `object_type` | text | NO | 'unknown'::text |
| 7 | `item` | jsonb | NO |  |
| 8 | `content_hash` | bytea | NO |  |
| 9 | `pii_class` | text | NO | 'unknown'::text |
| 10 | `item_status` | text | NO | 'content'::text |
| 11 | `fetched_at` | timestamp with time zone | NO | clock_timestamp() |
| 12 | `fetch_batch_id` | uuid | NO |  |

### raw.apify_item_202609

主键：collected_month, dataset_id, item_index

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `collected_month` ★ | date | NO |  |
| 2 | `dataset_id` ★ | text | NO |  |
| 3 | `item_index` ★ | integer | NO |  |
| 4 | `account_id` | uuid | NO |  |
| 5 | `platform` | text | NO | 'other'::text |
| 6 | `object_type` | text | NO | 'unknown'::text |
| 7 | `item` | jsonb | NO |  |
| 8 | `content_hash` | bytea | NO |  |
| 9 | `pii_class` | text | NO | 'unknown'::text |
| 10 | `item_status` | text | NO | 'content'::text |
| 11 | `fetched_at` | timestamp with time zone | NO | clock_timestamp() |
| 12 | `fetch_batch_id` | uuid | NO |  |

### raw.apify_item_202610

主键：collected_month, dataset_id, item_index

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `collected_month` ★ | date | NO |  |
| 2 | `dataset_id` ★ | text | NO |  |
| 3 | `item_index` ★ | integer | NO |  |
| 4 | `account_id` | uuid | NO |  |
| 5 | `platform` | text | NO | 'other'::text |
| 6 | `object_type` | text | NO | 'unknown'::text |
| 7 | `item` | jsonb | NO |  |
| 8 | `content_hash` | bytea | NO |  |
| 9 | `pii_class` | text | NO | 'unknown'::text |
| 10 | `item_status` | text | NO | 'content'::text |
| 11 | `fetched_at` | timestamp with time zone | NO | clock_timestamp() |
| 12 | `fetch_batch_id` | uuid | NO |  |

### raw.apify_item_202611

主键：collected_month, dataset_id, item_index

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `collected_month` ★ | date | NO |  |
| 2 | `dataset_id` ★ | text | NO |  |
| 3 | `item_index` ★ | integer | NO |  |
| 4 | `account_id` | uuid | NO |  |
| 5 | `platform` | text | NO | 'other'::text |
| 6 | `object_type` | text | NO | 'unknown'::text |
| 7 | `item` | jsonb | NO |  |
| 8 | `content_hash` | bytea | NO |  |
| 9 | `pii_class` | text | NO | 'unknown'::text |
| 10 | `item_status` | text | NO | 'content'::text |
| 11 | `fetched_at` | timestamp with time zone | NO | clock_timestamp() |
| 12 | `fetch_batch_id` | uuid | NO |  |

### raw.apify_item_202612

主键：collected_month, dataset_id, item_index

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `collected_month` ★ | date | NO |  |
| 2 | `dataset_id` ★ | text | NO |  |
| 3 | `item_index` ★ | integer | NO |  |
| 4 | `account_id` | uuid | NO |  |
| 5 | `platform` | text | NO | 'other'::text |
| 6 | `object_type` | text | NO | 'unknown'::text |
| 7 | `item` | jsonb | NO |  |
| 8 | `content_hash` | bytea | NO |  |
| 9 | `pii_class` | text | NO | 'unknown'::text |
| 10 | `item_status` | text | NO | 'content'::text |
| 11 | `fetched_at` | timestamp with time zone | NO | clock_timestamp() |
| 12 | `fetch_batch_id` | uuid | NO |  |

### raw.apify_item_202701

主键：collected_month, dataset_id, item_index

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `collected_month` ★ | date | NO |  |
| 2 | `dataset_id` ★ | text | NO |  |
| 3 | `item_index` ★ | integer | NO |  |
| 4 | `account_id` | uuid | NO |  |
| 5 | `platform` | text | NO | 'other'::text |
| 6 | `object_type` | text | NO | 'unknown'::text |
| 7 | `item` | jsonb | NO |  |
| 8 | `content_hash` | bytea | NO |  |
| 9 | `pii_class` | text | NO | 'unknown'::text |
| 10 | `item_status` | text | NO | 'content'::text |
| 11 | `fetched_at` | timestamp with time zone | NO | clock_timestamp() |
| 12 | `fetch_batch_id` | uuid | NO |  |

### raw.apify_run — actor run 记录

主键：run_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `run_id` ★ | text | NO |  |
| 2 | `account_id` | uuid | NO |  |
| 3 | `act_id` | text | YES |  |
| 4 | `actor_name` | text | YES |  |
| 5 | `build_id` | text | YES |  |
| 6 | `build_number` | text | YES |  |
| 7 | `status` | text | YES |  |
| 8 | `default_dataset_id` | text | YES |  |
| 9 | `started_at` | timestamp with time zone | YES |  |
| 10 | `finished_at` | timestamp with time zone | YES |  |
| 11 | `usage_total_usd` | numeric | YES |  |
| 12 | `usage_final` | boolean | NO | false |
| 13 | `input_sha256` | bytea | YES |  |
| 14 | `input_available` | boolean | NO | false |
| 15 | `created_at` | timestamp with time zone | NO | now() |

### raw.apify_tweet

主键：origin, src_file, src_row_ordinal

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `snapshot_date` | date | YES |  |
| 2 | `tweet_id` | text | YES |  |
| 3 | `conversation_id` | text | YES |  |
| 4 | `author_id` | text | YES |  |
| 5 | `author_user_name` | text | YES |  |
| 6 | `author_name` | text | YES |  |
| 7 | `author_followers` | bigint | YES |  |
| 8 | `author_verified` | boolean | YES |  |
| 9 | `author_description` | text | YES |  |
| 10 | `author_location` | text | YES |  |
| 11 | `created_at` | timestamp with time zone | YES |  |
| 12 | `full_text` | text | YES |  |
| 13 | `lang` | text | YES |  |
| 14 | `like_count` | integer | YES |  |
| 15 | `reply_count` | integer | YES |  |
| 16 | `retweet_count` | integer | YES |  |
| 17 | `quote_count` | integer | YES |  |
| 18 | `bookmark_count` | integer | YES |  |
| 19 | `view_count` | bigint | YES |  |
| 20 | `is_reply` | boolean | YES |  |
| 21 | `is_quote` | boolean | YES |  |
| 22 | `is_retweet` | boolean | YES |  |
| 23 | `is_pinned` | boolean | YES |  |
| 24 | `possibly_sensitive` | boolean | YES |  |
| 25 | `in_reply_to_id` | text | YES |  |
| 26 | `in_reply_to_user_id` | text | YES |  |
| 27 | `in_reply_to_username` | text | YES |  |
| 28 | `quoted_id` | text | YES |  |
| 29 | `hashtags` | array | YES |  |
| 30 | `urls` | json | YES |  |
| 31 | `media` | json | YES |  |
| 32 | `is_no_results` | boolean | NO | false |
| 33 | `raw` | json | YES |  |
| 34 | `origin` ★ | text | NO |  |
| 35 | `load_batch_id` | uuid | NO |  |
| 36 | `src_file` ★ | text | NO |  |
| 37 | `src_row_ordinal` ★ | integer | NO |  |
| 38 | `content_hash` | bytea | NO |  |
| 39 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.load_error — 拒收行定位（不存原值）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `load_batch_id` | uuid | NO |  |
| 3 | `origin` | text | NO |  |
| 4 | `src_file` | text | NO |  |
| 5 | `src_row_ordinal` | integer | NO |  |
| 6 | `column_name` | text | YES |  |
| 7 | `rule_id` | text | YES |  |
| 8 | `message` | text | YES |  |
| 9 | `created_at` | timestamp with time zone | NO | now() |

### raw.load_file — 源文件清单（可重放）

主键：file_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `file_id` ★ | uuid | NO |  |
| 2 | `origin` | text | NO |  |
| 3 | `source_path` | text | NO |  |
| 4 | `storage_path` | text | NO |  |
| 5 | `sha256` | bytea | NO |  |
| 6 | `size_bytes` | bigint | NO |  |
| 7 | `mtime` | timestamp with time zone | YES |  |
| 8 | `rows_total` | integer | YES |  |
| 9 | `rows_loaded` | integer | YES |  |
| 10 | `rows_rejected` | integer | YES |  |
| 11 | `status` | text | NO | 'pending'::text |
| 12 | `loaded_at` | timestamp with time zone | YES |  |

### raw.pmo_collection_record

主键：record_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `record_id` ★ | uuid | NO |  |
| 2 | `project_id` | uuid | YES |  |
| 3 | `workspace_id` | uuid | YES |  |
| 4 | `source_id` | uuid | YES |  |
| 5 | `task_run_id` | uuid | YES |  |
| 6 | `record_type` | text | YES |  |
| 7 | `source_url` | text | YES |  |
| 8 | `screenshot_url` | text | YES |  |
| 9 | `collected_at` | timestamp with time zone | YES |  |
| 10 | `created_at` | timestamp with time zone | YES |  |
| 11 | `snapshot_date` | date | NO |  |
| 12 | `schema_version` | text | NO |  |
| 13 | `provider` | text | YES |  |
| 14 | `platform` | text | YES |  |
| 15 | `actor_id` | text | YES |  |
| 16 | `content_text` | text | YES |  |
| 17 | `content` | json | YES |  |
| 18 | `origin` | text | NO |  |
| 19 | `load_batch_id` | uuid | NO |  |
| 20 | `src_file` | text | NO |  |
| 21 | `src_row_ordinal` | integer | NO |  |
| 22 | `content_hash` | bytea | NO |  |
| 23 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.probe_instagram_post

主键：origin, src_file, src_row_ordinal

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `probe_date` | date | YES |  |
| 2 | `short_code` | text | YES |  |
| 3 | `post_id` | text | YES |  |
| 4 | `post_type` | text | YES |  |
| 5 | `url` | text | YES |  |
| 6 | `input_url` | text | YES |  |
| 7 | `caption` | text | YES |  |
| 8 | `owner_id` | text | YES |  |
| 9 | `owner_username` | text | YES |  |
| 10 | `owner_full_name` | text | YES |  |
| 11 | `posted_at` | timestamp with time zone | YES |  |
| 12 | `likes_count` | integer | YES |  |
| 13 | `comments_count` | integer | YES |  |
| 14 | `video_view_count` | integer | YES |  |
| 15 | `video_duration` | double precision | YES |  |
| 16 | `dimensions_width` | integer | YES |  |
| 17 | `dimensions_height` | integer | YES |  |
| 18 | `display_url` | text | YES |  |
| 19 | `video_url` | text | YES |  |
| 20 | `images` | json | YES |  |
| 21 | `child_posts` | json | YES |  |
| 22 | `latest_comments` | json | YES |  |
| 23 | `first_comment` | text | YES |  |
| 24 | `hashtags` | array | YES |  |
| 25 | `mentions` | array | YES |  |
| 26 | `tagged_users` | json | YES |  |
| 27 | `location_id` | text | YES |  |
| 28 | `location_name` | text | YES |  |
| 29 | `music_info` | json | YES |  |
| 30 | `paid_partnership` | boolean | YES |  |
| 31 | `product_type` | text | YES |  |
| 32 | `is_pinned` | boolean | YES |  |
| 33 | `raw` | json | YES |  |
| 34 | `origin` ★ | text | NO |  |
| 35 | `load_batch_id` | uuid | NO |  |
| 36 | `src_file` ★ | text | NO |  |
| 37 | `src_row_ordinal` ★ | integer | NO |  |
| 38 | `content_hash` | bytea | NO |  |
| 39 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.probe_tiktok_video

主键：origin, src_file, src_row_ordinal

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `probe_date` | date | YES |  |
| 2 | `arm` | text | YES |  |
| 3 | `video_id` | text | YES |  |
| 4 | `text` | text | YES |  |
| 5 | `create_time` | bigint | YES |  |
| 6 | `create_time_iso` | timestamp with time zone | YES |  |
| 7 | `web_video_url` | text | YES |  |
| 8 | `search_query` | text | YES |  |
| 9 | `author_id` | text | YES |  |
| 10 | `author_name` | text | YES |  |
| 11 | `author_nickname` | text | YES |  |
| 12 | `author_signature` | text | YES |  |
| 13 | `author_fans` | bigint | YES |  |
| 14 | `author_following` | bigint | YES |  |
| 15 | `author_heart` | bigint | YES |  |
| 16 | `author_verified` | boolean | YES |  |
| 17 | `author_avatar_url` | text | YES |  |
| 18 | `author_bio_link` | text | YES |  |
| 19 | `author_profile_url` | text | YES |  |
| 20 | `author_private` | boolean | YES |  |
| 21 | `music_id` | text | YES |  |
| 22 | `music_name` | text | YES |  |
| 23 | `music_author` | text | YES |  |
| 24 | `music_original` | boolean | YES |  |
| 25 | `music_play_url` | text | YES |  |
| 26 | `music_cover_url` | text | YES |  |
| 27 | `video_height` | integer | YES |  |
| 28 | `video_width` | integer | YES |  |
| 29 | `video_duration` | integer | YES |  |
| 30 | `video_definition` | text | YES |  |
| 31 | `video_format` | text | YES |  |
| 32 | `video_cover_url` | text | YES |  |
| 33 | `video_cover_original_url` | text | YES |  |
| 34 | `transcription_link` | text | YES |  |
| 35 | `play_count` | bigint | YES |  |
| 36 | `digg_count` | bigint | YES |  |
| 37 | `comment_count` | bigint | YES |  |
| 38 | `share_count` | bigint | YES |  |
| 39 | `collect_count` | bigint | YES |  |
| 40 | `repost_count` | bigint | YES |  |
| 41 | `is_ad` | boolean | YES |  |
| 42 | `is_sponsored` | boolean | YES |  |
| 43 | `is_pinned` | boolean | YES |  |
| 44 | `is_slideshow` | boolean | YES |  |
| 45 | `is_story` | boolean | YES |  |
| 46 | `is_muted` | boolean | YES |  |
| 47 | `location_created` | text | YES |  |
| 48 | `hashtags` | json | YES |  |
| 49 | `mentions` | json | YES |  |
| 50 | `detailed_mentions` | json | YES |  |
| 51 | `effect_stickers` | json | YES |  |
| 52 | `media_urls` | json | YES |  |
| 53 | `slideshow_image_links` | json | YES |  |
| 54 | `has_tiktok_shop_product` | boolean | YES |  |
| 55 | `comments_dataset_url` | text | YES |  |
| 56 | `raw` | json | YES |  |
| 57 | `origin` ★ | text | NO |  |
| 58 | `load_batch_id` | uuid | NO |  |
| 59 | `src_file` ★ | text | NO |  |
| 60 | `src_row_ordinal` ★ | integer | NO |  |
| 61 | `content_hash` | bytea | NO |  |
| 62 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.probe_youtube_video

主键：origin, src_file, src_row_ordinal

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `probe_date` | date | YES |  |
| 2 | `arm` | text | YES |  |
| 3 | `video_id` | text | YES |  |
| 4 | `title` | text | YES |  |
| 5 | `description` | text | YES |  |
| 6 | `url` | text | YES |  |
| 7 | `from_yt_url` | text | YES |  |
| 8 | `channel_id` | text | YES |  |
| 9 | `channel_name` | text | YES |  |
| 10 | `channel_username` | text | YES |  |
| 11 | `channel_url` | text | YES |  |
| 12 | `number_of_subscribers` | bigint | YES |  |
| 13 | `published_at` | timestamp with time zone | YES |  |
| 14 | `duration` | text | YES |  |
| 15 | `view_count` | bigint | YES |  |
| 16 | `likes` | bigint | YES |  |
| 17 | `comments_count` | bigint | YES |  |
| 18 | `comments_turned_off` | boolean | YES |  |
| 19 | `is_members_only` | boolean | YES |  |
| 20 | `is_paid_content` | boolean | YES |  |
| 21 | `is_monetized` | boolean | YES |  |
| 22 | `hashtags` | array | YES |  |
| 23 | `description_links` | json | YES |  |
| 24 | `thumbnail_url` | text | YES |  |
| 25 | `order_index` | integer | YES |  |
| 26 | `input` | text | YES |  |
| 27 | `video_type` | text | YES |  |
| 28 | `translated_title` | text | YES |  |
| 29 | `translated_text` | text | YES |  |
| 30 | `ai_video_summary` | text | YES |  |
| 31 | `ai_video_description` | text | YES |  |
| 32 | `collaborators` | json | YES |  |
| 33 | `subtitles` | json | YES |  |
| 34 | `transcription_url` | text | YES |  |
| 35 | `location` | text | YES |  |
| 36 | `raw` | json | YES |  |
| 37 | `origin` ★ | text | NO |  |
| 38 | `load_batch_id` | uuid | NO |  |
| 39 | `src_file` ★ | text | NO |  |
| 40 | `src_row_ordinal` ★ | integer | NO |  |
| 41 | `content_hash` | bytea | NO |  |
| 42 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.product_catalog

主键：product_key

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `product_key` ★ | bigint | NO | nextval('raw.product_catalog_product_key |
| 2 | `file_date` | date | NO |  |
| 3 | `category` | text | YES |  |
| 4 | `brand` | text | YES |  |
| 5 | `product_name` | text | YES |  |
| 6 | `origin` | text | NO |  |
| 7 | `load_batch_id` | uuid | NO |  |
| 8 | `src_file` | text | NO |  |
| 9 | `src_row_ordinal` | integer | NO |  |
| 10 | `content_hash` | bytea | NO |  |
| 11 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_author_video_snapshot

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `origin` | text | NO |  |
| 3 | `load_batch_id` | uuid | NO |  |
| 4 | `src_file` | text | NO |  |
| 5 | `src_row_ordinal` | integer | NO |  |
| 6 | `content_hash` | bytea | NO |  |
| 7 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_metric_snapshot

主键：snapshot_date, platform_code, object_type, object_id, source_actor

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `snapshot_date` ★ | date | NO |  |
| 2 | `captured_at` | timestamp with time zone | YES |  |
| 3 | `platform_code` ★ | text | NO |  |
| 4 | `object_type` ★ | text | NO |  |
| 5 | `object_id` ★ | text | NO |  |
| 6 | `view_count` | bigint | YES |  |
| 7 | `like_count` | bigint | YES |  |
| 8 | `comment_count` | bigint | YES |  |
| 9 | `share_count` | bigint | YES |  |
| 10 | `collect_count` | bigint | YES |  |
| 11 | `source_actor` ★ | text | NO |  |
| 12 | `run_id` | text | YES |  |
| 13 | `origin` | text | NO |  |
| 14 | `load_batch_id` | uuid | NO |  |
| 15 | `src_file` | text | NO |  |
| 16 | `src_row_ordinal` | integer | NO |  |
| 17 | `content_hash` | bytea | NO |  |
| 18 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_music_platform_snapshot

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `origin` | text | NO |  |
| 3 | `load_batch_id` | uuid | NO |  |
| 4 | `src_file` | text | NO |  |
| 5 | `src_row_ordinal` | integer | NO |  |
| 6 | `content_hash` | bytea | NO |  |
| 7 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_social_post

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `origin` | text | NO |  |
| 3 | `load_batch_id` | uuid | NO |  |
| 4 | `src_file` | text | NO |  |
| 5 | `src_row_ordinal` | integer | NO |  |
| 6 | `content_hash` | bytea | NO |  |
| 7 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_tiktok_comment

主键：platform, video_id, comment_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `platform` ★ | text | NO | 'tiktok'::text |
| 2 | `video_id` ★ | text | NO |  |
| 3 | `comment_id` ★ | text | NO |  |
| 4 | `parent_id` | text | YES |  |
| 5 | `text` | text | YES |  |
| 6 | `digg_count` | bigint | YES |  |
| 7 | `reply_count` | bigint | YES |  |
| 8 | `author_handle` | text | YES |  |
| 9 | `author_id` | text | YES |  |
| 10 | `author_avatar` | text | YES |  |
| 11 | `liked_by_author` | boolean | YES |  |
| 12 | `pinned_by_author` | boolean | YES |  |
| 13 | `platform_created_at` | timestamp with time zone | YES |  |
| 14 | `fetched_at` | timestamp with time zone | YES |  |
| 15 | `source_tier` | text | YES |  |
| 16 | `run_id` | text | YES |  |
| 17 | `sample_rank` | integer | YES |  |
| 18 | `origin` | text | NO |  |
| 19 | `load_batch_id` | uuid | NO |  |
| 20 | `src_file` | text | NO |  |
| 21 | `src_row_ordinal` | integer | NO |  |
| 22 | `content_hash` | bytea | NO |  |
| 23 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_tiktok_hashtag_snapshot

主键：snapshot_date, hashtag_id, video_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `snapshot_date` ★ | date | NO |  |
| 2 | `captured_at` | timestamp with time zone | YES |  |
| 3 | `hashtag_id` ★ | text | NO |  |
| 4 | `hashtag` | text | YES |  |
| 5 | `source_actor` | text | YES |  |
| 6 | `rank_in_tag` | integer | YES |  |
| 7 | `video_id` ★ | text | NO |  |
| 8 | `author_id` | text | YES |  |
| 9 | `author_unique_id` | text | YES |  |
| 10 | `author_nickname` | text | YES |  |
| 11 | `author_avatar_url` | text | YES |  |
| 12 | `play_count` | bigint | YES |  |
| 13 | `digg_count` | bigint | YES |  |
| 14 | `comment_count` | bigint | YES |  |
| 15 | `share_count` | bigint | YES |  |
| 16 | `collect_count` | bigint | YES |  |
| 17 | `published_at` | timestamp with time zone | YES |  |
| 18 | `is_ad` | boolean | YES |  |
| 19 | `descr` | text | YES |  |
| 20 | `run_id` | text | YES |  |
| 21 | `cover_url` | text | YES |  |
| 22 | `music_id` | text | YES |  |
| 23 | `music_title` | text | YES |  |
| 24 | `music_author` | text | YES |  |
| 25 | `music_duration_sec` | integer | YES |  |
| 26 | `music_is_original` | boolean | YES |  |
| 27 | `music_is_commerce` | boolean | YES |  |
| 28 | `hashtags` | array | YES |  |
| 29 | `origin` | text | NO |  |
| 30 | `load_batch_id` | uuid | NO |  |
| 31 | `src_file` | text | NO |  |
| 32 | `src_row_ordinal` | integer | NO |  |
| 33 | `content_hash` | bytea | NO |  |
| 34 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

### raw.si_tiktok_video

主键：video_id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `video_id` ★ | text | NO |  |
| 2 | `hashtag` | text | YES |  |
| 3 | `snapshot_date` | date | YES |  |
| 4 | `rank_in_tag` | integer | YES |  |
| 5 | `author_unique_id` | text | YES |  |
| 6 | `author_nickname` | text | YES |  |
| 7 | `author_id` | text | YES |  |
| 8 | `descr` | text | YES |  |
| 9 | `published_at` | timestamp without time zone | YES |  |
| 10 | `is_ad` | boolean | YES |  |
| 11 | `music_id` | text | YES |  |
| 12 | `music_title` | text | YES |  |
| 13 | `music_author` | text | YES |  |
| 14 | `play_count` | bigint | YES |  |
| 15 | `digg_count` | bigint | YES |  |
| 16 | `comment_count` | bigint | YES |  |
| 17 | `share_count` | bigint | YES |  |
| 18 | `collect_count` | bigint | YES |  |
| 19 | `snap_days` | integer | YES |  |
| 20 | `peak_play` | bigint | YES |  |
| 21 | `first_seen` | date | YES |  |
| 22 | `last_seen` | date | YES |  |
| 23 | `play_gain_total` | bigint | YES |  |
| 24 | `play_gain_daily_avg` | double precision | YES |  |
| 25 | `parse_level` | text | YES |  |
| 26 | `recommendation` | text | YES |  |
| 27 | `analysis_status` | text | YES |  |
| 28 | `evidence_state` | text | YES |  |
| 29 | `analysis_version` | text | YES |  |
| 30 | `summary_original` | text | YES |  |
| 31 | `target_audience` | text | YES |  |
| 32 | `hook_visual` | text | YES |  |
| 33 | `hook_audio` | text | YES |  |
| 34 | `hook_formula` | text | YES |  |
| 35 | `n_mechanisms` | integer | YES |  |
| 36 | `n_timeline_segments` | integer | YES |  |
| 37 | `n_transcript_segments` | integer | YES |  |
| 38 | `brand_borrow_n` | integer | YES |  |
| 39 | `brand_replace_n` | integer | YES |  |
| 40 | `analysis_created_at` | timestamp without time zone | YES |  |
| 41 | `has_deepread` | boolean | YES |  |
| 42 | `deepread_model` | text | YES |  |
| 43 | `deepread_at` | timestamp without time zone | YES |  |
| 44 | `theme_tags` | text | YES |  |
| 45 | `mechanism_tags` | text | YES |  |
| 46 | `life_stage` | text | YES |  |
| 47 | `one_liner` | text | YES |  |
| 48 | `media_playable` | boolean | YES |  |
| 49 | `media_size_bytes` | bigint | YES |  |
| 50 | `comment_rows` | integer | YES |  |
| 51 | `comment_top_digg` | bigint | YES |  |
| 52 | `built_at` | timestamp without time zone | YES |  |
| 53 | `origin` | text | NO |  |
| 54 | `load_batch_id` | uuid | NO |  |
| 55 | `src_file` | text | NO |  |
| 56 | `src_row_ordinal` | integer | NO |  |
| 57 | `content_hash` | bytea | NO |  |
| 58 | `loaded_at` | timestamp with time zone | NO | clock_timestamp() |

## abi schema（12 张表，123 字段）


### abi.access_grant — 数据集授权

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | NO |  |
| 3 | `workspace_id` | uuid | NO |  |
| 4 | `user_id` | uuid | NO |  |
| 5 | `role` | text | NO | 'viewer'::text |
| 6 | `granted_by` | uuid | YES |  |
| 7 | `created_at` | timestamp with time zone | NO | now() |

### abi.cast_error — 类型转换失败记录

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | YES |  |
| 3 | `row_key` | text | YES |  |
| 4 | `column_name` | text | YES |  |
| 5 | `raw_value` | text | YES |  |
| 6 | `target_type` | text | YES |  |
| 7 | `created_at` | timestamp with time zone | NO | now() |

### abi.catalog_dataset — 看板数据集目录

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `workspace_id` | uuid | NO |  |
| 3 | `slug` | text | NO |  |
| 4 | `name` | text | NO |  |
| 5 | `description` | text | YES |  |
| 6 | `source_kind` | text | NO |  |
| 7 | `source_table` | text | YES |  |
| 8 | `platform` | text | YES |  |
| 9 | `object_type` | text | YES |  |
| 10 | `origin` | text | YES |  |
| 11 | `row_count` | bigint | NO | 0 |
| 12 | `last_loaded_at` | timestamp with time zone | YES |  |
| 13 | `version` | integer | NO | 1 |
| 14 | `is_current` | boolean | NO | true |
| 15 | `pii_scanned` | boolean | NO | false |
| 16 | `quality_status` | text | YES |  |
| 17 | `owner_id` | uuid | YES |  |
| 18 | `created_at` | timestamp with time zone | NO | now() |
| 19 | `updated_at` | timestamp with time zone | NO | now() |

### abi.dataset_column — 列元数据（查询白名单）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | NO |  |
| 3 | `column_name` | text | NO |  |
| 4 | `data_type` | text | NO |  |
| 5 | `ordinal` | integer | NO |  |
| 6 | `nullable` | boolean | NO | true |
| 7 | `filterable` | boolean | NO | true |
| 8 | `sortable` | boolean | NO | true |

### abi.dataset_daily_stat — 日统计（免 count）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | NO |  |
| 3 | `stat_date` | date | NO |  |
| 4 | `row_count` | bigint | NO | 0 |
| 5 | `bytes_total` | bigint | NO | 0 |
| 6 | `null_rate` | json | YES |  |

### abi.export_job — 导出任务

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `workspace_id` | uuid | NO |  |
| 3 | `dataset_id` | uuid | NO |  |
| 4 | `created_by` | uuid | NO |  |
| 5 | `format` | text | NO |  |
| 6 | `mask_pii` | boolean | NO | true |
| 7 | `filters` | json | YES |  |
| 8 | `filters_hmac` | bytea | YES |  |
| 9 | `columns` | array | YES |  |
| 10 | `reason` | text | YES |  |
| 11 | `status` | text | NO | 'queued'::text |
| 12 | `approved_by` | uuid | YES |  |
| 13 | `approved_at` | timestamp with time zone | YES |  |
| 14 | `artifact_path` | text | YES |  |
| 15 | `filename` | text | YES |  |
| 16 | `content_type` | text | YES |  |
| 17 | `bytes_total` | bigint | YES |  |
| 18 | `rows_total` | bigint | YES |  |
| 19 | `error` | text | YES |  |
| 20 | `created_at` | timestamp with time zone | NO | now() |
| 21 | `started_at` | timestamp with time zone | YES |  |
| 22 | `finished_at` | timestamp with time zone | YES |  |
| 23 | `expires_at` | timestamp with time zone | YES |  |

### abi.export_policy — 导出策略

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `workspace_id` | uuid | NO |  |
| 3 | `dataset_id` | uuid | YES |  |
| 4 | `max_rows_masked` | bigint | YES |  |
| 5 | `require_dual_approval` | boolean | NO | true |
| 6 | `allowed_formats` | array | YES |  |
| 7 | `created_at` | timestamp with time zone | NO | now() |

### abi.field_policy — 字段 PII 策略

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | NO |  |
| 3 | `field_path` | text | NO |  |
| 4 | `pii_class` | text | NO | 'unknown'::text |
| 5 | `mask_rule` | text | YES |  |
| 6 | `decided_by` | text | NO | 'system'::text |
| 7 | `created_at` | timestamp with time zone | NO | now() |

### abi.platform_object — 跨源实体映射

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `platform` | text | NO |  |
| 3 | `object_type` | text | NO |  |
| 4 | `canonical_id` | text | NO |  |
| 5 | `row_key` | text | NO |  |
| 6 | `origin` | text | YES |  |
| 7 | `created_at` | timestamp with time zone | NO | now() |

### abi.saved_query — 保存的查询（结构化）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | NO |  |
| 3 | `workspace_id` | uuid | NO |  |
| 4 | `created_by` | uuid | NO |  |
| 5 | `name` | text | NO |  |
| 6 | `definition` | json | NO |  |
| 7 | `created_at` | timestamp with time zone | NO | now() |

### abi.upload_batch — 上传批次

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `dataset_id` | uuid | NO |  |
| 3 | `workspace_id` | uuid | NO |  |
| 4 | `uploaded_by` | uuid | NO |  |
| 5 | `filename` | text | NO |  |
| 6 | `mode` | text | NO |  |
| 7 | `expected_sha256` | bytea | YES |  |
| 8 | `actual_sha256` | bytea | YES |  |
| 9 | `expected_rows` | bigint | YES |  |
| 10 | `actual_rows` | bigint | YES |  |
| 11 | `bytes_total` | bigint | NO | 0 |
| 12 | `status` | text | NO | 'pending'::text |
| 13 | `storage_path` | text | YES |  |
| 14 | `upload_token_hash` | bytea | YES |  |
| 15 | `token_expires_at` | timestamp with time zone | YES |  |
| 16 | `rows_loaded` | bigint | NO | 0 |
| 17 | `rows_rejected` | bigint | NO | 0 |
| 18 | `created_at` | timestamp with time zone | NO | now() |
| 19 | `committed_at` | timestamp with time zone | YES |  |

### abi.upload_error — 上传错误（只存定位）

主键：id

| # | 字段 | 类型 | 可空 | 默认值 |
|---|---|---|---|---|
| 1 | `id` ★ | uuid | NO |  |
| 2 | `batch_id` | uuid | NO |  |
| 3 | `row_number` | integer | NO |  |
| 4 | `column_name` | text | YES |  |
| 5 | `rule_id` | text | NO |  |
| 6 | `message` | text | YES |  |
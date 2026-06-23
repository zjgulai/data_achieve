---
title: M5 Public Content Retained Lifecycle Gate Evidence
doc_type: analysis
module: automation
topic: boundary-m5-public-content-retained-lifecycle-gate
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# M5 Public Content Retained Lifecycle Gate Evidence

## 1. Scope

This draft records one authorized production retained lifecycle gate for the M5 Public Web/RSS/Docs package.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: one retained user, one public_feed Source, one enabled Task, one RSS TaskRun, one public_content_update DatasetVersion, one read-only drift check, one public_content Report asset, one CSV DatasetExportJob, one export artifact file, post-login visibility checks
denied: cleanup execution, provider call, email send, scheduler mutation, production browser run, browser artifact write, drift event persistence
retention: retained_no_cleanup
```

This gate intentionally differs from the earlier cleanup-after-evidence gates. It leaves a small named production canary asset set in place so Dataset, Report, and Export visibility can be checked after the write transaction and a new login.

## 2. Production Baseline

```text
base_url: https://scrapy.lute-tlz-dddd.top
remote HEAD: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
.deploy-sha: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
health: production/ok/connected/current
schema_revision: 202606110023
schema_head: 202606110023
scheduler_enabled: true
containers: api/db/edge/web healthy
```

No deployment was performed for this gate. It used the already deployed `fb05c61` production code point.

## 3. Retained Asset Manifest

```text
actor_email: retained-public-content-20260623123816-90w0q7@example.com
project_id: aadde70a-acdd-5d0c-acc1-247387d81704
source_id: c86b280c-0315-4d93-bcd7-37786996a22b
task_id: b8a4cb3f-abe9-48f6-bb66-7ff4962bcdc6
task_run_id: 1f684c04-0aab-48b7-ae4b-824526efaadc
dataset_id: ee4a4a7a-1ea8-4864-b10d-031b365e5efb
dataset_version_id: 6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8
report_id: 38a0f8ce-59ed-46da-a9ae-968c6a020e57
export_job_id: 3f43b866-1312-47d0-95b6-90322a2c7ee5
cleanup_policy: retained_no_cleanup
```

Export artifact path from read-only DB/volume inventory:

```text
/app/exports/datasets/bf51c6a8-fba5-5528-ac91-89ffd84f85c2/ee4a4a7a-1ea8-4864-b10d-031b365e5efb/6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8/retained-public-content-lifecycle-20260623123816-v1-3f43b866.csv
```

## 4. Production Gate Evidence

Command class:

```text
node tmp/scratch/public_content_retained_lifecycle_production_smoke.mjs
```

Result:

```text
status: passed
retained: true
cleanup_policy: retained_no_cleanup
```

Public feed and Dataset evidence:

```text
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion schema_version: public_content_update.v1
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
```

Read-only drift evidence:

```text
endpoint: POST /api/automation/public-content-drift-check
checked_tasks: 1
warning_tasks: 1
critical_tasks: 0
added_rows: 0
removed_rows: 0
run_started: false
alert_created: false
drift_event_created: false
```

Report and export evidence:

```text
Report preview entry_count: 5
Report preview feed_count: 1
Report preview risk_section_count: 3
Report preview report_created: false
Report asset report_id: 38a0f8ce-59ed-46da-a9ae-968c6a020e57
Report asset report_type: public_content
Report asset report_status: generated
Report asset notification_created: false

Export endpoint: POST /api/automation/product-dataset-exports
Export status: success
Export filename: retained-public-content-lifecycle-20260623123816-v1-3f43b866.csv
Export content_type: text/csv; charset=utf-8
Export artifact_size_bytes: 4344
Export row_count: 5
Export checksum_sha256: 0253d01911bd63a4ef529ce53001e958fe1fab7570037b1c072863b4418b322a
```

## 5. Retention Verification

The smoke script cleared the initial cookie, logged in again as the retained user, and verified the retained assets through read endpoints.

```text
source_found: true
task_found: true
task_run_found: true
dataset_found: true
dataset version_found: true
report_found: true
export_found: true
export download content_type: text/csv; charset=utf-8
export download byte_length: 4344
download contains title/link/published_at header: true
download contains content_hash: true
download contains feed_url: true
```

Read-only DB/volume inventory:

```text
status: ready
violations: []
cleanup_executed: false
users=1
workspaces=1
workspace_members=2
notifications=1
sources=1
collection_tasks=1
task_runs=1
raw_records=1
entities=1
entity_snapshots=1
datasets=1
dataset_versions=1
dataset_drift_events=0
reports=1
report_audit_events=1
dataset_export_jobs=1
export_artifact_files=1
```

Generic E2E cleanup dry-run:

```text
scripts/cleanup-e2e-fixtures.sh --older-than-hours 0
dry_run: true
all categories: 0
```

The retained account intentionally does not use the `e2e-` email prefix, so generic E2E cleanup does not remove this canary. Future cleanup must use the exact IDs in the retained asset manifest.

Temporary remote inventory scripts were removed from host `/tmp` and API container `/tmp`.

## 6. Post-Gate Production Smoke

```text
GET /api/health: production/ok/connected/current
/dashboard=200
/automation=200
/datasets=200
/tasks=200
/sources=200
/raw-records=200
/reports=200
/alerts=200
/notifications=200
/projects=200
/signals=200
/entities=200
/toolkit=200
```

## 7. Boundary

Supported claim: M5 Public Content has one retained production canary covering public RSS collection, `public_content_update.v1` DatasetVersion save, read-only drift check, `public_content` Report asset persistence, CSV DatasetExportJob persistence, export artifact file retention, post-login list/detail visibility, export download, and read-only DB/volume inventory.

Unsupported claim: multi-day retention, automated TTL, automatic cleanup job, scheduler refresh, persisted public-content-specific drift event type, provider enrichment, product/report/subscription email, production browser execution, or browser artifact retention is complete.

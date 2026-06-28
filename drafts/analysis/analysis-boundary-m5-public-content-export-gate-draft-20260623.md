---
title: M5 Public Content Dataset Export Gate Evidence
doc_type: analysis
module: automation
topic: boundary-m5-public-content-export-gate
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# M5 Public Content Dataset Export Gate Evidence

## 1. Scope

This draft records one authorized production Dataset export gate for the M5 Public Web/RSS/Docs package.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: one temporary e2e user, one public_feed Source, one enabled Task, one RSS TaskRun, one public_content_update DatasetVersion, one CSV DatasetExportJob, one export artifact file, one authenticated export download
denied: Report asset, provider call, email send, scheduler mutation, production browser run, browser artifact write
retention: cleanup_after_evidence
```

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

## 3. Export Gate Evidence

Command class:

```text
node tmp/scratch/public_content_export_production_smoke.mjs
```

Result:

```text
status: passed
feed_url: https://hnrss.org/frontpage
actor_email: e2e-public-export-20260623121345-3l86fa@example.com
source_id: 4163e9db-b974-4b13-a2ad-240c6ecbe785
task_id: af4615b9-afb4-4889-aa24-435056ab4109
task_run_id: 0ddcdd7e-5ec6-46d2-bd4e-8744add159fb
dataset_id: ee4507a6-d492-4cc3-b5e0-4ab7b1237835
dataset_version_id: c1ae8de5-34b5-49ca-8232-f6f228d35d76
export_job_id: 1ad76121-2533-44e3-ad19-f4d073059ac3
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

Dataset export evidence:

```text
endpoint: POST /api/automation/product-dataset-exports
export_format: csv
export status: success
filename: e2e-public-content-export-dataset-20260623121345-v1-1ad76121.csv
content_type: text/csv; charset=utf-8
artifact_size_bytes: 4900
row_count: 5
checksum_sha256: d64474f7cc844de9be1faf48f5e597043dd5cb27318dbeb57a4ab1a78b4995f0
audit_event_count: 2
audit event: product_dataset_export_file_written
run_started: false
```

Export list and download evidence:

```text
GET /api/automation/product-datasets/{dataset_id}/exports?dataset_version_id={version_id}
total: 1
export_created: false
run_started: false

GET /api/automation/product-datasets/{dataset_id}/versions/{version_id}/exports/{export_job_id}/download
download content_type: text/csv; charset=utf-8
download byte_length: 4900
contains title/link/published_at header: true
contains content_hash: true
contains feed_url: true
```

Evidence JSON:

```text
tmp/outputs/public-content-export-production-smoke-20260623.json
```

## 4. Cleanup Evidence

Exact-ID cleanup dry-run before execute:

```text
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
dataset_export_jobs=1
export_artifact_files=1
dataset_drift_events=0
signals=0
evidences=0
```

Export artifact path:

```text
/app/exports/datasets/bf51c6a8-fba5-5528-ac91-89ffd84f85c2/ee4507a6-d492-4cc3-b5e0-4ab7b1237835/c1ae8de5-34b5-49ca-8232-f6f228d35d76/e2e-public-content-export-dataset-20260623121345-v1-1ad76121.csv
```

Cleanup result:

```text
exact cleanup execute: removed the same scoped database objects and the export artifact file
post-cleanup exact-ID dry-run: all categories returned zero, including export_artifact_files=0
post-cleanup generic E2E dry-run: all categories returned zero
temporary remote cleanup script: removed from host /tmp and container /tmp
```

Post-cleanup production read-only smoke:

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

## 5. Boundary

Supported claim: M5 Public Content has one authorized Dataset export gate covering public RSS collection, `public_content_update.v1` DatasetVersion save, CSV DatasetExportJob creation, export artifact file write, authenticated export download, exact-ID cleanup, artifact deletion, and generic cleanup recount.

Unsupported claim: recurring RSS monitoring, retained dataset/export lifecycle, provider enrichment, product/report/subscription email, scheduler mutation, production browser execution, or browser artifact retention is complete.

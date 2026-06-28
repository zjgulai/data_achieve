---
title: M5 Public Content Report Asset Production Gate
doc_type: analysis
module: automation
topic: boundary-m5-public-content-report-asset
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# M5 Public Content Report Asset Production Gate

## 1. Scope

本轮在已完成 M5 public content production smoke 的基础上，单独验证公开 RSS 内容数据集可以持久化为 Report 中心资产。

授权范围：

- `scope_type=public_rss_feed`
- `scope_value=https://hnrss.org/frontpage`
- allowed: one temporary e2e user, one `public_feed` Source, one enabled Task, one RSS TaskRun, one `public_content_update` DatasetVersion, one `public_content` Report asset, one ReportAuditEvent, exact-ID cleanup
- denied: dataset export, provider call, email send, scheduler mutation, production browser run, browser artifact write
- retention: `cleanup_after_evidence`

## 2. Deployment Evidence

Initial deploy:

- previous production HEAD: `e1359759aa1cab157bb98ec8abda4ff580cbfe7d`
- deployed SHA: `2ebbe4a584c6e1122ba3b180998e6548667de0f9`
- backup branch: `backup/pre-public-content-report-asset-gate-20260623115056`
- preflight: passed
- Docker build: passed
- Alembic upgrade: passed
- gateway reload: passed after waiting for edge health

Hotfix deploy:

- production bug: `reports.report_type` is `VARCHAR(20)`, while `public_content_update` is 21 characters
- fix: use `Report.report_type="public_content"` while preserving `Dataset.dataset_type="public_content_update"` and `schema_version=public_content_update.v1` in report content
- hotfix SHA: `fb05c61ab137b1c1cb7519b661d98a97ae0cead6`
- backup branch: `backup/pre-public-content-report-asset-hotfix-20260623115906`
- preflight: passed
- API image build: passed
- Alembic upgrade: passed
- API health: healthy
- production health: `environment=production`, `status=ok`, `database=connected`, `schema=current`, `schema_revision=schema_head=202606110023`

Public pages returned `200` after hotfix:

```text
/dashboard
/automation
/datasets
/tasks
/sources
/raw-records
/reports
/alerts
/notifications
/projects
/signals
/entities
/toolkit
```

## 3. Failure And Fix Evidence

First production smoke failed at `POST /api/automation/public-content-report-assets`:

```text
status: failed
message: POST /api/automation/public-content-report-assets failed with 500
root cause: asyncpg.exceptions.StringDataRightTruncationError, value too long for type character varying(20)
failed report_type: public_content_update
```

Evidence file:

```text
tmp/outputs/public-content-report-asset-production-smoke-20260623.json
```

The failed fixture was cleaned before retry:

```text
pre-cleanup: users=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entities=1, entity_snapshots=1, datasets=1, dataset_versions=1, reports=0, report_audit_events=0
post-cleanup exact-ID dry-run: all categories returned zero
```

Local hotfix validation:

```text
cd apps/api && uv run pytest tests/integration/test_sources_tasks.py -k "public_feed"
result: 1 passed, 20 deselected, 1 warning

cd apps/api && uv run ruff check src/data_intelligence_hub/services/automation_service.py tests/integration/test_sources_tasks.py
result: passed

git diff --check
result: passed
```

## 4. Successful Production Gate Evidence

Evidence file:

```text
tmp/outputs/public-content-report-asset-production-smoke-success-20260623.json
```

Successful smoke summary:

```text
feed_url: https://hnrss.org/frontpage
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
Drift checked_tasks: 1
Drift run_started: false
Drift alert_created: false
Report preview report_created: false
Report asset report_created: true
Report asset report_type: public_content
Report asset report_status: generated
Report asset notification_created: false
Report asset content_has_public_content_schema: true
Report asset content_has_collector_schema: true
reports.detail status: generated
```

Boundary flags from the successful smoke:

```text
production_write: true
external_public_feed_fetch: true
dataset_version_created: true
report_asset_created: true
notification_created: false
dataset_export_created: false
provider_call: false
email_sent: false
scheduler_mutated: false
production_browser_run: false
browser_artifact_written: false
```

## 5. Cleanup Evidence

Successful fixture exact-ID cleanup:

```text
pre-cleanup dry-run:
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
reports=1
report_audit_events=1
dataset_drift_events=0
dataset_export_jobs=0

cleanup execute: removed the same scoped objects
post-cleanup exact-ID dry-run: all listed categories returned zero
post-cleanup generic E2E dry-run: all categories returned zero
```

Temporary remote cleanup script and deploy bundles were removed from `/tmp`.

## 6. Supported Claim

Production SHA `fb05c61ab137b1c1cb7519b661d98a97ae0cead6` has one authorized small-scope M5 public content Report asset gate: public RSS collection, DatasetVersion save, read-only drift check, read-only report preview, Report asset creation, Report detail retrieval, and cleanup all completed.

## 7. Unsupported Claim

This gate did not validate recurring RSS monitoring, retained dataset lifecycle, dataset export, provider enrichment, email delivery, scheduler mutation, production browser execution, browser artifact retention, or broader public web/docs diff collection.

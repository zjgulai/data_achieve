---
title: M5 Public Content Production Package Smoke Evidence
doc_type: analysis
module: automation
topic: boundary-m5-public-content-production-smoke
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# M5 Public Content Production Package Smoke Evidence

## 0. Scope

This draft records the authorized M5 Public Web/RSS/Docs production package smoke executed on 2026-06-23 after local M5 dataset/drift/report validation.

Allowed scope:

- deploy current local release commit to production;
- create one temporary `e2e-*@example.com` user;
- create one `public_feed` Source and enabled Task;
- run one public RSS TaskRun against `https://hnrss.org/frontpage`;
- save one `public_content_update` DatasetVersion;
- run read-only `public-content-drift-check`;
- run read-only `public-content-report`;
- clean all scoped production fixtures after evidence capture.

Denied scope:

- no dataset export file;
- no Report asset creation;
- no provider call;
- no email send;
- no scheduler mutation;
- no production browser run;
- no browser artifact write.

## 1. Deployment Evidence

Production was fast-forward deployed from previous production `f04c8ea77cc64f28d391e992012525e1704ec1a3` to:

```text
deployed SHA: e1359759aa1cab157bb98ec8abda4ff580cbfe7d
remote HEAD: e1359759aa1cab157bb98ec8abda4ff580cbfe7d
.deploy-sha: e1359759aa1cab157bb98ec8abda4ff580cbfe7d
preflight: passed
Docker build: passed
Alembic upgrade head: completed
gateway reload: passed after edge became healthy
```

Post-deploy health:

```text
environment=production
status=ok
database=connected
schema=current
schema_revision=202606110023
schema_head=202606110023
scheduler_enabled=true
```

Containers:

```text
data_achieve_scrapy_api healthy
data_achieve_scrapy_db healthy
data_achieve_scrapy_edge healthy
data_achieve_scrapy_web healthy
```

Public page smoke returned `200` for:

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

## 2. Feed Selection

The initial candidate `https://www.python.org/blogs/rss/` returned `404` from the production host and was not used as smoke evidence.

Remote feed probes:

```text
https://hnrss.org/frontpage -> HTTP 200 application/xml
https://xkcd.com/rss.xml -> connection reset by peer
https://www.w3.org/blog/news/feed/ -> 301 to Cloudflare-protected path
```

Chosen feed:

```text
https://hnrss.org/frontpage
```

## 3. Production Smoke Result

Evidence artifact:

```text
tmp/outputs/public-content-production-smoke-20260623.json
```

Smoke summary:

```text
status=passed
feed_url=https://hnrss.org/frontpage
source_id=e537674d-3139-4e22-8d62-f6b826839f4a
task_id=382bcce2-2701-456d-82a1-8b7ce0ebc788
task_run_id=7ff3da09-80c2-49b9-b5fb-290a29f20ea3
dataset_id=ae4f4577-7699-4a44-862b-cb6dbe44b4c1
dataset_version_id=83d13a9e-4726-43d6-8c87-0e4a49f5f7ff
```

TaskRun result:

```text
status=success
records_count=1
entities_count=1
collector log: Collected 5 public feed entries from https://hnrss.org/frontpage.
collector log: Stored 1 new raw records.
collector log: Created 1 snapshots.
```

Dataset preview/save:

```text
preview rows_count=5
matched_runs=1
dataset_type=public_content_update
version_number=1
row_count=5
average_completeness_percent=90
selected_fields=title, link, published_at, author, tags, summary, content_hash, feed_url, feed_title, feed_type
```

Drift check:

```text
requested_tasks=1
checked_tasks=1
blocked_tasks=0
warning_tasks=1
critical_tasks=0
run_started=false
alert_created=false
drift_layers.field_missingness=1
signal_groups.field_missingness=missing:tags
```

Report preview:

```text
entry_count=5
feed_count=1
unique_author_count=5
entries_with_summary=5
content_hash_count=5
report_created=false
run_started=false
latest_entry_count=5
recommendation_count=3
risk_section_count=3
```

## 4. Cleanup Evidence

Generic cleanup dry-run after smoke showed that the standard `e2e-*@example.com` cleanup would remove the temporary user/workspace records but would not cover every source/task object created through demo workspace membership. A targeted exact-ID cleanup script was therefore used from `tmp/scratch/public_content_exact_cleanup.py`, with guardrails:

- match exact `source_id`, `task_id`, `task_run_id`, `dataset_id`, `dataset_version_id`, and email;
- block if Source type is not `public_feed`;
- block if Source URL is not `https://hnrss.org/frontpage`;
- block if Source name does not start with `E2E Public Feed Smoke`;
- block if Dataset type is not `public_content_update`;
- block if Dataset name does not start with `E2E Public Content Dataset`.

Exact cleanup dry-run:

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
dataset_drift_events=0
dataset_export_jobs=0
```

Exact cleanup execute removed the same scoped objects.

Post-cleanup exact-ID dry-run and generic E2E dry-run both returned zero counts for all categories. The remote temporary cleanup script was deleted after verification.

## 5. Supported Claims

Supported:

- Production is deployed to `e1359759aa1cab157bb98ec8abda4ff580cbfe7d`.
- `public_feed` can create a production Source/Task, run one authorized public RSS TaskRun, normalize public feed content into raw record/entity evidence, and save a `public_content_update` DatasetVersion.
- `public-content-drift-check` can evaluate the saved DatasetVersion read-only without starting a new run or creating an alert.
- `public-content-report` can produce a read-only report preview without creating a Report asset, writing a file, starting a run, or sending notification/email.
- Scoped production fixtures were cleaned and verified at both exact-ID and generic E2E cleanup levels.

Unsupported:

- No dataset export was created.
- No Report asset was created.
- No provider call occurred.
- No email was sent.
- No scheduler was mutated.
- No production browser run occurred.
- No browser artifact file was written.
- This does not prove recurring RSS monitoring, retained dataset lifecycle, or large-volume public content collection.

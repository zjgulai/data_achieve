---
title: M5 Public Content Docs Page Production Gate Evidence
doc_type: analysis
module: automation
topic: public-content-docs-page-production-gate
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Docs Page Production Gate Evidence

## Scope

This gate was executed on 2026-06-24 after authorization to continue the next M5 production gate.

Authorization envelope:

```text
scope_type=public_docs_page
scope_value=https://www.iana.org/help/example-domains
allowed: deploy, one scoped user/workspace, one generic_web Source, one enabled Task, one manual docs/page TaskRun, one public_content_update DatasetVersion, one read-only drift check, one public_content_drift DatasetDriftEvent save, one repeated save to verify reuse, one public_content Report asset, exact cleanup
denied: retained canary mutation, provider call, email send, scheduler mutation/tick, Dataset export file write, production browser run, browser artifact write
cleanup_policy=cleanup_after_evidence
```

## Deployment Evidence

```text
previous production HEAD: 68c27e0f9c62d542149eedc5b18439938103b4bb
deployed HEAD: af23cefc92aa9fec336f632a5b1561623811c2fd
.deploy-sha: af23cefc92aa9fec336f632a5b1561623811c2fd
preflight: passed
docker build: passed
alembic upgrade head: completed, schema stayed 202606110023
gateway reload: first attempt stopped while edge health was starting, retry passed after edge became healthy
backup branch: backup/pre-docs-page-gate-20260624-68c27e0
```

## Production Gate Evidence

```text
actor_email: e2e-public-docs-page-20260624034856-8vyj7q@example.com
docs_url: https://www.iana.org/help/example-domains
source_id: a3d15d9c-6301-42a7-a55d-8e3021717662
task_id: 003abf09-e28c-4947-9631-d7d680212f0a
task_run_id: a8317d82-fa1d-49b1-a834-18eafdc47ea1
dataset_id: dc577ed3-a6e1-40be-aab8-e64069c8b965
dataset_version_id: 9f4d3da5-2d87-45bd-8d15-5ef3d8b7a73d
drift_event_id: 05847c1a-5013-4fc8-8d1f-5bec747d0408
repeated_drift_event_id: 05847c1a-5013-4fc8-8d1f-5bec747d0408
report_id: 9b2ec052-0ba8-482f-9902-209da8c51885
```

Collector and Dataset evidence:

```text
Source type: generic_web
Task collector_type: generic_web
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
Dataset type: public_content_update
DatasetVersion row_count: 1
DatasetVersion average_completeness_percent: 100
collector_schema_versions: generic_web.v1
row source_type: generic_web
row content_kind: html_snapshot
row title: Example Domains
row link: https://www.iana.org/help/example-domains
row site_url: https://www.iana.org
row content_hash: d3362b3fe187484e529f2504d628e6b9f0f5c8a2ef10fc09efddcc1631d0be21
row text_length: 1217
```

Drift and Report evidence:

```text
drift checked_tasks: 1
drift status: ok
drift row_change: unchanged
drift run_started: false
drift alert_created: false
history before save: total=0
history after save: total=1
drift event_type: public_content_drift
drift event status: ok
repeated drift event reused: true
report preview entry_count: 1
report preview content_hash_count: 1
report preview report_created: false
report asset report_created: true
report asset report_type: public_content
report asset status: generated
report asset notification_created: false
stored report detail: passed
```

## Cleanup Evidence

Initial script attempt:

```text
result: failed before drift/report creation
reason: second identical static-page TaskRun succeeded but raw record was deduplicated, so records_count=0
cleanup: exact-ID cleanup executed
post-cleanup exact dry-run: all categories zero
```

Successful gate cleanup:

```text
exact dry-run before execute: users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entity_snapshots=1, entities=1, datasets=1, dataset_versions=1, dataset_drift_events=1, reports=1, report_audit_events=1, dataset_export_jobs=0
cleanup execute: succeeded
post-cleanup exact dry-run: all categories zero
generic E2E cleanup dry-run: all categories zero
temporary host bundle/script: removed
temporary container cleanup script: removed
```

## Post-Gate Smoke

```text
health: production/ok/connected/current
remote HEAD: af23cefc92aa9fec336f632a5b1561623811c2fd
.deploy-sha: af23cefc92aa9fec336f632a5b1561623811c2fd
containers: api/db/edge/web healthy
/dashboard, /automation, /datasets, /tasks, /sources, /raw-records, /reports, /alerts, /notifications, /projects, /signals, /entities, /toolkit: 200
```

## Supported Claim

Production now includes the M5 `generic_web` docs/page path, and one scoped production gate proved:

- `generic_web` public docs/page TaskRun.
- `public_content_update` DatasetVersion with `generic_web.v1` collector schema and content hash.
- Read-only public-content drift check.
- `public_content_drift` DatasetDriftEvent save/list/idempotent reuse.
- `public_content` Report asset creation and detail retrieval.
- Exact-ID cleanup plus generic cleanup dry-run to zero.

## Unsupported Claim

This gate does not prove retained canary mutation, recurring monitoring, scheduler refresh, multi-day TTL, automatic cleanup, provider enrichment, email sending, Dataset export file writing, production browser execution, or browser artifact writing.

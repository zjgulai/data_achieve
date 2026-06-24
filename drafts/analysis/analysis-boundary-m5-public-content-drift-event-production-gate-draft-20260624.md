---
title: M5 Public Content Drift Event Production Gate
doc_type: analysis
module: automation
topic: boundary-m5-public-content-drift-event-production-gate
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Drift Event Production Gate

## 1. Authorization Envelope

This gate was executed after explicit approval to continue the next M5 step.

Allowed side effects:

- Deploy local public-content drift-event persistence code to production.
- Create one scoped production user/workspace.
- Create one scoped `public_feed` Source, enabled Task, and manual TaskRun against `https://hnrss.org/frontpage`.
- Save one `public_content_update` DatasetVersion.
- Run one read-only public-content drift check.
- Save one `public_content_drift` DatasetDriftEvent.
- Submit the same drift event payload again to verify reuse/idempotency.
- Clean the scoped fixture set after evidence.

Denied side effects:

- Provider call.
- Email send.
- Scheduler mutation or scheduler tick.
- Dataset export file write.
- Report asset creation.
- Production browser run.
- Browser artifact write.
- Mutation of the retained public-content canary from 2026-06-23.

## 2. Deployment Evidence

Production was updated by Git bundle and fast-forward merge on the remote app checkout.

```text
previous production HEAD: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
deployed HEAD: 68c27e0f9c62d542149eedc5b18439938103b4bb
.deploy-sha: 68c27e0f9c62d542149eedc5b18439938103b4bb
remote branch: main...origin/main [ahead 14]
preflight: passed
docker build: passed
alembic upgrade head: completed, schema stayed 202606110023
gateway reload: first attempt blocked while edge health was starting; retry passed after edge became healthy
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
containers: api/db/edge/web healthy
```

## 3. Gate Evidence

Production smoke output:

```text
output: tmp/outputs/public-content-drift-event-production-gate-20260624.json
actor_email: e2e-public-drift-event-20260624010551-nj20wh@example.com
source_id: d46bbd8e-cbeb-434c-a351-af4ec680e8d9
task_id: 73af3237-414e-4cfe-b39c-57935f2216f4
task_run_id: e4a4f1bb-c21e-4378-8abe-d0ada033b1e6
dataset_id: acc585e5-0388-4cfe-847c-90e490e68056
dataset_version_id: 961eb51d-ae1e-407f-9cbb-46dfd02bf8a7
drift_event_id: 6acbd871-e0f8-4580-a7c7-b3d2459962f1
repeated_drift_event_id: 6acbd871-e0f8-4580-a7c7-b3d2459962f1
```

Observed behavior:

```text
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion schema_version: public_content_update.v1
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
Drift checked_tasks: 1
Drift status: warning
Drift warning_tasks: 1
Drift critical_tasks: 0
Drift signal_groups: field_missingness -> missing:tags
Drift run_started: false
Drift alert_created: false
History before save: total=0
DriftEvent event_type: public_content_drift
DriftEvent status: warning
DriftEvent thresholds: completeness_drop_threshold_percent=10, freshness_grace_hours=24
DriftEvent saved audit: public_content_drift_event_saved
Repeated submit: reused same drift_event_id
Repeated audit: public_content_drift_event_reused
History after save: total=1
```

## 4. Cleanup Evidence

Initial exact cleanup dry-run found the intended scoped fixture set:

```text
users=1
workspaces=1
workspace_members=2
notifications=1
sources=1
collection_tasks=1
task_runs=1
raw_records=1
entity_snapshots=1
entities=1
datasets=1
dataset_versions=1
dataset_drift_events=1
dataset_export_jobs=0
export_artifact_files=0
```

The first cleanup execute exposed a cleanup helper boundary before commit:

```text
failure: deleting Entity while another EntitySnapshot still referenced it
effect: transaction failed before commit; post-failure dry-run still showed the scoped fixture set present
fix: temporary cleanup script expanded snapshot/raw_record dependencies through the scoped Entity and flushed after deleting snapshots/raw records
```

The patched exact cleanup dry-run stayed scoped to the same user/source/task/dataset and expanded only local dependencies:

```text
users=1
workspaces=1
workspace_members=2
notifications=1
sources=1
collection_tasks=1
task_runs=1
raw_records=2
entity_snapshots=2
entities=1
datasets=1
dataset_versions=1
dataset_drift_events=1
dataset_export_jobs=0
export_artifact_files=0
```

Cleanup execute succeeded, then exact post-cleanup dry-run returned zero for all categories:

```text
users=0
workspaces=0
workspace_members=0
notifications=0
sources=0
collection_tasks=0
task_runs=0
raw_records=0
entity_snapshots=0
entities=0
datasets=0
dataset_versions=0
dataset_drift_events=0
dataset_export_jobs=0
export_artifact_files=0
```

Generic E2E cleanup dry-run also returned zero for all categories. Temporary host and container cleanup scripts were removed; the container file required root removal because the initial delete ran as the app user.

## 5. Post-Gate Smoke

Final production checks:

```text
remote HEAD: 68c27e0f9c62d542149eedc5b18439938103b4bb
.deploy-sha: 68c27e0f9c62d542149eedc5b18439938103b4bb
health: production/ok/connected/current
containers: api/db/edge/web healthy
```

Public page smoke:

```text
/dashboard 200
/automation 200
/datasets 200
/tasks 200
/sources 200
/raw-records 200
/reports 200
/alerts 200
/notifications 200
/projects 200
/signals 200
/entities 200
/toolkit 200
```

## 6. Boundary

Supported claim: production now includes the dedicated public-content drift-event persistence path and one scoped production gate proved `public_content_drift` DatasetDriftEvent save, list, and idempotent reuse. The scoped fixture set was cleaned to zero.

Unsupported claim: the retained public-content canary has been updated with a drift event, recurring monitoring is active, scheduler refresh is configured, provider enrichment ran, email was sent, a Report asset was created in this gate, a Dataset export file was written in this gate, a production browser ran, or browser artifacts were written.

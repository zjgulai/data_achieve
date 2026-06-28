---
title: M5 Public Content Scheduler Approval Production Gate Evidence
doc_type: analysis
module: automation
topic: boundary-m5-public-content-scheduler-gate
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Scheduler Approval Production Gate Evidence

## 1. Scope

This draft records the scoped M5 public-content scheduler approval production gate executed on 2026-06-24.

Authorization envelope:

```text
scope_type=public_feed_schedule_approval
scope_value=https://hnrss.org/frontpage
allowed: deploy, one scoped user/workspace, one public_feed Source, one enabled Task, one manual public feed TaskRun, one public_content_update DatasetVersion, one public-content schedule approval mutation, exact cleanup
denied: retained canary mutation, provider call, email send, scheduler tick execution, Dataset export file write, Report asset creation, production browser run, browser artifact write
cleanup_policy: cleanup_after_evidence
```

## 2. Local Implementation

Implemented production-bound scheduler approval for public-content DatasetVersion lineage:

```text
route: POST /api/automation/public-content-schedule-approve
request schema: AutomationPublicContentScheduleApproveRequest
service: approve_public_content_schedule()
accepted dataset_type: public_content_update
accepted task collector types: public_feed, generic_web
required task status: enabled
cron gate: unsupported cron returns schedule_cron_unsupported
audit event: public_content_schedule_approved
side effect: task schedule metadata only
```

Validation:

```text
focused integration: 3 passed, 20 deselected, 1 warning
focused scheduler approval regression: 1 passed, 22 deselected, 1 warning
API full pytest: 108 passed, 1 warning
API ruff: All checks passed
Web lint: passed
Web unit: 8 passed
Web build: passed
git diff --check: passed
```

## 3. Deployment Evidence

```text
previous production HEAD: af23cefc92aa9fec336f632a5b1561623811c2fd
deployed HEAD: a81154426fd4e942fc9439de3dcbd9c816122562
.deploy-sha: a81154426fd4e942fc9439de3dcbd9c816122562
preflight: passed
docker build: passed
alembic upgrade head: completed, schema stayed 202606110023
gateway reload: corrected command passed after edge became healthy
health: production/ok/connected/current
containers: api/db/edge/web healthy
page smoke: /dashboard /automation /datasets /tasks /sources /raw-records /reports /alerts /notifications /projects /signals /entities /toolkit all 200
```

## 4. Production Gate Evidence

```text
actor_email: e2e-public-schedule-20260624042715-5vkxnc@example.com
feed_url: https://hnrss.org/frontpage
source_id: 9f43899f-7578-4df7-a157-62cc14b5b93b
task_id: 6338d234-554d-4527-9f51-5f695e646bdf
task_run_id: 758783cc-4eb0-43f7-b229-bf9ab749cbd7
dataset_id: 1a9f6b26-d1e2-4f8a-8611-4efb42c359b8
dataset_version_id: 1a9ce0f2-b7e3-4437-bb4e-a1c45c1a78b7
schedule_policy: manual_refresh_only
schedule_cron: null
freshness_target_hours: 72
approved schedules: 1
blocked schedules: 0
run_started: false
scheduler_tick_started: false
task runs before approval: 1
task runs after approval: 1
task run IDs unchanged: true
```

Boundary facts:

```text
production_write: true
external_public_feed_fetch: true
dataset_version_created: true
scheduler_approval_mutated_task_config: true
scheduler_tick_started: false
new_task_run_after_schedule_approval: false
dataset_export_created: false
report_asset_created: false
provider_call: false
email_sent: false
production_browser_run: false
browser_artifact_written: false
```

## 5. Cleanup Evidence

```text
exact cleanup dry-run: users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entity_snapshots=1, entities=1, datasets=1, dataset_versions=1
cleanup execute: succeeded
post-cleanup exact dry-run: all categories zero
generic E2E cleanup dry-run: all categories zero
post-cleanup health: production/ok/connected/current
post-cleanup containers: api/db/edge/web healthy
temporary host/container cleanup scripts and remote bundle: removed
```

## 6. Supported And Unsupported Claims

Supported:

- Production includes the public-content scheduler approval path at SHA `a81154426fd4e942fc9439de3dcbd9c816122562`.
- One scoped production fixture proved schedule approval metadata mutation for a `public_content_update` DatasetVersion lineage.
- Approval did not start a scheduler tick or create a new TaskRun.
- Exact-ID cleanup and generic E2E cleanup dry-run returned zero after evidence capture.

Unsupported:

- Retained public-content canary scheduler refresh.
- Scheduler tick execution or recurring monitoring.
- Multi-day TTL or automated cleanup lifecycle.
- Provider enrichment, product/report/subscription email, Dataset export creation, Report asset creation, production browser run, or browser artifact write in this gate.

---
title: P1 Production Read-Only And Dry-Run Inventory
doc_type: analysis
module: operations
topic: boundary-leftovers-p1
status: draft
created: 2026-06-22
updated: 2026-06-22
owner: self
source: human+ai
---

# P1 Production Read-Only And Dry-Run Inventory

## 0. Boundary

This P1 pass collected production read-only and dry-run evidence only.

Not executed:

- No `--execute` cleanup.
- No demo seed.
- No production write E2E.
- No provider call.
- No email send.
- No scheduler mutation.
- No real browser-harness run.

## 1. Live State

### Public health

Command class: public `GET /api/health`.

Result:

```json
{
  "service": "Data Intelligence Hub API",
  "environment": "production",
  "status": "ok",
  "database": "connected",
  "schema": "current",
  "schema_revision": "202606110023",
  "schema_head": "202606110023",
  "scheduler_enabled": true
}
```

Evidence grade: `L3-production-read-only`.

### Remote SHA and compose

Command class: SSH read-only inspection under `/opt/data-achieve-scrapy/app`.

Result:

```text
remote_head=e97810adb86f39f16efe96b9f2b7f0760f5acf7e
deploy_sha=e97810adb86f39f16efe96b9f2b7f0760f5acf7e
branch=main
api=healthy
db=healthy
edge=healthy
web=healthy
```

Note: `.deploy-sha` is untracked in the remote git worktree by design for deployment bookkeeping.

Evidence grade: `L3-production-read-only`.

### Public page smoke

Command class: public `GET` status check.

Result:

```text
/api/health 200
/dashboard 200
/automation 200
/datasets 200
/tasks 200
/sources 200
/alerts 200
/notifications 200
/projects 200
/signals 200
/raw-records 200
/entities 200
/toolkit 200
```

Note: first local attempt using bare `curl` failed because the shell could not resolve `curl`; rerun with `/usr/bin/curl` passed.

Evidence grade: `L3-production-read-only`.

## 2. Demo Cleanup Dry-Run

Command class: production Docker compose dry-run through `scripts/cleanup-demo-noise.sh`, without `--execute`.

Dry-run result:

```json
{
  "dry_run": true,
  "workspace_id": "bf51c6a8-fba5-5528-ac91-89ffd84f85c2",
  "counts": {
    "alert_events": 15,
    "alert_rules": 6,
    "collection_tasks": 12,
    "entities": 10,
    "entity_snapshots": 42,
    "evidences": 26,
    "intelligence_items": 8,
    "notifications": 42,
    "projects": 0,
    "raw_records": 34,
    "report_audit_events": 0,
    "report_subscription_runs": 0,
    "report_subscriptions": 0,
    "reports": 14,
    "signals": 8,
    "sources": 12,
    "task_runs": 84
  }
}
```

Interpretation:

- Demo workspace has non-curated runtime noise candidates.
- This pass did not delete or modify those records.
- P2 should decide whether to request explicit `--execute` cleanup authorization.

Evidence grade: `L2-fixture-or-dry-run`.

## 3. E2E Fixture Cleanup Dry-Run

Command class: production Docker compose dry-run through `scripts/cleanup-e2e-fixtures.sh --older-than-hours 0`, without `--execute`.

Dry-run result:

```json
{
  "dry_run": true,
  "cutoff": "2026-06-22T08:25:11.728335+00:00",
  "counts": {
    "alert_events": 0,
    "alert_rules": 0,
    "cleaning_plans": 0,
    "collection_tasks": 0,
    "dataset_drift_events": 0,
    "dataset_export_jobs": 0,
    "dataset_versions": 0,
    "datasets": 0,
    "entities": 0,
    "entity_snapshots": 0,
    "evidences": 0,
    "extraction_plans": 0,
    "intelligence_feedback": 0,
    "intelligence_items": 0,
    "notifications": 0,
    "projects": 0,
    "raw_records": 0,
    "report_audit_events": 0,
    "report_subscription_runs": 0,
    "report_subscriptions": 0,
    "reports": 0,
    "signals": 0,
    "site_analyses": 0,
    "sources": 0,
    "task_runs": 0,
    "users": 0,
    "workspace_members": 0,
    "workspaces": 0
  }
}
```

Interpretation:

- No matching `e2e-*@example.com` fixture residue was found at `--older-than-hours 0`.
- No cleanup execute is needed for E2E fixtures at this point.

Evidence grade: `L2-fixture-or-dry-run`.

## 4. Email Channel Status

The authenticated API route requires login, and login may run demo membership/notification repair logic. To keep this P1 pass narrower, status was inspected inside the production API container from settings only, without calling `/api/notifications/email-channel/test`.

Result:

```json
{
  "status": "ready",
  "configured": true,
  "missing_settings": [],
  "host_configured": true,
  "port": 587,
  "sender_configured": true,
  "auth_configured": true,
  "tls_mode": "starttls",
  "reason": null
}
```

Interpretation:

- SMTP configuration shape is ready.
- This does not prove email delivery.
- No test email was sent.

Evidence grade: `L3-production-read-only` for configuration presence; no delivery grade.

## 5. Gate Result

| Gate | Result | Evidence grade | Next step |
|---|---|---|---|
| Live SHA/health/schema/compose | Pass | L3 | Continue monitoring during next phase |
| Public page smoke | Pass | L3 | No action |
| Demo cleanup dry-run | Non-zero candidates | L2 | P2 explicit cleanup execute decision |
| E2E fixture cleanup dry-run | Zero candidates | L2 | No execute needed |
| Email channel status | Ready configuration | L3 config-only | Test send requires separate authorization |

## 6. Next Recommendation

Proceed to P2 with a narrow decision:

1. Request explicit authorization for `production demo cleanup --execute` using the dry-run counts above.
2. If authorized, execute cleanup, then run a read-only recount.
3. Do not run demo seed unless the post-cleanup demo counts or UI smoke prove a demo-data gap.

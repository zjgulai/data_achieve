---
title: P2 Production Demo Cleanup Execution
doc_type: analysis
module: operations
topic: boundary-leftovers-p2-demo-cleanup
status: draft
created: 2026-06-22
updated: 2026-06-22
owner: self
source: human+ai
---

# P2 Production Demo Cleanup Execution

## 0. Boundary

User authorization: "同意执行 P2".

Interpreted scope:

- Execute `production demo cleanup --execute` against the P1 dry-run candidate set.
- Run post-cleanup dry-run recount.
- Recheck production health, public pages, SHA, and compose status.

Not executed:

- No demo seed.
- No E2E fixture cleanup execute.
- No production write E2E.
- No provider call.
- No email send.
- No scheduler mutation.
- No real browser-harness run.

## 1. Execute Result

Command class: production Docker compose cleanup through `scripts/cleanup-demo-noise.sh --execute`.

Result:

```json
{
  "dry_run": false,
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

Evidence grade: `L4-authorized-live` for demo cleanup only.

## 2. Post-Cleanup Recount

Command class: production Docker compose dry-run through `scripts/cleanup-demo-noise.sh`, without `--execute`.

Result:

```json
{
  "dry_run": true,
  "workspace_id": "bf51c6a8-fba5-5528-ac91-89ffd84f85c2",
  "counts": {
    "alert_events": 0,
    "alert_rules": 0,
    "collection_tasks": 0,
    "entities": 0,
    "entity_snapshots": 0,
    "evidences": 0,
    "intelligence_items": 0,
    "notifications": 0,
    "projects": 0,
    "raw_records": 0,
    "report_audit_events": 0,
    "report_subscription_runs": 0,
    "report_subscriptions": 0,
    "reports": 0,
    "signals": 0,
    "sources": 0,
    "task_runs": 0
  }
}
```

Interpretation:

- Demo runtime noise candidates were cleared.
- The recount found no remaining non-curated demo cleanup candidates.
- No evidence currently requires demo seed.

Evidence grade: `L2-fixture-or-dry-run` for recount.

## 3. Service Recheck

### Health

```json
{
  "environment": "production",
  "status": "ok",
  "database": "connected",
  "schema": "current",
  "schema_revision": "202606110023",
  "schema_head": "202606110023",
  "scheduler_enabled": true
}
```

### Public page smoke

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

### Remote SHA and compose

```text
remote_head=e97810adb86f39f16efe96b9f2b7f0760f5acf7e
deploy_sha=e97810adb86f39f16efe96b9f2b7f0760f5acf7e
api=healthy
db=healthy
edge=healthy
web=healthy
```

Evidence grade: `L3-production-read-only`.

## 4. Gate Result

| Gate | Result | Evidence grade |
|---|---|---|
| Demo cleanup execute | Completed against P1 candidate set | L4 authorized live cleanup |
| Post-cleanup dry-run recount | All candidate counts zero | L2 dry-run |
| Health/schema | OK/current at `202606110023` | L3 read-only |
| Public page smoke | All checked routes `200` | L3 read-only |
| Compose | `api/db/edge/web` healthy | L3 read-only |
| Demo seed | Not needed from available evidence | Not executed |

## 5. Next Recommendation

Proceed to P3 only after a separate authorization envelope is accepted:

- Scope: L4 production write E2E.
- Identity: one-time account/workspace, not demo account.
- Required evidence: created IDs, cleanup dry-run, cleanup execute, recount.
- Explicit exclusions unless separately authorized: provider call, email send, scheduler mutation, real browser-harness run.

---
title: "M5 Public Content Retained TTL Midpoint Observation"
status: "draft"
created_at: "2026-06-25"
scope: "production retained public-content TTL midpoint read-only and dry-run observation"
evidence_level: "L3-production-read-only plus L4-production-dry-run"
cleanup_executed: false
---

# M5 Public Content Retained TTL Midpoint Observation

## Decision

This pass keeps the retained public-content canary in place and runs only read-only/dry-run checks. It does not pass `--execute`, does not delete retained assets, does not mutate scheduler state, does not create Dataset exports or Reports, and does not call providers, send email, run a production browser, or write browser artifacts.

## Artifacts

- `tmp/outputs/retained-public-content-ttl-midpoint-identity-20260625.json`
- `tmp/outputs/retained-public-content-ttl-midpoint-preflight-20260625.json`
- `tmp/outputs/retained-public-content-ttl-midpoint-default-168h-20260625.json`
- `tmp/outputs/retained-public-content-ttl-midpoint-48h-20260625.json`
- `tmp/outputs/retained-public-content-ttl-midpoint-0h-20260625.json`

## Identity And Health

- Checked at: `2026-06-25T00:51:59Z`.
- Active app `HEAD`: `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
- Active app `.deploy-sha`: `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
- API compose working directory: `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`.
- Web compose working directory: `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`.
- Health: `production`, `ok`, `connected`, `current`.
- Schema revision/head: `202606110023` / `202606110023`.
- Scheduler enabled: `true`.

## Retained Preflight

- Retained account: `retained-public-content-20260623123816-90w0q7@example.com`.
- Source `c86b280c-0315-4d93-bcd7-37786996a22b`: present, `public_feed`, `https://hnrss.org/frontpage`.
- Task `b8a4cb3f-abe9-48f6-bb66-7ff4962bcdc6`: present, `enabled`, `public_feed`.
- Task schedule policy: `manual_refresh_only`.
- Task `schedule_cron`: `null`.
- Task runs: `2`, both `success`.
- Dataset `ee4a4a7a-1ea8-4864-b10d-031b365e5efb`: present, `public_content_update`.
- DatasetVersion `6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8`: present, `row_count=5`, `average_completeness_percent=90`.
- Retained counts: `dataset_drift_events=1`, `dataset_export_jobs=1`, `reports=1`, `report_audit_events=1`.

## Dry-Run Results

Default 168h dry-run:

```text
dry_run=true
retention_hours=168
cleanup_ready=true
all cleanup candidate counts=0
provider_call=false
email_sent=false
scheduler_tick_started=false
```

48h dry-run:

```text
dry_run=true
retention_hours=48
cleanup_ready=true
all cleanup candidate counts=0
provider_call=false
email_sent=false
scheduler_tick_started=false
```

0h graph dry-run:

```text
dry_run=true
retention_hours=0
cleanup_ready=true
users=1
workspaces=1
workspace_members=2
sources=1
collection_tasks=1
task_runs=2
raw_records=1
entities=1
entity_snapshots=1
datasets=1
dataset_versions=1
dataset_drift_events=1
dataset_export_jobs=1
reports=1
report_audit_events=1
notifications=1
export_artifact_files=1
export_artifact_path_violations=0
```

## Supported Claims

1. The retained public-content canary is still present on 2026-06-25.
2. The retained task remains `manual_refresh_only` with no cron schedule.
3. Default 168h TTL has not reached the retained canary yet.
4. The 48h cutoff also does not yet match the retained canary at `2026-06-25T00:52Z`.
5. The 0h dry-run still covers the full retained graph and reports no export artifact path violation.

## Unsupported Claims

- Default 168h multi-day TTL is complete.
- Cleanup execute has run.
- Retained canary assets were deleted.
- Providers ran.
- Email was sent.
- Scheduler state was mutated.
- A Dataset export or Report asset was created by this pass.
- A production browser ran or browser artifacts were written.

## Next Gate

Keep the canary retained until the default 168h TTL window can be observed directly, or treat retained cleanup execute as a separate explicit decision gate with the latest dry-run artifact and rollback notes.

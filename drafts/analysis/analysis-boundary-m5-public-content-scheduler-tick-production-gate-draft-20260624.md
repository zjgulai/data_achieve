---
title: "M5 Public Content Scheduler Tick Production Gate"
status: "draft"
created_at: "2026-06-24"
scope: "production scoped scheduler tick and recurring monitoring read check"
evidence_level: "L4-authorized-live"
production_sha: "d11d5a477ea3125649f7674495bfca5b93148e32"
---

# M5 Public Content Scheduler Tick Production Gate

## Decision

This gate proves one scoped production public-content task can move from schedule approval into an actual background scheduler tick. It does not prove broad scheduler SLA, multi-tenant recurring reliability, retained-canary refresh, provider calls, email/report subscription delivery, dataset export, production browser execution, or browser artifact writes.

## Fresh Evidence

- Production health before and after the gate returned `environment=production`, `status=ok`, `database=connected`, `schema_revision=schema_head=202606110023`, and `scheduler_enabled=true`.
- Remote `.deploy-sha` remained `d11d5a477ea3125649f7674495bfca5b93148e32`.
- Preflight inventory at `2026-06-24T08:25:50Z` showed latest tick `22be6cb3-1dcd-4f54-8ab2-1c18e4d5b95f`, `scanned=84`, `due=0`, `started=0`, `report_subscriptions_due=0`, and `report_subscription_runs_total=0`.
- Passing gate artifact: `tmp/outputs/public-content-scheduler-tick-production-gate-20260624.json`.
- Scoped account: `e2e-public-scheduler-tick-20260624082600-z6e6h4@example.com`.
- Scoped Source `bf1f9150-a6e7-4f73-84f6-97d561f3855f` and Task `01a7e28d-489f-47f1-a67a-bcbc1b0369d1` used `public_feed` against `https://hnrss.org/frontpage`.
- Baseline manual TaskRun `9301b10f-8066-4ec0-9ae2-b3f7ca38aaa4` saved Dataset `ba261a74-11ed-41d7-8507-fb96c59343fe` and DatasetVersion `75a13ff2-040a-4ffb-b6dc-c152fc2d7f3e`.
- Schedule approval set `schedule_policy=auto_freshness`, `schedule_cron=* * * * *`, and `freshness_target_hours=1`; approval itself kept `run_started=false` and `scheduler_tick_started=false`.
- Background scheduler tick `47356df1-8f5e-442c-883b-f46ec51c6bbc` finished at `2026-06-24T08:27:35Z` with `scanned=85`, `due=1`, `started=1`, `task_errors=0`, `report_subscriptions_due=0`, and `report_subscriptions_started=0`.
- Scheduler-created TaskRun `258b2265-5f5a-4505-a9f7-400aee863259` finished `success`. It stored `records_count=0` because the public feed snapshot deduplicated against the baseline run; the passing script treats this as a valid recurring execution boundary when collector execution and deduplication logs are present.
- Read-only drift check after the scheduler run returned `checked_tasks=1`, `run_started=false`, `alert_created=false`, `critical_tasks=1`, `missing_field_tasks=1`, and `removed_rows=5`. This is expected for a deduplicated latest run and proves monitoring risk surfacing, not a saved drift event.
- Exact cleanup dry-run found the scoped fixture; execute removed it; post-cleanup dry-run returned zero for users, workspaces, members, sources, tasks, task runs, raw records, entities, snapshots, datasets, dataset versions, drift events, export jobs, reports, report audit events, notifications, signals, and evidences.
- Post-cleanup inventory at `2026-06-24T08:29:28Z` returned latest normal tick `460d4443-30ee-48e4-92f2-d98e0f3654e1`, `scanned=84`, `due=0`, `started=0`, `report_subscriptions_due=0`, `report_subscriptions_started=0`, `task_runs_total=109`, and `report_subscription_runs_total=0`.

## Boundary

Facts:

- One authorized production schedule approval mutated a scoped public-content Task config.
- One background scheduler tick started exactly one scoped public-content TaskRun.
- Read-only drift monitoring ran after the scheduled run and did not start another run or create alerts.
- Cleanup-after-evidence returned the scoped production fixture to zero.

Non-claims:

- This is not a proof of global scheduler SLA or multi-day recurring reliability.
- This is not a retained canary update.
- This did not create a Dataset export, Report asset, DatasetDriftEvent, ReportSubscriptionRun, product/report email, provider call, production browser run, or browser artifact.

## Notes

An initial script attempt at `2026-06-24T08:19Z` proved the same scheduler path but failed its own assertion because it required `records_count > 0`. The scheduled TaskRun was `success`, and tick metrics were `due=1` / `started=1`, but the public feed raw record deduplicated to zero new records. The fixture from that attempt was cleaned with exact-ID cleanup before the passing rerun.

---
title: "M5 Public Content Retained Refresh Drift Scheduler Gate"
status: "draft"
created_at: "2026-06-24"
scope: "production retained canary scheduler refresh, drift event persistence, cleanup dry-run lineage fix"
evidence_level: "L4-authorized-live"
production_sha_after_fix: "3c92fcbf2230e1b0b4eef71afea2b8e7547d3331"
---

# M5 Public Content Retained Refresh Drift Scheduler Gate

## Decision

This gate refreshes the existing retained public-content canary instead of creating and cleaning a new scoped fixture. It proves one retained `public_feed` canary task can be temporarily scheduled, executed by the production scheduler, restored to manual mode, and saved as a retained `public_content_drift` event.

## Fresh Evidence

- Preflight artifact: `tmp/outputs/retained-public-content-preflight-20260624.json`.
- Live refresh artifact: `tmp/outputs/retained-public-content-scheduler-drift-refresh-20260624.json`.
- Production retained canary: `retained-public-content-20260623123816-90w0q7@example.com`.
- Retained Source `c86b280c-0315-4d93-bcd7-37786996a22b`, Task `b8a4cb3f-abe9-48f6-bb66-7ff4962bcdc6`, Dataset `ee4a4a7a-1ea8-4864-b10d-031b365e5efb`, DatasetVersion `6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8`.
- Preflight counts before refresh: `task_runs=1`, `dataset_drift_events=0`, `dataset_export_jobs=1`, `reports=1`, `report_audit_events=1`.
- Temporary schedule approval set `schedule_policy=auto_freshness`, `schedule_cron=* * * * *`, and `freshness_target_hours=1`; approval itself reported `run_started=false`.
- Background scheduler tick `b1fa40d1-215a-469c-b2b7-f841fb8edcab` recorded `scanned=84`, `due=1`, `started=1`, `task_errors=0`, `report_subscriptions_due=0`, and `report_subscriptions_started=0`.
- Retained scheduler TaskRun `fb2dc909-f125-402e-8759-7443e0214e55` finished `success` with `records_count=1` and `entities_count=1`.
- The retained task was restored to `schedule_policy=manual_refresh_only`, `schedule_cron=null`, and `freshness_target_hours=72`.
- Drift event `73fbce88-ea11-4cc6-8c61-c6088d1ccaec` was saved as `event_type=public_content_drift`, `status=critical`, `checked_tasks=1`, `added_rows=5`, `removed_rows=5`, `run_started=false`, and `alert_created=false`.
- Postflight counts after refresh: `task_runs=2`, `dataset_drift_events=1`, `dataset_export_jobs=1`, `reports=1`, `report_audit_events=1`.

## Cleanup Dry-Run Lineage Finding

The first post-refresh retained cleanup dry-run showed `dataset_drift_events=1` but still reported `task_runs=1` even though the retained task had two runs. That exposed a cleanup lineage gap: the retained cleanup tool followed the DatasetVersion source run but did not include later TaskRuns from the same retained task.

Fix:

- Updated `apps/api/src/data_intelligence_hub/maintenance/public_content_retention.py` to include all TaskRuns for retained task IDs already reached through retained lineage.
- Updated `apps/api/tests/unit/test_public_content_retention.py` with a member-workspace retained fixture containing a later refresh run.
- Local validation passed:
  - `uv run pytest tests/unit/test_public_content_retention.py -q`: `3 passed`
  - `uv run pytest tests/unit/test_public_content_retention.py tests/unit/test_e2e_cleanup.py -q`: `5 passed`
  - `uv run ruff check src/data_intelligence_hub/maintenance/public_content_retention.py tests/unit/test_public_content_retention.py`: passed
  - `uv run pytest -q`: `111 passed, 1 warning`

Deployment:

- Remote commit and `.deploy-sha`: `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
- Deploy preflight passed, API image rebuilt, API recreated healthy, and `api/db/edge/web` were healthy.
- Production health returned `environment=production`, `status=ok`, `database=connected`, `schema_revision=schema_head=202606110023`, and `scheduler_enabled=true`.
- Route smoke artifact: `tmp/outputs/retained-public-content-refresh-post-deploy-route-smoke-20260624.json`; `/dashboard`, `/automation`, `/datasets`, `/tasks`, `/sources`, `/raw-records`, `/reports`, `/alerts`, `/notifications`, `/projects`, `/signals`, `/entities`, and `/toolkit` returned `200`.

Post-fix retained cleanup dry-run:

- Artifact: `tmp/outputs/retained-public-content-cleanup-dryrun-after-lineage-fix-20260624.json`.
- `dry_run=true`, `retention_hours=0`, `cleanup_ready=true`, `export_artifact_path_violations=0`.
- Counts: `users=1`, `workspaces=1`, `workspace_members=2`, `sources=1`, `collection_tasks=1`, `task_runs=2`, `raw_records=1`, `entities=1`, `entity_snapshots=1`, `datasets=1`, `dataset_versions=1`, `dataset_drift_events=1`, `dataset_export_jobs=1`, `reports=1`, `report_audit_events=1`, `notifications=1`, `export_artifact_files=1`.
- Post-fix preflight artifact: `tmp/outputs/retained-public-content-preflight-after-lineage-fix-20260624.json`; retained task remained `manual_refresh_only` with `schedule_cron=null`.

## Boundary

Facts:

- This is an authorized live retained canary update.
- One retained production TaskRun and one retained `public_content_drift` DatasetDriftEvent were added and intentionally retained.
- The retained cleanup dry-run plan now sees both retained TaskRuns.
- No retained cleanup execute ran.

Non-claims:

- This does not delete the retained canary.
- This does not prove multi-day TTL, automatic cleanup, provider enrichment, email delivery, Dataset export creation, Report asset creation, production browser execution, or browser artifact writing.
- A post-deploy scheduler preflight showed one unrelated `manual_json` due candidate. It was not the retained public-content task and was not mutated by this gate.

---
title: "M5 Public Content Retained TTL Observation Baseline"
status: "draft"
created_at: "2026-06-24"
scope: "production retained canary TTL dry-run observation baseline"
evidence_level: "L4-production-read-only-dry-run"
cleanup_executed: false
---

# M5 Public Content Retained TTL Observation Baseline

## Decision

This pass keeps the retained public-content canary in place and records a TTL observation baseline. It does not execute cleanup, delete the canary, call providers, send email, start a browser, write browser artifacts, create exports, create reports, or mutate scheduler configuration.

## Fresh Evidence

- Health: `GET https://scrapy.lute-tlz-dddd.top/api/health` returned `environment=production`, `status=ok`, `database=connected`, `schema=current`, `schema_revision=202606110023`, `schema_head=202606110023`, and `scheduler_enabled=true`.
- Deploy identity check, corrected after follow-up diagnosis: remote working tree `HEAD=3c92fcbf2230e1b0b4eef71afea2b8e7547d3331` and active app marker `/opt/data-achieve-scrapy/app/.deploy-sha=3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`; the earlier mismatch came from reading stale parent marker `/opt/data-achieve-scrapy/.deploy-sha=dda2786638d4aac8647bbff8b3694b05113678f3`.
- Compose status: `api`, `db`, `edge`, and `web` were running healthy.
- Preflight artifact: `tmp/outputs/retained-public-content-ttl-observation-preflight-20260624.json`.
- Default TTL dry-run artifact: `tmp/outputs/retained-public-content-ttl-observation-default-168h-20260624.json`.
- 24h TTL dry-run artifact: `tmp/outputs/retained-public-content-ttl-observation-24h-20260624.json`.
- 0h graph dry-run artifact: `tmp/outputs/retained-public-content-ttl-observation-0h-20260624.json`.

## Retained Canary State

- Account: `retained-public-content-20260623123816-90w0q7@example.com`.
- Source: `c86b280c-0315-4d93-bcd7-37786996a22b`, type `public_feed`, URL `https://hnrss.org/frontpage`.
- Task: `b8a4cb3f-abe9-48f6-bb66-7ff4962bcdc6`, `status=enabled`, `schedule_policy=manual_refresh_only`, `schedule_cron=null`, `freshness_target_hours=72`.
- Dataset: `ee4a4a7a-1ea8-4864-b10d-031b365e5efb`.
- DatasetVersion: `6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8`, `schema_version=public_content_update.v1`, `row_count=5`, `average_completeness_percent=90`.
- TaskRuns: two retained successful runs: `1f684c04-0aab-48b7-ae4b-824526efaadc` and `fb2dc909-f125-402e-8759-7443e0214e55`.
- Retained drift events: one `public_content_drift` event after refresh.
- Export artifact files: one retained CSV under `/app/exports/datasets/.../retained-public-content-lifecycle-20260623123816-v1-3f43b866.csv`.
- Scheduler preflight: latest scheduler tick completed with `due=0`, `started=0`, `task_errors=0`, `report_subscriptions_due=0`, and `report_subscriptions_started=0`.

## TTL Dry-Run Results

| TTL window | Cutoff | Result | Boundary |
|---|---|---|---|
| 168h default | `2026-06-17T14:12:01.545953+00:00` | All cleanup candidate counts were `0`; `cleanup_ready=true`; `provider_call=false`; `email_sent=false`; `scheduler_tick_started=false` | Default production TTL does not match the retained canary yet |
| 24h | `2026-06-23T14:12:12.634659+00:00` | Matched retained canary graph: `users=1`, `workspaces=1`, `workspace_members=2`, `sources=1`, `collection_tasks=1`, `task_runs=2`, `raw_records=1`, `entities=1`, `entity_snapshots=1`, `datasets=1`, `dataset_versions=1`, `dataset_drift_events=1`, `dataset_export_jobs=1`, `reports=1`, `report_audit_events=1`, `notifications=1`, `export_artifact_files=1`, `export_artifact_path_violations=0` | The canary has crossed a 24h observation threshold; this is still dry-run only |
| 0h | `2026-06-24T14:12:21.085240+00:00` | Same graph as 24h; `cleanup_ready=true`; `export_artifact_path_violations=0` | Confirms current cleanup graph coverage, not a cleanup recommendation |

## Supported Claims

1. The retained canary remains present and readable after the scheduler/drift refresh gate.
2. Default 168h TTL dry-run does not yet select the canary.
3. A 24h TTL dry-run now selects the complete retained public-content graph, including both TaskRuns, one retained drift event, and one export artifact file.
4. Artifact path validation returns `export_artifact_path_violations=0`.
5. No cleanup execute occurred in this pass.

## Unsupported Claims

- Cleanup has run.
- The retained canary was deleted.
- Default 168h TTL has been observed.
- Multi-day retention has completed.
- Provider calls, email sends, production browser runs, browser artifacts, Report asset creation, Dataset export creation, or scheduler mutation happened in this pass.

## Next Observation

Keep the canary retained for the default TTL window. The next useful read-only checkpoint is a fresh 168h default dry-run after the canary crosses the seven-day cutoff; cleanup execute remains a separate decision gate.

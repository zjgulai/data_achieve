---
title: GitHub API-first Production Gate Runbook
doc_type: workflow
module: automation
topic: github-api-first-production-gate
status: stable
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# GitHub API-first Production Gate Runbook

## 0. Boundary

This runbook is the gate before any production GitHub API-first collection. M3-5 local validation may prove UI/API behavior, but it does not authorize production GitHub collection, Dataset export, report delivery, provider call, scheduler mutation, or browser execution.

Production execution requires an explicit one-step authorization envelope with the exact topic or repository scope and a retention or cleanup decision.

## 1. Facts, Inferences, Unknowns

### Facts

1. The local GitHub API-first path supports `github_topic`, `github_repo`, `github_tool_radar` DatasetVersion, report asset generation, and drift check.
2. The local Dataset schema is `github_tool_radar.v2` and records field sources, collector versions, endpoint origins, and lineage fields.
3. Report generation surfaces maintenance risk, install/source entries, recommended use cases, and unsuitable boundaries.
4. Drift checks expose grouped signals for field missingness, repository coverage, popularity, issue activity, release freshness, and commit freshness.

### Inferences

1. GitHub is the lowest-risk next production platform package because it is API-first and does not require browser login state.
2. Production collection should start from a small public topic or exact repo list before any recurring schedule or export job.

### Unknowns

1. Production GitHub token and rate-limit status may differ from local tests.
2. The exact topic/repo, max rows, Dataset/report/export retention policy, and cleanup policy remain unapproved until the gate is opened.

## 2. Authorization Envelope

Required fields before execution:

| Field | Required value |
|---|---|
| `scope_type` | `topic` or `repo_list` |
| `scope_value` | Exact GitHub topic, or exact owner/repo list |
| `max_repositories` | Numeric cap, recommended `3` to `10` for the first run |
| `allow_source_task_write` | Whether production Source and CollectionTask may be created |
| `allow_task_run` | Whether one production GitHub API collection run may start |
| `allow_dataset_save` | Whether a `github_tool_radar` DatasetVersion may be saved |
| `allow_report_asset` | Whether a report asset may be created |
| `allow_export_file` | Whether CSV/JSON/JSONL export file may be written |
| `retention_policy` | `cleanup_after_evidence` or `retain_named_dataset` |
| `cleanup_deadline` | Timestamp or `not_applicable` |

Default deny:

- Provider call.
- Product/report/subscription email send.
- Scheduler mutation or manual scheduler tick.
- Dataset export file write.
- Production browser run.
- Screenshot, trace, HAR, or browser artifact file write.
- Login-state, cookie, private account, or anti-detect automation.

## 3. Gate Sequence

1. L3 read-only baseline: health, deploy SHA, schema, GitHub provider config/rate-limit status if available.
2. Local gate: targeted API tests and GitHub mock Playwright E2E pass on current worktree.
3. Production preflight: confirm exact scope and side-effect flags from the authorization envelope.
4. Execute only approved steps, in this order: Source/Task create or reuse, one task run, Dataset save, optional report asset, optional export file.
5. Evidence capture: response IDs, counts, schema version, report ID, export job ID if any, and no-provider/no-email/no-scheduler evidence.
6. Cleanup or retention: execute cleanup if `cleanup_after_evidence`; otherwise record retained dataset/report IDs and owner.
7. Post-check: health and page smoke remain healthy; cleanup dry-run returns zero for scoped fixtures when cleanup was required.

## 4. Acceptance Evidence

Minimum local evidence before production:

```bash
pnpm --dir apps/web exec playwright test --grep "automation platform packages"
pnpm lint:web
git diff --check
```

Minimum production evidence after authorization:

| Evidence | Required |
|---|---|
| Health | `schema_revision=schema_head`, `status=ok` |
| Scope | Exact topic or repo list recorded |
| Run | One run ID and row count, if task run was authorized |
| Dataset | Dataset ID, Version ID, `schema_version=github_tool_radar.v2`, if save was authorized |
| Report | Report ID and report type `github_tool_radar`, if report asset was authorized |
| Export | Export job ID, format, checksum or row count, if export was authorized |
| Cleanup | Dry-run, execute, recount evidence when cleanup is required |

## 5. Retention And Cleanup

`cleanup_after_evidence`:

- Delete scoped Source, CollectionTask, TaskRun, RawRecord, EntitySnapshot, Dataset, DatasetVersion, Report, ExportJob, and file artifacts created by this gate.
- Recount all scoped IDs after cleanup.
- Keep only Markdown evidence under `drafts/analysis/` and transient JSON under `tmp/outputs/`.

`retain_named_dataset`:

- Retain only named Dataset/Version/Report IDs listed in the authorization envelope.
- Record owner, purpose, and review deadline.
- Do not retain test accounts, one-off Sources/Tasks, or export files unless explicitly listed.

## 6. Stop Conditions

Stop immediately if any of these occur:

- GitHub API rate limit, auth, or permission error.
- Dataset schema is not `github_tool_radar.v2`.
- Unexpected email, provider, scheduler, browser, or export side effect occurs.
- Cleanup dry-run finds unscoped resources.
- Production health or core page smoke regresses after execution.

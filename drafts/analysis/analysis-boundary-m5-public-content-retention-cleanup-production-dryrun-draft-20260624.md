---
title: M5 Public Content Retention Cleanup Production Dry-Run Evidence
doc_type: analysis
module: automation
topic: boundary-m5-public-content-retention-cleanup-production-dryrun
status: draft
created: 2026-06-24
updated: 2026-06-24
owner: self
source: human+ai
---

# M5 Public Content Retention Cleanup Production Dry-Run Evidence

## 1. Scope Boundary

This gate deployed retained public-content cleanup tooling and ran production dry-run only.

Allowed:

- Deploy cleanup tooling.
- Run `scripts/cleanup-retained-public-content.sh --older-than-hours 0` in Docker dry-run mode.
- Run the default 168-hour TTL dry-run.
- Record candidate counts and export artifact path safety.

Denied:

- No `--execute`.
- No retained canary deletion.
- No provider call.
- No email send.
- No scheduler tick.
- No production browser run.
- No browser artifact write.

## 2. Initial Dry-Run Gap

The first deployment at `c321a5212bf6f1f51f63bf35dd1a522b4ebd6d90` passed preflight, Docker build, Alembic upgrade, gateway reload retry, health, container checks, and page smoke.

The first production dry-run with `--older-than-hours 0` returned `dry_run=true`, `cleanup_ready=true`, and `export_artifact_path_violations=0`, but it under-counted the retained canary graph:

```text
users=1
workspaces=1
workspace_members=2
dataset_versions=1
dataset_export_jobs=1
report_audit_events=1
notifications=1
export_artifact_files=1
sources=0
collection_tasks=0
task_runs=0
datasets=0
reports=0
```

No cleanup execute was run. Read-only diagnosis showed the retained assets were attached to a workspace where the retained user was a member, while `DatasetVersion.created_by_user_id` and `ReportAuditEvent.actor_id` still pointed to the retained user.

## 3. Fix And Validation

Fix commit:

```text
d11d5a477ea3125649f7674495bfca5b93148e32
```

Fix:

- Follow DatasetVersion source TaskRun lineage to Source, Task, TaskRun, RawRecord, EntitySnapshot, and Entity candidates.
- Follow ReportAuditEvent actor lineage to public-content Report candidates.
- Keep shared workspace/project rows out of the broad delete set unless the retained user owns them.
- Preserve export artifact root validation before execute mode.

Local validation:

```bash
cd apps/api && uv run pytest tests/unit/test_public_content_retention.py -q
```

Result: `3 passed`.

```bash
cd apps/api && uv run pytest tests/unit/test_public_content_retention.py tests/unit/test_e2e_cleanup.py -q
```

Result: `5 passed`.

```bash
cd apps/api && uv run pytest -q
```

Result: `111 passed, 1 warning`.

```bash
cd apps/api && uv run ruff check src tests
```

Result: `All checks passed`.

## 4. Final Production Dry-Run

Final deployed production identity:

```text
remote HEAD: d11d5a477ea3125649f7674495bfca5b93148e32
.deploy-sha: d11d5a477ea3125649f7674495bfca5b93148e32
schema_revision: 202606110023
schema_head: 202606110023
api/db/edge/web: healthy
```

Dry-run with `--older-than-hours 0`:

```text
dry_run=true
retention_hours=0
cleanup_ready=true
export_artifact_path_violations=0
users=1
workspaces=1
workspace_members=2
sources=1
collection_tasks=1
task_runs=1
raw_records=0
entities=0
entity_snapshots=0
datasets=1
dataset_versions=1
dataset_drift_events=0
dataset_export_jobs=1
reports=1
report_audit_events=1
notifications=1
export_artifact_files=1
```

Default 168-hour TTL dry-run:

```text
dry_run=true
retention_hours=168
all cleanup candidate counts=0
export_artifact_path_violations=0
```

## 5. Supported Claims

- Production has retained public-content cleanup tooling deployed at `d11d5a4`.
- The `--older-than-hours 0` dry-run now sees the retained canary cleanup plan, including Source/Task/TaskRun/Dataset/Version/Report/Export assets and one export artifact.
- The default 168-hour TTL dry-run does not match the retained canary yet.
- Export artifact path validation passed with no path violations.

## 6. Unsupported Claims

- Cleanup execute has run.
- The retained canary was deleted.
- Multi-day TTL has been observed.
- Scheduler recurring monitoring is active.
- Provider enrichment, email, production browser run, or browser artifact write occurred.

---
title: PRD2 R0 Release Boundary Execution Log
doc_type: workflow
module: automation
topic: prd2-r0-release-boundary
status: stable
created: 2026-06-21
updated: 2026-06-22
owner: self
source: human+ai
---

# PRD2 R0 Release Boundary Execution Log

## 0. Scope

本文件记录 2026-06-21 R0 release boundary 的实际执行结果，以及 2026-06-22 docs-only post-deploy closeout sync、P1/P2/P3 边界遗留执行结果。R0 目标是把本地 PRD2/M1/M2 工作树、生产部署、生产只读 smoke、authenticated API smoke 和生产写入 E2E 分层，不把本地通过、DB dry-run、public page smoke 或 authenticated API smoke 说成生产写入验收。

2026-06-22 本次文档同步没有执行生产部署、生产数据库 migration、生产写入、登录态操作、provider call、邮件发送、站内通知发送或调度变更；它只记录上一轮 release closeout 已产生的部署和 smoke 证据。

## 1. Task Orchestration

| Track | Task | Status | Evidence |
|---|---|---|---|
| R0-1 | Release scope inventory | done | `git status --short`、`git diff --stat`；当前在 `main`，无 staged diff |
| R0-2 | Local validation gate | done | `pnpm lint:web`、`pnpm test:web`、`bash scripts/verify-mvp.sh` |
| R0-3 | Local DB/migration gate | done | `POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db` |
| R0-4 | Production read-only smoke | done | `/api/health`、`/automation`、`/datasets`、unauthenticated `/api/automation/platform-packages` |
| R0-5 | Release branch setup and scoped staging | done | 已从 `main` 切到 `codex/prd2-r0-release-boundary`；RC1/RC2 已 staged，RC3 草稿未 staged；尚未 commit |
| R0-6 | Authorized production E2E | done_scoped_p3 | `drafts/analysis/analysis-boundary-p3-production-write-e2e-draft-20260622.md`；targeted real API E2E `16 passed`，cleanup recount zero |
| R0-7 | Production deploy closeout | done_previous_closeout | 上一轮 closeout 记录生产已部署到 `e97810adb86f39f16efe96b9f2b7f0760f5acf7e`，预快照 `lhsnap-erfd1c6c / pre-data-scrapy-deploy-20260622` |
| R0-8 | Post-deploy smoke closeout | done_previous_closeout | 上一轮 closeout 记录 health `schema_revision/schema_head=202606110023`、public page smoke 200、authenticated API smoke passed |
| R0-9 | Boundary leftovers plan | done_docs_only | `drafts/analysis/analysis-boundary-leftovers-execution-plan-draft-20260622.md` |

## 2. Release Scope Inventory

### Current branch

Initial inventory was run on `main`. Release preparation then moved the dirty worktree to:

```text
codex/prd2-r0-release-boundary
```

### Dirty worktree groups

| Group | Files | Release concern |
|---|---|---|
| Automation backend | `apps/api/src/data_intelligence_hub/api/routes/automation.py`、`services/automation_service.py`、`schemas/automation.py`、`repositories/automation_plans.py` | PlatformPackage、CapabilityProbe、BrowserDiagnostic、Dataset/Export/Drift/Report API |
| Browser diagnostic persistence | `apps/api/src/data_intelligence_hub/models/automation_plan.py`、`models/__init__.py`、`apps/api/alembic/versions/202606110021_*`、`202606110022_*`、`202606110023_*` | Local DB schema advances from `202606110020` to `202606110023` |
| API tests | `apps/api/tests/integration/test_sources_tasks.py` | Integration coverage for platform packages, capability probes, browser diagnostic jobs/runs, dataset/drift/report flows |
| Web automation workbench | `apps/web/src/components/automation/automation-workbench.tsx`、`apps/web/src/lib/api/automation.ts`、`apps/web/src/lib/api/mock.ts`、`apps/web/src/types/automation.ts` | PRD2 UI and API client surface |
| Web E2E | `apps/web/tests/e2e/main-flows.spec.ts` | Workbench, dataset, drift, browser diagnostic read-only acceptance |
| Docs | `README.md`、`docs/api/api-contract-data-intelligence-hub-stable.md`、`docs/product/product-prd-data-intelligence-hub-stable.md`、`docs/workflows/*`、`drafts/analysis/*` | PRD2 contracts, gap audit, execution plan, browser evidence retention |

Initial R0 validation did not stage or commit files. The later release-candidate pass staged only RC1/RC2:

```text
staged files: 22
staged diff: 8696 insertions, 172 deletions
unstaged drafts: 3
commit: not created
```

Unstaged drafts:

```text
drafts/analysis/analysis-prd-next-roadmap-draft-20260619.md
drafts/analysis/analysis-agent-reach-browser-harness-platform-roadmap-draft-20260621.md
drafts/analysis/analysis-prd2-r0-release-candidate-staging-plan-draft-20260621.md
```

## 3. Fixes Applied During Gate Execution

The first `bash scripts/verify-mvp.sh` run stopped at API mypy. Two narrow fixes were applied:

1. `apps/api/src/data_intelligence_hub/services/automation_service.py`
   - Added an explicit `Literal["passed", "review", "blocked"]` annotation for the browser diagnostic lineage check status before passing it to `_spec_check`.
2. `apps/api/tests/integration/test_sources_tasks.py`
   - Changed monkeypatch targets for `shutil.which` and `subprocess.run` to string module paths.
   - Removed the now-unused `automation_service` import.

Backups were written before editing:

```text
/Users/pray/.Codex/file-history/20260621_r0_mypy_automation_service.py
/Users/pray/.Codex/file-history/20260621_r0_mypy_test_sources_tasks.py
```

## 4. Local Validation Evidence

### Web-only checks

```text
pnpm lint:web
result: passed

pnpm test:web
result: passed
web unit tests: 2 files passed, 8 tests passed
```

### Full local MVP gate

```text
bash scripts/verify-mvp.sh
result: passed
API ruff: passed
API mypy: passed, 141 source files
API pytest: 102 passed, 1 warning
API Alembic heads: 202606110023 (head)
Web lint: passed
Web unit tests: 2 files passed, 8 tests passed
Web build: passed
Web Playwright E2E: 36 passed, 8 skipped
```

Important boundary: skipped E2E includes real dataset write-through cases that require real API mode. This does not prove production write E2E.

## 5. Local DB/Migration Evidence

The first DB gate attempt found local Docker unavailable. Docker Desktop was started, then `docker info` confirmed daemon readiness.

The second attempt found port `5432` already allocated by another local container:

```text
container: ai_video_pg
port: 0.0.0.0:5432->5432/tcp
```

This project was rerun on a non-conflicting local port:

```text
POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db
```

Result:

```text
result: passed
PostgreSQL local port: 15432
API PostgreSQL migration: upgraded from baseline through 202606110023
API pytest: 102 passed, 1 warning
Web Playwright E2E: 36 passed, 8 skipped
```

Migration chain observed:

```text
202606110020 -> 202606110021 browser diagnostic run assets
202606110021 -> 202606110022 browser diagnostic job assets
202606110022 -> 202606110023 browser diagnostic local run assets
```

### Post-staging validation refresh

After staging RC1/RC2, patch hygiene and secret scan were rerun:

```text
git diff --cached --check
result: passed

git grep --cached high-confidence secret patterns
result: no matches
```

The DB-backed gate was rerun after staging with the same local database URL. API ruff, API mypy, API pytest, Alembic head check, local PostgreSQL migration, Web lint, Web unit tests, and Web build completed before the process was killed by the OS during the Playwright phase with exit code `137`.

To isolate resource pressure from test assertions, Playwright was rerun with one worker:

```text
pnpm --dir apps/web exec playwright test --workers=1
result: passed
Web Playwright E2E: 36 passed, 8 skipped
```

The final acceptance rerun then completed the standard DB-backed gate:

```text
POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db
result: passed
API ruff: passed
API mypy: passed, 141 source files
API pytest: 102 passed, 1 warning
API Alembic heads: 202606110023 (head)
API PostgreSQL migration: passed
Web lint: passed
Web unit tests: 2 files passed, 8 tests passed
Web build: passed
Web Playwright E2E: 36 passed, 8 skipped
```

Boundary: this post-staging refresh is local validation and does not prove production deployment. The local DB container used for this refresh was stopped after validation.

## 6. Historical Production Read-only Smoke Before Deployment

This 2026-06-21 section is historical pre-deploy evidence. It is retained to show why R0 deployment was needed; Section 7 records the later post-deploy closeout evidence.

Production smoke was read-only and unauthenticated. No production mutation occurred during this historical smoke.

```text
GET https://scrapy.lute-tlz-dddd.top/api/health
environment=production
status=ok
database=connected
schema=current
schema_revision=202606110020
schema_head=202606110020
scheduler_enabled=true
```

```text
/automation status=200 content_type=text/html; charset=utf-8
/datasets status=200 content_type=text/html; charset=utf-8
/api/automation/platform-packages status=401 content_type=application/json
```

Historical supported claim at that time: production was healthy at schema `202606110020` and pages were reachable.

Historical unsupported claim at that time: BrowserDiagnosticRun/Job/JobRun schema `202606110021/022/023` was deployed to production. This was later superseded by the Section 7 post-deploy closeout record.

## 7. 2026-06-22 Post-Deploy Closeout Sync

This section supersedes the pre-deploy status lines in Section 6 for current planning, but it is still not a fresh live probe from this docs-only pass.

### Recorded deployment evidence from prior closeout

```text
production_sha=e97810adb86f39f16efe96b9f2b7f0760f5acf7e
pre_snapshot=lhsnap-erfd1c6c / pre-data-scrapy-deploy-20260622
schema_revision=202606110023
schema_head=202606110023
schema=current
scheduler_enabled=true
```

Public page smoke recorded in the prior closeout:

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

Authenticated API smoke recorded in the prior closeout:

```text
health passed
login passed
session passed
dashboard passed
tasks passed
reports passed
alert-events passed
notifications passed
```

### Evidence grade result

| Claim | Grade | Status |
|---|---|---|
| PRD2 R0 release deployment was recorded to SHA `e97810a...` with schema `202606110023` | L3/L4 closeout evidence from prior operation | supported for release closeout |
| Current live state at the moment of this docs-only pass | L0 in this pass | must be rechecked in P1 |
| Public pages and authenticated API smoke passed in the prior closeout | L3 production smoke | supported |
| Production write E2E passed | unsupported | still pending authorization |
| Demo seed/cleanup execute ran after deploy | unsupported | still pending dry-run and possible execute authorization |
| Provider call, email send, scheduler mutation, or production browser-harness run happened | unsupported | not executed |

## 8. Remaining Authorization Points

Before any new production side effect:

1. Recheck live SHA, health, schema, and compose state in read-only mode.
2. Run demo cleanup and E2E fixture cleanup in dry-run mode first.
3. Confirm no provider call, no external send, no scheduler mutation unless separately authorized.

Production write E2E status:

1. P3 completed a scoped production write E2E with one-time `e2e-*@example.com` accounts/workspaces.
2. P3 intentionally excluded full real suite cases that would send reports/emails, execute subscriptions, mutate schedule approval, write dataset export files, run GitHub Topic Radar, or start browser-harness.
3. Any broader full-suite production E2E remains a separate authorization envelope because it would include those side effects.

## 9. Next Execution Step

This section was written before P1/P2/P3 execution and is retained as the historical sequencing decision. The P1/P2/P3 results below supersede it for current status.

The current next executable step after Section 16 is platform collection deepening or another explicitly scoped P5 live gate. P5 B1 one-test-email has completed, and P4 local-only browser-harness adapter spike remains a local dedicated-CDP validation, not production browser execution.

## 10. 2026-06-22 P1 Production Inventory

Evidence record: `drafts/analysis/analysis-boundary-p1-production-inventory-draft-20260622.md`.

This pass was read-only / dry-run only. It did not execute cleanup, demo seed, production write E2E, provider call, email send, scheduler mutation, or real browser-harness run.

### Result summary

| Check | Result | Evidence grade |
|---|---|---|
| Live SHA | `remote_head=e97810adb86f39f16efe96b9f2b7f0760f5acf7e`; `.deploy-sha` same | L3 production read-only |
| Health/schema | `status=ok`, `database=connected`, `schema=current`, `schema_revision=schema_head=202606110023` | L3 production read-only |
| Compose | `api`, `db`, `edge`, `web` healthy | L3 production read-only |
| Public pages | `/api/health`, `/dashboard`, `/automation`, `/datasets`, `/tasks`, `/sources`, `/alerts`, `/notifications`, `/projects`, `/signals`, `/raw-records`, `/entities`, `/toolkit` all `200` | L3 production read-only |
| Demo cleanup dry-run | non-zero candidates, including `task_runs=84`, `raw_records=34`, `entity_snapshots=42`, `notifications=42` | L2 dry-run |
| E2E fixture cleanup dry-run | all counts zero with `--older-than-hours 0` | L2 dry-run |
| Email channel config | `status=ready`, `configured=true`, `tls_mode=starttls`; no send attempted | L3 config-only |

### Updated next step

P2 should decide whether to authorize `production demo cleanup --execute` against the P1 dry-run candidate counts. E2E fixture cleanup execute is not needed because its dry-run count is zero.

## 11. 2026-06-22 P2 Demo Cleanup Execute

Evidence record: `drafts/analysis/analysis-boundary-p2-demo-cleanup-execution-draft-20260622.md`.

User authorization: "同意执行 P2".

This pass executed only production demo cleanup. It did not execute demo seed, E2E fixture cleanup execute, production write E2E, provider call, email send, scheduler mutation, or real browser-harness run.

### Result summary

| Check | Result | Evidence grade |
|---|---|---|
| Demo cleanup execute | Completed with `dry_run=false`; cleaned P1 candidate set including `task_runs=84`, `raw_records=34`, `entity_snapshots=42`, `notifications=42`, `reports=14`, `sources=12`, `collection_tasks=12` | L4 authorized live cleanup |
| Post-cleanup demo dry-run recount | all cleanup candidate counts zero | L2 dry-run |
| Health/schema | `status=ok`, `database=connected`, `schema=current`, `schema_revision=schema_head=202606110023` | L3 production read-only |
| Public pages | `/api/health`, `/dashboard`, `/automation`, `/datasets`, `/tasks`, `/sources`, `/alerts`, `/notifications`, `/projects`, `/signals`, `/raw-records`, `/entities`, `/toolkit` all `200` | L3 production read-only |
| Compose | `api`, `db`, `edge`, `web` healthy | L3 production read-only |

### Updated next step

P3 should start with an authorization envelope for L4 production write E2E. It must use a one-time account/workspace and must include created IDs, cleanup dry-run, cleanup execute, and recount.

## 12. 2026-06-22 P3 Scoped Production Write E2E

Evidence record: `drafts/analysis/analysis-boundary-p3-production-write-e2e-draft-20260622.md`.

User authorization: "同意执行 P3".

This pass executed a scoped production write E2E and immediate fixture cleanup. It did not execute the full real Playwright suite, report send, external email send, provider call, scheduler mutation, dataset export, demo seed, or real browser-harness run.

### Result summary

| Check | Result | Evidence grade |
|---|---|---|
| Pre-run health/schema | `status=ok`, `database=connected`, `schema=current`, `schema_revision=schema_head=202606110023` | L3 production read-only |
| Pre-run live SHA | `remote_head=e97810adb86f39f16efe96b9f2b7f0760f5acf7e`; `.deploy-sha` same | L3 production read-only |
| Pre-run public pages | `/api/health`, `/dashboard`, `/automation`, `/datasets`, `/tasks`, `/sources`, `/alerts`, `/notifications`, `/projects`, `/signals`, `/raw-records`, `/entities`, `/toolkit` all `200` | L3 production read-only |
| E2E selection | Targeted grep set excluded report send, subscription execution, GitHub Topic Radar, dataset export, schedule approval, and browser-harness probe controls | Boundary control |
| Production write E2E | `16 passed (49.9s)` across desktop and mobile | L4 authorized live |
| Cleanup dry-run | Found scoped E2E candidates: `users=4`, `workspaces=4`, `sources=8`, `collection_tasks=8`, `task_runs=8`, `raw_records=8`, `alert_events=7`, `notifications=4`; `reports=0`, `datasets=0`, `dataset_export_jobs=0` | L2 dry-run |
| Cleanup execute | Removed the same scoped candidate set with `dry_run=false` | L4 authorized live cleanup |
| Cleanup recount | all E2E fixture counts zero | L2 dry-run |
| Post-run health/pages/compose | health current, all checked routes `200`, `api/db/edge/web` healthy | L3 production read-only |

### Updated next step

P4 completed as a local-only ephemeral browser-harness adapter spike. It keeps production unchanged, requires a dedicated CDP endpoint, and blocks default user Chrome profile reuse. It did not create Source, Task, TaskRun, Dataset, AlertEvent, Notification, email, export file, scheduler mutation, provider call, or production browser run.

## 13. P4 Local Browser-Harness Spike

P4 evidence: `drafts/analysis/analysis-boundary-p4-browser-harness-ephemeral-probe-draft-20260622.md`.

Key result:

- `ephemeral_browser_harness_probe` now requires `browser_harness_cdp_url`.
- Missing dedicated CDP returns `blocked_ephemeral_probe` / `browser_harness_isolated_cdp_required`.
- A local headless Chrome with a temporary profile exposed CDP at `127.0.0.1:9333`; browser-harness read `https://example.com/` page info and closed the target tab.
- Validation passed: API full pytest `102 passed`, API ruff passed, web lint/unit/build passed, Playwright mock E2E `4 passed`, and `git diff --check` passed.

This remains local validation only. It is not a production browser run and does not approve screenshot/trace/HAR file writes.

## 14. P5 Provider Email Scheduler Gate Plan

P5 plan: `drafts/analysis/analysis-boundary-p5-provider-email-scheduler-gate-plan-draft-20260622.md`.

This pass created the gate plan only. It did not execute provider calls, email test sends, report sends, report subscription runs, scheduler mutations, scheduler ticks, dataset exports, production browser runs, or browser artifact file writes.

### Gate summary

| Gate | Plan result | Evidence grade |
|---|---|---|
| Provider | Split into A0 read-only config/adapter inventory, A1 fixture-only validation, A2 authorized live provider call | L1 planning evidence |
| Email | Split into B0 read-only channel status, B1 max-one test email, B2 product email send; report send and subscription run are treated as separate send-capable paths | L1 planning evidence |
| Scheduler | Split into C0 read-only overview, C1 schedule approval mutation, C2 actual scheduler tick / task / report subscription execution | L1 planning evidence |
| Dataset export | Kept as a separate D gate because export writes artifact files and `DatasetExportJob` records | L1 planning evidence |

### Updated next step

Run P5 read-only inventory only:

1. Provider A0 config/adapter inventory without outputting secrets and without calling a provider.
2. Email B0 channel status refresh without sending test email.
3. Scheduler C0 overview refresh without triggering a tick or mutating schedules.
4. Dataset export D0 endpoint/candidate inventory without creating export jobs.

## 15. P5 Read-only Inventory

P5 inventory evidence: `drafts/analysis/analysis-boundary-p5-read-only-inventory-draft-20260623.md`.

This pass executed only production read-only checks. It did not execute provider calls, email test sends, product email sends, report sends, report subscription runs, scheduler mutations, manual scheduler ticks, dataset export creation, production browser runs, or browser artifact file writes.

### Result summary

| Check | Result | Evidence grade |
|---|---|---|
| Health/schema | `environment=production`, `status=ok`, `database=connected`, `schema=current`, `schema_revision=schema_head=202606110023` | L3 production read-only |
| Live SHA | `remote_head=e97810adb86f39f16efe96b9f2b7f0760f5acf7e`; `.deploy-sha` same | L3 production read-only |
| Compose | `api`, `db`, `edge`, `web` running and healthy | L3 production read-only |
| Provider A0 | `llm_provider=mock`, no model/key configured, default adapter `MockLLMAdapter`; no provider call | L3 production read-only/config-only |
| Email B0 | channel `ready`, configured, `tls_mode=starttls`, no missing settings; no test email sent | L3 production read-only/config-only |
| Scheduler C0 | enabled, poll interval `60.0s`, 75 enabled tasks, 0 cron tasks, 0 enabled report subscriptions; latest tick completed with `due=0`, `started=0` | L3 production read-only |
| Dataset export D0 | export dir `/app/exports/datasets` exists; datasets=29, versions=5, export jobs=4, successful export jobs=4; no export created | L3 production read-only |

### Updated next step

Select one L4 live gate. The smallest controllable candidate is B1 one-test-email because channel readiness is true and scope can be constrained to one recipient and one send. Provider A2 remains blocked until a real provider/model/key/budget are configured; Scheduler C1 requires exact dataset/version/task IDs plus rollback; Dataset export D live requires exact dataset/version IDs plus retention or cleanup policy.

## 16. P5 B1 One-test-email

P5 B1 evidence: `drafts/analysis/analysis-boundary-p5-b1-email-test-send-draft-20260623.md`.

User authorization: recipient `zhoujianaaa123@gmail.com`.

This pass executed one authorized test email send. It did not execute provider calls, product drift alert email sends, report sends, report subscription runs, scheduler mutations, manual scheduler ticks, dataset exports, production browser runs, or browser artifact file writes.

### Result summary

| Check | Result | Evidence grade |
|---|---|---|
| Recipient | `zhoujianaaa123@gmail.com` | Authorization scope |
| Max sends | `1` | Authorization scope |
| Attempted sends | `1` | L4 authorized live email test |
| Channel status before send | `ready`, configured, `tls_mode=starttls`, no missing settings | L3 config status |
| Delivery result | `delivered=true`, `reason=null` | L4 authorized live email test |
| Started/finished | `2026-06-23T07:27:18.928471+00:00` to `2026-06-23T07:27:23.503534+00:00` | Execution evidence |

### Boundary

This evidence supports only one authorized test email delivery. It does not validate product drift alert email delivery, report send email delivery, report subscription email delivery, bulk email delivery, scheduler-triggered email, provider calls, scheduler mutation, dataset export, or production browser execution.

### Updated next step

Recommended next step is to stop P5 email at B1 and return to platform collection deepening. If another P5 live gate is still needed, B2 product email requires exact DriftEvent/AlertEvent IDs, recipient, max sends, and audit/cleanup policy; Provider A2 remains blocked until real provider/model/key/budget are configured; Scheduler C1 requires exact dataset/version/task IDs and rollback; Dataset export D live requires exact dataset/version IDs plus retention or cleanup policy.

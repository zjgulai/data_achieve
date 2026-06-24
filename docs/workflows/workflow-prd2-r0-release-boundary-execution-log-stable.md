---
title: PRD2 R0 Release Boundary Execution Log
doc_type: workflow
module: automation
topic: prd2-r0-release-boundary
status: stable
created: 2026-06-21
updated: 2026-06-24
owner: self
source: human+ai
---

# PRD2 R0 Release Boundary Execution Log

## 0. Scope

本文件记录 2026-06-21 R0 release boundary 的实际执行结果。R0 目标是把本地 PRD2/M1/M2 工作树和当前生产部署状态分层，不把本地通过、DB dry-run 或生产只读 smoke 说成生产写入验收。

初始 R0 release-boundary pass 没有执行生产部署、生产数据库 migration、生产写入、登录态操作、provider call、邮件发送、站内通知发送或调度变更。2026-06-21 后续 post-merge release 已在明确授权后执行生产部署和 Alembic migration。2026-06-23 已完成一次明确授权的小范围 M3 GitHub API-first production package gate，并在取证后清理 scoped fixtures；同日已完成 M5 Public Web/RSS/Docs production package smoke，允许一次公开 RSS TaskRun、DatasetVersion save、read-only drift/report preview，并在取证后清理 scoped fixtures；之后又完成 M5 Public Content Report asset gate，允许创建一个 `public_content` Report asset 并清理 scoped fixtures；随后完成 M5 Public Content Dataset export gate，允许创建一个 CSV DatasetExportJob、写出一个受控导出文件、下载校验并清理 scoped fixtures 与导出文件；之后完成 M5 Public Content retained lifecycle gate，保留一组 public content canary 资产并验证重登录后 Dataset/Report/Export 可读。2026-06-24 先本地完成 public-content drift event persistence slice，随后在明确授权后部署 production SHA `68c27e0f9c62d542149eedc5b18439938103b4bb` 并完成 scoped production drift-event gate：创建一个 `public_content_drift` DatasetDriftEvent、重复提交复用同一 ID，并在取证后清理 scoped fixtures 至零；retained canary 未被修改。同日随后本地完成 M5 Public Content docs diff slice，并部署 production SHA `af23cefc92aa9fec336f632a5b1561623811c2fd` 完成 scoped production docs/page gate：`generic_web` docs/page snapshot 进入 `public_content_update` Dataset/drift/report/event/report-asset 链路，并在取证后清理 scoped fixtures 至零。provider call、product/report/subscription email、scheduler mutation、生产浏览器运行和浏览器 artifact 写入仍未执行。

## 1. Task Orchestration

| Track | Task | Status | Evidence |
|---|---|---|---|
| R0-1 | Release scope inventory | done | `git status --short`、`git diff --stat`；当前在 `main`，无 staged diff |
| R0-2 | Local validation gate | done | `pnpm lint:web`、`pnpm test:web`、`bash scripts/verify-mvp.sh` |
| R0-3 | Local DB/migration gate | done | `POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db` |
| R0-4 | Production read-only smoke | done | `/api/health`、`/automation`、`/datasets`、unauthenticated `/api/automation/platform-packages` |
| R0-5 | Release branch setup and scoped staging | done | 已从 `main` 切到 `codex/prd2-r0-release-boundary`；RC1/RC2 已 staged，RC3 草稿未 staged；尚未 commit |
| R0-6 | Post-merge production release | done | production HEAD `80f0566`；migration `202606110020 -> 202606110023`；L3 read-only smoke passed |
| R0-7 | Authorized production write E2E | done_scoped_m3 | M3 GitHub scope `topic=web-scraping`、`max_repositories=3`；真实 API E2E `2 passed`；cleanup recount 全 0 |
| R0-8 | M3 post-R0 production release | done | production HEAD `f04c8ea77cc64f28d391e992012525e1704ec1a3`；schema 仍为 `202606110023`；GitHub API-first package gate passed |
| R0-9 | M5 Public Content production package smoke | done_scoped_m5 | production HEAD `e1359759aa1cab157bb98ec8abda4ff580cbfe7d`；`public_feed` RSS TaskRun success；`public_content_update` DatasetVersion row_count=5；drift/report read-only preview passed；exact-ID 和 generic cleanup dry-run 全 0 |
| R0-10 | M5 Public Content Report asset gate | done_scoped_m5 | production HEAD `fb05c61ab137b1c1cb7519b661d98a97ae0cead6`；Report asset `report_type=public_content` created；`notification_created=false`；exact-ID 和 generic cleanup dry-run 全 0 |
| R0-11 | M5 Public Content Dataset export gate | done_scoped_m5 | production HEAD `fb05c61ab137b1c1cb7519b661d98a97ae0cead6`；CSV DatasetExportJob `success`；artifact_size_bytes=4900；download 校验通过；exact-ID 和 generic cleanup dry-run 全 0 |
| R0-12 | M5 Public Content retained lifecycle gate | done_retained_m5 | production HEAD `fb05c61ab137b1c1cb7519b661d98a97ae0cead6`；retained account/source/task/run/dataset/version/report/export/artifact 均保留；重登录 list/detail/download 校验通过；generic E2E cleanup dry-run 仍为 0 |
| R0-13 | M5 Public Content drift event persistence local slice | done_local_m5 | 本地新增 `public-content-drift-events` save/list、`event_type=public_content_drift`、saved/reused audit events；API full pytest `106 passed`、ruff、Web TypeScript/lint/unit/build、`git diff --check` 均通过 |
| R0-14 | M5 Public Content drift-event production gate | done_scoped_m5 | production HEAD `.deploy-sha=68c27e0f9c62d542149eedc5b18439938103b4bb`；生产创建 `public_content_drift` DatasetDriftEvent `6acbd871-e0f8-4580-a7c7-b3d2459962f1`；重复提交复用同一 ID；exact-ID cleanup 和 generic cleanup dry-run 全 0 |
| R0-15 | M5 Public Content docs diff local slice | done_local_m5 | `generic_web.v1` docs/page snapshot 可保存 `public_content_update` DatasetVersion、hash-only drift、`public_content_drift` event、public content report/asset；API full pytest `107 passed`、ruff、Web TypeScript/lint/unit/build、`git diff --check` 均通过；生产 gate 见 R0-16 |
| R0-16 | M5 Public Content docs/page production gate | done_scoped_m5 | production HEAD `.deploy-sha=af23cefc92aa9fec336f632a5b1561623811c2fd`；生产 `generic_web` docs/page TaskRun success；`public_content_update` DatasetVersion `row_count=1` 且 `collector_schema_versions=["generic_web.v1"]`；`public_content_drift` DatasetDriftEvent `05847c1a-5013-4fc8-8d1f-5bec747d0408` 创建/复用；Report asset `9b2ec052-0ba8-482f-9902-209da8c51885` 创建；exact-ID cleanup 和 generic cleanup dry-run 全 0 |
| R0-17 | Remaining live side-effect gates | pending_separate_authorization | provider call、product/report/subscription email、scheduler mutation、production browser run、multi-day TTL/cleanup policy 均未执行 |

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

## 6. Production Read-only Smoke

Production smoke was read-only and unauthenticated. No production mutation occurred.

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

Supported claim: current production is healthy at schema `202606110020` and pages are reachable.

Unsupported claim: BrowserDiagnosticRun/Job/JobRun schema `202606110021/022/023` is deployed to production.

## 7. Post-merge Production Release Evidence

Production release was executed after PR #1 was merged into `main`.

```text
release commit: 80f0566288ab1cab3348730c65df811bcfd42d9a
previous production HEAD: d9b2a5e35274963c1804d200824d5767d2f4ae3d
release method: git bundle upload + git merge --ff-only FETCH_HEAD
preflight: passed
image build: passed
gateway reload: passed
gateway dry-run: passed
```

Production Alembic migration:

```text
202606110020 -> 202606110021 browser diagnostic run assets
202606110021 -> 202606110022 browser diagnostic job assets
202606110022 -> 202606110023 browser diagnostic local run assets
```

Production health after release:

```text
environment=production
status=ok
database=connected
schema=current
schema_revision=202606110023
schema_head=202606110023
scheduler_enabled=true
```

Container state:

```text
data_achieve_scrapy_api healthy
data_achieve_scrapy_db healthy
data_achieve_scrapy_edge healthy
data_achieve_scrapy_web healthy
```

Public page smoke:

```text
/dashboard 200
/intelligence 200
/reports 200
/tasks 200
/sources 200
/alerts 200
/notifications 200
/projects 200
/signals 200
/raw-records 200
/entities 200
/automation 200
/datasets 200
```

Authenticated read-only API smoke passed for existing demo credentials:

```text
/api/auth/me passed
/api/dashboard/overview passed
/api/tasks non-empty
/api/reports non-empty
/api/alert-events non-empty
/api/notifications non-empty
```

Cross-domain gateway regression:

```text
https://video.lute-tlz-dddd.top 200
https://mkt.lute-tlz-dddd.top 200
https://voc.lute-tlz-dddd.top 200
```

Supported claim: production has been deployed to `80f0566` and schema `202606110023`.

Unsupported claim: production write E2E is complete. No new production test user, Source, Task, Dataset, Report, notification, email, provider call, or scheduler mutation was created in this release pass.

## 8. M3 Production Release Evidence

M3 GitHub API-first deepening production release was executed after PR #3 was merged into `main`.
This section is historical release evidence. The M3 GitHub package gate production identity is recorded in section 11 as `f04c8ea77cc64f28d391e992012525e1704ec1a3`; the current production identity after the M5 docs/page production gate is recorded near the end of this log as `af23cefc92aa9fec336f632a5b1561623811c2fd`.

```text
release commit: e9ccb814899231d49be2f130ed0a9ee9599c93fc
previous production HEAD: 80f0566288ab1cab3348730c65df811bcfd42d9a
release method: git bundle upload + git merge --ff-only FETCH_HEAD
preflight: passed
api image build: passed
web image build: passed
gateway reload: passed
gateway dry-run: passed
```

Schema state after M3:

```text
schema=current
schema_revision=202606110023
schema_head=202606110023
```

M3 did not add a migration; the production schema remained aligned with BrowserDiagnosticRun/Job/JobRun release head.

Container state:

```text
data_achieve_scrapy_api healthy
data_achieve_scrapy_db healthy
data_achieve_scrapy_edge healthy
data_achieve_scrapy_web healthy
```

Public page smoke:

```text
/dashboard 200
/intelligence 200
/reports 200
/tasks 200
/sources 200
/alerts 200
/notifications 200
/projects 200
/signals 200
/raw-records 200
/entities 200
/automation 200
/datasets 200
```

Authenticated read-only API smoke passed for existing demo credentials:

```text
/api/auth/me passed
/api/dashboard/overview passed
/api/tasks passed
/api/reports passed
/api/alert-events passed
/api/notifications passed
```

GitHub API-first package field contract:

```text
GET /api/automation/platform-packages/github-api-first
required fields include:
- license_spdx_id
- default_branch
- latest_release_tag
- latest_release_published_at
- pushed_at
```

Cross-domain gateway regression:

```text
https://video.lute-tlz-dddd.top 200
https://mkt.lute-tlz-dddd.top 200
https://voc.lute-tlz-dddd.top 302
https://voc.lute-tlz-dddd.top/login/?next=%2Fsuperset%2Fwelcome%2F 200 after redirect
https://scrapy.lute-tlz-dddd.top/api/health 200
```

Supported claim: production has been deployed to `e9ccb81`, schema remains `202606110023`, and M3 GitHub API-first field contract is available through authenticated read-only API.

Unsupported claim: production write E2E is complete. No new production test user, Source, Task, Dataset, Report, notification, email, provider call, or scheduler mutation was created in this release pass.

## 9. Remaining Authorization Points

Before any additional production write E2E outside the completed M3 GitHub scope:

1. Confirm test account/workspace.
2. Confirm allowed Source/Task/Dataset/Report write scope.
3. Confirm cleanup register fields and cleanup command.
4. Confirm no provider call, no external send, no scheduler mutation unless separately authorized.

## 10. Next Execution Step

The next executable step is not another release-boundary pass. It is either:

1. M4 Independent site authorized test-site E2E with cleanup register; or
2. M5 Public Web/RSS/Docs local package scaffold and tests; or
3. A separate P5 gate for dataset export, provider call, email send, scheduler mutation, or production browser run.

Do not claim broader L4 production write coverage until the specific option is explicitly authorized and completed.

## 11. M3 GitHub API-first Production Package Gate

M3 GitHub API-first production package gate was executed on 2026-06-23 after rebuilding the release candidate on top of production `origin/main`.

Authorization envelope:

```text
scope_type=topic
scope_value=web-scraping
max_repositories=3
allowed: Source/Task write, one GitHub API task run, Dataset save, report asset, drift snapshot
denied: dataset export, provider call, email send, scheduler mutation, production browser run, browser artifact write
retention: cleanup_after_evidence
```

Deployment evidence:

```text
stale direct candidate: c640ff4 was not fast-forward from production e97810a
release base: origin/main merged into codex/prd2-r0-release-boundary
backup branch: backup/pre-github-gate-20260623
deployed SHA: f04c8ea77cc64f28d391e992012525e1704ec1a3
remote HEAD: f04c8ea77cc64f28d391e992012525e1704ec1a3
.deploy-sha: f04c8ea77cc64f28d391e992012525e1704ec1a3
schema_revision: 202606110023
schema_head: 202606110023
```

Production gate evidence:

```text
PLAYWRIGHT_BASE_URL=https://scrapy.lute-tlz-dddd.top PLAYWRIGHT_REAL_API=true pnpm --dir apps/web exec playwright test --grep "renders automation platform packages"
result: 2 passed
```

Cleanup evidence:

```text
pre-cleanup dry-run:
users=8
workspaces=8
workspace_members=16
notifications=8
dataset_versions=2
dataset_drift_events=2
report_audit_events=2

cleanup execute: removed the same scoped residue
post-cleanup recount: all scoped E2E fixture categories returned zero
```

Supported claim: production has been deployed to `f04c8ea`, schema remains `202606110023`, and the M3 GitHub API-first package has one authorized small-scope L4 production gate with cleanup evidence.

Unsupported claim: broad recurring GitHub collection, retained dataset lifecycle, dataset export, provider enrichment, product/report/subscription email, scheduler mutation, production browser execution, or browser artifact retention is complete.

## 12. M5 Public Content Production Package Smoke

M5 Public Web/RSS/Docs production package smoke was executed on 2026-06-23 after deploying the public content Dataset/drift/report slice.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: one temporary e2e user, one public_feed Source, one enabled Task, one RSS TaskRun, one public_content_update DatasetVersion, read-only drift check, read-only report preview
denied: dataset export, Report asset creation, provider call, email send, scheduler mutation, production browser run, browser artifact write
retention: cleanup_after_evidence
```

Deployment evidence:

```text
previous production HEAD: f04c8ea77cc64f28d391e992012525e1704ec1a3
backup branch: backup/pre-public-content-gate-20260623-1915
deployed SHA: e1359759aa1cab157bb98ec8abda4ff580cbfe7d
remote HEAD: e1359759aa1cab157bb98ec8abda4ff580cbfe7d
.deploy-sha: e1359759aa1cab157bb98ec8abda4ff580cbfe7d
schema_revision: 202606110023
schema_head: 202606110023
containers: api/db/edge/web healthy
```

Public page smoke returned `200` for:

```text
/dashboard
/automation
/datasets
/tasks
/sources
/raw-records
/reports
/alerts
/notifications
/projects
/signals
/entities
/toolkit
```

Production smoke evidence:

```text
feed_url: https://hnrss.org/frontpage
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
Drift checked_tasks: 1
Drift run_started: false
Drift alert_created: false
Report entry_count: 5
Report report_created: false
Report run_started: false
```

Cleanup evidence:

```text
exact cleanup dry-run before execute:
users=1
workspaces=1
workspace_members=2
notifications=1
sources=1
collection_tasks=1
task_runs=1
raw_records=1
entities=1
entity_snapshots=1
datasets=1
dataset_versions=1
dataset_drift_events=0
dataset_export_jobs=0

exact cleanup execute: removed the same scoped objects
post-cleanup exact-ID dry-run: all listed categories returned zero
post-cleanup generic E2E dry-run: all categories returned zero
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-production-smoke-draft-20260623.md
```

Supported claim: production had been deployed to `e1359759` for this smoke, and the M5 Public Web/RSS/Docs package has one authorized small-scope production smoke covering public RSS collection, DatasetVersion save, read-only drift check, read-only report preview, and cleanup.

Unsupported claim: recurring RSS monitoring, retained dataset lifecycle, dataset export, provider enrichment, product/report/subscription email, scheduler mutation, production browser execution, or browser artifact retention is complete.

## 13. M5 Public Content Report Asset Gate

M5 Public Content Report asset gate was executed on 2026-06-23 after the prior production package smoke. The first run exposed a production-only database length constraint, then a hotfix was deployed and the gate was rerun successfully.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: one temporary e2e user, one public_feed Source, one enabled Task, one RSS TaskRun, one public_content_update DatasetVersion, one public_content Report asset, one ReportAuditEvent
denied: dataset export, provider call, email send, scheduler mutation, production browser run, browser artifact write
retention: cleanup_after_evidence
```

Deployment and hotfix evidence:

```text
initial deployed SHA: 2ebbe4a584c6e1122ba3b180998e6548667de0f9
initial backup branch: backup/pre-public-content-report-asset-gate-20260623115056
initial failure: POST /api/automation/public-content-report-assets returned 500
root cause: reports.report_type is VARCHAR(20); public_content_update is 21 characters
fix: Report.report_type uses public_content; Dataset.dataset_type and report content schema remain public_content_update
hotfix SHA: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
hotfix backup branch: backup/pre-public-content-report-asset-hotfix-20260623115906
remote HEAD: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
.deploy-sha: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
schema_revision: 202606110023
schema_head: 202606110023
containers: api/db/edge/web healthy
```

Successful production gate evidence:

```text
feed_url: https://hnrss.org/frontpage
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
Drift checked_tasks: 1
Drift run_started: false
Drift alert_created: false
Report preview report_created: false
Report asset report_created: true
Report asset report_type: public_content
Report asset report_status: generated
Report asset notification_created: false
reports.detail status: generated
```

Cleanup evidence:

```text
failed first-run cleanup:
pre-cleanup users=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entities=1, entity_snapshots=1, datasets=1, dataset_versions=1, reports=0, report_audit_events=0
post-cleanup exact-ID dry-run: all categories returned zero

successful run cleanup:
pre-cleanup users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entities=1, entity_snapshots=1, datasets=1, dataset_versions=1, reports=1, report_audit_events=1
cleanup execute: removed the same scoped objects
post-cleanup exact-ID dry-run: all categories returned zero
post-cleanup generic E2E dry-run: all categories returned zero
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-report-asset-gate-draft-20260623.md
```

Supported claim: production has been deployed to `fb05c61`, and M5 Public Content has one authorized Report asset gate covering public RSS collection, DatasetVersion save, read-only drift check, read-only report preview, Report asset creation, Report detail retrieval, and cleanup.

Unsupported claim: recurring RSS monitoring, retained dataset lifecycle, dataset export, provider enrichment, product/report/subscription email, scheduler mutation, production browser execution, or browser artifact retention is complete.

## 14. M5 Public Content Dataset Export Gate

M5 Public Content Dataset export gate was executed on 2026-06-23 against the already deployed `fb05c61` production code point. No production deployment was performed for this gate.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: one temporary e2e user, one public_feed Source, one enabled Task, one RSS TaskRun, one public_content_update DatasetVersion, one CSV DatasetExportJob, one export artifact file, one authenticated export download
denied: Report asset, provider call, email send, scheduler mutation, production browser run, browser artifact write
retention: cleanup_after_evidence
```

Production baseline:

```text
remote HEAD: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
.deploy-sha: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
health: production/ok/connected/current
schema_revision: 202606110023
schema_head: 202606110023
containers: api/db/edge/web healthy
```

Successful production gate evidence:

```text
feed_url: https://hnrss.org/frontpage
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion schema_version: public_content_update.v1
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
Export endpoint: POST /api/automation/product-dataset-exports
Export format: csv
Export status: success
Export filename: e2e-public-content-export-dataset-20260623121345-v1-1ad76121.csv
Export content_type: text/csv; charset=utf-8
Export artifact_size_bytes: 4900
Export checksum_sha256: d64474f7cc844de9be1faf48f5e597043dd5cb27318dbeb57a4ab1a78b4995f0
Export audit event: product_dataset_export_file_written
Export run_started: false
Export history total: 1
Export history export_created: false
Export history run_started: false
Download content_type: text/csv; charset=utf-8
Download byte_length: 4900
Download contains title/link/published_at header: true
Download contains content_hash: true
Download contains feed_url: true
```

Cleanup evidence:

```text
pre-cleanup users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entities=1, entity_snapshots=1, datasets=1, dataset_versions=1, dataset_export_jobs=1, export_artifact_files=1
cleanup execute: removed the same scoped database objects and the export artifact file
post-cleanup exact-ID dry-run: all categories returned zero, including export_artifact_files=0
post-cleanup generic E2E dry-run: all categories returned zero
temporary remote cleanup script: removed from host /tmp and container /tmp
post-cleanup production pages: /dashboard, /automation, /datasets, /tasks, /sources, /raw-records, /reports, /alerts, /notifications, /projects, /signals, /entities, and /toolkit returned 200
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-export-gate-draft-20260623.md
```

Supported claim: production remains deployed to `fb05c61`, and M5 Public Content has one authorized Dataset export gate covering public RSS collection, DatasetVersion save, CSV DatasetExportJob creation, export artifact file write, authenticated export download, exact-ID cleanup, artifact deletion, and generic cleanup recount.

Unsupported claim: recurring RSS monitoring, retained dataset/export lifecycle, provider enrichment, product/report/subscription email, scheduler mutation, production browser execution, or browser artifact retention is complete.

## 15. M5 Public Content Retained Lifecycle Gate

M5 Public Content retained lifecycle gate was executed on 2026-06-23 against the already deployed `fb05c61` production code point. No production deployment was performed for this gate. Unlike the previous cleanup-after-evidence gates, this one intentionally retained a small named canary asset set.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: one retained user, one public_feed Source, one enabled Task, one RSS TaskRun, one public_content_update DatasetVersion, one read-only drift check, one public_content Report asset, one CSV DatasetExportJob, one export artifact file, post-login visibility checks
denied: cleanup execution, provider call, email send, scheduler mutation, production browser run, browser artifact write, drift event persistence
retention: retained_no_cleanup
```

Retained asset manifest:

```text
actor_email: retained-public-content-20260623123816-90w0q7@example.com
source_id: c86b280c-0315-4d93-bcd7-37786996a22b
task_id: b8a4cb3f-abe9-48f6-bb66-7ff4962bcdc6
task_run_id: 1f684c04-0aab-48b7-ae4b-824526efaadc
dataset_id: ee4a4a7a-1ea8-4864-b10d-031b365e5efb
dataset_version_id: 6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8
report_id: 38a0f8ce-59ed-46da-a9ae-968c6a020e57
export_job_id: 3f43b866-1312-47d0-95b6-90322a2c7ee5
```

Production gate evidence:

```text
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion schema_version: public_content_update.v1
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
Drift checked_tasks: 1
Drift warning_tasks: 1
Drift critical_tasks: 0
Drift run_started: false
Drift alert_created: false
Drift event persisted: false
Report asset report_type: public_content
Report asset report_status: generated
Report asset notification_created: false
Export status: success
Export filename: retained-public-content-lifecycle-20260623123816-v1-3f43b866.csv
Export artifact_size_bytes: 4344
Export row_count: 5
Export checksum_sha256: 0253d01911bd63a4ef529ce53001e958fe1fab7570037b1c072863b4418b322a
```

Retention verification:

```text
cookie reset and relogin: passed
source_found: true
task_found: true
task_run_found: true
dataset_found: true
dataset version_found: true
report_found: true
export_found: true
export download content_type: text/csv; charset=utf-8
export download byte_length: 4344
download contains title/link/published_at header: true
download contains content_hash: true
download contains feed_url: true
```

Read-only DB/volume inventory:

```text
status: ready
violations: []
cleanup_executed: false
users=1
workspaces=1
workspace_members=2
notifications=1
sources=1
collection_tasks=1
task_runs=1
raw_records=1
entities=1
entity_snapshots=1
datasets=1
dataset_versions=1
dataset_drift_events=0
reports=1
report_audit_events=1
dataset_export_jobs=1
export_artifact_files=1
```

Export artifact path:

```text
/app/exports/datasets/bf51c6a8-fba5-5528-ac91-89ffd84f85c2/ee4a4a7a-1ea8-4864-b10d-031b365e5efb/6e2cbc17-4df3-44c3-b5ab-a5fd9e89cbd8/retained-public-content-lifecycle-20260623123816-v1-3f43b866.csv
```

Generic cleanup dry-run:

```text
scripts/cleanup-e2e-fixtures.sh --older-than-hours 0
dry_run: true
all categories: 0
```

Post-gate smoke:

```text
health: production/ok/connected/current
remote HEAD: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
.deploy-sha: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
containers: api/db/edge/web healthy
/dashboard, /automation, /datasets, /tasks, /sources, /raw-records, /reports, /alerts, /notifications, /projects, /signals, /entities, /toolkit: 200
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-retained-lifecycle-gate-draft-20260623.md
```

Supported claim: production remains deployed to `fb05c61`, and M5 Public Content has one retained production canary covering public RSS collection, DatasetVersion save, read-only drift check, Report asset persistence, DatasetExportJob persistence, export artifact retention, post-login list/detail visibility, export download, and read-only DB/volume inventory.

Unsupported claim: multi-day retention, automated TTL, automatic cleanup job, scheduler refresh, production-persisted public-content-specific drift event, provider enrichment, product/report/subscription email, production browser execution, or browser artifact retention is complete.

## 16. M5 Public Content Drift Event Persistence Local Slice

M5 Public Content drift event persistence was implemented locally on 2026-06-24 after the retained lifecycle gate showed `dataset_drift_events=0` for the retained canary inventory. This slice did not deploy production and did not write a production drift event.

Implemented local code paths:

```text
POST /api/automation/public-content-drift-events
GET /api/automation/public-content-drift-events
event_type: public_content_drift
audit saved: public_content_drift_event_saved
audit reused: public_content_drift_event_reused
run_started: false
alert_created: false
```

Validation:

```text
uv run pytest tests/integration/test_sources_tasks.py -k public_feed
result: 1 passed, 20 deselected

uv run pytest
result: 106 passed, 1 warning

uv run ruff check src tests
result: passed

pnpm --dir apps/web exec tsc --noEmit
result: passed

pnpm lint:web
result: passed

pnpm test:web
result: 8 passed

pnpm --dir apps/web build
result: passed

git diff --check
result: passed
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-drift-event-local-slice-draft-20260624.md
```

Supported claim: the local codebase now has a dedicated public-content drift event persistence path that saves and lists `public_content_drift` snapshots from the existing read-only drift check and keeps collector, alert, notification, scheduler, export, provider, and browser side effects disabled.

Unsupported claim: this local-slice validation alone proves production behavior, the retained canary has been updated, scheduler refresh is active, or recurring monitoring is enabled. The separate production gate is recorded in section 17.

## 17. M5 Public Content Drift Event Production Gate

M5 Public Content drift-event production gate was executed on 2026-06-24 after explicit authorization. This gate deployed the local drift-event persistence slice and used a new scoped fixture; it did not mutate the retained canary from 2026-06-23.

Authorization envelope:

```text
scope_type=public_rss_feed
scope_value=https://hnrss.org/frontpage
allowed: deploy, one scoped user/workspace, one public_feed Source, one enabled Task, one manual RSS TaskRun, one public_content_update DatasetVersion, one read-only drift check, one public_content_drift DatasetDriftEvent save, one repeated save to verify reuse, exact cleanup
denied: provider call, email send, scheduler mutation/tick, Dataset export file write, Report asset creation, production browser run, browser artifact write, retained canary mutation
cleanup_policy: cleanup_after_evidence
```

Deployment evidence:

```text
previous production HEAD: fb05c61ab137b1c1cb7519b661d98a97ae0cead6
deployed HEAD: 68c27e0f9c62d542149eedc5b18439938103b4bb
.deploy-sha: 68c27e0f9c62d542149eedc5b18439938103b4bb
preflight: passed
docker build: passed
alembic upgrade head: completed, schema stayed 202606110023
gateway reload: retry passed after edge became healthy
```

Production gate evidence:

```text
actor_email: e2e-public-drift-event-20260624010551-nj20wh@example.com
source_id: d46bbd8e-cbeb-434c-a351-af4ec680e8d9
task_id: 73af3237-414e-4cfe-b39c-57935f2216f4
task_run_id: e4a4f1bb-c21e-4378-8abe-d0ada033b1e6
dataset_id: acc585e5-0388-4cfe-847c-90e490e68056
dataset_version_id: 961eb51d-ae1e-407f-9cbb-46dfd02bf8a7
drift_event_id: 6acbd871-e0f8-4580-a7c7-b3d2459962f1
repeated_drift_event_id: 6acbd871-e0f8-4580-a7c7-b3d2459962f1
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
feed entries collected: 5
Dataset type: public_content_update
DatasetVersion schema_version: public_content_update.v1
DatasetVersion row_count: 5
DatasetVersion average_completeness_percent: 90
DriftEvent event_type: public_content_drift
DriftEvent status: warning
Drift signal_groups: field_missingness -> missing:tags
Drift run_started: false
Drift alert_created: false
history before save: total=0
history after save: total=1
saved audit: public_content_drift_event_saved
reused audit: public_content_drift_event_reused
```

Cleanup evidence:

```text
initial exact dry-run: users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entity_snapshots=1, entities=1, datasets=1, dataset_versions=1, dataset_drift_events=1, dataset_export_jobs=0, export_artifact_files=0
first cleanup execute: blocked by EntitySnapshot -> Entity foreign key before commit
post-failure dry-run: scoped fixture still present
patched exact dry-run: users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=2, entity_snapshots=2, entities=1, datasets=1, dataset_versions=1, dataset_drift_events=1, dataset_export_jobs=0, export_artifact_files=0
cleanup execute: succeeded
post-cleanup exact dry-run: all categories zero
generic E2E cleanup dry-run: all categories zero
temporary host cleanup script: removed
temporary container cleanup script: removed with root user after default user lacked permission
```

Post-gate smoke:

```text
health: production/ok/connected/current
remote HEAD: 68c27e0f9c62d542149eedc5b18439938103b4bb
.deploy-sha: 68c27e0f9c62d542149eedc5b18439938103b4bb
containers: api/db/edge/web healthy
/dashboard, /automation, /datasets, /tasks, /sources, /raw-records, /reports, /alerts, /notifications, /projects, /signals, /entities, /toolkit: 200
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-drift-event-production-gate-draft-20260624.md
```

Supported claim: production now includes the dedicated public-content drift-event persistence path, and one scoped production gate proved `public_content_drift` DatasetDriftEvent save/list/idempotent reuse with cleanup-after-evidence.

Unsupported claim: the retained public-content canary has been updated with a drift event, recurring monitoring is active, scheduler refresh is configured, provider enrichment ran, email was sent, a Report asset was created in this gate, a Dataset export file was written in this gate, a production browser ran, or browser artifacts were written.

## M5 Public Content Docs Diff Local Slice - 2026-06-24

M5 Public Content docs diff local slice was implemented after the scoped production drift-event gate. This section records the local code/test/docs pass that preceded the separate production docs/page gate recorded in the next section.

Scope:

```text
allowed: generic_web.v1 schema metadata, page content_hash, public-content Dataset preview/save for generic_web records, hash drift check, public_content_drift save/reuse, report preview, Report asset local path, API/Web/docs sync
denied: production deploy, production Source/Task/TaskRun/DatasetVersion/DatasetDriftEvent/Report write, retained canary mutation, provider call, email send, scheduler mutation/tick, Dataset export file write, production browser run, browser artifact write
```

Implementation evidence:

```text
generic_web content schema: generic_web.v1
generic_web docs/page row fields: title, link, updated_at, summary, content_hash, source_type, content_kind, site_url, text_length
public-content accepted record_types: public_feed, generic_web
public-content accepted task collector_types: public_feed, generic_web
export preview collector_schema_versions: actual source records, e.g. generic_web.v1
```

Validation evidence:

```text
targeted pytest: 3 passed, 1 warning
ruff: All checks passed
Web TypeScript: passed
Web lint: passed
API full pytest: 107 passed, 1 warning
Web unit: 8 passed
Web build: passed
git diff --check: passed
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-docs-diff-local-slice-draft-20260624.md
```

Supported claim: the local codebase can now use `generic_web` public docs/page snapshots as public-content Dataset rows, detect docs/page content hash changes, save/reuse `public_content_drift` events, and generate public-content report output without starting drift/report collectors.

Unsupported claim for this local slice alone: production behavior, recurring monitoring, scheduler refresh, provider enrichment, email delivery, Dataset export, production browser execution, or browser artifact writing. Production docs/page behavior is recorded separately in the next section.

## M5 Public Content Docs Page Production Gate - 2026-06-24

M5 Public Content docs/page production gate was executed after the local docs diff slice and explicit continuation authorization. This gate deployed the local `generic_web` public-content path and used a new scoped fixture; it did not mutate the retained canary from 2026-06-23.

Authorization envelope:

```text
scope_type=public_docs_page
scope_value=https://www.iana.org/help/example-domains
allowed: deploy, one scoped user/workspace, one generic_web Source, one enabled Task, one manual docs/page TaskRun, one public_content_update DatasetVersion, one read-only drift check, one public_content_drift DatasetDriftEvent save, one repeated save to verify reuse, one public_content Report asset, exact cleanup
denied: retained canary mutation, provider call, email send, scheduler mutation/tick, Dataset export file write, production browser run, browser artifact write
cleanup_policy: cleanup_after_evidence
```

Deployment evidence:

```text
previous production HEAD: 68c27e0f9c62d542149eedc5b18439938103b4bb
deployed HEAD: af23cefc92aa9fec336f632a5b1561623811c2fd
.deploy-sha: af23cefc92aa9fec336f632a5b1561623811c2fd
preflight: passed
docker build: passed
alembic upgrade head: completed, schema stayed 202606110023
gateway reload: first attempt stopped while edge health was starting, retry passed after edge became healthy
```

Production gate evidence:

```text
actor_email: e2e-public-docs-page-20260624034856-8vyj7q@example.com
docs_url: https://www.iana.org/help/example-domains
source_id: a3d15d9c-6301-42a7-a55d-8e3021717662
task_id: 003abf09-e28c-4947-9631-d7d680212f0a
task_run_id: a8317d82-fa1d-49b1-a834-18eafdc47ea1
dataset_id: dc577ed3-a6e1-40be-aab8-e64069c8b965
dataset_version_id: 9f4d3da5-2d87-45bd-8d15-5ef3d8b7a73d
drift_event_id: 05847c1a-5013-4fc8-8d1f-5bec747d0408
repeated_drift_event_id: 05847c1a-5013-4fc8-8d1f-5bec747d0408
report_id: 9b2ec052-0ba8-482f-9902-209da8c51885
TaskRun status: success
TaskRun records_count: 1
TaskRun entities_count: 1
Dataset type: public_content_update
DatasetVersion row_count: 1
DatasetVersion average_completeness_percent: 100
collector_schema_versions: generic_web.v1
row source_type: generic_web
row content_kind: html_snapshot
row content_hash: d3362b3fe187484e529f2504d628e6b9f0f5c8a2ef10fc09efddcc1631d0be21
row text_length: 1217
DriftEvent event_type: public_content_drift
DriftEvent status: ok
Drift run_started: false
Drift alert_created: false
history before save: total=0
history after save: total=1
repeated save reused same ID: true
Report asset report_type: public_content
Report asset status: generated
Report notification_created: false
stored report detail: passed
```

Cleanup evidence:

```text
initial script attempt: failed because second identical static-page TaskRun was successfully deduplicated to records_count=0
initial partial fixture cleanup: exact execute succeeded and post-cleanup dry-run returned all zero
successful gate exact dry-run: users=1, workspaces=1, workspace_members=2, notifications=1, sources=1, collection_tasks=1, task_runs=1, raw_records=1, entity_snapshots=1, entities=1, datasets=1, dataset_versions=1, dataset_drift_events=1, reports=1, report_audit_events=1, dataset_export_jobs=0
cleanup execute: succeeded
post-cleanup exact dry-run: all categories zero
generic E2E cleanup dry-run: all categories zero
temporary host/container cleanup scripts and remote bundle: removed
```

Post-gate smoke:

```text
health: production/ok/connected/current
remote HEAD: af23cefc92aa9fec336f632a5b1561623811c2fd
.deploy-sha: af23cefc92aa9fec336f632a5b1561623811c2fd
containers: api/db/edge/web healthy
/dashboard, /automation, /datasets, /tasks, /sources, /raw-records, /reports, /alerts, /notifications, /projects, /signals, /entities, /toolkit: 200
```

Evidence draft:

```text
drafts/analysis/analysis-boundary-m5-public-content-docs-page-production-gate-draft-20260624.md
```

Supported claim: production now includes the `generic_web` docs/page public-content path, and one scoped production gate proved docs/page TaskRun, `public_content_update` DatasetVersion, read-only drift, `public_content_drift` DatasetDriftEvent save/list/idempotent reuse, `public_content` Report asset creation, and cleanup-after-evidence.

Unsupported claim: the retained public-content canary has been updated, recurring monitoring is active, scheduler refresh is configured, provider enrichment ran, email was sent, a Dataset export file was written in this gate, a production browser ran, or browser artifacts were written.

---
title: PRD2 R0 Release Boundary Execution Log
doc_type: workflow
module: automation
topic: prd2-r0-release-boundary
status: stable
created: 2026-06-21
updated: 2026-06-21
owner: self
source: human+ai
---

# PRD2 R0 Release Boundary Execution Log

## 0. Scope

本文件记录 2026-06-21 R0 release boundary 的实际执行结果。R0 目标是把本地 PRD2/M1/M2 工作树和当前生产部署状态分层，不把本地通过、DB dry-run 或生产只读 smoke 说成生产写入验收。

初始 R0 release-boundary pass 没有执行生产部署、生产数据库 migration、生产写入、登录态操作、provider call、邮件发送、站内通知发送或调度变更。2026-06-21 后续 post-merge release 已在明确授权后执行生产部署和 Alembic migration；生产写入 E2E、provider call、邮件发送、站内通知发送和调度变更仍未执行。

## 1. Task Orchestration

| Track | Task | Status | Evidence |
|---|---|---|---|
| R0-1 | Release scope inventory | done | `git status --short`、`git diff --stat`；当前在 `main`，无 staged diff |
| R0-2 | Local validation gate | done | `pnpm lint:web`、`pnpm test:web`、`bash scripts/verify-mvp.sh` |
| R0-3 | Local DB/migration gate | done | `POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db` |
| R0-4 | Production read-only smoke | done | `/api/health`、`/automation`、`/datasets`、unauthenticated `/api/automation/platform-packages` |
| R0-5 | Release branch setup and scoped staging | done | 已从 `main` 切到 `codex/prd2-r0-release-boundary`；RC1/RC2 已 staged，RC3 草稿未 staged；尚未 commit |
| R0-6 | Post-merge production release | done | production HEAD `80f0566`；migration `202606110020 -> 202606110023`；L3 read-only smoke passed |
| R0-7 | Authorized production write E2E | pending_authorization | 需要专用测试账号/workspace、明确写入范围和 cleanup register |
| R0-8 | M3 post-R0 production release | done | production HEAD `e9ccb81`；schema 仍为 `202606110023`；GitHub API-first 字段合同 L3 read-only smoke passed |

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

Before production write E2E:

1. Confirm test account/workspace.
2. Confirm allowed Source/Task/Dataset/Report write scope.
3. Confirm cleanup register fields and cleanup command.
4. Confirm no provider call, no external send, no scheduler mutation unless separately authorized.

## 10. Next Execution Step

The next executable step is not another release-boundary pass. It is either:

1. Authorized production write E2E with cleanup register; or
2. Remaining M3 GitHub API-first deepening for README metadata, issue activity, commit freshness, explicit DatasetVersion schema/provenance and drift rules.

Do not claim L4 production write coverage until option 1 is explicitly authorized and completed.

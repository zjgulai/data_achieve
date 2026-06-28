---
title: PRD2 R0 Release Candidate Staging Plan
doc_type: analysis
module: automation
topic: prd2-r0-release-candidate-staging-plan
status: draft
created: 2026-06-21
updated: 2026-06-21
owner: self
source: human+ai
---

# PRD2 R0 Release Candidate Staging Plan

## 0. Scope

This plan splits the current dirty worktree on branch `codex/prd2-r0-release-boundary` into reviewable release candidates. It does not stage, commit, push, deploy, run production migrations, or perform production writes by itself.

Evidence labels remain separate:

| Label | Meaning in this plan |
|---|---|
| `local validation` | `pnpm lint:web`, `pnpm test:web`, `bash scripts/verify-mvp.sh` |
| `local DB validation` | `bash scripts/verify-mvp.sh --with-db` against local PostgreSQL |
| `production read-only smoke` | `curl` checks against production without auth or mutation |
| `authorized production write` | Not performed in this plan; requires explicit approval |

## 1. Current Change Inventory

Current branch:

```text
codex/prd2-r0-release-boundary
```

Current staged diff:

```text
none
```

Tracked modified files:

```text
README.md
apps/api/src/data_intelligence_hub/api/routes/automation.py
apps/api/src/data_intelligence_hub/models/__init__.py
apps/api/src/data_intelligence_hub/models/automation_plan.py
apps/api/src/data_intelligence_hub/repositories/automation_plans.py
apps/api/src/data_intelligence_hub/schemas/automation.py
apps/api/src/data_intelligence_hub/services/automation_service.py
apps/api/tests/integration/test_sources_tasks.py
apps/web/src/components/automation/automation-workbench.tsx
apps/web/src/lib/api/automation.ts
apps/web/src/lib/api/mock.ts
apps/web/src/types/automation.ts
apps/web/tests/e2e/main-flows.spec.ts
docs/api/api-contract-data-intelligence-hub-stable.md
docs/product/product-prd-data-intelligence-hub-stable.md
drafts/analysis/analysis-prd-next-roadmap-draft-20260619.md
```

Untracked candidate files:

```text
apps/api/alembic/versions/202606110021_browser_diagnostic_runs.py
apps/api/alembic/versions/202606110022_browser_diagnostic_jobs.py
apps/api/alembic/versions/202606110023_browser_diagnostic_job_runs.py
docs/workflows/workflow-browser-evidence-artifact-retention-stable.md
docs/workflows/workflow-prd2-deployed-state-gap-execution-plan-stable.md
docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md
docs/workflows/workflow-prd2-r0-release-boundary-execution-log-stable.md
drafts/analysis/analysis-agent-reach-browser-harness-platform-roadmap-draft-20260621.md
drafts/analysis/analysis-prd2-r0-release-candidate-staging-plan-draft-20260621.md
```

## 2. Release Candidate Split

### RC1 - PRD2 Automation Platform Runtime

Purpose: ship the actual runtime slice for PRD2 M1/M2: CapabilityProbe, BrowserDiagnosticRun/Job/JobRun, local browser runner evidence, platform packages, GitHub Tool Radar dataset/report/drift, and the matching workbench UI.

Recommended staged files:

```text
apps/api/src/data_intelligence_hub/api/routes/automation.py
apps/api/src/data_intelligence_hub/models/__init__.py
apps/api/src/data_intelligence_hub/models/automation_plan.py
apps/api/src/data_intelligence_hub/repositories/automation_plans.py
apps/api/src/data_intelligence_hub/schemas/automation.py
apps/api/src/data_intelligence_hub/services/automation_service.py
apps/api/alembic/versions/202606110021_browser_diagnostic_runs.py
apps/api/alembic/versions/202606110022_browser_diagnostic_jobs.py
apps/api/alembic/versions/202606110023_browser_diagnostic_job_runs.py
apps/api/tests/integration/test_sources_tasks.py
apps/web/src/components/automation/automation-workbench.tsx
apps/web/src/lib/api/automation.ts
apps/web/src/lib/api/mock.ts
apps/web/src/types/automation.ts
apps/web/tests/e2e/main-flows.spec.ts
```

Review focus:

1. `BrowserDiagnosticRun/Job/JobRun` schema and migration order from `202606110020` to `202606110023`.
2. No-read/no-write `CapabilityProbe` behavior, especially `agent-reach doctor --json` only.
3. Browser local runner flags: `files_written=false`, `collection_resources_written=false`, redaction summary, promotion gate.
4. UI wording separates diagnostic/probe/read-only evidence from collection success.
5. Test additions cover missing/fake Agent Reach, browser job lifecycle, snapshot replay, fake browser-harness cases, GitHub Tool Radar dataset/drift/report, and dataset alert boundaries.

Patch-staging risk:

| File | Risk | Recommendation |
|---|---|---|
| `apps/api/src/data_intelligence_hub/services/automation_service.py` | Very large mixed service diff | Stage whole file only if RC1 is reviewed as a single platform runtime slice; otherwise split later by backend subtopic |
| `apps/web/src/components/automation/automation-workbench.tsx` | Very large mixed UI diff | Stage whole file only with API client/types/E2E in the same RC |
| `apps/api/tests/integration/test_sources_tasks.py` | Large multi-flow test diff | Stage whole file with RC1 because tests cover the runtime contract |

Verification:

```bash
pnpm lint:web
pnpm test:web
bash scripts/verify-mvp.sh
POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db
```

Production boundary:

1. Deployment requires explicit approval.
2. Production migration from `202606110020` to `202606110023` requires explicit approval.
3. Production write E2E remains separate from deployment.

### RC2 - Stable PRD2 Docs And Release Evidence

Purpose: ship the stable documentation that explains PRD2 contracts, evidence boundaries, and the current release gap.

Recommended staged files:

```text
README.md
docs/api/api-contract-data-intelligence-hub-stable.md
docs/product/product-prd-data-intelligence-hub-stable.md
docs/workflows/workflow-browser-evidence-artifact-retention-stable.md
docs/workflows/workflow-prd2-deployed-state-gap-execution-plan-stable.md
docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md
docs/workflows/workflow-prd2-r0-release-boundary-execution-log-stable.md
```

Review focus:

1. Stable docs use frontmatter.
2. Evidence labels stay separated: local validation, local DB validation, production read-only smoke, authorized production write.
3. Docs do not say production has schema `202606110023`; they keep current production at `202606110020` until deployment evidence changes.
4. Browser evidence retention stays metadata-only by default.

Verification:

```bash
git diff --check -- README.md docs/api/api-contract-data-intelligence-hub-stable.md docs/product/product-prd-data-intelligence-hub-stable.md docs/workflows/workflow-browser-evidence-artifact-retention-stable.md docs/workflows/workflow-prd2-deployed-state-gap-execution-plan-stable.md docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md docs/workflows/workflow-prd2-r0-release-boundary-execution-log-stable.md
```

Production boundary:

Docs-only changes do not authorize deployment, migration, production write, provider call, notification send, or scheduler mutation.

### RC3 - Draft Research And Planning Artifacts

Purpose: preserve research context and future planning without coupling it to the production release candidate.

Recommended staged files:

```text
drafts/analysis/analysis-prd-next-roadmap-draft-20260619.md
drafts/analysis/analysis-agent-reach-browser-harness-platform-roadmap-draft-20260621.md
drafts/analysis/analysis-prd2-r0-release-candidate-staging-plan-draft-20260621.md
```

Review focus:

1. These files are draft/reference material, not product contracts.
2. They may cite local status and roadmap ideas, but should not be used alone to claim production readiness.
3. Keep them out of an emergency production fix if release scope must be minimized.

Verification:

```bash
git diff --check -- drafts/analysis/analysis-prd-next-roadmap-draft-20260619.md drafts/analysis/analysis-agent-reach-browser-harness-platform-roadmap-draft-20260621.md drafts/analysis/analysis-prd2-r0-release-candidate-staging-plan-draft-20260621.md
```

## 3. Recommended Commit Order

If the goal is a clean review history:

1. RC1: `Add PRD2 automation platform runtime`
2. RC2: `Document PRD2 release boundary and evidence gates`
3. RC3: `Add PRD2 platform roadmap and staging notes`

If the goal is one deployment PR:

1. Stage RC1 and RC2 together as a single release candidate.
2. Keep RC3 unstaged or in a separate docs/draft commit.
3. Run the full DB-backed gate on the full candidate.

## 4. Current Gate Result

Latest completed gates before this plan:

```text
pnpm lint:web: passed
pnpm test:web: passed
bash scripts/verify-mvp.sh: passed
POSTGRES_PORT=15432 ... bash scripts/verify-mvp.sh --with-db: passed
git diff --check: passed
production read-only smoke: healthy at schema 202606110020
```

Evidence grade:

| Claim | Max supported grade |
|---|---|
| Local code and migration gate passes through `202606110023` | L2 local validation |
| Production service is healthy at schema `202606110020` | L3 production read-only |
| Production has PRD2 browser diagnostic tables | L0 unsupported until deploy/migration evidence exists |
| Production write E2E passed for this release | L0 unsupported until explicitly authorized and run |

## 5. Immediate Execution Options

Recommended next action:

1. Stage RC1 and RC2 explicitly, not with `git add .`.
2. Leave RC3 unstaged unless the user wants drafts in the same PR.
3. Re-run:

```bash
git diff --cached --check
POSTGRES_PORT=15432 DATABASE_URL=postgresql+asyncpg://data_intel:<local-dev-password>@localhost:15432/data_intel bash scripts/verify-mvp.sh --with-db
```

Stop before commit unless the user explicitly asks for commit creation.

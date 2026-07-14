---
title: GOAL-V2-03 Workflow Planner Phase Two Persistence Implementation Plan
doc_type: implementation_plan
module: workflow-planner
topic: goal-v2-03-workflow-planner-phase-two-persistence
status: locally_complete
review_status: approved
created: 2026-07-13
updated: 2026-07-14
owner: self
source: human+ai
spec: ../specs/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md
phase_one_plan: 2026-07-12-goal-v2-03-workflow-planner-phase-1.md
implementation_authorization: true
local_database_authorization: true
database_migration: created-disposable-postgres-validated
provider_call: false
actor_run: false
llm_call: false
production_boundary: production unchanged
---

# GOAL-V2-03 Workflow Planner Phase Two Persistence Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with test-first discipline. Every task begins with a failing contract or regression test and ends with its focused green gate. Do not treat plan approval as commit、push、deploy、shared database、production migration、Provider、Actor、LLM、Activate 或 Run 授权。

**Goal:** Persist only server-recomputed and Fingerprint-validated WorkflowPlan Preview results as Project-scoped WorkflowPlan assets with immutable versions, reusable MonitoringScope records, per-version QueryTerm snapshots, history, structured comparison, and a bounded Web save flow.

**Architecture:** Keep the existing Phase One Planner pure and write-free. Add a focused persistence schema/model/repository/service layer around its build result. The service owns the only transaction boundary, locks Project then Plan, rechecks idempotency and optimistic concurrency inside the lock, and atomically writes Scope、Version、association、QueryTerm、current pointer and response snapshot. Web persistence contracts and mock state stay separate from the already-large Phase One Preview files.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, PostgreSQL 15, pytest/pytest-asyncio, ruff, mypy, Next.js 15, React 19, TypeScript 5.7, Vitest, Playwright, existing Workbench UI primitives.

---

## Global Constraints

- Source specification: `docs/superpowers/specs/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md`.
- Preserve the Phase One `POST /api/projects/{project_id}/workflow-plans/preview` request, response, deterministic Fingerprint, zero-write behavior, and existing tests.
- Persist no incomplete form draft. A saved Plan starts at `status=previewed`.
- Keep `planning_status=resolved | partially_resolved | held`; `partial` remains Route/Step-only.
- `held` may be saved but never described as approved, active, runnable, or unblocked.
- Plan `name` and `flow_mode` are immutable in Phase Two. A mode change creates a different Plan.
- Same current Fingerprint is a semantic no-op; A→B→A creates v3. Never add a Plan/Fingerprint unique constraint.
- Keep `provider_call=false`, `actor_run=false`, `browser_run=false`, `llm_call=false`, `workflow_run_created=false`, `execution_authorized=false`, `live_send=false`, and `production unchanged`.
- Do not add Activate、Run、Pause、Approval、Schedule、Archive、Delete、WorkflowRun 或 Provider endpoints/buttons.
- Do not read `.env` or credential files. Do not store or log a raw Idempotency-Key.
- Do not add dependencies. Use existing SQLAlchemy JSON, UUID, timestamp, FastAPI, Vitest and Playwright conventions.
- Preserve all pre-existing dirty/untracked files. Do not format or clean unrelated files.
- Never use `git add .`. Stage/commit/push only after separate explicit authorization and only exact Phase Two files.
- All normal unit/API/mock-E2E checks remain local L2 evidence. PostgreSQL constraints/migration checks are local disposable-database evidence, not production acceptance.
- PostgreSQL downgrade is destructive for Phase Two data. It may run only against an explicitly disposable PostgreSQL 15 database with a dedicated allow flag.
- Do not run Next dev server、Next build and Playwright webServer concurrently in the same checkout because they share `.next`.
- Treat every command block as a fresh shell. Commands beginning with `cd apps/api` do not carry that directory into later blocks.

## Authorization Gates

Implementation authorization recorded at Task 0 on 2026-07-13 (historical pre-checkpoint boundary):

    phase_2_design_approved=true
    phase_2_plan_review=approved
    phase_2_implementation_authorization=true
    local_disposable_postgres_write_authorization=true
    commit_authorization=false
    push_authorization=false
    deploy_authorization=false
    production_database_authorization=false

Before Task 0 changes any business file, the user must explicitly approve this plan and authorize local implementation. Before Task 3/9 execute upgrade、downgrade or persistence tests, the same approval must explicitly include disposable local PostgreSQL 15 writes. No approval in this Goal authorizes a shared or production database.

## Scope Check

This plan contains six ordered delivery domains:

1. Freeze persistence contracts without changing Preview.
2. Add tenant-safe models, Migration and repository primitives.
3. Add atomic Save/version/idempotency and read/compare APIs.
4. Prove PostgreSQL constraints, immutability, rollback and concurrency.
5. Add Web Save、Saved Plans、history and Compare using isolated persistence contracts/mock state.
6. Synchronize product/API/architecture state and run the full local exit gate.

Provider execution, WorkflowRun, scheduling, approval/activation lifecycle, production rollout and destructive shared-database rollback remain separate future work.

## Planned File Structure

### Backend — create

- `apps/api/src/data_intelligence_hub/models/workflow_plan.py`
- `apps/api/src/data_intelligence_hub/repositories/workflow_plans.py`
- `apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py`
- `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- `apps/api/src/data_intelligence_hub/services/workflow_planner/comparison.py`
- `apps/api/alembic/versions/202606110027_workflow_plan_persistence.py` only if `202606110026` is still the single head
- `apps/api/tests/unit/test_workflow_plan_models.py`
- `apps/api/tests/unit/test_workflow_plan_persistence_schema.py`
- `apps/api/tests/unit/test_workflow_plan_persistence.py`
- `apps/api/tests/unit/test_workflow_plan_comparison.py`
- `apps/api/tests/integration/test_workflow_plan_repository.py`
- `apps/api/tests/integration/test_workflow_plan_persistence_routes.py`
- `apps/api/tests/postgres/conftest.py`
- `apps/api/tests/postgres/test_workflow_plan_constraints.py`
- `apps/api/tests/postgres/test_workflow_plan_persistence.py`
- `apps/api/tests/postgres/test_workflow_plan_migration.py`
- `scripts/verify-workflow-planner-phase2-migration.sh`

### Backend — modify

- `apps/api/src/data_intelligence_hub/models/__init__.py`
- `apps/api/src/data_intelligence_hub/models/project.py` only for explicit relationships/supporting metadata required by the model
- `apps/api/src/data_intelligence_hub/services/exceptions.py`
- `apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py`
- `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py`
- `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py`
- `apps/api/tests/unit/test_workflow_planner_fingerprint.py`
- `apps/api/tests/integration/test_workflow_planner_preview.py`
- `.github/workflows/ci.yml`
- `.codex/commands.md`

### Web — create

- `apps/web/src/types/workflow-plan-persistence.ts`
- `apps/web/src/lib/api/workflow-plan-persistence.ts`
- `apps/web/src/lib/workflow-plan-persistence-mock.ts`
- `apps/web/src/components/workflow-planner/workflow-plan-save-panel.tsx`
- `apps/web/src/components/workflow-planner/use-unsaved-workflow-planner-guard.ts`
- `apps/web/src/app/automation/plans/page.tsx`
- `apps/web/src/app/automation/projects/[projectId]/plans/[planId]/page.tsx`
- `apps/web/src/components/workflow-planner/saved-workflow-plans-workspace.tsx`
- `apps/web/src/components/workflow-planner/workflow-plan-detail-workspace.tsx`
- `apps/web/src/components/workflow-planner/workflow-plan-version-history.tsx`
- `apps/web/src/components/workflow-planner/workflow-plan-version-compare.tsx`
- `apps/web/tests/unit/workflow-plan-persistence-api.test.ts`
- `apps/web/tests/unit/workflow-plan-persistence-mock.test.ts`
- `apps/web/tests/unit/workflow-plan-assets.test.ts`

### Web — modify

- `apps/web/src/lib/api/client.ts`
- `apps/web/src/app/automation/planner/page.tsx`
- `apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx`
- `apps/web/src/components/dashboard/workflow-planner-entry-cards.tsx`
- `apps/web/src/components/layout/navigation.ts`
- `apps/web/src/lib/workflow-planner.ts`
- `apps/web/tests/unit/workflow-plans-api.test.ts`
- `apps/web/tests/unit/workflow-planner.test.ts`
- `apps/web/tests/unit/navigation.test.ts`
- `apps/web/tests/e2e/main-flows.spec.ts`
- `apps/web/playwright.config.ts` only if a deterministic mock-only port/fixture hook is required

### Documentation and planning — modify

- `docs/product/product-prd-social-media-automation-platform-v2.md`
- `docs/architecture/architecture-data-intelligence-hub-stable.md`
- `docs/api/api-contract-data-intelligence-hub-stable.md`
- `docs/superpowers/specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md`
- `docs/superpowers/specs/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md`
- `docs/superpowers/plans/2026-07-12-goal-v2-03-workflow-planner-phase-1.md`
- `docs/superpowers/plans/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md`
- `TODO.md`
- `.codex/context-pack.md`
- `.codex/ralph-loop.local.md` only if its current overlay still names Phase One as active
- `.kiro/plan/task_plan.md`
- `.kiro/plan/findings.md`
- `.kiro/plan/progress.md`

---

### Task 0: Re-establish Baseline And Authorization Before Business Changes

**Files:**

- Read: `AGENTS.md` if present, user-provided repository contract, approved spec, Phase One plan, current `.codex/.kiro` overlays
- Create temporary evidence only under `tmp/goal-v2-03-phase2-*`
- Modify no business file

- [x] **Step 1: Verify execution authorization and exact boundary**

Require explicit values before continuing:

    phase_2_implementation_authorization=true
    local_disposable_postgres_write_authorization=true|false
    commit_authorization=false unless separately granted
    production_database_authorization=false

If implementation authorization is false, stop after read-only checks. If local PostgreSQL authorization is false, Tasks 1/2/4-8 may be prepared but any Migration execution or persistence test that writes a DB must stop.

- [x] **Step 2: Capture the dirty-worktree baseline without staging**

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --cached --name-only
```

Expected: branch and Phase One overlay are recorded; index is empty; unrelated `drafts/**`、`output/**`、`ref/**` and upload-temp files remain untouched.

- [x] **Step 3: Verify the approved specification and migration head**

```bash
rg -n '^status: approved$|^review_status: approved$|phase_2_spec_file_review=approved' docs/superpowers/specs/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md
cd apps/api && uv run alembic heads
```

Expected: approved spec; exactly one head. If the head is no longer `202606110026`, update this plan and choose the next linear revision before creating a migration.

- [x] **Step 4: Re-run the smallest Phase One contract baseline**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_planner_fingerprint.py tests/integration/test_workflow_planner_preview.py -q
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plans-api.test.ts tests/unit/workflow-planner.test.ts
```

Expected: green before Phase Two implementation. A pre-existing failure is recorded and resolved or separately approved before layering persistence work.

- [x] **Step 5: Record Task 0 progress only**

Update `.kiro/plan/progress.md` to `phase_2_persistence_in_progress` only after implementation authorization. Keep all external/live boundaries false.

Task 0 evidence (2026-07-13): branch `codex/social-api-private-matrix-20260708`, checkpoint `1e4cc4863c9629e2ff249edc0f7722dafaaf6831`, empty index, approved specification markers present, single Alembic head `202606110026`, API baseline `59 passed`, and Web baseline `84 passed`. No database write or migration execution occurred in Task 0.

---

### Task 1: Add Persistence API Contracts And Preserve The Pure Planner Build

**Files:**

- Create: `apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py`
- Create: `apps/api/tests/unit/test_workflow_plan_persistence_schema.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py`
- Modify: `apps/api/tests/unit/test_workflow_planner_fingerprint.py`

- [x] **Step 1: Write failing request/response contract tests**

Lock:

- create request: trimmed `name` length 1..200, `preview_input`, lowercase `sha256:<64hex>` expected Fingerprint;
- version request: no name, required `expected_current_version_id`;
- required trimmed Idempotency-Key length 12..200 at route boundary;
- save outcomes `created | semantic_no_op` and per-attempt `database_write/plan_changed/idempotent_replay`;
- fixed false Provider/Actor/browser/LLM/WorkflowRun/execution fields;
- Plan/Version/Scope/list/detail/history/compare DTOs;
- `limit=50`, range 1..100, `offset>=0`;
- archived Project read contract and immutable Plan name/mode.

Run and confirm RED because the persistence schema does not exist:

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_persistence_schema.py -q
```

- [x] **Step 2: Expose a pure internal build result**

Add a typed internal result containing:

- existing `WorkflowPlanPreview`;
- exact canonical `WorkflowPlanFingerprintPayload` used for the hash.

Keep `build_workflow_plan_preview()` backward-compatible and session-free. It may delegate to the internal builder but must return the identical Preview contract.

- [x] **Step 3: Implement the minimal persistence schemas**

Keep persistence types in the new file; do not add them to the already-large Phase One schema module. Serialize Preview snapshots with Pydantic JSON mode so Decimal、Enum and datetime never reach SQLAlchemy JSON as Python objects.

- [x] **Step 4: Turn the contract tests green and prove Preview parity**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_persistence_schema.py tests/unit/test_workflow_planner_fingerprint.py -q
cd apps/api && uv run ruff check src/data_intelligence_hub/schemas/workflow_plan_persistence.py src/data_intelligence_hub/services/workflow_planner/planner.py tests/unit/test_workflow_plan_persistence_schema.py tests/unit/test_workflow_planner_fingerprint.py
cd apps/api && uv run mypy src/data_intelligence_hub/schemas/workflow_plan_persistence.py src/data_intelligence_hub/services/workflow_planner/planner.py tests/unit/test_workflow_plan_persistence_schema.py
```

Expected: new contract green; identical PlanningInput still produces the same Preview and Fingerprint; all Preview boundary flags remain false.

Task 1 evidence (2026-07-13): missing persistence schema produced the expected collection RED; focused contract/fingerprint gate passed `58` tests; Ruff and mypy passed. The public Preview wrapper remains session-free and delegates to a typed build result containing the exact canonical Fingerprint payload.

---

### Task 2: Add Six SQLAlchemy Models With Tenant And History Constraints

**Files:**

- Create: `apps/api/src/data_intelligence_hub/models/workflow_plan.py`
- Create: `apps/api/tests/unit/test_workflow_plan_models.py`
- Modify: `apps/api/src/data_intelligence_hub/models/__init__.py`
- Modify: `apps/api/src/data_intelligence_hub/models/project.py` only if explicit relationships are required

- [x] **Step 1: Write failing metadata/model tests**

Require exactly:

- `WorkflowPlan`;
- `WorkflowVersion`;
- `MonitoringScope`;
- `WorkflowVersionScope`;
- `QueryTerm`;
- `WorkflowPlanSaveRequest`.

Tests must assert UUID Python defaults, JSON rather than JSONB, immutable rows without `updated_at`, no cascade delete, no Plan/Fingerprint unique constraint, 0-based ordinals, `matched_scope_id` non-null, and the supporting composite unique/FK key families from the approved spec.

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_models.py -q
```

Expected RED: `models.workflow_plan` missing.

- [x] **Step 2: Implement the minimum model graph**

Model fields and constraints must match approved spec section 6/7. In particular:

- Plan: `name`、`flow_mode`、`status=previewed`、current pointer and timestamps;
- Version: metadata、`fingerprint_payload`、normalized input、full Preview payload、Fingerprint and created time;
- Scope: canonical normalized semantic fields and `(project_id, scope_key)` unique;
- association: Version/Scope/ordinal;
- QueryTerm: per-Version data and required matched Scope;
- SaveRequest: exact scope/key/request hashes, Plan/Version, outcome/status and immutable resource response snapshot.

Do not implement update/delete methods or lifecycle statuses not approved.

- [x] **Step 3: Export models and keep metadata complete**

Add explicit imports/`__all__` entries in `models/__init__.py`. Avoid an Alembic env rewrite: importing `data_intelligence_hub.models.base` already loads the package initializer before the submodule.

- [x] **Step 4: Turn model tests green**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_models.py -q
cd apps/api && uv run ruff check src/data_intelligence_hub/models/workflow_plan.py src/data_intelligence_hub/models/__init__.py tests/unit/test_workflow_plan_models.py
cd apps/api && uv run mypy src/data_intelligence_hub/models/workflow_plan.py tests/unit/test_workflow_plan_models.py
```

Expected: metadata contains six tables and approved constraints; this is not Migration proof.

Task 2 evidence (2026-07-13): missing model module produced the expected collection RED; metadata/model gate passed `7` tests; Ruff、mypy and the limited diff check passed. This is model metadata evidence only, not PostgreSQL Migration or trigger proof.

---

### Task 3: Add Alembic 027 And PostgreSQL Constraint Tests

**Authorization:** Stop unless `local_disposable_postgres_write_authorization=true` before executing upgrade/downgrade or PostgreSQL tests.

**Files:**

- Create: `apps/api/alembic/versions/202606110027_workflow_plan_persistence.py` only if head is unchanged
- Create: `apps/api/tests/postgres/conftest.py`
- Create: `apps/api/tests/postgres/test_workflow_plan_constraints.py`

- [x] **Step 1: Recheck the single head immediately before creating the revision**

```bash
cd apps/api && uv run alembic heads
```

Expected: one `202606110026 (head)`. If not, stop and re-plan; do not create a branch or reuse 027.

- [x] **Step 2: Write PostgreSQL-only failing constraint tests**

Tests skip unless a disposable `TEST_DATABASE_URL` and destructive allow flag are present. Cover:

- six table existence;
- `projects(workspace_id,id)` supporting unique;
- all tenant composite FKs;
- legal Plan NULL→v1→current pointer transaction;
- commit with null current pointer rejected;
- cross-Plan/Workspace/Project current pointer rejected;
- Scope key and ordinal uniqueness;
- required QueryTerm matched Scope association;
- allowed status values.

- [x] **Step 3: Implement the additive upgrade**

Create in approved order:

1. Project supporting unique;
2. MonitoringScope;
3. Plan without circular FK;
4. Version;
5. Version–Scope;
6. QueryTerm;
7. SaveRequest;
8. supporting unique/index/composite FKs;
9. current-Version ownership FK and deferred final-state constraint trigger;
10. immutable triggers.

The deferred trigger must re-select the final Plan row by ID at constraint time. It must not reject the INSERT event's transient `NEW.current_version_id=NULL`.

- [x] **Step 4: Implement the destructive downgrade in strict reverse order**

Drop triggers/functions/FKs/indexes/tables and finally the Project supporting unique. Do not alter or backfill old business data.

- [x] **Step 5: Run the focused PostgreSQL gate only in the disposable database**

```bash
cd apps/api && TEST_DATABASE_URL="${TEST_DATABASE_URL:?disposable PostgreSQL required}" ALLOW_DESTRUCTIVE_MIGRATION_TEST=true uv run pytest tests/postgres/test_workflow_plan_constraints.py -q
```

Expected: constraint tests green. SQLite `create_all` is not accepted evidence for this task.

Task 3 evidence (2026-07-13): the pre-027 PostgreSQL RED was `30 failed / 1` false-positive pass; the loose error-message assertion was tightened to SQLSTATE `23514`. On the isolated local PostgreSQL 15 database `data_scrapy_workflow_plan_phase2_test`, the final focused constraint gate passed `31` tests. Ruff、format check and mypy passed; `027 -> 026 -> 027` succeeded, and the current single head is `202606110027`. This is disposable local DB evidence only.

---

### Task 4: Add Tenant-Safe Repository Primitives Without Commit

**Files:**

- Create: `apps/api/src/data_intelligence_hub/repositories/workflow_plans.py`
- Create: `apps/api/tests/integration/test_workflow_plan_repository.py`

- [x] **Step 1: Write failing repository tests**

Cover:

- tenant/project-scoped get/list/count for Plan、Version、Scope and SaveRequest;
- Plan ordering `updated_at DESC, id DESC`;
- Version ordering `version_number DESC`;
- Scope ordering `created_at DESC, id DESC`;
- offset/limit/total;
- Project then Plan row-lock SQL;
- PostgreSQL Scope insert compiled as `ON CONFLICT DO NOTHING RETURNING`;
- add/flush primitives do not commit;
- rollback leaves zero new rows;
- no historical update/delete primitive exists.

```bash
cd apps/api && uv run pytest tests/integration/test_workflow_plan_repository.py -q
```

Expected RED because the repository is missing.

- [x] **Step 2: Implement explicit repository methods**

Repository responsibilities are SQL only:

- workspace/project/Plan/Version restricted reads;
- `lock_project_for_workflow_plan_save`;
- `get_workflow_plan_for_update`;
- completed idempotency lookup;
- Scope insert-or-read;
- add/flush Plan、Version、association、QueryTerm、SaveRequest;
- counts and pagination.

Do not commit, rollback, recompute Preview, hash requests or map HTTP errors in the repository.

- [x] **Step 3: Turn repository tests green**

```bash
cd apps/api && uv run pytest tests/integration/test_workflow_plan_repository.py -q
cd apps/api && uv run ruff check src/data_intelligence_hub/repositories/workflow_plans.py tests/integration/test_workflow_plan_repository.py
cd apps/api && uv run mypy src/data_intelligence_hub/repositories/workflow_plans.py tests/integration/test_workflow_plan_repository.py
```

Task 4 evidence (2026-07-13): missing repository produced the expected collection RED; focused repository gate passed `5` tests. Ruff and mypy passed. Repository methods issue tenant-scoped SQL/add/flush only and expose no commit/rollback or historical update/delete primitive.

---

### Task 5: Implement Atomic v1 Save And Fingerprint Gate

**Files:**

- Create: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- Create: `apps/api/tests/unit/test_workflow_plan_persistence.py`
- Modify: `apps/api/src/data_intelligence_hub/services/exceptions.py`

- [x] **Step 1: Write failing service tests for new Plan save**

Cover:

- Idempotency-Key and request canonical hashes never expose raw key;
- existing completed replay short-circuits Project status/Catalog recompute;
- active Project required for a new key;
- server recomputes Preview from `preview_input`;
- stale Fingerprint returns `preview_stale` with zero Plan/Version/Scope/QueryTerm/SaveRequest rows;
- v1 saves normalized Scope、association、per-Version QueryTerm and full Preview;
- `resolved`、`partially_resolved` and `held` save;
- Plan name/mode frozen from validated input/server Preview;
- Provider/Actor/browser/LLM/WorkflowRun hooks are never called.

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_persistence.py -q -k 'create or stale or held or raw_key'
```

- [x] **Step 2: Implement the service-owned transaction**

New request order:

1. auth/workspace already resolved by route;
2. canonical scope/key/request hash;
3. completed replay lookup;
4. active Project read;
5. pure Planner build and Fingerprint equality;
6. continue inside the same explicit transaction that began before the first idempotency SELECT;
7. lock Project, recheck active and idempotency;
8. create Plan/Scope/v1/association/QueryTerm/current pointer;
9. create immutable response snapshot;
10. commit once.

The service must enter one explicit `async with session.begin()` before its first database query and keep replay lookup、Project checks、pure recomputation and writes in that transaction. Do not issue SELECTs that trigger `AsyncSession` autobegin and then enter a second transaction. Any failure rolls back everything. Do not call repository commit helpers.

- [x] **Step 3: Map QueryTerm attribution through the Version–Scope association**

Each Phase One QueryTerm Scope key must resolve to one required persisted `matched_scope_id` already associated with the same Version. A missing or colliding key fails closed.

- [x] **Step 4: Turn v1 tests green**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_persistence.py -q -k 'create or stale or held or raw_key'
cd apps/api && uv run ruff check src/data_intelligence_hub/services/workflow_planner/persistence.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_workflow_plan_persistence.py
cd apps/api && uv run mypy src/data_intelligence_hub/services/workflow_planner/persistence.py tests/unit/test_workflow_plan_persistence.py
```

Task 5 evidence (2026-07-13): the missing persistence service produced the expected collection RED. The v1 slice passed `8` behavior tests with Ruff and mypy green. An intermediate `MissingGreenlet` exposed unsafe access to an async-expired `updated_at`; response mapping now uses the transaction's known timestamp. The service clears only a clean auth autobegin, owns one explicit business transaction, recomputes Preview server-side, rejects stale Fingerprints before writes, persists the complete v1 Scope/association/QueryTerm graph and never stores or exposes the raw Idempotency-Key.

---

### Task 6: Implement New Versions, Semantic No-op, Idempotency And Optimistic Concurrency

**Files:**

- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- Modify: `apps/api/tests/unit/test_workflow_plan_persistence.py`

- [x] **Step 1: Add failing version semantics tests**

Cover:

- expected current Version required;
- Project lock then Plan lock order;
- lock-time idempotency recheck;
- current Version mismatch → `version_conflict`, zero business writes;
- flow mode mismatch → `workflow_plan_flow_mode_conflict`;
- same current Fingerprint → new SaveRequest only, `semantic_no_op`, no Plan timestamp change;
- A→B→A creates v3;
- same key/same request replay uses original resource snapshot and returns current attempt `database_write=false`、`plan_changed=false`;
- same key/different request → `idempotency_conflict`;
- final unique race rolls back candidate transaction then replays/conflicts in a new transaction;
- Scope key collision with different semantic payload fails closed.

- [x] **Step 2: Implement version creation inside the same service boundary**

Version number is allocated only while the Plan row is locked. Do not query `max+1` outside the lock. A semantic no-op does not update Plan or create Version/Scope/QueryTerm rows.

- [x] **Step 3: Implement truthful replay boundaries**

The immutable response snapshot preserves original resource content/outcome/status, but each replay overlays:

    database_write=false
    plan_changed=false
    idempotent_replay=true

- [x] **Step 4: Turn all save-service tests green**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_persistence.py -q
```

Task 6 evidence (2026-07-13): the missing Version persistence contract produced the expected RED. The first `18 passed` unit checkpoint was not accepted as final because a disposable PostgreSQL asyncpg probe showed the real unique-violation shape has SQLSTATE `23505` on `orig` and the constraint name on `orig.__cause__`, not `orig.diag`. A targeted `2 failed / 2 passed` RED reproduced the blind spot; after correction the full service gate passed `20` tests, adjacent schema/model/repository regression passed `30`, Ruff/mypy/diff checks passed, and a real asyncpg probe detected the target constraint while rejecting an unrelated one. Lock order, optimistic conflict, mode conflict, semantic no-op, A→B→A=v3, immutable replay snapshot, idempotency conflict and two-transaction final-race recovery are covered.

---

### Task 7: Add Tenant-Safe Reads, History And Pure Structured Compare

**Files:**

- Create: `apps/api/src/data_intelligence_hub/services/workflow_planner/comparison.py`
- Create: `apps/api/tests/unit/test_workflow_plan_comparison.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- Modify: `apps/api/tests/unit/test_workflow_plan_persistence.py`

- [x] **Step 1: Write failing read/history tests**

Cover current Plan detail, Version list/detail, saved Scope list, total/limit/offset, cross-tenant not-found, Version must belong to Plan, and archived Project read access.

- [x] **Step 2: Write failing comparison tests**

Compare must return stable sections for:

- Plan/planning status;
- Scope add/remove/order;
- QueryTerm add/remove/status;
- contract/catalog/policy/template/query versions;
- warnings/blocking issues;
- routes/budget/limits/steps.

JSON key order and set-like ordering must not produce changes. Comparing a Version with itself returns a valid empty structured diff. Missing Version or cross-Plan Version fails closed.

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_comparison.py tests/unit/test_workflow_plan_persistence.py -q -k 'read or list or compare or archived'
```

- [x] **Step 3: Implement pure comparison and read service methods**

Comparison receives frozen snapshots and returns a typed result. It does not access the database or mutate snapshots. Persistence service composes tenant-safe repository reads and the pure comparator.

- [x] **Step 4: Turn focused tests green**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_comparison.py tests/unit/test_workflow_plan_persistence.py -q
```

Task 7 evidence (2026-07-13): collection first failed on the missing `WorkflowVersionNotFoundError` and six read/history callables. The completed tenant-safe services support Plan list/detail, Version list/detail, MonitoringScope list and structured Compare; archived Projects remain readable, full Preview is detail-only, history/Compare use summaries, same-Version Compare is empty, and cross-tenant/cross-Plan resources fail closed. Read entry rejects pending Session state to prevent autoflush from contradicting `database_write=false`. The focused service/comparator gate passed `33` tests with Ruff/format/mypy/diff green.

---

### Task 8: Expose Two Write And Six Read API Endpoints

**Files:**

- Modify: `apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py`
- Create: `apps/api/tests/integration/test_workflow_plan_persistence_routes.py`
- Modify: `apps/api/tests/integration/test_workflow_planner_preview.py`

- [x] **Step 1: Write failing route contract tests**

Endpoints:

```text
POST /api/projects/{project_id}/workflow-plans
POST /api/projects/{project_id}/workflow-plans/{plan_id}/versions
GET  /api/projects/{project_id}/workflow-plans
GET  /api/projects/{project_id}/workflow-plans/{plan_id}
GET  /api/projects/{project_id}/workflow-plans/{plan_id}/versions
GET  /api/projects/{project_id}/workflow-plans/{plan_id}/versions/{version_id}
GET  /api/projects/{project_id}/workflow-plans/{plan_id}/version-compare
GET  /api/projects/{project_id}/monitoring-scopes
```

Register the static `version-compare` route so it cannot be consumed by a dynamic UUID route.

- [x] **Step 2: Lock status, headers and boundary envelopes**

Test:

- new resource/version `201`;
- semantic no-op `200`;
- replay preserves original HTTP status but reports current attempt zero-write;
- handler success and mapped errors include `X-Request-ID`;
- pre-handler Pydantic 422 does not promise that header;
- reads return `database_write=false` and all external/execution flags false.

- [x] **Step 3: Lock error mapping and privacy**

Cover 401, tenant-hidden 404, `project_not_active`, `preview_stale`, `version_conflict`, `idempotency_conflict`, mode conflict, header/body/query 422, Catalog/dependency/persistence 503, topology/internal 500, loc-aware normalizer issues, and absence of raw Idempotency-Key from response/log/database.

- [x] **Step 4: Assert forbidden endpoints do not exist**

No PATCH/DELETE/activate/run/archive route may be registered.

Task 8 RED evidence (2026-07-13): `22` route-contract tests collect; the pre-implementation run is `21 failed / 1 passed`. Every failure is an expected 404 or missing route-table entry for the two write and six read endpoints; the sole green test proves the forbidden mutation/execution routes remain absent. Ruff, strict mypy and diff checks pass, and this RED suite did not access a database.

- [x] **Step 5: Implement minimal route orchestration and turn tests green**

```bash
cd apps/api && uv run pytest tests/integration/test_workflow_plan_persistence_routes.py tests/integration/test_workflow_planner_preview.py -q
cd apps/api && uv run ruff check src/data_intelligence_hub/api/routes/workflow_plans.py tests/integration/test_workflow_plan_persistence_routes.py
cd apps/api && uv run mypy src/data_intelligence_hub/api/routes/workflow_plans.py tests/integration/test_workflow_plan_persistence_routes.py
```

Expected: persistence routes green and Preview remains zero-write.

Task 8 final evidence (2026-07-13): the stable pre-implementation contract was `21 failed / 1 passed`, with every failure caused by the eight missing routes and the forbidden-route test already green. The completed two-write/six-read API plus existing Preview passed `41` tests. Idempotency-Key normalization, dynamic `201/200` replay semantics, X-Request-ID, tenant-hidden 404s, 409/422/500/503 mapping and sanitized logs are covered; no PATCH/DELETE/activate/run/archive endpoint exists. Ruff, route/test format, mypy and diff checks passed. The aggregate backend Planner regression then passed `326` tests with Ruff and split mypy gates green.

---

### Task 9: Prove PostgreSQL Immutability, Atomicity, Concurrency And Migration Lifecycle

**Authorization:** Disposable PostgreSQL 15 only. Never point these commands at the default development database, a shared database, or production.

**Files:**

- Create: `apps/api/tests/postgres/test_workflow_plan_persistence.py`
- Create: `apps/api/tests/postgres/test_workflow_plan_migration.py`
- Create: `scripts/verify-workflow-planner-phase2-migration.sh`
- Modify as required by RED evidence: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- Modify as required by RED evidence: `apps/api/src/data_intelligence_hub/repositories/workflow_plans.py`
- Modify as required by RED evidence: `apps/api/alembic/versions/202606110027_workflow_plan_persistence.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.codex/commands.md`

- [x] **Step 1: Add failing immutable/atomic/concurrency tests**

PostgreSQL-only coverage:

- UPDATE/DELETE rejection for Version、VersionScope、QueryTerm、Scope and SaveRequest;
- service/repository expose no Plan name/flow_mode mutation path; PostgreSQL direct-mutation triggers remain limited to the history rows approved by the specification;
- injected failure after every write phase leaves zero partial rows;
- two sessions save same Plan: one advances, the other conflicts/replays;
- same Scope concurrently converges to one row;
- same Idempotency-Key concurrently produces one durable result;
- current pointer/tenant constraints hold under direct SQL attempts.

- [x] **Step 2: Add a fail-closed disposable migration script**

The script must require:

    TEST_DATABASE_URL=<explicit disposable database>
    ALLOW_DESTRUCTIVE_MIGRATION_TEST=true

It must reject a database name that matches the normal development/production name and never print credentials.

Parse the URL and require hostname `localhost` or `127.0.0.1` plus a database name ending `_workflow_plan_phase2_test`. Reject remote hosts, alternate encoded hosts, URL query overrides and unknown database names even when the allow flag is true. CI must use the same dedicated suffix on its local PostgreSQL service.

- [x] **Step 3: Verify three independent database cases**

1. fresh database → `upgrade head`;
2. 026 database with representative old Project/data → 027, assert old data/schema compatibility;
3. 027 → 026 → 027, assert Phase Two objects disappear/reappear and old data remains.

Also assert one Alembic head/current, trigger/function/constraint presence and complete downgrade cleanup.

Run the new PostgreSQL tests once before fixes and record the expected RED. Apply only the minimum required migration/service/repository corrections, then rerun to GREEN.

- [x] **Step 4: Add an independent PostgreSQL 15 CI job**

Use a PostgreSQL 15 service and an isolated test database. Keep the existing SQLite/full API job. Do not make the public/manual Web real-API job run persistence writes.

Task 9 migration-subset evidence (2026-07-13): the missing guard script produced the expected `9 failed` RED; the completed guard passed `9` tests, and fresh upgrade, representative `026 -> 027`, plus `027 -> 026 -> 027` lifecycle passed `3` tests. The guarded disposable PostgreSQL 15 suite passed `43` tests with one Alembic head at `202606110027`; Ruff/format/mypy, `bash -n`, YAML parse and diff checks passed. CI now has an independent PostgreSQL 15 job, while the manual Web real-API job is unchanged. `shellcheck` and `actionlint` were unavailable locally. Task 9 Step 1 atomicity/concurrency coverage and the final complete Step 5 gate remain pending.

- [x] **Step 5: Run the guarded PostgreSQL gate**

```bash
TEST_DATABASE_URL="${TEST_DATABASE_URL:?disposable PostgreSQL required}" ALLOW_DESTRUCTIVE_MIGRATION_TEST=true bash scripts/verify-workflow-planner-phase2-migration.sh
```

Expected: fresh/upgrade/downgrade/upgrade, constraint, immutability, transaction and concurrency evidence all green. Record database name as disposable without credentials.

Task 9 final evidence (2026-07-13): the new PostgreSQL persistence suite passed `6` tests; combined persistence plus constraints passed `37`; the complete fail-closed guarded PostgreSQL 15 gate passed `49` tests in `44.42s`. Real RED evidence found two service defects before final GREEN: a stale AsyncSession identity-map row after `FOR UPDATE` let both writers allocate v2, and the PostgreSQL updated-at trigger diverged from the response/Save snapshot. Project/Plan lock statements now force `populate_existing`, and write services explicitly refresh the trigger-written timestamp before building immutable output. The final gate covers six-phase rollback, same-Plan one-winner concurrency, Scope convergence, same-key replay/privacy, tenant/current-pointer/history constraints and all three migration lifecycle cases. Ruff/format/mypy passed. This is disposable local PostgreSQL evidence only; production is unchanged.

---

### Task 10: Add Isolated Web Persistence Types, API Transport And Mock Store

**Files:**

- Create: `apps/web/src/types/workflow-plan-persistence.ts`
- Create: `apps/web/src/lib/api/workflow-plan-persistence.ts`
- Create: `apps/web/src/lib/workflow-plan-persistence-mock.ts`
- Create: `apps/web/tests/unit/workflow-plan-persistence-api.test.ts`
- Create: `apps/web/tests/unit/workflow-plan-persistence-mock.test.ts`
- Modify: `apps/web/src/lib/api/client.ts`
- Modify: `apps/web/tests/unit/workflow-plans-api.test.ts`

- [x] **Step 1: Write failing transport/mapping tests**

Cover all eight endpoints, methods, URL params, pagination, snake/camel mapping, compare mapping, required Idempotency-Key on writes only, and write body containing `preview_input` rather than trusted `plan_payload`.

Extend `ApiRequestError` to retain a stable machine code and sanitized details for stale/conflict recovery without leaking arbitrary payloads.

```bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plan-persistence-api.test.ts tests/unit/workflow-plans-api.test.ts
```

- [x] **Step 2: Implement separate persistence contracts and transport**

Do not expand the already-large Phase One type/API files with persistence DTOs. Reuse only `PlanningInput` and `mapPlanningInputToDto()`.

- [x] **Step 3: Write failing deterministic mock-store tests**

Cover v1/v2, semantic no-op, A→B→A=v3, replay/key conflict/version conflict, held save, list/detail/history/compare, and Project isolation.

- [x] **Step 4: Implement mock-only in-memory persistence**

- Active only with `NEXT_PUBLIC_MOCK_API=true`.
- No `localStorage`/`sessionStorage` draft or history.
- Recompute Preview via existing mock Preview builder.
- Provide deterministic reset/seed helpers only for tests.
- Under test-fixture flag seed a stable two-Version asset; normal mock development starts empty.
- Components consume mock API results and never calculate Compare.

- [x] **Step 5: Turn contracts/mock green and typecheck**

```bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plan-persistence-api.test.ts tests/unit/workflow-plan-persistence-mock.test.ts tests/unit/workflow-plans-api.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
```

Task 10 evidence (2026-07-13): missing persistence modules produced the expected collection RED. The completed isolated contracts、eight-endpoint transport、allowlisted/sanitized `ApiRequestError` metadata and deterministic in-memory mock passed the focused three-file gate with `46` tests. Full Web unit regression passed `165` tests; TypeScript no-emit、full Web ESLint and `git diff --check` passed. The mock covers held v1、v2、semantic no-op、A→B→A=v3、immutable idempotent replay、key/version/Fingerprint conflict、Project/Scope isolation and stable two-Version fixture seeding without browser storage. No external call、database write、commit or push occurred in this Web task.

---

### Task 10A: Add Lossless Version Editable Input Contract

Route A amendment approved by the user on 2026-07-13. No database migration is required.

**Files:**

- Modify: `apps/api/src/data_intelligence_hub/schemas/workflow_plan_persistence.py`
- Modify: `apps/api/src/data_intelligence_hub/services/workflow_planner/persistence.py`
- Modify: API persistence schema/service/route tests
- Modify: `apps/web/src/types/workflow-plan-persistence.ts`
- Modify: `apps/web/src/lib/api/workflow-plan-persistence.ts`
- Modify: `apps/web/src/lib/workflow-plan-persistence-mock.ts`
- Modify: Web persistence transport/mock tests

- [x] **Step 1: Write failing backend reconstruction/response tests**

Cover defaults versus Scope overrides、Batch omission of `schedule_intent`、Periodic schedule、collapsed duplicate Scope、Save/current detail/historical detail and immutable idempotent replay.

- [x] **Step 2: Reconstruct `editable_input` from stored Fingerprint input**

Return a validated `PlanningInput` on every full Version response. Generate stable presentation-only `scope_ref` values, preserve Fingerprint semantics, and never expose `fingerprint_payload`.

- [x] **Step 3: Extend isolated Web contracts and deterministic mock**

Map `editable_input -> editableInput`; freeze it per Version in mock state and prove a historical input re-Previews to the same Fingerprint while Planner/Catalog/Policy/Template/Query Compiler/Candidate Fixture dependency versions remain unchanged. Across dependency-version upgrades, preserve canonical input semantics but allow the new Preview Fingerprint to change honestly.

- [x] **Step 4: Turn focused API/Web contracts green**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_persistence_schema.py tests/unit/test_workflow_plan_persistence.py tests/integration/test_workflow_plan_persistence_routes.py -q
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plan-persistence-api.test.ts tests/unit/workflow-plan-persistence-mock.test.ts tests/unit/workflow-plans-api.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
```

Task 10A evidence (2026-07-13): the missing `editable_input` contract produced backend `16 failed / 54 passed` and Web `3 failed` RED evidence. The completed server projector, local Batch serializer, transport mapper and deterministic mock passed root-focused API `75` tests and Web `49` tests; the Planner API aggregation passed `335` tests and full Web unit regression passed `168` tests. Ruff、strict mypy、TypeScript no-emit、full Web ESLint、targeted Prettier and `git diff --check` passed. Independent review found and then closed one P1: frozen Preview semantic body is now rebuilt into a complete Fingerprint payload and compared with the stored payload/hash, while normalized and metadata snapshots also fail closed on divergence. Tampered normalized input and QueryTerm tests prove read failure with zero business-row changes. This task used only in-memory SQLite fixtures; it did not access PostgreSQL、shared/production data、external systems、commit or push.

---

### Task 11: Add Explicit Save To The Existing Four-Step Planner

Pre-implementation contract gate (2026-07-13): the user approved Route A. Task 10A must turn the server-reconstructed `editable_input: PlanningInput` contract green before Task 11 business-code changes begin.

**Files:**

- Create: `apps/web/src/components/workflow-planner/workflow-plan-save-panel.tsx`
- Create: `apps/web/src/components/workflow-planner/use-unsaved-workflow-planner-guard.ts`
- Modify: `apps/web/src/app/automation/planner/page.tsx`
- Modify: `apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx`
- Modify: `apps/web/src/components/workflow-planner/planner-mode-step.tsx`
- Modify: `apps/web/src/lib/workflow-planner.ts`
- Modify: `apps/web/tests/unit/workflow-planner.test.ts`

- [x] **Step 1: Write failing Save-state tests**

Cover:

- Save visible only after accepted, non-stale Preview;
- new Plan requires name;
- Plan context freezes name/mode;
- input/Project/mode change disables Save;
- held warning says save does not unblock/approve/run;
- semantic no-op does not say a new Version was created;
- `preview_stale` preserves input and requires Preview again;
- `version_conflict` refreshes current Plan context and requires Preview again;
- historical hydration keeps two identities separate: `source_version_id` supplies draft content, while `expected_current_version_id` always comes from the Plan's latest current Version;
- loading source v1 while current is v3, re-Previewing and saving creates v4 rather than submitting v1 as the concurrency baseline;
- network retry reuses one logical Idempotency-Key;
- changed input/Preview/current Version discards the old key.

- [x] **Step 2: Add Plan context query and semantic draft hydration**

Use:

    /automation/planner?mode={mode}&project_id={projectId}&plan_id={planId}&source_version_id={versionId}

`source_version_id` is optional and defaults to the current Version. Add a pure projector from the selected Version's server-provided `editable_input` to a semantically equivalent editable draft. It need not reproduce the user's discarded raw draft ordering; with unchanged Planner dependencies, re-Preview preserves the original Fingerprint unless the user edits it, while a dependency-version upgrade may honestly change the Fingerprint without losing the loaded input semantics. Reject a source Version that does not belong to the given Project/Plan. Load Plan detail separately and retain its latest `current_version_id` as the optimistic-concurrency baseline; never use the historical source Version ID as `expected_current_version_id`.

- [x] **Step 3: Add explicit Save panel**

Use `crypto.randomUUID()` as client entropy for a new logical key; never show or persist it. Save success records Plan/current Version IDs. Do not auto-save.

- [x] **Step 4: Add dirty-leave protection without draft persistence**

Dirty means the current semantic draft differs from the last loaded/saved or conflict-refreshed semantic baseline. Guard browser `beforeunload` and ordinary same-origin anchor navigation inside the Planner. Refresh/close must not restore the form. Browser back/forward and programmatic `router.push/replace` remain outside this Planner-local guard and must not be claimed as covered.

- [x] **Step 5: Turn Planner unit tests green**

```bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-planner.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
```

Task 11 evidence (2026-07-13): missing Save/guard modules produced the expected collection RED; a Project-context predicate regression then failed one component test before the visible control and handler were aligned. Route A now hydrates only server-provided `editable_input`, keeps historical source content separate from the Plan's latest concurrency baseline, freezes the exact Preview input, and exposes explicit name-validated Save with immutable existing name/mode, honest held/no-op/idempotent-replay copy, stale/conflict recovery, logical Idempotency-Key reuse, archived read-only behavior and late-response invalidation. Independent review found one P2: after `version_conflict`, the preserved local draft was still compared with the old baseline and could leave without warning. A focused RED reproduced it (`1 failed / 67 passed`); the conflict path now advances only the semantic baseline to the refreshed current Version while preserving the local draft. Root-final gates passed focused Web `68`, full Web unit `184`, TypeScript no-emit, full ESLint, targeted Prettier and a serialized Next production build generating `23/23` pages. Dirty-leave proof is limited to `beforeunload` and ordinary same-origin anchors; browser back/forward and programmatic router navigation are not covered. No browser E2E, database, external system, commit, push or deploy was used in Task 11.

---

### Task 12: Add Saved Plans, Version History And Structured Compare UI

**Files:**

- Create: `apps/web/src/app/automation/plans/page.tsx`
- Create: `apps/web/src/app/automation/projects/[projectId]/plans/[planId]/page.tsx`
- Create: `apps/web/src/components/workflow-planner/saved-workflow-plans-workspace.tsx`
- Create: `apps/web/src/components/workflow-planner/workflow-plan-detail-workspace.tsx`
- Create: `apps/web/src/components/workflow-planner/workflow-plan-version-history.tsx`
- Create: `apps/web/src/components/workflow-planner/workflow-plan-version-compare.tsx`
- Create: `apps/web/tests/unit/workflow-plan-assets.test.ts`
- Modify: `apps/web/src/components/layout/navigation.ts`
- Modify: `apps/web/src/components/dashboard/workflow-planner-entry-cards.tsx`
- Modify: `apps/web/src/lib/project-selection.ts`
- Modify: `apps/web/tests/unit/navigation.test.ts`
- Modify: `apps/web/tests/unit/project-selection.test.ts`

- [x] **Step 1: Write failing list/navigation tests**

Add `已保存计划` under `采集工作流`. Test Project-scoped list, truthful applied-Project status, loading/empty/error/pagination, stale resolve/reject invalidation after Project switch, name/status/version/count/update/creator columns, dynamic detail parent-navigation activation, and no Activate/Run/Schedule/provider action UI.

- [x] **Step 2: Implement Saved Plans page**

Route: `/automation/plans`. Use current Project context and backend/mock pagination only.

- [x] **Step 3: Write failing detail/history/Compare tests**

Cover current full Preview, `Edit in Planner`, Version order/metadata, cumulative server pagination beyond 100 Versions with stable Compare selection, default adjacent Compare, arbitrary directional base/target, same-Version backend empty diff, structured recursive rendering for nested values, insufficient Version count, archived Project read, cross-tenant not-found, Workspace identity consistency, URL-bound Project context truth, late resolve/reject invalidation and no raw JSON diff. A same-Version response with non-empty sections is contradictory and must fail closed. Add a historical restore case where source v1 and current v3 route to Planner and the subsequent save uses expected current v3 to create v4.

- [x] **Step 4: Implement Plan detail and history**

Route: `/automation/projects/{projectId}/plans/{planId}`. Carry the Project ID explicitly so Project-scoped APIs and archived Project read-only deep links do not depend on the active-only Project Selector. The detail surface and global selector status must both name this URL-bound Project context without claiming the top-level preference controls the page. Reuse existing Preview display for the current Version. Load Version history through cumulative, ID-deduplicated server pages so any retained Version can become an explicit Compare endpoint; preserve selected IDs while loading more. Historical Version is read-only; using it as a starting point passes `project_id`、`plan_id` and `source_version_id` to Planner and creates a future Version only after a new Preview.

- [x] **Step 5: Implement Compare as a backend fact view**

Do not compute a diff in React. Render only typed server/mock change sections, including unknown keys and nested `PlannerJsonValue` through a recursive structured view rather than raw JSON. AbortSignal is advisory: list/history/Compare acceptance must also bind a monotonic sequence to the exact Project/Plan/base/target context because mock reads may resolve after abort.

- [x] **Step 6: Turn asset/navigation tests green**

```bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plan-assets.test.ts tests/unit/navigation.test.ts tests/unit/project-selection.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
```

Task 12 evidence (2026-07-13): the initially proposed `.test.tsx` asset suite was not collected because this repo's Vitest config includes only `tests/**/*.test.ts`; after aligning the plan, filename and command, the expected business REDs covered missing assets and then the independent-review gaps. Saved Plans now binds only validated active-Project list responses, while explicit detail URLs remain readable for archived Projects and truthfully identify their URL Project context. Detail/history/Compare bind Project, Plan, Version and Workspace identities; history cumulatively loads 101+ Versions with exact offsets, total-drift checks and late resolve/reject invalidation; Compare preserves both directions, calls the backend for same-Version, rejects contradictory same-Version sections and recursively renders only server facts. Fresh root gates passed focused Task 12 `42` tests, the historical source-v1/current-v3/save-as-v4 chain `1 passed / 67 skipped`, full Web unit `211`, TypeScript no-emit, full ESLint, targeted Prettier and a serialized Next production build generating `24/24` pages. Final independent review found no remaining P0-P2. No browser E2E, database, external system, commit, push or deploy was used in Task 12.

---

### Task 13: Add Mock E2E And Preserve The Real-API Boundary

**Files:**

- Modify: `apps/web/tests/e2e/main-flows.spec.ts`
- Modify: `apps/web/src/lib/workflow-plan-persistence-mock.ts` for fixture-gated save-time stale/conflict injection only
- Modify: `apps/web/tests/unit/workflow-plan-persistence-mock.test.ts` to prove the trigger is one-shot and fixture-only
- Modify: `apps/web/playwright.config.ts` only if required for deterministic fixture reset/port

- [x] **Step 1: Add mock-only end-to-end cases**

Cover:

- held Preview warning and v1 save;
- saved list/detail/history;
- edit→Preview→v2→Compare;
- semantic no-op does not increase history;
- changed input disables Save;
- dirty navigation confirmation;
- stale/conflict preserves input and prevents overwrite;
- desktop 1440 and mobile 375 no unrecoverable overflow;
- forbidden action text/buttons absent.

The save-time stale/conflict cases use reserved terms only inside the existing local mock plus Workflow Planner fixture gates and only for the synthetic-resolved fixture Project. They are testability fixtures, not evidence of real backend concurrency. Normal mock development and real-API paths must remain unchanged.

- [x] **Step 2: Keep network and evidence boundaries explicit**

Use the existing local-only request guard and assert external requests are `[]`. Skip persistence cases in real API mode. Do not add write cases to the manual Web real-API job, whose default base URL may be public.

- [x] **Step 3: Run Web checks serially**

First stop any local Web process using the selected test port. Then run, without concurrent `next build` or dev server:

```bash
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API PLAYWRIGHT_PORT=3114 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web test:e2e
```

Expected: new persistence cases pass in mock mode; real API persistence remains unclaimed and unexecuted.

Task 13 evidence (2026-07-13): the fixture contract followed a fresh RED→GREEN and the focused mock suite passed `9/9`. Serialized acceptance on one stable fresh server passed focused desktop/mobile persistence E2E `6/6` and the full Web mock E2E `64 passed / 12 expected skipped`; the local-only request guard observed `externalRequests=[]`. A real-mode focused command against an unreachable loopback base URL returned `3 skipped` without starting navigation, proving only that persistence E2E remained unexecuted in real mode—not real-API acceptance. Full Web unit regression passed `212`, TypeScript no-emit and full ESLint passed, the production build with both public mock flags unset generated `24/24` pages, and `git diff --check` passed. Reserved stale/conflict inputs remain fixture-only and are not real backend concurrency evidence. Archived-Project browser behavior is not claimed here and retains Task 12 unit/component evidence. No real API/backend/database, external system, commit, push or deploy was used in Task 13.

---

### Task 14: Synchronize Product, API, Architecture And Planning State

**Files:**

- Modify the documentation/planning files listed in Planned File Structure

- [x] **Step 1: Update the stable API contract**

Document all endpoints, required Idempotency-Key, request/response boundaries, pagination/sort, replay/no-op truth, errors, archived reads, and explicit absence of mutation/execution endpoints.

- [x] **Step 2: Update architecture and PRD**

Record Phase One pure Preview vs Phase Two persistence boundary, six-table relation, transaction/lock/idempotency/trigger flow, Save/history/Compare product behavior, and continuing no Activate/Run/provider boundary.

- [x] **Step 3: Preserve Phase One history and add successor pointers**

Do not rewrite Phase One test counts as current Phase Two evidence. Add only a successor pointer and new status boundary where appropriate.

- [x] **Step 4: Synchronize current execution entry points**

Update TODO、`.codex/context-pack.md` and `.kiro/plan/*` to actual state. Update `.codex/ralph-loop.local.md` only if its current overlay conflicts. Never mark locally complete before the full gate passes.

- [x] **Step 5: Search for stale claims**

```bash
rg -n 'phase_2_persistence_authorization=false|Phase 2 persistence remains.*unauthorized|draft -> previewed|planning_status.*partial' docs TODO.md .codex .kiro/plan
```

Expected: only clearly labeled historical facts remain; current docs say Phase Two implementation state accurately.

Task 14 evidence (2026-07-13): stable API contract, architecture, PRD, Phase One design/plan, Phase Two design/plan, TODO, Codex context, Ralph overlay and `.kiro/plan/*` now agree on `phase_2_persistence_in_progress` and `current_batch=phase_2_task_15_full_gate`. The required stale-claim scan found only Phase One historical instructions/evidence, the explicit V2 target lifecycle and valid `planning_status`/Route `partial` terminology; each is labeled by context and does not claim current Phase Two authorization is false. `git diff --check` passed and the index remains empty. This documents local task-level proof only; Task 15 full exit gate remains pending and no external action was performed.

---

### Task 15: Run The Full Local Exit Gate And Stop Before External Actions

**Files:**

- Modify: this plan's checkboxes/frontmatter/evidence section only after commands finish
- Modify current-state docs only with fresh results

- [x] **Step 1: Run focused API persistence and Preview regression**

```bash
cd apps/api && uv run pytest tests/unit/test_workflow_plan_models.py tests/unit/test_workflow_plan_persistence_schema.py tests/unit/test_workflow_plan_persistence.py tests/unit/test_workflow_plan_comparison.py tests/integration/test_workflow_plan_repository.py tests/integration/test_workflow_plan_persistence_routes.py tests/integration/test_workflow_planner_preview.py -q
```

- [x] **Step 2: Run API quality and full suite**

```bash
cd apps/api && uv run ruff check .
cd apps/api && uv run mypy src tests
cd apps/api && uv run pytest
cd apps/api && uv run alembic heads
```

Expected: PostgreSQL-only tests skip without their explicit disposable URL; all normal tests pass; one head remains.

- [x] **Step 3: Run the explicit disposable PostgreSQL 15 gate**

```bash
TEST_DATABASE_URL="${TEST_DATABASE_URL:?disposable PostgreSQL required}" ALLOW_DESTRUCTIVE_MIGRATION_TEST=true bash scripts/verify-workflow-planner-phase2-migration.sh
```

Expected: 026→027→026→027, old-data preservation, constraints, triggers, immutability, atomicity and concurrency pass. Do not substitute the normal development database.

- [x] **Step 4: Run focused and full Web gates**

```bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plans-api.test.ts tests/unit/workflow-plan-persistence-api.test.ts tests/unit/workflow-plan-persistence-mock.test.ts tests/unit/workflow-planner.test.ts tests/unit/workflow-plan-assets.test.ts tests/unit/navigation.test.ts tests/unit/project-selection.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env NEXT_PUBLIC_MOCK_API=false NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 corepack pnpm --dir apps/web build
```

Run the two builds serially. The second command is the production-API build guard and must not inherit `NEXT_PUBLIC_MOCK_API=true`.

- [x] **Step 5: Run mock E2E after build completes**

```bash
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API PLAYWRIGHT_PORT=3114 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web test:e2e
```

Task 15 final evidence (2026-07-13): Step 1 passed `113` tests with one existing deprecation warning. Step 2 initially exposed duplicate top-level test-module names; the scoped `apps/api/pyproject.toml` configuration now uses pytest `--import-mode=importlib` and mypy `explicit_package_bases`, after which the exact quality command passed Ruff, mypy `198`, full pytest `543 passed / 40 skipped / 1 warning`, and Alembic head `202606110027`. Step 3 passed the fail-closed URL guard and authorized disposable PostgreSQL 15 gate (`49 passed`). Step 4 passed focused Web `160`, full Web `212`, TypeScript, ESLint, and serial mock/production-API builds with `24/24` routes. Step 5 first correctly failed before page assertions on a missing managed Chromium headless-shell executable. After explicit user authorization, `corepack pnpm --dir apps/web exec playwright install --only-shell chromium` installed the local test runtime; the original fixture-only E2E command then passed `64` with `12` expected skips in `2.1m`. This is local mock evidence only, not real-API or production acceptance.

- [x] **Step 6: Verify exact diff, boundaries and no staging**

```bash
git diff --check
git diff --cached --name-only
git status --short
rg -n 'activate|/run|WorkflowRun|provider_call=true|actor_run=true|llm_call=true|production_write' apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py apps/web/src/components/workflow-planner apps/web/src/app/automation docs/superpowers/plans/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md
```

Expected: diff check clean; index empty unless a separate exact-file staging authorization exists; forbidden actions appear only in explicit negative-boundary text/tests.

- [x] **Step 7: Record fresh evidence without overclaiming**

Only after all mandatory gates pass may status become:

    phase_2_persistence_locally_complete
    database_write=local_disposable_postgres_only
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    workflow_run_created=false
    execution_authorized=false
    live_send=false
    production unchanged

Record exact counts, skips, warnings, migration DB type, head and commands. Do not describe mock E2E as real API or production acceptance.

- [x] **Step 8: Stop before commit, push, deploy or production database work**

Report the unstaged local result and remaining authorization gates. Do not create a checkpoint commit unless the user explicitly authorizes it after seeing the final evidence.

Post-closeout fact update (2026-07-14): repository `HEAD` is local checkpoint commit `39c07e9baf12ec2ec8a1a21afc4b4feacffc4d12`, and `1e4cc4863c9629e2ff249edc0f7722dafaaf6831` remains its Phase Two implementation baseline ancestor. This closes only the observed local commit gate; it does not retroactively change Task 15's pre-commit evidence or authorize push、PR、merge、deploy、shared/production database work or product execution.

---

## Exit Criteria

Phase Two persistence is locally complete only when:

1. Save accepts only server-recomputed, matching Preview Fingerprints.
2. v1/new Version/no-op/A→B→A and `held` semantics pass.
3. Scope reuse, Version–Scope freeze and QueryTerm snapshots pass PostgreSQL tests.
4. tenant composite constraints, current pointer ownership and history immutability reject direct invalid writes.
5. Idempotency replay/conflict and concurrent writers are deterministic.
6. All read/history/Compare endpoints enforce tenant/Project/Plan boundaries.
7. Phase One Preview stays deterministic and zero-write.
8. Web Save、stale/conflict、dirty guard、Saved Plans、history and Compare pass unit/mock E2E.
9. PostgreSQL 15 fresh/upgrade/downgrade/upgrade gate passes on a disposable database.
10. Product/API/architecture/current-state docs match the implementation.
11. No Activate、Run、Schedule、Provider、WorkflowRun、production or shared-database action occurred.

## Post-Closeout And Future Authorization Gates

- [x] Local exact-file checkpoint commit: `39c07e9baf12ec2ec8a1a21afc4b4feacffc4d12`
- [ ] Push / PR / merge
- [ ] Shared or staging database migration
- [ ] Production rollout strategy: maintenance window or compatibility release
- [ ] Production migration/deploy/read-only acceptance
- [ ] Approval/Activate/Run lifecycle Goal
- [ ] WorkflowRun/scheduler/provider execution Goal

## Plan Review Evidence

Planning-only review completed on 2026-07-13:

    data_migration_review=Critical:0,Important:0
    api_service_review=Critical:0,Important:0
    web_docs_qa_review=Critical:0,Important:0
    task_count=16
    executable_step_count=75
    trailing_whitespace=none
    markdown_code_fences=balanced
    staged_files=none

This evidence validates plan consistency only. It is not implementation、Migration、database write、test execution or product acceptance evidence.

## Execution Evidence

Full local exit-gate evidence (2026-07-13); this is not real API, CI, deployment, shared database or production acceptance:

    implementation_status=phase_2_persistence_locally_complete
    phase_2_plan_review=approved
    phase_2_implementation_authorization=true
    migration_created=true
    migration_applied=disposable_pg_027_then_026_then_027
    database_write=local_disposable_postgres_only
    postgres_15_guarded_gate=49 passed in 44.89s
    backend_tasks_0_9_regression=326 passed, 1 existing passlib warning
    web_task_13_mock_unit=9 passed
    web_task_13_focused_persistence_e2e=6 passed
    web_task_13_full_mock_e2e=64 passed, 12 expected skipped
    web_task_13_real_mode_boundary=3 skipped, real API persistence unexecuted
    web_unit=212 passed
    web_production_api_build=24/24 static pages
    task_15_api_focused=113 passed, 1 warning
    task_15_api_full=543 passed, 40 skipped, 1 warning
    task_15_api_mypy=198 source files
    task_15_web_focused=160 passed
    task_15_web_mock_e2e=64 passed, 12 expected skipped, 2.1m
    task_15_playwright_runtime=managed Chromium headless shell installed locally after explicit authorization
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    workflow_run_created=false
    execution_authorized=false
    live_send=false
    phase_2_checkpoint_commit=39c07e9baf12ec2ec8a1a21afc4b4feacffc4d12
    commit_created=true
    push_performed=false
    deploy_performed=false
    production unchanged
    full_phase_2_exit_gate=passed

Task 15 establishes `phase_2_persistence_locally_complete`. The evidence above remains local task/fixture and disposable PostgreSQL 15 evidence; it is not real API, CI, deployment, shared database, production or Provider acceptance. A local checkpoint commit now exists; push、PR、merge、deploy、shared/production database work and product execution still require separate explicit authorization.

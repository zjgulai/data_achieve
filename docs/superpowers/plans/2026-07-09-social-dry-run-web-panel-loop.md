# Social Dry Run Web Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the overseas social API fixture-only execution dry run in the Automation workbench without enabling live provider calls or production writes.

**Architecture:** Add a dedicated `social-provider` web API module and a small `SocialProviderDryRunPanel` component. The panel calls `POST /api/automation/social-execution-dry-run`, renders stage order, blockers, dataset preview rows, and side-effect flags, then mounts into the existing Automation workbench as a no-write review surface.

**Tech Stack:** Next.js, React, TypeScript, Vitest, existing Workbench UI primitives.

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not add live provider SDK dependencies or browser scraping code.
- Do not add buttons that create Source, Task, TaskRun, Dataset, export, scheduler, provider call, or production writes.
- Use existing Workbench UI primitives and `apiFetch`.
- Preserve unrelated untracked `drafts/analysis/*` files.

---

### Task 1: API Contract Mapper Tests

**Files:**
- Create: `apps/web/tests/unit/social-provider.test.ts`
- Create: `apps/web/src/types/social-provider.ts`
- Create: `apps/web/src/lib/api/social-provider.ts`

**Interfaces:**
- Consumes backend response fields from `social_execution_dry_run.v1`.
- Produces `mapSocialExecutionDryRunResponse(response: SocialExecutionDryRunResponseDto): SocialExecutionDryRun`.

- [x] **Step 1: Write failing mapper tests**

Test that snake_case response fields map to camelCase UI fields and all side-effect flags remain false.

- [x] **Step 2: Run targeted red test**

Run:

```bash
cd apps/web
corepack pnpm vitest run tests/unit/social-provider.test.ts
```

Expected: import error until the new API/type module exists.

### Task 2: API Glue And Fixture Fallback

**Files:**
- Create: `apps/web/src/types/social-provider.ts`
- Create: `apps/web/src/lib/api/social-provider.ts`

- [x] **Step 1: Add TypeScript types**

Define request, response DTO, mapped UI type, stage type, and minimal nested preview types used by the panel.

- [x] **Step 2: Add API function**

Implement:

```ts
export async function runSocialExecutionDryRun(input: SocialExecutionDryRunInput): Promise<SocialExecutionDryRun>
```

It must call `/api/automation/social-execution-dry-run` through `apiFetch`, and in mock mode return a deterministic no-write fixture.

### Task 3: Workbench Panel

**Files:**
- Create: `apps/web/src/components/automation/social-provider-dry-run-panel.tsx`
- Modify: `apps/web/src/components/automation/automation-workbench.tsx`

- [x] **Step 1: Build component**

Add form controls for platform, endpoint, fixture limit, and intended use. The primary action generates a fixture-only review bundle.

- [x] **Step 2: Render evidence**

Render stage order, blockers, side-effect flags, row count, and sample dataset rows. Keep visible copy focused on review state and no-write boundaries.

- [x] **Step 3: Mount component**

Insert the panel near the top of Automation workbench after the workflow rail, before existing collection-entry lanes.

### Task 4: Review Gate

**Files:**
- Update: this plan file

- [x] **Step 1: Run targeted unit test**

```bash
cd apps/web
corepack pnpm vitest run tests/unit/social-provider.test.ts
```

- [x] **Step 2: Run Web lint and tests**

```bash
corepack pnpm lint:web
corepack pnpm test:web
```

- [x] **Step 3: Run Web build**

```bash
cd apps/web
corepack pnpm build
```

- [x] **Step 4: Verify diff hygiene**

```bash
git diff --check
git status --short --branch
```

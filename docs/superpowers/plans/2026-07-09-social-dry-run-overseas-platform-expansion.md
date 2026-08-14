# Social Dry Run Overseas Platform Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the fixture-only overseas social API dry-run workbench from YouTube/Reddit to the full first-batch overseas catalog: YouTube, Reddit, X, Instagram, Threads, TikTok Research, and LinkedIn.

**Architecture:** Reuse the existing backend `social-execution-dry-run` endpoint and frontend workbench panel. Add a small frontend platform config module that mirrors the already-registered backend catalog endpoints, route the panel through that config, and keep request construction in one tested API helper so live/provider/write flags stay false.

**Tech Stack:** Next.js, React, TypeScript, Vitest, existing Workbench UI primitives, existing FastAPI social-provider fixture contract.

---

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not install live provider SDK dependencies.
- Do not add buttons that create Source, Task, TaskRun, Dataset, export, scheduler, provider call, credential read, or production writes.
- Use the existing backend catalog contract and Web workbench primitives; no new UI library.
- Preserve unrelated untracked `drafts/analysis/*` files.

## Task 1: Frontend Catalog Config And Request Contract

**Files:**
- Create: `apps/web/src/lib/social-provider-config.ts`
- Modify: `apps/web/src/types/social-provider.ts`
- Modify: `apps/web/src/lib/api/social-provider.ts`
- Modify: `apps/web/tests/unit/social-provider.test.ts`

- [x] **Step 1: Add failing tests for full overseas platform coverage**

Add assertions that the UI config exposes these platform ids exactly once:

```ts
expect(socialProviderUiConfigs.map((config) => config.platform)).toEqual([
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
]);
```

Add assertions that X maps to `x.v2`, TikTok maps to `tiktok_research`, LinkedIn maps to `linkedin.mcdm`, and each platform has at least one endpoint.

- [x] **Step 2: Add failing tests for dry-run request body flags**

Test `buildSocialExecutionDryRunRequestBody()` with a non-P0 platform such as LinkedIn and assert:

```ts
expect(body.credentials_ready).toBe(false);
expect(body.authorized).toBe(false);
expect(body.include_live_comparison).toBe(false);
expect(body.dataset_save_requested).toBe(false);
expect(body.export_requested).toBe(false);
expect(body.allow_ai_training).toBe(false);
expect(body.max_cost_usd).toBe(0);
expect(body.author_policy).toBe("hashed");
```

- [x] **Step 3: Run targeted red test**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: fail because `social-provider-config` and `buildSocialExecutionDryRunRequestBody` do not exist yet.

- [x] **Step 4: Implement config and request helper**

Create `social-provider-config.ts` with the seven platform labels and endpoint options from `social_provider_catalog_overseas.json`. Extend `SocialProviderPlatform` to include `x`, `instagram`, `threads`, `tiktok`, and `linkedin`. Add `buildSocialExecutionDryRunRequestBody(input)` and call it from `runSocialExecutionDryRun()`.

- [x] **Step 5: Run targeted test to green**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: pass.

## Task 2: Workbench Platform Expansion

**Files:**
- Modify: `apps/web/src/components/automation/social-provider-dry-run-panel.tsx`

- [x] **Step 1: Replace local platform constants with shared config**

Import `socialProviderUiConfigs`, `getDefaultEndpointForPlatform`, and `getSocialProviderUiConfig`. Remove duplicated local `endpointOptions` and `platformLabels`.

- [x] **Step 2: Render all first-batch platforms**

The platform selector must render YouTube, Reddit, X, Instagram, Threads, TikTok Research, and LinkedIn. Changing platform must reset endpoint to that platform's first configured endpoint.

- [x] **Step 3: Keep no-write visible evidence**

Keep these visible facts after dry-run:

```text
provider_call_attempted
credential_read_attempted
task_run_allowed
dataset_write_allowed
production_write_allowed
```

Do not add any live execution controls.

## Task 3: Local Validation And Browser Smoke

**Files:**
- Update: this plan file

- [x] **Step 1: Run unit, lint, and web tests**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
corepack pnpm lint:web
corepack pnpm test:web
```

- [x] **Step 2: Run Web build**

Run:

```bash
corepack pnpm --dir apps/web build
```

- [x] **Step 3: Run fixture-only browser smoke**

Run Next dev with `NEXT_PUBLIC_MOCK_API=true` on an available local port, open `/automation`, select `TikTok Research`, click `生成预案`, and assert no console errors and visible `provider_call_attempted`.

- [x] **Step 4: Verify diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

## Task 4: Review, Commit, And PR Check

**Files:**
- Commit only files modified in this plan.

- [x] **Step 1: Stage exact owned files**

Stage:

```bash
git add -- \
  apps/web/src/types/social-provider.ts \
  apps/web/src/lib/social-provider-config.ts \
  apps/web/src/lib/api/social-provider.ts \
  apps/web/src/components/automation/social-provider-dry-run-panel.tsx \
  apps/web/tests/unit/social-provider.test.ts \
  docs/superpowers/plans/2026-07-09-social-dry-run-overseas-platform-expansion.md
```

- [ ] **Step 2: Commit**

Run:

```bash
git commit -m "feat: expand social dry-run platform options"
```

- [ ] **Step 3: Push and check PR**

Run:

```bash
git push
gh pr checks 11 --watch=false
```

Expected: API and Web quality gates eventually pass; real API E2E remains manual/skipped unless explicitly authorized.

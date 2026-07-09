# Social Adapter Plan Web Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only adapter plan review panel so operators can inspect selected SDK metadata, dependency/import readiness, fixture replay support, and planned operations before any overseas social live gate.

**Architecture:** Reuse the existing FastAPI endpoint `POST /api/automation/social-provider-adapter-plan`. Extend the frontend `social-provider` API module with typed request builders and mappers, return deterministic mock responses in mock mode, and render an `Adapter Plan Gate` card inside `SocialProviderDryRunPanel`.

**Tech Stack:** Next.js, React, TypeScript, Vitest, existing Workbench UI primitives, existing FastAPI social-provider fixture adapter contract.

---

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production unchanged`.
- Do not install provider SDKs, import SDK live clients, read credentials, call platform APIs, or call LLM APIs.
- Do not create Source, Task, TaskRun, Dataset, DatasetVersion, export files, scheduler jobs, or production writes.
- Adapter plan is review-only. Do not add live-run, dependency-install, credential-read, save, export, or authorization buttons.
- Reuse existing UI primitives only: `WorkbenchFact`, `WorkbenchTag`, `WorkbenchMetricPill`.
- Preserve unrelated untracked `drafts/analysis/*` files.

## Task 1: Adapter Plan Contracts

**Files:**
- Modify: `apps/web/src/types/social-provider.ts`
- Modify: `apps/web/src/lib/api/social-provider.ts`
- Modify: `apps/web/tests/unit/social-provider.test.ts`

- [x] **Step 1: Add failing mapper test**

Add a test for:

```ts
mapSocialProviderAdapterPlanResponse(adapterDto).liveClientCreated === false
mapSocialProviderAdapterPlanResponse(adapterDto).providerCallAttempted === false
mapSocialProviderAdapterPlanResponse(adapterDto).plannedOperations[0].providerCall === false
```

- [x] **Step 2: Add failing request helper test**

Add a test for:

```ts
buildSocialProviderAdapterPlanRequestBody({
  platform: "youtube",
  endpoints: ["videos.list"],
  fixtureLimit: 2,
})
```

Assert:

```ts
authorized: false
fixture_limit: 2
credential_reference: undefined
```

- [x] **Step 3: Run targeted red test**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: the new helper and mapper are missing before implementation.

- [x] **Step 4: Implement types and API helpers**

Add DTO/UI types and exported helpers:

```ts
previewSocialProviderAdapterPlan(input): Promise<SocialProviderAdapterPlan>
buildSocialProviderAdapterPlanRequestBody(input): SocialProviderAdapterPlanRequestDto
mapSocialProviderAdapterPlanResponse(response): SocialProviderAdapterPlan
```

Mock mode must return deterministic fixture-only responses with `provider_call_attempted=false`, `credential_read_attempted=false`, and `live_client_created=false`.

- [x] **Step 5: Run targeted test to green**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: pass.

## Task 2: Workbench Adapter Rendering

**Files:**
- Modify: `apps/web/src/components/automation/social-provider-dry-run-panel.tsx`

- [x] **Step 1: Load adapter plan on submit**

On form submit, call:

```ts
previewSocialProviderAdapterPlan({
  platform,
  endpoints: [endpoint],
  fixtureLimit: safeFixtureLimit,
})
```

Keep the existing single loading and single error states.

- [x] **Step 2: Clear adapter plan on platform change**

Reset adapter plan state inside `selectPlatform`.

- [x] **Step 3: Render Adapter Plan Gate**

Render provider id, SDK package, dependency present, adapter ready, fixture replay supported, live client created, provider call attempted, credential read attempted, and production write allowed.

- [x] **Step 4: Render planned operations**

Render up to three operations with operation name, endpoint, mode, provider call, and fixture limit.

- [x] **Step 5: Preserve existing preview chain behavior**

Existing readiness/catalog/dataset/source/approval/dry-run cards remain visible.

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

Run Next dev with `NEXT_PUBLIC_MOCK_API=true`, open `/automation`, select YouTube `videos.list`, click `生成预案`, and assert visible `Adapter Plan Gate`, `google-api-python-client`, `live_client_created`, `provider_call_attempted`, and no page-level horizontal overflow after result render.

- [x] **Step 4: Verify diff hygiene and credential-field scan**

Run:

```bash
git diff --check
rg -n "(?i)(api[_-]?key|secret|token|password|private[_-]?key|bearer|sk-[A-Za-z0-9])" <touched files>
git status --short --branch
```

Expected: no whitespace issues; any matches are credential field labels only, not values.

## Task 4: Commit And Push

**Files:**
- Commit only files modified in this plan.

- [ ] **Step 1: Stage exact owned files**

Stage:

```bash
git add -- \
  apps/web/src/types/social-provider.ts \
  apps/web/src/lib/api/social-provider.ts \
  apps/web/src/components/automation/social-provider-dry-run-panel.tsx \
  apps/web/tests/unit/social-provider.test.ts \
  docs/superpowers/plans/2026-07-10-social-adapter-plan-web-panel.md
```

- [ ] **Step 2: Commit**

Run:

```bash
git commit -m "feat: add social adapter plan panel"
```

- [ ] **Step 3: Push and observe PR**

Run:

```bash
git push
gh pr checks 11 --watch=false
```

Report the observed PR status separately from local validation.

# Social Readiness Web Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only catalog/readiness review surface to the overseas social API workbench so operators can see credential gaps, scope gaps, rate-limit profile, and policy blockers before generating the dry-run bundle.

**Architecture:** Reuse existing backend routes `GET /api/automation/social-provider-catalog` and `POST /api/automation/social-provider-readiness`. Extend the existing frontend `social-provider` API module with typed mappers and mock fixtures, then render readiness and catalog facts inside `SocialProviderDryRunPanel` without adding live execution controls.

**Tech Stack:** Next.js, React, TypeScript, Vitest, existing Workbench UI primitives, existing FastAPI social-provider fixture contract.

---

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not install or import live provider SDK dependencies.
- Do not add buttons for live calls, credential reads, Source/Task creation, TaskRun, Dataset writes, export, scheduler, or production writes.
- Keep catalog/readiness as review-only UI; no `authorized=true` gate in this batch.
- Preserve unrelated untracked `drafts/analysis/*` files.

## Task 1: Catalog And Readiness API Contracts

**Files:**
- Modify: `apps/web/src/types/social-provider.ts`
- Modify: `apps/web/src/lib/api/social-provider.ts`
- Modify: `apps/web/tests/unit/social-provider.test.ts`

- [x] **Step 1: Add failing catalog/readiness mapper tests**

Add tests for:

```ts
mapSocialProviderCatalogResponse(catalogDto).providers[0].sdkSelection.status === "manual_review"
mapSocialProviderReadinessResponse(readinessDto).providerCallAttempted === false
mapSocialProviderReadinessResponse(readinessDto).missingCredentials === ["access_token", "app_secret"]
```

- [x] **Step 2: Add failing request helper test**

Add a test for `buildSocialProviderReadinessRequestBody({ platform: "instagram", endpoints: ["media"] })` and assert:

```ts
expect(body.credentials_ready).toBe(false);
expect(body.dry_run).toBe(true);
expect(body.policy_context).toEqual({
  allow_ai_training: false,
  allow_private_profile_merge: false,
  allow_login_state_collection: false,
  max_retention_hours: 24,
});
```

- [x] **Step 3: Run targeted red test**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: fail because mapper/request helper functions do not exist yet.

- [x] **Step 4: Implement types and API helpers**

Add DTO and UI types for `SocialProviderCatalog`, `SocialProviderReadiness`, and `SocialProviderRateLimitProfile`. Add:

```ts
getSocialProviderCatalog(platform: SocialProviderPlatform): Promise<SocialProviderCatalog>
checkSocialProviderReadiness(input: SocialProviderReadinessInput): Promise<SocialProviderReadiness>
buildSocialProviderReadinessRequestBody(input: SocialProviderReadinessInput): SocialProviderReadinessRequestDto
mapSocialProviderCatalogResponse(response: SocialProviderCatalogResponseDto): SocialProviderCatalog
mapSocialProviderReadinessResponse(response: SocialProviderReadinessResponseDto): SocialProviderReadiness
```

In `mockApiEnabled`, return deterministic no-call fixtures.

- [x] **Step 5: Run targeted test to green**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: pass.

## Task 2: Workbench Readiness Rendering

**Files:**
- Modify: `apps/web/src/components/automation/social-provider-dry-run-panel.tsx`

- [x] **Step 1: Load review bundle**

On form submit, call catalog, readiness, and execution dry-run in sequence for the selected platform/endpoint. Keep a single loading state and a single error state.

- [x] **Step 2: Render readiness facts**

Render:

```text
readiness
provider_call_allowed
provider_call_attempted
missing_credentials
missing_scope
budget_status
```

Use existing `WorkbenchFact`, `WorkbenchMetricPill`, and `WorkbenchTag`; do not add new UI primitives.

- [x] **Step 3: Render catalog facts**

Render provider id, stability, self-host priority, SDK status, auth mode, and up to four policy flags. Avoid raw secret names or any real credential value.

- [x] **Step 4: Preserve dry-run result behavior**

Existing dry-run stages, side-effect facts, and dataset preview remain visible and unchanged after readiness rendering is added.

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

Run Next dev with `NEXT_PUBLIC_MOCK_API=true`, open `/automation`, select Instagram `media`, click `生成预案`, and assert visible `missing_credentials`, `provider_call_attempted`, and no horizontal overflow after result render.

- [x] **Step 4: Verify diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

## Task 4: Commit And Push

**Files:**
- Commit only files modified in this plan.

- [x] **Step 1: Stage exact owned files**

Stage:

```bash
git add -- \
  apps/web/src/types/social-provider.ts \
  apps/web/src/lib/api/social-provider.ts \
  apps/web/src/components/automation/social-provider-dry-run-panel.tsx \
  apps/web/tests/unit/social-provider.test.ts \
  docs/superpowers/plans/2026-07-09-social-readiness-web-panel.md
```

- [x] **Step 2: Commit**

Run:

```bash
git commit -m "feat: add social readiness review panel"
```

- [x] **Step 3: Push and observe PR**

Run:

```bash
git push
gh pr checks 11 --watch=false
```

Report the observed PR status separately from local validation.

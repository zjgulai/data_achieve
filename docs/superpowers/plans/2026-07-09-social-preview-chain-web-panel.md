# Social Preview Chain Web Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only frontend review chain for social dataset preview, source template preview, and task-run approval template so operators can inspect each no-write boundary before any live provider gate.

**Architecture:** Reuse the existing FastAPI endpoints `POST /api/automation/social-dataset-preview`, `POST /api/automation/social-provider-source-template`, and `POST /api/automation/social-task-run-approval-template`. Extend the existing frontend `social-provider` API glue with typed request builders and mappers, keep mock responses deterministic, and render the extra review cards inside `SocialProviderDryRunPanel`.

**Tech Stack:** Next.js, React, TypeScript, Vitest, existing Workbench UI primitives, existing FastAPI social-provider fixture contracts.

---

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not add live provider SDK dependencies.
- Do not read credentials, create Source/Task/TaskRun/Dataset, run collectors, write production data, export files, or call provider/LLM APIs.
- The new UI is review-only. Do not add `authorized=true`, live run, save, export, scheduler, or production controls.
- Use existing UI primitives only: `WorkbenchFact`, `WorkbenchTag`, and `WorkbenchMetricPill`.
- Preserve unrelated untracked `drafts/analysis/*` files.

## Task 1: Preview Chain Contracts

**Files:**
- Modify: `apps/web/src/types/social-provider.ts`
- Modify: `apps/web/src/lib/api/social-provider.ts`
- Modify: `apps/web/tests/unit/social-provider.test.ts`

- [x] **Step 1: Add failing mapper tests**

Add tests for:

```ts
mapSocialDatasetPreviewResponse(datasetDto).datasetWriteAllowed === false
mapSocialProviderSourceTemplateResponse(sourceDto).sourceCreateAllowed === false
mapSocialTaskRunApprovalTemplateResponse(approvalDto).taskRunAllowed === false
```

- [x] **Step 2: Add failing request helper tests**

Add tests for:

```ts
buildSocialDatasetPreviewRequestBody({ platform: "reddit", endpoint: "comments.new", fixtureLimit: 2 })
buildSocialProviderSourceTemplateRequestBody({ platform: "reddit", endpoints: ["comments.new"], sourceName: "Reddit comments fixture source" })
buildSocialTaskRunApprovalTemplateRequestBody({ platform: "reddit", endpoints: ["comments.new"], intendedUse: "fixture-only approval review" })
```

Assert the request bodies keep:

```ts
include_live_comparison: false
authorized: false
save_requested: false
export_requested: false
allow_ai_training: false
dataset_save_requested: false
max_cost_usd: 0
cleanup_policy: "cleanup_after_evidence"
```

- [x] **Step 3: Run targeted red test**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: fail because the new helper and mapper functions do not exist yet.

- [x] **Step 4: Implement types and API helpers**

Add DTO/UI types and exported helpers:

```ts
previewSocialDataset(input): Promise<SocialDatasetPreview>
previewSocialProviderSourceTemplate(input): Promise<SocialProviderSourceTemplate>
previewSocialTaskRunApprovalTemplate(input): Promise<SocialTaskRunApprovalTemplate>
buildSocialDatasetPreviewRequestBody(input): SocialDatasetPreviewRequestDto
buildSocialProviderSourceTemplateRequestBody(input): SocialProviderSourceTemplateRequestDto
buildSocialTaskRunApprovalTemplateRequestBody(input): SocialTaskRunApprovalTemplateRequestDto
mapSocialDatasetPreviewResponse(response): SocialDatasetPreview
mapSocialProviderSourceTemplateResponse(response): SocialProviderSourceTemplate
mapSocialTaskRunApprovalTemplateResponse(response): SocialTaskRunApprovalTemplate
```

Mock mode must return deterministic fixture-only responses with every provider/write flag false.

- [x] **Step 5: Run targeted test to green**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts
```

Expected: pass.

## Task 2: Workbench Chain Rendering

**Files:**
- Modify: `apps/web/src/components/automation/social-provider-dry-run-panel.tsx`

- [x] **Step 1: Load the three preview endpoints**

On form submit, call:

```ts
getSocialProviderCatalog
checkSocialProviderReadiness
previewSocialDataset
previewSocialProviderSourceTemplate
previewSocialTaskRunApprovalTemplate
runSocialExecutionDryRun
```

Keep a single loading state and a single error state.

- [x] **Step 2: Render Dataset Preview Gate**

Render dataset name, row count, source item count, max rows, truncated, dataset write allowed, dataset created, export created, and the first three evidence rows.

- [x] **Step 3: Render Source Template Gate**

Render source type, template strategy, source create allowed, source created, task created, payload present, and blocked reasons.

- [x] **Step 4: Render L4 Approval Packet Gate**

Render task run allowed, dataset write allowed, export allowed, production write allowed, next authorization, and first four required confirmations.

- [x] **Step 5: Preserve existing dry-run behavior**

Existing readiness/catalog cards, metrics, side-effect facts, execution stages, and dataset row preview remain visible.

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

Run Next dev with `NEXT_PUBLIC_MOCK_API=true`, open `/automation`, select Reddit `comments.new`, click `生成预案`, and assert visible `Dataset Preview Gate`, `Source Template Gate`, `L4 Approval Packet Gate`, `provider_call_attempted`, and no horizontal overflow after result render.

- [x] **Step 4: Verify diff hygiene and secret scan**

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

- [x] **Step 1: Stage exact owned files**

Stage:

```bash
git add -- \
  apps/web/src/types/social-provider.ts \
  apps/web/src/lib/api/social-provider.ts \
  apps/web/src/components/automation/social-provider-dry-run-panel.tsx \
  apps/web/tests/unit/social-provider.test.ts \
  docs/superpowers/plans/2026-07-09-social-preview-chain-web-panel.md
```

- [ ] **Step 2: Commit**

Run:

```bash
git commit -m "feat: add social preview chain panel"
```

- [ ] **Step 3: Push and observe PR**

Run:

```bash
git push
gh pr checks 11 --watch=false
```

Report the observed PR status separately from local validation.

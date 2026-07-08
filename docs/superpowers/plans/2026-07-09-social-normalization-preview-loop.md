---
title: Social Normalization Preview Loop Plan
doc_type: implementation_plan
topic: overseas-social-normalization-preview
status: draft
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
private_deploy_boundary: self_hosted_collectors
created: 2026-07-09
updated: 2026-07-09
owner: self
source: codex
---

# Social Normalization Preview Loop Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only normalization preview that turns overseas social raw fixtures into `social_post.v1`, `social_comment.v1`, and `social_voc_item.v1` draft items without provider calls or writes.

**Architecture:** Reuse the existing `social_provider` catalog and `social-raw-preview` fixture generation. Add one glue-code endpoint that normalizes fixture records in memory, returns evidence-bound preview objects, and keeps live/provider/write fields blocked.

**Tech Stack:** FastAPI, Pydantic, pytest, existing `data_intelligence_hub.services.social_provider` helpers. No new third-party dependency is required for this slice because it is internal schema glue over existing fixtures.

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not read YouTube, Reddit, X, Meta, TikTok, LinkedIn, Kimi, or DeepSeek credentials.
- Do not call platform live APIs, TikHub endpoints, GitHub provider APIs, or LLM providers.
- Do not create Source, Task, RawRecord, Dataset, scheduler, production, or external writes.
- Author information remains `hashed` by default; `retained_with_approval` is blocked in preview.
- Use only fixture input from existing catalog-supported endpoints.

---

## Todo List

### Task 1: Contract And Tests

**Files:**
- Modify: `apps/api/tests/unit/test_social_provider_runtime.py`
- Modify: `apps/api/tests/integration/test_social_provider_routes.py`

**Interfaces:**
- Produces expected service function: `prepare_social_normalization_preview(payload: SocialNormalizationPreviewRequest) -> SocialNormalizationPreviewResponse`
- Produces expected route: `POST /api/automation/social-normalization-preview`

- [x] Add unit test for YouTube `videos.list` post + VOC preview with no side effects.
- [x] Add unit test for Reddit `comments.new` comment + VOC preview with raw evidence references.
- [x] Add unit test that `authorized`, `approval_id`, live comparison, and retained authors are blocked.
- [x] Add integration test for authenticated route response.
- [x] Run targeted tests and confirm they fail before implementation.

### Task 2: Schema And Service

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/social_provider.py`
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`

**Interfaces:**
- Add `SocialNormalizationPreviewRequest`
- Add `SocialNormalizedPreviewItem`
- Add `SocialNormalizationPreviewResponse`
- Add `prepare_social_normalization_preview`

- [x] Add request/response schemas with explicit no-call/no-write defaults.
- [x] Reuse `prepare_social_raw_preview` to build fixture raw records.
- [x] Normalize supported post endpoints into `social_post.v1`.
- [x] Normalize comment endpoints into `social_comment.v1`.
- [x] Add optional `social_voc_item.v1` preview items with `raw_record_id` and `evidence_ref`.
- [x] Block live/provider/write/retained-author fields.

### Task 3: Route And Documentation

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/social_provider.py`
- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/workflows/workflow-social-api-youtube-reddit-phase2-runbook-draft-20260708.md`

**Interfaces:**
- Route: `POST /api/automation/social-normalization-preview`

- [x] Wire authenticated FastAPI route.
- [x] Document request, response invariants, and blocked fields.
- [x] Update the Phase 2 runbook sequence after raw preview and before source template.

### Task 4: Review And Compound

**Files:**
- Validate touched files only plus social provider tests.

- [x] Run `ruff format` on touched Python files.
- [x] Run `ruff check` on touched Python files.
- [x] Run targeted `mypy` on touched Python files.
- [x] Run scoped pytest for social provider runtime/routes.
- [x] Run `py_compile`, `uv lock --check`, and `git diff --check`.
- [ ] Commit and push the branch, then re-check PR #11 CI status.

## Review Notes

- This slice intentionally does not install or invoke `google-api-python-client`, `asyncpraw`, or any browser collector.
- Open-source SDK reuse remains selected at the adapter metadata layer; normalization preview is project-specific glue code over local fixtures.
- The next slice after this should be either a no-write TaskRun authorization packet or a fixture-only Dataset draft preview, not a live provider adapter.

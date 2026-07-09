---
title: Social Dataset Preview Loop Plan
doc_type: implementation_plan
topic: overseas-social-dataset-preview
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

# Social Dataset Preview Loop Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only social dataset preview that turns normalized overseas social preview items into reviewable dataset rows without creating Dataset, DatasetVersion, export files, provider calls, or production writes.

**Architecture:** Reuse the existing `social-normalization-preview` service and build a thin dataset-row projection over its `social_voc_item.v1` evidence. The endpoint returns an in-memory dataset draft with row counts, schema metadata, and blocker fields; it deliberately does not touch Dataset ORM services or export jobs.

**Tech Stack:** FastAPI, Pydantic, pytest, existing `data_intelligence_hub.services.social_provider` helpers. No third-party SDK is needed because this slice is glue code over local fixtures.

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not read YouTube, Reddit, X, Meta, TikTok, LinkedIn, Kimi, or DeepSeek credentials.
- Do not call platform live APIs, TikHub endpoints, GitHub provider APIs, or LLM providers.
- Do not create Source, Task, RawRecord, EntitySnapshot, Dataset, DatasetVersion, DatasetExportJob, scheduler, production, or external writes.
- Dataset preview rows must carry `raw_record_id`, `evidence_ref`, and the source normalized item ID.
- Author information remains `hashed` or `dropped`; `retained_with_approval` is blocked in preview.
- Post-push PR/CI observation is reported in the final response, not tracked as a checked item in this committed plan file.

---

## Todo List

### Task 1: Contract And Tests

**Files:**
- Modify: `apps/api/tests/unit/test_social_provider_runtime.py`
- Modify: `apps/api/tests/integration/test_social_provider_routes.py`

**Interfaces:**
- Produces expected service function: `prepare_social_dataset_preview(payload: SocialDatasetPreviewRequest) -> SocialDatasetPreviewResponse`
- Produces expected route: `POST /api/automation/social-dataset-preview`

- [x] Add unit test for Reddit `comments.new` dataset preview rows with raw evidence references.
- [x] Add unit test for YouTube `videos.list` max row limiting and no-write flags.
- [x] Add unit test that save/export/live/retained-author fields are blocked.
- [x] Add integration test for authenticated route response.
- [x] Run targeted tests and confirm they fail before implementation.

### Task 2: Schema And Service

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/social_provider.py`
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`

**Interfaces:**
- Add `SocialDatasetPreviewRequest`
- Add `SocialDatasetPreviewRow`
- Add `SocialDatasetPreviewResponse`
- Add `prepare_social_dataset_preview`

- [x] Add request/row/response schemas with explicit no-call/no-write defaults.
- [x] Reuse `prepare_social_normalization_preview` with `include_voc=true`.
- [x] Convert `social_voc_item.v1` preview items into `social_voc_dataset.v1` rows.
- [x] Enforce `max_rows` without mutating source fixture data.
- [x] Block save/export/live/retained-author fields with explicit blocker strings.

### Task 3: Route And Documentation

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/social_provider.py`
- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/workflows/workflow-social-api-youtube-reddit-phase2-runbook-draft-20260708.md`

**Interfaces:**
- Route: `POST /api/automation/social-dataset-preview`

- [x] Wire authenticated FastAPI route.
- [x] Document request, response invariants, and blocked fields.
- [x] Update the Phase 2 runbook sequence after normalization preview and before source template.

### Task 4: Local Review Gates

**Files:**
- Validate touched files only plus social provider tests.

- [x] Run `ruff format` on touched Python files.
- [x] Run `ruff check` on touched Python files.
- [x] Run targeted `mypy` on touched Python files.
- [x] Run scoped pytest for social provider runtime/routes.
- [x] Run full local API gate: ruff, mypy, pytest.
- [x] Run `py_compile`, `uv lock --check`, secret scan, and `git diff --check`.

## Review Notes

- This endpoint is a dataset preview only; it is not a DatasetVersion save path.
- The later live-capable path still needs a separate L4 authorization packet covering Source/Task/TaskRun, Dataset save, retention, export, and cleanup.
- Mature provider SDK reuse remains at adapter metadata/dependency gate layers; this dataset slice intentionally adds only internal projection glue.

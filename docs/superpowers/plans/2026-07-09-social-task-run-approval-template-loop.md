---
title: Social Task Run Approval Template Loop Plan
doc_type: implementation_plan
topic: overseas-social-task-run-approval-template
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

# Social Task Run Approval Template Loop Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a no-write approval packet endpoint for future overseas social Source/Task/TaskRun/Dataset execution, without creating resources or calling providers.

**Architecture:** Reuse the existing social provider catalog validation and prior fixture preview boundaries. The new endpoint returns a structured L4 approval packet plus blockers and required confirmations; it does not call Source/Task services, collector services, provider SDKs, or credential resolvers.

**Tech Stack:** FastAPI, Pydantic, pytest, existing `data_intelligence_hub.services.social_provider` helpers. No external provider SDK is used in this slice.

## Global Constraints

- Preserve `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, and `production unchanged`.
- Do not read YouTube, Reddit, X, Meta, TikTok, LinkedIn, Kimi, or DeepSeek credentials.
- Do not call platform live APIs, TikHub endpoints, GitHub provider APIs, or LLM providers.
- Do not create Source, Task, TaskRun, RawRecord, EntitySnapshot, Dataset, DatasetVersion, DatasetExportJob, scheduler, production, or external writes.
- The approval packet must include scope, budget, retention, credential reference, dataset/export intent, cleanup policy, and `allow_ai_training=false`.
- Post-push PR/CI observation is reported in the final response, not tracked as a checked item in this committed plan file.

---

## Todo List

### Task 1: Contract And Tests

**Files:**
- Modify: `apps/api/tests/unit/test_social_provider_runtime.py`
- Modify: `apps/api/tests/integration/test_social_provider_routes.py`

**Interfaces:**
- Produces expected service function: `prepare_social_task_run_approval_template(payload: SocialTaskRunApprovalTemplateRequest) -> SocialTaskRunApprovalTemplateResponse`
- Produces expected route: `POST /api/automation/social-task-run-approval-template`

- [x] Add unit test for Reddit approval packet with no write/no provider invariants.
- [x] Add unit test that unknown endpoints and missing credential reference return blockers.
- [x] Add unit test that `authorized`, `approval_id`, AI training, dataset save, and export requests are recorded but still not executed.
- [x] Add integration test for authenticated route response.
- [x] Run targeted tests and confirm they fail before implementation.

### Task 2: Schema And Service

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/social_provider.py`
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`

**Interfaces:**
- Add `SocialTaskRunApprovalTemplateRequest`
- Add `SocialTaskRunApprovalTemplateResponse`
- Add `prepare_social_task_run_approval_template`

- [x] Add request/response schemas with explicit no-call/no-write defaults.
- [x] Validate platform and endpoint scope through catalog provider metadata.
- [x] Build `social_task_run_l4_approval_packet.v1` with source/task/run/dataset/export gates.
- [x] Include required confirmations for owner review.
- [x] Preserve all execution flags as false even when request includes `authorized=true`.

### Task 3: Route And Documentation

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/social_provider.py`
- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/workflows/workflow-social-api-youtube-reddit-phase2-runbook-draft-20260708.md`

**Interfaces:**
- Route: `POST /api/automation/social-task-run-approval-template`

- [x] Wire authenticated FastAPI route.
- [x] Document request, response invariants, and blocker fields.
- [x] Update the Phase 2 runbook sequence after dataset preview and before live/dependency gates.

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

- This endpoint is an authorization template only; it is not a task run gate.
- Any later implementation that creates Source/Task/TaskRun/Dataset must use a separate explicit L4 request with owner approval and cleanup/retention policy.
- Mature provider SDK reuse remains at adapter metadata/dependency gate layers; this slice only creates the approval packet contract.

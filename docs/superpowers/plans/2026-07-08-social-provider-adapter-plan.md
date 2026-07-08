---
title: Social Provider Adapter Plan Implementation Plan
doc_type: implementation_plan
topic: overseas-social-provider-adapter-plan
status: draft
evidence_level: L1-public-or-runtime
provider_call: false
production_boundary: production unchanged
private_deploy_boundary: self_hosted_collectors
created: 2026-07-08
updated: 2026-07-08
owner: self
source: codex
---

# Social Provider Adapter Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only overseas social provider adapter planning API that confirms selected mature SDKs and local dependency availability without reading credentials, constructing live clients, or calling providers.

**Architecture:** Reuse the existing `social_provider` catalog/readiness/gate service and add one glue-code endpoint, `POST /api/automation/social-provider-adapter-plan`. The service maps catalog providers to selected SDK metadata and adapter module names, checks dependency presence with `importlib.util.find_spec`, and returns planned fixture operations only.

**Tech Stack:** FastAPI, Pydantic, pytest, `google-api-python-client` for later YouTube live adapter selection, `asyncpraw` for later Reddit live adapter selection.

## Global Constraints

- Keep `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production unchanged`.
- Do not instantiate `googleapiclient` or `asyncpraw` clients in this phase.
- Only inspect optional dependency presence by import name; do not read env vars or secret manager values.
- Use mature SDK metadata from the catalog: `google-api-python-client` for YouTube and `asyncpraw` for Reddit.
- Preserve unrelated untracked drafts and do not stage or commit unless separately asked.

---

### Task 1: Adapter Plan Contract

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/social_provider.py`
- Test: `apps/api/tests/unit/test_social_provider_runtime.py`

**Interfaces:**
- Produces: `SocialProviderAdapterPlanRequest`
- Produces: `SocialProviderAdapterPlanResponse`

- [x] **Step 1: Write the failing tests**

Add tests that call `prepare_social_provider_adapter_plan(...)` and assert:

```python
assert plan.provider_call_allowed is False
assert plan.provider_call_attempted is False
assert plan.credential_read_attempted is False
assert plan.live_client_created is False
```

- [x] **Step 2: Add schema models**

Add request/response models with fields for platform, provider, endpoints, mode, SDK selection, dependency presence, blocked reasons, and planned fixture operations.

### Task 2: Adapter Plan Service

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`
- Test: `apps/api/tests/unit/test_social_provider_runtime.py`

**Interfaces:**
- Consumes: `SocialProviderAdapterPlanRequest`
- Produces: `prepare_social_provider_adapter_plan(payload) -> SocialProviderAdapterPlanResponse`

- [x] **Step 1: Check dependency presence**

Use `importlib.util.find_spec(import_name) is not None`, not a live SDK import or client construction.

- [x] **Step 2: Build fixture operations**

For each known endpoint, return operation metadata with `request_mode=fixture_replay` and `provider_call=false`.

- [x] **Step 3: Block live/credential escalation**

If `mode=live_dry_run`, `authorized=true`, or `credential_reference` is present, return explicit blockers and keep all side-effect flags false.

### Task 3: API Route

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/api/routes/social_provider.py`
- Test: `apps/api/tests/integration/test_social_provider_routes.py`

**Interfaces:**
- Produces: `POST /api/automation/social-provider-adapter-plan`

- [x] **Step 1: Register route**

Import schema/service objects and wire the route under the existing authenticated automation router.

- [x] **Step 2: Add integration coverage**

Authenticate through the existing test helper, call the route, and assert no provider call, no credential read, and at least one planned operation for a valid endpoint.

### Task 4: Docs And Acceptance

**Files:**
- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/workflows/workflow-social-api-youtube-reddit-phase2-runbook-draft-20260708.md`

**Interfaces:**
- Produces: API contract section and runbook step for adapter planning.

- [x] **Step 1: Document request/response invariants**

Add the adapter-plan request shape and invariant response flags.

- [x] **Step 2: Run verification**

Run format, lint, compile, pytest, lock check, and `git diff --check`.

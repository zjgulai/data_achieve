---
title: Social Provider Fixture Adapter Shells Implementation Plan
doc_type: implementation_plan
topic: overseas-social-provider-fixture-adapters
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

# Social Provider Fixture Adapter Shells Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace string-only overseas adapter planning with real fixture adapter modules for YouTube and Reddit while still blocking live provider calls.

**Architecture:** Add focused modules under `data_intelligence_hub.social_api` so the service can dynamically load local adapter metadata and fixture operation builders. The modules expose stable glue-code functions only; they do not import or construct `google-api-python-client` or `asyncpraw` clients.

**Tech Stack:** FastAPI, Pydantic, pytest, importlib, selected mature SDK metadata from [google-api-python-client](https://github.com/googleapis/google-api-python-client) and [asyncpraw](https://github.com/praw-dev/asyncpraw).

## Global Constraints

- Keep `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production unchanged`.
- Do not read `YOUTUBE_API_KEY`, Reddit OAuth secrets, env vars, or secret manager values.
- Do not instantiate SDK live clients or call platform APIs.
- Reuse mature SDKs only as catalog metadata and optional dependency choices; this task writes glue code only.
- Stage only owned social-provider files; preserve unrelated untracked drafts.

---

### Task 1: Shared Adapter Contract

**Files:**
- Create: `apps/api/src/data_intelligence_hub/social_api/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/social_api/contracts.py`
- Test: `apps/api/tests/unit/test_social_provider_adapters.py`

**Interfaces:**
- Produces: `SocialAdapterMetadata`
- Produces: `build_fixture_operations(provider_id, endpoints, fixture_limit, sdk_package)`

- [x] **Step 1: Write failing test**

```python
from data_intelligence_hub.social_api.contracts import build_fixture_operations

def test_build_fixture_operations_uses_fixture_mode():
    operations = build_fixture_operations(
        provider_id="youtube.v3",
        endpoints=["videos.list"],
        fixture_limit=2,
        sdk_package="google-api-python-client",
    )
    assert operations[0]["provider_call"] is False
```

- [x] **Step 2: Implement minimal contract**

Create a dataclass for metadata and a helper that returns deterministic fixture operation dictionaries.

### Task 2: YouTube And Reddit Adapter Modules

**Files:**
- Create: `apps/api/src/data_intelligence_hub/social_api/youtube/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/social_api/youtube/google_api_client.py`
- Create: `apps/api/src/data_intelligence_hub/social_api/reddit/__init__.py`
- Create: `apps/api/src/data_intelligence_hub/social_api/reddit/asyncpraw.py`
- Test: `apps/api/tests/unit/test_social_provider_adapters.py`

**Interfaces:**
- Produces: `adapter_metadata() -> SocialAdapterMetadata`
- Produces: `plan_fixture_operations(...) -> list[dict[str, object]]`

- [x] **Step 1: Write failing module tests**

Assert YouTube metadata returns `sdk_package="google-api-python-client"` and Reddit metadata returns `sdk_package="asyncpraw"`.

- [x] **Step 2: Implement modules**

Each module calls the shared contract helper and sets `supports_live_client=false` for this phase.

### Task 3: Service Integration

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`
- Test: `apps/api/tests/unit/test_social_provider_runtime.py`
- Test: `apps/api/tests/integration/test_social_provider_routes.py`

**Interfaces:**
- Consumes: `adapter_metadata()`
- Consumes: `plan_fixture_operations(...)`
- Preserves: `prepare_social_provider_adapter_plan(...)`

- [x] **Step 1: Replace static planned operation helper**

Load local adapter module by import path and call `plan_fixture_operations` for known endpoints.

- [x] **Step 2: Keep side-effect flags false**

Assert no credential read, no live client creation, and no provider call after service integration.

### Task 4: Docs, Verification, And Atomic Commit

**Files:**
- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/workflows/workflow-social-api-youtube-reddit-phase2-runbook-draft-20260708.md`
- Stage: explicit file list only

**Interfaces:**
- Produces: documented local adapter module contract
- Produces: one atomic commit if all checks pass

- [x] **Step 1: Update docs**

Document the module import path and no-live-client invariants.

- [x] **Step 2: Verify**

Run ruff format/check, py_compile, targeted pytest, `uv lock --check`, `git diff --check`, and cached diff checks before commit.

- [x] **Step 3: Commit owned files only**

Use explicit `git add` paths; do not stage unrelated `drafts/analysis/*`.

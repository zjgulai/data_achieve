# Social Execution Dry Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fixture-only execution dry-run endpoint that composes existing overseas social provider gates into one reviewable no-write plan.

**Architecture:** Reuse the existing `social_provider` service functions instead of creating a new runtime. The endpoint returns a `social_execution_dry_run.v1` packet with ordered stage summaries and side-effect flags fixed to false.

**Tech Stack:** FastAPI, Pydantic, pytest, ruff, mypy.

## Global Constraints

- `provider_call=false`
- `production unchanged`
- `credential_read_attempted=false`
- Do not create Source, Task, TaskRun, RawRecord, Dataset, DatasetVersion, DatasetExportJob, scheduler, production, or external writes.
- Do not read `.env` or credential files.
- Do not install optional live SDK dependencies.
- Preserve unrelated untracked `drafts/analysis/*` files.

---

### Task 1: Red Tests For Fixture Execution Dry Run

**Files:**
- Modify: `apps/api/tests/unit/test_social_provider_runtime.py`
- Modify: `apps/api/tests/integration/test_social_provider_routes.py`

**Interfaces:**
- Consumes: `SocialExecutionDryRunRequest`
- Produces expected service function: `prepare_social_execution_dry_run(payload: SocialExecutionDryRunRequest) -> SocialExecutionDryRunResponse`
- Produces expected route: `POST /api/automation/social-execution-dry-run`

- [x] **Step 1: Write failing unit tests**

Add tests for:

- Reddit comments fixture dry-run returns stage order: `readiness`, `raw_preview`, `normalization_preview`, `dataset_preview`, `source_template`, `task_run_approval_template`.
- Unknown endpoint returns blockers and no rows or operation execution.
- Live-like fields are recorded as blockers and side-effect flags stay false.

- [x] **Step 2: Write failing integration test**

Add route test for authenticated `POST /api/automation/social-execution-dry-run`.

- [x] **Step 3: Run red tests**

Run:

```bash
cd apps/api
/tmp/data-scrapy-api-venv-20260709/bin/python -m pytest tests/unit/test_social_provider_runtime.py::test_social_execution_dry_run_reddit_fixture_bundle_no_write tests/integration/test_social_provider_routes.py::test_social_execution_dry_run_route_returns_fixture_bundle -q
```

Expected: collection or import error because the new schema/service/route does not exist yet.

### Task 2: Schema, Service, Route

**Files:**
- Modify: `apps/api/src/data_intelligence_hub/schemas/social_provider.py`
- Modify: `apps/api/src/data_intelligence_hub/services/social_provider.py`
- Modify: `apps/api/src/data_intelligence_hub/api/routes/social_provider.py`

**Interfaces:**
- Request fields: `platform`, `endpoint`, `provider_id`, `fixture_limit`, `dataset_name`, `source_name`, `task_name`, `intended_use`, `credential_reference`, `authorized`, `approval_id`, `include_live_comparison`, `dataset_save_requested`, `export_requested`, `allow_ai_training`, `max_requests`, `max_items`, `max_rows`, `max_cost_usd`, `retention_hours`, `author_policy`.
- Response fields: `schema_version`, `execution_plan`, component previews, side-effect flags, `blocked_reasons`, `next_required_authorization`.

- [x] **Step 1: Add Pydantic models**

Add `SocialExecutionDryRunRequest`, `SocialExecutionDryRunStage`, and `SocialExecutionDryRunResponse`.

- [x] **Step 2: Add service orchestration**

Implement `prepare_social_execution_dry_run` by calling existing readiness, raw preview, normalization preview, dataset preview, source template, and task-run approval template functions. It must not call live provider clients or DB services.

- [x] **Step 3: Add route**

Add authenticated route:

```http
POST /api/automation/social-execution-dry-run
```

### Task 3: Docs And Runbook

**Files:**
- Modify: `docs/api/api-contract-social-api-overseas-provider-catalog-draft-20260708.md`
- Modify: `docs/workflows/workflow-social-api-youtube-reddit-phase2-runbook-draft-20260708.md`

- [x] **Step 1: Document API contract**

Add section `4.9 API 合同补充：social-execution-dry-run`.

- [x] **Step 2: Insert runbook step**

Insert the dry-run bundle after TaskRun approval template and before live/dependency gates.

### Task 4: Review Gate And Compound

**Files:**
- Update: this plan file

- [x] **Step 1: Run targeted tests**

```bash
cd apps/api
/tmp/data-scrapy-api-venv-20260709/bin/python -m pytest tests/unit/test_social_provider_runtime.py tests/integration/test_social_provider_routes.py -q
```

- [x] **Step 2: Run format/lint/type gates**

```bash
cd apps/api
/tmp/data-scrapy-api-venv-20260709/bin/python -m ruff format src/data_intelligence_hub/services/social_provider.py src/data_intelligence_hub/schemas/social_provider.py src/data_intelligence_hub/api/routes/social_provider.py tests/unit/test_social_provider_runtime.py tests/integration/test_social_provider_routes.py
/tmp/data-scrapy-api-venv-20260709/bin/python -m ruff check src/data_intelligence_hub/services/social_provider.py src/data_intelligence_hub/schemas/social_provider.py src/data_intelligence_hub/api/routes/social_provider.py tests/unit/test_social_provider_runtime.py tests/integration/test_social_provider_routes.py
/tmp/data-scrapy-api-venv-20260709/bin/python -m mypy src/data_intelligence_hub/services/social_provider.py src/data_intelligence_hub/schemas/social_provider.py src/data_intelligence_hub/api/routes/social_provider.py tests/unit/test_social_provider_runtime.py tests/integration/test_social_provider_routes.py
```

- [x] **Step 3: Run full API gate**

```bash
cd apps/api
/tmp/data-scrapy-api-venv-20260709/bin/python -m ruff check .
/tmp/data-scrapy-api-venv-20260709/bin/python -m mypy src tests
/tmp/data-scrapy-api-venv-20260709/bin/python -m pytest -q
/tmp/data-scrapy-api-venv-20260709/bin/uv lock --check
```

- [x] **Step 4: Verify diff hygiene**

```bash
git diff --check
git status --short --branch
```

- [x] **Step 5: Commit and push**

Stage only owned files from this plan, then commit:

```bash
git commit -m "feat: add social execution dry run"
git push
```

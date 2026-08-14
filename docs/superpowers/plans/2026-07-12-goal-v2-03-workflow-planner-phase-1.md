---
title: GOAL-V2-03 Workflow Planner Phase 1 Implementation Plan
doc_type: implementation_plan
module: workflow-planner
topic: goal-v2-03-workflow-planner-phase-1
status: locally_complete
review_status: local_gates_passed
created: 2026-07-12
updated: 2026-07-13
owner: self
source: human+ai
spec: ../specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md
depends_on: 2026-07-11-goal-v2-02-capability-matrix-navigation.md
checkpoint_required: true
provider_call: false
actor_run: false
llm_call: false
database_migration: false
production_boundary: production unchanged
goal_execution: phase_1_locally_complete
---

# GOAL-V2-03 Workflow Planner Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use - [ ] checkbox syntax for tracking.

**Goal:** Deliver a write-free, deterministic MonitoringScope and WorkflowPlan Preview vertical slice for periodic monitoring and batch research, with honest held behavior against the canonical candidate-only Catalog and synthetic verified/partial route proof in tests.

**Architecture:** Normalize both user flows into one PlanningInput, compile deterministic query and step contracts, resolve each platform/resource/operation against atomic Capability Assertions, and fingerprint the semantic plan. Expose one authenticated Project-scoped Preview API and one dual-mode Web planner; stage-one responses never persist, activate, schedule, or execute anything.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLAlchemy async read path, pytest, ruff, mypy, Next.js 15, React 19, TypeScript 5.7, Vitest, Playwright, existing Tailwind and Workbench primitives.

**Current completion state (2026-07-13):** Tasks 0-13 的 mandatory Phase 1 steps 和 fresh API/Web/scope/no-migration exit gates 已完成；本计划保持 `phase_1_locally_complete` 的历史基线。所有 optional commit steps 保持未勾选。后继 Phase Two persistence/versioning 已单独获准本地实施，当前为 `phase_2_persistence_in_progress`；该状态不回写或重算本计划的 Phase One 证据，且没有 stage、commit、push、deploy 或生产验收。

## Global Constraints

- Source specification: docs/superpowers/specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md.
- GOAL-V2-02 is a hard dependency and is still unstaged/uncommitted at plan-writing time.
- Do not begin Task 1 until Task 0 has produced an explicitly authorized GOAL-V2-02 checkpoint or the user has approved an equivalent clean isolation method.
- Canonical runtime truth remains apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json.
- Current canonical counts are 7 Implementations and 35 candidate Assertions; do not promote or rewrite them.
- Resolver input is atomic CapabilityAssertion data, never the 42-cell matrix summary.
- Keep provider_call=false, actor_run=false, browser_run=false, llm_call=false, credential_read_status=not_read, database_write=false, migration_applied=false, workflow_run_created=false, execution_authorized=false, and production unchanged.
- Do not add SQLAlchemy models, repositories, Alembic revisions, database seed code, Provider clients, SDK dependencies, LLM clients, browser calls, TaskRun, Dataset, Alert, VOC, Brief, scheduler, or delivery code.
- Do not read .env or credential files and do not accept readiness or Secret data from the HTTP request.
- Product Preview may derive auth_readiness=not_required only when required_credentials is empty. Credential-requiring implementations remain not_checked on the product path.
- Synthetic verified/partial Assertions and ready snapshots belong only in tests or an explicitly test-only Web fixture mode.
- Request body must reject project_id, scope_key, readiness snapshots, and every unknown field with 422.
- Preview endpoint is POST /api/projects/{project_id}/workflow-plans/preview.
- A 200 response with planning_status=held is a valid business result, not an API error.
- The no-LLM Fixture Preview target is p95 below 3 seconds and must record fresh local evidence.
- Reuse the existing same-tab event name data-intelligence-hub:project-selection; do not introduce a renamed duplicate event.
- Do not add npm, pnpm, uv, or Python dependencies.
- Preserve unrelated drafts, output/, ref/, tmp/, and user changes.
- Never use git add .; stage only an exact allowlist after explicit commit authorization.
- Commits, push, PR, merge, deploy, production smoke, database migration, Provider calls, and live execution require separate user authorization.
- If commit authorization is absent after implementation starts, finish each task with verified changes unstaged and report the exact paths.
- Run commands from the repository root unless a step explicitly begins with cd apps/api; treat every command block as a fresh shell.

---

## Scope Check

This plan covers one vertical product slice with one exit gate:

1. Backend contracts, normalization, query compilation, mode templates, routing, fingerprinting, and Preview API.
2. Web Project context, API contracts, dual-mode wizard, simple/advanced Preview, and mock E2E.
3. Documentation, full local regression, and phase-one evidence closeout.

Backend and Web are not independent products: the Web must consume the same Preview contract and may not recompute routing. Phase-two MonitoringScope/WorkflowPlan/WorkflowVersion persistence is intentionally excluded and requires a separate implementation plan after phase-one closeout.

## File Structure

### Backend files

- Create apps/api/src/data_intelligence_hub/schemas/workflow_planner.py
  - All public request/response enums and Pydantic contracts; extra fields forbidden.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py
  - Stable exports for the pure Planner entrypoint.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/normalization.py
  - Unicode, defaults, URL classification, scope_key, stable ordering, and input diagnostics.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py
  - Adapter protocol and Fixture-only implementation.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/query_compiler.py
  - QueryTerm builder and seven declarative platform compilers.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/templates.py
  - periodic_monitoring.v1 and batch_research.v1 step/requirement construction.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/policies.py
  - market_monitoring_balanced.v1 weights and score calculation.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py
  - Hard gates, readiness, Primary/Fallback/Shadow, held, partial proposal, and exclusions.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/fingerprint.py
  - Canonical JSON, Catalog Snapshot, fingerprint payload, and SHA-256 functions.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py
  - Pure orchestration and WorkflowPlanPreview assembly.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/fixtures/candidate_expansions_v1.json
  - Versioned deterministic candidate output; no network and no capability status.
- Create apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py
  - Project-scoped authenticated Preview endpoint and error mapping.
- Modify apps/api/src/data_intelligence_hub/main.py
  - Register workflow_plans_router under /api/projects.
- Modify apps/api/src/data_intelligence_hub/services/project_service.py
  - Add workspace-scoped active Project lookup.
- Modify apps/api/src/data_intelligence_hub/services/exceptions.py
  - Add Project and Planner-specific errors.

### Backend tests and fixtures

- Create apps/api/tests/fixtures/workflow_planner/periodic_monitoring_request_v1.json.
- Create apps/api/tests/fixtures/workflow_planner/batch_research_request_v1.json.
- Create apps/api/tests/fixtures/workflow_planner/synthetic_capability_catalog_v1.json.
- Create apps/api/tests/unit/test_workflow_planner_schema.py.
- Create apps/api/tests/unit/test_workflow_planner_normalization.py.
- Create apps/api/tests/unit/test_workflow_planner_query_compiler.py.
- Create apps/api/tests/unit/test_workflow_planner_templates.py.
- Create apps/api/tests/unit/test_workflow_planner_resolver.py.
- Create apps/api/tests/unit/test_workflow_planner_fingerprint.py.
- Create apps/api/tests/unit/test_workflow_planner.py.
- Create apps/api/tests/integration/test_workflow_planner_preview.py.

### Web files

- Create apps/web/src/types/workflow-planner.ts.
- Create apps/web/src/lib/api/workflow-plans.ts.
- Create apps/web/src/lib/workflow-planner.ts.
- Create apps/web/src/lib/workflow-planner-mock.ts.
- Create apps/web/src/components/layout/project-selection-provider.tsx.
- Modify apps/web/src/lib/project-selection.ts.
- Modify apps/web/src/components/layout/project-selector.tsx.
- Modify apps/web/src/components/layout/app-shell.tsx.
- Modify apps/web/src/components/layout/navigation.ts.
- Modify apps/web/src/lib/api/client.ts.
- Modify apps/web/src/lib/api/projects.ts.
- Modify apps/web/playwright.config.ts.
- Create apps/web/src/app/automation/planner/page.tsx.
- Create apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx.
- Create apps/web/src/components/workflow-planner/workflow-planner-stepper.tsx.
- Create apps/web/src/components/workflow-planner/planner-mode-step.tsx.
- Create apps/web/src/components/workflow-planner/planner-scope-step.tsx.
- Create apps/web/src/components/workflow-planner/planner-constraints-step.tsx.
- Create apps/web/src/components/workflow-planner/workflow-plan-preview.tsx.
- Create apps/web/src/components/workflow-planner/workflow-plan-simple-view.tsx.
- Create apps/web/src/components/workflow-planner/workflow-plan-advanced-view.tsx.
- Create apps/web/src/components/dashboard/workflow-planner-entry-cards.tsx.
- Modify apps/web/src/app/dashboard/page.tsx.
- Create apps/web/tests/unit/project-selection.test.ts.
- Create apps/web/tests/unit/workflow-plans-api.test.ts.
- Create apps/web/tests/unit/workflow-planner.test.ts.
- Modify apps/web/tests/unit/navigation.test.ts.
- Modify apps/web/tests/e2e/main-flows.spec.ts.

### Product, contract, and local state files

- Modify docs/product/product-prd-social-media-automation-platform-v2.md.
- Modify docs/architecture/architecture-data-intelligence-hub-stable.md.
- Modify docs/api/api-contract-data-intelligence-hub-stable.md.
- Modify docs/superpowers/specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md.
- Modify docs/superpowers/plans/2026-07-12-goal-v2-03-workflow-planner-phase-1.md.
- Modify TODO.md.
- Modify .codex/context-pack.md.
- Modify .codex/ralph-loop.local.md.
- Modify .kiro/plan/task_plan.md.
- Modify .kiro/plan/findings.md.
- Modify .kiro/plan/progress.md.



---

### Task 0: Establish The GOAL-V2-02 Checkpoint And Activate Phase One

**Files:**
- Existing V2-02 allowlist shown in Step 4.
- Modify after checkpoint: docs/product/product-prd-social-media-automation-platform-v2.md.
- Modify after checkpoint: TODO.md.
- Modify after checkpoint: .codex/context-pack.md.
- Modify after checkpoint: .codex/ralph-loop.local.md.
- Modify after checkpoint: .kiro/plan/task_plan.md.
- Modify after checkpoint: .kiro/plan/findings.md.
- Modify after checkpoint: .kiro/plan/progress.md.

**Interfaces:**
- Consumes: locally verified GOAL-V2-02 working tree at base HEAD 615e88c.
- Produces: one reviewable V2-02 checkpoint or a user-approved equivalent clean isolation; explicit GOAL-V2-03 phase-one in-progress local control state.

- [x] **Step 1: Reconfirm the dirty-worktree boundary without writing**

~~~bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --cached --name-only
git diff --check
~~~

Expected:

- branch is codex/social-api-private-matrix-20260708;
- HEAD is still 615e88c before the V2-02 checkpoint;
- staged output is empty;
- V2-02 files and the approved V2-03 spec/plan are visible as unstaged or untracked;
- git diff --check exits 0.

- [x] **Step 2: Stop for explicit checkpoint authorization**

Report:

    ready_for_owner_authorization
    requested_action=GOAL-V2-02 checkpoint commit or owner-approved clean isolation
    push=false
    pr=false
    deploy=false
    production unchanged

Do not run Task 1 if authorization is absent. Do not infer commit authorization from “continue”, “execute”, or an implementation-mode choice.

- [x] **Step 3: After authorization, rerun the complete V2-02 local gate**

~~~bash
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
~~~

Expected: all commands exit 0 and Alembic still reports one head, 202606110026.

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API PLAYWRIGHT_PORT=3113 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web test:e2e
~~~

Expected: typecheck, lint, unit, build, and the full mock Playwright suite exit 0. Record fresh totals; any failure stops checkpoint creation.

- [x] **Step 4: Stage exactly the V2-02 allowlist only after authorization**

~~~bash
git add -- apps/api/src/data_intelligence_hub/main.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/src/data_intelligence_hub/api/routes/capabilities.py apps/api/src/data_intelligence_hub/schemas/capability_matrix.py apps/api/src/data_intelligence_hub/services/capability_matrix.py apps/api/tests/integration/test_capability_routes.py apps/api/tests/unit/test_capability_matrix.py apps/web/playwright.config.ts 'apps/web/src/app/api-market/[endpointId]/page.tsx' apps/web/src/app/api-market/page.tsx apps/web/src/components/api-market/api-market-detail-workspace.tsx apps/web/src/components/api-market/api-market-workspace.tsx apps/web/src/components/api-market/capability-comparison-panel.tsx apps/web/src/components/api-market/capability-detail-drawer.tsx apps/web/src/components/api-market/capability-list-view.tsx apps/web/src/components/api-market/capability-matrix-view.tsx apps/web/src/components/api-market/capability-scenario-view.tsx apps/web/src/components/layout/app-shell.tsx apps/web/src/components/layout/mobile-navigation.tsx apps/web/src/components/layout/navigation.ts apps/web/src/components/layout/project-selector.tsx apps/web/src/components/layout/sidebar.tsx apps/web/src/components/layout/top-bar.tsx apps/web/src/lib/api/capabilities.ts apps/web/src/lib/api-market-catalog.ts apps/web/src/lib/capability-market.ts apps/web/src/lib/capability-mock.ts apps/web/src/lib/project-selection.ts apps/web/src/types/api-market.ts apps/web/src/types/capability.ts apps/web/tests/e2e/main-flows.spec.ts apps/web/tests/unit/api-market.test.ts apps/web/tests/unit/capability-api.test.ts apps/web/tests/unit/capability-market.test.ts apps/web/tests/unit/navigation.test.ts apps/web/tests/unit/social-provider.test.ts docs/api/api-contract-data-intelligence-hub-stable.md docs/architecture/architecture-data-intelligence-hub-stable.md docs/product/product-prd-social-media-automation-platform-v2.md docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
git diff --cached --name-only
git diff --cached --check
~~~

Expected: exactly 42 paths, no drafts/output/ref/V2-03 paths, and no whitespace errors.

- [x] **Step 5: Create the authorized V2-02 checkpoint**

~~~bash
git commit -m "feat: deliver capability matrix and navigation"
~~~

Expected: one new local commit. Do not push. If the user authorized isolation without a commit, follow only that explicit method and record its evidence before continuing.

- [x] **Step 6: Activate GOAL-V2-03 phase one in local control files**

Apply these exact state values with apply_patch:

~~~text
GOAL-V2-03 status=in_progress
current_batch=phase_1_fixture_preview
provider_call=false
database_migration=false
production unchanged
~~~

Set checkpoint_reference to the actual new V2-02 commit SHA or the exact owner-approved isolation identifier; never write a placeholder value.

Update the PRD Goal list and the current overlays in TODO.md, .codex/context-pack.md, .codex/ralph-loop.local.md, and .kiro/plan/*. Preserve the historical PRD2 sections. Do not attempt to stage ignored TODO/.codex/.kiro files.

- [x] **Step 7: Verify the activation boundary**

~~~bash
git status --short
git diff --check
rg -n "GOAL-V2-03|phase_1_fixture_preview|provider_call=false|database_migration=false|production unchanged" docs/product/product-prd-social-media-automation-platform-v2.md TODO.md .codex/context-pack.md .codex/ralph-loop.local.md .kiro/plan
~~~

Expected: V2-02 allowlist is clean after its checkpoint; V2-03 spec/plan and local state are visible; no business-code file has a V2-03 diff yet.



---

### Task 1: Define The Workflow Planner Contract And Golden Requests

**Files:**
- Create apps/api/src/data_intelligence_hub/schemas/workflow_planner.py.
- Create apps/api/tests/unit/test_workflow_planner_schema.py.
- Create apps/api/tests/fixtures/workflow_planner/periodic_monitoring_request_v1.json.
- Create apps/api/tests/fixtures/workflow_planner/batch_research_request_v1.json.

**Interfaces:**
- Consumes: PlatformId, ResourceType, CapabilityOperation, and CapabilityStatus from schemas/capability_catalog.py.
- Produces: PlanningInput, NormalizedPlanningInput, QueryTerm, CompiledPlatformQuery, QueryCompilerFailure, RouteRequirement, CapabilityReadinessSnapshot, RouteCandidateDecision, RoutePlanPreview, WorkflowStepPreview, DecisionTrace, WorkflowPlanFingerprintPayload, supporting typed contracts, and WorkflowPlanPreview.

- [x] **Step 1: Add two exact request Fixtures**

periodic_monitoring_request_v1.json:

~~~json
{
  "flow_mode": "periodic_monitoring",
  "scopes": [
    {
      "scope_ref": "scope-1",
      "scope_type": "brand",
      "canonical_term": "Acme",
      "aliases": ["ACME"],
      "include_terms": ["running shoes"],
      "exclude_terms": ["jobs"],
      "official_accounts": ["@acme"],
      "seed_urls": ["https://www.youtube.com/watch?v=demo"],
      "languages": ["en"],
      "regions": ["US"],
      "platforms": ["youtube"],
      "match_mode": "phrase"
    },
    {
      "scope_ref": "scope-2",
      "scope_type": "category",
      "canonical_term": "running shoes",
      "aliases": ["running footwear"],
      "include_terms": ["trail shoes"],
      "exclude_terms": ["jobs"],
      "official_accounts": [],
      "seed_urls": [],
      "languages": [],
      "regions": [],
      "platforms": [],
      "match_mode": null
    }
  ],
  "default_languages": ["en"],
  "default_regions": ["US"],
  "default_platforms": ["youtube"],
  "schedule_intent": {"cadence": "daily", "timezone": "UTC"},
  "delivery_intent": {"outputs": ["brief"]},
  "policy_profile": "market_monitoring_balanced",
  "purpose": "market_research",
  "required_fields": ["id", "url", "text", "published_at"],
  "optional_fields": ["author", "metrics"],
  "budget_ceiling": null,
  "rate_limit_intent": null,
  "retention_intent": {"days": 30},
  "allow_partial_degradation": false
}
~~~

batch_research_request_v1.json:

~~~json
{
  "flow_mode": "batch_research",
  "scopes": [
    {
      "scope_ref": "scope-1",
      "scope_type": "topic",
      "canonical_term": "running shoes",
      "aliases": [],
      "include_terms": ["trail shoes"],
      "exclude_terms": ["jobs"],
      "official_accounts": [],
      "seed_urls": [
        "https://www.reddit.com/r/running/comments/demo",
        "https://example.com/research/demo"
      ],
      "languages": ["en"],
      "regions": ["US"],
      "platforms": ["reddit"],
      "match_mode": "hybrid"
    }
  ],
  "default_languages": ["en"],
  "default_regions": ["US"],
  "default_platforms": ["reddit"],
  "delivery_intent": {"outputs": ["dataset"]},
  "policy_profile": "market_monitoring_balanced",
  "purpose": "market_research",
  "required_fields": ["id", "url", "text"],
  "optional_fields": ["author", "published_at", "metrics"],
  "budget_ceiling": null,
  "rate_limit_intent": null,
  "retention_intent": {"days": 30},
  "allow_partial_degradation": false
}
~~~

- [x] **Step 2: Write schema tests before the module exists**

~~~python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_planner import PlanningInput

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"


def load_request(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_periodic_request_requires_schedule_and_effective_platform() -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    parsed = PlanningInput.model_validate(payload)
    assert parsed.flow_mode.value == "periodic_monitoring"
    assert parsed.schedule_intent is not None

    payload["schedule_intent"] = None
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)

    payload = load_request("periodic_monitoring_request_v1.json")
    payload["default_platforms"] = []
    for scope in payload["scopes"]:
        scope["platforms"] = []
        scope["seed_urls"] = []
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_batch_request_allows_unclassified_seed_and_rejects_schedule() -> None:
    payload = load_request("batch_research_request_v1.json")
    parsed = PlanningInput.model_validate(payload)
    assert parsed.flow_mode.value == "batch_research"
    assert len(parsed.scopes[0].seed_urls) == 2
    assert "schedule_intent" not in parsed.model_fields_set

    for forbidden_value in (
        None,
        {"cadence": "daily", "timezone": "UTC"},
    ):
        payload["schedule_intent"] = forbidden_value
        with pytest.raises(ValidationError):
            PlanningInput.model_validate(payload)


@pytest.mark.parametrize("extra_field", ["project_id", "scope_key", "readiness_snapshots"])
def test_request_rejects_server_owned_or_unknown_fields(extra_field: str) -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    payload[extra_field] = "forbidden"
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_scope_refs_are_unique_and_lists_are_bounded() -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    payload["scopes"][1]["scope_ref"] = "scope-1"
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)

    payload = load_request("periodic_monitoring_request_v1.json")
    payload["scopes"][0]["aliases"] = [f"alias-{index}" for index in range(51)]
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)
~~~

- [x] **Step 3: Run the schema test and verify the red state**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_schema.py -q
~~~

Expected: FAIL with ModuleNotFoundError for schemas.workflow_planner.

- [x] **Step 4: Implement the request contract and shared enums**

Use one local base model so no existing Capability contract is refactored:

~~~python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)


class WorkflowPlannerContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlowMode(StrEnum):
    PERIODIC_MONITORING = "periodic_monitoring"
    BATCH_RESEARCH = "batch_research"


class MonitoringScopeType(StrEnum):
    BRAND = "brand"
    CATEGORY = "category"
    COMPETITOR = "competitor"
    TOPIC = "topic"
    CAMPAIGN = "campaign"


class MatchMode(StrEnum):
    EXACT = "exact"
    PHRASE = "phrase"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class PolicyProfile(StrEnum):
    MARKET_MONITORING_BALANCED = "market_monitoring_balanced"


class AuthReadiness(StrEnum):
    NOT_REQUIRED = "not_required"
    READY = "ready"
    MISSING = "missing"
    NOT_CHECKED = "not_checked"


class PlanningStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    HELD = "held"


class RoutePlanStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    HELD = "held"


class WorkflowStepPlanningStatus(StrEnum):
    PLANNED = "planned"
    PARTIAL = "partial"
    HELD = "held"
    NOT_APPLICABLE = "not_applicable"


class BudgetStatus(StrEnum):
    WITHIN_CEILING = "within_ceiling"
    EXCEEDED = "exceeded"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ScheduleIntent(WorkflowPlannerContract):
    cadence: Literal["hourly", "daily", "weekly"]
    timezone: str = Field(min_length=1, max_length=100)


class DeliveryIntent(WorkflowPlannerContract):
    outputs: list[Literal["dataset", "alert", "brief"]] = Field(min_length=1)


class BudgetCeiling(WorkflowPlannerContract):
    amount: Decimal = Field(ge=0)
    currency: Literal["USD"] = "USD"


class RateLimitIntent(WorkflowPlannerContract):
    max_requests: int = Field(ge=1)
    period_seconds: int = Field(ge=1)


class RetentionIntent(WorkflowPlannerContract):
    days: int = Field(ge=1, le=3650)


class MonitoringScopeDraft(WorkflowPlannerContract):
    scope_ref: str = Field(min_length=1, max_length=100)
    scope_type: MonitoringScopeType
    canonical_term: str | None = Field(default=None, max_length=500)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    include_terms: list[str] = Field(default_factory=list, max_length=50)
    exclude_terms: list[str] = Field(default_factory=list, max_length=50)
    official_accounts: list[str] = Field(default_factory=list, max_length=50)
    seed_urls: list[str] = Field(default_factory=list, max_length=100)
    languages: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    platforms: list[PlatformId] = Field(default_factory=list)
    match_mode: MatchMode | None = None

    @model_validator(mode="after")
    def validate_scope_content(self) -> "MonitoringScopeDraft":
        if self.scope_type in {
            MonitoringScopeType.BRAND,
            MonitoringScopeType.CATEGORY,
            MonitoringScopeType.COMPETITOR,
        } and not (self.canonical_term and self.canonical_term.strip()):
            raise ValueError("canonical_term_required")
        if self.scope_type in {
            MonitoringScopeType.TOPIC,
            MonitoringScopeType.CAMPAIGN,
        } and not any(
            (
                self.canonical_term and self.canonical_term.strip(),
                self.aliases,
                self.include_terms,
                self.official_accounts,
                self.seed_urls,
            )
        ):
            raise ValueError("scope_input_required")
        return self


class PlanningInput(WorkflowPlannerContract):
    flow_mode: FlowMode
    scopes: list[MonitoringScopeDraft] = Field(min_length=1, max_length=20)
    default_languages: list[str] = Field(default_factory=list)
    default_regions: list[str] = Field(default_factory=list)
    default_platforms: list[PlatformId] = Field(default_factory=list)
    schedule_intent: ScheduleIntent | None = None
    delivery_intent: DeliveryIntent | None = None
    policy_profile: PolicyProfile = PolicyProfile.MARKET_MONITORING_BALANCED
    purpose: Literal["brand_monitoring", "market_research", "competitive_research"]
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    budget_ceiling: BudgetCeiling | None = None
    rate_limit_intent: RateLimitIntent | None = None
    retention_intent: RetentionIntent | None = None
    allow_partial_degradation: bool = False

    @model_validator(mode="after")
    def validate_flow_contract(self) -> "PlanningInput":
        refs = [scope.scope_ref for scope in self.scopes]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate_scope_ref")
        if sum(len(scope.seed_urls) for scope in self.scopes) > 100:
            raise ValueError("seed_url_limit_exceeded")
        if self.flow_mode is FlowMode.PERIODIC_MONITORING:
            if self.schedule_intent is None:
                raise ValueError("periodic_schedule_required")
            if any(
                not (scope.platforms or self.default_platforms or scope.seed_urls)
                for scope in self.scopes
            ):
                raise ValueError("periodic_platform_or_seed_url_required")
        else:
            if "schedule_intent" in self.model_fields_set:
                raise ValueError("batch_schedule_not_allowed")
            if not any(
                (
                    scope.canonical_term and scope.canonical_term.strip(),
                    scope.aliases,
                    scope.include_terms,
                    scope.official_accounts,
                    scope.seed_urls,
                )
                for scope in self.scopes
            ):
                raise ValueError("batch_input_required")
            if any(
                any(
                    (
                        scope.canonical_term and scope.canonical_term.strip(),
                        scope.aliases,
                        scope.include_terms,
                        scope.official_accounts,
                    )
                )
                and not (scope.platforms or self.default_platforms)
                for scope in self.scopes
            ):
                raise ValueError("batch_query_platform_required")
        return self
~~~

Add the remaining response contracts with the exact field names from design sections 6.3 through 6.8 and these locked types:

| Contract | Required typed fields |
|---|---|
| NormalizedMonitoringScope | scope_key, source_scope_refs, effective_languages, effective_regions, effective_platforms, normalized term/account/URL lists, match_mode |
| NormalizedPlanningInput | flow_mode, scopes, schedule/delivery/policy/purpose/field/budget/rate/retention/partial values |
| QueryTerm | term, normalized_term, scope_ref, scope_key, origin, status, reason, source, score, conflict_codes |
| CompiledPlatformQuery | platform, scope_keys, source_scope_refs, resource_type, operation, query_version, normalized_expression, include/exclude/account/url lists, limitations |
| RouteRequirement | requirement_ref, scope_keys, step_refs, platform, resource_type, operation, purpose, regions, required/optional fields, budget/rate/retention/freshness, allow_partial_degradation, precondition_failures |
| CapabilityReadinessSnapshot | implementation_id, auth_readiness, source, credential_read_status fixed to not_read |
| RouteCandidateDecision | assertion_id, implementation_id, capability_status, score_breakdown, weighted_score, route_eligible, readiness_status, approval_required/reasons, missing optional fields, evidence_refs |
| RoutePlanPreview | requirement_ref, status, primary, fallbacks, shadow, fields, budget/rate/retention, gates, score, exclusions, degradation, limitations, execution_authorized fixed false |
| WorkflowStepPreview | step_ref, template_key, sequence, label, execution_kind, depends_on, platform, scope_keys, resource/operation, requirement_ref, input/output contracts, planning_status, limitations |
| DecisionTrace | semantic_entries and input_diagnostics |
| WorkflowPlanFingerprintPayload | every semantic field named in design section 9.3 and no runtime/reference fields |
| WorkflowPlanPreview | schema/version/project/mode/status/input/ref-map/query/step/route/coverage/budget/limits/trace/attribution/snapshot/policy/fingerprint/boundary/runtime fields |

Lock the supporting contracts instead of leaving free-form dictionaries:

| Supporting contract | Exact fields |
|---|---|
| ScopeRefMapping | scope_ref, scope_key |
| DecisionReason | code, reason |
| QueryCompilerFailure | platform, scope_keys, code fixed compiler_missing, reason |
| DecisionTraceEntry | code, reason, scope_keys, requirement_ref, details |
| ScoreBreakdown | raw_dimensions, effective_dimensions, weights, weighted_score, trace_codes |
| ShadowRule | enabled, fallback_implementation_id, sample_rate, max_items, reason, execution_authorized |
| CoverageSummary | total_requirements, resolved_requirements, partial_requirements, held_requirements |
| BudgetSummary | currency, known_selected_unit_cost, unknown_count, budget_status |
| StepDataContractField | name, data_type, cardinality, required, source_step_ref, description |
| StepDataContract | schema_version, fields |
| AttributionContract | matched_scope_id, matched_term, match_reason, query_version, requirement_ref, route_plan_ref |

Use dict[str, int] for score dimension/weight maps, dict[str, JsonValue] for DecisionTraceEntry.details, Decimal for known costs, and Literal[False] for ShadowRule.execution_authorized. Empty or unavailable Primary score/budget values use None plus an explicit status/code; they never use zero as an unknown sentinel.

Implement every enum and contract named in the two tables in schemas/workflow_planner.py before the schema test can turn green. Do not replace AuthReadiness, ScopeRefMapping, DecisionTraceEntry, ScoreBreakdown, StepDataContract, ShadowRule, CoverageSummary, or BudgetSummary with untyped dict[str, Any].

All boundary booleans use Literal[False]. WorkflowPlanPreview.project_id uses UUID; generated_at uses datetime.

- [x] **Step 5: Run schema tests and static checks**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_schema.py -q
uv run ruff check src/data_intelligence_hub/schemas/workflow_planner.py tests/unit/test_workflow_planner_schema.py
uv run mypy src/data_intelligence_hub/schemas/workflow_planner.py tests/unit/test_workflow_planner_schema.py
~~~

Expected: all commands exit 0.

- [ ] **Step 6: Optional authorized commit**

If and only if task-level commit authorization exists:

~~~bash
git add -- apps/api/src/data_intelligence_hub/schemas/workflow_planner.py apps/api/tests/unit/test_workflow_planner_schema.py apps/api/tests/fixtures/workflow_planner/periodic_monitoring_request_v1.json apps/api/tests/fixtures/workflow_planner/batch_research_request_v1.json
git diff --cached --check
git commit -m "feat: define workflow planner contracts"
~~~

Otherwise leave the verified files unstaged.



---

### Task 2: Normalize Scopes, Defaults, Terms, URLs, And Semantic Identity

**Files:**
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/fingerprint.py.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/normalization.py.
- Modify apps/api/src/data_intelligence_hub/services/exceptions.py.
- Create apps/api/tests/unit/test_workflow_planner_normalization.py.

**Interfaces:**
- Consumes: PlanningInput and normalized contracts from Task 1.
- Produces: canonical_json_bytes(value), sha256_id(value), normalize_text(value), normalize_seed_url(value), classify_seed_url(value), build_scope_key(scope), normalize_planning_input(payload), and NormalizationResult.

- [x] **Step 1: Write failing normalization tests**

~~~python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_intelligence_hub.schemas.workflow_planner import PlanningInput
from data_intelligence_hub.services.exceptions import WorkflowPlannerInputError
from data_intelligence_hub.services.workflow_planner.normalization import (
    classify_seed_url,
    normalize_planning_input,
    normalize_text,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "periodic_monitoring_request_v1.json"
)


def test_text_normalization_is_nfkc_trimmed_and_casefolded() -> None:
    assert normalize_text("  ＡＣＭＥ  ") == "acme"


def test_scope_key_ignores_scope_ref_and_input_order() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first = normalize_planning_input(PlanningInput.model_validate(payload))

    payload["scopes"][0]["scope_ref"] = "another-ref"
    payload["scopes"][0]["aliases"] = list(reversed(payload["scopes"][0]["aliases"]))
    second = normalize_planning_input(PlanningInput.model_validate(payload))

    assert first.normalized_input.scopes[0].scope_key == second.normalized_input.scopes[0].scope_key
    assert first.fingerprint_input == second.fingerprint_input


def test_scope_override_replaces_global_defaults() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["scopes"][0]["platforms"] = ["reddit"]
    result = normalize_planning_input(PlanningInput.model_validate(payload))
    assert result.normalized_input.scopes[0].effective_platforms == ["reddit"]
    assert result.normalized_input.scopes[1].effective_platforms == ["youtube"]


def test_seed_url_classification_is_string_only() -> None:
    assert classify_seed_url("https://youtu.be/demo") == "youtube"
    assert classify_seed_url("https://www.reddit.com/r/demo") == "reddit"
    assert classify_seed_url("https://example.com/demo") is None


def test_periodic_seed_url_can_derive_effective_platform() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["default_platforms"] = []
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["platforms"] = []
    payload["scopes"][0]["seed_urls"] = ["https://youtu.be/demo"]

    result = normalize_planning_input(PlanningInput.model_validate(payload))

    assert result.normalized_input.scopes[0].effective_platforms == ["youtube"]


def test_periodic_unclassified_seed_without_platform_is_a_field_error() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["default_platforms"] = []
    payload["scopes"] = [payload["scopes"][0]]
    payload["scopes"][0]["platforms"] = []
    payload["scopes"][0]["seed_urls"] = ["https://example.com/demo"]

    with pytest.raises(WorkflowPlannerInputError) as captured:
        normalize_planning_input(PlanningInput.model_validate(payload))

    assert captured.value.issues[0]["loc"] == ["body", "scopes", 0, "platforms"]
~~~

- [x] **Step 2: Run the test and verify the red state**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_normalization.py -q
~~~

Expected: FAIL because WorkflowPlannerInputError and normalization.py do not exist.

- [x] **Step 3: Implement canonical primitives**

~~~python
from __future__ import annotations

import hashlib
import json
from typing import TypeAlias

from pydantic import JsonValue

CanonicalValue: TypeAlias = JsonValue


def canonical_json_bytes(value: CanonicalValue) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_id(value: CanonicalValue) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"
~~~

Place this code in fingerprint.py. Task 6 extends the same file; do not duplicate hashing elsewhere.

- [x] **Step 4: Implement the normalizer**

Use these exact platform host groups without performing DNS or HTTP:

~~~python
PLATFORM_HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "reddit": {"reddit.com", "www.reddit.com", "old.reddit.com"},
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "threads": {"threads.net", "www.threads.net"},
    "tiktok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com"},
    "linkedin": {"linkedin.com", "www.linkedin.com"},
}
~~~

Implement:

- normalize_text with NFKC, strip, and casefold.
- normalize_seed_url with urlsplit/urlunsplit, http/https only, lowercase scheme/host, remove fragment, retain and stably sort query pairs, and never open the URL.
- classify_seed_url by exact normalized hostname membership.
- effective lists as Scope non-empty override, otherwise global defaults.
- when both Scope and default platforms are empty, derive effective platforms from classified Seed URLs before enforcing the periodic requirement;
- after classification, when periodic Scope index i still has no effective platform, raise WorkflowPlannerInputError with exactly {"loc": ["body", "scopes", i, "platforms"], "msg": "periodic_effective_platform_required", "type": "value_error"};
- match_mode defaults: brand=phrase, category=hybrid, all other scope types=phrase.
- exclusion precedence and duplicate semantic Scope collapse.
- scope_key as SHA-256 of the effective semantic Scope without scope_ref.
- fingerprint_input with scope_key and no source_scope_refs.
- input diagnostics for duplicate_scope_collapsed, seed_url_unclassified, and platform_not_selected.

Use a frozen NormalizationResult dataclass with:

~~~python
@dataclass(frozen=True)
class NormalizationResult:
    normalized_input: NormalizedPlanningInput
    fingerprint_input: dict[str, JsonValue]
    scope_ref_map: tuple[ScopeRefMapping, ...]
    semantic_entries: tuple[DecisionTraceEntry, ...]
    input_diagnostics: tuple[DecisionTraceEntry, ...]
~~~

Add the field-error carrier to services/exceptions.py before normalization.py imports it:

~~~python
class WorkflowPlannerInputError(ServiceError):
    message = "workflow_planner_input_invalid"

    def __init__(self, issues: list[dict[str, object]]) -> None:
        super().__init__(self.message)
        self.issues = issues
~~~

- [x] **Step 5: Add edge-case tests and run the green gate**

Add complete tests for:

- brand/category/competitor canonical requirement;
- topic/campaign Seed-URL-only input;
- exclude term winning over active terms;
- semantic duplicate Scope collapse with two ref mappings;
- 20/21 Scope, 50/51 term, and 100/101 URL limits;
- classified URL outside an explicit platform list;
- batch keyword without effective platform rejected;
- periodic schedule and effective platform requirements.

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_schema.py tests/unit/test_workflow_planner_normalization.py -q
uv run ruff check src/data_intelligence_hub/services/workflow_planner/fingerprint.py src/data_intelligence_hub/services/workflow_planner/normalization.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_workflow_planner_normalization.py
uv run mypy src/data_intelligence_hub/services/workflow_planner/fingerprint.py src/data_intelligence_hub/services/workflow_planner/normalization.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_workflow_planner_normalization.py
~~~

Expected: all commands exit 0.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py apps/api/src/data_intelligence_hub/services/workflow_planner/fingerprint.py apps/api/src/data_intelligence_hub/services/workflow_planner/normalization.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_workflow_planner_normalization.py
git diff --cached --check
git commit -m "feat: normalize workflow planning inputs"
~~~

Run only under task-level commit authorization.



---

### Task 3: Build Fixture Candidate Expansion And Declarative Platform Queries

**Files:**
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/query_compiler.py.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/fixtures/candidate_expansions_v1.json.
- Create apps/api/tests/unit/test_workflow_planner_query_compiler.py.

**Interfaces:**
- Consumes: NormalizationResult and QueryTerm/CompiledPlatformQuery contracts.
- Produces: CandidateExpansionAdapter, FixtureCandidateExpansionAdapter, PlatformQueryCompiler, QueryCompilerFailure, QueryCompilationResult, build_query_terms(), and compile_platform_queries().

- [x] **Step 1: Add the versioned candidate Fixture**

~~~json
{
  "schema_version": "workflow_candidate_expansion_fixture.v1",
  "version": "candidate-expansion.v1",
  "entries": {
    "acme": [
      {
        "term": "acme official",
        "reason": "Fixture candidate for official-brand phrasing",
        "source": "fixture:acme",
        "score": 0.70,
        "conflict_codes": []
      }
    ],
    "running shoes": [
      {
        "term": "performance running footwear",
        "reason": "Fixture candidate for category synonym",
        "source": "fixture:running-shoes",
        "score": 0.75,
        "conflict_codes": []
      },
      {
        "term": "shoe jobs",
        "reason": "Fixture candidate intentionally conflicting with exclusions",
        "source": "fixture:running-shoes",
        "score": 0.20,
        "conflict_codes": ["excluded_term_overlap"]
      }
    ]
  }
}
~~~

Unknown normalized terms return no candidates and add fixture_expansion_no_match to the semantic trace.

- [x] **Step 2: Write failing query tests**

~~~python
from pathlib import Path

from data_intelligence_hub.schemas.capability_catalog import PlatformId
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    CandidateExpansionFixture,
    FixtureCandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.query_compiler import (
    build_query_terms,
    compile_platform_queries,
    default_platform_query_compilers,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    NormalizationResult,
)


def test_candidate_terms_never_enter_compiled_expression(
    periodic_normalization: NormalizationResult,
) -> None:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(periodic_normalization, candidate_adapter=adapter)
    result = compile_platform_queries(
        periodic_normalization,
        terms,
        compilers=default_platform_query_compilers(),
    )

    assert any(term.status == "candidate" for term in terms)
    deterministic_terms = {
        term.normalized_term for term in terms if term.status == "active"
    }
    assert all(
        candidate.normalized_term not in deterministic_terms
        for candidate in terms
        if candidate.status == "candidate"
    )
    assert all(
        candidate.normalized_term not in query.normalized_expression
        for candidate in terms
        if candidate.status == "candidate"
        for query in result.compiled_queries
    )


def test_every_platform_has_a_stable_declarative_version(
    periodic_normalization: NormalizationResult,
) -> None:
    compilers = default_platform_query_compilers()
    assert set(compilers) == set(PlatformId)
    assert {compiler.query_version for compiler in compilers.values()} == {
        f"{platform.value}.declarative.v1" for platform in PlatformId
    }


def test_candidate_fixture_is_schema_valid() -> None:
    fixture_path = (
        Path(__file__).parents[2]
        / "src"
        / "data_intelligence_hub"
        / "services"
        / "workflow_planner"
        / "fixtures"
        / "candidate_expansions_v1.json"
    )
    fixture = CandidateExpansionFixture.model_validate_json(
        fixture_path.read_text(encoding="utf-8")
    )
    assert fixture.schema_version == "workflow_candidate_expansion_fixture.v1"
    assert CandidateExpansionFixture.model_json_schema()["type"] == "object"
~~~

- [x] **Step 3: Run the test and verify the red state**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_query_compiler.py -q
~~~

Expected: FAIL because candidate_expansion.py and query_compiler.py do not exist.

- [x] **Step 4: Implement the Fixture adapter and compiler registry**

The adapter interface is:

~~~python
class CandidateExpansionAdapter(Protocol):
    version: str

    def expand(
        self,
        scope: NormalizedMonitoringScope,
        *,
        flow_mode: FlowMode,
    ) -> list[QueryTerm]:
        raise NotImplementedError
~~~

CandidateExpansionFixture and CandidateExpansionEntry are strict Pydantic contracts with extra="forbid". The adapter must load the JSON through CandidateExpansionFixture.model_validate_json; direct untyped json.loads output may not enter the Planner.

The compiler interface is:

~~~python
class PlatformQueryCompiler(Protocol):
    platform: PlatformId
    query_version: str

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        raise NotImplementedError
~~~

QueryCompilationResult must retain failed query intent instead of dropping it:

~~~python
@dataclass(frozen=True)
class QueryCompilationResult:
    query_terms: tuple[QueryTerm, ...]
    compiled_queries: tuple[CompiledPlatformQuery, ...]
    compiler_failures: tuple[QueryCompilerFailure, ...]
    limitations: tuple[str, ...]
    semantic_entries: tuple[DecisionTraceEntry, ...]
    query_versions: Mapping[PlatformId, str]
~~~

Use one DeclarativePlatformQueryCompiler class instantiated once per PlatformId. normalized_expression is canonical JSON containing platform, match_mode, active terms, exclusions, accounts, and URL inputs. It is not Provider request syntax and always includes limitation declarative_preview_only.

QueryTerm rules:

- brand: canonical, alias, and official account are active; include terms carry reason brand_context_required and cannot stand alone;
- category: canonical, alias, and include terms are active;
- competitor/topic/campaign: deterministic inputs are active;
- terms matching exclude_terms are rejected;
- all Fixture outputs remain candidate;
- candidate score/conflict/reason/source are preserved;
- QueryTerms sort by scope_key, normalized_term, and origin; platform ordering belongs to CompiledPlatformQuery because QueryTerm is platform-neutral.
- each requested platform missing from the supplied compiler mapping creates one stable QueryCompilerFailure and compiler_missing:{platform} limitation; it is never silently removed.

- [x] **Step 5: Prove missing compilers and conflict behavior**

Add tests that:

- remove the Reddit compiler and assert compiler_missing:reddit limitation;
- assert the missing platform produces no compiled query but does produce QueryCompilerFailure(platform=reddit, code=compiler_missing);
- assert excluded candidates are visible but rejected;
- assert the adapter opens only its local Fixture path;
- monkeypatch socket and httpx entrypoints to raise if invoked, then prove compilation still passes.

Use an explicit outbound-call tripwire in the test module:

~~~python
import socket
from typing import NoReturn

import httpx
import pytest


def test_fixture_compilation_never_uses_network(
    periodic_normalization: NormalizationResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("workflow planner compilation attempted network I/O")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(httpx.Client, "request", fail_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", fail_network)

    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(periodic_normalization, candidate_adapter=adapter)
    result = compile_platform_queries(
        periodic_normalization,
        terms,
        compilers=default_platform_query_compilers(),
    )

    assert result.compiled_queries
    assert all(
        "declarative_preview_only" in query.limitations
        for query in result.compiled_queries
    )
~~~

The network imports are tripwires only; they do not authorize outbound calls.

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_query_compiler.py -q
uv run ruff check src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py src/data_intelligence_hub/services/workflow_planner/query_compiler.py tests/unit/test_workflow_planner_query_compiler.py
uv run mypy src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py src/data_intelligence_hub/services/workflow_planner/query_compiler.py tests/unit/test_workflow_planner_query_compiler.py
~~~

Expected: all commands exit 0.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/api/src/data_intelligence_hub/services/workflow_planner/candidate_expansion.py apps/api/src/data_intelligence_hub/services/workflow_planner/query_compiler.py apps/api/src/data_intelligence_hub/services/workflow_planner/fixtures/candidate_expansions_v1.json apps/api/tests/unit/test_workflow_planner_query_compiler.py
git diff --cached --check
git commit -m "feat: compile deterministic platform query previews"
~~~

Run only under task-level commit authorization.



---

### Task 4: Expand The Two Stable Workflow Templates

**Files:**
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/templates.py.
- Modify apps/api/src/data_intelligence_hub/services/exceptions.py.
- Create apps/api/tests/unit/test_workflow_planner_templates.py.

**Interfaces:**
- Consumes: NormalizedPlanningInput and QueryCompilationResult.
- Produces: TemplateBuildResult, build_workflow_template(), validate_step_graph(), stable WorkflowStepPreview, and RouteRequirement sequences.

- [x] **Step 1: Write failing template tests**

~~~python
def test_periodic_template_has_locked_steps(
    periodic_normalization: NormalizationResult,
    periodic_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        periodic_normalization.normalized_input,
        periodic_queries,
    )
    assert result.mode_template_version == "periodic_monitoring.v1"
    assert [step.template_key for step in result.steps] == [
        "compile_scope_queries",
        "classify_seed_urls",
        "discover_content",
        "resolve_seed_content",
        "monitor_incremental",
        "summarize_delivery_intent",
    ]
    validate_step_graph(result.steps)


def test_batch_template_maps_to_search_and_batch_parse(
    batch_normalization: NormalizationResult,
    batch_queries: QueryCompilationResult,
) -> None:
    result = build_workflow_template(
        batch_normalization.normalized_input,
        batch_queries,
    )
    requirements = {
        (requirement.resource_type, requirement.operation)
        for requirement in result.requirements
    }
    assert (ResourceType.CONTENT, CapabilityOperation.SEARCH_DISCOVER) in requirements
    assert (ResourceType.CONTENT, CapabilityOperation.BATCH_PARSE) in requirements
    assert all(step.execution_kind != "workflow_run" for step in result.steps)
~~~

- [x] **Step 2: Run the test and verify the red state**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_templates.py -q
~~~

Expected: FAIL because templates.py does not exist.

- [x] **Step 3: Implement exact template expansion**

Add the topology error before templates.py imports it:

~~~python
class WorkflowPlannerTopologyError(ServiceError):
    message = "workflow_planner_invalid_step_graph"
~~~

Use the step tables from design section 6.8 without adding execution steps. Each StepDataContract field has name, data_type, cardinality, required, source_step_ref, and description, sorted by name.

Stable identifiers use:

~~~python
def stable_ref(prefix: str, value: dict[str, JsonValue]) -> str:
    digest = sha256_id(value).removeprefix("sha256:")
    return f"{prefix}:{digest[:16]}"
~~~

Use the full query result so compiler failures cannot disappear between stages:

~~~python
def build_workflow_template(
    normalized_input: NormalizedPlanningInput,
    query_result: QueryCompilationResult,
) -> TemplateBuildResult:
    raise NotImplementedError
~~~

Rules:

- expand future_capability steps once per effective platform;
- merge semantically equal platform/resource/operation Requirements and retain all scope_keys/step_refs;
- derive known Seed URL platform only when no explicit platform exists;
- record platform_not_selected and seed_url_unclassified on classify_seed_urls;
- do not create a fake Requirement for unclassified URLs;
- make monitor_incremental depend on same-platform discover or resolve steps;
- make batch_parse depend on same-platform discover and accept direct Seed URL contracts;
- internal steps never produce RouteRequirement;
- for each QueryCompilerFailure, emit the corresponding query-dependent future Step and RouteRequirement as held with precondition_failures=[DecisionReason(code="compiler_missing", reason=f"Query compiler missing for {failure.platform.value}")]; do not fabricate a CompiledPlatformQuery;
- topologically validate every dependency and raise WorkflowPlannerTopologyError for missing, forward, or cyclic references.

- [x] **Step 4: Add graph and mapping edge tests**

Cover:

- no Seed URL removes classify/resolve optional steps and records not_applicable trace;
- a mixed classified/unclassified input makes classify_seed_urls partial;
- explicit platform mismatch records held input and no Requirement;
- duplicate Requirements merge deterministically;
- a missing compiler survives into a held Step and a RouteRequirement with compiler_missing precondition, even when the Catalog contains a verified implementation;
- changing input order does not change step_ref or requirement_ref;
- invalid dependency raises WorkflowPlannerTopologyError.

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_templates.py -q
uv run ruff check src/data_intelligence_hub/services/workflow_planner/templates.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_workflow_planner_templates.py
uv run mypy src/data_intelligence_hub/services/workflow_planner/templates.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_workflow_planner_templates.py
~~~

Expected: all commands exit 0.

- [ ] **Step 5: Optional authorized commit**

~~~bash
git add -- apps/api/src/data_intelligence_hub/services/workflow_planner/templates.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_workflow_planner_templates.py
git diff --cached --check
git commit -m "feat: add workflow planner mode templates"
~~~

Run only under task-level commit authorization.


---

### Task 5: Resolve Capability Routes With Fail-Closed Evidence Gates

**Files:**
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/policies.py.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py.
- Create apps/api/tests/fixtures/workflow_planner/synthetic_capability_catalog_v1.json.
- Create apps/api/tests/unit/test_workflow_planner_resolver.py.

**Interfaces:**
- Consumes: RouteRequirement, CapabilityCatalog, and test-only CapabilityReadinessSnapshot mappings.
- Produces: RoutingPolicy, ScoreBreakdown, get_routing_policy(), calculate_weighted_score(), derive_product_readiness(), and resolve_route_plans().

- [x] **Step 1: Add one test-only synthetic Catalog**

The file must validate as CapabilityCatalog and contain:

| Implementation | Status set | Credentials | Unit cost USD | Required fields | Optional fields |
|---|---|---|---:|---|---|
| fixture.primary | verified | none | 0.01 | id,url,text | author,published_at,metrics |
| fixture.fallback | verified | none | 0.02 | id,url,text | author,published_at |
| fixture.partial | partial | none | 0.005 | id,url,text | author |

All three use platform=youtube, access_channel=official_authorized_api, delivery_form=endpoint, deployment_mode=managed_saas, lifecycle_status=active, region_scope=["global"], purpose_scope=["market_research"], auth_scope=["not_required"], and no blocking constraints.

Use these exact score profiles:

| Implementation | coverage | freshness | history | reliability | schema_stability | cost_efficiency | maintainability | evidence_confidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixture.primary | 5 | 5 | 4 | 5 | 5 | 4 | 5 | 5 |
| fixture.fallback | 4 | 4 | 4 | 4 | 4 | 3 | 4 | 5 |
| fixture.partial | 5 | 4 | 3 | 3 | 3 | 5 | 3 | 4 |

For each Implementation create Assertions for these four content operations:

    search_discover
    resolve_detail
    monitor_incremental
    batch_parse

Assertion IDs follow:

    {implementation_id}:content:{operation}

Each Assertion references one unique fixture Evidence row. Use generated_at and observed_at 2026-07-12T00:00:00Z, hash_scope=source_reference_only, evidence_grade=L2-fixture, and a 64-character lowercase hexadecimal content_hash. This file lives only under apps/api/tests/fixtures.

- [x] **Step 2: Write the failing resolver golden tests**

~~~python
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_planner import (
    AuthReadiness,
    CapabilityReadinessSnapshot,
    PolicyProfile,
    RouteRequirement,
)
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner.capability_resolver import (
    derive_product_readiness,
    resolve_route_plans,
)
from data_intelligence_hub.services.workflow_planner.policies import (
    get_routing_policy,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "synthetic_capability_catalog_v1.json"
)


def load_synthetic_catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(
        FIXTURE.read_text(encoding="utf-8")
    )


@pytest.fixture(autouse=True)
def isolate_catalog_cache() -> Iterator[None]:
    clear_capability_catalog_cache()
    yield
    clear_capability_catalog_cache()


@pytest.fixture()
def search_requirement() -> RouteRequirement:
    return RouteRequirement(
        requirement_ref="requirement:search",
        scope_keys=["sha256:" + ("a" * 64)],
        step_refs=["step:discover"],
        platform=PlatformId.YOUTUBE,
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.SEARCH_DISCOVER,
        purpose="market_research",
        regions=["US"],
        required_fields=["id", "url", "text"],
        optional_fields=["author"],
        budget_ceiling=None,
        freshness_requirement=None,
        rate_limit_requirement=None,
        retention_requirement={"days": 30},
        allow_partial_degradation=False,
    )


def test_canonical_candidate_catalog_is_held(search_requirement: RouteRequirement) -> None:
    routes = resolve_route_plans(
        [search_requirement],
        get_capability_catalog(),
        policy=get_routing_policy(PolicyProfile.MARKET_MONITORING_BALANCED),
        readiness_snapshots=None,
    )
    assert routes[0].status == "held"
    assert routes[0].primary_implementation is None
    assert "candidate_not_execution_eligible" in {
        reason.code for reason in routes[0].exclusion_reasons
    }


def test_synthetic_catalog_selects_stable_primary_fallback_and_shadow(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog()
    routes = resolve_route_plans(
        [search_requirement],
        catalog,
        policy=get_routing_policy(PolicyProfile.MARKET_MONITORING_BALANCED),
        readiness_snapshots=derive_product_readiness(catalog),
    )
    route = routes[0]
    assert route.status == "resolved"
    assert route.primary_implementation.implementation_id == "fixture.primary"
    assert route.fallback_implementations[0].implementation_id == "fixture.fallback"
    assert route.shadow_rule.enabled is True
    assert route.execution_authorized is False


def test_test_only_ready_snapshot_never_authorizes_execution(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog()
    readiness = {
        "fixture.primary": CapabilityReadinessSnapshot(
            implementation_id="fixture.primary",
            auth_readiness=AuthReadiness.READY,
            source="test_fixture",
            credential_read_status="not_read",
        )
    }
    route = resolve_route_plans(
        [search_requirement],
        catalog,
        policy=get_routing_policy(PolicyProfile.MARKET_MONITORING_BALANCED),
        readiness_snapshots=readiness,
    )[0]
    assert route.execution_authorized is False
~~~

- [x] **Step 3: Run the test and verify the red state**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_resolver.py -q
~~~

Expected: FAIL because policies.py and capability_resolver.py do not exist.

- [x] **Step 4: Implement market_monitoring_balanced.v1**

~~~python
MARKET_MONITORING_BALANCED_WEIGHTS = {
    "coverage": 15,
    "freshness": 15,
    "history": 5,
    "reliability": 20,
    "schema_stability": 15,
    "cost_efficiency": 10,
    "maintainability": 5,
    "evidence_confidence": 15,
}
~~~

Assert the sum is 100 at import time. calculate_weighted_score returns integer weighted_score and every effective dimension. If cost is unknown and no budget ceiling exists, effective cost_efficiency is 1 and decision_trace includes cost_score_capped_unknown.

The phase-one budget contract is per RouteRequirement:

- numeric cost_hint.unit_cost_usd is the estimated unit cost;
- budget_ceiling compares that unit cost in USD;
- unknown cost plus a ceiling fails with budget_unknown_under_ceiling;
- known cost above the ceiling fails with budget_ceiling_exceeded;
- no ceiling keeps unknown status and never awards cost advantage;
- the top-level BudgetSummary sums known selected Primary unit costs and keeps unknown_count.

- [x] **Step 5: Implement hard gates in the fixed order**

Before Capability evaluation, treat RouteRequirement.precondition_failures as an upstream fail-closed result: return held with those exclusion reasons, Primary=None, Fallbacks=[], and no scored candidates. This precheck is separate from, and does not reorder, the Capability hard gates below.

resolve_route_plans performs and records:

1. Capability status.
2. Blocking policy/blocked_action constraints.
3. Auth readiness.
4. Purpose scope.
5. Region scope.
6. Exact platform/resource/operation.
7. Required fields.
8. Budget.

Fail-closed rules:

- candidate, unknown, blocked, unsupported, and deprecated never become route candidates;
- a blocking policy or blocked_action constraint excludes the Assertion in phase one because no approval object exists;
- purpose must match purpose_scope or purpose_scope must contain global;
- each requested region must be covered or region_scope must contain global;
- missing Required Fields exclude; Optional Field gaps remain visible;
- required_credentials empty derives not_required;
- required_credentials non-empty derives not_checked on the product path;
- HTTP cannot inject readiness;
- verified candidates rank by weighted score descending, then implementation_id and assertion_id ascending;
- partial candidates require policy support, allow_partial_degradation=true, complete Required Fields, and approval_required=true;
- the request flag is never an approval object;
- Primary is the first qualified candidate;
- remaining qualified candidates are ordered Fallbacks;
- ShadowRule is declarative only, enabled when a qualified fallback exists, sample_rate=0.05, max_items=10, execution_authorized=false;
- no qualified candidate produces held with primary=None, fallbacks=[], and every exclusion reason.

- [x] **Step 6: Complete all 13 resolver scenarios**

Add tests for:

1. canonical candidate-only held;
2. verified Primary and verified Fallback;
3. partial excluded when allow_partial_degradation=false;
4. partial proposed when the flag is true and Required Fields are complete;
5. stable ID tie-break;
6. Policy exclusion;
7. Region exclusion;
8. Purpose exclusion;
9. Required Field exclusion;
10. budget ceiling exclusion;
11. unknown cost without ceiling;
12. auth not_required/not_checked/test-ready paths;
13. Shadow enabled/disabled and execution_authorized=false.

Add one additional cross-stage regression: a compiler_missing precondition remains held even with the synthetic verified Catalog.

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_resolver.py -q
uv run ruff check src/data_intelligence_hub/services/workflow_planner/policies.py src/data_intelligence_hub/services/workflow_planner/capability_resolver.py tests/unit/test_workflow_planner_resolver.py
uv run mypy src/data_intelligence_hub/services/workflow_planner/policies.py src/data_intelligence_hub/services/workflow_planner/capability_resolver.py tests/unit/test_workflow_planner_resolver.py
~~~

Expected: all commands exit 0.

- [ ] **Step 7: Optional authorized commit**

~~~bash
git add -- apps/api/src/data_intelligence_hub/services/workflow_planner/policies.py apps/api/src/data_intelligence_hub/services/workflow_planner/capability_resolver.py apps/api/tests/fixtures/workflow_planner/synthetic_capability_catalog_v1.json apps/api/tests/unit/test_workflow_planner_resolver.py
git diff --cached --check
git commit -m "feat: resolve evidence-gated workflow routes"
~~~

Run only under task-level commit authorization.



---

### Task 6: Assemble And Fingerprint The Pure WorkflowPlan Preview

**Files:**
- Modify apps/api/src/data_intelligence_hub/schemas/workflow_planner.py.
- Modify apps/api/src/data_intelligence_hub/services/workflow_planner/fingerprint.py.
- Create apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py.
- Modify apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py.
- Modify apps/api/tests/unit/test_workflow_planner_schema.py.
- Create apps/api/tests/unit/test_workflow_planner_fingerprint.py.
- Create apps/api/tests/unit/test_workflow_planner.py.

**Interfaces:**
- Consumes: normalization, query, template, policy, resolver, Catalog, and injected runtime metadata.
- Produces: compute_catalog_snapshot_id(), build_preview_fingerprint_payload(), compute_preview_fingerprint(), assemble_workflow_plan_preview(), and build_workflow_plan_preview().

**Execution correction (2026-07-12):**
- The advanced view in Task 11 must consume backend facts rather than reconstructing them. Before Planner assembly, extend `WorkflowPlanPreview` with required `route_requirements`, `mode_template_version`, and `query_versions` fields, and lock them in the Task 1 schema regression test.

- [x] **Step 1: Write failing Catalog Snapshot and Fingerprint tests**

~~~python
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Iterator
from uuid import UUID

import pytest

from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_planner import (
    PlanningInput,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

PERIODIC_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "periodic_monitoring_request_v1.json"
)
SYNTHETIC_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "synthetic_capability_catalog_v1.json"
)


def build_periodic_preview(
    *,
    scope_ref: str,
    request_id: str,
) -> WorkflowPlanPreview:
    payload = json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8"))
    payload["scopes"][0]["scope_ref"] = scope_ref
    return build_workflow_plan_preview(
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
        planning_input=PlanningInput.model_validate(payload),
        catalog=get_capability_catalog(),
        generated_at=datetime(2026, 7, 12, tzinfo=UTC),
        request_id=request_id,
    )


def test_catalog_snapshot_ignores_generated_at_only() -> None:
    catalog = get_capability_catalog()
    shifted = catalog.model_copy(
        update={"generated_at": catalog.generated_at + timedelta(days=1)}
    )
    assert compute_catalog_snapshot_id(catalog) == compute_catalog_snapshot_id(shifted)

    changed = catalog.model_copy(
        update={
            "assertions": [
                catalog.assertions[0].model_copy(
                    update={"source_resource_group": "changed"}
                ),
                *catalog.assertions[1:],
            ]
        }
    )
    assert compute_catalog_snapshot_id(catalog) != compute_catalog_snapshot_id(changed)


def test_scope_ref_and_runtime_metadata_do_not_change_preview_fingerprint() -> None:
    first = build_periodic_preview(scope_ref="scope-1", request_id="req-1")
    second = build_periodic_preview(scope_ref="renamed", request_id="req-2")
    assert first.preview_fingerprint == second.preview_fingerprint
    assert first.request_id != second.request_id
    assert first.scope_ref_map != second.scope_ref_map
~~~

- [x] **Step 2: Run tests and verify the red state**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_fingerprint.py tests/unit/test_workflow_planner.py -q
~~~

Expected: FAIL because Catalog Snapshot and Planner assembly functions do not exist.

- [x] **Step 3: Extend fingerprint.py with exact canonical Catalog rules**

compute_catalog_snapshot_id must:

- model_dump(mode="json");
- remove only generated_at;
- sort implementations/assertions/evidence by stable ID;
- sort set-like nested lists including required_credentials, supported_endpoints, region_scope, purpose_scope, auth_scope, and evidence_refs;
- sort constraints by constraint_type, severity, code, and canonical details;
- recursively sort object keys;
- use UTF-8 compact JSON and SHA-256;
- return sha256:<hex>.

WorkflowPlanFingerprintPayload includes:

    planner_contract_version
    fingerprint_input
    catalog_snapshot_id
    policy_version
    mode_template_version
    query_versions
    candidate_fixture_version
    semantic_query_terms
    semantic_steps
    semantic_compiled_queries
    route_plans
    coverage
    budget_summary
    limitations
    semantic_decision_trace

It excludes project_id, generated_at, request_id, scope_ref_map, source_scope_refs, input_diagnostics, and every raw scope_ref.

- [x] **Step 4: Implement the pure Planner entrypoint**

~~~python
def build_workflow_plan_preview(
    *,
    project_id: UUID,
    planning_input: PlanningInput,
    catalog: CapabilityCatalog,
    generated_at: datetime,
    request_id: str,
    candidate_adapter: CandidateExpansionAdapter | None = None,
    query_compilers: Mapping[PlatformId, PlatformQueryCompiler] | None = None,
    readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None = None,
) -> WorkflowPlanPreview:
    normalization = normalize_planning_input(planning_input)
    adapter = candidate_adapter or FixtureCandidateExpansionAdapter.from_default_fixture()
    query_terms = build_query_terms(
        normalization,
        candidate_adapter=adapter,
    )
    query_result = compile_platform_queries(
        normalization,
        query_terms,
        compilers=(
            default_platform_query_compilers()
            if query_compilers is None
            else query_compilers
        ),
    )
    template_result = build_workflow_template(
        normalization.normalized_input,
        query_result,
    )
    policy = get_routing_policy(planning_input.policy_profile)
    readiness = (
        readiness_snapshots
        if readiness_snapshots is not None
        else derive_product_readiness(catalog)
    )
    route_plans = resolve_route_plans(
        template_result.requirements,
        catalog,
        policy=policy,
        readiness_snapshots=readiness,
    )
    return assemble_workflow_plan_preview(
        project_id=project_id,
        generated_at=generated_at,
        request_id=request_id,
        normalization=normalization,
        query_result=query_result,
        template_result=template_result,
        route_plans=route_plans,
        catalog=catalog,
        policy=policy,
        candidate_fixture_version=adapter.version,
    )
~~~

The function signature must not accept AsyncSession, repository, Settings, Provider, Actor, browser, or LLM objects.

planning_status:

- resolved when every Requirement has a verified Primary;
- partially_resolved when at least one Requirement resolves or proposes partial and at least one is partial/held;
- held when there is no routeable Requirement or none resolves/proposes partial.

WorkflowPlanPreview fixes provider_call, actor_run, browser_run, llm_call, workflow_run_created, database_write, and execution_authorized to false.

- [x] **Step 5: Prove both Flows, synthetic routing, and p95**

Add tests that:

- periodic and batch canonical previews are deterministic held;
- batch preserves seed_url_unclassified in input diagnostics;
- synthetic Catalog resolves all four required operations;
- simple/advanced consumers can share the same Fingerprint fields;
- every semantic input/Catalog/Policy/Query/Fixture/template change changes the Fingerprint;
- list order and scope_ref changes do not;
- an explicitly empty query_compilers mapping is preserved, yields compiler_missing held routes, and is never replaced by the default registry;
- 50 warmed Fixture runs measured with time.perf_counter have p95 below 3 seconds;
- the Planner assembly/fingerprint test modules import no network, database, Provider, browser, or LLM clients.

Isolate the existing Catalog cache around every Planner test:

~~~python
@pytest.fixture(autouse=True)
def isolate_capability_catalog_cache() -> Iterator[None]:
    clear_capability_catalog_cache()
    yield
    clear_capability_catalog_cache()
~~~

Place this small autouse fixture in each Planner test module that calls the cached loader: test_workflow_planner_resolver.py, test_workflow_planner_fingerprint.py, test_workflow_planner.py, and test_workflow_planner_preview.py. Import Iterator, pytest, and clear_capability_catalog_cache at module scope. Add a mutation regression proving that changing a returned deep copy does not affect the next get_capability_catalog() result. Do not add a repository-wide autouse conftest fixture.

Use the nearest-rank p95 calculation and always print one machine-copyable evidence line, including on success:

~~~python
def test_explicit_empty_compiler_registry_stays_fail_closed() -> None:
    payload = PlanningInput.model_validate_json(
        PERIODIC_FIXTURE.read_text(encoding="utf-8")
    )
    catalog = CapabilityCatalog.model_validate_json(
        SYNTHETIC_FIXTURE.read_text(encoding="utf-8")
    )

    preview = build_workflow_plan_preview(
        project_id=UUID("00000000-0000-0000-0000-000000000001"),
        planning_input=payload,
        catalog=catalog,
        generated_at=datetime(2026, 7, 12, tzinfo=UTC),
        request_id="missing-compilers",
        query_compilers={},
    )

    compiler_held_routes = [
        route
        for route in preview.route_plans
        if any(reason.code == "compiler_missing" for reason in route.exclusion_reasons)
    ]
    assert compiler_held_routes
    assert all(route.status == "held" for route in compiler_held_routes)
    assert all(route.primary_implementation is None for route in compiler_held_routes)


def test_fixture_preview_p95_is_below_three_seconds() -> None:
    payload = PlanningInput.model_validate_json(
        PERIODIC_FIXTURE.read_text(encoding="utf-8")
    )
    catalog = get_capability_catalog()

    for index in range(5):
        build_workflow_plan_preview(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            planning_input=payload,
            catalog=catalog,
            generated_at=datetime(2026, 7, 12, tzinfo=UTC),
            request_id=f"warmup-{index}",
        )

    durations: list[float] = []
    for index in range(50):
        started = perf_counter()
        build_workflow_plan_preview(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
            planning_input=payload,
            catalog=catalog,
            generated_at=datetime(2026, 7, 12, tzinfo=UTC),
            request_id=f"measured-{index}",
        )
        durations.append(perf_counter() - started)

    p95_seconds = sorted(durations)[math.ceil(len(durations) * 0.95) - 1]
    preview_p95_ms = p95_seconds * 1000
    print(f"preview_p95_ms={preview_p95_ms:.3f}")
    assert p95_seconds < 3.0
~~~

Place the fingerprint and p95 tests in test_workflow_planner_fingerprint.py so its import block is complete; place Flow assembly and synthetic route tests in test_workflow_planner.py.

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_fingerprint.py tests/unit/test_workflow_planner.py -q
uv run pytest tests/unit/test_workflow_planner_fingerprint.py -q -s -k fixture_preview_p95
uv run ruff check src/data_intelligence_hub/services/workflow_planner/fingerprint.py src/data_intelligence_hub/services/workflow_planner/planner.py tests/unit/test_workflow_planner_fingerprint.py tests/unit/test_workflow_planner.py
uv run mypy src/data_intelligence_hub/services/workflow_planner/fingerprint.py src/data_intelligence_hub/services/workflow_planner/planner.py tests/unit/test_workflow_planner_fingerprint.py tests/unit/test_workflow_planner.py
~~~

Expected: all commands exit 0 and the performance assertion records p95 below 3 seconds.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/api/src/data_intelligence_hub/services/workflow_planner/__init__.py apps/api/src/data_intelligence_hub/services/workflow_planner/fingerprint.py apps/api/src/data_intelligence_hub/services/workflow_planner/planner.py apps/api/tests/unit/test_workflow_planner_fingerprint.py apps/api/tests/unit/test_workflow_planner.py
git diff --cached --check
git commit -m "feat: assemble deterministic workflow plan previews"
~~~

Run only under task-level commit authorization.



---

### Task 7: Expose The Authenticated Project-Scoped Preview API

**Files:**
- Modify apps/api/src/data_intelligence_hub/services/exceptions.py.
- Modify apps/api/src/data_intelligence_hub/services/project_service.py.
- Create apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py.
- Modify apps/api/src/data_intelligence_hub/main.py.
- Create apps/api/tests/integration/test_workflow_planner_preview.py.

**Interfaces:**
- Consumes: build_workflow_plan_preview(), get_capability_catalog(), AuthContext, SessionDep, and workspace-scoped Project lookup.
- Produces: get_active_project_or_raise() and POST /api/projects/{project_id}/workflow-plans/preview.

- [x] **Step 1: Add service errors and active Project lookup tests**

Add:

~~~python
class ProjectNotActiveError(ServiceError):
    message = "project_not_active"


class WorkflowPlannerDependencyUnavailableError(ServiceError):
    message = "workflow_planner_dependency_unavailable"
~~~

Add to project_service.py:

~~~python
async def get_active_project_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
) -> Project:
    project = await get_project_or_raise(session, workspace, project_id)
    if project.status != "active":
        raise ProjectNotActiveError
    return project
~~~

Write integration assertions for 404 cross-workspace and 409 archived before registering the route.

- [x] **Step 2: Write failing endpoint tests**

Cover:

- unauthenticated 401;
- valid canonical Preview returns 200 held;
- body project_id and scope_key return 422;
- a periodic platformless youtu.be Seed URL derives youtube and returns a normal 200 Preview;
- a periodic unclassified Seed URL with no declared/default platform returns 422 with loc=["body", "scopes", 0, "platforms"];
- missing/cross-workspace Project returns 404;
- archived Project returns 409 project_not_active;
- Catalog load failure returns 503;
- unexpected Planner failure returns 500 with X-Request-ID;
- provider_call/actor_run/browser_run/llm_call/workflow_run_created/database_write/execution_authorized are false.

~~~bash
cd apps/api
uv run pytest tests/integration/test_workflow_planner_preview.py -q
~~~

Expected: FAIL with 404 because the route is not registered.

- [x] **Step 3: Implement the route**

~~~python
from time import perf_counter

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["workflow-plans"])


@router.post(
    "/{project_id}/workflow-plans/preview",
    response_model=WorkflowPlanPreview,
)
async def preview_workflow_plan_item(
    project_id: uuid.UUID,
    payload: PlanningInput,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> WorkflowPlanPreview:
    started = perf_counter()
    request_id = str(uuid.uuid4())
    response.headers["X-Request-ID"] = request_id
    project = await get_active_project_or_raise(
        session,
        context.workspace,
        project_id,
    )
    catalog = get_capability_catalog()
    preview = build_workflow_plan_preview(
        project_id=project.id,
        planning_input=payload,
        catalog=catalog,
        generated_at=datetime.now(UTC),
        request_id=request_id,
    )
    logger.info(
        "workflow_plan_preview_generated",
        request_id=request_id,
        project_id=str(project.id),
        flow_mode=preview.flow_mode.value,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        preview_fingerprint=preview.preview_fingerprint,
        planning_status=preview.planning_status.value,
        route_requirement_count=len(preview.route_plans),
        resolved_count=sum(route.status == "resolved" for route in preview.route_plans),
        held_count=sum(route.status == "held" for route in preview.route_plans),
        duration_ms=round((perf_counter() - started) * 1000, 3),
    )
    return preview
~~~

Wrap the call to map:

- ProjectNotFoundError to 404;
- ProjectNotActiveError to 409;
- WorkflowPlannerInputError to 422 with detail=exc.issues;
- CapabilityCatalogLoadError and WorkflowPlannerDependencyUnavailableError to 503;
- WorkflowPlannerTopologyError and unexpected exceptions to 500.

Every raised HTTPException carries X-Request-ID. Use structlog.exception for 500 with request_id, project_id, and flow_mode. The success/held info event must contain every field shown above. Never log raw term/URL values, request bodies, credentials, or Secret-derived data.

Register:

~~~python
from data_intelligence_hub.api.routes.workflow_plans import (
    router as workflow_plans_router,
)
~~~

and immediately after projects_router:

~~~python
app.include_router(workflow_plans_router, prefix="/api/projects")
~~~

- [x] **Step 4: Prove zero writes with SQL capture and table counts**

In the integration fixture:

1. create the user, workspace, and Project;
2. record COUNT(*) for every Base.metadata.sorted_tables;
3. attach before_cursor_execute to engine.sync_engine;
4. clear captured statements;
5. call only the Preview endpoint;
6. remove the listener in finally;
7. recount every table;
8. assert counts are identical;
9. assert no captured statement begins with INSERT, UPDATE, DELETE, CREATE, DROP, or ALTER after whitespace normalization.
10. repeat Preview with one Scope and with 20 equivalent valid Scopes, capture each request separately, and assert the SELECT count is equal; this proves Planner expansion adds no database N+1 reads.

Also inspect the pure Planner signature and assert it has no session parameter.

Monkeypatch workflow_plans.logger.info in the successful integration test and assert the event contains request_id, project_id, flow_mode, planner_contract_version, catalog_snapshot_id, policy_version, preview_fingerprint, planning_status, route_requirement_count, resolved_count, held_count, and non-negative duration_ms, with no raw term or Seed URL key/value.

- [x] **Step 5: Run API and compatibility gates**

~~~bash
cd apps/api
uv run pytest tests/integration/test_workflow_planner_preview.py -q
uv run pytest tests/unit/test_capability_catalog.py tests/unit/test_capability_matrix.py tests/integration/test_capability_routes.py tests/integration/test_workflow_planner_preview.py -q
uv run ruff check src/data_intelligence_hub/api/routes/workflow_plans.py src/data_intelligence_hub/services/project_service.py src/data_intelligence_hub/services/exceptions.py src/data_intelligence_hub/main.py tests/integration/test_workflow_planner_preview.py
uv run mypy src/data_intelligence_hub/api/routes/workflow_plans.py src/data_intelligence_hub/services/project_service.py src/data_intelligence_hub/services/exceptions.py src/data_intelligence_hub/main.py tests/integration/test_workflow_planner_preview.py
~~~

Expected: all commands exit 0; the canonical API returns held and zero-write assertions pass.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/src/data_intelligence_hub/services/project_service.py apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py apps/api/src/data_intelligence_hub/main.py apps/api/tests/integration/test_workflow_planner_preview.py
git diff --cached --check
git commit -m "feat: expose workflow plan preview api"
~~~

Run only under task-level commit authorization.



---

### Task 8: Make Project Selection Shared, Synchronized, And Honest

**Files:**
- Create apps/web/src/components/layout/project-selection-provider.tsx.
- Modify apps/web/src/lib/project-selection.ts.
- Modify apps/web/src/components/layout/project-selector.tsx.
- Modify apps/web/src/components/layout/app-shell.tsx.
- Modify apps/web/src/components/layout/navigation.ts.
- Create apps/web/tests/unit/project-selection.test.ts.
- Modify apps/web/tests/unit/navigation.test.ts.

**Interfaces:**
- Consumes: existing listProjects(), selectedProjectStorageKey, data-intelligence-hub:project-selection event, and active Project contract.
- Produces: ProjectSelectionProvider, useProjectSelection(), markProjectFilterApplied(), clearProjectFilterApplied(), and query-aware Planner navigation entries.

- [x] **Step 1: Write failing Project-selection pure tests**

~~~typescript
import { describe, expect, it } from "vitest";

import {
  isProjectFilterApplied,
  projectSelectionEventName,
} from "@/lib/project-selection";

describe("shared project selection", () => {
  it("reuses the existing same-tab event name", () => {
    expect(projectSelectionEventName).toBe(
      "data-intelligence-hub:project-selection",
    );
  });

  it("marks filtering only for the matching successful planner project", () => {
    expect(
      isProjectFilterApplied({
        pathname: "/automation/planner",
        selectedProjectId: "project-a",
        appliedProjectId: "project-a",
      }),
    ).toBe(true);
    expect(
      isProjectFilterApplied({
        pathname: "/dashboard",
        selectedProjectId: "project-a",
        appliedProjectId: "project-a",
      }),
    ).toBe(false);
  });
});
~~~

- [x] **Step 2: Run unit tests and verify the red state**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/project-selection.test.ts tests/unit/navigation.test.ts
~~~

Expected: FAIL because provider helpers and Planner navigation children do not exist.

- [x] **Step 3: Add the shared Provider**

Expose:

~~~typescript
export type ProjectSelectionContextValue = {
  projects: Project[];
  selectedProject: Project | null;
  selectedProjectId: string | null;
  loading: boolean;
  projectListError: string | null;
  preferenceError: string | null;
  filterApplied: boolean;
  selectProject: (projectId: string | null) => void;
  markProjectFilterApplied: (projectId: string) => void;
  clearProjectFilterApplied: () => void;
};

export function ProjectSelectionProvider(props: {
  children: React.ReactNode;
}): React.ReactNode;

export function useProjectSelection(): ProjectSelectionContextValue;
~~~

Provider rules:

- fetch active Projects once;
- resolve stored selection against the fetched list;
- listen to data-intelligence-hub:project-selection for same-tab changes;
- listen to storage only for selectedProjectStorageKey for cross-tab changes;
- revalidate both event values against active Projects;
- clear appliedProjectId on selection/path change;
- filterApplied is true only on /automation/planner when selectedProjectId equals the last successful Preview project;
- 200 held Preview is still a successful binding;
- unmount removes both listeners.

Wrap the AppShell content in ProjectSelectionProvider. Refactor ProjectSelector to consume the Hook, remove its duplicate listProjects lifecycle, and render data-project-filter-applied from filterApplied.

- [x] **Step 4: Add the two navigation children**

Under the existing 采集工作流 primary entry add:

~~~typescript
{ label: "创建监测项目", href: "/automation/planner?mode=periodic_monitoring" },
{ label: "批量检索与解析", href: "/automation/planner?mode=batch_research" },
~~~

Extend navigation tests so each query activates only its matching child and /automation still activates the parent.

- [x] **Step 5: Run the focused Web gate**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/project-selection.test.ts tests/unit/navigation.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm --dir apps/web lint
~~~

Expected: unit, typecheck, and lint exit 0; no existing non-Planner page reports applied=true.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/web/src/components/layout/project-selection-provider.tsx apps/web/src/lib/project-selection.ts apps/web/src/components/layout/project-selector.tsx apps/web/src/components/layout/app-shell.tsx apps/web/src/components/layout/navigation.ts apps/web/tests/unit/project-selection.test.ts apps/web/tests/unit/navigation.test.ts
git diff --cached --check
git commit -m "feat: share planner project context"
~~~

Run only under task-level commit authorization.



---

### Task 9: Add Web Preview Contracts, Field Errors, And Explicit Test Fixtures

**Files:**
- Create apps/web/src/types/workflow-planner.ts.
- Create apps/web/src/lib/api/workflow-plans.ts.
- Create apps/web/src/lib/workflow-planner-mock.ts.
- Modify apps/web/src/lib/api/client.ts.
- Modify apps/web/src/lib/api/projects.ts.
- Modify apps/web/playwright.config.ts.
- Create apps/web/tests/unit/workflow-plans-api.test.ts.

**Interfaces:**
- Consumes: backend snake_case WorkflowPlan contract and existing apiFetch/mockApiEnabled.
- Produces: typed DTO/domain contracts, ApiValidationIssue, backward-compatible ApiRequestError, mapPlanningInputToDto(), previewWorkflowPlan(), mapWorkflowPlanPreview(), and mapPlannerValidationIssues().

- [x] **Step 1: Write failing API-client tests**

~~~typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import {
  mapPlanningInputToDto,
  mapPlannerValidationIssues,
  previewWorkflowPlan,
} from "@/lib/api/workflow-plans";
import type { PlanningInput } from "@/types/workflow-planner";

const validPlanningInput: PlanningInput = {
  flowMode: "batch_research",
  scopes: [
    {
      scopeRef: "scope-1",
      scopeType: "topic",
      canonicalTerm: "running shoes",
      aliases: [],
      includeTerms: [],
      excludeTerms: [],
      officialAccounts: [],
      seedUrls: [],
      languages: ["en"],
      regions: ["US"],
      platforms: ["reddit"],
      matchMode: "phrase",
    },
  ],
  defaultLanguages: ["en"],
  defaultRegions: ["US"],
  defaultPlatforms: ["reddit"],
  deliveryIntent: { outputs: ["dataset"] },
  policyProfile: "market_monitoring_balanced",
  purpose: "market_research",
  requiredFields: ["id", "url", "text"],
  optionalFields: ["author"],
  budgetCeiling: null,
  rateLimitIntent: null,
  retentionIntent: { days: 30 },
  allowPartialDegradation: false,
};

describe("workflow plan preview api", () => {
  it("preserves FastAPI validation locations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: [
              {
                loc: ["body", "scopes", 0, "canonical_term"],
                msg: "Field required",
                type: "missing",
              },
            ],
          }),
          {
            status: 422,
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    );

    await expect(
      previewWorkflowPlan("project-a", validPlanningInput),
    ).rejects.toMatchObject({
      status: 422,
      validationIssues: [
        {
          loc: ["body", "scopes", 0, "canonical_term"],
          msg: "Field required",
          type: "missing",
        },
      ],
    } satisfies Partial<ApiRequestError>);
  });

  it("maps backend locations to stable form ids", () => {
    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body", "scopes", 0, "canonical_term"],
          msg: "Field required",
          type: "missing",
        },
      ]),
    ).toEqual({
      "planner-scope-0-canonical-term": "Field required",
    });

    expect(
      mapPlannerValidationIssues([
        {
          loc: ["body", "scopes", 0, "platforms"],
          msg: "periodic_effective_platform_required",
          type: "value_error",
        },
      ]),
    ).toEqual({
      "planner-scope-0-platforms": "periodic_effective_platform_required",
    });
  });

  it("omits schedule_intent from batch requests", () => {
    expect(mapPlanningInputToDto(validPlanningInput)).not.toHaveProperty(
      "schedule_intent",
    );
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});
~~~

- [x] **Step 2: Run the test and verify the red state**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plans-api.test.ts
~~~

Expected: FAIL because workflow-plans.ts and validationIssues do not exist.

- [x] **Step 3: Extend ApiRequestError without breaking existing callers**

~~~typescript
export type ApiValidationIssue = {
  loc: Array<string | number>;
  msg: string;
  type?: string;
};

export class ApiRequestError extends Error {
  status: number;
  validationIssues: ApiValidationIssue[];
  requestId: string | null;

  constructor(
    status: number,
    message: string,
    options: {
      validationIssues?: ApiValidationIssue[];
      requestId?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.validationIssues = options.validationIssues ?? [];
    this.requestId = options.requestId ?? null;
  }
}
~~~

Change the error reader to return message plus validationIssues, and copy X-Request-ID from the response header. Existing login-panel behavior continues to read caught.message and caught.status.

- [x] **Step 4: Define Web contracts and the Preview client**

Reuse CapabilityPlatform, CapabilityResourceType, CapabilityOperation, and CapabilityStatus from types/capability.ts. Define every Planner request/response field from the backend using snake_case DTO types, then map once into camelCase domain types.

PlanningInput is a discriminated union: periodic_monitoring requires scheduleIntent, while batch_research declares scheduleIntent?: never. mapPlanningInputToDto must omit the schedule_intent key entirely for batch; neither null nor undefined may be serialized.

~~~typescript
export async function previewWorkflowPlan(
  projectId: string,
  input: PlanningInput,
  options: { signal?: AbortSignal } = {},
): Promise<WorkflowPlanPreview> {
  if (mockApiEnabled) {
    await waitForWorkflowPlannerTestDelay(projectId, input);
    return buildMockWorkflowPlanPreview(projectId, input);
  }
  const response = await apiFetch<WorkflowPlanPreviewDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/preview`,
    {
      method: "POST",
      body: JSON.stringify(mapPlanningInputToDto(input)),
      signal: options.signal,
    },
  );
  return mapWorkflowPlanPreview(response);
}
~~~

Import buildMockWorkflowPlanPreview and waitForWorkflowPlannerTestDelay from workflow-planner-mock.ts. There is no catch/fallback around the real apiFetch call.

- [x] **Step 5: Add explicit mock scenarios**

~~~typescript
export type WorkflowPlannerMockScenario =
  | "canonical-held"
  | "synthetic-partial"
  | "synthetic-resolved"
  | "service-unavailable";
~~~

Default mock Projects return canonical-held. Only when NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true may listProjects append active fixture Projects for partial/resolved/unavailable scenarios. workflow-planner-mock.ts maps those fixed IDs to static, schema-valid Preview objects.

Use these exact test-only Project identities so unit and E2E tests do not depend on array order:

| Project ID | Project name | Scenario |
|---|---|---|
| 00000000-0000-4000-8000-000000000031 | Planner Fixture - Canonical Held | canonical-held |
| 00000000-0000-4000-8000-000000000032 | Planner Fixture - Synthetic Partial | synthetic-partial |
| 00000000-0000-4000-8000-000000000033 | Planner Fixture - Synthetic Resolved | synthetic-resolved |
| 00000000-0000-4000-8000-000000000034 | Planner Fixture - Service Unavailable | service-unavailable |

All four are active, domain=social, and appear only under the explicit test variable. Production and ordinary mock builds must not contain them.

For the stale-response E2E only, waitForWorkflowPlannerTestDelay is enabled by the same test variable and recognizes exact first-scope canonical terms:

~~~typescript
export async function waitForWorkflowPlannerTestDelay(
  projectId: string,
  input: PlanningInput,
): Promise<void> {
  if (
    process.env.NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES !== "true" ||
    projectId !== "00000000-0000-4000-8000-000000000033"
  ) {
    return;
  }
  const term = input.scopes[0]?.canonicalTerm?.trim().toLowerCase();
  const delayMs = term === "e2e-slow-first" ? 250 : term === "e2e-fast-second" ? 10 : 0;
  if (delayMs > 0) {
    await new Promise((resolve) => globalThis.setTimeout(resolve, delayMs));
  }
}

export function resolveWorkflowPlannerMockFingerprint(
  projectId: string,
  input: PlanningInput,
  fallback: string,
): string {
  if (
    process.env.NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES !== "true" ||
    projectId !== "00000000-0000-4000-8000-000000000033"
  ) {
    return fallback;
  }
  const term = input.scopes[0]?.canonicalTerm?.trim().toLowerCase();
  if (term === "e2e-slow-first") {
    return `sha256:${"1".repeat(64)}`;
  }
  if (term === "e2e-fast-second") {
    return `sha256:${"2".repeat(64)}`;
  }
  return fallback;
}
~~~

buildMockWorkflowPlanPreview must assign previewFingerprint from resolveWorkflowPlannerMockFingerprint before returning its single Preview object. The two magic terms are acceptance-fixture controls, never shown as product presets and never active without NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true.

The fixture responses must include:

- canonical-held: no Primary, exclusion candidate_not_execution_eligible;
- synthetic-partial: approval_required=true and execution_authorized=false;
- synthetic-resolved: Primary, Fallback, enabled Shadow, execution_authorized=false;
- service-unavailable: throw ApiRequestError with status 503;
- all scenarios: providerCall=false, actorRun=false, browserRun=false, llmCall=false, workflowRunCreated=false, databaseWrite=false.

Modify the local Playwright webServer command only:

~~~typescript
command: `NEXT_PUBLIC_MOCK_API=true NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true corepack pnpm exec next dev --port ${port}`,
~~~

Do not set this variable in production build commands.

- [x] **Step 6: Run API contract and static gates**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-plans-api.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm --dir apps/web lint
~~~

Expected: all commands exit 0; API errors retain field locations and real failures never become Mock success.

- [ ] **Step 7: Optional authorized commit**

~~~bash
git add -- apps/web/src/types/workflow-planner.ts apps/web/src/lib/api/workflow-plans.ts apps/web/src/lib/workflow-planner-mock.ts apps/web/src/lib/api/client.ts apps/web/src/lib/api/projects.ts apps/web/playwright.config.ts apps/web/tests/unit/workflow-plans-api.test.ts
git diff --cached --check
git commit -m "feat: add workflow planner web contracts"
~~~

Run only under task-level commit authorization.



---

### Task 10: Build The Dual-Mode Four-Step Planner Form

**Files:**
- Create apps/web/src/app/automation/planner/page.tsx.
- Create apps/web/src/lib/workflow-planner.ts.
- Create apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx.
- Create apps/web/src/components/workflow-planner/workflow-planner-stepper.tsx.
- Create apps/web/src/components/workflow-planner/planner-mode-step.tsx.
- Create apps/web/src/components/workflow-planner/planner-scope-step.tsx.
- Create apps/web/src/components/workflow-planner/planner-constraints-step.tsx.
- Create apps/web/tests/unit/workflow-planner.test.ts.

**Interfaces:**
- Consumes: PlanningInput Web type and useProjectSelection().
- Produces: parseWorkflowPlannerMode(), createWorkflowPlannerDraft(), createScopeDraft(), validatePlannerStep(), buildPlanningInput(), and the four-step accessible form.

- [x] **Step 1: Write failing form-logic tests**

~~~typescript
import { describe, expect, it } from "vitest";

import {
  buildPlanningInput,
  createScopeDraft,
  createWorkflowPlannerDraft,
  parseWorkflowPlannerMode,
  validatePlannerStep,
} from "@/lib/workflow-planner";

describe("workflow planner form", () => {
  it("parses only the two supported modes", () => {
    expect(parseWorkflowPlannerMode("periodic_monitoring")).toBe(
      "periodic_monitoring",
    );
    expect(parseWorkflowPlannerMode(["batch_research"])).toBe("batch_research");
    expect(parseWorkflowPlannerMode("unknown")).toBe("periodic_monitoring");
  });

  it("creates stable non-random scope refs", () => {
    expect(createScopeDraft(1, "brand").scopeRef).toBe("scope-1");
    expect(createScopeDraft(2, "topic").scopeRef).toBe("scope-2");
  });

  it("requires schedule only for periodic mode", () => {
    const periodic = createWorkflowPlannerDraft("periodic_monitoring");
    const periodicIssues = validatePlannerStep(periodic, "constraints");
    expect(periodicIssues.map((issue) => issue.fieldId)).toContain(
      "planner-schedule-cadence",
    );

    const batch = createWorkflowPlannerDraft("batch_research");
    expect(buildPlanningInput(batch)).not.toHaveProperty("scheduleIntent");
  });

  it("allows periodic Seed URL input to reach backend platform classification", () => {
    const periodic = createWorkflowPlannerDraft("periodic_monitoring");
    periodic.scheduleIntent = { cadence: "daily", timezone: "UTC" };
    periodic.defaultPlatforms = [];
    periodic.scopes[0].platforms = [];
    periodic.scopes[0].seedUrls = ["https://youtu.be/demo"];

    expect(
      validatePlannerStep(periodic, "constraints").map(
        (issue) => issue.fieldId,
      ),
    ).not.toContain("planner-scope-0-platforms");
  });
});
~~~

- [x] **Step 2: Run the test and verify the red state**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-planner.test.ts
~~~

Expected: FAIL because lib/workflow-planner.ts does not exist.

- [x] **Step 3: Implement the pure form model**

~~~typescript
export type PlannerStep = "mode" | "scopes" | "constraints" | "preview";

export type PlannerFieldIssue = {
  fieldId: string;
  message: string;
};

export type WorkflowPlannerDraft = {
  mode: WorkflowPlannerMode;
  purpose: "brand_monitoring" | "market_research" | "competitive_research";
  scopes: MonitoringScopeFormDraft[];
  defaultLanguages: string[];
  defaultRegions: string[];
  defaultPlatforms: CapabilityPlatform[];
  scheduleIntent: ScheduleIntent | null;
  deliveryIntent: DeliveryIntent | null;
  requiredFields: string[];
  optionalFields: string[];
  budgetCeiling: BudgetCeiling | null;
  rateLimitIntent: RateLimitIntent | null;
  retentionIntent: RetentionIntent | null;
  allowPartialDegradation: boolean;
  revision: number;
};
~~~

Implement exact rules:

- parse mode from string/string-array/null/undefined and default to periodic_monitoring;
- initial draft has one scope-1 and no schedule value;
- add Scope uses the next monotonic sequence and never reuses a removed ref;
- brand/category/competitor require canonicalTerm;
- topic/campaign require canonical/alias/include/account/Seed URL;
- periodic local validation requires schedule plus either a declared/default platform or at least one Seed URL; it must not reject platformless Seed input before backend classification;
- do not duplicate the seven-host classifier in React. The backend remains authoritative: a known Seed URL derives the platform, while an unclassified periodic URL returns 422 and maps to planner-scope-{index}-platforms;
- batch rejects schedule and accepts Seed-URL-only;
- required/optional fields normalize, de-duplicate, and cannot overlap;
- buildPlanningInput removes form-only revision and sends no project_id/scope_key/readiness;
- buildPlanningInput omits scheduleIntent for batch; mapPlanningInputToDto therefore emits no schedule_intent key;
- validatePlannerStep returns stable DOM field IDs.

- [x] **Step 4: Add the Next 15 route**

~~~typescript
type WorkflowPlannerPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function WorkflowPlannerPage({
  searchParams,
}: WorkflowPlannerPageProps) {
  const resolved = await searchParams;
  const mode = parseWorkflowPlannerMode(resolved.mode);
  return (
    <AppShell
      title="Workflow Planner"
      description="从 MonitoringScope 生成可解释的采集计划预览"
      brief="阶段一只生成 Fixture Preview；不保存、不激活、不调用 Provider。"
      signals={[
        "双模式规划",
        "Candidate 不可执行",
        "production unchanged",
      ]}
    >
      <WorkflowPlannerWorkspace initialMode={mode} />
    </AppShell>
  );
}
~~~

- [x] **Step 5: Implement the first three form steps**

Requirements:

- Stepper uses an ordered list with aria-current="step".
- Mode step exposes two radio options and purpose.
- Scope step supports add/remove and all approved fields.
- Constraints step supports platform/language/region/fields/budget/rate/retention and periodic schedule/delivery.
- Batch mode never renders cadence controls.
- Next validates only the current step.
- On validation failure, requestAnimationFrame focuses the first element with aria-invalid="true".
- Render the validated controls with the exact IDs planner-scope-{index}-type, planner-scope-{index}-canonical-term, planner-scope-{index}-seed-url-{urlIndex}, planner-scope-{index}-platforms, planner-platform-{platform}, planner-schedule-cadence, and planner-schedule-timezone; labels use htmlFor so keyboard and E2E selectors share the same accessibility contract. Render planner-scope-{index}-platforms on the Scope platform fieldset with tabIndex={-1}, aria-invalid, and aria-describedby so a server 422 can focus that real element. The add-Scope control has accessible name “添加 Scope”.
- Back preserves all values.
- Preview step renders an honest empty state until Task 11 connects the API.
- Missing Project shows “请先选择一个 active Project” and disables Generate Preview.
- There are no Save or Activate buttons.

- [x] **Step 6: Run form and static gates**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-planner.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm --dir apps/web lint
~~~

Expected: all commands exit 0 and /automation/planner builds through typecheck.

- [ ] **Step 7: Optional authorized commit**

~~~bash
git add -- apps/web/src/app/automation/planner/page.tsx apps/web/src/lib/workflow-planner.ts apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx apps/web/src/components/workflow-planner/workflow-planner-stepper.tsx apps/web/src/components/workflow-planner/planner-mode-step.tsx apps/web/src/components/workflow-planner/planner-scope-step.tsx apps/web/src/components/workflow-planner/planner-constraints-step.tsx apps/web/tests/unit/workflow-planner.test.ts
git diff --cached --check
git commit -m "feat: add workflow planner form"
~~~

Run only under task-level commit authorization.



---

### Task 11: Connect Preview Requests, Stale Protection, And Two Views

**Files:**
- Modify apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx.
- Create apps/web/src/components/workflow-planner/workflow-plan-preview.tsx.
- Create apps/web/src/components/workflow-planner/workflow-plan-simple-view.tsx.
- Create apps/web/src/components/workflow-planner/workflow-plan-advanced-view.tsx.
- Modify apps/web/src/lib/workflow-planner.ts.
- Modify apps/web/tests/unit/workflow-planner.test.ts.

**Interfaces:**
- Consumes: previewWorkflowPlan(), ApiRequestError.validationIssues, form revision, selected Project, and Project selection applied-state methods.
- Produces: PreviewRequestState, shouldAcceptPreviewResponse(), invalidatePreviewRequest(), held rendering, retry, simple/advanced tabs, and a single shared Fingerprint.

- [x] **Step 1: Write request-state tests**

~~~typescript
import type { WorkflowPlanPreview } from "@/types/workflow-planner";
import {
  invalidatePreviewRequest,
  isPreviewSnapshotCurrent,
  shouldAcceptPreviewResponse,
  type PreviewRequestState,
  type PreviewSnapshot,
} from "@/lib/workflow-planner";

it("marks a successful preview stale when its semantic context changes", () => {
  const preview = {
    previewFingerprint: "sha256:test",
  } as WorkflowPlanPreview;
  const snapshot: PreviewSnapshot = {
    projectId: "project-a",
    mode: "periodic_monitoring",
    formRevision: 3,
    preview,
  };
  expect(
    isPreviewSnapshotCurrent(snapshot, {
      projectId: "project-a",
      mode: "periodic_monitoring",
      formRevision: 3,
    }),
  ).toBe(true);
  expect(
    isPreviewSnapshotCurrent(snapshot, {
      projectId: "project-a",
      mode: "periodic_monitoring",
      formRevision: 4,
    }),
  ).toBe(false);
});

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

it("ignores an older preview response that resolves after the latest one", async () => {
  const first = createDeferred<WorkflowPlanPreview>();
  const second = createDeferred<WorkflowPlanPreview>();
  let currentSequence = 1;
  let currentFingerprint: string | null = null;

  const settle = async (
    sequence: number,
    pending: Promise<WorkflowPlanPreview>,
  ) => {
    const preview = await pending;
    if (
      shouldAcceptPreviewResponse({
        responseSequence: sequence,
        currentSequence,
        responseContext: {
          projectId: "project-a",
          mode: "periodic_monitoring",
          formRevision: sequence,
        },
        currentContext: {
          projectId: "project-a",
          mode: "periodic_monitoring",
          formRevision: currentSequence,
        },
      })
    ) {
      currentFingerprint = preview.previewFingerprint;
    }
  };

  const firstRequest = settle(1, first.promise);
  currentSequence = 2;
  const secondRequest = settle(2, second.promise);
  second.resolve({ previewFingerprint: "sha256:new" } as WorkflowPlanPreview);
  await secondRequest;
  first.resolve({ previewFingerprint: "sha256:old" } as WorkflowPlanPreview);
  await firstRequest;

  expect(currentFingerprint).toBe("sha256:new");
});

it("leaves loading immediately when semantic context changes", () => {
  expect(
    invalidatePreviewRequest({ status: "loading", sequence: 7 }),
  ).toEqual({ status: "idle" });

  const state: PreviewRequestState = {
    status: "success",
    snapshot: {
      projectId: "project-a",
      mode: "periodic_monitoring",
      formRevision: 3,
      preview: { previewFingerprint: "sha256:old" } as WorkflowPlanPreview,
    },
    stale: false,
  };
  expect(invalidatePreviewRequest(state)).toMatchObject({
    status: "success",
    stale: true,
  });
});
~~~

- [x] **Step 2: Run the tests and verify the red state**

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-planner.test.ts
~~~

Expected: FAIL because PreviewSnapshot/currentness helpers do not exist.

- [x] **Step 3: Implement the request state**

~~~typescript
export type PreviewSnapshot = {
  projectId: string;
  mode: WorkflowPlannerMode;
  formRevision: number;
  preview: WorkflowPlanPreview;
};

export type PreviewRequestState =
  | { status: "idle" }
  | { status: "loading"; sequence: number; previous?: PreviewSnapshot }
  | { status: "success"; snapshot: PreviewSnapshot; stale: boolean }
  | {
      status: "error";
      message: string;
      requestId: string | null;
      fieldErrors: Record<string, string>;
    };

export type PreviewSemanticContext = {
  projectId: string;
  mode: WorkflowPlannerMode;
  formRevision: number;
};

export function shouldAcceptPreviewResponse(input: {
  responseSequence: number;
  currentSequence: number;
  responseContext: PreviewSemanticContext;
  currentContext: PreviewSemanticContext;
}): boolean {
  return (
    input.responseSequence === input.currentSequence &&
    input.responseContext.projectId === input.currentContext.projectId &&
    input.responseContext.mode === input.currentContext.mode &&
    input.responseContext.formRevision === input.currentContext.formRevision
  );
}

export function invalidatePreviewRequest(
  state: PreviewRequestState,
): PreviewRequestState {
  if (state.status === "success") {
    return { ...state, stale: true };
  }
  if (state.status === "loading" && state.previous) {
    return { status: "success", snapshot: state.previous, stale: true };
  }
  return { status: "idle" };
}
~~~

Workspace keeps requestSequenceRef and abortControllerRef:

1. abort the previous controller;
2. increment sequence;
3. enter loading with previous equal to the current successful snapshot when one exists;
4. clear applied Project state;
5. validate and build PlanningInput;
6. call previewWorkflowPlan with signal;
7. before committing success, compare sequence, projectId, mode, and revision;
8. accept held as success and call markProjectFilterApplied(projectId);
9. ignore AbortError without an error banner;
10. map 422 validation issues to field IDs and focus the first invalid field;
11. preserve the form and show retry for 500/503;
12. input, mode, or Project changes immediately abort the current controller, increment requestSequenceRef, call invalidatePreviewRequest(), and clear applied state;
13. a prior successful snapshot remains visible but stale, while an in-flight request with no prior snapshot becomes idle immediately and can never leave the UI permanently loading.

- [x] **Step 4: Implement simple and advanced views**

workflow-plan-preview.tsx owns role=tablist and one Preview object.

Simple view displays only response fields:

- planning status;
- coverage;
- Step labels/status;
- BudgetSummary including unknown;
- limitations;
- partial approval_required and field gaps;
- reason the plan can or cannot enter future execution;
- execution_authorized=false.

Advanced view displays:

- active/candidate/rejected QueryTerms;
- CompiledPlatformQueries;
- every WorkflowStep and dependency;
- RouteRequirement/RoutePlan;
- Primary/Fallback/Shadow;
- gates, score breakdown, exclusions, fields, Evidence refs;
- Catalog Snapshot, policy/template/query versions, and Fingerprint;
- provider_call=false, actor_run=false, browser_run=false, llm_call=false, database_write=false.

Both tabs display the same Fingerprint. Use max-w-full overflow-x-auto for tables and break-all for IDs/hash. Do not derive scores or route choice in React.

- [x] **Step 5: Add stale, held, and error rendering tests**

Unit-test pure view-model helpers for:

- held remains success;
- partial requires approval;
- unknown cost never becomes zero;
- advanced and simple receive the same object;
- 422 issue mapping;
- 503 retry state;
- stale snapshot clears applied state;
- semantic change during loading aborts, increments sequence, and transitions to idle or stale-success;
- aborted request produces no alert.

~~~bash
corepack pnpm --dir apps/web exec vitest run tests/unit/workflow-planner.test.ts tests/unit/workflow-plans-api.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm --dir apps/web lint
~~~

Expected: all commands exit 0.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/web/src/components/workflow-planner/workflow-planner-workspace.tsx apps/web/src/components/workflow-planner/workflow-plan-preview.tsx apps/web/src/components/workflow-planner/workflow-plan-simple-view.tsx apps/web/src/components/workflow-planner/workflow-plan-advanced-view.tsx apps/web/src/lib/workflow-planner.ts apps/web/tests/unit/workflow-planner.test.ts
git diff --cached --check
git commit -m "feat: render workflow plan previews"
~~~

Run only under task-level commit authorization.



---

### Task 12: Add Product Entry Points And Mock End-To-End Acceptance

**Files:**
- Create apps/web/src/components/dashboard/workflow-planner-entry-cards.tsx.
- Modify apps/web/src/app/dashboard/page.tsx.
- Modify apps/web/tests/e2e/main-flows.spec.ts.

**Interfaces:**
- Consumes: dual-mode route, explicit Web mock scenarios, global Project selection, and shared Preview UI.
- Produces: two business entry cards and desktop/mobile end-to-end evidence.

- [x] **Step 1: Add two Dashboard entry cards**

~~~typescript
const plannerEntries = [
  {
    href: "/automation/planner?mode=periodic_monitoring",
    title: "创建监测项目",
    description: "配置品牌、品类、竞品、平台与周期，生成可解释计划。",
  },
  {
    href: "/automation/planner?mode=batch_research",
    title: "批量检索与解析",
    description: "输入关键词与 Seed URL，预览跨平台查询和解析路线。",
  },
] as const;
~~~

Render semantic links before DashboardOverview. Cards must not say “运行”“激活” or imply data was collected.

- [x] **Step 2: Write the seven E2E scenarios**

Add named tests:

1. workflow planner periodic flow stays held with canonical catalog
2. workflow planner batch flow preserves unclassified seed url
3. workflow planner renders synthetic resolved primary fallback and shadow
4. workflow planner marks preview stale and ignores older response
5. project selection syncs in same tab and across tabs
6. workflow planner focuses first invalid field
7. workflow planner has no horizontal overflow at 375 and 1440

Required assertions:

- both Dashboard links set the correct mode;
- Project state changes false to true only after successful 200 Preview, including held;
- changing input/mode/Project returns applied state to false;
- canonical response shows held and no Primary;
- synthetic response shows Primary/Fallback/Shadow and execution_authorized=false;
- unclassified URL remains visible;
- simple/advanced show the same Fingerprint;
- delayed older response cannot replace the latest;
- second Playwright Page receives the first Page selection through storage;
- invalid submission focuses the first aria-invalid control;
- keyboard can navigate steps and tabs;
- at 375×812 and 1440×900, scrollWidth minus clientWidth is at most 1;
- intercept requests and assert every origin is localhost or 127.0.0.1.

The new components expose this exact acceptance-only selector contract:

~~~text
data-testid=workflow-planner-workspace
data-testid=workflow-planner-generate-preview
data-testid=workflow-planner-preview
data-testid=workflow-planner-fingerprint
data-testid=workflow-planner-stale
data-testid=workflow-planner-primary
data-testid=workflow-planner-fallback
data-testid=workflow-planner-shadow
data-testid=workflow-planner-unclassified-url
~~~

Use one shared setup helper and semantic selectors. The first and responsive scenarios are implemented exactly as follows; the other five named tests use the same Project names and selector contract rather than positional CSS:

~~~typescript
function watchExternalRequests(page: Page): () => string[] {
  const external: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.hostname !== "localhost" &&
      url.hostname !== "127.0.0.1"
    ) {
      external.push(request.url());
    }
  });
  return () => external;
}

async function openPlanner(
  page: Page,
  projectName: string,
  mode: "periodic_monitoring" | "batch_research",
) {
  await page.goto(`/automation/planner?mode=${mode}`);
  await page.getByTestId("global-project-selector").selectOption({
    label: projectName,
  });
  await expect(
    page.locator('[data-project-filter-applied="false"]'),
  ).toBeVisible();
}

test("workflow planner periodic flow stays held with canonical catalog", async ({
  page,
}) => {
  const externalRequests = watchExternalRequests(page);
  await openPlanner(
    page,
    "Planner Fixture - Canonical Held",
    "periodic_monitoring",
  );
  await page.getByRole("button", { name: "下一步" }).click();
  await page.locator("#planner-scope-0-canonical-term").fill("Acme");
  await page.getByRole("button", { name: "添加 Scope" }).click();
  await page.locator("#planner-scope-1-type").selectOption("category");
  await page.locator("#planner-scope-1-canonical-term").fill("running shoes");
  await page.getByRole("button", { name: "下一步" }).click();
  await page.locator("#planner-platform-reddit").check();
  await page.locator("#planner-schedule-cadence").selectOption("daily");
  await page.locator("#planner-schedule-timezone").fill("Asia/Shanghai");
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByTestId("workflow-planner-generate-preview").click();

  await expect(page.getByTestId("workflow-planner-preview")).toContainText(
    "held",
  );
  await expect(page.getByTestId("workflow-planner-primary")).toHaveCount(0);
  await expect(
    page.locator('[data-project-filter-applied="true"]'),
  ).toBeVisible();
  const simpleFingerprint = await page
    .getByTestId("workflow-planner-fingerprint")
    .textContent();
  await page.getByRole("tab", { name: "高级视图" }).click();
  await expect(page.getByTestId("workflow-planner-fingerprint")).toHaveText(
    simpleFingerprint ?? "",
  );
  await expect(page.getByText("execution_authorized=false")).toBeVisible();
  expect(externalRequests()).toEqual([]);
});

test("workflow planner has no horizontal overflow at 375 and 1440", async ({
  page,
}) => {
  for (const viewport of [
    { width: 375, height: 812 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await openPlanner(
      page,
      "Planner Fixture - Synthetic Resolved",
      "batch_research",
    );
    await page.getByRole("button", { name: "下一步" }).click();
    await page.locator("#planner-scope-0-canonical-term").fill("running shoes");
    await page.getByRole("button", { name: "下一步" }).click();
    await page.locator("#planner-platform-reddit").check();
    await page.getByRole("button", { name: "下一步" }).click();
    await page.getByTestId("workflow-planner-generate-preview").click();
    await expect(page.getByTestId("workflow-planner-preview")).toBeVisible();
    await page.getByRole("tab", { name: "高级视图" }).click();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  }
});
~~~

For the remaining five tests, keep these exact decisive assertions:

- batch: fill one external Seed URL, generate Preview twice without changing semantic input, assert workflow-planner-unclassified-url contains the original URL, and assert both generated Fingerprints are identical;
- synthetic resolved: assert workflow-planner-primary, workflow-planner-fallback, and workflow-planner-shadow are visible and execution_authorized=false;
- stale ordering: submit e2e-slow-first, immediately submit e2e-fast-second, wait for both delays, and assert the Fingerprint remains sha256: plus 64 "2" characters; after a later input edit, workflow-planner-stale appears;
- Project sync: create a second Page in the same BrowserContext, select Synthetic Partial in the first, and assert both global-project-selector values equal 00000000-0000-4000-8000-000000000032 after the storage event;
- invalid focus: submit the Scope step empty and assert document.activeElement.id is planner-scope-0-canonical-term.

- [x] **Step 3: Run focused desktop E2E**

~~~bash
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true PLAYWRIGHT_PORT=3114 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web exec playwright test tests/e2e/main-flows.spec.ts --grep "workflow planner|project selection syncs" --project=desktop
~~~

Expected: all seven new desktop scenarios selected for desktop exit 0; no external origin appears.

- [x] **Step 4: Run focused mobile E2E**

~~~bash
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true PLAYWRIGHT_PORT=3115 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web exec playwright test tests/e2e/main-flows.spec.ts --grep "workflow planner" --project=mobile
~~~

Expected: all mobile Planner scenarios exit 0, including the explicit 375px viewport assertion.

- [x] **Step 5: Run the full Web local gate**

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true PLAYWRIGHT_PORT=3116 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web test:e2e
~~~

Expected: typecheck, lint, all unit tests, production build, and full mock E2E exit 0. Record actual totals and expected skips; do not describe them as real API or production proof.

- [ ] **Step 6: Optional authorized commit**

~~~bash
git add -- apps/web/src/components/dashboard/workflow-planner-entry-cards.tsx apps/web/src/app/dashboard/page.tsx apps/web/tests/e2e/main-flows.spec.ts
git diff --cached --check
git commit -m "test: cover workflow planner product flows"
~~~

Run only under task-level commit authorization.



---

> **Historical Phase One execution record:** The Task 13 instructions and evidence below intentionally retain the Phase One closeout boundary `phase_2_persistence_authorization=false`. They describe the 2026-07-13 Phase One checkpoint, not the current Phase Two authorization or implementation state; use the successor links in Execution Handoff for current work.

### Task 13: Synchronize Contracts And Run The Phase-One Exit Gate

**Files:**
- Modify docs/product/product-prd-social-media-automation-platform-v2.md.
- Modify docs/architecture/architecture-data-intelligence-hub-stable.md.
- Modify docs/api/api-contract-data-intelligence-hub-stable.md.
- Modify docs/superpowers/specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md.
- Modify docs/superpowers/plans/2026-07-12-goal-v2-03-workflow-planner-phase-1.md.
- Modify TODO.md.
- Modify .codex/context-pack.md.
- Modify .codex/ralph-loop.local.md.
- Modify .kiro/plan/task_plan.md.
- Modify .kiro/plan/findings.md.
- Modify .kiro/plan/progress.md.

**Interfaces:**
- Consumes: fresh API/Web evidence from Tasks 1-12.
- Produces: synchronized L1/L2 contracts, exact evidence record, and phase_1_locally_complete state without phase-two activation.

- [x] **Step 1: Update the tracked product and contract documents**

Record:

- POST /api/projects/{project_id}/workflow-plans/preview request/response/error contract;
- write-free Project read path;
- MonitoringScopeDraft, Query Compiler, templates, Resolver, Snapshot, Fingerprint, and UI architecture;
- canonical candidate-only held behavior;
- test-only synthetic routing;
- Project Selector applied semantics;
- phase-one status and explicit phase-two persistence gate.

Do not document GET/POST MonitoringScope persistence, WorkflowVersion storage, Activate, or Run as implemented.

At this step keep the plan and local Goal state in verification_in_progress. Do not write locally_complete, local_gates_passed, or phase_1_locally_complete before Steps 3-5 pass. The approved design remains status=approved and phase two remains unauthorized.

- [x] **Step 2: Update the local control overlays**

Set:

~~~text
GOAL-V2-03 status=verification_in_progress
database_write=false
migration_applied=false
provider_call=false
actor_run=false
browser_run=false
llm_call=false
workflow_run_created=false
production unchanged
GOAL-V2-03 phase_2_persistence_authorization=false
~~~

Keep historical PRD2 material below the current overlay. Do not stage ignored TODO/.codex/.kiro files.

- [x] **Step 3: Run the complete API gate**

~~~bash
cd apps/api
uv run pytest tests/unit/test_workflow_planner_fingerprint.py -q -s -k fixture_preview_p95
uv run pytest tests/unit/test_workflow_planner_schema.py tests/unit/test_workflow_planner_normalization.py tests/unit/test_workflow_planner_query_compiler.py tests/unit/test_workflow_planner_templates.py tests/unit/test_workflow_planner_resolver.py tests/unit/test_workflow_planner_fingerprint.py tests/unit/test_workflow_planner.py tests/integration/test_workflow_planner_preview.py -q
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
~~~

Expected:

- the dedicated performance command exits 0 and prints exactly one preview_p95_ms= line with a numeric millisecond value;
- targeted Planner tests exit 0;
- Ruff and mypy exit 0;
- full pytest exits 0;
- Alembic reports one unchanged head, 202606110026;
- no migration file is added.

- [x] **Step 4: Run the complete Web gate**

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES=true PLAYWRIGHT_PORT=3117 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web test:e2e
~~~

Expected: all static, unit, build, and full mock E2E commands exit 0. Record actual page/test/pass/expected-skip totals.

- [x] **Step 5: Verify scope, boundaries, and no migration**

~~~bash
git diff --check
git status --short
git diff --name-only
git ls-files --others --exclude-standard
git status --short -- apps/api/alembic
! rg -n "[p]rovider(_call|Call)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[a]ctor(_run|Run)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[b]rowser(_run|Run)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[l]lm(_call|Call)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[e]xecution(_authorized|Authorized)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[d]atabase(_write|Write)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[m]igration(_applied|Applied)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)|[w]orkflow(_run_created|RunCreated)['\"]?[[:space:]]*[:=][[:space:]]*(true|True)" apps/api/src/data_intelligence_hub/schemas/workflow_planner.py apps/api/src/data_intelligence_hub/services/workflow_planner apps/api/src/data_intelligence_hub/api/routes/workflow_plans.py apps/web/src/types/workflow-planner.ts apps/web/src/components/workflow-planner apps/web/src/lib/api/workflow-plans.ts apps/web/src/lib/workflow-planner.ts apps/web/src/lib/workflow-planner-mock.ts docs/superpowers/specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md docs/superpowers/plans/2026-07-12-goal-v2-03-workflow-planner-phase-1.md
~~~

Expected:

- git diff --check exits 0;
- only approved Goal files plus pre-existing unrelated paths appear;
- git status for apps/api/alembic prints nothing;
- the negative boundary grep exits 0 and prints nothing.

- [x] **Step 6: Record exact evidence**

Only after Steps 3-5 all pass, append one Execution Evidence section to this plan. Copy the fresh command output for these keys verbatim: implementation_status, api_targeted, api_ruff, api_mypy, api_pytest, alembic_head, web_typecheck, web_lint, web_unit, web_build, web_mock_e2e, and preview_p95_ms.

Then, and only then:

- set this plan frontmatter to status=locally_complete, review_status=local_gates_passed, goal_execution=phase_1_locally_complete;
- keep the approved design status=approved and set its goal_execution=phase_1_locally_complete;
- change the local overlays from verification_in_progress to phase_1_locally_complete;
- keep phase_2_persistence_authorization=false.

The same section must contain these literal boundary values:

~~~text
implementation_status=phase_1_locally_complete
alembic_head=202606110026
database_write=false
migration_applied=false
provider_call=false
actor_run=false
browser_run=false
llm_call=false
workflow_run_created=false
production unchanged
~~~

If any fresh command output is unavailable, keep status=verification_in_progress and list the missing gate instead of adding a completion evidence block.

After writing final status/evidence, rerun git diff --check and the negative boundary grep from Step 5. Either failure returns the Goal state to verification_in_progress; do not retain a completion claim.

- [ ] **Step 7: Optional authorized phase-one commit**

Do not create a new aggregate stage set implicitly. If task-level commits were authorized and completed, commit only the tracked Task 13 evidence documents with this exact allowlist:

~~~bash
git add -- docs/product/product-prd-social-media-automation-platform-v2.md docs/architecture/architecture-data-intelligence-hub-stable.md docs/api/api-contract-data-intelligence-hub-stable.md docs/superpowers/specs/2026-07-12-goal-v2-03-monitoring-scope-workflow-planner-design.md docs/superpowers/plans/2026-07-12-goal-v2-03-workflow-planner-phase-1.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: record workflow planner phase-one evidence"
~~~

Do not stage ignored TODO/.codex/.kiro overlays. If the user instead requests one aggregate phase-one commit, stop and generate an exact allowlist from only the Backend, Backend tests/fixtures, Web, and tracked Product/contract entries in File Structure; explicitly exclude TODO.md, .codex/**, .kiro/**, drafts/**, output/**, ref/**, and every unrelated pre-existing path. Show that allowlist together with current unstaged/untracked paths and wait for separate aggregate commit authorization. Before any aggregate commit, verify the staged names equal that owner-approved allowlist and only then run git commit -m "feat: add deterministic workflow planner preview". Do not push. If commit authorization is absent, leave all phase-one files unstaged and report that state.

- [x] **Step 8: Stop before phase two**

Report:

    GOAL-V2-03 phase_1_locally_complete
    phase_2_persistence_authorization=false
    database_write=false
    migration_applied=false
    provider_call=false
    actor_run=false
    browser_run=false
    llm_call=false
    workflow_run_created=false
    production unchanged

Do not create MonitoringScope/QueryTerm/WorkflowPlan/WorkflowVersion tables or an Alembic revision. The next planning action is a separate phase-two persistence plan only after user authorization.



---

## Execution Evidence

Fresh Phase 1 exit evidence recorded on 2026-07-13:

```text
implementation_status=phase_1_locally_complete
api_targeted=240 passed, 0 skipped, 1 warning in 2.80s
api_ruff=All checks passed!
api_mypy=Success: no issues found in 183 source files
api_pytest=439 passed, 0 skipped, 12 warnings in 34.58s
alembic_head=202606110026
web_typecheck=exit 0
web_lint=exit 0
web_unit=10 files passed; 151 tests passed
web_build=Next.js 15.5.19; 23/23 static pages generated; /automation/planner 15.3 kB; First Load JS 161 kB; exit 0
web_mock_e2e=70 total; 58 passed; 12 expected skipped; 0 failed; 1.6m; exit 0
preview_p95_ms=5.287
database_write=false
migration_applied=false
provider_call=false
actor_run=false
browser_run=false
llm_call=false
workflow_run_created=false
production unchanged
```

API warning breakdown:

- Targeted Planner gate: one existing passlib `crypt` deprecation warning.
- Full pytest: the same passlib warning plus 11 `PytestUnhandledThreadExceptionWarning` entries from scheduler-test aiosqlite cleanup after the event loop closed. All 439 tests passed; these warnings are retained as warnings rather than hidden or promoted to failure.

Web warning breakdown:

- Next.js reported multiple lockfiles while inferring the workspace root; the Web build still exited 0.
- The Web commands reported that `NO_COLOR` was ignored because `FORCE_COLOR` was set; the affected gates still exited 0.
- Mock E2E reported that local `127.0.0.1` requests to `/_next` will require `allowedDevOrigins` in a future Next.js version; the current run completed with 58 passed, 12 expected skipped, and 0 failed. These Web warnings did not cause a gate failure.

Evidence interpretation and remaining boundaries:

```text
evidence_grade=L2-fixture-or-dry-run
evidence_label=web_mock_e2e
local_playwright_browser=true
product_browser_run=false
scope_check=passed
negative_boundary_scan=passed
alembic_changes=none
staged_files=none
commit=none
push=false
ci_status=not_run
deploy_status=not_run
production_acceptance=not_run
GOAL-V2-03 phase_2_persistence_authorization=false
```

`local_playwright_browser=true` 只表示本地 mock UI 验收使用了 Playwright 浏览器；产品/collector `browser_run=false`，没有 Provider、Actor、LLM、WorkflowRun、数据库写入、migration 或生产变化。测试 fixture 的数据库写入仅发生在隔离测试环境，不改变产品 `database_write=false` 边界。

## Requirement Coverage

| Requirement | Implemented by | Proof |
|---|---|---|
| PRJ-004 / PRJ-005 | Tasks 1-4, 10 | Scope fields, effective platform, Precision/Recall tests |
| QRY-001 / QRY-003 / QRY-004 / QRY-005 | Tasks 2-4 | deterministic terms, candidate exclusion, query version, attribution |
| QRY-002 Fixture contract only | Task 3 | versioned candidate adapter with no LLM call |
| WFL-002 / WFL-003 | Tasks 4, 6, 7 | complete Preview and stable Fingerprint |
| WFL-004 / WFL-005 / WFL-006 | Task 5 | policy, independent RoutePlans, field contracts |
| WFL-007 / UI-003 / UI-007 | Tasks 9-12 | one response, simple/advanced views |
| UI-002 | Tasks 8, 12 | two Dashboard/navigation entries |
| UI-009 | Task 12 | 375px/1440px mock E2E |
| Zero persistence and execution boundary | Tasks 7, 13 | SQL capture, table counts, unchanged Alembic head, boundary flags |



---

## Phase-One Exit Gate

Phase one can be described as locally complete only when all conditions hold:

1. Both periodic_monitoring and batch_research generate full WorkflowPlanPreview responses.
2. The same semantic input/Catalog/Policy/template/query/Fixture produces the same Fingerprint.
3. Canonical candidate-only Assertions return held with complete exclusions.
4. Synthetic verified/partial test data proves Primary, Fallback, Shadow, and approval_required.
5. Project Selector reports applied only after a successful Project-scoped Preview.
6. Simple and advanced views display the same Fingerprint and no frontend route recomputation.
7. 422 field focus, 409, 404, 500, 503, stale responses, unclassified URL, keyboard, and responsive paths pass.
8. API targeted/full, Ruff, mypy, Web unit/type/lint/build, and full mock E2E gates pass.
9. p95 for the no-LLM Fixture Preview is below 3 seconds.
10. No model, repository, Alembic revision, DB write, WorkflowRun, Provider, Actor, browser, LLM, deploy, or production change occurs.



---

## Execution Handoff

Phase 1 is locally closed out. Do not rerun Tasks 0-13 merely to produce newer Phase Two evidence.

The current successor is the approved Phase Two design and implementation plan:

1. [`2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md`](../specs/2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence-design.md)
2. [`2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md`](2026-07-13-goal-v2-03-workflow-planner-phase-2-persistence.md)

The successor currently permits local implementation and disposable PostgreSQL 15 verification only. Optional Phase One commit, any checkpoint commit, push, deploy, shared/production database, Provider, Activate, Run and WorkflowRun remain separate authorization gates.

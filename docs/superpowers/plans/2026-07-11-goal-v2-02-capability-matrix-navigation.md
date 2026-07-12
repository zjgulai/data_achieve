---
title: GOAL-V2-02 能力矩阵与六入口导航 Implementation Plan
doc_type: implementation_plan
module: capability-market
topic: goal-v2-02-capability-matrix-navigation
status: locally_complete
review_status: local_gates_passed
created: 2026-07-11
updated: 2026-07-11
owner: self
source: human+ai
spec: ../specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
provider_call: false
database_migration: false
production_boundary: production unchanged
---

# GOAL-V2-02 Capability Matrix And Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a read-only 7×6 capability matrix, canonical capability APIs, a three-view capability market, six-entry desktop/mobile navigation, and an honest project selector from the existing capability_catalog.v1 source.

**Architecture:** Keep capability_catalog_overseas_v2.json as the only runtime capability fact source. Derive the 42-cell matrix in a focused backend read-model service, expose authenticated read-only APIs, and make the Web capability market consume those APIs while retaining only presentation samples locally. Navigation is generated from one shared config; no database persistence or Provider execution is introduced.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, pytest, ruff, mypy, Next.js 15, React 19, TypeScript 5.7, Vitest, Playwright, existing Workbench UI primitives, lucide-react.

---

## Global Constraints

- Source specification: docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md.
- Runtime capability truth: apps/api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json.
- Keep provider_call=false, provider_call_attempted=false, credential_read_attempted=false, live_client_created=false, and production_write_allowed=false.
- Do not add SQLAlchemy models, Alembic revisions, database seed/sync code, Provider clients, SDK dependencies, or live routes.
- Keep all existing /api/automation/social-provider-* contracts compatible.
- Preserve every existing route; navigation changes only affect grouping and prominence.
- Do not read .env or secret files and do not print credential values.
- Preserve the existing untracked drafts, output/, and ref/ trees.
- Never use git add .; stage only the exact files listed for an authorized commit.
- Commits, push, PR, merge, deploy, production smoke, and live calls require separate user authorization. If commit authorization is absent, finish each task with verified changes unstaged.
- Local unit, fixture, build, and mock-browser evidence must not be described as CI, production acceptance, or live-provider evidence.
- Run commands from the repository root unless a block begins with `cd apps/api`; treat every command block as a fresh shell and do not carry a prior `cd` forward.

## Scope Check

This plan contains five ordered domains that form one Goal and one exit gate:

1. Activate the V2 control plane while preserving historical PRD2 records.
2. Restore the Web typecheck baseline.
3. Build the backend matrix read model and read-only API.
4. Migrate the capability market and navigation to the approved product shape.
5. Synchronize implementation contracts and run the full local gate.

MonitoringScope, WorkflowPlan V2, dynamic capability publication, Provider adapters, and production deployment remain separate future Goals.

## File Structure

### Backend files

- Create apps/api/src/data_intelligence_hub/schemas/capability_matrix.py
  - API/read-model contracts only.
- Create apps/api/src/data_intelligence_hub/services/capability_matrix.py
  - Pure matrix aggregation, filtering, and implementation detail projection.
- Create apps/api/src/data_intelligence_hub/api/routes/capabilities.py
  - Authenticated read-only HTTP routes.
- Modify apps/api/src/data_intelligence_hub/services/exceptions.py
  - Add implementation-not-found error.
- Modify apps/api/src/data_intelligence_hub/main.py
  - Register the new router.
- Create apps/api/tests/unit/test_capability_matrix.py
  - Matrix count, status aggregation, filtering, immutability, and detail tests.
- Create apps/api/tests/integration/test_capability_routes.py
  - Authentication, response, filter, 422, and 404 tests.

### Web files

- Modify apps/web/tests/unit/social-provider.test.ts
  - Restore typecheck-safe typed fixtures.
- Create apps/web/src/types/capability.ts
  - Capability API DTOs and UI domain types.
- Create apps/web/src/lib/api/capabilities.ts
  - Capability API client and response mappers.
- Create apps/web/src/lib/capability-mock.ts
  - Mock-only L2 fixture data; never a non-mock fallback.
- Create apps/web/src/lib/capability-market.ts
  - URL view parsing, eight-scenario grouping, filtering, status labels, and comparison projection.
- Modify apps/web/src/types/api-market.ts
  - Separate presentation data from backend capability facts.
- Modify apps/web/src/lib/api-market-catalog.ts
  - Retain only endpoint presentation records and compose them with API facts.
- Modify apps/web/src/components/api-market/api-market-workspace.tsx
  - Load capability APIs and coordinate the three views.
- Create apps/web/src/components/api-market/capability-scenario-view.tsx
- Create apps/web/src/components/api-market/capability-matrix-view.tsx
- Create apps/web/src/components/api-market/capability-list-view.tsx
- Create apps/web/src/components/api-market/capability-detail-drawer.tsx
- Create apps/web/src/components/api-market/capability-comparison-panel.tsx
- Modify apps/web/src/components/api-market/api-market-detail-workspace.tsx
  - Use composed capability facts plus endpoint presentation.
- Modify apps/web/src/app/api-market/page.tsx
  - Accept and normalize the view query.
- Modify apps/web/src/app/api-market/[endpointId]/page.tsx
  - Load presentation identity and let the client retrieve canonical facts.
- Create apps/web/src/components/layout/navigation.ts
  - Single six-entry navigation config.
- Modify apps/web/src/components/layout/sidebar.tsx
  - Render six primary entries and their secondary pages.
- Create apps/web/src/components/layout/mobile-navigation.tsx
- Create apps/web/src/components/layout/project-selector.tsx
- Create apps/web/src/lib/project-selection.ts
- Modify apps/web/src/components/layout/top-bar.tsx
- Modify apps/web/src/components/layout/app-shell.tsx
- Modify apps/web/tests/unit/api-market.test.ts
- Create apps/web/tests/unit/capability-api.test.ts
- Create apps/web/tests/unit/capability-market.test.ts
- Create apps/web/tests/unit/navigation.test.ts
- Modify apps/web/tests/e2e/main-flows.spec.ts
- Modify apps/web/playwright.config.ts
  - Allow forced fresh mock-only ports for deterministic local E2E.

### State and documentation files

- Modify docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md
- Modify docs/product/product-prd-social-media-automation-platform-v2.md
- Modify docs/architecture/architecture-data-intelligence-hub-stable.md
- Modify docs/api/api-contract-data-intelligence-hub-stable.md
- Modify docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
- Modify docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md
- Modify TODO.md
- Modify .codex/context-pack.md
- Modify .codex/ralph-loop.local.md
- Modify .kiro/plan/task_plan.md
- Modify .kiro/plan/findings.md
- Modify .kiro/plan/progress.md

---

### Task 0: Activate The V2 Control Plane Before Feature Work

**Files:**
- Modify: docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md
- Modify: docs/product/product-prd-social-media-automation-platform-v2.md
- Modify: docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
- Modify: docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md
- Modify: TODO.md
- Modify: .codex/context-pack.md
- Modify: .codex/ralph-loop.local.md
- Modify: .kiro/plan/task_plan.md
- Modify: .kiro/plan/findings.md

- [x] **Step 1: Capture the execution base and verify the stale state first**

~~~bash
git rev-parse HEAD > tmp/goal-v2-02-base-sha
git status --short > tmp/goal-v2-02-initial-status.txt
git diff --binary > tmp/goal-v2-02-initial-tracked.patch
git ls-files --others --exclude-standard > tmp/goal-v2-02-initial-untracked.txt
rg -n '^status: approved$|^- \[ \] \*\*Step|当前状态均为 `ready_for_goal_activation`|^active: true$|Loop 37 is pending|Product source of truth: `docs/product/product-prd-data-intelligence-hub-stable.md`' docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md docs/product/product-prd-social-media-automation-platform-v2.md .codex/context-pack.md .codex/ralph-loop.local.md
~~~

Expected: the command records one BASE_SHA and the initial dirty/untracked manifest; grep exposes the known GOAL-V2-01/V2/PRD2 state drift before edits. Do not put tmp/goal-v2-02-* files in a commit.

- [x] **Step 2: Close GOAL-V2-01 from its existing evidence**

In docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md, apply these exact state changes only because its existing Execution Evidence already says implementation_status=complete and lists passing gates:

~~~diff
-status: approved
+status: complete
+review_status: local_verified
~~~

Change all 25 task markers in that plan from `- [ ] **Step` to `- [x] **Step`; do not change prose, commands, evidence, SHAs, or Goal boundaries.

- [x] **Step 3: Mark the V2 Goal sequence explicitly**

Replace the single blanket sentence in docs/product/product-prd-social-media-automation-platform-v2.md with:

~~~markdown
以下 Goal 由独立规格、计划和证据推进；状态不代表部署或生产验收。

- GOAL-V2-01: complete (local contract evidence)
- GOAL-V2-02: in_progress (local implementation only)
- GOAL-V2-03 及后续 Goal: queued, not activated
~~~

Add `**Status**: complete` under the GOAL-V2-01 heading and `**Status**: in_progress` under GOAL-V2-02. Do not change later Goal scopes or activate GOAL-V2-03.

- [x] **Step 4: Switch Codex/Kiro current-state entry points without deleting history**

Replace .codex/context-pack.md Current Focus with:

~~~markdown
## Current Focus

Execute GOAL-V2-02 from the approved design and implementation plan: fixture-derived read-only Capability APIs, 7×6 matrix, three Capability Market views, six-entry navigation, and an honest global Project Selector.

Boundaries: provider_call=false; credential_read_attempted=false; live_client_created=false; production_write_allowed=false; database_migration=false; production unchanged. Local checks are not CI, deployment, Provider execution, or production acceptance.
~~~

In .codex/ralph-loop.local.md set `active: false`, keep completion_promise null, rename the title to `# Historical PRD2 Loop State`, and replace Current Phase with:

~~~markdown
## Current Phase

Inactive. PRD2 Loop 37 is historical and remains preserved below. Current work is GOAL-V2-02 plan execution; no autonomous loop is active.
~~~

Prepend this block after the title in .kiro/plan/task_plan.md:

~~~markdown
## Current Planning Overlay: GOAL-V2-02

- Status: in_progress, local implementation only
- Spec: docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
- Plan: docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md
- Current batch: Task 0 control-plane activation
- Boundaries: provider_call=false; database_migration=false; production unchanged

Historical Phase 15/17 and Boundary Leftovers remain below and are not the current execution source.
~~~

Append a dated finding to .kiro/plan/findings.md stating the canonical Fixture counts (7 Implementations, 35 Candidate Assertions, 14 Evidence), the 42-cell derived model decision, and the same false boundary flags. Do not rewrite prior findings.

- [x] **Step 5: Switch the local plan/spec/TODO.md execution markers**

Apply these exact frontmatter changes:

~~~diff
# design spec
-goal_execution: implementation_plan_ready
+goal_execution: implementation_in_progress

# implementation plan
-status: ready
+status: in_progress
~~~

In TODO.md change `status: plan_ready_waiting_execution_mode` to `status: execution_in_progress` and mark only Task 0 complete after Step 6 passes. Leave Task 1-10 unchecked.

- [x] **Step 6: Verify the active state and historical preservation**

~~~bash
rg -n '^status: complete$|^review_status: local_verified$|GOAL-V2-01: complete|GOAL-V2-02: in_progress|GOAL-V2-03 及后续 Goal: queued|^active: false$|Current Planning Overlay: GOAL-V2-02|provider_call=false|production unchanged' docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md docs/product/product-prd-social-media-automation-platform-v2.md .codex/context-pack.md .codex/ralph-loop.local.md .kiro/plan/task_plan.md TODO.md
rg -n 'Loop 37|Phase 15/17|Boundary Leftovers' .codex/ralph-loop.local.md .kiro/plan/task_plan.md
git diff --check
~~~

Expected: current-state markers are present, historical markers still exist only under historical sections, and diff check exits 0.

- [ ] **Step 7: Commit only after explicit commit authorization**

~~~bash
git add docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md docs/product/product-prd-social-media-automation-platform-v2.md docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md .codex/context-pack.md .codex/ralph-loop.local.md .kiro/plan/task_plan.md .kiro/plan/findings.md
git diff --cached --check
git commit -m "docs: activate goal v2 capability matrix"
~~~

TODO.md is ignored and remains local even when commit authorization is present. Without authorization, leave all Task 0 changes unstaged.

---

### Task 1: Restore The Web TypeScript Baseline

**Files:**
- Modify: apps/web/tests/unit/social-provider.test.ts:18-247

**Interfaces:**
- Consumes: existing Social Provider response DTO types.
- Produces: typechecked test fixtures accepted by the existing mapper signatures.

- [x] **Step 1: Reproduce the current typecheck blocker**

Run:

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
~~~

Expected: exit 2 with six TS2345 diagnostics at social-provider.test.ts lines 438, 448, 461, 478, 490, and 502. Each diagnostic reports a readonly array that cannot be assigned to a mutable DTO array.

- [x] **Step 2: Import every fixture DTO explicitly**

Replace the single DTO import with:

~~~typescript
import type {
  SocialDatasetPreviewResponseDto,
  SocialExecutionDryRunResponseDto,
  SocialProviderAdapterPlanResponseDto,
  SocialProviderCatalogResponseDto,
  SocialProviderReadinessResponseDto,
  SocialProviderSourceTemplateResponseDto,
  SocialTaskRunApprovalTemplateResponseDto,
} from "@/types/social-provider";
~~~

- [x] **Step 3: Contextually type each response fixture**

Replace the six as const suffixes with these exact satisfies clauses:

~~~typescript
} satisfies SocialProviderCatalogResponseDto;

} satisfies SocialProviderReadinessResponseDto;

} satisfies SocialProviderAdapterPlanResponseDto;

} satisfies SocialDatasetPreviewResponseDto;

} satisfies SocialProviderSourceTemplateResponseDto;

} satisfies SocialTaskRunApprovalTemplateResponseDto;
~~~

Keep the existing SocialExecutionDryRunResponseDto fixture annotation unchanged.

- [x] **Step 4: Verify the focused type and mapper gates**

Run:

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm --dir apps/web test -- tests/unit/social-provider.test.ts tests/unit/api-market.test.ts
corepack pnpm lint:web
corepack pnpm --dir apps/web build
~~~

Expected:

- TypeScript exits 0 with no diagnostics.
- Vitest reports 21 passing tests across the two files.
- ESLint exits 0.
- Next build exits 0 and lists /api-market plus /api-market/[endpointId].

- [ ] **Step 5: Commit only after explicit commit authorization**

Authorized commands:

~~~bash
git add apps/web/tests/unit/social-provider.test.ts
git diff --cached --check
git commit -m "test: restore social provider typecheck baseline"
~~~

Without commit authorization: leave the verified file unstaged and continue only if the chosen execution workflow permits an unstaged task boundary.

---

### Task 2: Build The Capability Matrix Contract And Pure Read Model

**Files:**
- Create: apps/api/src/data_intelligence_hub/schemas/capability_matrix.py
- Create: apps/api/src/data_intelligence_hub/services/capability_matrix.py
- Modify: apps/api/src/data_intelligence_hub/services/exceptions.py:152-165
- Create: apps/api/tests/unit/test_capability_matrix.py

**Interfaces:**
- Consumes: get_capability_catalog() -> CapabilityCatalog.
- Produces:
  - build_capability_matrix() -> CapabilityMatrixResponse
  - list_capability_assertions(...) -> list[CapabilityAssertion]
  - list_capability_implementations(...) -> list[CapabilityImplementation]
  - get_capability_implementation_detail(implementation_id) -> CapabilityImplementationDetail

- [x] **Step 1: Write the matrix unit tests**

Create apps/api/tests/unit/test_capability_matrix.py:

~~~python
from __future__ import annotations

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.services import capability_matrix as capability_matrix_service
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_matrix import (
    build_capability_matrix,
    get_capability_implementation_detail,
    list_capability_assertions,
    list_capability_implementations,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityImplementationNotFoundError,
)


def test_matrix_returns_all_platform_channel_cells() -> None:
    matrix = build_capability_matrix()

    assert matrix.schema_version == "capability_matrix.v1"
    assert len(matrix.platforms) == 7
    assert len(matrix.access_channels) == 6
    assert len(matrix.cells) == 42
    assert matrix.summary.cell_count == 42
    assert matrix.summary.populated_cell_count == 7
    assert matrix.summary.unknown_cell_count == 35
    assert matrix.provider_call is False
    assert matrix.production_write_allowed is False


def test_matrix_marks_current_official_api_cells_candidate() -> None:
    matrix = build_capability_matrix()
    official_cells = [
        cell
        for cell in matrix.cells
        if cell.access_channel is AccessChannel.OFFICIAL_AUTHORIZED_API
    ]

    assert len(official_cells) == 7
    assert {cell.summary_status for cell in official_cells} == {
        CapabilityStatus.CANDIDATE
    }
    assert all(cell.assertion_ids for cell in official_cells)
    assert all(cell.evidence_count > 0 for cell in official_cells)


def test_populated_cell_projects_constraints_evidence_and_time() -> None:
    catalog = get_capability_catalog()
    expected_assertions = [
        item
        for item in catalog.assertions
        if item.implementation_id == "youtube.v3"
    ]
    cell = next(
        item
        for item in build_capability_matrix().cells
        if item.platform is PlatformId.YOUTUBE
        and item.access_channel is AccessChannel.OFFICIAL_AUTHORIZED_API
    )

    assert cell.constraint_codes == sorted(
        {
            constraint.code
            for assertion in expected_assertions
            for constraint in assertion.constraints
        }
    )
    assert cell.evidence_count == len(
        {ref for assertion in expected_assertions for ref in assertion.evidence_refs}
    )
    assert cell.last_verified_at == max(
        item.last_verified_at for item in expected_assertions
    )


def test_summary_priority_keeps_mixed_status_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = get_capability_catalog()
    source = next(
        item
        for item in catalog.assertions
        if item.implementation_id == "youtube.v3"
    )
    verified = source.model_copy(
        update={
            "assertion_id": source.assertion_id + ":verified-test",
            "support_status": CapabilityStatus.VERIFIED,
        }
    )
    mixed = catalog.model_copy(
        deep=True,
        update={"assertions": [*catalog.assertions, verified]},
    )
    monkeypatch.setattr(
        capability_matrix_service,
        "get_capability_catalog",
        lambda: mixed.model_copy(deep=True),
    )

    cell = next(
        item
        for item in build_capability_matrix().cells
        if item.platform is PlatformId.YOUTUBE
        and item.access_channel is AccessChannel.OFFICIAL_AUTHORIZED_API
    )

    assert cell.summary_status is CapabilityStatus.VERIFIED
    assert cell.status_counts[CapabilityStatus.CANDIDATE] == 5
    assert cell.status_counts[CapabilityStatus.VERIFIED] == 1


def test_matrix_emits_explicit_unknown_cells() -> None:
    matrix = build_capability_matrix()
    cell = next(
        item
        for item in matrix.cells
        if item.platform is PlatformId.YOUTUBE
        and item.access_channel is AccessChannel.AUTHORIZED_BROWSER
    )

    assert cell.summary_status is CapabilityStatus.UNKNOWN
    assert cell.status_counts == {CapabilityStatus.UNKNOWN: 1}
    assert cell.implementation_ids == []
    assert cell.assertion_ids == []
    assert cell.evidence_count == 0
    assert cell.last_verified_at is None


def test_filters_are_deterministic_and_do_not_mutate_catalog() -> None:
    before = get_capability_catalog()
    assertions = list_capability_assertions(
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
        resource_type=ResourceType.CONVERSATION,
        operation=CapabilityOperation.LIST_ENUMERATE,
        support_status=CapabilityStatus.CANDIDATE,
    )
    implementations = list_capability_implementations(
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
    )
    after = get_capability_catalog()

    assert len(assertions) == 1
    assert assertions[0].implementation_id == "youtube.v3"
    assert [item.implementation_id for item in implementations] == ["youtube.v3"]
    assert before == after


def test_implementation_detail_and_missing_id() -> None:
    detail = get_capability_implementation_detail("youtube.v3")

    assert detail.schema_version == "capability_implementation_detail.v1"
    assert detail.implementation.implementation_id == "youtube.v3"
    assert len(detail.assertions) == 5
    assert detail.evidence

    with pytest.raises(CapabilityImplementationNotFoundError):
        get_capability_implementation_detail("missing-provider")
~~~

- [x] **Step 2: Run the tests to verify the red state**

Run:

~~~bash
cd apps/api
uv run pytest tests/unit/test_capability_matrix.py -q
~~~

Expected: collection stops with ModuleNotFoundError for data_intelligence_hub.services.capability_matrix.

- [x] **Step 3: Add the response contracts**

Create apps/api/src/data_intelligence_hub/schemas/capability_matrix.py:

~~~python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityEvidence,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    ContractModel,
    PlatformId,
    ResourceType,
)


class CapabilityMatrixCell(ContractModel):
    platform: PlatformId
    access_channel: AccessChannel
    summary_status: CapabilityStatus
    status_counts: dict[CapabilityStatus, int]
    implementation_ids: list[str]
    assertion_ids: list[str]
    resource_types: list[ResourceType]
    operations: list[CapabilityOperation]
    constraint_codes: list[str]
    evidence_count: int = Field(ge=0)
    last_verified_at: datetime | None


class CapabilityMatrixSummary(ContractModel):
    cell_count: Literal[42]
    populated_cell_count: int = Field(ge=0, le=42)
    unknown_cell_count: int = Field(ge=0, le=42)
    implementation_count: int = Field(ge=0)
    assertion_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)


class CapabilityMatrixResponse(ContractModel):
    schema_version: Literal["capability_matrix.v1"]
    generated_at: datetime
    evidence_level: str
    provider_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    platforms: list[PlatformId]
    access_channels: list[AccessChannel]
    cells: list[CapabilityMatrixCell]
    summary: CapabilityMatrixSummary


class CapabilityImplementationDetail(ContractModel):
    schema_version: Literal["capability_implementation_detail.v1"]
    implementation: CapabilityImplementation
    assertions: list[CapabilityAssertion]
    evidence: list[CapabilityEvidence]
~~~

- [x] **Step 4: Add the not-found service error**

Append beside the existing Capability Catalog errors:

~~~python
class CapabilityImplementationNotFoundError(ServiceError):
    message = "capability_implementation_not_found"
~~~

- [x] **Step 5: Implement the pure read model**

Create apps/api/src/data_intelligence_hub/services/capability_matrix.py:

~~~python
from __future__ import annotations

from collections import Counter

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_matrix import (
    CapabilityImplementationDetail,
    CapabilityMatrixCell,
    CapabilityMatrixResponse,
    CapabilityMatrixSummary,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.exceptions import (
    CapabilityImplementationNotFoundError,
)

STATUS_PRIORITY = (
    CapabilityStatus.VERIFIED,
    CapabilityStatus.PARTIAL,
    CapabilityStatus.CANDIDATE,
    CapabilityStatus.BLOCKED,
    CapabilityStatus.UNSUPPORTED,
    CapabilityStatus.DEPRECATED,
    CapabilityStatus.UNKNOWN,
)


def _summary_status(
    counts: Counter[CapabilityStatus],
) -> CapabilityStatus:
    for status in STATUS_PRIORITY:
        if counts[status] > 0:
            return status
    return CapabilityStatus.UNKNOWN


def build_capability_matrix() -> CapabilityMatrixResponse:
    catalog = get_capability_catalog()
    cells: list[CapabilityMatrixCell] = []

    for platform in PlatformId:
        for access_channel in AccessChannel:
            implementations = [
                item
                for item in catalog.implementations
                if item.platform is platform and item.access_channel is access_channel
            ]
            implementation_ids = {
                item.implementation_id for item in implementations
            }
            assertions = [
                item
                for item in catalog.assertions
                if item.implementation_id in implementation_ids
            ]
            counts = Counter(item.support_status for item in assertions)
            if not assertions:
                counts[CapabilityStatus.UNKNOWN] = 1
            evidence_refs = {
                ref for assertion in assertions for ref in assertion.evidence_refs
            }
            cells.append(
                CapabilityMatrixCell(
                    platform=platform,
                    access_channel=access_channel,
                    summary_status=_summary_status(counts),
                    status_counts=dict(counts),
                    implementation_ids=sorted(implementation_ids),
                    assertion_ids=sorted(
                        item.assertion_id for item in assertions
                    ),
                    resource_types=sorted(
                        {item.resource_type for item in assertions},
                        key=lambda item: item.value,
                    ),
                    operations=sorted(
                        {item.operation for item in assertions},
                        key=lambda item: item.value,
                    ),
                    constraint_codes=sorted(
                        {
                            constraint.code
                            for assertion in assertions
                            for constraint in assertion.constraints
                        }
                    ),
                    evidence_count=len(evidence_refs),
                    last_verified_at=max(
                        (item.last_verified_at for item in assertions),
                        default=None,
                    ),
                )
            )

    populated = sum(bool(cell.assertion_ids) for cell in cells)
    return CapabilityMatrixResponse(
        schema_version="capability_matrix.v1",
        generated_at=catalog.generated_at,
        evidence_level=catalog.evidence_level,
        provider_call=False,
        production_write_allowed=False,
        platforms=list(PlatformId),
        access_channels=list(AccessChannel),
        cells=cells,
        summary=CapabilityMatrixSummary(
            cell_count=42,
            populated_cell_count=populated,
            unknown_cell_count=42 - populated,
            implementation_count=len(catalog.implementations),
            assertion_count=len(catalog.assertions),
            evidence_count=len(catalog.evidence),
        ),
    )


def list_capability_implementations(
    *,
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
) -> list[CapabilityImplementation]:
    items = get_capability_catalog().implementations
    if platform is not None:
        items = [item for item in items if item.platform is platform]
    if access_channel is not None:
        items = [
            item for item in items if item.access_channel is access_channel
        ]
    return sorted(items, key=lambda item: item.implementation_id)


def list_capability_assertions(
    *,
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
    resource_type: ResourceType | None = None,
    operation: CapabilityOperation | None = None,
    support_status: CapabilityStatus | None = None,
) -> list[CapabilityAssertion]:
    catalog = get_capability_catalog()
    implementation_ids = {
        item.implementation_id
        for item in catalog.implementations
        if (platform is None or item.platform is platform)
        and (
            access_channel is None
            or item.access_channel is access_channel
        )
    }
    items = [
        item
        for item in catalog.assertions
        if item.implementation_id in implementation_ids
        and (resource_type is None or item.resource_type is resource_type)
        and (operation is None or item.operation is operation)
        and (
            support_status is None
            or item.support_status is support_status
        )
    ]
    return sorted(items, key=lambda item: item.assertion_id)


def get_capability_implementation_detail(
    implementation_id: str,
) -> CapabilityImplementationDetail:
    catalog = get_capability_catalog()
    implementation = next(
        (
            item
            for item in catalog.implementations
            if item.implementation_id == implementation_id
        ),
        None,
    )
    if implementation is None:
        raise CapabilityImplementationNotFoundError
    assertions = [
        item
        for item in catalog.assertions
        if item.implementation_id == implementation_id
    ]
    evidence_refs = {
        ref for assertion in assertions for ref in assertion.evidence_refs
    }
    evidence = [
        item for item in catalog.evidence if item.evidence_id in evidence_refs
    ]
    return CapabilityImplementationDetail(
        schema_version="capability_implementation_detail.v1",
        implementation=implementation,
        assertions=sorted(assertions, key=lambda item: item.assertion_id),
        evidence=sorted(evidence, key=lambda item: item.evidence_id),
    )
~~~

- [x] **Step 6: Run the unit and static gates**

Run:

~~~bash
cd apps/api
uv run pytest tests/unit/test_capability_matrix.py -q
uv run ruff check src/data_intelligence_hub/schemas/capability_matrix.py src/data_intelligence_hub/services/capability_matrix.py src/data_intelligence_hub/services/exceptions.py tests/unit/test_capability_matrix.py
uv run mypy src/data_intelligence_hub/schemas/capability_matrix.py src/data_intelligence_hub/services/capability_matrix.py tests/unit/test_capability_matrix.py
~~~

Expected: 7 tests pass; ruff and mypy exit 0.

- [ ] **Step 7: Commit only after explicit commit authorization**

~~~bash
git add apps/api/src/data_intelligence_hub/schemas/capability_matrix.py apps/api/src/data_intelligence_hub/services/capability_matrix.py apps/api/src/data_intelligence_hub/services/exceptions.py apps/api/tests/unit/test_capability_matrix.py
git diff --cached --check
git commit -m "feat: add capability matrix read model"
~~~

---

### Task 3: Expose Authenticated Read-Only Capability APIs

**Files:**
- Create: apps/api/src/data_intelligence_hub/api/routes/capabilities.py
- Modify: apps/api/src/data_intelligence_hub/main.py:9-87
- Create: apps/api/tests/integration/test_capability_routes.py

**Interfaces:**
- Produces:
  - GET /api/capabilities/matrix
  - GET /api/capabilities/assertions
  - GET /api/capabilities/implementations
  - GET /api/capabilities/implementations/{implementation_id}

- [x] **Step 1: Write the route integration tests**

Create apps/api/tests/integration/test_capability_routes.py using the same SQLite/auth fixture pattern as test_social_provider_routes.py. The test bodies must be:

~~~python
@pytest.mark.asyncio
async def test_capability_routes_require_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/capabilities/matrix")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_capability_matrix_route_returns_explicit_cells(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    response = await client.get("/api/capabilities/matrix")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "capability_matrix.v1"
    assert len(payload["cells"]) == 42
    assert payload["summary"]["populated_cell_count"] == 7
    assert payload["summary"]["unknown_cell_count"] == 35
    assert payload["provider_call"] is False
    assert payload["production_write_allowed"] is False


@pytest.mark.asyncio
async def test_capability_assertion_filters_are_typed(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    response = await client.get(
        "/api/capabilities/assertions",
        params={
            "platform": "youtube",
            "access_channel": "official_authorized_api",
            "resource_type": "conversation",
            "operation": "list_enumerate",
            "support_status": "candidate",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["implementation_id"] == "youtube.v3"


@pytest.mark.asyncio
async def test_capability_filter_rejects_unknown_enum(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    response = await client.get(
        "/api/capabilities/assertions",
        params={"platform": "missing"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_capability_filter_returns_empty_list_for_valid_zero_result(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    response = await client.get(
        "/api/capabilities/assertions",
        params={
            "platform": "youtube",
            "access_channel": "authorized_browser",
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_capability_implementation_detail_and_404(
    client: AsyncClient,
) -> None:
    await register_and_login(client)
    found = await client.get(
        "/api/capabilities/implementations/youtube.v3"
    )
    missing = await client.get(
        "/api/capabilities/implementations/missing-provider"
    )

    assert found.status_code == 200
    assert found.json()["implementation"]["implementation_id"] == "youtube.v3"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "capability_implementation_not_found"


@pytest.mark.asyncio
async def test_capability_catalog_load_failure_is_explicit(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_and_login(client)

    def fail_catalog_load() -> CapabilityMatrixResponse:
        raise CapabilityCatalogLoadError

    monkeypatch.setattr(
        capability_routes,
        "build_capability_matrix",
        fail_catalog_load,
    )
    response = await client.get("/api/capabilities/matrix")

    assert response.status_code == 500
    assert response.json()["detail"] == "capability_catalog_load_failed"
~~~

Place this complete import/fixture/helper block before the tests; do not import another test module:

~~~python
from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.routes import capabilities as capability_routes
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.schemas.capability_matrix import CapabilityMatrixResponse
from data_intelligence_hub.services.exceptions import CapabilityCatalogLoadError


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
    await engine.dispose()


async def register_and_login(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "StrongPassword123!",
            "name": "Owner",
        },
    )
    assert response.status_code == 201
~~~

- [x] **Step 2: Run the integration tests to verify the red state**

~~~bash
cd apps/api
uv run pytest tests/integration/test_capability_routes.py -q
~~~

Expected: test collection fails with ModuleNotFoundError for data_intelligence_hub.api.routes.capabilities because the route module has not been created.

- [x] **Step 3: Implement the read-only router**

Create apps/api/src/data_intelligence_hub/api/routes/capabilities.py:

~~~python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_matrix import (
    CapabilityImplementationDetail,
    CapabilityMatrixResponse,
)
from data_intelligence_hub.services.capability_matrix import (
    build_capability_matrix,
    get_capability_implementation_detail,
    list_capability_assertions,
    list_capability_implementations,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityCatalogLoadError,
    CapabilityImplementationNotFoundError,
)

router = APIRouter(tags=["capabilities"])


@router.get("/matrix", response_model=CapabilityMatrixResponse)
async def read_capability_matrix(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityMatrixResponse:
    _ = context
    try:
        return build_capability_matrix()
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get("/assertions", response_model=list[CapabilityAssertion])
async def read_capability_assertions(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
    resource_type: ResourceType | None = None,
    operation: CapabilityOperation | None = None,
    support_status: CapabilityStatus | None = None,
) -> list[CapabilityAssertion]:
    _ = context
    try:
        return list_capability_assertions(
            platform=platform,
            access_channel=access_channel,
            resource_type=resource_type,
            operation=operation,
            support_status=support_status,
        )
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get(
    "/implementations",
    response_model=list[CapabilityImplementation],
)
async def read_capability_implementations(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    platform: PlatformId | None = None,
    access_channel: AccessChannel | None = None,
) -> list[CapabilityImplementation]:
    _ = context
    try:
        return list_capability_implementations(
            platform=platform,
            access_channel=access_channel,
        )
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.get(
    "/implementations/{implementation_id}",
    response_model=CapabilityImplementationDetail,
)
async def read_capability_implementation_detail(
    implementation_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CapabilityImplementationDetail:
    _ = context
    try:
        return get_capability_implementation_detail(implementation_id)
    except CapabilityCatalogLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except CapabilityImplementationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
~~~

- [x] **Step 4: Register the router**

Add the import beside the other route imports:

~~~python
from data_intelligence_hub.api.routes.capabilities import (
    router as capabilities_router,
)
~~~

Add this line immediately after the projects router:

~~~python
app.include_router(capabilities_router, prefix="/api/capabilities")
~~~

- [x] **Step 5: Run new and compatibility gates**

~~~bash
cd apps/api
uv run pytest tests/integration/test_capability_routes.py -q
uv run pytest tests/unit/test_capability_matrix.py tests/unit/test_capability_catalog.py tests/unit/test_social_provider_runtime.py tests/integration/test_social_provider_routes.py -q
uv run ruff check src/data_intelligence_hub/api/routes/capabilities.py src/data_intelligence_hub/main.py tests/integration/test_capability_routes.py
uv run mypy src tests
~~~

Expected: 7 new route tests pass; all capability/social regression tests pass; ruff and mypy exit 0.

- [ ] **Step 6: Commit only after explicit commit authorization**

~~~bash
git add apps/api/src/data_intelligence_hub/api/routes/capabilities.py apps/api/src/data_intelligence_hub/main.py apps/api/tests/integration/test_capability_routes.py
git diff --cached --check
git commit -m "feat: expose read-only capability APIs"
~~~

---

### Task 4: Add Web Capability Contracts, Mappers, And Mock-Only Fixtures

**Files:**
- Create: apps/web/src/types/capability.ts
- Create: apps/web/src/lib/api/capabilities.ts
- Create: apps/web/src/lib/capability-mock.ts
- Create: apps/web/tests/unit/capability-api.test.ts

**Interfaces:**
- Produces:
  - getCapabilityMatrix() -> Promise<CapabilityMatrix>
  - listCapabilityImplementations(filters?) -> Promise<CapabilityImplementation[]>
  - listCapabilityAssertions(filters?) -> Promise<CapabilityAssertion[]>
  - getCapabilityImplementationDetail(id) -> Promise<CapabilityImplementationDetail>

- [x] **Step 1: Write the mapper and mock-boundary tests**

Create apps/web/tests/unit/capability-api.test.ts:

~~~typescript
import { describe, expect, it } from "vitest";

import {
  buildCapabilityQuery,
  mapCapabilityImplementationDetail,
  mapCapabilityMatrixResponse,
} from "@/lib/api/capabilities";
import {
  buildMockCapabilityImplementationDetailDto,
  buildMockCapabilityMatrixDto,
} from "@/lib/capability-mock";

describe("capability API mappers", () => {
  it("maps all 42 cells and keeps boundary flags false", () => {
    const mapped = mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());

    expect(mapped.cells).toHaveLength(42);
    expect(mapped.summary.populatedCellCount).toBe(7);
    expect(mapped.summary.unknownCellCount).toBe(35);
    expect(mapped.providerCall).toBe(false);
    expect(mapped.productionWriteAllowed).toBe(false);
  });

  it("keeps official API cells candidate and browser cells unknown", () => {
    const mapped = mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());
    const youtubeOfficial = mapped.cells.find(
      (cell) =>
        cell.platform === "youtube" &&
        cell.accessChannel === "official_authorized_api",
    );
    const youtubeBrowser = mapped.cells.find(
      (cell) =>
        cell.platform === "youtube" &&
        cell.accessChannel === "authorized_browser",
    );

    expect(youtubeOfficial?.summaryStatus).toBe("candidate");
    expect(youtubeBrowser?.summaryStatus).toBe("unknown");
  });

  it("maps implementation detail without credential values", () => {
    const mapped = mapCapabilityImplementationDetail(
      buildMockCapabilityImplementationDetailDto("youtube.v3"),
    );

    expect(mapped.implementation.implementationId).toBe("youtube.v3");
    expect(mapped.implementation.requiredCredentials).toEqual(["api_key"]);
    expect(mapped.assertions.every((item) => item.support_status === "candidate")).toBe(true);
    expect(JSON.stringify(mapped)).not.toContain("credential_value");
  });

  it("marks mock evidence as fixture-only", () => {
    const dto = buildMockCapabilityMatrixDto();
    expect(dto.evidence_level).toBe("L2-fixture");
    expect(dto.provider_call).toBe(false);
    expect(dto.production_write_allowed).toBe(false);
  });

  it("serializes typed filters with backend query names", () => {
    expect(
      buildCapabilityQuery({
        platform: "youtube",
        accessChannel: "official_authorized_api",
        resourceType: "conversation",
        operation: "list_enumerate",
        supportStatus: "candidate",
      }).toString(),
    ).toBe(
      "platform=youtube&access_channel=official_authorized_api&resource_type=conversation&operation=list_enumerate&support_status=candidate",
    );
  });
});
~~~

- [x] **Step 2: Run the tests to verify the red state**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/capability-api.test.ts
~~~

Expected: Vitest reports module resolution errors for @/lib/api/capabilities and @/lib/capability-mock.

- [x] **Step 3: Define the capability types**

Create apps/web/src/types/capability.ts with these exact unions and public shapes:

~~~typescript
export type CapabilityPlatform =
  | "youtube"
  | "reddit"
  | "x"
  | "instagram"
  | "threads"
  | "tiktok"
  | "linkedin";

export type CapabilityAccessChannel =
  | "official_authorized_api"
  | "licensed_partner_data_service"
  | "public_web_feed"
  | "authorized_browser"
  | "managed_opaque_collector"
  | "authorized_export_import";

export type CapabilityStatus =
  | "unknown"
  | "candidate"
  | "verified"
  | "partial"
  | "blocked"
  | "unsupported"
  | "deprecated";

export type CapabilityResourceType =
  | "content"
  | "conversation"
  | "creator"
  | "topic"
  | "metrics"
  | "media_live"
  | "commerce_ads"
  | "relationship_graph";

export type CapabilityOperation =
  | "resolve_detail"
  | "search_discover"
  | "list_enumerate"
  | "monitor_incremental"
  | "backfill_history"
  | "batch_parse"
  | "export_download";

export type CapabilityMatrixCellDto = {
  platform: CapabilityPlatform;
  access_channel: CapabilityAccessChannel;
  summary_status: CapabilityStatus;
  status_counts: Partial<Record<CapabilityStatus, number>>;
  implementation_ids: string[];
  assertion_ids: string[];
  resource_types: CapabilityResourceType[];
  operations: CapabilityOperation[];
  constraint_codes: string[];
  evidence_count: number;
  last_verified_at: string | null;
};

export type CapabilityMatrixResponseDto = {
  schema_version: "capability_matrix.v1";
  generated_at: string;
  evidence_level: string;
  provider_call: false;
  production_write_allowed: false;
  platforms: CapabilityPlatform[];
  access_channels: CapabilityAccessChannel[];
  cells: CapabilityMatrixCellDto[];
  summary: {
    cell_count: 42;
    populated_cell_count: number;
    unknown_cell_count: number;
    implementation_count: number;
    assertion_count: number;
    evidence_count: number;
  };
};

export type CapabilityImplementationDto = {
  schema_version: "capability_implementation.v1";
  implementation_id: string;
  provider_id: string;
  platform: CapabilityPlatform;
  access_channel: CapabilityAccessChannel;
  delivery_form: string;
  deployment_mode: string;
  data_domains: string[];
  resource_groups: string[];
  official_docs: string[];
  sdk_selection: {
    package: string;
    import_name: string | null;
    source_url: string;
    status: "selected" | "candidate" | "manual_review" | "blocked";
    reason: string;
  } | null;
  live_adapter_strategy: string;
  auth_mode: string;
  quota_hint: Record<string, unknown>;
  cost_hint: Record<string, unknown>;
  policy_flags: string[];
  blocked_actions: string[];
  stability: "high" | "medium" | "low";
  self_host_priority: string;
  api_version: string;
  required_credentials: string[];
  supported_endpoints: string[];
  lifecycle_status: "active" | "limited" | "deprecated";
};

export type CapabilityAssertionDto = {
  schema_version: "capability_assertion.v1";
  assertion_id: string;
  implementation_id: string;
  resource_type: CapabilityResourceType;
  operation: CapabilityOperation;
  support_status: CapabilityStatus;
  source_resource_group: string;
  region_scope: string[];
  purpose_scope: string[];
  auth_scope: string[];
  field_contract: Record<string, unknown>;
  constraints: Array<{
    constraint_type: string;
    severity: "blocking" | "major" | "minor";
    code: string;
    details: Record<string, unknown>;
  }>;
  score_profile: Record<string, number>;
  evidence_refs: string[];
  last_verified_at: string;
};

export type CapabilityEvidenceDto = {
  schema_version: "capability_evidence.v1";
  evidence_id: string;
  evidence_type: string;
  source_url: string;
  source_version: string;
  observed_at: string;
  content_hash: string;
  hash_scope: "source_reference_only" | "retrieved_content";
  evidence_grade: string;
  provider_call_attempted: false;
  credential_read_attempted: false;
  live_client_created: false;
  production_write_attempted: false;
};

export type CapabilityImplementationDetailDto = {
  schema_version: "capability_implementation_detail.v1";
  implementation: CapabilityImplementationDto;
  assertions: CapabilityAssertionDto[];
  evidence: CapabilityEvidenceDto[];
};

export type CapabilityMatrixCell = {
  platform: CapabilityPlatform;
  accessChannel: CapabilityAccessChannel;
  summaryStatus: CapabilityStatus;
  statusCounts: Partial<Record<CapabilityStatus, number>>;
  implementationIds: string[];
  assertionIds: string[];
  resourceTypes: CapabilityResourceType[];
  operations: CapabilityOperation[];
  constraintCodes: string[];
  evidenceCount: number;
  lastVerifiedAt: string | null;
};

export type CapabilityMatrix = {
  schemaVersion: "capability_matrix.v1";
  generatedAt: string;
  evidenceLevel: string;
  providerCall: false;
  productionWriteAllowed: false;
  platforms: CapabilityPlatform[];
  accessChannels: CapabilityAccessChannel[];
  cells: CapabilityMatrixCell[];
  summary: {
    cellCount: 42;
    populatedCellCount: number;
    unknownCellCount: number;
    implementationCount: number;
    assertionCount: number;
    evidenceCount: number;
  };
};

export type CapabilityImplementation = {
  implementationId: string;
  providerId: string;
  platform: CapabilityPlatform;
  accessChannel: CapabilityAccessChannel;
  deliveryForm: string;
  deploymentMode: string;
  dataDomains: string[];
  resourceGroups: string[];
  officialDocs: string[];
  sdkSelection: CapabilityImplementationDto["sdk_selection"];
  authMode: string;
  quotaHint: Record<string, unknown>;
  costHint: Record<string, unknown>;
  policyFlags: string[];
  blockedActions: string[];
  stability: "high" | "medium" | "low";
  apiVersion: string;
  requiredCredentials: string[];
  supportedEndpoints: string[];
  lifecycleStatus: "active" | "limited" | "deprecated";
};

export type CapabilityAssertion = CapabilityAssertionDto;
export type CapabilityEvidence = CapabilityEvidenceDto;

export type CapabilityImplementationDetail = {
  schemaVersion: "capability_implementation_detail.v1";
  implementation: CapabilityImplementation;
  assertions: CapabilityAssertion[];
  evidence: CapabilityEvidence[];
};

export type CapabilityImplementationFilters = {
  platform?: CapabilityPlatform;
  accessChannel?: CapabilityAccessChannel;
};

export type CapabilityAssertionFilters = CapabilityImplementationFilters & {
  resourceType?: CapabilityResourceType;
  operation?: CapabilityOperation;
  supportStatus?: CapabilityStatus;
};
~~~

- [x] **Step 4: Implement mappers and API calls**

Create apps/web/src/lib/api/capabilities.ts. Use mapCapabilityMatrixResponse, mapCapabilityImplementation, and mapCapabilityImplementationDetail as exported pure functions. The API functions must use:

~~~typescript
const matrixPath = "/api/capabilities/matrix";
const assertionsPath = "/api/capabilities/assertions";
const implementationsPath = "/api/capabilities/implementations";
~~~

Non-mock mode must call apiFetch with these paths. Mock mode must call only the builders in capability-mock.ts. There must be no catch block that falls back from an API error to mock data.

The four public API functions must follow these bodies:

~~~typescript
export async function getCapabilityMatrix(): Promise<CapabilityMatrix> {
  if (mockApiEnabled) {
    return mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());
  }
  return mapCapabilityMatrixResponse(
    await apiFetch<CapabilityMatrixResponseDto>(matrixPath),
  );
}

export async function listCapabilityImplementations(
  filters: CapabilityImplementationFilters = {},
): Promise<
  CapabilityImplementation[]
> {
  if (mockApiEnabled) {
    return filterMockImplementations(
      buildMockCapabilityImplementations(),
      filters,
    );
  }
  const query = buildCapabilityQuery(filters);
  const response = await apiFetch<CapabilityImplementationDto[]>(
    appendCapabilityQuery(implementationsPath, query),
  );
  return response.map(mapCapabilityImplementation);
}

export async function listCapabilityAssertions(
  filters: CapabilityAssertionFilters = {},
): Promise<
  CapabilityAssertion[]
> {
  if (mockApiEnabled) {
    return filterMockAssertions(
      buildMockCapabilityAssertions(),
      buildMockCapabilityImplementations(),
      filters,
    );
  }
  const query = buildCapabilityQuery(filters);
  return apiFetch<CapabilityAssertionDto[]>(
    appendCapabilityQuery(assertionsPath, query),
  );
}

export async function getCapabilityImplementationDetail(
  implementationId: string,
): Promise<CapabilityImplementationDetail> {
  if (mockApiEnabled) {
    return mapCapabilityImplementationDetail(
      buildMockCapabilityImplementationDetailDto(implementationId),
    );
  }
  const response = await apiFetch<CapabilityImplementationDetailDto>(
    implementationsPath + "/" + encodeURIComponent(implementationId),
  );
  return mapCapabilityImplementationDetail(response);
}
~~~

Import CapabilityAssertionFilters and CapabilityImplementationFilters with the other capability types, then add these pure helpers to capabilities.ts:

~~~typescript
export function buildCapabilityQuery(
  filters: CapabilityAssertionFilters | CapabilityImplementationFilters,
): URLSearchParams {
  const query = new URLSearchParams();
  if (filters.platform) query.set("platform", filters.platform);
  if (filters.accessChannel) query.set("access_channel", filters.accessChannel);
  if ("resourceType" in filters && filters.resourceType) query.set("resource_type", filters.resourceType);
  if ("operation" in filters && filters.operation) query.set("operation", filters.operation);
  if ("supportStatus" in filters && filters.supportStatus) query.set("support_status", filters.supportStatus);
  return query;
}

function appendCapabilityQuery(path: string, query: URLSearchParams): string {
  const encoded = query.toString();
  return encoded ? `${path}?${encoded}` : path;
}

function filterMockImplementations(
  items: CapabilityImplementation[],
  filters: CapabilityImplementationFilters,
): CapabilityImplementation[] {
  return items.filter(
    (item) =>
      (!filters.platform || item.platform === filters.platform) &&
      (!filters.accessChannel || item.accessChannel === filters.accessChannel),
  );
}

function filterMockAssertions(
  assertions: CapabilityAssertion[],
  implementations: CapabilityImplementation[],
  filters: CapabilityAssertionFilters,
): CapabilityAssertion[] {
  const implementationById = new Map(
    implementations.map((item) => [item.implementationId, item]),
  );
  return assertions.filter((item) => {
    const implementation = implementationById.get(item.implementation_id);
    return Boolean(
      implementation &&
        (!filters.platform || implementation.platform === filters.platform) &&
        (!filters.accessChannel || implementation.accessChannel === filters.accessChannel) &&
        (!filters.resourceType || item.resource_type === filters.resourceType) &&
        (!filters.operation || item.operation === filters.operation) &&
        (!filters.supportStatus || item.support_status === filters.supportStatus),
    );
  });
}
~~~

These mock filters must not call fetch.

The cell mapper must be:

~~~typescript
function mapCapabilityMatrixCell(
  item: CapabilityMatrixCellDto,
): CapabilityMatrixCell {
  return {
    platform: item.platform,
    accessChannel: item.access_channel,
    summaryStatus: item.summary_status,
    statusCounts: item.status_counts,
    implementationIds: item.implementation_ids,
    assertionIds: item.assertion_ids,
    resourceTypes: item.resource_types,
    operations: item.operations,
    constraintCodes: item.constraint_codes,
    evidenceCount: item.evidence_count,
    lastVerifiedAt: item.last_verified_at,
  };
}
~~~

Add these complete public mappers:

~~~typescript
export function mapCapabilityMatrixResponse(
  response: CapabilityMatrixResponseDto,
): CapabilityMatrix {
  return {
    schemaVersion: response.schema_version,
    generatedAt: response.generated_at,
    evidenceLevel: response.evidence_level,
    providerCall: response.provider_call,
    productionWriteAllowed: response.production_write_allowed,
    platforms: response.platforms,
    accessChannels: response.access_channels,
    cells: response.cells.map(mapCapabilityMatrixCell),
    summary: {
      cellCount: response.summary.cell_count,
      populatedCellCount: response.summary.populated_cell_count,
      unknownCellCount: response.summary.unknown_cell_count,
      implementationCount: response.summary.implementation_count,
      assertionCount: response.summary.assertion_count,
      evidenceCount: response.summary.evidence_count,
    },
  };
}

export function mapCapabilityImplementation(
  item: CapabilityImplementationDto,
): CapabilityImplementation {
  return {
    implementationId: item.implementation_id,
    providerId: item.provider_id,
    platform: item.platform,
    accessChannel: item.access_channel,
    deliveryForm: item.delivery_form,
    deploymentMode: item.deployment_mode,
    dataDomains: item.data_domains,
    resourceGroups: item.resource_groups,
    officialDocs: item.official_docs,
    sdkSelection: item.sdk_selection,
    authMode: item.auth_mode,
    quotaHint: item.quota_hint,
    costHint: item.cost_hint,
    policyFlags: item.policy_flags,
    blockedActions: item.blocked_actions,
    stability: item.stability,
    apiVersion: item.api_version,
    requiredCredentials: item.required_credentials,
    supportedEndpoints: item.supported_endpoints,
    lifecycleStatus: item.lifecycle_status,
  };
}

export function mapCapabilityImplementationDetail(
  response: CapabilityImplementationDetailDto,
): CapabilityImplementationDetail {
  return {
    schemaVersion: response.schema_version,
    implementation: mapCapabilityImplementation(response.implementation),
    assertions: response.assertions,
    evidence: response.evidence,
  };
}
~~~

Do not copy live_adapter_strategy into the UI model because this Goal does not execute adapters.

- [x] **Step 5: Add deterministic mock-only builders**

Create apps/web/src/lib/capability-mock.ts. Build the matrix from the seven platforms and six channels, with candidate only for official_authorized_api and unknown for every other channel. Set evidence_level to L2-fixture and every side-effect flag to false.

Start the file with:

~~~typescript
import type {
  CapabilityAccessChannel,
  CapabilityAssertion,
  CapabilityEvidenceDto,
  CapabilityImplementation,
  CapabilityImplementationDetailDto,
  CapabilityImplementationDto,
  CapabilityMatrixCellDto,
  CapabilityMatrixResponseDto,
  CapabilityOperation,
  CapabilityPlatform,
  CapabilityResourceType,
} from "@/types/capability";
~~~

The implementation builder must expose these exact IDs:

~~~typescript
const mockImplementationIds = {
  youtube: "youtube.v3",
  reddit: "reddit.praw",
  x: "x.v2",
  instagram: "instagram_graph.v19",
  threads: "threads.graph.v1",
  tiktok: "tiktok_research",
  linkedin: "linkedin.mcdm",
} satisfies Record<CapabilityPlatform, string>;
~~~

Export all five builders consumed by Tasks 4-6:

~~~typescript
export function buildMockCapabilityMatrixDto(): CapabilityMatrixResponseDto;
export function buildMockCapabilityImplementations(): CapabilityImplementation[];
export function buildMockCapabilityAssertions(): CapabilityAssertion[];
export function buildMockCapabilityImplementationDetailDto(
  implementationId: string,
): CapabilityImplementationDetailDto;
export function buildMockCapabilityEvidence(): CapabilityEvidenceDto[];
~~~

Use these exact platform and channel arrays:

~~~typescript
const mockPlatforms: CapabilityPlatform[] = [
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
];

const mockChannels: CapabilityAccessChannel[] = [
  "official_authorized_api",
  "licensed_partner_data_service",
  "public_web_feed",
  "authorized_browser",
  "managed_opaque_collector",
  "authorized_export_import",
];
~~~

buildMockCapabilityMatrixDto must create cells with mockPlatforms.flatMap and mockChannels.map, so the fixture has 42 cells by construction. Official API cells receive one Implementation ID, five Assertion IDs, candidate status, and evidence_count=2. All other cells receive unknown status, no IDs, and evidence_count=0.

Use this exact matrix builder:

~~~typescript
export function buildMockCapabilityMatrixDto(): CapabilityMatrixResponseDto {
  const cells = mockPlatforms.flatMap((platform) =>
    mockChannels.map((accessChannel) => {
      const candidate =
        accessChannel === "official_authorized_api";
      const implementationId = mockImplementationIds[platform];
      return {
        platform,
        access_channel: accessChannel,
        summary_status: candidate ? "candidate" : "unknown",
        status_counts: candidate
          ? { candidate: 5 }
          : { unknown: 1 },
        implementation_ids: candidate ? [implementationId] : [],
        assertion_ids: candidate
          ? Array.from(
              { length: 5 },
              (_, index) =>
                implementationId + ":mock:" + String(index + 1),
            )
          : [],
        resource_types: candidate
          ? ["content", "conversation", "creator", "topic", "metrics"]
          : [],
        operations: candidate
          ? [
              "search_discover",
              "list_enumerate",
              "resolve_detail",
              "monitor_incremental",
              "batch_parse",
            ]
          : [],
        constraint_codes: candidate ? ["fixture_only"] : [],
        evidence_count: candidate ? 2 : 0,
        last_verified_at: candidate
          ? "2026-07-10T00:00:00Z"
          : null,
      } satisfies CapabilityMatrixCellDto;
    }),
  );
  return {
    schema_version: "capability_matrix.v1",
    generated_at: "2026-07-10T00:00:00Z",
    evidence_level: "L2-fixture",
    provider_call: false,
    production_write_allowed: false,
    platforms: mockPlatforms,
    access_channels: mockChannels,
    cells,
    summary: {
      cell_count: 42,
      populated_cell_count: 7,
      unknown_cell_count: 35,
      implementation_count: 7,
      assertion_count: 35,
      evidence_count: 14,
    },
  };
}
~~~

Add the remaining builders below buildMockCapabilityMatrixDto. This is an explicit Web mock fixture, not runtime capability truth; the Task 5 parity test reads the real backend Fixture to catch drift:

~~~typescript
const mockSupportedEndpoints: Record<CapabilityPlatform, string[]> = {
  youtube: ["search.list", "videos.list", "videos.insert", "commentThreads.list", "videos.getRating", "channels.list", "channels.update"],
  reddit: ["hot.list", "new.list", "comments.new", "search", "r/{subreddit}/about", "user.profile"],
  x: ["tweets/search/recent", "tweets/search/all", "tweets", "users/me", "users/by/username/:id"],
  instagram: ["media", "user_media", "mentions", "comments", "insights"],
  threads: ["threads", "users", "mentions", "media", "replies"],
  tiktok: ["video.search", "video.list", "comment.list", "user.info", "vce.batch_status"],
  linkedin: ["ugcPosts", "network_sizes", "organizations", "shares", "socialActions"],
};

const mockAssertionScopes = [
  ["content", "search_discover"],
  ["conversation", "list_enumerate"],
  ["creator", "resolve_detail"],
  ["topic", "monitor_incremental"],
  ["metrics", "batch_parse"],
] as const satisfies readonly (readonly [CapabilityResourceType, CapabilityOperation])[];

export function buildMockCapabilityImplementations(): CapabilityImplementation[] {
  return mockPlatforms.map((platform) => ({
    implementationId: mockImplementationIds[platform],
    providerId: mockImplementationIds[platform],
    platform,
    accessChannel: "official_authorized_api",
    deliveryForm: "authorized_api",
    deploymentMode: "fixture_only",
    dataDomains: ["social_content"],
    resourceGroups: ["content", "conversation", "creator", "topic", "metrics"],
    officialDocs: [`https://example.invalid/${platform}/official-docs`],
    sdkSelection: {
      package: `${platform}-sdk-candidate`,
      import_name: null,
      source_url: `https://example.invalid/${platform}/sdk`,
      status: "candidate",
      reason: "fixture-only UI contract",
    },
    authMode: platform === "youtube" ? "api_key" : "oauth_access_token",
    quotaHint: { mode: "fixture", requests: 0 },
    costHint: { currency: "none", provider_call: false },
    policyFlags: ["fixture_only", "manual_review"],
    blockedActions: ["provider_live_call", "production_write"],
    stability: "medium",
    apiVersion: "fixture-v1",
    requiredCredentials: [platform === "youtube" ? "api_key" : "access_token"],
    supportedEndpoints: mockSupportedEndpoints[platform],
    lifecycleStatus: "active",
  }));
}

export function buildMockCapabilityAssertions(): CapabilityAssertion[] {
  return buildMockCapabilityImplementations().flatMap((implementation) =>
    mockAssertionScopes.map(([resourceType, operation], index) => ({
      schema_version: "capability_assertion.v1",
      assertion_id: `${implementation.implementationId}:mock:${index + 1}`,
      implementation_id: implementation.implementationId,
      resource_type: resourceType,
      operation,
      support_status: "candidate",
      source_resource_group: resourceType,
      region_scope: ["global"],
      purpose_scope: ["market_research"],
      auth_scope: ["fixture_only"],
      field_contract: {},
      constraints: [{
        constraint_type: "execution_boundary",
        severity: "blocking",
        code: "fixture_only",
        details: { provider_call: false },
      }],
      score_profile: {
        coverage: 3,
        freshness: 3,
        history: 2,
        reliability: 5,
        schema_stability: 5,
        cost_efficiency: 3,
        maintainability: 4,
        evidence_confidence: 3,
      },
      evidence_refs: [
        `${implementation.implementationId}:evidence:contract`,
        `${implementation.implementationId}:evidence:boundary`,
      ],
      last_verified_at: "2026-07-10T00:00:00Z",
    })),
  );
}

export function buildMockCapabilityEvidence(): CapabilityEvidenceDto[] {
  return buildMockCapabilityImplementations().flatMap((implementation) =>
    ["contract", "boundary"].map((kind) => ({
      schema_version: "capability_evidence.v1",
      evidence_id: `${implementation.implementationId}:evidence:${kind}`,
      evidence_type: kind,
      source_url: `https://example.invalid/${implementation.platform}/${kind}`,
      source_version: "fixture-v1",
      observed_at: "2026-07-10T00:00:00Z",
      content_hash: `${implementation.implementationId}:${kind}:fixture`,
      hash_scope: "source_reference_only",
      evidence_grade: "L2-fixture",
      provider_call_attempted: false,
      credential_read_attempted: false,
      live_client_created: false,
      production_write_attempted: false,
    } satisfies CapabilityEvidenceDto)),
  );
}

function implementationToDto(
  item: CapabilityImplementation,
): CapabilityImplementationDto {
  return {
    schema_version: "capability_implementation.v1",
    implementation_id: item.implementationId,
    provider_id: item.providerId,
    platform: item.platform,
    access_channel: item.accessChannel,
    delivery_form: item.deliveryForm,
    deployment_mode: item.deploymentMode,
    data_domains: item.dataDomains,
    resource_groups: item.resourceGroups,
    official_docs: item.officialDocs,
    sdk_selection: item.sdkSelection,
    live_adapter_strategy: "not_enabled",
    auth_mode: item.authMode,
    quota_hint: item.quotaHint,
    cost_hint: item.costHint,
    policy_flags: item.policyFlags,
    blocked_actions: item.blockedActions,
    stability: item.stability,
    self_host_priority: "not_in_scope",
    api_version: item.apiVersion,
    required_credentials: item.requiredCredentials,
    supported_endpoints: item.supportedEndpoints,
    lifecycle_status: item.lifecycleStatus,
  };
}

export function buildMockCapabilityImplementationDetailDto(
  implementationId: string,
): CapabilityImplementationDetailDto {
  const implementation = buildMockCapabilityImplementations().find(
    (item) => item.implementationId === implementationId,
  );
  if (!implementation) {
    throw new Error("mock_capability_implementation_not_found");
  }
  const assertions = buildMockCapabilityAssertions().filter(
    (item) => item.implementation_id === implementationId,
  );
  const evidenceRefs = new Set(assertions.flatMap((item) => item.evidence_refs));
  return {
    schema_version: "capability_implementation_detail.v1",
    implementation: implementationToDto(implementation),
    assertions,
    evidence: buildMockCapabilityEvidence().filter((item) =>
      evidenceRefs.has(item.evidence_id),
    ),
  };
}
~~~

- [x] **Step 6: Run the focused Web gates**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/capability-api.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
~~~

Expected: 5 tests pass; TypeScript and ESLint exit 0.

- [ ] **Step 7: Commit only after explicit commit authorization**

~~~bash
git add apps/web/src/types/capability.ts apps/web/src/lib/api/capabilities.ts apps/web/src/lib/capability-mock.ts apps/web/tests/unit/capability-api.test.ts
git diff --cached --check
git commit -m "feat: add capability web contracts"
~~~

---

### Task 5: Convert API Market Data Into Presentation-Only Records

**Files:**
- Modify: apps/web/src/types/api-market.ts
- Modify: apps/web/src/lib/api-market-catalog.ts
- Create: apps/web/src/lib/capability-market.ts
- Modify: apps/web/src/components/api-market/api-market-workspace.tsx
- Modify: apps/web/src/components/api-market/api-market-detail-workspace.tsx
- Modify: apps/web/src/app/api-market/[endpointId]/page.tsx
- Modify: apps/web/tests/unit/api-market.test.ts

**Interfaces:**
- Produces:
  - ApiMarketEndpointPresentation
  - composeApiMarketEndpoints(presentations, implementations, assertions)
  - assertApiMarketPresentationParity(presentations, implementations)
  - findApiMarketPresentationById(endpointId)
  - listApiMarketPresentationsByProviderId(providerId)
  - findApiMarketEndpointById(endpoints, endpointId)
  - filterApiMarketEndpoints(endpoints, filters)
  - buildApiMarketStats(endpoints)

- [x] **Step 1: Write parity and composition tests**

Add these tests to apps/web/tests/unit/api-market.test.ts:

Add these imports and read the real backend Fixture only from the test process. The runtime Web bundle must never import this JSON file:

~~~typescript
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { mapCapabilityImplementation } from "@/lib/api/capabilities";
import type { CapabilityImplementationDto } from "@/types/capability";

function readCanonicalImplementations() {
  const fixturePath = resolve(
    process.cwd(),
    "../api/src/data_intelligence_hub/services/fixtures/capability_catalog_overseas_v2.json",
  );
  const parsed = JSON.parse(readFileSync(fixturePath, "utf8")) as {
    implementations: CapabilityImplementationDto[];
  };
  return parsed.implementations.map(mapCapabilityImplementation);
}
~~~

Replace direct reads from apiMarketEndpoints with one canonical composition fixture at the top of the describe block:

~~~typescript
const composedEndpoints = composeApiMarketEndpoints(
  apiMarketEndpointPresentations,
  buildMockCapabilityImplementations(),
  buildMockCapabilityAssertions(),
);
~~~

The existing find, filter, stats, and Preview Chain tests must pass composedEndpoints explicitly. The presentation-only lookup test must call findApiMarketPresentationById before capability detail is loaded.

~~~typescript
it("keeps every presentation endpoint backed by canonical implementation data", () => {
  expect(() =>
    assertApiMarketPresentationParity(
      apiMarketEndpointPresentations,
      buildMockCapabilityImplementations(),
    ),
  ).not.toThrow();
});

it("checks presentation parity against the real backend Fixture", () => {
  const implementations = readCanonicalImplementations();
  expect(
    implementations.reduce(
      (total, item) => total + item.supportedEndpoints.length,
      0,
    ),
  ).toBe(38);
  expect(() =>
    assertApiMarketPresentationParity(
      apiMarketEndpointPresentations,
      implementations,
    ),
  ).not.toThrow();
  const endpoints = composeApiMarketEndpoints(
    apiMarketEndpointPresentations,
    implementations,
    buildMockCapabilityAssertions(),
  );
  expect(endpoints).toHaveLength(38);
  expect(
    endpoints.filter((item) => item.presentationMode === "enhanced"),
  ).toHaveLength(18);
  expect(
    endpoints.filter((item) => item.presentationMode === "generic"),
  ).toHaveLength(20);
});

it("rejects a presentation endpoint absent from the implementation", () => {
  const invalid = [
    ...apiMarketEndpointPresentations,
    {
      ...apiMarketEndpointPresentations[0],
      id: "youtube-missing-endpoint",
      endpointId: "missing.endpoint",
    },
  ];
  expect(() =>
    assertApiMarketPresentationParity(
      invalid,
      buildMockCapabilityImplementations(),
    ),
  ).toThrow("api_market_presentation_endpoint_not_in_catalog");
});

it("composes capability facts without provider calls", () => {
  const endpoints = composeApiMarketEndpoints(
    apiMarketEndpointPresentations,
    buildMockCapabilityImplementations(),
    buildMockCapabilityAssertions(),
  );
  const endpoint = endpoints.find(
    (item) => item.id === "youtube-v3-commentthreads-list",
  );

  expect(endpoint?.providerId).toBe("youtube.v3");
  expect(endpoint?.accessChannel).toBe("official_authorized_api");
  expect(endpoint?.supportStatus).toBe("candidate");
  expect(endpoint?.providerCall).toBe(false);
  expect(endpoint?.productionWriteAllowed).toBe(false);
});

it("retains a backend-only endpoint with generic presentation", () => {
  const endpoints = composeApiMarketEndpoints(
    apiMarketEndpointPresentations,
    buildMockCapabilityImplementations(),
    buildMockCapabilityAssertions(),
  );
  const endpoint = endpoints.find(
    (item) =>
      item.providerId === "youtube.v3" && item.endpoint === "videos.insert",
  );

  expect(endpoint?.presentationMode).toBe("generic");
  expect(endpoint?.presentation).toBeNull();
  expect(endpoint?.title).toBe("videos.insert");
  expect(endpoint?.blockedActions.length).toBeGreaterThan(0);
});
~~~

- [x] **Step 2: Run the tests to verify the red state**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/api-market.test.ts
~~~

Expected: TypeScript/Vitest reports missing exports for apiMarketEndpointPresentations, assertApiMarketPresentationParity, and composeApiMarketEndpoints.

- [x] **Step 3: Split presentation fields from capability fields**

In apps/web/src/types/api-market.ts, replace ApiMarketEndpoint with:

~~~typescript
export type ApiMarketEndpointPresentation = {
  category: ApiMarketCategory;
  endpointId: string;
  id: string;
  method: ApiMarketMethod;
  priority: ApiMarketPriority;
  providerId: string;
  request: {
    parameters: ApiMarketParameter[];
    requestBodyExample?: Record<string, unknown>;
  };
  responsePreview: {
    sample: Record<string, unknown>;
    schemaVersion: string;
  };
  summary: string;
  title: string;
};

type ApiMarketEndpointCapabilityFields = {
  accessChannel: CapabilityAccessChannel;
  apiVersion: string;
  authMode: string;
  blockedActions: string[];
  costHint: string;
  credentialReadAttempted: false;
  dataDomains: string[];
  endpoint: string;
  id: string;
  liveClientCreated: false;
  officialDocs: string[];
  platform: ApiMarketPlatform;
  platformLabel: string;
  policyFlags: string[];
  providerCall: false;
  providerCallAttempted: false;
  providerId: string;
  productionWriteAllowed: false;
  quotaHint: string;
  requiredCredentials: string[];
  sdkPackage: string | null;
  sdkStatus: "selected" | "candidate" | "manual_review" | "blocked" | null;
  stability: ApiMarketStability;
  summary: string;
  supportStatus: CapabilityStatus;
  title: string;
};

export type ApiMarketEnhancedEndpoint = ApiMarketEndpointCapabilityFields & {
  category: ApiMarketCategory;
  method: ApiMarketMethod;
  presentation: ApiMarketEndpointPresentation;
  presentationMode: "enhanced";
  priority: ApiMarketPriority;
  request: ApiMarketEndpointPresentation["request"];
  responsePreview: ApiMarketEndpointPresentation["responsePreview"];
};

export type ApiMarketGenericEndpoint = ApiMarketEndpointCapabilityFields & {
  category: null;
  method: null;
  presentation: null;
  presentationMode: "generic";
  priority: null;
  request: null;
  responsePreview: null;
};

export type ApiMarketEndpoint =
  | ApiMarketEnhancedEndpoint
  | ApiMarketGenericEndpoint;

export type ApiMarketFilterState = {
  accessChannel: CapabilityAccessChannel | "all";
  category: ApiMarketCategory | "all";
  platform: ApiMarketPlatform | "all";
  priority: ApiMarketPriority | "all";
  query: string;
  status: CapabilityStatus | "all";
};

export type ApiMarketStats = {
  endpointCount: number;
  candidateCount: number;
  verifiedCount: number;
  unknownCount: number;
  platformCount: number;
  providerCallAttempted: false;
};
~~~

Import CapabilityAccessChannel and CapabilityStatus from @/types/capability.
Delete ApiMarketExecutionMode. Remove executionMode and stability from ApiMarketFilterState, and replace fixtureReadyCount, liveGatedCount, and p0Count with the canonical support-status counts above. ApiMarketStability remains only as a composed display field on ApiMarketEndpoint.

- [x] **Step 4: Remove duplicated platform profiles**

Delete platformProfiles and the endpoint() default-merging helper from api-market-catalog.ts.

Rename apiMarketEndpoints to apiMarketEndpointPresentations and keep only fields permitted by ApiMarketEndpointPresentation. Preserve the current 18 route IDs, titles, methods, endpoint identifiers, request examples, response samples, categories, priorities, and summaries.

For each current record, replace endpoint with endpointId and platform with providerId. The linkage key must be providerId + endpointId. Use the Provider IDs already present in the current records; do not infer Provider from platform and do not add a second platform-to-Provider mapping. Platform and platformLabel must be taken from the matched CapabilityImplementation during composition; platformLabel is produced by capabilityPlatformLabel(implementation.platform), not stored in Presentation.

The composer must call strict parity first, then iterate every CapabilityImplementation.supportedEndpoints entry. Join an optional Presentation by the exact providerId + endpointId key. For an enhanced match, preserve the presentation route ID and display fields. For a backend-only Endpoint, set presentation=null, presentationMode="generic", id=`generic:${implementationId}:${endpointId}`, title=endpointId, summary="无展示增强；仅显示规范能力事实", and method/category/priority/request/responsePreview=null. Obtain platform, auth, quota, cost, policies, blocked actions, data domains, credentials, SDK, stability, and API version from the Implementation. Derive supportStatus from that Implementation's assertions using the same priority as the backend and hard-code only providerCall=false, providerCallAttempted=false, credentialReadAttempted=false, liveClientCreated=false, and productionWriteAllowed=false. Convert quotaHint and costHint to display strings with a deterministic formatCapabilityHint helper: sort object keys, render primitive values as key=value, render nested values with JSON.stringify, and join entries with `; `. This preserves the existing React text boundary without copying capability facts into presentation data.

Keep the catalog helper contracts explicit and data-driven:

~~~typescript
export function findApiMarketPresentationById(
  endpointId: string,
): ApiMarketEndpointPresentation | null;

export function listApiMarketPresentationsByProviderId(
  providerId: string,
): ApiMarketEndpointPresentation[];

export function findApiMarketEndpointById(
  endpoints: ApiMarketEndpoint[],
  endpointId: string,
): ApiMarketEndpoint | null;

export function filterApiMarketEndpoints(
  endpoints: ApiMarketEndpoint[],
  filters: ApiMarketFilterState,
): ApiMarketEndpoint[];

export function buildApiMarketStats(
  endpoints: ApiMarketEndpoint[],
): ApiMarketStats;
~~~

findApiMarketPresentationById and listApiMarketPresentationsByProviderId are the only helpers allowed to read apiMarketEndpointPresentations directly. Both return records by exact equality and never add capability facts. The composed lookup, filter, and stats helpers must operate only on their endpoints argument. A non-all category or priority filter excludes generic records whose value is null. Filter the remaining fields by accessChannel, platform, status, and case-insensitive text query over title, summary, endpoint, provider ID, and platform label. Stats must count endpointCount, distinct platformCount, and candidate/verified/unknown supportStatus values; providerCallAttempted is always false.

- [x] **Step 5: Implement strict parity**

assertApiMarketPresentationParity must:

1. Read presentation.providerId as the linkage key.
2. Find that CapabilityImplementation.
3. Require presentation.endpointId in implementation.supportedEndpoints.
4. Throw api_market_presentation_implementation_not_found for a missing Implementation.
5. Throw api_market_presentation_endpoint_not_in_catalog for an extra endpoint.

Use these exact helpers after the presentation array in api-market-catalog.ts:

~~~typescript
const apiMarketStatusPriority: readonly CapabilityStatus[] = [
  "verified", "partial", "candidate", "blocked", "unsupported", "deprecated", "unknown",
];

function presentationKey(providerId: string, endpointId: string): string {
  return `${providerId}\u0000${endpointId}`;
}

function formatCapabilityHint(value: Record<string, unknown>): string {
  return Object.keys(value)
    .sort()
    .map((key) => {
      const item = value[key];
      return `${key}=${item !== null && typeof item === "object" ? JSON.stringify(item) : String(item)}`;
    })
    .join("; ");
}

export function assertApiMarketPresentationParity(
  presentations: ApiMarketEndpointPresentation[],
  implementations: CapabilityImplementation[],
): void {
  const implementationByProviderId = new Map<string, CapabilityImplementation>();
  for (const implementation of implementations) {
    if (implementationByProviderId.has(implementation.providerId)) {
      throw new Error("api_market_duplicate_provider_id");
    }
    implementationByProviderId.set(implementation.providerId, implementation);
  }
  const seen = new Set<string>();
  for (const presentation of presentations) {
    const key = presentationKey(presentation.providerId, presentation.endpointId);
    if (seen.has(key)) throw new Error("api_market_duplicate_presentation_key");
    seen.add(key);
    const implementation = implementationByProviderId.get(presentation.providerId);
    if (!implementation) {
      throw new Error("api_market_presentation_implementation_not_found");
    }
    if (!implementation.supportedEndpoints.includes(presentation.endpointId)) {
      throw new Error("api_market_presentation_endpoint_not_in_catalog");
    }
  }
}

export function composeApiMarketEndpoints(
  presentations: ApiMarketEndpointPresentation[],
  implementations: CapabilityImplementation[],
  assertions: CapabilityAssertion[],
): ApiMarketEndpoint[] {
  assertApiMarketPresentationParity(presentations, implementations);
  const presentationByKey = new Map(
    presentations.map((item) => [presentationKey(item.providerId, item.endpointId), item]),
  );
  return implementations.flatMap((implementation) => {
    const ownedAssertions = assertions.filter(
      (item) => item.implementation_id === implementation.implementationId,
    );
    const supportStatus = apiMarketStatusPriority.find((status) =>
      ownedAssertions.some((item) => item.support_status === status),
    ) ?? "unknown";
    return implementation.supportedEndpoints.map((endpointId) => {
      const presentation = presentationByKey.get(
        presentationKey(implementation.providerId, endpointId),
      ) ?? null;
      const capabilityFields = {
        accessChannel: implementation.accessChannel,
        apiVersion: implementation.apiVersion,
        authMode: implementation.authMode,
        blockedActions: implementation.blockedActions,
        costHint: formatCapabilityHint(implementation.costHint),
        credentialReadAttempted: false as const,
        dataDomains: implementation.dataDomains,
        endpoint: endpointId,
        liveClientCreated: false as const,
        officialDocs: implementation.officialDocs,
        platform: implementation.platform,
        platformLabel: capabilityPlatformLabel(implementation.platform),
        policyFlags: implementation.policyFlags,
        providerCall: false as const,
        providerCallAttempted: false as const,
        providerId: implementation.providerId,
        productionWriteAllowed: false as const,
        quotaHint: formatCapabilityHint(implementation.quotaHint),
        requiredCredentials: implementation.requiredCredentials,
        sdkPackage: implementation.sdkSelection?.package ?? null,
        sdkStatus: implementation.sdkSelection?.status ?? null,
        stability: implementation.stability,
        supportStatus,
      };
      if (presentation) {
        return {
          ...capabilityFields,
          category: presentation.category,
          id: presentation.id,
          method: presentation.method,
          presentation,
          presentationMode: "enhanced",
          priority: presentation.priority,
          request: presentation.request,
          responsePreview: presentation.responsePreview,
          summary: presentation.summary,
          title: presentation.title,
        } satisfies ApiMarketEndpoint;
      }
      return {
        ...capabilityFields,
        category: null,
        id: `generic:${implementation.implementationId}:${endpointId}`,
        method: null,
        presentation: null,
        presentationMode: "generic",
        priority: null,
        request: null,
        responsePreview: null,
        summary: "无展示增强；仅显示规范能力事实",
        title: endpointId,
      } satisfies ApiMarketEndpoint;
    });
  });
}

export function findApiMarketPresentationById(
  endpointId: string,
): ApiMarketEndpointPresentation | null {
  return apiMarketEndpointPresentations.find((item) => item.id === endpointId) ?? null;
}

export function listApiMarketPresentationsByProviderId(
  providerId: string,
): ApiMarketEndpointPresentation[] {
  return apiMarketEndpointPresentations.filter((item) => item.providerId === providerId);
}

export function findApiMarketEndpointById(
  endpoints: ApiMarketEndpoint[],
  endpointId: string,
): ApiMarketEndpoint | null {
  return endpoints.find((item) => item.id === endpointId) ?? null;
}

export function filterApiMarketEndpoints(
  endpoints: ApiMarketEndpoint[],
  filters: ApiMarketFilterState,
): ApiMarketEndpoint[] {
  const query = filters.query.trim().toLowerCase();
  return endpoints.filter((item) =>
    (filters.accessChannel === "all" || item.accessChannel === filters.accessChannel) &&
    (filters.category === "all" || item.category === filters.category) &&
    (filters.platform === "all" || item.platform === filters.platform) &&
    (filters.priority === "all" || item.priority === filters.priority) &&
    (filters.status === "all" || item.supportStatus === filters.status) &&
    (!query || [item.title, item.summary, item.endpoint, item.providerId, item.platformLabel].some((value) => value.toLowerCase().includes(query))),
  );
}

export function buildApiMarketStats(
  endpoints: ApiMarketEndpoint[],
): ApiMarketStats {
  return {
    endpointCount: endpoints.length,
    candidateCount: endpoints.filter((item) => item.supportStatus === "candidate").length,
    verifiedCount: endpoints.filter((item) => item.supportStatus === "verified").length,
    unknownCount: endpoints.filter((item) => item.supportStatus === "unknown").length,
    platformCount: new Set(endpoints.map((item) => item.platform)).size,
    providerCallAttempted: false,
  };
}
~~~

Import capabilityPlatformLabel from @/lib/capability-market and the CapabilityAssertion/CapabilityImplementation/CapabilityStatus types from @/types/capability. The 18 presentation records must use their existing route id, title, summary, category, priority, method, request, and response sample with only these key substitutions:

~~~typescript
{
  category: "comment_threads",
  endpointId: "commentThreads.list",
  id: "youtube-v3-commentthreads-list",
  method: "GET",
  priority: "p0",
  providerId: "youtube.v3",
  request: {
    parameters: [
      parameter("part", "query", "string", true, "Requested comment fields.", "snippet,replies"),
      parameter("videoId", "query", "string", true, "Video id.", "video_id"),
    ],
  },
  responsePreview: itemSample(
    "youtube.v3",
    "commentThreads.list",
    "social_comment.v1",
  ),
  summary: "Read public comment thread fixtures and prepare official comment collection gates.",
  title: "YouTube Comment Threads",
}
~~~

Apply the same direct providerId/endpointId substitution to all 18 existing records. Do not preserve platform, auth, policy, quota, cost, SDK, status, Evidence, or boundary fields in a Presentation record.

Update the pre-existing tests with these exact call-shape changes:

~~~typescript
const filtered = filterApiMarketEndpoints(composedEndpoints, {
  accessChannel: "all",
  category: "comment_threads",
  platform: "youtube",
  priority: "all",
  query: "commentThreads",
  status: "all",
});
const endpoint = findApiMarketEndpointById(
  composedEndpoints,
  "youtube-v3-commentthreads-list",
);
const stats = buildApiMarketStats(composedEndpoints);
const presentation = findApiMarketPresentationById(
  "youtube-v3-commentthreads-list",
);
~~~

The no-side-effect test must assert providerCall, providerCallAttempted, and productionWriteAllowed are false on every composed endpoint. The stats test must assert candidateCount is non-zero and must not assert the removed liveGatedCount or fixtureReadyCount fields. Both Preview Chain tests must resolve their endpoint from composedEndpoints before calling buildApiMarketPreviewChainInputs.

The composition test must also assert the composed count equals the sum of supportedEndpoints across all Implementations (38 for the current canonical Fixture), including generic entries. Generic entries render a canonical-facts summary in the existing workspace and do not link to /api-market/[endpointId] or expose Fixture sample/Preview actions; enhanced entries retain the existing detail route and Fixture Review path.

Create apps/web/src/lib/capability-market.ts in this task with the shared total labels needed by the migrated consumers:

~~~typescript
const capabilityStatusLabels: Record<CapabilityStatus, string> = {
  unknown: "尚无能力事实",
  candidate: "候选，尚不可执行",
  verified: "已核验",
  partial: "部分支持",
  blocked: "已阻断",
  unsupported: "不支持",
  deprecated: "已弃用",
};

const capabilityPlatformLabels: Record<CapabilityPlatform, string> = {
  youtube: "YouTube",
  reddit: "Reddit",
  x: "X",
  instagram: "Instagram",
  threads: "Threads",
  tiktok: "TikTok",
  linkedin: "LinkedIn",
};

export function capabilityStatusLabel(status: CapabilityStatus): string {
  return capabilityStatusLabels[status];
}

export function capabilityPlatformLabel(platform: CapabilityPlatform): string {
  return capabilityPlatformLabels[platform];
}
~~~

Import CapabilityPlatform and CapabilityStatus as types. Task 6 extends this same file with URL, scenario, matrix, and comparison helpers; it must not create a second label map.

- [x] **Step 6: Migrate the existing endpoint-list consumer**

Replace apps/web/src/components/api-market/api-market-workspace.tsx with this green transitional consumer. Task 7 later replaces it with the approved three-view workspace:

~~~typescript
"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useMemo, useState } from "react";

import {
  apiMarketEndpointPresentations,
  buildApiMarketStats,
  composeApiMarketEndpoints,
  filterApiMarketEndpoints,
} from "@/lib/api-market-catalog";
import {
  listCapabilityAssertions,
  listCapabilityImplementations,
} from "@/lib/api/capabilities";
import { capabilityStatusLabel } from "@/lib/capability-market";
import type { ApiMarketEndpoint, ApiMarketFilterState } from "@/types/api-market";

const initialFilters: ApiMarketFilterState = {
  accessChannel: "all",
  category: "all",
  platform: "all",
  priority: "all",
  query: "",
  status: "all",
};

export function ApiMarketWorkspace() {
  const [endpoints, setEndpoints] = useState<ApiMarketEndpoint[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filters, setFilters] = useState(initialFilters);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listCapabilityImplementations(),
      listCapabilityAssertions(),
    ])
      .then(([implementations, assertions]) => {
        if (!cancelled) {
          setEndpoints(
            composeApiMarketEndpoints(
              apiMarketEndpointPresentations,
              implementations,
              assertions,
            ),
          );
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setLoadError(
            caught instanceof Error ? caught.message : "api_market_unavailable",
          );
        }
      });
    return () => { cancelled = true; };
  }, []);

  const visible = useMemo(
    () => (endpoints ? filterApiMarketEndpoints(endpoints, filters) : []),
    [endpoints, filters],
  );
  const stats = useMemo(
    () => (endpoints ? buildApiMarketStats(endpoints) : null),
    [endpoints],
  );
  if (loadError) return <p role="alert">{loadError} · 未使用静态能力事实回退</p>;
  if (!endpoints || !stats) return <p role="status">正在加载规范能力事实…</p>;

  return (
    <div className="grid gap-5">
      <section><h2>Capability Endpoint</h2><p>{stats.platformCount} platforms · {stats.endpointCount} endpoints · {stats.candidateCount} candidate · {stats.verifiedCount} verified · {stats.unknownCount} unknown</p><p>provider_call_attempted={String(stats.providerCallAttempted)}</p></section>
      <section aria-label="Endpoint 筛选" className="grid gap-2 md:grid-cols-3">
        <input aria-label="搜索 Endpoint" onChange={(event) => setFilters((value) => ({ ...value, query: event.target.value }))} value={filters.query} />
        {(["platform", "accessChannel", "category", "priority", "status"] as const).map((key) => <input aria-label={key} key={key} onChange={(event) => setFilters((value) => ({ ...value, [key]: event.target.value || "all" }) as ApiMarketFilterState)} value={filters[key]} />)}
      </section>
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visible.map((endpoint) => <article className="rounded-2xl border p-4" key={endpoint.id}>
          <h2>{endpoint.title}</h2><p>{endpoint.platformLabel} · {endpoint.providerId}</p><p>{endpoint.endpoint}</p>
          <p>{capabilityStatusLabel(endpoint.supportStatus)}</p>
          {endpoint.supportStatus === "candidate" ? <p>未经 live verification，尚不可执行。</p> : null}
          <p>{endpoint.costHint}</p><p>{endpoint.dataDomains.join(", ")}</p>
          <p>credentialReadAttempted={String(endpoint.credentialReadAttempted)} · liveClientCreated={String(endpoint.liveClientCreated)}</p>
          {endpoint.presentationMode === "enhanced" ? <><Link href={`/api-market/${endpoint.id}` as Route}>查看详情</Link><Link href={`/automation?platform=${endpoint.platform}&endpoint=${encodeURIComponent(endpoint.endpoint)}` as Route}>生成预案</Link></> : <p>无展示增强；仅显示规范能力事实，不提供 Fixture Preview。</p>}
        </article>)}
      </section>
    </div>
  );
}
~~~

- [x] **Step 7: Add the canonical detail loader around the existing Fixture Review**

Migrate ApiMarketDetailWorkspace in this task, not a later task:

~~~typescript
type ApiMarketDetailWorkspaceProps = {
  presentation: ApiMarketEndpointPresentation;
};
~~~

The server page must call findApiMarketPresentationById(endpointId), use presentation title and endpointId only for the AppShell title/description, and pass presentation to the client workspace. The client workspace must first call listCapabilityImplementations(), require exactly one item whose providerId equals presentation.providerId, then call getCapabilityImplementationDetail(matched.implementationId). Call composeApiMarketEndpoints([presentation], [detail.implementation], detail.assertions), then select the one item whose id equals presentation.id and require presentationMode="enhanced". The existing Fixture Preview Chain must receive only that selected endpoint; the other generic supported endpoints returned by the composer stay out of this route. Never pass providerId to an API whose path parameter is implementationId.

Before canonical detail resolves, show a loading state and do not call any Social Provider preview helper. When detail loading or composition fails, show the exact API/Error message and the back link; do not render auth, policy, status, cost, quota, credential names, or Fixture Preview actions from presentation data. Keep every existing explicit Preview/Dry-run authorization boundary unchanged.

In api-market-detail-workspace.tsx, add useEffect to the existing React import; import getCapabilityImplementationDetail/listCapabilityImplementations, composeApiMarketEndpoints/findApiMarketEndpointById, capabilityStatusLabel, ApiMarketEndpointPresentation, and ApiMarketEnhancedEndpoint. Rename the current exported function to the private `ApiMarketEnhancedDetail` without changing its Preview action bodies, and add this exported loader before it:

~~~typescript
export function ApiMarketDetailWorkspace({
  presentation,
}: ApiMarketDetailWorkspaceProps) {
  const [endpoint, setEndpoint] = useState<ApiMarketEnhancedEndpoint | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const implementations = await listCapabilityImplementations();
      const matches = implementations.filter(
        (item) => item.providerId === presentation.providerId,
      );
      if (matches.length !== 1) {
        throw new Error("api_market_presentation_implementation_not_found");
      }
      const detail = await getCapabilityImplementationDetail(
        matches[0]!.implementationId,
      );
      const composed = composeApiMarketEndpoints(
        [presentation],
        [detail.implementation],
        detail.assertions,
      );
      const selected = findApiMarketEndpointById(composed, presentation.id);
      if (!selected || selected.presentationMode !== "enhanced") {
        throw new Error("api_market_enhanced_endpoint_not_found");
      }
      if (!cancelled) setEndpoint(selected);
    }
    load().catch((caught: unknown) => {
      if (!cancelled) {
        setLoadError(
          caught instanceof Error ? caught.message : "api_market_detail_unavailable",
        );
      }
    });
    return () => { cancelled = true; };
  }, [presentation]);

  if (loadError) {
    return <section><Link href="/api-market">返回能力市场</Link><p role="alert">{loadError}</p></section>;
  }
  if (!endpoint) {
    return <p role="status">正在加载规范能力事实…</p>;
  }
  return <ApiMarketEnhancedDetail endpoint={endpoint} />;
}
~~~

Immediately below the loader, change only the existing function declaration as follows; its current body stays attached to the renamed function:

~~~diff
-export function ApiMarketDetailWorkspace({ endpoint }: { endpoint: ApiMarketEndpoint }) {
+function ApiMarketEnhancedDetail({ endpoint }: { endpoint: ApiMarketEnhancedEndpoint }) {
~~~

Inside that private function body, make exactly two field substitutions: replace `endpoint.executionMode` with `capabilityStatusLabel(endpoint.supportStatus)` and replace `endpoint.dataDomain.join(", ")` with `endpoint.dataDomains.join(", ")`. Because the private prop is ApiMarketEnhancedEndpoint, request and responsePreview remain non-null without assertions.

- [x] **Step 8: Switch the dynamic route to presentation identity**

Replace apps/web/src/app/api-market/[endpointId]/page.tsx with:

~~~typescript
import { notFound } from "next/navigation";

import { ApiMarketDetailWorkspace } from "@/components/api-market/api-market-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";
import { findApiMarketPresentationById } from "@/lib/api-market-catalog";

export default async function ApiMarketEndpointPage({
  params,
}: {
  params: Promise<{ endpointId: string }>;
}) {
  const { endpointId } = await params;
  const presentation = findApiMarketPresentationById(endpointId);
  if (!presentation) notFound();
  return (
    <AppShell
      brief="展示增强只提供 Fixture Review；能力事实由后端 Capability API 加载。"
      description={presentation.endpointId}
      signals={["Fixture Review", "provider_call=false", "production unchanged"]}
      title={presentation.title}
    >
      <ApiMarketDetailWorkspace presentation={presentation} />
    </AppShell>
  );
}
~~~

- [x] **Step 9: Run API Market and type gates**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/api-market.test.ts tests/unit/capability-api.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm --dir apps/web build
~~~

Expected: all tests in both files pass; TypeScript, ESLint, and build exit 0. No consumer imports ApiMarketExecutionMode or reads executionMode, fixtureReadyCount, liveGatedCount, or the old apiMarketEndpoints export.

- [ ] **Step 10: Commit only after explicit commit authorization**

~~~bash
git add apps/web/src/types/api-market.ts apps/web/src/lib/api-market-catalog.ts apps/web/src/lib/capability-market.ts apps/web/src/components/api-market/api-market-workspace.tsx apps/web/src/components/api-market/api-market-detail-workspace.tsx 'apps/web/src/app/api-market/[endpointId]/page.tsx' apps/web/tests/unit/api-market.test.ts
git diff --cached --check
git commit -m "refactor: make API market presentation-only"
~~~

---

### Task 6: Extend Capability Market View Models And URL State

**Files:**
- Modify: apps/web/src/lib/capability-market.ts
- Create: apps/web/tests/unit/capability-market.test.ts

**Interfaces:**
- Produces:
  - parseCapabilityMarketView(value) -> "scenarios" | "matrix" | "list"
  - parseCapabilityMarketFilters(search) -> CapabilityMarketFilters
  - updateCapabilityMarketQuery(search, patch) -> string
  - filterCapabilityMatrixCells(cells, filters)
  - filterCapabilityImplementations(implementations, assertions, filters)
  - groupCapabilityScenarios(assertions)
  - capabilityStatusLabel(status)

- [x] **Step 1: Write the view-model tests**

Create apps/web/tests/unit/capability-market.test.ts:

~~~typescript
import { describe, expect, it } from "vitest";

import {
  capabilityStatusLabel,
  filterCapabilityImplementations,
  filterCapabilityMatrixCells,
  groupCapabilityScenarios,
  parseCapabilityMarketFilters,
  parseCapabilityMarketView,
  updateCapabilityMarketQuery,
} from "@/lib/capability-market";
import {
  buildMockCapabilityAssertions,
  buildMockCapabilityMatrixDto,
} from "@/lib/capability-mock";
import { mapCapabilityMatrixResponse } from "@/lib/api/capabilities";

describe("capability market view model", () => {
  it("normalizes view values", () => {
    expect(parseCapabilityMarketView("matrix")).toBe("matrix");
    expect(parseCapabilityMarketView("list")).toBe("list");
    expect(parseCapabilityMarketView("missing")).toBe("scenarios");
    expect(parseCapabilityMarketView(null)).toBe("scenarios");
  });

  it("preserves unrelated query parameters", () => {
    expect(
      updateCapabilityMarketQuery("project_id=p1&view=list", {
        view: "matrix",
        platform: "youtube",
        accessChannel: "official_authorized_api",
        status: "candidate",
      }),
    ).toBe(
      "project_id=p1&view=matrix&platform=youtube&access_channel=official_authorized_api&status=candidate",
    );
  });

  it("parses valid filters and drops invalid enum values", () => {
    expect(
      parseCapabilityMarketFilters(
        "platform=reddit&access_channel=authorized_browser&resource_type=conversation&operation=list_enumerate&status=candidate&q=voc",
      ),
    ).toEqual({
      platform: "reddit",
      accessChannel: "authorized_browser",
      resourceType: "conversation",
      operation: "list_enumerate",
      status: "candidate",
      query: "voc",
    });
    expect(
      parseCapabilityMarketFilters("platform=missing&status=made_up"),
    ).toEqual({});
  });

  it("filters matrix cells without removing explicit unknown cells by default", () => {
    const cells = mapCapabilityMatrixResponse(
      buildMockCapabilityMatrixDto(),
    ).cells;
    expect(filterCapabilityMatrixCells(cells, {})).toHaveLength(42);
    expect(
      filterCapabilityMatrixCells(cells, { platform: "reddit" }),
    ).toHaveLength(6);
  });

  it("groups assertions into fixed business scenarios", () => {
    const groups = groupCapabilityScenarios(
      buildMockCapabilityAssertions(),
    );
    expect(groups.map((item) => item.id)).toEqual([
      "market-monitoring",
      "keyword-discovery",
      "content-detail",
      "conversation-voc",
      "creator-tracking",
      "incremental-monitoring",
      "batch-parsing",
      "export-delivery",
    ]);
  });

  it("filters implementations through their assertion scope", () => {
    const results = filterCapabilityImplementations(
      buildMockCapabilityImplementations(),
      buildMockCapabilityAssertions(),
      {
        platform: "youtube",
        resourceType: "conversation",
        status: "candidate",
      },
    );
    expect(results.map((item) => item.implementationId)).toEqual([
      "youtube.v3",
    ]);
  });

  it("uses explicit Chinese labels for every status", () => {
    expect(capabilityStatusLabel("candidate")).toBe("候选，尚不可执行");
    expect(capabilityStatusLabel("unknown")).toBe("尚无能力事实");
  });

  it("allows only two or three comparable implementations", () => {
    const base = mapCapabilityImplementationDetail(
      buildMockCapabilityImplementationDetailDto("youtube.v3"),
    );
    const clone = (implementationId: string) => ({
      ...base,
      implementation: {
        ...base.implementation,
        implementationId,
        providerId: implementationId,
      },
      assertions: base.assertions.map((item) => ({
        ...item,
        assertion_id: item.assertion_id.replace("youtube.v3", implementationId),
        implementation_id: implementationId,
      })),
    });
    const second = clone("youtube.fixture-alternate");
    const third = clone("youtube.fixture-third");

    const comparison = buildImplementationComparison([base, second]);
    expect(comparison.columns.map((item) => item.implementationId)).toEqual([
      "youtube.v3",
      "youtube.fixture-alternate",
    ]);
    expect(Object.keys(comparison.columns[0]!.scores)).toEqual([
      "coverage",
      "freshness",
      "history",
      "reliability",
      "schema_stability",
      "cost_efficiency",
      "maintainability",
      "evidence_confidence",
    ]);
    expect(comparison.columns[0]!.constraintCodes.length).toBeGreaterThan(0);
    expect(comparison.columns[0]!.evidence.length).toBeGreaterThan(0);
    expect(buildImplementationComparison([base, second, third]).columns).toHaveLength(3);
    expect(() => buildImplementationComparison([base])).toThrow(
      "capability_comparison_requires_two_or_three",
    );
  });
});
~~~

Add buildMockCapabilityImplementationDetailDto, buildMockCapabilityImplementations, buildImplementationComparison, and mapCapabilityImplementationDetail to the imports.

- [x] **Step 2: Run the tests to verify the red state**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/capability-market.test.ts
~~~

Expected: TypeScript/Vitest reports missing exports for parseCapabilityMarketFilters, filterCapabilityImplementations, groupCapabilityScenarios, and buildImplementationComparison because Task 5 created only the shared label helpers.

- [x] **Step 3: Implement deterministic view helpers**

Extend capability-market.ts with:

~~~typescript
import type {
  CapabilityAccessChannel,
  CapabilityAssertion,
  CapabilityEvidence,
  CapabilityImplementation,
  CapabilityImplementationDetail,
  CapabilityMatrixCell,
  CapabilityOperation,
  CapabilityPlatform,
  CapabilityResourceType,
  CapabilityStatus,
} from "@/types/capability";

export type CapabilityMarketView = "scenarios" | "matrix" | "list";

export type CapabilityMarketFilters = {
  platform?: CapabilityPlatform;
  accessChannel?: CapabilityAccessChannel;
  resourceType?: CapabilityResourceType;
  operation?: CapabilityOperation;
  status?: CapabilityStatus;
  query?: string;
};

export type CapabilityMarketQueryPatch = {
  view?: CapabilityMarketView | null;
  platform?: CapabilityPlatform | null;
  accessChannel?: CapabilityAccessChannel | null;
  resourceType?: CapabilityResourceType | null;
  operation?: CapabilityOperation | null;
  status?: CapabilityStatus | null;
  query?: string | null;
};

export function parseCapabilityMarketView(
  value: string | null | undefined,
): CapabilityMarketView {
  return value === "matrix" || value === "list" ? value : "scenarios";
}

export function updateCapabilityMarketQuery(
  search: string,
  patch: CapabilityMarketQueryPatch,
): string {
  const query = new URLSearchParams(search);
  setQueryValue(query, "view", patch.view);
  setQueryValue(query, "platform", patch.platform);
  setQueryValue(query, "access_channel", patch.accessChannel);
  setQueryValue(query, "resource_type", patch.resourceType);
  setQueryValue(query, "operation", patch.operation);
  setQueryValue(query, "status", patch.status);
  setQueryValue(
    query,
    "q",
    patch.query === undefined ? undefined : patch.query?.trim() ?? null,
  );
  return query.toString();
}

function setQueryValue(
  query: URLSearchParams,
  key: string,
  value: string | null | undefined,
) {
  if (value === null || value === "") query.delete(key);
  else if (value !== undefined) query.set(key, value);
}
~~~

Add these total arrays, parser, and filters in the same file:

~~~typescript
export const capabilityPlatforms: readonly CapabilityPlatform[] = [
  "youtube", "reddit", "x", "instagram", "threads", "tiktok", "linkedin",
];
export const capabilityAccessChannels: readonly CapabilityAccessChannel[] = [
  "official_authorized_api",
  "licensed_partner_data_service",
  "public_web_feed",
  "authorized_browser",
  "managed_opaque_collector",
  "authorized_export_import",
];
export const capabilityResourceTypes: readonly CapabilityResourceType[] = [
  "content", "conversation", "creator", "topic", "metrics", "media_live",
  "commerce_ads", "relationship_graph",
];
export const capabilityOperations: readonly CapabilityOperation[] = [
  "resolve_detail", "search_discover", "list_enumerate",
  "monitor_incremental", "backfill_history", "batch_parse", "export_download",
];
export const capabilityStatuses: readonly CapabilityStatus[] = [
  "unknown", "candidate", "verified", "partial", "blocked", "unsupported",
  "deprecated",
];

function parseEnum<T extends string>(
  value: string | null,
  allowed: readonly T[],
): T | undefined {
  return value && allowed.includes(value as T) ? (value as T) : undefined;
}

export function parseCapabilityMarketFilters(
  search: string,
): CapabilityMarketFilters {
  const query = new URLSearchParams(search);
  const trimmedQuery = query.get("q")?.trim();
  return {
    platform: parseEnum(query.get("platform"), capabilityPlatforms),
    accessChannel: parseEnum(
      query.get("access_channel"),
      capabilityAccessChannels,
    ),
    resourceType: parseEnum(
      query.get("resource_type"),
      capabilityResourceTypes,
    ),
    operation: parseEnum(query.get("operation"), capabilityOperations),
    status: parseEnum(query.get("status"), capabilityStatuses),
    ...(trimmedQuery ? { query: trimmedQuery } : {}),
  };
}

export function filterCapabilityMatrixCells(
  cells: CapabilityMatrixCell[],
  filters: CapabilityMarketFilters,
): CapabilityMatrixCell[] {
  return cells.filter(
    (cell) =>
      (!filters.platform || cell.platform === filters.platform) &&
      (!filters.accessChannel || cell.accessChannel === filters.accessChannel) &&
      (!filters.status || cell.summaryStatus === filters.status),
  );
}

export function filterCapabilityImplementations(
  implementations: CapabilityImplementation[],
  assertions: CapabilityAssertion[],
  filters: CapabilityMarketFilters,
): CapabilityImplementation[] {
  const normalizedQuery = filters.query?.toLowerCase();
  return implementations.filter((implementation) => {
    if (filters.platform && implementation.platform !== filters.platform) return false;
    if (
      filters.accessChannel &&
      implementation.accessChannel !== filters.accessChannel
    ) return false;
    const owned = assertions.filter(
      (item) => item.implementation_id === implementation.implementationId,
    );
    const assertionMatch = owned.some(
      (item) =>
        (!filters.resourceType || item.resource_type === filters.resourceType) &&
        (!filters.operation || item.operation === filters.operation) &&
        (!filters.status || item.support_status === filters.status),
    );
    if (
      (filters.resourceType || filters.operation || filters.status) &&
      !assertionMatch
    ) return false;
    if (!normalizedQuery) return true;
    return [
      implementation.implementationId,
      implementation.providerId,
      implementation.platform,
      implementation.deliveryForm,
      ...implementation.resourceGroups,
      ...implementation.dataDomains,
    ].some((value) => value.toLowerCase().includes(normalizedQuery));
  });
}
~~~

Define the eight scenario IDs exactly as tested, even when a current scenario has zero matching Assertions. Assign assertions by:

- market-monitoring: resource_type=metrics
- keyword-discovery: operation=search_discover or resource_type=topic
- content-detail: operation=resolve_detail or resource_type=content
- conversation-voc: resource_type=conversation
- creator-tracking: resource_type=creator
- incremental-monitoring: operation=monitor_incremental
- batch-parsing: operation=batch_parse
- export-delivery: operation=export_download

Implement the fixed scenario projection exactly as follows. It preserves all eight groups, including empty ones, and deduplicates Assertions by assertion_id:

~~~typescript
export type CapabilityScenario = {
  id: string;
  label: string;
  assertions: CapabilityAssertion[];
};

const scenarioDefinitions = [
  { id: "market-monitoring", label: "市场监测", matches: (item: CapabilityAssertion) => item.resource_type === "metrics" },
  { id: "keyword-discovery", label: "关键词发现", matches: (item: CapabilityAssertion) => item.operation === "search_discover" || item.resource_type === "topic" },
  { id: "content-detail", label: "内容详情", matches: (item: CapabilityAssertion) => item.operation === "resolve_detail" || item.resource_type === "content" },
  { id: "conversation-voc", label: "评论与对话", matches: (item: CapabilityAssertion) => item.resource_type === "conversation" },
  { id: "creator-tracking", label: "创作者", matches: (item: CapabilityAssertion) => item.resource_type === "creator" },
  { id: "incremental-monitoring", label: "增量监测", matches: (item: CapabilityAssertion) => item.operation === "monitor_incremental" },
  { id: "batch-parsing", label: "批量解析", matches: (item: CapabilityAssertion) => item.operation === "batch_parse" },
  { id: "export-delivery", label: "导出", matches: (item: CapabilityAssertion) => item.operation === "export_download" },
] as const;

export function groupCapabilityScenarios(
  assertions: CapabilityAssertion[],
): CapabilityScenario[] {
  return scenarioDefinitions.map((definition) => {
    const seen = new Set<string>();
    const matches = assertions.filter((item) => {
      if (!definition.matches(item) || seen.has(item.assertion_id)) return false;
      seen.add(item.assertion_id);
      return true;
    });
    return { id: definition.id, label: definition.label, assertions: matches };
  });
}
~~~

Retain the total capabilityStatusLabels Record created in Task 5; do not add a fallback to raw engineering text.

Implement buildImplementationComparison with these public result shapes:

~~~typescript
export const capabilityScoreKeys = [
  "coverage",
  "freshness",
  "history",
  "reliability",
  "schema_stability",
  "cost_efficiency",
  "maintainability",
  "evidence_confidence",
] as const;

export type CapabilityScoreKey = (typeof capabilityScoreKeys)[number];

export type CapabilityComparisonColumn = {
  implementationId: string;
  providerId: string;
  scores: Record<CapabilityScoreKey, number | null>;
  constraintCodes: string[];
  evidence: CapabilityEvidence[];
};

export type CapabilityImplementationComparison = {
  platform: CapabilityPlatform;
  sharedResources: CapabilityResourceType[];
  sharedOperations: CapabilityOperation[];
  columns: CapabilityComparisonColumn[];
};

export function buildImplementationComparison(
  details: CapabilityImplementationDetail[],
): CapabilityImplementationComparison {
  if (details.length < 2 || details.length > 3) {
    throw new Error("capability_comparison_requires_two_or_three");
  }
  const platforms = new Set(
    details.map((item) => item.implementation.platform),
  );
  if (platforms.size !== 1) {
    throw new Error("capability_comparison_requires_same_platform");
  }
  const sharedResources = intersection(
    details.map((detail) =>
      detail.assertions.map((item) => item.resource_type),
    ),
  );
  const sharedOperations = intersection(
    details.map((detail) =>
      detail.assertions.map((item) => item.operation),
    ),
  );
  if (sharedResources.length === 0 && sharedOperations.length === 0) {
    throw new Error("capability_comparison_requires_shared_scope");
  }

  const columns = details.map((detail) => {
    const scoped = detail.assertions.filter(
      (item) =>
        sharedResources.includes(item.resource_type) ||
        sharedOperations.includes(item.operation),
    );
    const evidenceRefs = new Set(
      scoped.flatMap((item) => item.evidence_refs),
    );
    const scores = Object.fromEntries(
      capabilityScoreKeys.map((key) => {
        const values = scoped
          .map((item) => item.score_profile[key])
          .filter((value): value is number => typeof value === "number");
        const average = values.length
          ? Math.round(
              (values.reduce((sum, value) => sum + value, 0) / values.length) *
                100,
            ) / 100
          : null;
        return [key, average];
      }),
    ) as Record<CapabilityScoreKey, number | null>;
    return {
      implementationId: detail.implementation.implementationId,
      providerId: detail.implementation.providerId,
      scores,
      constraintCodes: Array.from(
        new Set(
          scoped.flatMap((item) =>
            item.constraints.map((constraint) => constraint.code),
          ),
        ),
      ).sort(),
      evidence: detail.evidence
        .filter((item) => evidenceRefs.has(item.evidence_id))
        .sort((left, right) =>
          left.evidence_id.localeCompare(right.evidence_id),
        ),
    };
  });
  return {
    platform: details[0]!.implementation.platform,
    sharedResources,
    sharedOperations,
    columns,
  };
}
~~~

The result column order matches input detail order. This comparison model is the only source for the comparison UI; React components must not recompute scores.

Define intersection as a generic local helper that returns unique values present in every input array and preserves the first array's order.

~~~typescript
function intersection<T>(groups: T[][]): T[] {
  if (groups.length === 0) return [];
  const [first, ...rest] = groups;
  return Array.from(new Set(first)).filter((item) =>
    rest.every((group) => group.includes(item)),
  );
}
~~~

- [x] **Step 4: Run the unit and type gates**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/capability-market.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
~~~

Expected: 8 tests pass and TypeScript exits 0.

- [ ] **Step 5: Commit only after explicit commit authorization**

~~~bash
git add apps/web/src/lib/capability-market.ts apps/web/tests/unit/capability-market.test.ts
git diff --cached --check
git commit -m "feat: add capability market view model"
~~~

---

### Task 7: Build The Three-View Capability Market And Detail Drawer

**Files:**
- Modify: apps/web/src/components/api-market/api-market-workspace.tsx
- Create: apps/web/src/components/api-market/capability-scenario-view.tsx
- Create: apps/web/src/components/api-market/capability-matrix-view.tsx
- Create: apps/web/src/components/api-market/capability-list-view.tsx
- Create: apps/web/src/components/api-market/capability-detail-drawer.tsx
- Create: apps/web/src/components/api-market/capability-comparison-panel.tsx
- Modify: apps/web/src/app/api-market/page.tsx
- Modify: apps/web/playwright.config.ts
- Modify: apps/web/tests/e2e/main-flows.spec.ts

**Interfaces:**
- CapabilityScenarioView receives assertions, implementations, evidenceLevel, and onSelectImplementation.
- CapabilityMatrixView receives cells, generatedAt, summary, evidenceLevel, mobilePlatform, onMobilePlatformChange, and onSelectCell.
- CapabilityListView receives filtered implementations, assertions, evidenceLevel, onSelectImplementation, and onCompare.
- CapabilityDetailDrawer receives cell, implementationId, generatedAt, evidenceLevel, returnFocusTo, and onClose; it owns detail loading.
- CapabilityComparisonPanel receives CapabilityImplementationComparison and onClose.

- [x] **Step 1: Add the E2E acceptance test first**

Append this complete mock-mode test to apps/web/tests/e2e/main-flows.spec.ts:

~~~typescript
test("capability market switches views and opens evidence detail", async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  await page.setViewportSize(
    mobile ? { width: 375, height: 812 } : { width: 1440, height: 900 },
  );
  const blockedOrigins: string[] = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.hostname !== "127.0.0.1" &&
      url.hostname !== "localhost"
    ) {
      blockedOrigins.push(url.origin);
      await route.abort();
      return;
    }
    await route.continue();
  });

  await page.goto("/api-market?view=scenarios&project_id=p1");
  await expect(page.getByRole("heading", { name: "能力市场" })).toBeVisible();
  await expect(page.getByTestId("capability-scenario")).toHaveCount(8);
  await expect(page.getByText("候选，尚不可执行").first()).toBeVisible();
  await expect(page.getByText("L2-fixture").first()).toBeVisible();

  await page.getByRole("button", { name: "矩阵视图" }).click();
  await expect(page).toHaveURL(/project_id=p1.*view=matrix|view=matrix.*project_id=p1/);
  const visibleCells = page.locator(
    '[data-testid="capability-matrix-cell"]:visible',
  );
  if (mobile) {
    const platformSelect = page.getByTestId("capability-platform-select");
    await expect(platformSelect.locator("option")).toHaveCount(7);
    for (const platform of [
      "youtube", "reddit", "x", "instagram", "threads", "tiktok", "linkedin",
    ]) {
      await platformSelect.selectOption(platform);
      await expect(visibleCells).toHaveCount(6);
    }
    await platformSelect.selectOption("youtube");
  } else {
    await expect(visibleCells).toHaveCount(42);
    const firstBox = await visibleCells.nth(0).boundingBox();
    const secondBox = await visibleCells.nth(1).boundingBox();
    expect(firstBox).not.toBeNull();
    expect(secondBox).not.toBeNull();
    expect(Math.abs(firstBox!.width - secondBox!.width)).toBeLessThan(2);
    expect(Math.abs(firstBox!.height - secondBox!.height)).toBeLessThan(2);
  }

  const youtubeOfficial = page.locator(
    '[data-testid="capability-matrix-cell"][data-platform="youtube"][data-access-channel="official_authorized_api"]',
  );
  await youtubeOfficial.click();
  const dialog = page.getByRole("dialog", { name: "能力详情" });
  await expect(dialog).toContainText("候选，尚不可执行");
  await expect(dialog).toContainText("provider_call=false");
  await expect(dialog).toContainText("youtube.v3");
  await expect(dialog.getByText("Evidence")).toBeVisible();
  await expect(dialog.getByRole("link", { name: /Fixture Review/ }).first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(youtubeOfficial).toBeFocused();

  await page.getByRole("button", { name: "列表视图" }).click();
  await page.getByTestId("capability-filter-platform").selectOption("reddit");
  await expect(page).toHaveURL(/platform=reddit/);
  await page.reload();
  await expect(page.getByTestId("capability-filter-platform")).toHaveValue("reddit");
  await expect(page.locator('[data-implementation-id="reddit.praw"]')).toBeVisible();
  await expect(page.locator("[data-implementation-id]")).toHaveCount(1);
  await expect(page.getByText("候选，尚不可执行").first()).toBeVisible();
  await expect(page.getByText("L2-fixture").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "比较实现" })).toBeDisabled();
  await expect(page.getByText("当前平台只有一个实现，暂无可比较项")).toBeVisible();
  await page.goto("/api-market/youtube-v3-commentthreads-list");
  await expect(page.getByRole("heading", { name: "YouTube Comment Threads" })).toBeVisible();
  await expect(page.getByText("provider_call=false").first()).toBeVisible();
  expect(blockedOrigins).toEqual([]);
});
~~~

- [x] **Step 2: Run the scoped E2E to verify the red state**

~~~bash
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API corepack pnpm --dir apps/web exec playwright test --grep "capability market switches views"
~~~

Expected: both projects report the new heading or controls missing.

- [x] **Step 3: Implement the workspace data boundary**

Replace apps/web/src/components/api-market/api-market-workspace.tsx with this complete orchestration boundary. It preserves unrelated query keys such as project_id, applies every URL filter after refresh, and never falls back to presentation data when Capability API loading fails:

~~~typescript
"use client";

import { useEffect, useMemo, useState } from "react";

import { WorkbenchPanel } from "@/components/common/workbench-ui";
import { CapabilityComparisonPanel } from "@/components/api-market/capability-comparison-panel";
import { CapabilityDetailDrawer } from "@/components/api-market/capability-detail-drawer";
import { CapabilityListView } from "@/components/api-market/capability-list-view";
import { CapabilityMatrixView } from "@/components/api-market/capability-matrix-view";
import { CapabilityScenarioView } from "@/components/api-market/capability-scenario-view";
import {
  getCapabilityImplementationDetail,
  getCapabilityMatrix,
  listCapabilityAssertions,
  listCapabilityImplementations,
} from "@/lib/api/capabilities";
import {
  buildImplementationComparison,
  capabilityAccessChannels,
  capabilityOperations,
  capabilityPlatforms,
  capabilityResourceTypes,
  capabilityStatuses,
  filterCapabilityImplementations,
  filterCapabilityMatrixCells,
  parseCapabilityMarketFilters,
  updateCapabilityMarketQuery,
} from "@/lib/capability-market";
import type {
  CapabilityImplementationComparison,
  CapabilityMarketFilters,
  CapabilityMarketQueryPatch,
  CapabilityMarketView,
} from "@/lib/capability-market";
import type {
  CapabilityAssertion,
  CapabilityImplementation,
  CapabilityMatrix,
  CapabilityMatrixCell,
} from "@/types/capability";

type ApiMarketWorkspaceProps = {
  initialView: CapabilityMarketView;
  initialFilters: CapabilityMarketFilters;
};

type CapabilityMarketData = {
  matrix: CapabilityMatrix;
  implementations: CapabilityImplementation[];
  assertions: CapabilityAssertion[];
};

export function ApiMarketWorkspace({
  initialView,
  initialFilters,
}: ApiMarketWorkspaceProps) {
  const [data, setData] = useState<CapabilityMarketData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [view, setView] = useState(initialView);
  const [filters, setFilters] = useState(initialFilters);
  const [selectedCell, setSelectedCell] =
    useState<CapabilityMatrixCell | null>(null);
  const [selectedImplementationId, setSelectedImplementationId] =
    useState<string | null>(null);
  const [returnFocusTo, setReturnFocusTo] = useState<HTMLElement | null>(null);
  const [comparison, setComparison] =
    useState<CapabilityImplementationComparison | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getCapabilityMatrix(),
      listCapabilityImplementations(),
      listCapabilityAssertions(),
    ])
      .then(([matrix, implementations, assertions]) => {
        if (!cancelled) {
          setData({ matrix, implementations, assertions });
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setLoadError(
            caught instanceof Error
              ? caught.message
              : "capability_market_unavailable",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredImplementations = useMemo(
    () =>
      data
        ? filterCapabilityImplementations(
            data.implementations,
            data.assertions,
            filters,
          )
        : [],
    [data, filters],
  );
  const filteredImplementationIds = useMemo(
    () =>
      new Set(filteredImplementations.map((item) => item.implementationId)),
    [filteredImplementations],
  );
  const filteredAssertions = useMemo(
    () =>
      (data?.assertions ?? []).filter(
        (item) =>
          filteredImplementationIds.has(item.implementation_id) &&
          (!filters.resourceType || item.resource_type === filters.resourceType) &&
          (!filters.operation || item.operation === filters.operation) &&
          (!filters.status || item.support_status === filters.status),
      ),
    [data, filteredImplementationIds, filters],
  );
  const filteredCells = useMemo(
    () =>
      data ? filterCapabilityMatrixCells(data.matrix.cells, filters) : [],
    [data, filters],
  );

  function replaceQuery(patch: CapabilityMarketQueryPatch): string {
    const query = updateCapabilityMarketQuery(
      window.location.search.slice(1),
      patch,
    );
    window.history.replaceState(null, "", query ? `/api-market?${query}` : "/api-market");
    return query;
  }

  function selectView(nextView: CapabilityMarketView) {
    setView(nextView);
    replaceQuery({ view: nextView });
  }

  function patchFilters(patch: CapabilityMarketQueryPatch) {
    const query = replaceQuery(patch);
    setFilters(parseCapabilityMarketFilters(query));
  }

  function selectCell(cell: CapabilityMatrixCell, trigger: HTMLElement) {
    setReturnFocusTo(trigger);
    setSelectedImplementationId(null);
    setSelectedCell(cell);
  }

  function selectImplementation(implementationId: string, trigger: HTMLElement) {
    setReturnFocusTo(trigger);
    setSelectedCell(null);
    setSelectedImplementationId(implementationId);
  }

  async function compareImplementations(implementationIds: string[]) {
    setComparisonError(null);
    try {
      const details = await Promise.all(
        implementationIds.map(getCapabilityImplementationDetail),
      );
      setComparison(buildImplementationComparison(details));
    } catch (caught: unknown) {
      setComparisonError(
        caught instanceof Error ? caught.message : "capability_comparison_failed",
      );
    }
  }

  if (loadError) {
    return (
      <WorkbenchPanel
        label="Capability API"
        subtitle={loadError}
        title="能力目录暂不可用"
      >
        <p>未使用静态能力事实回退。</p>
      </WorkbenchPanel>
    );
  }
  if (!data) {
    return <p role="status">正在加载能力目录…</p>;
  }

  return (
    <div className="grid min-w-0 gap-5">
      <CapabilityViewTabs onChange={selectView} value={view} />
      <CapabilityFilterBar filters={filters} onChange={patchFilters} />
      {comparisonError ? <p role="alert">{comparisonError}</p> : null}
      {view === "scenarios" ? (
        <CapabilityScenarioView
          assertions={filteredAssertions}
          evidenceLevel={data.matrix.evidenceLevel}
          implementations={filteredImplementations}
          onSelectImplementation={selectImplementation}
        />
      ) : null}
      {view === "matrix" ? (
        <CapabilityMatrixView
          cells={filteredCells}
          evidenceLevel={data.matrix.evidenceLevel}
          generatedAt={data.matrix.generatedAt}
          mobilePlatform={filters.platform ?? "youtube"}
          onMobilePlatformChange={(platform) => patchFilters({ platform })}
          onSelectCell={selectCell}
          summary={data.matrix.summary}
        />
      ) : null}
      {view === "list" ? (
        <CapabilityListView
          assertions={data.assertions}
          evidenceLevel={data.matrix.evidenceLevel}
          implementations={filteredImplementations}
          onCompare={compareImplementations}
          onSelectImplementation={selectImplementation}
        />
      ) : null}
      <CapabilityDetailDrawer
        cell={selectedCell}
        evidenceLevel={data.matrix.evidenceLevel}
        generatedAt={data.matrix.generatedAt}
        implementationId={selectedImplementationId}
        returnFocusTo={returnFocusTo}
        onClose={() => {
          setSelectedCell(null);
          setSelectedImplementationId(null);
        }}
      />
      {comparison ? (
        <CapabilityComparisonPanel
          comparison={comparison}
          onClose={() => setComparison(null)}
        />
      ) : null}
    </div>
  );
}

function CapabilityViewTabs({
  onChange,
  value,
}: {
  onChange: (view: CapabilityMarketView) => void;
  value: CapabilityMarketView;
}) {
  return (
    <div aria-label="能力市场视图" className="flex flex-wrap gap-2" role="group">
      {([
        ["scenarios", "场景视图"],
        ["matrix", "矩阵视图"],
        ["list", "列表视图"],
      ] as const).map(([nextView, label]) => (
        <button
          aria-pressed={value === nextView}
          key={nextView}
          onClick={() => onChange(nextView)}
          type="button"
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function CapabilityFilterBar({
  filters,
  onChange,
}: {
  filters: CapabilityMarketFilters;
  onChange: (patch: CapabilityMarketQueryPatch) => void;
}) {
  return (
    <section aria-label="能力筛选" className="grid gap-3 md:grid-cols-3">
      <FilterSelect dataTestId="capability-filter-platform" label="平台" value={filters.platform} values={capabilityPlatforms} onChange={(value) => onChange({ platform: value || null })} />
      <FilterSelect dataTestId="capability-filter-channel" label="访问通道" value={filters.accessChannel} values={capabilityAccessChannels} onChange={(value) => onChange({ accessChannel: value || null })} />
      <FilterSelect dataTestId="capability-filter-resource" label="资源" value={filters.resourceType} values={capabilityResourceTypes} onChange={(value) => onChange({ resourceType: value || null })} />
      <FilterSelect dataTestId="capability-filter-operation" label="操作" value={filters.operation} values={capabilityOperations} onChange={(value) => onChange({ operation: value || null })} />
      <FilterSelect dataTestId="capability-filter-status" label="状态" value={filters.status} values={capabilityStatuses} onChange={(value) => onChange({ status: value || null })} />
      <label className="grid gap-1 text-sm">
        搜索
        <input
          data-testid="capability-filter-query"
          onChange={(event) => onChange({ query: event.target.value || null })}
          value={filters.query ?? ""}
        />
      </label>
    </section>
  );
}

function FilterSelect<T extends string>({
  dataTestId,
  label,
  onChange,
  value,
  values,
}: {
  dataTestId: string;
  label: string;
  onChange: (value: T | "") => void;
  value: T | undefined;
  values: readonly T[];
}) {
  return (
    <label className="grid gap-1 text-sm">
      {label}
      <select
        data-testid={dataTestId}
        onChange={(event) => onChange(event.target.value as T | "")}
        value={value ?? ""}
      >
        <option value="">全部</option>
        {values.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    </label>
  );
}
~~~

- [x] **Step 4: Implement the scenario view**

Create apps/web/src/components/api-market/capability-scenario-view.tsx:

~~~typescript
"use client";

import { capabilityStatusLabel, groupCapabilityScenarios } from "@/lib/capability-market";
import type { CapabilityAssertion, CapabilityImplementation } from "@/types/capability";

export function CapabilityScenarioView({
  assertions,
  evidenceLevel,
  implementations,
  onSelectImplementation,
}: {
  assertions: CapabilityAssertion[];
  evidenceLevel: string;
  implementations: CapabilityImplementation[];
  onSelectImplementation: (implementationId: string, trigger: HTMLElement) => void;
}) {
  const implementationById = new Map(
    implementations.map((item) => [item.implementationId, item]),
  );
  return (
    <section className="grid gap-3 md:grid-cols-2" aria-label="业务场景">
      {groupCapabilityScenarios(assertions).map((scenario) => {
        const implementationIds = Array.from(
          new Set(scenario.assertions.map((item) => item.implementation_id)),
        );
        const platformCount = new Set(
          implementationIds
            .map((id) => implementationById.get(id)?.platform)
            .filter(Boolean),
        ).size;
        const statuses = Array.from(
          new Set(scenario.assertions.map((item) => item.support_status)),
        );
        const evidenceCount = new Set(
          scenario.assertions.flatMap((item) => item.evidence_refs),
        ).size;
        return (
          <article data-testid="capability-scenario" key={scenario.id} className="rounded-2xl border p-4">
            <h2>{scenario.label}</h2>
            <p>{scenario.assertions.length} 项能力 · {platformCount} 个平台</p>
            <p>Evidence: {evidenceLevel} · {evidenceCount} 条引用</p>
            <p>{statuses.length ? statuses.map(capabilityStatusLabel).join(" / ") : "尚无能力事实"}</p>
            {statuses.includes("candidate") ? <p>候选能力未经 live verification，尚不可执行。</p> : null}
            <button
              disabled={implementationIds.length === 0}
              onClick={(event) => onSelectImplementation(implementationIds[0]!, event.currentTarget)}
              type="button"
            >
              {implementationIds.length ? "查看能力详情" : "当前场景暂无实现"}
            </button>
          </article>
        );
      })}
    </section>
  );
}
~~~

- [x] **Step 5: Implement the responsive matrix view**

Create apps/web/src/components/api-market/capability-matrix-view.tsx. The fixed desktop width/height and table-fixed layout are part of UI-005 acceptance, not optional styling:

~~~typescript
"use client";

import { capabilityPlatformLabel, capabilityStatusLabel } from "@/lib/capability-market";
import type { CapabilityMatrix, CapabilityMatrixCell, CapabilityPlatform } from "@/types/capability";

function CellButton({
  cell,
  evidenceLevel,
  onSelectCell,
}: {
  cell: CapabilityMatrixCell;
  evidenceLevel: string;
  onSelectCell: (cell: CapabilityMatrixCell, trigger: HTMLElement) => void;
}) {
  return (
    <button
      className="grid h-28 w-full content-start gap-1 overflow-hidden rounded-xl border p-3 text-left"
      data-access-channel={cell.accessChannel}
      data-platform={cell.platform}
      data-testid="capability-matrix-cell"
      onClick={(event) => onSelectCell(cell, event.currentTarget)}
      type="button"
    >
      <strong>{capabilityStatusLabel(cell.summaryStatus)}</strong>
      <span>{cell.assertionIds.length} Assertions</span>
      <span>{cell.evidenceCount} Evidence · {evidenceLevel}</span>
      {cell.summaryStatus === "candidate" ? <span>未经 live verification，尚不可执行</span> : null}
    </button>
  );
}

export function CapabilityMatrixView({
  cells,
  evidenceLevel,
  generatedAt,
  mobilePlatform,
  onMobilePlatformChange,
  onSelectCell,
  summary,
}: {
  cells: CapabilityMatrixCell[];
  evidenceLevel: string;
  generatedAt: string;
  mobilePlatform: CapabilityPlatform;
  onMobilePlatformChange: (platform: CapabilityPlatform) => void;
  onSelectCell: (cell: CapabilityMatrixCell, trigger: HTMLElement) => void;
  summary: CapabilityMatrix["summary"];
}) {
  const platforms = Array.from(new Set(cells.map((item) => item.platform)));
  const channels = Array.from(new Set(cells.map((item) => item.accessChannel)));
  const mobileCells = cells.filter((item) => item.platform === mobilePlatform);
  return (
    <section aria-label="能力矩阵">
      <p>Generated: {generatedAt} · Evidence: {evidenceLevel} · {summary.cellCount} cells · {summary.populatedCellCount} populated · {summary.unknownCellCount} unknown · provider_call=false · production_write_allowed=false</p>
      {cells.length === 0 ? <p>筛选结果为空；没有把空结果伪造为 unknown Assertion。</p> : null}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full table-fixed border-separate border-spacing-2">
          <colgroup><col className="w-32" />{channels.map((item) => <col className="w-44" key={item} />)}</colgroup>
          <thead><tr><th scope="col">平台</th>{channels.map((item) => <th key={item} scope="col">{item}</th>)}</tr></thead>
          <tbody>
            {platforms.map((platform) => (
              <tr key={platform}>
                <th scope="row">{capabilityPlatformLabel(platform)}</th>
                {channels.map((channel) => {
                  const cell = cells.find((item) => item.platform === platform && item.accessChannel === channel);
                  return <td className="h-28 align-top" key={channel}>{cell ? <CellButton cell={cell} evidenceLevel={evidenceLevel} onSelectCell={onSelectCell} /> : null}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-3 md:hidden">
        <label>平台<select data-testid="capability-platform-select" onChange={(event) => onMobilePlatformChange(event.target.value as CapabilityPlatform)} value={mobilePlatform}>
          {(["youtube", "reddit", "x", "instagram", "threads", "tiktok", "linkedin"] as const).map((platform) => <option key={platform} value={platform}>{capabilityPlatformLabel(platform)}</option>)}
        </select></label>
        <div className="grid gap-2">{mobileCells.map((cell) => <CellButton cell={cell} evidenceLevel={evidenceLevel} key={`${cell.platform}:${cell.accessChannel}`} onSelectCell={onSelectCell} />)}</div>
      </div>
    </section>
  );
}
~~~

- [x] **Step 6: Implement the list and selection view**

Create apps/web/src/components/api-market/capability-list-view.tsx:

~~~typescript
"use client";

import { useMemo, useState } from "react";

import { capabilityStatusLabel } from "@/lib/capability-market";
import type { CapabilityAssertion, CapabilityImplementation, CapabilityStatus } from "@/types/capability";

const statusPriority: readonly CapabilityStatus[] = ["verified", "partial", "candidate", "blocked", "unsupported", "deprecated", "unknown"];

export function CapabilityListView({
  assertions,
  evidenceLevel,
  implementations,
  onCompare,
  onSelectImplementation,
}: {
  assertions: CapabilityAssertion[];
  evidenceLevel: string;
  implementations: CapabilityImplementation[];
  onCompare: (implementationIds: string[]) => void;
  onSelectImplementation: (implementationId: string, trigger: HTMLElement) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const platformCounts = useMemo(() => {
    const counts = new Map<string, number>();
    implementations.forEach((item) => counts.set(item.platform, (counts.get(item.platform) ?? 0) + 1));
    return counts;
  }, [implementations]);
  const comparisonAvailable = Array.from(platformCounts.values()).some((count) => count >= 2);

  function toggle(implementation: CapabilityImplementation) {
    setSelected((current) => {
      if (current.includes(implementation.implementationId)) return current.filter((id) => id !== implementation.implementationId);
      const selectedPlatform = implementations.find((item) => item.implementationId === current[0])?.platform;
      if (current.length >= 3 || (selectedPlatform && selectedPlatform !== implementation.platform)) return current;
      return [...current, implementation.implementationId];
    });
  }

  return (
    <section className="grid gap-3" aria-label="Implementation 列表">
      {implementations.length === 0 ? <p>筛选结果为空。</p> : null}
      {implementations.length > 0 && !comparisonAvailable ? <p>当前平台只有一个实现，暂无可比较项</p> : null}
      <button disabled={selected.length < 2 || selected.length > 3} onClick={() => onCompare(selected)} type="button">比较实现</button>
      {implementations.map((implementation) => {
        const owned = assertions.filter((item) => item.implementation_id === implementation.implementationId);
        const status = statusPriority.find((candidate) => owned.some((item) => item.support_status === candidate)) ?? "unknown";
        const resources = Array.from(new Set(owned.map((item) => item.resource_type)));
        const operations = Array.from(new Set(owned.map((item) => item.operation)));
        const lastVerified = owned.map((item) => item.last_verified_at).sort().at(-1) ?? "—";
        return (
          <article className="rounded-2xl border p-4" data-implementation-id={implementation.implementationId} key={implementation.implementationId}>
            <h2>{implementation.providerId}</h2>
            <p>{implementation.platform} · {implementation.accessChannel} · {implementation.deliveryForm}</p>
            <p>{capabilityStatusLabel(status)} · Evidence: {evidenceLevel}</p>
            {status === "candidate" ? <p>未经 live verification，尚不可执行。</p> : null}
            <p>Resources: {resources.join(", ") || "—"}</p>
            <p>Operations: {operations.join(", ") || "—"}</p>
            <p>Stability: {implementation.stability} · Last verified: {lastVerified}</p>
            <button onClick={(event) => onSelectImplementation(implementation.implementationId, event.currentTarget)} type="button">查看详情</button>
            <label><input checked={selected.includes(implementation.implementationId)} disabled={!comparisonAvailable} onChange={() => toggle(implementation)} type="checkbox" />加入比较</label>
          </article>
        );
      })}
    </section>
  );
}
~~~

- [x] **Step 7: Implement the shared detail drawer**

Create apps/web/src/components/api-market/capability-detail-drawer.tsx with this data-loading and focus contract. It does not fetch detail for an explicit unknown cell, and it never renders Credential values or a Live action:

~~~typescript
"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useMemo, useState } from "react";

import { getCapabilityImplementationDetail } from "@/lib/api/capabilities";
import { listApiMarketPresentationsByProviderId } from "@/lib/api-market-catalog";
import { capabilityStatusLabel } from "@/lib/capability-market";
import type { CapabilityImplementationDetail, CapabilityMatrixCell } from "@/types/capability";

export function CapabilityDetailDrawer({
  cell,
  evidenceLevel,
  generatedAt,
  implementationId,
  onClose,
  returnFocusTo,
}: {
  cell: CapabilityMatrixCell | null;
  evidenceLevel: string;
  generatedAt: string;
  implementationId: string | null;
  onClose: () => void;
  returnFocusTo: HTMLElement | null;
}) {
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CapabilityImplementationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestedId = implementationId ?? chosenId ?? (cell?.implementationIds.length === 1 ? cell.implementationIds[0]! : null);
  const open = Boolean(cell || implementationId);

  useEffect(() => {
    setChosenId(null);
    setDetail(null);
    setError(null);
  }, [cell, implementationId]);

  useEffect(() => {
    if (!open || !requestedId) return;
    let cancelled = false;
    setDetail(null);
    setError(null);
    getCapabilityImplementationDetail(requestedId)
      .then((value) => { if (!cancelled) setDetail(value); })
      .catch((caught: unknown) => { if (!cancelled) setError(caught instanceof Error ? caught.message : "capability_detail_unavailable"); });
    return () => { cancelled = true; };
  }, [open, requestedId]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const assertions = detail?.assertions ?? [];
  const constraints = useMemo(() => assertions.flatMap((item) => item.constraints), [assertions]);
  const presentations = detail ? listApiMarketPresentationsByProviderId(detail.implementation.providerId) : [];

  function close() {
    onClose();
    window.requestAnimationFrame(() => returnFocusTo?.focus());
  }
  if (!open) return null;

  return (
    <aside aria-label="能力详情" aria-modal="true" className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl overflow-y-auto bg-white p-6" role="dialog">
      <button onClick={close} type="button">关闭</button>
      <section><h2>聚合状态与边界</h2><p>{cell ? capabilityStatusLabel(cell.summaryStatus) : "Implementation 详情"}</p><p>Generated: {generatedAt} · Evidence: {evidenceLevel}</p><p>provider_call=false · credential_read_attempted=false · live_client_created=false · production_write_allowed=false</p></section>
      <section><h2>Resource 与 Operation</h2><p>{(cell?.resourceTypes ?? assertions.map((item) => item.resource_type)).join(", ") || "—"}</p><p>{(cell?.operations ?? assertions.map((item) => item.operation)).join(", ") || "—"}</p></section>
      {cell && cell.implementationIds.length > 1 && !requestedId ? <section><h2>选择 Implementation</h2>{cell.implementationIds.map((id) => <button key={id} onClick={() => setChosenId(id)} type="button">{id}</button>)}</section> : null}
      {!requestedId ? <p>{cell?.summaryStatus === "unknown" ? "该矩阵格尚无能力事实。" : "请选择 Implementation。"}</p> : null}
      {requestedId && !detail && !error ? <p role="status">正在加载 Implementation…</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {detail ? <>
        <section><h2>Implementation</h2><p>{detail.implementation.implementationId} · {detail.implementation.providerId}</p><p>{detail.implementation.platform} · {detail.implementation.accessChannel}</p><p>Blocked actions: {detail.implementation.blockedActions.join(", ") || "—"}</p></section>
        <section><h2>Constraint 与禁止动作</h2><ul>{constraints.map((item) => <li key={`${item.code}:${item.severity}`}>{item.code} · {item.severity}</li>)}</ul></section>
        <section><h2>八维评分</h2>{assertions.map((item) => <dl key={item.assertion_id}>{Object.entries(item.score_profile).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>)}</section>
        <section><h2>Evidence</h2><ul>{detail.evidence.map((item) => <li key={item.evidence_id}><a href={item.source_url} rel="noreferrer" target="_blank">{item.evidence_id}</a> · {item.evidence_grade} · {item.observed_at}</li>)}</ul></section>
        <section><h2>Fixture Review</h2>{presentations.length ? presentations.map((item) => <Link href={`/api-market/${item.id}` as Route} key={item.id}>Fixture Review: {item.title}</Link>) : <p>无展示增强；仅保留通用能力详情。</p>}</section>
      </> : null}
    </aside>
  );
}
~~~

- [x] **Step 8: Implement the fixed-field comparison panel**

Create apps/web/src/components/api-market/capability-comparison-panel.tsx. It renders only the model from buildImplementationComparison; it does not average or join data in React:

~~~typescript
"use client";

import { capabilityScoreKeys } from "@/lib/capability-market";
import type { CapabilityImplementationComparison } from "@/lib/capability-market";

export function CapabilityComparisonPanel({
  comparison,
  onClose,
}: {
  comparison: CapabilityImplementationComparison;
  onClose: () => void;
}) {
  return (
    <section aria-label="Implementation 比较" aria-modal="true" className="fixed inset-6 z-50 overflow-auto bg-white p-6" role="dialog">
      <button onClick={onClose} type="button">关闭比较</button>
      <h2>Implementation 比较</h2>
      <p>Coverage scope: {comparison.sharedResources.join(", ") || comparison.sharedOperations.join(", ")}</p>
      <table><thead><tr><th>字段</th>{comparison.columns.map((column) => <th key={column.implementationId}>{column.providerId}</th>)}</tr></thead><tbody>
        {capabilityScoreKeys.map((key) => <tr key={key}><th>{key}</th>{comparison.columns.map((column) => <td key={column.implementationId}>{column.scores[key] ?? "—"}</td>)}</tr>)}
        <tr><th>限制</th>{comparison.columns.map((column) => <td key={column.implementationId}>{column.constraintCodes.join(", ") || "—"}</td>)}</tr>
        <tr><th>Evidence</th>{comparison.columns.map((column) => <td key={column.implementationId}>{column.evidence.map((item) => <a href={item.source_url} key={item.evidence_id} rel="noreferrer" target="_blank">{item.evidence_id}</a>)}</td>)}</tr>
      </tbody></table>
    </section>
  );
}
~~~

- [x] **Step 9: Update the page title and view parsing**

Replace apps/web/src/app/api-market/page.tsx with:

~~~typescript
import { ApiMarketWorkspace } from "@/components/api-market/api-market-workspace";
import { AppShell } from "@/components/layout/app-shell";
import {
  parseCapabilityMarketFilters,
  parseCapabilityMarketView,
} from "@/lib/capability-market";

type ApiMarketPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function ApiMarketPage({ searchParams }: ApiMarketPageProps) {
  const resolved = await searchParams;
  const query = new URLSearchParams();
  for (const [key, rawValue] of Object.entries(resolved)) {
    const value = Array.isArray(rawValue) ? rawValue[0] : rawValue;
    if (value !== undefined) query.set(key, value);
  }
  return (
    <AppShell
      brief="按场景、平台和访问通道审查规范能力事实；Candidate 不代表可执行。"
      description="7×6 能力矩阵、Implementation、Constraint 与 Evidence"
      signals={["42 个显式矩阵格", "Candidate 不可执行", "provider_call=false"]}
      title="能力市场"
    >
      <ApiMarketWorkspace
        initialFilters={parseCapabilityMarketFilters(query.toString())}
        initialView={parseCapabilityMarketView(query.get("view"))}
      />
    </AppShell>
  );
}
~~~

- [x] **Step 10: Force a fresh mock-only Playwright server**

In apps/web/playwright.config.ts, replace the fixed port and reuse flag with:

~~~typescript
const port = Number(process.env.PLAYWRIGHT_PORT ?? "3100");
const forceFreshServer = process.env.PLAYWRIGHT_FORCE_FRESH_SERVER === "true";
const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;
const localBaseUrl = `http://127.0.0.1:${port}`;
~~~

Keep the existing webServer command with NEXT_PUBLIC_MOCK_API=true, and change only its reuse setting:

~~~typescript
reuseExistingServer: !forceFreshServer,
~~~

- [x] **Step 11: Run focused Web acceptance**

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API PLAYWRIGHT_PORT=3111 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web exec playwright test --grep "capability market switches views"
~~~

Expected:

- TypeScript, ESLint, Vitest, and build exit 0.
- The scoped Playwright test passes once in desktop and once in mobile.
- The E2E request guard reports no non-local HTTP(S) origin and the fresh server visibly returns L2-fixture data.

- [ ] **Step 12: Commit only after explicit commit authorization**

~~~bash
git add apps/web/src/components/api-market/api-market-workspace.tsx apps/web/src/components/api-market/capability-scenario-view.tsx apps/web/src/components/api-market/capability-matrix-view.tsx apps/web/src/components/api-market/capability-list-view.tsx apps/web/src/components/api-market/capability-detail-drawer.tsx apps/web/src/components/api-market/capability-comparison-panel.tsx apps/web/src/app/api-market/page.tsx apps/web/playwright.config.ts apps/web/tests/e2e/main-flows.spec.ts
git diff --cached --check
git commit -m "feat: deliver capability market views"
~~~

---

### Task 8: Replace The Navigation With Six Shared Entries And Add Project Context

**Files:**
- Create: apps/web/src/components/layout/navigation.ts
- Modify: apps/web/src/components/layout/sidebar.tsx
- Create: apps/web/src/components/layout/mobile-navigation.tsx
- Create: apps/web/src/components/layout/project-selector.tsx
- Create: apps/web/src/lib/project-selection.ts
- Modify: apps/web/src/components/layout/top-bar.tsx
- Modify: apps/web/src/components/layout/app-shell.tsx
- Create: apps/web/tests/unit/navigation.test.ts
- Modify: apps/web/tests/e2e/main-flows.spec.ts

**Interfaces:**
- primaryNavigation contains exactly six top-level items.
- isNavigationItemActive(pathname, item) is shared by desktop and mobile.
- readSelectedProjectId and writeSelectedProjectId manage only a local project ID.
- ProjectSelector emits data-project-filter-applied=false until a page proves filtering.

- [x] **Step 1: Write navigation unit tests**

Create apps/web/tests/unit/navigation.test.ts:

~~~typescript
import { describe, expect, it } from "vitest";

import {
  isNavigationChildActive,
  isNavigationItemActive,
  primaryNavigation,
} from "@/components/layout/navigation";
import { resolveSelectedProjectId } from "@/lib/project-selection";
import type { Project } from "@/types/project";

describe("primary navigation", () => {
  it("contains exactly the six approved entries", () => {
    expect(primaryNavigation.map((item) => item.label)).toEqual([
      "工作台",
      "监测项目",
      "采集工作流",
      "数据资产",
      "洞察与交付",
      "能力市场",
    ]);
  });

  it("keeps legacy pages as secondary links", () => {
    const secondaryHrefs = primaryNavigation.flatMap((item) =>
      item.children.map((child) => child.href),
    );
    expect(secondaryHrefs).toEqual(
      expect.arrayContaining([
        "/tasks",
        "/sources",
        "/raw-records",
        "/entities",
        "/signals",
        "/reports",
        "/alerts",
        "/notifications",
        "/toolkit",
        "/domain/osint",
        "/domain/ecommerce",
        "/domain/social",
        "/domain/competitor",
        "/domain/agent",
        "/domain/platform",
        "/domain/governance",
      ]),
    );
  });

  it("marks a child route through its parent", () => {
    const workflow = primaryNavigation.find(
      (item) => item.href === "/automation",
    );
    expect(workflow).toBeDefined();
    expect(isNavigationItemActive("/tasks", "", workflow!)).toBe(true);
  });

  it("does not mark unrelated routes active", () => {
    expect(
      isNavigationItemActive("/api-market", "", primaryNavigation[0]!),
    ).toBe(false);
  });

  it("uses query values to highlight exactly one capability child", () => {
    const market = primaryNavigation.find((item) => item.href === "/api-market")!;
    const [scenarios, matrix, list] = market.children;
    expect(isNavigationChildActive("/api-market", "view=matrix", matrix!)).toBe(true);
    expect(isNavigationChildActive("/api-market", "view=matrix", scenarios!)).toBe(false);
    expect(isNavigationChildActive("/api-market", "view=matrix", list!)).toBe(false);
    expect(isNavigationChildActive("/api-market", "", scenarios!)).toBe(true);
  });
});

describe("project selection", () => {
  const projects = [
    { id: "active", name: "Active", status: "active" },
    { id: "archived", name: "Archived", status: "archived" },
  ] as Project[];

  it("keeps only an existing active selection", () => {
    expect(resolveSelectedProjectId(projects, "active")).toBe("active");
  });

  it("falls back to all projects for archived or missing ids", () => {
    expect(resolveSelectedProjectId(projects, "archived")).toBeNull();
    expect(resolveSelectedProjectId(projects, "missing")).toBeNull();
    expect(resolveSelectedProjectId(projects, null)).toBeNull();
  });
});
~~~

- [x] **Step 2: Run the tests to verify the red state**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/navigation.test.ts
~~~

Expected: module resolution error for @/components/layout/navigation.

- [x] **Step 3: Create the shared navigation config**

Create apps/web/src/components/layout/navigation.ts with this complete config and query-aware active logic:

~~~typescript
import {
  Bot,
  ChartNoAxesCombined,
  FolderKanban,
  Gauge,
  Store,
  TableProperties,
  type LucideIcon,
} from "lucide-react";
import type { Route } from "next";

export type NavigationChild = {
  href: Route;
  label: string;
};

export type NavigationItem = {
  href: Route;
  label: string;
  icon: LucideIcon;
  children: NavigationChild[];
};

function child(href: string, label: string): NavigationChild {
  return { href: href as Route, label };
}

function nav(
  href: string,
  label: string,
  icon: LucideIcon,
  children: NavigationChild[],
): NavigationItem {
  return { href: href as Route, label, icon, children };
}

function targetUrl(href: Route): URL {
  return new URL(String(href), "http://navigation.local");
}

export function isNavigationChildActive(
  pathname: string,
  search: string,
  item: NavigationChild,
): boolean {
  const target = targetUrl(item.href);
  if (target.pathname !== pathname) return false;
  const current = new URLSearchParams(search);
  for (const [key, expected] of target.searchParams) {
    if (key === "view" && expected === "scenarios" && !current.has(key)) continue;
    if (current.get(key) !== expected) return false;
  }
  return true;
}

export function isNavigationItemActive(
  pathname: string,
  search: string,
  item: NavigationItem,
): boolean {
  const primaryPath = targetUrl(item.href).pathname;
  if (
    pathname === primaryPath ||
    (primaryPath === "/api-market" &&
      pathname.startsWith("/api-market/"))
  ) {
    return true;
  }
  return item.children.some((childItem) =>
    isNavigationChildActive(pathname, search, childItem),
  );
}

export const primaryNavigation = [
  nav("/dashboard", "工作台", Gauge, [
    child("/toolkit", "采集工具库"),
    child("/playbooks/site-user-playbook.html", "使用手册"),
  ]),
  nav("/projects", "监测项目", FolderKanban, [
    child("/domain/osint", "开源雷达"),
    child("/domain/ecommerce", "电商风向"),
    child("/domain/social", "社媒范围"),
    child("/domain/competitor", "竞品范围"),
    child("/domain/agent", "Agent 生态"),
    child("/domain/platform", "平台采集"),
    child("/domain/governance", "合规边界"),
  ]),
  nav("/automation", "采集工作流", Bot, [
    child("/tasks", "采集任务"),
    child("/sources", "数据源"),
  ]),
  nav("/datasets", "数据资产", TableProperties, [
    child("/raw-records", "原始数据"),
    child("/entities", "实体库"),
  ]),
  nav("/intelligence", "洞察与交付", ChartNoAxesCombined, [
    child("/signals", "信号中心"),
    child("/reports", "报告中心"),
    child("/alerts", "预警中心"),
    child("/notifications", "站内通知"),
  ]),
  nav("/api-market", "能力市场", Store, [
    child("/api-market?view=scenarios", "场景视图"),
    child("/api-market?view=matrix", "矩阵视图"),
    child("/api-market?view=list", "能力列表"),
  ]),
] satisfies NavigationItem[];
~~~

- [x] **Step 4: Refactor the desktop Sidebar**

Replace apps/web/src/components/layout/sidebar.tsx with:

~~~typescript
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import {
  isNavigationChildActive,
  isNavigationItemActive,
  primaryNavigation,
} from "@/components/layout/navigation";

export function Sidebar() {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  return (
    <aside className="hidden min-h-screen w-72 border-r bg-white px-4 py-5 lg:fixed lg:inset-y-0 lg:flex lg:flex-col">
      <Link className="mb-6 font-semibold" href="/dashboard">Data Intelligence Hub</Link>
      <nav aria-label="主导航" className="grid gap-2">
        {primaryNavigation.map((item) => {
          const active = isNavigationItemActive(pathname, search, item);
          const Icon = item.icon;
          return (
            <div key={String(item.href)}>
              <Link aria-current={active ? "page" : undefined} className="flex items-center gap-2 rounded-xl px-3 py-2" data-testid="primary-nav-link" href={item.href}>
                <Icon aria-hidden="true" size={17} />{item.label}
              </Link>
              {active ? <div className="ml-7 grid gap-1">{item.children.map((child) => <Link aria-current={isNavigationChildActive(pathname, search, child) ? "page" : undefined} href={child.href} key={String(child.href)}>{child.label}</Link>)}</div> : null}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
~~~

- [x] **Step 5: Add the accessible Mobile Navigation**

Create apps/web/src/components/layout/mobile-navigation.tsx:

~~~typescript
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  isNavigationChildActive,
  isNavigationItemActive,
  primaryNavigation,
} from "@/components/layout/navigation";

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();
  const search = useSearchParams().toString();

  const close = useCallback(() => {
    setOpen(false);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [close, open]);

  return (
    <>
      <button className="lg:hidden" onClick={() => setOpen(true)} ref={openerRef} type="button">打开导航</button>
      {open ? <>
        <button aria-label="关闭导航遮罩" className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={close} type="button" />
        <aside aria-label="移动主导航" aria-modal="true" className="fixed inset-y-0 left-0 z-50 w-[min(20rem,88vw)] overflow-y-auto bg-white p-5 lg:hidden" role="dialog">
          <button onClick={close} type="button">关闭导航</button>
          <nav aria-label="主导航" className="mt-4 grid gap-3">
            {primaryNavigation.map((item) => {
              const active = isNavigationItemActive(pathname, search, item);
              return <div key={String(item.href)}>
                <Link aria-current={active ? "page" : undefined} data-testid="mobile-primary-nav-link" href={item.href} onClick={close}>{item.label}</Link>
                {active ? <div className="ml-4 grid gap-1">{item.children.map((child) => <Link aria-current={isNavigationChildActive(pathname, search, child) ? "page" : undefined} href={child.href} key={String(child.href)} onClick={close}>{child.label}</Link>)}</div> : null}
              </div>;
            })}
          </nav>
        </aside>
      </> : null}
    </>
  );
}
~~~

- [x] **Step 6: Add safe local project selection**

Create project-selection.ts:

~~~typescript
import type { Project } from "@/types/project";

export const selectedProjectStorageKey =
  "data-intelligence-hub:selected-project-id";

export function resolveSelectedProjectId(
  projects: Project[],
  storedProjectId: string | null,
): string | null {
  if (!storedProjectId) return null;
  return projects.some(
    (project) =>
      project.id === storedProjectId && project.status === "active",
  )
    ? storedProjectId
    : null;
}

export function readSelectedProjectId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(selectedProjectStorageKey);
}

export function writeSelectedProjectId(value: string | null): void {
  if (typeof window === "undefined") return;
  if (value) {
    window.localStorage.setItem(selectedProjectStorageKey, value);
  } else {
    window.localStorage.removeItem(selectedProjectStorageKey);
  }
  window.dispatchEvent(
    new CustomEvent("data-intelligence-hub:project-selection", {
      detail: { projectId: value },
    }),
  );
}
~~~

Create apps/web/src/components/layout/project-selector.tsx:

~~~typescript
"use client";

import { useEffect, useState } from "react";

import { listProjects } from "@/lib/api/projects";
import {
  readSelectedProjectId,
  resolveSelectedProjectId,
  writeSelectedProjectId,
} from "@/lib/project-selection";
import type { Project } from "@/types/project";

export function ProjectSelector() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then((items) => {
        if (cancelled) return;
        const active = items.filter((item) => item.status === "active");
        const stored = readSelectedProjectId();
        const resolved = resolveSelectedProjectId(items, stored);
        if (resolved !== stored) writeSelectedProjectId(resolved);
        setProjects(active);
        setSelectedId(resolved);
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "project_list_unavailable");
      });
    return () => { cancelled = true; };
  }, []);

  function select(value: string) {
    const next = value || null;
    setSelectedId(next);
    writeSelectedProjectId(next);
  }

  return (
    <div data-project-filter-applied="false">
      <label>项目<select data-testid="global-project-selector" disabled={Boolean(error)} onChange={(event) => select(event.target.value)} value={selectedId ?? ""}>
        <option value="">全部项目</option>
        {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select></label>
      <p>当前页面未应用项目过滤（全局数据）</p>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
~~~

This Goal deliberately has no global project-filter consumer: existing page-local project selectors keep their current behavior, and the global selector remains an honest context preference until a later Goal wires page contracts. The visible false-state text is required on every AppShell page.

- [x] **Step 7: Wire TopBar and AppShell**

Replace apps/web/src/components/layout/top-bar.tsx with:

~~~typescript
import { Suspense } from "react";

import { GlobalSearch } from "@/components/layout/global-search";
import { MobileNavigation } from "@/components/layout/mobile-navigation";
import { ProjectSelector } from "@/components/layout/project-selector";

export function TopBar({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <header className="border-b bg-white/95">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-start gap-3"><Suspense fallback={null}><MobileNavigation /></Suspense><div><h1 className="text-xl font-semibold">{title}</h1><p className="mt-1 text-sm">{description}</p></div></div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center"><ProjectSelector /><GlobalSearch /></div>
      </div>
    </header>
  );
}
~~~

In apps/web/src/components/layout/app-shell.tsx, import Suspense from React, wrap Sidebar because it reads search params, and change the root class so the shared shell cannot create document-level horizontal overflow:

~~~diff
+import { Suspense } from "react";
 import { Sidebar } from "@/components/layout/sidebar";

-    <div className="min-h-screen bg-[#F7F0EB] text-[#231A1A]">
-      <Sidebar />
+    <div className="min-h-screen overflow-x-clip bg-[#F7F0EB] text-[#231A1A]">
+      <Suspense fallback={null}>
+        <Sidebar />
+      </Suspense>
~~~

Do not call listProjects from AppShell; ProjectSelector is the single global caller.

- [x] **Step 8: Add navigation E2E**

Append this test to apps/web/tests/e2e/main-flows.spec.ts:

~~~typescript
test("six-entry navigation is complete on desktop and mobile", async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === "mobile";
  await page.setViewportSize(
    mobile ? { width: 375, height: 812 } : { width: 1440, height: 900 },
  );
  await page.goto("/dashboard");

  if (mobile) {
    const opener = page.getByRole("button", { name: "打开导航" });
    await opener.click();
    const drawer = page.getByRole("dialog", { name: "移动主导航" });
    await expect(drawer).toHaveAttribute("aria-modal", "true");
    await expect(drawer.getByTestId("mobile-primary-nav-link")).toHaveCount(6);
    await expect(drawer.getByRole("link", { name: "采集工具库" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(opener).toBeFocused();
    await opener.click();
    await drawer.getByRole("link", { name: "数据资产" }).click();
    await expect(page).toHaveURL(/\/datasets$/);
  } else {
    await expect(page.getByTestId("primary-nav-link")).toHaveCount(6);
    await page.getByRole("link", { name: "能力市场", exact: true }).click();
    await expect(page).toHaveURL(/\/api-market/);
  }

  const selector = page.getByTestId("global-project-selector");
  await expect(selector.locator("option").nth(1)).toBeAttached();
  const projectId = await selector.locator("option").nth(1).getAttribute("value");
  expect(projectId).toBeTruthy();
  await selector.selectOption(projectId!);
  await page.reload();
  await expect(page.getByTestId("global-project-selector")).toHaveValue(projectId!);
  await expect(page.getByText("当前页面未应用项目过滤（全局数据）")).toBeVisible();
  await expect(page.locator('[data-project-filter-applied="false"]')).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
~~~

- [x] **Step 9: Run the navigation and full Web gates**

~~~bash
corepack pnpm --dir apps/web test -- tests/unit/navigation.test.ts
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API PLAYWRIGHT_PORT=3112 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web exec playwright test --grep "six-entry navigation"
~~~

Expected: 7 navigation/project-selection unit tests pass; all Web static gates exit 0; the E2E passes once in desktop and once in mobile, including Escape/focus restoration and persisted active Project ID with data-project-filter-applied=false.

- [ ] **Step 10: Commit only after explicit commit authorization**

~~~bash
git add apps/web/src/components/layout/navigation.ts apps/web/src/components/layout/sidebar.tsx apps/web/src/components/layout/mobile-navigation.tsx apps/web/src/components/layout/project-selector.tsx apps/web/src/lib/project-selection.ts apps/web/src/components/layout/top-bar.tsx apps/web/src/components/layout/app-shell.tsx apps/web/tests/unit/navigation.test.ts apps/web/tests/e2e/main-flows.spec.ts
git diff --cached --check
git commit -m "feat: add six-entry responsive navigation"
~~~

---

### Task 9: Synchronize Architecture, API Contracts, And Local Progress

**Files:**
- Modify: docs/architecture/architecture-data-intelligence-hub-stable.md
- Modify: docs/api/api-contract-data-intelligence-hub-stable.md
- Modify: docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md
- Modify: TODO.md
- Modify: .kiro/plan/progress.md

- [x] **Step 1: Add the implemented architecture boundary**

Append this section to docs/architecture/architecture-data-intelligence-hub-stable.md:

~~~markdown
## Capability Catalog And Matrix

`capability_catalog_overseas_v2.json` is the only runtime Capability fact source for GOAL-V2-02. The Matrix is an in-memory read projection and is never persisted:

```text
capability_catalog.v1
-> strict cached loader with deep-copy isolation
-> Capability Matrix Read Model (PlatformId x AccessChannel = 42 cells)
-> authenticated read-only /api/capabilities/*
-> Capability Market scenario / matrix / list / detail views
```

The Web keeps only keyed Endpoint presentation enhancements. Capability facts, status, constraints, scores, Evidence, Provider metadata, policy, cost, quota, and boundaries come from the Capability API. No SQLAlchemy model, Alembic revision, Provider client, Credential read, or production write is introduced.
~~~

- [x] **Step 2: Add the exact read-only API contract**

Append this section to docs/api/api-contract-data-intelligence-hub-stable.md:

~~~markdown
## Capability Read API

All routes require the existing authenticated session and are read-only.

| Method | Route | Filters / result |
|---|---|---|
| GET | `/api/capabilities/matrix` | `capability_matrix.v1`; 7 platforms, 6 channels, 42 explicit cells |
| GET | `/api/capabilities/assertions` | `platform`, `access_channel`, `resource_type`, `operation`, `support_status`; valid zero result is `[]` |
| GET | `/api/capabilities/implementations` | `platform`, `access_channel`; valid zero result is `[]` |
| GET | `/api/capabilities/implementations/{implementation_id}` | Implementation + owned Assertions + referenced Evidence |

Invalid enum query values return `422`. A missing Implementation returns `404` with `capability_implementation_not_found`. Catalog load/parse/validation failure returns `500` with `capability_catalog_load_failed`; there is no static-data fallback.

Every Matrix response carries `provider_call=false` and `production_write_allowed=false`. Evidence retains `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production_write_attempted=false`.
~~~

- [x] **Step 3: Record only evidence that actually ran**

Append this block to .kiro/plan/progress.md after Tasks 1-8 gates have passed:

~~~markdown
## 2026-07-11 GOAL-V2-02 implementation progress

- Task 0 control-plane activation: passed local consistency checks
- Task 1 Web TypeScript baseline: passed targeted test, typecheck, lint, and build
- Tasks 2-3 Capability Matrix/API: passed unit, integration, ruff, and mypy gates
- Tasks 4-7 Capability Web/Market: passed unit, typecheck, lint, build, desktop/mobile mock E2E
- Task 8 Navigation/Project context: passed unit, typecheck, lint, build, desktop/mobile mock E2E
- provider_call=false
- credential_read_attempted=false
- live_client_created=false
- production_write_allowed=false
- database_migration=false
- production unchanged
- CI/deploy/production/provider evidence: not run
~~~

If any named gate did not pass, do not append this block; keep the corresponding TODO.md item unchecked and record the actual failure instead.

- [x] **Step 4: Update the local indices**

Mark Task 1-9 complete in TODO.md and this plan only after their named evidence exists. Keep Task 10 unchecked. TODO.md remains a short index and contains no test code or commit commands.

- [x] **Step 5: Verify contract and state consistency**

~~~bash
rg -n 'Capability Catalog And Matrix|PlatformId x AccessChannel = 42 cells|no SQLAlchemy model' docs/architecture/architecture-data-intelligence-hub-stable.md
rg -n '/api/capabilities/matrix|capability_implementation_not_found|capability_catalog_load_failed|provider_call=false' docs/api/api-contract-data-intelligence-hub-stable.md
rg -n 'all Goals.*ready_for_goal_activation|^active: true$|Product source of truth: `docs/product/product-prd-data-intelligence-hub-stable.md`' TODO.md .codex .kiro docs/product docs/architecture docs/api
git diff --check
~~~

Expected: architecture/API markers are present; stale current-state patterns have no output outside explicitly historical sections; diff check exits 0.

- [ ] **Step 6: Commit only after explicit commit authorization**

~~~bash
git add docs/architecture/architecture-data-intelligence-hub-stable.md docs/api/api-contract-data-intelligence-hub-stable.md docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md .kiro/plan/progress.md
git diff --cached --check
git commit -m "docs: document capability matrix contracts"
~~~

TODO.md is ignored and remains local. No deploy, production check, or later Goal activation follows.

---

### Task 10: Run The Full Local Exit Gate And Record Evidence

**Files:**
- Modify: docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md
- Modify: docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md
- Modify: docs/product/product-prd-social-media-automation-platform-v2.md
- Modify: .codex/context-pack.md
- Modify: TODO.md
- Modify: .kiro/plan/progress.md

**Interfaces:**
- Produces a local-only Execution Evidence block.
- Does not authorize CI, push, PR, merge, deploy, DB changes, or Provider calls.

- [x] **Step 1: Freeze the intended file manifest**

Run:

~~~bash
BASE_SHA="$(cat tmp/goal-v2-02-base-sha)"
git diff --name-only "$BASE_SHA"..HEAD
git diff --name-only
git ls-files --others --exclude-standard
git status --short
~~~

Expected: the committed-since-base, current tracked, and current untracked layers together contain only files named by Tasks 0-9 plus entries already present in tmp/goal-v2-02-initial-status.txt. Any additional file stops the exit gate until classified; do not infer scope from git diff --name-only alone.

- [x] **Step 2: Run the complete API gate**

~~~bash
cd apps/api
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run alembic heads
~~~

Expected:

- ruff exits 0.
- mypy exits 0.
- all collected API tests pass with no new skip.
- Alembic prints exactly one head: 202606110026 (head).
- No external or persistent database connection and no migration upgrade is attempted. Isolated in-memory SQLite used by integration fixtures is allowed and must not be described as production/database migration evidence.

- [x] **Step 3: Run the complete Web gate**

~~~bash
corepack pnpm --dir apps/web exec tsc --noEmit --pretty false --incremental false
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
~~~

Expected: all commands exit 0; the build includes /api-market and /api-market/[endpointId].

- [x] **Step 4: Run local mock Playwright**

~~~bash
env -u PLAYWRIGHT_BASE_URL -u PLAYWRIGHT_REAL_API PLAYWRIGHT_PORT=3113 PLAYWRIGHT_FORCE_FRESH_SERVER=true corepack pnpm --dir apps/web test:e2e
~~~

Expected:

- The run uses the local Web server with NEXT_PUBLIC_MOCK_API=true.
- Desktop and mobile capability-market/navigation cases pass.
- Only explicitly real-API tests remain skipped.
- Artifacts, if any, remain under tmp/playwright-results.
- The two new request-guarded Capability tests contact only localhost; the fresh-server config prevents reuse of a non-mock server. No Provider or production URL is contacted.

- [x] **Step 5: Run boundary and consistency guards**

~~~bash
git diff --check
if rg -n -P '(provider_call|providerCall|provider_call_attempted|providerCallAttempted|credential_read_attempted|credentialReadAttempted|live_client_created|liveClientCreated|production_write_allowed|productionWriteAllowed)\s*(?:"?\s*:|=)\s*true' apps/api/src/data_intelligence_hub/services/fixtures apps/web/src/lib/capability-mock.ts apps/web/src/lib/api/capabilities.ts apps/web/src/lib/api-market-catalog.ts; then exit 1; fi
if rg -n '[ \t]+$|^(<<<<<<<|=======|>>>>>>>)' apps/api/src/data_intelligence_hub/schemas/capability_matrix.py apps/api/src/data_intelligence_hub/services/capability_matrix.py apps/api/src/data_intelligence_hub/api/routes/capabilities.py apps/web/src/types/capability.ts apps/web/src/lib/api/capabilities.ts apps/web/src/lib/capability-mock.ts apps/web/src/lib/capability-market.ts apps/web/src/lib/api-market-catalog.ts apps/web/src/components/api-market apps/web/src/components/layout docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md; then exit 1; fi
if rg -n '^- \[ \] \*\*Step' docs/superpowers/plans/2026-07-10-goal-v2-01-capability-contract-foundation.md; then exit 1; fi
~~~

Expected: all four commands have no output. The explicit whitespace/conflict scan covers new untracked files that git diff --check cannot see.

- [x] **Step 6: Append exact Execution Evidence**

Append a section containing:

~~~markdown
## Execution Evidence

- implementation_status: complete
- evidence_scope: local_validation_and_mock_e2e
- provider_call: false
- credential_read_attempted: false
- live_client_created: false
- production_write_allowed: false
- database_migration: false
- api_ruff: passed
- api_mypy: passed
- api_pytest: passed
- alembic_head: 202606110026
- web_typecheck: passed
- web_lint: passed
- web_unit: passed
- web_build: passed
- web_mock_e2e: passed
- production_status: unchanged
~~~

Use actual counts from command output in additional lines. Do not infer counts or copy historical numbers. Append the same evidence boundary to .kiro/plan/progress.md.

- [x] **Step 7: Close every current-state document**

Apply these exact status changes only after Steps 1-6 pass:

~~~diff
# implementation plan frontmatter
-status: in_progress
+status: locally_complete
-review_status: approved_spec_and_self_reviewed
+review_status: local_gates_passed

# design spec frontmatter
-goal_execution: implementation_in_progress
+goal_execution: local_implementation_complete

# V2 PRD Goal line
-**Status**: in_progress
+**Status**: locally_complete
~~~

Replace .codex/context-pack.md Current Focus with:

~~~markdown
## Current Focus

GOAL-V2-02 is locally complete with fixture/API/unit/build/mock-E2E evidence only. Commit/push/PR, deployment, production acceptance, Provider execution, database changes, and GOAL-V2-03 activation remain separate unchecked gates. Production unchanged.
~~~

Keep GOAL-V2-03 and later Goals queued.

- [x] **Step 8: Close the local TODO.md state**

Mark Task 0-10 complete in TODO.md only after their evidence exists. Set its status to locally_complete. Keep separate unchecked entries for:

- commit/push/PR decision;
- deployment authorization;
- production read-only acceptance;
- GOAL-V2-03 activation;
- any Provider Live Gate.

- [ ] **Step 9: Final commit only after explicit commit authorization**

~~~bash
git add docs/superpowers/plans/2026-07-11-goal-v2-02-capability-matrix-navigation.md docs/superpowers/specs/2026-07-11-goal-v2-02-capability-matrix-navigation-design.md docs/product/product-prd-social-media-automation-platform-v2.md .codex/context-pack.md .kiro/plan/progress.md
git diff --cached --check
git commit -m "docs: close GOAL-V2-02 local evidence"
~~~

No push, PR, merge, deploy, or live action follows automatically.

## Execution Evidence

- implementation_status: complete
- evidence_scope: local_validation_and_mock_e2e
- evidence_grade: L2-fixture-or-dry-run
- provider_call: false
- provider_call_attempted: false
- credential_read_attempted: false
- live_client_created: false
- production_write_allowed: false
- database_migration: false
- api_ruff: passed
- api_mypy: passed
- api_mypy_files: 164
- api_pytest: passed
- api_pytest_count: 199
- api_pytest_skipped: 0
- api_pytest_warnings: 1
- alembic_head: 202606110026
- web_typecheck: passed
- web_lint: passed
- web_unit: passed
- web_unit_files: 7
- web_unit_count: 60
- web_build: passed
- web_build_static_pages: 22
- web_mock_e2e: passed
- web_mock_e2e_passed: 45
- web_mock_e2e_skipped: 11
- web_mock_e2e_total: 56
- web_mock_e2e_skip_breakdown: 2 real-API skips and 9 desktop skips for mobile-only guards
- ci_status: not_run
- deploy_status: not_run
- production_acceptance: not_run
- provider_execution: not_run
- production_status: unchanged

---

## Requirement Traceability

| Requirement | Implemented by | Fresh acceptance |
|---|---|---|
| CAP-001 / CAP-004 | Tasks 2-3 | 42-cell, unknown, mixed-status, filter, immutability tests |
| CAP-008 | Tasks 4-5 | real backend Fixture parity, 18 enhanced keys, 38 supported Endpoint projections, no fallback |
| CAP-009 | Task 7 | shared drawer with Resource, Operation, Implementation, Constraint, score, Evidence, Fixture Review |
| CAP-010 | Tasks 6-7 | 2-3 same-platform comparison with eight scores, constraints, and Evidence |
| UI-001 | Task 8 | one six-entry config used by desktop/mobile; legacy-route coverage |
| UI-004 | Tasks 6-7 | eight scenarios plus matrix/list URL-preserved views |
| UI-005 / UI-006 | Task 7 | fixed desktop cell geometry and accessible side drawer |
| UI-009 | Tasks 7-8 | 1440×900 and 375×812 mock Playwright acceptance |
| Control-plane and local closeout | Tasks 0, 9, 10 | current-state activation, contract sync, full local exit gate |

## Goal Exit Gate

The Goal can be described as locally complete only when:

1. Matrix API returns 7 platforms, 6 channels, and 42 explicit cells.
2. The 7 current official API cells are candidate and the other 35 are unknown.
3. No Assertion is upgraded by aggregation or display.
4. API Market capability facts come from the canonical backend API.
5. All 18 presentation keys pass against the real canonical Fixture, and all 38 supported Endpoint entries remain visible through enhanced or generic detail.
6. Scenario, matrix, list, and detail drawer work in desktop and mobile mock E2E.
7. Desktop and mobile navigation both expose exactly six primary entries.
8. Project Selector states whether filtering is actually applied.
9. Legacy pages and Social Provider compatibility APIs remain available.
10. API/Web/type/build/mock-E2E gates pass on the current working tree.
11. Control-plane documents agree on V2-01 complete and V2-02 current.
12. provider_call=false, database_migration=false, and production unchanged.

## Rollback Map

When task commits were explicitly authorized, use new `git revert` commits in this order; never reset or rewrite history:

1. Revert Task 10 local-complete closeout.
2. Revert Task 9 architecture/API/progress sync.
3. Revert Task 8 navigation; all legacy routes remain available.
4. Revert Task 7 capability UI; no data cleanup is required.
5. Revert Tasks 6, 5, and 4 Web helpers/contracts.
6. Revert Task 3 API router registration and route file.
7. Revert Task 2 matrix schema/service/error.
8. Revert Task 1 test-fixture typing only if restoring the known TypeScript blocker is intentional.
9. Revert Task 0 activation last so current-state documents continue to describe the runtime during rollback.

When commit authorization was absent, use tmp/goal-v2-02-base-sha, tmp/goal-v2-02-initial-status.txt, tmp/goal-v2-02-initial-tracked.patch, and tmp/goal-v2-02-initial-untracked.txt to review the Goal delta. Save the current task-scoped diff under tmp before any reversal. Reverse only Goal-owned hunks with apply_patch; delete a Goal-created file only after confirming it is absent from the initial-untracked manifest. Preserve every pre-existing draft/output/ref entry. `git reset`, `git checkout --`, `git clean`, and blanket reverse patches are prohibited.

There is no Alembic downgrade, database restore, Provider cleanup, Credential rotation, or production rollback in this Goal because those actions are outside scope.

## Execution Handoff

After this plan is reviewed, choose exactly one execution mode:

1. Subagent-Driven: use superpowers:subagent-driven-development, one fresh implementer per task with specification and quality review between tasks.
2. Inline Execution: use superpowers:executing-plans, execute in checked batches with review checkpoints.

Neither mode implies commit, push, PR, merge, deploy, production, database, or Provider authorization.

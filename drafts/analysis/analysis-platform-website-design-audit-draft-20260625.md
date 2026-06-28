---
title: "Platform website design audit and optimization backlog"
created_at: "2026-06-25T01:06:23Z"
status: "draft"
updated_at: "2026-06-25T02:36:00Z"
scope: "local website audit plus side-effect gate implementation slices"
project: "data_scrapy"
skills_used:
  - "claude-design"
  - "popular-web-designs"
  - "humanizer"
  - "playwright"
evidence:
  - "tmp/outputs/platform-website-design-audit-20260625/audit-render-snapshot.json"
  - "tmp/outputs/platform-website-design-audit-20260625/desktop-automation.png"
  - "tmp/outputs/platform-website-design-audit-20260625/mobile-automation.png"
  - "tmp/outputs/platform-website-design-audit-20260625/desktop-datasets.png"
  - "tmp/outputs/platform-website-design-audit-20260625/mobile-datasets.png"
  - "tmp/outputs/platform-website-design-audit-20260625-followup/audit-render-snapshot.json"
boundary:
  production_changed: false
  business_code_changed: true
  provider_call: false
  production_browser_run: false
  scheduler_mutation: false
  dataset_export_created: false
---

# Platform website design audit and optimization backlog

## 1. Audit boundary

This pass audits the current local Web platform in mock mode. It does not modify product code, deploy production, call providers, send emails, run production browser collection, create exports, or mutate schedules.

Fresh evidence was collected from `http://127.0.0.1:3100` with `NEXT_PUBLIC_MOCK_API=true`. The audited routes were:

- `/dashboard`
- `/automation`
- `/datasets`
- `/tasks`
- `/sources`
- `/reports`
- `/alerts`
- `/notifications`

## 2. Skill interpretation

`claude-design` was used as the process guardrail: start from repository context, inspect actual routes/components/tokens, avoid generic SaaS redesign, and verify the surface before making recommendations.

`popular-web-designs` was used as a reference library, not as a brand clone:

- Linear: precision, low-noise command surface, subtle hierarchy, controlled accent usage.
- Vercel: neutral canvas, shadow-as-border, tight component rules, strong focus states.
- Sentry: data-dense operational console patterns and incident/status communication.
- Supabase: developer-platform restraint, border-defined depth, technical labels used sparingly.

`humanizer` was used to evaluate user-facing copy. The goal is direct product language, not promotional language. Technical terms can remain when they help operators, but fallback English and internal debug names should not leak into normal product surfaces.

## 3. Fresh evidence summary

Render evidence:

| Route | Desktop status | Mobile status | Desktop buttons | Mobile buttons | Desktop card-like count | Mobile local overflow sample | Visible technical / English fallback |
|---|---:|---:|---:|---:|---:|---:|---|
| `/dashboard` | 200 | 200 | 0 | 0 | 25 | 0 | `Failed to` from toolkit overview fetch |
| `/automation` | 200 | 200 | 23 | 23 | 18 | 8 | `Browser Harness`, `browser-harness` |
| `/datasets` | 200 | 200 | 8 | 8 | 20 | 0 | none detected |
| `/tasks` | 200 | 200 | 81 | 81 | 20 | 0 | none detected |
| `/sources` | 200 | 200 | 34 | 34 | 23 | 0 | none detected |
| `/reports` | 200 | 200 | 17 | 17 | 23 | 0 | none detected |
| `/alerts` | 200 | 200 | 9 | 9 | 18 | 0 | none detected |
| `/notifications` | 200 | 200 | 17 | 17 | 15 | 0 | none detected |

Static check:

- `pnpm --dir apps/web exec tsc --noEmit` passed.
- Screenshots and the render snapshot were saved under `tmp/outputs/platform-website-design-audit-20260625/`.

Known local evidence caveat:

- Four routes emitted console messages while trying to fetch `http://localhost:8000/api/toolkit` in mock mode. This appears to come from `useTrainingOverview()` calling `getToolkitOverview()` while `apps/web/src/lib/api/toolkit.ts` does not branch on `mockApiEnabled` for `/api/toolkit`.

## 4. Current platform shape

### Facts

- The product is now an AI-assisted data collection workbench, not a training-first tool. `.kiro/plan/task_plan.md` defines the core journey as target URL/platform -> structure analysis -> field selection -> extraction plan -> cleaning plan -> structured storage -> scheduled runs -> quality and drift monitoring.
- The Web shell is shared through `apps/web/src/components/layout/app-shell.tsx`. It fixes the page width at `max-w-7xl`, uses a persistent sidebar on desktop, and adds a shared brief/signals strip on every main page.
- The global token base in `apps/web/src/app/globals.css` is warm: `#f7f0eb`, `#231a1a`, `#c25b6e`, and related cream/rose surfaces.
- `apps/web/src/app/dashboard/page.tsx`, `apps/web/src/app/automation/page.tsx`, and `apps/web/src/app/datasets/page.tsx` still frame parts of the product with training/demo language.
- `apps/web/src/components/automation/automation-workbench.tsx` is a very large component that owns platform packages, capability probes, site analysis, browser diagnostics, GitHub radar, fan-out, batch run, dataset preview, schedule approval, drift check, browser job contracts, and local runner controls.
- `apps/web/src/components/datasets/datasets-workspace.tsx` includes dataset exports, alert rule creation, alert event bridge, in-app notification sending, and email sending in one surface.

### Inferences

- The site already has strong product depth, but the UI reads like multiple generations of workbench features were layered into a warm demo shell. The product is more serious than the visual system suggests.
- The main design opportunity is not a landing-page redesign. It is an operator console redesign: tighter hierarchy, clearer task lanes, more explicit side-effect gates, and less card nesting.
- The copy should move from "training/demo/workbench" language to "collection/asset/monitoring/operator" language except where training content is the actual domain object.

### Uncertain items

- This audit did not inspect production screenshots in this pass. Production may differ because real data volume, auth, and API health can expose different density and copy issues.
- The render audit used mock mode. It proves local visual behavior and local mock-mode API routing, not live production data behavior.
- Screenshots were captured headlessly. A manual Chrome visual pass can still catch nuance around font rendering and scroll rhythm.

## 5. Main findings

### P0. Mock-mode toolkit data path leaks network noise into product pages

Evidence:

- `/dashboard`, `/tasks`, `/alerts`, and `/notifications` attempted `http://localhost:8000/api/toolkit` during a `NEXT_PUBLIC_MOCK_API=true` local run.
- The visible `/dashboard` sample included an English network fallback inside the training-content panel.
- Source path: `apps/web/src/lib/use-training-overview.ts` calls `getToolkitOverview()`, and `apps/web/src/lib/api/toolkit.ts` calls `apiFetch("/api/toolkit")` without a mock branch.

Impact:

- Local design QA and demos can show backend connectivity noise even when the rest of the app is intentionally mocked.
- This makes page review feel less reliable and weakens the product boundary between mock evidence and live evidence.

Recommendation:

- Add mock-mode support to toolkit overview/preflight API helpers or isolate the training/toolkit panel from pages that are now collection-first.
- Replace English fallback messages with short Chinese operator copy.
- Acceptance: with `NEXT_PUBLIC_MOCK_API=true`, audited routes should not call `localhost:8000/api/toolkit`; the visible text should not include raw English network messages.

### P0. Product positioning copy is stale in top-level pages

Evidence:

- `apps/web/src/app/dashboard/page.tsx` says "当前训练工作台".
- `apps/web/src/app/datasets/page.tsx` says saved datasets can enter "培训、调度或后续导出".
- `apps/web/src/app/notifications/page.tsx` uses "训练工作台状态".

Impact:

- The app has shifted to a data collection workbench, but the first-screen wording still partially sells the older training product.
- This blurs the product promise for operators: is this a training hub, a collection console, or a monitoring system?

Recommendation:

- Rename generic training references to collection/asset/monitoring language.
- Keep "training" only where the object is explicitly the toolkit or training content asset.
- Acceptance: top-level route briefs should describe the collection workflow and evidence boundary without mixing old product framing.

### P0. Side-effect controls need stronger visual gating

Evidence:

- `datasets-workspace.tsx` includes export creation, alert policy creation, event bridge, notification send, and email send in the same page.
- Several handlers pass `authorized: true` and `confirmCreate` / `confirmSend` from a button click path.

Impact:

- The backend may still enforce boundaries, but the UI should make side effects visibly different from read-only preview actions.
- The user has repeatedly required exact separation among read-only checks, production writes, email sends, provider calls, exports, and scheduler mutations.

Recommendation:

- Separate read-only preview actions from write/send actions with a visible gate pattern: scope summary, affected object count, retention/cleanup note, and a clearly named confirm action.
- Use different button hierarchy: read-only preview as neutral, write/send as high-friction.
- Acceptance: a reviewer can tell from the UI which buttons create records, write files, send messages, or only preview data.

### P1. Visual system is too warm and too rounded for an operational console

Evidence:

- Global tokens center on cream/rose (`#f7f0eb`, `#c25b6e`), while many pages repeat `rounded-2xl`, warm shadows, and soft card shells.
- `rg` found pervasive `rounded-2xl`, warm surface colors, and shadow stacks across dashboard, projects, entities, raw records, notifications, reports, and toolkit surfaces.

Impact:

- The system reads as a soft training/demo dashboard more than a precise platform workbench.
- Dense operational pages lose scan speed because too many regions receive similar card emphasis.

Recommendation:

- Move the base console toward a neutral system inspired by Vercel/Linear: neutral background, tighter 6-8px radii, shadow-as-border, fewer large soft cards.
- Keep rose only as one accent or semantic tone, not the dominant surface identity.
- Introduce distinct status colors for success/warning/risk/info, with rose reserved for one clear role.
- Acceptance: `/automation`, `/datasets`, `/tasks`, and `/sources` should read as one coherent operator console, not separate themed dashboards.

### P1. Touch targets are often below 44px

Evidence:

- The Playwright audit counted many interactive elements under 40px height, including sidebar links at 36px, automation mode buttons at 36px, field chips at 36px, and task table actions.
- The highest counts were `/tasks` and `/automation`.

Impact:

- Desktop density is acceptable, but mobile and touch use suffer.
- Tiny action buttons also make side-effect controls feel casual.

Recommendation:

- Define control sizes: 44px default touch target, 36-40px only for dense desktop-only table controls, and icon-only buttons with tooltips.
- For field chips and mode selectors, use segmented controls or checkbox pills with stable 40-44px height.
- Acceptance: mobile route audit should show no primary interactive controls below 40px and no workflow action below 44px.

### P1. `/automation` mobile layout has local geometry overflow

Evidence:

- Document-level horizontal scroll was not present, but the audit found local elements on `/automation` mobile with bounding boxes extending beyond the viewport, including the intake header and mode panel.

Impact:

- This is a near-miss: it may not create a visible horizontal scrollbar now, but longer content, translated labels, or font changes can break the layout.

Recommendation:

- Add stricter `min-w-0`, `max-w-full`, `overflow-hidden`, and responsive wrapping to the automation intake panel.
- Rework the mode selector into a scroll-safe segmented control.
- Acceptance: mobile geometry audit should return zero viewport-overflow samples for `/automation`.

### P1. Operational pages need clearer information lanes

Evidence:

- `/tasks` has 81 buttons and combines summary metrics, scheduler observations, filters, table actions, logs, and row-level controls.
- `/automation` includes platform packages, capability probes, fields, history, browser diagnostics, GitHub radar, dataset/schedule/drift, and local runner states in one page.

Impact:

- The features are valuable, but the page asks users to parse too many modules at the same visual weight.

Recommendation:

- Define lanes:
  - Intake: choose target, confirm boundary, run analysis.
  - Review: fields, candidates, source/task preview.
  - Persist: create assets, save dataset, approve schedule.
  - Monitor: drift, alerts, notification/export gates.
  - Diagnostics: browser diagnostic evidence and executor contracts.
- Use tabs or a left-side step rail for `/automation`; use table-first density for `/tasks`.
- Acceptance: every page should have one primary action area and one evidence/history area.

### P1. User-facing technical terms are mixed with product terms

Evidence:

- `/automation` visibly shows `Browser Harness`, `browser-harness`, `Topic Radar`, `ALLOWED OUTPUTS`, `FORBIDDEN`, and internal output names.
- Some terms are legitimate operator vocabulary, but they are not consistently introduced or translated.

Impact:

- Expert users can infer meaning, but business users may confuse internal execution components with product capabilities.

Recommendation:

- Keep technical nouns when they name an adapter, but wrap them in product labels:
  - "Browser Harness" -> "浏览器证据适配器 (browser-harness)"
  - "Topic Radar" -> "GitHub 主题雷达"
  - "ALLOWED OUTPUTS" -> "允许产物"
  - "FORBIDDEN" -> "禁止动作"
- Acceptance: product labels should lead; raw adapter names should be secondary.

### P2. Component architecture is ready for UI atom extraction

Evidence:

- Many pages manually repeat panel, metric, pill, status badge, action button, empty state, and alert box styling.
- `automation-workbench.tsx` and `datasets-workspace.tsx` carry large amounts of UI state and rendering logic.

Impact:

- Consistency work will be slow if every page keeps bespoke class strings.

Recommendation:

- Extract small Web-only primitives after the P0 copy/data-path work:
  - `WorkbenchPanel`
  - `StatusPill`
  - `MetricTile`
  - `ActionButton`
  - `EvidenceBoundary`
  - `EmptyWorkspace`
- Keep this narrow; do not refactor business logic during design cleanup.

## 6. Design direction

Recommended direction: "Linear/Vercel-style collection console with Sentry/Supabase status language."

Concrete rules:

- Background: move from cream to neutral off-white or very light gray for the main console.
- Radii: 6-8px for controls and cards; 12px only for major panels.
- Borders: prefer subtle ring/shadow-as-border over warm heavy borders.
- Accent: one primary accent; use semantic colors for state, not decoration.
- Typography: keep system fonts, tighten hierarchy with size/weight before adding boxes.
- Cards: reduce card nesting. Use table/list/detail panes for repeated operational objects.
- Actions: distinguish preview, create, send, export, and scheduler actions visually.
- Copy: direct Chinese labels first; technical adapter terms in parentheses only when useful.

## 7. To do

### P0: Fix current product trust issues

- [x] Add `mockApiEnabled` handling for toolkit overview/preflight paths used by shared pages.
- [x] Replace top-level "训练工作台" wording on non-toolkit pages with "数据采集工作台", "采集资产", or "运行监控" language.
- [ ] Localize English fallback messages in dashboard/datasets/automation/tasks/reports/shared API catch paths. Current slice covered dashboard, datasets, notifications, shared training overview, and the high-visibility automation GitHub topic path; reports/tasks/shared API catch paths remain open.
- [x] Add explicit side-effect labels for dataset export, alert event bridge, in-app notification send, email send, and scheduler mutation controls.
- [x] Re-run local mock Playwright audit and verify no toolkit network noise appears in audited routes.

### P1: Build the operator console visual system

- [ ] Introduce a small set of shared visual primitives for panels, pills, metrics, action buttons, boundary callouts, and empty states. First shared pass now covers lane rail, lane wrapper, panel, fact, status pill, and action gate; metric/action button/empty state remain open.
- [ ] Neutralize the global console palette while preserving rose as a limited accent or semantic tone.
- [ ] Reduce default radii from `rounded-2xl` to 6-8px on repeated cards and controls.
- [ ] Standardize focus rings and hover states across buttons, links, inputs, selects, and segmented controls.
- [ ] Enforce touch target rules: 44px for workflow actions; 40px minimum for compact secondary controls. Current slice fixed the `/automation` mode selector to 44px; broader route audit remains open.
- [x] Re-audit `/automation` mobile geometry until local overflow samples reach zero.

### P1: Rework core workflows

- [x] `/automation`: split into Intake, Review, Persist, Monitor, and Diagnostics lanes.
- [x] `/automation`: turn mode buttons into a responsive segmented control.
- [ ] `/automation`: separate public page structure preflight, GitHub API-first collection, product discovery, and browser diagnostic jobs more clearly.
- [x] `/datasets`: make read-only inspection the default pane and move export/send actions into gated panels.
- [ ] `/tasks`: make the table the primary surface, reduce competing metric cards, and group row actions.
- [ ] `/sources`: align source creation/test/enable states with the same boundary language as `/automation`.

### P2: Polish and verification

- [x] Run `pnpm --dir apps/web exec tsc --noEmit`.
- [x] Run `pnpm lint:web`.
- [x] Run `pnpm test:web`.
- [x] Run `pnpm --dir apps/web build`.
- [x] Run local Playwright desktop/mobile route smoke on `/automation`, `/datasets`, `/tasks`, `/sources`, `/dashboard`.
- [x] Capture before/after screenshots under `tmp/outputs/platform-website-design-audit-20260625/` or a dated follow-up directory.
- [x] Run `git diff --check`.

## 8. Suggested first implementation slice

Start with a narrow P0/P1 hybrid:

1. Fix toolkit mock mode so local pages stop leaking API connectivity noise.
2. Update top-level page briefs and high-visibility fallback copy.
3. Add a shared `ActionButton` and `StatusPill` only if they reduce immediate duplication in the touched pages.
4. Fix `/automation` mobile local overflow and mode selector target height.
5. Re-run the same render audit script and compare metrics.

This slice is small enough to validate quickly and large enough to move the platform away from the old training/demo skin.

## 9. First implementation slice closeout

Completed on 2026-06-25 as a local web/UI slice.

Changed:

- `apps/web/src/lib/api/toolkit.ts` now returns local mock-mode toolkit overview, preflight, and method-card draft responses when `NEXT_PUBLIC_MOCK_API=true`.
- High-visibility route briefs on `/dashboard`, `/datasets`, and `/notifications` now use collection/workbench language.
- Dashboard, datasets, notifications, shared training overview, and automation GitHub topic labels now use direct Chinese fallback copy.
- `/automation` intake mode selector now uses a 44px touch target and localized "GitHub 主题" label.
- `apps/web/tests/e2e/main-flows.spec.ts` now asserts the updated notification and automation labels.

Verification:

- `pnpm --dir apps/web exec tsc --noEmit`: passed.
- `pnpm lint:web`: passed.
- `pnpm test:web`: passed with 8 unit tests.
- `pnpm --dir apps/web build`: passed.
- Targeted Playwright E2E: `10 passed`, `6 skipped` for automation package, notification bulk-read, and mobile layout guard coverage.
- Follow-up render audit: `toolkitRequests=0`, `consoleMessages=0`, `documentOverflow=0`, `/automation` mobile `overflowSamples=0`, and mode buttons `height=44`.
- `git diff --check`: passed.

Evidence:

- `tmp/outputs/platform-website-design-audit-20260625-followup/audit-render-snapshot.json`
- `tmp/outputs/platform-website-design-audit-20260625-followup/desktop-automation.png`
- `tmp/outputs/platform-website-design-audit-20260625-followup/mobile-automation.png`
- `tmp/outputs/platform-website-design-audit-20260625-followup/desktop-dashboard.png`
- `tmp/outputs/platform-website-design-audit-20260625-followup/mobile-dashboard.png`

Remaining open work:

- Reports/tasks/shared API fallback localization.
- Broader neutral operator-console visual system and shared UI primitives.
- Deeper extraction of shared Web primitives after the `/automation` lane shell has stabilized.

## 10. Side-effect gate slice closeout

Completed on 2026-06-25 as a local web/UI slice.

Changed:

- `/datasets` now separates dataset export into a "文件写出 Gate" with write target, no-run boundary, and checksum review note.
- `/datasets` now separates drift alert controls into "只读预览 Gate", "策略写入 Gate", "事件桥接 Gate", "站内通知发送 Gate", and "外部邮件发送 Gate".
- `/automation` schedule approval now shows "调度变更 Gate" with task-config write scope plus `run_started=false` and `scheduler_tick_started=false` boundary labels.
- Dataset export and alert fallback copy now uses direct Chinese operator language instead of raw English fallback strings.
- `apps/web/tests/e2e/main-flows.spec.ts` now asserts the new gate labels in dataset and schedule flows.

Verification:

- `pnpm --dir apps/web exec tsc --noEmit`: passed.
- `pnpm lint:web`: passed.
- `pnpm test:web`: passed with 8 unit tests.
- Targeted Playwright E2E for automation package, browser diagnostic, and dataset gate smoke: `6 passed`.
- Targeted Playwright E2E for dataset save / drift check and `/datasets` mobile overflow guard: `3 passed`, `1 skipped`.
- `pnpm --dir apps/web build`: passed.
- `git diff --check`: passed.

Boundary:

- Local Web/UI and E2E only.
- No production deploy, production write, provider call, email send, dataset export creation, scheduler mutation, scheduler tick, production browser run, or browser artifact write.

## 11. Automation lane shell closeout

Completed on 2026-06-25 as a local web/UI slice.

Changed:

- `/automation` now has a five-step flow rail: 采集入口、复核、持久化、监控、诊断.
- The intake form is wrapped in a dedicated "采集入口与授权边界" lane.
- Capability probes and platform packages are grouped under "能力评估与平台包选择".
- Product-page history moved out of the intake card into a separate "历史采集方案" review lane.
- Browser diagnostic assets, automation plan history, diagnostic jobs, executor contracts, and local runner evidence moved into "浏览器诊断与执行器边界".
- Mode results now sit in a result lane whose label changes by workflow: product review, discovery persistence, GitHub persistence/monitoring, or structure preflight.
- E2E now asserts the new lane titles and includes `/automation` in the mobile overflow guard.

Verification:

- `pnpm --dir apps/web exec tsc --noEmit`: passed.
- `pnpm lint:web`: passed.
- `pnpm test:web`: passed with 8 unit tests.
- Targeted Playwright E2E for dataset save, platform package, and browser diagnostic flows: `6 passed`.
- `/automation` mobile overflow guard: `1 passed`, `1 skipped`.
- `pnpm --dir apps/web build`: passed after rerunning serially.
- `git diff --check`: passed.

Boundary:

- Local Web/UI and E2E only.
- No production deploy, production write, provider call, email send, dataset export creation, scheduler mutation, scheduler tick, production browser run, or browser artifact write.

## 12. Shared workbench primitives closeout

Completed on 2026-06-25 as a local Web/UI refactor slice.

Changed:

- Added `apps/web/src/components/common/workbench-ui.tsx`.
- Shared primitives now include `WorkflowLaneRail`, `WorkflowLane`, `WorkbenchPanel`, `WorkbenchFact`, `WorkbenchStatusPill`, and `ActionGate`.
- `/automation` now imports shared lane rail, lane wrapper, panel, and fact primitives.
- `/datasets` now imports shared panel, fact, and action gate primitives.
- Local business state, handler functions, API calls, and side-effect confirmation payloads were not moved.

Verification:

- `pnpm --dir apps/web exec tsc --noEmit`: passed.
- `pnpm lint:web`: passed.
- `pnpm test:web`: passed with 8 unit tests.
- Targeted Playwright E2E for automation package, browser diagnostic, dataset mock flow, and `/automation` + `/datasets` mobile overflow guards: `8 passed`, `2 skipped`.
- `pnpm --dir apps/web build`: passed.
- `git diff --check`: passed.

Remaining primitive work:

- Shared metric tile, action button, and empty state are still open.
- Status pill is available in the shared module but page-specific status badges with icons remain local until the status taxonomy is normalized.

Boundary:

- Local Web/UI refactor only.
- No production deploy, production write, provider call, email send, dataset export creation, scheduler mutation, scheduler tick, production browser run, or browser artifact write.

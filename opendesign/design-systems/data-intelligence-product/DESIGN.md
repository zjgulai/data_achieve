---
name: data-intelligence-product
version: 0.1.0
status: stable
updated: 2026-07-22
scope: apps/web product surfaces
---

# Data Intelligence Product DESIGN

## 1. Visual theme and atmosphere

The product is a calm, evidence-first operations workspace. It should feel precise,
traceable and trustworthy rather than futuristic or decorative.

The design combines three useful ideas from the `awesome-design-md` collection:

- Linear: scarce accent color, exact surface hierarchy, compact controls and hairline
  separation.
- Airtable: a light editorial workspace, structured data density and generous white
  space around primary decisions.
- Sentry: operational state must be visible, actionable and distinct from ordinary
  content.

This is an adaptation, not a visual copy. Keep the existing warm canvas and rose brand
identity. Do not introduce the reference products' lavender, violet, lime or ornamental
marketing motifs.

### Product character

- Warm, sober and exact.
- Business language on the default surface; technical diagnostics behind progressive
  disclosure.
- Data density where comparison is the job; breathing room where a decision is the job.
- One strong action per decision area.
- Evidence and constraints are first-class, not footnotes.

## 2. Color roles

Use `tokens/colors_and_type.css`. Components consume semantic variables, never raw hex
values.

| Role | Token | Use |
|---|---|---|
| Canvas | `--surface-canvas` | App background and page gutters |
| Primary surface | `--surface-primary` | Tables, panels, drawers, forms |
| Secondary surface | `--surface-secondary` | Nested groups and calm highlights |
| Muted surface | `--surface-muted` | Selected rows, empty states, grouped metadata |
| Brand action | `--action-primary` | One primary action per decision area |
| Info | `--state-info` | Read-only evidence and explanatory status |
| Success | `--state-success` | Completed/verified with supporting evidence |
| Warning | `--state-warning` | Held, partial, stale, needs review |
| Danger | `--state-danger` | Failed, blocked or destructive action |

Semantic state colors never carry meaning alone. Pair them with an icon, label and
plain-language explanation. Do not use the brand rose as a generic error color.

## 3. Typography

- Use the system sans stack. Do not add a font dependency for this iteration.
- Page title: 32/38, weight 600. Product pages should not use marketing-scale display
  type.
- Section title: 24/30, weight 600.
- Panel title: 18/24, weight 600.
- Default UI body: 14/22, weight 400.
- Labels: 13/18, weight 500. Avoid all caps in Chinese.
- Metadata: 12/17. Use mono only for IDs, hashes and payload snippets in Advanced mode.
- Emphasis comes from hierarchy and spacing, not repeated bold text.

## 4. Layout and density

- Base unit: 4px. Primary spacing steps: 4, 8, 12, 16, 24, 32, 48, 64.
- Desktop content max: 1280px. Sidebar: 272px. Do not scale content beyond the max;
  add outer breathing room.
- Default grid: 12 columns. Operational lists may use full-width tables.
- Decision pages use a 7/5 split: primary work area plus contextual evidence/summary.
- Lists and tables support Comfortable and Compact density; default to Comfortable.
- Large, repeated equal-height cards are not the default. Use rows and grouped panels for
  data comparison.

## 5. Depth and surfaces

Depth is carried by surface steps and borders, not decorative shadows.

- Level 0: canvas, no shadow.
- Level 1: white surface plus 1px subtle border.
- Level 2: selected or nested surface plus stronger border.
- Level 3: drawer, popover or modal with overlay shadow.
- Focus: visible 3px focus ring using `--focus-ring`.

Avoid stacked cards inside cards. A panel may contain rows, sections or a table; nested
panels require a real information boundary.

## 6. Shape system

- 4px: badges and compact status labels.
- 8px: inputs, buttons, table controls.
- 12px: panels, drawers and action gates.
- 16px: only high-level page summary or empty-state surfaces.
- Pill: status, filter chips and segmented selection only. Never use pill shape for all
  buttons.

## 7. Component contracts

Recreate and consolidate existing product components; do not add a parallel component
library.

### AppShell

- Desktop: sidebar, top bar, Project context, page title, description, optional boundary
  strip, then content.
- Mobile: top bar remains visible; navigation opens as a focus-trapped drawer.
- Project context is persistent in URL/query state and visible on every Project-scoped
  page.

### PageHeader

- One page title, one short outcome description and at most one primary action.
- Boundary metadata moves to a compact evidence strip or Advanced panel; do not put raw
  booleans in the hero.

### WorkbenchPanel

- 12px radius, subtle border, no default shadow.
- Header supports title, short subtitle and one action area.
- Prefer rows/table content over grids of nested cards.

### StatusBadge and StatusSummary

- Badge format: label + icon/dot. StatusSummary adds cause, impact and next action.
- Product state vocabulary: Draft, Ready, Running, Completed, Degraded, Held,
  Cancelled, Failed, Empty valid.
- Translate state for default Chinese UI. Preserve canonical state in Advanced mode.

### ActionGate

- Show what the action will do, what it will not do, evidence level, prerequisites and
  the next required approval.
- Preview, save, activate, run, send, export and live call are visually and verbally
  distinct actions.
- Destructive or live actions require a review step; disabled state explains the missing
  gate.

### DataTable / AssetList

- Sticky header, visible row selection, sortable columns, saved filters and density
  control.
- Essential fields stay left; Evidence and actions stay right.
- At narrow widths, switch to summary rows/cards rather than compressing every column.

### EvidenceDrawer

- Opens from a statement, status or row without losing Project/filter context.
- Shows claim, evidence grade, source, timestamp, lineage, limitations and canonical
  identifiers.
- Technical payload, fingerprint and hashes live in a collapsed Diagnostics section.

### Empty, loading and error states

- Loading: preserve page geometry with skeletons; use `aria-busy`.
- Empty: distinguish “not configured”, “no valid result”, “filtered out” and “not
  authorized”. Always offer the correct next action.
- Error: state what failed, impact, retry safety and alternative. Never surface raw
  Provider exception text.

## 8. Interaction principles

### Progressive disclosure

Default mode answers business questions. Advanced mode exposes provider, adapter,
fingerprint, quota, raw payload and audit identifiers. Advanced state is per user and
does not change underlying data.

### Context preservation

Project, Scope, date range, filters and selected Evidence survive list → detail → back
navigation. A deep link recreates the same view when authorization permits.

### Action hierarchy

- One primary action per panel or decision step.
- Secondary actions are outlined or text actions.
- Preview never looks like Run. Save never looks like Send.
- Disabled actions include an adjacent reason and remediation.

### Feedback

- Optimistic UI is limited to reversible local preferences.
- Plan saves, state transitions, exports, external calls and notifications wait for a
  server receipt.
- Toasts summarize; durable results live in the page and audit trail.

### Motion

- 120ms hover/focus, 180ms panel transition, 240ms drawer/dialog.
- Animate opacity and transform only. No parallax, bounce or ambient motion.
- Respect `prefers-reduced-motion`.

## 9. Responsive behavior

| Width | Behavior |
|---|---|
| ≥1440 | Full sidebar, 12-column content, optional evidence side pane |
| 1024–1439 | Full sidebar, reduced gutters, evidence drawer overlays content |
| 768–1023 | Collapsed navigation, two-column forms become one or two columns by task |
| 375–767 | Single column, 44px targets, bottom action bar for the current step |

Tables either scroll inside a labeled region or become summary rows. Never allow the page
itself to overflow horizontally. Sticky controls must not cover focused elements.

## 10. Content and terminology

- Use concise Chinese business language by default.
- Replace `RawRecord` with “原始记录”, `fixture` with “本地样例”, `fingerprint` with
  “配置校验值” only inside Advanced mode, and `held` with “已暂停，等待处理”.
- State facts first, then impact, then next action.
- Do not use “成功” for `degraded`, fallback or empty-valid outcomes.
- Keep provider names, API paths and canonical error codes unchanged only in Diagnostics.
- No emoji in product UI. Use existing Lucide icons with text labels.

## 11. Accessibility

- Minimum touch target 44×44px.
- Full keyboard path for navigation, planners, tables, drawers and dialogs.
- Focus is visible on every interactive element and restored when overlays close.
- Status does not rely on color. Errors connect to fields with accessible descriptions.
- Use `aria-live="polite"` for completed async operations and `role="alert"` for blocking
  failures.
- Meet WCAG 2.2 AA contrast for text and controls.

## 12. Do and do not

### Do

- Treat accent color as scarce and semantic.
- Show state, cause, impact and next action together.
- Keep Project context visible and persistent.
- Prefer a clear table or row to six equal cards when the job is comparison.
- Make evidence drilldown reachable from every business conclusion.
- Keep live/provider boundaries explicit and fail closed.

### Do not

- Do not add purple/blue gradients, glassmorphism or glowing SaaS cards.
- Do not place colored left accent strips on every card.
- Do not expose fixture/fingerprint/provider booleans in the default business view.
- Do not use color alone for state or put five primary buttons in one viewport.
- Do not mass-replace 267 color literals in one change; migrate by shared primitive and
  screen slice with visual regression evidence.
- Do not imply that a polished UI upgrades L2 evidence to live or GA.

## 13. Screen blueprints

### Dashboard

1. Project context and time range.
2. Two primary jobs: “创建周期监测” and “解析一批数据”.
3. Needs-attention queue: held/degraded/failed/stale/approval.
4. Outcome summary: latest Intelligence, Evidence coverage, next delivery.
5. Advanced operations summary collapsed by default.

### Planner

1. Business goal and Scope.
2. Source and capability choice.
3. Schedule, budget and delivery.
4. Review: plain-language summary, blockers and evidence.
5. Save Version. Activation and Run remain separate gated actions.

### Run detail

1. Current state and business impact.
2. Timeline of steps and attempts.
3. Budget/quota/health.
4. Fallback and missing-field comparison.
5. Evidence and Diagnostics drawer.
6. Allowed next action: retry, resume, cancel or request approval.

### Capability decision workspace

1. Scenario and resource intent.
2. Hard gates first.
3. Feasible candidate comparison.
4. Evidence recency and limitations.
5. Selection reason and approval receipt.

## 14. Agent implementation prompt

When changing a product screen:

1. Read this file and `tokens/colors_and_type.css`.
2. Preserve the current architecture and reuse `workbench-ui.tsx` components.
3. Run GitNexus impact before editing any symbol.
4. Identify the user's primary job, one primary action, default business content and
   Advanced diagnostics.
5. Use semantic tokens; do not add new raw hex values.
6. Implement loading, empty, error, disabled, success and degraded/held states.
7. Verify 375px and 1440px, keyboard flow, focus restoration, contrast and no horizontal
   overflow.
8. Record evidence level; do not imply live behavior unless separately verified.

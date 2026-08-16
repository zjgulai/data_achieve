---
title: Data Intelligence Product Design System
status: stable
updated: 2026-07-22
---

# Data Intelligence Product Design System

This folder defines the stable UI design system for the Data Intelligence Hub Web
product. It preserves the current warm, rose-accented interface while replacing scattered
visual decisions with semantic tokens, explicit interaction contracts and evidence-first
screen patterns.

## Sources consulted

- Current Web source: `apps/web/src/app/globals.css`, layout components,
  `common/workbench-ui.tsx`, Dashboard, Workflow Planner, Workflow Run and Capability
  Market workspaces.
- Current project review:
  `output/data-scrapy-project-review-design-guide-20260722.html`.
- Product and execution state: `TODO.md`, `.codex/context-pack.md`, PRD V2 traceability.
- [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md): DESIGN.md
  format and its sections for atmosphere, semantic color, type, components, layout,
  depth, guardrails and responsive behavior.
- Selected references from that collection: Linear for precise hierarchy and scarce
  accent, Airtable for a light structured workspace, and Sentry for operational state
  visibility. Their identities are not copied.

## Index

- `DESIGN.md`: canonical visual, interaction, responsive, accessibility and copy rules.
- `tokens/colors_and_type.css`: canonical raw and semantic tokens.
- `brand/voice-and-tone.md`: product language and terminology.
- `brand/style-notes.md`: rationale, retained patterns and migration boundaries.
- `ui-kit-web/index.html`: static review catalog built from existing product patterns.
- `SKILL.md`: portable agent entrypoint.

## Current audit baseline

- 56 product component TSX files.
- 4,778 raw six-digit color occurrences and 267 unique values in `apps/web/src`.
- Only two current `var(--...)` uses, both in `globals.css`.
- Shared Workbench primitives already exist and should be migrated rather than replaced.
- Current product language mixes business and diagnostic terms; the stable system
  separates default and Advanced modes.

These counts are a 2026-07-22 local snapshot. They are planning evidence, not a quality
score and not a production acceptance result.

## Approval and first adoption evidence

- Owner approval: 2026-07-22.
- First implementation slice: `UX-B01 / UIX-02`.
- Runtime adoption: canonical tokens imported by `apps/web/src/app/globals.css`;
  AppShell, Sidebar, TopBar, MobileNavigation and shared Workbench primitives migrated.
- Local evidence: 19 unit files / 256 tests, TypeScript, full ESLint and 26/26 Next build;
  reviewed 1440px and 375px screenshots, mobile Escape focus restoration and no horizontal
  overflow; eight core foreground/background token pairs meet WCAG AA contrast.
- Boundary: this is UI evidence only; Provider, database, production and GA remain unchanged.

## Adoption rule

Do not run a repository-wide color replacement. Migrate in this order:

1. Global tokens and AppShell.
2. Shared Workbench primitives and state semantics.
3. Dashboard and Project context.
4. Planner, Runs and ActionGate.
5. Capability, Data Assets and Intelligence surfaces.
6. Remaining domain/toolkit pages.

Each slice must pass focused tests, TypeScript, ESLint, 375/1440 layout checks, keyboard
acceptance and a reviewed visual diff.

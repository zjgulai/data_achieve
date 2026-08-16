---
name: data-intelligence-product-design
description: Apply the Data Intelligence Hub product design system to apps/web UI work.
status: stable
---

# Data Intelligence Product Design Skill

Use this skill for UI, UX, interaction, responsive, accessibility or product-copy changes
inside `apps/web`.

## Required reading

1. `DESIGN.md`
2. `tokens/colors_and_type.css`
3. `README.md`
4. `../../../docs/product/data-intelligence-ui-ux-integrated-plan-2026-07-22.md`
5. The current screen source and its tests

## Working rules

- Preserve the current product architecture and reuse existing Workbench components.
- Use semantic tokens; do not introduce raw hex values in migrated components.
- Keep default business language separate from Advanced diagnostics.
- Implement state, cause, impact and next action together.
- Treat Preview, Save, Activate, Run, Export, Send and Live Call as distinct gates.
- Preserve Project, Scope, filter and Evidence context across navigation.
- Verify 375px and 1440px, keyboard operation, focus restoration, contrast and reduced
  motion.
- Run GitNexus impact before editing any function, class or method.
- Do not claim Provider, production or GA evidence from UI/fixture checks.

## Canonical outputs

- Tokens: `tokens/colors_and_type.css`
- UI rules: `DESIGN.md`
- Execution plan: project-level integrated UI/UX plan referenced above

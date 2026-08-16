<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **data_achieve** (25560 symbols, 43899 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/data_achieve/context` | Codebase overview, check index freshness |
| `gitnexus://repo/data_achieve/clusters` | All functional areas |
| `gitnexus://repo/data_achieve/processes` | All execution flows |
| `gitnexus://repo/data_achieve/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

## Product UI design source

- Before changing `apps/web` UI, UX, interaction, responsive behavior, accessibility or
  product copy, read
  `opendesign/design-systems/data-intelligence-product/DESIGN.md` and
  `opendesign/design-systems/data-intelligence-product/tokens/colors_and_type.css`.
- The integrated screen roadmap and dependency map are in
  `docs/product/data-intelligence-ui-ux-integrated-plan-2026-07-22.md`.
- `TODO.md` remains the execution-status source of truth. UIX-01 received Owner approval
  on 2026-07-22; the design system is stable, while individual screens remain governed by
  their own UIX acceptance status.
- Preserve the current Web architecture and migrate shared primitives by narrow slices.
  Do not mass-replace raw colors or imply live/production readiness from a visual change.

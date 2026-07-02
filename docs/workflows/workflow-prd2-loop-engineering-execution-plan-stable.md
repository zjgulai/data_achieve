---
title: PRD2 Loop Engineering Execution Plan
doc_type: workflow
module: automation
topic: prd2-loop-engineering
status: stable
created: 2026-07-01
updated: 2026-07-02
owner: self
source: human+ai
evidence_boundary: "docs/local/read-only loop by default; production write, cleanup execute, provider call, email send, scheduler mutation, production browser run, and browser artifact write require separate explicit authorization"
---

# PRD2 Loop Engineering Execution Plan

## 0. Evidence Boundary

This plan starts a bounded engineering loop for the remaining PRD2 work. It does not claim any new production write, provider call, email send, cleanup execute, scheduler mutation, production browser run, or browser artifact write.

Fresh current-state inputs:

- Product context: Data Intelligence Hub is a traceable data collection and analysis platform with the core chain `RawRecord -> EntitySnapshot -> Signal -> Intelligence -> Evidence -> Report / Alert`.
- Current production identity evidence: active app `HEAD` and `.deploy-sha` are `b81a4be2a47f387d381293db7c4b2932128f6708`; production health is `production/ok/connected/current` with schema `202606110026`.
- Current source-control evidence: local branch `codex/release-3b-on-428` and `origin/codex/release-3b-on-428` now point to docs-only follow-up commit `9e3d2077a3903b627b8f0a489caf8b1acf897616`; production remains on release commit `b81a4be2a47f387d381293db7c4b2932128f6708`; `main` and `origin/main` remain at `42851929d59d82708c9380d36347ca721979297d`; draft PR #10 exists for `codex/release-3b-on-428 -> main` and was first observed as `OPEN`, `isDraft=true`, `mergeable=MERGEABLE`.
- M5 retained public-content final 168h observation is complete: default 168h dry-run now matches the retained graph with `cleanup_ready=true` and `export_artifact_path_violations=0`; cleanup execute remains separate.
- Existing `.Codex/ralph-loop.local.md` and `TODO.md` represented an older closed loop that was already marked complete; this document supersedes that loop for PRD2 remaining-task execution.

## 1. Loop Engineering Five Components

### Component 1: Goal Contract

Goal: close the remaining PRD2 platform-collection gaps by turning each target platform or side-effect capability into an evidence-graded work package.

Completion means:

- Every remaining PRD2 task has a current owner track, evidence grade, next action, and blocked boundary.
- Safe autonomous work is completed through docs/local/read-only gates.
- Any task requiring live side effects is queued with explicit authorization requirements rather than executed implicitly.

Component constraints:

- Do not call a task "done" without a fresh evidence artifact or command result.
- Do not merge local, dry-run, production read-only, authorized production write, provider call, and email send into one claim.
- Do not execute production writes, provider calls, email sends, cleanup execute, scheduler mutation, production browser run, or browser artifact writes inside the autonomous loop.

### Component 2: State Model

State is the machine-readable and human-readable snapshot that each loop iteration reads before acting.

Canonical state files:

- `.Codex/ralph-loop.local.md`
- `TODO.md`
- `docs/workflows/workflow-prd2-deployed-state-gap-execution-plan-stable.md`
- `docs/workflows/workflow-prd2-platform-collection-execution-plan-stable.md`
- `docs/workflows/workflow-prd2-r0-release-boundary-execution-log-stable.md`
- `docs/product/product-prd-data-intelligence-hub-stable.md`
- `docs/api/api-contract-data-intelligence-hub-stable.md`
- `docs/architecture/architecture-data-intelligence-hub-stable.md`

Component constraints:

- Read current state before every iteration; do not rely only on prior chat.
- Treat dirty worktree state as input, not as something to revert.
- Keep tracked docs, untracked drafts, and code changes separated in closeout.

### Component 3: Action Policy

Allowed autonomous actions:

- Docs and planning sync.
- Local static validation.
- Local tests and builds when they do not require secrets or live providers.
- Production read-only probes already defined in `.Codex/commands.md`.
- Dry-run cleanup checks without `--execute`.

Blocked without explicit authorization:

- `--execute` cleanup.
- Any production write or data mutation.
- Provider calls.
- Email send.
- Scheduler mutation or live tick that writes runs.
- Production browser execution.
- Screenshot, trace, HAR, cookie, header, or body artifact writes.
- Deploy, service restart, marker rewrite, or symlink rewrite.

Component constraints:

- Pick one incomplete task per iteration.
- Prefer finishing one evidence slice over widening scope.
- If the next useful step is blocked by a live side effect, stop and write an authorization packet instead of improvising.

### Component 4: Evaluator

Every iteration must end with explicit verification.

Default verification:

```bash
git diff --check
```

Docs-only verification:

```bash
rg -n "production write|provider call|email send|cleanup execute|production browser|browser artifact" docs/workflows drafts/analysis .Codex TODO.md
```

Local code verification, when code changes are included:

```bash
pnpm lint:web
pnpm test:web
bash scripts/verify-mvp.sh
```

DB/API verification, when migrations or backend contracts are included:

```bash
bash scripts/verify-mvp.sh --with-db
```

Component constraints:

- A passing local gate cannot be reported as production acceptance.
- A production read-only smoke cannot be reported as write-through validation.
- A dry-run cleanup plan cannot be reported as deleted assets.

### Component 5: Memory And Feedback

The loop must preserve what changed, what was verified, and what remains blocked.

Feedback sinks:

- `TODO.md` for machine-visible loop progress.
- `.kiro/plan/progress.md` for project progress when fresh evidence changes state.
- Workflow docs for stable execution state.
- `tmp/outputs/` for bounded evidence artifacts.
- Self-evolution candidate pool only after a concrete failure, correction, or test failure, and only as candidate memory.

Component constraints:

- Do not write long-term memory automatically.
- Do not store secrets, tokens, passwords, private keys, or personal private data.
- Keep `docs-only`, `draft`, `read-only`, `production unchanged`, `no provider call`, and `manual review` as literal boundaries.

## 2. Current Remaining Work Packages

| Priority | Package | Current fact | Next loop action | Boundary |
|---|---|---|---|---|
| P0 | Loop state and task tracker | Previous loop marked all tasks complete | Replace loop state with PRD2 remaining-task loop and validate docs | docs/local only |
| P0 | Dirty worktree scope audit | Many code/docs/migration files are modified or untracked | Produce scoped diff audit by track before touching code | local read-only |
| P0 | State sync | Retained TTL final observation changed M5 current state | Sync stale platform plan lines to 2026-07-01 evidence | docs-only |
| P0 | Run safety / provider-email readiness | Local idempotency and default-deny contracts exist | Refresh production read-only readiness packet; do not send | production read-only only |
| P0 | Independent site / Shopify-style production gate | Local public test-site E2E exists | Prepare authorization packet with URL, max pages, cleanup/retention plan | no live write until approved |
| P1 | GitHub API-first scale gate | Small L4 package gate completed | Prepare larger-scope rate-limit and retention/export plan | no production write until approved |
| P1 | Public Web/RSS/Docs cleanup decision | Default 168h dry-run is cleanup-ready | Prepare cleanup execute authorization packet or defer retained canary | no `--execute` until approved |
| P1 | Browser evidence governance | Local metadata-only gates exist | Prepare L3 read-only browser observation packet | no production browser until approved |
| P2 | ExternalToolSnapshot/import-only | PRD object defined, implementation absent | Plan local schema/API/UI slice | local code only after scoped diff audit |
| P2 | Video transcript import | PRD boundary defined | Plan metadata/transcript import schema | no media download |
| P2 | Public community aggregate | PRD boundary defined | Plan aggregate-only package | no person-level profiling |
| P3 | Social SOP/import-only | PRD boundary defined | Plan SOP/import-only package states | no automatic scraping |

## 3. Iteration Plan

### Loop 0: Control Plane Reset

Objective: replace the stale completed loop with a current PRD2 loop and verify that the plan is self-consistent.

Actions:

1. Back up old loop/TODO files.
2. Create this workflow.
3. Update `.Codex/ralph-loop.local.md` and `TODO.md`.
4. Run `git diff --check`.

Exit criteria:

- `TODO.md` lists current loop tasks.
- `.Codex/ralph-loop.local.md` points to this workflow.
- No production side effects occurred.

### Loop 1: Dirty Worktree Scope Audit

Objective: prevent unrelated work from being blended into one release or one completion claim.

Actions:

1. Group modified/untracked files into tracks: run safety/provider-email, PRD/docs, platform collection, migrations, frontend automation/tasks, tests, scripts.
2. Identify files touched by current loop vs pre-existing changes.
3. Produce `tmp/outputs/prd2-loop-diff-audit-YYYYMMDD.md`.

Exit criteria:

- Each dirty file has an ownership track and release risk label.
- No files are reverted.

### Loop 2: Current-State Documentation Sync

Objective: align stale docs with the retained TTL final observation and known unfinished gates.

Actions:

1. Update stale current-state lines in `workflow-prd2-platform-collection-execution-plan-stable.md`.
2. Cross-check PRD/API/architecture documents for outdated "default 168h pending" wording.
3. Run `git diff --check`.

Exit criteria:

- Current docs no longer list default 168h TTL observation as pending.
- Cleanup execute remains separate.

### Loop 3: Safe Local Verification

Objective: verify whether the current dirty worktree can pass the non-production gates.

Actions:

1. Run `git diff --check`.
2. If scope audit shows code changes are coherent, run the relevant local tests.
3. Record failures as blockers and candidate self-evolution only if concrete and reusable.

Exit criteria:

- Either local gates pass, or blockers are named with exact failing commands.

### Loop 4: Authorization Packet Queue

Objective: convert live side-effect work into approval-ready packets.

Packets:

- Retained cleanup execute.
- Independent site production/customer-site gate.
- Provider/email L4 send.
- GitHub larger-scope rate-limit gate.
- Production browser read-only observation.

Exit criteria:

- Each packet states allowed action, forbidden action, evidence artifacts, rollback/cleanup, and stop condition.

## 4. First Execution Order

1. Complete Loop 0 now.
2. Execute Loop 1 next.
3. Execute Loop 2 only after Loop 1 confirms docs scope is separable from code scope.
4. Execute Loop 3 only after code ownership is clear.
5. Stop before Loop 4 live side effects unless explicit authorization is given.

## 5. Definition Of Done

The PRD2 loop is complete only when:

- `TODO.md` marks `[x] ALL_TASKS_COMPLETE`.
- All safe docs/local/read-only tasks have fresh evidence.
- All remaining live side-effect tasks are either completed with explicit authorization and cleanup evidence, or intentionally deferred with a documented authorization packet.
- No boundary wording has been weakened.

---
title: "M5 Production Identity Probe Standardization"
status: "draft"
created_at: "2026-06-25"
scope: "documentation and runbook standardization"
evidence_level: "docs-only with prior L3 production read-only evidence"
cleanup_executed: false
---

# M5 Production Identity Probe Standardization

## Decision

Future production closeout and release identity checks for the current compose deployment layout must use the active app marker:

```bash
cd /opt/data-achieve-scrapy/app
git rev-parse HEAD
cat .deploy-sha
docker inspect data_achieve_scrapy_api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
docker inspect data_achieve_scrapy_web --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
curl -fsS https://scrapy.lute-tlz-dddd.top/api/health
```

Expected identity source: `/opt/data-achieve-scrapy/app/.deploy-sha` should match `/opt/data-achieve-scrapy/app` `HEAD`.

## Basis

The 2026-06-24 deploy marker diagnosis found:

- Active app working tree: `/opt/data-achieve-scrapy/app`.
- Active app marker: `/opt/data-achieve-scrapy/app/.deploy-sha=3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
- Active app `HEAD=3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
- API/Web containers use compose working directory `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`.
- Parent `/opt/data-achieve-scrapy/.deploy-sha=dda2786638d4aac8647bbff8b3694b05113678f3` and `/opt/data-achieve-scrapy/current` point to an older release-directory path.

## Supported Claims

1. Current compose deployment identity should be checked from `/opt/data-achieve-scrapy/app`.
2. The active marker to compare with `HEAD` is `/opt/data-achieve-scrapy/app/.deploy-sha`.
3. Parent marker and `current` symlink are historical release-directory metadata until a separate housekeeping gate changes them.

## Unsupported Claims

- This pass repaired parent marker files.
- This pass updated `current`.
- This pass deployed code or restarted services.
- This pass executed retained cleanup, mutated scheduler state, called providers, sent email, ran a production browser, or wrote browser artifacts.

## Files Updated

- `.codex/commands.md`
- `docs/workflows/workflow-prd2-r0-release-boundary-execution-log-stable.md`
- `docs/workflows/workflow-prd2-deployed-state-gap-execution-plan-stable.md`
- `.kiro/plan/task_plan.md`
- `.kiro/plan/progress.md`

## Remaining Separate Gate

If the release-directory deployment path is still intended to be used, open a separate production housekeeping gate to deliberately update `/opt/data-achieve-scrapy/.deploy-sha` and `/opt/data-achieve-scrapy/current`, with rollback notes and read-only post-checks.

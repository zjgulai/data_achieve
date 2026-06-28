---
title: "M5 Deploy Marker Diagnosis"
status: "draft"
created_at: "2026-06-24"
scope: "production deploy marker read-only diagnosis"
evidence_level: "L3-production-read-only"
cleanup_executed: false
---

# M5 Deploy Marker Diagnosis

## Decision

This pass diagnoses the apparent deploy marker drift found during the retained TTL observation baseline. It is read-only. It does not rewrite marker files, restart services, deploy code, run cleanup, mutate scheduler state, call providers, send email, or touch retained canary assets.

## Fresh Evidence

- Health: `GET https://scrapy.lute-tlz-dddd.top/api/health` returned `environment=production`, `status=ok`, `database=connected`, `schema=current`, `schema_revision=202606110023`, `schema_head=202606110023`, and `scheduler_enabled=true`.
- Active app working tree: `/opt/data-achieve-scrapy/app` is at `HEAD=3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
- Active app marker: `/opt/data-achieve-scrapy/app/.deploy-sha` contains `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331` and was modified on 2026-06-24 18:40 CST.
- Parent marker: `/opt/data-achieve-scrapy/.deploy-sha` contains `dda2786638d4aac8647bbff8b3694b05113678f3` and was modified on 2026-06-19 19:07 CST.
- Parent `current` symlink points to `/opt/data-achieve-scrapy/releases/20260619190523-dda2786638d4`, not the active app working tree.
- Running API container compose working directory is `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`; image ID `sha256:1df3dd1c2b877a048a102f3ecc4e5af948967eccfc7c490b3f85896182d9814d`, container created `2026-06-24T10:40:09Z`.
- Running Web container compose working directory is `/opt/data-achieve-scrapy/app/configs/deploy/scrapy`; image ID `sha256:6835637a20996bfd842c17b774ee4d6e5868d24b337fbd1ba6ce9291531f61d4`, container created `2026-06-24T03:41:16Z`.
- Local search for `.deploy-sha` references found docs/drafts references, but no active repo deploy script under `scripts`, `configs`, or `.github` that establishes `/opt/data-achieve-scrapy/.deploy-sha` as the current compose marker.

## Interpretation

The earlier mismatch came from reading the parent marker `../.deploy-sha` from inside `/opt/data-achieve-scrapy/app`. The active deployment marker for the current compose working tree is `/opt/data-achieve-scrapy/app/.deploy-sha`, and it matches the active app `HEAD`.

The parent marker and `current` symlink are stale remnants from an older release-directory deployment path. They should not be used as the evidence source for the current compose deployment unless the deployment process is intentionally moved back to the release symlink pattern.

## Supported Claims

1. Production health is current and healthy.
2. The active app working tree and active app `.deploy-sha` both point to `3c92fcbf2230e1b0b4eef71afea2b8e7547d3331`.
3. The apparent deploy marker drift was a marker path selection issue, not evidence that the running API is on `dda2786638d4aac8647bbff8b3694b05113678f3`.
4. Future production identity checks for the current deployment layout should read `/opt/data-achieve-scrapy/app/.deploy-sha` or run from `/opt/data-achieve-scrapy/app`.

## Unsupported Claims

- The parent marker was repaired.
- The `current` symlink was updated.
- A deploy was executed in this pass.
- Containers were restarted in this pass.
- Retained cleanup, provider calls, email sends, scheduler mutation, production browser runs, or browser artifact writes occurred.

## Follow-Up

If we want to remove the stale parent marker ambiguity, treat it as a separate production housekeeping task: either update `/opt/data-achieve-scrapy/.deploy-sha` and `current` deliberately, or standardize all probes on `/opt/data-achieve-scrapy/app/.deploy-sha` and label parent release markers historical.

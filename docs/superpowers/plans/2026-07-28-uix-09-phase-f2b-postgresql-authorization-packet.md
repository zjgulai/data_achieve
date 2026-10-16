---
title: UIX-09 Phase F2B Workflow Executor PostgreSQL Authorization Packet
doc_type: authorization_packet
module: workflow-execution
topic: uix-09-phase-f2b-postgresql-candidate
status: exact_target_completed_cleanup_verified
created: 2026-07-28
updated: 2026-07-28
owner: self
source: human+ai
evidence_grade: L2-disposable-local-postgresql-candidate
authorization_grade: L4-exact-local-side-effect
phase_f2a_authorized: true
phase_f2b_packet_preparation_authorized: true
phase_f2b_authorized: true
owner_authorization_present: true
exact_target_selected: true
docker_reachable: true
image_present_locally: true
image_pull_required: false
connection_attempted: true
image_pull_attempted: false
runner_started: true
sql_executed: true
migration_execution: true
cleanup_verified: true
provider_call: false
credential_read_attempted: false
production_boundary: production unchanged
---

# UIX-09 Phase F2B PostgreSQL Authorization Packet

## 1. Decision currently gated

F2B is complete for the exact disposable target below. The Owner's generic
`同意下一门禁` decision on
2026-07-28 authorizes preparation of this exact tuple only because the target,
runner and authorization string had not yet been presented. It cannot approve
an unknown runtime target retroactively.

The Owner subsequently supplied the complete authorization string from section
2 verbatim on 2026-07-28. The exact lifecycle passed after preserving three
fixture-only negative attempts, and the named runner was destroyed with its
port proved closed. Historical Phase E authorization remains consumed and
invalid here.

## 2. Exact tuple proposed for Owner approval

| Field | Exact value |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `55444` |
| Database | `uix09_phase_f2b_20260728_workflow_executor_test` |
| User | `phase_f2b_test` |
| URL | `postgresql+asyncpg://phase_f2b_test@127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test` |
| Authorized target | `127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test` |
| Runner id | `data-scrapy-uix09-phase-f2b-pg15-20260728` |
| PostgreSQL image | `postgres:15` |
| Local image digest | `sha256:74e110c41804365e3915fcc09d5e7a1eff50161aaa94d5da0e58e0cd75ae509c` |
| Storage | ephemeral container storage; no volume |
| Network exposure | loopback only: `127.0.0.1:55444:5432` |
| Revision lifecycle | `043 -> 044 -> 043 -> 044` |
| Cleanup contract | `destroy_exact_runner_and_prove_port_closed` |

The only valid authorization string is:

```text
authorize-workflow-executor-postgres-candidate:127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test:revision-202607280044:runner-data-scrapy-uix09-phase-f2b-pg15-20260728:image-postgres:15:cleanup-destroy_exact_runner_and_prove_port_closed
```

Approval must include this exact string without abbreviation. `同意`, `通过`,
or another generic response does not authorize the runtime.

## 3. Fresh read-only preflight evidence

At `2026-07-28T13:54:20+0800`:

- `lsof` found no listener on TCP port `55444`;
- Docker listed no container using the exact runner name and no container port
  binding for `55444`;
- Docker client/server `29.4.1` was reachable;
- local `postgres:15` resolved to the exact image digest recorded above;
- the exact database, user and runner names had no repository-history match;
- the only repository occurrence of the bare number `55444` was an unrelated
  negative guard-test replacement literal, not a target or runner;
- no password, query, fragment or encoded URL component is present.

This is L1 read-only preflight evidence only. No listener, runner or database
was created; no image was pulled; no PostgreSQL connection, SQL or migration
was attempted.

## 4. Image and environment authority

The local image is already present, so `image_pull_required=false`. The proposed
authorization does **not** permit `docker pull`. If `postgres:15` is absent or
its digest changes at execution time, F2B must stop and return to the Owner
rather than pull or substitute an image.

The runtime must use the existing Docker daemon only. It does not authorize
starting Docker Desktop, using native PostgreSQL, connecting to port `5432`, or
touching any existing Compose service, database, container or volume.

## 5. Exact commands executed under authorization

### 5.1 Revalidate the target before creation

```bash
lsof -nP -iTCP:55444 -sTCP:LISTEN
docker ps -a --filter 'name=^/data-scrapy-uix09-phase-f2b-pg15-20260728$'
docker image inspect postgres:15 --format '{{.Id}} {{json .RepoDigests}}'
```

Any listener, exact-name collision, missing image or digest mismatch stops the
run. These commands grant no cleanup authority over a pre-existing collision.

### 5.2 Start the exact disposable runner

```bash
docker run -d \
  --name data-scrapy-uix09-phase-f2b-pg15-20260728 \
  --pull=never \
  --label data-scrapy.gate=uix09-phase-f2b \
  --label data-scrapy.cleanup=destroy-exact-runner \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -e POSTGRES_USER=phase_f2b_test \
  -e POSTGRES_DB=uix09_phase_f2b_20260728_workflow_executor_test \
  -p 127.0.0.1:55444:5432 \
  postgres:15
```

No `--volume`, named volume, host directory or shared network is allowed.

### 5.3 Prove the exact runtime identity

```bash
docker exec data-scrapy-uix09-phase-f2b-pg15-20260728 \
  pg_isready -U phase_f2b_test \
  -d uix09_phase_f2b_20260728_workflow_executor_test

docker exec data-scrapy-uix09-phase-f2b-pg15-20260728 \
  psql -v ON_ERROR_STOP=1 -At \
  -U phase_f2b_test \
  -d uix09_phase_f2b_20260728_workflow_executor_test \
  -c 'SHOW server_version;' \
  -c 'SELECT current_user;' \
  -c 'SELECT current_database();'
```

Only directly observed PostgreSQL 15 or newer, exact user and exact database
may advance to the candidate suite.

### 5.4 Run the guarded candidate lifecycle

```bash
WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED=true \
WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED=true \
WORKFLOW_EXECUTOR_TEST_DATABASE_URL='postgresql+asyncpg://phase_f2b_test@127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test' \
WORKFLOW_EXECUTOR_AUTHORIZED_TARGET='127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test' \
WORKFLOW_EXECUTOR_RUNNER_ID='data-scrapy-uix09-phase-f2b-pg15-20260728' \
WORKFLOW_EXECUTOR_POSTGRES_IMAGE='postgres:15' \
WORKFLOW_EXECUTOR_CLEANUP_CONTRACT='destroy_exact_runner_and_prove_port_closed' \
WORKFLOW_EXECUTOR_AUTHORIZATION='authorize-workflow-executor-postgres-candidate:127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test:revision-202607280044:runner-data-scrapy-uix09-phase-f2b-pg15-20260728:image-postgres:15:cleanup-destroy_exact_runner_and_prove_port_closed' \
./scripts/verify-workflow-executor-migration.sh
```

The verifier may run without `--check-only` only after the exact authorization
is recorded in project state.

### 5.5 Destroy only the exact runner and prove closure

```bash
docker rm -f data-scrapy-uix09-phase-f2b-pg15-20260728
docker ps -a --filter 'name=^/data-scrapy-uix09-phase-f2b-pg15-20260728$'
lsof -nP -iTCP:55444 -sTCP:LISTEN
```

Cleanup authority applies only to the runner created by this exact authorized
run. If preflight finds a same-name runner before creation, stop without
removing it. Cleanup must run after success or failure, and absence plus a
closed port require independent evidence before `cleanup_verified=true`.

## 6. Runtime environment required after exact approval

- `WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED=true`
- `WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED=true`
- `WORKFLOW_EXECUTOR_TEST_DATABASE_URL=postgresql+asyncpg://phase_f2b_test@127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test`
- `WORKFLOW_EXECUTOR_AUTHORIZED_TARGET=127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test`
- `WORKFLOW_EXECUTOR_RUNNER_ID=data-scrapy-uix09-phase-f2b-pg15-20260728`
- `WORKFLOW_EXECUTOR_POSTGRES_IMAGE=postgres:15`
- `WORKFLOW_EXECUTOR_CLEANUP_CONTRACT=destroy_exact_runner_and_prove_port_closed`
- `WORKFLOW_EXECUTOR_AUTHORIZATION=<the exact string in section 2>`

No API key, platform credential, Provider client or Provider/network flag may
be added to this environment.

## 7. Candidate evidence required

- independently observed PostgreSQL version 15 or newer;
- migration lifecycle `043 -> 044 -> 043 -> 044`;
- eight executor tables and named tenant/fencing/evidence constraints;
- one-winner claim, monotonic fencing, stale-worker rejection and takeover;
- tenant-scoped replay, atomic rollback and single-use permit behavior;
- ordered Provider CallAudit plus hash-chained execution events;
- exactly-once cancellation acknowledgement;
- final head/table/boundary inventory before cleanup;
- exact runner removal and proof that port `55444` is closed.

## 8. Evidence ceiling and exclusions

Even if F2B later passes, the maximum result is L2 disposable PostgreSQL
candidate evidence. It does not authorize credential resolution, API-key
injection, Provider/network calls, staging, CI, Git, deployment, production,
or F3-F6.

## 9. Current gate result

- decision: `completed_for_exact_disposable_target_only`
- supported claim: revision 044 migration lifecycle and Workflow Executor
  PostgreSQL coordination contracts passed on the exact disposable target
- forbidden claim: credential, Provider, staging, production or general live
  executor readiness has been validated
- next evidence: separate Owner decision for F3 disabled runtime composition

## 10. Owner authorization recorded

The Owner supplied the section-2 authorization string verbatim on 2026-07-28.
That authority was consumed only by the exact target, local pinned image,
runner lifecycle, candidate tests and destructive cleanup contract. No image
pull, shared service/database/volume, API key, Credential, Provider/network,
CI, Git, deployment or production action was authorized or performed.

## 11. Execution and cleanup evidence

- Runtime identity: Docker server `29.4.1`; image digest
  `sha256:74e110c41804365e3915fcc09d5e7a1eff50161aaa94d5da0e58e0cd75ae509c`;
  PostgreSQL `15.18`; exact user and database matched the packet.
- Attempt 1: `2 passed / 6 errors`; six tests were setup-blocked by
  relationship-free `WorkflowRun -> StepRun` ORM flush ordering. Cleanup passed.
- Attempt 2: `2 passed / 6 errors`; explicit Step ordering exposed the preceding
  `WorkflowVersion -> WorkflowRun` ordering gap. Cleanup passed.
- Attempt 3: `2 passed / 6 errors`; all immediate foreign keys passed, then the
  deferred current-Version check rejected the incomplete Plan lifecycle.
  Cleanup passed.
- Narrow correction: the PostgreSQL-only seed fixture now flushes User,
  Workspace, Project, Plan, Version, Run, Step and Dispatch in dependency order
  and assigns the current Version before commit. Production models, migration
  and repositories were unchanged. GitNexus impact was exact LOW/0; Ruff,
  format and strict Mypy passed.
- Attempt 4: PostgreSQL candidate `8 passed in 84.71s`, including lifecycle
  `043 -> 044 -> 043 -> 044`, constraints, one-winner coordination,
  fencing/takeover, replay/rollback, audit/event chain and exactly-once cancel
  acknowledgement.
- Final in-run evidence: `final_alembic_head=202607280044`,
  `executor_table_count=8`, all eight expected table names, and
  `live_boundary_true_rows=0`.
- Final cleanup: exact runner absent, TCP port `55444` closed,
  `lifecycle_status=0`, `cleanup_status=0`.

This result is capped at L2 disposable local PostgreSQL candidate evidence.

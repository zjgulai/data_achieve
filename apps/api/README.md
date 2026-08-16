# Data Intelligence Hub API

FastAPI backend for Data Intelligence Hub.

## Commands

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn data_intelligence_hub.main:app --reload --host 0.0.0.0 --port 8000
```

Quality checks:

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

## Workflow Run action surface

The authenticated, tenant-scoped Workflow Run surface preserves the historical
`workflow_run_action_gates.v1` response and exposes the current strict
`workflow_run_action_gates.v2` discriminator.

- `POST /api/projects/{project_id}/workflow-runs/{run_id}/action-approval-receipts`
  issues an expiring Owner approval for the exact action proposal.
- `POST /api/projects/{project_id}/workflow-runs/{run_id}/actions` consumes that
  approval and returns the immutable action receipt.
- Both POST requests require a caller-generated `Idempotency-Key`. A new
  accepted write returns `201`; an exact, write-free replay returns `200`.
- Retry and resume only prepare local state, overrides keep the Run held, and
  running cancel remains unavailable without durable executor acknowledgement.

This local fixture boundary does not read platform credentials, inject API
keys, call a Provider, start an executor, or claim PostgreSQL/production
readiness.

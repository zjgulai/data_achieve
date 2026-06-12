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

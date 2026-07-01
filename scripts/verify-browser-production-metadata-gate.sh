#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> API production metadata gate targeted checks"
(
  cd apps/api
  uv run ruff check \
    src/data_intelligence_hub/schemas/automation.py \
    src/data_intelligence_hub/services/automation_service.py \
    src/data_intelligence_hub/api/routes/automation.py \
    tests/integration/test_sources_tasks.py
  uv run mypy \
    src/data_intelligence_hub/schemas/automation.py \
    src/data_intelligence_hub/services/automation_service.py \
    src/data_intelligence_hub/api/routes/automation.py
  uv run pytest \
    tests/integration/test_sources_tasks.py::test_browser_automation_plan_persists_read_only_draft \
    -q
)

echo "==> Web production metadata gate type check"
(
  cd apps/web
  corepack pnpm exec tsc --noEmit --pretty false
)

echo "Browser production metadata gate verification complete."

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = PROJECT_ROOT / "scripts/verify-ci-no-unscoped-real-e2e.py"

SAFE_WORKFLOW = """\
name: CI

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  api:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/verify-ci-no-unscoped-real-e2e.py
  web:
    runs-on: ubuntu-latest
    steps:
      - name: Next.js production API build guard
        env:
          NEXT_PUBLIC_API_URL: "https://example.invalid"
          NEXT_PUBLIC_MOCK_API: "false"
        run: pnpm -C apps/web build
"""


def run_guard(workflow: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--workflow", str(workflow)],
        check=False,
        capture_output=True,
        text=True,
    )


def write_workflow(tmp_path: Path, content: str) -> Path:
    workflow = tmp_path / "ci.yml"
    workflow.write_text(content, encoding="utf-8")
    return workflow


def test_guard_accepts_safe_workflow_and_static_production_build_url(
    tmp_path: Path,
) -> None:
    result = run_guard(write_workflow(tmp_path, SAFE_WORKFLOW))

    assert result.returncode == 0
    assert result.stdout.strip() == "ci_real_e2e_boundary_ok"
    assert result.stderr == ""


def test_repository_ci_preserves_planner_and_lineage_postgres_gates() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "verify-workflow-lineage-migration.sh" in workflow
    assert "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED" in workflow
    assert "WORKFLOW_LINEAGE_AUTHORIZED_TARGET" in workflow
    assert "verify-workflow-planner-phase2-migration.sh" in workflow
    assert "data_scrapy_workflow_plan_phase2_test" in workflow
    assert "data_scrapy_ci_workflow_lineage_test" in workflow


def test_guard_rejects_unscoped_real_e2e_job(tmp_path: Path) -> None:
    workflow = SAFE_WORKFLOW + """\
  web-real-e2e:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm -C apps/web test:e2e:real
"""

    result = run_guard(write_workflow(tmp_path, workflow))

    assert result.returncode == 1
    assert result.stdout.splitlines() == ["ci_boundary_violation:unscoped_real_e2e_job"]
    assert result.stderr == ""


def test_guard_rejects_real_api_environment_flag(tmp_path: Path) -> None:
    workflow = SAFE_WORKFLOW.replace(
        "NEXT_PUBLIC_MOCK_API: \"false\"",
        'NEXT_PUBLIC_MOCK_API: "false"\n          PLAYWRIGHT_REAL_API: "true"',
    )

    result = run_guard(write_workflow(tmp_path, workflow))

    assert result.returncode == 1
    assert result.stdout.splitlines() == ["ci_boundary_violation:real_api_environment_flag"]
    assert result.stderr == ""


def test_guard_rejects_workflow_dispatch_base_url_input(tmp_path: Path) -> None:
    workflow = SAFE_WORKFLOW.replace(
        "  workflow_dispatch:\n",
        "  workflow_dispatch:\n    inputs:\n      base_url:\n        required: false\n",
    )

    result = run_guard(write_workflow(tmp_path, workflow))

    assert result.returncode == 1
    assert result.stdout.splitlines() == ["ci_boundary_violation:dispatch_base_url_input"]
    assert result.stderr == ""


def test_guard_reports_all_detected_rules_in_stable_order(tmp_path: Path) -> None:
    workflow = SAFE_WORKFLOW.replace(
        "  workflow_dispatch:\n",
        "  workflow_dispatch:\n    inputs:\n      base_url:\n        required: false\n",
    )
    workflow += """\
  web-real-e2e:
    env:
      PLAYWRIGHT_REAL_API: "true"
"""

    result = run_guard(write_workflow(tmp_path, workflow))

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "ci_boundary_violation:dispatch_base_url_input",
        "ci_boundary_violation:real_api_environment_flag",
        "ci_boundary_violation:unscoped_real_e2e_job",
    ]
    assert result.stderr == ""


def test_guard_fails_closed_for_missing_workflow_without_echoing_path(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "secret-workflow-name.yml"

    result = run_guard(missing)

    assert result.returncode == 2
    assert result.stdout.strip() == "ci_boundary_error:workflow_unreadable"
    assert result.stderr == ""
    assert str(missing) not in result.stdout

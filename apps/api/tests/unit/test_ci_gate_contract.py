from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _job_block(workflow: str, job: str) -> str:
    """Return the raw text of one top-level job, stopping at the next job."""

    pattern = re.compile(rf"^  {re.escape(job)}:\n", re.MULTILINE)
    match = pattern.search(workflow)
    assert match is not None, f"ci.yml has no top-level job named {job!r}"
    following = re.compile(r"^  [A-Za-z0-9_-]+:\n", re.MULTILINE)
    end = following.search(workflow, match.end())
    return workflow[match.start() : end.start() if end else len(workflow)]


def _step_blocks(job_block: str) -> list[str]:
    """Split a job block into one chunk per ``- name:``/``- run:`` list item."""

    starts = [
        match.start()
        for match in re.finditer(r"^      - ", job_block, re.MULTILINE)
    ]
    return [
        job_block[start : starts[index + 1] if index + 1 < len(starts) else len(job_block)]
        for index, start in enumerate(starts)
    ]


def _step_named(job_block: str, name: str) -> str:
    matches = [
        step
        for step in _step_blocks(job_block)
        if re.search(rf"^      - name: {re.escape(name)}$", step, re.MULTILINE)
    ]
    assert len(matches) == 1, f"expected exactly one step named {name!r}, found {len(matches)}"
    return matches[0]


def _normalized(step: str) -> str:
    return " ".join(step.split())


def test_api_job_file_integrity_runs_from_repository_root() -> None:
    step = _step_named(_job_block(_workflow_text(), "api"), "Check file integrity")

    assert re.search(r"^        working-directory: \.$", step, re.MULTILINE) is not None
    assert "python3 scripts/check_file_integrity.py" in step


def test_api_job_pytest_is_scoped_to_unit_tests() -> None:
    step = _step_named(_job_block(_workflow_text(), "api"), "Pytest")

    assert _normalized(step).endswith("run: uv run pytest tests/unit")


def test_api_job_pytest_regression_guard_is_scoped_to_unit_tests() -> None:
    step = _step_named(
        _job_block(_workflow_text(), "api"),
        "Pytest regression guard (unit scope)",
    )

    assert (
        "uv run python ../../scripts/check_pytest_baseline.py --path tests/unit"
        in _normalized(step)
    )


def test_api_job_mypy_step_uses_the_multiset_baseline_gate() -> None:
    step = _step_named(_job_block(_workflow_text(), "api"), "Mypy (non-regression)")

    assert (
        "uv run python ../../scripts/check_mypy_baseline.py "
        "--baseline ../../configs/quality/mypy-src-tests-signatures.txt "
        "--path src --path tests"
    ) in _normalized(step)


def test_api_job_has_no_second_unbaselined_mypy_step() -> None:
    job_block = _job_block(_workflow_text(), "api")

    assert "uv run mypy" not in job_block
    for step in _step_blocks(job_block):
        assert not re.search(r"^      - name: Mypy$", step, re.MULTILINE), step


def test_platform_packages_job_runs_no_integration_tests() -> None:
    job_block = _job_block(_workflow_text(), "platform-packages")

    assert "tests/integration/" not in job_block
    assert "tests/integration/test_platform_package_routes.py" not in job_block

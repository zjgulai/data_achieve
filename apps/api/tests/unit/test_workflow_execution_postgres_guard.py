from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[4] / "scripts" / "verify-workflow-execution-migration.sh"
POSTGRES_TEST_ROOT = Path(__file__).parents[1] / "postgres_workflow_execution"
POSTGRES_TEST_FILES = {
    "conftest.py",
    "test_migration.py",
    "test_constraints.py",
    "test_concurrency.py",
}
SAFE_URL = "postgresql+asyncpg://user:secret@127.0.0.1:55367/local_workflow_execution_test"
SAFE_TARGET = "127.0.0.1:55367/local_workflow_execution_test"


def _run_guard(
    *,
    authorized: str | None,
    database_url: str | None,
    authorized_target: str | None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for key in (
        "WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED",
        "WORKFLOW_EXECUTION_TEST_DATABASE_URL",
        "WORKFLOW_EXECUTION_AUTHORIZED_TARGET",
    ):
        environment.pop(key, None)
    if authorized is not None:
        environment["WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED"] = authorized
    if database_url is not None:
        environment["WORKFLOW_EXECUTION_TEST_DATABASE_URL"] = database_url
    if authorized_target is not None:
        environment["WORKFLOW_EXECUTION_AUTHORIZED_TARGET"] = authorized_target
    return subprocess.run(
        ["bash", str(SCRIPT), "--check-only"],
        cwd=SCRIPT.parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_secret_safe(result: subprocess.CompletedProcess[str]) -> None:
    assert SAFE_URL not in result.stdout
    assert SAFE_URL not in result.stderr
    assert "secret" not in result.stdout
    assert "secret" not in result.stderr


def test_guard_source_exists_and_requires_three_independent_inputs() -> None:
    assert SCRIPT.is_file()
    assert POSTGRES_TEST_ROOT.is_dir()
    assert {path.name for path in POSTGRES_TEST_ROOT.iterdir() if path.is_file()} == (
        POSTGRES_TEST_FILES
    )
    missing_auth = _run_guard(
        authorized=None,
        database_url=SAFE_URL,
        authorized_target=SAFE_TARGET,
    )
    missing_url = _run_guard(
        authorized="true",
        database_url=None,
        authorized_target=SAFE_TARGET,
    )
    missing_target = _run_guard(
        authorized="true",
        database_url=SAFE_URL,
        authorized_target=None,
    )

    assert missing_auth.returncode == 2
    assert "WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED=true is required" in (missing_auth.stderr)
    assert missing_url.returncode == 2
    assert "WORKFLOW_EXECUTION_TEST_DATABASE_URL is required" in missing_url.stderr
    assert missing_target.returncode == 2
    assert "WORKFLOW_EXECUTION_AUTHORIZED_TARGET is required" in missing_target.stderr
    for result in (missing_auth, missing_url, missing_target):
        _assert_secret_safe(result)


def test_guard_rejects_remote_suffix_query_encoding_and_target_mismatch() -> None:
    unsafe_pairs = [
        (
            "postgresql+asyncpg://user:secret@example.com/db_workflow_execution_test",
            "example.com:55367/db_workflow_execution_test",
        ),
        (
            "postgresql+asyncpg://user:secret@127.0.0.1:55367/not_disposable",
            "127.0.0.1:55367/not_disposable",
        ),
        (f"{SAFE_URL}?ssl=require", SAFE_TARGET),
        (
            "postgresql+asyncpg://user:secret@127.0.0.1:55367/db%5fworkflow_execution_test",
            "127.0.0.1:55367/db_workflow_execution_test",
        ),
        (SAFE_URL, "127.0.0.1:55368/local_workflow_execution_test"),
    ]

    for database_url, authorized_target in unsafe_pairs:
        result = _run_guard(
            authorized="true",
            database_url=database_url,
            authorized_target=authorized_target,
        )
        assert result.returncode == 2
        _assert_secret_safe(result)


def test_guard_check_only_accepts_exact_local_disposable_boundary() -> None:
    result = _run_guard(
        authorized="true",
        database_url=SAFE_URL,
        authorized_target=SAFE_TARGET,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == (
        "migration guard passed: exact local disposable workflow execution PostgreSQL database"
    )
    assert result.stderr == ""
    _assert_secret_safe(result)


def test_guard_runs_against_current_alembic_head() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "^202607170034 \\(head\\)$" in source
    assert "expected exactly one Alembic head at 202607170034" in source

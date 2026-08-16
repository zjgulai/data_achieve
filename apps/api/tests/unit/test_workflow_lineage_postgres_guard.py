from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[4] / "scripts" / "verify-workflow-lineage-migration.sh"
POSTGRES_TEST_ROOT = Path(__file__).parents[1] / "postgres_workflow_lineage"
POSTGRES_TEST_FILES = {
    "conftest.py",
    "test_constraints.py",
    "test_materialization.py",
    "test_migration.py",
}
SAFE_URL = "postgresql+asyncpg://user:secret@127.0.0.1:55367/local_workflow_lineage_test"
SAFE_TARGET = "127.0.0.1:55367/local_workflow_lineage_test"


def _run_guard(
    *,
    authorized: str | None,
    database_url: str | None,
    authorized_target: str | None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    for key in (
        "DATABASE_URL",
        "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED",
        "WORKFLOW_LINEAGE_TEST_DATABASE_URL",
        "WORKFLOW_LINEAGE_AUTHORIZED_TARGET",
        "WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED",
        "WORKFLOW_EXECUTION_TEST_DATABASE_URL",
        "WORKFLOW_EXECUTION_AUTHORIZED_TARGET",
    ):
        environment.pop(key, None)
    if authorized is not None:
        environment["WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED"] = authorized
    if database_url is not None:
        environment["WORKFLOW_LINEAGE_TEST_DATABASE_URL"] = database_url
    if authorized_target is not None:
        environment["WORKFLOW_LINEAGE_AUTHORIZED_TARGET"] = authorized_target
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
    assert "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED=true is required" in (missing_auth.stderr)
    assert missing_url.returncode == 2
    assert "WORKFLOW_LINEAGE_TEST_DATABASE_URL is required" in missing_url.stderr
    assert missing_target.returncode == 2
    assert "WORKFLOW_LINEAGE_AUTHORIZED_TARGET is required" in missing_target.stderr
    for result in (missing_auth, missing_url, missing_target):
        _assert_secret_safe(result)


def test_guard_rejects_old_authorization_remote_suffix_query_encoding_and_mismatch() -> None:
    old_environment = os.environ.copy()
    for key in (
        "DATABASE_URL",
        "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED",
        "WORKFLOW_LINEAGE_TEST_DATABASE_URL",
        "WORKFLOW_LINEAGE_AUTHORIZED_TARGET",
    ):
        old_environment.pop(key, None)
    old_environment.update(
        {
            "WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED": "true",
            "WORKFLOW_EXECUTION_TEST_DATABASE_URL": SAFE_URL,
            "WORKFLOW_EXECUTION_AUTHORIZED_TARGET": SAFE_TARGET,
        }
    )
    old_only = subprocess.run(
        ["bash", str(SCRIPT), "--check-only"],
        cwd=SCRIPT.parents[1],
        env=old_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert old_only.returncode == 2
    assert "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED=true is required" in old_only.stderr
    _assert_secret_safe(old_only)

    unsafe_pairs = [
        (
            "postgresql+asyncpg://user:secret@127.0.0.1/db_workflow_lineage_test",
            "127.0.0.1:5432/db_workflow_lineage_test",
        ),
        (
            "postgresql://user:secret@127.0.0.1:55367/db_workflow_lineage_test",
            "127.0.0.1:55367/db_workflow_lineage_test",
        ),
        (
            "postgresql+asyncpg://user:secret@example.com:55367/db_workflow_lineage_test",
            "example.com:55367/db_workflow_lineage_test",
        ),
        (
            "postgresql+asyncpg://user:secret@127.0.0.1:55367/not_disposable",
            "127.0.0.1:55367/not_disposable",
        ),
        (f"{SAFE_URL}?ssl=require", SAFE_TARGET),
        (f"{SAFE_URL}#unsafe", SAFE_TARGET),
        (
            "postgresql+asyncpg://user:secret@127.0.0.1:55367/db%5fworkflow_lineage_test",
            "127.0.0.1:55367/db_workflow_lineage_test",
        ),
        (SAFE_URL, "127.0.0.1:55368/local_workflow_lineage_test"),
    ]

    for database_url, authorized_target in unsafe_pairs:
        result = _run_guard(
            authorized="true",
            database_url=database_url,
            authorized_target=authorized_target,
        )
        assert result.returncode == 2
        _assert_secret_safe(result)


def test_guard_check_only_accepts_exact_local_target_without_connecting() -> None:
    result = _run_guard(
        authorized="true",
        database_url=SAFE_URL,
        authorized_target=SAFE_TARGET,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == (
        "migration guard passed: exact local disposable workflow lineage PostgreSQL database"
    )
    assert result.stderr == ""
    _assert_secret_safe(result)


def _run_guard_with_fake_uv(
    tmp_path: Path,
    *,
    pytest_status: int,
    cleanup_status: int,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_path = tmp_path / "uv.log"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
case "$*" in
  "run alembic heads")
    printf '%s\\n' "202607170034 (head)"
    ;;
  "run pytest tests/postgres_workflow_lineage -q")
    exit "$FAKE_PYTEST_STATUS"
    ;;
  "run python -")
    cat >/dev/null
    ;;
  "run alembic upgrade 202607170034")
    exit "$FAKE_CLEANUP_STATUS"
    ;;
  *)
    exit 91
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    environment = os.environ.copy()
    for key in (
        "DATABASE_URL",
        "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED",
        "WORKFLOW_LINEAGE_TEST_DATABASE_URL",
        "WORKFLOW_LINEAGE_AUTHORIZED_TARGET",
    ):
        environment.pop(key, None)
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED": "true",
            "WORKFLOW_LINEAGE_TEST_DATABASE_URL": SAFE_URL,
            "WORKFLOW_LINEAGE_AUTHORIZED_TARGET": SAFE_TARGET,
            "FAKE_UV_LOG": str(log_path),
            "FAKE_PYTEST_STATUS": str(pytest_status),
            "FAKE_CLEANUP_STATUS": str(cleanup_status),
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return result, log_path.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize(
    ("pytest_status", "cleanup_status", "expected_status"),
    [(0, 0, 0), (7, 0, 7), (0, 9, 1)],
)
def test_guard_cleanup_runs_after_success_or_failure_and_preserves_exit_status(
    tmp_path: Path,
    pytest_status: int,
    cleanup_status: int,
    expected_status: int,
) -> None:
    result, commands = _run_guard_with_fake_uv(
        tmp_path,
        pytest_status=pytest_status,
        cleanup_status=cleanup_status,
    )

    assert result.returncode == expected_status
    assert commands[:2] == [
        "run alembic heads",
        "run pytest tests/postgres_workflow_lineage -q",
    ]
    assert commands[2:4] == [
        "run python -",
        "run alembic upgrade 202607170034",
    ]
    if cleanup_status == 0:
        assert commands[4:] == ["run python -"]
    else:
        assert commands[4:] == []
    _assert_secret_safe(result)

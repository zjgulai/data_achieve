from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[4] / "scripts" / "verify-workflow-executor-migration.sh"
POSTGRES_TEST_ROOT = Path(__file__).parents[1] / "postgres_workflow_executor"
AUTHORIZATION_PACKET = (
    Path(__file__).parents[4]
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-07-28-uix-09-phase-f2b-postgresql-authorization-packet.md"
)
EXPECTED_FILES = {
    "conftest.py",
    "test_constraints.py",
    "test_coordination.py",
    "test_evidence.py",
    "test_migration.py",
}
SAFE_URL = "postgresql+asyncpg://f2a_guard@127.0.0.1:65534/f2a_guard_fixture_workflow_executor_test"
SAFE_TARGET = "127.0.0.1:65534/f2a_guard_fixture_workflow_executor_test"
SAFE_RUNNER = "f2a-guard-fixture-never-started"
SAFE_IMAGE = "postgres:15"
SAFE_CLEANUP = "destroy_exact_runner_and_prove_port_closed"
SAFE_AUTHORIZATION = (
    "authorize-workflow-executor-postgres-candidate:"
    f"{SAFE_TARGET}:revision-202607280044:runner-{SAFE_RUNNER}:"
    f"image-{SAFE_IMAGE}:cleanup-{SAFE_CLEANUP}"
)

GUARD_KEYS = (
    "DATABASE_URL",
    "WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED",
    "WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED",
    "WORKFLOW_EXECUTOR_TEST_DATABASE_URL",
    "WORKFLOW_EXECUTOR_AUTHORIZED_TARGET",
    "WORKFLOW_EXECUTOR_RUNNER_ID",
    "WORKFLOW_EXECUTOR_POSTGRES_IMAGE",
    "WORKFLOW_EXECUTOR_CLEANUP_CONTRACT",
    "WORKFLOW_EXECUTOR_AUTHORIZATION",
)


def _environment(**overrides: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    for key in GUARD_KEYS:
        environment.pop(key, None)
    values: dict[str, str | None] = {
        "WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED": "true",
        "WORKFLOW_EXECUTOR_TEST_DATABASE_URL": SAFE_URL,
        "WORKFLOW_EXECUTOR_AUTHORIZED_TARGET": SAFE_TARGET,
        "WORKFLOW_EXECUTOR_RUNNER_ID": SAFE_RUNNER,
        "WORKFLOW_EXECUTOR_POSTGRES_IMAGE": SAFE_IMAGE,
        "WORKFLOW_EXECUTOR_CLEANUP_CONTRACT": SAFE_CLEANUP,
        "WORKFLOW_EXECUTOR_AUTHORIZATION": SAFE_AUTHORIZATION,
    }
    values.update(overrides)
    for key, value in values.items():
        if value is not None:
            environment[key] = value
    return environment


def _run_guard(
    *,
    check_only: bool = True,
    **overrides: str | None,
) -> subprocess.CompletedProcess[str]:
    command = ["bash", str(SCRIPT)]
    if check_only:
        command.append("--check-only")
    return subprocess.run(
        command,
        cwd=SCRIPT.parents[1],
        env=_environment(**overrides),
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_secret_safe(result: subprocess.CompletedProcess[str]) -> None:
    assert SAFE_URL not in result.stdout
    assert SAFE_URL not in result.stderr
    assert "secret" not in result.stdout.lower()
    assert "secret" not in result.stderr.lower()


def test_guard_source_and_candidate_suite_exist() -> None:
    assert SCRIPT.is_file()
    assert POSTGRES_TEST_ROOT.is_dir()
    assert {path.name for path in POSTGRES_TEST_ROOT.iterdir() if path.is_file()} == (
        EXPECTED_FILES
    )


def test_guard_requires_every_independent_authority_input() -> None:
    expected_errors = {
        "WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED": (
            "WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED=true is required"
        ),
        "WORKFLOW_EXECUTOR_TEST_DATABASE_URL": ("WORKFLOW_EXECUTOR_TEST_DATABASE_URL is required"),
        "WORKFLOW_EXECUTOR_AUTHORIZED_TARGET": ("WORKFLOW_EXECUTOR_AUTHORIZED_TARGET is required"),
        "WORKFLOW_EXECUTOR_RUNNER_ID": "WORKFLOW_EXECUTOR_RUNNER_ID is required",
        "WORKFLOW_EXECUTOR_POSTGRES_IMAGE": ("WORKFLOW_EXECUTOR_POSTGRES_IMAGE is required"),
        "WORKFLOW_EXECUTOR_CLEANUP_CONTRACT": ("WORKFLOW_EXECUTOR_CLEANUP_CONTRACT is required"),
        "WORKFLOW_EXECUTOR_AUTHORIZATION": ("WORKFLOW_EXECUTOR_AUTHORIZATION is required"),
    }
    for key, message in expected_errors.items():
        result = _run_guard(**{key: None})
        assert result.returncode == 2
        assert message in result.stderr
        _assert_secret_safe(result)


def test_guard_rejects_target_revision_runner_image_and_cleanup_drift() -> None:
    unsafe_overrides = (
        {
            "WORKFLOW_EXECUTOR_TEST_DATABASE_URL": SAFE_URL.replace("127.0.0.1", "db.example.test"),
        },
        {
            "WORKFLOW_EXECUTOR_TEST_DATABASE_URL": SAFE_URL.replace(
                "_workflow_executor_test", "_other_test"
            ),
        },
        {"WORKFLOW_EXECUTOR_TEST_DATABASE_URL": f"{SAFE_URL}?ssl=require"},
        {
            "WORKFLOW_EXECUTOR_TEST_DATABASE_URL": SAFE_URL.replace(
                "f2a_guard@", "f2a_guard:secret@"
            ),
        },
        {"WORKFLOW_EXECUTOR_AUTHORIZED_TARGET": SAFE_TARGET.replace("65534", "65533")},
        {"WORKFLOW_EXECUTOR_RUNNER_ID": "../unsafe-runner"},
        {"WORKFLOW_EXECUTOR_POSTGRES_IMAGE": "postgres:latest"},
        {"WORKFLOW_EXECUTOR_CLEANUP_CONTRACT": "keep_runner"},
        {
            "WORKFLOW_EXECUTOR_AUTHORIZATION": SAFE_AUTHORIZATION.replace(
                "revision-202607280044", "revision-head"
            ),
        },
    )
    for overrides in unsafe_overrides:
        result = _run_guard(**overrides)
        assert result.returncode == 2
        _assert_secret_safe(result)


def test_guard_check_only_accepts_synthetic_tuple_without_connecting() -> None:
    result = _run_guard()

    assert result.returncode == 0
    assert result.stdout.strip() == (
        "workflow executor guard passed: exact authorization tuple; connection not attempted"
    )
    assert result.stderr == ""
    _assert_secret_safe(result)


def test_runtime_mode_requires_separate_runtime_authorization() -> None:
    result = _run_guard(check_only=False)

    assert result.returncode == 2
    assert "WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED=true is required" in result.stderr
    assert "alembic" not in result.stdout.lower()
    _assert_secret_safe(result)


def test_guard_is_pinned_to_revision_044_without_runner_commands() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "^202607280044 \\(head\\)$" in source
    assert "expected exactly one Alembic head at 202607280044" in source
    assert "pytest tests/postgres_workflow_executor -q" in source
    assert "docker " not in source
    assert "podman " not in source


def test_f2b_packet_is_unbound_and_explicitly_unauthorized() -> None:
    source = AUTHORIZATION_PACKET.read_text(encoding="utf-8")

    assert "status: exact_target_completed_cleanup_verified" in source
    assert "evidence_grade: L2-disposable-local-postgresql-candidate" in source
    assert "phase_f2b_packet_preparation_authorized: true" in source
    assert "phase_f2b_authorized: true" in source
    assert "owner_authorization_present: true" in source
    assert "exact_target_selected: true" in source
    assert "connection_attempted: true" in source
    assert "image_pull_attempted: false" in source
    assert "runner_started: true" in source
    assert "migration_execution: true" in source
    assert "cleanup_verified: true" in source
    assert "8 passed in 84.71s" in source
    assert "live_boundary_true_rows=0" in source
    assert "127.0.0.1:55444/uix09_phase_f2b_20260728_workflow_executor_test" in source
    assert "data-scrapy-uix09-phase-f2b-pg15-20260728" in source
    assert "<LOOPBACK_HOST>" not in source
    assert "<DEDICATED_FREE_PORT>" not in source
    assert "127.0.0.1:55443/uix09_phase_e_20260728_workflow_execution_test" not in source

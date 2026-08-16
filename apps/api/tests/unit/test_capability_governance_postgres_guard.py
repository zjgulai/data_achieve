from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[4] / "scripts" / "verify-capability-governance-migration.sh"
SAFE_URL = "postgresql+asyncpg://user:secret@127.0.0.1:5432/local_capability_governance_test"


def _run_guard(
    *,
    authorized: str | None,
    database_url: str | None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED", None)
    environment.pop("CAPABILITY_GOVERNANCE_TEST_DATABASE_URL", None)
    if authorized is not None:
        environment["CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED"] = authorized
    if database_url is not None:
        environment["CAPABILITY_GOVERNANCE_TEST_DATABASE_URL"] = database_url
    return subprocess.run(
        ["bash", str(SCRIPT), "--check-only"],
        cwd=SCRIPT.parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_guard_requires_new_explicit_authorization_and_url() -> None:
    missing_auth = _run_guard(authorized=None, database_url=SAFE_URL)
    missing_url = _run_guard(authorized="true", database_url=None)

    assert missing_auth.returncode == 2
    assert "CAPABILITY_GOVERNANCE_POSTGRES_TEST_AUTHORIZED=true is required" in (
        missing_auth.stderr
    )
    assert missing_url.returncode == 2
    assert "CAPABILITY_GOVERNANCE_TEST_DATABASE_URL is required" in missing_url.stderr


def test_guard_rejects_remote_wrong_suffix_query_and_encoded_paths() -> None:
    unsafe_urls = [
        "postgresql+asyncpg://user:secret@example.com/db_capability_governance_test",
        "postgresql+asyncpg://user:secret@127.0.0.1:5432/not_disposable",
        f"{SAFE_URL}?ssl=require",
        "postgresql+asyncpg://user:secret@127.0.0.1:5432/db%5fcapability_governance_test",
    ]

    for database_url in unsafe_urls:
        result = _run_guard(authorized="true", database_url=database_url)
        assert result.returncode == 2
        assert database_url not in result.stdout
        assert database_url not in result.stderr
        assert "secret" not in result.stdout
        assert "secret" not in result.stderr


def test_guard_check_only_accepts_exact_local_disposable_boundary() -> None:
    result = _run_guard(authorized="true", database_url=SAFE_URL)

    assert result.returncode == 0
    assert result.stdout.strip() == (
        "migration guard passed: local disposable capability governance PostgreSQL database"
    )
    assert result.stderr == ""
    assert SAFE_URL not in result.stdout
    assert "secret" not in result.stdout


def test_guard_runs_against_current_alembic_head() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "^202607170034 \\(head\\)$" in source
    assert "expected exactly one Alembic head at 202607170034" in source

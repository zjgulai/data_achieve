from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = PROJECT_ROOT / "apps" / "api"
SCRIPTS = PROJECT_ROOT / "scripts"

# Pinned in the test on purpose: a change of head must edit this file.
CURRENT_HEAD = "202610210057"

VERIFY_SCRIPTS = (
    "verify-capability-governance-migration.sh",
    "verify-workflow-action-migration.sh",
    "verify-workflow-execution-migration.sh",
    "verify-workflow-executor-migration.sh",
    "verify-workflow-lineage-migration.sh",
    "verify-workflow-planner-phase2-migration.sh",
)

DEDICATED_SUITES = (
    ("tests/postgres/test_workflow_plan_migration.py", "assert _database_revision"),
    ("tests/postgres_workflow_lineage/test_migration.py", "assert _revision"),
    ("tests/postgres_capability_governance/test_migration.py", "assert _database_revision"),
    ("tests/postgres_workflow_execution/test_migration.py", "assert _revision"),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _alembic_head() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one Alembic head, got {lines!r}"
    assert lines[0] == f"{CURRENT_HEAD} (head)", lines[0]
    return CURRENT_HEAD


def test_the_live_alembic_head_matches_the_pinned_constant() -> None:
    assert _alembic_head() == CURRENT_HEAD


def test_every_named_verify_script_pins_the_current_head() -> None:
    sources = {name: _read(SCRIPTS / name) for name in VERIFY_SCRIPTS}

    for name, source in sources.items():
        assert f"'^{CURRENT_HEAD} \\(head\\)$'" in source, name
        assert (
            f'"error: expected exactly one Alembic head at {CURRENT_HEAD}"' in source
        ), name


def test_every_named_verify_script_announces_the_current_head_on_success() -> None:
    for name in VERIFY_SCRIPTS:
        source = _read(SCRIPTS / name)
        assert f"head check passed: {CURRENT_HEAD}" in source, name


def test_no_verify_script_still_pins_a_superseded_head() -> None:
    stale = (
        "202607160033",
        "202607170034",
        "202607270043",
        "202607280044",
    )

    for name in VERIFY_SCRIPTS:
        source = _read(SCRIPTS / name)
        for revision in stale:
            assert f"'^{revision} \\(head\\)$'" not in source, f"{name} pins head {revision}"
            assert (
                f'"error: expected exactly one Alembic head at {revision}"' not in source
            ), f"{name} still pins head {revision}"


def test_lineage_cleanup_upgrades_to_and_reports_the_current_head() -> None:
    source = _read(SCRIPTS / "verify-workflow-lineage-migration.sh")

    assert f"uv run alembic upgrade {CURRENT_HEAD} &&" in source
    assert f'if revision != "{CURRENT_HEAD}" or any(counts.values()):' in source
    assert (
        f'"authorized workflow lineage database cleanup passed: '
        f'head {CURRENT_HEAD}, zero rows"' in source
    )


def test_lineage_cleanup_keeps_no_historical_head_reference() -> None:
    source = _read(SCRIPTS / "verify-workflow-lineage-migration.sh")
    cleanup_start = source.index("cleanup_authorized_target() {")
    cleanup_end = source.index("cleanup_complete=false")
    cleanup = source[cleanup_start:cleanup_end]

    for revision in ("202607160033", "202607170034", "202607270043", "202607280044"):
        assert revision not in cleanup, f"cleanup still references {revision}"


def test_executor_head_pin_is_decoupled_from_the_authorization_candidate_label() -> None:
    source = _read(SCRIPTS / "verify-workflow-executor-migration.sh")

    assert f"'^{CURRENT_HEAD} \\(head\\)$'" in source
    assert f'"error: expected exactly one Alembic head at {CURRENT_HEAD}"' in source
    # The candidate label builds `revision-<REVISION>`, which the suite's
    # conftest hardcodes. It is not a head pin and must not track the head.
    assert 'REVISION = "202607280044"' in source


def test_each_dedicated_suite_pins_the_current_head_pair() -> None:
    for relative, companion in DEDICATED_SUITES:
        source = _read(API_ROOT / relative)
        assert f'heads == ["{CURRENT_HEAD} (head)"]' in source, relative
        assert f'{companion}(postgres_database_url) == "{CURRENT_HEAD}"' in source, relative


def test_lineage_suite_head_test_is_named_for_the_current_head() -> None:
    source = _read(API_ROOT / "tests/postgres_workflow_lineage/test_migration.py")

    assert "def test_source_has_one_head_at_current_head(" in source
    assert "def test_source_has_one_head_at_" + "034(" not in source


def test_no_tracked_or_on_disk_verify_script_backup_remains() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "scripts/*.bak"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout.strip() == ""
    assert list(SCRIPTS.glob("*.bak")) == []

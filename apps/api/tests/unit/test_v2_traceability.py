from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = PROJECT_ROOT / "scripts/verify-v2-traceability.py"

MINI_PRD = """\
# Mini PRD

| ID | Priority | Requirement | Acceptance |
|---|---|---|---|
| AAA-001 | P0 | First | First accepted |
| BATCH-001 | P1 | Second | Second accepted |

| ID | Scenario | Must prove |
|---|---|---|
| AT-01 | First | Proof |
| AT-02 | Second | Proof |

| KPI | Definition | Target |
|---|---|---|
| KPI-01 First KPI | First | 100% |
| KPI-02 Second KPI | Second | 0 |
"""

AT_02_ROW = "| AT-02 | absent | none | Batch 2 | — | implementation | local_only | 2026-07-14 |"
KPI_02_ROW = (
    "| KPI-02 | external_gate_after_implementation | none | Batch 2 | — | pilot | "
    "owner_authorization | 2026-07-14 |"
)
VALID_LEDGER = (
    "\n".join(
        [
            "# Mini Traceability",
            "",
            "## Functional Requirements",
            "",
            (
                "| requirement_id | priority | current_verdict | evidence_grade | "
                "owning_batch | code_anchor | test_anchor | remaining_gate | "
                "authorization_boundary | last_reviewed |"
            ),
            "|---|---|---|---|---|---|---|---|---|---|",
            (
                "| AAA-001 | P0 | partial | L2-local | Batch 1 | `a.py` | "
                "`test_a.py` | runtime | local_only | 2026-07-14 |"
            ),
            (
                "| BATCH-001 | P1 | absent | none | Batch 2 | — | — | "
                "implementation | local_only | 2026-07-14 |"
            ),
            "",
            "## Acceptance Scenarios",
            "",
            (
                "| acceptance_id | current_verdict | evidence_grade | owning_batch | "
                "evidence_anchor | remaining_gate | authorization_boundary | last_reviewed |"
            ),
            "|---|---|---|---|---|---|---|---|",
            (
                "| AT-01 | partial | L2-local | Batch 1 | `test_a.py` | runtime | "
                "local_only | 2026-07-14 |"
            ),
            AT_02_ROW,
            "",
            "## KPI",
            "",
            (
                "| kpi_id | current_verdict | evidence_grade | owning_batch | "
                "evidence_anchor | remaining_gate | authorization_boundary | last_reviewed |"
            ),
            "|---|---|---|---|---|---|---|---|",
            (
                "| KPI-01 | partial | L2-local | Batch 1 | `test_a.py` | pilot | "
                "local_only | 2026-07-14 |"
            ),
            KPI_02_ROW,
        ]
    )
    + "\n"
)


def run_verifier(
    prd: Path,
    ledger: Path,
    *,
    requirement_count: int = 2,
    acceptance_count: int = 2,
    kpi_count: int = 2,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--prd",
            str(prd),
            "--ledger",
            str(ledger),
            "--expected-requirements",
            str(requirement_count),
            "--expected-acceptance",
            str(acceptance_count),
            "--expected-kpis",
            str(kpi_count),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def write_inputs(tmp_path: Path, ledger_text: str) -> tuple[Path, Path]:
    prd = tmp_path / "prd.md"
    ledger = tmp_path / "ledger.md"
    prd.write_text(MINI_PRD, encoding="utf-8")
    ledger.write_text(ledger_text, encoding="utf-8")
    return prd, ledger


def test_verifier_accepts_exact_requirement_acceptance_and_kpi_mapping(
    tmp_path: Path,
) -> None:
    prd, ledger = write_inputs(tmp_path, VALID_LEDGER)

    result = run_verifier(prd, ledger)

    assert result.returncode == 0
    assert result.stdout.strip() == (
        "v2_traceability_ok requirements=2 acceptance=2 kpis=2"
    )
    assert result.stderr == ""


def test_verifier_rejects_missing_and_duplicate_requirement_ids(
    tmp_path: Path,
) -> None:
    invalid = VALID_LEDGER.replace(
        "| BATCH-001 | P1 | absent |",
        "| AAA-001 | P1 | absent |",
    )
    prd, ledger = write_inputs(tmp_path, invalid)

    result = run_verifier(prd, ledger)

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "v2_traceability_violation:duplicate_requirement_id",
        "v2_traceability_violation:priority_mismatch",
        "v2_traceability_violation:requirement_set_mismatch",
    ]
    assert result.stderr == ""


def test_verifier_rejects_missing_required_functional_column(tmp_path: Path) -> None:
    invalid = VALID_LEDGER.replace("| test_anchor ", "| ")
    prd, ledger = write_inputs(tmp_path, invalid)

    result = run_verifier(prd, ledger)

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "v2_traceability_violation:functional_columns_missing"
    ]


def test_verifier_rejects_invalid_verdict(tmp_path: Path) -> None:
    invalid = VALID_LEDGER.replace("| AAA-001 | P0 | partial |", "| AAA-001 | P0 | done |")
    prd, ledger = write_inputs(tmp_path, invalid)

    result = run_verifier(prd, ledger)

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "v2_traceability_violation:invalid_current_verdict"
    ]


def test_verifier_rejects_missing_acceptance_and_kpi_ids(tmp_path: Path) -> None:
    invalid = VALID_LEDGER.replace(f"{AT_02_ROW}\n", "").replace(
        f"{KPI_02_ROW}\n",
        "",
    )
    prd, ledger = write_inputs(tmp_path, invalid)

    result = run_verifier(prd, ledger)

    assert result.returncode == 1
    assert result.stdout.splitlines() == [
        "v2_traceability_violation:acceptance_count_mismatch",
        "v2_traceability_violation:acceptance_set_mismatch",
        "v2_traceability_violation:kpi_count_mismatch",
        "v2_traceability_violation:kpi_set_mismatch",
    ]


def test_repository_v2_traceability_ledger_is_complete() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout or result.stderr
    assert result.stdout.strip() == (
        "v2_traceability_ok requirements=92 acceptance=10 kpis=12"
    )
    assert result.stderr == ""

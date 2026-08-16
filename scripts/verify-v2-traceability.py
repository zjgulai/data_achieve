#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import cast

DEFAULT_PRD = Path("docs/product/product-prd-social-media-automation-platform-v2.md")
DEFAULT_LEDGER = Path(
    "docs/product/product-prd-social-media-automation-platform-v2-traceability.md"
)

REQUIREMENT_ROW = re.compile(r"^\|\s*([A-Z]{2,5}-\d{3})\s*\|\s*(P[012])\s*\|", re.MULTILINE)
ACCEPTANCE_ROW = re.compile(r"^\|\s*(AT-\d{2})\s*\|", re.MULTILINE)
KPI_ROW = re.compile(r"^\|\s*(KPI-\d{2})(?:\s+[^|]+)?\s*\|", re.MULTILINE)
REQUIREMENT_ID = re.compile(r"^[A-Z]{2,5}-\d{3}$")
ACCEPTANCE_ID = re.compile(r"^AT-\d{2}$")
KPI_ID = re.compile(r"^KPI-\d{2}$")

FUNCTIONAL_COLUMNS = {
    "requirement_id",
    "priority",
    "current_verdict",
    "evidence_grade",
    "owning_batch",
    "code_anchor",
    "test_anchor",
    "remaining_gate",
    "authorization_boundary",
    "last_reviewed",
}
ACCEPTANCE_COLUMNS = {
    "acceptance_id",
    "current_verdict",
    "evidence_grade",
    "owning_batch",
    "evidence_anchor",
    "remaining_gate",
    "authorization_boundary",
    "last_reviewed",
}
KPI_COLUMNS = {
    "kpi_id",
    "current_verdict",
    "evidence_grade",
    "owning_batch",
    "evidence_anchor",
    "remaining_gate",
    "authorization_boundary",
    "last_reviewed",
}
ALLOWED_VERDICTS = {
    "implemented_local",
    "partial",
    "fixture_only",
    "absent",
    "external_gate_after_implementation",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify V2 PRD traceability coverage.")
    parser.add_argument("--prd", default=str(DEFAULT_PRD))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--expected-requirements", type=int, default=92)
    parser.add_argument("--expected-acceptance", type=int, default=10)
    parser.add_argument("--expected-kpis", type=int, default=12)
    return parser.parse_args(argv)


def markdown_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        rows.append([cell.strip() for cell in line[1:-1].split("|")])
    return rows


def find_header(rows: list[list[str]], first_column: str) -> list[str] | None:
    for row in rows:
        if row and row[0] == first_column:
            return row
    return None


def rows_with_id(
    rows: list[list[str]],
    pattern: re.Pattern[str],
) -> list[list[str]]:
    return [row for row in rows if row and pattern.fullmatch(row[0]) is not None]


def duplicate_ids(rows: list[list[str]]) -> bool:
    counts = Counter(row[0] for row in rows)
    return any(count > 1 for count in counts.values())


def validate_row_shape_and_verdicts(
    header: list[str] | None,
    rows: list[list[str]],
    *,
    shape_code: str,
    violations: set[str],
) -> None:
    if header is None or "current_verdict" not in header:
        return
    verdict_index = header.index("current_verdict")
    for row in rows:
        if len(row) != len(header):
            violations.add(shape_code)
            continue
        if row[verdict_index] not in ALLOWED_VERDICTS:
            violations.add("invalid_current_verdict")


def validate_traceability(
    prd_text: str,
    ledger_text: str,
    *,
    expected_requirements: int,
    expected_acceptance: int,
    expected_kpis: int,
) -> tuple[list[str], tuple[int, int, int]]:
    violations: set[str] = set()
    prd_requirement_pairs = REQUIREMENT_ROW.findall(prd_text)
    prd_requirement_ids = [requirement_id for requirement_id, _ in prd_requirement_pairs]
    prd_priorities = dict(prd_requirement_pairs)
    prd_acceptance_ids = ACCEPTANCE_ROW.findall(prd_text)
    prd_kpi_ids = KPI_ROW.findall(prd_text)

    if len(prd_requirement_ids) != expected_requirements:
        violations.add("prd_requirement_count_mismatch")
    if len(set(prd_requirement_ids)) != len(prd_requirement_ids):
        violations.add("prd_duplicate_requirement_id")
    if len(prd_acceptance_ids) != expected_acceptance:
        violations.add("prd_acceptance_count_mismatch")
    if len(set(prd_acceptance_ids)) != len(prd_acceptance_ids):
        violations.add("prd_duplicate_acceptance_id")
    if len(prd_kpi_ids) != expected_kpis:
        violations.add("prd_kpi_count_mismatch")
    if len(set(prd_kpi_ids)) != len(prd_kpi_ids):
        violations.add("prd_duplicate_kpi_id")

    ledger_rows = markdown_rows(ledger_text)
    functional_header = find_header(ledger_rows, "requirement_id")
    acceptance_header = find_header(ledger_rows, "acceptance_id")
    kpi_header = find_header(ledger_rows, "kpi_id")

    if functional_header is None or not FUNCTIONAL_COLUMNS.issubset(functional_header):
        violations.add("functional_columns_missing")
    if acceptance_header is None or not ACCEPTANCE_COLUMNS.issubset(acceptance_header):
        violations.add("acceptance_columns_missing")
    if kpi_header is None or not KPI_COLUMNS.issubset(kpi_header):
        violations.add("kpi_columns_missing")

    functional_rows = rows_with_id(ledger_rows, REQUIREMENT_ID)
    acceptance_rows = rows_with_id(ledger_rows, ACCEPTANCE_ID)
    kpi_rows = rows_with_id(ledger_rows, KPI_ID)

    if duplicate_ids(functional_rows):
        violations.add("duplicate_requirement_id")
    if duplicate_ids(acceptance_rows):
        violations.add("duplicate_acceptance_id")
    if duplicate_ids(kpi_rows):
        violations.add("duplicate_kpi_id")

    ledger_requirement_ids = [row[0] for row in functional_rows]
    ledger_acceptance_ids = [row[0] for row in acceptance_rows]
    ledger_kpi_ids = [row[0] for row in kpi_rows]

    if len(ledger_requirement_ids) != expected_requirements:
        violations.add("requirement_count_mismatch")
    if set(ledger_requirement_ids) != set(prd_requirement_ids):
        violations.add("requirement_set_mismatch")
    if len(ledger_acceptance_ids) != expected_acceptance:
        violations.add("acceptance_count_mismatch")
    if set(ledger_acceptance_ids) != set(prd_acceptance_ids):
        violations.add("acceptance_set_mismatch")
    if len(ledger_kpi_ids) != expected_kpis:
        violations.add("kpi_count_mismatch")
    if set(ledger_kpi_ids) != set(prd_kpi_ids):
        violations.add("kpi_set_mismatch")

    if functional_header is not None and "priority" in functional_header:
        priority_index = functional_header.index("priority")
        for row in functional_rows:
            if (
                len(row) == len(functional_header)
                and row[priority_index] != prd_priorities.get(row[0])
            ):
                violations.add("priority_mismatch")

    validate_row_shape_and_verdicts(
        functional_header,
        functional_rows,
        shape_code="malformed_functional_row",
        violations=violations,
    )
    validate_row_shape_and_verdicts(
        acceptance_header,
        acceptance_rows,
        shape_code="malformed_acceptance_row",
        violations=violations,
    )
    validate_row_shape_and_verdicts(
        kpi_header,
        kpi_rows,
        shape_code="malformed_kpi_row",
        violations=violations,
    )

    return sorted(violations), (
        len(ledger_requirement_ids),
        len(ledger_acceptance_ids),
        len(ledger_kpi_ids),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    prd_path = Path(cast(str, args.prd))
    ledger_path = Path(cast(str, args.ledger))
    try:
        prd_text = prd_path.read_text(encoding="utf-8")
        ledger_text = ledger_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("v2_traceability_error:input_unreadable")
        return 2

    violations, counts = validate_traceability(
        prd_text,
        ledger_text,
        expected_requirements=cast(int, args.expected_requirements),
        expected_acceptance=cast(int, args.expected_acceptance),
        expected_kpis=cast(int, args.expected_kpis),
    )
    if violations:
        for violation in violations:
            print(f"v2_traceability_violation:{violation}")
        return 1

    requirement_count, acceptance_count, kpi_count = counts
    print(
        "v2_traceability_ok "
        f"requirements={requirement_count} "
        f"acceptance={acceptance_count} "
        f"kpis={kpi_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

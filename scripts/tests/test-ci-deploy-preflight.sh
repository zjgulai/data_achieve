#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CI_WORKFLOW_PATH="${CI_WORKFLOW_PATH:-$REPO_ROOT/.github/workflows/ci.yml}"

python3 - "$CI_WORKFLOW_PATH" <<'PY'
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

workflow_path = Path(sys.argv[1])
try:
    workflow_text = workflow_path.read_text(encoding="utf-8")
except (OSError, UnicodeError) as exc:
    print(f"FAIL  cannot read CI workflow: {exc}")
    raise SystemExit(1) from exc

lines = workflow_text.splitlines()
failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)
    print(f"FAIL  {message}")


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def is_ignored(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def find_top_level_block(name: str) -> tuple[int, int] | None:
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(rf"{re.escape(name)}\s*:\s*", line)
        ),
        None,
    )
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not is_ignored(line) and indentation(line) == 0:
            end = index
            break
    return start, end


def assert_unfiltered_trigger(trigger: str) -> None:
    on_block = find_top_level_block("on")
    if on_block is None:
        fail("CI workflow is missing the top-level on trigger block")
        return

    start, end = on_block
    trigger_match: tuple[int, str] | None = None
    pattern = re.compile(rf"^  {re.escape(trigger)}\s*:\s*(.*?)\s*$")
    for index in range(start + 1, end):
        match = pattern.match(lines[index])
        if match:
            trigger_match = (index, match.group(1))
            break

    if trigger_match is None:
        fail(f"CI workflow is missing the {trigger} trigger")
        return

    trigger_index, inline_value = trigger_match
    if inline_value not in {"", "{}"}:
        fail(f"{trigger} trigger must be unfiltered; found inline configuration")
        return

    if inline_value == "{}":
        return

    for index in range(trigger_index + 1, end):
        line = lines[index]
        if is_ignored(line):
            continue
        current_indent = indentation(line)
        if current_indent <= 2:
            break
        fail(
            f"{trigger} trigger must be unfiltered; found nested configuration "
            f"on line {index + 1}"
        )
        return


@dataclass(frozen=True)
class Step:
    job: str
    index: int
    lines: tuple[str, ...]
    job_has_continue_on_error: bool

    @property
    def has_continue_on_error(self) -> bool:
        return self.job_has_continue_on_error or any(
            re.match(r"^\s*continue-on-error\s*:", line)
            for line in self.lines
            if not is_ignored(line)
        )

    def run_text(self) -> str:
        commands: list[str] = []
        for line_index, line in enumerate(self.lines):
            match = re.match(r"^(\s*)run\s*:\s*(.*?)\s*$", line)
            if not match:
                continue

            run_indent = len(match.group(1))
            value = match.group(2)
            if value in {"|", "|-", "|+", ">", ">-", ">+"}:
                for nested_line in self.lines[line_index + 1 :]:
                    if is_ignored(nested_line):
                        continue
                    if indentation(nested_line) <= run_indent:
                        break
                    commands.append(nested_line.strip())
            elif value:
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                commands.append(value.strip())
        return " ".join(commands)


def parse_steps() -> list[Step]:
    jobs_block = find_top_level_block("jobs")
    if jobs_block is None:
        fail("CI workflow is missing the top-level jobs block")
        return []

    jobs_start, jobs_end = jobs_block
    job_starts: list[tuple[int, str]] = []
    job_pattern = re.compile(r"^  ([A-Za-z0-9_-]+)\s*:\s*$")
    for index in range(jobs_start + 1, jobs_end):
        match = job_pattern.match(lines[index])
        if match:
            job_starts.append((index, match.group(1)))

    parsed_steps: list[Step] = []
    for position, (job_start, job_name) in enumerate(job_starts):
        job_end = job_starts[position + 1][0] if position + 1 < len(job_starts) else jobs_end
        steps_line = next(
            (
                index
                for index in range(job_start + 1, job_end)
                if re.match(r"^    steps\s*:\s*$", lines[index])
            ),
            None,
        )
        if steps_line is None:
            continue

        job_has_continue_on_error = any(
            re.match(r"^    continue-on-error\s*:", lines[index])
            for index in range(job_start + 1, steps_line)
            if not is_ignored(lines[index])
        )
        step_starts = [
            index
            for index in range(steps_line + 1, job_end)
            if re.match(r"^      -\s+", lines[index])
        ]
        for step_index, step_start in enumerate(step_starts):
            step_end = (
                step_starts[step_index + 1]
                if step_index + 1 < len(step_starts)
                else job_end
            )
            parsed_steps.append(
                Step(
                    job=job_name,
                    index=step_index,
                    lines=tuple(lines[step_start:step_end]),
                    job_has_continue_on_error=job_has_continue_on_error,
                )
            )
    return parsed_steps


assert_unfiltered_trigger("push")
assert_unfiltered_trigger("pull_request")
steps = parse_steps()

catalog_lock_command = "check_catalog_locks.py --json --require-generated"
if catalog_lock_command not in workflow_text:
    fail(f"CI workflow is missing SP-41 command: {catalog_lock_command}")

required_commands = (
    "bash scripts/tests/test-preflight-production.sh",
    "bash scripts/tests/test-deploy-p0-preflight.sh",
)
locations: dict[str, list[Step]] = {}
for command in required_commands:
    locations[command] = [
        step for step in steps if command in step.run_text()
    ]
    if not locations[command]:
        fail(f"CI workflow is missing required command: {command}")

if all(locations[command] for command in required_commands):
    valid_pair = any(
        not first.has_continue_on_error
        and not second.has_continue_on_error
        and first.job == second.job
        and (first.index == second.index or abs(first.index - second.index) == 1)
        for first in locations[required_commands[0]]
        for second in locations[required_commands[1]]
    )
    if not valid_pair:
        fail(
            "production preflight commands must run in one blocking step or "
            "adjacent blocking steps without continue-on-error"
        )

if failures:
    print(f"\nAssertions: {len(failures)} failed")
    raise SystemExit(1)

print("PASS  CI deploy preflight gate is blocking and complete")
PY

#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CI_WORKFLOW_PATH="${CI_WORKFLOW_PATH:-$REPO_ROOT/.github/workflows/ci.yml}"

python3 - "$CI_WORKFLOW_PATH" <<'PY'
from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

workflow_path = Path(sys.argv[1])
failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)
    print(f"FAIL  {message}")


try:
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)
except (OSError, UnicodeError, yaml.YAMLError) as exc:
    print(f"FAIL  cannot load CI workflow: {exc}")
    raise SystemExit(1) from exc

if not isinstance(workflow, Mapping):
    print("FAIL  CI workflow root must be a YAML mapping")
    raise SystemExit(1)

# PyYAML follows YAML 1.1 and resolves the unquoted key `on` as boolean true.
on_config = workflow.get("on", workflow.get(True))
if isinstance(on_config, list):
    triggers: Mapping[Any, Any] = {trigger: None for trigger in on_config}
elif isinstance(on_config, str):
    triggers = {on_config: None}
elif isinstance(on_config, Mapping):
    triggers = on_config
else:
    fail("CI workflow is missing a valid top-level on trigger block")
    triggers = {}


def assert_unfiltered_trigger(trigger: str) -> None:
    if trigger not in triggers:
        fail(f"CI workflow is missing the {trigger} trigger")
        return

    config = triggers[trigger]
    if config is None:
        return
    if not isinstance(config, Mapping):
        fail(f"{trigger} trigger must be unfiltered; found invalid configuration")
        return

    branches = config.get("branches")
    if branches not in (None, {}, [], ""):
        fail(f"{trigger} trigger must not have a branches filter")


assert_unfiltered_trigger("push")
assert_unfiltered_trigger("pull_request")

jobs = workflow.get("jobs")
if not isinstance(jobs, Mapping):
    fail("CI workflow is missing a valid top-level jobs block")
    jobs = {}


def run_script(step: Any) -> str:
    if not isinstance(step, Mapping):
        return ""
    run = step.get("run")
    return run if isinstance(run, str) else ""


def normalized_expression(value: str) -> str:
    expression = value.strip().lower()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2].strip()
    return expression


def continue_on_error_can_be_true(container: Mapping[Any, Any]) -> bool:
    if "continue-on-error" not in container:
        return False
    value = container["continue-on-error"]
    if value is False or value is None:
        return False
    if isinstance(value, str) and normalized_expression(value) == "false":
        return False
    return True


def has_disabling_condition(step: Mapping[Any, Any]) -> bool:
    if "if" not in step:
        return False
    condition = step["if"]
    if condition is True:
        return False
    if not isinstance(condition, str):
        return True
    return normalized_expression(condition) not in {"true", "always()", "success()"}


all_steps: list[tuple[str, Mapping[Any, Any], Mapping[Any, Any]]] = []
for job_name, job in jobs.items():
    if not isinstance(job, Mapping):
        continue
    steps = job.get("steps")
    if not isinstance(steps, list):
        continue
    for step in steps:
        if isinstance(step, Mapping):
            all_steps.append((str(job_name), job, step))

catalog_lock_command = "check_catalog_locks.py --json --require-generated"
if not any(catalog_lock_command in run_script(step) for _, _, step in all_steps):
    fail(f"CI workflow is missing SP-41 command in a step run script: {catalog_lock_command}")

required_commands = (
    "bash scripts/tests/test-preflight-production.sh",
    "bash scripts/tests/test-deploy-p0-preflight.sh",
)
api_job = jobs.get("api")
if not isinstance(api_job, Mapping):
    fail("CI workflow is missing the api job")
else:
    api_steps = api_job.get("steps")
    paired_steps = [
        step
        for step in api_steps if isinstance(step, Mapping)
        and all(command in run_script(step) for command in required_commands)
    ] if isinstance(api_steps, list) else []

    if not paired_steps:
        fail("api job must run both production preflight commands in the same step")
    elif continue_on_error_can_be_true(api_job):
        fail("api job must not enable continue-on-error")
    elif not any(
        not continue_on_error_can_be_true(step) and not has_disabling_condition(step)
        for step in paired_steps
    ):
        fail(
            "production preflight step must be blocking and must not have a disabling if condition"
        )

if failures:
    print(f"\nAssertions: {len(failures)} failed")
    raise SystemExit(1)

print("PASS  CI deploy preflight gate is blocking and complete")
PY

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

DEFAULT_WORKFLOW = Path(".github/workflows/ci.yml")
KEY_PATTERN = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_-]+):(?P<value>.*)$")
UNSCOPED_JOB_PATTERN = re.compile(r"(?m)^ {2}web-real-e2e:\s*(?:#.*)?$")


def parse_workflow_path(argv: Sequence[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(
        description="Reject unscoped external-write real API CI contracts."
    )
    parser.add_argument(
        "--workflow",
        default=str(DEFAULT_WORKFLOW),
        help="Workflow file to inspect (defaults to .github/workflows/ci.yml).",
    )
    namespace = parser.parse_args(argv)
    return Path(cast(str, namespace.workflow))


def has_dispatch_base_url_input(text: str) -> bool:
    key_stack: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        match = KEY_PATTERN.match(line)
        if match is None:
            continue

        indent = len(match.group("indent"))
        key = match.group("key")
        while key_stack and key_stack[-1][0] >= indent:
            key_stack.pop()
        key_path = [stack_key for _, stack_key in key_stack]
        key_path.append(key)
        if key_path[-3:] == ["workflow_dispatch", "inputs", "base_url"]:
            return True

        value = match.group("value").strip()
        if not value:
            key_stack.append((indent, key))
    return False


def find_violations(text: str) -> list[str]:
    violations: set[str] = set()
    if has_dispatch_base_url_input(text):
        violations.add("dispatch_base_url_input")
    if "PLAYWRIGHT_REAL_API" in text:
        violations.add("real_api_environment_flag")
    if UNSCOPED_JOB_PATTERN.search(text) is not None:
        violations.add("unscoped_real_e2e_job")
    return sorted(violations)


def main(argv: Sequence[str] | None = None) -> int:
    workflow_path = parse_workflow_path(argv)
    try:
        workflow_text = workflow_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("ci_boundary_error:workflow_unreadable")
        return 2

    violations = find_violations(workflow_text)
    if violations:
        for violation in violations:
            print(f"ci_boundary_violation:{violation}")
        return 1

    print("ci_real_e2e_boundary_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

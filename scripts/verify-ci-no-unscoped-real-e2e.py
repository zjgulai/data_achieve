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
# 有边界的真实链路门禁 job 名。见 ADR-008 D6。
SCOPED_JOB_NAME = "web-real-chain-e2e"
SCOPED_JOB_PATTERN = re.compile(rf"(?m)^ {{2}}{SCOPED_JOB_NAME}:\s*(?:#.*)?$")
# 门禁只许连本机一次性栈。任何其他主机名都意味着有人在把门禁指向真实环境。
LOOPBACK_URL_PATTERN = re.compile(r"http://(?:127\.0\.0\.1|localhost|\[::1\]):\d+")
# 清理必须无条件执行，否则失败时卷会留下，下一次运行带着脏数据。
ALWAYS_CLEANUP_PATTERN = re.compile(r"always\(\)")
DOWN_V_PATTERN = re.compile(r"e2e-real-stack\.sh\s+down|compose[^\n]*\bdown\b[^\n]*-v")


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
    violations.update(find_scoped_job_violations(text))
    return sorted(violations)


def extract_job_block(text: str, job_name: str) -> str | None:
    """取出某个 job 的整段 YAML（从 job 键到下一个顶层 job 键之前）。

    只按两空格缩进的 job 边界切分，不做完整 YAML 解析：这里要防的是
    「有人把门禁指向外网」和「有人去掉清理」，两者都写在 job 内部的文本里。
    """
    lines = text.splitlines()
    start = None
    for index, raw in enumerate(lines):
        if re.match(rf"^ {{2}}{re.escape(job_name)}:\s*(?:#.*)?$", raw):
            start = index
            break
    if start is None:
        return None

    block = [lines[start]]
    for raw in lines[start + 1 :]:
        # 下一个 job 键：恰好两空格缩进 + 标识符 + 冒号。
        if re.match(r"^ {2}[A-Za-z0-9_-]+:\s*(?:#.*)?$", raw):
            break
        block.append(raw)
    return "\n".join(block)


def find_scoped_job_violations(text: str) -> list[str]:
    """正向校验有边界的真实链路门禁。

    这个脚本原来只会说「不行」。门禁合法化之后，它还必须在有人把门禁
    改坏时说出来——否则它退化成一句永真断言，看着在保护，实际什么都没保护。
    """
    block = extract_job_block(text, SCOPED_JOB_NAME)
    if block is None:
        # job 不存在不算违规：分支上还没引入门禁时，旧规则仍然有效。
        return []

    violations: list[str] = []

    url_matches = re.findall(r"PLAYWRIGHT_BASE_URL:\s*[\"']?([^\"'\s]+)", block)
    if not url_matches:
        violations.append("scoped_job_missing_base_url")
    elif not all(LOOPBACK_URL_PATTERN.fullmatch(url) for url in url_matches):
        # 指向任何非本机地址都意味着门禁在打真实环境，而那没有清理账本，
        # 也没有人授权。
        violations.append("scoped_job_non_loopback_base_url")

    if DOWN_V_PATTERN.search(block) is None:
        violations.append("scoped_job_missing_down_v")
    # 清理必须在 always() 里：只在成功路径清理，失败时卷会留下来，
    # 下一次运行就带着上一轮的脏数据跑，种子可重复这个前提直接失效。
    if ALWAYS_CLEANUP_PATTERN.search(block) is None:
        violations.append("scoped_job_missing_always_cleanup")

    return violations


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

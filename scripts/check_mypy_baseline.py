#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/check_mypy_baseline.py \
#   --baseline ../../configs/quality/mypy-src-tests-signatures.txt --path src --path tests
#
# 回归守卫。基线是 multiset：每行「次数 TAB 归一化签名」。
#
# 判据：
#   - 现有签名计数上升，或出现基线里没有的签名，都是回归，退出码 1。
#   - 计数下降是允许的（decreased），退出码仍为 0。基线只会变松，不会变紧。
#   - 基线缺失/不可解析、mypy 输出不可解析、mypy 退出码不在 {0, 1}，都是无效输入，退出码 2。
#
# 这个脚本故意不提供 --update：它必须无法重设基线。

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = ROOT / "apps" / "api"

# 只读常量，供测试引用；helper 自身不读它。
CURRENT_HEAD = "202610220059"

DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>[^:\n]+):(?P<line>\d+):(?: (?P<col>\d+):)? error: (?P<msg>.*)$"
)
BASELINE_RE = re.compile(r"^(?P<count>[0-9]+)\t(?P<signature>.*\S.*)$")
SUMMARY_PREFIX = "Found "


class UnparsableLine(ValueError):
    """A mypy diagnostic line the helper cannot normalize."""


def normalize_diagnostics(stderr_stdout: str) -> Counter[str]:
    """Collapse a mypy run into a multiset of normalized signatures.

    Line and column collapse to the literal ``LINE``; ``note:`` lines and the
    ``Found N errors ...`` summary are dropped. Any line containing
    ``" error: "`` that does not match the diagnostic grammar raises
    :class:`UnparsableLine` — the helper fails closed instead of silently
    dropping a diagnostic.
    """

    diagnostics: Counter[str] = Counter()
    for raw_line in stderr_stdout.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.lstrip().startswith(SUMMARY_PREFIX):
            continue
        if " error: " not in line:
            # Notes, warnings and mypy's own chatter are not part of the gate.
            continue
        match = DIAGNOSTIC_RE.match(line)
        if match is None:
            raise UnparsableLine(line)
        diagnostics[
            f"{match.group('path')}:LINE: error: {match.group('msg')}"
        ] += 1
    return diagnostics


def compare(
    baseline: Counter[str], current: Counter[str]
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int, int]]]:
    """Return ``(regressions, decreases)`` as sorted ``(signature, baseline, current)``."""

    regressions = [
        (signature, baseline.get(signature, 0), count)
        for signature, count in current.items()
        if count > baseline.get(signature, 0)
    ]
    decreases = [
        (signature, count, current.get(signature, 0))
        for signature, count in baseline.items()
        if current.get(signature, 0) < count
    ]
    regressions.sort(key=lambda item: item[0].encode("utf-8"))
    decreases.sort(key=lambda item: item[0].encode("utf-8"))
    return regressions, decreases


def parse_baseline(path: Path) -> Counter[str]:
    """Read a multiset-v1 baseline. Raises :class:`ValueError` when invalid."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"baseline is unreadable: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"baseline is not UTF-8: {path}") from exc

    baseline: Counter[str] = Counter()
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line:
            raise ValueError(f"baseline line {number} is blank")
        match = BASELINE_RE.match(line)
        if match is None:
            raise ValueError(f"baseline line {number} is not '<count>\\t<signature>'")
        count = int(match.group("count"))
        if count <= 0:
            raise ValueError(f"baseline line {number} has a non-positive count")
        signature = match.group("signature")
        if signature in baseline:
            raise ValueError(f"baseline line {number} duplicates a signature")
        baseline[signature] = count
    if not baseline:
        raise ValueError("baseline is empty")
    return baseline


def _totals(diagnostics: Counter[str]) -> int:
    return sum(diagnostics.values())


def _decreased_total(
    decreases: list[tuple[str, int, int]],
) -> int:
    return sum(baseline_count - current_count for _, baseline_count, current_count in decreases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when mypy diagnostics regress against a multiset baseline.",
    )
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--api-dir", type=Path, default=DEFAULT_API)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)

    baseline_path = args.baseline.resolve()
    try:
        baseline = parse_baseline(baseline_path)
    except ValueError as exc:
        print(f"INVALID: {exc}")
        return 2

    api_dir = args.api_dir.resolve()
    command = [
        args.python,
        "-m",
        "mypy",
        *args.path,
        "--no-incremental",
        "--no-pretty",
        "--show-error-codes",
        "--no-error-summary",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=api_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"INVALID: mypy could not be started: {exc.strerror or exc}")
        return 2

    if completed.returncode not in {0, 1}:
        print(f"INVALID: mypy exited {completed.returncode}")
        return 2

    try:
        current = normalize_diagnostics(completed.stdout + completed.stderr)
    except UnparsableLine as exc:
        print(f"INVALID: unparsable mypy diagnostic: {exc}")
        return 2

    regressions, decreases = compare(baseline, current)
    fields = (
        f"current={_totals(current)} baseline={_totals(baseline)} "
        f"decreased={_decreased_total(decreases)}"
    )

    if regressions:
        print(f"REGRESSION: mypy baseline non-regression {fields}")
        for signature, baseline_count, current_count in regressions:
            print(f"  {signature} baseline={baseline_count} current={current_count}")
        return 1

    print(f"OK: mypy baseline non-regression {fields}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

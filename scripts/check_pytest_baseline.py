#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/check_pytest_baseline.py
#
# 回归守卫。基线为空集。
#
# 历史：2026-10-09 的 137 条失败已全部修复。
# 那份基线文件已归档到 reports/live-sweep/archive/，只作存档，不再作为比对依据。
#
# 判据：
#   - 任何 FAILED 行都是回归，退出码 1。
#   - pytest 没有产出汇总行（收集失败）也是回归。
#   - 全部通过时退出码 0。
#
# 本脚本可单独运行，且会启动 pytest，所以先跑目录生成前置。
# generated/ 不在版本控制里；没有它，目录测试在干净 checkout 上失败。
# 生成命令与 scripts/verify-mvp.sh、CI 完全相同。

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = ROOT / "apps" / "api"
GENERATE_SCRIPT = ROOT / "scripts" / "generate_platform_packages.py"

FAILED_RE = re.compile(r"^(FAILED|ERROR)\s+(\S+)", re.MULTILINE)
SUMMARY_RE = re.compile(r"^\s*(\d+)\s+(passed|failed|error)", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when any pytest test fails. Baseline is the empty set."
    )
    parser.add_argument(
        "--path",
        action="append",
        default=None,
        help="测试路径。可重复。默认依次跑 tests/unit 与 tests/integration。",
    )
    parser.add_argument(
        "--api-dir",
        type=Path,
        default=DEFAULT_API,
        help="apps/api 目录。",
    )
    parser.add_argument(
        "--python",
        default=None,
        help="解释器。默认用当前解释器。",
    )
    return parser.parse_args()


def ensure_generated(api_dir: Path, python: str | None) -> str | None:
    """运行目录生成前置。成功返回 None，失败返回错误说明。

    目录测试读取 generated/。本脚本会启动 pytest，所以必须先保证它存在。
    """
    print("==> Generate platform packages (pytest prerequisite)", flush=True)
    cmd = [python or sys.executable, str(GENERATE_SCRIPT)]
    print(f"    {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    except OSError as exc:
        return f"REGRESSION: 目录生成前置无法启动：{exc}。pytest 未启动。"
    if proc.returncode != 0:
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        return (
            f"REGRESSION: 目录生成前置失败（退出码 {proc.returncode}）。"
            "pytest 未启动。"
        )
    print(proc.stdout.rstrip())
    return None


def run(paths: list[str], api_dir: Path, python: str | None) -> tuple[int, str]:
    cmd = [python or sys.executable, "-m", "pytest", "-q", "--no-header", *paths]
    proc = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    args = parse_args()
    paths = args.path or ["tests/unit", "tests/integration"]

    generation_error = ensure_generated(args.api_dir, args.python)
    if generation_error is not None:
        print(generation_error)
        return 1

    code, output = run(paths, args.api_dir, args.python)
    failures = FAILED_RE.findall(output)
    summary = SUMMARY_RE.findall(output)

    print(output.rstrip())
    print()

    if not summary:
        print("REGRESSION: pytest 未产出汇总行。收集失败或参数错误。")
        return 1

    if failures:
        print(f"REGRESSION: {len(failures)} 项失败。基线为空集，任何失败都算回归。")
        for kind, name in failures:
            print(f"  {kind} {name}")
        return 1

    if code != 0:
        print(f"REGRESSION: pytest 退出码 {code}，但没有 FAILED 行。检查收集错误。")
        return 1

    print("OK: 0 failed。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

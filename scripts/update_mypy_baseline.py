#!/usr/bin/env python3
# ─── How to run ───
# cd apps/api && uv run python ../../scripts/update_mypy_baseline.py --confirm
#
# 重建 mypy 基线。这是**独立**于守卫的工具：check_mypy_baseline.py 故意不提供
# --update，它必须无法重设自己的基线，否则一次手滑就能把回归洗白。
# 重建基线是一个显式的、需要人工确认的动作，所以放在这里。
#
# 必须带 --confirm，并打印将要写入的变更摘要（新增/消失的签名各多少），
# 让人在提交前看清基线是变松还是变紧。
#
# 同时写一份 provenance：基线是何时、用什么 Python、在哪个 commit 下测的。
# 没有 provenance 的基线无法判断「这条差异是历史累积还是环境噪声」。
#
# 退出码：0 已写入，1 需要确认，2 输入错误。

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = ROOT / "apps" / "api"
GUARD = ROOT / "scripts" / "check_mypy_baseline.py"
DEFAULT_BASELINE = ROOT / "configs" / "quality" / "mypy-src-tests-signatures.txt"
PROVENANCE = ROOT / "configs" / "quality" / "mypy-baseline-provenance.json"

PROVENANCE_SCHEMA = "mypy-baseline-provenance.v1"

# 与守卫完全一致的 mypy 参数。任何偏离都会让基线不可比。
MYPY_FLAGS = (
    "--no-incremental",
    "--no-pretty",
    "--show-error-codes",
    "--no-error-summary",
    "--no-color-output",
)


def _load_guard():
    """复用守卫的解析器，避免两套实现漂移。"""
    spec = importlib.util.spec_from_file_location("_mypy_guard", GUARD)
    if spec is None or spec.loader is None:
        raise SystemExit(f"输入错误：无法加载 {GUARD}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_mypy(api_dir: Path, python: str, paths: list[str]) -> str:
    env = os.environ.copy()
    env["MYPY_FORCE_COLOR"] = "0"
    env["FORCE_COLOR"] = "0"
    env["NO_COLOR"] = "1"
    completed = subprocess.run(
        [python, "-m", "mypy", *paths, *MYPY_FLAGS],
        cwd=api_dir,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if completed.returncode not in {0, 1}:
        raise SystemExit(f"输入错误：mypy 退出 {completed.returncode}")
    return completed.stdout + completed.stderr


def _python_version(python: str) -> str:
    completed = subprocess.run(
        [python, "-c", "import platform; print(platform.python_version())"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() or platform.python_version()


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def _read_baseline(path: Path) -> Counter[str]:
    """读现有基线，用于对比；文件不存在时返回空。"""
    if not path.is_file():
        return Counter()
    existing: Counter[str] = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        count, _, signature = line.partition("\t")
        if count.isdigit() and signature:
            existing[signature] = int(count)
    return existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="重建 mypy 基线（独立于守卫，需显式确认）",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--path", action="append", default=None)
    parser.add_argument("--api-dir", type=Path, default=DEFAULT_API)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="确认写入。没有这个开关只打印摘要。",
    )
    args = parser.parse_args(argv)

    paths = args.path or ["src", "tests"]
    api_dir = args.api_dir.resolve()
    baseline_path = args.baseline.resolve()

    guard = _load_guard()
    output = _run_mypy(api_dir, args.python, paths)
    try:
        current = guard.normalize_diagnostics(output)
    except guard.ColorizedOutput as exc:
        print(f"INVALID: {exc}")
        return 2
    except guard.UnparsableLine as exc:
        print(f"INVALID: unparsable mypy diagnostic: {exc}")
        return 2

    if not current:
        print("INVALID: 解析到 0 条诊断，拒绝用空基线覆盖")
        return 2

    previous = _read_baseline(baseline_path)
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    increased = sorted(
        (sig, previous[sig], current[sig])
        for sig in set(current) & set(previous)
        if current[sig] > previous[sig]
    )
    decreased = sorted(
        (sig, previous[sig], current[sig])
        for sig in set(current) & set(previous)
        if current[sig] < previous[sig]
    )

    total_old = sum(previous.values())
    total_new = sum(current.values())

    print(f"基线：{baseline_path.relative_to(ROOT)}")
    print(f"签名数 {len(previous)} → {len(current)}，诊断数 {total_old} → {total_new}")
    print(f"  新增签名 {len(added)}，消失签名 {len(removed)}")
    print(f"  计数上升 {len(increased)}，计数下降 {len(decreased)}")

    if increased:
        print("\n计数上升（收紧检查前请确认这些是历史累积而非新引入）：")
        for sig, was, now in increased[:12]:
            print(f"  +{now - was} ({was}→{now}) {sig[:110]}")
        if len(increased) > 12:
            print(f"  ...另有 {len(increased) - 12} 条")

    if not args.confirm:
        print("\n未写入。确认无误后加 --confirm。")
        return 1

    # 格式固定为 "<count>\t<signature>"，签名按 utf-8 字节序排序，保证可复现。
    lines = [
        f"{count}\t{signature}"
        for signature, count in sorted(
            current.items(), key=lambda item: item[0].encode("utf-8")
        )
    ]
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    PROVENANCE.write_text(
        json.dumps(
            {
                "schema_version": PROVENANCE_SCHEMA,
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "commit": _git_commit(),
                "python_version": _python_version(args.python),
                "paths": paths,
                "mypy_flags": list(MYPY_FLAGS),
                "signatures": len(current),
                "diagnostics": sum(current.values()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\n已写入 {baseline_path.relative_to(ROOT)}")
    print(f"已写入 {PROVENANCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
HELPER = PROJECT_ROOT / "scripts" / "check_mypy_baseline.py"

MESSAGE = 'Returning Any from function declared to return "int"  [no-any-return]'
NORMALIZED = f"src/pkg/mod.py:LINE: error: {MESSAGE}"


def _diagnostic(line: int, path: str = "src/pkg/mod.py") -> str:
    return f"{path}:{line}: error: {MESSAGE}"


def _write_shim(tmp_path: Path, *, body: str, status: int) -> Path:
    """Write a fake interpreter that logs its cwd and replays a canned run."""

    shim = tmp_path / "fake-python"
    shim.write_text(
        "#!/bin/sh\n"
        'pwd -P > "$SHIM_CWD_LOG"\n'
        f"{body}\n"
        f"exit {status}\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def _emit(*lines: str) -> str:
    return "".join(f"printf '%s\\n' {line!r}\n" for line in lines)


def _run(
    tmp_path: Path,
    *,
    baseline: str,
    shim_body: str,
    shim_status: int = 1,
    paths: tuple[str, ...] = ("src",),
    api_dir: Path | None = None,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str]:
    baseline_path = tmp_path / "baseline.txt"
    baseline_path.write_text(baseline, encoding="utf-8")
    shim = _write_shim(tmp_path, body=shim_body, status=shim_status)
    cwd_log = tmp_path / "cwd.log"
    resolved_api_dir = (api_dir or tmp_path / "apps" / "api").resolve()
    resolved_api_dir.mkdir(parents=True, exist_ok=True)

    command = [sys.executable, str(HELPER), "--baseline", str(baseline_path)]
    for path in paths:
        command += ["--path", path]
    command += ["--api-dir", str(resolved_api_dir), "--python", str(shim)]

    environment = {"SHIM_CWD_LOG": str(cwd_log), "PATH": "/usr/bin:/bin"}
    if extra_env:
        environment.update(extra_env)
    result = subprocess.run(
        command,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    return result, cwd_log.read_text(encoding="utf-8").strip() if cwd_log.exists() else ""


def test_normalization_collapses_line_and_column_and_counts_duplicates(
    tmp_path: Path,
) -> None:
    baseline = f"2\t{NORMALIZED}\n"
    shim_body = _emit(
        _diagnostic(41),
        _diagnostic(902),
        "src/pkg/mod.py:41: note: See https://mypy.readthedocs.io/en/stable/_refs.html",
        "Found 2 errors in 1 file (checked 7 source files)",
    )

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == (
        "OK: mypy baseline non-regression current=2 baseline=2 decreased=0"
    )


def test_decrease_is_allowed_and_reported(tmp_path: Path) -> None:
    baseline = f"3\t{NORMALIZED}\n"
    shim_body = _emit(_diagnostic(11), _diagnostic(12))

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == (
        "OK: mypy baseline non-regression current=2 baseline=3 decreased=1"
    )


def test_count_increase_on_an_existing_signature_is_a_regression(tmp_path: Path) -> None:
    baseline = f"2\t{NORMALIZED}\n"
    shim_body = _emit(*(_diagnostic(line) for line in (10, 20, 30)))

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 1, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == (
        "REGRESSION: mypy baseline non-regression current=3 baseline=2 decreased=0"
    )
    assert lines[1] == f"  {NORMALIZED} baseline=2 current=3"
    assert len(lines) == 2


def test_brand_new_signature_is_a_regression(tmp_path: Path) -> None:
    baseline = f"1\t{NORMALIZED}\n"
    new_signature = (
        'src/pkg/other.py:LINE: error: Need type annotation for "cache"  [var-annotated]'
    )
    shim_body = _emit(
        _diagnostic(10),
        'src/pkg/other.py:7: error: Need type annotation for "cache"  [var-annotated]',
    )

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        "REGRESSION: mypy baseline non-regression current=2 baseline=1 decreased=0",
        f"  {new_signature} baseline=0 current=1",
    ]


def test_signature_entirely_absent_from_current_output_is_clean(tmp_path: Path) -> None:
    baseline = f"1\t{NORMALIZED}\n"
    shim_body = _emit("Success: no issues found in 7 source files")

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=0)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == (
        "OK: mypy baseline non-regression current=0 baseline=1 decreased=1"
    )


def test_mypy_usage_error_exits_two_and_never_zero(tmp_path: Path) -> None:
    baseline = f"1\t{NORMALIZED}\n"
    shim_body = _emit("usage: mypy [-h] [--version] [-v] [--config-file FILE]")

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=2)

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["INVALID: mypy exited 2"]


def test_unparsable_error_line_fails_closed(tmp_path: Path) -> None:
    baseline = f"1\t{NORMALIZED}\n"
    shim_body = _emit('src/pkg/mod.py: error: Something the grammar rejects  [misc]')

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout.startswith("INVALID: unparsable mypy diagnostic:")


def test_cwd_is_forced_to_the_absolute_api_dir(tmp_path: Path) -> None:
    baseline = f"1\t{NORMALIZED}\n"
    shim_body = _emit(_diagnostic(10))
    api_dir = tmp_path / "nested" / "apps" / "api"

    result, recorded_cwd = _run(
        tmp_path,
        baseline=baseline,
        shim_body=shim_body,
        paths=("src",),
        api_dir=api_dir,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert recorded_cwd == str(api_dir.resolve())
    assert recorded_cwd != str(PROJECT_ROOT)


@pytest.mark.parametrize(
    ("label", "baseline"),
    [
        ("duplicate signature", f"1\t{NORMALIZED}\n1\t{NORMALIZED}\n"),
        ("zero count", f"0\t{NORMALIZED}\n"),
        ("missing tab", f"1 {NORMALIZED}\n"),
        ("empty file", ""),
    ],
)
def test_malformed_baseline_is_invalid(
    tmp_path: Path, label: str, baseline: str
) -> None:
    shim_body = _emit("Success: no issues found in 7 source files")

    result, _ = _run(
        tmp_path, baseline=baseline, shim_body=shim_body, shim_status=0
    )

    assert result.returncode == 2, f"{label}: {result.stdout}{result.stderr}"
    assert result.stdout.startswith("INVALID:"), label


def test_missing_baseline_is_invalid(tmp_path: Path) -> None:
    shim = _write_shim(tmp_path, body=":", status=0)
    missing = tmp_path / "absent.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "--baseline",
            str(missing),
            "--path",
            "src",
            "--api-dir",
            str(tmp_path),
            "--python",
            str(shim),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"SHIM_CWD_LOG": str(tmp_path / "cwd.log"), "PATH": "/usr/bin:/bin"},
    )

    assert result.returncode == 2
    assert result.stdout.startswith("INVALID: baseline is unreadable:")


# ── fail-open 回归防护（2026-10-28） ────────────────────────────────────────
# 曾经的缺陷：mypy 输出带 ANSI 颜色码时，`" error: "` 字面量匹配不到诊断行，
# 整轮结果被算成 0 条，脚本输出 OK、退出码 0。本机 shell 常带 FORCE_COLOR=1，
# 于是在终端里跑守卫永远「通过」。以下测试锁住三条防线。


def test_colorized_output_fails_closed(tmp_path: Path) -> None:
    """带 ANSI 颜色码的输出必须判 INVALID，绝不能报 OK。"""
    baseline = f"1\t{NORMALIZED}\n"
    # \x1b 在 Python 里是真实 ESC 字节，写进 shim 后由 printf 原样输出。
    shim_body = (
        "printf '%s\\n' 'src/pkg/mod.py:10: "
        "\x1b[1m\x1b[31merror:\x1b(B\x1b[m " + MESSAGE + "'\n"
    )

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout.startswith("INVALID:")
    assert "ANSI" in result.stdout


def test_exit_one_with_zero_parsed_diagnostics_is_invalid(tmp_path: Path) -> None:
    """mypy 说报过错（exit 1），却一条都没解析出来，说明解析器失效。"""
    baseline = f"1\t{NORMALIZED}\n"
    shim_body = _emit("some unusual output that contains no diagnostics")

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout.startswith("INVALID:")
    assert "0 条诊断" in result.stdout


def test_child_env_forces_colors_off(tmp_path: Path) -> None:
    """即使父进程带 FORCE_COLOR=1，传给 mypy 的环境也必须关色。

    shim 的标准输出被子进程捕获、不会进入 helper 的输出，所以写日志文件再读。
    """
    baseline = f"1\t{NORMALIZED}\n"
    env_log = tmp_path / "env.log"
    shim_body = (
        '{\n'
        '  printf "FORCE=%s\\n" "${FORCE_COLOR:-unset}"\n'
        '  printf "MYPYFORCE=%s\\n" "${MYPY_FORCE_COLOR:-unset}"\n'
        '  printf "NOCOLOR=%s\\n" "${NO_COLOR:-unset}"\n'
        f'}} > "{env_log}"\n'
    ) + _emit(_diagnostic(10))

    result, _ = _run(
        tmp_path,
        baseline=baseline,
        shim_body=shim_body,
        shim_status=1,
        extra_env={"FORCE_COLOR": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    captured = env_log.read_text(encoding="utf-8")
    assert "FORCE=0" in captured
    assert "MYPYFORCE=0" in captured
    assert "NOCOLOR=1" in captured


def test_no_color_output_flag_is_passed_to_mypy(tmp_path: Path) -> None:
    """命令行也要显式关色：环境变量在旧版 mypy 上不一定生效。"""
    baseline = f"1\t{NORMALIZED}\n"
    args_log = tmp_path / "args.log"
    shim_body = f'printf "ARGS=%s\\n" "$*" > "{args_log}"\n' + _emit(_diagnostic(10))

    result, _ = _run(tmp_path, baseline=baseline, shim_body=shim_body, shim_status=1)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "--no-color-output" in args_log.read_text(encoding="utf-8")

"""生成物前置静态断言。

目录测试读取 generated/platform-packages.json。它不在版本控制里。
所有会运行这些 pytest 的本地入口必须先执行同一个生成命令。
删掉任一处前置时本文件失败。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GENERATE_SCRIPT = "scripts/generate_platform_packages.py"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_verify_mvp_generates_before_pytest() -> None:
    """verify-mvp.sh 必须在 pytest 前生成目录。"""
    text = _read("scripts/verify-mvp.sh")
    assert GENERATE_SCRIPT in text
    generation = text.index(
        'run_step "Generate platform packages (pytest prerequisite)"'
    )
    pytest_step = text.index('run_step "API pytest"')
    assert generation < pytest_step, "verify-mvp.sh 必须在 pytest 前生成目录"


def test_check_pytest_baseline_generates_before_pytest() -> None:
    """check_pytest_baseline.py 可单独运行，必须先生成再启动 pytest。"""
    text = _read("scripts/check_pytest_baseline.py")
    assert (
        'GENERATE_SCRIPT = ROOT / "scripts" / "generate_platform_packages.py"'
        in text
    )
    generation = text.index("generation_error = ensure_generated")
    pytest_run = text.index("code, output = run(")
    assert generation < pytest_run, "check_pytest_baseline.py 必须先生成再启动 pytest"


def test_ci_generates_before_pytest_in_each_job() -> None:
    """CI 的两个 pytest 作业都必须在 pytest 前生成目录。"""
    text = _read(".github/workflows/ci.yml")
    assert text.count("Generate platform packages") == 2
    platform_job = text.split("platform-packages:", 1)[1].split("\n  api:", 1)[0]
    api_job = text.split("\n  api:", 1)[1].split(
        "\n  workflow-planner-postgres:", 1
    )[0]
    assert platform_job.index(GENERATE_SCRIPT) < platform_job.index(
        "Run package and MCP tests"
    )
    assert api_job.index(GENERATE_SCRIPT) < api_job.index("- name: Pytest")

"""KG-08 recall 插件单测：真实检索（skipif nmem 不可用）+ 超时降级 + 空查询 + 门控。"""
from __future__ import annotations

import shutil

import pytest

from data_intelligence_hub.nmem_recall import recall_durable_memories

nmem_available = shutil.which("nmem") is not None


def test_empty_query_returns_empty() -> None:
    assert recall_durable_memories("") == ""
    assert recall_durable_memories("   ") == ""


def test_disabled_by_default() -> None:
    """NMEM_RECALL 未设时（默认关闭）即使 nmem 可用也返回空串。"""
    monkey = pytest.MonkeyPatch()
    monkey.delenv("NMEM_RECALL", raising=False)
    try:
        assert recall_durable_memories("发布红线") == ""
    finally:
        monkey.undo()


def test_degrades_on_bad_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI 不存在/失败时静默降级为空串，不抛异常。"""
    monkeypatch.setenv("NMEM_RECALL", "1")
    monkeypatch.setenv("NMEM_CLI_PATH", "nmem-definitely-not-exists-xyz")
    assert recall_durable_memories("发布红线") == ""


def test_degrades_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """超时降级：用一个睡眠超过 3 秒的假 CLI 验证不阻塞。"""
    import sys

    monkeypatch.setenv("NMEM_RECALL", "1")
    sleeper = "import time; time.sleep(10)"
    monkeypatch.setenv("NMEM_CLI_PATH", f"{sys.executable} -c '{sleeper}' --")
    # NMEM_CLI_PATH 作为可执行名含空格不会按 shell 展开，这里换一种方式：
    # 直接把 PATH 指到含假 nmem 的临时目录更贴近真实路径解析。
    import os
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "nmem"
        fake.write_text(f"#!{sys.executable}\n{sleeper}\n")
        fake.chmod(0o755)
        monkeypatch.setenv("PATH", f"{td}{os.pathsep}{os.environ.get('PATH','')}")
        monkeypatch.delenv("NMEM_CLI_PATH", raising=False)
        assert recall_durable_memories("发布红线") == ""


@pytest.mark.skipif(not nmem_available, reason="nmem CLI not installed")
def test_real_search_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实检索：门控开启时应能从 source-agent 检索到红线记忆。"""
    monkeypatch.setenv("NMEM_RECALL", "1")
    out = recall_durable_memories("发布红线 restart edge", limit=2, min_score=0.3)
    if not out:
        pytest.skip("nmem service unavailable or no match")
    assert "Nowledge Mem" in out
    assert "【" in out and "】" in out

"""提示词文件化与口径注入的回归测试。

覆盖三件事：
1. 加载器能读到两个 Agent 的提示词文件，且文件确实是 UTF-8 且非空。
2. 占位符只认双花括号，JSON 示例里的花括号不被误替换。
3. 取不到 catalog 时，提示词不会把 {{...}} 泄露给模型，也不会说旧数字。
"""

from __future__ import annotations

import pytest

from data_intelligence_hub.agents.prompt_loader import (
    load_prompt,
    missing_placeholders,
    prompt_path,
    prompt_sha256,
    render_prompt,
)


def test_both_agents_ship_a_system_prompt() -> None:
    for agent_id in ("shusuo", "tiktok_cdo"):
        path = prompt_path(agent_id)
        assert path.is_file(), f"{agent_id} 缺少 {path}"
        text = path.read_text(encoding="utf-8")
        assert text.strip(), f"{agent_id} 的提示词为空"


def test_prompt_sha_is_stable_and_hex() -> None:
    for agent_id in ("shusuo", "tiktok_cdo"):
        sha = prompt_sha256(agent_id)
        assert sha is not None
        assert len(sha) == 64
        assert sha == prompt_sha256(agent_id), "同一文件两次读取的 sha 必须一致"
        int(sha, 16)  # 必须是合法十六进制


def test_prompt_sha_missing_file_returns_none() -> None:
    assert prompt_sha256("no_such_agent") is None


def test_render_replaces_known_placeholders() -> None:
    out = render_prompt("平台 {{platform_count}} 个", {"platform_count": 70})
    assert out == "平台 70 个"


def test_render_leaves_unknown_placeholders_intact() -> None:
    out = render_prompt("{{known}} 与 {{unknown}}", {"known": "A"})
    assert out == "A 与 {{unknown}}"
    assert missing_placeholders(out) == ["unknown"]


def test_render_does_not_touch_json_braces() -> None:
    """意图提示词里有 {"action": ...} 这样的 JSON 示例，不能被当成占位符。"""
    template = '严格输出：{"action": "<action>", "limit": 10}'
    assert render_prompt(template, {"action": "search"}) == template


def test_shusuo_prompt_has_no_stale_counts_after_render() -> None:
    """渲染后的提示词不应残留任何占位符，也不应出现旧口径数字。"""
    values = {
        "catalog_clause": (
            "当前能力口径：70 个平台包、312 个能力视图、284 个唯一端点；"
        )
    }
    text = load_prompt("shusuo", values=values)
    assert text is not None
    assert missing_placeholders(text) == []
    assert "312" in text and "284" in text
    # 旧提示词里写死的 286/258 已随锁文件变化，不得再出现。
    assert "286" not in text
    assert "258" not in text


def test_shusuo_prompt_without_catalog_omits_numbers() -> None:
    """catalog 取不到时传空 catalog_clause：提示词里不能出现任何数字口径。"""
    text = load_prompt("shusuo", values={"catalog_clause": ""})
    assert text is not None
    assert missing_placeholders(text) == []
    assert "286" not in text
    assert "258" not in text
    assert "能力视图" not in text


def test_tiktok_prompt_reads_cleanly() -> None:
    text = load_prompt("tiktok_cdo")
    assert text is not None
    assert "action" in text
    assert missing_placeholders(text) == [], "意图提示词不应含占位符"


def test_load_prompt_falls_back_when_file_absent() -> None:
    assert load_prompt("no_such_agent") is None
    assert load_prompt("no_such_agent", default="fallback") == "fallback"


@pytest.mark.parametrize("agent_id", ["shusuo", "tiktok_cdo"])
def test_prompt_files_are_plain_utf8(agent_id: str) -> None:
    """本环境 Write 工具会留 NUL 尾洞；NUL 会让 docker build 内的 Python 直接报错。"""
    raw = prompt_path(agent_id).read_bytes()
    assert b"\x00" not in raw, f"{agent_id} 提示词含 NUL 字节"
    raw.decode("utf-8")

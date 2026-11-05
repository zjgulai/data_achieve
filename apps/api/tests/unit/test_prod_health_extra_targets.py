"""SP-43 prod_health 多目标巡检测试。

与 test_prod_health_check.py 分文件:_parse_extra_targets 与 main 的
extra_targets 分支(2026-11-09 D4 新增)。B 口径=监控不验收:B 掉线
不改变 A 的退出码。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from data_intelligence_hub.maintenance.prod_health_check import (
    DEFAULT_STATE_FILE,
    _parse_extra_targets,
    config_from_env,
    main,
)


def _ready_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": "connected",
        "schema_revision": "202610310068",
        "schema_head": "202610310068",
    }


def test_parse_extra_targets_sp43() -> None:
    assert _parse_extra_targets(None) == ()
    assert _parse_extra_targets("") == ()
    assert _parse_extra_targets("   ") == ()
    parsed = _parse_extra_targets("b=https://scrapy.example-b.com/, prod2=https://p2.test")
    assert parsed == (("b", "https://scrapy.example-b.com"), ("prod2", "https://p2.test"))
    # 坏段(无 =)跳过,不炸整个巡检
    assert _parse_extra_targets("badsegment,ok=https://x.test") == (
        ("ok", "https://x.test"),
    )


def test_config_from_env_parses_extra_targets() -> None:
    config = config_from_env({"SCRAPY_HEALTH_EXTRA_TARGETS": "b=https://scrapy-b.test"})
    assert config.extra_targets == (("b", "https://scrapy-b.test"),)
    # 不配置时为空元组,行为与旧版一致
    assert config_from_env({}).extra_targets == ()
    assert config_from_env({}).state_file == Path(DEFAULT_STATE_FILE)


def test_main_checks_extra_targets_with_independent_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A 健康时退出码必须为 0,B 掉线只体现在 B 自己的报告里(监控不验收)。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "a.test":
            if request.url.path == "/mcp/":
                return httpx.Response(401)  # 未带凭证,401 = 部署正常
            return httpx.Response(200, json=_ready_payload())
        # B 故意 500:掉线场景
        return httpx.Response(500, json={})

    state_a = tmp_path / "state.json"

    monkeypatch.setenv("SCRAPY_HEALTH_BASE_URL", "https://a.test")
    monkeypatch.setenv("SCRAPY_HEALTH_STATE_FILE", str(state_a))
    monkeypatch.setenv("SCRAPY_HEALTH_EXTRA_TARGETS", "b=https://b.test")
    monkeypatch.setenv("HEALTH_ALERTS_DISABLED", "true")
    monkeypatch.setenv("LARK_SHUSUO_APP_ID", "")
    monkeypatch.setenv("LARK_SHUSUO_APP_SECRET", "")

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs.pop("timeout", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(
        "data_intelligence_hub.maintenance.prod_health_check.httpx.Client", fake_client
    )

    captured: list[dict[str, Any]] = []
    real_print = print
    monkeypatch.setattr("builtins.print", lambda line: captured.append(json.loads(line)))

    exit_code = main()
    real_print("exit:", exit_code)

    assert exit_code == 0, "A 健康时退出码必须是 0(B 掉线不改变 A 的退出码)"
    assert len(captured) == 2, "应有 A、B 两份 JSON 报告"
    assert captured[0]["base_url"] == "https://a.test"
    assert "target_name" not in captured[0]
    assert captured[0]["status"] == "ok"
    assert captured[1]["base_url"] == "https://b.test"
    assert captured[1]["target_name"] == "b"
    assert captured[1]["status"] == "failed"
    # B 的 state 文件独立(由 A 的 stem 推导)
    assert captured[1]["state_file"] != captured[0]["state_file"]

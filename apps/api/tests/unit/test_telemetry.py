"""telemetry v0 单测(Plan C D5)。

覆盖:_log_bot_request 打点与失败不阻断;bot-summary 聚合接口。
DB 相关用例用 SQLite 内存库(项目单测惯例,见 conftest)。
"""

from __future__ import annotations

import json
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data_intelligence_hub.agents.shusuo import lark_client as shusuo_lark_client
from data_intelligence_hub.agents.shusuo import router as shusuo_router
from data_intelligence_hub.agents.shusuo.config import get_shushuo_config
from data_intelligence_hub.models.bot_request_log import BotRequestLog


@pytest.fixture()
async def anyio_backend() -> str:
    return "asyncio"


def test_log_bot_request_writes_row(monkeypatch) -> None:
    """打点:合法输入写一行 BotRequestLog。"""
    saved: list[BotRequestLog] = []

    class FakeSession:
        def add(self, obj):
            saved.append(obj)

        async def commit(self):
            return None

    class _FakeCtx:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(
        "data_intelligence_hub.core.database.async_session_factory",
        lambda: _FakeCtx(),
    )

    import asyncio

    asyncio.run(
        shusuo_router._log_bot_request(
            channel="p2p",
            chat_id="oc_x",
            open_id="ou_y",
            trigger="message",
            message_type="text",
            text="采集 TikTok",
            command_name="collect",
            argument="TikTok",
        )
    )
    assert len(saved) == 1
    assert saved[0].command == "collect"
    assert saved[0].channel == "p2p"
    assert saved[0].trigger == "message"


def test_log_bot_request_failure_does_not_raise(monkeypatch) -> None:
    """打点失败绝不抛异常(不阻断回复链路)。"""

    def boom_factory():
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "data_intelligence_hub.core.database.async_session_factory", boom_factory
    )
    import asyncio

    # 不抛即通过
    asyncio.run(
        shusuo_router._log_bot_request(
            channel="p2p",
            chat_id="oc_x",
            open_id="ou_y",
            trigger="message",
            message_type="text",
            text="x",
        )
    )


def test_log_bot_request_empty_chat_id_skips(monkeypatch) -> None:
    saved: list[BotRequestLog] = []

    class FakeSession:
        def add(self, obj):
            saved.append(obj)

        async def commit(self):
            return None

    class _FakeCtx:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(
        "data_intelligence_hub.core.database.async_session_factory",
        lambda: _FakeCtx(),
    )
    import asyncio

    asyncio.run(
        shusuo_router._log_bot_request(
            channel="p2p",
            chat_id="",
            open_id="ou",
            trigger="message",
            message_type="text",
            text="x",
        )
    )
    assert saved == []


def test_handle_envelope_logs_message_request(monkeypatch) -> None:
    """完整链路:p2p 帮助消息 → _handle_envelope → 打点 command=help。"""
    saved: list[BotRequestLog] = []

    class FakeSession:
        def add(self, obj):
            saved.append(obj)

        async def commit(self):
            return None

    class _FakeCtx:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(
        "data_intelligence_hub.core.database.async_session_factory",
        lambda: _FakeCtx(),
    )
    monkeypatch.setattr(
        shusuo_lark_client, "reply_text", AsyncMock(return_value="om")
    )
    monkeypatch.delenv("SHUSUO_ALLOWED_OPEN_IDS", raising=False)
    get_shushuo_config.cache_clear()
    shusuo_router._seen_events.clear()

    envelope = {
        "header": {"event_type": "im.message.receive_v1", "event_id": "evt-tl-1"},
        "event": {
            "sender": {"sender_type": "user", "sender_id": {"open_id": "ou_t"}},
            "message": {
                "message_id": "om_tl_1",
                "chat_id": "oc_tl",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "帮助"}),
            },
        },
    }
    import asyncio

    asyncio.run(shusuo_router._handle_envelope(envelope))
    assert len(saved) == 1
    assert saved[0].command == "help"
    assert saved[0].channel == "p2p"


def test_bot_summary_aggregates(monkeypatch) -> None:
    """bot-summary:按 command/channel/trigger 聚合(DB 依赖注入由
    postgres_abi/契约套件覆盖,这里做函数级验证)。"""
    rows = [
        ("help", "p2p", "message", 3),
        ("collect", "group", "message", 8),
        ("collect", "group", "message", 2),
        ("card:confirm", "group", "card_action", 1),
    ]

    class FakeExecute:
        def all(self):
            return rows

    class FakeSess:
        async def execute(self, *a, **kw):
            return FakeExecute()

    from data_intelligence_hub.api.routes.telemetry import bot_summary

    result = asyncio_run(
        bot_summary(session=FakeSess(), _context=object(), days=30)  # type: ignore[arg-type]
    )
    assert result["total_requests"] == 14
    by_command = {item["command"]: item["count"] for item in result["by_command"]}
    assert by_command["collect"] == 10
    assert by_command["help"] == 3
    assert by_command["card:confirm"] == 1
    by_channel = {item["channel"]: item["count"] for item in result["by_channel"]}
    assert by_channel["group"] == 11
    by_trigger = {item["trigger"]: item["count"] for item in result["by_trigger"]}
    assert by_trigger["message"] == 13
    assert by_trigger["card_action"] == 1
    assert result["window_days"] == 30


def asyncio_run(coro: Coroutine[Any, Any, dict[str, Any]]) -> dict[str, Any]:
    import asyncio

    return asyncio.run(coro)

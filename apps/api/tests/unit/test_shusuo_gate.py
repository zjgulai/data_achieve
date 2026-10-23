from __future__ import annotations

import pytest

from data_intelligence_hub.agents.shusuo.gate import (
    MessageGateDecision,
    decide_message_gate,
)


@pytest.mark.parametrize(
    ("chat_type", "mentions", "bot_open_id", "expected"),
    [
        ("p2p", None, None, MessageGateDecision.ALLOW_P2P),
        (
            "group",
            [{"id": {"open_id": "ou_bot"}}],
            "ou_bot",
            MessageGateDecision.ALLOW_GROUP_MENTION,
        ),
        ("group", [], "ou_bot", MessageGateDecision.IGNORE_GROUP_NO_MENTION),
        (
            "group",
            [{"id": {"open_id": "ou_other"}}],
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            [
                {"id": {"open_id": "ou_other"}},
                {"id": {"open_id": "ou_bot"}},
            ],
            "ou_bot",
            MessageGateDecision.ALLOW_GROUP_MENTION,
        ),
        (
            "group",
            [{"key": "@_all", "id": {}}],
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            None,
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            "not-a-list",
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            [None, {}, {"id": "bad"}, {"id": {}}],
            "ou_bot",
            MessageGateDecision.IGNORE_GROUP_NO_MENTION,
        ),
        (
            "group",
            [{"id": {"open_id": "ou_bot"}}],
            "",
            MessageGateDecision.IGNORE_BOT_ID_UNAVAILABLE,
        ),
        (None, [], None, MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE),
        ("", [], None, MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE),
        ("topic", [], None, MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE),
    ],
)
def test_decide_message_gate(
    chat_type: object,
    mentions: object,
    bot_open_id: str | None,
    expected: MessageGateDecision,
) -> None:
    assert (
        decide_message_gate(
            chat_type=chat_type,
            mentions=mentions,
            bot_open_id=bot_open_id,
        )
        is expected
    )

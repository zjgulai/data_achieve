"""数说飞书消息的会话门禁。

本模块只做纯数据判断。它不读配置、不发请求、不写日志、不发送回复。
"""

from __future__ import annotations

from enum import StrEnum


class MessageGateDecision(StrEnum):
    ALLOW_P2P = "allow_p2p"
    ALLOW_GROUP_MENTION = "allow_group_mention"
    IGNORE_GROUP_NO_MENTION = "ignore_group_no_mention"
    IGNORE_UNKNOWN_CHAT_TYPE = "ignore_unknown_chat_type"
    IGNORE_BOT_ID_UNAVAILABLE = "ignore_bot_id_unavailable"


def _mentions_bot(mentions: object, bot_open_id: str) -> bool:
    if not isinstance(mentions, list):
        return False
    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        mention_id = mention.get("id")
        if not isinstance(mention_id, dict):
            continue
        if str(mention_id.get("open_id", "")) == bot_open_id:
            return True
    return False


def decide_message_gate(
    *,
    chat_type: object,
    mentions: object,
    bot_open_id: str | None,
) -> MessageGateDecision:
    if chat_type == "p2p":
        return MessageGateDecision.ALLOW_P2P
    if chat_type != "group":
        return MessageGateDecision.IGNORE_UNKNOWN_CHAT_TYPE
    if not bot_open_id:
        return MessageGateDecision.IGNORE_BOT_ID_UNAVAILABLE
    if _mentions_bot(mentions, bot_open_id):
        return MessageGateDecision.ALLOW_GROUP_MENTION
    return MessageGateDecision.IGNORE_GROUP_NO_MENTION

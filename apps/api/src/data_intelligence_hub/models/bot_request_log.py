"""数说 Bot 请求日志模型(迁移 202610310069)。

Stage 3 自进化的统计基座:记录 @数说 的每条消息请求,供「高频请求
≥10 次/周 → 固化为常驻任务」的周聚合统计。最小 schema,不存消息原文。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class BotRequestLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "bot_request_log"
    __table_args__ = (
        Index("ix_bot_request_log_created_at", "created_at"),
        Index("ix_bot_request_log_command", "command"),
    )

    bot: Mapped[str] = mapped_column(String(30), nullable=False, default="shusuo")
    # channel: p2p / group(来自 message.chat_type)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(80), nullable=False)
    open_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    # trigger: message / card_action(未来扩展)
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    # command: 解析出的命令名(help/collect/status/...),未识别也如实记录
    command: Mapped[str] = mapped_column(String(40), nullable=False)
    # argument 截断到 200;不存消息原文
    argument: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "bot": self.bot,
            "channel": self.channel,
            "trigger": self.trigger,
            "command": self.command,
            "created_at": self.created_at.isoformat(),
        }

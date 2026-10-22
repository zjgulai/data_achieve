"""搜索监控。

一个 Monitor 绑定一个端点与一组参数，按固定间隔重跑。
调度复用 CollectionTask：创建 Monitor 时同时建一条启用任务，
任务 config 里带 ``monitor_id``，执行完成后由 monitor_service 判定新结果。

成员与信号：
- 每次有新结果时，用一条合成实体（entity_type=monitor）与快照承载本次计数，
  这样能复用已有的信号、告警规则与通知链路。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Monitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monitors"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String(80), nullable=False)
    params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    # 1 / 6 / 24 小时。与执行任务的 cron 一一对应。
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="enabled", nullable=False)
    # 执行任务的 id。暂停监控时同步暂停它。
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collection_tasks.id"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_new_count: Mapped[int | None] = mapped_column(Integer)

    task = relationship("CollectionTask", foreign_keys=[task_id])

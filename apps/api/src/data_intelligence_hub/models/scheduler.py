from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class SchedulerLease(Base):
    __tablename__ = "scheduler_leases"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SchedulerTick(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scheduler_ticks"

    lease_name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    lock_acquired: Mapped[bool] = mapped_column(Boolean, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_running: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_invalid_schedule: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    task_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_subscriptions_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_subscriptions_due: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_subscriptions_started: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_subscriptions_skipped_running: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    report_subscription_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

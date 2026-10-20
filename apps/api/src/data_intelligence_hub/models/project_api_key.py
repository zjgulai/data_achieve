"""项目级 API 密钥的持久化模型。

一张表保存 MCP 访问密钥。表只存哈希，不存明文。
``key_hash`` 唯一。同一密钥不能登记两次。
密钥归属一个工作区与一个项目。两列建立复合索引，用于隔离查询。

字段对照 PRD 5.7：
``name`` → ``label``；``created_by`` → ``created_by_user_id``。
后者与仓库其他表的命名一致（如 ``dataset_versions.created_by_user_id``）。
``workspace_id``、``key_prefix``、``created_at`` 是 PRD 之外的补充列，
分别用于隔离查询、界面识别与审计。

「每个项目一把密钥」由部分唯一索引保证：
每个项目最多一把未撤销的密钥。已撤销的不计入，因此轮换必须先撤销后签发。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class ProjectApiKey(UUIDPrimaryKeyMixin, Base):
    """一行代表一把项目级 MCP 密钥。

    ``key_prefix`` 是明文的可读前缀，只用于界面识别。
    ``key_hash`` 是明文的 sha256 十六进制摘要。
    ``revoked_at`` 非空表示已撤销。已撤销的密钥不得再通过鉴权。
    """

    __tablename__ = "project_api_keys"
    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_project_api_keys_key_hash"),
        Index("ix_project_api_keys_workspace_project", "workspace_id", "project_id"),
        # 每个项目最多一把未撤销的密钥。Postgres 与 SQLite 都支持部分索引。
        Index(
            "uq_project_api_keys_active_project",
            "project_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # 允许调用的 MCP 工具名。白名单外的工具返回 403 tool_not_allowed。
    # 空列表表示不允许任何工具。签发时必须显式给出。
    tool_allowlist: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # 每日采集额度。超额返回明确错误码。必须为正整数。
    daily_collect_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

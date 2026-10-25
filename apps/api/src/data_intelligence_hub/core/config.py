from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Data Intelligence Hub API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://data_intel:dev_password@localhost:5432/data_intel"

    jwt_secret: str = Field(default="change-me-in-local-env", min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440
    auth_cookie_name: str = "access_token"
    auth_cookie_secure: bool = False

    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_model: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    email_live_send_enabled: bool = False
    email_live_recipient_allowlist: list[str] = []
    email_live_approval_required: bool = True

    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str | None = None

    platform_credential_master_key: SecretStr | None = None
    mcp_token: SecretStr | None = Field(
        default=None,
        validation_alias="SCRAPY_MCP_TOKEN",
    )
    mcp_tokens: dict[str, SecretStr] = Field(
        default_factory=dict,
        validation_alias="SCRAPY_MCP_TOKENS_JSON",
    )
    mcp_rate_per_minute: int = Field(
        default=120,
        ge=1,
        validation_alias="SCRAPY_MCP_RATE_PER_MINUTE",
    )
    mcp_concurrent_calls: int = Field(
        default=8,
        ge=1,
        validation_alias="SCRAPY_MCP_CONCURRENT_CALLS",
    )
    mcp_daily_collects: int = Field(
        default=500,
        ge=1,
        validation_alias="SCRAPY_MCP_DAILY_COLLECTS",
    )
    # collect 与 16 个 TikTok 执行工具的端点级白名单。
    # 默认 None = 允许全部端点（保持现行为，A/B 零变化）。
    # 非空时只允许列出的 endpoint_type，其余返回 tool_not_allowed。
    # 全局 token 不受限：它是运维超级权限。
    mcp_collect_allowed_endpoints: frozenset[str] | None = Field(
        default=None,
        validation_alias="SCRAPY_MCP_COLLECT_ALLOWED_ENDPOINTS",
    )

    dataset_export_dir: str = "tmp/dataset-exports"

    scheduler_enabled: bool = False
    scheduler_poll_interval_seconds: float = Field(default=60.0, gt=0)
    # run_worker_enabled: 是否启动持久运行队列 worker。
    # 默认关闭。测试与本地开发不被后台循环干扰。
    run_worker_enabled: bool = False
    # demo_mode: 允许无 token 请求回退到 demo workspace。
    # None 表示未显式设置，此时按 app_env 推导：生产关闭，其他环境开启。
    # 显式设置 DEMO_MODE=true / false 可覆盖推导结果。
    demo_mode: bool | None = None
    collection_network_mode: Literal["offline", "restricted"] | None = None
    collection_http_grants: list[dict[str, Any]] = Field(default_factory=list)
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def effective_collection_network_mode(self) -> Literal["offline", "restricted"]:
        if self.collection_network_mode is not None:
            return self.collection_network_mode
        return "restricted" if self.app_env == "production" else "offline"

    @property
    def effective_demo_mode(self) -> bool:
        """demo 回退是否启用。

        显式设置优先。未设置时，生产关闭，其他环境开启。
        这条推导保证生产默认为 fail-closed，同时不破坏本地开发与测试。
        """
        if self.demo_mode is not None:
            return self.demo_mode
        return self.app_env != "production"

    @field_validator("cors_origins", "email_live_recipient_allowlist", mode="before")
    @classmethod
    def parse_string_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("mcp_collect_allowed_endpoints", mode="before")
    @classmethod
    def _parse_endpoint_allowlist(cls, value: object) -> object:
        """逗号分隔字符串 → frozenset。空白或空串视为未配置（None）。

        未配置必须与「配了但为空」区分：前者允许全部端点，
        后者若返回空集合会让所有 collect 调用都失败。
        """
        if value is None:
            return None
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",")]
            endpoints = frozenset(item for item in items if item)
            return endpoints or None
        if isinstance(value, frozenset | set | list | tuple):
            endpoints = frozenset(str(item).strip() for item in value if str(item).strip())
            return endpoints or None
        return value

    @field_validator("mcp_token", mode="before")
    @classmethod
    def _blank_mcp_token_is_unset(cls, value: object) -> object:
        """`SCRAPY_MCP_TOKEN=`（空串）必须视为未配置。

        compose 用 `${SCRAPY_MCP_TOKEN:-}` 注入，未配置时会传空字符串；pydantic 会把
        它当成 SecretStr("")，使 accepted_mcp_tokens 非空，从而对**所有人**返回 401
        且任何 token 都无法通过。这里把空白值归一为 None。
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")

    @property
    def accepted_mcp_tokens(self) -> tuple[str, ...]:
        values = [
            secret.get_secret_value()
            for secret in self.mcp_tokens.values()
            if secret.get_secret_value().strip()
        ]
        if self.mcp_token is not None:
            token = self.mcp_token.get_secret_value()
            if token.strip():
                values.append(token)
        return tuple(values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

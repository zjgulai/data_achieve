from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
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

    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str | None = None

    dataset_export_dir: str = "tmp/dataset-exports"

    scheduler_enabled: bool = False
    scheduler_poll_interval_seconds: float = Field(default=60.0, gt=0)
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

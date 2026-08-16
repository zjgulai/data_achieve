from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator


class PlatformCredentialUpdateRequest(BaseModel):
    values: dict[str, SecretStr] = Field(min_length=1, max_length=12)

    @field_validator("values")
    @classmethod
    def validate_values(cls, values: dict[str, SecretStr]) -> dict[str, SecretStr]:
        for key, value in values.items():
            if not key or len(key) > 80 or not key.replace("_", "").isalnum():
                raise ValueError("platform_credential_field_invalid")
            secret = value.get_secret_value()
            if not secret or secret.isspace() or len(secret) > 8192:
                raise ValueError("platform_credential_value_invalid")
        return values


class PlatformCredentialFieldStatus(BaseModel):
    key: str
    label: str
    configured: bool


class PlatformCredentialSettings(BaseModel):
    platform: str
    provider_id: str
    label: str
    auth_mode: str
    fields: list[PlatformCredentialFieldStatus]
    configured: bool
    configured_field_count: int
    updated_at: datetime | None = None
    live_execution_enabled: Literal[False] = False


class PlatformCredentialSettingsResponse(BaseModel):
    schema_version: Literal["platform_credential_settings.v1"] = "platform_credential_settings.v1"
    vault_write_enabled: bool
    provider_call_allowed: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    platforms: list[PlatformCredentialSettings]

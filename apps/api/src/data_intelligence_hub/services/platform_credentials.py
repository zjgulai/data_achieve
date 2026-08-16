from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.platform_credentials import (
    get_platform_credential_bundle,
    list_platform_credential_bundles,
)
from data_intelligence_hub.schemas.platform_credentials import (
    PlatformCredentialFieldStatus,
    PlatformCredentialSettings,
    PlatformCredentialSettingsResponse,
    PlatformCredentialUpdateRequest,
)
from data_intelligence_hub.schemas.social_provider import (
    SocialProviderCatalogItem,
    SocialProviderCatalogResponse,
)

FIELD_LABELS = {
    "access_token": "Access token",
    "api_key": "API key",
    "app_id": "App ID",
    "app_secret": "App secret",
    "bearer_token": "Bearer token",
    "client_id": "Client ID",
    "client_secret": "Client secret",
    "oauth_token": "OAuth token",
    "page_access_token": "Page access token",
    "scope": "OAuth scope",
}

PLATFORM_LABELS = {
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "reddit": "Reddit",
    "threads": "Threads",
    "tiktok": "TikTok Research",
    "x": "X",
    "youtube": "YouTube",
}


class PlatformCredentialError(RuntimeError):
    code = "platform_credential_error"


class PlatformCredentialForbiddenError(PlatformCredentialError):
    code = "platform_credential_forbidden"


class PlatformCredentialPlatformNotFoundError(PlatformCredentialError):
    code = "platform_credential_platform_not_found"


class PlatformCredentialFieldInvalidError(PlatformCredentialError):
    code = "platform_credential_field_invalid"


class PlatformCredentialVaultUnavailableError(PlatformCredentialError):
    code = "platform_credential_vault_unavailable"


class PlatformCredentialPayloadInvalidError(PlatformCredentialError):
    code = "platform_credential_payload_invalid"


@dataclass(frozen=True, slots=True)
class PlatformCredentialCipher:
    _fernet: Fernet = field(repr=False)
    key_version: str = "fernet.v1"

    @classmethod
    def from_secret(cls, secret: SecretStr) -> PlatformCredentialCipher:
        try:
            return cls(_fernet=Fernet(secret.get_secret_value().encode("ascii")))
        except (ValueError, UnicodeEncodeError) as exc:
            raise PlatformCredentialVaultUnavailableError(
                "platform_credential_vault_unavailable"
            ) from exc

    def encrypt(self, values: dict[str, str]) -> str:
        payload = json.dumps(
            values,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return self._fernet.encrypt(payload).decode("ascii")

    def decrypt(self, encrypted_payload: str) -> dict[str, str]:
        try:
            raw = self._fernet.decrypt(encrypted_payload.encode("ascii"))
            payload = json.loads(raw.decode("utf-8"))
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
            raise PlatformCredentialPayloadInvalidError(
                "platform_credential_payload_invalid"
            ) from exc
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
        ):
            raise PlatformCredentialPayloadInvalidError("platform_credential_payload_invalid")
        return payload


def _field_label(key: str) -> str:
    return FIELD_LABELS.get(key, key.replace("_", " ").title())


def _provider_for_platform(
    catalog: SocialProviderCatalogResponse,
    platform: str,
) -> SocialProviderCatalogItem:
    normalized = platform.strip().lower()
    for provider in catalog.providers:
        if provider.platform == normalized:
            return provider
    raise PlatformCredentialPlatformNotFoundError("platform_credential_platform_not_found")


def _assert_owner(user: User, workspace: Workspace) -> None:
    if workspace.owner_id != user.id:
        raise PlatformCredentialForbiddenError("platform_credential_forbidden")


def build_platform_credential_settings(
    *,
    catalog: SocialProviderCatalogResponse,
    bundles: list[PlatformCredentialBundle],
    vault_write_enabled: bool,
) -> PlatformCredentialSettingsResponse:
    bundle_by_provider = {bundle.provider_id: bundle for bundle in bundles}
    platforms: list[PlatformCredentialSettings] = []
    for provider in sorted(catalog.providers, key=lambda item: item.platform):
        bundle = bundle_by_provider.get(provider.provider_id)
        configured_fields = set(bundle.configured_fields if bundle else [])
        fields = [
            PlatformCredentialFieldStatus(
                key=key,
                label=_field_label(key),
                configured=key in configured_fields,
            )
            for key in provider.required_credentials
        ]
        platforms.append(
            PlatformCredentialSettings(
                platform=provider.platform,
                provider_id=provider.provider_id,
                label=PLATFORM_LABELS.get(provider.platform, provider.platform.title()),
                auth_mode=provider.auth_mode,
                fields=fields,
                configured=bool(fields) and all(field.configured for field in fields),
                configured_field_count=sum(field.configured for field in fields),
                updated_at=bundle.updated_at if bundle else None,
            )
        )
    return PlatformCredentialSettingsResponse(
        vault_write_enabled=vault_write_enabled,
        platforms=platforms,
    )


async def list_platform_credentials(
    session: AsyncSession,
    *,
    user: User,
    workspace: Workspace,
    catalog: SocialProviderCatalogResponse,
    vault_write_enabled: bool,
) -> PlatformCredentialSettingsResponse:
    _assert_owner(user, workspace)
    bundles = await list_platform_credential_bundles(session, workspace.id)
    return build_platform_credential_settings(
        catalog=catalog,
        bundles=bundles,
        vault_write_enabled=vault_write_enabled,
    )


async def update_platform_credentials(
    session: AsyncSession,
    *,
    user: User,
    workspace: Workspace,
    platform: str,
    payload: PlatformCredentialUpdateRequest,
    catalog: SocialProviderCatalogResponse,
    cipher: PlatformCredentialCipher,
) -> PlatformCredentialSettings:
    _assert_owner(user, workspace)
    provider = _provider_for_platform(catalog, platform)
    allowed_fields = set(provider.required_credentials)
    requested_fields = set(payload.values)
    if not requested_fields.issubset(allowed_fields):
        raise PlatformCredentialFieldInvalidError("platform_credential_field_invalid")

    bundle = await get_platform_credential_bundle(session, workspace.id, provider.provider_id)
    existing_values = cipher.decrypt(bundle.encrypted_payload) if bundle else {}
    merged_values = {
        **existing_values,
        **{key: value.get_secret_value() for key, value in payload.values.items()},
    }
    encrypted_payload = cipher.encrypt(merged_values)
    configured_fields = sorted(merged_values)
    if bundle is None:
        bundle = PlatformCredentialBundle(
            workspace_id=workspace.id,
            provider_id=provider.provider_id,
            encrypted_payload=encrypted_payload,
            configured_fields=configured_fields,
            key_version=cipher.key_version,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
        )
        session.add(bundle)
    else:
        bundle.encrypted_payload = encrypted_payload
        bundle.configured_fields = configured_fields
        bundle.key_version = cipher.key_version
        bundle.updated_by_user_id = user.id
    await session.commit()
    await session.refresh(bundle)
    response = build_platform_credential_settings(
        catalog=catalog,
        bundles=[bundle],
        vault_write_enabled=True,
    )
    return next(item for item in response.platforms if item.platform == provider.platform)


async def remove_platform_credentials(
    session: AsyncSession,
    *,
    user: User,
    workspace: Workspace,
    platform: str,
    catalog: SocialProviderCatalogResponse,
    vault_write_enabled: bool,
) -> PlatformCredentialSettings:
    _assert_owner(user, workspace)
    provider = _provider_for_platform(catalog, platform)
    bundle = await get_platform_credential_bundle(session, workspace.id, provider.provider_id)
    if bundle is not None:
        await session.delete(bundle)
        await session.commit()
    response = build_platform_credential_settings(
        catalog=catalog,
        bundles=[],
        vault_write_enabled=vault_write_enabled,
    )
    return next(item for item in response.platforms if item.platform == provider.platform)


def platform_credential_reference(bundle: PlatformCredentialBundle) -> str:
    return f"secret:{bundle.id}"


def parse_platform_credential_bundle_id(reference_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(reference_name)
    except ValueError as exc:
        raise PlatformCredentialPayloadInvalidError("platform_credential_payload_invalid") from exc

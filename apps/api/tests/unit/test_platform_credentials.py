from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub import models as _models  # noqa: F401
from data_intelligence_hub.core.config import Settings
from data_intelligence_hub.main import create_app
from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.platform_credentials import (
    get_platform_credential_bundle,
)
from data_intelligence_hub.schemas.platform_credentials import (
    PlatformCredentialUpdateRequest,
)
from data_intelligence_hub.services.platform_credentials import (
    PlatformCredentialCipher,
    PlatformCredentialForbiddenError,
    build_platform_credential_settings,
    list_platform_credentials,
    remove_platform_credentials,
    update_platform_credentials,
)
from data_intelligence_hub.services.social_provider import get_social_provider_catalog


def test_platform_settings_cover_every_catalog_provider_without_reading_secrets() -> None:
    response = build_platform_credential_settings(
        catalog=get_social_provider_catalog(),
        bundles=[],
        vault_write_enabled=True,
    )

    assert [item.platform for item in response.platforms] == [
        "instagram",
        "linkedin",
        "reddit",
        "threads",
        "tiktok",
        "x",
        "youtube",
    ]
    assert all(item.fields for item in response.platforms)
    assert all(not field.configured for item in response.platforms for field in item.fields)
    assert response.provider_call_allowed is False
    assert response.credential_read_attempted is False


def test_ciphertext_round_trip_never_contains_or_represents_plaintext() -> None:
    cipher = PlatformCredentialCipher.from_secret(SecretStr(Fernet.generate_key().decode()))
    values = {
        "client_id": "client-visible-only-during-submit",
        "client_secret": "super-sensitive-value",
    }

    encrypted = cipher.encrypt(values)

    assert "client-visible-only-during-submit" not in encrypted
    assert "super-sensitive-value" not in encrypted
    assert cipher.decrypt(encrypted) == values
    assert "super-sensitive-value" not in repr(cipher)


def test_update_request_masks_secret_values_and_rejects_blank_entries() -> None:
    request = PlatformCredentialUpdateRequest(
        values={"api_key": SecretStr("secret-value")},
    )

    assert "secret-value" not in repr(request)
    assert request.values["api_key"].get_secret_value() == "secret-value"


def test_settings_and_openapi_do_not_expose_vault_or_secret_payloads() -> None:
    settings = Settings(platform_credential_master_key=Fernet.generate_key().decode())
    assert settings.platform_credential_master_key is not None
    assert settings.platform_credential_master_key.get_secret_value() not in repr(settings)

    schema = create_app().openapi()
    path = schema["paths"]["/api/settings/platform-credentials/{platform}"]
    assert set(path) >= {"put", "delete"}
    assert "encrypted_payload" not in str(path)
    assert "platform_credential_bundles" in Base.metadata.tables


async def test_non_owner_is_rejected_before_vault_status_query() -> None:
    user = User(
        id=uuid.uuid4(),
        email="member@example.com",
        password_hash="hash",
        name="Member",
    )
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Vault",
        slug="vault-forbidden",
        owner_id=uuid.uuid4(),
    )
    session = AsyncMock()

    with pytest.raises(PlatformCredentialForbiddenError):
        await list_platform_credentials(
            session,
            user=user,
            workspace=workspace,
            catalog=get_social_provider_catalog(),
            vault_write_enabled=True,
        )

    session.execute.assert_not_awaited()


async def test_owner_can_store_rotate_list_and_remove_without_secret_echo() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_connection: User.__table__.create(sync_connection))
        await connection.run_sync(
            lambda sync_connection: Workspace.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: WorkspaceMember.__table__.create(sync_connection)
        )
        await connection.run_sync(
            lambda sync_connection: PlatformCredentialBundle.__table__.create(sync_connection)
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    cipher = PlatformCredentialCipher.from_secret(SecretStr(Fernet.generate_key().decode()))
    catalog = get_social_provider_catalog()

    async with session_factory() as session:
        user = User(email="vault-owner@example.com", password_hash="hash", name="Owner")
        session.add(user)
        await session.flush()
        workspace = Workspace(name="Vault", slug="vault", owner_id=user.id)
        session.add(workspace)
        await session.flush()
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        await session.commit()

        updated = await update_platform_credentials(
            session,
            user=user,
            workspace=workspace,
            platform="youtube",
            payload=PlatformCredentialUpdateRequest(
                values={"api_key": SecretStr("database-secret-value")},
            ),
            catalog=catalog,
            cipher=cipher,
        )
        assert updated.configured is True
        assert "database-secret-value" not in updated.model_dump_json()

        bundle = await get_platform_credential_bundle(
            session,
            workspace.id,
            "youtube.v3",
        )
        assert bundle is not None
        assert "database-secret-value" not in bundle.encrypted_payload
        assert cipher.decrypt(bundle.encrypted_payload) == {"api_key": "database-secret-value"}

        listed = await list_platform_credentials(
            session,
            user=user,
            workspace=workspace,
            catalog=catalog,
            vault_write_enabled=True,
        )
        youtube = next(item for item in listed.platforms if item.platform == "youtube")
        assert youtube.configured is True
        assert "database-secret-value" not in listed.model_dump_json()

        removed = await remove_platform_credentials(
            session,
            user=user,
            workspace=workspace,
            platform="youtube",
            catalog=catalog,
            vault_write_enabled=True,
        )
        assert removed.configured is False
        assert await get_platform_credential_bundle(session, workspace.id, "youtube.v3") is None

    await engine.dispose()

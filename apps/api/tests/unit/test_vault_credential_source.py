from __future__ import annotations

import json
import pickle
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_intelligence_hub import models as _models  # noqa: F401
from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCredentialResolutionPermit,
    WorkflowExecutionDispatch,
    canonical_workflow_execution_dispatch_key,
    canonical_workflow_provider_side_effect_key,
)
from data_intelligence_hub.services.platform_credentials import PlatformCredentialCipher
from data_intelligence_hub.services.workflow_execution.executor_contract import (
    WorkflowExecutorContractError,
)
from data_intelligence_hub.social_api.contracts import (
    CredentialReference,
    CredentialSource,
    InjectedCredentialResolver,
)
from data_intelligence_hub.social_api.vault_credentials import (
    VaultCredentialHandle,
    VaultCredentialResolutionError,
    VaultCredentialSource,
    vault_credential_reference_fingerprint,
)

NOW = datetime(2026, 7, 29, 1, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
PROVIDER_ID = "youtube.v3"
OPERATION_ID = "youtube.search.list"
PURPOSE = "workflow_provider_call"
FAKE_SECRET = "generated-f4a-secret-value"


def _dispatch(workspace_id: uuid.UUID) -> WorkflowExecutionDispatch:
    project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step_id = uuid.uuid4()
    request_id = uuid.uuid4()
    receipt_id = uuid.uuid4()
    dispatch_key = canonical_workflow_execution_dispatch_key(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        source_action_request_id=request_id,
        source_action_receipt_id=receipt_id,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
    )
    return WorkflowExecutionDispatch(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        source_action_request_id=request_id,
        source_action_receipt_id=receipt_id,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
        dispatch_key=dispatch_key,
        provider_side_effect_key=canonical_workflow_provider_side_effect_key(
            dispatch_key=dispatch_key,
            provider_id=PROVIDER_ID,
            operation_id=OPERATION_ID,
        ),
        state="claimable",
        created_at=NOW,
    )


def _permit(
    dispatch: WorkflowExecutionDispatch,
    reference: CredentialReference,
    *,
    fingerprint: str | None = None,
    purpose: str = PURPOSE,
    provider_id: str = PROVIDER_ID,
    expires_at: datetime | None = None,
) -> WorkflowCredentialResolutionPermit:
    return WorkflowCredentialResolutionPermit(
        id=uuid.uuid4(),
        dispatch_id=dispatch.id,
        workspace_id=dispatch.workspace_id,
        workflow_run_id=dispatch.workflow_run_id,
        workflow_step_run_id=dispatch.workflow_step_run_id,
        attempt_generation=dispatch.attempt_generation,
        provider_id=provider_id,
        operation_id=OPERATION_ID,
        environment="local",
        issued_at=NOW,
        expires_at=expires_at or NOW + timedelta(minutes=5),
        purpose=purpose,
        credential_reference_fingerprint=(
            fingerprint
            or vault_credential_reference_fingerprint(
                workspace_id=dispatch.workspace_id,
                provider_id=PROVIDER_ID,
                purpose=PURPOSE,
                reference=reference,
            )
        ),
    )


@asynccontextmanager
async def _vault_database(
    *,
    provider_id: str = PROVIDER_ID,
    values: dict[str, str] | None = None,
) -> AsyncIterator[
    tuple[
        AsyncEngine,
        AsyncSession,
        PlatformCredentialCipher,
        Workspace,
        PlatformCredentialBundle,
    ]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: User.__table__.create(sync))
        await connection.run_sync(lambda sync: Workspace.__table__.create(sync))
        await connection.run_sync(lambda sync: PlatformCredentialBundle.__table__.create(sync))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    cipher = PlatformCredentialCipher.from_secret(SecretStr(Fernet.generate_key().decode("ascii")))
    async with sessions() as session:
        owner = User(email="f4a-owner@example.com", password_hash="hash", name="Owner")
        session.add(owner)
        await session.flush()
        workspace = Workspace(name="F4A", slug=f"f4a-{uuid.uuid4()}", owner_id=owner.id)
        session.add(workspace)
        await session.flush()
        bundle = PlatformCredentialBundle(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            provider_id=provider_id,
            encrypted_payload=cipher.encrypt(values or {"api_key": FAKE_SECRET}),
            configured_fields=sorted((values or {"api_key": FAKE_SECRET}).keys()),
            key_version=cipher.key_version,
            created_by_user_id=owner.id,
            updated_by_user_id=owner.id,
        )
        session.add(bundle)
        await session.commit()
        try:
            yield engine, session, cipher, workspace, bundle
        finally:
            await session.rollback()
    await engine.dispose()


async def test_exact_secret_reference_resolves_once_without_secret_leakage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with _vault_database() as (_engine, session, cipher, workspace, bundle):
        reference = CredentialReference.parse(f"secret:{bundle.id}")
        dispatch = _dispatch(workspace.id)
        permit = _permit(dispatch, reference)
        source = VaultCredentialSource(
            session=session,
            workspace_id=workspace.id,
            dispatch=dispatch,
            permit=permit,
            operation_id=OPERATION_ID,
            purpose=PURPOSE,
            environment="local",
            cipher=cipher,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        resolver = InjectedCredentialResolver(sources=(source,))

        assert isinstance(source, CredentialSource)
        handle = await resolver.resolve(
            provider_id=PROVIDER_ID,
            credential_reference=reference,
        )

        assert isinstance(handle, VaultCredentialHandle)
        assert handle.credential_permit_id == permit.id
        assert handle.reference_fingerprint == permit.credential_reference_fingerprint
        assert handle.configured_fields == ("api_key",)
        assert handle.reveal_field_for_transport("api_key") == FAKE_SECRET
        assert FAKE_SECRET not in repr(source)
        assert FAKE_SECRET not in repr(handle)
        assert bundle.encrypted_payload not in repr(source)
        assert FAKE_SECRET not in caplog.text
        assert bundle.encrypted_payload not in caplog.text
        with pytest.raises(TypeError):
            json.dumps(handle)
        with pytest.raises(TypeError):
            pickle.dumps(handle)
        assert not session.new and not session.dirty and not session.deleted

        with pytest.raises(VaultCredentialResolutionError) as replay:
            await source.resolve(provider_id=PROVIDER_ID, reference=reference)
        assert str(replay.value) == "vault_credential_source_consumed"

        handle.close()
        assert handle.closed is True
        with pytest.raises(VaultCredentialResolutionError) as closed:
            handle.reveal_field_for_transport("api_key")
        assert str(closed.value) == "vault_credential_handle_closed"


@pytest.mark.parametrize(
    ("permit_change", "expected_code"),
    [
        ({"provider_id": "reddit.oauth"}, "workflow_executor_credential_permit_mismatch"),
        ({"purpose": "other_purpose"}, "workflow_executor_credential_permit_mismatch"),
        (
            {"credential_reference_fingerprint": DIGEST_A},
            "vault_credential_reference_not_authorized",
        ),
    ],
)
async def test_mismatched_permit_stops_before_bundle_read(
    permit_change: dict[str, str],
    expected_code: str,
) -> None:
    from unittest.mock import AsyncMock

    workspace_id = uuid.uuid4()
    dispatch = _dispatch(workspace_id)
    reference = CredentialReference.parse(f"secret:{uuid.uuid4()}")
    permit = _permit(dispatch, reference)
    permit = WorkflowCredentialResolutionPermit.model_validate(
        {**permit.model_dump(), **permit_change}
    )
    session = AsyncMock()
    cipher = PlatformCredentialCipher.from_secret(SecretStr(Fernet.generate_key().decode("ascii")))
    source = VaultCredentialSource(
        session=session,
        workspace_id=workspace_id,
        dispatch=dispatch,
        permit=permit,
        operation_id=OPERATION_ID,
        purpose=PURPOSE,
        environment="local",
        cipher=cipher,
        clock=lambda: NOW + timedelta(seconds=1),
    )

    with pytest.raises(Exception) as exc_info:
        await source.resolve(provider_id=PROVIDER_ID, reference=reference)

    assert str(exc_info.value) == expected_code
    session.execute.assert_not_awaited()


async def test_bundle_provider_mismatch_and_payload_bound_fail_closed() -> None:
    oversized = {f"field_{index}": "value" for index in range(33)}
    async with _vault_database(provider_id="reddit.oauth") as (
        _engine,
        session,
        cipher,
        workspace,
        bundle,
    ):
        reference = CredentialReference.parse(f"secret:{bundle.id}")
        dispatch = _dispatch(workspace.id)
        source = VaultCredentialSource(
            session=session,
            workspace_id=workspace.id,
            dispatch=dispatch,
            permit=_permit(dispatch, reference),
            operation_id=OPERATION_ID,
            purpose=PURPOSE,
            environment="local",
            cipher=cipher,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        with pytest.raises(VaultCredentialResolutionError) as mismatch:
            await source.resolve(provider_id=PROVIDER_ID, reference=reference)
        assert str(mismatch.value) == "vault_credential_bundle_not_authorized"
        assert FAKE_SECRET not in repr(mismatch.value)

    async with _vault_database(values=oversized) as (
        _engine,
        session,
        cipher,
        workspace,
        bundle,
    ):
        reference = CredentialReference.parse(f"secret:{bundle.id}")
        dispatch = _dispatch(workspace.id)
        source = VaultCredentialSource(
            session=session,
            workspace_id=workspace.id,
            dispatch=dispatch,
            permit=_permit(dispatch, reference),
            operation_id=OPERATION_ID,
            purpose=PURPOSE,
            environment="local",
            cipher=cipher,
            clock=lambda: NOW + timedelta(seconds=1),
        )
        with pytest.raises(VaultCredentialResolutionError) as bounded:
            await source.resolve(provider_id=PROVIDER_ID, reference=reference)
        assert str(bounded.value) == "vault_credential_payload_too_large"
        assert not session.new and not session.dirty and not session.deleted


async def test_cipher_key_fields_and_errors_never_expose_fake_secret() -> None:
    mutations = (
        (
            lambda bundle: setattr(bundle, "key_version", "unsupported.v2"),
            VaultCredentialResolutionError,
            "vault_credential_key_version_unsupported",
        ),
        (
            lambda bundle: setattr(bundle, "configured_fields", ["client_secret"]),
            VaultCredentialResolutionError,
            "vault_credential_payload_invalid",
        ),
        (
            lambda bundle: setattr(bundle, "encrypted_payload", "not-fernet"),
            Exception,
            "platform_credential_payload_invalid",
        ),
    )

    for mutate, error_type, expected_code in mutations:
        async with _vault_database() as (
            _engine,
            session,
            cipher,
            workspace,
            bundle,
        ):
            mutate(bundle)
            await session.commit()
            reference = CredentialReference.parse(f"secret:{bundle.id}")
            dispatch = _dispatch(workspace.id)
            source = VaultCredentialSource(
                session=session,
                workspace_id=workspace.id,
                dispatch=dispatch,
                permit=_permit(dispatch, reference),
                operation_id=OPERATION_ID,
                purpose=PURPOSE,
                environment="local",
                cipher=cipher,
                clock=lambda: NOW + timedelta(seconds=1),
            )

            with pytest.raises(error_type) as exc_info:
                await source.resolve(provider_id=PROVIDER_ID, reference=reference)

            assert str(exc_info.value) == expected_code
            assert FAKE_SECRET not in str(exc_info.value)
            assert FAKE_SECRET not in repr(exc_info.value)
            assert not session.new and not session.dirty and not session.deleted


async def test_injected_loader_cannot_cross_the_workspace_boundary() -> None:
    async with _vault_database() as (_engine, session, cipher, workspace, bundle):
        reference = CredentialReference.parse(f"secret:{bundle.id}")
        dispatch = _dispatch(workspace.id)
        cross_workspace_bundle = PlatformCredentialBundle(
            id=bundle.id,
            workspace_id=uuid.uuid4(),
            provider_id=PROVIDER_ID,
            encrypted_payload=bundle.encrypted_payload,
            configured_fields=["api_key"],
            key_version=cipher.key_version,
            created_by_user_id=bundle.created_by_user_id,
            updated_by_user_id=bundle.updated_by_user_id,
        )

        async def wrong_workspace_loader(
            _session: AsyncSession,
            _workspace_id: uuid.UUID,
            _bundle_id: uuid.UUID,
        ) -> PlatformCredentialBundle:
            return cross_workspace_bundle

        source = VaultCredentialSource(
            session=session,
            workspace_id=workspace.id,
            dispatch=dispatch,
            permit=_permit(dispatch, reference),
            operation_id=OPERATION_ID,
            purpose=PURPOSE,
            environment="local",
            cipher=cipher,
            clock=lambda: NOW + timedelta(seconds=1),
            bundle_loader=wrong_workspace_loader,
        )

        with pytest.raises(VaultCredentialResolutionError) as exc_info:
            await source.resolve(provider_id=PROVIDER_ID, reference=reference)

        assert str(exc_info.value) == "vault_credential_workspace_not_authorized"
        assert FAKE_SECRET not in repr(exc_info.value)
        assert not session.new and not session.dirty and not session.deleted


async def test_invalid_reference_and_expired_permit_never_read_bundle() -> None:
    from unittest.mock import AsyncMock

    workspace_id = uuid.uuid4()
    dispatch = _dispatch(workspace_id)
    cipher = PlatformCredentialCipher.from_secret(SecretStr(Fernet.generate_key().decode("ascii")))
    invalid_reference = CredentialReference.parse("secret:not-a-uuid")
    valid_reference = CredentialReference.parse(f"secret:{uuid.uuid4()}")
    cases: tuple[
        tuple[
            CredentialReference,
            WorkflowCredentialResolutionPermit,
            type[Exception],
            str,
        ],
        ...,
    ] = (
        (
            invalid_reference,
            _permit(dispatch, invalid_reference),
            VaultCredentialResolutionError,
            "vault_credential_reference_invalid",
        ),
        (
            valid_reference,
            _permit(dispatch, valid_reference, expires_at=NOW + timedelta(seconds=1)),
            WorkflowExecutorContractError,
            "workflow_executor_credential_permit_expired",
        ),
    )

    for reference, permit, error_type, expected_code in cases:
        session = AsyncMock()
        source = VaultCredentialSource(
            session=session,
            workspace_id=workspace_id,
            dispatch=dispatch,
            permit=permit,
            operation_id=OPERATION_ID,
            purpose=PURPOSE,
            environment="local",
            cipher=cipher,
            clock=lambda: NOW + timedelta(seconds=2),
        )
        with pytest.raises(error_type) as exc_info:
            await source.resolve(provider_id=PROVIDER_ID, reference=reference)
        assert str(exc_info.value) == expected_code
        session.execute.assert_not_awaited()


def test_vault_source_module_has_no_environment_client_or_transport_boundary() -> None:
    import data_intelligence_hub.social_api.vault_credentials as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "os.environ",
        "os.getenv",
        "YOUTUBE_API_KEY",
        "googleapiclient",
        "asyncpraw",
        "requests.",
        "httpx.",
        "WorkflowProviderCallAudit",
        "add_workflow_provider_call_audit",
    )
    assert all(token not in source for token in forbidden)
    assert "provider_call = True" not in source
    assert "network_call = True" not in source


def test_metadata_remains_imported_for_sqlalchemy_relationship_resolution() -> None:
    assert "platform_credential_bundles" in Base.metadata.tables

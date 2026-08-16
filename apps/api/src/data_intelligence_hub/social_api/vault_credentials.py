from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Literal, Never, SupportsIndex

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.platform_credential import PlatformCredentialBundle
from data_intelligence_hub.repositories.platform_credentials import (
    get_platform_credential_bundle_by_id,
)
from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCredentialResolutionPermit,
    WorkflowExecutionDispatch,
)
from data_intelligence_hub.services.platform_credentials import (
    PlatformCredentialCipher,
    PlatformCredentialPayloadInvalidError,
    parse_platform_credential_bundle_id,
)
from data_intelligence_hub.services.workflow_execution.executor_contract import (
    consume_workflow_credential_resolution_permit,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.social_api.contracts import (
    CredentialHandle,
    CredentialReference,
)

MAX_VAULT_CREDENTIAL_FIELDS = 32
MAX_VAULT_CREDENTIAL_FIELD_BYTES = 128
MAX_VAULT_CREDENTIAL_PAYLOAD_BYTES = 65_536
MAX_VAULT_CIPHERTEXT_BYTES = 131_072

CredentialClock = Callable[[], datetime]
CredentialBundleLoader = Callable[
    [AsyncSession, uuid.UUID, uuid.UUID],
    Awaitable[PlatformCredentialBundle | None],
]


class VaultCredentialResolutionError(RuntimeError):
    """A fixed-code failure that never includes credential material."""


class VaultCredentialHandle:
    """One-attempt credential values with explicit discard semantics."""

    __slots__ = (
        "_closed",
        "_credential_permit_id",
        "_reference_fingerprint",
        "_values",
    )

    def __init__(
        self,
        *,
        credential_permit_id: uuid.UUID,
        reference_fingerprint: str,
        values: Mapping[str, str],
    ) -> None:
        self._credential_permit_id = credential_permit_id
        self._reference_fingerprint = reference_fingerprint
        self._values = dict(values)
        self._closed = False

    @property
    def credential_permit_id(self) -> uuid.UUID:
        return self._credential_permit_id

    @property
    def reference_fingerprint(self) -> str:
        return self._reference_fingerprint

    @property
    def configured_fields(self) -> tuple[str, ...]:
        self._require_open()
        return tuple(sorted(self._values))

    @property
    def closed(self) -> bool:
        return self._closed

    def reveal_field_for_transport(self, field_name: str) -> str:
        self._require_open()
        value = self._values.get(field_name)
        if value is None:
            raise VaultCredentialResolutionError("vault_credential_field_unavailable")
        return value

    def close(self) -> None:
        self._values.clear()
        self._closed = True

    def __enter__(self) -> VaultCredentialHandle:
        self._require_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"VaultCredentialHandle(closed={self._closed!r})"

    def __getstate__(self) -> None:
        raise TypeError("vault_credential_handle_not_serializable")

    def __reduce_ex__(self, _protocol: SupportsIndex) -> Never:
        raise TypeError("vault_credential_handle_not_serializable")

    def _require_open(self) -> None:
        if self._closed:
            raise VaultCredentialResolutionError("vault_credential_handle_closed")


def vault_credential_reference_fingerprint(
    *,
    workspace_id: uuid.UUID,
    provider_id: str,
    purpose: str,
    reference: CredentialReference,
) -> str:
    return sha256_id(
        {
            "credential_reference": f"{reference.scheme}:{reference.name}",
            "provider_id": provider_id,
            "purpose": purpose,
            "workspace_id": str(workspace_id),
        }
    )


@dataclass(slots=True)
class VaultCredentialSource:
    session: AsyncSession = field(repr=False)
    workspace_id: uuid.UUID = field(repr=False)
    dispatch: WorkflowExecutionDispatch = field(repr=False)
    permit: WorkflowCredentialResolutionPermit = field(repr=False)
    operation_id: str = field(repr=False)
    purpose: str = field(repr=False)
    environment: str = field(repr=False)
    cipher: PlatformCredentialCipher = field(repr=False)
    clock: CredentialClock = field(repr=False)
    bundle_loader: CredentialBundleLoader = field(
        default=get_platform_credential_bundle_by_id,
        repr=False,
    )
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _consumed: bool = field(default=False, init=False, repr=False)

    scheme: ClassVar[Literal["secret"]] = "secret"

    async def resolve(
        self,
        *,
        provider_id: str,
        reference: CredentialReference,
    ) -> CredentialHandle:
        async with self._lock:
            if self._consumed:
                raise VaultCredentialResolutionError("vault_credential_source_consumed")
            bundle_id = self._validated_bundle_id(
                provider_id=provider_id,
                reference=reference,
            )
            consumed_permit = consume_workflow_credential_resolution_permit(
                self.permit,
                self.dispatch,
                provider_id=provider_id,
                operation_id=self.operation_id,
                purpose=self.purpose,
                environment=self.environment,
                consumed_at=self.clock(),
            )
            self._require_clean_session()
            bundle = await self.bundle_loader(self.session, self.workspace_id, bundle_id)
            if bundle is None:
                raise VaultCredentialResolutionError("vault_credential_bundle_unavailable")
            if bundle.workspace_id != self.workspace_id:
                raise VaultCredentialResolutionError("vault_credential_workspace_not_authorized")
            if bundle.provider_id != provider_id:
                raise VaultCredentialResolutionError("vault_credential_bundle_not_authorized")
            if bundle.key_version != self.cipher.key_version:
                raise VaultCredentialResolutionError("vault_credential_key_version_unsupported")
            if len(bundle.encrypted_payload.encode("utf-8")) > MAX_VAULT_CIPHERTEXT_BYTES:
                raise VaultCredentialResolutionError("vault_credential_payload_too_large")

            values = await asyncio.to_thread(
                self.cipher.decrypt,
                bundle.encrypted_payload,
            )
            try:
                _validate_decrypted_values(
                    values,
                    configured_fields=bundle.configured_fields,
                )
                self._require_clean_session()
                handle = VaultCredentialHandle(
                    credential_permit_id=consumed_permit.id,
                    reference_fingerprint=(consumed_permit.credential_reference_fingerprint),
                    values=values,
                )
            finally:
                values.clear()
            self._consumed = True
            return handle

    def _validated_bundle_id(
        self,
        *,
        provider_id: str,
        reference: CredentialReference,
    ) -> uuid.UUID:
        if reference.scheme != self.scheme:
            raise VaultCredentialResolutionError("vault_credential_reference_not_authorized")
        if self.workspace_id != self.dispatch.workspace_id:
            raise VaultCredentialResolutionError("vault_credential_workspace_not_authorized")
        expected_fingerprint = vault_credential_reference_fingerprint(
            workspace_id=self.workspace_id,
            provider_id=provider_id,
            purpose=self.purpose,
            reference=reference,
        )
        if expected_fingerprint != self.permit.credential_reference_fingerprint:
            raise VaultCredentialResolutionError("vault_credential_reference_not_authorized")
        try:
            return parse_platform_credential_bundle_id(reference.name)
        except PlatformCredentialPayloadInvalidError as exc:
            raise VaultCredentialResolutionError("vault_credential_reference_invalid") from exc

    def _require_clean_session(self) -> None:
        if self.session.new or self.session.dirty or self.session.deleted:
            raise VaultCredentialResolutionError("vault_credential_session_not_clean")


def _validate_decrypted_values(
    values: dict[str, str],
    *,
    configured_fields: list[str],
) -> None:
    if len(values) > MAX_VAULT_CREDENTIAL_FIELDS:
        raise VaultCredentialResolutionError("vault_credential_payload_too_large")
    if set(values) != set(configured_fields):
        raise VaultCredentialResolutionError("vault_credential_payload_invalid")
    total_bytes = 0
    for field_name, value in values.items():
        field_bytes = len(field_name.encode("utf-8"))
        value_bytes = len(value.encode("utf-8"))
        if not field_name or not value or field_bytes > MAX_VAULT_CREDENTIAL_FIELD_BYTES:
            raise VaultCredentialResolutionError("vault_credential_payload_invalid")
        total_bytes += field_bytes + value_bytes
    if total_bytes > MAX_VAULT_CREDENTIAL_PAYLOAD_BYTES:
        raise VaultCredentialResolutionError("vault_credential_payload_too_large")


__all__ = [
    "MAX_VAULT_CIPHERTEXT_BYTES",
    "MAX_VAULT_CREDENTIAL_FIELD_BYTES",
    "MAX_VAULT_CREDENTIAL_FIELDS",
    "MAX_VAULT_CREDENTIAL_PAYLOAD_BYTES",
    "VaultCredentialHandle",
    "VaultCredentialResolutionError",
    "VaultCredentialSource",
    "vault_credential_reference_fingerprint",
]

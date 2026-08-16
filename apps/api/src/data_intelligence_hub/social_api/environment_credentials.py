from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from typing import ClassVar, Literal

from data_intelligence_hub.social_api.contracts import (
    CredentialHandle,
    CredentialReference,
)

EnvironmentLookup = Callable[[str], str | None]
EnvironmentCredentialGrant = tuple[str, str]


class CredentialReferenceNotAuthorizedError(PermissionError):
    """The provider is not authorized to resolve the requested reference."""


class CredentialValueUnavailableError(RuntimeError):
    """The authorized credential reference has no usable value."""


@dataclass(frozen=True, slots=True)
class EnvironmentCredentialHandle:
    reference_fingerprint: str = field(repr=False)
    _secret_value: str = field(repr=False)

    def reveal_for_transport(self) -> str:
        return self._secret_value


@dataclass(frozen=True, slots=True)
class EnvironmentCredentialSource:
    lookup: EnvironmentLookup = field(repr=False)
    grants: frozenset[EnvironmentCredentialGrant] = field(repr=False)
    scheme: ClassVar[Literal["env"]] = "env"

    async def resolve(
        self,
        *,
        provider_id: str,
        reference: CredentialReference,
    ) -> CredentialHandle:
        grant = (provider_id, reference.name)
        if reference.scheme != self.scheme or grant not in self.grants:
            raise CredentialReferenceNotAuthorizedError(
                "credential_reference_not_authorized"
            )

        secret_value = self.lookup(reference.name)
        if secret_value is None or secret_value == "":
            raise CredentialValueUnavailableError("credential_value_unavailable")

        fingerprint_input = f"{provider_id}:{reference.scheme}:{reference.name}"
        return EnvironmentCredentialHandle(
            reference_fingerprint=sha256(fingerprint_input.encode()).hexdigest(),
            _secret_value=secret_value,
        )


__all__ = [
    "CredentialReferenceNotAuthorizedError",
    "CredentialValueUnavailableError",
    "EnvironmentCredentialHandle",
    "EnvironmentCredentialSource",
]

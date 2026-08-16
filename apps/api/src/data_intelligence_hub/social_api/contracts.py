from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from data_intelligence_hub.social_api.output_contracts import (
    PlatformAdapterFixtureRequest,
    PlatformAdapterFixtureResponse,
    PlatformFixtureResponseBuilder,
    PlatformFixtureResponseNormalizer,
    prepare_platform_adapter_fixture_response,
)

CredentialScheme = Literal["env", "secret"]

_CREDENTIAL_REFERENCE = re.compile(
    r"^(?:env:[A-Z][A-Z0-9_]{0,127}|secret:[A-Za-z0-9][A-Za-z0-9_-]{0,127})$"
)


class CredentialReferenceInvalidError(ValueError):
    """The supplied value is not a supported opaque credential reference."""


class CredentialSourceConfigurationError(ValueError):
    """The injected credential source registry is ambiguous."""


class CredentialSourceUnavailableError(RuntimeError):
    """No explicitly injected source can resolve the reference scheme."""


@dataclass(frozen=True, slots=True)
class CredentialReference:
    scheme: CredentialScheme
    name: str = field(repr=False)

    def __post_init__(self) -> None:
        if _CREDENTIAL_REFERENCE.fullmatch(f"{self.scheme}:{self.name}") is None:
            raise CredentialReferenceInvalidError("credential_reference_invalid")

    @classmethod
    def parse(cls, value: str) -> CredentialReference:
        if value.startswith("env:"):
            return cls(scheme="env", name=value.removeprefix("env:"))
        if value.startswith("secret:"):
            return cls(scheme="secret", name=value.removeprefix("secret:"))
        raise CredentialReferenceInvalidError("credential_reference_invalid")


@dataclass(frozen=True)
class SocialAdapterMetadata:
    provider_id: str
    platform: str
    sdk_package: str
    sdk_import_name: str | None
    adapter_module: str
    supports_fixture_replay: bool = True
    supports_live_client: bool = False


@runtime_checkable
class PlatformAdapter(Protocol):
    @property
    def metadata(self) -> SocialAdapterMetadata: ...

    def plan_fixture_operations(
        self,
        *,
        endpoints: list[str],
        fixture_limit: int,
    ) -> list[dict[str, Any]]: ...

    def prepare_fixture_response(
        self,
        request: PlatformAdapterFixtureRequest,
    ) -> PlatformAdapterFixtureResponse: ...


@runtime_checkable
class CredentialHandle(Protocol):
    @property
    def reference_fingerprint(self) -> str: ...


@runtime_checkable
class CredentialSource(Protocol):
    @property
    def scheme(self) -> CredentialScheme: ...

    async def resolve(
        self,
        *,
        provider_id: str,
        reference: CredentialReference,
    ) -> CredentialHandle: ...


@runtime_checkable
class CredentialResolver(Protocol):
    async def resolve(
        self,
        *,
        provider_id: str,
        credential_reference: CredentialReference,
    ) -> CredentialHandle: ...


@dataclass(frozen=True, slots=True)
class InjectedCredentialResolver:
    sources: tuple[CredentialSource, ...] = field(repr=False)

    def __post_init__(self) -> None:
        schemes = [source.scheme for source in self.sources]
        if len(schemes) != len(set(schemes)):
            raise CredentialSourceConfigurationError("credential_source_duplicate")

    async def resolve(
        self,
        *,
        provider_id: str,
        credential_reference: CredentialReference,
    ) -> CredentialHandle:
        for source in self.sources:
            if source.scheme == credential_reference.scheme:
                return await source.resolve(
                    provider_id=provider_id,
                    reference=credential_reference,
                )
        raise CredentialSourceUnavailableError("credential_source_unavailable")


def build_fixture_operations(
    *,
    provider_id: str,
    endpoints: list[str],
    fixture_limit: int,
    sdk_package: str | None,
) -> list[dict[str, Any]]:
    return [
        {
            "operation_id": f"fixture:{provider_id}:{endpoint}",
            "endpoint": endpoint,
            "sdk_package": sdk_package,
            "request_mode": "fixture_replay",
            "fixture_record_count": fixture_limit,
            "provider_call": False,
        }
        for endpoint in endpoints
        if endpoint.strip()
    ]


@dataclass(frozen=True, slots=True)
class FixtureOnlyPlatformAdapter:
    metadata: SocialAdapterMetadata
    fixture_response_builder: PlatformFixtureResponseBuilder = field(repr=False)
    fixture_response_normalizer: PlatformFixtureResponseNormalizer = field(repr=False)

    def plan_fixture_operations(
        self,
        *,
        endpoints: list[str],
        fixture_limit: int,
    ) -> list[dict[str, Any]]:
        return build_fixture_operations(
            provider_id=self.metadata.provider_id,
            endpoints=endpoints,
            fixture_limit=fixture_limit,
            sdk_package=self.metadata.sdk_package,
        )

    def prepare_fixture_response(
        self,
        request: PlatformAdapterFixtureRequest,
    ) -> PlatformAdapterFixtureResponse:
        return prepare_platform_adapter_fixture_response(
            provider_id=self.metadata.provider_id,
            platform=self.metadata.platform,
            request=request,
            response_builder=self.fixture_response_builder,
            response_normalizer=self.fixture_response_normalizer,
        )

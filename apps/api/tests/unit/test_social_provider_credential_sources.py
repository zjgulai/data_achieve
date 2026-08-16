from __future__ import annotations

from dataclasses import dataclass, field
from inspect import signature
from typing import Literal

import pytest

from data_intelligence_hub.social_api.contracts import (
    CredentialHandle,
    CredentialReference,
    CredentialReferenceInvalidError,
    CredentialResolver,
    CredentialSource,
    CredentialSourceConfigurationError,
    CredentialSourceUnavailableError,
    InjectedCredentialResolver,
)
from data_intelligence_hub.social_api.environment_credentials import (
    CredentialReferenceNotAuthorizedError,
    CredentialValueUnavailableError,
    EnvironmentCredentialHandle,
    EnvironmentCredentialSource,
)
from data_intelligence_hub.social_api.youtube.contracts import YouTubeTransportFactory
from data_intelligence_hub.social_api.youtube.foundation import (
    DisabledYouTubeTransportFactory,
    YouTubeLiveExecutionDisabledError,
)


@pytest.mark.parametrize(
    ("raw_reference", "scheme", "name"),
    [
        ("env:YOUTUBE_API_KEY", "env", "YOUTUBE_API_KEY"),
        ("secret:youtube-api-key", "secret", "youtube-api-key"),
    ],
)
def test_credential_reference_is_strict_and_repr_redacted(
    raw_reference: str,
    scheme: str,
    name: str,
) -> None:
    reference = CredentialReference.parse(raw_reference)

    assert reference.scheme == scheme
    assert reference.name == name
    assert name not in repr(reference)


@pytest.mark.parametrize(
    "raw_reference",
    [
        "YOUTUBE_API_KEY",
        "env:youtube_api_key",
        "env:YOUTUBE/API/KEY",
        "secret:youtube/api/key",
        " secret:youtube-api-key",
        "secret:youtube-api-key ",
    ],
)
def test_credential_reference_rejects_non_reference_values(raw_reference: str) -> None:
    with pytest.raises(
        CredentialReferenceInvalidError,
        match="^credential_reference_invalid$",
    ):
        CredentialReference.parse(raw_reference)


@dataclass(frozen=True, slots=True)
class _FakeCredentialHandle:
    reference_fingerprint: str


@dataclass(slots=True)
class _FakeCredentialSource:
    scheme: Literal["env"] = "env"
    calls: list[tuple[str, CredentialReference]] = field(default_factory=list)

    async def resolve(
        self,
        *,
        provider_id: str,
        reference: CredentialReference,
    ) -> CredentialHandle:
        self.calls.append((provider_id, reference))
        return _FakeCredentialHandle(reference_fingerprint="f" * 64)


async def test_injected_resolver_routes_only_to_the_explicit_fake_source() -> None:
    source = _FakeCredentialSource()
    resolver = InjectedCredentialResolver(sources=(source,))
    reference = CredentialReference.parse("env:YOUTUBE_API_KEY")

    assert isinstance(source, CredentialSource)
    assert isinstance(resolver, CredentialResolver)
    assert "sources=" not in repr(resolver)

    handle = await resolver.resolve(
        provider_id="youtube.v3",
        credential_reference=reference,
    )

    assert handle.reference_fingerprint == "f" * 64
    assert source.calls == [("youtube.v3", reference)]


async def test_injected_resolver_fails_closed_for_an_unregistered_source() -> None:
    resolver = InjectedCredentialResolver(sources=())

    with pytest.raises(
        CredentialSourceUnavailableError,
        match="^credential_source_unavailable$",
    ):
        await resolver.resolve(
            provider_id="youtube.v3",
            credential_reference=CredentialReference.parse("secret:youtube-api-key"),
        )


def test_injected_resolver_rejects_duplicate_source_schemes() -> None:
    with pytest.raises(
        CredentialSourceConfigurationError,
        match="^credential_source_duplicate$",
    ):
        InjectedCredentialResolver(
            sources=(_FakeCredentialSource(), _FakeCredentialSource()),
        )


class _PoisonCredentialHandle:
    def __init__(self) -> None:
        self.touched = False

    @property
    def reference_fingerprint(self) -> str:
        self.touched = True
        raise AssertionError("credential_handle_touched")


async def test_disabled_youtube_transport_factory_fails_before_handle_access() -> None:
    credential = _PoisonCredentialHandle()
    factory = DisabledYouTubeTransportFactory()

    assert isinstance(factory, YouTubeTransportFactory)
    with pytest.raises(
        YouTubeLiveExecutionDisabledError,
        match="^youtube_live_execution_disabled$",
    ):
        await factory.create(credential=credential)

    assert credential.touched is False


async def test_environment_source_resolves_only_an_explicit_provider_grant() -> None:
    calls: list[str] = []

    def lookup(name: str) -> str | None:
        calls.append(name)
        return {"YOUTUBE_API_KEY": "secret-value"}.get(name)

    source = EnvironmentCredentialSource(
        lookup=lookup,
        grants=frozenset({("youtube.v3", "YOUTUBE_API_KEY")}),
    )
    reference = CredentialReference.parse("env:YOUTUBE_API_KEY")

    assert isinstance(source, CredentialSource)
    handle = await source.resolve(
        provider_id="youtube.v3",
        reference=reference,
    )

    assert isinstance(handle, CredentialHandle)
    assert isinstance(handle, EnvironmentCredentialHandle)
    assert len(handle.reference_fingerprint) == 64
    assert handle.reveal_for_transport() == "secret-value"
    assert calls == ["YOUTUBE_API_KEY"]
    assert "YOUTUBE_API_KEY" not in repr(source)
    assert "secret-value" not in repr(handle)


def test_environment_source_scheme_cannot_be_overridden_at_construction() -> None:
    assert "scheme" not in signature(EnvironmentCredentialSource).parameters


@pytest.mark.parametrize(
    ("provider_id", "raw_reference"),
    [
        ("reddit.asyncpraw", "env:YOUTUBE_API_KEY"),
        ("youtube.v3", "env:UNAUTHORIZED_API_KEY"),
        ("youtube.v3", "secret:youtube-api-key"),
    ],
)
async def test_environment_source_rejects_ungranted_references_before_lookup(
    provider_id: str,
    raw_reference: str,
) -> None:
    def poison_lookup(name: str) -> str | None:
        raise AssertionError(f"environment_lookup_touched:{name}")

    source = EnvironmentCredentialSource(
        lookup=poison_lookup,
        grants=frozenset({("youtube.v3", "YOUTUBE_API_KEY")}),
    )

    with pytest.raises(
        CredentialReferenceNotAuthorizedError,
        match="^credential_reference_not_authorized$",
    ):
        await source.resolve(
            provider_id=provider_id,
            reference=CredentialReference.parse(raw_reference),
        )


@pytest.mark.parametrize("value", [None, ""])
async def test_environment_source_fails_closed_for_missing_values(
    value: str | None,
) -> None:
    source = EnvironmentCredentialSource(
        lookup=lambda _name: value,
        grants=frozenset({("youtube.v3", "YOUTUBE_API_KEY")}),
    )

    with pytest.raises(
        CredentialValueUnavailableError,
        match="^credential_value_unavailable$",
    ):
        await source.resolve(
            provider_id="youtube.v3",
            reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
        )

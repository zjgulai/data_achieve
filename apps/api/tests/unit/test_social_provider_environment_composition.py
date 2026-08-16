from __future__ import annotations

import pytest

from data_intelligence_hub.social_api.contracts import (
    CredentialReference,
    CredentialResolver,
    CredentialSourceUnavailableError,
)
from data_intelligence_hub.social_api.environment_composition import (
    YOUTUBE_ENVIRONMENT_VARIABLE,
    YOUTUBE_PROVIDER_ID,
    build_youtube_environment_credential_resolver,
)
from data_intelligence_hub.social_api.environment_credentials import (
    CredentialReferenceNotAuthorizedError,
    CredentialValueUnavailableError,
    EnvironmentCredentialHandle,
)


async def test_youtube_environment_composition_reads_the_exact_process_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(YOUTUBE_ENVIRONMENT_VARIABLE, "fixture-secret-value")
    resolver = build_youtube_environment_credential_resolver()

    assert isinstance(resolver, CredentialResolver)
    handle = await resolver.resolve(
        provider_id=YOUTUBE_PROVIDER_ID,
        credential_reference=CredentialReference.parse(
            f"env:{YOUTUBE_ENVIRONMENT_VARIABLE}"
        ),
    )

    assert isinstance(handle, EnvironmentCredentialHandle)
    assert handle.reveal_for_transport() == "fixture-secret-value"
    assert "fixture-secret-value" not in repr(handle)


async def test_youtube_environment_composition_fails_when_variable_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(YOUTUBE_ENVIRONMENT_VARIABLE, raising=False)
    resolver = build_youtube_environment_credential_resolver()

    with pytest.raises(
        CredentialValueUnavailableError,
        match="^credential_value_unavailable$",
    ):
        await resolver.resolve(
            provider_id=YOUTUBE_PROVIDER_ID,
            credential_reference=CredentialReference.parse(
                f"env:{YOUTUBE_ENVIRONMENT_VARIABLE}"
            ),
        )


@pytest.mark.parametrize(
    ("provider_id", "raw_reference", "expected_error", "expected_message"),
    [
        (
            "reddit.asyncpraw",
            "env:YOUTUBE_API_KEY",
            CredentialReferenceNotAuthorizedError,
            "credential_reference_not_authorized",
        ),
        (
            "youtube.v3",
            "env:OPENAI_API_KEY",
            CredentialReferenceNotAuthorizedError,
            "credential_reference_not_authorized",
        ),
        (
            "youtube.v3",
            "secret:youtube-api-key",
            CredentialSourceUnavailableError,
            "credential_source_unavailable",
        ),
    ],
)
async def test_youtube_environment_composition_denies_other_authority_before_lookup(
    provider_id: str,
    raw_reference: str,
    expected_error: type[Exception],
    expected_message: str,
) -> None:
    def poison_lookup(name: str) -> str | None:
        raise AssertionError(f"process_environment_lookup_touched:{name}")

    resolver = build_youtube_environment_credential_resolver(lookup=poison_lookup)

    with pytest.raises(
        expected_error,
        match=f"^{expected_message}$",
    ):
        await resolver.resolve(
            provider_id=provider_id,
            credential_reference=CredentialReference.parse(raw_reference),
        )

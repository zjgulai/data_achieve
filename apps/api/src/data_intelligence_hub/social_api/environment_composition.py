from __future__ import annotations

import os

from data_intelligence_hub.social_api.contracts import InjectedCredentialResolver
from data_intelligence_hub.social_api.environment_credentials import (
    EnvironmentCredentialSource,
    EnvironmentLookup,
)

YOUTUBE_PROVIDER_ID = "youtube.v3"
YOUTUBE_ENVIRONMENT_VARIABLE = "YOUTUBE_API_KEY"


def build_youtube_environment_credential_resolver(
    *,
    lookup: EnvironmentLookup | None = None,
) -> InjectedCredentialResolver:
    environment_lookup = os.environ.get if lookup is None else lookup
    source = EnvironmentCredentialSource(
        lookup=environment_lookup,
        grants=frozenset(
            {(YOUTUBE_PROVIDER_ID, YOUTUBE_ENVIRONMENT_VARIABLE)}
        ),
    )
    return InjectedCredentialResolver(sources=(source,))


__all__ = [
    "YOUTUBE_ENVIRONMENT_VARIABLE",
    "YOUTUBE_PROVIDER_ID",
    "build_youtube_environment_credential_resolver",
]

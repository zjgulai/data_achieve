from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")

PlatformAdapterOutputErrorCode = Literal[
    "platform_adapter_provider_mismatch",
    "platform_adapter_response_invalid",
    "platform_adapter_response_too_large",
]


class PlatformAdapterOutputError(ValueError):
    def __init__(self, code: PlatformAdapterOutputErrorCode) -> None:
        self.code = code
        super().__init__(code)


class PlatformAdapterContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PlatformAdapterFixtureRequest(PlatformAdapterContractModel):
    schema_version: Literal["platform_adapter_fixture_request.v1"] = (
        "platform_adapter_fixture_request.v1"
    )
    provider_id: str = Field(min_length=1, max_length=200)
    operation_id: str = Field(min_length=1, max_length=300)
    endpoint: str = Field(min_length=1, max_length=200)
    fixture_limit: int = Field(ge=1, le=10)
    max_response_bytes: int = Field(ge=1, le=10_000_000)

    @model_validator(mode="after")
    def validate_identity(self) -> PlatformAdapterFixtureRequest:
        values = (self.provider_id, self.operation_id, self.endpoint)
        if any(_IDENTIFIER.fullmatch(value) is None for value in values):
            raise ValueError("platform_adapter_request_identity_invalid")
        expected_operation_id = f"fixture:{self.provider_id}:{self.endpoint}"
        if self.operation_id != expected_operation_id:
            raise ValueError("platform_adapter_request_operation_mismatch")
        return self


class PlatformAdapterNormalizedRecord(PlatformAdapterContractModel):
    schema_version: Literal["platform_adapter_normalized_record.v1"] = (
        "platform_adapter_normalized_record.v1"
    )
    raw_record_id: str = Field(min_length=1, max_length=500)
    provider_id: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=100)
    endpoint: str = Field(min_length=1, max_length=200)
    source_ref: str = Field(min_length=1, max_length=500)
    evidence_ref: str = Field(min_length=1, max_length=2000)
    record_type: Literal["post", "comment"]
    external_post_id: str = Field(min_length=1, max_length=500)
    external_comment_id: str | None = Field(default=None, min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=5000)
    metrics: dict[str, JsonValue]
    payload_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    provider_call_attempted: Literal[False] = False

    @model_validator(mode="after")
    def validate_record_type(self) -> PlatformAdapterNormalizedRecord:
        if self.record_type == "comment" and self.external_comment_id is None:
            raise ValueError("platform_adapter_comment_identity_missing")
        if self.record_type == "post" and self.external_comment_id is not None:
            raise ValueError("platform_adapter_post_comment_identity_unexpected")
        return self


class PlatformAdapterFixtureResponse(PlatformAdapterContractModel):
    schema_version: Literal["platform_adapter_fixture_response.v1"] = (
        "platform_adapter_fixture_response.v1"
    )
    request: PlatformAdapterFixtureRequest
    provider_id: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=100)
    response_size_bytes: int = Field(ge=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=10)
    records: tuple[PlatformAdapterNormalizedRecord, ...] = Field(min_length=1, max_length=10)
    provider_call_attempted: Literal[False] = False

    @model_validator(mode="after")
    def validate_response(self) -> PlatformAdapterFixtureResponse:
        if self.provider_id != self.request.provider_id:
            raise ValueError("platform_adapter_response_provider_mismatch")
        if self.response_size_bytes > self.request.max_response_bytes:
            raise ValueError("platform_adapter_response_size_invalid")
        if len(self.records) > self.request.fixture_limit:
            raise ValueError("platform_adapter_response_record_limit_exceeded")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("platform_adapter_evidence_duplicate")
        if self.evidence_refs != tuple(record.evidence_ref for record in self.records):
            raise ValueError("platform_adapter_evidence_mismatch")
        for record in self.records:
            if (
                record.provider_id != self.provider_id
                or record.platform != self.platform
                or record.endpoint != self.request.endpoint
            ):
                raise ValueError("platform_adapter_record_identity_mismatch")
        return self


class PlatformFixtureResponseBuilder(Protocol):
    def __call__(self, *, endpoint: str, fixture_limit: int) -> JsonValue: ...


class PlatformFixtureResponseNormalizer(Protocol):
    def __call__(
        self,
        *,
        endpoint: str,
        response_payload: JsonValue,
        evidence_refs: tuple[str, ...],
    ) -> tuple[PlatformAdapterNormalizedRecord, ...]: ...


def canonical_platform_payload_digest(payload: JsonValue) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def prepare_platform_adapter_fixture_response(
    *,
    provider_id: str,
    platform: str,
    request: PlatformAdapterFixtureRequest,
    response_builder: PlatformFixtureResponseBuilder,
    response_normalizer: PlatformFixtureResponseNormalizer,
) -> PlatformAdapterFixtureResponse:
    if request.provider_id != provider_id:
        raise PlatformAdapterOutputError("platform_adapter_provider_mismatch")

    try:
        response_payload = response_builder(
            endpoint=request.endpoint,
            fixture_limit=request.fixture_limit,
        )
        encoded = json.dumps(
            response_payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except Exception:
        raise PlatformAdapterOutputError("platform_adapter_response_invalid") from None

    if len(encoded) > request.max_response_bytes:
        raise PlatformAdapterOutputError("platform_adapter_response_too_large")

    evidence_refs = tuple(
        f"fixture://{provider_id}/{request.endpoint}/{index}"
        for index in range(1, request.fixture_limit + 1)
    )
    try:
        records = response_normalizer(
            endpoint=request.endpoint,
            response_payload=response_payload,
            evidence_refs=evidence_refs,
        )
        return PlatformAdapterFixtureResponse(
            request=request,
            provider_id=provider_id,
            platform=platform,
            response_size_bytes=len(encoded),
            evidence_refs=evidence_refs,
            records=records,
        )
    except (PlatformAdapterOutputError, ValidationError):
        raise PlatformAdapterOutputError("platform_adapter_response_invalid") from None
    except Exception:
        raise PlatformAdapterOutputError("platform_adapter_response_invalid") from None


__all__ = [
    "PlatformAdapterFixtureRequest",
    "PlatformAdapterFixtureResponse",
    "PlatformAdapterNormalizedRecord",
    "PlatformAdapterOutputError",
    "PlatformAdapterOutputErrorCode",
    "PlatformFixtureResponseBuilder",
    "PlatformFixtureResponseNormalizer",
    "canonical_platform_payload_digest",
    "prepare_platform_adapter_fixture_response",
]

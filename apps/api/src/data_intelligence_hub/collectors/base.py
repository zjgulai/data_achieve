from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

HTTP_TIMEOUT_SECONDS = 10.0
HTTP_USER_AGENT = "DataIntelligenceHub/0.1 (+https://localhost)"
HTTP_HEADERS = {"User-Agent": HTTP_USER_AGENT, "Accept": "application/json, text/html"}

JsonContent = dict[str, Any] | list[Any]


class CollectorError(Exception):
    pass


@dataclass(frozen=True)
class CollectorRawRecord:
    record_type: str
    source_url: str | None
    content: JsonContent
    screenshot_url: str | None = None
    collected_at: datetime | None = None


@dataclass(frozen=True)
class CollectorTestResult:
    status: Literal["ok", "failed"]
    message: str
    logs: list[dict[str, Any]]


@dataclass(frozen=True)
class CollectionResult:
    raw_records: list[CollectorRawRecord]
    logs: list[dict[str, Any]]
    errors: list[str]


class BaseCollector(ABC):
    collector_type: str

    def __init__(
        self,
        config: dict[str, Any],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.http_client = http_client

    @abstractmethod
    def validate_config(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def test(self) -> CollectorTestResult:
        raise NotImplementedError

    @abstractmethod
    async def collect(self) -> CollectionResult:
        raise NotImplementedError

    def normalize(self, raw_record: CollectorRawRecord) -> list[dict[str, Any]]:
        return []


def collector_log(step: str, message: str, level: str = "info") -> dict[str, Any]:
    return {
        "step": step,
        "message": message,
        "level": level,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def require_text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise CollectorError(f"Collector config field is required: {key}")
    return value.strip()

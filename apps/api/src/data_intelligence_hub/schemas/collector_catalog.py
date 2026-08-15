from __future__ import annotations

from pydantic import BaseModel, Field


class CollectorEndpointMetadata(BaseModel):
    """Single endpoint capability within a collector."""

    endpoint_type: str = Field(description="Unique endpoint identifier")
    label: str = Field(description="Human-readable name")
    platform: str = Field(description="Target platform (tiktok, instagram, etc.)")
    description: str = Field(description="What this endpoint does")
    status: str = Field(
        default="verified", description="verified | pending | disabled"
    )
    required_params: list[str] = Field(default_factory=list)
    optional_params: list[str] = Field(default_factory=list)
    cost_hint: str | None = Field(default=None, description="Estimated cost per item")
    provider: str = Field(description="TikHub REST API, Apify Actor, etc.")
    content_type: str = Field(
        default="post",
        description=(
            "Content category on the platform: "
            "post | comment | account | product | review | ad | "
            "job | news | trend | ai_answer | repo | feed | web_page"
        ),
    )
    method: str = Field(
        default="tikhub",
        description=(
            "Collection method / service tier: "
            "tikhub | apify | github_api | rss | web_crawl"
        ),
    )


class CollectorCatalogEntry(BaseModel):
    """Top-level collector with all its endpoints."""

    collector_type: str = Field(description="Collector type from registry")
    label: str = Field(description="Human-readable collector name")
    platform: str = Field(description="Primary platform family")
    endpoints: list[CollectorEndpointMetadata] = Field(default_factory=list)


class CollectorCatalogResponse(BaseModel):
    """Full catalog response."""

    collectors: list[CollectorCatalogEntry]

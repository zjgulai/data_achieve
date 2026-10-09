from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

Action = Literal["search", "hashtag", "user_posts", "top_ads", "creator", "live", "sentiment"]
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class TikTokIntent:
    action: Action
    keyword: str = ""
    username: str = ""
    limit: int = 10


class CollectRequest(TypedDict):
    project_id: str
    endpoint_type: str
    params: dict[str, JsonValue]

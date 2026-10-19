"""数说机器人的运行配置。

所有值来自环境变量。未配置 App ID / Secret 时，webhook 仍然返回 200，
但不会处理消息；`GET /api/agents/shusuo/health` 会报 ready=false。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_PROJECT_ID = "7fd6ed55-7b0c-5482-92f3-d03130168b70"
DEFAULT_CONSOLE_BASE_URL = "https://scrapy.luteos.com"


def _split_csv(value: str) -> frozenset[str]:
    return frozenset(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class ShushuoConfig:
    app_id: str
    app_secret: str
    verification_token: str
    encrypt_key: str
    default_project_id: str
    console_base_url: str
    allowed_open_ids: frozenset[str]

    @property
    def ready(self) -> bool:
        return bool(self.app_id and self.app_secret)

    @property
    def encrypt_enabled(self) -> bool:
        return bool(self.encrypt_key)


@lru_cache(maxsize=1)
def get_shushuo_config() -> ShushuoConfig:
    return ShushuoConfig(
        app_id=os.environ.get("LARK_SHUSUO_APP_ID", "").strip(),
        app_secret=os.environ.get("LARK_SHUSUO_APP_SECRET", "").strip(),
        verification_token=os.environ.get("LARK_SHUSUO_VERIFICATION_TOKEN", "").strip(),
        encrypt_key=os.environ.get("LARK_SHUSUO_ENCRYPT_KEY", "").strip(),
        default_project_id=(
            os.environ.get("SHUSUO_DEFAULT_PROJECT_ID", "").strip() or DEFAULT_PROJECT_ID
        ),
        console_base_url=(
            os.environ.get("SHUSUO_CONSOLE_BASE_URL", "").strip() or DEFAULT_CONSOLE_BASE_URL
        ).rstrip("/"),
        allowed_open_ids=_split_csv(os.environ.get("SHUSUO_ALLOWED_OPEN_IDS", "")),
    )

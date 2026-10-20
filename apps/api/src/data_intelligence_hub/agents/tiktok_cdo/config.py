from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class TikTokCDOConfig:
    # 飞书应用
    lark_app_id: str
    lark_app_secret: str
    lark_verification_token: str
    lark_encrypt_key: str

    # DeepSeek
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str

    # Exa.ai
    exa_api_key: str

    # 内部 API
    internal_api_base: str

    # 工具层路由
    project_id: str
    tool_routing: str
    tool_actions: tuple[str, ...]
    tool_timeout_seconds: float

    # 多维表格（可选，导出用）
    bitable_app_token: str
    bitable_table_id: str


def _tool_actions() -> tuple[str, ...]:
    raw = os.environ.get("LARK_CDO_TOOL_ACTIONS", "search,hashtag,user_posts,creator,followers")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@lru_cache(maxsize=1)
def get_cdo_config() -> TikTokCDOConfig:
    return TikTokCDOConfig(
        lark_app_id=os.environ.get("LARK_CDO_APP_ID", ""),
        lark_app_secret=os.environ.get("LARK_CDO_APP_SECRET", ""),
        lark_verification_token=os.environ.get("LARK_CDO_VERIFICATION_TOKEN", ""),
        lark_encrypt_key=os.environ.get("LARK_CDO_ENCRYPT_KEY", ""),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        exa_api_key=os.environ.get("EXA_API_KEY", ""),
        internal_api_base=os.environ.get("INTERNAL_API_BASE", "http://localhost:8000"),
        project_id=os.environ.get(
            "LARK_CDO_PROJECT_ID", "7fd6ed55-7b0c-5482-92f3-d03130168b70"
        ),
        tool_routing=os.environ.get("LARK_CDO_TOOL_ROUTING", "hybrid").strip().lower(),
        tool_actions=_tool_actions(),
        tool_timeout_seconds=float(
            os.environ.get("LARK_CDO_TOOL_TIMEOUT_SECONDS", "90")
        ),
        bitable_app_token=os.environ.get("LARK_CDO_BITABLE_APP_TOKEN", ""),
        bitable_table_id=os.environ.get("LARK_CDO_BITABLE_TABLE_ID", ""),
    )

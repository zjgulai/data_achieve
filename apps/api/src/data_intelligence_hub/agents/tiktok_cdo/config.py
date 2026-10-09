from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TikTokCDOSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    lark_cdo_app_id: str = ""
    lark_cdo_app_secret: str = ""
    lark_cdo_verification_token: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    internal_api_base: str = "http://127.0.0.1:8000"
    lark_cdo_project_id: str = "7fd6ed55-7b0c-5482-92f3-d03130168b70"


@lru_cache(maxsize=1)
def get_cdo_settings() -> TikTokCDOSettings:
    return TikTokCDOSettings()

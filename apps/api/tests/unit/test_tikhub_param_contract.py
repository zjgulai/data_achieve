"""TikHub 端点参数契约。

`services/collector_catalog.py` 的 `_validate_tikhub_social_config` 用一份**白名单**
过滤 quick-collect 传来的参数，而 `_build_params` 按 endpoint_type 从 config 里取键。
两者一旦不一致，被漏掉的键会被**静默丢成空串**，上游再报一个看不出原因的参数错误。

2026-10-09 实测：`tikhub_reddit_subreddit_posts` 的 `subreddit` 不在白名单，
`_build_params` 传出 `subreddit_name=""` → 上游 422 "subreddit_name too short"。
同批被发现漏掉的键还有 `channel_id` / `aweme_id` / `keywords` / `post_urn` 等。
"""

from __future__ import annotations

import inspect
import re

import pytest

from data_intelligence_hub.collectors.tikhub_social import (
    _TIKHUB_POST_ENDPOINTS,
    TIKHUB_ENDPOINT_MAP,
    _build_params,
)
from data_intelligence_hub.services.collector_catalog import (
    _validate_tikhub_social_config,
)

PROBE = "probe-value"


def _read_keys() -> set[str]:
    """_build_params 里所有 ``config.get("X")`` 的键。"""
    src = inspect.getsource(_build_params)
    return set(re.findall(r'config\.get\("([a-z_0-9]+)"\)', src))


def test_build_params_reads_at_least_one_key() -> None:
    assert _read_keys(), "解析 _build_params 失败，契约测试失去意义"


@pytest.mark.parametrize("key", sorted(_read_keys()))
def test_every_key_build_params_reads_survives_the_whitelist(key: str) -> None:
    validated = _validate_tikhub_social_config(
        {"endpoint_type": "tikhub_tiktok_video_search", key: PROBE}
    )
    assert key in validated, f"白名单丢掉了 _build_params 会读取的键: {key}"
    assert validated[key] == PROBE


def test_post_endpoints_are_all_known_endpoints() -> None:
    unknown = _TIKHUB_POST_ENDPOINTS - set(TIKHUB_ENDPOINT_MAP)
    assert not unknown, f"_TIKHUB_POST_ENDPOINTS 指向未知端点: {sorted(unknown)}"


def test_weibo_user_posts_uses_the_v2_path() -> None:
    """旧路径 /weibo/web/fetch_user_posts 在官方 OpenAPI 里不存在（实测 404）。"""
    path, _record_type, _platform = TIKHUB_ENDPOINT_MAP["tikhub_weibo_user_posts"]
    assert path == "/api/v1/weibo/web_v2/fetch_user_posts"


def test_post_only_endpoints_are_declared_post() -> None:
    """这三个端点在官方 spec 里只注册了 POST，用 GET 会得到 405/422。"""
    assert {
        "tikhub_wechat_search",
        "tikhub_tiktok_ads_search",
        "tikhub_wechat_channels_video",
    } <= _TIKHUB_POST_ENDPOINTS

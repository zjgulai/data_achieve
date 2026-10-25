"""采集器视角的参数契约。

预检不能只看目录：目录声明与采集器实现会漂移。

- 目录（`PackageEndpoint.required_params/optional_params`）是给控制台看的公告。
- 采集器（`collectors/tikhub_social.py`）决定参数是否被读取、是否被白名单保留。

2026-10 final review 抓到的硬漂移：

- `tikhub_bilibili_comments`：目录 `oid`，采集器读 `bvid|video_id`。
- `tikhub_tiktok_ads_search`：目录 `keyword`，采集器读 `material_id`。
- `tikhub_tiktok_creator_info` / `tikhub_tiktok_live_user`：目录 `unique_id`，
  采集器读 `creator_uid`。

本模块把「采集器真的会读这个端点上的哪些键」和「采集器声明的必填别名组」
抽出来，供 `capabilities.preflight_proposal` 使用。数据来源是采集器本身，
不是另抄一份：`_TIKHUB_REQUIRED_PARAMS` 直接复用，读取键由
`_build_params` 的记录式调用现场采集。
"""

from __future__ import annotations

import contextlib
import functools
from dataclasses import dataclass
from typing import Any

from data_intelligence_hub.collectors.endpoint_catalog import _ENDPOINT_TO_COLLECTOR

TIKHUB_COLLECTOR = "tikhub_social"

# 目录与采集器已知不一致、必须按采集器口径收敛的端点。
# 只在这里列出的端点会丢弃「目录声明但采集器不读」的键；
# 其余端点保持目录声明不变，避免把潜在有用的转发参数一并拒掉。
DRIFT_ENDPOINTS: frozenset[str] = frozenset(
    {
        "tikhub_bilibili_comments",
        "tikhub_tiktok_ads_search",
        "tikhub_tiktok_creator_info",
        "tikhub_tiktok_live_user",
    }
)

# 探测 `_build_params` 时回给每个 `config.get` 的值。
# 必须是假值：`config.get("keyword") or config.get("query")` 这类回退链在真值处
# 会短路，真值探测只能采到链上第一个键。假值让整条链全部走完，
# 一次拿到该端点分支上的完整读取集合。
_PROBE_VALUE = ""


@dataclass(frozen=True)
class ParamContract:
    """一个端点的参数契约。

    accepted：预检允许出现的键（端点级，不是全局放行）。
    required_groups：每组内部任一键有值即算满足，组与组之间全部必填。
    """

    accepted: frozenset[str]
    required_groups: tuple[tuple[str, ...], ...]


def is_tikhub_endpoint(endpoint_type: str) -> bool:
    return _ENDPOINT_TO_COLLECTOR.get(endpoint_type) == TIKHUB_COLLECTOR


class _RecordingConfig(dict[str, Any]):
    """记录 `_build_params` 读了哪些 config 键的最小映射。

    除 `endpoint_type` 外，所有 `.get()` 都返回假值哨兵并留痕，
    从而把整条 `or` 回退链上的候选键一次采全。
    """

    def __init__(self, endpoint_type: str) -> None:
        super().__init__({"endpoint_type": endpoint_type})
        self.endpoint_type = endpoint_type
        self.reads: list[str] = []

    def __getitem__(self, key: str) -> Any:
        if key == "endpoint_type":
            return self.endpoint_type
        return self.get(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "endpoint_type":
            return self.endpoint_type
        self.reads.append(key)
        return _PROBE_VALUE


@functools.lru_cache(maxsize=512)
def collector_read_keys(endpoint_type: str) -> frozenset[str]:
    """该端点的 `_build_params` 实际读取的 config 键。

    采集器抛错（例如缺 creator cookie）不影响已记录到的读取键。
    """
    from data_intelligence_hub.collectors.tikhub_social import _build_params

    config = _RecordingConfig(endpoint_type)
    # 只为采键：采集器在该端点的自身错误（例如缺 creator cookie）不属预检职责。
    with contextlib.suppress(Exception):
        _build_params(config, 1)
    return frozenset(config.reads)


def required_groups_for(endpoint_type: str) -> tuple[tuple[str, ...], ...]:
    """采集器声明的必填参数组（组内别名任一满足即可）。"""
    if not is_tikhub_endpoint(endpoint_type):
        return ()
    from data_intelligence_hub.collectors.tikhub_social import _TIKHUB_REQUIRED_PARAMS

    return _TIKHUB_REQUIRED_PARAMS.get(endpoint_type, ())


def contract_for(
    endpoint_type: str, required_params: tuple[str, ...], optional_params: tuple[str, ...]
) -> ParamContract:
    """把目录声明与采集器实现合成端点级契约。"""
    declared = set(required_params) | set(optional_params)
    if not is_tikhub_endpoint(endpoint_type):
        return ParamContract(
            accepted=frozenset(declared),
            required_groups=tuple((key,) for key in required_params),
        )

    reads = collector_read_keys(endpoint_type)
    if endpoint_type in DRIFT_ENDPOINTS:
        # 漂移端点：目录声明不可信，只保留采集器真的会读的键。
        declared &= reads
    accepted = declared | reads

    groups = list(required_groups_for(endpoint_type))
    covered = {key for group in groups for key in group}
    # 目录额外要求、采集器没有归组的键仍然必填（例如账号健康检查的 unique_id）。
    groups.extend(
        (key,) for key in required_params if key in accepted and key not in covered
    )
    return ParamContract(accepted=frozenset(accepted), required_groups=tuple(groups))


# ---------------------------------------------------------------------------
# 用户可见的契约视图
# ---------------------------------------------------------------------------

_FREE_REQUIRED_TEXT = "无"


@dataclass(frozen=True)
class ContractView:
    """「能力」「详情」渲染用的参数视图。

    required_text：必填别名组，组内写 `bvid 或 video_id`，组间用 `；`。
    optional_keys：预检真正接受、又没被任何必填组覆盖的键（排序后）。
    """

    required_text: str
    optional_keys: tuple[str, ...]


def contract_view(
    endpoint_type: str, required_params: tuple[str, ...], optional_params: tuple[str, ...]
) -> ContractView:
    """帮助文案唯一的参数来源：与 `preflight_proposal` 共用同一份契约。

    目录声明不能直接渲染：四个漂移端点会把采集器不读的键（`oid`、`unique_id`、
    `keyword`）宣传成可用参数，用户照着填必然被预检拒绝。
    """
    contract = contract_for(endpoint_type, required_params, optional_params)
    groups = contract.required_groups
    required_text = (
        "；".join(" 或 ".join(group) for group in groups) if groups else _FREE_REQUIRED_TEXT
    )
    covered = {key for group in groups for key in group}
    return ContractView(
        required_text=required_text,
        optional_keys=tuple(sorted(contract.accepted - covered)),
    )


# ---------------------------------------------------------------------------
# Actor 侧的结果数量上限
# ---------------------------------------------------------------------------

# Actor 侧限制产出的数量键。其中 `maxItems` 与 Apify 采集开关同名，
# 调用方传的值会被 `_APIFY_META_KEYS` 剥掉，到不了 Actor input。
ACTOR_RESULT_LIMIT_KEYS: frozenset[str] = frozenset(
    {"maxItems", "resultsPerPage", "resultsLimit"}
)


def actor_result_cap(endpoint_type: str) -> int | None:
    """该端点 Actor 缺省 input 钉住的结果数量上限；没有就是 None。

    直接读 `_APIFY_ENDPOINT_DEFAULTS`，不另抄数字：`apify_twitter_user_scraper`
    的缺省 input 就是 `maxItems: 3`，调用方传 10 也只能拿到 3 条。
    """
    from data_intelligence_hub.collectors.endpoint_catalog import (
        _APIFY_ENDPOINT_DEFAULTS,
    )

    defaults = _APIFY_ENDPOINT_DEFAULTS.get(endpoint_type)
    if defaults is None:
        return None
    _, base_input = defaults
    caps = [
        value
        for key, value in base_input.items()
        if key in ACTOR_RESULT_LIMIT_KEYS
        and isinstance(value, int)
        and not isinstance(value, bool)
    ]
    return min(caps) if caps else None

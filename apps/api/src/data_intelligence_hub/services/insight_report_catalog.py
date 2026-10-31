"""分析类型注册表。

类型来自代码，不建表。当前只有一个类型，没有管理界面，也没有按工作区
启停的需求；超过 3 个类型或需要按工作区配置时再加表（设计文档 §3.2）。
"""

from __future__ import annotations

from dataclasses import dataclass

# 数据源状态说明。它不是实时探测：描述的是“生成这份报告的数据源没有
# 接入生产”，不声称此刻的网络状态。页面用中性说明，不渲染成红灯错误。
SOURCE_NOT_CONNECTED_REASON = (
    "数据源未连接，无法生成新报告。当前只能查看归档报告。"
)


@dataclass(frozen=True)
class InsightAnalysisTypeSpec:
    key: str
    name: str
    description: str


INSIGHT_ANALYSIS_TYPES: tuple[InsightAnalysisTypeSpec, ...] = (
    InsightAnalysisTypeSpec(
        key="tiktok_viral_topic",
        name="TikTok 爆款选题分析",
        description=(
            "对已爆母婴与喂养视频做主题、吸引机制、可复刻性和评论需求分析。"
        ),
    ),
)

_ANALYSIS_TYPES_BY_KEY = {spec.key: spec for spec in INSIGHT_ANALYSIS_TYPES}


def get_analysis_type(key: str) -> InsightAnalysisTypeSpec | None:
    return _ANALYSIS_TYPES_BY_KEY.get(key)


def is_registered_analysis_type(key: str) -> bool:
    return key in _ANALYSIS_TYPES_BY_KEY

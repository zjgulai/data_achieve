"""工具的执行可达性。

参数契约登记的是「实现要求什么参数」，那是实现层的事实。
但一个类型还可能被出口策略拦下——`assert_collector_allowed` 在类级
`validate_config` **之前**执行，所以对这类类型，参数规格描述的是一段
永远走不到的代码（除非直接实例化采集器）。

本模块把两件事分开记录：

- 规格照实登记实现约束，不因为不可执行就不写。
- 可达性单独可查，避免消费方把「必填」误读成「能跑」。

2026-10-16 实测：86 个采集器类型中 53 个是 `unsupported`，
策略层无条件拒绝，与网络模式无关。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.collectors.outbound_policy import (
    CollectionPolicyDenied,
    assert_collector_allowed,
    execution_kind,
)

ToolExecutionKind = Literal["offline", "guarded_http", "provider_api", "unsupported"]


class ToolReachability(BaseModel):
    """一个类型在策略层是否可执行。

    ``execution_kind`` 是静态归类，与运行环境无关。
    ``allowed_now`` 还包含环境因素：``guarded_http`` 与 ``provider_api``
    在离线模式下会被拒，切到受限联网即放行；
    ``unsupported`` 则任何模式都拒。
    """

    model_config = ConfigDict(frozen=True)

    tool_id: str
    execution_kind: ToolExecutionKind
    allowed_now: bool
    block_reason: str | None = None

    @property
    def permanently_blocked(self) -> bool:
        """策略层无条件拒绝，切换网络模式也不会放行。"""
        return self.execution_kind == "unsupported"


def execution_reachability(tool_id: str) -> ToolReachability:
    """查询一个类型的执行可达性。

    未注册的类型会得到 ``unsupported``——策略层就是这样对待未知类型的，
    这里不另造一套判断。
    """
    kind = execution_kind(tool_id)
    try:
        assert_collector_allowed(tool_id)
    except CollectionPolicyDenied as exc:
        return ToolReachability(
            tool_id=tool_id,
            execution_kind=kind,
            allowed_now=False,
            block_reason=str(exc),
        )
    return ToolReachability(tool_id=tool_id, execution_kind=kind, allowed_now=True)

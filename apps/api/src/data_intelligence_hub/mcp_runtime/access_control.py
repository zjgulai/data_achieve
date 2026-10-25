"""N1 统一授权入口。

governed_mcp_tool 把白名单、项目绑定、对象归属、额度扣减与审计元数据
集中到一个异步上下文管理器。工具实现只处理业务参数。

全局 token（无 project key 身份）保留运维超级权限：不做白名单与额度，
但 project_id 解析与对象归属仍执行。
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from mcp.server.mcpserver import Context

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.auth import (
    ProjectApiKeyContext,
    project_api_key_context,
)
from data_intelligence_hub.mcp_runtime.runtime import governed_tool
from data_intelligence_hub.mcp_runtime.tool_registry import get_policy
from data_intelligence_hub.repositories.project_api_keys import (
    consume_daily_quota,
    find_by_id,
)

logger = structlog.get_logger(__name__)


def assert_tool_allowed(tool_name: str, allowlist: list[str]) -> bool:
    """显式白名单：空列表拒绝全部；未登记工具拒绝。"""
    return tool_name in (allowlist or [])


def resolve_bound_project(
    identity: ProjectApiKeyContext | None,
    value: str | uuid.UUID,
) -> uuid.UUID:
    parsed = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    if identity is not None and parsed != identity.project_id:
        raise ValueError("project_not_found")
    return parsed


@dataclass(frozen=True, slots=True)
class AccessDecision:
    identity_type: str  # global_operator | project_key
    identity: ProjectApiKeyContext | None
    quota_consumed: bool
    started_at: float


@asynccontextmanager
async def governed_mcp_tool(
    context: Context,
    tool_name: str,
    *,
    project_id: str | uuid.UUID | None = None,
    object_project_id: uuid.UUID | None = None,
    is_collect: bool = False,
) -> AsyncIterator[AccessDecision]:
    policy = get_policy(tool_name)
    identity = project_api_key_context(context)

    # 1. 解析项目：项目密钥强制绑定；全局 token 解析给定值。
    #    resolve_bound_project 只做校验；绑定值由各工具按需取用。
    if identity is not None:
        if project_id is not None:
            resolve_bound_project(identity, project_id)
    elif project_id is not None:
        _ = project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))

    # 2. requires_project 的结构性守卫。
    #    只针对全局 token（identity is None）且 project_scope=bound_project 的工具：
    #    这类工具必须拿到一个项目，否则无从做归属判定。给出 project_id 时放行，
    #    保留全局 token 的运维超级权限（spec §2.3）；scope=workspace 与 operator
    #    的工具不受这条约束（workspace_answer 在全工作区上工作，stop 按对象归属）。
    #    当前工具面里所有 bound_project 且 requires_project 的工具都把 project_id
    #    声明为必填参数，所以生产不会命中这条守卫；它挡住的是未来把 project_id
    #    改成可选的新工具。
    if (
        identity is None
        and policy.requires_project
        and policy.project_scope == "bound_project"
        and project_id is None
    ):
        raise ValueError("project_not_found")

    # 3. 对象归属：传入 object_project_id 时必须与绑定项目一致。
    if identity is not None and object_project_id is not None:
        expected = identity.project_id
        if object_project_id != expected:
            raise ValueError("object_not_found")

    async with governed_tool(context, tool_name, is_collect=is_collect):
        quota_consumed = False
        if identity is not None:
            # 3. 白名单。
            async with async_session_factory() as session:
                key = await find_by_id(session, identity.key_id)
            if key is None or key.revoked_at is not None:
                raise ValueError("project_key_not_found")
            if not assert_tool_allowed(tool_name, list(key.tool_allowlist or [])):
                raise ValueError("tool_not_allowed")
            # 4. 额度：per_call 在进入时扣；per_row_worker 由 worker 扣；
            #    per_scheduled_run 由调度执行扣。
            if policy.consumes_quota == "per_call":
                async with async_session_factory() as session:
                    allowed = await consume_daily_quota(session, identity.key_id)
                    await session.commit()
                if not allowed:
                    raise ValueError("quota_exceeded")
                quota_consumed = True

        started = time.perf_counter()
        # access_mode 只进审计字段，不参与判定：control 类工具（stop）单独可筛。
        audit_fields: dict[str, object] = {
            "tool": tool_name,
            "identity_type": "global_operator" if identity is None else "project_key",
            "access_mode": policy.access_mode,
        }
        try:
            yield AccessDecision(
                identity_type="global_operator" if identity is None else "project_key",
                identity=identity,
                quota_consumed=quota_consumed,
                started_at=started,
            )
        except Exception as exc:
            logger.info(
                "mcp_tool_access_failed",
                **audit_fields,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        else:
            logger.info(
                "mcp_tool_access_ok",
                **audit_fields,
                quota_consumed=quota_consumed,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

"""MCP 入口的 Bearer 鉴权。

鉴权接受两类凭据：

1. 全局 token。它来自环境配置，没有项目身份。
2. 项目密钥。它在 ``project_api_keys`` 表里，带工作区与项目身份。

全局 token 暂不删除。决策 D6 要求分阶段退役。
项目密钥命中时，本模块把身份写入 ASGI ``scope['state']``。
MCP 工具用 ``project_api_key_context`` 读取该身份。
全局 token 路径不写身份。它的行为与改动前一致。
"""

from __future__ import annotations

import dataclasses
import hmac
import uuid

import structlog
from mcp.server.mcpserver import Context
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.services.project_api_keys import authenticate_key

logger = structlog.get_logger(__name__)

PROJECT_KEY_STATE_KEY = "mcp_project_api_key"
PROJECT_KEY_MARKER = "dih_"
BEARER_PREFIX = "Bearer "


@dataclasses.dataclass(frozen=True, slots=True)
class ProjectApiKeyContext:
    """项目密钥通过鉴权后的调用身份。它不含明文。"""

    key_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    key_prefix: str
    label: str


def _bearer_value(authorization: str) -> str:
    """从 Authorization 头取出 token。格式不符时返回空串。"""
    if authorization.startswith(BEARER_PREFIX):
        return authorization.removeprefix(BEARER_PREFIX)
    return ""


def project_api_key_context(context: Context) -> ProjectApiKeyContext | None:
    """从 MCP 调用上下文读取项目密钥身份。

    全局 token 路径返回 None。stdin 传输或缺少请求对象时也返回 None。
    """
    try:
        request = context.request_context.request
    except (AttributeError, ValueError):
        return None
    scope = getattr(request, "scope", None)
    if not isinstance(scope, dict):
        return None
    state = scope.get("state")
    if not isinstance(state, dict):
        return None
    identity = state.get(PROJECT_KEY_STATE_KEY)
    if isinstance(identity, ProjectApiKeyContext):
        return identity
    return None


class BearerTokenMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._app = app
        self._session_factory = session_factory or async_session_factory

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        provided = headers.get(b"authorization", b"").decode()
        tokens = get_settings().accepted_mcp_tokens
        if any(hmac.compare_digest(provided, f"Bearer {token}") for token in tokens):
            await self._app(scope, receive, send)
            return
        raw_token = _bearer_value(provided)
        if raw_token.startswith(PROJECT_KEY_MARKER):
            identity = await self._resolve_project_key(raw_token)
            if identity is not None:
                self._attach_identity(scope, identity)
                await self._app(scope, receive, send)
                return
            await self._reject(send)
            return
        if not tokens:
            # 未配置全局 token 时的行为。
            # 生产必须 fail-closed：无凭据一律 401。
            # 开发与测试保留放行，否则本地 MCP 无法联调。
            # 判定与 demo_mode 同一口径，见 ADR-007 D2 与计划 R7。
            if get_settings().app_env == "production":
                await self._reject(send)
                return
            await self._app(scope, receive, send)
            return
        await self._reject(send)

    async def _resolve_project_key(self, token: str) -> ProjectApiKeyContext | None:
        """按哈希查项目密钥。数据库失败时按未命中处理。"""
        try:
            async with self._session_factory() as session:
                identity = await authenticate_key(session, token)
        except Exception as exc:
            logger.warning(
                "mcp_project_key_lookup_failed",
                error_type=type(exc).__name__,
            )
            return None
        if identity is None:
            return None
        return ProjectApiKeyContext(
            key_id=identity.key_id,
            workspace_id=identity.workspace_id,
            project_id=identity.project_id,
            key_prefix=identity.key_prefix,
            label=identity.label,
        )

    @staticmethod
    def _attach_identity(scope: Scope, identity: ProjectApiKeyContext) -> None:
        """把身份写入请求 state。MCP 工具可从同一 scope 读取。"""
        state = scope.get("state")
        if not isinstance(state, dict):
            state = {}
            scope["state"] = state
        state[PROJECT_KEY_STATE_KEY] = identity

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"detail":"mcp_authentication_required"}',
            }
        )

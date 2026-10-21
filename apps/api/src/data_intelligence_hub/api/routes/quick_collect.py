"""One-click quick collect: create ephemeral Source + Task, run immediately.

同步路径（``POST /api/quick-collect``）行为不变：立即执行并返回 TaskRun。

异步路径（``POST /api/quick-collect/async``）写一行 ``runs(status=queued)``。
队列 worker 领取后执行。进程重启不丢任务。
原先的进程内后台任务已移除。
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import (
    AuthContext,
    SessionDep,
    get_authenticated_context,
)
from data_intelligence_hub.collectors.endpoint_catalog import (  # noqa: F401
    _APIFY_ENDPOINT_DEFAULTS,
    _APIFY_META_KEYS,
    _COLLECTOR_TEST_DEFAULTS,
    _ENDPOINT_TO_COLLECTOR,
    build_apify_actor_input,
)
from data_intelligence_hub.services.exceptions import (
    QuickCollectCollectorUnavailableError,
    QuickCollectDemoWorkspaceUnavailableError,
    QuickCollectExecutionError,
    QuickCollectUnknownEndpointError,
    QuickCollectUnknownProjectError,
)
from data_intelligence_hub.services.quick_collect_service import (
    QuickCollectQueuedResponse,
    QuickCollectRequest,
    QuickCollectResponse,
    enqueue_quick_collect,
    run_quick_collect,
    to_queued_response,
    to_response,
)
from data_intelligence_hub.services.run_queue import RunQueueError

router = APIRouter(tags=["quick-collect"])

_QUICK_COLLECT_ERRORS = (
    QuickCollectDemoWorkspaceUnavailableError,
    QuickCollectUnknownProjectError,
    QuickCollectUnknownEndpointError,
    QuickCollectCollectorUnavailableError,
    QuickCollectExecutionError,
)


@router.post("", response_model=QuickCollectResponse, status_code=status.HTTP_201_CREATED)
async def quick_collect(
    body: QuickCollectRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> QuickCollectResponse:
    """Create an ephemeral Source + Task and run one collection immediately.

    Returns the completed (or failed) TaskRun synchronously.
    Suitable for small quick-collect requests (up to ~30 s) from the console UI.

    workspace 由已鉴权的请求方提供；无 token 时由路由依赖拒绝。
    MCP 与 agent 走服务层，不经过这里。
    """
    try:
        outcome = await run_quick_collect(session, body, workspace=context.workspace)
    except _QUICK_COLLECT_ERRORS as exc:
        _raise_quick_collect_error(exc)
    return to_response(outcome)


@router.post(
    "/async",
    response_model=QuickCollectQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def quick_collect_async(
    body: QuickCollectRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> QuickCollectQueuedResponse:
    """提交一次异步采集，立即返回 run_id。

    只写库，不执行。``runs`` 行状态为 ``queued``。
    队列 worker 用 ``runs.task_id`` 找到 CollectionTask 并执行。

    迁移方式：客户端从同步端点切到本端点。
    回退方式：客户端切回同步端点；已入队的 runs 行仍留在库中，
    可由 worker 继续执行。
    ``runs`` 表不可用时返回 503。同步端点不受影响。
    """
    try:
        outcome = await enqueue_quick_collect(session, body, workspace=context.workspace)
    except _QUICK_COLLECT_ERRORS as exc:
        _raise_quick_collect_error(exc)
    except RunQueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"run_queue_unavailable: {exc}",
        ) from exc
    return to_queued_response(outcome)


def _raise_quick_collect_error(exc: Exception) -> NoReturn:
    """把服务层领域异常映射为 HTTP 状态码。"""
    if isinstance(exc, QuickCollectDemoWorkspaceUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        ) from exc
    if isinstance(exc, QuickCollectUnknownProjectError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown project_id: {exc.project_id}",
        ) from exc
    if isinstance(exc, QuickCollectUnknownEndpointError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown endpoint_type: {exc.endpoint_type}",
        ) from exc
    if isinstance(exc, QuickCollectCollectorUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collector {exc.collector_type!r} is not available",
        ) from exc
    if isinstance(exc, QuickCollectExecutionError):
        if exc.is_config_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid collector config: {exc.detail}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collection failed: {exc.detail}",
        ) from exc
    raise exc

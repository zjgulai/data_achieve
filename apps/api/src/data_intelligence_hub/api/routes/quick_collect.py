"""One-click quick collect: create ephemeral Source + Task, run immediately."""

from __future__ import annotations

from typing import Annotated

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
from data_intelligence_hub.services.quick_collect_service import (  # noqa: F401
    QuickCollectRequest,
    QuickCollectResponse,
    run_quick_collect,
    to_response,
)

router = APIRouter(tags=["quick-collect"])


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
    except QuickCollectDemoWorkspaceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        ) from exc
    except QuickCollectUnknownProjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown project_id: {exc.project_id}",
        ) from exc
    except QuickCollectUnknownEndpointError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown endpoint_type: {exc.endpoint_type}",
        ) from exc
    except QuickCollectCollectorUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collector {exc.collector_type!r} is not available",
        ) from exc
    except QuickCollectExecutionError as exc:
        if exc.is_config_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid collector config: {exc.detail}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collection failed: {exc.detail}",
        ) from exc
    return to_response(outcome)

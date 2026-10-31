"""``/api/insight`` 的只读端点。

v1 只有查看能力：分析类型、报告列表、报告详情、HTML 正文。没有生成端点，
``POST`` 由路由层自然返回 405，不存在永远 501 的占位。

错误信封为 ``{"detail": 人类可读文案, "code": 稳定错误码}``。401/403 由
``main.py`` 中按路径前缀挂的 HTTP 异常处理器补齐，其余错误由本模块的
``InsightApiError`` 处理器返回。
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.insight_report import (
    InsightAnalysisTypeListResponse,
    InsightReportListResponse,
    InsightReportResponse,
)
from data_intelligence_hub.services.exceptions import (
    InsightReportContentMissingError,
    InsightReportIntegrityError,
    InsightReportNotFoundError,
)
from data_intelligence_hub.services.insight_report_service import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    InsightCursorError,
    get_report,
    get_report_content,
    list_analysis_types,
    list_reports,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["insight"])

INSIGHT_REPORT_CSP = (
    "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    "script-src 'none'; base-uri 'none'; form-action 'none'"
)

class InsightApiError(Exception):
    """带稳定错误码的端点错误，由 ``insight_exception_handler`` 序列化。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers or {}


def ensure_request_id(request: Request) -> str:
    value = getattr(request.state, "insight_request_id", None)
    if value is None:
        value = str(uuid.uuid4())
        request.state.insight_request_id = value
    return value


async def insight_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    assert isinstance(exc, InsightApiError)
    request_id = ensure_request_id(request)
    headers = {**exc.headers, "X-Request-ID": request_id}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=headers,
    )


def _not_found() -> InsightApiError:
    return InsightApiError(
        status.HTTP_404_NOT_FOUND,
        "insight_report_not_found",
        "报告不存在或已被移除。",
    )


async def _guarded[RESULT](operation: Awaitable[RESULT], request: Request) -> RESULT:
    """把服务层错误映射成稳定的 HTTP 错误信封。"""
    try:
        return await operation
    except InsightReportNotFoundError as exc:
        raise _not_found() from exc
    except InsightReportContentMissingError as exc:
        raise InsightApiError(
            status.HTTP_409_CONFLICT,
            "insight_report_content_missing",
            "报告正文未导入。",
        ) from exc
    except InsightReportIntegrityError as exc:
        raise InsightApiError(
            status.HTTP_409_CONFLICT,
            "insight_report_integrity_failed",
            "报告正文校验失败。",
        ) from exc
    except InsightCursorError as exc:
        # 游标解析失败。FastAPI 自身的参数校验仍是默认 422 形状。
        raise InsightApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "cursor 无效。",
        ) from exc
    except SQLAlchemyError as exc:
        logger.error(
            "insight_reports_database_error",
            request_id=ensure_request_id(request),
            error_type=type(exc).__name__,
        )
        raise InsightApiError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_server_error",
            "服务暂时不可用，请稍后重试。",
        ) from exc


@router.get("/analysis-types", response_model=InsightAnalysisTypeListResponse)
async def list_insight_analysis_types(
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> InsightAnalysisTypeListResponse:
    request_id = ensure_request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _guarded(list_analysis_types(session, context.workspace), request)


@router.get("/reports", response_model=InsightReportListResponse)
async def list_insight_reports(
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    analysis_type: Annotated[str | None, Query(max_length=40)] = None,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_LIST_LIMIT)
    ] = DEFAULT_LIST_LIMIT,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> InsightReportListResponse:
    request_id = ensure_request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _guarded(
        list_reports(
            session,
            context.workspace,
            analysis_type=analysis_type,
            project_id=project_id,
            limit=limit,
            cursor=cursor,
        ),
        request,
    )


@router.get("/reports/{report_id}", response_model=InsightReportResponse)
async def get_insight_report(
    report_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> InsightReportResponse:
    request_id = ensure_request_id(request)
    response.headers["X-Request-ID"] = request_id
    return await _guarded(
        get_report(session, context.workspace, report_id),
        request,
    )


@router.get("/reports/{report_id}/content")
async def get_insight_report_content(
    report_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    download: Annotated[bool, Query()] = False,
) -> Response:
    request_id = ensure_request_id(request)
    content = await _guarded(
        get_report_content(
            session,
            context.workspace,
            report_id,
            request_id=request_id,
        ),
        request,
    )

    headers = {
        "Content-Security-Policy": INSIGHT_REPORT_CSP,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "private, max-age=300",
        "ETag": f'"{content.sha256}"',
        "Content-Disposition": (
            f'{"attachment" if download else "inline"}; '
            f'filename="{content.filename}"'
        ),
        "X-Request-ID": request_id,
    }

    if_none_match = request.headers.get("if-none-match")
    if if_none_match is not None and if_none_match.strip() == headers["ETag"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    return Response(
        content=content.html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers=headers,
    )

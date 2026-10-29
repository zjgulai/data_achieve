"""``/api/abi`` 路由。

路由层只做参数收集、依赖注入与错误转换。业务规则在
``services/abi_service.py``，SQL 在 ``repositories/abi.py``。
"""

from __future__ import annotations

import uuid
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from data_intelligence_hub.api.deps import (
    AuthenticatedContextDep,
    DatasetAccess,
    SessionDep,
    require_dataset_role,
)
from data_intelligence_hub.schemas.abi import (
    AbiDatasetCreateRequest,
    AbiDatasetDetailResponse,
    AbiDatasetListResponse,
    AbiDatasetSummary,
    AbiDeleteResponse,
    AbiExportCreateRequest,
    AbiExportJobResponse,
    AbiExportListResponse,
    AbiExportPolicyResponse,
    AbiExportPolicyUpdateRequest,
    AbiExportRejectRequest,
    AbiGrantCreateRequest,
    AbiGrantListResponse,
    AbiGrantResponse,
    AbiOverviewResponse,
    AbiPolicyResponse,
    AbiPolicyUpdateRequest,
    AbiQueryRequest,
    AbiQueryResponse,
    AbiUploadBatchResponse,
    AbiUploadCreateRequest,
    AbiUploadCreateResponse,
    AbiUploadErrorListResponse,
    AbiUploadListResponse,
)
from data_intelligence_hub.services import abi_service
from data_intelligence_hub.services.abi_service import AbiServiceError

router = APIRouter(tags=["abi"])

# dataset 端点按角色使用不同依赖。每个依赖都会重新校验 workspace + grant，
# 不存在 admin 万能 bypass。
ViewerAccessDep = Annotated[DatasetAccess, Depends(require_dataset_role("viewer"))]
PublisherAccessDep = Annotated[
    DatasetAccess, Depends(require_dataset_role("publisher"))
]
AdminAccessDep = Annotated[DatasetAccess, Depends(require_dataset_role("admin"))]


def _raise_http(exc: AbiServiceError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _attachment_header(filename: str) -> str:
    """生成安全的 attachment 头。文件名由服务端生成，仍去掉引号与反斜杠。"""
    safe = filename.replace("\\", "_").replace('"', "_")
    return f'attachment; filename="{safe}"'


@router.get("/overview", response_model=AbiOverviewResponse)
async def get_overview(
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiOverviewResponse:
    """工作区 ABI 概览。只统计当前用户有 grant 的 dataset。"""
    return await abi_service.get_abi_overview(
        session, context.workspace, context.user
    )


@router.get("/datasets", response_model=AbiDatasetListResponse)
async def list_datasets(
    session: SessionDep,
    context: AuthenticatedContextDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    cursor: str | None = None,
) -> AbiDatasetListResponse:
    """列出当前用户有 grant 的 dataset。cursor 优先于 offset。"""
    try:
        return await abi_service.list_abi_datasets(
            session,
            context.workspace,
            context.user,
            limit=limit,
            offset=offset,
            cursor=cursor,
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/datasets",
    response_model=AbiDatasetSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    payload: AbiDatasetCreateRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiDatasetSummary:
    """建 dataset。仅 workspace owner 可建，创建者自动获得 admin grant。"""
    try:
        return await abi_service.create_abi_dataset(
            session, context.workspace, context.user, payload
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get("/datasets/{slug}", response_model=AbiDatasetDetailResponse)
async def get_dataset(
    access: ViewerAccessDep,
    session: SessionDep,
) -> AbiDatasetDetailResponse:
    """dataset 详情：目录项 + 列 + 有效 PII 策略。"""
    return await abi_service.get_abi_dataset_detail(session, access)


@router.post("/datasets/{slug}/query", response_model=AbiQueryResponse)
async def query_dataset(
    payload: AbiQueryRequest,
    access: ViewerAccessDep,
    session: SessionDep,
) -> AbiQueryResponse:
    """结构化查询。列名、过滤列、排序列都来自服务端 allowlist。"""
    try:
        return await abi_service.query_abi_dataset(session, access, payload)
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get("/datasets/{slug}/grants", response_model=AbiGrantListResponse)
async def list_dataset_grants(
    access: AdminAccessDep,
    session: SessionDep,
) -> AbiGrantListResponse:
    """列出 dataset 授权。仅 admin。"""
    return await abi_service.list_abi_grants(session, access)


@router.post(
    "/datasets/{slug}/grants",
    response_model=AbiGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_grant(
    payload: AbiGrantCreateRequest,
    access: AdminAccessDep,
    session: SessionDep,
) -> AbiGrantResponse:
    """新增授权。仅 admin。"""
    try:
        return await abi_service.create_abi_grant(session, access, payload)
    except AbiServiceError as exc:
        _raise_http(exc)


@router.delete(
    "/datasets/{slug}/grants/{grant_id}",
    response_model=AbiDeleteResponse,
)
async def delete_dataset_grant(
    grant_id: uuid.UUID,
    access: AdminAccessDep,
    session: SessionDep,
) -> AbiDeleteResponse:
    """删除授权。不允许删掉最后一个 admin grant。"""
    try:
        return await abi_service.delete_abi_grant(session, access, grant_id)
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get("/datasets/{slug}/policy", response_model=AbiPolicyResponse)
async def get_dataset_policy(
    access: ViewerAccessDep,
    session: SessionDep,
) -> AbiPolicyResponse:
    """读取有效 PII 策略。没有策略行的字段返回 unknown。"""
    return await abi_service.get_abi_policy(session, access)


@router.put("/datasets/{slug}/policy", response_model=AbiPolicyResponse)
async def put_dataset_policy(
    payload: AbiPolicyUpdateRequest,
    access: PublisherAccessDep,
    session: SessionDep,
) -> AbiPolicyResponse:
    """按提交项更新 PII 策略。

    未提交的列保留原分类——这是增量语义，不是全量替换。降级
    （``direct``/``secret``/``quasi`` 往低档走）需要 admin 权限与
    ``reason``（>= 10 字），否则返回 403 / 400。
    """
    try:
        return await abi_service.replace_abi_policy(session, access, payload)
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/uploads",
    response_model=AbiUploadCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload(
    payload: AbiUploadCreateRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiUploadCreateResponse:
    """创建上传批次并一次性返回 X-Upload-Token。明文令牌不落库。"""
    try:
        return await abi_service.create_abi_upload(
            session, context.workspace, context.user, payload
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.put("/uploads/content", response_model=AbiUploadBatchResponse)
async def upload_content(
    request: Request,
    session: SessionDep,
    context: AuthenticatedContextDep,
    x_upload_token: Annotated[str, Header(alias="X-Upload-Token")],
) -> AbiUploadBatchResponse:
    """按 X-Upload-Token 接收字节流。令牌与 cookie 鉴权同时校验。"""
    try:
        return await abi_service.write_abi_upload_content(
            session,
            context.workspace,
            context.user,
            x_upload_token,
            request.stream(),
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/uploads/{batch_id}/commit",
    response_model=AbiUploadBatchResponse,
)
async def commit_upload(
    batch_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiUploadBatchResponse:
    """提交上传批次。校验 hash、行数与文件路径。"""
    try:
        return await abi_service.commit_abi_upload(
            session, context.workspace, context.user, batch_id
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get(
    "/datasets/{slug}/uploads",
    response_model=AbiUploadListResponse,
)
async def list_uploads(
    slug: str,
    session: SessionDep,
    context: AuthenticatedContextDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AbiUploadListResponse:
    """列出某 dataset 的上传批次，按创建时间倒序。

    viewer 即可查看：批次历史是可观测性需求，不含行内容。
    """
    try:
        return await abi_service.list_abi_uploads(
            session,
            context.workspace,
            context.user,
            slug,
            limit=limit,
            offset=offset,
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get(
    "/uploads/{batch_id}/errors",
    response_model=AbiUploadErrorListResponse,
)
async def list_upload_errors(
    batch_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AbiUploadErrorListResponse:
    """列出批次的行级校验错误。

    只给定位（行号、列名、规则名）与不含数据值的说明。批次不存在与
    跨租户一律 404，不区分——否则状态码差异本身就是存在性泄露。
    """
    try:
        return await abi_service.get_abi_upload_errors(
            session,
            context.workspace,
            context.user,
            batch_id,
            limit=limit,
            offset=offset,
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/uploads/{batch_id}/retry",
    response_model=AbiUploadBatchResponse,
)
async def retry_upload(
    batch_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiUploadBatchResponse:
    """重跑 failed 批次的 commit。不需要重新上传字节。

    只接受 ``failed``：``committed`` 已成功，``pending``/``uploaded``
    应走正常 commit。文件必须仍在且 sha256 与记录一致。
    """
    try:
        return await abi_service.retry_abi_upload(
            session, context.workspace, context.user, batch_id
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/exports",
    response_model=AbiExportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_export(
    payload: AbiExportCreateRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiExportJobResponse:
    """创建导出任务。publisher 及以上；不遮罩导出要求 admin。"""
    try:
        return await abi_service.create_abi_export(
            session, context.workspace, context.user, payload
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get(
    "/datasets/{slug}/export-policy",
    response_model=AbiExportPolicyResponse,
)
async def get_export_policy(
    access: ViewerAccessDep,
    session: SessionDep,
) -> AbiExportPolicyResponse:
    """读 dataset 级导出策略。

    没有策略行时返回表定义的默认值：``require_dual_approval=True``、
    格式与行数不额外限制（行数仍受系统上限 5 万约束）。
    """
    return await abi_service.get_abi_export_policy(session, access)


@router.put(
    "/datasets/{slug}/export-policy",
    response_model=AbiExportPolicyResponse,
)
async def put_export_policy(
    payload: AbiExportPolicyUpdateRequest,
    access: AdminAccessDep,
    session: SessionDep,
) -> AbiExportPolicyResponse:
    """写入 dataset 级导出策略。需要 admin。

    策略直接决定审批要求、可用格式与行数上限，放宽任一条都等于削弱管控，
    因此门槛与 PII 降级同级。
    """
    try:
        return await abi_service.set_abi_export_policy(session, access, payload)
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get("/exports", response_model=AbiExportListResponse)
async def list_exports(
    session: SessionDep,
    context: AuthenticatedContextDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AbiExportListResponse:
    """列出本人创建的导出，或本人有 publisher/admin grant 的 dataset 导出。"""
    return await abi_service.list_abi_exports(
        session,
        context.workspace,
        context.user,
        limit=limit,
        offset=offset,
    )


@router.get("/exports/{job_id}", response_model=AbiExportJobResponse)
async def get_export(
    job_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiExportJobResponse:
    """导出详情。过期任务返回 410。"""
    try:
        return await abi_service.get_abi_export(
            session, context.workspace, context.user, job_id
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/exports/{job_id}/approve",
    response_model=AbiExportJobResponse,
)
async def approve_export(
    job_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiExportJobResponse:
    """批准一个等待双人审批的导出。

    只有未遮罩导出会进入审批（遮罩导出本身已限制暴露面，没有可批的东西）。
    申请人不能批自己的作业——单人自批只是自证，不是控制。
    """
    try:
        return await abi_service.approve_abi_export(
            session, context.workspace, context.user, job_id
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.post(
    "/exports/{job_id}/reject",
    response_model=AbiExportJobResponse,
)
async def reject_export(
    job_id: uuid.UUID,
    payload: AbiExportRejectRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> AbiExportJobResponse:
    """驳回一个等待审批的导出。``rejected`` 是终态，要数据得重新发起。"""
    try:
        return await abi_service.reject_abi_export(
            session, context.workspace, context.user, job_id, payload.reason
        )
    except AbiServiceError as exc:
        _raise_http(exc)


@router.get(
    "/exports/{job_id}/download",
    response_model=None,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_export(
    job_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> FileResponse:
    """下载导出产物。

    校验顺序：workspace + (created_by/grant) → 过期 410 → 状态 → 路径
    ``resolve().relative_to(export_root)``。文件不存在统一 404。
    """
    try:
        job, path = await abi_service.get_abi_export_download(
            session, context.workspace, context.user, job_id
        )
    except AbiServiceError as exc:
        _raise_http(exc)
    return FileResponse(
        path,
        media_type=job.content_type or "application/octet-stream",
        filename=job.filename or path.name,
        headers={
            "Content-Disposition": _attachment_header(job.filename or path.name),
            "X-Content-Type-Options": "nosniff",
        },
    )

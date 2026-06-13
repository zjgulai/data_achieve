from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.intelligence import EvidenceResponse, IntelligenceResponse
from data_intelligence_hub.schemas.report import (
    ReportAuditEventCreateRequest,
    ReportAuditEventResponse,
    ReportEvidenceReferenceResponse,
    ReportGenerateRequest,
    ReportResponse,
    ReportSubscriptionResponse,
    ReportSubscriptionUpsertRequest,
)
from data_intelligence_hub.services.exceptions import ProjectNotFoundError, ReportNotFoundError
from data_intelligence_hub.services.report_service import (
    generate_report,
    get_report_audit_events,
    get_report_evidence_references,
    get_report_or_raise,
    get_report_subscriptions,
    get_reports,
    record_report_share_event,
    send_report,
    upsert_report_subscription,
)

router = APIRouter(tags=["reports"])


@router.get("", response_model=list[ReportResponse])
async def list_report_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ReportResponse]:
    reports = await get_reports(session, context.workspace, project_id=project_id)
    return [ReportResponse.from_model(report) for report in reports]


@router.post(
    "/generate",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report_item(
    payload: ReportGenerateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ReportResponse:
    try:
        report = await generate_report(session, context.workspace, context.user, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ReportResponse.from_model(report)


@router.get("/subscriptions", response_model=list[ReportSubscriptionResponse])
async def list_report_subscription_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[ReportSubscriptionResponse]:
    subscriptions = await get_report_subscriptions(session, context.workspace, context.user)
    return [ReportSubscriptionResponse.from_model(subscription) for subscription in subscriptions]


@router.put("/subscriptions", response_model=ReportSubscriptionResponse)
async def upsert_report_subscription_item(
    payload: ReportSubscriptionUpsertRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ReportSubscriptionResponse:
    try:
        subscription = await upsert_report_subscription(
            session=session,
            workspace=context.workspace,
            user=context.user,
            payload=payload,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ReportSubscriptionResponse.from_model(subscription)


@router.get(
    "/{report_id}/evidence-references",
    response_model=list[ReportEvidenceReferenceResponse],
)
async def list_report_evidence_references(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[ReportEvidenceReferenceResponse]:
    try:
        references = await get_report_evidence_references(session, context.workspace, report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    return [
        ReportEvidenceReferenceResponse(
            intelligence=IntelligenceResponse.from_model(
                reference.intelligence.item,
                reference.intelligence.evidence_count,
            ),
            evidences=[
                EvidenceResponse.from_model(
                    evidence=trace.evidence,
                    screenshot_url=trace.screenshot_url,
                    signal=trace.signal,
                    entity=trace.entity,
                    raw_record=trace.raw_record,
                    task_run=trace.task_run,
                    source=trace.source,
                )
                for trace in reference.evidences
            ],
        )
        for reference in references
    ]


@router.get("/{report_id}/audit-events", response_model=list[ReportAuditEventResponse])
async def list_report_audit_event_items(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[ReportAuditEventResponse]:
    try:
        events = await get_report_audit_events(session, context.workspace, report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [ReportAuditEventResponse.from_model(event) for event in events]


@router.post(
    "/{report_id}/audit-events",
    response_model=ReportAuditEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report_audit_event_item(
    report_id: uuid.UUID,
    payload: ReportAuditEventCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ReportAuditEventResponse:
    try:
        event = await record_report_share_event(
            session=session,
            workspace=context.workspace,
            user=context.user,
            report_id=report_id,
            event_type=payload.event_type,
            metadata=payload.metadata,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ReportAuditEventResponse.from_model(event)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_item(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ReportResponse:
    try:
        report = await get_report_or_raise(session, context.workspace, report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ReportResponse.from_model(report)


@router.post("/{report_id}/send", response_model=ReportResponse)
async def send_report_item(
    report_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ReportResponse:
    try:
        report = await send_report(session, context.workspace, context.user, report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ReportResponse.from_model(report)

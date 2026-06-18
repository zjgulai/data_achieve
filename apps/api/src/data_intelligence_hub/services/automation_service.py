from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import (
    ECOMMERCE_PRODUCT_FIELDS,
    EcommerceProductPageCollector,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.alert import AlertEvent
from data_intelligence_hub.models.dataset import (
    Dataset,
    DatasetDriftEvent,
    DatasetExportJob,
    DatasetVersion,
)
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.alerts import get_alert_event, get_alert_rule
from data_intelligence_hub.repositories.datasets import (
    count_dataset_drift_events,
    count_dataset_versions,
    create_dataset_drift_event,
    create_dataset_export_job,
    get_dataset,
    get_dataset_by_name,
    get_dataset_drift_event,
    get_dataset_export_job,
    get_dataset_version,
    get_latest_dataset_version,
    list_dataset_drift_events,
    list_dataset_export_jobs,
    list_dataset_versions,
    list_datasets,
)
from data_intelligence_hub.repositories.entities import (
    get_entity_by_external_id,
    get_entity_snapshot,
)
from data_intelligence_hub.repositories.notifications import get_notification_by_reference
from data_intelligence_hub.repositories.raw_records import list_raw_records
from data_intelligence_hub.repositories.signals import get_signal, list_signals
from data_intelligence_hub.repositories.sources import get_source_by_type_url
from data_intelligence_hub.repositories.tasks import get_task, list_task_runs
from data_intelligence_hub.repositories.users import get_user_by_id
from data_intelligence_hub.scheduler.cron import UnsupportedCronExpression, cron_interval
from data_intelligence_hub.schemas.alert import (
    AlertEventResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
)
from data_intelligence_hub.schemas.automation import (
    AutomationCleaningStepResponse,
    AutomationDatasetResponse,
    AutomationDatasetVersionResponse,
    AutomationDiscoveryPageStructureResponse,
    AutomationDiscoveryPlanResponse,
    AutomationFanoutBatchPlanResponse,
    AutomationFanoutCandidateStatusResponse,
    AutomationFanoutCreateSummaryResponse,
    AutomationFanoutPersistedSourceResponse,
    AutomationFieldCandidateResponse,
    AutomationPageStructureResponse,
    AutomationPlatformProfileResponse,
    AutomationProductBatchFieldCompletenessResponse,
    AutomationProductBatchRunItemResponse,
    AutomationProductBatchRunRequest,
    AutomationProductBatchRunResponse,
    AutomationProductBatchRunSummaryResponse,
    AutomationProductCandidateResponse,
    AutomationProductDatasetExportCreateRequest,
    AutomationProductDatasetExportJobResponse,
    AutomationProductDatasetExportListResponse,
    AutomationProductDatasetListItemResponse,
    AutomationProductDatasetListResponse,
    AutomationProductDatasetPreviewRequest,
    AutomationProductDatasetPreviewResponse,
    AutomationProductDatasetRowResponse,
    AutomationProductDatasetSaveRequest,
    AutomationProductDatasetSaveResponse,
    AutomationProductDatasetSummaryResponse,
    AutomationProductDatasetVersionListResponse,
    AutomationProductDiscoveryRequest,
    AutomationProductDiscoveryResponse,
    AutomationProductDriftAlertEmailDeliveryResponse,
    AutomationProductDriftAlertEmailSendRequest,
    AutomationProductDriftAlertEmailSendResponse,
    AutomationProductDriftAlertEventCreateRequest,
    AutomationProductDriftAlertEventCreateResponse,
    AutomationProductDriftAlertNotificationSendRequest,
    AutomationProductDriftAlertNotificationSendResponse,
    AutomationProductDriftAlertPreviewRequest,
    AutomationProductDriftAlertPreviewResponse,
    AutomationProductDriftAlertRuleCreateRequest,
    AutomationProductDriftAlertRuleCreateResponse,
    AutomationProductDriftAlertRuleDraftResponse,
    AutomationProductDriftAlertSummaryResponse,
    AutomationProductDriftCheckRequest,
    AutomationProductDriftCheckResponse,
    AutomationProductDriftEventListResponse,
    AutomationProductDriftEventResponse,
    AutomationProductDriftEventSaveRequest,
    AutomationProductDriftItemResponse,
    AutomationProductDriftSummaryResponse,
    AutomationProductFanoutCreateRequest,
    AutomationProductFanoutCreateResponse,
    AutomationProductFanoutPreviewRequest,
    AutomationProductFanoutPreviewResponse,
    AutomationProductScheduleApproveRequest,
    AutomationProductScheduleApproveResponse,
    AutomationProductScheduleApproveSummaryResponse,
    AutomationScheduleApprovedTaskResponse,
    AutomationScheduleBlockedTaskResponse,
    AutomationSiteAnalysisRequest,
    AutomationSiteAnalysisResponse,
    AutomationSourceDraftResponse,
    AutomationToolRecommendationResponse,
)
from data_intelligence_hub.schemas.notification import NotificationResponse
from data_intelligence_hub.schemas.signal import SignalResponse
from data_intelligence_hub.schemas.source import SourceCreateRequest, SourceResponse
from data_intelligence_hub.schemas.task import CollectionTaskResponse
from data_intelligence_hub.services.alert_service import (
    create_alert_rule as create_alert_rule_from_payload,
)
from data_intelligence_hub.services.alert_service import (
    match_alert_rules_for_signal,
)
from data_intelligence_hub.services.exceptions import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskNotRunnableError,
)
from data_intelligence_hub.services.notification_service import (
    create_in_app_notification,
    send_email_notification,
)
from data_intelligence_hub.services.source_service import create_source, enable_source
from data_intelligence_hub.services.task_service import get_task_or_raise, run_task_now

DATASET_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "jsonl": "application/x-ndjson; charset=utf-8",
}


async def analyze_site_for_collection(
    payload: AutomationSiteAnalysisRequest,
    http_client: httpx.AsyncClient | None = None,
) -> AutomationSiteAnalysisResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    fields = payload.fields or list(ECOMMERCE_PRODUCT_FIELDS)
    collector = EcommerceProductPageCollector(
        {"url": payload.url, "fields": fields, "platform_hint": "auto"},
        http_client=http_client,
    )
    result = await collector.collect()
    content = result.raw_records[0].content
    if not isinstance(content, dict):
        raise CollectorError("automation_analysis_invalid_content")

    platform_profile = content["platform_profile"]
    page_structure = content["page_structure"]
    field_candidates = content["field_schema"]
    tool_recommendations = content["tool_recommendations"]
    cleaning_plan = content["cleaning_plan"]
    selected_fields = [
        candidate["key"]
        for candidate in field_candidates
        if candidate.get("selected") and candidate.get("value") is not None
    ]
    blocked_reasons = _blocked_reasons(page_structure, selected_fields)
    title = page_structure.get("title") or "Ecommerce Product Page"
    return AutomationSiteAnalysisResponse(
        requested_url=payload.url.strip(),
        analyzed_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        platform_profile=AutomationPlatformProfileResponse(**platform_profile),
        page_structure=AutomationPageStructureResponse(**page_structure),
        field_candidates=[
            AutomationFieldCandidateResponse(**candidate) for candidate in field_candidates
        ],
        tool_recommendations=[
            AutomationToolRecommendationResponse(**recommendation)
            for recommendation in tool_recommendations
        ],
        cleaning_plan=[AutomationCleaningStepResponse(**step) for step in cleaning_plan],
        source_draft=AutomationSourceDraftResponse(
            type="ecommerce_product_page",
            config={
                "url": payload.url.strip(),
                "fields": selected_fields or fields,
                "platform_hint": platform_profile["platform_type"],
            },
            suggested_name=f"商品页采集：{title[:80]}",
            schedule_cron=None,
        ),
        blocked_reasons=blocked_reasons,
    )


async def discover_products_for_collection(
    payload: AutomationProductDiscoveryRequest,
    http_client: httpx.AsyncClient | None = None,
) -> AutomationProductDiscoveryResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    collector = EcommerceProductDiscoveryCollector(
        {
            "url": payload.url,
            "max_products": payload.max_products,
            "platform_hint": "auto",
        },
        http_client=http_client,
    )
    result = await collector.collect()
    content = result.raw_records[0].content
    if not isinstance(content, dict):
        raise CollectorError("automation_discovery_invalid_content")

    platform_profile = content["platform_profile"]
    page_structure = content["page_structure"]
    product_candidates = content["product_candidates"]
    tool_recommendations = content["tool_recommendations"]
    discovery_plan = content["discovery_plan"]
    blocked_reasons = _discovery_blocked_reasons(product_candidates)
    title = page_structure.get("title") or "Ecommerce Product Discovery"
    return AutomationProductDiscoveryResponse(
        requested_url=payload.url.strip(),
        analyzed_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        platform_profile=AutomationPlatformProfileResponse(**platform_profile),
        page_structure=AutomationDiscoveryPageStructureResponse(**page_structure),
        product_candidates=[
            AutomationProductCandidateResponse(**candidate) for candidate in product_candidates
        ],
        tool_recommendations=[
            AutomationToolRecommendationResponse(**recommendation)
            for recommendation in tool_recommendations
        ],
        discovery_plan=AutomationDiscoveryPlanResponse(**discovery_plan),
        source_draft=AutomationSourceDraftResponse(
            type="ecommerce_product_discovery",
            config={
                "url": payload.url.strip(),
                "max_products": payload.max_products,
                "platform_hint": platform_profile["platform_type"],
            },
            suggested_name=f"商品链接发现：{title[:80]}",
            schedule_cron=None,
        ),
        blocked_reasons=blocked_reasons,
    )


async def preview_product_fanout(
    payload: AutomationProductFanoutPreviewRequest,
) -> AutomationProductFanoutPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    parent_url = payload.parent_url.strip()
    parent_origin = _origin(parent_url)
    if parent_origin is None:
        raise CollectorError("parent_url must be an absolute HTTP or HTTPS URL")
    fields = _fanout_fields(payload.fields)
    statuses: list[AutomationFanoutCandidateStatusResponse] = []
    source_drafts: list[AutomationSourceDraftResponse] = []
    seen_urls: set[str] = set()

    for candidate in payload.candidates:
        candidate_url = _normalize_candidate_url(candidate.url)
        reason = _candidate_block_reason(
            candidate_url,
            parent_origin,
            seen_urls,
            len(source_drafts),
            payload.max_sources,
        )
        if reason is None and candidate_url is not None:
            seen_urls.add(candidate_url)
            source_drafts.append(
                AutomationSourceDraftResponse(
                    type="ecommerce_product_page",
                    config={
                        "url": candidate_url,
                        "fields": fields,
                        "platform_hint": "auto",
                    },
                    suggested_name=_fanout_source_name(candidate.title, candidate_url),
                    schedule_cron=None,
                )
            )
        statuses.append(
            AutomationFanoutCandidateStatusResponse(
                url=candidate_url or candidate.url.strip(),
                title=candidate.title,
                source=candidate.source,
                confidence=candidate.confidence,
                status="blocked" if reason else "ready",
                reason=reason,
            )
        )

    blocked_count = len([status for status in statuses if status.status == "blocked"])
    blocked_reasons = _fanout_blocked_reasons(source_drafts, blocked_count)
    return AutomationProductFanoutPreviewResponse(
        requested_parent_url=parent_url,
        analyzed_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        candidate_statuses=statuses,
        source_drafts=source_drafts,
        batch_plan=AutomationFanoutBatchPlanResponse(
            run_mode="preview_only",
            next_collector_type="ecommerce_product_page",
            ready_count=len(source_drafts),
            blocked_count=blocked_count,
            max_sources=payload.max_sources,
            fields=fields,
            manual_review_required=True,
            execution_boundary="preview_only_no_database_write",
        ),
        blocked_reasons=blocked_reasons,
    )


async def create_reviewed_product_fanout(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductFanoutCreateRequest,
) -> AutomationProductFanoutCreateResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    preview = await preview_product_fanout(
        AutomationProductFanoutPreviewRequest(
            parent_url=payload.parent_url,
            authorized=payload.authorized,
            candidates=payload.candidates,
            fields=payload.fields,
            max_sources=payload.max_sources,
        )
    )
    persisted_sources: list[AutomationFanoutPersistedSourceResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "fanout_create_requested",
            "parent_url": preview.requested_parent_url,
            "candidate_count": len(payload.candidates),
            "preview_ready_count": preview.batch_plan.ready_count,
            "preview_blocked_count": preview.batch_plan.blocked_count,
            "enable_tasks": payload.enable_tasks,
        }
    ]

    created_sources = 0
    reused_sources = 0
    enabled_tasks = 0

    for draft in preview.source_drafts:
        url = _draft_url(draft)
        if url is None:
            audit_events.append({"event": "fanout_source_skipped", "reason": "draft_url_missing"})
            continue
        existing_source = await get_source_by_type_url(
            session,
            workspace.id,
            payload.project_id,
            "ecommerce_product_page",
            url,
        )
        if existing_source is None:
            source = await create_source(
                session,
                workspace,
                SourceCreateRequest(
                    project_id=payload.project_id,
                    name=draft.suggested_name,
                    type="ecommerce_product_page",
                    url=url,
                    config=draft.config,
                    schedule_cron=None,
                ),
            )
            action = "created"
            created_sources += 1
        else:
            source = existing_source
            action = "reused"
            reused_sources += 1

        task_response: CollectionTaskResponse | None = None
        if payload.enable_tasks:
            _source, task = await enable_source(session, workspace, source.id)
            task_response = CollectionTaskResponse.from_task(task)
            enabled_tasks += 1

        persisted_sources.append(
            AutomationFanoutPersistedSourceResponse(
                url=url,
                action=action,
                source=SourceResponse.model_validate(source),
                task=task_response,
            )
        )
        audit_events.append(
            {
                "event": "fanout_source_persisted",
                "url": url,
                "action": action,
                "source_id": str(source.id),
                "task_enabled": task_response is not None,
                "run_started": False,
            }
        )

    blocked_reasons = list(preview.blocked_reasons)
    if persisted_sources:
        blocked_reasons.append("已完成持久化创建或复用，但尚未启动任何采集运行。")
    else:
        blocked_reasons.append("没有创建或复用任何商品页采集源。")
    return AutomationProductFanoutCreateResponse(
        requested_parent_url=preview.requested_parent_url,
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        persisted_sources=persisted_sources,
        candidate_statuses=preview.candidate_statuses,
        summary=AutomationFanoutCreateSummaryResponse(
            created_sources=created_sources,
            reused_sources=reused_sources,
            enabled_tasks=enabled_tasks,
            blocked_candidates=preview.batch_plan.blocked_count,
            run_started=False,
        ),
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def run_reviewed_product_batch(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductBatchRunRequest,
) -> AutomationProductBatchRunResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if len(payload.task_ids) > payload.max_tasks:
        raise CollectorError("batch_task_limit_exceeded")

    items: list[AutomationProductBatchRunItemResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_batch_run_requested",
            "requested_tasks": len(payload.task_ids),
            "max_tasks": payload.max_tasks,
            "collector_type": "ecommerce_product_page",
        }
    ]
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            items.append(_blocked_batch_item(task_id, "duplicate_task_id"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task_id),
                    "reason": "duplicate_task_id",
                }
            )
            continue
        seen_task_ids.add(task_id)

        try:
            task = await get_task_or_raise(session, workspace, task_id)
        except TaskNotFoundError:
            items.append(_blocked_batch_item(task_id, "task_not_found"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task_id),
                    "reason": "task_not_found",
                }
            )
            continue

        if task.collector_type != "ecommerce_product_page":
            items.append(_blocked_batch_item_from_task(task, "unsupported_collector_type"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task.id),
                    "collector_type": task.collector_type,
                    "reason": "unsupported_collector_type",
                }
            )
            continue
        if task.status != "enabled":
            items.append(_blocked_batch_item_from_task(task, "task_not_enabled"))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task.id),
                    "task_status": task.status,
                    "reason": "task_not_enabled",
                }
            )
            continue

        try:
            run = await run_task_now(session, workspace, task.id)
        except (TaskAlreadyRunningError, TaskNotRunnableError) as exc:
            items.append(_blocked_batch_item_from_task(task, exc.message))
            audit_events.append(
                {
                    "event": "product_batch_task_blocked",
                    "task_id": str(task.id),
                    "reason": exc.message,
                }
            )
            continue

        raw_records, reused_deduplicated_records = await _product_records_for_task_run(
            session=session,
            workspace_id=workspace.id,
            task_run_id=run.id,
            limit=500,
        )
        field_completeness = _product_field_completeness(task, raw_records)
        item_status = (
            "run_completed" if run.status in {"success", "partial_success"} else "run_failed"
        )
        effective_records_count = (
            len(raw_records) if reused_deduplicated_records else run.records_count
        )
        items.append(
            AutomationProductBatchRunItemResponse(
                task_id=task.id,
                task_name=task.name,
                source_id=task.source_id,
                source_url=_task_source_url(task),
                status=item_status,
                blocked_reason=None,
                run=run,
                records_count=effective_records_count,
                entities_count=run.entities_count,
                field_completeness=field_completeness,
                error_message=run.error_message,
            )
        )
        audit_events.append(
            {
                "event": "product_batch_task_run_completed",
                "task_id": str(task.id),
                "run_id": str(run.id),
                "status": run.status,
                "records_count": effective_records_count,
                "entities_count": run.entities_count,
                "completeness_percent": field_completeness.completeness_percent,
                "deduplicated_source_records_reused": reused_deduplicated_records,
            }
        )

    summary = _product_batch_summary(payload.task_ids, items)
    blocked_reasons: list[str] = []
    if summary.blocked_tasks > 0:
        blocked_reasons.append("部分任务未运行，需查看 blocked_reason 后再重试。")
    if summary.run_tasks == 0:
        blocked_reasons.append("没有任何商品页任务被启动。")
    else:
        blocked_reasons.append("本次仅执行用户确认的小批量任务，没有创建调度或自动循环。")

    return AutomationProductBatchRunResponse(
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        items=items,
        summary=summary,
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def preview_product_dataset(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDatasetPreviewRequest,
) -> AutomationProductDatasetPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    selected_fields = _dataset_fields(payload.fields)
    rows: list[AutomationProductDatasetRowResponse] = []
    matched_run_ids: set[uuid.UUID] = set()
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_dataset_preview_requested",
            "requested_runs": len(payload.task_run_ids),
            "max_rows": payload.max_rows,
            "fields": selected_fields,
        }
    ]

    for task_run_id in payload.task_run_ids:
        product_records, reused_deduplicated_records = await _product_records_for_task_run(
            session=session,
            workspace_id=workspace.id,
            task_run_id=task_run_id,
            limit=payload.max_rows,
        )
        if not product_records:
            audit_events.append(
                {
                    "event": "product_dataset_run_skipped",
                    "task_run_id": str(task_run_id),
                    "reason": "no_product_page_records",
                }
            )
            continue
        if reused_deduplicated_records:
            audit_events.append(
                {
                    "event": "product_dataset_run_reused_deduplicated_source_records",
                    "task_run_id": str(task_run_id),
                    "records_count": len(product_records),
                }
            )
        matched_run_ids.add(task_run_id)
        for raw_record in product_records:
            if len(rows) >= payload.max_rows:
                break
            row = _dataset_row(raw_record, selected_fields)
            rows.append(row)
        if len(rows) >= payload.max_rows:
            audit_events.append(
                {
                    "event": "product_dataset_row_limit_reached",
                    "max_rows": payload.max_rows,
                }
            )
            break

    summary = _dataset_summary(payload.task_run_ids, matched_run_ids, rows, selected_fields)
    blocked_reasons: list[str] = []
    if summary.rows_count == 0:
        blocked_reasons.append("未找到可进入数据集预览的商品页采集记录。")
    if summary.rows_count >= payload.max_rows:
        blocked_reasons.append("数据集预览已达到本次最大行数限制。")
    blocked_reasons.append("当前为只读数据集预览，尚未保存 Dataset 或写出导出文件。")

    return AutomationProductDatasetPreviewResponse(
        created_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        rows=rows,
        summary=summary,
        cleaning_script_draft=_cleaning_script_draft(selected_fields),
        export_preview=_dataset_export_preview(rows, selected_fields),
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def save_product_dataset_version(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationProductDatasetSaveRequest,
) -> AutomationProductDatasetSaveResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    dataset_name = payload.name.strip()
    if not dataset_name:
        raise CollectorError("dataset_name_required")
    preview = await preview_product_dataset(session, workspace, payload)
    if not preview.rows:
        raise CollectorError("dataset_preview_empty")

    raw_records = await _dataset_product_raw_records(
        session,
        workspace.id,
        payload.task_run_ids,
        payload.max_rows,
    )
    project_ids = {raw_record.project_id for raw_record in raw_records}
    if len(project_ids) != 1:
        raise CollectorError("dataset_project_lineage_ambiguous")
    project_id = next(iter(project_ids))

    dataset = await get_dataset_by_name(session, workspace.id, dataset_name)
    created_dataset = False
    if dataset is None:
        dataset = Dataset(
            workspace_id=workspace.id,
            project_id=project_id,
            name=dataset_name,
            dataset_type="ecommerce_product",
            status="active",
            description=payload.description.strip() if payload.description else None,
        )
        session.add(dataset)
        await session.flush()
        created_dataset = True
    elif dataset.project_id != project_id:
        raise CollectorError("dataset_project_lineage_conflict")

    latest_version = await get_latest_dataset_version(session, dataset.id)
    next_version_number = 1 if latest_version is None else latest_version.version_number + 1
    created_at = datetime.now(UTC)
    version = DatasetVersion(
        dataset_id=dataset.id,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        created_by_user_id=user.id,
        version_number=next_version_number,
        source_task_run_ids=[str(task_run_id) for task_run_id in payload.task_run_ids],
        selected_fields=preview.summary.selected_fields,
        cleaning_script=preview.cleaning_script_draft,
        rows=[
            {
                "row_id": row.row_id,
                "task_run_id": str(row.task_run_id),
                "raw_record_id": str(row.raw_record_id),
                "source_url": row.source_url,
                "values": row.values,
                "missing_fields": row.missing_fields,
                "completeness_percent": row.completeness_percent,
            }
            for row in preview.rows
        ],
        export_preview=preview.export_preview,
        row_count=preview.summary.rows_count,
        average_completeness_percent=preview.summary.average_completeness_percent,
        status="saved",
        created_at=created_at,
    )
    session.add(version)
    await session.commit()
    await session.refresh(dataset)
    await session.refresh(version)

    return AutomationProductDatasetSaveResponse(
        saved_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        audit_events=[
            {
                "event": "product_dataset_version_saved",
                "dataset_id": str(dataset.id),
                "version_id": str(version.id),
                "version_number": version.version_number,
                "created_dataset": created_dataset,
                "row_count": version.row_count,
            }
        ],
        blocked_reasons=[
            "Dataset 版本已保存；尚未写出文件、对象存储导出或自动调度。"
        ],
    )


async def approve_product_schedule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductScheduleApproveRequest,
) -> AutomationProductScheduleApproveResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    version = await get_dataset_version(
        session,
        workspace.id,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    if dataset is None or version is None:
        raise CollectorError("dataset_version_not_found")
    if version.average_completeness_percent < payload.minimum_completeness_percent:
        raise CollectorError("dataset_quality_gate_failed")

    schedule_cron = payload.schedule_cron.strip() if payload.schedule_cron else None
    if schedule_cron is not None:
        try:
            cron_interval(schedule_cron)
        except UnsupportedCronExpression as exc:
            raise CollectorError("schedule_cron_unsupported") from exc

    approved_at = datetime.now(UTC)
    approved_tasks: list[AutomationScheduleApprovedTaskResponse] = []
    blocked_tasks: list[AutomationScheduleBlockedTaskResponse] = []
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            blocked_tasks.append(
                AutomationScheduleBlockedTaskResponse(
                    task_id=task_id,
                    reason="duplicate_task_id",
                )
            )
            continue
        seen_task_ids.add(task_id)
        task = await get_task(session, workspace.id, task_id)
        reason = _schedule_task_block_reason(task, dataset)
        if reason is not None:
            blocked_tasks.append(
                AutomationScheduleBlockedTaskResponse(task_id=task_id, reason=reason)
            )
            continue

        assert task is not None
        task.schedule_cron = schedule_cron
        task.config = _approved_schedule_config(
            task.config,
            dataset=dataset,
            version=version,
            payload=payload,
            approved_at=approved_at,
        )
        approved_tasks.append(
            AutomationScheduleApprovedTaskResponse(
                task_id=task.id,
                task_name=task.name,
                status=task.status,
                schedule_cron=task.schedule_cron,
                schedule_policy=payload.schedule_policy,
                freshness_target_hours=payload.freshness_target_hours,
                dataset_id=dataset.id,
                dataset_version_id=version.id,
                approved_at=approved_at,
            )
        )

    await session.commit()

    blocked_reasons = ["调度审批只更新 Task 配置，不会立即启动采集运行。"]
    if blocked_tasks:
        blocked_reasons.append("部分 Task 未通过调度审批条件，已在 blocked_tasks 中列出。")
    if not approved_tasks:
        blocked_reasons.append("没有 Task 进入已审批调度状态。")

    return AutomationProductScheduleApproveResponse(
        approved_at=approved_at,
        authorization_confirmed=payload.authorized,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        approved_tasks=approved_tasks,
        blocked_tasks=blocked_tasks,
        summary=AutomationProductScheduleApproveSummaryResponse(
            requested_tasks=len(payload.task_ids),
            approved_tasks=len(approved_tasks),
            blocked_tasks=len(blocked_tasks),
            run_started=False,
        ),
        audit_events=[
            {
                "event": "product_schedule_approved",
                "dataset_id": str(dataset.id),
                "dataset_version_id": str(version.id),
                "approved_tasks": len(approved_tasks),
                "blocked_tasks": len(blocked_tasks),
                "run_started": False,
            }
        ],
        blocked_reasons=blocked_reasons,
    )


async def check_product_drift(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftCheckRequest,
) -> AutomationProductDriftCheckResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    version = await get_dataset_version(
        session,
        workspace.id,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    if dataset is None or version is None:
        raise CollectorError("dataset_version_not_found")

    checked_at = datetime.now(UTC)
    items: list[AutomationProductDriftItemResponse] = []
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_drift_check_requested",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "requested_tasks": len(payload.task_ids),
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
            "run_started": False,
            "alert_created": False,
        }
    ]
    seen_task_ids: set[uuid.UUID] = set()

    for task_id in payload.task_ids:
        if task_id in seen_task_ids:
            items.append(_blocked_drift_item(task_id, version, "duplicate_task_id"))
            audit_events.append(
                {
                    "event": "product_drift_task_blocked",
                    "task_id": str(task_id),
                    "reason": "duplicate_task_id",
                }
            )
            continue
        seen_task_ids.add(task_id)

        task = await get_task(session, workspace.id, task_id)
        reason = _drift_task_block_reason(task, dataset, version)
        if reason is not None:
            items.append(_blocked_drift_item(task_id, version, reason, task))
            audit_events.append(
                {
                    "event": "product_drift_task_blocked",
                    "task_id": str(task_id),
                    "reason": reason,
                }
            )
            continue

        assert task is not None
        latest_runs = await list_task_runs(session, workspace.id, task.id)
        latest_run = latest_runs[0] if latest_runs else None
        approved_fields = _dataset_fields(version.selected_fields)
        issues: list[str] = []
        latest_completeness_percent: int | None = None
        completeness_drop_percent: int | None = None
        missing_fields: list[str] = []
        new_missing_fields: list[str] = []
        reused_deduplicated_records = False

        if latest_run is None:
            issues.append("latest_run_missing")
        elif latest_run.status not in {"success", "partial_success"}:
            issues.append("latest_run_failed")
        else:
            product_records, reused_deduplicated_records = await _product_records_for_task_run(
                session=session,
                workspace_id=workspace.id,
                task_run_id=latest_run.id,
                limit=500,
            )
            field_completeness = _product_field_completeness_for_fields(
                product_records,
                approved_fields,
            )
            latest_completeness_percent = field_completeness.completeness_percent
            completeness_drop_percent = max(
                version.average_completeness_percent - latest_completeness_percent,
                0,
            )
            missing_fields = field_completeness.missing_fields
            new_missing_fields = [
                field for field in approved_fields if field in field_completeness.missing_fields
            ]
            if completeness_drop_percent > payload.completeness_drop_threshold_percent:
                issues.append("completeness_drift_exceeded")
            if new_missing_fields:
                issues.append("approved_fields_missing")

        freshness_target_hours, stale_hours = _task_freshness_drift(
            task,
            checked_at,
            payload.freshness_grace_hours,
        )
        if stale_hours is not None and stale_hours > 0:
            issues.append("freshness_target_missed")

        status = _drift_status(issues)
        items.append(
            AutomationProductDriftItemResponse(
                task_id=task.id,
                task_name=task.name,
                source_url=_task_source_url(task),
                status=status,
                blocked_reason=None,
                latest_run_id=latest_run.id if latest_run else None,
                latest_run_status=latest_run.status if latest_run else None,
                dataset_version_completeness_percent=version.average_completeness_percent,
                latest_completeness_percent=latest_completeness_percent,
                completeness_drop_percent=completeness_drop_percent,
                missing_fields=missing_fields,
                new_missing_fields=new_missing_fields,
                freshness_target_hours=freshness_target_hours,
                stale_hours=stale_hours,
                issues=issues,
            )
        )
        audit_events.append(
            {
                "event": "product_drift_task_checked",
                "task_id": str(task.id),
                "latest_run_id": str(latest_run.id) if latest_run else None,
                "status": status,
                "issues": issues,
                "run_started": False,
                "alert_created": False,
                "deduplicated_source_records_reused": (
                    reused_deduplicated_records if latest_run else False
                ),
            }
        )

    summary = _product_drift_summary(payload.task_ids, items)
    blocked_reasons = ["漂移检查为只读评估，不会启动采集、创建告警或发送通知。"]
    if summary.blocked_tasks:
        blocked_reasons.append("部分 Task 未通过 DatasetVersion 审批谱系或类型校验。")
    if summary.critical_tasks:
        blocked_reasons.append("存在关键漂移，请先复核字段缺失、采集失败或数据集基准。")
    elif summary.warning_tasks:
        blocked_reasons.append("存在轻度漂移或新鲜度风险，建议在下次调度前复核。")

    return AutomationProductDriftCheckResponse(
        checked_at=checked_at,
        authorization_confirmed=payload.authorized,
        dataset=AutomationDatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            status=dataset.status,
            description=dataset.description,
        ),
        version=AutomationDatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            source_task_run_ids=version.source_task_run_ids,
            selected_fields=version.selected_fields,
            cleaning_script=version.cleaning_script,
            row_count=version.row_count,
            average_completeness_percent=version.average_completeness_percent,
            status=version.status,
            created_at=version.created_at,
            export_preview=version.export_preview,
        ),
        items=items,
        summary=summary,
        audit_events=audit_events,
        blocked_reasons=blocked_reasons,
    )


async def save_product_drift_event(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftEventSaveRequest,
) -> AutomationProductDriftEventResponse:
    checked = await check_product_drift(session, workspace, payload)
    created_at = datetime.now(UTC)
    event_status = _drift_event_status(checked.summary)
    audit_events = [
        *checked.audit_events,
        {
            "event": "product_drift_event_saved",
            "dataset_id": str(checked.dataset.id),
            "dataset_version_id": str(checked.version.id),
            "status": event_status,
            "run_started": False,
            "alert_created": False,
        },
    ]
    event = DatasetDriftEvent(
        workspace_id=workspace.id,
        project_id=checked.dataset.project_id,
        dataset_id=checked.dataset.id,
        dataset_version_id=checked.version.id,
        event_type="ecommerce_product_drift",
        status=event_status,
        thresholds={
            "completeness_drop_threshold_percent": payload.completeness_drop_threshold_percent,
            "freshness_grace_hours": payload.freshness_grace_hours,
        },
        summary=checked.summary.model_dump(mode="json"),
        items=[item.model_dump(mode="json") for item in checked.items],
        audit_events=audit_events,
        note=payload.note.strip() if payload.note and payload.note.strip() else None,
        created_at=created_at,
    )
    saved_event = await create_dataset_drift_event(session, event)
    return _drift_event_response(saved_event, checked.dataset, checked.version)


async def list_product_drift_events(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID | None = None,
    dataset_version_id: uuid.UUID | None = None,
    limit: int = 20,
) -> AutomationProductDriftEventListResponse:
    events = await list_dataset_drift_events(
        session,
        workspace.id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        limit=limit,
    )
    responses: list[AutomationProductDriftEventResponse] = []
    for event in events:
        dataset = await get_dataset(session, workspace.id, event.dataset_id)
        version = await get_dataset_version(
            session,
            workspace.id,
            event.dataset_id,
            event.dataset_version_id,
        )
        if dataset is None or version is None:
            continue
        responses.append(_drift_event_response(event, dataset, version))
    return AutomationProductDriftEventListResponse(
        items=responses,
        total=len(responses),
        run_started=False,
        alert_created=False,
    )


async def list_product_datasets(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None = None,
    limit: int = 50,
) -> AutomationProductDatasetListResponse:
    datasets = await list_datasets(
        session,
        workspace.id,
        project_id=project_id,
        limit=limit,
    )
    items: list[AutomationProductDatasetListItemResponse] = []
    for dataset in datasets:
        latest_version = await get_latest_dataset_version(session, dataset.id)
        latest_events = await list_dataset_drift_events(
            session,
            workspace.id,
            dataset_id=dataset.id,
            limit=1,
        )
        latest_drift_event: AutomationProductDriftEventResponse | None = None
        if latest_events:
            event = latest_events[0]
            event_version = await get_dataset_version(
                session,
                workspace.id,
                event.dataset_id,
                event.dataset_version_id,
            )
            if event_version is not None:
                latest_drift_event = _drift_event_response(event, dataset, event_version)
        items.append(
            AutomationProductDatasetListItemResponse(
                dataset=_dataset_response(dataset),
                latest_version=(
                    _dataset_version_response(latest_version)
                    if latest_version is not None
                    else None
                ),
                version_count=await count_dataset_versions(session, workspace.id, dataset.id),
                latest_drift_event=latest_drift_event,
                drift_event_count=await count_dataset_drift_events(
                    session,
                    workspace.id,
                    dataset_id=dataset.id,
                ),
            )
        )
    return AutomationProductDatasetListResponse(
        items=items,
        total=len(items),
        run_started=False,
        alert_created=False,
    )


async def list_product_dataset_versions(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    limit: int = 50,
) -> AutomationProductDatasetVersionListResponse:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    versions = await list_dataset_versions(
        session,
        workspace.id,
        dataset_id,
        limit=limit,
    )
    return AutomationProductDatasetVersionListResponse(
        dataset=_dataset_response(dataset),
        versions=[_dataset_version_response(version) for version in versions],
        total=await count_dataset_versions(session, workspace.id, dataset_id),
        run_started=False,
        alert_created=False,
    )


async def create_product_dataset_export(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    payload: AutomationProductDatasetExportCreateRequest,
) -> AutomationProductDatasetExportJobResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("dataset_export_confirmation_required")

    dataset, version = await _get_dataset_and_version(
        session,
        workspace,
        payload.dataset_id,
        payload.dataset_version_id,
    )
    export_format = payload.export_format
    job_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    filename = _dataset_export_filename(dataset, version, job_id, export_format)
    target_path = _dataset_export_path(
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        version_id=version.id,
        filename=filename,
    )
    audit_events: list[dict[str, object]] = [
        {
            "event": "product_dataset_export_requested",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "export_format": export_format,
            "row_count": version.row_count,
            "run_started": False,
        }
    ]

    content = _render_dataset_export(dataset, version, export_format)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(f"{target_path.name}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(target_path)

    checksum = hashlib.sha256(content).hexdigest()
    finished_at = datetime.now(UTC)
    export_job = DatasetExportJob(
        id=job_id,
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        created_by_user_id=user.id,
        export_format=export_format,
        status="success",
        filename=filename,
        content_type=DATASET_EXPORT_CONTENT_TYPES[export_format],
        artifact_path=str(target_path),
        artifact_size_bytes=len(content),
        row_count=version.row_count,
        checksum_sha256=checksum,
        error_message=None,
        audit_events=[
            *audit_events,
            {
                "event": "product_dataset_export_file_written",
                "artifact_size_bytes": len(content),
                "checksum_sha256": checksum,
                "run_started": False,
            },
        ],
        created_at=created_at,
        finished_at=finished_at,
    )
    created_job = await create_dataset_export_job(session, export_job)
    return _dataset_export_job_response(created_job, dataset, version)


async def list_product_dataset_exports(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID | None = None,
    limit: int = 20,
) -> AutomationProductDatasetExportListResponse:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    if dataset_version_id is not None:
        version = await get_dataset_version(session, workspace.id, dataset.id, dataset_version_id)
        if version is None:
            raise CollectorError("dataset_version_not_found")
    jobs = await list_dataset_export_jobs(
        session,
        workspace.id,
        dataset.id,
        dataset_version_id=dataset_version_id,
        limit=limit,
    )
    items: list[AutomationProductDatasetExportJobResponse] = []
    for job in jobs:
        version = await get_dataset_version(
            session,
            workspace.id,
            job.dataset_id,
            job.dataset_version_id,
        )
        if version is None:
            continue
        items.append(_dataset_export_job_response(job, dataset, version))
    return AutomationProductDatasetExportListResponse(
        items=items,
        total=len(items),
        export_created=False,
        run_started=False,
    )


async def get_product_dataset_export_file(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    dataset_version_id: uuid.UUID,
    export_job_id: uuid.UUID,
) -> tuple[DatasetExportJob, Path]:
    dataset, version = await _get_dataset_and_version(
        session,
        workspace,
        dataset_id,
        dataset_version_id,
    )
    export_job = await get_dataset_export_job(
        session,
        workspace.id,
        dataset.id,
        version.id,
        export_job_id,
    )
    if export_job is None:
        raise CollectorError("dataset_export_not_found")
    if export_job.status != "success":
        raise CollectorError("dataset_export_not_ready")
    artifact_path = Path(export_job.artifact_path).resolve()
    export_root = _dataset_export_root().resolve()
    try:
        artifact_path.relative_to(export_root)
    except ValueError as exc:
        raise CollectorError("dataset_export_artifact_outside_root") from exc
    if not artifact_path.is_file():
        raise CollectorError("dataset_export_file_missing")
    return export_job, artifact_path


async def preview_product_drift_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertPreviewRequest,
) -> AutomationProductDriftAlertPreviewResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    latest_version = (
        await get_dataset_version(
            session,
            workspace.id,
            dataset.id,
            payload.dataset_version_id,
        )
        if payload.dataset_version_id is not None
        else await get_latest_dataset_version(session, dataset.id)
    )
    if payload.dataset_version_id is not None and latest_version is None:
        raise CollectorError("dataset_version_not_found")

    statuses = _drift_alert_statuses(payload.min_status)
    events = await list_dataset_drift_events(
        session,
        workspace.id,
        dataset_id=dataset.id,
        dataset_version_id=payload.dataset_version_id,
        limit=payload.limit,
    )
    matched_event_models = [event for event in events if event.status in statuses]
    matched_events: list[AutomationProductDriftEventResponse] = []
    for event in matched_event_models:
        event_version = await get_dataset_version(
            session,
            workspace.id,
            event.dataset_id,
            event.dataset_version_id,
        )
        if event_version is None:
            continue
        matched_events.append(_drift_event_response(event, dataset, event_version))

    rule_draft = _drift_alert_rule_draft(
        dataset=dataset,
        latest_version=latest_version,
        min_status=payload.min_status,
        channel=payload.channel,
        enabled=payload.enabled,
        name=payload.name,
    )
    return _drift_alert_preview_response(
        dataset=dataset,
        latest_version=latest_version,
        rule_draft=rule_draft,
        matched_events=matched_events,
        authorization_confirmed=payload.authorized,
        alert_rule_created=False,
    )


async def create_product_drift_alert_rule(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertRuleCreateRequest,
) -> AutomationProductDriftAlertRuleCreateResponse:
    if not payload.confirm_create:
        raise CollectorError("drift_alert_rule_confirmation_required")
    preview = await preview_product_drift_alert_rule(session, workspace, payload)
    rule = await create_alert_rule_from_payload(
        session,
        workspace,
        AlertRuleCreateRequest(
            name=preview.rule_draft.name,
            project_id=preview.rule_draft.project_id,
            signal_type=preview.rule_draft.signal_type,
            condition=preview.rule_draft.condition,
            channel=preview.rule_draft.channel,
            enabled=preview.rule_draft.enabled,
        ),
    )
    return AutomationProductDriftAlertRuleCreateResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=preview.authorization_confirmed,
        dataset=preview.dataset,
        latest_version=preview.latest_version,
        rule_draft=preview.rule_draft,
        matched_events=preview.matched_events,
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=preview.summary.matched_events,
            critical_events=preview.summary.critical_events,
            warning_events=preview.summary.warning_events,
            alert_rule_created=True,
            signal_created=False,
            alert_event_created=False,
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "已创建 DriftEvent 告警策略；本次不会回放历史事件、"
                "创建 Signal、AlertEvent 或发送通知。"
            ),
            "后续需要 DatasetDrift 信号桥接后，规则才会进入现有 AlertEvent 生成链路。",
        ],
        alert_rule=AlertRuleResponse.from_model(rule),
    )


async def create_product_drift_alert_events(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertEventCreateRequest,
) -> AutomationProductDriftAlertEventCreateResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_create:
        raise CollectorError("drift_alert_event_confirmation_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(
        session,
        workspace.id,
        dataset.id,
        payload.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    drift_event = await get_dataset_drift_event(
        session,
        workspace.id,
        payload.drift_event_id,
    )
    if drift_event is None:
        raise CollectorError("dataset_drift_event_not_found")
    if drift_event.dataset_id != dataset.id or drift_event.dataset_version_id != version.id:
        raise CollectorError("dataset_drift_event_lineage_mismatch")

    signal, signal_created = await _create_or_reuse_dataset_drift_signal(
        session=session,
        workspace=workspace,
        dataset=dataset,
        version=version,
        drift_event=drift_event,
    )
    alert_events = await match_alert_rules_for_signal(
        session,
        workspace,
        signal,
        intelligence=None,
        deliver_notifications=False,
    )
    await session.commit()
    await session.refresh(signal)
    for event in alert_events:
        await session.refresh(event)

    return AutomationProductDriftAlertEventCreateResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        drift_event=_drift_event_response(drift_event, dataset, version),
        signal=SignalResponse.from_model(signal),
        alert_events=[AlertEventResponse.from_model(event) for event in alert_events],
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=1,
            critical_events=1 if drift_event.status == "critical" else 0,
            warning_events=1 if drift_event.status == "warning" else 0,
            alert_rule_created=False,
            signal_created=signal_created,
            alert_event_created=bool(alert_events),
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "本次只桥接已保存 DriftEvent 到 Signal/AlertEvent；"
                "不会启动采集、创建 TaskRun、发送通知或写出文件。"
            ),
        ],
    )


async def send_product_drift_alert_notifications(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertNotificationSendRequest,
) -> AutomationProductDriftAlertNotificationSendResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_send:
        raise CollectorError("drift_alert_notification_confirmation_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(
        session,
        workspace.id,
        dataset.id,
        payload.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    drift_event = await get_dataset_drift_event(
        session,
        workspace.id,
        payload.drift_event_id,
    )
    if drift_event is None:
        raise CollectorError("dataset_drift_event_not_found")
    if drift_event.dataset_id != dataset.id or drift_event.dataset_version_id != version.id:
        raise CollectorError("dataset_drift_event_lineage_mismatch")

    alert_events = []
    notifications = []
    notification_created = False
    now = datetime.now(UTC)
    for alert_event_id in list(dict.fromkeys(payload.alert_event_ids)):
        event = await get_alert_event(session, workspace.id, alert_event_id)
        if event is None:
            raise CollectorError("alert_event_not_found")
        signal = await get_signal(session, workspace.id, event.signal_id)
        if signal is None:
            raise CollectorError("alert_event_signal_not_found")
        _assert_dataset_drift_alert_event_matches(
            signal=signal,
            dataset=dataset,
            version=version,
            drift_event=drift_event,
        )
        rule = await get_alert_rule(session, workspace.id, event.rule_id)
        if rule is None:
            raise CollectorError("alert_event_rule_not_found")
        if rule.channel not in {"in_app", "both"}:
            raise CollectorError("alert_event_channel_not_in_app")

        notification = await get_notification_by_reference(
            session=session,
            user_id=workspace.owner_id,
            reference_type="alert_event",
            reference_id=event.id,
            notification_type="alert",
        )
        if notification is None:
            notification = await create_in_app_notification(
                session=session,
                user_id=workspace.owner_id,
                title=f"数据集漂移告警：{dataset.name}",
                body=(
                    f"{drift_event.event_type} 已命中 {rule.name}；"
                    f"状态 {drift_event.status}，请复核字段完整率与刷新策略。"
                ),
                notification_type="alert",
                reference_type="alert_event",
                reference_id=event.id,
            )
            notification_created = True
        event.status = "sent"
        if event.sent_at is None:
            event.sent_at = now
        alert_events.append(event)
        notifications.append(notification)

    await session.commit()
    for event in alert_events:
        await session.refresh(event)
    for notification in notifications:
        await session.refresh(notification)

    return AutomationProductDriftAlertNotificationSendResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        drift_event=_drift_event_response(drift_event, dataset, version),
        alert_events=[AlertEventResponse.from_model(event) for event in alert_events],
        notifications=[
            NotificationResponse.from_model(notification) for notification in notifications
        ],
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=len(alert_events),
            critical_events=len(alert_events) if drift_event.status == "critical" else 0,
            warning_events=len(alert_events) if drift_event.status == "warning" else 0,
            alert_rule_created=False,
            signal_created=False,
            alert_event_created=False,
            notification_created=notification_created,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "本次只发送已生成 AlertEvent 的站内通知；不会启动采集、"
                "创建 TaskRun、发送邮件、修改调度或写出文件。"
            ),
        ],
    )


async def send_product_drift_alert_emails(
    session: AsyncSession,
    workspace: Workspace,
    payload: AutomationProductDriftAlertEmailSendRequest,
) -> AutomationProductDriftAlertEmailSendResponse:
    if not payload.authorized:
        raise CollectorError("automation_authorization_required")
    if not payload.confirm_send:
        raise CollectorError("drift_alert_email_confirmation_required")

    dataset = await get_dataset(session, workspace.id, payload.dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(
        session,
        workspace.id,
        dataset.id,
        payload.dataset_version_id,
    )
    if version is None:
        raise CollectorError("dataset_version_not_found")
    drift_event = await get_dataset_drift_event(
        session,
        workspace.id,
        payload.drift_event_id,
    )
    if drift_event is None:
        raise CollectorError("dataset_drift_event_not_found")
    if drift_event.dataset_id != dataset.id or drift_event.dataset_version_id != version.id:
        raise CollectorError("dataset_drift_event_lineage_mismatch")

    owner = await get_user_by_id(session, workspace.owner_id)
    if owner is None:
        raise CollectorError("workspace_owner_not_found")
    recipient_email = payload.recipient_email or owner.email

    email_deliveries: list[AutomationProductDriftAlertEmailDeliveryResponse] = []
    alert_events: list[AlertEvent] = []
    now = datetime.now(UTC)
    for alert_event_id in list(dict.fromkeys(payload.alert_event_ids)):
        event = await get_alert_event(session, workspace.id, alert_event_id)
        if event is None:
            raise CollectorError("alert_event_not_found")
        signal = await get_signal(session, workspace.id, event.signal_id)
        if signal is None:
            raise CollectorError("alert_event_signal_not_found")
        _assert_dataset_drift_alert_event_matches(
            signal=signal,
            dataset=dataset,
            version=version,
            drift_event=drift_event,
        )
        rule = await get_alert_rule(session, workspace.id, event.rule_id)
        if rule is None:
            raise CollectorError("alert_event_rule_not_found")
        if rule.channel not in {"email", "both"}:
            raise CollectorError("alert_event_channel_not_email")

        email_result = await send_email_notification(
            recipient_email=recipient_email,
            subject=f"数据集漂移告警：{dataset.name}",
            body=(
                f"漂移事件 {drift_event.event_type} 已命中 {rule.name}。"
                f"状态：{drift_event.status}，请复核字段完整率与刷新策略。"
            ),
        )
        email_deliveries.append(
            AutomationProductDriftAlertEmailDeliveryResponse(
                alert_event_id=event.id,
                recipient_email=recipient_email,
                delivered=email_result.delivered,
                delivered_at=now if email_result.delivered else None,
                reason=email_result.reason,
            )
        )
        alert_events.append(event)

    return AutomationProductDriftAlertEmailSendResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=payload.authorized,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        drift_event=_drift_event_response(drift_event, dataset, version),
        alert_events=[AlertEventResponse.from_model(event) for event in alert_events],
        email_deliveries=email_deliveries,
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=len(alert_events),
            critical_events=len(alert_events) if drift_event.status == "critical" else 0,
            warning_events=len(alert_events) if drift_event.status == "warning" else 0,
            alert_rule_created=False,
            signal_created=False,
            alert_event_created=False,
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=[
            (
                "本次只发送已生成 AlertEvent 的邮件告警；不会启动采集、"
                "创建 TaskRun、发送站内通知、修改调度或写出文件。"
            ),
        ],
    )


def _assert_dataset_drift_alert_event_matches(
    *,
    signal: Signal,
    dataset: Dataset,
    version: DatasetVersion,
    drift_event: DatasetDriftEvent,
) -> None:
    if signal.signal_type != "dataset_drift":
        raise CollectorError("alert_event_signal_type_mismatch")
    if signal.project_id != dataset.project_id:
        raise CollectorError("alert_event_project_mismatch")
    metadata = signal.metadata_json if isinstance(signal.metadata_json, dict) else {}
    expected = {
        "source": "dataset_drift_event",
        "dataset_id": str(dataset.id),
        "dataset_version_id": str(version.id),
        "drift_event_id": str(drift_event.id),
        "event_type": drift_event.event_type,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise CollectorError("alert_event_dataset_drift_mismatch")


def _drift_alert_statuses(min_status: str) -> set[str]:
    if min_status == "warning":
        return {"warning", "critical"}
    return {"critical"}


def _drift_alert_severities(min_status: str) -> list[str]:
    if min_status == "warning":
        return ["medium", "high"]
    return ["high"]


def _drift_alert_rule_draft(
    *,
    dataset: Dataset,
    latest_version: DatasetVersion | None,
    min_status: str,
    channel: str,
    enabled: bool,
    name: str | None,
) -> AutomationProductDriftAlertRuleDraftResponse:
    normalized_name = name.strip() if name and name.strip() else None
    return AutomationProductDriftAlertRuleDraftResponse(
        name=normalized_name or f"Dataset drift alert: {dataset.name}",
        project_id=dataset.project_id,
        signal_type="dataset_drift",
        condition={
            "field": "severity",
            "op": "in",
            "value": _drift_alert_severities(min_status),
            "source": "dataset_drift_event",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(latest_version.id) if latest_version else None,
            "drift_statuses": sorted(_drift_alert_statuses(min_status)),
            "event_type": "ecommerce_product_drift",
        },
        channel=channel,
        enabled=enabled,
    )


def _drift_alert_preview_response(
    *,
    dataset: Dataset,
    latest_version: DatasetVersion | None,
    rule_draft: AutomationProductDriftAlertRuleDraftResponse,
    matched_events: list[AutomationProductDriftEventResponse],
    authorization_confirmed: bool,
    alert_rule_created: bool,
) -> AutomationProductDriftAlertPreviewResponse:
    critical_events = len([event for event in matched_events if event.status == "critical"])
    warning_events = len([event for event in matched_events if event.status == "warning"])
    blocked_reasons = [
        "告警策略预览只读取已保存 DriftEvent，不会创建 AlertRule、Signal、AlertEvent 或通知。",
    ]
    if not matched_events:
        blocked_reasons.append("当前筛选条件下没有匹配的历史 DriftEvent；策略仍可用于后续事件。")
    return AutomationProductDriftAlertPreviewResponse(
        generated_at=datetime.now(UTC),
        authorization_confirmed=authorization_confirmed,
        dataset=_dataset_response(dataset),
        latest_version=(
            _dataset_version_response(latest_version)
            if latest_version is not None
            else None
        ),
        rule_draft=rule_draft,
        matched_events=matched_events,
        summary=AutomationProductDriftAlertSummaryResponse(
            matched_events=len(matched_events),
            critical_events=critical_events,
            warning_events=warning_events,
            alert_rule_created=alert_rule_created,
            signal_created=False,
            alert_event_created=False,
            notification_created=False,
            run_started=False,
        ),
        blocked_reasons=blocked_reasons,
    )


async def _create_or_reuse_dataset_drift_signal(
    *,
    session: AsyncSession,
    workspace: Workspace,
    dataset: Dataset,
    version: DatasetVersion,
    drift_event: DatasetDriftEvent,
) -> tuple[Signal, bool]:
    existing = await _existing_dataset_drift_signal(session, workspace, drift_event)
    if existing is not None:
        return existing, False

    task_run, task = await _dataset_version_anchor_task(session, workspace, version)
    now = datetime.now(UTC)
    raw_record = RawRecord(
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        source_id=task.source_id,
        task_run_id=task_run.id,
        record_type="dataset_drift_event",
        source_url=dataset.name,
        content={
            "source": "dataset_drift_event",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "drift_event_id": str(drift_event.id),
            "event_type": drift_event.event_type,
            "status": drift_event.status,
            "summary": drift_event.summary,
            "thresholds": drift_event.thresholds,
            "items": drift_event.items,
        },
        content_hash=_stable_json_hash(
            {
                "record_type": "dataset_drift_event",
                "drift_event_id": str(drift_event.id),
            }
        ),
        screenshot_url=None,
        collected_at=drift_event.created_at,
        created_at=now,
    )
    session.add(raw_record)
    await session.flush()

    entity = await _upsert_dataset_entity(
        session=session,
        workspace=workspace,
        dataset=dataset,
        version=version,
        drift_event=drift_event,
    )
    previous_snapshot = (
        await get_entity_snapshot(session, entity.latest_snapshot_id)
        if entity.latest_snapshot_id is not None
        else None
    )
    if previous_snapshot is None:
        previous_snapshot = EntitySnapshot(
            entity_id=entity.id,
            raw_record_id=raw_record.id,
            snapshot_data={
                "dataset_id": str(dataset.id),
                "dataset_version_id": str(version.id),
                "event_type": "dataset_baseline",
                "status": version.status,
                "selected_fields": version.selected_fields,
                "row_count": version.row_count,
                "average_completeness_percent": version.average_completeness_percent,
            },
            metrics={
                "critical_tasks": 0,
                "warning_tasks": 0,
                "missing_field_tasks": 0,
                "average_completeness_percent": version.average_completeness_percent,
            },
            captured_at=version.created_at,
            created_at=now,
        )
        session.add(previous_snapshot)
        await session.flush()

    current_snapshot = EntitySnapshot(
        entity_id=entity.id,
        raw_record_id=raw_record.id,
        snapshot_data={
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "drift_event_id": str(drift_event.id),
            "event_type": drift_event.event_type,
            "status": drift_event.status,
            "summary": drift_event.summary,
            "thresholds": drift_event.thresholds,
            "items": drift_event.items,
        },
        metrics={
            "critical_tasks": _summary_number(drift_event.summary, "critical_tasks"),
            "warning_tasks": _summary_number(drift_event.summary, "warning_tasks"),
            "missing_field_tasks": _summary_number(drift_event.summary, "missing_field_tasks"),
            "checked_tasks": _summary_number(drift_event.summary, "checked_tasks"),
        },
        captured_at=drift_event.created_at,
        created_at=now,
    )
    session.add(current_snapshot)
    await session.flush()

    entity.latest_snapshot_id = current_snapshot.id
    entity.last_seen_at = drift_event.created_at
    entity.name = dataset.name

    current_value = _dataset_drift_signal_value(drift_event)
    signal = Signal(
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        entity_id=entity.id,
        signal_type="dataset_drift",
        previous_snapshot_id=previous_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        current_value=current_value,
        previous_value=0.0,
        delta=current_value,
        delta_ratio=None,
        confidence=90.0 if drift_event.status == "critical" else 80.0,
        severity=_dataset_drift_signal_severity(drift_event.status),
        metadata_json={
            "source": "dataset_drift_event",
            "dataset_id": str(dataset.id),
            "dataset_version_id": str(version.id),
            "drift_event_id": str(drift_event.id),
            "event_type": drift_event.event_type,
            "status": drift_event.status,
            "summary": drift_event.summary,
        },
        detected_at=datetime.now(UTC),
    )
    session.add(signal)
    await session.flush()
    return signal, True


async def _existing_dataset_drift_signal(
    session: AsyncSession,
    workspace: Workspace,
    drift_event: DatasetDriftEvent,
) -> Signal | None:
    signals = await list_signals(
        session,
        workspace.id,
        project_id=drift_event.project_id,
        signal_type="dataset_drift",
    )
    drift_event_id = str(drift_event.id)
    for signal in signals:
        metadata = signal.metadata_json if isinstance(signal.metadata_json, dict) else {}
        if metadata.get("drift_event_id") == drift_event_id:
            return signal
    return None


async def _dataset_version_anchor_task(
    session: AsyncSession,
    workspace: Workspace,
    version: DatasetVersion,
) -> tuple[TaskRun, CollectionTask]:
    for raw_id in version.source_task_run_ids:
        try:
            run_id = uuid.UUID(raw_id)
        except (TypeError, ValueError):
            continue
        task_run = await session.get(TaskRun, run_id)
        if task_run is None or task_run.workspace_id != workspace.id:
            continue
        task = await get_task(session, workspace.id, task_run.task_id)
        if task is None or task.project_id != version.project_id:
            continue
        return task_run, task
    raise CollectorError("dataset_drift_signal_bridge_lineage_missing")


async def _upsert_dataset_entity(
    *,
    session: AsyncSession,
    workspace: Workspace,
    dataset: Dataset,
    version: DatasetVersion,
    drift_event: DatasetDriftEvent,
) -> Entity:
    external_id = f"dataset:{dataset.id}"
    entity = await get_entity_by_external_id(session, workspace.id, "dataset", external_id)
    if entity is not None:
        return entity
    entity = Entity(
        workspace_id=workspace.id,
        project_id=dataset.project_id,
        entity_type="dataset",
        external_id=external_id,
        canonical_url=None,
        name=dataset.name,
        domain="ecommerce",
        latest_snapshot_id=None,
        first_seen_at=version.created_at,
        last_seen_at=drift_event.created_at,
    )
    session.add(entity)
    await session.flush()
    return entity


def _dataset_drift_signal_value(drift_event: DatasetDriftEvent) -> float:
    critical_tasks = _summary_number(drift_event.summary, "critical_tasks")
    missing_fields = _summary_number(drift_event.summary, "missing_field_tasks")
    return max(critical_tasks, missing_fields)


def _dataset_drift_signal_severity(status: str) -> str:
    if status == "critical":
        return "high"
    if status == "warning":
        return "medium"
    return "low"


def _summary_number(summary: dict[str, object], key: str) -> float:
    value = summary.get(key)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _blocked_reasons(page_structure: dict[str, object], selected_fields: list[str]) -> list[str]:
    blocked: list[str] = []
    if not selected_fields:
        blocked.append("未识别到可直接结构化保存的商品字段。")
    if page_structure.get("form_count", 0) and page_structure.get("product_schema_count", 0) == 0:
        blocked.append("页面包含表单且缺少 Product schema，需人工确认是否涉及登录态。")
    return blocked


def _blocked_batch_item(
    task_id: uuid.UUID,
    reason: str,
) -> AutomationProductBatchRunItemResponse:
    return AutomationProductBatchRunItemResponse(
        task_id=task_id,
        task_name=None,
        source_id=None,
        source_url=None,
        status="blocked",
        blocked_reason=reason,
        run=None,
        records_count=0,
        entities_count=0,
        field_completeness=None,
        error_message=None,
    )


def _blocked_batch_item_from_task(
    task: CollectionTask,
    reason: str,
) -> AutomationProductBatchRunItemResponse:
    return AutomationProductBatchRunItemResponse(
        task_id=task.id,
        task_name=task.name,
        source_id=task.source_id,
        source_url=_task_source_url(task),
        status="blocked",
        blocked_reason=reason,
        run=None,
        records_count=0,
        entities_count=0,
        field_completeness=None,
        error_message=None,
    )


def _schedule_task_block_reason(task: CollectionTask | None, dataset: Dataset) -> str | None:
    if task is None:
        return "task_not_found"
    if task.project_id != dataset.project_id:
        return "task_project_mismatch"
    if task.collector_type != "ecommerce_product_page":
        return "unsupported_collector_type"
    if task.status != "enabled":
        return "task_not_enabled"
    return None


def _drift_task_block_reason(
    task: CollectionTask | None,
    dataset: Dataset,
    version: DatasetVersion,
) -> str | None:
    reason = _schedule_task_block_reason(task, dataset)
    if reason is not None:
        return reason
    assert task is not None
    config = task.config or {}
    if config.get("approved_dataset_id") != str(dataset.id):
        return "task_dataset_lineage_unapproved"
    if config.get("approved_dataset_version_id") != str(version.id):
        return "task_dataset_lineage_unapproved"
    return None


def _blocked_drift_item(
    task_id: uuid.UUID,
    version: DatasetVersion,
    reason: str,
    task: CollectionTask | None = None,
) -> AutomationProductDriftItemResponse:
    return AutomationProductDriftItemResponse(
        task_id=task_id,
        task_name=task.name if task else None,
        source_url=_task_source_url(task) if task else None,
        status="blocked",
        blocked_reason=reason,
        latest_run_id=None,
        latest_run_status=None,
        dataset_version_completeness_percent=version.average_completeness_percent,
        latest_completeness_percent=None,
        completeness_drop_percent=None,
        missing_fields=[],
        new_missing_fields=[],
        freshness_target_hours=None,
        stale_hours=None,
        issues=[],
    )


def _approved_schedule_config(
    current_config: dict[str, object] | None,
    *,
    dataset: Dataset,
    version: DatasetVersion,
    payload: AutomationProductScheduleApproveRequest,
    approved_at: datetime,
) -> dict[str, object]:
    config = dict(current_config or {})
    config["schedule_policy"] = payload.schedule_policy
    config["freshness_target_hours"] = payload.freshness_target_hours
    config["approved_dataset_id"] = str(dataset.id)
    config["approved_dataset_version_id"] = str(version.id)
    config["schedule_approved_at"] = approved_at.isoformat()
    config["schedule_boundary"] = "approved_no_immediate_run"
    config["schedule_quality_gate"] = {
        "minimum_completeness_percent": payload.minimum_completeness_percent,
        "actual_completeness_percent": version.average_completeness_percent,
        "row_count": version.row_count,
        "selected_fields": version.selected_fields,
    }
    if payload.note:
        config["schedule_approval_note"] = payload.note
    else:
        config.pop("schedule_approval_note", None)
    return config


def _product_field_completeness(
    task: CollectionTask,
    raw_records: list[RawRecord],
) -> AutomationProductBatchFieldCompletenessResponse:
    configured_fields = _configured_product_fields(task)
    return _product_field_completeness_for_fields(raw_records, configured_fields)


def _product_field_completeness_for_fields(
    raw_records: list[RawRecord],
    configured_fields: list[str],
) -> AutomationProductBatchFieldCompletenessResponse:
    field_values: dict[str, object] = {}
    for raw_record in raw_records:
        extracted_fields = _raw_record_extracted_fields(raw_record)
        for field in configured_fields:
            if field in field_values:
                continue
            value = extracted_fields.get(field)
            if _has_field_value(value):
                field_values[field] = value

    extracted = [field for field in configured_fields if field in field_values]
    missing = [field for field in configured_fields if field not in field_values]
    ratio = len(extracted) / len(configured_fields) if configured_fields else 0
    return AutomationProductBatchFieldCompletenessResponse(
        configured_fields=configured_fields,
        extracted_fields=extracted,
        missing_fields=missing,
        field_values=field_values,
        completeness_ratio=round(ratio, 4),
        completeness_percent=round(ratio * 100),
    )


def _task_freshness_drift(
    task: CollectionTask,
    checked_at: datetime,
    freshness_grace_hours: int,
) -> tuple[int | None, float | None]:
    config = task.config or {}
    target = config.get("freshness_target_hours")
    freshness_target_hours = target if isinstance(target, int) else 24
    if task.last_run_at is None:
        return freshness_target_hours, None
    last_run_at = _aware_datetime(task.last_run_at)
    checked = _aware_datetime(checked_at)
    age_hours = (checked - last_run_at).total_seconds() / 3600
    stale_hours = max(age_hours - freshness_target_hours - freshness_grace_hours, 0)
    return freshness_target_hours, round(stale_hours, 2)


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _drift_status(issues: list[str]) -> str:
    critical_issues = {"latest_run_failed", "completeness_drift_exceeded"}
    if any(issue in critical_issues for issue in issues):
        return "critical"
    if issues:
        return "warning"
    return "ok"


def _product_drift_summary(
    requested_task_ids: list[uuid.UUID],
    items: list[AutomationProductDriftItemResponse],
) -> AutomationProductDriftSummaryResponse:
    checked_items = [item for item in items if item.status != "blocked"]
    blocked_items = [item for item in items if item.status == "blocked"]
    warning_items = [item for item in items if item.status == "warning"]
    critical_items = [item for item in items if item.status == "critical"]
    return AutomationProductDriftSummaryResponse(
        requested_tasks=len(requested_task_ids),
        checked_tasks=len(checked_items),
        blocked_tasks=len(blocked_items),
        warning_tasks=len(warning_items),
        critical_tasks=len(critical_items),
        stale_tasks=len([
            item
            for item in checked_items
            if item.stale_hours is not None and item.stale_hours > 0
        ]),
        missing_field_tasks=len([item for item in checked_items if item.new_missing_fields]),
        run_started=False,
        alert_created=False,
    )


def _drift_event_status(summary: AutomationProductDriftSummaryResponse) -> str:
    if summary.critical_tasks > 0:
        return "critical"
    if summary.warning_tasks > 0:
        return "warning"
    if summary.checked_tasks == 0 and summary.blocked_tasks > 0:
        return "blocked"
    if summary.blocked_tasks > 0:
        return "warning"
    return "ok"


def _dataset_response(dataset: Dataset | AutomationDatasetResponse) -> AutomationDatasetResponse:
    return AutomationDatasetResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        dataset_type=dataset.dataset_type,
        status=dataset.status,
        description=dataset.description,
    )


def _dataset_version_response(
    version: DatasetVersion | AutomationDatasetVersionResponse,
) -> AutomationDatasetVersionResponse:
    return AutomationDatasetVersionResponse(
        id=version.id,
        dataset_id=version.dataset_id,
        version_number=version.version_number,
        source_task_run_ids=version.source_task_run_ids,
        selected_fields=version.selected_fields,
        cleaning_script=version.cleaning_script,
        row_count=version.row_count,
        average_completeness_percent=version.average_completeness_percent,
        status=version.status,
        created_at=version.created_at,
        export_preview=version.export_preview,
    )


async def _get_dataset_and_version(
    session: AsyncSession,
    workspace: Workspace,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
) -> tuple[Dataset, DatasetVersion]:
    dataset = await get_dataset(session, workspace.id, dataset_id)
    if dataset is None:
        raise CollectorError("dataset_not_found")
    version = await get_dataset_version(session, workspace.id, dataset.id, version_id)
    if version is None:
        raise CollectorError("dataset_version_not_found")
    return dataset, version


def _dataset_export_job_response(
    export_job: DatasetExportJob,
    dataset: Dataset,
    version: DatasetVersion,
) -> AutomationProductDatasetExportJobResponse:
    download_url = None
    if export_job.status == "success":
        download_url = (
            f"/api/automation/product-datasets/{dataset.id}/versions/{version.id}"
            f"/exports/{export_job.id}/download"
        )
    return AutomationProductDatasetExportJobResponse(
        id=export_job.id,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        export_format=export_job.export_format,
        status=export_job.status,
        filename=export_job.filename,
        content_type=export_job.content_type,
        artifact_size_bytes=export_job.artifact_size_bytes,
        row_count=export_job.row_count,
        checksum_sha256=export_job.checksum_sha256,
        error_message=export_job.error_message,
        created_at=export_job.created_at,
        finished_at=export_job.finished_at,
        download_url=download_url,
        audit_events=export_job.audit_events,
        blocked_reasons=[
            "导出文件已写入受控目录；下载接口会再次校验当前账号的数据集权限。"
        ],
    )


def _dataset_export_root() -> Path:
    return Path(get_settings().dataset_export_dir).expanduser()


def _dataset_export_path(
    *,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    filename: str,
) -> Path:
    return (
        _dataset_export_root()
        / str(workspace_id)
        / str(dataset_id)
        / str(version_id)
        / filename
    ).resolve()


def _dataset_export_filename(
    dataset: Dataset,
    version: DatasetVersion,
    job_id: uuid.UUID,
    export_format: str,
) -> str:
    slug = _dataset_export_slug(dataset.name)
    return f"{slug}-v{version.version_number}-{str(job_id)[:8]}.{export_format}"


def _dataset_export_slug(value: str) -> str:
    characters: list[str] = []
    for character in value.lower():
        if character.isalnum():
            characters.append(character)
        elif characters and characters[-1] != "-":
            characters.append("-")
    slug = "".join(characters).strip("-")
    return slug[:80] or "dataset"


def _render_dataset_export(
    dataset: Dataset,
    version: DatasetVersion,
    export_format: str,
) -> bytes:
    rows = _dataset_export_rows(version)
    if export_format == "csv":
        return _render_dataset_csv(version, rows)
    if export_format == "jsonl":
        lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows]
        return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    payload = {
        "dataset": {
            "id": str(dataset.id),
            "project_id": str(dataset.project_id),
            "name": dataset.name,
            "dataset_type": dataset.dataset_type,
        },
        "version": {
            "id": str(version.id),
            "version_number": version.version_number,
            "selected_fields": version.selected_fields,
            "row_count": version.row_count,
            "average_completeness_percent": version.average_completeness_percent,
            "created_at": version.created_at.isoformat(),
        },
        "schema": version.export_preview.get("schema", {}),
        "rows": rows,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _dataset_export_rows(version: DatasetVersion) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for saved_row in version.rows:
        values = saved_row.get("values") if isinstance(saved_row, dict) else None
        if not isinstance(values, dict):
            values = {}
        row: dict[str, object] = {
            field: values.get(field)
            for field in version.selected_fields
        }
        row["row_id"] = saved_row.get("row_id")
        row["source_url"] = saved_row.get("source_url")
        row["task_run_id"] = saved_row.get("task_run_id")
        row["raw_record_id"] = saved_row.get("raw_record_id")
        row["missing_fields"] = saved_row.get("missing_fields", [])
        row["completeness_percent"] = saved_row.get("completeness_percent")
        rows.append(row)
    return rows


def _render_dataset_csv(version: DatasetVersion, rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO()
    fieldnames = [
        *version.selected_fields,
        "row_id",
        "source_url",
        "task_run_id",
        "raw_record_id",
        "missing_fields",
        "completeness_percent",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_export_value(row.get(field)) for field in fieldnames})
    return stream.getvalue().encode("utf-8")


def _csv_export_value(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _drift_event_response(
    event: DatasetDriftEvent,
    dataset: Dataset | AutomationDatasetResponse,
    version: DatasetVersion | AutomationDatasetVersionResponse,
) -> AutomationProductDriftEventResponse:
    summary = AutomationProductDriftSummaryResponse(**event.summary)
    return AutomationProductDriftEventResponse(
        id=event.id,
        created_at=event.created_at,
        dataset=_dataset_response(dataset),
        version=_dataset_version_response(version),
        event_type=event.event_type,
        status=event.status,
        thresholds=event.thresholds,
        summary=summary,
        items=[AutomationProductDriftItemResponse(**item) for item in event.items],
        audit_events=event.audit_events,
        note=event.note,
        run_started=summary.run_started,
        alert_created=summary.alert_created,
    )


def _configured_product_fields(task: CollectionTask) -> list[str]:
    config = task.config or {}
    configured = config.get("fields")
    if not isinstance(configured, list):
        return list(ECOMMERCE_PRODUCT_FIELDS)
    fields = [field for field in configured if isinstance(field, str)]
    allowed = set(ECOMMERCE_PRODUCT_FIELDS)
    normalized = [field for field in fields if field in allowed]
    return normalized or list(ECOMMERCE_PRODUCT_FIELDS)


def _raw_record_extracted_fields(raw_record: RawRecord) -> dict[str, object]:
    content = raw_record.content
    if not isinstance(content, dict):
        return {}
    extracted = content.get("extracted_fields")
    if not isinstance(extracted, dict):
        return {}
    return extracted


def _has_field_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return bool(value)
    return True


def _task_source_url(task: CollectionTask) -> str | None:
    config = task.config or {}
    url = config.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def _product_batch_summary(
    requested_task_ids: list[uuid.UUID],
    items: list[AutomationProductBatchRunItemResponse],
) -> AutomationProductBatchRunSummaryResponse:
    run_items = [item for item in items if item.status in {"run_completed", "run_failed"}]
    blocked_items = [item for item in items if item.status == "blocked"]
    successful = [
        item
        for item in run_items
        if item.run is not None and item.run.status in {"success", "partial_success"}
    ]
    failed = [item for item in run_items if item.run is not None and item.run.status == "failed"]
    completeness_values = [
        item.field_completeness.completeness_percent
        for item in run_items
        if item.field_completeness is not None
    ]
    average = (
        round(sum(completeness_values) / len(completeness_values))
        if completeness_values
        else 0
    )
    return AutomationProductBatchRunSummaryResponse(
        requested_tasks=len(requested_task_ids),
        run_tasks=len(run_items),
        blocked_tasks=len(blocked_items),
        successful_runs=len(successful),
        failed_runs=len(failed),
        records_count=sum(item.records_count for item in run_items),
        entities_count=sum(item.entities_count for item in run_items),
        average_completeness_percent=average,
        run_started=bool(run_items),
    )


def _dataset_fields(fields: list[str] | None) -> list[str]:
    requested = fields or list(ECOMMERCE_PRODUCT_FIELDS)
    allowed = set(ECOMMERCE_PRODUCT_FIELDS)
    normalized = [field for field in requested if field in allowed]
    return normalized or list(ECOMMERCE_PRODUCT_FIELDS)


def _dataset_row(
    raw_record: RawRecord,
    selected_fields: list[str],
) -> AutomationProductDatasetRowResponse:
    extracted_fields = _raw_record_extracted_fields(raw_record)
    values = {
        field: extracted_fields.get(field)
        for field in selected_fields
        if _has_field_value(extracted_fields.get(field))
    }
    missing_fields = [field for field in selected_fields if field not in values]
    ratio = len(values) / len(selected_fields) if selected_fields else 0
    return AutomationProductDatasetRowResponse(
        row_id=f"{raw_record.task_run_id}:{raw_record.id}",
        task_run_id=raw_record.task_run_id,
        raw_record_id=raw_record.id,
        source_url=raw_record.source_url,
        values=values,
        missing_fields=missing_fields,
        completeness_percent=round(ratio * 100),
    )


def _dataset_summary(
    requested_task_run_ids: list[uuid.UUID],
    matched_run_ids: set[uuid.UUID],
    rows: list[AutomationProductDatasetRowResponse],
    selected_fields: list[str],
) -> AutomationProductDatasetSummaryResponse:
    average = (
        round(sum(row.completeness_percent for row in rows) / len(rows))
        if rows
        else 0
    )
    return AutomationProductDatasetSummaryResponse(
        requested_runs=len(requested_task_run_ids),
        matched_runs=len(matched_run_ids),
        rows_count=len(rows),
        selected_fields=selected_fields,
        average_completeness_percent=average,
        export_format="json",
        export_ready=bool(rows),
    )


def _cleaning_script_draft(selected_fields: list[str]) -> list[str]:
    steps = [
        "drop rows where title is empty",
        "trim string fields and collapse repeated whitespace",
        "cast price to decimal when present",
        "normalize canonical_url and image_url as absolute URL strings",
        "keep missing values explicit as null for downstream review",
    ]
    if "currency" in selected_fields:
        steps.append("uppercase currency code when present")
    if "availability" in selected_fields:
        steps.append("map availability text into in_stock/out_of_stock/unknown")
    return steps


def _dataset_export_preview(
    rows: list[AutomationProductDatasetRowResponse],
    selected_fields: list[str],
) -> dict[str, object]:
    return {
        "format": "json",
        "schema": {
            "fields": selected_fields,
            "primary_key": "canonical_url",
            "missing_value_policy": "explicit_null",
        },
        "rows": [
            {
                field: row.values.get(field)
                for field in selected_fields
            }
            for row in rows[:10]
        ],
    }


async def _dataset_product_raw_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_ids: list[uuid.UUID],
    max_rows: int,
) -> list[RawRecord]:
    records: list[RawRecord] = []
    for task_run_id in task_run_ids:
        product_records, _reused_deduplicated_records = await _product_records_for_task_run(
            session=session,
            workspace_id=workspace_id,
            task_run_id=task_run_id,
            limit=max_rows,
        )
        records.extend(product_records)
        if len(records) >= max_rows:
            return records[:max_rows]
    return records


async def _product_records_for_task_run(
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_run_id: uuid.UUID,
    limit: int,
) -> tuple[list[RawRecord], bool]:
    raw_records = await list_raw_records(
        session=session,
        workspace_id=workspace_id,
        task_run_id=task_run_id,
        limit=limit,
    )
    product_records = _product_page_records(raw_records)
    if product_records:
        return product_records, False

    task_run = await session.get(TaskRun, task_run_id)
    if (
        task_run is None
        or task_run.workspace_id != workspace_id
        or task_run.status not in {"success", "partial_success"}
    ):
        return [], False
    task = await session.get(CollectionTask, task_run.task_id)
    if task is None or task.workspace_id != workspace_id:
        return [], False
    source_records = await list_raw_records(
        session=session,
        workspace_id=workspace_id,
        source_id=task.source_id,
        limit=limit,
    )
    fallback_records = _product_page_records(source_records)
    return fallback_records, bool(fallback_records)


def _product_page_records(raw_records: list[RawRecord]) -> list[RawRecord]:
    return [
        raw_record
        for raw_record in raw_records
        if raw_record.record_type == "ecommerce_product_page"
    ]


def _discovery_blocked_reasons(product_candidates: object) -> list[str]:
    if not isinstance(product_candidates, list) or not product_candidates:
        return ["未识别到可进入商品详情页采集的商品 URL。"]
    return []


def _fanout_fields(fields: list[str] | None) -> list[str]:
    requested = fields or list(ECOMMERCE_PRODUCT_FIELDS)
    allowed = set(ECOMMERCE_PRODUCT_FIELDS)
    normalized = [field for field in requested if field in allowed]
    return normalized or list(ECOMMERCE_PRODUCT_FIELDS)


def _candidate_block_reason(
    candidate_url: str | None,
    parent_origin: str,
    seen_urls: set[str],
    ready_count: int,
    max_sources: int,
) -> str | None:
    if candidate_url is None:
        return "candidate_url_invalid"
    if _origin(candidate_url) != parent_origin:
        return "candidate_url_cross_origin"
    if candidate_url in seen_urls:
        return "duplicate_candidate_url"
    if ready_count >= max_sources:
        return "candidate_exceeds_preview_limit"
    return None


def _normalize_candidate_url(value: str) -> str | None:
    cleaned, _fragment = urldefrag(value.strip())
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return cleaned


def _origin(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return None
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _fanout_source_name(title: str | None, url: str) -> str:
    display = title.strip() if isinstance(title, str) and title.strip() else urlparse(url).path
    return f"商品页采集：{display[:80]}"


def _fanout_blocked_reasons(
    source_drafts: list[AutomationSourceDraftResponse],
    blocked_count: int,
) -> list[str]:
    blocked: list[str] = []
    if not source_drafts:
        blocked.append("没有可预览的商品页采集源。")
    if blocked_count:
        blocked.append("部分候选 URL 被阻断，请复核后再创建批量任务。")
    blocked.append("当前结果仅为预览，尚未创建真实 Source、Task 或采集运行。")
    return blocked


def _draft_url(draft: AutomationSourceDraftResponse) -> str | None:
    value = draft.config.get("url")
    return value if isinstance(value, str) and value.strip() else None

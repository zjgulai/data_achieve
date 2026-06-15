from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.models.alert import AlertEvent, AlertRule
from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.report import Report
from data_intelligence_hub.models.signal import Signal
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace

TRAINING_NAMESPACE = uuid.UUID("f51bbf7e-40fa-49b7-9163-a59bb40b56cc")
DEMO_NAMESPACE = uuid.UUID("2df8a496-5ea6-49c3-8aef-9604ac8e6238")
TRAINING_SEED_VERSION = "2026-06-15-curated-training-v1"
DEFAULT_CURATION_PATH = Path("tmp/outputs/training-content-curation-20260615.json")
DEFAULT_SNAPSHOT_PATH = Path("tmp/outputs/training-content-snapshot-20260615.json")

TRAINING_PROJECT_KEYS = (
    "open-source-collection",
    "platform-methods",
    "agent-collection-ecosystem",
    "compliance-boundary",
)

TRAINING_SOURCE_IDS = (
    "github-topic-web-scraping",
    "github-topic-crawler",
    "github-topic-data-extraction",
    "github-topic-browser-automation",
    "github-topic-ai-agent",
    "github-topic-mcp-server",
    "github-topic-agent-framework",
    "github-topic-web-crawler",
    "github-topic-scraping",
    "github-topic-data-mining",
    "github-repo-scrapy",
    "github-repo-playwright",
    "github-repo-puppeteer",
    "github-repo-selenium",
    "github-repo-crawlee",
    "github-repo-crawlee-python",
    "github-repo-crawl4ai",
    "github-repo-firecrawl",
    "github-repo-browser-use",
    "github-repo-openai-agents-python",
    "github-repo-openai-agents-js",
    "github-repo-crewai",
    "github-repo-crewai-tools",
    "github-repo-mcp-servers",
    "github-repo-stagehand",
    "github-repo-langchain",
    "docs-github-rest",
    "docs-github-repos",
    "docs-scrapy-news",
    "docs-playwright",
    "docs-crawlee",
    "docs-crawl4ai",
    "docs-firecrawl",
    "docs-openai-agents",
    "docs-crewai-tools",
    "docs-mcp-intro",
    "method-github-public-api",
    "method-amazon-public-pages",
    "method-shopify-storefront",
    "method-reddit-public-api",
    "method-youtube-data-api",
    "method-tiktok-creative-center",
    "method-competitor-public-site",
    "method-compliance-boundary",
)

ATTENTION_SIGNAL_SOURCE_IDS = (
    "github-repo-langchain",
    "github-repo-firecrawl",
    "github-repo-browser-use",
    "github-repo-puppeteer",
    "github-repo-playwright",
    "github-repo-mcp-servers",
    "github-repo-crawl4ai",
    "github-repo-scrapy",
)
TOPIC_SIGNAL_SOURCE_IDS = (
    "github-topic-mcp-server",
    "github-topic-ai-agent",
    "github-topic-web-scraping",
    "github-topic-crawler",
)
RISK_SIGNAL_SOURCE_IDS = ("method-compliance-boundary",)
TRAINING_SIGNAL_SOURCE_IDS = (
    *ATTENTION_SIGNAL_SOURCE_IDS,
    *TOPIC_SIGNAL_SOURCE_IDS,
    *RISK_SIGNAL_SOURCE_IDS,
)
TRAINING_SIGNAL_IDS = (
    *(f"signal-attention-{source_id}" for source_id in ATTENTION_SIGNAL_SOURCE_IDS),
    *(f"signal-topic-coverage-{source_id}" for source_id in TOPIC_SIGNAL_SOURCE_IDS),
    "signal-risk-method-compliance-boundary",
)

TRAINING_INTELLIGENCE_EVIDENCE_SOURCE_IDS: dict[str, tuple[str, ...]] = {
    "intel-ai-ready-crawling-stack": (
        "github-repo-firecrawl",
        "github-repo-browser-use",
        "github-repo-crawl4ai",
    ),
    "intel-browser-automation-remains-core": (
        "github-repo-playwright",
        "github-repo-puppeteer",
        "github-repo-selenium",
        "docs-playwright",
    ),
    "intel-scrapy-remains-python-baseline": ("github-repo-scrapy", "docs-scrapy-news"),
    "intel-crawlee-bridges-crawler-production-patterns": (
        "github-repo-crawlee",
        "github-repo-crawlee-python",
        "docs-crawlee",
    ),
    "intel-agent-frameworks-need-tool-boundaries": (
        "github-repo-langchain",
        "github-repo-crewai",
        "docs-openai-agents",
        "docs-crewai-tools",
    ),
    "intel-mcp-source-connectors": (
        "github-repo-mcp-servers",
        "github-topic-mcp-server",
        "docs-mcp-intro",
    ),
    "intel-github-api-first-low-risk": (
        "github-topic-web-scraping",
        "github-topic-ai-agent",
        "docs-github-rest",
        "docs-github-repos",
    ),
    "intel-official-docs-need-parser-strategy": (
        "docs-github-repos",
        "docs-scrapy-news",
        "docs-openai-agents",
    ),
    "intel-ecommerce-method-boundary": (
        "method-amazon-public-pages",
        "method-shopify-storefront",
    ),
    "intel-social-collection-aggregate-only": (
        "method-reddit-public-api",
        "method-youtube-data-api",
        "method-tiktok-creative-center",
    ),
    "intel-competitor-public-site-monitoring": (
        "method-competitor-public-site",
        "docs-playwright",
    ),
    "intel-compliance-as-first-class-intelligence": ("method-compliance-boundary",),
    "intel-topic-map-guides-training-priority": (
        "github-topic-mcp-server",
        "github-topic-ai-agent",
        "github-topic-web-scraping",
    ),
    "intel-raw-evidence-trail-is-training-asset": (
        "docs-github-rest",
        "github-repo-scrapy",
        "method-github-public-api",
    ),
}

TRAINING_REPORT_IDS = ("report-training-intelligence-weekly-20260615",)
TRAINING_ALERT_IDS = (
    "alert-ai-agent-tool-attention",
    "alert-browser-automation-core",
    "alert-compliance-boundary-required",
)
TRAINING_NOTIFICATION_IDS = (
    "notification-training-report-ready",
    "notification-training-alerts-ready",
    "notification-training-evidence-ready",
)


@dataclass(frozen=True)
class TrainingSeedReport:
    dry_run: bool
    workspace_id: uuid.UUID
    counts: dict[str, int]
    curation_path: str
    snapshot_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "workspace_id": str(self.workspace_id),
            "counts": self.counts,
            "curation_path": self.curation_path,
            "snapshot_path": self.snapshot_path,
        }


def curated_training_ids() -> dict[str, list[uuid.UUID]]:
    entity_ids = [f"entity-{source_id}" for source_id in TRAINING_SOURCE_IDS]
    snapshot_ids = [
        *[_id(f"snapshot:{entity_id}:current") for entity_id in entity_ids],
        *[
            _id(f"snapshot:entity-{source_id}:previous")
            for source_id in TRAINING_SIGNAL_SOURCE_IDS
        ],
    ]
    return {
        "projects": [_id(f"project:{key}") for key in TRAINING_PROJECT_KEYS],
        "sources": [_id(f"source:{source_id}") for source_id in TRAINING_SOURCE_IDS],
        "tasks": [_id(f"task:{source_id}") for source_id in TRAINING_SOURCE_IDS],
        "task_runs": [_id(f"run:{source_id}") for source_id in TRAINING_SOURCE_IDS],
        "raw_records": [_id(f"raw:{source_id}") for source_id in TRAINING_SOURCE_IDS],
        "entities": [_id(f"entity:{entity_id}") for entity_id in entity_ids],
        "snapshots": snapshot_ids,
        "signals": [_id(f"signal:{signal_id}") for signal_id in TRAINING_SIGNAL_IDS],
        "intelligence": [
            _id(f"intelligence:{item_id}")
            for item_id in TRAINING_INTELLIGENCE_EVIDENCE_SOURCE_IDS
        ],
        "evidence": [
            _id(f"evidence:{item_id}:{source_id}")
            for item_id, source_ids in TRAINING_INTELLIGENCE_EVIDENCE_SOURCE_IDS.items()
            for source_id in source_ids
        ],
        "reports": [_id(f"report:{report_id}") for report_id in TRAINING_REPORT_IDS],
        "alert_rules": [_id(f"alert-rule:{alert_id}") for alert_id in TRAINING_ALERT_IDS],
        "alert_events": [_id(f"alert-event:{alert_id}") for alert_id in TRAINING_ALERT_IDS],
        "notifications": [
            _id(f"notification:{notification_id}")
            for notification_id in TRAINING_NOTIFICATION_IDS
        ],
    }


async def seed_training_content(
    *,
    curation_path: Path,
    snapshot_path: Path,
    execute: bool,
) -> TrainingSeedReport:
    curation = _load_json(curation_path)
    snapshot = _load_json(snapshot_path)
    _validate_payload(curation, snapshot)
    context = _build_context(curation, snapshot)
    async with async_session_factory() as session:
        await _require_demo_workspace(session)
        report = TrainingSeedReport(
            dry_run=not execute,
            workspace_id=_demo_id("workspace-main"),
            counts={
                "projects": len(context.projects),
                "sources": len(context.records),
                "collection_tasks": len(context.records),
                "task_runs": len(context.records),
                "raw_records": len(context.records),
                "entities": len(context.entities),
                "entity_snapshots": _snapshot_count(context),
                "signals": len(context.signals),
                "intelligence_items": len(context.intelligence_items),
                "evidences": sum(
                    len(item["evidence_source_ids"]) for item in context.intelligence_items
                ),
                "reports": 1,
                "alert_rules": len(context.alerts),
                "alert_events": len(context.alerts),
                "notifications": len(context.notifications),
            },
            curation_path=str(curation_path),
            snapshot_path=str(snapshot_path),
        )
        if not execute:
            return report

        await _merge_projects(session, context)
        await _merge_collection_layer(session, context)
        await _merge_entity_layer(session, context)
        await _merge_intelligence_layer(session, context)
        await _merge_report_alert_notification_layer(session, context)
        await session.commit()
        return report


@dataclass(frozen=True)
class TrainingContext:
    generated_at: datetime
    snapshot_generated_at: datetime
    projects: list[dict[str, Any]]
    records: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    intelligence_items: list[dict[str, Any]]
    report: dict[str, Any]
    alerts: list[dict[str, Any]]
    notifications: list[dict[str, Any]]


def _build_context(curation: dict[str, Any], snapshot: dict[str, Any]) -> TrainingContext:
    records = [record for record in snapshot["records"] if record.get("status") == "ok"]
    return TrainingContext(
        generated_at=_parse_datetime(curation["generated_at"]),
        snapshot_generated_at=_parse_datetime(snapshot["generated_at"]),
        projects=_require_list(curation, "projects"),
        records=records,
        entities=_require_list(curation, "entities"),
        signals=_require_list(curation, "signals"),
        intelligence_items=_require_list(curation, "intelligence_items"),
        report=_require_dict(curation, "report"),
        alerts=_require_list(curation, "alerts"),
        notifications=_require_list(curation, "notifications"),
    )


def _snapshot_count(context: TrainingContext) -> int:
    return len(context.entities) + len({str(signal["source_id"]) for signal in context.signals})


async def _require_demo_workspace(session: AsyncSession) -> None:
    user = await session.get(User, _demo_id("user-owner"))
    workspace = await session.get(Workspace, _demo_id("workspace-main"))
    if user is None or workspace is None:
        raise RuntimeError("curated demo workspace is missing; run demo_data seed first")


async def _merge_projects(session: AsyncSession, context: TrainingContext) -> None:
    items = [
        Project(
            id=_id(f"project:{project['key']}"),
            workspace_id=_demo_id("workspace-main"),
            name=str(project["name"]),
            description=str(project.get("description") or ""),
            domain=str(project["domain"]),
            status="active",
            owner_id=_demo_id("user-owner"),
            created_at=context.generated_at,
            updated_at=context.generated_at,
        )
        for project in context.projects
    ]
    await _merge_all(session, items)


async def _merge_collection_layer(session: AsyncSession, context: TrainingContext) -> None:
    source_items: list[Source] = []
    task_items: list[CollectionTask] = []
    run_items: list[TaskRun] = []
    raw_items: list[RawRecord] = []
    for record in context.records:
        source_id = str(record["source_id"])
        project_id = _id(f"project:{record['project_key']}")
        source_uuid = _id(f"source:{source_id}")
        task_uuid = _id(f"task:{source_id}")
        run_uuid = _id(f"run:{source_id}")
        raw_uuid = _id(f"raw:{source_id}")
        collected_at = _parse_datetime(str(record["collected_at"]))
        source_config = _source_config(record)
        source_items.append(
            Source(
                id=source_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=project_id,
                name=str(record["source_title"]),
                type=str(record["collector_type"]),
                url=_optional_text(record.get("source_url")),
                config=source_config,
                schedule_cron=None,
                enabled=True,
                created_at=context.generated_at,
                updated_at=context.generated_at,
            )
        )
        task_items.append(
            CollectionTask(
                id=task_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=project_id,
                source_id=source_uuid,
                collector_type=str(record["collector_type"]),
                name=f"{record['source_title']} training refresh",
                schedule_cron=None,
                status="enabled",
                config=source_config,
                success_count=1,
                failure_count=0,
                last_run_at=collected_at,
                created_at=context.generated_at,
                updated_at=context.generated_at,
            )
        )
        run_items.append(
            TaskRun(
                id=run_uuid,
                task_id=task_uuid,
                workspace_id=_demo_id("workspace-main"),
                status="success",
                started_at=collected_at,
                finished_at=collected_at,
                records_count=1,
                entities_count=1,
                error_message=None,
                error_traceback=None,
                logs=[
                    {
                        "step": "training_snapshot_imported",
                        "source_id": source_id,
                        "collector_type": record["collector_type"],
                    }
                ],
                created_at=collected_at,
            )
        )
        content = _raw_content(record)
        raw_items.append(
            RawRecord(
                id=raw_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=project_id,
                source_id=source_uuid,
                task_run_id=run_uuid,
                record_type=str(record["record_type"]),
                source_url=_optional_text(record.get("source_url")),
                content=content,
                content_hash=_content_hash(content),
                screenshot_url=None,
                collected_at=collected_at,
                created_at=collected_at,
            )
        )
    await _merge_all(session, source_items)
    await _merge_all(session, task_items)
    await _merge_all(session, run_items)
    await _merge_all(session, raw_items)


async def _merge_entity_layer(session: AsyncSession, context: TrainingContext) -> None:
    entity_items: list[Entity] = []
    snapshot_items: list[EntitySnapshot] = []
    signal_source_ids = {str(signal["source_id"]) for signal in context.signals}
    record_by_source = {str(record["source_id"]): record for record in context.records}
    for entity in context.entities:
        source_id = str(entity["source_id"])
        entity_uuid = _id(f"entity:{entity['id']}")
        record = record_by_source[source_id]
        captured_at = _parse_datetime(str(record["collected_at"]))
        entity_items.append(
            Entity(
                id=entity_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=_id(f"project:{entity['project_key']}"),
                entity_type=str(entity["entity_type"]),
                external_id=str(entity["external_id"]),
                canonical_url=_optional_text(entity.get("canonical_url")),
                name=str(entity["name"]),
                domain=str(entity["domain"]),
                latest_snapshot_id=None,
                first_seen_at=captured_at,
                last_seen_at=captured_at,
                created_at=context.generated_at,
                updated_at=context.generated_at,
            )
        )
        snapshot_items.append(
            _snapshot(
                entity=entity,
                source_id=source_id,
                label="current",
                captured_at=captured_at,
                metrics=_metrics(entity),
            )
        )
        if source_id in signal_source_ids:
            snapshot_items.append(
                _snapshot(
                    entity=entity,
                    source_id=source_id,
                    label="previous",
                    captured_at=captured_at,
                    metrics=_metrics(entity),
                )
            )
    await _merge_all(session, entity_items)
    await _merge_all(session, snapshot_items)
    for entity in context.entities:
        entity_row = await session.get(Entity, _id(f"entity:{entity['id']}"))
        if entity_row is not None:
            entity_row.latest_snapshot_id = _id(f"snapshot:{entity['id']}:current")
    await session.flush()

    signal_items = [
        Signal(
            id=_id(f"signal:{signal['id']}"),
            workspace_id=_demo_id("workspace-main"),
            project_id=_id(f"project:{signal['project_key']}"),
            entity_id=_id(f"entity:{signal['entity_id']}"),
            signal_type=str(signal["signal_type"]),
            previous_snapshot_id=_id(f"snapshot:{signal['entity_id']}:previous"),
            current_snapshot_id=_id(f"snapshot:{signal['entity_id']}:current"),
            current_value=_optional_float(signal.get("current_value")),
            previous_value=_optional_float(signal.get("previous_value")),
            delta=_optional_float(signal.get("delta")),
            delta_ratio=_optional_float(signal.get("delta_ratio")),
            confidence=float(signal["confidence"]),
            severity=str(signal["severity"]),
            metadata_json={
                **_require_dict(signal, "metadata"),
                "provenance": _provenance("signal"),
            },
            detected_at=context.snapshot_generated_at,
        )
        for signal in context.signals
    ]
    await _merge_all(session, signal_items)


def _snapshot(
    *,
    entity: dict[str, Any],
    source_id: str,
    label: str,
    captured_at: datetime,
    metrics: dict[str, Any],
) -> EntitySnapshot:
    return EntitySnapshot(
        id=_id(f"snapshot:{entity['id']}:{label}"),
        entity_id=_id(f"entity:{entity['id']}"),
        raw_record_id=_id(f"raw:{source_id}"),
        snapshot_data={
            "name": entity.get("name"),
            "summary": entity.get("summary"),
            "metrics": metrics,
            "snapshot_role": label,
            "provenance": _provenance("entity_snapshot"),
        },
        metrics=metrics,
        captured_at=captured_at,
        created_at=captured_at,
    )


async def _merge_intelligence_layer(session: AsyncSession, context: TrainingContext) -> None:
    signal_by_source_id = {str(signal["source_id"]): signal for signal in context.signals}
    items: list[IntelligenceItem] = []
    evidence_items: list[Evidence] = []
    for item in context.intelligence_items:
        scores = _require_dict(item, "scores")
        intelligence_uuid = _id(f"intelligence:{item['id']}")
        items.append(
            IntelligenceItem(
                id=intelligence_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=_id(f"project:{item['project_key']}"),
                title=str(item["title"]),
                summary=_intelligence_summary(item),
                intelligence_type=str(item["intelligence_type"]),
                status=str(item["status"]),
                impact_score=float(scores["impact"]) * 100,
                confidence_score=float(scores["confidence"]) * 100,
                novelty_score=float(scores["novelty"]) * 100,
                urgency_score=float(scores["urgency"]) * 100,
                final_score=float(scores["final"]) * 100,
                generated_by="rule",
                domain=str(item["domain"]),
                created_at=context.generated_at,
                updated_at=context.generated_at,
            )
        )
        for source_id in item["evidence_source_ids"]:
            signal = signal_by_source_id.get(str(source_id))
            evidence_items.append(
                Evidence(
                    id=_id(f"evidence:{item['id']}:{source_id}"),
                    intelligence_id=intelligence_uuid,
                    signal_id=_id(f"signal:{signal['id']}") if signal is not None else None,
                    entity_id=_id(f"entity:entity-{source_id}"),
                    raw_record_id=_id(f"raw:{source_id}"),
                    evidence_type="source",
                    title=f"{item['title']} evidence: {source_id}",
                    url=_evidence_url(item, str(source_id)),
                    excerpt=str(item["claim"])[:800],
                    highlighted_text=str(item["recommended_action"])[:500],
                    reference_metadata={
                        "source_id": source_id,
                        "dataset": "curated_training",
                        "seed_version": TRAINING_SEED_VERSION,
                    },
                    created_at=context.generated_at,
                )
            )
    await _merge_all(session, items)
    await _merge_all(session, evidence_items)


async def _merge_report_alert_notification_layer(
    session: AsyncSession,
    context: TrainingContext,
) -> None:
    report = context.report
    report_uuid = _id(f"report:{report['id']}")
    report_content = _report_content(report, context.intelligence_items)
    await _merge_all(
        session,
        [
            Report(
                id=report_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=None,
                report_type="weekly_training",
                title=str(report["title"]),
                content=report_content,
                status=str(report["status"]),
                period_start=_parse_date_as_datetime(str(report["period_start"])),
                period_end=_parse_date_as_datetime(str(report["period_end"])),
                created_at=context.generated_at,
            )
        ],
    )

    signal_by_id = {str(signal["id"]): signal for signal in context.signals}
    alert_rules: list[AlertRule] = []
    alert_events: list[AlertEvent] = []
    for alert in context.alerts:
        signal_id = str(alert["signal_ids"][0])
        signal = signal_by_id[signal_id]
        rule_uuid = _id(f"alert-rule:{alert['id']}")
        alert_rules.append(
            AlertRule(
                id=rule_uuid,
                workspace_id=_demo_id("workspace-main"),
                project_id=_id(f"project:{signal['project_key']}"),
                name=str(alert["title"]),
                signal_type=str(signal["signal_type"]),
                condition={
                    "dataset": "curated_training",
                    "severity": alert["severity"],
                    "recommended_action": alert["recommended_action"],
                },
                channel="in_app",
                enabled=True,
                created_at=context.generated_at,
            )
        )
        alert_events.append(
            AlertEvent(
                id=_id(f"alert-event:{alert['id']}"),
                rule_id=rule_uuid,
                signal_id=_id(f"signal:{signal_id}"),
                status=str(alert["status"]),
                payload={**alert, "provenance": _provenance("alert_event")},
                triggered_at=context.generated_at,
                sent_at=context.generated_at,
            )
        )
    await _merge_all(session, alert_rules)
    await _merge_all(session, alert_events)

    notification_items: list[Notification] = []
    for notification in context.notifications:
        notification_type = str(notification["type"])
        reference_type = "report" if notification_type != "alerts_ready" else "alert_event"
        reference_id = (
            report_uuid
            if reference_type == "report"
            else _id(f"alert-event:{context.alerts[0]['id']}")
        )
        notification_items.append(
            Notification(
                id=_id(f"notification:{notification['id']}"),
                user_id=_demo_id("user-owner"),
                title=str(notification["title"]),
                body=str(notification["message"]),
                notification_type=notification_type,
                reference_type=reference_type,
                reference_id=reference_id,
                is_read=False,
                created_at=context.generated_at,
            )
        )
    await _merge_all(session, notification_items)


async def _merge_all(session: AsyncSession, items: list[Any]) -> None:
    for item in items:
        await session.merge(item)
    await session.flush()


def _source_config(record: dict[str, Any]) -> dict[str, Any]:
    content = _require_dict(record, "content")
    config: dict[str, Any] = {
        "training_source_id": record["source_id"],
        "category": record["category"],
        "risk_level": record["risk_level"],
        "provenance": _provenance("source"),
    }
    collector_type = str(record["collector_type"])
    if collector_type == "github_repo":
        owner, repo = str(content["full_name"]).split("/", maxsplit=1)
        config.update({"owner": owner, "repo": repo})
    elif collector_type == "github_topic":
        config.update({"topic": content["topic"], "max_results": len(content["repositories"])})
    elif collector_type == "generic_web":
        config.update({"url": record["source_url"], "extract_mode": "main_content"})
    elif collector_type == "manual_json":
        config.update({"entity_type": content["entity_type"], "json_data": content["payload"]})
    return config


def _raw_content(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": record["source_id"],
        "source_title": record["source_title"],
        "category": record["category"],
        "risk_level": record["risk_level"],
        "collector_type": record["collector_type"],
        "content": record["content"],
        "provenance": _provenance("raw_record"),
    }


def _metrics(entity: dict[str, Any]) -> dict[str, Any]:
    metrics = entity.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _intelligence_summary(item: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"结论：{item['claim']}",
            f"影响：{item['impact']}",
            f"建议动作：{item['recommended_action']}",
            f"培训讲解：{item['training_talk_track']}",
            f"来源：{', '.join(item['evidence_urls'])}",
        ]
    )


def _report_content(report: dict[str, Any], intelligence_items: list[dict[str, Any]]) -> str:
    item_by_id = {item["id"]: item for item in intelligence_items}
    lines = [
        f"# {report['title']}",
        "",
        str(report["summary"]),
        "",
        "## 核心情报",
    ]
    for item_id in report["intelligence_ids"]:
        item = item_by_id[str(item_id)]
        lines.extend(
            [
                "",
                f"### {item['title']}",
                "",
                str(item["claim"]),
                "",
                f"- 影响：{item['impact']}",
                f"- 建议动作：{item['recommended_action']}",
                f"- 证据：{', '.join(item['evidence_urls'])}",
            ]
        )
    return "\n".join(lines)


def _evidence_url(item: dict[str, Any], source_id: str) -> str | None:
    source_ids = [str(value) for value in item["evidence_source_ids"]]
    if source_id not in source_ids:
        return None
    return str(item["evidence_urls"][source_ids.index(source_id)])


def _validate_payload(curation: dict[str, Any], snapshot: dict[str, Any]) -> None:
    if curation.get("dataset") != "curated_training":
        raise ValueError("curation dataset must be curated_training")
    if snapshot.get("dataset") != "curated_training":
        raise ValueError("snapshot dataset must be curated_training")
    if len(_require_list(snapshot, "records")) < 40:
        raise ValueError("snapshot must contain at least 40 records")
    if len(_require_list(curation, "intelligence_items")) < 12:
        raise ValueError("curation must contain at least 12 intelligence items")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _require_dict(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"field must be an object: {key}")
    return item


def _require_list(value: dict[str, Any], key: str) -> list[dict[str, Any]]:
    item = value.get(key)
    if not isinstance(item, list):
        raise ValueError(f"field must be a list: {key}")
    return [entry for entry in item if isinstance(entry, dict)]


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_date_as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _content_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _provenance(layer: str) -> dict[str, str]:
    return {
        "data_layer": layer,
        "dataset": "curated_training",
        "seed_version": TRAINING_SEED_VERSION,
        "source": "data_intelligence_hub.training_content",
    }


def _id(key: str) -> uuid.UUID:
    return uuid.uuid5(TRAINING_NAMESPACE, f"data-achieve-training:{key}")


def _demo_id(key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"data-achieve-demo:{key}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed curated training content.")
    parser.add_argument(
        "--curation-path",
        type=Path,
        default=Path(os.getenv("SCRAPY_TRAINING_CURATION_PATH", DEFAULT_CURATION_PATH)),
    )
    parser.add_argument(
        "--snapshot-path",
        type=Path,
        default=Path(os.getenv("SCRAPY_TRAINING_SNAPSHOT_PATH", DEFAULT_SNAPSHOT_PATH)),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write curated training content. Without this flag, the command is dry-run.",
    )
    args = parser.parse_args()
    report = asyncio.run(
        seed_training_content(
            curation_path=args.curation_path,
            snapshot_path=args.snapshot_path,
            execute=args.execute,
        )
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
